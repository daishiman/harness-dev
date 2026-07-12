#!/usr/bin/env python3
# /// script
# name: hook-guard-skillgen
# purpose: skill-intake 実行中にスキル生成 (run-skill-create / run-build-skill / capability-build) が
#          Skill / Task / Bash 経由で起動されるのをハーネス強制で 100% ブロックする機械バリア。
#          LLM の指示遵守に依存しない。
# inputs:
#   - stdin: hook JSON ({hook_event_name, tool_name, tool_input, cwd, ...})
# outputs:
#   - exit: 0=許可 / 2=ブロック(stderrに理由)。例外時は graceful に 0 (可用性優先)。
# contexts: [E]
# network: false
# write-scope: eval-log/intake-locks/ (intake 実行中フラグ lock のみ)
# dependencies: []
# requires-python: ">=3.11"
# ///
"""skill-intake 実行中フラグ (lock) を用いた、スキル生成のハーネス強制ブロック。

設計 (elegant-review 3 analyst 収束結論):
  プロンプト/SKILL.md の禁止文 (PR #28) は LLM の確率的遵守 (<100%) でしか効かない。
  「100 人中 100 人が intake を実行しても harness-creator が 100% 起動しない」を満たすのは、
  tool 呼び出しを必ず仲介する PreToolUse hook で exit 2 する **ハーネス強制層** のみ
  (制御反転: 信頼するな、仲介点で塞げ)。

lock ライフサイクル (作成も解除もモデル非依存 = hook 駆動):
  - PreToolUse  / Skill(run-skill-intake) → lock 作成 (intake 開始)
  - PreToolUse  / Skill|Task|Bash(生成スキル) → lock 有効なら exit 2 (intake 実行中の生成を遮断)
  - PreToolUse  / Bash(lock 削除・移動)     → lock 有効なら exit 2 (lock 改ざんによる遮断回避を封鎖)
  - PostToolUse / Skill(intake skill)      → lock 削除 (intake 正常終了。外側スキルの Post は
                                              intake 全 phase 完了時に発火するため、lock は
                                              intake 実行中ずっと有効)
  - SessionEnd                              → lock 削除 (セッション終了 backstop)
  - Stop                                    → 解除しない。Stop は応答ターン毎に発火しうるため、
                                              intake が複数ターンに跨ると途中で lock を早期解除し
                                              以降の生成が素通る fail-open を招く (F-LOOP-01)。
  - TTL 失効                                → 古い lock は無視+削除 (dangling 防止・fail-open)

誤爆ゼロの根拠:
  - intake の 11 phase 子委譲 (run-intake-* / skill-intake-*) は denylist 非該当 → 素通し。
  - intake 非実行時 (lock 無/失効) は生成スキルも素通し → 通常の run-skill-create 単独起動を妨げない。
  - 将来 run-skill-create が intake を内包しても、lock は「run-skill-intake が stack 上にある間」
    だけ有効なため、intake 戻り後の正規生成は通る。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# intake 実行中フラグ。現行 orchestrator で lock を立てる。
INTAKE_SKILLS = {
    "run-skill-intake",
}

# 遮断対象 (Skill 名 / Task subagent_type を suffix 一致で判定)
DENY_TARGETS = {
    "run-skill-create",
    "run-build-skill",
    "capability-build",
    "run-build-skill-subagent",  # Task 経由の生成 worker
}
DENY_COMMAND_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:/)?("
    + "|".join(re.escape(target) for target in sorted(DENY_TARGETS))
    + r")(?![A-Za-z0-9_-])"
)

# lock ファイル自体の削除・移動を Bash 経由で行う回避路を遮断する (paradox attack_path_1)。
# 例: `rm eval-log/intake-locks/intake-active.lock` を打って lock を消し生成を素通させる。
LOCK_TAMPER_RE = re.compile(
    r"\b(?:rm|unlink|mv|rmdir|shred|truncate|trash)\b[^\n]*intake-(?:active\.lock|locks)"
)

LOCK_RELPATH = Path("eval-log") / "intake-locks" / "intake-active.lock"
LOCK_TTL_SECONDS = 6 * 60 * 60  # intake はユーザー対話を含み長時間化しうる。失効で dangling を断つ。

BLOCK_MESSAGE = (
    "[hook-guard-skillgen] BLOCKED: skill-intake (ヒアリング) 実行中はスキル生成を起動できません。\n"
    "  intake はヒアリング〜Notion 公開〜next-action 推奨までで完結します。\n"
    "  スキルを実際に作成する場合は intake 完了後にユーザーが別途明示的に\n"
    "  run-skill-create を起動してください (これは意図された独立アクションです)。\n"
)

LOCK_TAMPER_MESSAGE = (
    "[hook-guard-skillgen] BLOCKED: skill-intake 実行中に intake lock の削除・移動はできません。\n"
    "  lock を消すと生成遮断が無効化されます。intake は正常終了 (PostToolUse) /\n"
    "  セッション終了 / TTL 失効で自動解除されます。手動削除は不要かつ不可です。\n"
)


def _suffix(name: str) -> str:
    """'harness-creator:run-skill-create' / 'run-skill-create' いずれも 'run-skill-create' に正規化。"""
    if not isinstance(name, str):
        return ""
    return name.split(":", 1)[1] if ":" in name else name


def _lock_path(payload: dict) -> Path:
    # CLAUDE_PROJECT_DIR (プロジェクト固定根) を最優先にする。cwd は SubAgent 起動や
    # `cd` 後の Bash で揺れ、lock の「書き先」と「読み先」が分裂して fail-open する (F-STRAT-01)。
    base = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(base) / LOCK_RELPATH


def _lock_active(lock: Path) -> bool:
    """lock が存在し失効していなければ True。失効していれば削除して False (fail-open)。"""
    try:
        if not lock.is_file():
            return False
        data = json.loads(lock.read_text(encoding="utf-8"))
        if time.time() > float(data.get("expires_at", 0)):
            _remove_lock(lock)  # stale → 自動掃除
            return False
        return True
    except Exception:
        return False  # 解釈不能な lock は無効扱い (可用性優先)


def _create_lock(lock: Path) -> None:
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        lock.write_text(
            json.dumps({
                "intake_skill": "run-skill-intake",
                "intake_skills": sorted(INTAKE_SKILLS),
                "created_at": now,
                "expires_at": now + LOCK_TTL_SECONDS,
            }),
            encoding="utf-8",
        )
    except Exception as exc:
        # lock 作成失敗でも intake 自体は止めない (可用性優先) が、保証層が無効化された
        # 事実は黙殺せず警告する。これ以降 intake 実行中でも生成遮断が効かない状態になる。
        sys.stderr.write(
            f"[hook-guard-skillgen] WARN: intake lock の作成に失敗しました ({exc}). "
            "この間スキル生成の機械遮断は効きません。\n"
        )


def _remove_lock(lock: Path) -> None:
    try:
        lock.unlink(missing_ok=True)
    except Exception:
        pass


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
    except Exception:
        return 0  # 解釈不能入力は素通し (可用性優先・既存 hook と同方針)

    event = payload.get("hook_event_name", "")
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input", {}) or {}
    lock = _lock_path(payload)

    # --- SessionEnd: セッション終了 backstop でのみ解除 ---
    # Stop は応答ターン毎に発火しうる。intake は AskUserQuestion を挟み複数ターンに跨るため、
    # Stop で解除すると intake 途中で lock が消え以降の生成が素通る (F-LOOP-01)。Stop では解除しない。
    if event == "SessionEnd":
        _remove_lock(lock)
        return 0
    if event == "Stop":
        return 0

    # --- PostToolUse: intake 正常終了で lock 解除 ---
    if event == "PostToolUse":
        if tool == "Skill" and _suffix(
            ti.get("skill") or ti.get("skill_name") or ti.get("name") or ""
        ) in INTAKE_SKILLS:
            _remove_lock(lock)
        return 0

    # --- PreToolUse: lock 作成 / 生成遮断 ---
    if event == "PreToolUse" or tool in ("Skill", "Task", "Bash"):
        if tool == "Skill":
            target = _suffix(ti.get("skill") or ti.get("skill_name") or ti.get("name") or "")
        elif tool == "Task":
            target = _suffix(ti.get("subagent_type") or "")
        elif tool == "Bash":
            command = ti.get("command") or ti.get("cmd") or ""
            # lock 改ざん (削除/移動) による遮断回避を最優先で封鎖する。
            if LOCK_TAMPER_RE.search(command) and _lock_active(lock):
                sys.stderr.write(LOCK_TAMPER_MESSAGE)
                return 2
            match = DENY_COMMAND_RE.search(command)
            target = match.group(1) if match else ""
        else:
            return 0

        # intake 開始 → lock 作成 (モデル非依存でフラグを立てる)
        if tool == "Skill" and target in INTAKE_SKILLS:
            _create_lock(lock)
            return 0

        # intake 実行中の生成起動 → ハーネス強制ブロック
        if target in DENY_TARGETS and _lock_active(lock):
            sys.stderr.write(BLOCK_MESSAGE)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

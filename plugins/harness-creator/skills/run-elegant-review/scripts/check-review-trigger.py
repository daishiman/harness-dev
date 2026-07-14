#!/usr/bin/env python3
# 発火: Stop hook (Claude Code, plugin.json の Stop matcher 経由)
# 副作用境界: git は read-only (status/diff の参照のみ)。queue は append-only。exit は常に 0
#            (Stop の継続/停止判断は stdout の {"decision":"block"} JSON で行い exit code では行わない)。
# 想定 input: {"session_id": ..., "stop_hook_active": bool, ...} 形式 JSON(stdin 空でも落ちない)。
# 出力1 (推奨): 変更ファイル合計が 20 件以上なら run-elegant-review 起動を stdout 推奨。
# 出力2 (queue): 評価要求を eval-log/review-queue.jsonl へ 1 行 append
#         (content-review-protocol.md「hook 発火と queue」の queue を実体化。診断ログであり自動 consumer は無い)。
# 出力3 (確実起動 / decision:block): 他プラグインに未評価 or stale な変更 skill が残る場合、
#         Stop を block し Claude 本体へ「既定は focused combined review 1 context、
#         exhaustive 明示時だけ run-elegant-review + rubric evaluator」と差し戻す。
#         フック自身は重い LLM を実行しない(=protocol の原則を維持)。トリガのみ行い、実行は Claude 本体。
# 出力4 (self 通知): 自プラグイン (dogfooding) の pending は block 除外のため完全無音だった。
#         Stop 時に stdout 通知のみ出す (block はしない)。強制は CI/pre-push の lint-content-review.py。
#
# 三層防御 (確実性の担保):
#   1) 通知層: 変更件数に応じ run-elegant-review を stdout 推奨 (情報提供)。
#   2) トリガ層 (このフックの出力3): 未評価/stale が残る Stop を decision:block で差し戻し評価を実起動。
#      安全弁=stop_hook_active ガード(無限ループ防止)/ harness-creator 自身は除外 / env HARNESS_CREATOR_NO_REVIEW_BLOCK=1 で opt-out。
#   3) 強制層 (最終担保): lint-content-review.py が pre-push / CI gate で verdict の
#      存在・PASS・SHA 一致を強制する。フックを抜けても CI が block するため確実性が最終保証される。
"""Stop hook。変更量から run-elegant-review を推奨・queue 化し、未評価が残れば decision:block で評価を実起動する."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# dogfooding 除外境界の正本は repo-root scripts/feedback_contract_ssot.py (単一 SSOT)。
# 散在していた制御リテラル "harness-creator" を排除し、Stop block 除外判定を SSOT 述語へ委譲する。
#
# このローダは Stop/Edit/Write/Skill フックから import-time に実行されるため **絶対に raise しない**。
# raise すると単独 install (plugin だけを marketplace から install) 時に plugin 外 repo-root の
# SSOT が見つからず import 時クラッシュし、全フックが exit≠0 で落ちる ("exit は常に 0" の設計と矛盾)。
# 解決順: (a) env CLAUDE_PLUGIN_ROOT/scripts → (b) 上方探索 (vendored plugin 内コピーを dev/install 双方で発見)
# → (c) 全滅時は最小 fallback。vendored コピー (plugins/harness-creator/scripts/) が常在するため
# fallback は実質 dead code (多層防御の最終安全弁)。
def _load_feedback_contract_ssot():
    """feedback_contract_ssot を fail-soft に解決する (絶対に raise しない)。"""
    import importlib.util

    candidates: list[Path] = []
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidates.append(Path(plugin_root) / "scripts" / "feedback_contract_ssot.py")
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidates.append(ancestor / "scripts" / "feedback_contract_ssot.py")
    for cand in candidates:
        try:
            if cand.is_file():
                spec = importlib.util.spec_from_file_location("feedback_contract_ssot", cand)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                return mod
        except Exception:
            continue
    return _fallback_feedback_contract_ssot()


def _fallback_feedback_contract_ssot():
    """SSOT 全滅時の最小 fallback。check-review-trigger が実際に使う述語のみ提供。

    自プラグイン名を __file__ パス (plugins/<self>/skills/<skill>/scripts/) から
    導出し、判定用リテラルを直書きせず変数比較する (dogfooding 境界判定は
    「対象が自プラグイン自身か」であり、self-derive が意味的にも正しい)。SSOT 実装と
    同値のため drift せず、散在リテラル禁止 (test_dogfooding_boundary) も満たす。
    vendored コピーが常在するため通常ここには到達しない (多層防御の最終安全弁)。
    """
    import types

    self_plugin = Path(__file__).resolve().parents[3].name
    fc = types.SimpleNamespace()
    fc.SELF_DOGFOODING_PLUGIN = self_plugin
    fc.is_stop_block_exempt = lambda plugin: plugin == self_plugin
    return fc


_FC = _load_feedback_contract_ssot()

# 後方互換エイリアス: 値は SSOT 由来 (リテラル直書きではない)。production の判定は
# _FC.is_stop_block_exempt() を使い、この名前は外部参照 (テスト fixture 等) 向けに残す。
SELF_EXCLUDED_PLUGIN = _FC.SELF_DOGFOODING_PLUGIN

THRESHOLD = 20

# git 変更にこれらに該当するパスが含まれれば、件数 20 未満でも評価要求を enqueue する
# (セマンティック判定: 評価対象 artifact が触られたら確実に再評価キューへ載せる)。
SEMANTIC_BASENAMES = ("rubric.json", "workflow-manifest.json")
QUEUE_RELPATH = os.path.join("eval-log", "review-queue.jsonl")

# 自己ブロック除外: 生成器自身の変更は Stop decision:block の対象にしない。
# CI/pre-push の content-review lint では dogfooding 対象にするが、編集中セッションを
# 自己ブロックすると改善不能になるため Stop hook だけ安全弁として除外する。
# 除外判定は SSOT 述語 _FC.is_stop_block_exempt() に委譲 (リテラル散在を排除)。
# 評価結果 (verdict) の保存先ファイル名 (content-review-protocol.md と一致)。
REQUIRED_VERDICTS = ("elegance-verdict.json", "rubric-verdict.json")


def _read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def _git_repo_root() -> str | None:
    """queue / verdict の基準ルートを解決する。

    (a) git rev-parse が成功すればその repo root (dev での従来挙動を維持)。
    (b) 失敗時 (git 外 / 単独 install) は env CLAUDE_PLUGIN_ROOT を基準にする。
        CLAUDE_PLUGIN_ROOT は plugin ディレクトリを指すため、eval-log を
        その配下へ self-relative に落とし、**無関係なユーザ cwd を汚染しない**。
    (c) どちらも無ければ None を返し、呼び出し側で queue 書込を silent skip する
        (append-only 副作用境界の宣言と整合・exit 0 維持)。
    旧実装は失敗時 os.getcwd() を返し、ユーザの作業ディレクトリに
    eval-log/review-queue.jsonl を生成しうる副作用漏れがあった。
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        root = proc.stdout.strip()
        if proc.returncode == 0 and root:
            return root
    except Exception:
        pass
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root and os.path.isdir(plugin_root):
        return plugin_root
    return None


def _changed_paths() -> list[str]:
    """git status --porcelain と diff --name-only を read-only で参照し変更パス集合を返す."""
    paths: set[str] = set()
    # 1) ワークツリー / index の変更 (porcelain は "XY path" 形式・rename は "->" 含む)
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                # 先頭 3 文字は status コード+空白。以降がパス (rename は "old -> new")。
                payload = line[3:] if len(line) > 3 else line
                if " -> " in payload:
                    payload = payload.split(" -> ", 1)[1]
                payload = payload.strip().strip('"')
                if payload:
                    paths.add(payload)
    except Exception:
        pass
    # 2) HEAD との diff (commit 済みだが未 push の変更も拾う・best-effort)
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                p = line.strip()
                if p:
                    paths.add(p)
    except Exception:
        pass
    return sorted(paths)


def _is_skill_md(path: str) -> bool:
    """plugins/*/skills/*/SKILL.md に該当するか (深さは問わずファイル名+配置で判定)。"""
    norm = path.replace("\\", "/")
    return norm.startswith("plugins/") and "/skills/" in norm and norm.endswith("/SKILL.md")


def _semantic_changed_paths(paths: list[str]) -> list[str]:
    """評価対象 artifact (SKILL.md / rubric.json / workflow-manifest.json) のみ抽出。"""
    hits: list[str] = []
    for p in paths:
        norm = p.replace("\\", "/")
        base = norm.rsplit("/", 1)[-1]
        if _is_skill_md(norm) or base in SEMANTIC_BASENAMES:
            hits.append(norm)
    return sorted(set(hits))


def _last_queue_changed_set(queue_path: str) -> set | None:
    """直近 queue 行の changed_skills セットを返す (冪等判定用)。読めなければ None。"""
    try:
        if not os.path.exists(queue_path):
            return None
        last = None
        with open(queue_path, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line
        if not last:
            return None
        rec = json.loads(last)
        return set(rec.get("changed_skills") or [])
    except Exception:
        return None


def _enqueue(queue_path: str, reason: str, changed_skills: list[str]) -> bool:
    """評価要求を append-only で 1 行追記。冪等スキップ時 / 失敗時は False。"""
    try:
        new_set = set(changed_skills)
        # 冪等: 直近行と同一 changed_skills セットなら追記しない (queue 肥大防止)。
        prev = _last_queue_changed_set(queue_path)
        if prev is not None and prev == new_set:
            return False
        record = {
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "changed_skills": changed_skills,
            "trigger": "Stop",
        }
        os.makedirs(os.path.dirname(queue_path), exist_ok=True)
        with open(queue_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def _parse_plugin_skill(skill_md_path: str) -> tuple[str | None, str | None]:
    """plugins/<plugin>/skills/<skill>/SKILL.md から (plugin, skill) を抽出。"""
    parts = skill_md_path.replace("\\", "/").split("/")
    try:
        i = parts.index("plugins")
        j = parts.index("skills", i + 1)
        return parts[i + 1], parts[j + 1]
    except (ValueError, IndexError):
        return None, None


def _sha256_file(abs_path: str) -> str | None:
    try:
        with open(abs_path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _verdict_recorded_sha(root: str, plugin: str, skill: str, fname: str) -> tuple[str | None, bool]:
    """(target.skill_md_sha256, ファイル存在) を返す。読めなければ (None, False)。"""
    p = os.path.join(root, "eval-log", plugin, skill, "content-review", fname)
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return (data.get("target", {}) or {}).get("skill_md_sha256"), True
    except (OSError, json.JSONDecodeError, ValueError):
        return None, False


def _pending_review_targets(root: str, semantic_paths: list[str], exempt: bool) -> list[str]:
    """変更 SKILL.md のうち、verdict が欠落 or SHA 不一致 (stale) の skill を返す。

    exempt=False: Stop block 対象 (自プラグイン dogfooding は除外済)。
    exempt=True: 自プラグインのみ (block はせず stdout 通知にのみ使う)。
    """
    pending: list[str] = []
    for path in semantic_paths:
        if not _is_skill_md(path):
            continue
        plugin, skill = _parse_plugin_skill(path)
        if not plugin or not skill:
            continue
        if bool(_FC.is_stop_block_exempt(plugin)) != exempt:
            continue
        current = _sha256_file(os.path.join(root, path))
        for fname in REQUIRED_VERDICTS:
            recorded, exists = _verdict_recorded_sha(root, plugin, skill, fname)
            if not exists or not recorded or (current and recorded != current):
                pending.append(f"{plugin}/{skill}")
                break
    return sorted(set(pending))


def _unevaluated_or_stale(root: str, semantic_paths: list[str]) -> list[str]:
    """Stop block 対象の pending (自プラグインは除外)。既存契約を維持する薄い wrapper。
    生成器自身は Stop block では除外 (自己ブロック回避)。CI/pre-push では対象。
    """
    return _pending_review_targets(root, semantic_paths, exempt=False)


def main() -> int:
    try:
        inp = _read_stdin_json()
        hook_event = str(
            inp.get("hook_event_name")
            or inp.get("event_name")
            or inp.get("event")
            or inp.get("hook")
            or ""
        )
        is_stop_event = not inp or hook_event in {"Stop", "stop"}
        paths = _changed_paths()
        count = len(paths)
        semantic = _semantic_changed_paths(paths)
        root = _git_repo_root()

        # --- 出力2: queue 化 ---
        # 発火条件: (a) 変更件数が閾値以上、または (b) 評価対象 artifact を含む (件数 20 未満でも)。
        # root が None (git 外 / plugin root 不明) のときは無関係な cwd を汚さないため silent skip。
        if root and (count >= THRESHOLD or semantic):
            if semantic:
                reason = (
                    f"評価対象 artifact の変更を検出 ({len(semantic)} 件): "
                    + ", ".join(semantic[:5])
                    + ("…" if len(semantic) > 5 else "")
                )
            else:
                reason = f"git 変更ファイルが {count} 件 (閾値 {THRESHOLD})"
            queue_path = os.path.join(root, QUEUE_RELPATH)
            _enqueue(queue_path, reason, semantic)

        # --- 出力3: 評価の確実起動 (decision:block で Claude 本体に評価を実行させる) ---
        # 安全弁: (1) stop_hook_active 継続中は再 block しない (無限ループ防止)、
        #         (2) env HARNESS_CREATOR_NO_REVIEW_BLOCK=1 で opt-out、
        #         (3) harness-creator 自身の変更は対象外 (_unevaluated_or_stale 内で除外)。
        # 重い LLM はここでは実行しない。未評価/stale が残るなら Stop を差し戻し評価を促す (トリガのみ)。
        if (
            root
            and is_stop_event
            and not inp.get("stop_hook_active")
            and os.environ.get("HARNESS_CREATOR_NO_REVIEW_BLOCK") != "1"
        ):
            pending = _unevaluated_or_stale(root, semantic)
            if pending:
                shown = ", ".join(pending[:8]) + (" …" if len(pending) > 8 else "")
                sys.stdout.write(
                    json.dumps(
                        {
                            "decision": "block",
                            "reason": (
                                f"未評価 or stale な変更 skill が {len(pending)} 件あります: {shown}。"
                                "停止前に各対象へ assign-skill-design-evaluator の focused combined review "
                                "(4条件+rubric、1 context・再評価1回まで) を実行し、"
                                "eval-log/<plugin>/<skill>/content-review/{elegance,rubric}-verdict.json を保存してください "
                                "(skill_md_sha256 を現在の SKILL.md と一致させる)。"
                                "30思考法の run-elegant-review + 独立rubric evaluator は "
                                "verification_profile=exhaustive を明示した場合だけ実行します。"
                                "意図的にスキップする場合のみ環境変数 HARNESS_CREATOR_NO_REVIEW_BLOCK=1 を設定。"
                            ),
                        },
                        ensure_ascii=False,
                    )
                )
                return 0

        # --- 出力4: self-plugin 通知 (block はしない・1 分岐) ---
        # 自プラグイン (dogfooding) の pending は Stop block から除外され (自己ブロック回避)、
        # 従来はセッション内で完全無音のまま pre-push/CI で一括顕在化していた。
        # block 分岐が return した後にのみ到達するため decision JSON と混ざらない。
        if root and is_stop_event:
            self_pending = _pending_review_targets(root, semantic, exempt=True)
            if self_pending:
                shown = ", ".join(self_pending[:8]) + (" …" if len(self_pending) > 8 else "")
                sys.stdout.write(
                    json.dumps(
                        {
                            "hook": "check-review-trigger",
                            "notice": "self-plugin content-review pending",
                            "pending_skills": self_pending,
                            "reason": (
                                f"{_FC.SELF_DOGFOODING_PLUGIN} 自身の変更 skill が未評価 or stale です"
                                f" ({len(self_pending)} 件): {shown}。Stop は妨げませんが、push 前に"
                                " content-review verdict を再生成してください"
                                " (pre-push/CI の lint-content-review.py が強制します)。"
                            ),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        # --- 出力1: stdout 推奨 (block しない場合のみ・既存挙動を維持) ---
        if count >= THRESHOLD:
            sys.stdout.write(
                json.dumps(
                    {
                        "hook": "check-review-trigger",
                        "recommendation": "run-elegant-review",
                        "changed_files": count,
                        "threshold": THRESHOLD,
                        "reason": f"git status の変更ファイルが {count} 件 (閾値 {THRESHOLD})",
                    },
                    ensure_ascii=False,
                )
            )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

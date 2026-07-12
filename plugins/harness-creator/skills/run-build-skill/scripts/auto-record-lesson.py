#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""auto-record-lesson.py

Claude Code Hook input (JSON via stdin) を解釈し、失敗パターンが検出された場合に
plugins/harness-creator/lessons-learned/ 配下へ構造化 lesson を追記する。
新規 lesson の追記と同時に knowledge/knowledge-lessons-index.json へ最小索引
エントリを append する (Loop B: 索引の description 宣言と実装の真実合わせ)。

記録条件 (genuine 文脈最少条件):
    tool 名 + 対象ヒント (command / file_path / path / skill) + tool_response 内の
    失敗シグネチャが揃った入力のみ記録する。無関係キーに失敗語が紛れただけの
    断片 (テスト副産物・引用の混入) は記録しない。

副作用境界:
    - lessons-learned ディレクトリと、その sibling knowledge/ 索引への書き込みのみ。
    - git・他ディレクトリには触れない。

exit_code 仕様 (Claude Code Hooks 準拠):
    0  非ブロック (正常 / 失敗未検出 / 書き込み成功)
    2  明示拒否 (本 hook は使用しない)
    その他 非ブロック警告

想定発火イベント:
    - PostToolUse:Skill
    - PostToolUse:Edit (rubric.json 等)
    - Stop
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# --- 失敗検出パターン ---------------------------------------------------------
# tool_response / stderr / messages 内に現れる代表的な失敗シグネチャ。
_FAILURE_PATTERNS = [
    re.compile(r"\bFAIL(ED|URE)?\b", re.IGNORECASE),
    re.compile(r"\bERROR\b", re.IGNORECASE),
    re.compile(r"\bTraceback\b"),
    re.compile(r"\bvalidator\b.*\bFAIL", re.IGNORECASE),
    re.compile(r"\bnon-?zero exit\b", re.IGNORECASE),
    re.compile(r"\bexit (?:code|status)\s*[:=]?\s*[1-9]\d*", re.IGNORECASE),
]

# severity 推定: 強いキーワードがあれば high、それ以外は medium。
_HIGH_SEVERITY_HINTS = re.compile(
    r"\b(FATAL|CRITICAL|Traceback|validator FAIL)\b", re.IGNORECASE
)

# capability 推定 (tool 名から大雑把に分類)。
_CAPABILITY_MAP = {
    "Edit": "edit",
    "Write": "write",
    "Bash": "shell",
    "Skill": "skill-invoke",
    "Read": "read",
}


def _plugin_root() -> Path:
    # このスクリプトは plugins/harness-creator/skills/run-build-skill/scripts/ 配下。
    # 4 つ上って plugins/harness-creator (= plugin-root)。
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


def _state_fallback_root() -> Path:
    """plugin-root が書込不能な install (read-only / 次回 update で消失) 用の退避先。

    手本: notifier-check.py の `Path.home()/.cache/harness` (user 領域退避)。
    優先順: $CLAUDE_PROJECT_DIR → $XDG_STATE_HOME → ~/.claude/state。
    いずれも harness-creator/ サブディレクトリに隔離する。
    """
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project:
        return Path(project) / ".claude" / "state" / "harness-creator"
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".claude" / "state"
    return base / "harness-creator"


def _lessons_dir() -> Path:
    """lessons-learned の書込先。env override > plugin-root (既定・dogfooding 互換)。

    plugin-root を既定に保つことで maintainer の読取フロー (lessons-learned/ 直読み)
    を壊さない。read-only install での fallback は呼び出し側 (_write_lesson) が担う。
    """
    override = os.environ.get("HARNESS_CREATOR_LESSONS_DIR")
    if override:
        return Path(override).resolve()
    return _plugin_root() / "lessons-learned"


def _dir_is_writable(d: Path) -> bool:
    """d (存在しなければ最寄りの既存祖先) が書込可能かを実 mkdir/touch せず判定。"""
    probe = d
    while not probe.exists():
        if probe.parent == probe:
            return False
        probe = probe.parent
    return os.access(probe, os.W_OK)


def _read_hook_input() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 不正入力も非ブロックで握りつぶす (hook の sla)。
        return {}


def _flatten_text(payload: Any) -> str:
    """payload 内の文字列を再帰的に抽出して結合 (失敗パターン走査用)。"""
    bucket: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            bucket.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(payload)
    return "\n".join(bucket)


def _detect_failure(text: str) -> bool:
    return any(p.search(text) for p in _FAILURE_PATTERNS)


def _has_genuine_context(hook: Any) -> bool:
    """genuine 文脈最少条件: 何がどう失敗したか追跡できる入力のみ記録を許可する。

    条件 = tool 名 + 対象ヒント (command / file_path / path / skill) +
    tool_response 内の失敗シグネチャ。失敗語が tool_response 以外の無関係キーに
    紛れただけの断片 ("ERROR boom" 型ノイズ) は human triage 不能なため封鎖する。
    """
    if not isinstance(hook, dict):
        return False
    tool = hook.get("tool_name") or hook.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        return False
    ti = hook.get("tool_input")
    if not isinstance(ti, dict):
        return False
    if not any(
        isinstance(ti.get(k), str) and ti.get(k).strip()
        for k in ("file_path", "path", "skill", "command")
    ):
        return False
    return _detect_failure(_flatten_text(hook.get("tool_response")))


def _estimate_severity(text: str) -> str:
    return "high" if _HIGH_SEVERITY_HINTS.search(text) else "medium"


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "lesson"


def _extract_slug(hook: dict[str, Any], text: str) -> str:
    tool = hook.get("tool_name") or hook.get("tool") or "event"
    event = hook.get("hook_event_name") or hook.get("event") or "post"
    # tool_input から file_path 等のヒントを拾う。
    ti = hook.get("tool_input") or {}
    hint = ""
    if isinstance(ti, dict):
        for k in ("file_path", "path", "skill", "command"):
            v = ti.get(k)
            if isinstance(v, str) and v:
                hint = Path(v).name if k.endswith("path") else v
                break
    base = f"{event}-{tool}-{hint}" if hint else f"{event}-{tool}"
    return _slugify(base)[:60]


def _build_entry(hook: dict[str, Any], text: str, severity: str) -> dict[str, str]:
    tool = str(hook.get("tool_name") or hook.get("tool") or "unknown")
    event = str(hook.get("hook_event_name") or hook.get("event") or "unknown")
    capability = _CAPABILITY_MAP.get(tool, "unknown")
    # 観測サマリ: 先頭の失敗一致行を 240 文字以内で。
    observation = ""
    for line in text.splitlines():
        if _detect_failure(line):
            observation = line.strip()[:240]
            break
    if not observation:
        observation = "(失敗シグネチャは検出されたが該当行抽出に失敗)"
    return {
        "date": _dt.date.today().isoformat(),
        "trigger_event": event,
        "tool": tool,
        "severity": severity,
        "capability": capability,
        "observation": observation,
    }


def _render_markdown(entry: dict[str, str]) -> str:
    fm_lines = [
        "---",
        f"date: {entry['date']}",
        f"trigger_event: {entry['trigger_event']}",
        f"tool: {entry['tool']}",
        f"severity: {entry['severity']}",
        f"capability: {entry['capability']}",
        "---",
        "",
        "## observation",
        "",
        entry["observation"],
        "",
        "## hypothesis",
        "",
        "(自動記録: 失敗パターンを検出。根本原因は要 human triage)",
        "",
        "## proposed_action",
        "",
        "- 当該 capability に対する rubric 強化 / validator 追加を検討",
        "- 再現条件を別 issue に起票",
        "",
    ]
    return "\n".join(fm_lines)


def _upsert_lesson(path: Path, entry: dict[str, str]) -> None:
    """同日同 slug は新規 observation を追記 (upsert)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_render_markdown(entry), encoding="utf-8")
        return
    # 追記モード: 既存ファイル末尾に observation セクションを足す。
    appended = [
        "",
        f"## observation ({_dt.datetime.now().isoformat(timespec='seconds')})",
        "",
        entry["observation"],
        "",
    ]
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(appended))


_INDEX_ID_RE = re.compile(r"lessons-index_(\d+)$")


def _lessons_index_path(lessons_dir: Path) -> Path:
    """lessons 書込先の sibling knowledge/ 配下の索引パス。

    既定 (lessons_dir = plugin-root/lessons-learned) では
    plugin-root/knowledge/knowledge-lessons-index.json (正本) を指す。
    fallback/override 時は同じ相対関係で書込先ローカルの索引になる。
    """
    return lessons_dir.parent / "knowledge" / "knowledge-lessons-index.json"


def _index_source_file(lesson_path: Path) -> str:
    """索引 source.file は repo 相対 (既存エントリと同形)。相対化不能なら絶対のまま。"""
    try:
        repo_root = _plugin_root().parent.parent
        return lesson_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (ValueError, OSError):
        return lesson_path.as_posix()


def _append_index_entry(index_path: Path, lesson_path: Path, entry: dict[str, str]) -> bool:
    """lesson md 追記と同時に索引へ最小エントリを決定論 append する (冪等)。

    knowledge-lessons-index.json:description の宣言「auto-record-lesson.py が
    新規 lesson を追記したら本索引にもエントリを追加する」の実装。
    同一 source.file は再登録しない (md 側は observation 追記で対応済)。
    索引書込失敗は lesson 記録を巻き込まない (best-effort, False で握る)。
    """
    source_file = _index_source_file(lesson_path)
    try:
        if index_path.exists():
            data = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return False
        else:
            data = {
                "category": "lessons-index",
                "label": "lessons-learned 索引 (失敗ログへのポインタ)",
                "source_note": "本文は lessons-learned/*.md が正本。本索引は検索ヒット用の最小要約のみ持つ。",
                "items": [],
            }
        items = data.setdefault("items", [])
        if not isinstance(items, list):
            return False
        max_seq = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            if (item.get("source") or {}).get("file") == source_file:
                return False
            m = _INDEX_ID_RE.match(str(item.get("id", "")))
            if m:
                max_seq = max(max_seq, int(m.group(1)))
        items.append(
            {
                "id": f"lessons-index_{max_seq + 1:03d}",
                "title": (
                    f"[auto] {entry['trigger_event']}:{entry['tool']} 失敗 — "
                    f"{entry['observation'][:80]}"
                ),
                "keywords": [
                    entry["trigger_event"],
                    entry["tool"],
                    entry["capability"],
                    entry["severity"],
                ],
                "message": "自動記録。根本原因の human triage 後に title/message を書き直す。",
                "source": {"file": source_file, "type": "lesson", "date": entry["date"]},
            }
        )
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return True
    except Exception:
        return False


def _candidate_dirs() -> list[Path]:
    """書込先候補を優先順で返す (3 段 fallback)。

    (a) 既定 = plugin-root 配下 lessons-learned/ (dev 既存挙動・dogfooding 読取互換)
    (b) plugin-root が書込不能なら user state 領域 (~/.claude/state or $CLAUDE_PROJECT_DIR)
    env `HARNESS_CREATOR_LESSONS_DIR` が明示されればそれを単独で使う (override)。
    """
    if os.environ.get("HARNESS_CREATOR_LESSONS_DIR"):
        return [_lessons_dir()]
    return [_lessons_dir(), _state_fallback_root() / "lessons-learned"]


def main() -> int:
    hook = _read_hook_input()
    text = _flatten_text(hook)
    if not text or not _detect_failure(text):
        # サイレント正常終了。
        return 0
    if not _has_genuine_context(hook):
        # 文脈不足の断片ノイズは記録しない (genuine 文脈最少条件)。
        return 0
    severity = _estimate_severity(text)
    slug = _extract_slug(hook, text)
    today = _dt.date.today().isoformat()
    entry = _build_entry(hook, text, severity)
    filename = f"{today}-{slug}.md"

    # 3 段 fallback: 書込可能な最初の候補へ。全滅なら (c) silent no-op exit 0。
    last_exc: OSError | None = None
    for base in _candidate_dirs():
        if not _dir_is_writable(base):
            continue
        try:
            _upsert_lesson(base / filename, entry)
            sys.stderr.write(f"[auto-record-lesson] recorded -> {base / filename}\n")
            index_path = _lessons_index_path(base)
            if _append_index_entry(index_path, base / filename, entry):
                sys.stderr.write(f"[auto-record-lesson] indexed -> {index_path}\n")
            return 0
        except OSError as exc:
            last_exc = exc
            continue
    # どこにも書けない (read-only install 等): クラッシュさせず no-op で握る。
    if last_exc is not None:
        sys.stderr.write(f"[auto-record-lesson] no writable sink, skipped: {last_exc}\n")
    else:
        sys.stderr.write("[auto-record-lesson] no writable sink, skipped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# /// script
# name: live-trial-status
# purpose: claude transcript JSONL からセッション状態を 4 状態 (WAITING_USER_INPUT/BUSY_TOOL_RUNNING/BUSY_GENERATING/IDLE_TURN_COMPLETE) に分類する。
# inputs:
#   - argv: <session-jsonl-path> [--self-test]
# outputs:
#   - stdout: "STATE:<state> PENDING:<tool名csv|-> LAST_TS:<ISO|-> BYTES:<n>"
#   - exit: 0=判定成功 / 3=ファイル不在・空・parse不能 (呼び出し側は TUI fallback)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""transcript JSONL (~/.claude/projects/<proj>/<session-id>.jsonl) の状態分類器。

ターン終端マーカー (system subtype=turn_duration) と pending tool_use
(assistant の tool_use id 集合 − user の tool_result tool_use_id 集合) で
4 状態に分類する。スキーマの実測根拠は同 skill の references/transcript-jsonl.md
(版依存につき spec-drift 監視対象)。

移植忠実性 (AG live-trial-status.sh 由来):
- 順序判定は配列 index で行う (compact 後に timestamp 非単調の実例あり)。
- busy 中の jsonl は完全無音 (長 Bash で 200s 級) — 経過時間で busy 判定しない。
- fork (Skill/Agent) 内の長時間実行は main jsonl 無音のまま進む —
  transcript_bytes() が subagents/*.jsonl を合算し poll の STALL 誤報を防ぐ。
- kill/crash したセッションは BUSY_GENERATING のまま凍結 (turn_duration が
  書かれない) — tmux 生存確認 (backend.has_session) が最終 fallback。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 対話 gate として扱う pending ツール (AskUserQuestion 実測 / ExitPlanMode 同型推測)
GATE_TOOLS = {"AskUserQuestion", "ExitPlanMode"}

STATE_WAITING = "WAITING_USER_INPUT"
STATE_BUSY_TOOL = "BUSY_TOOL_RUNNING"
STATE_BUSY_GEN = "BUSY_GENERATING"
STATE_IDLE = "IDLE_TURN_COMPLETE"


def _content_items(entry: dict) -> list:
    content = (entry.get("message") or {}).get("content")
    return content if isinstance(content, list) else []


def _content_text(entry: dict) -> str:
    return str((entry.get("message") or {}).get("content", ""))


def _is_real_prompt(entry: dict) -> bool:
    if entry.get("type") != "user":
        return False
    if entry.get("isMeta") is True or entry.get("isCompactSummary") is True:
        return False
    content = (entry.get("message") or {}).get("content")
    has_text = isinstance(content, str) or any(
        isinstance(c, dict) and c.get("type") == "text" for c in _content_items(entry)
    )
    if not has_text:
        return False
    text = _content_text(entry)
    if "[Request interrupted" in text:
        return False
    if "<command-name>" in text or "<local-command" in text:
        return False
    return True


def _is_turn_end(entry: dict) -> bool:
    # Esc 中断は turn_duration を出さず "[Request interrupted" の user 行を残す —
    # これも終端扱いにしないと永久 busy 誤判定 (transcript-jsonl.md interrupt 例外)。
    if entry.get("subtype") == "turn_duration":
        return True
    return "[Request interrupted" in _content_text(entry)


def load_events(path: Path) -> list[dict] | None:
    """1 行 1 JSON を読み timestamp 付きイベントのみ返す。不在/空/全行 parse 不能は None。"""
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not raw.strip():
        return None
    events: list[dict] = []
    parsed_any = False
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed_any = True
        # メタ状態イベント (mode/file-history-snapshot 等) は timestamp を持たず判定外
        if isinstance(obj, dict) and obj.get("timestamp"):
            events.append(obj)
    if not parsed_any:
        return None
    return events


def classify_events(events: list[dict]) -> dict:
    uses: list[dict] = []
    result_ids: set[str] = set()
    last_prompt = -1
    last_end = -1
    for idx, entry in enumerate(events):
        etype = entry.get("type")
        if etype == "assistant":
            for item in _content_items(entry):
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    uses.append({"id": item.get("id"), "name": item.get("name")})
        elif etype == "user":
            for item in _content_items(entry):
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    result_ids.add(item.get("tool_use_id"))
        if _is_real_prompt(entry):
            last_prompt = idx
        if _is_turn_end(entry):
            last_end = idx
    pending = [u["name"] for u in uses if u["id"] not in result_ids]
    if any(name in GATE_TOOLS for name in pending):
        state = STATE_WAITING
    elif last_prompt > last_end:
        state = STATE_BUSY_TOOL if pending else STATE_BUSY_GEN
    else:
        state = STATE_IDLE
    last_ts = events[-1].get("timestamp") if events else None
    return {"state": state, "pending": pending, "last_ts": last_ts}


def classify(path: Path) -> dict | None:
    events = load_events(path)
    if events is None:
        return None
    return classify_events(events)


def transcript_bytes(path: Path) -> int:
    """main jsonl + subagents/*.jsonl の bytes 合算 (fork 内長時間実行の STALL 誤報対策)。"""
    total = path.stat().st_size if path.is_file() else 0
    sub_dir = path.with_suffix("") / "subagents"
    if sub_dir.is_dir():
        for p in sub_dir.glob("*.jsonl"):
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _mk(entries: list[dict]) -> list[dict]:
    for i, e in enumerate(entries):
        e.setdefault("timestamp", f"2026-07-02T00:00:{i:02d}Z")
    return entries


def _self_test() -> int:
    prompt = {"type": "user", "message": {"content": "run the task"}}
    turn_end = {"type": "system", "subtype": "turn_duration"}
    ask = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t1", "name": "AskUserQuestion"}]}}
    bash_use = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t2", "name": "Bash"}]}}
    bash_result = {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t2"}]}}

    assert classify_events(_mk([dict(prompt), dict(ask)]))["state"] == STATE_WAITING
    assert classify_events(_mk([dict(prompt), dict(bash_use)]))["state"] == STATE_BUSY_TOOL
    assert classify_events(_mk([dict(prompt)]))["state"] == STATE_BUSY_GEN
    assert classify_events(
        _mk([dict(prompt), dict(bash_use), dict(bash_result), dict(turn_end)])
    )["state"] == STATE_IDLE
    # interrupt 例外: turn_duration なしでも終端扱い
    interrupted = {"type": "user", "message": {"content": "[Request interrupted by user]"}}
    assert classify_events(_mk([dict(prompt), dict(interrupted)]))["state"] == STATE_IDLE
    print("OK: live-trial-status self-test (4 状態 + interrupt 例外)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("jsonl", nargs="?", help="transcript jsonl path")
    ap.add_argument("--self-test", action="store_true")
    ns = ap.parse_args(argv)
    if ns.self_test:
        return _self_test()
    if not ns.jsonl:
        ap.print_usage(sys.stderr)
        return 2
    path = Path(ns.jsonl)
    result = classify(path)
    if result is None:
        return 3
    pending = ",".join(str(n) for n in result["pending"]) if result["pending"] else "-"
    print(
        f"STATE:{result['state']} PENDING:{pending} "
        f"LAST_TS:{result['last_ts'] or '-'} BYTES:{transcript_bytes(path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

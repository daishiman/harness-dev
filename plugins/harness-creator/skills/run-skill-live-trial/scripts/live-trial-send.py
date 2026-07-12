#!/usr/bin/env python3
# /// script
# name: live-trial-send
# purpose: タスクをファイル経由 (load-buffer + paste-buffer) で trial セッションに渡し、着手を確認する。
# inputs:
#   - argv: <session> <taskfile>
#   - env: SESSION_ID (jsonl 一次判定用, optional) / CLAUDE_PROJECTS_DIR ($HOME/.claude/projects)
# outputs:
#   - stdout: "SENT (着手確認): <session>" / WARN
#   - exit: 0=着手確認 / 1=着手未確認 (Enter 不達の可能性) / 2=usage / 3=BLOCKED (tmux 不在)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""タスク本文を「ファイル経由」で安全に渡す (絶対ルール: 送信はファイル経由)。

長文/改行/括弧を send-keys で生送信すると TUI のペースト検知で誤動作する。
タスク本文はファイルに置き、セッションへは「そのファイルを読んで実行」の短い
1 行を tmux load-buffer + paste-buffer で貼り付ける (バッファ経由はキー入力の
逐次解釈を避けられるため、send-keys 生送信より改行/括弧に頑健)。

着手確認は二層: env SESSION_ID があれば「transcript jsonl の出現 + user 行に
taskfile パス」を一次判定 (transcript は初 prompt 送信時に生成されるので、
出現自体が prompt 受理の証拠)。TUI capture の busy 検知は fallback。
"""
from __future__ import annotations

import argparse
import glob as globmod
import importlib.util
import os
import re
import sys
import tempfile
import time
from pathlib import Path

# TUI fallback の着手マーカー。旧 AG 版の知見: BSD grep はマルチバイト (… ✻ 等) が
# 不安定で ASCII 限定を強いられたが、Python re は Unicode 安全なので … も判定に使える。
# 完了サマリ " for Ns" / スピナー / esc to interrupt のいずれかで「着手した」とみなす。
_STARTED_RE = re.compile(r"…|esc to interrupt| for [0-9]+m? ?[0-9]*s")


def _load_sibling(stem: str):
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jsonl_accepted(projects_dir: str, session_id: str, abs_taskfile: str) -> bool:
    """jsonl が出現し user 行 (prompt) に taskfile パスが含まれるか (一次判定)。"""
    for p in globmod.glob(os.path.join(projects_dir, "*", f"{session_id}.jsonl")):
        try:
            text = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if abs_taskfile in line and '"type":"user"' in line.replace(" ", ""):
                return True
    return False


def main(argv: list[str] | None = None, backend=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session")
    ap.add_argument("taskfile")
    ns = ap.parse_args(argv)

    if backend is None:  # テストは fake backend を注入できる (tmux 非依存)
        backend = _load_sibling("live-trial-backend")
    if not backend.valid_session_name(ns.session):
        print(f"[ERROR] invalid session name: {ns.session}", file=sys.stderr)
        return 2
    taskfile = Path(ns.taskfile)
    if not taskfile.is_file():
        print(f"[ERROR] taskfile not found: {taskfile}", file=sys.stderr)
        return 2
    backend.require_tmux()

    session_id = os.environ.get("SESSION_ID", "")
    projects_dir = os.environ.get(
        "CLAUDE_PROJECTS_DIR", str(Path.home() / ".claude" / "projects")
    )
    # パスを絶対化 (別 cwd のセッションでも Read できるように)
    abs_path = str(taskfile.resolve())
    instruction = (
        "次のファイルに書かれたタスクを読み、その指示どおりに実行してください。"
        f"余計な確認は返さず即着手: {abs_path}"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write(instruction)
        tmp = fh.name
    try:
        backend.paste_file(ns.session, tmp)
    finally:
        Path(tmp).unlink(missing_ok=True)
    time.sleep(1)

    # boot 直後の TUI は Enter を取りこぼすことがある。「着手した」を検知するまで
    # Enter を再送する。着手を検知したら必ず止める — 過剰な Enter は完了後の画面を撹乱する。
    for _ in range(3):
        backend.send_keys(ns.session, "Enter")
        time.sleep(3)
        if session_id and jsonl_accepted(projects_dir, session_id, abs_path):
            print(f"SENT (着手確認): {ns.session}")
            return 0
        cap = backend.capture_pane(ns.session)
        if _STARTED_RE.search(cap):
            print(f"SENT (着手確認): {ns.session}")
            return 0
    print(f"WARN: {ns.session} の着手を確認できない (Enter 不達の可能性)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

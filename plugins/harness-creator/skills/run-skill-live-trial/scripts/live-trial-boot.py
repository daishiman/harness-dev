#!/usr/bin/env python3
# /// script
# name: live-trial-boot
# purpose: 隔離 claude セッションを tmux 上で起動し READY まで待つ (session UUID 固定で transcript を決定的に引けるようにする)。
# inputs:
#   - argv: <session> <cwd> [--model M] [--session-id UUID] [--target-skill plugin:skill] [--self-test]
#   - env: BOOT_TIMEOUT(90) BOOT_GRACE(3) — テスト高速化用。通常は触らない
# outputs:
#   - stdout: "READY: <session> (Ns) MODEL:<model|default> SESSION_ID:<uuid>" / BOOT_FAIL / TIMEOUT
#   - exit: 0=READY / 1=BOOT_FAIL・TIMEOUT / 2=usage・denylist / 3=BLOCKED (tmux 不在)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""本物の claude を別 tmux プロセスで起動する (fork subagent では自走/入れ子/hook が再現できないため)。

- model 省略/空 = ユーザー既定 model。指定時は claude コマンド行に --model を焼き込む
  (env 継承は tmux 越しに不確実なためコマンドライン焼き込みが唯一確実)。
- 注意: claude は --model を起動時検証しない (実測 v2.1.173: 不正 model でも READY まで
  到達し初 turn でエラー)。BOOT_FAIL が捕まえるのは claude 不在 / 即 crash のみ —
  実走 model の検証は live-trial-verdict.py の transcript 機械 gate で行う。
- --session-id で transcript を ~/.claude/projects/*/<uuid>.jsonl に決定的に固定する
  (transcript は初 prompt 送信時に生成されるため READY 検知自体は TUI capture で行う)。
- trial の workdir (task.md / out/ / verdict) は eval-log/<plugin>/<skill>/live-trial/<run-id>/
  固定 (SKILL.md 準備局面参照)。旧 AG 版の $HOME/playground fallback / .mso は全廃。
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import time
import uuid
from pathlib import Path

_MODEL_RE = re.compile(r"^[A-Za-z0-9._-]+$")  # send-keys 焼き込みのため shell 安全文字のみ
_READY_RE = re.compile(r"bypass permissions|for shortcuts|❯ ")
# pane_current_command 実測: claude (native binary) 起動中は版数文字列 (node とは限らない)
# → whitelist でなく shell blacklist (+ 空 = tmux 消失) 固定で判定。ワイルドカード不使用
# (`*sh` は ssh 等を誤爆)。blacklist 外 shell (tcsh/ksh/nu/pwsh) では BOOT_FAIL も READY
# 偽陽性 guard も無効 → TIMEOUT へ縮退 (安全側)。
_SHELL_BLACKLIST = {"zsh", "bash", "sh", "fish", "dash", ""}


def _load_sibling(stem: str):
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_claude_command(session_id: str, model: str) -> str:
    # trust 済み project 前提。多数のツール呼びを止めないため bypass で起動
    cmd = f"claude --session-id {session_id} --dangerously-skip-permissions"
    if model:
        cmd += f" --model {model}"
    return cmd


def _tail(text: str, n: int = 15) -> str:
    return "\n".join(text.splitlines()[-n:])


def boot(backend, session: str, cwd: str, model: str, session_id: str,
         timeout: int, grace: int) -> int:
    backend.new_session(session, cwd)
    backend.send_line(session, build_claude_command(session_id, model))
    for i in range(1, timeout + 1):
        cap = backend.capture_pane(session)
        cmd = backend.pane_current_command(session)
        at_shell = cmd in _SHELL_BLACKLIST
        # READY = 「READY パターン + 前面プロセスが shell でない」の AND
        # (shell prompt の ❯ で偽 READY しない)
        if not at_shell and _READY_RE.search(cap):
            print(f"READY: {session} ({i}s) MODEL:{model or 'default'} SESSION_ID:{session_id}")
            return 0
        # 死亡検出: claude が即死 (claude 不在 / 即 crash) すると前面プロセスが shell に戻る
        if at_shell and i > grace:
            print(f"BOOT_FAIL: claude exited before ready ({i}s)")
            print("--- capture tail ---")
            print(_tail(cap))
            backend.kill_session(session)
            return 1
        time.sleep(1)
    print(f"TIMEOUT: {session} did not boot in {timeout}s")
    print("--- capture tail ---")
    print(_tail(backend.capture_pane(session)))
    backend.kill_session(session)
    return 1


def _self_test() -> int:
    backend = _load_sibling("live-trial-backend")
    assert _MODEL_RE.match("claude-opus-4-8")
    assert not _MODEL_RE.match("bad model; rm -rf")
    assert backend.deny_target_skill("run-skill-live-trial")
    cmd = build_claude_command("u-1", "claude-opus-4-8")
    assert "--session-id u-1" in cmd and "--model claude-opus-4-8" in cmd
    assert "--model" not in build_claude_command("u-1", "")
    print("OK: live-trial-boot self-test")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session", nargs="?")
    ap.add_argument("cwd", nargs="?")
    ap.add_argument("--model", default="", help="空=ユーザー既定 model。proof trial は full id 必須")
    ap.add_argument("--session-id", default="", help="transcript 固定用 UUID (省略時は自動生成)")
    ap.add_argument("--target-skill", default="",
                    help="被験 skill (denylist 再帰遮断の機械 gate。省略可だが指定推奨)")
    ap.add_argument("--self-test", action="store_true")
    ns = ap.parse_args(argv)
    if ns.self_test:
        return _self_test()
    if not ns.session or not ns.cwd:
        ap.print_usage(sys.stderr)
        return 2

    backend = _load_sibling("live-trial-backend")
    if ns.target_skill and backend.deny_target_skill(ns.target_skill):
        print(f"[ERROR] DENYLIST: 被験 skill {ns.target_skill} は再帰遮断対象 "
              f"({sorted(backend.DENY_TARGET_SKILLS)})", file=sys.stderr)
        return 2
    if not backend.valid_session_name(ns.session):
        print(f"[ERROR] invalid session name: {ns.session}", file=sys.stderr)
        return 2
    if not Path(ns.cwd).is_dir():
        print(f"[ERROR] cwd not found: {ns.cwd}", file=sys.stderr)
        return 2
    if ns.model and not _MODEL_RE.match(ns.model):
        print(f"[ERROR] invalid model: {ns.model}", file=sys.stderr)
        return 2
    backend.require_tmux()

    session_id = (ns.session_id or str(uuid.uuid4())).lower()
    timeout = int(os.environ.get("BOOT_TIMEOUT", "90"))
    grace = int(os.environ.get("BOOT_GRACE", "3"))
    return boot(backend, ns.session, ns.cwd, ns.model, session_id, timeout, grace)


if __name__ == "__main__":
    raise SystemExit(main())

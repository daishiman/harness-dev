#!/usr/bin/env python3
# /// script
# name: live-trial-backend
# purpose: live-trial の tmux 呼出を一手に引き受ける輸送層境界 (new-session/send-keys/load-buffer/paste-buffer/capture-pane/has-session/kill-session/reap)。
# inputs:
#   - argv: <subcommand> (require|new-session|send-line|paste-file|capture-pane|has-session|kill-session|pane-command|reap|deny-check|--self-test)
# outputs:
#   - stdout: subcommand 依存 (capture 本文 / OK 行 / reap 対象一覧)
#   - exit: 0=OK / 1=失敗 / 2=usage・denylist / 3=BLOCKED (tmux 不在, fail-closed)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""版依存モジュール境界: live-trial が外部 CLI `tmux` に触れる唯一の場所。

tmux のオプション/表示仕様が版で変わったら本 module だけを更新する (boot/send/
poll/verdict は本 module の関数または CLI 経由でのみ tmux に触れる)。tmux は
Python stdlib で代替不能な輸送層 (別プロセス本物 claude セッションの pane 制御)
として plugin.json の requirements.external_clis に登録済み。不在時は exit 3
BLOCKED (fail-closed) — verdict の overall.verdict=BLOCKED に対応する (D2)。
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 被験 skill denylist (再帰遮断)。live-trial が自分自身や iter-improve を被験体に
# すると trial 内で更に trial/改善ループが起動し無限入れ子になるため、エンジン
# 閉包 (feedback_contract_ssot.py ENGINE_SKILLS と同族) を起動前に拒否する。
# 全 entrypoint (boot/verdict) が本 module を経由するため、policy 定数はここに
# 一元配置する (二重宣言禁止)。
DENY_TARGET_SKILLS = frozenset({"run-skill-live-trial", "run-skill-iter-improve"})

# session 名: path traversal / 区切り文字を拒否 (tmux -t への注入防止)
_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

EXIT_BLOCKED = 3


def deny_target_skill(target: str) -> bool:
    """`plugin:skill` / 素の skill 名のどちらでも denylist 照合する。"""
    name = str(target or "").strip().rsplit(":", 1)[-1].strip()
    return name in DENY_TARGET_SKILLS


def valid_session_name(name: str) -> bool:
    if not name or ".." in name:
        return False
    return bool(_SESSION_RE.match(name))


def tmux_available() -> bool:
    return shutil.which("tmux") is not None


def require_tmux() -> None:
    """tmux 不在は BLOCKED (exit 3) で fail-closed。呼び出し側は verdict=BLOCKED を記録する。"""
    if not tmux_available():
        print(
            "BLOCKED: tmux not found — live-trial は実行不能 (fail-closed)。"
            " verdict=BLOCKED を記録し、tmux を導入して再実行する"
            " (plugin.json requirements.external_clis 参照)",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_BLOCKED)


def _tmux(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["tmux", *args], capture_output=True, text=True, check=check
    )


def new_session(session: str, cwd: str, width: int = 220, height: int = 50) -> None:
    require_tmux()
    kill_session(session)  # 同名残骸は事前掃除 (boot 再試行の冪等性)
    _tmux(
        "new-session", "-d", "-s", session, "-c", cwd,
        "-x", str(width), "-y", str(height), check=True,
    )


def send_keys(session: str, *keys: str) -> None:
    """短い固定文字列 (コマンド行 / gate 応答 / Enter) 専用。タスク本文は paste_file を使う。"""
    require_tmux()
    _tmux("send-keys", "-t", session, *keys, check=True)


def send_line(session: str, text: str) -> None:
    send_keys(session, text, "Enter")


def paste_file(session: str, path: str) -> None:
    """load-buffer + paste-buffer によるファイル経由送信。

    長文/改行/括弧を send-keys で生送信すると TUI のペースト検知が誤動作する
    (絶対ルール: 送信はファイル経由)。paste-buffer は -d でバッファを消費する。
    """
    require_tmux()
    _tmux("load-buffer", str(path), check=True)
    _tmux("paste-buffer", "-d", "-t", session, check=True)


def paste_text(session: str, text: str) -> None:
    """テキストを一時ファイル化して paste_file へ (呼び出し側にファイルを強制)。"""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write(text)
        tmp = fh.name
    try:
        paste_file(session, tmp)
    finally:
        Path(tmp).unlink(missing_ok=True)


def capture_pane(session: str, scrollback: bool = False) -> str:
    if not tmux_available():
        return ""
    args = ["capture-pane", "-t", session, "-p"]
    if scrollback:
        args += ["-S", "-"]
    cp = _tmux(*args)
    return cp.stdout if cp.returncode == 0 else ""


def has_session(session: str) -> bool:
    if not tmux_available():
        return False
    return _tmux("has-session", "-t", session).returncode == 0


def kill_session(session: str) -> bool:
    if not tmux_available():
        return False
    return _tmux("kill-session", "-t", session).returncode == 0


def pane_current_command(session: str) -> str:
    """boot の READY/BOOT_FAIL 判定用。tmux 消失や失敗は空文字 (shell 扱い) を返す。"""
    if not tmux_available():
        return ""
    cp = _tmux("list-panes", "-t", session, "-F", "#{pane_current_command}")
    if cp.returncode != 0:
        return ""
    return cp.stdout.splitlines()[0].strip() if cp.stdout.strip() else ""


def list_sessions() -> list[str]:
    if not tmux_available():
        return []
    cp = _tmux("list-sessions", "-F", "#{session_name}")
    if cp.returncode != 0:
        return []
    return [ln.strip() for ln in cp.stdout.splitlines() if ln.strip()]


def reap(prefix: str = "lt-") -> list[str]:
    """取りこぼした trial セッションの一括回収 (全終了経路のリーク掃除)。"""
    victims = [s for s in list_sessions() if s.startswith(prefix)]
    for s in victims:
        kill_session(s)
    return victims


def _self_test() -> int:
    assert valid_session_name("lt-20260702-x")
    assert not valid_session_name("../evil")
    assert not valid_session_name("a/b")
    assert not valid_session_name("")
    assert deny_target_skill("run-skill-live-trial")
    assert deny_target_skill("harness-creator:run-skill-iter-improve")
    assert not deny_target_skill("harness-creator:run-goal-seek")
    print("OK: live-trial-backend self-test")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("require")
    p = sub.add_parser("new-session")
    p.add_argument("session")
    p.add_argument("cwd")
    p = sub.add_parser("send-line")
    p.add_argument("session")
    p.add_argument("text")
    p = sub.add_parser("paste-file")
    p.add_argument("session")
    p.add_argument("path")
    p = sub.add_parser("capture-pane")
    p.add_argument("session")
    p.add_argument("--scrollback", action="store_true")
    p = sub.add_parser("has-session")
    p.add_argument("session")
    p = sub.add_parser("kill-session")
    p.add_argument("session")
    p = sub.add_parser("pane-command")
    p.add_argument("session")
    p = sub.add_parser("reap")
    p.add_argument("--prefix", default="lt-")
    p = sub.add_parser("deny-check")
    p.add_argument("target")
    ns = ap.parse_args(argv)

    if ns.self_test:
        return _self_test()
    if ns.cmd is None:
        ap.print_usage(sys.stderr)
        return 2
    if ns.cmd == "deny-check":
        if deny_target_skill(ns.target):
            print(f"DENY: {ns.target} は被験 skill denylist (再帰遮断) に該当", file=sys.stderr)
            return 2
        print(f"OK: {ns.target}")
        return 0
    if ns.cmd == "require":
        require_tmux()
        print("OK: tmux available")
        return 0
    if getattr(ns, "session", None) is not None and not valid_session_name(ns.session):
        print(f"[ERROR] invalid session name: {ns.session}", file=sys.stderr)
        return 2
    if ns.cmd == "new-session":
        new_session(ns.session, ns.cwd)
        print(f"OK: new-session {ns.session}")
    elif ns.cmd == "send-line":
        send_line(ns.session, ns.text)
        print(f"OK: send-line {ns.session}")
    elif ns.cmd == "paste-file":
        paste_file(ns.session, ns.path)
        print(f"OK: paste-file {ns.session}")
    elif ns.cmd == "capture-pane":
        sys.stdout.write(capture_pane(ns.session, scrollback=ns.scrollback))
    elif ns.cmd == "has-session":
        return 0 if has_session(ns.session) else 1
    elif ns.cmd == "kill-session":
        kill_session(ns.session)
        print(f"OK: kill-session {ns.session}")
    elif ns.cmd == "reap":
        for s in reap(ns.prefix):
            print(f"REAPED: {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""live-trial 隔離ガード (PreToolUse hook)。

argv[1] の policy JSON に書いた書込み境界の外へ出るツール呼び出しと、外部サービスへ届くツールを exit 2 で止める。
被験 session の cwd/.claude/settings.local.json から呼ばれる (--setting-sources local で読まれる)。
すべての判定を policy["log"] に 1 行 1 JSON で残す (leak 監査の一次資料)。

方針: 外部へ届くツールは名前で止める (mcp__*、Artifact 系、Web 系、通知・遠隔実行系)。
Write/Edit 系は file_path を realpath にして境界の内側かを見る。Bash は文字列の発見的検査で、
外部 CLI の直接呼出し・ネットワーク CLI・tmux/claude の入れ子・境界外の監査対象パスへの言及を止める。
Bash 経由の書込みは、隔離 env (stub PATH・空の GH_CONFIG_DIR・資格情報なしの git) と事後監査で補う。

例外 (sysspec3 から): policy に allowed_fetch_hosts があるときだけ、WebFetch をその host への https の GET に限って通す。
host は完全一致 (小文字化だけ。ワイルドカード・部分一致・www の付け外しはしない)。userinfo と 443 以外の port は拒否する。
WebFetch は GET しか送らず、別 host への redirect は追わずに新しい URL を返すので、その次の呼出しもここで照合される。
WebSearch は policy に関係なく止める。allowed_fetch_hosts の無い policy では、従来どおり WebFetch も止める。

allowlist (render4・status3 から。team-lead の 2026-10-12 の指示): ALLOW_TOOLS に無い tool は、名前を知らなくても止める。
BLOCK_TOOLS と mcp__* は、拒否の理由を「外部へ届く」と書き分けるために残す (ALLOW_TOOLS より先に見る)。
ALLOW_TOOLS は pr85 の全 run の guard の記録に出た local の tool と、作業に要る local の tool だけ。
WebFetch は ALLOW_TOOLS に入れない (allowed_fetch_hosts の照合を通ったときだけ、その前の分岐で通す)。
Agent/Task の isolation (remote・worktree) は止める。
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
from urllib.parse import urlsplit

BLOCK_TOOLS = {
    "Artifact", "ArtifactComments", "ArtifactData", "ArtifactCheck",
    "WebFetch", "WebSearch", "RemoteTrigger", "PushNotification",
    "CronCreate", "CronDelete", "SendMessage", "TeamCreate", "TeamDelete",
    "EnterWorktree", "ExitWorktree", "DesignSync", "ScheduleWakeup", "SendFeedback",
}
ALLOW_TOOLS = {
    "Read", "Glob", "Grep", "LSP", "Bash", "Monitor", "TaskOutput", "TaskStop",
    "Write", "Edit", "MultiEdit", "NotebookEdit", "Skill", "Agent", "Task", "ToolSearch",
    "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet",
    "AskUserQuestion", "EnterPlanMode", "ExitPlanMode",
}
SUBAGENT_TOOLS = {"Agent", "Task"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Bash: 外部へ届く・隔離を壊すコマンド
BASH_DENY = [
    (r"(^|[^\w.-])/(opt/homebrew|usr/local)/bin/(gh|bd)\b", "実物の gh/bd の絶対パス呼出し"),
    (r"\bgit\b[^\n;&|]*\s(push|fetch|pull|clone|worktree|submodule)\b", "git の remote 操作・worktree 操作"),
    (r"\bgit\b[^\n;&|]*\sremote\s+(add|set-url)\b", "git remote の追加・変更"),
    (r"(^|[\s;&|(`$])(curl|wget|nc|ncat|ssh|scp|sftp|rsync|telnet|ftp)(\s|$)", "ネットワーク CLI"),
    (r"(^|[\s;&|(`$])(open|osascript|launchctl|crontab|security)(\s|$)", "macOS の外部起動・資格情報 CLI"),
    (r"(^|[\s;&|(`$])tmux(\s|$)", "tmux の操作 (trial 同士の干渉を防ぐ)"),
    (r"(^|[\s;&|(`$])claude(\s|$)", "claude CLI の入れ子起動"),
    (r"\b(npm|npx|pnpm|yarn|pip3?|brew|uv|gem|cargo)\s+(install|add|publish|i)\b", "パッケージの導入・公開"),
    (r"(~|\$HOME|/Users/dm)/\.(claude|config|ssh|gitconfig|git-credentials)", "利用者の設定ディレクトリへの言及"),
    (r"(~|\$HOME|/Users/dm)/(dev|Library)/", "隔離外の利用者ディレクトリへの言及"),
    (r"/Users/dm/dev/dev/", "本体の作業ツリーへの言及"),
]


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def fetch_refusal(url: str, allowed_hosts: list[str]) -> str:
    """WebFetch の URL が許可 host への https かを見る。通すなら空文字、止めるなら理由を返す。"""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return f"WebFetch の URL を解釈できない ({url[:160]})"
    if parts.scheme.lower() != "https":
        return f"WebFetch は https だけ許可 ({url[:160]})"
    if parts.username is not None or parts.password is not None:
        return f"WebFetch の URL に userinfo がある ({url[:160]})"
    if port not in (None, 443):
        return f"WebFetch の port は 443 だけ許可 ({url[:160]})"
    host = (parts.hostname or "").lower()
    if host not in {h.lower() for h in allowed_hosts}:
        return f"WebFetch の host が許可一覧に無い (host={host})"
    return ""


import ast
import shlex


def _literal_json_writer(code, roots, cwd):
    """eval-log内へstdinをそのまま保存する限定的なPythonコードだけを認める。"""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    imported = set()
    writes = 0

    def literal_path(node):
        if not isinstance(node, ast.Call) or len(node.args) != 1 or node.keywords:
            return None
        func = node.func
        valid = (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                 and func.value.id == 'pathlib' and func.attr == 'Path' and 'pathlib' in imported)
        valid |= isinstance(func, ast.Name) and func.id == 'Path' and 'Path' in imported
        arg = node.args[0]
        if not valid or not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            return None
        path = os.path.realpath(arg.value if os.path.isabs(arg.value) else os.path.join(cwd, arg.value))
        if not path.endswith('.json') or 'eval-log' not in path.split(os.sep):
            return None
        return path if any(path.startswith(root + os.sep) for root in roots) else None

    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            if any(a.name not in {'pathlib', 'sys'} or a.asname for a in stmt.names):
                return False
            imported.update(a.name for a in stmt.names)
            continue
        if isinstance(stmt, ast.ImportFrom):
            if stmt.module != 'pathlib' or stmt.level or len(stmt.names) != 1 or stmt.names[0].name != 'Path' or stmt.names[0].asname:
                return False
            imported.add('Path')
            continue
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            return False
        call = stmt.value
        func = call.func
        if not isinstance(func, ast.Attribute):
            return False
        if func.attr == 'mkdir':
            if not isinstance(func.value, ast.Attribute) or func.value.attr != 'parent' or not literal_path(func.value.value) or call.args:
                return False
            if {kw.arg for kw in call.keywords} != {'parents', 'exist_ok'} or any(not isinstance(kw.value, ast.Constant) or kw.value.value is not True for kw in call.keywords):
                return False
            continue
        if func.attr != 'write_text' or not literal_path(func.value) or len(call.args) != 1 or 'sys' not in imported:
            return False
        value = call.args[0]
        if not isinstance(value, ast.Call) or value.args or value.keywords or ast.dump(value.func) != ast.dump(ast.parse('sys.stdin.read', mode='eval').body):
            return False
        if any(kw.arg != 'encoding' or not isinstance(kw.value, ast.Constant) or kw.value.value not in {'utf-8', 'utf8'} for kw in call.keywords):
            return False
        writes += 1
    return writes == 1


def _macos_command_view(command, roots, cwd):
    """引用済みJSON stdinをCLI名の探索から除外。実コマンドと他の全規則は維持。"""
    view = list(command)
    for match in re.finditer(r'''<<[ \t]*(?:'([A-Za-z_][A-Za-z0-9_]*)'|"([A-Za-z_][A-Za-z0-9_]*)")[ \t]*\n''', command):
        try:
            header = shlex.split(command[:match.start()])
        except ValueError:
            continue
        if len(header) < 3 or header[-2] != '-c':
            continue
        pos = -4 if len(header) >= 4 and header[-3] == '-B' else -3
        if os.path.basename(header[pos]) not in {'python3', 'python'}:
            continue
        if not _literal_json_writer(header[-1], roots, cwd):
            continue
        label = match.group(1) or match.group(2)
        end = re.search(r'(?m)^' + re.escape(label) + r'\r?$', command[match.end():])
        if end is None:
            continue
        start = match.end()
        stop = start + end.start()
        try:
            json.loads(command[start:stop])
        except (ValueError, TypeError):
            continue
        view[start:stop] = ['\n' if ch == '\n' else ' ' for ch in command[start:stop]]
    return ''.join(view)


def main() -> int:
    policy = json.load(open(sys.argv[1], encoding="utf-8"))
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        data = {}
    tool = str(data.get("tool_name", ""))
    tool_input = data.get("tool_input") or {}
    cwd = str(data.get("cwd") or os.getcwd())
    roots = [os.path.realpath(r) for r in policy["allowed_write_roots"]]
    guarded = [os.path.realpath(r) for r in policy.get("guarded_roots", [])]

    def log(decision: str, reason: str) -> None:
        entry = {"ts": _now(), "label": policy.get("label"), "session_id": data.get("session_id"),
                 "agent_id": data.get("agent_id"), "tool": tool, "decision": decision, "reason": reason,
                 "input": {k: (str(v)[:400]) for k, v in tool_input.items()} if isinstance(tool_input, dict) else str(tool_input)[:400]}
        with open(policy["log"], "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def deny(reason: str) -> int:
        log("deny", reason)
        print(f"[live-trial 隔離ガード] 拒否: {reason}。この trial は隔離環境で実行中で、"
              "書込みは許可された作業領域の内側だけ、外部サービスへの接続は禁止です。", file=sys.stderr)
        return 2

    def inside(path: str) -> bool:
        absolute = path if os.path.isabs(path) else os.path.join(cwd, path)
        real = os.path.realpath(absolute)
        return any(real == root or real.startswith(root + os.sep) for root in roots)

    fetch_hosts = policy.get("allowed_fetch_hosts") or []
    if tool == "WebFetch" and fetch_hosts:
        refusal = fetch_refusal(str(tool_input.get("url", "")), fetch_hosts)
        if refusal:
            return deny(refusal)
        log("allow", "WebFetch: 許可 host への https GET")
        return 0
    if tool.startswith("mcp__") or tool in BLOCK_TOOLS:
        return deny(f"外部へ届く可能性のあるツール {tool}")
    if tool not in ALLOW_TOOLS:
        return deny(f"許可一覧に無いツール {tool or '(名前なし)'}")
    if tool in SUBAGENT_TOOLS and tool_input.get("isolation"):
        # remote は外部のクラウドで動き、worktree は git worktree add になる
        return deny(f"subagent の isolation={tool_input.get('isolation')}")
    if tool in WRITE_TOOLS:
        target = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if not target or not inside(target):
            return deny(f"書込み先が隔離境界の外 ({target})")
    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        if tool_input.get("dangerouslyDisableSandbox"):
            return deny("sandbox の解除")
        macos_view = _macos_command_view(command, roots, cwd)
        for pattern, why in BASH_DENY:
            checked = macos_view if why == "macOS の外部起動・資格情報 CLI" else command
            if re.search(pattern, checked):
                return deny(why)
        # 監査対象 (wtpy など) のパスは、許可した run dir の内側を指すときだけ通す。
        # 許可した root の祖先そのもの (R=<T>; cat $R/runs/<label>/... のような変数の接頭辞) は通す。
        # 祖先を起点にした境界外への書込みは OS の sandbox (denyWrite) が止める (06:58 JST に追加。schedule の
        # verifier が T を変数に置いただけの読取りで止められた誤検知への対処)
        for root in guarded:
            for match in re.finditer(re.escape(root) + r"[^\s'\"`;|&<>)]*", command):
                mentioned = os.path.realpath(match.group(0).rstrip("/"))
                if not inside(match.group(0)) and not any(r.startswith(mentioned + os.sep) for r in roots):
                    return deny(f"監査対象の領域への言及 ({match.group(0)[:160]})")
    log("allow", "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

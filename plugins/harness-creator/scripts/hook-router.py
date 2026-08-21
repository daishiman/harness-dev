#!/usr/bin/env python3
# /// script
# name: hook-router
# purpose: 単一 hook entry point。生成済み registry を正本に、event / tool 名 / plugin / slash-command / skill の 4 粒度で発火対象 handler を決定し、Claude Code と Codex の双方で等価に dispatch する。Codex は plugin_hooks が removed のため plugin 配下 hooks.json を読めず、project 層のこの router が唯一の配達経路になる。
# inputs:
#   - stdin: hook event JSON (両ホスト共通スキーマ: hook_event_name / tool_name / tool_input / session_id / cwd ...)
#   - argv: --event EVENT [--host claude|codex|auto] [--registry PATH] [--dry-run]
# outputs:
#   - stdout: 各 handler の stdout をそのまま連結
#   - stderr: 発火した handler と非零終了の内訳
#   - exit: 0=許可 / 2=ブロック (いずれかの handler が 2) / 1=非ブロック失敗
# contexts: [C, E]
# network: false
# write-scope: none (委譲先 handler の write-scope に従う)
# dependencies: []
# requires-python: ">=3.11"
# ///
"""Dispatch hook handlers with per-tool / per-plugin / per-command / per-skill scope.

Neither Claude Code nor Codex can match on a slash-command or a skill: both
compare `matcher` against the tool name only.  Eighteen of this repository's
hook scripts already re-implement that missing filter internally, each in its
own way.  This router makes the filter one declarative layer so the same
registry drives both hosts identically.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# repo root は cwd ではなく自身の位置から解決する。hook の cwd はホストと
# 起動経路で変わるが、このファイルの位置は repo 構造そのものなので不変。
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = REPO_ROOT / ".codex" / "hooks" / "registry.json"

# ブロック相当の終了コード。両ホストとも 2 を「拒否」として解釈する。
BLOCK = 2


def load_registry(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # registry が読めないまま 0 を返すと、hook が沈黙しているのに緑に見える。
        print(f"hook-router: registry unreadable {path}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if not isinstance(data.get("entries"), list):
        print(f"hook-router: registry lacks entries[]: {path}", file=sys.stderr)
        raise SystemExit(1)
    return data


def read_payload() -> tuple[dict, str]:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    return (payload if isinstance(payload, dict) else {}), raw


def detect_host() -> str:
    """Codex は CLAUDE_* を一切渡さない。存在の有無が唯一の決定論的な区別。"""
    if os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR"):
        return "claude"
    if os.environ.get("CODEX_HOME"):
        return "codex"
    return "claude"


def resolve_skill(payload: dict) -> str | None:
    """発火中の skill 名を payload から取り出す (無ければ None)。

    Claude は Skill tool の tool_input に載せる。Codex に skill tool は無く、
    プロンプト内の `$skill-name` が唯一の起動表現なので、そちらも見る。
    """
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if isinstance(tool_input, dict):
        for key in ("skill_name", "skill", "name", "command"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    prompt = payload.get("prompt")
    if isinstance(prompt, str):
        match = re.match(r"\s*[$/]([A-Za-z0-9][A-Za-z0-9:_-]*)", prompt)
        if match:
            return match.group(1)
    return None


def resolve_slash_command(payload: dict) -> str | None:
    """先頭の slash command を取り出す (無ければ None)。"""
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return None
    match = re.match(r"\s*/([A-Za-z0-9][A-Za-z0-9:_-]*)", prompt)
    return match.group(1) if match else None


def matches_tool(entry: dict, host: str, tool_name: str | None) -> bool:
    """matcher は tool 名にのみ効く。tool を伴わない event は matcher を無視する。"""
    matcher = (entry.get("matcher") or {}).get(host)
    if not matcher:
        # そのホストに到達手段が無い entry (例: Skill 相当が無い Codex)。
        return False
    if tool_name is None:
        return True
    try:
        return re.search(matcher, tool_name) is not None
    except re.error:
        return False


def matches_scope(entry: dict, skill: str | None, command: str | None) -> bool:
    """skills / commands スコープ。宣言が無い entry は全実行に発火する。"""
    for key, actual in (("skills", skill), ("commands", command)):
        patterns = entry.get("scope", {}).get(key)
        if not patterns:
            continue
        if actual is None:
            # スコープを宣言した entry は、対象を特定できない実行には発火しない。
            return False
        if not any(fnmatch.fnmatch(actual, pattern) for pattern in patterns):
            return False
    return True


def select(registry: dict, event: str, host: str, payload: dict) -> list[dict]:
    tool_name = payload.get("tool_name") or payload.get("toolName")
    skill = resolve_skill(payload)
    command = resolve_slash_command(payload)
    selected = []
    for entry in registry["entries"]:
        if entry.get("event") != event:
            continue
        if host not in (entry.get("products") or []):
            continue
        if not matches_tool(entry, host, tool_name if entry.get("tool_scoped") else None):
            continue
        if not matches_scope(entry, skill, command):
            continue
        selected.append(entry)
    return selected


def handler_env(entry: dict) -> dict:
    """委譲先が両ホストで同じ変数を読めるようにする。Codex は何も渡さないため
    router が repo 構造から復元する。"""
    plugin_root = str(REPO_ROOT / "plugins" / entry["plugin"])
    env = dict(os.environ)
    env.setdefault("CLAUDE_PROJECT_DIR", str(REPO_ROOT))
    env["PLUGIN_ROOT"] = plugin_root
    env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    env["HARNESS_HOOK_HOST"] = entry["_host"]
    return env


def run_handler(entry: dict, raw: str) -> int:
    command = entry["command"]
    env = handler_env(entry)
    if entry.get("async"):
        # async handler の結果は判定に使えない。待たずに投げ、失敗も判定に混ぜない。
        subprocess.Popen(  # noqa: S602 - command は registry 由来 (repo 所有)
            command, shell=True, cwd=str(REPO_ROOT), env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return 0
    try:
        proc = subprocess.run(  # noqa: S602 - 同上
            command, shell=True, cwd=str(REPO_ROOT), env=env,
            input=raw, text=True, capture_output=True,
            timeout=entry.get("timeout") or 30,
        )
    except subprocess.TimeoutExpired:
        # timeout を成功扱いにすると guard が沈黙する。非ブロック失敗として上げる。
        print(f"hook-router: timeout {entry['id']}", file=sys.stderr)
        return 1
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def combine_verdicts(codes: list[int]) -> int:
    """複数 handler の終了コードを router 1 個の verdict へ畳み込む。

    規則は「どの guard も単独で拒否権を持つ」。多数決にすると、guard を 1 個
    足すだけで既存の拒否が薄まるため、guard の追加が安全性を下げる方向に働く。

    ブロック (2) > 非ブロック失敗 (それ以外の非零) > 許可 (0) の順で優先する。
    失敗を 0 に丸めないのは、guard が壊れているのに緑に見える状態を作らない
    ため (registry が読めないときに 1 を返すのと同じ理由)。
    """
    if BLOCK in codes:
        return BLOCK
    if any(code != 0 for code in codes):
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--host", default="auto", choices=["auto", "claude", "codex"])
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    host = detect_host() if args.host == "auto" else args.host
    registry = load_registry(Path(args.registry))
    payload, raw = read_payload()
    selected = select(registry, args.event, host, payload)
    for entry in selected:
        entry["_host"] = host

    if args.dry_run:
        print(json.dumps({"host": host, "event": args.event,
                          "selected": [e["id"] for e in selected]}, ensure_ascii=False))
        return 0

    codes = [run_handler(entry, raw) for entry in selected if not entry.get("async")]
    for entry in selected:
        if entry.get("async"):
            run_handler(entry, raw)
    return combine_verdicts(codes)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# /// script
# name: build-hook-registry
# purpose: plugins/*/hooks/hooks.json (Claude 側の正本) を唯一の入力として、hook-router が読む .codex/hooks/registry.json と、その router を呼ぶ .codex/hooks.json の managed entry を決定論生成する。Codex は plugin_hooks が removed のため plugin 配下 hooks.json を読めず、この投影が Codex 側の唯一の配達経路になる。
# inputs:
#   - argv: --repo-root PATH [--apply|--check|--dry-run(既定 check)] [--json]
# outputs:
#   - stdout: 状態文字列 (既定) / JSON report (--json)。drift path・Codex 到達不能 entry・非対応 event。
#   - write: .codex/hooks/registry.json 全体 と .codex/hooks.json の managed entry のみ (atomic replace)。foreign handler (bd 等) は温存。
#   - exit: 0=synced/noop / 1=drift / 3=contract invalid
# contexts: [C, E]
# network: false
# write-scope: .codex/hooks/registry.json / .codex/hooks.json (managed entry のみ)
# dependencies: []
# requires-python: ">=3.11"
# ///
"""Project per-plugin Claude hooks into the single Codex project-layer router.

`plugin_hooks` is `removed` in Codex 0.148.0, so a plugin's own `hooks/hooks.json`
is invisible there.  Declaring `products = ["codex"]` while delivering through the
plugin layer is therefore a claim that cannot be true; this projector replaces that
claim with an actual delivery path and reports every handler it cannot reach.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

ROUTER_REL = "plugins/harness-creator/scripts/hook-router.py"
REGISTRY_REL = ".codex/hooks/registry.json"
CODEX_HOOKS_REL = ".codex/hooks.json"
MARKER = "# harness-managed:hook-router"

# Codex 0.148.0 の HookEventsToml が受け付ける event (実測)。ここに無い event を
# 投影すると Codex 側で沈黙するので、生成せず「Claude 専用」として報告する。
CODEX_EVENTS = {
    "PreToolUse", "PermissionRequest", "PostToolUse", "PreCompact", "PostCompact",
    "SessionStart", "SessionEnd", "UserPromptSubmit", "SubagentStart", "SubagentStop", "Stop",
}

# matcher が tool 名に対して効く event。これ以外 (SessionStart 等) の matcher は
# tool 名ではなく trigger 種別なので、翻訳せずそのまま通す。
TOOL_SCOPED_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest"}

# ホスト間の tool 名語彙。Claude の matcher をそのまま Codex へ渡すと 1 件も
# 一致しない (Codex に Bash / Edit / Write という tool 名は存在しない)。
TOOL_MAP: dict[str, tuple[str, ...]] = {
    "Bash": ("shell_command", "exec_command"),
    "Edit": ("apply_patch",),
    "Write": ("apply_patch",),
    "MultiEdit": ("apply_patch",),
    "NotebookEdit": ("apply_patch",),
    "Read": ("read_file",),
    # 対応 tool が存在しないもの。空タプルは「Codex では到達不能」を意味し、
    # 黙って落とさず report に出す。
    "Skill": (),
    "Task": (),
    "WebFetch": (),
    "WebSearch": (),
    "Glob": (),
    "Grep": (),
}
CODEX_TOOL_NAMES = {name for names in TOOL_MAP.values() for name in names}


class ContractError(Exception):
    pass


def translate_matcher(matcher: str) -> tuple[str, list[str]]:
    """Claude の tool matcher を Codex の tool 名へ翻訳する。

    戻り値は (Codex matcher, 到達不能だった Claude tool 名)。すべての選択肢が
    到達不能なら matcher は空文字になり、その entry は Codex へ投影されない。
    """
    if not matcher or matcher == ".*":
        return matcher or "", []
    alternatives = [token for token in re.split(r"\|", matcher) if token]
    translated: list[str] = []
    unreachable: list[str] = []
    for token in alternatives:
        if token in CODEX_TOOL_NAMES:
            translated.append(token)  # 既に Codex 名 (手書き union) はそのまま
        elif token in TOOL_MAP:
            mapped = TOOL_MAP[token]
            translated.extend(mapped)
            if not mapped:
                unreachable.append(token)
        else:
            # 未知の tool 名を推測で写すと嘘になる。到達不能として報告する。
            unreachable.append(token)
    seen: list[str] = []
    for name in translated:
        if name not in seen:
            seen.append(name)
    return "|".join(seen), unreachable


def collect_entries(repo: Path) -> tuple[list[dict], list[dict]]:
    """plugins/*/hooks/hooks.json を registry entry 群へ正規化する。"""
    entries: list[dict] = []
    unreachable: list[dict] = []
    for hooks_path in sorted((repo / "plugins").glob("*/hooks/hooks.json")):
        plugin = hooks_path.parents[1].name
        try:
            doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(f"cannot read {hooks_path}: {exc}") from exc
        events = doc.get("hooks", doc)
        if not isinstance(events, dict):
            raise ContractError(f"{hooks_path}: hooks must be an object")
        for event in sorted(events):
            groups = events[event]
            if not isinstance(groups, list):
                raise ContractError(f"{hooks_path}: {event} must be an array")
            for group_index, group in enumerate(groups):
                matcher = group.get("matcher", "")
                tool_scoped = event in TOOL_SCOPED_EVENTS
                if tool_scoped:
                    codex_matcher, dead = translate_matcher(matcher)
                else:
                    codex_matcher, dead = matcher, []
                for handler_index, handler in enumerate(group.get("hooks", [])):
                    command = handler.get("command")
                    if handler.get("type") != "command" or not isinstance(command, str):
                        raise ContractError(f"{hooks_path}: only type=command handlers are projected")
                    products = ["claude"]
                    if event in CODEX_EVENTS and (codex_matcher or not tool_scoped):
                        products.append("codex")
                    entry = {
                        "id": f"{plugin}:{event}:{group_index}:{handler_index}",
                        "plugin": plugin,
                        "event": event,
                        "tool_scoped": tool_scoped,
                        "matcher": {
                            "claude": matcher or (".*" if not tool_scoped else ""),
                            "codex": codex_matcher or (".*" if not tool_scoped else ""),
                        },
                        "scope": {},
                        "command": command,
                        "timeout": handler.get("timeout"),
                        "async": bool(handler.get("async")),
                        "products": products,
                    }
                    entries.append(entry)
                    companion = skill_invocation_companion(entry, dead)
                    if companion is not None:
                        entries.append(companion)
                        continue
                    if "codex" not in products:
                        unreachable.append({
                            "id": entry["id"],
                            "reason": ("event-unsupported-on-codex" if event not in CODEX_EVENTS
                                       else "no-codex-tool-equivalent"),
                            "tools": dead,
                        })
    return entries, unreachable


# Codex に skill/subagent の tool は存在せず、skill はプロンプト内の `$skill-name`
# で起動される。よって「skill 実行の直前に走る guard」は UserPromptSubmit でしか
# 拾えない。PreToolUse に限って companion を生成するのは、事前判定という意味が
# 保たれるのがこの向きだけだから (PostToolUse+Skill = 実行後は Codex に相当機構が
# 無く、companion を作ると発火時点が変わって嘘になる)。
SKILL_INVOCATION_TOOLS = {"Skill", "Task"}


def skill_invocation_companion(entry: dict, dead: list[str]) -> dict | None:
    if entry["event"] != "PreToolUse" or "codex" in entry["products"]:
        return None
    if not dead or not set(dead) <= SKILL_INVOCATION_TOOLS:
        return None
    companion = json.loads(json.dumps(entry))
    companion.update({
        "id": entry["id"] + ":codex-skill-invocation",
        "event": "UserPromptSubmit",
        "tool_scoped": False,
        "matcher": {"claude": "", "codex": ".*"},
        # skills スコープの fail-closed 規則により、skill 名を特定できない
        # 通常プロンプトでは発火しない。
        "scope": {"skills": ["*"]},
        "products": ["codex"],
        "derived_from": entry["id"],
    })
    return companion


def desired_registry(entries: list[dict], unreachable: list[dict]) -> str:
    doc = {
        "schema_version": 1,
        "generated_by": "plugins/harness-creator/scripts/build-hook-registry.py",
        "note": "生成物。編集は plugins/*/hooks/hooks.json 側で行い make hook-registry で再生成する。",
        "entries": entries,
        "codex_unreachable": unreachable,
    }
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def router_command(event: str) -> str:
    return f'python3 "{ROUTER_REL}" --event {event} --host codex {MARKER}:{event}'


def desired_codex_hooks(existing: dict, entries: list[dict]) -> dict:
    """Router entry だけを再生成し、foreign handler (bd 等) は温存する。"""
    desired = json.loads(json.dumps(existing))
    hooks_obj = desired.setdefault("hooks", {})
    if not isinstance(hooks_obj, dict):
        raise ContractError(".codex/hooks.json hooks must be an object")
    # 既存の router entry を全撤去してから、必要な event だけ入れ直す。
    for event in list(hooks_obj):
        kept_groups = []
        for group in hooks_obj[event]:
            handlers = [h for h in group.get("hooks", []) if MARKER not in h.get("command", "")]
            if handlers:
                kept_groups.append({**group, "hooks": handlers})
        if kept_groups:
            hooks_obj[event] = kept_groups
        else:
            hooks_obj.pop(event, None)

    by_event: dict[str, list[dict]] = {}
    for entry in entries:
        if "codex" in entry["products"]:
            by_event.setdefault(entry["event"], []).append(entry)
    for event in sorted(by_event):
        alternatives: list[str] = []
        for entry in by_event[event]:
            for token in entry["matcher"]["codex"].split("|"):
                if token and token not in alternatives:
                    alternatives.append(token)
        # hooks.json 側は粗く受け、正確な絞り込みは router が payload を見て行う。
        group = {"hooks": [{"type": "command", "command": router_command(event)}]}
        if alternatives and alternatives != [".*"]:
            group = {"matcher": "|".join(sorted(alternatives)), **group}
        hooks_obj.setdefault(event, []).append(group)
    return desired


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False)
    try:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, path)


def run(repo: Path, mode: str) -> tuple[dict, int]:
    if not (repo / ROUTER_REL).is_file():
        raise ContractError(f"router missing: {ROUTER_REL}")
    entries, unreachable = collect_entries(repo)
    registry_path = repo / REGISTRY_REL
    codex_path = repo / CODEX_HOOKS_REL
    registry_text = desired_registry(entries, unreachable)
    existing = json.loads(codex_path.read_text(encoding="utf-8")) if codex_path.is_file() else {"hooks": {}}
    codex_text = json.dumps(desired_codex_hooks(existing, entries), ensure_ascii=False,
                            indent=2, sort_keys=True) + "\n"

    drift = []
    for path, text, rel in ((registry_path, registry_text, REGISTRY_REL),
                            (codex_path, codex_text, CODEX_HOOKS_REL)):
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            drift.append(rel)
    if mode == "apply":
        if REGISTRY_REL in drift:
            atomic_write(registry_path, registry_text)
        if CODEX_HOOKS_REL in drift:
            atomic_write(codex_path, codex_text)
        status, code = ("synced" if drift else "noop"), 0
    elif drift and mode == "check":
        status, code = "drift", 1
    else:
        status, code = ("would-sync" if drift else "noop"), 0
    return {
        "status": status,
        "paths": drift,
        "entries": len(entries),
        "codex_reachable": sum(1 for e in entries if "codex" in e["products"]),
        "codex_unreachable": unreachable,
    }, code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_const", const="apply", dest="mode")
    modes.add_argument("--check", action="store_const", const="check", dest="mode")
    modes.add_argument("--dry-run", action="store_const", const="dry-run", dest="mode")
    parser.set_defaults(mode="check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report, code = run(Path(args.repo_root).resolve(), args.mode)
    except ContractError as exc:
        print(f"build-hook-registry: {exc}")
        return 3
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['status']} entries={report['entries']} "
              f"codex_reachable={report['codex_reachable']} "
              f"codex_unreachable={len(report['codex_unreachable'])}")
        for item in report["codex_unreachable"]:
            print(f"  - {item['id']}: {item['reason']}"
                  + (f" ({'|'.join(item['tools'])})" if item["tools"] else ""))
        for path in report["paths"]:
            print(f"  drift: {path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

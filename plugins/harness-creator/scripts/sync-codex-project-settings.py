#!/usr/bin/env python3
# /// script
# name: sync-codex-project-settings
# purpose: native-surfaces.toml を正本に Codex project settings (.codex/config.toml の features.hooks と .codex/hooks.json の managed hook entry) を apply/check する adapter。C01 (sync-native-surfaces.py) から child として呼ばれる。
# inputs:
#   - argv: --repo-root PATH --contract PATH(native-surfaces.toml) [--apply|--check|--dry-run(既定 check)] [--json]
# outputs:
#   - stdout: status 文字列 (既定) / JSON report (--json)。managed key の diff・verdict・exit_code。
#   - write: .codex/config.toml の features.hooks と .codex/hooks.json の managed hook entry のみ (atomic replace)。foreign handler は温存。--check/--dry-run は無書込。
#   - exit: 0=success/noop / 1=drift / 3=contract invalid (ContractError)。
# contexts: [C, E]
# network: false
# write-scope: .codex/config.toml (features.hooks key のみ) / .codex/hooks.json (managed hook entry のみ)。他 .codex key・user global config・.agents は read-only。
# dependencies: []
# requires-python: ">=3.11"
# ///
"""Apply/check project Codex settings derived from native-surfaces.toml."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import tomllib
from pathlib import Path


class ContractError(Exception):
    pass


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"JSON root must be object: {path}")
    return data


def load_contract(path: Path) -> dict:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ContractError(f"cannot read native surface contract {path}: {exc}") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("codex"), dict):
        raise ContractError("native-surfaces.toml requires schema_version=1 and [codex]")
    if not isinstance(data.get("activation"), dict) or not isinstance(data.get("discovery"), dict):
        raise ContractError("native-surfaces.toml requires [activation] and [discovery]")
    discovery = data["discovery"]
    required_discovery = {
        "marketplace_name": str,
        "plugin_name": str,
        "source_path": str,
        "installation": str,
        "authentication": str,
        "category": str,
        "distributable": bool,
        "scope": str,
        "activation_requires": list,
    }
    for key, expected in required_discovery.items():
        if not isinstance(discovery.get(key), expected):
            raise ContractError(f"discovery.{key} has invalid or missing type")
    if not discovery["marketplace_name"] or not discovery["plugin_name"]:
        raise ContractError("discovery marketplace_name/plugin_name must be non-empty")
    if not all(isinstance(value, str) and value for value in discovery["activation_requires"]):
        raise ContractError("discovery.activation_requires must contain non-empty strings")
    hooks = data.get("hooks", [])
    if not isinstance(hooks, list):
        raise ContractError("native-surfaces.toml hooks must be an array of tables")
    for hook in hooks:
        if not isinstance(hook, dict):
            raise ContractError("native-surfaces.toml hook entries must be tables")
        for key in ("id", "owner", "event", "command"):
            if not isinstance(hook.get(key), str) or not hook[key]:
                raise ContractError(f"hook.{key} must be a non-empty string")
        if "matcher" in hook and not isinstance(hook["matcher"], str):
            raise ContractError("hook.matcher must be a string")
        if not isinstance(hook.get("products"), list) or not all(
            isinstance(value, str) and value for value in hook["products"]
        ):
            raise ContractError("hook.products must contain non-empty strings")
        if hook.get("delivery") not in {"plugin", "project"}:
            raise ContractError("hook delivery must be exactly plugin or project")
    return data


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def apply_transaction(updates: list[tuple[Path, str]]) -> None:
    """Write all managed outputs or restore every preimage if any step fails."""
    preimages = [(path, path.is_file(), path.read_bytes() if path.is_file() else b"") for path, _ in updates]
    try:
        for path, text in updates:
            atomic_write(path, text)
            if path.read_text(encoding="utf-8") != text:
                raise ContractError(f"post-write readback mismatch: {path}")
    except BaseException as original:
        rollback_errors = []
        for path, existed, content in reversed(preimages):
            try:
                if existed:
                    atomic_write(path, content.decode("utf-8"))
                else:
                    path.unlink(missing_ok=True)
            except BaseException as rollback_error:
                rollback_errors.append(f"{path}: {rollback_error}")
        if rollback_errors:
            raise ContractError(
                f"settings transaction failed ({original}); rollback also failed: {'; '.join(rollback_errors)}"
            ) from original
        raise ContractError(f"settings transaction failed and preimages were restored: {original}") from original


def desired_config(existing: str, enabled: bool) -> str:
    """Preserve all user/project TOML except the repo-owned features.hooks key."""
    try:
        parsed = tomllib.loads(existing) if existing.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise ContractError(f"invalid .codex/config.toml: {exc}") from exc
    if isinstance(parsed.get("hooks"), dict):
        raise ContractError("inline [hooks] is forbidden when .codex/hooks.json owns this layer")
    lines = existing.splitlines()
    section = None
    output: list[str] = []
    replaced = False
    insertion = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if section == "features" and not replaced:
                insertion = len(output)
            section = stripped[1:-1].strip()
        if section == "features" and stripped.split("=", 1)[0].strip() == "hooks" and "=" in stripped:
            if not replaced:
                output.append(f"hooks = {'true' if enabled else 'false'}")
                replaced = True
            continue
        output.append(line)
    if not replaced:
        if section == "features":
            output.append(f"hooks = {'true' if enabled else 'false'}")
        elif insertion is not None:
            output.insert(insertion, f"hooks = {'true' if enabled else 'false'}")
        else:
            if output and output[-1] != "":
                output.append("")
            output.extend(["[features]", f"hooks = {'true' if enabled else 'false'}"])
    return "\n".join(output).rstrip() + "\n"


def hook_key(event: str, group: dict, handler: dict) -> tuple[str, str, str]:
    return event, group.get("matcher") or "", handler.get("command") or ""


def _validate_existing_hooks(existing: dict) -> None:
    hooks = existing.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ContractError(".codex/hooks.json hooks must be an object")
    for event, groups in hooks.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            raise ContractError(".codex/hooks.json events must map to arrays")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
                raise ContractError(".codex/hooks.json groups must be objects with hooks arrays")
            if "matcher" in group and not isinstance(group["matcher"], str):
                raise ContractError(".codex/hooks.json matcher must be a string")
            for handler in group.get("hooks", []):
                if not isinstance(handler, dict) or not isinstance(handler.get("command"), str):
                    raise ContractError(".codex/hooks.json handlers require string command")


def managed_marker(hook: dict) -> str:
    return f"# harness-managed:{hook['owner']}:{hook['id']}"


def managed_command(hook: dict) -> str:
    return f"{hook['command']} {managed_marker(hook)}"


def desired_hooks(existing: dict, contract: dict) -> dict:
    """Preserve foreign hooks and enforce one canonical delivery owner."""
    _validate_existing_hooks(existing)
    desired = json.loads(json.dumps(existing))
    hooks_obj = desired.setdefault("hooks", {})
    if not isinstance(hooks_obj, dict):
        raise ContractError(".codex/hooks.json hooks must be an object")
    canonical = {
        (h["event"], h.get("matcher") or "", h["command"]): h
        for h in contract.get("hooks", [])
    }
    # Remove canonical plugin-delivered handlers from the project layer. Keep
    # unrelated handlers (notably Beads) byte-semantically intact.
    managed_markers = {managed_marker(h): h for h in contract.get("hooks", [])}
    for event in list(hooks_obj):
        groups_out = []
        for group in hooks_obj[event]:
            handlers = [
                handler for handler in group.get("hooks", [])
                if not any(marker in handler.get("command", "") for marker in managed_markers)
                and not (
                    hook_key(event, group, handler) in canonical
                    and canonical[hook_key(event, group, handler)]["delivery"] == "plugin"
                )
            ]
            if handlers:
                kept = dict(group)
                kept["hooks"] = handlers
                groups_out.append(kept)
        if groups_out:
            hooks_obj[event] = groups_out
        else:
            hooks_obj.pop(event, None)
    # Project-delivered hooks are generated exactly once.
    for key, hook in canonical.items():
        if hook["delivery"] != "project":
            continue
        group = {
            "matcher": hook.get("matcher", ""),
            "hooks": [{"type": "command", "command": managed_command(hook)}],
        }
        hooks_obj.setdefault(hook["event"], []).append(group)
    return desired


def desired_discovery(existing: dict, contract: dict, repo: Path) -> dict:
    desired = json.loads(json.dumps(existing))
    plugins = desired.setdefault("plugins", [])
    if not isinstance(plugins, list) or not all(isinstance(entry, dict) for entry in plugins):
        raise ContractError("Codex marketplace plugins must be an array of objects")
    spec = contract["discovery"]
    source_path = spec["source_path"]
    source_root = (repo / source_path).resolve()
    try:
        source_root.relative_to(repo.resolve())
    except ValueError as exc:
        raise ContractError("discovery.source_path escapes repository") from exc
    if not (source_root / ".codex-plugin" / "plugin.json").is_file():
        raise ContractError(f"marketplace source lacks Codex manifest: {source_path}")
    managed = {
        "name": spec["plugin_name"],
        "source": {"source": "local", "path": source_path},
        "policy": {
            "installation": spec["installation"],
            "authentication": spec["authentication"],
        },
        "category": spec["category"],
        "x_harness": {
            "distributable": spec["distributable"],
            "scope": spec["scope"],
            "activation_requires": spec["activation_requires"],
        },
    }
    desired["name"] = spec["marketplace_name"]
    desired["plugins"] = [entry for entry in plugins if entry.get("name") != spec["plugin_name"]] + [managed]
    return desired


def run(repo: Path, contract_path: Path, mode: str) -> tuple[dict, int]:
    contract = load_contract(contract_path)
    expected = {
        "hooks_file": ".codex/hooks.json",
        "config_file": ".codex/config.toml",
    }
    for key, path in expected.items():
        if contract["codex"].get(key) != path:
            raise ContractError(f"codex.{key} must be confined to {path}")
    if contract.get("activation", {}).get("codex_discovery") != ".agents/plugins/marketplace.json":
        raise ContractError("activation.codex_discovery must be .agents/plugins/marketplace.json")
    discovery_path = repo / contract["activation"]["codex_discovery"]
    hooks_path = repo / contract["codex"]["hooks_file"]
    config_path = repo / contract["codex"]["config_file"]
    hooks_existing = load_json(hooks_path) if hooks_path.is_file() else {"hooks": {}}
    config_existing = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    discovery_existing = load_json(discovery_path) if discovery_path.is_file() else {}
    hooks_text = json.dumps(desired_hooks(hooks_existing, contract), ensure_ascii=False, indent=2) + "\n"
    config_text = desired_config(config_existing, bool(contract["codex"]["features_hooks"]))
    discovery_text = json.dumps(
        desired_discovery(discovery_existing, contract, repo), ensure_ascii=False, indent=2
    ) + "\n"
    drift = []
    if not hooks_path.is_file() or hooks_path.read_text(encoding="utf-8") != hooks_text:
        drift.append(contract["codex"]["hooks_file"])
    if not config_path.is_file() or config_path.read_text(encoding="utf-8") != config_text:
        drift.append(contract["codex"]["config_file"])
    if not discovery_path.is_file() or discovery_path.read_text(encoding="utf-8") != discovery_text:
        drift.append(contract["activation"]["codex_discovery"])
    if mode == "apply":
        desired_by_path = {
            contract["codex"]["hooks_file"]: (hooks_path, hooks_text),
            contract["codex"]["config_file"]: (config_path, config_text),
            contract["activation"]["codex_discovery"]: (discovery_path, discovery_text),
        }
        apply_transaction([desired_by_path[path] for path in drift])
        status, code = ("synced" if drift else "noop"), 0
    elif drift:
        status, code = "drift", 1
    else:
        status, code = "noop", 0
    return {"status": status, "changed": len(drift), "paths": drift, "delivery": {
        h["id"]: h["delivery"] for h in contract.get("hooks", [])
    }}, code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--contract", required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_const", const="apply", dest="mode")
    modes.add_argument("--check", action="store_const", const="check", dest="mode")
    modes.add_argument("--dry-run", action="store_const", const="dry-run", dest="mode")
    parser.set_defaults(mode="check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report, code = run(Path(args.repo_root).resolve(), Path(args.contract).resolve(), args.mode)
    except ContractError as exc:
        report, code = {"status": "invalid", "error": str(exc)}, 3
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else report["status"])
    return code


if __name__ == "__main__":
    raise SystemExit(main())

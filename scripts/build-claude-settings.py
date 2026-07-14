#!/usr/bin/env python3
"""Build .claude/settings.json from plugin-owned settings fragments."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


# Claude Code の hook events。plugin manifest が実際に配線するイベントを網羅すること
# (stale allowlist だと discover_plugins→normalize_hook_entries が LayoutError で exit3 する)。
HOOK_EVENTS = (
    "PreToolUse",
    "PostToolUse",
    "UserPromptSubmit",
    "UserPromptExpansion",
    "Stop",
    "SubagentStop",
    "SessionStart",
    "SessionEnd",
    "Notification",
    "PreCompact",
    "PostCompact",
)
INVARIANTS = [f"INV-{index}" for index in range(1, 13)]
USAGE = """build-claude-settings.py [-h]
                                [--plugins-dir PLUGINS_DIR]
                                [--target TARGET]
                                [--exclude-plugin PLUGIN]
                                [--dry-run]
                                [--check]
                                [--print-user-section-hash]
                                [--json]
                                [--verbose]"""


class LayoutError(Exception):
    pass


class InvariantError(Exception):
    pass


class ContractHelpParser(argparse.ArgumentParser):
    def format_help(self):
        return f"usage: {USAGE}\n"


def parse_args(argv=None):
    parser = ContractHelpParser(prog="build-claude-settings.py", usage=USAGE)
    parser.add_argument("--plugins-dir", default="plugins")
    parser.add_argument("--target", default=".claude/settings.json")
    parser.add_argument("--exclude-plugin", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--print-user-section-hash", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def serialize(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def load_json_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LayoutError(f"invalid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise LayoutError(f"cannot read JSON: {path}: {exc}") from exc


def load_target(path):
    path = Path(path)
    if not path.exists():
        return {}
    if not path.is_file():
        raise LayoutError(f"target is not a file: {path}")
    data = load_json_file(path)
    if not isinstance(data, dict):
        raise LayoutError(f"target root must be an object: {path}")
    validate_settings_structure(data)
    return data


def hook_key(hook):
    return (hook["event"], hook.get("matcher") or "", hook["command"])


def permission_key(permission):
    return (permission["scope"], permission["rule"])


def command_from_hook_entry(entry):
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        raise LayoutError("hook entry must contain hooks array")
    commands = []
    for command_entry in hooks:
        if not isinstance(command_entry, dict):
            raise LayoutError("hook command entry must be an object")
        if command_entry.get("type") != "command":
            raise LayoutError("hook command entry type must be command")
        command = command_entry.get("command")
        if not isinstance(command, str) or not command:
            raise LayoutError("hook command entry command must be a non-empty string")
        commands.append(command)
    return commands


def normalize_hook_entries(hooks_obj, from_plugin, *, source="unknown"):
    if not isinstance(hooks_obj, dict):
        raise LayoutError("hooks must be an object")
    normalized = []
    for event in sorted(hooks_obj):
        if event not in HOOK_EVENTS:
            raise LayoutError(f"unknown hook event: {event}")
        entries = hooks_obj[event]
        if not isinstance(entries, list):
            raise LayoutError(f"hook event must be an array: {event}")
        for entry in entries:
            if not isinstance(entry, dict):
                raise LayoutError(f"hook entry must be an object: {event}")
            matcher = entry.get("matcher")
            if matcher is not None and not isinstance(matcher, str):
                raise LayoutError(f"hook matcher must be a string: {event}")
            for command in command_from_hook_entry(entry):
                normalized.append(
                    {
                        "event": event,
                        "matcher": matcher,
                        "command": command,
                        "from_plugin": from_plugin,
                        "source": source,
                    }
                )
    return normalized


def normalize_permissions(permissions_obj, from_plugin):
    if not isinstance(permissions_obj, dict):
        raise LayoutError("permissions must be an object")
    normalized = []
    for decision in ("deny", "ask"):
        rules = permissions_obj.get(decision, [])
        if not isinstance(rules, list):
            raise LayoutError(f"permissions.{decision} must be an array")
        for rule in rules:
            if not isinstance(rule, str) or not rule:
                raise LayoutError(f"permissions.{decision} rule must be a non-empty string")
            normalized.append(
                {
                    "scope": f"permissions.{decision}",
                    "decision": decision,
                    "rule": rule,
                    "from_plugin": from_plugin,
                }
            )
    return normalized


def read_skill_frontmatter_name(skill_dir):
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        raise LayoutError(f"skill item is missing SKILL.md: {skill_dir}")
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise LayoutError(f"cannot read skill file: {skill_file}: {exc}") from exc
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return None
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip().strip("\"'")
    return None


def namespace_items(plugin_dir, plugin_name):
    items = {"skills": [], "agents": [], "commands": []}
    skills_dir = plugin_dir / "skills"
    if skills_dir.exists():
        if not skills_dir.is_dir():
            raise LayoutError(f"skills path is not a directory: {skills_dir}")
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                raise LayoutError(f"skill item is not a directory: {skill_dir}")
            names = [skill_dir.name]
            frontmatter_name = read_skill_frontmatter_name(skill_dir)
            if frontmatter_name:
                names.append(frontmatter_name)
            real_path = str(skill_dir.resolve())
            for name in sorted(set(names)):
                items["skills"].append(
                    {
                        "name": name,
                        "from_plugin": plugin_name,
                        "verdict": "ok",
                        "real_path": real_path,
                    }
                )

    for kind in ("agents", "commands"):
        kind_dir = plugin_dir / kind
        if not kind_dir.exists():
            continue
        if not kind_dir.is_dir():
            raise LayoutError(f"{kind} path is not a directory: {kind_dir}")
        for item in sorted(kind_dir.iterdir()):
            if not item.is_file() or item.suffix != ".md":
                raise LayoutError(f"{kind} item must be a markdown file: {item}")
            items[kind].append(
                {
                    "name": item.name,
                    "from_plugin": plugin_name,
                    "verdict": "ok",
                    "real_path": str(item.resolve()),
                }
            )
    return items


def plugin_hooks_from_file(path, from_plugin):
    data = load_json_file(path)
    if not isinstance(data, dict):
        raise LayoutError(f"hook file root must be an object: {path}")
    if "hooks" in data:
        return normalize_hook_entries(data["hooks"], from_plugin, source=str(path))
    return normalize_hook_entries(data, from_plugin, source=str(path))


def plugin_permissions_from_file(path, from_plugin):
    data = load_json_file(path)
    if not isinstance(data, dict):
        raise LayoutError(f"permissions file root must be an object: {path}")
    if "permissions" in data:
        data = data["permissions"]
    return normalize_permissions(data, from_plugin)


PLUGIN_ROOT_VAR = "CLAUDE_PLUGIN_ROOT"
PROJECT_DIR_VAR = "CLAUDE_PROJECT_DIR"


def expand_plugin_root(command, plugin_path):
    """plugin hook の $CLAUDE_PLUGIN_ROOT を project 文脈で解決可能な形へ展開する。

    plugin manifest の hook command は plugin-manifest 文脈の $CLAUDE_PLUGIN_ROOT を
    使うが、flat な project .claude/settings.json へ反映すると同変数は未定義で hook が
    走らない。反映時に ${CLAUDE_PROJECT_DIR}/<plugin path> へ展開することで
    (a) project settings でも実際に解決でき、(b) plugin ごとに別パスへ解決されるため
    同名別実体の hook が偽の name/command 衝突 (INV-5) を起こさない。
    """
    replacement = "${%s}/%s" % (PROJECT_DIR_VAR, plugin_path)
    return command.replace(
        "${%s}" % PLUGIN_ROOT_VAR, replacement
    ).replace("$%s" % PLUGIN_ROOT_VAR, replacement)


def discover_plugins(plugins_dir, exclude_plugins=(), *, project_root=None):
    plugins_dir = Path(plugins_dir)
    project_root = Path(project_root).resolve() if project_root is not None else plugins_dir.resolve().parent
    if not plugins_dir.exists():
        return []
    if not plugins_dir.is_dir():
        raise LayoutError(f"plugins dir is not a directory: {plugins_dir}")

    excluded = set(exclude_plugins)
    plugins = []
    seen_names = {}
    for plugin_dir in sorted(path for path in plugins_dir.iterdir() if path.is_dir()):
        # Activation/source selection is owned by the caller (C01).  Exclude by
        # directory slug before reading the manifest so disabled/untrusted sources
        # cannot contribute hooks, permissions, or namespace entries.
        if plugin_dir.name in excluded:
            continue
        manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
        if not manifest_path.is_file():
            raise LayoutError(f"plugin manifest missing: {manifest_path}")
        manifest = load_json_file(manifest_path)
        if not isinstance(manifest, dict):
            raise LayoutError(f"plugin manifest root must be an object: {manifest_path}")
        name = manifest.get("name")
        if not isinstance(name, str) or not name:
            raise LayoutError(f"plugin manifest name must be a non-empty string: {manifest_path}")
        if name in seen_names:
            raise LayoutError(f"duplicate plugin name: {name}")
        seen_names[name] = plugin_dir
        plugin = {
            "name": name,
            "path": plugin_dir,
            "hooks": [],
            "permissions": [],
            "namespace": namespace_items(plugin_dir, name),
        }
        if "hooks" in manifest:
            plugin["hooks"].extend(
                normalize_hook_entries(
                    manifest["hooks"], name, source=f"{manifest_path}:inline"
                )
            )
        if "permissions" in manifest:
            plugin["permissions"].extend(normalize_permissions(manifest["permissions"], name))

        hooks_dir = plugin_dir / "hooks"
        if hooks_dir.exists():
            if not hooks_dir.is_dir():
                raise LayoutError(f"hooks path is not a directory: {hooks_dir}")
            for path in sorted(hooks_dir.glob("*.json")):
                plugin["hooks"].extend(plugin_hooks_from_file(path, name))

        permissions_path = plugin_dir / "settings" / "permissions.json"
        if permissions_path.exists():
            plugin["permissions"].extend(plugin_permissions_from_file(permissions_path, name))

        # project settings へ反映するため、この plugin の hook command 内の
        # $CLAUDE_PLUGIN_ROOT を当該 plugin の実パスへ展開する (同名別実体の
        # 偽 INV-5 衝突解消 + project 文脈での hook 実行可能化)。
        try:
            plugin_rel = plugin_dir.resolve().relative_to(project_root).as_posix()
        except ValueError as exc:
            raise LayoutError(
                f"plugins must be inside project root {project_root}: {plugin_dir}"
            ) from exc
        for hook in plugin["hooks"]:
            hook["command"] = expand_plugin_root(hook["command"], plugin_rel)
        plugins.append(plugin)
    return sorted(plugins, key=lambda item: item["name"])


def validate_settings_structure(data):
    permissions = data.get("permissions", {})
    if permissions is not None:
        if not isinstance(permissions, dict):
            raise LayoutError("permissions must be an object")
        for key in ("deny", "ask"):
            if key in permissions and not isinstance(permissions[key], list):
                raise LayoutError(f"permissions.{key} must be an array")
    hooks = data.get("hooks", {})
    if hooks is not None:
        if not isinstance(hooks, dict):
            raise LayoutError("hooks must be an object")
        for event, entries in hooks.items():
            if not isinstance(entries, list):
                raise LayoutError(f"hooks.{event} must be an array")
            if event not in HOOK_EVENTS:
                # 互換修復 (target=preserve / managed source=block の非対称化):
                # target の .claude/settings.json は、この script の HOOK_EVENTS
                # allowlist より新しい Claude Code event (例: FileChanged) を持ちうる。
                # 従来はここで raise して exit3 になり reflector が壊れていた。
                # managed source 側 (normalize_hook_entries) は従来どおり block のまま。
                #
                # 未知 event は別 owner の領域ゆえ内部 schema を検証せず opaque に素通し
                # (verbatim preserve)。managed event は必ず HOOK_EVENTS に含まれるため
                # 未知 event に managed command は入り得ず、remove_managed_values も
                # この event を skip する。将来の非標準 schema event にも頑健。
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    raise LayoutError(f"hooks.{event} entry must be an object")
                command_from_hook_entry(entry)


def managed_from_target(target):
    metadata = target.get("_build_claude_settings", {})
    if not isinstance(metadata, dict):
        return {"managed_hooks": [], "managed_permissions": []}
    return {
        "managed_hooks": metadata.get("managed_hooks", [])
        if isinstance(metadata.get("managed_hooks", []), list)
        else [],
        "managed_permissions": metadata.get("managed_permissions", [])
        if isinstance(metadata.get("managed_permissions", []), list)
        else [],
    }


def remove_managed_values(target):
    target = json.loads(serialize(target))
    metadata = managed_from_target(target)
    managed_hooks = set()
    for item in metadata["managed_hooks"]:
        if isinstance(item, dict) and "event" in item and "command" in item:
            managed_hooks.add((item["event"], item.get("matcher") or "", item["command"]))
    managed_permissions = set()
    for item in metadata["managed_permissions"]:
        if isinstance(item, dict) and "scope" in item and "rule" in item:
            managed_permissions.add((item["scope"], item["rule"]))

    target.pop("_build_claude_settings", None)
    hooks = target.get("hooks", {})
    if isinstance(hooks, dict):
        for event in list(hooks):
            if event not in HOOK_EVENTS:
                # 未知 target event は verbatim 保持する。managed event は必ず
                # HOOK_EVENTS に含まれる (managed source 側 normalize_hook_entries が
                # block するため) ので、未知 event に managed command は入り得ず、
                # ここで entry 内部を触る必要も剥がす対象も無い (非破壊 preserve)。
                continue
            entries = []
            for entry in hooks.get(event, []):
                matcher = entry.get("matcher")
                commands = command_from_hook_entry(entry)
                if all((event, matcher or "", command) not in managed_hooks for command in commands):
                    entries.append(entry)
            if entries:
                hooks[event] = entries
            else:
                hooks.pop(event, None)
        if not hooks:
            target.pop("hooks", None)

    permissions = target.get("permissions", {})
    if isinstance(permissions, dict):
        for decision in ("deny", "ask"):
            scope = f"permissions.{decision}"
            permissions[decision] = [
                rule
                for rule in permissions.get(decision, [])
                if (scope, rule) not in managed_permissions
            ]
        if not permissions.get("deny") and not permissions.get("ask"):
            target.pop("permissions", None)
    return target


def user_section_sha256(data):
    user_data = remove_managed_values(data)
    normalized = json.dumps(user_data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def namespace_preflight(plugins):
    namespace = {
        "plugins": [],
        "skills": [],
        "agents": [],
        "commands": [],
        "conflicts": [],
    }
    seen = {"skills": {}, "agents": {}, "commands": {}}
    for plugin in plugins:
        namespace["plugins"].append({"name": plugin["name"], "path": str(plugin["path"])})
        for kind in ("skills", "agents", "commands"):
            for item in plugin["namespace"][kind]:
                existing = seen[kind].get(item["name"])
                if existing is None:
                    # 初出。real_path も記録し、後続の同名を実体単位で照合する。
                    seen[kind][item["name"]] = item
                    namespace[kind].append(item)
                    continue
                if existing["real_path"] == item["real_path"]:
                    # 同名かつ同一実体 (symlink で共通コンテンツを共有) = 衝突でなく共有。
                    # 複数 plugin が意図的に 1 実体を symlink 参照する設計を尊重し dedupe する。
                    item = dict(item)
                    item["verdict"] = "shared"
                    namespace[kind].append(item)
                    continue
                # 同名かつ別実体 = 本物の名前衝突 (異なる中身が同名を奪い合う)。
                conflict = {
                    "type": kind[:-1],
                    "name": item["name"],
                    "plugins": sorted([existing["from_plugin"], item["from_plugin"]]),
                }
                namespace["conflicts"].append(conflict)
                item = dict(item)
                item["verdict"] = "conflict"
                namespace[kind].append(item)
    return namespace


def merge_hooks(user, plugins):
    generated = []
    for plugin in plugins:
        generated.extend(plugin["hooks"])
    generated = sorted(generated, key=lambda item: (item["from_plugin"], item["event"], item.get("matcher") or "", item["command"]))

    seen = {}
    conflicts = []
    deduped = []
    dedupe_count = 0
    for hook in generated:
        key = hook_key(hook)
        existing = seen.get(key)
        if existing and existing["from_plugin"] != hook["from_plugin"]:
            conflicts.append(
                {
                    "type": "hook",
                    "event": hook["event"],
                    "matcher": hook.get("matcher"),
                    "command": hook["command"],
                    "plugins": sorted([existing["from_plugin"], hook["from_plugin"]]),
                }
            )
            continue
        if existing:
            # A plugin may declare one native hook both in its inline Claude
            # manifest and in hooks/hooks.json for another native loader.  The
            # source declarations are evidence, not two runtime invocations.
            # Collapse only exact same-plugin hooks; cross-plugin ownership is
            # still an INV-5 conflict above.
            dedupe_count += 1
            continue
        seen[key] = hook
        deduped.append(hook)
    return deduped, conflicts, dedupe_count


def merge_permissions(plugins):
    generated = []
    for plugin in plugins:
        generated.extend(plugin["permissions"])
    generated = sorted(generated, key=lambda item: (item["from_plugin"], item["scope"], item["rule"]))

    exact = {}
    by_rule = {}
    conflicts = []
    deduped = []
    for permission in generated:
        exact_key = (permission["scope"], permission["decision"], permission["rule"])
        rule_key = permission["rule"]
        existing_decision = by_rule.get(rule_key)
        if existing_decision and existing_decision != permission["decision"]:
            conflicts.append(
                {
                    "type": "permission",
                    "rule": permission["rule"],
                    "decisions": sorted([existing_decision, permission["decision"]]),
                }
            )
            continue
        by_rule[rule_key] = permission["decision"]
        if exact_key in exact:
            exact[exact_key]["dedupe"] += 1
            continue
        exact[exact_key] = dict(permission)
        exact[exact_key]["dedupe"] = 0
        deduped.append(permission)
    return deduped, conflicts, sum(item["dedupe"] for item in exact.values())


def hook_entry(hook):
    entry = {"hooks": [{"type": "command", "command": hook["command"]}]}
    if hook.get("matcher") is not None:
        entry = {"matcher": hook["matcher"], **entry}
    return entry


def build_desired_settings(target, generated_hooks, generated_permissions):
    user_values = remove_managed_values(target)
    desired = {
        "_build_claude_settings": {
            "managed_hooks": [
                {
                    "event": hook["event"],
                    "matcher": hook.get("matcher"),
                    "command": hook["command"],
                    "from_plugin": hook["from_plugin"],
                }
                for hook in generated_hooks
            ],
            "managed_permissions": [
                {
                    "scope": permission["scope"],
                    "decision": permission["decision"],
                    "rule": permission["rule"],
                    "from_plugin": permission["from_plugin"],
                }
                for permission in generated_permissions
            ],
        }
    }

    permissions = user_values.pop("permissions", None)
    if not isinstance(permissions, dict):
        permissions = {}
    permissions.setdefault("deny", [])
    permissions.setdefault("ask", [])
    for permission in generated_permissions:
        decision = permission["decision"]
        if permission["rule"] not in permissions[decision]:
            permissions[decision].append(permission["rule"])
    desired["permissions"] = permissions

    hooks = user_values.pop("hooks", None)
    if not isinstance(hooks, dict):
        hooks = {}
    for hook in generated_hooks:
        hooks.setdefault(hook["event"], []).append(hook_entry(hook))
    desired["hooks"] = hooks

    for key, value in user_values.items():
        desired[key] = value
    validate_settings_structure(desired)
    return desired

def build_plan(target_path, plugins, namespace, generated_hooks, generated_permissions, conflicts, user_preserved, dedupe_count, excluded_plugins=()):
    hooks = [
        {
            "event": hook["event"],
            "matcher": hook.get("matcher"),
            "command": hook["command"],
            "from_plugin": hook["from_plugin"],
            "verdict": "add",
        }
        for hook in generated_hooks
    ]
    permissions = [
        {
            "scope": permission["decision"],
            "rule": permission["rule"],
            "from_plugin": permission["from_plugin"],
            "verdict": "add",
        }
        for permission in generated_permissions
    ]
    return {
        "target": str(target_path),
        "plugins": [plugin["name"] for plugin in plugins],
        "excluded_plugins": sorted(set(excluded_plugins)),
        "management_format": "_build_claude_settings.managed_hooks",
        "namespace": namespace,
        "conflicts": conflicts,
        "settings": {"hooks": hooks, "permissions": permissions},
        "user_values_preserved": user_preserved,
        "invariants_checked": INVARIANTS,
        "summary": {
            "add": len(hooks) + len(permissions),
            "keep": 0,
            "dedupe": dedupe_count,
            "conflict": len(conflicts),
        },
    }


def print_report(plan, as_json):
    if as_json:
        print(serialize(plan), end="")
        return
    summary = plan["summary"]
    print(
        "add={add} keep={keep} dedupe={dedupe} conflict={conflict}".format(
            **summary
        )
    )


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.rename(tmp, path)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def check_mode(target, desired):
    return serialize(target) == serialize(desired)


def build(target_path, plugins_dir, exclude_plugins=()):
    target = load_target(target_path)
    before_hash = user_section_sha256(target)
    project_root = Path(target_path).resolve().parent.parent
    plugins = discover_plugins(plugins_dir, exclude_plugins, project_root=project_root)
    namespace = namespace_preflight(plugins)
    generated_hooks, hook_conflicts, hook_dedupe_count = merge_hooks(target, plugins)
    generated_permissions, permission_conflicts, permission_dedupe_count = merge_permissions(plugins)
    dedupe_count = hook_dedupe_count + permission_dedupe_count
    conflicts = namespace["conflicts"] + hook_conflicts + permission_conflicts
    desired = build_desired_settings(target, generated_hooks, generated_permissions)
    after_hash = user_section_sha256(desired)
    user_preserved = before_hash == after_hash
    if not user_preserved:
        conflicts.append({"type": "invariant", "id": "INV-1", "message": "user values changed"})
    plan = build_plan(
        target_path,
        plugins,
        namespace,
        generated_hooks,
        generated_permissions,
        conflicts,
        user_preserved,
        dedupe_count,
        exclude_plugins,
    )
    return target, desired, plan


def main(argv=None):
    args = parse_args(argv)
    try:
        target_path = Path(args.target)
        target, desired, plan = build(target_path, args.plugins_dir, args.exclude_plugin)
        if args.print_user_section_hash:
            print(user_section_sha256(target))
            return 0
        if plan["conflicts"]:
            print_report(plan, args.json or args.dry_run or args.verbose)
            return 2
        if args.dry_run:
            print_report(plan, args.json or args.verbose)
            return 0
        if args.check:
            print_report(plan, args.json or args.verbose)
            return 0 if check_mode(target, desired) else 1
        before_hash = user_section_sha256(target)
        atomic_write(target_path, serialize(desired))
        after_hash = user_section_sha256(load_target(target_path))
        if before_hash != after_hash:
            raise InvariantError("INV-1 violation")
        print_report(plan, args.json or args.verbose)
        return 0
    except InvariantError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except LayoutError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())

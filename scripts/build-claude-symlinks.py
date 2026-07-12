#!/usr/bin/env python3
"""Build .claude symlinks from plugin-owned source trees."""

import argparse
import json
import os
import sys
from pathlib import Path


VALID_KINDS = ("agents", "skills", "commands")
USAGE = """build-claude-symlinks.py [-h]
                                [--plugins-dir PLUGINS_DIR]
                                [--target-dir TARGET_DIR]
                                [--kinds KINDS]
                                [--dry-run]
                                [--check]
                                [--prune]
                                [--exclude-plugin PLUGIN]
                                [--conflicts-only]
                                [--json]"""


class LayoutError(Exception):
    pass


class ContractHelpParser(argparse.ArgumentParser):
    def format_help(self):
        return f"usage: {USAGE}\n"


def parse_args(argv=None):
    parser = ContractHelpParser(
        prog="build-claude-symlinks.py",
        usage=USAGE,
    )
    parser.add_argument("--plugins-dir", default="plugins")
    parser.add_argument("--target-dir", default=".claude")
    parser.add_argument("--kinds", default="agents,skills,commands")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--exclude-plugin", action="append", default=[])
    parser.add_argument("--conflicts-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def parse_kinds(value):
    kinds = [kind.strip() for kind in value.split(",") if kind.strip()]
    if not kinds or any(kind not in VALID_KINDS for kind in kinds):
        raise LayoutError(f"invalid kinds: {value}")
    return kinds


def discover_plugins(plugins_dir, exclude_plugins=None):
    exclude_plugins = set(exclude_plugins or [])
    plugins_dir = Path(plugins_dir)
    if not plugins_dir.exists():
        raise LayoutError(f"plugins dir does not exist: {plugins_dir}")
    if not plugins_dir.is_dir():
        raise LayoutError(f"plugins dir is not a directory: {plugins_dir}")
    return sorted(
        path for path in plugins_dir.iterdir()
        if path.is_dir() and path.name not in exclude_plugins
    )


def discover_items(plugin, kind):
    kind_dir = plugin / kind
    if not kind_dir.exists():
        return []
    if not kind_dir.is_dir():
        raise LayoutError(f"{kind} path is not a directory: {kind_dir}")

    items = []
    for item in sorted(kind_dir.iterdir()):
        if kind == "skills":
            if not item.is_dir():
                raise LayoutError(f"skill item is not a directory: {item}")
            if not (item / "SKILL.md").is_file():
                raise LayoutError(f"skill item is missing SKILL.md: {item}")
        else:
            if not item.is_file():
                raise LayoutError(f"{kind} item is not a file: {item}")
            if item.suffix != ".md":
                raise LayoutError(f"{kind} item is not a markdown file: {item}")
        items.append(item)
    return items


def read_skill_frontmatter_name(skill_dir):
    skill_file = skill_dir / "SKILL.md"
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


def desired_entries(plugins_dir, target_dir, kinds, exclude_plugins=None):
    raw_entries = []
    identifiers = {}
    conflicts = set()

    for plugin in discover_plugins(plugins_dir, exclude_plugins=exclude_plugins):
        for kind in kinds:
            for item in discover_items(plugin, kind):
                dst = target_dir / kind / item.name
                entry = {"kind": kind, "src": item, "dst": dst}
                raw_entries.append(entry)
                names = [item.name]
                if kind == "skills":
                    frontmatter_name = read_skill_frontmatter_name(item)
                    if frontmatter_name:
                        names.append(frontmatter_name)
                for name in set(names):
                    key = (kind, name)
                    identifiers.setdefault(key, set()).add(item)

    # SSOT alias 解決: 複数 plugin の source が同一 realpath を指す場合 (symlink alias) は単一エントリ化する。
    # realpath が複数あれば本物の名前衝突として conflict にする。
    entries = []
    seen_dst = {}
    for entry in raw_entries:
        dst = entry["dst"]
        if dst not in seen_dst:
            seen_dst[dst] = []
        seen_dst[dst].append(entry)

    for dst, group in seen_dst.items():
        if len(group) == 1:
            entries.append(group[0])
            continue
        realpaths = {e["src"].resolve(strict=False) for e in group}
        if len(realpaths) == 1:
            canonical_real = next(iter(realpaths))
            canonical = next(
                (e for e in group if e["src"].resolve(strict=False) == e["src"].absolute() and not e["src"].is_symlink()),
                None,
            )
            if canonical is None:
                canonical = next((e for e in group if e["src"] == canonical_real), group[0])
            entries.append(canonical)
        else:
            for e in group:
                entries.append(e)
                conflicts.add(e["src"])

    for sources in identifiers.values():
        if len(sources) > 1:
            realpaths = {Path(s).resolve(strict=False) for s in sources}
            if len(realpaths) > 1:
                conflicts.update(sources)

    return entries, conflicts


def plan_item(action, src, dst, reason):
    return {
        "action": action,
        "src": str(src) if src is not None else "",
        "dst": str(dst),
        "reason": reason,
    }


def is_known_source(readlink_value, dst, source_paths):
    target = (dst.parent / readlink_value).resolve(strict=False)
    return target in source_paths


def compute_plan(plugins_dir, target_dir, kinds, prune=False, exclude_plugins=None):
    plugins_dir = Path(plugins_dir)
    target_dir = Path(target_dir)
    entries, conflicts = desired_entries(
        plugins_dir, target_dir, kinds, exclude_plugins=exclude_plugins
    )
    source_paths = {entry["src"].resolve(strict=False) for entry in entries}
    desired_dsts = {entry["dst"] for entry in entries}
    plan = []

    for entry in entries:
        src = entry["src"]
        dst = entry["dst"]
        if src in conflicts:
            plan.append(plan_item("conflict", src, dst, "name conflict"))
            continue

        src_rel = os.path.relpath(src, dst.parent)
        if dst.is_symlink():
            current = os.readlink(dst)
            if current == src_rel:
                plan.append(plan_item("noop", src, dst, "already linked"))
            else:
                plan.append(plan_item("update", src, dst, "wrong target"))
        elif dst.exists():
            plan.append(plan_item("conflict", src, dst, "real file/dir found"))
        else:
            plan.append(plan_item("create", src, dst, "missing symlink"))

    for kind in kinds:
        kind_dir = target_dir / kind
        if not kind_dir.exists():
            continue
        if not kind_dir.is_dir():
            plan.append(plan_item("conflict", None, kind_dir, "target kind path is not a directory"))
            continue
        for dst in sorted(kind_dir.iterdir()):
            if dst in desired_dsts or not dst.is_symlink():
                continue
            current = os.readlink(dst)
            target_exists = (dst.parent / current).exists()
            reason = "orphan symlink" if is_known_source(current, dst, source_paths) else "orphan symlink"
            if not target_exists:
                reason = "broken symlink"
            if prune:
                plan.append(plan_item("update", None, dst, f"prune {reason}"))
            else:
                plan.append(plan_item("noop", None, dst, reason))

    return plan


def summarize(plan):
    summary = {"created": 0, "updated": 0, "noop": 0, "conflict": 0}
    for item in plan:
        if item["action"] == "create":
            summary["created"] += 1
        elif item["action"] == "update":
            summary["updated"] += 1
        elif item["action"] == "noop":
            summary["noop"] += 1
        elif item["action"] == "conflict":
            summary["conflict"] += 1
    return summary


def apply_plan(plan, dry_run=False):
    if dry_run:
        return
    for item in plan:
        action = item["action"]
        if action == "noop" or action == "conflict":
            continue
        dst = Path(item["dst"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        if action == "update" and item["src"] == "":
            dst.unlink()
            continue
        src = Path(item["src"])
        src_rel = os.path.relpath(src, dst.parent)
        if action == "update":
            dst.unlink()
        dst.symlink_to(src_rel)


def check_drift(plan):
    for item in plan:
        if item["action"] in ("create", "update", "conflict"):
            return True
        if item["reason"] in ("broken symlink", "orphan symlink"):
            return True
    return False


def build_report(plugins_dir, target_dir, kinds, plan, exclude_plugins=None):
    return {
        "plugins_dir": str(plugins_dir),
        "target_dir": str(target_dir),
        "kinds": kinds,
        "exclude_plugins": list(exclude_plugins or []),
        "plan": plan,
        "summary": summarize(plan),
    }


def print_report(report, as_json):
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    summary = report["summary"]
    print(
        "created={created} updated={updated} noop={noop} conflict={conflict}".format(
            **summary
        )
    )


def main(argv=None):
    args = parse_args(argv)
    try:
        kinds = parse_kinds(args.kinds)
        plan = compute_plan(
            args.plugins_dir,
            args.target_dir,
            kinds,
            prune=args.prune,
            exclude_plugins=args.exclude_plugin,
        )
        report = build_report(
            args.plugins_dir,
            args.target_dir,
            kinds,
            plan,
            exclude_plugins=args.exclude_plugin,
        )
        if report["summary"]["conflict"]:
            print_report(report, args.json or args.dry_run)
            return 2
        if args.conflicts_only:
            print_report(report, args.json or args.dry_run)
            return 0
        if args.check:
            print_report(report, args.json or args.dry_run)
            return 1 if check_drift(plan) else 0
        apply_plan(plan, dry_run=args.dry_run)
        print_report(report, args.json or args.dry_run)
        return 0
    except LayoutError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())

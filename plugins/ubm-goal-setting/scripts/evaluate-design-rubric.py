#!/usr/bin/env python3
# /// script
# name: evaluate-design-rubric
# purpose: Inject the registered UBM L1 into the existing design-rubric evaluator.
# inputs: [--repo-root, --target]
# outputs: [stdout evaluator JSON, stderr diagnostics]
# network: false
# write-scope: none
# dependencies: []
# ///
"""UBM-only review routing; semantic quality remains an independent review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

DOMAIN = "ubm-goal-setting"


def evaluation_command(repo_root: Path, target: Path) -> list[str]:
    root = repo_root.resolve(strict=True)
    plugin = (root / "plugins" / DOMAIN).resolve(strict=True)
    if plugin != Path(__file__).resolve().parents[1]:
        raise ValueError("repo-root does not contain this UBM evaluator runner")
    manifest = json.loads((plugin / ".claude-plugin/plugin.json").read_text())
    if manifest.get("name") != DOMAIN:
        raise ValueError("UBM plugin identity mismatch")
    source = target.resolve(strict=True)
    if (source.name != "SKILL.md" or source.parent.parent != plugin / "skills"
            or not source.parent.name.startswith("run-ubm-")):
        raise ValueError("target must be a UBM entrypoint in this plugin")
    registry = json.loads((root / "plugins/skill-governance-config/config/rubric-registry.json").read_text())
    entries = [item for item in registry.get("rubrics", []) if item.get("domain") == DOMAIN]
    if len(entries) != 1:
        raise ValueError("exactly one registered UBM L1 is required")
    entry = entries[0]
    l0 = root / "plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json"
    registered_path = root / entry["rubric"]
    l1 = registered_path.resolve(strict=True)
    expected_l1 = plugin / "skills/run-ubm-knowledge-sync/references/rubric.json"
    if (registered_path != expected_l1 or expected_l1.is_symlink()
            or not expected_l1.is_file() or l1 != expected_l1
            or not l1.is_relative_to(plugin)):
        raise ValueError("registered UBM L1 must resolve to its declared local owner")
    data = json.loads(l1.read_text())
    if (entry.get("layer") != "L1" or data.get("layer") != "L1"
            or data.get("domain") != DOMAIN
            or entry.get("merge_strategy") != "deep-merge"
            or entry.get("conflict_policy") != "most-specific-wins"):
        raise ValueError("invalid registered UBM L1 composition contract")
    evaluator = root / "plugins/harness-creator/skills/assign-skill-design-evaluator"
    l2 = evaluator / "references/rubric.json"
    return [sys.executable, str(evaluator / "scripts/render-findings-score.py"),
            "--rubric-refs", str(l0), str(l1), str(l2), "--target", str(source),
            "--merge-strategy", "deep-merge", "--conflict-policy", "most-specific-wins",
            "--emit-hash"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    try:
        command = evaluation_command(args.repo_root, args.target)
        return subprocess.run(command, check=False).returncode
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"UBM_REVIEW_ROUTING_INVALID: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

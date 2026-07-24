#!/usr/bin/env python3
# /// script
# name: validate-plugin-completeness
# purpose: slide-report-generatorのplugin surfaceとentry point完全性を検証する。
# inputs:
#   - argv: none
# outputs:
#   - stdout: PASS status
#   - stderr: completeness findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""validate-plugin-completeness.py - plugin surface completeness gate.

Checks the local slide-report-generator plugin without importing project
dependencies. The gate intentionally stays small and stdlib-only so it can run
before vendor/node_modules are installed.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
REQUIRED_TOP_LEVEL = (
    "README.md",
    "plugin-composition.yaml",
    "EVALS.json",
)
PLACEHOLDER_TOKENS = ("[TODO", "TODO:", "{{TODO", "未定義")
# lint-feedback-protocol R7 で全 product plugin に配備される共有 vendored skill。
# skills/run-skill-feedback は harness-creator SSOT への symlink であり所有 skill では
# ないため、他 product plugin (notion-gmail-send / mf-kessai-invoice-check 等) と同様
# entry_points.skills には宣言しない。completeness 突合でも所有計上から除外する。
SHARED_SKILLS = frozenset({"run-skill-feedback"})
MAX_AGENT_ADAPTER_LINES = 80
PROMPT_REF_RE = re.compile(
    r"^skills/[a-z][a-z0-9-]*/prompts/R[0-9]+(-[a-z0-9]+)*\.md$"
)
AGENT_REQUIRED_SECTIONS = (
    "## Purpose",
    "## Inputs",
    "## Outputs",
    "## Goal-Seeking Execution",
    "## Constraints",
    "## Prompt Templates",
    "## Self-Evaluation",
    "## Handoff",
)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_manifest(errors: list[str]) -> dict:
    if not MANIFEST_PATH.exists():
        fail(errors, f"manifest missing: {MANIFEST_PATH.relative_to(PLUGIN_ROOT)}")
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(errors, f"manifest JSON invalid: {exc}")
        return {}


def check_placeholders(errors: list[str], path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for token in PLACEHOLDER_TOKENS:
        if token in text:
            fail(errors, f"placeholder token {token!r} found in {path.relative_to(PLUGIN_ROOT)}")


def names_in_dir(path: Path, suffix: str = "") -> list[str]:
    if not path.exists():
        return []
    if suffix:
        return sorted(p.name[: -len(suffix)] for p in path.glob(f"*{suffix}") if p.is_file())
    return sorted(p.name for p in path.iterdir() if p.is_dir())


def check_entry_points(errors: list[str], manifest: dict) -> None:
    entry_points = manifest.get("entry_points")
    if not isinstance(entry_points, dict):
        fail(errors, "entry_points object missing")
        return

    expected = {
        "skills": [s for s in names_in_dir(PLUGIN_ROOT / "skills") if s not in SHARED_SKILLS],
        "agents": names_in_dir(PLUGIN_ROOT / "agents", ".md"),
        "commands": names_in_dir(PLUGIN_ROOT / "commands", ".md"),
    }
    for key, actual in expected.items():
        declared = sorted(entry_points.get(key, []))
        if declared != actual:
            fail(errors, f"entry_points.{key} mismatch: declared={declared} actual={actual}")


def parse_frontmatter(path: Path, errors: list[str]) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(errors, f"frontmatter missing: {path.relative_to(PLUGIN_ROOT)}")
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        fail(errors, f"frontmatter malformed: {path.relative_to(PLUGIN_ROOT)}")
        return {}
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def check_thin_agent_adapters(errors: list[str]) -> None:
    """Enforce harness-creator style: agents are Task adapters, prompts live in skills."""
    agents_dir = PLUGIN_ROOT / "agents"
    nested_prompt_dirs = sorted((PLUGIN_ROOT / "skills").glob("*/prompts/*/"))
    for nested in nested_prompt_dirs:
        if nested.name != "__pycache__":
            fail(
                errors,
                f"nested prompts directory forbidden by prompt-placement-convention: "
                f"{nested.relative_to(PLUGIN_ROOT)}",
            )
    for path in sorted(agents_dir.glob("*.md")):
        rel = path.relative_to(PLUGIN_ROOT)
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if len(lines) > MAX_AGENT_ADAPTER_LINES:
            fail(
                errors,
                f"agent adapter too large: {rel} has {len(lines)} lines "
                f"(max {MAX_AGENT_ADAPTER_LINES}); move detail to skills/*/prompts/agents/",
            )
        fm = parse_frontmatter(path, errors)
        owner_skill = fm.get("owner_skill", "")
        prompt_ref = fm.get("prompt_ref", "")
        if not owner_skill:
            fail(errors, f"agent owner_skill missing: {rel}")
        if not prompt_ref:
            fail(errors, f"agent prompt_ref missing: {rel}")
            continue
        if not PROMPT_REF_RE.match(prompt_ref):
            fail(
                errors,
                f"agent prompt_ref must be flat prompts/R*.md path: {rel} -> {prompt_ref}",
            )
        prompt_path = PLUGIN_ROOT / prompt_ref
        if not prompt_path.exists():
            fail(errors, f"agent prompt_ref target missing: {rel} -> {prompt_ref}")
        expected_prefix = f"skills/{owner_skill}/prompts/"
        if owner_skill and not prompt_ref.startswith(expected_prefix):
            fail(
                errors,
                f"agent prompt_ref must be packaged under owner skill: "
                f"{rel} owner={owner_skill} prompt_ref={prompt_ref}",
            )
        prompt_id = Path(prompt_ref).stem
        if f"<!-- responsibility: {prompt_id} -->" not in text:
            fail(errors, f"agent responsibility anchor missing: {rel} -> {prompt_id}")
        for section in AGENT_REQUIRED_SECTIONS:
            if section not in text:
                fail(errors, f"agent required section missing: {rel} -> {section}")


def check_hooks(errors: list[str], manifest: dict) -> None:
    hooks = manifest.get("hooks", {})
    if not hooks:
        fail(errors, "hooks object missing")
        return
    for event, configs in hooks.items():
        if not isinstance(configs, list):
            fail(errors, f"hooks.{event} must be a list")
            continue
        for i, config in enumerate(configs):
            for j, hook in enumerate(config.get("hooks", [])):
                command = hook.get("command", "")
                if "$CLAUDE_PLUGIN_ROOT/" not in command:
                    fail(errors, f"hooks.{event}[{i}].hooks[{j}] command must use $CLAUDE_PLUGIN_ROOT")
                    continue
                rel = command.split("$CLAUDE_PLUGIN_ROOT/", 1)[1].split()[0]
                if not (PLUGIN_ROOT / rel).exists():
                    fail(errors, f"hook command target missing: {rel}")


def check_plugin_surfaces(errors: list[str]) -> None:
    for rel in REQUIRED_TOP_LEVEL:
        if not (PLUGIN_ROOT / rel).exists():
            fail(errors, f"required surface missing: {rel}")
    for rel in ("schemas", "references", "vendor"):
        if not (PLUGIN_ROOT / rel).is_dir():
            fail(errors, f"required directory missing: {rel}")


def main() -> int:
    errors: list[str] = []
    manifest = load_manifest(errors)

    if manifest:
        if manifest.get("name") != PLUGIN_ROOT.name:
            fail(errors, f"manifest name must match folder: {manifest.get('name')!r} != {PLUGIN_ROOT.name!r}")
        if manifest.get("distributable") is not False:
            fail(errors, "distributable must be false for this local-only plugin")
        if manifest.get("bundle_targets") != []:
            fail(errors, "bundle_targets must be an empty array when distributable=false")
        check_placeholders(errors, MANIFEST_PATH)
        check_entry_points(errors, manifest)
        check_hooks(errors, manifest)

    check_plugin_surfaces(errors)
    check_thin_agent_adapters(errors)

    if errors:
        print("plugin completeness: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"plugin completeness: PASS ({PLUGIN_ROOT.name})")
    return 0


if __name__ == "__main__":
    os.chdir(PLUGIN_ROOT)
    sys.exit(main())

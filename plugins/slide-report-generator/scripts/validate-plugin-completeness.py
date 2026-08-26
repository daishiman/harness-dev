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
import shlex
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
NATIVE_MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
PACKAGE_CONTRACT_PATH = PLUGIN_ROOT / "references" / "package-contract.json"
REQUIRED_TOP_LEVEL = (
    "README.md",
    "plugin-composition.yaml",
    "EVALS.json",
)
PLACEHOLDER_TOKENS = ("[TODO", "TODO:", "{{TODO", "未定義")
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
COMPOSITION_SCRIPT_RE = re.compile(
    r"\{\s*kind:\s*script,\s*ref:\s*(scripts/[A-Za-z0-9_.-]+)\s*,"
)
# scripts/ 直下で「実体」として数える拡張子。宣言側 (COMPOSITION_SCRIPT_RE) は拡張子を
# 問わないので、集合一致の網の広さはこの集合だけで決まる。ここに無い拡張子で検査器を
# 書くと、plugin-composition.yaml へ配線しないまま素通りする。実際 .mjs が抜けており、
# .mjs の検査器 2 本が未宣言のまま通っていた。実行系を増やしたらここへ足すこと。
SCRIPT_SUFFIXES = frozenset({".py", ".js", ".cjs", ".mjs"})


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(errors: list[str], path: Path, label: str) -> dict:
    if not path.exists():
        fail(errors, f"{label} missing: {path.relative_to(PLUGIN_ROOT)}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            fail(errors, f"{label} must be a JSON object")
            return {}
        return data
    except json.JSONDecodeError as exc:
        fail(errors, f"{label} JSON invalid: {exc}")
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


def check_entry_points(errors: list[str], contract: dict) -> None:
    """Package inventory is owned by package-contract, not the native manifest."""
    entry_points = contract.get("entry_points")
    if not isinstance(entry_points, dict):
        fail(errors, "package-contract entry_points object missing")
        return

    expected = {
        "skills": names_in_dir(PLUGIN_ROOT / "skills"),
        "agents": names_in_dir(PLUGIN_ROOT / "agents", ".md"),
        "commands": names_in_dir(PLUGIN_ROOT / "commands", ".md"),
        "hooks": sorted(
            p.name
            for p in (PLUGIN_ROOT / "hooks").iterdir()
            if p.is_file() and p.suffix in {".py", ".sh"}
        ),
    }
    for key, actual in expected.items():
        declared_raw = entry_points.get(key)
        if not isinstance(declared_raw, list) or not all(isinstance(v, str) for v in declared_raw):
            fail(errors, f"package-contract entry_points.{key} must be a string array")
            continue
        declared = sorted(declared_raw)
        if declared != actual:
            fail(
                errors,
                f"package-contract entry_points.{key} mismatch: "
                f"declared={declared} actual={actual}",
            )


def check_distribution(errors: list[str], contract: dict) -> None:
    distribution = contract.get("distribution")
    if not isinstance(distribution, dict):
        fail(errors, "package-contract distribution object missing")
        return
    distributable = distribution.get("distributable")
    targets = distribution.get("bundle_targets")
    if not isinstance(distributable, bool):
        fail(errors, "package-contract distribution.distributable must be boolean")
    if not isinstance(targets, list) or not all(isinstance(v, str) for v in targets):
        fail(errors, "package-contract distribution.bundle_targets must be a string array")
    elif distributable is False and targets:
        fail(errors, "package-contract bundle_targets must be empty when distributable=false")
    elif distributable is True and not targets:
        fail(errors, "package-contract bundle_targets must not be empty when distributable=true")


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
    # 禁止したいのは「prompt をディレクトリで階層化すること」。prompt_ref は
    # PROMPT_REF_RE で flat な skills/<skill>/prompts/R*.md に限っており、階層を作ると
    # 参照できない prompt が prompts/ の下に溜まる。それを防ぐのがこの検査の目的。
    #
    # 旧実装は glob("*/prompts/*/") で、末尾スラッシュの解釈が python の版で違った
    # (3.9 は無視してファイルも一致し 20 件 FAIL / 3.11+ は 0 件)。同じ木で結論が割れる
    # ので、どちらが元の意図だったかは書いてある情報からは決まらない。決められないため
    # 推測で確定させず、上の目的を新しい正として is_dir() で明示する。
    # (script header は requires-python >=3.10 だが shebang は env python3 で、3.9 でも
    #  起動できてしまう。is_dir() なら起動した版に関係なく同じものを返す)
    nested_prompt_dirs = sorted(
        path for path in (PLUGIN_ROOT / "skills").glob("*/prompts/*") if path.is_dir()
    )
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
                f"(max {MAX_AGENT_ADAPTER_LINES}); move detail into the flat prompt this "
                f"agent already points at (skills/<owner_skill>/prompts/R*.md)",
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


def check_hooks(errors: list[str], manifest: dict, contract: dict) -> None:
    hook_ref = manifest.get("hooks")
    if not isinstance(hook_ref, str) or not hook_ref:
        fail(errors, "manifest hooks must reference a plugin-relative hooks.json")
        return
    hook_path = (PLUGIN_ROOT / hook_ref).resolve()
    try:
        hook_path.relative_to(PLUGIN_ROOT.resolve())
    except ValueError:
        fail(errors, f"manifest hooks reference escapes plugin root: {hook_ref}")
        return
    hook_doc = load_json(errors, hook_path, "hook config")
    hooks = hook_doc.get("hooks") if hook_doc else None
    if not isinstance(hooks, dict) or not hooks:
        fail(errors, "hook config hooks object missing")
        return
    declared = set(contract.get("entry_points", {}).get("hooks", []))
    wired: set[str] = set()
    for event, configs in hooks.items():
        if not isinstance(configs, list):
            fail(errors, f"hooks.{event} must be a list")
            continue
        for i, config in enumerate(configs):
            if not isinstance(config, dict):
                fail(errors, f"hooks.{event}[{i}] must be an object")
                continue
            for j, hook in enumerate(config.get("hooks", [])):
                if not isinstance(hook, dict):
                    fail(errors, f"hooks.{event}[{i}].hooks[{j}] must be an object")
                    continue
                command = hook.get("command", "")
                if not isinstance(command, str) or not command:
                    fail(errors, f"hooks.{event}[{i}].hooks[{j}] command missing")
                    continue
                try:
                    tokens = shlex.split(command)
                except ValueError as exc:
                    fail(errors, f"hooks.{event}[{i}].hooks[{j}] command malformed: {exc}")
                    continue
                targets = [
                    match.group(1)
                    for token in tokens
                    if (match := re.search(r"/hooks/([A-Za-z0-9_.-]+)$", token))
                ]
                if len(targets) != 1:
                    fail(
                        errors,
                        f"hooks.{event}[{i}].hooks[{j}] must reference exactly one hooks/* target",
                    )
                    continue
                name = targets[0]
                wired.add(name)
                if name not in declared:
                    fail(errors, f"hook target not declared in package-contract: {name}")
                if not (PLUGIN_ROOT / "hooks" / name).is_file():
                    fail(errors, f"hook command target missing: hooks/{name}")
    if wired != declared:
        fail(errors, f"hook wiring mismatch: wired={sorted(wired)} declared={sorted(declared)}")


def check_plugin_surfaces(errors: list[str]) -> None:
    for rel in REQUIRED_TOP_LEVEL:
        if not (PLUGIN_ROOT / rel).exists():
            fail(errors, f"required surface missing: {rel}")
    for rel in ("schemas", "references", "vendor"):
        if not (PLUGIN_ROOT / rel).is_dir():
            fail(errors, f"required directory missing: {rel}")


def check_script_inventory(errors: list[str]) -> None:
    """plugin-composition の script 宣言と scripts/ 直下の実体を集合一致させる。"""
    composition = PLUGIN_ROOT / "plugin-composition.yaml"
    if not composition.exists():
        return
    declared = sorted(set(COMPOSITION_SCRIPT_RE.findall(composition.read_text(encoding="utf-8"))))
    actual = sorted(
        str(path.relative_to(PLUGIN_ROOT))
        for path in (PLUGIN_ROOT / "scripts").iterdir()
        if path.is_file() and path.suffix in SCRIPT_SUFFIXES
    )
    if declared != actual:
        missing = sorted(set(actual) - set(declared))
        dangling = sorted(set(declared) - set(actual))
        fail(
            errors,
            "plugin-composition script inventory mismatch: "
            f"undeclared={missing} dangling={dangling}",
        )


def main() -> int:
    errors: list[str] = []
    manifest = load_json(errors, MANIFEST_PATH, "manifest")
    native_manifest = load_json(errors, NATIVE_MANIFEST_PATH, "native manifest")
    contract = load_json(errors, PACKAGE_CONTRACT_PATH, "package contract")

    if manifest:
        if manifest.get("name") != PLUGIN_ROOT.name:
            fail(errors, f"manifest name must match folder: {manifest.get('name')!r} != {PLUGIN_ROOT.name!r}")
        check_placeholders(errors, MANIFEST_PATH)
    if native_manifest:
        if native_manifest.get("name") != PLUGIN_ROOT.name:
            fail(
                errors,
                f"native manifest name must match folder: "
                f"{native_manifest.get('name')!r} != {PLUGIN_ROOT.name!r}",
            )
        check_placeholders(errors, NATIVE_MANIFEST_PATH)
    if contract:
        if contract.get("plugin_name") != PLUGIN_ROOT.name:
            fail(
                errors,
                f"package-contract plugin_name must match folder: "
                f"{contract.get('plugin_name')!r} != {PLUGIN_ROOT.name!r}",
            )
        check_placeholders(errors, PACKAGE_CONTRACT_PATH)
        check_entry_points(errors, contract)
        check_distribution(errors, contract)
    if native_manifest and contract:
        check_hooks(errors, native_manifest, contract)

    check_plugin_surfaces(errors)
    check_script_inventory(errors)
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

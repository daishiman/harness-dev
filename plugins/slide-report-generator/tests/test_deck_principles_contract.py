from __future__ import annotations

import builtins
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SELECTOR_PATH = PLUGIN_ROOT / "scripts" / "extract-deck-principles.py"
VALIDATOR_PATH = PLUGIN_ROOT / "scripts" / "validate-deck-principles.py"
CATALOG_DIR = PLUGIN_ROOT / "references" / "deck-principles"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_selector(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["DECK_PRINCIPLES_DIR"] = str(CATALOG_DIR)
    return subprocess.run(
        [sys.executable, str(SELECTOR_PATH), *args],
        cwd=PLUGIN_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_xref_parser_expands_range_and_short_slash() -> None:
    selector = load_module("deck_principles_selector", SELECTOR_PATH)
    assert selector.extract_xrefs("DP-022〜025 と DP-076/079/081") == [
        "DP-022",
        "DP-023",
        "DP-024",
        "DP-025",
        "DP-076",
        "DP-079",
        "DP-081",
    ]


def test_json_selection_envelope_and_tool_projection() -> None:
    proc = run_selector(
        "--consumer",
        "structure-designer",
        "--tool",
        "google-slides",
        "--format",
        "json",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    selection = payload["selection"]
    assert selection["consumer"] == "structure-designer"
    assert selection["catalog_digest"].startswith("sha256:")
    assert selection["selected_ids"] == [item["id"] for item in payload["selected"]]
    assert selection["xref_ids"] == [item["id"] for item in payload["xrefs"]]
    assert selection["tool_adapter"]["id"] == "google-slides"
    assert selection["budgets"] == {"base_limit": 16, "xref_limit": 8}


def test_xref_budget_fails_instead_of_silent_truncation() -> None:
    proc = run_selector("--applies-to", "doc", "--phase", "write", "--limit", "16", "--xref-limit", "1")
    assert proc.returncode == 2
    assert "依存を黙って欠落させない" in proc.stderr


def test_schema_dependency_missing_is_a_failure() -> None:
    validator = load_module("deck_principles_validator", VALIDATOR_PATH)
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("forced missing dependency")
        return real_import(name, *args, **kwargs)

    report = validator.Report()
    with mock.patch("builtins.__import__", side_effect=guarded_import):
        validator.validate_schema({}, PLUGIN_ROOT / "schemas" / "deck-principles.schema.json", "catalog", report)
    assert report.errors
    assert "jsonschema が未導入" in report.errors[0]


def test_binding_partitions_are_an_exclusive_closure() -> None:
    catalog = json.loads((CATALOG_DIR / "principles.json").read_text(encoding="utf-8"))
    binding = json.loads((CATALOG_DIR / "binding.json").read_text(encoding="utf-8"))
    all_ids = {item["id"] for item in catalog["principles"]}
    mapped = set(binding["mapped_by_filter"]["refs"])
    enforced = {ref for item in binding["already_enforced"]["map"] for ref in item["refs"]}
    excluded = set(binding["out_of_scope"]["refs"])
    assert not (mapped & enforced)
    assert not (mapped & excluded)
    assert not (enforced & excluded)
    assert mapped | enforced | excluded == all_ids


def test_consumer_scope_closes_owner_agents_with_explicit_renderer_exclusion() -> None:
    binding = json.loads((CATALOG_DIR / "binding.json").read_text(encoding="utf-8"))
    owners = set(binding["consumer_scope"]["owner_skills"])
    expected: set[str] = set()
    for path in (PLUGIN_ROOT / "agents").glob("*.md"):
        fields = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(("name:", "owner_skill:")):
                key, value = line.split(":", 1)
                fields[key] = value.strip()
        if fields.get("owner_skill") in owners:
            expected.add(fields.get("name", path.stem))
    consumers = {item["id"] for item in binding["consumers"]}
    excluded = {item["id"] for item in binding["consumer_scope"]["excluded_agents"]}
    assert consumers | excluded == expected
    assert not consumers & excluded
    assert excluded == {"slide-renderer"}
    assert "ai-image-diagram-producer" in consumers


def test_ai_image_consumer_selects_principles_and_has_exact_marker() -> None:
    proc = run_selector("--consumer", "ai-image-diagram-producer", "--format", "json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["selection"]["selected_ids"]
    prompt = (
        PLUGIN_ROOT
        / "skills/run-slide-report-generate/prompts/R3-agent-ai-image-diagram-producer.md"
    ).read_text(encoding="utf-8")
    marker = "<!-- deck-principles-consumer: ai-image-diagram-producer; run-by: agent -->"
    assert prompt.count(marker) == 1


def test_binding_conforms_to_versioned_schema() -> None:
    import jsonschema

    binding = json.loads((CATALOG_DIR / "binding.json").read_text(encoding="utf-8"))
    schema = json.loads(
        (PLUGIN_ROOT / "schemas" / "deck-principles-binding.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft7Validator(schema).validate(binding)


def test_full_validator_includes_manifest_parity() -> None:
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        cwd=PLUGIN_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "PASS principles=" in proc.stdout


def test_composition_declares_generate_and_modify_selector_dependencies() -> None:
    composition = (PLUGIN_ROOT / "plugin-composition.yaml").read_text(encoding="utf-8")
    lines = composition.splitlines()
    for owner in ("skills/run-slide-report-generate", "skills/run-slide-report-modify"):
        assert any(
            f"from: {owner}," in line and "to: scripts/extract-deck-principles.py" in line
            for line in lines
        )
        assert any(
            f"from: {owner}," in line
            and "to: references/deck-principles/consumer-bootstrap.md" in line
            for line in lines
        )

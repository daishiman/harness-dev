"""deck-principles の guide-local overlay と standalone 配布境界を固定する。"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
SOURCE_ROOT = REPO_ROOT / "plugins" / "slide-report-generator"
ASSET_DIR = PLUGIN_ROOT / "assets" / "deck-principles"
SELECTOR = PLUGIN_ROOT / "scripts" / "extract-deck-principles.py"
BINDING = ASSET_DIR / "binding.json"

ROOT_ENV_KEYS = (
    "DECK_PRINCIPLES_DIR",
    "SRG_ROOT",
    "HB_ROOT",
    "PLUGIN_ROOT",
    "CLAUDE_PLUGIN_ROOT",
)
EXPECTED_CONSUMERS = {
    "handout-content-architect": "orchestrator",
    "handout-readability-reviewer": "agent",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_selector():
    spec = importlib.util.spec_from_file_location("guide_deck_principles_selector", SELECTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ROOT_ENV_KEYS:
        env.pop(key, None)
    return env


def test_binding_is_a_guide_local_overlay_only() -> None:
    binding = _load_json(BINDING)
    consumers = binding["consumers"]
    assert {item["id"]: item["run_by"] for item in consumers} == EXPECTED_CONSUMERS
    assert {item["plugin"] for item in consumers} == {"guide-doc-generator"}
    assert str(binding.get("$schema", "")).endswith("deck-principles-binding.schema.json")
    assert set(binding["consumer_scope"]["owner_skills"]) == {
        "run-handout-build",
        "assign-handout-readability-evaluator",
    }
    assert binding["consumer_scope"]["excluded_agents"] == []


def test_binding_conforms_to_shared_schema_and_closes_the_local_partition() -> None:
    import jsonschema

    binding = _load_json(BINDING)
    catalog = _load_json(ASSET_DIR / "principles.json")
    schema = _load_json(SOURCE_ROOT / "schemas" / "deck-principles-binding.schema.json")
    jsonschema.Draft7Validator(schema).validate(binding)

    all_ids = {item["id"] for item in catalog["principles"]}
    already = {
        ref
        for entry in binding["already_enforced"]["map"]
        for ref in entry["refs"]
    }
    mapped = set(binding["mapped_by_filter"]["refs"])
    out_of_scope = set(binding["out_of_scope"]["refs"])

    assert not (mapped & already or mapped & out_of_scope or already & out_of_scope)
    assert mapped | already | out_of_scope == all_ids

    expected_mapped: set[str] = set()
    for consumer in binding["consumers"]:
        argv = consumer["select"]
        applies_to = [argv[index + 1] for index, arg in enumerate(argv) if arg == "--applies-to"]
        phases = [argv[index + 1] for index, arg in enumerate(argv) if arg == "--phase"]
        enforcement = [argv[index + 1] for index, arg in enumerate(argv) if arg == "--enforcement"]
        for principle in catalog["principles"]:
            if applies_to and not (set(principle["applies_to"]) & set(applies_to)):
                continue
            if phases and not (set(principle["phase"]) & set(phases)):
                continue
            if enforcement and principle["enforcement"] not in enforcement:
                continue
            expected_mapped.add(principle["id"])
        assert set(consumer["core_refs"]) <= expected_mapped

    assert mapped == expected_mapped - already


def test_canonical_catalog_and_selector_are_generated_byte_mirrors() -> None:
    assert (ASSET_DIR / "principles.json").read_bytes() == (
        SOURCE_ROOT / "references" / "deck-principles" / "principles.json"
    ).read_bytes()
    assert SELECTOR.read_bytes() == (
        SOURCE_ROOT / "scripts" / "extract-deck-principles.py"
    ).read_bytes()
    assert (ASSET_DIR / "tool-adapters.json").read_bytes() == (
        SOURCE_ROOT / "references" / "deck-principles" / "tool-adapters.json"
    ).read_bytes()


def test_selector_prefers_colocated_guide_assets_over_sibling_env(monkeypatch) -> None:
    module = _load_selector()
    monkeypatch.delenv("DECK_PRINCIPLES_DIR", raising=False)
    monkeypatch.setenv("SRG_ROOT", str(SOURCE_ROOT))
    monkeypatch.delenv("HB_ROOT", raising=False)
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    assert module.catalog_dir().resolve() == ASSET_DIR.resolve()


def test_selector_runs_from_repo_without_root_environment() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SELECTOR),
            "--consumer",
            "handout-content-architect",
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        env=_clean_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["selection"]["consumer"] == "handout-content-architect"
    assert payload["selection"]["selected_ids"]
    assert "references/deck-principles/principles.json" not in result.stdout


def test_consumer_prompts_use_one_marker_and_shared_contract() -> None:
    cases = {
        PLUGIN_ROOT
        / "skills/assign-handout-readability-evaluator/prompts/R1-review-readability.md": (
            "handout-readability-reviewer",
            "agent",
        ),
        PLUGIN_ROOT / "skills/run-handout-build/prompts/R2a-design-config.md": (
            "handout-content-architect",
            "orchestrator",
        ),
    }
    for path, (consumer_id, run_by) in cases.items():
        body = path.read_text(encoding="utf-8")
        marker = f"<!-- deck-principles-consumer: {consumer_id}; run-by: {run_by} -->"
        assert body.count(marker) == 1, path
        assert "assets/deck-principles/README.md" in body, path
        assert "principles.json` を直接読まない" not in body, path


def test_guide_docs_do_not_redeclare_the_shared_policy_block() -> None:
    paths = (
        PLUGIN_ROOT / "skills/ref-handout-design-system/SKILL.md",
        PLUGIN_ROOT / "skills/run-handout-build/SKILL.md",
    )
    for path in paths:
        body = path.read_text(encoding="utf-8")
        assert "assets/deck-principles/README.md" in body, path
        assert "返ってきた規範文・閾値" not in body, path


def test_plugin_composition_declares_selector_and_local_assets() -> None:
    composition = (PLUGIN_ROOT / "plugin-composition.yaml").read_text(encoding="utf-8")
    lines = composition.splitlines()
    assert "kind: script, ref: scripts/extract-deck-principles.py" in composition
    for owner in ("skills/run-handout-build", "skills/assign-handout-readability-evaluator"):
        assert any(
            f"from: {owner}," in line and "to: scripts/extract-deck-principles.py" in line
            for line in lines
        )
    for asset in ("principles.json", "binding.json", "tool-adapters.json"):
        assert any(
            "from: scripts/extract-deck-principles.py," in line
            and f"to: assets/deck-principles/{asset}" in line
            for line in lines
        )

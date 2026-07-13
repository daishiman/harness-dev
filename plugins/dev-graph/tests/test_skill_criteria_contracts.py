from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parents[1]
INVENTORY = REPO / "plugin-plans" / "dev-graph" / "component-inventory.json"
EVALS = PLUGIN / "EVALS.json"


def _contracts() -> list[tuple[str, str, Path, list[str]]]:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    components = {item["id"]: item for item in inventory["components"]}
    evals = json.loads(EVALS.read_text(encoding="utf-8"))["criteria_tests"]["components"]
    rows: list[tuple[str, str, Path, list[str]]] = []
    for component_id, test_contract in evals.items():
        inventory_ids = {
            item["id"] for item in components[component_id]["feedback_contract"]["criteria"]
        }
        declared = set(test_contract["criteria"])
        assert declared == inventory_ids, (
            f"{component_id}: criteria-test mapping drift; "
            f"missing={sorted(inventory_ids - declared)}, extra={sorted(declared - inventory_ids)}"
        )
        skill = PLUGIN / test_contract["skill"]
        for criterion_id, markers in test_contract["criteria"].items():
            rows.append((component_id, criterion_id, skill, markers))
    return rows


def _criteria_clauses(text: str) -> dict[str, str]:
    """Parse only the dedicated acceptance section; markers elsewhere do not count."""

    match = re.search(
        r"^## Criteria acceptance\s*$\n(?P<body>.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, "missing `## Criteria acceptance` section"
    clauses: dict[str, str] = {}
    for line in match.group("body").splitlines():
        item = re.match(r"^- `criteria:(?P<id>[A-Z]+[0-9]+)`:\s*(?P<body>.+)$", line)
        if not item:
            continue
        criterion_id = item.group("id")
        assert criterion_id not in clauses, f"duplicate criteria clause: {criterion_id}"
        clauses[criterion_id] = item.group("body")
    return clauses


@pytest.mark.parametrize(
    ("component_id", "criterion_id", "skill_path", "markers"),
    _contracts(),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_skill_criterion_has_dedicated_acceptance_clause(
    component_id: str,
    criterion_id: str,
    skill_path: Path,
    markers: list[str],
) -> None:
    """Every inventory criterion has one named clause; unrelated text cannot satisfy it."""

    text = skill_path.read_text(encoding="utf-8")
    clauses = _criteria_clauses(text)
    assert f"source: plugin-plans/dev-graph/component-inventory.json#{component_id}" in text
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    expected = {
        item["id"]
        for item in next(
            item for item in inventory["components"] if item["id"] == component_id
        )["feedback_contract"]["criteria"]
    }
    assert set(clauses) == expected
    folded = clauses[criterion_id].casefold()
    missing = [
        marker for marker in markers if marker.casefold() not in folded
        and marker.casefold() != f"criteria:{criterion_id}".casefold()
    ]
    assert not missing, f"{component_id}/{criterion_id}: missing acceptance markers {missing}"


def test_criteria_harness_covers_every_loop_skill() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    expected = {
        item["id"]
        for item in inventory["components"]
        if (item.get("harness_coverage") or {}).get("kind_pass")
        == "loop=criteria-test+content-review-verdict"
    }
    configured = set(
        json.loads(EVALS.read_text(encoding="utf-8"))["criteria_tests"]["components"]
    )
    assert configured == expected

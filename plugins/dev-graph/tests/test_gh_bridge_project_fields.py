from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
BRIDGE = SCRIPTS / "gh-bridge.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_bridge(name: str):
    spec = importlib.util.spec_from_file_location(name, BRIDGE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def adapter_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "github-adapter.json"
    fixture.write_text(json.dumps({
        "schema_version": "1.0.0",
        "fixture_id": "two-pass",
        "network": "disabled",
        "repo": "fixture/repo",
        "issues": {
            "7": {
                "id": "ISSUE-7",
                "number": 7,
                "url": "https://github.invalid/fixture/repo/issues/7",
            },
        },
        "projects": {
            "delivery": {
                "id": "PROJECT-1",
                "fields": [
                    {
                        "id": "FIELD-STATUS",
                        "name": "Status",
                        "options": [
                            {"id": "OPTION-ACTIVE", "name": "In Progress"},
                            {"id": "OPTION-DONE", "name": "Done"},
                        ],
                    },
                    {"id": "FIELD-DATE", "name": "Target date"},
                ],
                "items": [{
                    "id": "ITEM-7",
                    "content_id": "ISSUE-7",
                    "content_number": 7,
                    "fields": {"Target date": "2026-08-31", "Status": "In Progress"},
                    "field_updated_at": {
                        "Target date": "2026-08-24T01:00:00Z",
                        "Status": "2026-08-24T02:00:00Z",
                    },
                }],
            },
        },
    }, ensure_ascii=False), encoding="utf-8")
    return fixture


def run_fixture_read(fixture: Path) -> dict:
    env = os.environ.copy()
    env["DEV_GRAPH_GH"] = str(fixture.parent / "network-must-not-run")
    completed = subprocess.run(
        [
            sys.executable,
            str(BRIDGE),
            "--op", "project-item-fields",
            "--repo", "fixture/repo",
            "--project-id", "PROJECT-1",
            "--item-id", "ITEM-7",
            "--adapter-fixture", str(fixture),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_fixture_read_is_offline_and_preserves_two_pass_base(tmp_path: Path) -> None:
    fixture = adapter_fixture(tmp_path)

    pass_1 = run_fixture_read(fixture)
    pass_2 = run_fixture_read(fixture)

    assert pass_1 == pass_2
    result = pass_2["result"]
    assert result["source"] == {
        "kind": "adapter_fixture",
        "fixture_id": "two-pass",
        "network": "disabled",
    }
    assert result["project_id"] == "PROJECT-1"
    assert result["item_id"] == "ITEM-7"
    assert result["content"]["id"] == "ISSUE-7"
    assert result["snapshot_sha256"] == pass_1["result"]["snapshot_sha256"]
    assert [(row["field_name"], row["value"], row["updated_at"]) for row in result["fields"]] == [
        ("Status", "In Progress", "2026-08-24T02:00:00Z"),
        ("Target date", "2026-08-31", "2026-08-24T01:00:00Z"),
    ]
    assert pass_2["retry_classification"] == "safe_read"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda value: value.update({"network": "enabled"}), "network=disabled"),
        (lambda value: value.update({"repo": "other/repo"}), "does not match"),
        (lambda value: value["projects"].update({"duplicate": value["projects"]["delivery"]}), "exactly once"),
    ],
)
def test_fixture_boundary_fails_closed(tmp_path: Path, change, message: str) -> None:
    fixture = adapter_fixture(tmp_path)
    value = json.loads(fixture.read_text(encoding="utf-8"))
    change(value)
    fixture.write_text(json.dumps(value), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(BRIDGE),
            "--op", "project-item-fields",
            "--repo", "fixture/repo",
            "--project-id", "PROJECT-1",
            "--item-id", "ITEM-7",
            "--adapter-fixture", str(fixture),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert message in completed.stderr


def test_real_graphql_read_normalizes_paginated_values(monkeypatch) -> None:
    bridge = load_bridge("gh_bridge_project_fields")
    pages = iter([
        {"data": {"node": {
            "id": "ITEM-7",
            "project": {"id": "PROJECT-1"},
            "content": {
                "id": "ISSUE-7",
                "number": 7,
                "url": "https://github.test/o/r/issues/7",
                "repository": {"nameWithOwner": "o/r"},
            },
            "fieldValues": {
                "nodes": [{
                    "__typename": "ProjectV2ItemFieldDateValue",
                    "updatedAt": "2026-08-24T01:00:00Z",
                    "date": "2026-08-31",
                    "field": {"id": "FIELD-DATE", "name": "Target date"},
                }],
                "pageInfo": {"hasNextPage": True, "endCursor": "page-2"},
            },
        }}},
        {"data": {"node": {
            "id": "ITEM-7",
            "project": {"id": "PROJECT-1"},
            "content": {
                "id": "ISSUE-7",
                "number": 7,
                "url": "https://github.test/o/r/issues/7",
                "repository": {"nameWithOwner": "o/r"},
            },
            "fieldValues": {
                "nodes": [{
                    "__typename": "ProjectV2ItemFieldSingleSelectValue",
                    "updatedAt": "2026-08-24T02:00:00Z",
                    "name": "In Progress",
                    "optionId": "OPTION-ACTIVE",
                    "field": {"id": "FIELD-STATUS", "name": "Status"},
                }],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }}},
    ])
    seen: list[dict[str, str]] = []
    monkeypatch.setattr(bridge, "graphql", lambda query, variables: seen.append(variables) or next(pages))

    result = bridge.project_item_fields(repo="o/r", project_id="PROJECT-1", item_id="ITEM-7")

    assert seen == [
        {"item": "ITEM-7", "cursor": ""},
        {"item": "ITEM-7", "cursor": "page-2"},
    ]
    assert result["pages"] == 2
    assert result["source"] == {"kind": "github", "repository": "o/r"}
    assert [row["field_name"] for row in result["fields"]] == ["Status", "Target date"]
    assert result["fields"][0]["option_id"] == "OPTION-ACTIVE"
    assert len(result["snapshot_sha256"]) == 64


def test_real_graphql_read_rejects_cross_repository_item(monkeypatch) -> None:
    bridge = load_bridge("gh_bridge_project_fields_cross_repo")
    monkeypatch.setattr(bridge, "graphql", lambda query, variables: {"data": {"node": {
        "id": "ITEM-7",
        "project": {"id": "PROJECT-1"},
        "content": {
            "id": "ISSUE-7",
            "number": 7,
            "url": "https://github.test/other/repo/issues/7",
            "repository": {"nameWithOwner": "other/repo"},
        },
        "fieldValues": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}},
    }}})

    with pytest.raises(bridge.ContractError, match="does not belong to --repo"):
        bridge.project_item_fields(repo="o/r", project_id="PROJECT-1", item_id="ITEM-7")


def mutation_args(**overrides) -> Namespace:
    values = {
        "project_id": "PROJECT-1",
        "item_id": "ITEM-7",
        "field_id": "FIELD-1",
        "option_id": None,
        "iteration_id": None,
        "value_type": None,
        "value": None,
        "clear": False,
    }
    values.update(overrides)
    return Namespace(**values)


@pytest.mark.parametrize(
    ("arguments", "input_key", "expected_value"),
    [
        ({"value_type": "single_select", "option_id": "OPTION-1"}, "singleSelectOptionId", "OPTION-1"),
        ({"value_type": "text", "value": "ready"}, "text", "ready"),
        ({"value_type": "number", "value": "2.5"}, "number", 2.5),
        ({"value_type": "date", "value": "2026-08-31"}, "date", "2026-08-31"),
        ({"value_type": "iteration", "iteration_id": "ITERATION-1"}, "iterationId", "ITERATION-1"),
    ],
)
def test_project_field_mutation_supports_every_repo_config_value_type(
    arguments: dict,
    input_key: str,
    expected_value,
) -> None:
    bridge = load_bridge(f"gh_bridge_mutation_{input_key}")

    query, variables = bridge._project_field_mutation(mutation_args(**arguments))

    assert f"{input_key}:$value" in query
    assert variables == {
        "project": "PROJECT-1",
        "item": "ITEM-7",
        "field": "FIELD-1",
        "value": expected_value,
    }


def test_project_field_mutation_supports_clear_and_rejects_ambiguous_values() -> None:
    bridge = load_bridge("gh_bridge_mutation_clear")

    query, variables = bridge._project_field_mutation(mutation_args(clear=True))

    assert "clearProjectV2ItemFieldValue" in query
    assert variables == {"project": "PROJECT-1", "item": "ITEM-7", "field": "FIELD-1"}
    with pytest.raises(bridge.ContractError, match="only --value"):
        bridge._project_field_mutation(
            mutation_args(value_type="date", value="2026-08-31", option_id="OPTION-1")
        )
    with pytest.raises(bridge.ContractError, match="ISO date"):
        bridge._project_field_mutation(mutation_args(value_type="date", value="31-08-2026"))
    with pytest.raises(bridge.ContractError, match="finite number"):
        bridge._project_field_mutation(mutation_args(value_type="number", value="NaN"))


def test_graphql_preserves_numeric_looking_text_but_types_numeric_variables(monkeypatch) -> None:
    bridge = load_bridge("gh_bridge_graphql_variable_types")
    seen: list[list[str]] = []
    monkeypatch.setattr(bridge, "gh_json", lambda argv: seen.append(argv) or {})

    bridge.graphql("query Q", {"text": "123", "truthy_text": "true", "number": 2.5})

    assert seen == [[
        "api", "graphql", "-f", "query=query Q",
        "-F", "number=2.5",
        "-f", "text=123",
        "-f", "truthy_text=true",
    ]]


def test_dry_run_validates_before_preview_and_fixture_cannot_reach_mutation(tmp_path: Path) -> None:
    invalid_preview = subprocess.run(
        [sys.executable, str(BRIDGE), "--op", "issue-create", "--repo", "fixture/repo", "--dry-run"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert invalid_preview.returncode == 1
    assert "--title required" in invalid_preview.stderr

    fixture = adapter_fixture(tmp_path)
    mutation = subprocess.run(
        [
            sys.executable,
            str(BRIDGE),
            "--op", "project-item-edit",
            "--project-id", "PROJECT-1",
            "--item-id", "ITEM-7",
            "--field-id", "FIELD-STATUS",
            "--option-id", "OPTION-DONE",
            "--adapter-fixture", str(fixture),
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert mutation.returncode == 1
    assert "supported only by read-only project-item-fields" in mutation.stderr

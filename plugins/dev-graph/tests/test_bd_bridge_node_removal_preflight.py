"""C28 graph node removal preflight.

Physical graph deletion must never turn a non-closed Beads reference into an
orphan.  The bridge is deliberately read-only: close/detach is a human decision,
and the gate only verifies that the selected disposition already matches reality.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


def load():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "bd_bridge_node_removal_preflight",
        SCRIPTS / "bd-bridge.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def graph(path: Path, *node_ids: str) -> str:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "repository_id": "fixture",
                "graph_revision": 1,
                "nodes": [
                    {"graph_node_id": node_id}
                    for node_id in node_ids
                ],
            }
        ),
        encoding="utf-8",
    )
    return path.name


def manifest(node_id: str, disposition: str, issue_ids: list[str]):
    return {
        "schema_version": "1.0.0",
        "dispositions": [
            {
                "graph_node_id": node_id,
                "disposition": disposition,
                "bd_issue_ids": issue_ids,
                "reason": "fixture decision",
            }
        ],
    }


def run(module, tmp_path: Path, monkeypatch, rows, disposition=None):
    before = graph(tmp_path / "before.json", "node-live", "node-kept")
    after = graph(tmp_path / "after.json", "node-kept")
    monkeypatch.setattr(module, "bd", lambda *_args, **_kwargs: rows)
    return module._removal_preflight(
        tmp_path,
        before_graph=before,
        before_ref=None,
        after_graph=after,
        after_ref=None,
        disposition_manifest=disposition,
    )


def test_non_closed_reference_blocks_even_when_close_was_selected(
    tmp_path,
    monkeypatch,
):
    module = load()
    receipt = run(
        module,
        tmp_path,
        monkeypatch,
        [
            {
                "id": "B-open",
                "status": "in_progress",
                "external_ref": "dev-graph:node-live",
            }
        ],
        manifest("node-live", "close_issue_first", ["B-open"]),
    )

    assert receipt["allowed"] is False
    assert receipt["write_count"] == 0
    assert receipt["orphan_audit"] == {
        "before_non_closed": 0,
        "after_non_closed": 1,
        "new_non_closed_bd_issue_ids": ["B-open"],
    }
    assert "non_closed_reference" in receipt["decisions"][0]["errors"]
    assert any(
        "non_closed_orphan_increase" in blocker["errors"]
        for blocker in receipt["blockers"]
    )


def test_close_issue_first_passes_only_after_all_references_are_closed(
    tmp_path,
    monkeypatch,
):
    module = load()
    receipt = run(
        module,
        tmp_path,
        monkeypatch,
        [
            {
                "id": "B-closed",
                "status": "closed",
                "external_ref": "dev-graph:node-live",
            }
        ],
        manifest("node-live", "close_issue_first", ["B-closed"]),
    )

    assert receipt["allowed"] is True
    assert receipt["decisions"][0]["verified"] is True
    assert receipt["orphan_audit"]["before_non_closed"] == 0
    assert receipt["orphan_audit"]["after_non_closed"] == 0


def test_detach_external_ref_first_passes_only_after_reference_is_absent(
    tmp_path,
    monkeypatch,
):
    module = load()
    receipt = run(
        module,
        tmp_path,
        monkeypatch,
        [],
        manifest("node-live", "detach_external_ref_first", []),
    )
    assert receipt["allowed"] is True
    assert receipt["decisions"][0]["references"] == []

    blocked = run(
        module,
        tmp_path,
        monkeypatch,
        [
            {
                "id": "B-still-linked",
                "status": "closed",
                "external_ref": "dev-graph:node-live",
            }
        ],
        manifest(
            "node-live",
            "detach_external_ref_first",
            ["B-still-linked"],
        ),
    )
    assert blocked["allowed"] is False
    assert "external_ref_not_detached" in blocked["decisions"][0]["errors"]


def test_every_physical_removal_requires_an_explicit_disposition(
    tmp_path,
    monkeypatch,
):
    module = load()
    receipt = run(module, tmp_path, monkeypatch, [], None)
    assert receipt["allowed"] is False
    assert receipt["decisions"][0]["errors"] == ["disposition_missing"]


def test_cancel_deletion_requires_the_node_to_be_restored(
    tmp_path,
    monkeypatch,
):
    module = load()
    receipt = run(
        module,
        tmp_path,
        monkeypatch,
        [],
        manifest("node-live", "cancel_deletion", []),
    )
    assert receipt["allowed"] is False
    assert receipt["decisions"][0]["errors"] == ["deletion_not_cancelled"]


def test_cancel_deletion_is_recorded_after_the_node_is_restored(
    tmp_path,
    monkeypatch,
):
    module = load()
    before = graph(tmp_path / "before.json", "node-live", "node-kept")
    after = graph(tmp_path / "after.json", "node-live", "node-kept")
    rows = [
        {
            "id": "B-open",
            "status": "open",
            "external_ref": "dev-graph:node-live",
        }
    ]
    monkeypatch.setattr(module, "bd", lambda *_args, **_kwargs: rows)

    receipt = module._removal_preflight(
        tmp_path,
        before_graph=before,
        before_ref=None,
        after_graph=after,
        after_ref=None,
        disposition_manifest=manifest(
            "node-live",
            "cancel_deletion",
            ["B-open"],
        ),
    )

    assert receipt["allowed"] is True
    assert receipt["removed_nodes"] == []
    assert receipt["decisions"] == [
        {
            "graph_node_id": "node-live",
            "removed": False,
            "disposition": "cancel_deletion",
            "reason": "fixture decision",
            "references": [{"bd_issue_id": "B-open", "status": "open"}],
            "non_closed_references": [
                {"bd_issue_id": "B-open", "status": "open"}
            ],
            "verified": True,
            "errors": [],
        }
    ]
    assert receipt["orphan_audit"]["new_non_closed_bd_issue_ids"] == []


def test_no_removal_is_idempotently_allowed_without_a_manifest(
    tmp_path,
    monkeypatch,
):
    module = load()
    before = graph(tmp_path / "before.json", "node-kept")
    after = graph(tmp_path / "after.json", "node-kept", "node-added")
    monkeypatch.setattr(module, "bd", lambda *_args, **_kwargs: [])

    receipt = module._removal_preflight(
        tmp_path,
        before_graph=before,
        before_ref=None,
        after_graph=after,
        after_ref=None,
        disposition_manifest=None,
    )

    assert receipt["allowed"] is True
    assert receipt["removed_nodes"] == []
    assert receipt["decisions"] == []
    assert receipt["write_count"] == 0


def test_disposition_issue_ids_must_match_the_current_beads_references(
    tmp_path,
    monkeypatch,
):
    module = load()
    receipt = run(
        module,
        tmp_path,
        monkeypatch,
        [
            {
                "id": "B-actual",
                "status": "closed",
                "external_ref": "dev-graph:node-live",
            }
        ],
        manifest("node-live", "close_issue_first", ["B-stale"]),
    )
    assert receipt["allowed"] is False
    assert receipt["decisions"][0]["errors"] == ["bd_issue_ids_mismatch"]


def test_removal_disposition_vocabulary_is_an_exact_set():
    load()
    # 受理語彙は lib/bd_bridge_contracts.py が正本。bd-bridge は load のたびにそれを読み直す。
    assert sys.modules["bd_bridge_contracts"].REMOVAL_DISPOSITIONS == (
        "cancel_deletion",
        "close_issue_first",
        "detach_external_ref_first",
    )

"""decompose criteria:OUT1: a draft that has not passed evaluation is never published to the tracker.

build-github-projection.plan() is the C14 selector. A github-bound node whose confirmation, evaluation
or implementation readiness is not yet confirmed/pass/complete must produce zero publication targets and
be reported in ``skipped`` with its reason; the same node becomes a target once all three gates hold.
Only plan() is called, so no gh process and no network are involved.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

REASON = "not confirmed/pass/readiness complete"


def load(script: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def github_task(**gates):
    node = {
        "graph_node_id": "task-api-users",
        "artifact_kind": "task",
        "status": "draft",
        "tracker_binding": "github",
        "github_publication": {"mode": "issue"},
        "confirmation_status": "confirmed",
        "evaluation_status": "pass",
        "implementation_readiness": {"status": "complete"},
    }
    node.update(gates)
    return node


# The first four are drafts graph-node.schema.json accepts. The last four open exactly one gate each, even
# where the schema would reject the combination, so every element of the gate tuple is shown to be checked
# by plan() itself rather than by an upstream schema pass.
@pytest.mark.parametrize("gates", [
    {"confirmation_status": "draft", "evaluation_status": "pending",
     "implementation_readiness": {"status": "incomplete"}},
    {"evaluation_status": "pending"},
    {"evaluation_status": "fail"},
    {"evaluation_status": "stale"},
    {"confirmation_status": "draft"},
    {"confirmation_status": "superseded"},
    {"implementation_readiness": {"status": "incomplete"}},
    {"implementation_readiness": None},
], ids=["all-gates-open", "evaluation-pending", "evaluation-fail", "evaluation-stale", "confirmation-draft",
        "confirmation-superseded", "readiness-incomplete", "readiness-missing"])
def test_draft_before_evaluation_has_zero_targets_and_is_skipped_with_reason(gates):
    projection = load("build-github-projection.py", "build_github_projection_readiness_gate")
    draft = github_task(**gates)

    targets, skipped = projection.plan([draft], {"projects": []})

    assert targets == []
    assert skipped == [{"graph_node_id": "task-api-users", "reason": REASON}]


def test_same_node_becomes_a_target_once_confirmed_pass_complete():
    projection = load("build-github-projection.py", "build_github_projection_readiness_gate")
    draft = github_task(confirmation_status="draft", evaluation_status="pending",
                        implementation_readiness={"status": "incomplete"})
    assert projection.plan([draft], {"projects": []}) == (
        [], [{"graph_node_id": "task-api-users", "reason": REASON}])

    promoted = dict(draft, status="active", confirmation_status="confirmed", evaluation_status="pass",
                    implementation_readiness={"status": "complete"})
    targets, skipped = projection.plan([promoted], {"projects": []})

    assert skipped == []
    assert targets == [{"node": promoted, "aliases": []}]

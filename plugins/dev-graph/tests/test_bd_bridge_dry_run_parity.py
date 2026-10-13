"""bd-bridge ``--dry-run`` rejects every input the apply rejects, and differs from the apply only in the write.

A dry-run used to return its preview before the argument checks and the ``bd show`` reads of the apply, so
``dep-add --dry-run`` without an issue, or with a blocker bd does not know, answered rc 0 (decompose live trial
20261012T2336-pr85). The fake bd replaces the bridge's process runner, so neither the network nor a real bd is used.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
READS = {"version", "where", "show", "search", "ready"}


class FakeBd:
    """Knows the issues B1 (task, open) and B0; ``bd show`` of any other id returns no row, as bd does."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.issues = {"B1": {"id": "B1", "status": "open", "issue_type": "task", "dependencies": []},
                       "B0": {"id": "B0", "status": "open", "issue_type": "task", "dependencies": []}}

    def __call__(self, argv, *, cwd=None, check=True):
        args = [str(value) for value in argv[1:]]
        self.calls.append(args)
        if args == ["version"]:
            out = "bd version 1.4.2"
        elif args == ["where", "--json"]:
            out = {"database_path": "/fake/.beads/beads.db", "prefix": "bd", "schema_version": "1"}
        elif args[0] == "show":
            out = [self.issues[args[1]]] if args[1] in self.issues else []
        elif args[:2] == ["gate", "list"]:
            out = []
        else:
            out = {"ok": True}
        return SimpleNamespace(returncode=0, stdout=out if isinstance(out, str) else json.dumps(out), stderr="")

    def writes(self) -> list[list[str]]:
        return [args for args in self.calls if args[0] not in READS and args[:2] != ["gate", "list"]]


@pytest.fixture
def bridge(monkeypatch):
    spec = importlib.util.spec_from_file_location("bd_bridge_dry_run_parity", SCRIPTS / "bd-bridge.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fake = FakeBd()
    monkeypatch.setattr(module, "run", fake)
    return module, fake


def call(module, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["bd-bridge.py", *map(str, argv)])
    code = module.main()
    output = capsys.readouterr().out
    return code, json.loads(output) if output else None


@pytest.mark.parametrize("argv,message", [
    (("--op", "dep-add", "--graph-node-id", "feature-render-diff", "--depends-on", "LT-FEATURE-001"), "dep-add requires issue and depends-on"),
    (("--op", "dep-add", "--bd-issue-id", "B1"), "dep-add requires issue and depends-on"),
    (("--op", "update", "--status", "in_progress"), "update requires --bd-issue-id"),
    (("--op", "close",), "close requires --bd-issue-id"),
    (("--op", "claim",), "claim requires --bd-issue-id"),
    (("--op", "gate-add", "--bd-issue-id", "B1"), "gate operation requires issue and --pr"),
])
def test_missing_arguments_are_rejected_in_both_modes_before_any_bd_process(bridge, monkeypatch, capsys, tmp_path, argv, message):
    module, fake = bridge
    for extra in ((), ("--dry-run",)):
        with pytest.raises(module.ContractError, match=message):
            call(module, monkeypatch, capsys, *argv, "--repo-root", tmp_path, *extra)
    assert fake.calls == []


@pytest.mark.parametrize("argv,missing", [
    (("--op", "dep-add", "--bd-issue-id", "B1", "--depends-on", "B404"), "B404"),
    (("--op", "dep-add", "--bd-issue-id", "B404", "--depends-on", "B0"), "B404"),
    (("--op", "update", "--bd-issue-id", "B404", "--status", "in_progress"), "B404"),
    (("--op", "close", "--bd-issue-id", "B404"), "B404"),
    (("--op", "claim", "--bd-issue-id", "B404"), "B404"),
])
def test_an_issue_bd_does_not_know_is_rejected_in_both_modes(bridge, monkeypatch, capsys, tmp_path, argv, missing):
    module, fake = bridge
    for extra in ((), ("--dry-run",)):
        with pytest.raises(module.ContractError, match=f"exactly one issue: {missing}"):
            call(module, monkeypatch, capsys, *argv, "--repo-root", tmp_path, *extra)
    assert fake.writes() == []


@pytest.mark.parametrize("argv,planned", [
    (("--op", "dep-add", "--bd-issue-id", "B1", "--depends-on", "B0"), ["dep", "add", "B1", "B0", "--json"]),
    (("--op", "update", "--bd-issue-id", "B1", "--status", "in_progress"), ["update", "B1", "--status", "in_progress", "--json"]),
    (("--op", "claim", "--bd-issue-id", "B1"), ["update", "B1", "--claim", "--json"]),
    (("--op", "close", "--bd-issue-id", "B1"), ["close", "B1", "--reason", "dev-graph completion", "--json"]),
    (("--op", "gate-add", "--bd-issue-id", "B1", "--pr", "7"),
     ["gate", "create", "--type", "gh:pr", "--blocks", "B1", "--await-id", "7", "--reason", "PR #7 merge", "--json"]),
    (("--op", "github-push",), ["github", "sync", "--push-only", "--json"]),
])
def test_a_valid_dry_run_stops_exactly_at_the_write_the_apply_makes(bridge, monkeypatch, capsys, tmp_path, argv, planned):
    module, fake = bridge
    code, preview = call(module, monkeypatch, capsys, *argv, "--repo-root", tmp_path, "--dry-run")
    assert code == 0 and preview["dry_run_preview"]["result"] == {"planned_bd_args": planned, "write_count": 0}
    assert fake.writes() == []
    code, _ = call(module, monkeypatch, capsys, *argv, "--repo-root", tmp_path)
    assert code == 0 and fake.writes() == [planned]


def test_planned_preview_is_refused_outside_create_dry_run(bridge, monkeypatch, capsys, tmp_path):
    module, fake = bridge
    preview = tmp_path / "preview.json"
    preview.write_text("{}", encoding="utf-8")
    for argv in (("--op", "create", "--graph-node-id", "G1", "--title", "T"),
                 ("--op", "dep-add", "--bd-issue-id", "B1", "--depends-on", "B0", "--dry-run")):
        with pytest.raises(module.ContractError, match="only for create --dry-run"):
            call(module, monkeypatch, capsys, *argv, "--repo-root", tmp_path, "--planned-preview", preview)
    assert fake.calls == []

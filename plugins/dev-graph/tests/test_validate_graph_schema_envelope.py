from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
LIB = PLUGIN / "lib"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


def load():
    name = "validate_graph_schema_envelope_focused"
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / "validate-graph-schema.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def codes(findings: list[dict[str, str]]) -> set[str]:
    return {item["code"] for item in findings}


def test_envelope_findings_flag_noncanonical_store_shapes():
    mod = load()
    canonical = {
        "schema_version": "1.0.0",
        "repository_id": "repo",
        "graph_revision": 3,
        "nodes": [],
    }
    assert mod.envelope_findings(canonical) == []

    extra = mod.envelope_findings({**canonical, "backdoor": True})
    assert codes(extra) == {"envelope_violation"}
    assert any("backdoor" in item["detail"] for item in extra)
    assert codes(mod.envelope_findings({"nodes": []})) == {"envelope_violation"}

    for broken in (
        {**canonical, "graph_revision": -1},
        {**canonical, "graph_revision": True},
        {**canonical, "schema_version": "2.0.0"},
        {**canonical, "repository_id": ""},
        {**canonical, "nodes": [1, 2]},
        {**canonical, "nodes": "nodes"},
        ["not", "an", "object"],
    ):
        assert mod.envelope_findings(broken), f"逸脱が検出されていない: {broken}"

    for item in extra:
        assert set(item) == {"node", "code", "detail"}
        assert item["node"] == "$graph"


def test_canonical_store_path_triggers_envelope_check_but_preview_does_not(tmp_path):
    """既存 preview は保ち、canonical store と opt-in だけ envelope を要求する。"""
    root = tmp_path / "repo"
    state = root / ".dev-graph" / "state"
    state.mkdir(parents=True)
    partial = json.dumps({"nodes": []})

    def run(*args, stdin=partial):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "validate-graph-schema.py"), *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )

    preview = run("--graph", "-", "--repo-root", str(root))
    assert json.loads(preview.stdout)["valid"] is True

    opted_in = run("--graph", "-", "--repo-root", str(root), "--require-canonical-envelope")
    payload = json.loads(opted_in.stdout)
    assert payload["valid"] is False
    assert codes(payload["violations"]) == {"envelope_violation"}

    store = state / "graph.json"
    store.write_text(partial, encoding="utf-8")
    from_file = run("--graph", str(store), "--repo-root", str(root), stdin="")
    payload = json.loads(from_file.stdout)
    assert payload["valid"] is False
    assert "envelope_violation" in codes(payload["violations"])

    store.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "repository_id": "repo",
                "graph_revision": 0,
                "nodes": [],
            }
        ),
        encoding="utf-8",
    )
    ok = run("--graph", str(store), "--repo-root", str(root), stdin="")
    assert json.loads(ok.stdout)["valid"] is True, ok.stdout


def test_envelope_definition_is_shared_not_copied():
    """C11・PostToolUse 監査が同じ envelope 定義を import し、C02 writer は定義を複製しない。"""
    from graph_envelope import CANONICAL_GRAPH_KEYS, REQUIRED_GRAPH_KEYS

    assert CANONICAL_GRAPH_KEYS == frozenset(
        {"schema_version", "repository_id", "graph_revision", "nodes"}
    )
    # repository_id は任意 key: build-init-scaffold.py の初期 graph は持たない。
    assert REQUIRED_GRAPH_KEYS == frozenset({"schema_version", "graph_revision", "nodes"})
    for consumer in (
        SCRIPTS / "validate-graph-schema.py",
        PLUGIN / "hooks" / "audit-graph-authority-drift.py",
    ):
        body = consumer.read_text(encoding="utf-8")
        assert "graph_envelope import" in body, f"{consumer.name} が共有定義を参照していない"
    for consumer in (
        SCRIPTS / "build-graph-node.py",
        SCRIPTS / "build-init-scaffold.py",
        SCRIPTS / "register-package.py",
        SCRIPTS / "validate-graph-schema.py",
        PLUGIN / "hooks" / "audit-graph-authority-drift.py",
    ):
        body = consumer.read_text(encoding="utf-8")
        assert "CANONICAL_GRAPH_KEYS = " not in body, (
            f"{consumer.name} が envelope 定義を複製している"
        )


def test_initial_graph_of_the_scaffold_writer_passes_the_envelope():
    """C02 writer (build-init-scaffold.py) が作る初期 graph は repository_id を持たないが canonical。"""
    mod = load()
    spec = importlib.util.spec_from_file_location(
        "build_init_scaffold_envelope_focused", SCRIPTS / "build-init-scaffold.py"
    )
    assert spec and spec.loader
    scaffold = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scaffold)
    assert mod.envelope_findings(scaffold.EMPTY_GRAPH) == []

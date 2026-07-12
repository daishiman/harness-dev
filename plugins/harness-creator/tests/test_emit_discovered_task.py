"""emit-discovered-task.py (TG-C04) の機能テスト — E4 境界の consumer 側 emit 口。

conftest 非依存で module-level に importlib ロードする (自己完結)。
網羅: additive/structural emit・discovering_task_id 実在検証 (不在 exit1)・
schema (discovered-task.schema.json) 必須キー充足 (required を assert)・status を書かない
(pending)・default inbox パスが resolve_build_dir 由来・E3 (improvement-*) 非参照
(ソース grep で参照ゼロ)・proposed_node 必須キー充足・provenance.route_id・entity_ref null。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

# producer 所有 schema 正本 (必須キーの SSOT)。
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "plugin-dev-planner/skills/run-plugin-dev-plan/schemas/discovered-task.schema.json"
)
SOURCE_PATH = SCRIPTS / "emit-discovered-task.py"


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


emit = _load("emit-discovered-task")


# ─────────────────────────── fixtures / helpers ───────────────────────────
def _graph(*ids) -> dict:
    ids = ids or ("T1", "T2", "T3")
    return {"schema_version": "1.0", "nodes": [{"id": i} for i in ids], "edges": []}


def _write_graph(tmp_path, *ids, name="task-graph.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(_graph(*ids)), encoding="utf-8")
    return p


def _base_argv(graph_path, *, discovering="T1", change_level=None, output=None,
               entity_ref="C04", node_state=None, target_slug=None, cycle_id=None):
    argv = [
        "--discovering-task-id", discovering,
        "--reason", "T1 の build 中に未網羅の依存を発見",
        "--produces-ref", "eval-log/acme/build/route-r1.json",
        "--node-id", "T99",
        "--node-title", "新規 validator 追加",
        "--node-phase-ref", "P05",
        "--node-write-scope", "plugins/acme/scripts/validate-x.py",
        "--route-id", "r1",
        "--task-graph", str(graph_path),
    ]
    if entity_ref is not None:
        argv += ["--node-entity-ref", entity_ref]
    if node_state is not None:
        argv += ["--node-state", node_state]
    if change_level is not None:
        argv += ["--change-level", change_level]
    if output is not None:
        argv += ["--output", str(output)]
    if target_slug is not None:
        argv += ["--target-plugin-slug", target_slug]
    if cycle_id is not None:
        argv += ["--cycle-id", cycle_id]
    return argv


def _parse(argv):
    return emit._build_parser().parse_args(argv)


def _schema_required():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema, schema["required"], schema["properties"]["proposed_node"]["required"]


# ─────────────────────────── build_discovered_task: form 構築 ───────────────────────────
def test_build_form_has_all_schema_required_top_keys(tmp_path):
    g = _write_graph(tmp_path)
    _, top_required, _ = _schema_required()
    form = emit.build_discovered_task(_parse(_base_argv(g)))
    for key in top_required:
        assert key in form, f"schema required top-level key 欠落: {key}"


def test_build_form_proposed_node_has_all_schema_required_keys(tmp_path):
    g = _write_graph(tmp_path)
    _, _, node_required = _schema_required()
    form = emit.build_discovered_task(_parse(_base_argv(g)))
    for key in node_required:
        assert key in form["proposed_node"], f"proposed_node required key 欠落: {key}"


def test_build_form_does_not_write_status(tmp_path):
    # emit=pending: status を一切書かない (未設定=未処理=TG-C08 完了ゲート block 対象)。
    g = _write_graph(tmp_path)
    form = emit.build_discovered_task(_parse(_base_argv(g)))
    assert "status" not in form


def test_build_form_default_change_level_is_additive(tmp_path):
    g = _write_graph(tmp_path)
    form = emit.build_discovered_task(_parse(_base_argv(g)))
    assert form["change_level"] == "additive"


def test_build_form_structural_change_level(tmp_path):
    # 外ループ: stall の仕様不備由来発見は structural で emit される (TG-C06 が指定)。
    g = _write_graph(tmp_path)
    form = emit.build_discovered_task(_parse(_base_argv(g, change_level="structural")))
    assert form["change_level"] == "structural"


def test_build_form_discovered_at_artifact_is_top_level(tmp_path):
    # discovered_at_artifact は top-level・provenance へネストしない。
    g = _write_graph(tmp_path)
    form = emit.build_discovered_task(_parse(_base_argv(g)))
    assert form["discovered_at_artifact"] == "eval-log/acme/build/route-r1.json"
    assert "discovered_at_artifact" not in form["provenance"]


def test_build_form_provenance_route_id(tmp_path):
    g = _write_graph(tmp_path)
    form = emit.build_discovered_task(_parse(_base_argv(g)))
    assert form["provenance"]["route_id"] == "r1"


def test_build_form_entity_ref_null_when_omitted(tmp_path):
    # --node-entity-ref 省略時は null (schema: string|null) で必須キーを埋める。
    g = _write_graph(tmp_path)
    form = emit.build_discovered_task(_parse(_base_argv(g, entity_ref=None)))
    assert "entity_ref" in form["proposed_node"]
    assert form["proposed_node"]["entity_ref"] is None


def test_build_form_proposed_node_default_state_pending(tmp_path):
    g = _write_graph(tmp_path)
    form = emit.build_discovered_task(_parse(_base_argv(g)))
    assert form["proposed_node"]["state"] == "pending"


def test_node_state_ready_is_rejected_by_cli(tmp_path):
    g = _write_graph(tmp_path)
    with pytest.raises(SystemExit):
        _parse(_base_argv(g, node_state="ready"))


def test_schema_proposed_node_state_excludes_ready():
    schema, _, _ = _schema_required()
    enum = schema["properties"]["proposed_node"]["properties"]["state"]["enum"]
    assert enum == ["pending", "running", "done", "blocked"]


def test_build_form_no_extra_keys_beyond_schema(tmp_path):
    # additionalProperties:false 準拠: top-level と proposed_node に schema 外キーを持たない。
    schema, _, _ = _schema_required()
    allowed_top = set(schema["properties"].keys())
    allowed_node = set(schema["properties"]["proposed_node"]["properties"].keys())
    g = _write_graph(tmp_path)
    form = emit.build_discovered_task(_parse(_base_argv(g)))
    assert set(form).issubset(allowed_top)
    assert set(form["proposed_node"]).issubset(allowed_node)


# ─────────────────────────── discovering_task_id 実在検証 ───────────────────────────
def test_build_form_raises_when_discovering_absent(tmp_path):
    g = _write_graph(tmp_path, "T1", "T2")
    with pytest.raises(ValueError):
        emit.build_discovered_task(_parse(_base_argv(g, discovering="TX")))


def test_build_form_uses_plan_dir_default_task_graph(tmp_path):
    # --task-graph 省略時は <plan-dir>/task-graph.json を既定に使う。
    _write_graph(tmp_path, "T1")
    argv = [
        "--discovering-task-id", "T1", "--reason", "r", "--produces-ref", "a.json",
        "--node-id", "T9", "--node-title", "t", "--node-phase-ref", "P05",
        "--node-write-scope", "w", "--route-id", "r1", "--plan-dir", str(tmp_path),
    ]
    form = emit.build_discovered_task(_parse(argv))
    assert form["discovering_task_id"] == "T1"


def test_build_form_couples_with_populates_proposed_node(tmp_path):
    # --node-couples-with で接合が密な既存兄弟を宣言 → proposed_node.couples_with へ載る
    # (accept 側が同一 phase 兄弟の後へ直列化・外ループ追記の盲目並列防止)。
    g = _write_graph(tmp_path)
    argv = _base_argv(g) + ["--node-couples-with", "C05", "--node-couples-with", "C07"]
    form = emit.build_discovered_task(_parse(argv))
    assert form["proposed_node"]["couples_with"] == ["C05", "C07"]
    # schema: proposed_node.couples_with は許容キー (余剰キー違反にならない)。
    _, _, node_required = _schema_required()
    schema, _, _ = _schema_required()
    allowed = set(schema["properties"]["proposed_node"]["properties"].keys())
    assert set(form["proposed_node"].keys()) <= allowed


def test_build_form_couples_with_omitted_when_absent(tmp_path):
    g = _write_graph(tmp_path)
    form = emit.build_discovered_task(_parse(_base_argv(g)))
    assert "couples_with" not in form["proposed_node"]   # 未指定は付与しない (additive optional)


# ─────────────────────────── main() CLI: 出力先 / exit code ───────────────────────────
def test_main_writes_to_explicit_output_and_stdout(tmp_path, capsys):
    g = _write_graph(tmp_path)
    out = tmp_path / "out" / "form.json"
    rc = emit.main(_base_argv(g, output=out))
    assert rc == 0
    assert out.exists()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["proposed_node"]["id"] == "T99"
    assert "status" not in written
    assert out.read_text(encoding="utf-8").endswith("\n")
    stdout = json.loads(capsys.readouterr().out.strip())
    assert stdout["emitted"] == str(out)
    assert stdout["change_level"] == "additive"
    assert stdout["proposed_node_id"] == "T99"


def test_main_default_inbox_path_from_resolve_build_dir(tmp_path, monkeypatch):
    # default 出力は resolve_build_dir(...)/discovered-tasks/<uuid>.json 由来。
    monkeypatch.chdir(tmp_path)
    g = _write_graph(tmp_path)
    rc = emit.main(_base_argv(g, target_slug="acme", cycle_id="20260706-x"))
    assert rc == 0
    inbox = tmp_path / "eval-log/acme/build/20260706-x/discovered-tasks"
    assert inbox.is_dir()
    forms = list(inbox.glob("*.json"))
    assert len(forms) == 1
    # <uuid>.json 形式 (uuid.uuid4().hex = 32 hex)。
    assert len(forms[0].stem) == 32
    data = json.loads(forms[0].read_text(encoding="utf-8"))
    assert data["discovering_task_id"] == "T1"


def test_main_default_inbox_flat_when_cycle_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    g = _write_graph(tmp_path)
    rc = emit.main(_base_argv(g, target_slug="acme"))
    assert rc == 0
    assert (tmp_path / "eval-log/acme/build/discovered-tasks").is_dir()


def test_main_discovering_absent_exit1(tmp_path):
    g = _write_graph(tmp_path, "T1")
    out = tmp_path / "form.json"
    rc = emit.main(_base_argv(g, discovering="TX", output=out))
    assert rc == 1
    assert not out.exists()  # 検証失敗時は書かない (fail-closed)。


def test_main_structural_emit_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    g = _write_graph(tmp_path)
    out = tmp_path / "structural.json"
    rc = emit.main(_base_argv(g, change_level="structural", output=out))
    assert rc == 0
    assert json.loads(out.read_text(encoding="utf-8"))["change_level"] == "structural"


def test_main_missing_output_and_slug_exit2(tmp_path):
    # --output 省略かつ --target-plugin-slug 省略は usage error (exit2)。
    g = _write_graph(tmp_path)
    rc = emit.main(_base_argv(g))
    assert rc == 2


def test_main_no_task_graph_no_plan_dir_exit2(tmp_path):
    # discovering 検証用の task-graph が解決できない → usage error (exit2)。
    argv = [
        "--discovering-task-id", "T1", "--reason", "r", "--produces-ref", "a.json",
        "--node-id", "T9", "--node-title", "t", "--node-phase-ref", "P05",
        "--node-write-scope", "w", "--route-id", "r1",
        "--output", str(tmp_path / "x.json"),
    ]
    assert emit.main(argv) == 2


def test_main_bad_task_graph_json_exit2(tmp_path):
    bad = tmp_path / "task-graph.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = emit.main(_base_argv(bad, output=tmp_path / "x.json"))
    assert rc == 2


def test_main_missing_required_arg_exit2(tmp_path):
    g = _write_graph(tmp_path)
    # --reason 欠落 → argparse usage error (exit2)。
    argv = [
        "--discovering-task-id", "T1", "--produces-ref", "a.json",
        "--node-id", "T9", "--node-title", "t", "--node-phase-ref", "P05",
        "--node-write-scope", "w", "--route-id", "r1", "--task-graph", str(g),
        "--output", str(tmp_path / "x.json"),
    ]
    assert emit.main(argv) == 2


# ─────────────────────────── E4 境界: E3 (improvement-*) 非参照 ───────────────────────────
def test_source_does_not_reference_improvement_handoff():
    # E4 境界: 本 script は E3 (build 完了後改善還流) 境界の schema を一切 import/参照しない。
    src = SOURCE_PATH.read_text(encoding="utf-8")
    assert "improvement-handoff" not in src
    assert "improvement_handoff" not in src


def test_source_writes_only_the_form_output():
    # plan 本体 (component-inventory.json / phase-*.md) への書込処理を持たない (emit のみ)。
    # write は form 出力の単一 .write_text 呼出しに限定される (単一 emit・複数書込なし)。
    src = SOURCE_PATH.read_text(encoding="utf-8")
    assert src.count(".write_text(") == 1

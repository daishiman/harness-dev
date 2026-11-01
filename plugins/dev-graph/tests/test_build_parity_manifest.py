"""C28 parity manifest generator (`build-parity-manifest.py`) の回帰テスト。

C28 `bd-bridge.py --op ready --parity-manifest` は manifest を受け取るだけで、manifest を作る
正規経路が無かった。正規経路が無いと manifest は手書きか不在になり、graph 管理下の候補が
全て `parity_manifest_missing` へ落ちて C16 の ready-set が空になる。

ここで固定する不変条件は 4 つ。

1. **digest 式の同一性**: generator と C16 `schedule-graph.py` の `_canonical_digest`
   が同じ式であること。ずれると生成直後の manifest が常に stale 判定になり、
   schedule が恒久停止する (静かに壊れて誰も気付かない種類の破綻)。
2. **status 語彙の同一性**: generator の `BRIDGE_STATUS_MAP` と C28
   `bd-bridge.py` の `status_map` が同じ exact-set であること。片方だけ増えると
   その status の node が全て conflicts へ落ちる。
3. **status で間引かない**: 終了済み (`done`/`closed`) node も manifest に載せる。
   省くと、それを依存に持つ `active` node が C28 で
   `parity manifest dependency lacks a Beads linkage` へ落ち、ready-set が再び空になる。
4. **落ちた node は理由つきで残す**: 起票前 node と manifest 外依存を receipt へ出す
   (silent drop の禁止)。

C28 が manifest の由来 (`parity_provenance`) を返すことの検査は bd-bridge 側の責務であり、
ここでは扱わない。
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, argv)])
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    code = module.main()
    output = capsys.readouterr().out.strip()
    return code, json.loads(output) if output else None


def node(node_id: str, issue_id: str | None, status: str = "active", **extra):
    payload = {
        "graph_node_id": node_id,
        "artifact_kind": "task",
        "status": status,
        "tracker_binding": "beads",
        "depends_on": [],
        **extra,
    }
    payload["beads_linkage"] = {"bd_issue_id": issue_id} if issue_id else None
    return payload


def workspace(tmp_path: Path, nodes: list[dict]) -> Path:
    graph = tmp_path / ".dev-graph" / "state" / "graph.json"
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_text(json.dumps({"schema_version": "1.0.0", "graph_revision": 1, "nodes": nodes}), encoding="utf-8")
    return graph


# --- 1. digest 式の同一性 ---------------------------------------------------


def test_generator_digest_formula_matches_c16_schedule():
    """式がずれると manifest は生成直後から stale 扱いになり schedule が恒久停止する。"""
    builder = load("build-parity-manifest.py", "c28_manifest_digest")
    schedule = load("schedule-graph.py", "c16_manifest_digest")

    for sample in (
        {"nodes": []},
        {"nodes": [node("n-1", "B-1")]},
        # key 順・非 ASCII・入れ子を含めても一致し続けること (canonical JSON の性質)。
        {"z": 1, "nodes": [node("n-2", "B-2", title="日本語タイトル")], "a": {"b": [1, 2]}},
    ):
        assert builder._canonical_digest(sample) == schedule._canonical_digest(sample)


def test_generated_manifest_is_fresh_for_c16(tmp_path, monkeypatch, capsys):
    """生成直後の manifest が C16 の鮮度判定 (現 graph の canonical digest) を満たす。"""
    builder = load("build-parity-manifest.py", "c28_manifest_fresh")
    schedule = load("schedule-graph.py", "c16_manifest_fresh")
    graph = workspace(tmp_path, [node("n-1", "B-1")])

    code, receipt = call_main(builder, monkeypatch, capsys, "--repo-root", tmp_path, "--graph", graph)
    assert code == 0
    manifest = json.loads((tmp_path / receipt["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["source_graph_digest"] == schedule._canonical_digest(json.loads(graph.read_text()))


# --- 2. status 語彙の同一性 -------------------------------------------------


def bridge_status_map() -> dict[str, str]:
    """C28 `_ready_with_parity` 内のローカル `status_map` を AST で取り出す。

    import では取れない (関数ローカル) ため構文木から読む。実行時の値と乖離しないよう、
    見つからなければ落とす。
    """
    tree = ast.parse((SCRIPTS / "bd-bridge.py").read_text(encoding="utf-8"))
    for function in ast.walk(tree):
        if isinstance(function, ast.FunctionDef) and function.name == "_ready_with_parity":
            for statement in ast.walk(function):
                if (
                    isinstance(statement, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "status_map" for t in statement.targets)
                ):
                    return ast.literal_eval(statement.value)
    raise AssertionError("bd-bridge.py _ready_with_parity no longer defines status_map")


def test_status_vocabulary_matches_c28_bridge():
    builder = load("build-parity-manifest.py", "c28_manifest_status")
    assert builder.BRIDGE_STATUS_MAP == bridge_status_map()


def test_status_vocabulary_covers_graph_schema_enum():
    """graph schema の status enum を漏れなく覆う (漏れた status は fail-closed で停止する)。"""
    builder = load("build-parity-manifest.py", "c28_manifest_enum")
    schema = json.loads((PLUGIN / "schemas" / "graph-node.schema.json").read_text(encoding="utf-8"))
    assert set(builder.BRIDGE_STATUS_MAP) == set(schema["properties"]["status"]["enum"])


def test_unmappable_status_fails_closed(tmp_path, monkeypatch, capsys):
    """C28 が写せない status は黙って除外せず停止する。

    除外すると下流で `parity_manifest_missing` (= C03 sync 案件) という誤った札が付き、
    対処 owner を誤らせたまま発見が遅れる。
    """
    builder = load("build-parity-manifest.py", "c28_manifest_unmappable")
    graph = workspace(tmp_path, [node("n-1", "B-1", status="archived")])
    with pytest.raises(builder.ContractError, match="not accepted by the C28 status map"):
        call_main(builder, monkeypatch, capsys, "--repo-root", tmp_path, "--graph", graph)


# --- 3. status で間引かない -------------------------------------------------


def test_terminal_status_nodes_stay_in_manifest(tmp_path, monkeypatch, capsys):
    """`done`/`closed` を省くと、それを依存に持つ active node が C28 で conflicts へ落ちる。"""
    builder = load("build-parity-manifest.py", "c28_manifest_terminal")
    graph = workspace(tmp_path, [
        node("n-done", "B-done", status="done"),
        node("n-closed", "B-closed", status="closed"),
        node("n-draft", "B-draft", status="draft"),
        node("n-live", "B-live", depends_on=["n-done", "n-closed"]),
    ])

    code, receipt = call_main(builder, monkeypatch, capsys, "--repo-root", tmp_path, "--graph", graph)
    assert code == 0 and receipt["dependency_gaps"] == []
    manifest = json.loads((tmp_path / receipt["manifest_path"]).read_text(encoding="utf-8"))
    assert {row["graph_node_id"]: row["graph_status"] for row in manifest["nodes"]} == {
        "n-done": "done", "n-closed": "closed", "n-draft": "draft", "n-live": "active",
    }


def test_manifest_recovers_a_non_empty_ready_set(tmp_path, monkeypatch, capsys):
    """受入: 生成 → C28 ready で ready-set が空にならず conflicts も出ない。"""
    builder = load("build-parity-manifest.py", "c28_manifest_e2e_build")
    graph = workspace(tmp_path, [
        node("n-done", "B-done", status="done"),
        node("n-live", "B-live", depends_on=["n-done"]),
    ])
    code, receipt = call_main(builder, monkeypatch, capsys, "--repo-root", tmp_path, "--graph", graph)
    assert code == 0
    manifest_path = tmp_path / receipt["manifest_path"]

    bridge = load("bd-bridge.py", "c28_manifest_e2e_ready")
    issues = [{"id": "B-live", "status": "open", "dependencies": [{"id": "B-done"}],
               "external_ref": "dev-graph:n-live"}]
    shown = {"B-live": {**issues[0], "dependencies": [{"id": "B-done", "dependency_type": "blocks"}]}}
    monkeypatch.setattr(
        bridge, "preflight",
        lambda root, expected=None: {"version": "1.1.0", "workspace_identity": {"workspace_id": "bdw_fixture"}},
    )
    monkeypatch.setattr(
        bridge, "bd",
        lambda args, cwd, check=True: issues if args[0] == "ready" else shown[args[1]],
    )

    code, ready = call_main(
        bridge, monkeypatch, capsys,
        "--op", "ready", "--repo-root", tmp_path, "--parity-manifest", manifest_path,
    )
    assert code == 0
    assert [row["bd_issue_id"] for row in ready["ready_set"]] == ["B-live"]
    assert ready["conflicts"] == [] and ready["unmapped"] == []


# --- 4. 落ちた node は理由つきで残す ----------------------------------------


def test_unlinked_and_dependency_gaps_are_reported_not_dropped(tmp_path, monkeypatch, capsys):
    builder = load("build-parity-manifest.py", "c28_manifest_diagnostics")
    graph = workspace(tmp_path, [
        node("n-unlinked", None),
        node("n-github", "ignored", tracker_binding="github"),
        node("n-live", "B-live", depends_on=["n-unlinked"]),
    ])

    code, receipt = call_main(builder, monkeypatch, capsys, "--repo-root", tmp_path, "--graph", graph)
    assert code == 0 and receipt["node_count"] == 1
    assert receipt["unlinked"] == [{"graph_node_id": "n-unlinked", "reason": "beads_linkage_absent"}]
    # 依存欠けは manifest から消さず事実どおり載せ、生成時点でも可視化する
    # (消すと C28 の conflicts と parity_manifest_missing が区別できなくなる)。
    assert receipt["dependency_gaps"] == [{
        "graph_node_id": "n-live", "bd_issue_id": "B-live",
        "dependencies_outside_manifest": ["n-unlinked"],
    }]
    manifest = json.loads((tmp_path / receipt["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["nodes"][0]["depends_on"] == ["n-unlinked"]


def test_graph_node_ids_is_the_full_existence_set_not_the_projection(tmp_path, monkeypatch, capsys):
    """`graph_node_ids` は「graph に実在した node の全集合」で `nodes[]` の superset。

    投影対象だけを載せると、起票前 node と「graph から消えた node」が C28 で同じ札に
    なる。前者は C03 sync / C02 起票で解ける一方、後者 (orphan external_ref) は sync を
    何度回しても解けないため、混ぜると「sync すれば直る」という誤診断が常駐する。
    """
    builder = load("build-parity-manifest.py", "c28_manifest_existence_set")
    graph = workspace(tmp_path, [
        node("n-linked", "B-linked"),
        node("n-unlinked", None),                          # 起票前 (投影対象外)
        node("n-github", "ignored", tracker_binding="github"),  # tracker が beads でない
    ])

    code, receipt = call_main(builder, monkeypatch, capsys, "--repo-root", tmp_path, "--graph", graph)
    assert code == 0
    manifest = json.loads((tmp_path / receipt["manifest_path"]).read_text(encoding="utf-8"))
    assert [row["graph_node_id"] for row in manifest["nodes"]] == ["n-linked"]
    assert manifest["graph_node_ids"] == ["n-github", "n-linked", "n-unlinked"]
    assert {"generated_at", "source_graph_digest", "nodes", "graph_node_ids"} <= set(manifest)


def test_duplicate_bd_issue_id_fails_closed(tmp_path, monkeypatch, capsys):
    """C28 が manifest 破損として拒否する重複を、生成側で先に止める。"""
    builder = load("build-parity-manifest.py", "c28_manifest_duplicate")
    graph = workspace(tmp_path, [node("n-a", "B-same"), node("n-b", "B-same")])
    with pytest.raises(builder.ContractError, match="duplicate bd_issue_id"):
        call_main(builder, monkeypatch, capsys, "--repo-root", tmp_path, "--graph", graph)


def test_output_is_confined_to_repository_eval_log(tmp_path, monkeypatch, capsys):
    """read-only な投影 script が graph/tracker state の書込経路にならないこと。"""
    builder = load("build-parity-manifest.py", "c28_manifest_scope")
    graph = workspace(tmp_path, [node("n-1", "B-1")])
    with pytest.raises(builder.ContractError, match="escapes authority root"):
        call_main(
            builder, monkeypatch, capsys, "--repo-root", tmp_path, "--graph", graph,
            "--out", ".dev-graph/state/graph.json",
        )
    assert json.loads(graph.read_text())["nodes"][0]["graph_node_id"] == "n-1"


def test_graph_defaults_to_the_managed_repository_config(tmp_path, monkeypatch, capsys):
    """`--graph` を省くと managed repository の `.dev-graph/config.json` の local_state.graph を読む。"""
    builder = load("build-parity-manifest.py", "c28_manifest_config")
    workspace(tmp_path, [node("n-1", "B-1")])
    (tmp_path / ".dev-graph" / "config.json").write_text(
        json.dumps({"local_state": {"graph": ".dev-graph/state/graph.json"}}), encoding="utf-8"
    )

    code, receipt = call_main(builder, monkeypatch, capsys, "--repo-root", tmp_path)

    assert code == 0
    assert receipt["manifest_path"] == builder.DEFAULT_OUT
    assert receipt["node_count"] == 1

"""build-merged-graph.py (graph.json 専用 git merge driver) の検証。

graph.json は多数のノードが1配列に並ぶ単一 JSON のため、git 標準の行ベース 3-way
マージは「配列の同じ位置への両側追加」を衝突として誤検出する。本テストは次の4層を検証する。

1. 構造マージ本体 — graph_node_id 単位の集合演算とフィールド単位の 3-way 分岐
2. git merge driver 契約 — exit 0 なら %A を採用 / 非0 なら未解決のまま sentinel を残す
3. 実 git merge での発火 — managed repository の `.gitattributes` 宣言と `--install` の
   git config が噛み合って driver が実際に呼ばれること
4. 既に conflicted な index の解消 — C02 lock の下で envelope を検査してから書くこと

3 は「driver は書いたが .gitattributes が無く一度も発火していなかった」という失敗を、
機械検査として塞ぐためのもの。plugin は利用者の repository に `.gitattributes` を
書かないので、`--install` の receipt が宣言の有無を報告することもここで固定する。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
DRIVER = SCRIPTS / "build-merged-graph.py"
GRAPH_REL = ".dev-graph/state/graph.json"
ATTRIBUTE_LINE = f"{GRAPH_REL} merge=devgraph-json\n"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(PLUGIN / "lib") not in sys.path:
    sys.path.insert(0, str(PLUGIN / "lib"))

from graph_envelope import envelope_violations  # noqa: E402


def load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load("build-merged-graph.py", "build_merged_graph")


def _node(node_id: str, **fields) -> dict:
    node = {"graph_node_id": node_id, "artifact_kind": "issue", "status": "draft"}
    node.update(fields)
    return node


def _graph(revision: int, nodes: list[dict], *, repository_id: str | None = "acme/web") -> dict:
    graph = {"schema_version": "1.0.0", "graph_revision": revision, "nodes": nodes}
    if repository_id is not None:
        graph["repository_id"] = repository_id
    return graph


def _ids(graph: dict) -> list[str]:
    return [node["graph_node_id"] for node in graph["nodes"]]


# --- 1. フィールド単位の 3-way -------------------------------------------------


def test_scalar_convergent_edit_is_not_conflict():
    """両側が base から「同じ値」へ変えた収束編集は衝突にしない。"""
    assert mod._merge_scalar("draft", "active", "active") == ("active", False)


def test_scalar_one_sided_change_takes_the_changed_side():
    """片側だけが base から動いたなら、動いた側を採用する (もう片方は無変更)。"""
    assert mod._merge_scalar("draft", "active", "draft") == ("active", False)
    assert mod._merge_scalar("draft", "draft", "tombstoned") == ("tombstoned", False)


def test_scalar_divergent_change_is_conflict():
    """両側が base から別々の値へ動いた場合だけを真の衝突とする。"""
    value, conflicted = mod._merge_scalar("draft", "active", "tombstoned")
    assert conflicted is True
    assert value == "active"


# --- 2. ノード単位の集合演算 ---------------------------------------------------


def test_both_sides_add_distinct_nodes_are_both_kept():
    """別々のノードを両側が追加した場合は両方残す。順序は ours 優先 + theirs 追記。"""
    base = _graph(10, [_node("a")])
    ours = _graph(11, [_node("a"), _node("ours-only")])
    theirs = _graph(11, [_node("a"), _node("theirs-only")])

    merged, conflicted, preserved = mod.merge_graph(base, ours, theirs)

    assert conflicted is False
    assert _ids(merged) == ["a", "ours-only", "theirs-only"]
    assert preserved == []


def test_same_node_different_fields_merge_without_conflict():
    """同じノードでも触ったフィールドが異なるなら、両方の変更を取り込む。"""
    base = _graph(10, [_node("a", status="draft", priority="low")])
    ours = _graph(11, [_node("a", status="active", priority="low")])
    theirs = _graph(11, [_node("a", status="draft", priority="high")])

    merged, conflicted, _ = mod.merge_graph(base, ours, theirs)

    assert conflicted is False
    assert merged["nodes"][0]["status"] == "active"
    assert merged["nodes"][0]["priority"] == "high"


def test_same_field_divergent_change_writes_sentinel():
    """同じノードの同じフィールドが両側で別値になったら sentinel を残して衝突を報告する。"""
    base = _graph(10, [_node("a", status="draft")])
    ours = _graph(11, [_node("a", status="active")])
    theirs = _graph(11, [_node("a", status="tombstoned")])

    merged, conflicted, _ = mod.merge_graph(base, ours, theirs)

    sentinel = merged["nodes"][0]
    assert conflicted is True
    assert sentinel["__merge_conflict__"] is True
    assert "status" in sentinel["reason"]
    assert sentinel["ours"]["status"] == "active"
    assert sentinel["theirs"]["status"] == "tombstoned"


def test_one_sided_deletion_is_preserved_by_default():
    """片側から消えたノードは既定で温存する。事故で消えたノードを黙って葬らないため。"""
    base = _graph(10, [_node("a"), _node("gone")])
    ours = _graph(11, [_node("a"), _node("gone")])
    theirs = _graph(11, [_node("a")])

    merged, conflicted, preserved = mod.merge_graph(base, ours, theirs)

    assert conflicted is False
    assert preserved == ["gone"]
    assert _ids(merged) == ["a", "gone"]


def test_accepted_deletion_is_actually_dropped():
    """意図的な削除と確認できた id だけ --accept-deletion で実際に落とせる。"""
    base = _graph(10, [_node("a"), _node("gone")])
    ours = _graph(11, [_node("a"), _node("gone")])
    theirs = _graph(11, [_node("a")])

    merged, conflicted, preserved = mod.merge_graph(
        base, ours, theirs, accept_deletions=frozenset({"gone"})
    )

    assert conflicted is False
    assert preserved == []
    assert _ids(merged) == ["a"]


def test_same_id_added_by_both_sides_with_identical_content_is_not_conflict():
    """同じ id を両側が独立に追加しても、内容が同一なら衝突にしない。"""
    base = _graph(10, [])
    ours = _graph(11, [_node("dup", status="draft")])
    theirs = _graph(11, [_node("dup", status="draft")])

    merged, conflicted, _ = mod.merge_graph(base, ours, theirs)

    assert conflicted is False
    assert _ids(merged) == ["dup"]


def test_same_id_added_by_both_sides_with_different_content_is_conflict():
    """同じ id を両側が別内容で追加した場合は base が無いため field 3-way できず衝突。"""
    base = _graph(10, [])
    ours = _graph(11, [_node("dup", status="draft")])
    theirs = _graph(11, [_node("dup", status="active")])

    merged, conflicted, _ = mod.merge_graph(base, ours, theirs)

    assert conflicted is True
    assert merged["nodes"][0]["__merge_conflict__"] is True
    assert "independently added" in merged["nodes"][0]["reason"]


def test_graph_revision_advances_past_the_more_advanced_side():
    """マージ自体を1回の書込みとみなし、進んでいる側の revision に +1 する。"""
    base = _graph(10, [_node("a")])
    ours = _graph(11, [_node("a"), _node("ours-only")])
    theirs = _graph(15, [_node("a"), _node("theirs-only")])

    merged, _, _ = mod.merge_graph(base, ours, theirs)

    assert merged["graph_revision"] == 16


def test_graph_revision_is_not_advanced_when_both_sides_are_identical():
    """実質無変更マージでは revision を無駄に進めない。"""
    base = _graph(10, [_node("a")])
    ours = _graph(11, [_node("a"), _node("x")])
    theirs = _graph(12, [_node("a"), _node("x")])

    merged, _, _ = mod.merge_graph(base, ours, theirs)

    assert merged["graph_revision"] == 12


def test_merged_envelope_stays_canonical_with_and_without_repository_id():
    """外枠は canonical key だけで組み直す。repository_id が無い store へ null を足さない。"""
    for repository_id in ("acme/web", None):
        base = _graph(1, [_node("a")], repository_id=repository_id)
        ours = _graph(2, [_node("a"), _node("o")], repository_id=repository_id)
        theirs = _graph(2, [_node("a"), _node("t")], repository_id=repository_id)

        merged, conflicted, _ = mod.merge_graph(base, ours, theirs)

        assert conflicted is False
        assert ("repository_id" in merged) is (repository_id is not None)
        assert envelope_violations(merged) == []


# --- 3. git merge driver 契約 (%O %A %B) --------------------------------------


def _run_driver(tmp_path: Path, base: dict, ours: dict, theirs: dict):
    paths = {}
    for name, graph in (("base", base), ("ours", ours), ("theirs", theirs)):
        path = tmp_path / f"{name}.json"
        path.write_text(
            json.dumps(graph, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        paths[name] = path
    proc = subprocess.run(
        [sys.executable, "-B", str(DRIVER), str(paths["base"]), str(paths["ours"]), str(paths["theirs"]), GRAPH_REL],
        capture_output=True,
        text=True,
    )
    return proc, json.loads(paths["ours"].read_text(encoding="utf-8"))


def test_driver_exit_zero_writes_merged_result_into_ours_path(tmp_path):
    """契約: exit 0 のとき git は %A をそのまま採用するので、%A にマージ結果が要る。"""
    proc, result = _run_driver(
        tmp_path,
        _graph(10, [_node("a")]),
        _graph(11, [_node("a"), _node("ours-only")]),
        _graph(11, [_node("a"), _node("theirs-only")]),
    )

    assert proc.returncode == 0, proc.stderr
    assert _ids(result) == ["a", "ours-only", "theirs-only"]


def test_driver_exit_one_leaves_sentinel_for_manual_resolution(tmp_path):
    """契約: 非0 で git は未解決のまま残す。%A には診断用 sentinel を書く。"""
    proc, result = _run_driver(
        tmp_path,
        _graph(10, [_node("a", status="draft")]),
        _graph(11, [_node("a", status="active")]),
        _graph(11, [_node("a", status="tombstoned")]),
    )

    assert proc.returncode == 1
    assert result["nodes"][0]["__merge_conflict__"] is True
    assert "__merge_conflict__" in proc.stderr or "unresolved" in proc.stderr


def test_driver_rejects_unparsable_input_without_writing_garbage(tmp_path):
    """fail-closed: 入力が読めないときは exit 1 で止まり、勝手な内容を書かない。"""
    base = tmp_path / "base.json"
    ours = tmp_path / "ours.json"
    theirs = tmp_path / "theirs.json"
    base.write_text("{}", encoding="utf-8")
    ours.write_text("not json at all", encoding="utf-8")
    theirs.write_text("{}", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-B", str(DRIVER), str(base), str(ours), str(theirs), GRAPH_REL],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 1
    assert ours.read_text(encoding="utf-8") == "not json at all"


# --- 4. 実 git merge での発火 ---------------------------------------------------


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if check and proc.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr or proc.stdout}")
    return proc


def _write_graph(root: Path, graph: dict) -> None:
    (root / GRAPH_REL).write_text(
        json.dumps(graph, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _commit_graph(root: Path, graph: dict, message: str) -> None:
    _write_graph(root, graph)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)


def _branch(root: Path, name: str) -> None:
    _git(root, "checkout", "-b", name)


def _install(root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", str(DRIVER), "--install", "--repo-root", str(root)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _init_repo(tmp_path: Path, *, install_driver: bool = True, declare: bool = True) -> Path:
    """managed repository と同じ形の最小 git repo を作る。

    `declare=True` は利用者が `.gitattributes` に driver の宣言を置いた repository を再現する。
    `install_driver=False` は対照実験用。宣言はあるが `merge.devgraph-json.driver` の
    git config が無い = 未 install の clone を再現する。
    """
    root = tmp_path / "repo"
    (root / ".dev-graph" / "state").mkdir(parents=True)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "dev-graph test")
    _git(root, "config", "core.hooksPath", "/dev/null")
    if declare:
        (root / ".gitattributes").write_text(ATTRIBUTE_LINE, encoding="utf-8")
    if install_driver:
        _install(root)
    return root


def _build_conflicting_branches(root: Path) -> None:
    """行ベース 3-way マージが衝突するシナリオを 2 ブランチで構築する。

    base の nodes 配列末尾へ、feature-a と main がそれぞれ別のノードを追加する。
    `sort_keys=True, indent=2` で整形された JSON では、どちらの追加も「base-2 の
    オブジェクト直後」という同じ行位置への挿入になるため、git は同一ハンクの競合として
    衝突を報告する。構造マージなら graph_node_id が異なる別ノードの追加として両方を保持できる。
    """
    _commit_graph(root, _graph(1, [_node("base-1"), _node("base-2")]), "base")
    _branch(root, "feature-a")
    _commit_graph(
        root, _graph(2, [_node("base-1"), _node("base-2"), _node("theirs-only")]), "theirs adds a node"
    )
    _git(root, "checkout", "main")
    _commit_graph(
        root, _graph(2, [_node("base-1"), _node("base-2"), _node("ours-only")]), "ours adds a node"
    )


def test_install_reports_routing_without_writing_gitattributes(tmp_path):
    """`--install` は tracked file を書かない。宣言が無ければ receipt で未配線と次の手を返す。"""
    root = _init_repo(tmp_path, install_driver=False, declare=False)

    receipt = _install(root)

    assert receipt["installed"] is True
    assert receipt["gitattributes_routed"] is False
    assert ATTRIBUTE_LINE.strip() in receipt["next"]
    assert not (root / ".gitattributes").exists()
    assert " -B " in _git(root, "config", "--get", "merge.devgraph-json.driver").stdout

    (root / ".gitattributes").write_text(ATTRIBUTE_LINE, encoding="utf-8")
    assert _install(root)["gitattributes_routed"] is True


def test_scenario_really_conflicts_without_the_driver(tmp_path):
    """対照実験: driver 未 install の repo では、同じシナリオが必ず行ベースで衝突する。

    これが緑でなければ本命テストは「行ベースでも偶然解決できるシナリオ」を見ているだけで、
    driver の発火を何も保証しない。
    """
    root = _init_repo(tmp_path, install_driver=False)
    _build_conflicting_branches(root)

    merge = _git(root, "merge", "feature-a", check=False)

    assert merge.returncode != 0, "driver 無しでも解決できてしまう = 衝突シナリオになっていない"
    assert "<<<<<<<" in (root / GRAPH_REL).read_text(encoding="utf-8")


def test_driver_resolves_conflicting_array_appends_on_real_git_merge(tmp_path):
    """行ベースなら衝突するシナリオを、実際の git merge で driver が解決することを検証する。"""
    root = _init_repo(tmp_path)
    _build_conflicting_branches(root)

    merge = _git(root, "merge", "feature-a", check=False)

    graph_text = (root / GRAPH_REL).read_text(encoding="utf-8")
    assert "<<<<<<<" not in graph_text, "行ベースの衝突マーカーが残っている = driver が発火していない"
    assert merge.returncode == 0, f"driver が解決できなかった: {merge.stdout}{merge.stderr}"

    merged = json.loads(graph_text)
    assert {"ours-only", "theirs-only"} <= set(_ids(merged)), "両側の追加ノードが揃っていない"
    assert all(not node.get("__merge_conflict__") for node in merged["nodes"])
    assert envelope_violations(merged) == []


# --- 5. 既に conflicted な index の解消 -----------------------------------------


def test_resolve_conflict_writes_canonical_graph_under_the_c02_lock(tmp_path):
    """driver 未 install で作られた衝突を、構造マージ結果で解消する。外枠は canonical のまま。"""
    root = _init_repo(tmp_path, install_driver=False)
    _build_conflicting_branches(root)
    assert _git(root, "merge", "feature-a", check=False).returncode != 0

    proc = subprocess.run(
        [sys.executable, "-B", str(DRIVER), "--resolve-conflict", "--repo-root", str(root)],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["written"] is True
    graph = json.loads((root / GRAPH_REL).read_text(encoding="utf-8"))
    assert {"ours-only", "theirs-only"} <= set(_ids(graph))
    assert envelope_violations(graph) == []
    # build-graph-node.py / register-package.py と同じ lock file を取っている。
    assert (root / ".dev-graph" / "state" / ".graph.json.register.lock").exists()


def test_resolve_conflict_refuses_a_merged_envelope_that_is_not_canonical(tmp_path, monkeypatch):
    """マージ結果の外枠が canonical でなければ、衝突中の graph を書き換えずに止める (fail-closed)。"""
    root = _init_repo(tmp_path, install_driver=False)
    _build_conflicting_branches(root)
    assert _git(root, "merge", "feature-a", check=False).returncode != 0
    conflicted = (root / GRAPH_REL).read_text(encoding="utf-8")
    original = mod.merge_graph

    def broken_envelope(base, ours, theirs, accept_deletions=frozenset()):
        merged, has_conflict, preserved = original(base, ours, theirs, accept_deletions)
        merged["repository_id"] = ""
        return merged, has_conflict, preserved

    monkeypatch.setattr(mod, "merge_graph", broken_envelope)

    assert mod.resolve_conflict(root, GRAPH_REL, dry_run=False) == 1
    assert (root / GRAPH_REL).read_text(encoding="utf-8") == conflicted

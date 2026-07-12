"""lint-dependency-direction.py の DAG 循環 / 依存方向検出を実入力で網羅検証する。

tests/scripts-root/ 及び tests/scripts-plugins/ 側の既存テストと別ディレクトリ・別観点で、本ファイル単独でも対象
script の主要分岐を覆う。純関数 (skill_prefix / parse_invocation_dependencies /
build_graph / detect_cycles / detect_direction_violations) を実入力で呼び、main を
直接 import 呼び出し + subprocess の双方で OK / 方向違反 / 循環 / dir 欠落 /
--out 書き出し / 空 dir の各経路を検証する。

特に注力する分岐:
  - detect_cycles の path.pop / 未知ノード辺スキップ / 自己ループ / 多段DAG
  - detect_direction_violations の unknown レイヤー fallback (LAYER.get 既定 99)
  - main の stdout-print 分岐 (--out 無し) と --out 書き出し分岐
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-governance-lint"
    / "scripts"
    / "lint-dependency-direction.py"
)


def _load():
    """coverage 計測下 (テスト実行フェーズ) で module を import するため遅延ロードする。
    module-level で exec すると collection 時に実行されカバレッジに乗らないため。
    """
    spec = importlib.util.spec_from_file_location("lint_dependency_direction_t", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def MOD():
    return _load()


def _mk_skill(root: Path, name: str, body: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


# --- skill_prefix ---


def test_skill_prefix_all_known_and_unknown(MOD):
    for name, expect in [
        ("ref-x", "ref"),
        ("assign-x", "assign"),
        ("run-x", "run"),
        ("wrap-x", "wrap"),
        ("delegate-x", "delegate"),
    ]:
        assert MOD.skill_prefix(name) == expect
    # 接頭辞だがハイフン無し -> unknown (誤マッチ防止)
    assert MOD.skill_prefix("running") == "unknown"
    assert MOD.skill_prefix("capability-build") == "unknown"


# --- parse_invocation_dependencies ---


def test_parse_dedups_and_excludes_pair(MOD, tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text(
        "Skill(run-a) と Skill(ref-b)\n"
        "Skill(run-a) 重複\n"
        "pair: run-zzz は依存でない\n",
        encoding="utf-8",
    )
    deps = sorted(MOD.parse_invocation_dependencies(md))
    assert deps == ["ref-b", "run-a"]
    assert "run-zzz" not in deps


def test_parse_empty_body(MOD, tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text("", encoding="utf-8")
    assert MOD.parse_invocation_dependencies(md) == []


# --- build_graph ---


def test_build_graph_collects_nested_skills(MOD, tmp_path):
    _mk_skill(tmp_path / "nested", "run-a", "Skill(ref-b)\n")
    _mk_skill(tmp_path, "ref-b", "leaf\n")
    graph, prefixes = MOD.build_graph(tmp_path)
    assert set(graph.keys()) == {"run-a", "ref-b"}
    assert graph["run-a"] == ["ref-b"]
    assert prefixes["run-a"] == "run"
    assert prefixes["ref-b"] == "ref"


def test_build_graph_empty_dir(MOD, tmp_path):
    graph, prefixes = MOD.build_graph(tmp_path)
    assert graph == {}
    assert prefixes == {}


# --- detect_cycles ---


def test_detect_cycles_self_loop(MOD):
    cycles = MOD.detect_cycles({"run-a": ["run-a"]})
    assert len(cycles) == 1
    assert cycles[0][0] == "run-a"


def test_detect_cycles_three_node_cycle(MOD):
    graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
    cycles = MOD.detect_cycles(graph)
    assert len(cycles) >= 1
    assert {"a", "b", "c"} <= set(cycles[0])


def test_detect_cycles_clean_dag_with_shared_leaf(MOD):
    # 共有葉を持つ DAG: path.pop / BLACK 着色を通すが循環なし
    graph = {
        "run-a": ["ref-leaf"],
        "run-b": ["ref-leaf"],
        "ref-leaf": [],
    }
    assert MOD.detect_cycles(graph) == []


def test_detect_cycles_ignores_external_edges(MOD):
    # グラフ外ノードへの辺は辿らない
    assert MOD.detect_cycles({"run-a": ["ghost"]}) == []


def test_detect_cycles_empty_graph(MOD):
    assert MOD.detect_cycles({}) == []


# --- detect_direction_violations ---


def test_violation_ref_to_run(MOD):
    v = MOD.detect_direction_violations(
        {"ref-a": ["run-b"]}, {"ref-a": "ref", "run-b": "run"}
    )
    assert len(v) == 1
    assert v[0]["source"] == "ref-a"
    assert v[0]["dependency"] == "run-b"
    assert "should not invoke" in v[0]["violation"]


def test_violation_assign_to_run(MOD):
    v = MOD.detect_direction_violations(
        {"assign-a": ["run-b"]}, {"assign-a": "assign", "run-b": "run"}
    )
    assert len(v) == 1
    assert v[0]["source_layer"] == "assign"
    assert v[0]["dependency_layer"] == "run"


def test_no_violation_downward_and_same_layer(MOD):
    # run(2)->ref(0) 下向き / run(2)->wrap(2) 同層 はいずれも合法
    graph = {"run-a": ["ref-b", "wrap-c"]}
    prefixes = {"run-a": "run", "ref-b": "ref", "wrap-c": "wrap"}
    assert MOD.detect_direction_violations(graph, prefixes) == []


def test_unknown_source_layer_treated_as_top(MOD):
    # source が unknown (LAYER 既定 99) なら dep は必ず <=99 なので違反にならない
    graph = {"cap-x": ["run-b"]}
    prefixes = {"cap-x": "unknown", "run-b": "run"}
    assert MOD.detect_direction_violations(graph, prefixes) == []


def test_unknown_dependency_layer_is_violation_from_ref(MOD):
    # ref(0) -> unknown(99) は上向きなので違反
    graph = {"ref-a": ["cap-x"]}
    prefixes = {"ref-a": "ref", "cap-x": "unknown"}
    v = MOD.detect_direction_violations(graph, prefixes)
    assert len(v) == 1
    assert v[0]["dependency_layer"] == "unknown"


# --- main: import 直呼びで stdout-print 分岐 / 各 return code ---


def test_main_ok_prints_report_to_stdout(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill(tmp_path, "run-a", "Skill(ref-b)\n")
    _mk_skill(tmp_path, "ref-b", "leaf\n")
    monkeypatch.setattr(sys, "argv", ["prog", "--skills-dir", str(tmp_path)])
    rc = MOD.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK: no cycles" in out
    report = json.loads(out.split("OK:")[0].strip())
    assert report["skills_scanned"] == 2
    assert report["cycles_count"] == 0
    assert report["violations_count"] == 0
    # invocation_graph は非空依存のみを残す
    assert report["invocation_graph"] == {"run-a": ["ref-b"]}


def test_main_missing_dir_returns_2(MOD, tmp_path, monkeypatch, capsys):
    missing = tmp_path / "no_such"
    monkeypatch.setattr(sys, "argv", ["prog", "--skills-dir", str(missing)])
    rc = MOD.main()
    assert rc == 2
    assert "skills-dir not found" in capsys.readouterr().err


def test_main_writes_out_file_and_no_stdout_report(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill(tmp_path, "run-a", "Skill(ref-b)\n")
    _mk_skill(tmp_path, "ref-b", "leaf\n")
    out = tmp_path / "rep.json"
    monkeypatch.setattr(
        sys, "argv", ["prog", "--skills-dir", str(tmp_path), "--out", str(out)]
    )
    rc = MOD.main()
    assert rc == 0
    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["skills_scanned"] == 2
    # --out 指定時、stdout には JSON を出さず OK 行のみ
    stdout = capsys.readouterr().out
    assert "OK: no cycles" in stdout
    assert "skills_scanned" not in stdout


def test_main_empty_dir_is_ok(MOD, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--skills-dir", str(tmp_path)])
    rc = MOD.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "0 skills scanned" in out


def test_main_direction_violation_returns_1_inprocess(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill(tmp_path, "ref-a", "Skill(run-b)\n")  # 上向き違反
    _mk_skill(tmp_path, "run-b", "leaf\n")
    monkeypatch.setattr(sys, "argv", ["prog", "--skills-dir", str(tmp_path)])
    rc = MOD.main()
    assert rc == 1
    cap = capsys.readouterr()
    assert "direction violation" in cap.err
    # stdout 側 report にも違反件数が出る
    report = json.loads(cap.out.split("FAIL")[0].strip()) if "FAIL" in cap.out else json.loads(cap.out.strip())
    assert report["violations_count"] == 1


def test_main_cycle_returns_2_inprocess(MOD, tmp_path, monkeypatch, capsys):
    _mk_skill(tmp_path, "run-a", "Skill(run-b)\n")
    _mk_skill(tmp_path, "run-b", "Skill(run-a)\n")
    monkeypatch.setattr(sys, "argv", ["prog", "--skills-dir", str(tmp_path)])
    rc = MOD.main()
    assert rc == 2
    cap = capsys.readouterr()
    assert "cycle" in cap.err
    report = json.loads(cap.out.strip())
    assert report["cycles_count"] >= 1


# --- main: subprocess で違反 / 循環の exit code を確認 ---


def test_subprocess_direction_violation_exits_1(tmp_path):
    _mk_skill(tmp_path, "ref-a", "Skill(run-b)\n")
    _mk_skill(tmp_path, "run-b", "leaf\n")
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 1
    assert "direction violation" in proc.stderr


def test_subprocess_cycle_exits_2(tmp_path):
    _mk_skill(tmp_path, "run-a", "Skill(run-b)\n")
    _mk_skill(tmp_path, "run-b", "Skill(run-a)\n")
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 2
    assert "cycle" in proc.stderr

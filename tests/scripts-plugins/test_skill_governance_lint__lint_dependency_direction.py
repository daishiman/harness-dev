"""lint-dependency-direction.py の依存方向/循環検出ロジックを実入力で検証する。

このスクリプトは SKILL.md 群から Skill() 呼び出しのみを依存辺として抽出し、
(a) DAG 循環、(b) 上向き依存 (ref->run 等) を検出する。pair: は所有宣言なので
依存辺に含めない。本テストは純関数 (skill_prefix / parse_invocation_dependencies /
build_graph / detect_cycles / detect_direction_violations) を実入力で呼び、main を
subprocess で OK/違反/循環/エラーの 4 経路について exit code と出力を検証する。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-governance-lint"
    / "scripts"
    / "lint-dependency-direction.py"
)
SPEC = importlib.util.spec_from_file_location("lint_dependency_direction", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- skill_prefix: レイヤー接頭辞の分類 ---

def test_skill_prefix_known_layers():
    assert MOD.skill_prefix("ref-output-routing") == "ref"
    assert MOD.skill_prefix("assign-x") == "assign"
    assert MOD.skill_prefix("run-build") == "run"
    assert MOD.skill_prefix("wrap-git") == "wrap"
    assert MOD.skill_prefix("delegate-review") == "delegate"


def test_skill_prefix_unknown_returns_unknown():
    assert MOD.skill_prefix("capability-build") == "unknown"
    assert MOD.skill_prefix("noprefix") == "unknown"
    # 接頭辞に "-" が続かない名前は誤マッチしない
    assert MOD.skill_prefix("runner") == "unknown"


# --- parse_invocation_dependencies: Skill() 抽出 (pair: 除外) ---

def test_parse_invocation_dependencies_extracts_only_skill_calls(tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text(
        "本文では Skill(run-build-skill) を呼ぶ。\n"
        "pair: run-elegant-review\n"  # pair: は依存辺に含めない
        "また Skill(ref-output-routing) も使う。\n"
        "Skill(run-build-skill) は重複しても 1 件。\n",
        encoding="utf-8",
    )
    deps = MOD.parse_invocation_dependencies(md)
    assert sorted(deps) == ["ref-output-routing", "run-build-skill"]
    # pair: で書いた run-elegant-review は抽出されない
    assert "run-elegant-review" not in deps


def test_parse_invocation_dependencies_empty_when_no_calls(tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text("ここには Skill 呼び出しは無い。pair: run-x のみ。\n", encoding="utf-8")
    assert MOD.parse_invocation_dependencies(md) == []


# --- build_graph: ディレクトリ走査でグラフ構築 ---

def _mk_skill(root: Path, name: str, body: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def test_build_graph_maps_skill_to_deps_and_prefix(tmp_path):
    _mk_skill(tmp_path, "run-a", "Skill(ref-b) を使う\n")
    _mk_skill(tmp_path, "ref-b", "葉ノード\n")
    graph, prefixes = MOD.build_graph(tmp_path)
    assert graph["run-a"] == ["ref-b"]
    assert graph["ref-b"] == []
    assert prefixes["run-a"] == "run"
    assert prefixes["ref-b"] == "ref"


# --- detect_cycles: 循環検出 ---

def test_detect_cycles_finds_self_loop():
    graph = {"run-a": ["run-a"]}
    cycles = MOD.detect_cycles(graph)
    assert len(cycles) == 1
    assert "run-a" in cycles[0]


def test_detect_cycles_finds_two_node_cycle():
    graph = {"run-a": ["run-b"], "run-b": ["run-a"]}
    cycles = MOD.detect_cycles(graph)
    assert len(cycles) >= 1
    nodes = set(cycles[0])
    assert {"run-a", "run-b"} <= nodes


def test_detect_cycles_none_in_dag():
    graph = {"run-a": ["assign-b"], "assign-b": ["ref-c"], "ref-c": []}
    assert MOD.detect_cycles(graph) == []


def test_detect_cycles_ignores_edges_to_unknown_nodes():
    # 依存先がグラフに無いノードは辺として辿らない -> 循環なし
    graph = {"run-a": ["nonexistent-x"]}
    assert MOD.detect_cycles(graph) == []


# --- detect_direction_violations: 上向き依存検出 ---

def test_direction_violation_when_ref_invokes_run():
    graph = {"ref-a": ["run-b"], "run-b": []}
    prefixes = {"ref-a": "ref", "run-b": "run"}
    violations = MOD.detect_direction_violations(graph, prefixes)
    assert len(violations) == 1
    v = violations[0]
    assert v["source"] == "ref-a"
    assert v["dependency"] == "run-b"
    assert v["source_layer"] == "ref"
    assert v["dependency_layer"] == "run"


def test_no_direction_violation_when_run_invokes_ref():
    # run(2) -> ref(0) は下向きなので合法
    graph = {"run-a": ["ref-b"], "ref-b": []}
    prefixes = {"run-a": "run", "ref-b": "ref"}
    assert MOD.detect_direction_violations(graph, prefixes) == []


def test_same_layer_invocation_is_not_violation():
    # run(2) -> wrap(2) は同レイヤーなので違反でない
    graph = {"run-a": ["wrap-b"], "wrap-b": []}
    prefixes = {"run-a": "run", "wrap-b": "wrap"}
    assert MOD.detect_direction_violations(graph, prefixes) == []


# --- main(): subprocess で 4 経路を検証 ---

def _run(args, **kw):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        **kw,
    )


def test_main_missing_dir_returns_2():
    proc = _run(["--skills-dir", "/no/such/dir/xyz"])
    assert proc.returncode == 2
    assert "skills-dir not found" in proc.stderr


def test_main_ok_path_returns_0_with_clean_dag(tmp_path):
    _mk_skill(tmp_path, "run-a", "Skill(ref-b) を呼ぶ\n")
    _mk_skill(tmp_path, "ref-b", "葉\n")
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 0
    assert "OK: no cycles" in proc.stdout
    report = json.loads(proc.stdout.split("OK:")[0].strip())
    assert report["skills_scanned"] == 2
    assert report["cycles_count"] == 0
    assert report["violations_count"] == 0


def test_main_direction_violation_returns_1(tmp_path):
    _mk_skill(tmp_path, "ref-a", "Skill(run-b) を呼ぶ\n")  # 上向き違反
    _mk_skill(tmp_path, "run-b", "葉\n")
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 1
    assert "direction violation" in proc.stderr


def test_main_cycle_returns_2(tmp_path):
    _mk_skill(tmp_path, "run-a", "Skill(run-b)\n")
    _mk_skill(tmp_path, "run-b", "Skill(run-a)\n")
    proc = _run(["--skills-dir", str(tmp_path)])
    assert proc.returncode == 2
    assert "cycle" in proc.stderr


def test_main_writes_report_to_out_file(tmp_path):
    _mk_skill(tmp_path, "run-a", "Skill(ref-b)\n")
    _mk_skill(tmp_path, "ref-b", "葉\n")
    out = tmp_path / "report.json"
    proc = _run(["--skills-dir", str(tmp_path), "--out", str(out)])
    assert proc.returncode == 0
    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["skills_scanned"] == 2
    assert "run-a" in report["invocation_graph"]

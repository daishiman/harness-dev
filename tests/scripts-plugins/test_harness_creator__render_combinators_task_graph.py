"""route C03 render-combinators.py の engine:task-graph 変種拡張の genuine テスト。

GOAL_SEEK_WIRING_SECTION への 3 サブセクション追加 + 2 schema の additive 拡張を検証する。
既存 combinator 生成 (回帰) が壊れないことも確認する。

カバー:
- GOAL_SEEK_TASK_GRAPH_SECTION が GOAL_SEEK_WIRING_SECTION に連結されている
- run kind 生成物に task-graph 変種トークン (ENG-C01/ENG-C02/ENG-C06/ENG-C07 script名・ready_set/selected_item・
  依存順消費・self-reflect 完了 gate・dependency graph knowledge) が全て出現
- 既存トークン (intermediate.jsonl/original_goal/required_keys/hashlib.sha256) が維持 (回帰)
- build-flags.schema の engine enum に task-graph が additive 追加され既存 (inline/run-goal-seek) 維持
- goal-seek-loop.schema の checklist item に depends_on (array/default[]) が additive 追加され既存維持
- engine FM コメントに task-graph 言及

network: false, 実 repo 書換: なし。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RB = ROOT / "plugins/harness-creator/skills/run-build-skill"
SCRIPT = RB / "scripts/render-combinators.py"
BUILD_FLAGS = RB / "schemas/build-flags.schema.json"
LOOP_SCHEMA = RB / "schemas/goal-seek-loop.schema.json"

TASK_GRAPH_TOKENS = [
    "ゴールシーク配線（task-graph 変種）",
    "ゴールシーク検証（task-graph 変種・機械検査）",
    "dependency graph knowledge consult",
    "ready-set-from-checklist.py",
    "self-reflect-append.py",
    "extract-capability-dependency-graph.py",
    "record-capability-graph-knowledge.py",
    "ready_set",
    "selected_item",
    "依存順消費",
    "self-reflect 完了 gate",
]
EXISTING_TOKENS = ["intermediate.jsonl", "original_goal", "merged_directive_for_next",
                   "required_keys", "hashlib.sha256", "ゴールシーク配線（実行可能機構）"]


def _load():
    spec = importlib.util.spec_from_file_location("render_combinators", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def test_task_graph_section_concatenated():
    assert mod.GOAL_SEEK_TASK_GRAPH_SECTION in mod.GOAL_SEEK_WIRING_SECTION


def test_fm_block_mentions_task_graph():
    assert "task-graph" in mod.GOAL_SEEK_FM_BLOCK


def _render(kind):
    r = subprocess.run([sys.executable, str(SCRIPT), "--kind", kind],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_run_kind_has_all_task_graph_tokens():
    out = _render("run")
    for tok in TASK_GRAPH_TOKENS:
        assert tok in out, f"missing task-graph token: {tok}"


def test_run_kind_regression_existing_tokens():
    out = _render("run")
    for tok in EXISTING_TOKENS:
        assert tok in out, f"regression: existing token dropped: {tok}"


def test_ref_kind_no_goal_seek():
    # ref は goal-seek 非対象 (回帰: task-graph 追加が ref を汚染しない)
    out = _render("ref")
    assert "ゴールシーク配線（task-graph 変種）" not in out


def test_build_flags_engine_enum_additive():
    schema = json.loads(BUILD_FLAGS.read_text(encoding="utf-8"))
    enum = schema["properties"]["with_goal_seek"]["properties"]["engine"]["enum"]
    assert "task-graph" in enum
    assert "inline" in enum and "run-goal-seek" in enum  # 既存維持 (enum は additive)
    # 量産既定を task-graph へ反転 (SKILL.md Step 10.6「engine 既定=task-graph」/ with-goal-seek.patch default 準拠)。
    assert schema["properties"]["with_goal_seek"]["properties"]["engine"]["default"] == "task-graph"


def test_loop_schema_depends_on_additive():
    schema = json.loads(LOOP_SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]["checklist"]["items"]["properties"]
    assert "depends_on" in props
    dep = props["depends_on"]
    assert dep["type"] == "array" and dep["default"] == []
    assert dep["items"]["pattern"] == "^C[0-9]+$"
    # 既存フィールド維持
    for k in ("id", "text", "status", "verify_by"):
        assert k in props


def test_loop_schema_engine_additive():
    schema = json.loads(LOOP_SCHEMA.read_text(encoding="utf-8"))
    eng = schema["properties"]["engine"]
    # enum は additive (3値維持)・既定は量産反転で task-graph (SKILL.md Step 10.6 準拠)。
    assert eng["default"] == "task-graph" and set(eng["enum"]) == {"inline", "run-goal-seek", "task-graph"}


# --- consumption verifier bash の「実挙動」検査 (presence でなく behavior・§11 対応) ---
import re as _re
import subprocess as _sub


def _extract_verifier_bash():
    """生成 SKILL.md から task-graph 検証 bash の PY heredoc 本体を抽出する。"""
    out = _render("run")
    m = _re.search(r"absence-as-violation.*?<<'PY'\n(.*?)\nPY\n", out, _re.DOTALL)
    assert m, "task-graph 検証 bash (absence-as-violation) が抽出できない"
    return m.group(1)


VERIFIER = _extract_verifier_bash()


def _run_verifier(tmp_path, prog, inter_lines):
    prog_path = tmp_path / "progress.json"
    prog_path.write_text(json.dumps(prog), encoding="utf-8")
    inter_path = tmp_path / "intermediate.jsonl"
    if inter_lines is not None:
        inter_path.write_text("\n".join(json.dumps(l) for l in inter_lines) + "\n", encoding="utf-8")
    r = _sub.run([sys.executable, "-", str(prog_path), str(inter_path)],
                 input=VERIFIER, capture_output=True, text=True)
    return r


def test_verifier_inline_non_applicable(tmp_path):
    r = _run_verifier(tmp_path, {"engine": "inline", "checklist": []}, None)
    assert r.returncode == 0 and "非適用" in r.stdout


def test_verifier_task_graph_absent_trace_violation(tmp_path):
    # engine:task-graph だが intermediate.jsonl 未生成 → 拘束違反 exit1
    prog = {"engine": "task-graph", "checklist": [{"id": "C1", "status": "done"}]}
    r = _run_verifier(tmp_path, prog, None)
    assert r.returncode != 0 and "拘束違反" in r.stderr


def test_verifier_task_graph_empty_trace_violation(tmp_path):
    # トレース行はあるが ready_set/selected_item を1行も持たない → 沈黙回避=違反
    prog = {"engine": "task-graph", "checklist": [{"id": "C1", "status": "done"}]}
    r = _run_verifier(tmp_path, prog, [{"iteration": 0, "note": "no trace keys"}])
    assert r.returncode != 0 and "1 行も無い" in r.stderr


def test_verifier_task_graph_valid_trace_ok(tmp_path):
    # 完全トレース: C1(dep なし)→C2(dep C1) を依存順に各周回 selected し、両者 done。
    # 消費完全性 (done 全 item が selected 済) と依存順 (C2 の dep C1 が先行周回で選択済) を満たす。
    prog = {"engine": "task-graph", "status": "completed",
            "checklist": [{"id": "C1", "status": "done"}, {"id": "C2", "status": "done", "depends_on": ["C1"]}]}
    inter = [{"iteration": 0, "ready_set": ["C1"], "selected_item": "C1"},
             {"iteration": 1, "ready_set": ["C2"], "selected_item": "C2"}]
    r = _run_verifier(tmp_path, prog, inter)
    assert r.returncode == 0 and "OK" in r.stdout


def test_verifier_empty_ready_with_selection_violation(tmp_path):
    # selected_item はあるが ready_set 空 → 空 ready 申告での検査回避を封鎖 (依存順消費違反)
    prog = {"engine": "task-graph", "checklist": [{"id": "C1", "status": "done"}]}
    inter = [{"iteration": 0, "ready_set": [], "selected_item": "C1"}]
    r = _run_verifier(tmp_path, prog, inter)
    assert r.returncode != 0 and "検査回避" in r.stderr


def test_verifier_dep_selected_before_its_dependency_violation(tmp_path):
    # C2(dep C1) を C1 より先に選択 → 選択列で依存順違反を実証 (自己申告 ready に依存しない)
    prog = {"engine": "task-graph",
            "checklist": [{"id": "C1", "status": "done"}, {"id": "C2", "status": "done", "depends_on": ["C1"]}]}
    inter = [{"iteration": 0, "ready_set": ["C2"], "selected_item": "C2"},
             {"iteration": 1, "ready_set": ["C1"], "selected_item": "C1"}]
    r = _run_verifier(tmp_path, prog, inter)
    assert r.returncode != 0 and "未選択のまま選択された" in r.stderr


def test_verifier_incomplete_consumption_violation(tmp_path):
    # C1/C2 とも done だが selected_item トレースは C1 のみ → 消費完全性違反 (選択証跡なき done を封鎖)
    prog = {"engine": "task-graph", "status": "completed",
            "checklist": [{"id": "C1", "status": "done"}, {"id": "C2", "status": "done", "depends_on": ["C1"]}]}
    inter = [{"iteration": 0, "ready_set": ["C1"], "selected_item": "C1"}]
    r = _run_verifier(tmp_path, prog, inter)
    assert r.returncode != 0 and "消費完全性" in r.stderr


def test_verifier_blocked_completion_violation(tmp_path):
    # completed 宣言だが blocked 残 → 完了 gate は pending だけでなく blocked も封鎖する
    prog = {"engine": "task-graph", "status": "completed",
            "checklist": [{"id": "C1", "status": "done"}, {"id": "C2", "status": "blocked"}]}
    inter = [{"iteration": 0, "ready_set": ["C1"], "selected_item": "C1"}]
    r = _run_verifier(tmp_path, prog, inter)
    assert r.returncode != 0 and "完了 gate 違反" in r.stderr and "blocked" in r.stderr


def test_verifier_initial_cycle_violation(tmp_path):
    # 初期 checklist の depends_on が循環 (C1<->C2) → 永久 unready=沈黙 stall を fail-closed 封鎖
    prog = {"engine": "task-graph",
            "checklist": [{"id": "C1", "status": "pending", "depends_on": ["C2"]},
                          {"id": "C2", "status": "pending", "depends_on": ["C1"]}]}
    inter = [{"iteration": 0, "ready_set": [], "selected_item": ""}]
    r = _run_verifier(tmp_path, prog, inter)
    assert r.returncode != 0 and "循環" in r.stderr


def test_verifier_wrong_selection_violation(tmp_path):
    # selected_item が ready 最小 id でない → 依存順消費違反
    prog = {"engine": "task-graph", "checklist": [{"id": "C1", "status": "done"}]}
    inter = [{"iteration": 0, "ready_set": ["C1", "C2"], "selected_item": "C2"}]
    r = _run_verifier(tmp_path, prog, inter)
    assert r.returncode != 0 and "依存順消費違反" in r.stderr


def test_verifier_dangling_depends_on_violation(tmp_path):
    # 初期 checklist に dangling depends_on → closure 違反 (§12)
    prog = {"engine": "task-graph", "checklist": [{"id": "C2", "status": "pending", "depends_on": ["CZZ"]}]}
    r = _run_verifier(tmp_path, prog, [{"iteration": 0, "ready_set": [], "selected_item": ""}])
    assert r.returncode != 0 and "dangling" in r.stderr


def test_verifier_self_reflect_gate_violation(tmp_path):
    # completed 宣言だが pending 残 → self-reflect 完了 gate 違反
    prog = {"engine": "task-graph", "status": "completed",
            "checklist": [{"id": "C1", "status": "done"}, {"id": "C2", "status": "pending"}]}
    inter = [{"iteration": 0, "ready_set": ["C1"], "selected_item": "C1"}]
    r = _run_verifier(tmp_path, prog, inter)
    assert r.returncode != 0 and "完了 gate 違反" in r.stderr

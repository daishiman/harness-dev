"""lint-sibling-coupling.py の advisory 検出契約 (未宣言密結合の安全網)。

同一 phase 兄弟 + データ流シグナル (B が A の出力ファイル名を参照) を候補化し、
couples_with 宣言 / depends_on 順序 / シグナル不在の各除外を固定する。
"""
import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


LSC = _load("lint-sibling-coupling")


def _plan(tmp_path: Path, components, phase_entities=("C05", "C06")):
    ents = ", ".join(phase_entities)
    (tmp_path / "phase-05-implementation.md").write_text(
        f"---\nid: P05\nphase_name: impl\nentities_covered: [{ents}]\n---\n# p\n\n## 完了チェックリスト\n- [ ] 実装\n",
        encoding="utf-8",
    )
    (tmp_path / "component-inventory.json").write_text(
        json.dumps({"components": components}, ensure_ascii=False), encoding="utf-8"
    )


def _c05(**extra):
    return {"id": "C05", "component_kind": "script", "script_name": "row-emit.py",
            "build_target": "plugins/x/scripts/row-emit.py", "depends_on": [],
            "purpose": "行を出力する", "inputs": "argv(--src FILE)", "outputs": "stdout(rows)", **extra}


def _c06(**extra):
    return {"id": "C06", "component_kind": "script", "script_name": "row-read.py",
            "build_target": "plugins/x/scripts/row-read.py", "depends_on": [],
            "purpose": "row-emit.py の出力行を読んで整形する", "inputs": "stdin(rows from row-emit.py)",
            "outputs": "stdout(formatted)", **extra}


def test_candidate_detected_on_dataflow(tmp_path):
    # C06 の inputs/purpose が C05 の出力 row-emit.py を参照 → 未宣言の密結合候補。
    _plan(tmp_path, [_c05(), _c06()])
    cands = LSC.find_candidates(tmp_path)
    assert len(cands) == 1
    assert cands[0]["a"] == "C05" and cands[0]["b"] == "C06"
    assert "row-emit.py" in cands[0]["signal"]


def test_no_candidate_when_couples_declared(tmp_path):
    _plan(tmp_path, [_c05(couples_with=["C06"]), _c06()])
    assert LSC.find_candidates(tmp_path) == []


def test_no_candidate_when_depends_on_ordered(tmp_path):
    _plan(tmp_path, [_c05(), _c06(depends_on=["C05"])])
    assert LSC.find_candidates(tmp_path) == []


def test_no_candidate_without_dataflow_signal(tmp_path):
    # C06 が C05 の出力を参照しない (無関係な兄弟) → 候補化しない (盲目に全兄弟を挙げない)。
    c06 = _c06(purpose="独立した整形", inputs="argv(--x FILE)")
    _plan(tmp_path, [_c05(), c06])
    assert LSC.find_candidates(tmp_path) == []


def test_strict_exit1_when_candidates(tmp_path, capsys):
    _plan(tmp_path, [_c05(), _c06()])
    assert LSC.main([str(tmp_path), "--strict"]) == 1


def test_advisory_exit0_by_default(tmp_path, capsys):
    _plan(tmp_path, [_c05(), _c06()])
    assert LSC.main([str(tmp_path)]) == 0


def test_exit0_no_candidates(tmp_path):
    _plan(tmp_path, [_c05(couples_with=["C06"]), _c06()])
    assert LSC.main([str(tmp_path), "--strict"]) == 0


def test_candidate_detected_on_subagent_pair(tmp_path):
    # 実 C05/C06 型 (sub-agent 兄弟)。script 専用フィールドを持たず description で相手を参照する
    # ケースでも検出する (script 専用フィールドしか読まない不感バグの回帰)。
    a = {"id": "C05", "component_kind": "sub-agent", "name": "row-reconcile-auditor",
         "build_target": "plugins/x/agents/row-reconcile-auditor.md", "depends_on": [],
         "description": "行を照合して検査する"}
    b = {"id": "C06", "component_kind": "sub-agent", "name": "row-backfill-writer",
         "build_target": "plugins/x/agents/row-backfill-writer.md", "depends_on": [],
         "description": "row-reconcile-auditor の照合結果を読んで backfill する"}
    _plan(tmp_path, [a, b])
    cands = LSC.find_candidates(tmp_path)
    assert len(cands) == 1
    assert cands[0]["a"] == "C05" and cands[0]["b"] == "C06"


def test_candidate_detected_on_skill_pair(tmp_path):
    # skill 兄弟 (goal/output_contract フィールド + 拡張子なし build_target basename)。
    a = {"id": "C05", "component_kind": "skill", "skill_kind": "run", "name": "run-row-emit",
         "build_target": "plugins/x/skills/run-row-emit/", "depends_on": [],
         "goal": "行を出力する", "output_contract": {"produces": "rows.json"}}
    b = {"id": "C06", "component_kind": "skill", "skill_kind": "run", "name": "run-row-read",
         "build_target": "plugins/x/skills/run-row-read/", "depends_on": [],
         "goal": "run-row-emit の出力を読んで整形する", "output_contract": {"reads": "rows.json"}}
    _plan(tmp_path, [a, b])
    cands = LSC.find_candidates(tmp_path)
    assert len(cands) == 1


def test_usage_error(tmp_path):
    assert LSC.main([]) == 2
    assert LSC.main([str(tmp_path / "missing")]) == 2

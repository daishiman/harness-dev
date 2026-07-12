from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parents[1]
SAMPLE_PLAN = PLUGIN_ROOT / "skills" / "run-plugin-dev-plan" / "examples" / "sample-plan"


def _load_evaluator():
    path = SKILL_DIR / "scripts" / "evaluate-plan.py"
    spec = importlib.util.spec_from_file_location("evaluate_plan", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_schema_and_rubric_exist_and_cover_four_conditions():
    schema = json.loads((SKILL_DIR / "schemas" / "plan-findings.schema.json").read_text(encoding="utf-8"))
    rubric = json.loads((SKILL_DIR / "references" / "plan-rubric.json").read_text(encoding="utf-8"))

    assert set(schema["properties"]["conditions"]["required"]) == {"C1", "C2", "C3", "C4"}
    assert set(rubric["conditions"]) == {"C1", "C2", "C3", "C4"}
    # ゲート数は evaluate-plan.py._gate_defs から導出し数値ハードコードの drift を避ける
    # (id/name/conditions の完全一致は test_gate_parity.py が別途縛る)
    evaluator = _load_evaluator()
    expected_gates = len(evaluator._gate_defs(PLUGIN_ROOT / "skills" / "run-plugin-dev-plan", Path("/tmp/plan")))
    assert len(rubric["deterministic_gates"]) == expected_gates


def test_golden_plan_evaluates_pass(tmp_path):
    evaluator = _load_evaluator()
    output = tmp_path / "plan-findings.json"

    code, data = evaluator.evaluate(SAMPLE_PLAN.resolve(), output)

    assert code == 0
    assert output.is_file()
    assert data["verdict"] == "PASS"
    assert {k: v["status"] for k, v in data["conditions"].items()} == {
        "C1": "PASS",
        "C2": "PASS",
        "C3": "PASS",
        "C4": "PASS",
    }
    assert all(g["exit_code"] == 0 for g in data["gate_results"])
    assert data["findings"][0]["severity"] == "info"


def test_missing_plugin_level_surface_fails_c2(tmp_path):
    evaluator = _load_evaluator()
    plan = tmp_path / "sample-plan"
    shutil.copytree(SAMPLE_PLAN, plan)
    inventory_path = plan / "component-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["plugin_level_surfaces"].pop("harness_eval")
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    code, data = evaluator.evaluate(plan.resolve(), tmp_path / "findings.json")

    assert code == 1
    assert data["verdict"] == "FAIL"
    assert data["conditions"]["C2"]["status"] == "FAIL"
    assert any("harness_eval" in f["observation"] for f in data["findings"])

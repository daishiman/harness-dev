from __future__ import annotations

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


cpl = _load("check-plan-ledger")
specfm = _load("specfm")


# ─────────── 受入例 fixtures (P04 C13 節が正本) ───────────
def _valid_ledger() -> dict:
    return {
        "schema_version": "1.0",
        "entries": [
            {
                "cycle_id": "20260601-task-graph",
                "status": "finished",
                "plan_dir": "plugin-plans/plugin-dev-planner/20260601-task-graph",
                "summary": "初回導入",
            },
            {
                "cycle_id": "20260705-cycle-ledger",
                "status": "active",
                "plan_dir": "plugin-plans/plugin-dev-planner/20260705-cycle-ledger",
                "summary": "台帳導入",
            },
        ],
    }


# ─────────── validate_ledger 単体 ───────────
def test_valid_ledger_no_errors():
    assert cpl.validate_ledger(_valid_ledger()) == []


def test_two_active_is_violation():
    data = _valid_ledger()
    data["entries"][0]["status"] = "active"  # 両 entry を active に
    errs = cpl.validate_ledger(data)
    assert errs
    assert any("同時 active 重複" in e for e in errs)


def test_bad_cycle_id_is_violation():
    data = _valid_ledger()
    data["entries"][0]["cycle_id"] = "bad"
    errs = cpl.validate_ledger(data)
    assert any("cycle_id" in e for e in errs)


def test_status_out_of_domain_is_violation():
    data = _valid_ledger()
    data["entries"][1]["status"] = "wip"
    errs = cpl.validate_ledger(data)
    assert any("status" in e for e in errs)


def test_empty_summary_is_violation():
    data = _valid_ledger()
    data["entries"][0]["summary"] = ""
    errs = cpl.validate_ledger(data)
    assert any("summary" in e for e in errs)


def test_empty_plan_dir_is_violation():
    data = _valid_ledger()
    data["entries"][1]["plan_dir"] = ""
    errs = cpl.validate_ledger(data)
    assert any("plan_dir" in e for e in errs)


def test_non_dict_root():
    assert cpl.validate_ledger([]) == ["plan-ledger root が object でない"]


def test_entries_not_list():
    errs = cpl.validate_ledger({"schema_version": "1.0", "entries": {}})
    assert any("entries" in e for e in errs)


def test_entry_not_object():
    data = {"schema_version": "1.0", "entries": ["nope"]}
    errs = cpl.validate_ledger(data)
    assert any("object でない" in e for e in errs)


def test_missing_cycle_id_reports_empty():
    data = {"schema_version": "1.0", "entries": [
        {"status": "active", "plan_dir": "p", "summary": "s"}
    ]}
    errs = cpl.validate_ledger(data)
    assert any("cycle_id が空" in e for e in errs)


def test_empty_entries_ok():
    assert cpl.validate_ledger({"schema_version": "1.0", "entries": []}) == []


def test_single_active_ok():
    data = _valid_ledger()
    # 1 件だけ active (既定) → OK
    assert cpl.validate_ledger(data) == []


# ─────────── predecessor_cycle_id lineage (C19) ───────────
def test_valid_predecessor_lineage_ok():
    data = _valid_ledger()
    # active cycle が finished cycle を先行として結ぶ (満たす例)
    data["entries"][1]["predecessor_cycle_id"] = "20260601-task-graph"
    assert cpl.validate_ledger(data) == []


def test_active_predecessor_is_violation():
    data = _valid_ledger()
    data["entries"][0]["status"] = "superseded"
    data["entries"].append({
        "cycle_id": "20260706-next",
        "status": "finished",
        "plan_dir": "plugin-plans/plugin-dev-planner/20260706-next",
        "summary": "next",
        "predecessor_cycle_id": "20260705-cycle-ledger",
    })
    errs = cpl.validate_ledger(data)
    assert any("active cycle" in e for e in errs)


def test_dangling_predecessor_is_violation():
    data = _valid_ledger()
    data["entries"][1]["predecessor_cycle_id"] = "20250101-nonexistent"
    errs = cpl.validate_ledger(data)
    assert any("dangling lineage" in e for e in errs)


def test_self_referential_predecessor_is_violation():
    data = _valid_ledger()
    data["entries"][1]["predecessor_cycle_id"] = data["entries"][1]["cycle_id"]
    errs = cpl.validate_ledger(data)
    assert any("自己参照" in e for e in errs)


def test_predecessor_cycle_loop_is_violation():
    data = _valid_ledger()
    # A→B かつ B→A の閉路
    data["entries"][0]["predecessor_cycle_id"] = data["entries"][1]["cycle_id"]
    data["entries"][1]["predecessor_cycle_id"] = data["entries"][0]["cycle_id"]
    errs = cpl.validate_ledger(data)
    assert any("閉路" in e for e in errs)


def test_null_predecessor_ok():
    data = _valid_ledger()
    data["entries"][1]["predecessor_cycle_id"] = None
    assert cpl.validate_ledger(data) == []


# ─────────── main (CLI 経路 + exit code) ───────────
def _write(tmp_path, data) -> Path:
    p = tmp_path / "plan-ledger.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_main_exit0_on_valid(tmp_path, capsys):
    p = _write(tmp_path, _valid_ledger())
    assert cpl.main([str(p)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_main_exit1_on_two_active(tmp_path, capsys):
    data = _valid_ledger()
    data["entries"][0]["status"] = "active"
    p = _write(tmp_path, data)
    assert cpl.main([str(p)]) == 1
    assert "同時 active 重複" in capsys.readouterr().out


def test_main_exit2_on_missing_file(tmp_path):
    assert cpl.main([str(tmp_path / "nope.json")]) == 2


def test_main_exit2_on_bad_json(tmp_path):
    p = tmp_path / "plan-ledger.json"
    p.write_text("{ not json", encoding="utf-8")
    assert cpl.main([str(p)]) == 2


# ─────────── plan_output_dir 後方互換 (C13 契約) ───────────
def test_plan_output_dir_flat_backcompat():
    assert specfm.plan_output_dir("plugin-dev-planner") == "plugin-plans/plugin-dev-planner"


def test_plan_output_dir_with_cycle_id():
    assert (
        specfm.plan_output_dir("plugin-dev-planner", cycle_id="20260705-x")
        == "plugin-plans/plugin-dev-planner/20260705-x"
    )

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mpl = _load("migrate-plan-layout")
cpl = _load("check-plan-ledger")


def _flat_plan(tmp_path, slug="myslug", files=("phase-01.md", "index.md")) -> Path:
    old = tmp_path / "plugin-plans" / slug
    old.mkdir(parents=True)
    for name in files:
        (old / name).write_text(f"# {name}\n", encoding="utf-8")
    return old


# ─────────── 受入例: flat → cycle スコープ移行 ───────────
def test_migrate_moves_files_and_writes_ledger(tmp_path):
    old = _flat_plan(tmp_path)
    result = mpl.migrate(old, "myslug", "20260705-abc")

    target = old / "20260705-abc"
    # ファイルが cycle スコープ配下へ移動
    assert (target / "phase-01.md").is_file()
    assert (target / "index.md").is_file()
    assert not (old / "phase-01.md").exists()
    assert set(result["moved"]) == {"phase-01.md", "index.md"}
    assert result["cycle_id"] == "20260705-abc"

    # plan-ledger.json は slug 直下 (cycle スコープ外) に残る
    ledger_path = old / "plan-ledger.json"
    assert Path(result["ledger_path"]) == ledger_path
    assert ledger_path.is_file()
    assert not (target / "plan-ledger.json").exists()

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = ledger["entries"][-1]
    assert entry["cycle_id"] == "20260705-abc"
    assert entry["status"] == "active"
    assert entry["plan_dir"] == "plugin-plans/myslug/20260705-abc"
    assert entry["summary"]
    # validate_ledger が exit0 相当 (違反なし)
    assert cpl.validate_ledger(ledger) == []


def test_migrate_creates_new_ledger_when_absent(tmp_path):
    old = _flat_plan(tmp_path)
    assert not (old / "plan-ledger.json").exists()
    mpl.migrate(old, "myslug", "20260705-abc")
    assert (old / "plan-ledger.json").is_file()


# ─────────── 同時 active 重複拒否 ───────────
def test_migrate_rejects_second_active(tmp_path):
    old = _flat_plan(tmp_path)
    mpl.migrate(old, "myslug", "20260705-abc")  # 1 件目 active
    # 別 cycle を再度 active で足そうとすると同時 active 重複で ValueError
    (old / "phase-02.md").write_text("# next\n", encoding="utf-8")
    with pytest.raises(ValueError) as ei:
        mpl.migrate(old, "myslug", "20260706-def", status="active")
    assert "active" in str(ei.value)


def test_migrate_second_cycle_ok_when_prior_finished(tmp_path):
    old = _flat_plan(tmp_path)
    mpl.migrate(old, "myslug", "20260705-abc", status="finished")  # 1 件目 finished
    (old / "phase-02.md").write_text("# next\n", encoding="utf-8")
    # 既存が finished なら新規 active は同時 active 重複にならない
    result = mpl.migrate(old, "myslug", "20260706-def", status="active")
    assert result["cycle_id"] == "20260706-def"
    ledger = json.loads((old / "plan-ledger.json").read_text(encoding="utf-8"))
    assert cpl.validate_ledger(ledger) == []


# ─────────── cycle_id / status バリデーション ───────────
def test_migrate_rejects_bad_cycle_id(tmp_path):
    old = _flat_plan(tmp_path)
    with pytest.raises(ValueError) as ei:
        mpl.migrate(old, "myslug", "bad")
    assert "cycle_id" in str(ei.value)


def test_migrate_rejects_bad_status(tmp_path):
    old = _flat_plan(tmp_path)
    with pytest.raises(ValueError) as ei:
        mpl.migrate(old, "myslug", "20260705-abc", status="wip")
    assert "status" in str(ei.value)


def test_migrate_custom_summary(tmp_path):
    old = _flat_plan(tmp_path)
    mpl.migrate(old, "myslug", "20260705-abc", summary="独自サマリ")
    ledger = json.loads((old / "plan-ledger.json").read_text(encoding="utf-8"))
    assert ledger["entries"][-1]["summary"] == "独自サマリ"


# ─────────── main (CLI 経路 + exit code) ───────────
def test_main_exit0_and_json_stdout(tmp_path, capsys):
    old = _flat_plan(tmp_path)
    rc = mpl.main(["--old-plan-dir", str(old), "--slug", "myslug", "--cycle-id", "20260705-abc"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cycle_id"] == "20260705-abc"
    assert (old / "20260705-abc" / "phase-01.md").is_file()


def test_main_exit1_on_bad_cycle_id(tmp_path):
    old = _flat_plan(tmp_path)
    rc = mpl.main(["--old-plan-dir", str(old), "--slug", "myslug", "--cycle-id", "bad"])
    assert rc == 1


def test_main_exit1_on_duplicate_active(tmp_path):
    old = _flat_plan(tmp_path)
    mpl.main(["--old-plan-dir", str(old), "--slug", "myslug", "--cycle-id", "20260705-abc"])
    (old / "phase-02.md").write_text("# next\n", encoding="utf-8")
    rc = mpl.main(["--old-plan-dir", str(old), "--slug", "myslug", "--cycle-id", "20260706-def"])
    assert rc == 1


def test_main_exit2_on_missing_required_arg(tmp_path):
    with pytest.raises(SystemExit) as ei:
        mpl.main(["--slug", "myslug"])
    assert ei.value.code == 2

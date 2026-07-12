"""genuine 機能テスト: scripts/contract-intake-enum-ssot.py

純関数 (fail/ok/load_schema/c1-c4/main) を実 schema + 合成 schema で呼び実出力を assert。
FAIL 経路 (options 欠落 / projection 不一致 / 二重定義 / 注記欠落) を合成入力で再現。
main() は (a) 直呼びで報告 dict を検証、(b) subprocess で --json / 実 repo PASS を検証。
network/Notion は一切叩かない純 contract test (副作用なし)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "contract-intake-enum-ssot.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("contract_intake_enum_ssot_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# ---------- fail / ok ヘルパ ----------
def test_fail_and_ok_append_expected_records():
    results = []
    MOD.ok(results, "C1", "good")
    MOD.fail(results, "C2", "bad")
    assert results[0] == {"gate": "C1", "status": "PASS", "detail": "good"}
    assert results[1] == {"gate": "C2", "status": "FAIL", "detail": "bad"}


# ---------- load_schema (実ファイル) ----------
def test_load_schema_reads_real_intake_schema():
    sc = MOD.load_schema()
    assert isinstance(sc, dict)
    props = sc.get("properties", {})
    for key in ("ステータス", "パターン", "ワークフロー"):
        assert key in props, f"{key} が実 schema に無い"


# ---------- c1_canonical_load ----------
def test_c1_passes_on_real_schema():
    results = []
    enums = MOD.c1_canonical_load(MOD.load_schema(), results)
    assert enums is not None
    assert set(enums.keys()) == {"ステータス", "パターン", "ワークフロー"}
    assert results[-1]["status"] == "PASS"
    assert all(len(v) > 0 for v in enums.values())


def test_c1_fails_when_options_missing():
    results = []
    bad = {"properties": {"ステータス": {"options": ["x"]}, "パターン": {}, "ワークフロー": {"options": ["y"]}}}
    enums = MOD.c1_canonical_load(bad, results)
    assert enums is None
    assert results[-1]["status"] == "FAIL"
    assert "パターン" in results[-1]["detail"]


# ---------- c2_projection_parity ----------
def test_c2_passes_on_real_render():
    results = []
    MOD.c2_projection_parity(MOD.load_schema(), results)
    assert results[-1]["status"] == "PASS"
    assert "網羅" in results[-1]["detail"]


def test_c2_fails_on_render_absent(monkeypatch, tmp_path):
    results = []
    monkeypatch.setattr(MOD, "RENDER", tmp_path / "no-render.py")
    MOD.c2_projection_parity(MOD.load_schema(), results)
    assert results[-1]["status"] == "FAIL"
    assert "不在" in results[-1]["detail"]


def test_c2_fails_on_key_mismatch(monkeypatch, tmp_path):
    # projection できないキーを schema に追加 => missing 検出で FAIL。
    sc = MOD.load_schema()
    sc["properties"]["架空プロパティ"] = {"type": "rich_text"}
    results = []
    MOD.c2_projection_parity(sc, results)
    assert results[-1]["status"] == "FAIL"
    assert "架空プロパティ" in results[-1]["detail"]


def test_c2_fails_when_return_dict_unparseable(monkeypatch, tmp_path):
    fake = tmp_path / "render.py"
    fake.write_text("def project_db_properties(ctx):\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "RENDER", fake)
    results = []
    MOD.c2_projection_parity(MOD.load_schema(), results)
    assert results[-1]["status"] == "FAIL"
    assert "抽出できず" in results[-1]["detail"]


# ---------- c3_no_double_definition ----------
def test_c3_passes_on_real_handoff():
    results = []
    MOD.c3_no_double_definition(results)
    assert results[-1]["status"] == "PASS"


def test_c3_fails_when_guarded_ref_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "GUARDED_REFS", [tmp_path / "missing.md"])
    results = []
    MOD.c3_no_double_definition(results)
    assert results[-1]["status"] == "FAIL"
    assert "被ガード文書不在" in results[-1]["detail"]


def test_c3_fails_when_canonical_ref_missing(monkeypatch, tmp_path):
    ref = tmp_path / "handoff.md"
    ref.write_text("正本参照記述が無い本文", encoding="utf-8")
    monkeypatch.setattr(MOD, "GUARDED_REFS", [ref])
    results = []
    MOD.c3_no_double_definition(results)
    assert results[-1]["status"] == "FAIL"
    assert "正本参照が欠落" in results[-1]["detail"]


def test_c3_detects_double_definition_reinjection(monkeypatch, tmp_path):
    ref = tmp_path / "handoff.md"
    # 正本参照は在るが、旧 enum ラベルの直書きが再混入 => 二重定義検出。
    ref.write_text(
        "参照: notion-db-schema.json#/properties/ワークフロー\n"
        "A = 対話生成 / B = 分析レポート\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MOD, "GUARDED_REFS", [ref])
    results = []
    MOD.c3_no_double_definition(results)
    assert results[-1]["status"] == "FAIL"
    assert "再混入" in results[-1]["detail"]


def test_c3_passes_with_canonical_reference_only(monkeypatch, tmp_path):
    ref = tmp_path / "handoff.md"
    ref.write_text(
        "ワークフロー値は notion-db-schema.json#/properties/ワークフロー を正本とする\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MOD, "GUARDED_REFS", [ref])
    results = []
    MOD.c3_no_double_definition(results)
    assert results[-1]["status"] == "PASS"


# ---------- c4_axis_separation_notes ----------
def test_c4_passes_on_real_repo():
    results = []
    MOD.c4_axis_separation_notes(MOD.load_schema(), results)
    assert results[-1]["status"] == "PASS"


def test_c4_fails_when_schema_note_missing(monkeypatch, tmp_path):
    sc = MOD.load_schema()
    sc["properties"]["パターン"]["description"] = "注記を消した説明"
    # advisor/handoff も tmp の空ファイルへ向けて全注記欠落を強制。
    empty = tmp_path / "empty.md"
    empty.write_text("注記なし", encoding="utf-8")
    monkeypatch.setattr(MOD, "ADVISOR", empty)
    monkeypatch.setattr(MOD, "HANDOFF", empty)
    results = []
    MOD.c4_axis_separation_notes(sc, results)
    assert results[-1]["status"] == "FAIL"
    assert "軸独立性注記が欠落" in results[-1]["detail"]
    assert "schema:パターン" in results[-1]["detail"]


# ---------- main() 直呼び ----------
def test_main_returns_zero_and_reports_all_pass_on_real_repo(capsys):
    rc = MOD.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ALL PASS" in out
    for gate in ("C1", "C2", "C3", "C4"):
        assert f"[PASS] {gate}" in out


def test_main_json_mode_emits_valid_report(capsys):
    rc = MOD.main(["--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["contract"] == "intake-enum-ssot"
    assert report["exit"] == 0
    assert report["gate_results"] == {"C1": "PASS", "C2": "PASS", "C3": "PASS", "C4": "PASS"}


def test_main_returns_one_when_c1_fails(monkeypatch, tmp_path, capsys):
    # 不正 schema をファイルに置き SCHEMA を差し替え => C1 FAIL で exit 1、C2 は短絡 skip。
    bad = tmp_path / "schema.json"
    bad.write_text(json.dumps({"properties": {"ステータス": {}, "パターン": {}, "ワークフロー": {}}}), "utf-8")
    monkeypatch.setattr(MOD, "SCHEMA", bad)
    rc = MOD.main([])
    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL] C1" in out
    assert "FAIL" in out
    # C1 失敗で c2 は実行されない (enums is None)。
    assert "[PASS] C2" not in out and "[FAIL] C2" not in out


# ---------- main() via subprocess (実 repo + CLI 契約) ----------
def test_subprocess_default_passes_on_real_repo():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0
    assert "ALL PASS" in r.stdout


def test_subprocess_json_flag_outputs_parseable_json():
    r = subprocess.run([sys.executable, str(SCRIPT), "--json"], capture_output=True, text=True)
    assert r.returncode == 0
    report = json.loads(r.stdout)
    assert report["exit"] == 0

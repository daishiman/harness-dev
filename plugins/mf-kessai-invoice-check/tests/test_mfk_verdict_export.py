"""C05 mfk_verdict_export のユニット/seam テスト。

構造的主因 C2 の根治=「reconcile() の全 rows(GAP/SUPPRESS 含む)+orphans を carrier 込みで
curr/prev-verdicts へ無損失に直列化し curr=None を出さない」を検証する。
"""
import json
import subprocess
import sys

import mfk_verdict_export as V
import mfk_reconcile as R
from mfk_period_report import compare_periods, STATE_CONTINUED


# ---------------------------------------------------------------------------
# 最小 MF raw / sheet fixture
# ---------------------------------------------------------------------------
def _mf_raw(customers):
    return {"customers": customers, "canceled_count": 0}


def _active_customer(name, desc, amount):
    """build_mf_index が active services へ振り分ける最小 customer(status 無し=passed 相当)。"""
    return {"name": name, "lines": [
        {"desc": desc, "amount": amount, "unit_price": amount, "qty": 1,
         "billing_id": "b1", "txn_date": None, "status": None, "canceled_at": None},
    ]}


def _sheet_row(torihiki, product, amount=50000, kaishi="2601"):
    # 確認内容に『月額N円』を書き _recurring_amount が現行単価を拾える形にする
    # (これがないと REVIEW_NO_AMOUNT に落ち find_mf_match を経ず carrier が付かない)。
    return {"取引先": torihiki, "商品": product,
            "確認内容": f"月額 {amount:,}円", "契約開始日": kaishi, "契約終了月": ""}


# ---------------------------------------------------------------------------
# serialize_verdicts — rows 全件 + orphans + carrier
# ---------------------------------------------------------------------------
def test_serialize_includes_all_rows_and_carrier():
    recon = {
        "target_ym": "2606",
        "rows": [
            {"取引先": "A社", "商品": "月額サービス", "verdict": "MATCH_MONTHLY",
             "actual_amount": 50000, "reliable_issued": True,
             "supply_state": R.mfk_actuals.SUPPLY_ACTIVE, "canceled_at": None},
            {"取引先": "B社", "商品": "対象外役務", "verdict": "SUPPRESS_OFFMONTH",
             "actual_amount": None, "reliable_issued": False,
             "supply_state": R.mfk_actuals.SUPPLY_NONE, "canceled_at": None},
        ],
        "orphans": [
            {"verdict": "ORPHAN", "MF顧客ID": "c9", "cust": "C社", "desc": "未登録役務",
             "amount": 30000, "services": [], "contract_id": None},
        ],
        "summary": {"MATCH_MONTHLY": 1, "SUPPRESS_OFFMONTH": 1, "ORPHAN": 1},
    }
    doc = V.serialize_verdicts(recon)
    # SUPPRESS 行も落とさない(全 rec persist)。
    assert len(doc["rows"]) == 2
    verdicts = {r["verdict"] for r in doc["rows"]}
    assert verdicts == {"MATCH_MONTHLY", "SUPPRESS_OFFMONTH"}
    # orphan は period_report 読み取り可能な形へ写像し carrier を持つ。
    assert len(doc["orphans"]) == 1
    orow = doc["orphans"][0]
    assert orow["customer"] == "C社" and orow["product"] == "未登録役務"
    assert orow["reliable_issued"] is True
    assert orow["actual_amount"] == 30000
    assert orow["supply_state"] == R.mfk_actuals.SUPPLY_ACTIVE


def test_serialize_preserves_carrier_on_all_rows():
    recon = {"target_ym": "2606", "rows": [
        {"取引先": "A", "商品": "x", "verdict": "GAP", "actual_amount": None,
         "reliable_issued": False, "supply_state": R.mfk_actuals.SUPPLY_NONE,
         "canceled_at": None}], "orphans": [], "summary": {}}
    doc = V.serialize_verdicts(recon)
    assert V.validate_carrier(doc) == []


# ---------------------------------------------------------------------------
# validate_carrier — fail-closed (carrier/row 欠落検知)
# ---------------------------------------------------------------------------
def test_validate_detects_missing_carrier():
    doc = {"rows": [{"取引先": "A", "商品": "x", "verdict": "MATCH_MONTHLY"}]}  # carrier 欠落
    v = V.validate_carrier(doc)
    assert any("actual_amount" in m for m in v)
    assert any("reliable_issued" in m for m in v)


def test_validate_detects_missing_verdict_and_customer():
    doc = {"rows": [{"actual_amount": None, "reliable_issued": False,
                     "supply_state": "none", "canceled_at": None}]}
    v = V.validate_carrier(doc)
    assert any("verdict" in m for m in v)
    assert any("customer" in m for m in v)


# ---------------------------------------------------------------------------
# export_curr_prev — reconcile を curr/prev で回し全行直列化 (curr=None なし)
# ---------------------------------------------------------------------------
def test_export_produces_curr_present_for_every_contract():
    """発行済み社の当月行が必ず出る(curr=None を出さない=C2 根治の核)。"""
    mf_curr = _mf_raw({"c1": _active_customer("A社", "月額サービス", 50000)})
    mf_prev = _mf_raw({"c1": _active_customer("A社", "月額サービス", 50000)})
    sheet = [_sheet_row("A社", "月額サービス")]
    curr_doc, prev_doc = V.export_curr_prev(sheet, mf_curr, mf_prev, "2606")
    assert curr_doc["target_month"] == "2606"
    assert prev_doc["target_month"] == "2605"
    # A社の契約行が当月に存在する(curr=None でない)。
    a_rows = [r for r in curr_doc["rows"]
              if (r.get("customer") or r.get("取引先")) and "A社" in (r.get("取引先") or r.get("customer") or "")]
    assert a_rows, "A社の当月行が curr-verdicts に存在すること (curr=None 根治)"
    # carrier 検証が通る。
    assert V.validate_carrier(curr_doc) == []
    assert V.validate_carrier(prev_doc) == []


def test_export_prev_ym_invalid_raises():
    import pytest
    with pytest.raises(ValueError):
        V.export_curr_prev([], _mf_raw({}), _mf_raw({}), "bad")


# ---------------------------------------------------------------------------
# seam: C05 出力 → period_report.compare_periods が消費できる (carrier 貫通)
# ---------------------------------------------------------------------------
def test_seam_c05_output_flows_into_compare_periods():
    """C05 が直列化した curr/prev rows を compare_periods が突合でき、両月発行済みは継続発行。"""
    mf = _mf_raw({"c1": _active_customer("A社", "月額サービス", 50000)})
    sheet = [_sheet_row("A社", "月額サービス")]
    curr_doc, prev_doc = V.export_curr_prev(sheet, mf, mf, "2606")
    pairing = compare_periods(prev_doc["rows"], curr_doc["rows"])
    # 単一契約×単一MF顧客ゆえ突合ペアは 1 件。key は normalize 済みなので生表示名で照合せず、
    # ペア成立と状態(両月 active 発行=継続発行・STATE_NEW にならない)で検証する。
    assert len(pairing) == 1, pairing
    assert pairing[0]["state"] == STATE_CONTINUED
    assert pairing[0]["curr"] is not None and pairing[0]["prev"] is not None


# ---------------------------------------------------------------------------
# CLI — 入出力 round-trip + fail-closed exit code
# ---------------------------------------------------------------------------
def test_cli_roundtrip(tmp_path):
    mf = _mf_raw({"c1": _active_customer("A社", "月額サービス", 50000)})
    sheet = [_sheet_row("A社", "月額サービス")]
    sheet_p = tmp_path / "sheet.json"; sheet_p.write_text(json.dumps(sheet), encoding="utf-8")
    curr_p = tmp_path / "mfc.json"; curr_p.write_text(json.dumps(mf), encoding="utf-8")
    prev_p = tmp_path / "mfp.json"; prev_p.write_text(json.dumps(mf), encoding="utf-8")
    out_c = tmp_path / "curr.json"; out_p = tmp_path / "prev.json"
    r = subprocess.run(
        [sys.executable, V.__file__, "--sheet", str(sheet_p), "--mf-curr", str(curr_p),
         "--mf-prev", str(prev_p), "--target", "2606",
         "--out-curr", str(out_c), "--out-prev", str(out_p)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    doc = json.loads(out_c.read_text(encoding="utf-8"))
    assert doc["target_month"] == "2606"
    assert doc["rows"], "rows が直列化されていること"


def _write(tmp_path, name, payload):
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return str(p)


def test_main_in_process_happy_path(tmp_path):
    """main() を in-process で回し exit 0・出力 JSON が書かれる (fail-closed 分岐のカバレッジ計上)。"""
    mf = _mf_raw({"c1": _active_customer("A社", "月額サービス", 50000)})
    argv = [
        "--sheet", _write(tmp_path, "sheet.json", [_sheet_row("A社", "月額サービス")]),
        "--mf-curr", _write(tmp_path, "mfc.json", mf),
        "--mf-prev", _write(tmp_path, "mfp.json", mf),
        "--target", "2606",
        "--out-curr", str(tmp_path / "c.json"), "--out-prev", str(tmp_path / "p.json"),
    ]
    assert V.main(argv) == 0
    doc = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    assert doc["rows"]


def test_main_load_error_exits_2(tmp_path):
    """入力ファイル不在は exit 2 (fail-closed・確定しない)。"""
    argv = [
        "--sheet", str(tmp_path / "missing.json"),
        "--mf-curr", str(tmp_path / "missing.json"),
        "--mf-prev", str(tmp_path / "missing.json"),
        "--target", "2606",
        "--out-curr", str(tmp_path / "c.json"), "--out-prev", str(tmp_path / "p.json"),
    ]
    assert V.main(argv) == 2


def test_main_bad_target_exits_2_in_process(tmp_path):
    mf = _mf_raw({})
    argv = [
        "--sheet", _write(tmp_path, "sheet.json", []),
        "--mf-curr", _write(tmp_path, "mfc.json", mf),
        "--mf-prev", _write(tmp_path, "mfp.json", mf),
        "--target", "badval",
        "--out-curr", str(tmp_path / "c.json"), "--out-prev", str(tmp_path / "p.json"),
    ]
    assert V.main(argv) == 2


def test_main_schema_violation_exits_1(tmp_path, monkeypatch):
    """carrier 欠落を検知したら exit 1 (schema fail-closed)。validate_carrier を強制違反させる。"""
    mf = _mf_raw({"c1": _active_customer("A社", "月額サービス", 50000)})
    monkeypatch.setattr(V, "validate_carrier", lambda doc: ["forced carrier violation"])
    argv = [
        "--sheet", _write(tmp_path, "sheet.json", [_sheet_row("A社", "月額サービス")]),
        "--mf-curr", _write(tmp_path, "mfc.json", mf),
        "--mf-prev", _write(tmp_path, "mfp.json", mf),
        "--target", "2606",
        "--out-curr", str(tmp_path / "c.json"), "--out-prev", str(tmp_path / "p.json"),
    ]
    assert V.main(argv) == 1
    # fail-closed: 出力ファイルを書かない。
    assert not (tmp_path / "c.json").exists()


def test_cli_bad_target_exits_2(tmp_path):
    mf = _mf_raw({})
    for n in ("sheet.json", "mfc.json", "mfp.json"):
        (tmp_path / n).write_text(json.dumps([] if n == "sheet.json" else mf), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, V.__file__, "--sheet", str(tmp_path / "sheet.json"),
         "--mf-curr", str(tmp_path / "mfc.json"), "--mf-prev", str(tmp_path / "mfp.json"),
         "--target", "badval", "--out-curr", str(tmp_path / "c.json"),
         "--out-prev", str(tmp_path / "p.json")],
        capture_output=True, text=True)
    assert r.returncode == 2, (r.returncode, r.stderr)

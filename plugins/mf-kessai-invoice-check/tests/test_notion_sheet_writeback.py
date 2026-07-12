#!/usr/bin/env python3
"""lib/notion_sheet_writeback.py (請求確認シート 判定/AI確認 片方向ミラー) の単体テスト。

実ネットワークなし。fake req で GET databases / PATCH databases / PATCH pages を模す。
検証する不変条件:
  - 5値投影: GAP→発行漏れ / MATCH_*→AIの確認OK / SUPPRESS_*→対象外 / REVIEW_*→要確認。
  - ORPHAN(逆方向)はシート行が無いため投影しない (sheet_label=None)。
  - 1契約=複数シート行は全行へ展開し、重複 page_id は除去する。
      - 非破壊: PATCH props は『判定』『AI確認』『確認ポイント』のみ
    (契約開始日の補完は空欄だけ、契約終了月・人間列に触れない)。
  - ensure_judgment_property: 判定列が無ければ作成・既存optionは保持し不足5値だけ追加。
"""
import mfk_reconcile
import notion_sheet_writeback as wb


def _fake_req(db_props=None, writes=None, db_patches=None):
    """GET databases / PATCH databases / PATCH pages を扱う fake _req。"""
    def req(method, path, token, body=None):
        if method == "GET" and path.startswith("/databases/"):
            return {"properties": db_props or {}}
        if method == "PATCH" and path.startswith("/databases/"):
            if db_patches is not None:
                db_patches.append((body or {}).get("properties", {}))
            return {}
        if method == "PATCH" and path.startswith("/pages/"):
            if writes is not None:
                writes[path.split("/pages/")[1]] = (body or {}).get("properties", {})
            return {}
        raise AssertionError(f"想定外: {method} {path}")
    return req


def test_sheet_label_5value_mapping():
    assert mfk_reconcile.sheet_label("GAP") == "発行漏れ"
    assert mfk_reconcile.sheet_label("MATCH_MONTHLY") == "AIの確認OK"
    assert mfk_reconcile.sheet_label("MATCH_ANNUAL") == "AIの確認OK"
    assert mfk_reconcile.sheet_label("SUPPRESS_ANNUAL") == "対象外"
    assert mfk_reconcile.sheet_label("SUPPRESS_ENDED") == "対象外"
    assert mfk_reconcile.sheet_label("REVIEW_AMOUNT_MISMATCH") == "要確認"
    assert mfk_reconcile.sheet_label("REVIEW_ENDED_BUT_BILLED") == "要確認"
    # ORPHAN はシート行が無いため投影しない。
    assert mfk_reconcile.sheet_label("ORPHAN") is None
    # 未定義は None (fail-soft)。
    assert mfk_reconcile.sheet_label("__UNKNOWN__") is None


def test_build_writeback_expands_rows_and_excludes_orphan():
    rows = [
        {"verdict": "GAP", "_sheet_row_ids": ["p1", "p2"]},
        {"verdict": "MATCH_MONTHLY", "_sheet_row_ids": ["p3"]},
        {"verdict": "ORPHAN", "_sheet_row_ids": []},
        {"verdict": "REVIEW_QTY_MISMATCH", "_sheet_row_ids": ["p4"]},
        {"verdict": "GAP", "_sheet_row_ids": ["p1"]},  # 重複 p1 は除去
    ]
    items = wb.build_writeback(rows)
    by_pid = {it["page_id"]: it for it in items}
    assert set(by_pid) == {"p1", "p2", "p3", "p4"}
    assert by_pid["p1"]["sheet_label"] == "発行漏れ" and by_pid["p1"]["ai_check"] is False
    assert by_pid["p3"]["sheet_label"] == "AIの確認OK" and by_pid["p3"]["ai_check"] is True
    assert by_pid["p4"]["sheet_label"] == "要確認"


def test_writeback_is_nondestructive_three_columns_only():
    writes = {}
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": n} for n in wb.SHEET_LABELS]}},
                              "確認ポイント": {"rich_text": {}}},
                    writes=writes)
    rows = [{"verdict": "GAP", "_sheet_row_ids": ["pg1"]},
            {"verdict": "MATCH_MONTHLY", "_sheet_row_ids": ["pg2"]}]
    res = wb.writeback(rows, "sheetdb", "tok", req)
    assert res["updated"] == 2 and res["failed"] == []
    for props in writes.values():
        # 人間列『チェック済み』『確認内容』等に触れない (機械 3 列のみ)。
        assert set(props) == {"判定", "AI確認", "確認ポイント"}
    assert writes["pg1"]["判定"]["select"]["name"] == "発行漏れ"
    assert writes["pg1"]["AI確認"]["checkbox"] is False
    # 発行漏れ行には確認ポイントが入り、確認OK行は空。
    assert "発行" in writes["pg1"]["確認ポイント"]["rich_text"][0]["text"]["content"]
    assert writes["pg2"]["AI確認"]["checkbox"] is True
    assert writes["pg2"]["確認ポイント"]["rich_text"][0]["text"]["content"] == ""


def test_writeback_autofills_empty_start_only():
    # 契約開始日(ISO)は空欄セルのみ派生値で自動補完し、人間入力の非空値は不可侵。
    # 契約終了月は根拠なく入ると請求漏れを隠すため、自動補完しない。
    writes = {}
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": n} for n in wb.SHEET_LABELS]}},
                              "確認ポイント": {"rich_text": {}}}, writes=writes)
    rows = [{"verdict": "GAP", "契約開始日": "2026-06-01", "契約終了月": "2026-05-01",
             "_sheet_row_ids": ["empty", "filled"]}]
    current = {
        "empty":  {"契約開始日": "", "契約終了月": ""},            # 空欄→補完される
        "filled": {"契約開始日": "2026/6/8", "契約終了月": "2605"},  # 非空→不可侵
    }
    wb.writeback(rows, "sheetdb", "tok", req, current_dates=current)
    # 空欄行: 契約開始日(ISOそのまま)だけ補完される。
    assert writes["empty"]["契約開始日"]["rich_text"][0]["text"]["content"] == "2026-06-01"
    assert "契約終了月" not in writes["empty"]
    # 非空行: 日付列に触れない (人間入力不可侵)。判定3列は両行とも書く。
    assert "契約開始日" not in writes["filled"] and "契約終了月" not in writes["filled"]
    assert set(writes["empty"]) == {"判定", "AI確認", "確認ポイント", "契約開始日"}
    assert set(writes["filled"]) == {"判定", "AI確認", "確認ポイント"}


def test_writeback_skips_date_autofill_without_current_dates():
    # current_dates 未指定なら日付補完しない (後方互換・判定3列のみ)。
    writes = {}
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": n} for n in wb.SHEET_LABELS]}},
                              "確認ポイント": {"rich_text": {}}}, writes=writes)
    rows = [{"verdict": "GAP", "契約開始日": "2026-06-01", "契約終了月": "2026-05-01",
             "_sheet_row_ids": ["p1"]}]
    wb.writeback(rows, "sheetdb", "tok", req)  # current_dates=None
    assert set(writes["p1"]) == {"判定", "AI確認", "確認ポイント"}


def test_compose_note_combines_hint_and_warning():
    # 定型ガイダンス + 行固有の警告詳細を全角括弧で連結。
    n = wb.compose_note("REVIEW_QTY_MISMATCH", "数量差: 期待2>MF供給1(想定漏れ額 330,000円)")
    assert "確認" in n and "想定漏れ額 330,000円" in n
    # AIの確認OK は空 (stale を消す)。
    assert wb.compose_note("MATCH_MONTHLY", "") == ""
    # 警告がガイダンスに包含済みなら二重化しない。
    assert wb.compose_note("GAP", "") == mfk_reconcile.action_hint("GAP")


def test_compose_note_only_green_suppresses_nonempty_warning():
    # 分岐軸は sheet_label。緑(AIの確認OK=MATCH_*)だけ warning を漏らさず空を返す
    # (集約請求の MATCH_MONTHLY は verdict を保ちつつ engine が warning を付すが、シート
    #  確認ポイントには漏らさない=漏洩防止の核)。
    aggregated_warning = "MF 1明細に期待2件分が集約されているため数量差に降格しない"
    assert mfk_reconcile.sheet_label("MATCH_MONTHLY") == "AIの確認OK"
    assert wb.compose_note("MATCH_MONTHLY", aggregated_warning) == ""
    assert wb.compose_note("MATCH_ANNUAL", "情報") == ""
    # 対象外 (SUPPRESS 系) は ai_check=true でも『なぜ対象外か』の理由を確認ポイントへ出す
    # (決定2: 分岐軸が is_check_verdict → sheet_label に変わった)。
    assert mfk_reconcile.is_check_verdict("SUPPRESS_ENDED") is True
    assert wb.compose_note("SUPPRESS_ENDED", "") == mfk_reconcile.action_hint("SUPPRESS_ENDED")
    assert wb.compose_note("SUPPRESS_ENDED", ""), "対象外の理由が空になってはいけない"
    # 要確認/発行漏れ系 (非 ai_check) は warning を確認ポイントへ残す。
    assert mfk_reconcile.is_check_verdict("REVIEW_QTY_MISMATCH") is False
    assert wb.compose_note("REVIEW_QTY_MISMATCH", "行固有メモ") != ""


def test_compose_note_suppress_shows_each_reason():
    # 決定2: 全対象外(SUPPRESS_*)は『なぜ対象外か』の理由を確認ポイントへ出す(空にしない)。
    for v in ("SUPPRESS_ANNUAL", "SUPPRESS_ENDED", "SUPPRESS_ONESHOT", "SUPPRESS_OFFMONTH"):
        note = wb.compose_note(v, "")
        assert note == mfk_reconcile.action_hint(v)
        assert note, f"{v} の対象外理由が空"


def test_compose_note_review_canceled_combines_hint_and_warning():
    # 要確認(取消): 定型ガイダンス + 取消日時/取消前金額の行固有警告を全角括弧で連結する。
    warn = "取消日: 2026-06-25T17:39:45+09:00 / 取消前金額: 70,000円"
    note = wb.compose_note("REVIEW_CANCELED", warn)
    assert mfk_reconcile.action_hint("REVIEW_CANCELED") in note
    assert "取消前金額: 70,000円" in note
    assert mfk_reconcile.sheet_label("REVIEW_CANCELED") == "要確認"


def test_compose_note_review_txn_not_passed_combines_hint_and_warning():
    # 要確認(取引未確定): 定型ガイダンス + status/金額の行固有警告を確認ポイントに残す。
    warn = "MF取引状態: examining / 金額: 70,000円"
    note = wb.compose_note("REVIEW_TXN_NOT_PASSED", warn)
    assert mfk_reconcile.action_hint("REVIEW_TXN_NOT_PASSED") in note
    assert "examining" in note and "70,000円" in note
    assert mfk_reconcile.sheet_label("REVIEW_TXN_NOT_PASSED") == "要確認"


def test_compose_note_suppress_ended_with_cancellation_warning():
    # 対象外(契約終了)でも取消注記 warning があれば確認ポイントに取消理由が出る (WARN-not-FAIL)。
    # engine の cancellation_note が warning へ注記し、compose_note が {hint}（{warning}）で流す。
    warn = "当月MFに取消取引あり: 取消前金額 90,000円 / 取消日 2026-06-25T17:39:45+09:00"
    note = wb.compose_note("SUPPRESS_ENDED", warn)
    assert mfk_reconcile.sheet_label("SUPPRESS_ENDED") == "対象外"
    assert mfk_reconcile.action_hint("SUPPRESS_ENDED") in note  # 対象外理由は残る
    assert "取消取引あり" in note and "取消前金額 90,000円" in note  # 取消理由も確認ポイントに出る


def test_ensure_note_property_creates_when_missing():
    req = _fake_req(db_props={})  # 確認ポイント無し
    assert wb.ensure_note_property("sheetdb", "tok", req) == "created"
    req2 = _fake_req(db_props={"確認ポイント": {"rich_text": {}}})
    assert wb.ensure_note_property("sheetdb", "tok", req2) == "ok"


def test_ensure_judgment_property_creates_when_missing():
    patches = []
    req = _fake_req(db_props={}, db_patches=patches)  # 判定列なし
    state = wb.ensure_judgment_property("sheetdb", "tok", req)
    assert state == "created"
    opts = patches[0]["判定"]["select"]["options"]
    names = [o["name"] for o in opts]
    assert names == wb.SHEET_LABELS
    assert {o["name"]: o["color"] for o in opts}["発行漏れ"] == "red"


def test_ensure_judgment_property_merges_missing_options():
    # 既存 option を保持しつつ不足 5 値だけ追加する。
    patches = []
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": "確認OK", "color": "green"}]}}},
                   db_patches=patches)
    state = wb.ensure_judgment_property("sheetdb", "tok", req)
    assert state == "updated"
    names = [o["name"] for o in patches[0]["判定"]["select"]["options"]]
    assert "確認OK" in names and "発行漏れ" in names and "未照合" in names


def test_ensure_judgment_property_noop_when_complete():
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": n} for n in wb.SHEET_LABELS]}}})
    assert wb.ensure_judgment_property("sheetdb", "tok", req) == "ok"


def test_ensure_judgment_property_fail_soft_on_unknown_label_color(monkeypatch):
    # SSOT に色未定義の 6 値目が増えても KeyError で全停止せず default 色で fail-soft 投影する。
    monkeypatch.setattr(wb, "SHEET_LABELS", wb.SHEET_LABELS + ["新ラベル"])
    # 作成パス (判定列なし) と マージパス (既存option保持) の両方で KeyError を出さない。
    patches = []
    req = _fake_req(db_props={}, db_patches=patches)
    assert wb.ensure_judgment_property("sheetdb", "tok", req) == "created"
    new_opt = {o["name"]: o["color"] for o in patches[0]["判定"]["select"]["options"]}["新ラベル"]
    assert new_opt == "default"
    patches2 = []
    req2 = _fake_req(db_props={"判定": {"select": {"options": [{"name": "発行漏れ", "color": "red"}]}}},
                     db_patches=patches2)
    assert wb.ensure_judgment_property("sheetdb", "tok", req2) == "updated"
    merged = {o["name"]: o.get("color") for o in patches2[0]["判定"]["select"]["options"]}
    assert merged["新ラベル"] == "default"


def test_writeback_failure_is_collected_not_raised():
    def req(method, path, token, body=None):
        if method == "GET":
            return {"properties": {"判定": {"select": {"options": []}}}}
        if method == "PATCH" and path.startswith("/databases/"):
            return {}
        if method == "PATCH" and path.startswith("/pages/"):
            raise RuntimeError("boom")
        raise AssertionError(path)
    res = wb.writeback([{"verdict": "GAP", "_sheet_row_ids": ["pg1"]}], "s", "t", req)
    assert res["updated"] == 0
    assert len(res["failed"]) == 1 and res["failed"][0]["page_id"] == "pg1"


# ---------------------------------------------------------------------------
# 同一取引先への契約開始日 伝播 backfill (独立パス)
# ---------------------------------------------------------------------------
def test_plan_propagation_single_value_fills_blanks():
    # X株式会社 / X は normalize で同一グループ。開始日は ISO 2026-06-01 で 1 種類
    # (2606 も to_date で同値) → 空欄行へ伝播する。終了月は伝播しない。
    rows = [
        {"page_id": "a", "取引先": "X株式会社", "契約開始日": "2026-06-01", "契約終了月": "2608"},
        {"page_id": "b", "取引先": "X株式会社", "契約開始日": "", "契約終了月": ""},
        {"page_id": "c", "取引先": "X", "契約開始日": "2606", "契約終了月": ""},
    ]
    plan = wb.plan_contract_date_propagation(rows)
    assert plan["updates"]["b"]["契約開始日"] == "2026-06-01"
    assert "契約終了月" not in plan["updates"]["b"]
    assert "契約終了月" not in plan["updates"].get("c", {})
    # c の開始日は非空 (2606) なので touch しない。a は全非空 → updates に出ない。
    assert "契約開始日" not in plan["updates"].get("c", {})
    assert "a" not in plan["updates"]
    assert plan["conflicts"] == []
    assert plan["stats"]["start_filled"] == 1 and plan["stats"]["end_filled"] == 0


def test_plan_propagation_conflict_blocks_fill():
    # 同一取引先で開始日が 2 種類 (複数契約) → 伝播せず conflicts に記録 (誤伝播=請求漏れ回避)。
    rows = [
        {"page_id": "a", "取引先": "Y", "契約開始日": "2026-04-01", "契約終了月": ""},
        {"page_id": "b", "取引先": "Y", "契約開始日": "2026-09-01", "契約終了月": ""},
        {"page_id": "c", "取引先": "Y", "契約開始日": "", "契約終了月": ""},
    ]
    plan = wb.plan_contract_date_propagation(rows)
    assert "契約開始日" not in plan["updates"].get("c", {})
    assert any(cf["列"] == "契約開始日" and cf["取引先"] == "Y" for cf in plan["conflicts"])


def test_plan_propagation_ignores_end_month_values():
    # 終了月は値があっても伝播対象外。開始日が単一値なら開始日だけ伝播する。
    rows = [
        {"page_id": "a", "取引先": "W", "契約開始日": "2026-06-01", "契約終了月": "2608"},
        {"page_id": "b", "取引先": "W", "契約開始日": "2606", "契約終了月": "2610"},
        {"page_id": "c", "取引先": "W", "契約開始日": "", "契約終了月": ""},
    ]
    plan = wb.plan_contract_date_propagation(rows)
    assert plan["updates"]["c"] == {"契約開始日": "2026-06-01"}
    assert not any(cf["列"] == "契約終了月" for cf in plan["conflicts"])


def test_plan_propagation_blocks_end_leak_to_continuing_contract():
    # B-1 回帰防止: 同一取引先に「終了済(終了月2606)」と「継続中(終了月=空欄)」が混在。
    # 契約終了月は伝播対象外なので、開始日がどうであっても終了月2606 を継続契約の空欄へ漏らさない。
    rows = [
        {"page_id": "ended", "取引先": "Y", "契約開始日": "2604", "契約終了月": "2606"},
        {"page_id": "cont", "取引先": "Y", "契約開始日": "2609", "契約終了月": ""},
    ]
    plan = wb.plan_contract_date_propagation(rows)
    assert "cont" not in plan["updates"], "終了月が継続契約へ漏れてはいけない"
    assert any(cf["列"] == "契約開始日" for cf in plan["conflicts"])


def test_plan_propagation_idempotent_when_all_filled():
    # 全行が既に記入済み → 伝播対象ゼロ (冪等: 再実行で差分なし)。
    rows = [
        {"page_id": "a", "取引先": "Z", "契約開始日": "2606", "契約終了月": "2612"},
        {"page_id": "b", "取引先": "Z", "契約開始日": "2606", "契約終了月": "2612"},
    ]
    plan = wb.plan_contract_date_propagation(rows)
    assert plan["updates"] == {}
    assert plan["conflicts"] == []


def test_plan_propagation_ignores_blank_torihiki():
    # 取引先が空欄の行はグループ化せず無視する (誤った全行一括伝播を防ぐ)。
    rows = [
        {"page_id": "a", "取引先": "", "契約開始日": "2026-06-01", "契約終了月": ""},
        {"page_id": "b", "取引先": "", "契約開始日": "", "契約終了月": ""},
    ]
    plan = wb.plan_contract_date_propagation(rows)
    assert plan["updates"] == {}


def test_apply_propagation_writes_blank_cells_only():
    writes = {}
    req = _fake_req(writes=writes)
    updates = {"p1": {"契約開始日": "2026-06-01"}, "p2": {"契約終了月": "2608"}}
    res = wb.apply_contract_date_propagation(updates, "sheetdb", "tok", req)
    assert res["written"] == 1 and res["failed"] == []
    assert writes["p1"]["契約開始日"]["rich_text"][0]["text"]["content"] == "2026-06-01"
    assert "p2" not in writes
    # 契約開始日のみ書く (判定/AI確認/確認ポイント/契約終了月には触れない)。
    assert set(writes["p1"]) == {"契約開始日"}


def test_apply_propagation_failure_is_collected_not_raised():
    def req(method, path, token, body=None):
        if method == "PATCH" and path.startswith("/pages/"):
            raise RuntimeError("boom")
        raise AssertionError(path)
    res = wb.apply_contract_date_propagation({"p1": {"契約開始日": "2026-06-01"}}, "s", "t", req)
    assert res["written"] == 0
    assert len(res["failed"]) == 1 and res["failed"][0]["page_id"] == "p1"


# ---------------------------------------------------------------------------
# 確認内容に終了根拠の無い契約終了月のクリア (健全性回復)
# ---------------------------------------------------------------------------
def test_has_end_basis():
    # 明示的な終了注記は根拠あり。
    assert wb.has_end_basis("（2605終了）") is True
    assert wb.has_end_basis("請求なし（2604契約終了）") is True
    assert wb.has_end_basis("8月で解約予定") is True
    assert wb.has_end_basis("終了月: 2606") is True
    # 終了注記なし / 曖昧語「まで」は根拠にしない (誤検出回避)。
    assert wb.has_end_basis("300,000円\n田中太郎") is False
    assert wb.has_end_basis("2605まで継続予定") is False
    assert wb.has_end_basis("") is False


def test_plan_unsupported_end_date_clear():
    rows = [
        {"page_id": "g", "契約終了月": "2606", "確認内容": "（2606終了）"},   # 根拠あり→残す
        {"page_id": "u1", "契約終了月": "2606", "確認内容": "300,000円\n田中"},  # 根拠なし→クリア
        {"page_id": "u2", "契約終了月": "2605", "確認内容": ""},              # 根拠なし→クリア
        {"page_id": "empty", "契約終了月": "", "確認内容": "x"},              # 終了月空→対象外
    ]
    plan = wb.plan_unsupported_end_date_clear(rows)
    assert set(plan["clears"]) == {"u1", "u2"}
    assert plan["stats"] == {"with_end": 3, "grounded": 1, "unsupported": 2}


def test_apply_end_date_clear_writes_empty_richtext():
    writes = {}
    req = _fake_req(writes=writes)
    res = wb.apply_end_date_clear(["p1", "p2"], "sheetdb", "tok", req)
    assert res["cleared"] == 2 and res["failed"] == []
    # 契約終了月を空 rich_text で上書き (空欄化)。他列には触れない。
    assert writes["p1"]["契約終了月"]["rich_text"] == []
    assert set(writes["p1"]) == {"契約終了月"}


def test_apply_end_date_clear_failure_collected():
    def req(method, path, token, body=None):
        raise RuntimeError("boom")
    res = wb.apply_end_date_clear(["p1"], "s", "t", req)
    assert res["cleared"] == 0
    assert len(res["failed"]) == 1 and res["failed"][0]["page_id"] == "p1"

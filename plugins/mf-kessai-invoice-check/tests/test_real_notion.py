#!/usr/bin/env python3
"""L3 real_test: 実 Notion DB への往復で I2 冪等性を mock 抜きに実証する。

mock では守れない「実 API のレスポンス形・本文 table のページネーション・型」と、
同月再 upsert で行が重複しない冪等性を、本番コード (notion_invoice_sink) そのものを
叩いて検証する。

安全弁 (production を絶対に汚さない):
  - 専用サンドボックス DB を環境変数 MFK_TEST_DATABASE_ID で受け取る。未設定なら skip。
    .mf-kessai-config.json の本番 database_id は決して使わない。
  - Notion トークン (NOTION_API_KEY or Keychain) が引けなければ skip。
  - 作成したテストページは必ず後始末 (archived=True) する。
  - 顧客IDは毎回ユニーク (__mfk_l3_test__<uuid>) にし、対象年月は明らかに合成の 2099-01。

secrets を持つ運用者環境でのみ走り、CI / 一般環境では無言で skip する。
"""
import os
import uuid

import pytest

import notion_invoice_sink as sink

PERIOD = "2099-01"  # 明らかに合成のテスト月 (実運用と衝突しない)


def _sandbox():
    """サンドボックス (database_id, token) を返す。secrets が無ければ skip。"""
    db_id = os.environ.get("MFK_TEST_DATABASE_ID")
    if not db_id:
        pytest.skip("MFK_TEST_DATABASE_ID 未設定 (L3 real_test は専用サンドボックスDBが必要)")
    try:
        token = sink._notion_token()
    except RuntimeError as e:
        pytest.skip(f"Notion トークン取得不可: {e}")
    return db_id, token


def _row(cid, curr_amount):
    return {
        "customer_id": cid,
        "period_ym": PERIOD,
        "company_name": "L3テスト株式会社",
        "verdict": "発行漏れ候補",
        "product_name": "テスト商品",
        "prev_amount": 1000,
        "curr_amount": curr_amount,
    }


def _archive(db_id, cid, token):
    """テストで作った顧客ページを後始末する (失敗しても本テストは汚さない)。"""
    try:
        page_id = sink._find_page(db_id, cid, token)
        if page_id:
            sink._req("PATCH", f"/pages/{page_id}", token, {"archived": True})
    except Exception:
        pass


def test_real_upsert_roundtrip_and_idempotency():
    """upsert→read-back→再upsert で I2 冪等性 (重複ページ無し/重複行無し) を実 API 実証する。"""
    db_id, token = _sandbox()
    cid = f"__mfk_l3_test__{uuid.uuid4().hex[:8]}"
    try:
        # --- 1 回目 upsert: 新規ページ + 本文 table に当月行が出来る ---
        res1 = sink.upsert(db_id, [_row(cid, curr_amount=0)], token=token, period_ym=PERIOD)
        assert res1["created"] == 1 and res1["updated"] == 0

        page_id = sink._find_page(db_id, cid, token)
        assert page_id, "顧客IDで作成ページを read-back できること"

        table_id = sink._find_table_id(page_id, token)
        assert table_id, "本文に table block が出来ていること"

        def month_rows():
            rows = sink._all_block_children(table_id, token)
            # 先頭はヘッダ。対象年月セルが PERIOD の行だけ抽出。
            out = []
            for idx, blk in enumerate(rows):
                if idx == 0:
                    continue
                cells = (blk.get("table_row") or {}).get("cells") or []
                if cells and sink._cell_plain(cells[0]) == PERIOD:
                    out.append(blk)
            return out

        rows1 = month_rows()
        assert len(rows1) == 1, "当月行はちょうど 1 行"
        # 今月金額セル (TABLE_COLUMNS の index 3) が 0 で書かれていること
        cells1 = rows1[0]["table_row"]["cells"]
        assert sink._cell_plain(cells1[3]) == "0"

        # --- 2 回目 upsert: 同じ顧客・同じ月。金額だけ変える ---
        res2 = sink.upsert(db_id, [_row(cid, curr_amount=500)], token=token, period_ym=PERIOD)
        assert res2["updated"] == 1 and res2["created"] == 0, "既存ページを更新 (新規作成しない)"

        # I2: ページが重複していない (顧客IDで一意のまま)。_find_page は複数ヒットで raise。
        page_id2 = sink._find_page(db_id, cid, token)
        assert page_id2 == page_id, "同一ページを更新していること"

        # I2: 当月行が増えていない (重複追記でなく既存行更新)。値は 500 に更新。
        rows2 = month_rows()
        assert len(rows2) == 1, "再 upsert で当月行が重複しない (冪等)"
        cells2 = rows2[0]["table_row"]["cells"]
        assert sink._cell_plain(cells2[3]) == "500", "既存行が新しい金額で更新されている"
    finally:
        _archive(db_id, cid, token)


def test_real_schema_verify_passes_on_sandbox():
    """サンドボックス DB が schema を満たすか verify する (drift 検知の実 API 版)。

    build_notion_db で schema 適用済みの DB を前提に、欠落プロパティが無いことを実 API で確認。
    """
    db_id, token = _sandbox()
    res = sink._req("GET", f"/databases/{db_id}", token)
    existing = set((res.get("properties") or {}).keys())
    # 集約モデルの必須事実列が揃っていること (最低限の drift ガード)。
    required = {"取引先企業名", "顧客ID", "対象年月", "今月の発行状況", "今月金額"}
    missing = required - existing
    assert not missing, f"サンドボックスDBに必須プロパティが欠落: {sorted(missing)}"

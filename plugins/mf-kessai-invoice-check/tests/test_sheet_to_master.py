#!/usr/bin/env python3
"""lib/sheet_to_master.py のテスト (2606 実データ golden + 純関数ユニット + 冪等 upsert)。

golden 入力(tests/fixtures/):
  - notion_2606.json  : 請求確認シート 95 行(取引先/商品/確認内容/契約開始日/契約終了月)。
  - mf_2606.json      : MF掛け払い 対象月取引実績 82 顧客(支払サイクル推定の補助シグナル)。

サイクル推定の正答(検証フェーズ結果): 月払い45 / 年間払い15 / 年間一括更新3 / 分割1 /
保留3 / 従量(都度)1 = 計68契約。ツネマツ業務委託『45,000円/件 澤田聖陽』は旧 inventory では
不明だが『/件』=従量(都度)で確定(本推定の改善点)。期待値は仕様・実データから導いており、
実装出力に合わせて歪めていない。
"""
import json
import os
import unicodedata

import pytest

import sheet_to_master as S


def _nfc(s):
    # fixture は macOS 由来でカタカナが NFD(濁点合成)のことがあるため NFC で揃えて部分一致する。
    return unicodedata.normalize("NFC", s or "")

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
TARGET = "2606"


def _load(name):
    with open(os.path.join(FX, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def sheet_rows():
    return _load("notion_2606.json")


@pytest.fixture(scope="module")
def mf_json():
    return _load("mf_2606.json")


@pytest.fixture(scope="module")
def contracts(sheet_rows, mf_json):
    return S.build_contracts(sheet_rows, mf_index=mf_json, target_ym=TARGET)


def _find(contracts, torihiki_sub, ec_sub=None, amount=None):
    """取引先部分一致(+任意で ec 部分一致 / 現行単価一致)で契約を 1 件返す。"""
    hits = []
    for c in contracts:
        if _nfc(torihiki_sub) not in _nfc(c["取引先"]):
            continue
        if ec_sub is not None and _nfc(ec_sub) not in _nfc(c["エンドクライアント名"]):
            continue
        if amount is not None and c["現行単価"] != amount:
            continue
        hits.append(c)
    assert len(hits) == 1, f"{torihiki_sub}/{ec_sub}/{amount} -> {len(hits)}件: {[h['契約ID'] for h in hits]}"
    return hits[0]


# ---------------------------------------------------------------------------
# golden: 集約数 と サイクル推定の内訳
# ---------------------------------------------------------------------------
def test_aggregates_to_68_contracts(contracts):
    assert len(contracts) == 68


def test_expected_meisai_sum_equals_sheet_rows(contracts, sheet_rows):
    # 期待明細数の総和は集約元の行数(95)に一致する(行を落とさず束ねた証跡)。
    assert sum(c["期待明細数"] for c in contracts) == len(sheet_rows)


def test_cycle_distribution_matches_ground_truth(contracts):
    from collections import Counter
    dist = Counter((c["支払サイクル"] or "保留") for c in contracts)
    expected = {
        "月払い": 45,
        "年間払い": 15,
        "年間一括更新": 3,
        "分割": 1,
        "従量(都度)": 1,
        "保留": 3,
    }
    assert sum(dist.values()) == 68
    for label, exp in expected.items():
        assert abs(dist.get(label, 0) - exp) <= 1, f"{label}: actual={dist.get(label, 0)} expected≈{exp} (dist={dict(dist)})"
    # 推定外のラベルが紛れ込まないこと(MECE)。
    assert set(dist) <= set(expected)


def test_contract_ids_are_unique(contracts):
    ids = [c["契約ID"] for c in contracts]
    assert len(ids) == len(set(ids))


def test_sheet_row_ids_cover_all_source_rows_once(contracts, sheet_rows):
    # シート書き戻し用 _sheet_row_ids が当月全行を漏れなく・重複なく保持する。
    src = {r["page_id"] for r in sheet_rows if r.get("page_id")}
    collected = [pid for c in contracts for pid in c["_sheet_row_ids"]]
    assert all(isinstance(c["_sheet_row_ids"], list) for c in contracts)
    assert len(collected) == len(set(collected)), "page_id が複数契約に重複している"
    assert set(collected) == src, "当月シート行の一部が契約に紐づいていない"
    # 請求確認シートID(代表1件)は _sheet_row_ids の部分集合 (代表は全行のいずれか)。
    for c in contracts:
        if c.get("請求確認シートID"):
            assert c["請求確認シートID"] in c["_sheet_row_ids"]


# ---------------------------------------------------------------------------
# golden: 代表例の固定 assert
# ---------------------------------------------------------------------------
def test_motoya_monthly_meisai3(contracts):
    c = _find(contracts, "モトヤユナイテッド", ec_sub="玉井修司")
    assert c["支払サイクル"] == "月払い"
    assert c["期待明細数"] == 3  # ThinkTank表記2行+業務委託費1行を1契約へ統合
    assert c["商品"] == S.PROD_BIZ
    # 集約元の商品集合は _source_products 一本に保持 (SSOT: 重複キー 商品一覧 は廃止)。
    assert S.PROD_BIZ in c["_source_products"]
    assert S.PROD_THINKTANK in c["_source_products"]
    assert "商品一覧" not in c  # 非永続の重複キーが復活していないこと (回帰防止)
    assert c["現行単価"] == 330000


def test_aggregated_contract_keeps_source_product_set():
    rows = [
        {
            "取引先": "同額株式会社",
            "商品": "チイキズカン業務委託費",
            "確認内容": "100,000円 山田太郎",
            "契約開始日": "",
            "契約終了月": "",
            "page_id": "p-biz",
        },
        {
            "取引先": "同額株式会社",
            "商品": "100億ThinkTank利用料",
            "確認内容": "100,000円 山田太郎",
            "契約開始日": "",
            "契約終了月": "",
            "page_id": "p-think",
        },
    ]
    contracts = S.build_contracts(rows, mf_index=None, target_ym="2606")
    assert len(contracts) == 1
    assert contracts[0]["商品"] == S.PROD_BIZ
    assert contracts[0]["_source_products"] == [S.PROD_BIZ, S.PROD_THINKTANK]
    assert "商品一覧" not in contracts[0]  # 非永続の重複キーが復活していないこと (回帰防止)


def test_hatada_annual(contracts):
    c = _find(contracts, "ハタダ")
    assert c["支払サイクル"] == "年間払い"


def test_cityplus_annual_renewal(contracts):
    c = _find(contracts, "シティプラス")
    assert c["支払サイクル"] == "年間一括更新"


def test_sansui_split_without_start_falls_back_to_monthly(contracts):
    # 山翠舎は MF注記『分割支払い 50,000円/月』で分割推定されるが、契約開始日も期間も無いため
    # ユーザー確定(2026-06-27)の「アンカー無し→月払い」降格が適用される(50,000円/月=実質月払いで
    # 毎月発行が期待される)。分割は契約開始日があれば従来通り分割のまま。
    c = _find(contracts, "山翠舎")
    assert c["支払サイクル"] == "月払い"


def test_tsunematsu_sawada_metered(contracts):
    c = _find(contracts, "ツネマツ", ec_sub="澤田聖陽")
    assert c["支払サイクル"] == "従量(都度)"  # 『45,000円/件』


def test_ashida_blank_is_pending(contracts):
    # 芦田は 2 契約(オオウチトモ430k=月払い / 確認内容空欄=保留)。空欄側を現行単価None で特定。
    blank = [c for c in contracts if "芦田" in c["取引先"] and c["現行単価"] is None]
    assert len(blank) == 1
    c = blank[0]
    assert c["エンドクライアント名"] == ""
    assert c["支払サイクル"] is None
    assert c["ステータス"] == "保留"


def test_ended_contract_status(contracts):
    # 森信建設『430,000円 2H株式会社 …（2606終了）』終了月=2606<=対象2606 → ステータス終了。
    c = _find(contracts, "森信建設", ec_sub="2H株式会社")
    assert c["ステータス"] == "終了"
    assert c["契約終了月"] == "2026-06-01"


def test_content_end_note_does_not_create_contract_end():
    # 自由文の『（2605終了）』は請求メモ等の可能性があり、正式な契約終了月として扱わない。
    rows = [{
        "取引先": "メモ株式会社",
        "商品": "チイキズカン業務委託費",
        "確認内容": "220,000円 森祐輔 請求なし（2605終了）",
        "契約開始日": "",
        "契約終了月": "",
        "page_id": "p-note",
    }]
    c = S.build_contracts(rows, mf_index=None, target_ym="2606")[0]
    assert c["契約終了月"] is None
    assert c["ステータス"] == "有効"


def test_build_contracts_preserves_explicit_mf_customer_id():
    rows = [{
        "取引先": "ID明示株式会社",
        "商品": "チイキズカン利用料（2年目以降）",
        "確認内容": "50,000円",
        "契約開始日": "",
        "契約終了月": "",
        "MF顧客ID": "CUST-EXPLICIT",
        "page_id": "p-id",
    }]
    c = S.build_contracts(rows, mf_index=None, target_ym="2606")[0]
    assert c["MF顧客ID"] == "CUST-EXPLICIT"


def test_build_contracts_derives_unique_mf_customer_id_from_mf_names():
    """会社名一致(完全一致 or 3文字以上包含)で一意解決できる場合のみ backfill する。
    名前→ID 解決は mfk_customer_id_resolve(C02)へ一本化(mfk_reconcile._company_match 消費)。"""
    rows = [{
        "取引先": "アルファ商事株式会社",
        "商品": "チイキズカン利用料（2年目以降）",
        "確認内容": "50,000円",
        "契約開始日": "",
        "契約終了月": "",
        "page_id": "p-alpha",
    }]
    mf = {"customers": {
        "633V-AYRW": {"name": "アルファ商事株式会社", "lines": []},
        "OTHER": {"name": "別会社株式会社", "lines": []},
    }}
    c = S.build_contracts(rows, mf_index=mf, target_ym="2606")[0]
    assert c["MF顧客ID"] == "633V-AYRW"


def test_build_contracts_ambiguous_mf_name_match_does_not_backfill():
    """複数 MF顧客が同名境界一致する(ambiguous)場合は自動 backfill しない(誤結線回避)。"""
    rows = [{
        "取引先": "商事株式会社",
        "商品": "チイキズカン利用料（2年目以降）",
        "確認内容": "50,000円",
        "契約開始日": "",
        "契約終了月": "",
        "page_id": "p-ambi",
    }]
    mf = {"customers": {
        "A": {"name": "商事株式会社", "lines": []},
        "B": {"name": "商事株式会社", "lines": []},
    }}
    c = S.build_contracts(rows, mf_index=mf, target_ym="2606")[0]
    assert "MF顧客ID" not in c


# ---------------------------------------------------------------------------
# 純関数ユニット
# ---------------------------------------------------------------------------
def test_shohin_canon():
    assert S.shohin_canon("チイキズカン業務委託費") == S.PROD_BIZ
    assert S.shohin_canon("100億ThinkTank利用料") == S.PROD_THINKTANK
    assert S.shohin_canon("チイキズカン利用料（1年目）") == S.PROD_RIYO_Y1
    assert S.shohin_canon("チイキズカン利用料（2年目以降）") == S.PROD_RIYO_Y2
    assert S.shohin_canon("謎商品(備考)") == "謎商品"
    assert S.shohin_canon("") == ""


def test_to_date_formats():
    assert S.to_date("2026-06-24") == "2026-06-24"
    assert S.to_date("2606") == "2026-06-01"        # YYMM
    assert S.to_date("2026/6/8") == "2026-06-08"    # YYYY/M/D
    assert S.to_date("2026/6") == "2026-06-01"      # YYYY/M
    assert S.to_date("2026-06") == "2026-06-01"     # YYYY-MM
    assert S.to_date("") is None
    assert S.to_date("不明") is None
    assert S.to_date("2099") is None                # 末尾2桁が月として不正(99月)


def test_infer_cycle_rules():
    assert S.infer_cycle("45,000円/件 澤田", S.PROD_BIZ, 45000, {}) == "従量(都度)"
    assert S.infer_cycle("50,000円", S.PROD_RIYO_Y1, 50000, {"has_split": True}) == "分割"
    assert S.infer_cycle("", S.PROD_BIZ, None, {}) is None
    assert S.infer_cycle("5/19契約書未締結", S.PROD_BIZ, None, {}) is None
    assert S.infer_cycle("月額150,000円", S.PROD_THINKTANK, 150000, {}) == "月払い"
    assert S.infer_cycle("50,000円", S.PROD_RIYO_Y2, 50000, {}) == "月払い"
    assert S.infer_cycle("更新確認", S.PROD_THINKTANK, None, {}) == "年間一括更新"
    assert S.infer_cycle("更新確認", S.PROD_RIYO_Y1, None, {"riyo_lump": True}) == "年間払い"
    assert S.infer_cycle("50,000円", S.PROD_RIYO_Y1, 50000, {"riyo_monthly": True}) == "月払い"
    assert S.infer_cycle("50,000円", S.PROD_RIYO_Y1, 50000, {}) == "年間払い"
    assert S.infer_cycle("300,000円", S.PROD_BIZ, 300000, {}) == "月払い"
    assert S.infer_cycle("41,000円", S.PROD_BIZ, 41000, {}) is None  # 月額下限未満→保留
    assert S.infer_cycle("謎", "謎商品", 100000, {}) == "月払い"      # fallback
    assert S.infer_cycle("謎", "謎商品", None, {}) is None


def test_period_drives_initial_annual_cycle_before_monthly_wording():
    content = "月額払い：150,000円 期間：2026/6/8〜2027/6/7"
    assert S.infer_cycle(content, S.PROD_RIYO_Y1, 150000, {}) == "年間払い"
    assert S.parse_period_start(content) == "2026-06-08"


def test_second_year_product_stays_monthly_even_with_period():
    content = "月額払い：50,000円 期間：2026/6/8〜2027/6/7"
    assert S.infer_cycle(content, S.PROD_RIYO_Y2, 50000, {}) == "月払い"


def test_thinktank_period_is_annual_renewal():
    content = "月額払い：150,000円 期間：2026/6/8〜2027/6/7"
    assert S.infer_cycle(content, S.PROD_THINKTANK, 150000, {}) == "年間一括更新"


def test_recurring_amount_prefers_monthly():
    # 初期費用と月額の併記行では月額側を採る。
    assert S._recurring_amount("初期：300,000円 月額払い：150,000円") == 150000
    assert S._recurring_amount("330,000円 玉井修司") == 330000
    assert S._recurring_amount("確認待ち") is None


def test_clean_endclient_rejects_pseudo_names():
    row = {"取引先": "株式会社エスツー", "確認内容": "初期：300,000円 月額払い：150,000円 契約期間：2026/6/8〜"}
    assert S._clean_endclient(row) == ""  # 『月額払い：150,000円』を人名と誤抽出しない


def test_build_mf_signals_and_as_signals(mf_json):
    sig = S.build_mf_signals(mf_json)
    import mfk_reconcile as rc
    assert sig[rc.normalize("株式会社山翠舎")]["has_split"] is True
    assert sig[rc.normalize("株式会社ハタダ")]["riyo_lump"] is True
    assert sig[rc.normalize("2nd Community株式会社")]["riyo_monthly"] is True
    # _as_signals: None / raw JSON / 既製 signals dict の 3 経路。
    assert S._as_signals(None) == {}
    assert S._as_signals(mf_json) == sig
    assert S._as_signals(sig) is sig


def test_majority_prefers_nonempty_over_blank():
    # 同数なら非空を優先。空が多数でも非空商品名を採る(商品空メモ行対策)。全空なら空のまま。
    assert S._majority(["", "X"]) == "X"
    assert S._majority(["", "", "X"]) == "X"
    assert S._majority(["A", "A", "B"]) == "A"   # 通常の多数決は不変
    assert S._majority(["", ""]) == ""


def test_blank_product_memo_row_does_not_blank_real_product():
    # 商品空のメモ行(連絡先変更・金額なし)と実商品行が同一バケツ(取引先同/EC空/金額None)に
    # 入っても、商品が空文字で潰れない(エス HD で実際に起きた Notion 空 select 拒否の回帰)。
    rows = [
        {"取引先": "エス社", "商品": "", "確認内容": "変更：a@b.com",
         "契約開始日": "", "契約終了月": ""},
        {"取引先": "エス社", "商品": "チイキズカン利用料（1年目）",
         "確認内容": "更新確認 期間：2025/10/27〜2026/10/26",
         "契約開始日": "2025-10-27", "契約終了月": ""},
    ]
    cs = S.build_contracts(rows, mf_index=None, target_ym="2606")
    es = [c for c in cs if "エス社" in c["取引先"]]
    assert len(es) == 1
    assert es[0]["商品"] == S.PROD_RIYO_Y1
    assert es[0]["商品"] != ""


def test_to_props_blank_product_falls_back_to_unclassified():
    # 万一 商品='' が残っても select は『未分類』へ倒し、空 select 拒否で投入が落ちない。
    fake = FakeNotion()
    contract = {"契約ID": "Z//", "取引先": "Z", "商品": "", "ステータス": "保留",
                "期待明細数": 1, "備考": ""}
    S.upsert_master([contract], "DB1", "tok", req=fake.req)
    props = next(iter(fake.pages.values()))
    assert props["商品"]["select"]["name"] == "未分類"


def test_status_helper():
    assert S._status("月払い", "2605", "", "2606") == "終了"
    assert S._status("月払い", "2607", "", "2606") == "有効"   # 終了月が未来
    assert S._status(None, None, "", "2606") == "保留"
    assert S._status("月払い", None, "5/19契約書未締結", "2606") == "保留"
    assert S._status("月払い", None, "", "2606") == "有効"


# ---------------------------------------------------------------------------
# 冪等 upsert (mock req)
# ---------------------------------------------------------------------------
class FakeNotion:
    """Notion REST の最小モック: /databases/{id}/query, POST /pages, PATCH /pages/{id}。"""

    def __init__(self):
        self.pages = {}   # page_id -> properties
        self.calls = []
        self._n = 0

    def req(self, method, path, token, body=None):
        self.calls.append((method, path))
        if method == "POST" and path.endswith("/query"):
            results = [{"id": pid, "properties": props} for pid, props in self.pages.items()]
            return {"results": results, "has_more": False}
        if method == "POST" and path == "/pages":
            self._n += 1
            pid = f"page-{self._n}"
            self.pages[pid] = body["properties"]
            return {"id": pid}
        if method == "PATCH" and path.startswith("/pages/"):
            pid = path.split("/pages/")[1]
            self.pages[pid].update(body["properties"])
            return {"id": pid}
        raise AssertionError(f"unexpected request {method} {path}")


def test_upsert_master_is_idempotent(contracts):
    fake = FakeNotion()
    r1 = S.upsert_master(contracts, "DB1", "tok", req=fake.req)
    assert r1 == {"created": 68, "updated": 0, "failed": []}
    assert len(fake.pages) == 68
    # 同一契約を再投入 → 全件 update 経路・新規作成は起きない(冪等)。
    r2 = S.upsert_master(contracts, "DB1", "tok", req=fake.req)
    assert r2 == {"created": 0, "updated": 68, "failed": []}
    assert len(fake.pages) == 68  # ページは増えない


def test_upsert_master_property_shapes():
    fake = FakeNotion()
    contract = {
        "契約ID": "X社/田中太郎/" + S.PROD_BIZ,
        "取引先": "X社",
        "商品": S.PROD_BIZ,
        "エンドクライアント名": "田中太郎",
        "現行単価": 300000,
        "契約開始日": "2026-05-01",
        "契約終了月": "2026-06-01",
        "請求確認シートID": "page-xyz",
        "備考": "300,000円 田中太郎",
        "支払サイクル": "月払い",
        "ステータス": "有効",
        "期待明細数": 2,
    }
    S.upsert_master([contract], "DB1", "tok", req=fake.req)
    props = next(iter(fake.pages.values()))
    assert props["契約ID"]["title"][0]["text"]["content"].startswith("X社/田中太郎/")
    assert props["商品"]["select"]["name"] == S.PROD_BIZ
    assert props["ステータス"]["select"]["name"] == "有効"
    assert props["支払サイクル"]["select"]["name"] == "月払い"
    assert props["現行単価"]["number"] == 300000
    assert props["期待明細数"]["number"] == 2
    assert props["契約開始日"]["date"]["start"] == "2026-05-01"
    assert props["契約終了月"]["date"]["start"] == "2026-06-01"
    assert props["エンドクライアント名"]["rich_text"][0]["text"]["content"] == "田中太郎"
    assert props["請求確認シートID"]["rich_text"][0]["text"]["content"] == "page-xyz"


def test_upsert_master_omits_empty_optionals():
    fake = FakeNotion()
    contract = {
        "契約ID": "Y社//" + S.PROD_BIZ,
        "取引先": "Y社",
        "商品": S.PROD_BIZ,
        "エンドクライアント名": "",
        "現行単価": None,
        "契約開始日": None,
        "契約終了月": None,
        "請求確認シートID": None,
        "備考": "",
        "支払サイクル": None,       # 保留契約
        "ステータス": "保留",
        "期待明細数": 1,
    }
    S.upsert_master([contract], "DB1", "tok", req=fake.req)
    props = next(iter(fake.pages.values()))
    for omitted in ("エンドクライアント名", "支払サイクル", "現行単価",
                    "契約開始日", "契約終了月", "請求確認シートID"):
        assert omitted not in props
    assert props["ステータス"]["select"]["name"] == "保留"


def test_existing_contract_ids_paginates():
    # 既存 100件超を has_more/next_cursor で全ページ辿り、契約ID→page_id を漏れなく集める。
    def title(cid):
        return {"properties": {"契約ID": {"title": [{"plain_text": cid}]}}, "id": "pg-" + cid}

    pages = [
        {"results": [title("A")], "has_more": True, "next_cursor": "c1"},
        {"results": [title("B")], "has_more": False},
    ]
    seen_cursors = []

    def req(method, path, token, body=None):
        assert path.endswith("/query")
        seen_cursors.append(body.get("start_cursor"))
        return pages[len(seen_cursors) - 1]

    out = S._existing_contract_ids("DB1", "tok", req)
    assert out == {"A": "pg-A", "B": "pg-B"}
    assert seen_cursors == [None, "c1"]  # 2 ページ目は cursor 付きで取得


def test_existing_contract_ids_dedups_duplicate_page_id():
    # pagination が同一 page_id を重複返却しても 1 度だけ処理する (stale な契約ID で
    # 同じページを二重登録しない)。2 ページ目の pg-X は既処理なので無視される。
    def page(cid, pid):
        return {"properties": {"契約ID": {"title": [{"plain_text": cid}]}}, "id": pid}

    pages = [
        {"results": [page("A", "pg-X")], "has_more": True, "next_cursor": "c1"},
        {"results": [page("DUP", "pg-X"), page("B", "pg-Y")], "has_more": False},
    ]
    n = []

    def req(method, path, token, body=None):
        n.append(1)
        return pages[len(n) - 1]

    out = S._existing_contract_ids("DB1", "tok", req)
    # pg-X は 1 度だけ採用 → 重複返却の "DUP" は混入しない。
    assert out == {"A": "pg-X", "B": "pg-Y"}


def test_upsert_master_individual_failure_does_not_block_others():
    # 1 件の書込失敗 (HTTP400 等) で全体を止めず、failed に記録して後続を処理し続ける。
    seen_titles = []

    def req(method, path, token, body=None):
        if path.endswith("/query"):
            return {"results": [], "has_more": False}
        title = body["properties"]["契約ID"]["title"][0]["text"]["content"]
        seen_titles.append(title)
        if title.startswith("BAD"):
            raise RuntimeError("Notion POST /pages: HTTP 400 invalid property")
        return {"id": "pg-" + title}

    def c(cid):
        return {"契約ID": cid, "取引先": cid, "商品": S.PROD_BIZ,
                "ステータス": "有効", "期待明細数": 1, "備考": ""}

    contracts = [c("OK1"), c("BAD"), c("OK2")]
    out = S.upsert_master(contracts, "DB1", "tok", req=req)
    assert out["created"] == 2          # OK1 / OK2 は作成成功
    assert out["updated"] == 0
    assert len(out["failed"]) == 1
    assert out["failed"][0]["契約ID"] == "BAD"
    assert "400" in out["failed"][0]["error"]
    # 失敗後も 3 件目 (OK2) を処理している = 全体停止していない。
    assert seen_titles == ["OK1", "BAD", "OK2"]


def test_upsert_master_preserves_newlines_in_rich_text():
    # 備考 (確認内容) の改行(\n)を text content にそのまま保持して投入する。
    fake = FakeNotion()
    multiline = "1行目: 月額150,000円\n2行目: 初期費用300,000円\n3行目: 2026/6/8〜"
    contract = {
        "契約ID": "NL社//", "取引先": "NL社\n部署", "商品": S.PROD_BIZ,
        "エンドクライアント名": "", "ステータス": "有効", "期待明細数": 1,
        "備考": multiline,
    }
    S.upsert_master([contract], "DB1", "tok", req=fake.req)
    props = next(iter(fake.pages.values()))
    assert props["備考"]["rich_text"][0]["text"]["content"] == multiline
    assert "\n" in props["取引先"]["rich_text"][0]["text"]["content"]


def test_upsert_master_default_req_is_sink(monkeypatch):
    # req 未指定なら notion_invoice_sink._req を遅延 import して使う。
    import notion_invoice_sink as sink
    captured = []

    def fake_req(method, path, token, body=None):
        captured.append((method, path))
        if path.endswith("/query"):
            return {"results": [], "has_more": False}
        return {"id": "p1"}

    monkeypatch.setattr(sink, "_req", fake_req)
    out = S.upsert_master(
        [{"契約ID": "Z/", "取引先": "Z", "商品": S.PROD_BIZ, "ステータス": "有効",
          "期待明細数": 1, "備考": ""}],
        "DB1", "tok")
    assert out == {"created": 1, "updated": 0, "failed": []}
    assert ("POST", "/pages") in captured


# ---------------------------------------------------------------------------
# 期間ベースのサイクル判定 (ユーザー確定 2026-06-26)
#   確認内容『期間：A〜B』= 作業開始から1年の契約 → 年間系。商品で年間払い/年間一括更新を
#   出し分け、『利用料(2年目以降)』は月払いフェーズとして除外する。
# ---------------------------------------------------------------------------
def test_has_period_detects_period_line():
    assert S.has_period("更新確認\n期間：2025/7/31〜2026/7/30")
    assert S.has_period("初期300,000円\n150,000*12=1,800,000\n期間：2026/6/24〜2027/6/23")
    assert S.has_period("期間: 2026/3/25〜2027/3/24")   # 半角コロン
    assert not S.has_period("300,000円\n水元慎司")       # 期間なし(業務委託費)
    assert not S.has_period("")
    assert not S.has_period(None)


def test_parse_period_start():
    assert S.parse_period_start("期間：2025/7/31〜2026/7/30") == "2025-07-31"
    assert S.parse_period_start("期間：2026/6/8〜2027/6/7") == "2026-06-08"
    assert S.parse_period_start("期間：2026/12〜2027/12") == "2026-12-01"  # 日なし→月初
    assert S.parse_period_start("月額150,000円") is None                  # 期間なし→None
    assert S.parse_period_start(None) is None
    # YYMM〜YYMM 形式(期間：2606〜2608)は開始 2606 を月初 2026-06-01 へ反映(ユーザー確定2026-06-27)。
    assert S.parse_period_start("5/19契約書未締結\n期間：2606〜2608") == "2026-06-01"
    assert S.parse_period_start("期間：2512〜2603") == "2025-12-01"
    # YYMM は年間化トリガー(has_period)には含めない(短期レンジでありうるため。開始日補完のみ)。
    assert S.has_period("期間：2606〜2608") is False
    assert S.has_period("期間：2026/6/8〜2027/6/7") is True


def test_infer_cycle_period_priority_over_monthly_keyword():
    # ThinkTank に『月額払い』表記と期間が併記されても、期間優先で年間一括更新(月払いにしない)。
    cyc = S.infer_cycle("月額払い：150,000\n期間：2026/6/24〜2027/6/23",
                        S.PROD_THINKTANK, 150000, {})
    assert cyc == "年間一括更新"
    # 利用料(1年目)+期間 → 年間払い(初年度一括→翌年月額)。
    cyc = S.infer_cycle("50,000*12\n期間：2026/6/1〜2027/5/31", S.PROD_RIYO_Y1, 50000, {})
    assert cyc == "年間払い"
    # 利用料(2年目以降) は定義上すでに月払いフェーズ。期間があっても月払いを維持。
    cyc = S.infer_cycle("期間：2026/6/5〜2027/6/4", S.PROD_RIYO_Y2, 50000, {})
    assert cyc == "月払い"
    # 期間なしの業務委託費 → 月払い(従来通り・回帰なし)。
    assert S.infer_cycle("300,000円\n水元慎司", S.PROD_BIZ, 300000, {}) == "月払い"


def test_build_contracts_fills_start_from_period_when_column_empty():
    # 契約開始日列が空でも、確認内容『期間：A〜B』の開始日 A で補完される(年払い elapsed 起点)。
    rows = [{
        "取引先": "テスト株式会社",
        "商品": "100億ThinkTank利用料",
        "確認内容": "初期300,000円\n期間：2026/6/8〜2027/6/7",
        "契約開始日": "",      # 列は空 → 期間開始で補完されるべき
        "契約終了月": "",
        "page_id": "pid-1",
    }]
    contracts = S.build_contracts(rows, mf_index=None, target_ym="2606")
    assert len(contracts) == 1
    assert contracts[0]["契約開始日"] == "2026-06-08"   # 期間開始で補完
    assert contracts[0]["支払サイクル"] == "年間一括更新"


def test_no_anchor_falls_back_to_monthly():
    # ユーザー確定(2026-06-27): 期間も契約開始日も無い契約は月払い前提(毎月必ず請求が発生し
    # MF に反映されるべき)。年間/分割等の推定はアンカー(期間/契約開始日)が無いと月払いへ降格し、
    # REVIEW_DATA_INCOMPLETE(要確認)へ落とさない。
    # 利用料(1年目)=本来年間払いだが、期間も契約開始日も無いので月払いへ降格。
    rows_annual = [{"取引先": "アンカー無株式会社", "商品": "チイキズカン利用料（1年目）",
                    "確認内容": "50,000円", "契約開始日": "", "契約終了月": "", "page_id": "p1"}]
    c = S.build_contracts(rows_annual, mf_index=None, target_ym="2606")[0]
    assert c["契約開始日"] is None
    assert c["支払サイクル"] == "月払い"
    # 契約開始日があれば従来通り年間払いのまま(降格は「アンカー無し」限定)。
    rows_with_start = [{"取引先": "開始日有株式会社", "商品": "チイキズカン利用料（1年目）",
                        "確認内容": "50,000円", "契約開始日": "2026-06-01", "契約終了月": "", "page_id": "p2"}]
    c2 = S.build_contracts(rows_with_start, mf_index=None, target_ym="2606")[0]
    assert c2["支払サイクル"] == "年間払い"

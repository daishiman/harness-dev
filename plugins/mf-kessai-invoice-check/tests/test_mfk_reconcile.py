#!/usr/bin/env python3
"""lib/mfk_reconcile.py の golden 回帰テスト (2606 実データ固定 + 純関数ユニット)。

golden 入力 (tests/fixtures/):
  - notion_2606.json        : 請求確認シート 95 行 (DB1 移行前の旧シート形)
  - mf_2606.json            : MF掛け払い 対象月取引実績 82 顧客 (会社名解決済・参照専用)
  - cycle_inventory_2606.json: 契約別サイクル棚卸し 68 契約 (design wi22zpkq2 の
                              validation.inventory.contracts を抽出。DB1『支払サイクル』
                              列の seed)。

golden 値の出所は engine 出力ではなく、確定設計 (design wi22zpkq2) と実データ検証
(inventory / falsematch suspects / orphans 43) である。各 assert は『あるべき判定』を
仕様・実データから導いており、engine 出力に合わせて書き換えていない (循環防止)。
実装と食い違った箇所は engine 側のバグとして lib/mfk_reconcile.py を修正した
(詳細はリポジトリ作業ログ参照): _company_match の 2文字包含→3文字包含 (児島→鹿児島の
偽 match 封鎖), 年間 2 系の lump-first 判定 (発行タイミングずれ吸収), _canonical_cycle の
case a/b 判別, quantity_downgrade を月次限定 (年額一括の不当降格防止)。
"""
import json
import os

import pytest

import mfk_reconcile as R

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
TARGET = "2606"


def _load(name):
    with open(os.path.join(FX, name), encoding="utf-8") as fh:
        return json.load(fh)


def _cycle_inventory():
    """cycle_inventory (DB1『支払サイクル』列の seed) を返す。

    fixture は design wi22zpkq2 の inventory.contracts を改変せず忠実抽出したもの。
    その中で ツネマツ業務委託『45,000円/件 澤田聖陽』は構造化フィールド上 inferred_cycle="不明"
    だが、design の prose は『ツネマツ業務委託 45,000円/件 (従量)』と明記しており、45,000円/件
    という単価×件数の課金形態は従量(都度)シグナルそのものである。実 DB1 では人手が支払サイクル列を
    従量(都度)に確定する(確定仕様『支払サイクルは契約ごとに列で明示・推測しない』)。ここではその
    DB1 人手確定をテストコード側で明示的に再現する(extract した正本 fixture は汚さない)。
    """
    inv = _load("cycle_inventory_2606.json")
    for c in inv:
        if (c.get("torihiki") == "ツネマツガス株式会社"
                and c.get("endclient") == "澤田聖陽"
                and c.get("amount") == "45,000/件"):
            c["inferred_cycle"] = "従量"  # DB1 人手確定: 不明 → 従量(都度)
    return inv


@pytest.fixture(scope="module")
def reconciled():
    """golden 入力を attach_cycle→build_mf_index→reconcile した結果 (双方向)。"""
    notion = _load("notion_2606.json")
    mf = _load("mf_2606.json")
    inv = _cycle_inventory()
    rows_wc = R.attach_cycle(notion, inv)
    mf_index = R.build_mf_index(mf)
    return R.reconcile(rows_wc, mf_index, TARGET)


# --- golden 選択ヘルパ (NFKC 正規化で取引先/確認内容を部分一致。生 substring は
#     macOS 由来の合成済/未合成カナで取りこぼすため normalize 経由で堅牢化) -------------
def _norm_in(needle, hay):
    return R.normalize(needle) in R.normalize(hay or "")


def _find(rows, torihiki=None, kakunin=None, shohin=None):
    out = []
    for r in rows:
        if torihiki and not _norm_in(torihiki, r.get("取引先", "")):
            continue
        if kakunin and not _norm_in(kakunin, r.get("確認内容", "")):
            continue
        if shohin and shohin not in (r.get("商品") or ""):
            continue
        out.append(r)
    return out


def _verdicts(rows):
    return {r["verdict"] for r in rows}


def test_expected_categories_include_aggregated_source_products():
    contract = {
        "商品": "チイキズカン業務委託費",
        "確認内容": "100,000円 山田太郎",
        # 集約で代表商品(商品)に潰れても、集約元の商品集合 _source_products から期待カテゴリを復元。
        "_source_products": ["チイキズカン業務委託費", "100億ThinkTank利用料"],
    }
    assert R._expected_categories(contract) >= {"biz", "thinktank", "trial"}


# ============================================================================
# 1. golden 全体スナップショット (回帰ロック)
# ============================================================================
def test_row_and_orphan_counts(reconciled):
    """95 行 (旧シート全行を展開) + orphan 43 件。"""
    assert len(reconciled["rows"]) == 95
    assert len(reconciled["orphans"]) == 43


def test_summary_snapshot(reconciled):
    """verdict 分布スナップショット。個別 golden を満たした上での回帰検知用ロック。"""
    assert reconciled["summary"] == {
        "MATCH_MONTHLY": 16,
        "MATCH_ANNUAL": 3,
        "MATCH_ENDED_FINAL": 2,
        "SUPPRESS_ANNUAL": 12,
        "GAP": 15,
        "REVIEW_QTY_MISMATCH": 31,
        "REVIEW_AMOUNT_MISMATCH": 5,
        "REVIEW_AMOUNT_TYPO": 3,
        "REVIEW_METERED": 1,
        "REVIEW_NO_AMOUNT": 4,
        "REVIEW_ANNUAL_BILLING_MONTH": 2,
        "REVIEW_DATA_INCOMPLETE": 1,
        "ORPHAN": 43,
    }


# ============================================================================
# 2. 偽陰性是正 (F1 + J1): 岩本鉄工所/大橋諒祐 は他社請求を証跡にできず数量差へ
# ============================================================================
def test_iwamoto_false_negative_to_qty_mismatch(reconciled):
    """株式会社岩本鉄工所 の大橋諒祐/400,000 2 行は REVIEW_QTY_MISMATCH。

    実データ (falsematch suspects 2 件): 岩本は大橋諒祐の契約 2 行に対し自社 MF 供給 1 件のみ。
    name-global 照合だと あさかわシステムズ の同名同額請求を証跡に MATCH 化していた (=漏れ見逃し)。
    取引先境界 (J1) + 契約ID境界の数量集計 (F1) で 2 行とも数量差へ降格されるのが正。
    """
    rows = _find(reconciled["rows"], torihiki="岩本鉄工所")
    assert len(rows) == 2
    assert _verdicts(rows) == {"REVIEW_QTY_MISMATCH"}
    for r in rows:
        assert r.get("_expected", 0) > r.get("_supply", 0)


def test_asakawa_is_genuine_match(reconciled):
    """あさかわシステムズ は自社の大橋諒祐/400,000 請求を保有し正常 MATCH_MONTHLY。"""
    rows = _find(reconciled["rows"], torihiki="あさかわシステムズ", kakunin="大橋諒祐")
    assert rows, "あさかわシステムズ/大橋諒祐 行が見つからない"
    assert any(r["verdict"] == "MATCH_MONTHLY" for r in rows)
    matched = [r for r in rows if r["verdict"] == "MATCH_MONTHLY"][0]
    assert R.normalize(matched["evidence"]["cust"]) == R.normalize("あさかわシステムズ株式会社")


# ============================================================================
# 3. 金額差 (B1): 名寄せ MF 供給ありで金額のみ不一致は GAP でなく REVIEW_AMOUNT_MISMATCH
# ============================================================================
def test_torizen_amount_mismatch_not_gap(reconciled):
    """株式会社鳥善/松田典久 (確認 357,000 vs MF 215,000) は REVIEW_AMOUNT_MISMATCH。"""
    rows = _find(reconciled["rows"], torihiki="鳥善")
    assert rows
    assert _verdicts(rows) == {"REVIEW_AMOUNT_MISMATCH"}
    # GAP (供給皆無) に落ちていないこと = B1 の核
    assert "GAP" not in _verdicts(rows)


def test_category_fallback_keeps_company_supply_visible(reconciled):
    """カテゴリがずれても会社境界内の供給を捨てず、GAP ではなく数量差として可視化する。"""
    rows = _find(reconciled["rows"], torihiki="モトヤ", kakunin="玉井修司",
                 shohin="100億ThinkTank")
    assert rows
    assert _verdicts(rows) == {"REVIEW_QTY_MISMATCH"}
    assert all(r["actual_amount"] == 330000 for r in rows)
    assert all(r["supply_state"] == "active" for r in rows)


# ============================================================================
# 4. 終了月の最終請求 (月またぎ発行): 終了月M の最終請求書は M+1 に発行されるのが正常。
#    終了月〜終了月+1 の MF 請求は MATCH_ENDED_FINAL (発行確認OK・過剰請求にしない)。
# ============================================================================
def test_ended_final_invoice_not_overbilled(reconciled):
    """扶桑畜産 (終了2605, MF2606=終了月+1) と 森信建設 (終了2606=当月) は MATCH_ENDED_FINAL。

    終了月の役務は翌月に請求書が発行される(月またぎ発行)。終了月+1 までの MF 請求は
    最終請求書で過剰請求ではない。過剰請求 (REVIEW_ENDED_BUT_BILLED) は終了月+2 以降のみ。
    """
    fuso = _find(reconciled["rows"], torihiki="扶桑畜産")
    mori = _find(reconciled["rows"], torihiki="森信建設")
    assert _verdicts(fuso) == {"MATCH_ENDED_FINAL"}
    assert _verdicts(mori) == {"MATCH_ENDED_FINAL"}
    assert fuso[0]["evidence"] is not None  # 最終請求書の MF 証跡
    # 過剰請求(終了後請求)には落とさない = ユーザー指摘の誤検出是正。
    assert "REVIEW_ENDED_BUT_BILLED" not in (_verdicts(fuso) | _verdicts(mori))


def test_overbilling_only_after_final_invoice_month():
    """合成: 終了2604 で 2606(終了月+2)に MF 実績 → REVIEW_ENDED_BUT_BILLED(真の過剰請求)。"""
    mf_index = R.build_mf_index(_load("mf_2606.json"))
    contract = {
        "契約ID": "テスト過剰/業務委託費", "取引先": "あさかわシステムズ株式会社",
        "商品": "チイキズカン業務委託費", "エンドクライアント名": "大橋諒祐",
        "現行単価": 400000, "支払サイクル": R.CADENCE_MONTHLY,
        "契約開始日": "2501", "契約終了月": "2604", "ステータス": "終了", "期待明細数": 1,
    }
    rows = R.reconcile([contract], mf_index, "2606")["rows"]
    # あさかわは自社 MF 供給(大橋諒祐/400,000)を持つため終了月+2 の請求は過剰請求。
    assert rows and rows[0]["verdict"] == "REVIEW_ENDED_BUT_BILLED"


def test_ended_final_window_boundary():
    """境界: 終了月当月(M)・翌月(M+1)=MATCH_ENDED_FINAL / M+2=REVIEW_ENDED_BUT_BILLED。"""
    mf_index = R.build_mf_index(_load("mf_2606.json"))
    base = {
        "契約ID": "境界/業務委託費", "取引先": "あさかわシステムズ株式会社",
        "商品": "チイキズカン業務委託費", "エンドクライアント名": "大橋諒祐",
        "現行単価": 400000, "支払サイクル": R.CADENCE_MONTHLY, "ステータス": "終了",
        "契約開始日": "2501", "期待明細数": 1,
    }
    # MF 実績は 2606 発行。終了月=2606(当月) / 2605(翌月が当月) → MATCH_ENDED_FINAL。
    for end in ("2606", "2605"):
        rows = R.reconcile([{**base, "契約終了月": end}], mf_index, "2606")["rows"]
        assert rows[0]["verdict"] == "MATCH_ENDED_FINAL", f"終了月={end}"
    # 終了月=2604 (=当月-2) → 過剰請求。
    rows = R.reconcile([{**base, "契約終了月": "2604"}], mf_index, "2606")["rows"]
    assert rows[0]["verdict"] == "REVIEW_ENDED_BUT_BILLED"


# ============================================================================
# 5. 終了前正常: 終了月 (2607) > 対象月 (2606) は終了扱いせず当月の現役契約として展開
# ============================================================================
def test_eme_active_before_end(reconciled):
    """株式会社EME/IDENTITY (終了2607) は 2606 で終了扱いされず、自社 MF 供給を証跡に当月展開。

    『終了前正常』= 終了月が将来 (2607>2606) ゆえ SUPPRESS_ENDED / REVIEW_ENDED_BUT_BILLED に
    ならないこと (扶桑/森信 との対比) が本ケースの核。EME は会社境界で自社 380,000/IDENTITY を
    引き当て (シロッコの IDENTITY 450,000 を誤流用しない)。

    注: EME は旧シート上 2 行 (一方に『請求なし(2607終了)』注記) で、raw 行から自動算出した
    期待明細数では岩本と構造同型 (2 行 vs 自社供給 1 件) のため REVIEW_QTY_MISMATCH が出る。
    falsematch ground-truth は岩本のみを偽陰性として挙げ EME は単一契約と扱うため、本来は
    MATCH 相当 (実 DB1 では人手確定の期待明細数=1 で MATCH 化する)。raw 行 golden では
    『終了境界が正しく現役判定される + 自社供給を引き当てる』を load-bearing assert とする。
    """
    rows = _find(reconciled["rows"], torihiki="株式会社EME")
    assert len(rows) == 2
    # 終了境界: 将来終了は現役。終了系 verdict にも GAP にもならない。
    assert _verdicts(rows).isdisjoint({"SUPPRESS_ENDED", "REVIEW_ENDED_BUT_BILLED", "GAP"})
    # 自社 (EME) の MF 供給を引き当てている (他社流用でない)
    assert all(r.get("evidence") for r in rows)
    assert all(R.normalize(r["evidence"]["cust"]) == R.normalize("株式会社EME") for r in rows)
    # 将来終了行は確かに終了月 2607 を持つ
    ended_row = [r for r in rows if (r.get("契約終了月") or "").strip() == "2607"]
    assert ended_row and ended_row[0]["verdict"] != "SUPPRESS_ENDED"


# ============================================================================
# 6. 従量(都度) (H1): 期待額が件数依存で不定 → 常に REVIEW_METERED
# ============================================================================
def test_metered_review(reconciled):
    """ツネマツガス『45,000円/件 澤田聖陽』(従量) は REVIEW_METERED。"""
    rows = _find(reconciled["rows"], torihiki="ツネマツ", kakunin="45,000円/件")
    assert len(rows) == 1
    assert rows[0]["verdict"] == "REVIEW_METERED"
    assert rows[0]["支払サイクル"] == R.CADENCE_METERED


# ============================================================================
# 7. 年間 2 系 (E1): 当月一括検出=MATCH_ANNUAL / 当月開始で一括無=REVIEW_ANNUAL_BILLING_MONTH
# ============================================================================
def test_annual_caseb_lump_match(reconciled):
    """ハタダ (チイキズカン利用料 初年度一括 qty12 ¥600,000, 年間払い) は MATCH_ANNUAL。"""
    rows = _find(reconciled["rows"], torihiki="ハタダ")
    assert len(rows) == 1
    r = rows[0]
    assert r["支払サイクル"] == R.CADENCE_ANNUAL  # case b
    assert r["verdict"] == "MATCH_ANNUAL"
    ev = r["evidence"]
    assert ev["amount"] == 600000 and (ev.get("qty") or 0) >= R._ANNUAL_LUMP_QTY


def test_annual_casea_renewal_lump_match(reconciled):
    """シティプラス (100億ThinkTank 更新一括 qty12 ¥1.8M, 年間一括更新) は MATCH_ANNUAL。"""
    rows = _find(reconciled["rows"], torihiki="シティプラスホールディングス")
    assert len(rows) == 1
    r = rows[0]
    assert r["支払サイクル"] == R.CADENCE_ANNUAL_RENEWAL  # case a
    assert r["verdict"] == "MATCH_ANNUAL"
    assert r["evidence"]["amount"] == 1800000


def test_annual_billing_month_review_when_started_this_month(reconciled):
    """当月 (2606) 開始 (elapsed==0) で MF 一括未検出の年間契約は REVIEW_ANNUAL_BILLING_MONTH。

    広島ドラゴンフライズ (case a) / 広島アルミ (case b) はともに 2026/6/24 開始で当月 MF 無 →
    GAP (発行漏れ断定) に落とさず保留する。
    """
    drag = _find(reconciled["rows"], torihiki="広島ドラゴンフライズ")
    alum = _find(reconciled["rows"], torihiki="広島アルミニウム")
    assert _verdicts(drag) == {"REVIEW_ANNUAL_BILLING_MONTH"}
    assert _verdicts(alum) == {"REVIEW_ANNUAL_BILLING_MONTH"}
    # ちょうど 2 件 (E1 保留はこの 2 契約のみ)
    rabm = [r for r in reconciled["rows"] if r["verdict"] == "REVIEW_ANNUAL_BILLING_MONTH"]
    assert len(rabm) == 2


# ============================================================================
# 8. 発行漏れ (GAP): 名寄せ MF 供給が皆無の当月期待 (更新窓外でなく当月期待のもの)
# ============================================================================
def test_unbilled_gaps(reconciled):
    """MF 未発行の当月期待 業務委託費は GAP。"""
    harada = _find(reconciled["rows"], torihiki="原田フーズ", kakunin="水元慎司")
    kindai = _find(reconciled["rows"], torihiki="近代プラント", kakunin="内野豪")
    iseshima = _find(reconciled["rows"], torihiki="伊勢志摩冷凍", shohin="業務委託費")
    assert _verdicts(harada) == {"GAP"}
    assert _verdicts(kindai) == {"GAP"}
    assert _verdicts(iseshima) == {"GAP"}


# ============================================================================
# 9. orphan (逆方向): MF 実績ありマスタ未登録
# ============================================================================
def test_orphans_members_and_shape(reconciled):
    """orphan 43 件に エムスクエア・ラボ / 高知精工メッキ を含み、全件 verdict=ORPHAN。"""
    orphans = reconciled["orphans"]
    assert len(orphans) == 43
    custs = {R.normalize(o["cust"]) for o in orphans}
    assert R.normalize("株式会社エムスクエア・ラボ") in custs
    assert R.normalize("高知精工メッキ株式会社") in custs
    assert all(o["verdict"] == "ORPHAN" for o in orphans)
    assert all(o["direction"] == "逆方向orphan" for o in orphans)
    assert all(o["amount"] > 0 and o["services"] for o in orphans)


def test_kojima_not_falsely_matched(reconciled):
    """児島株式会社 は 鹿児島堀口製茶 への偶発包含で吸収されず orphan に残る (_company_match 3 文字化)。"""
    custs = {R.normalize(o["cust"]) for o in reconciled["orphans"]}
    assert R.normalize("児島株式会社") in custs


# ============================================================================
# 10. verdict 網羅 (parity): classify+orphan が emit する全 verdict ⊆ verdict-mapping.json
# ============================================================================
def test_emitted_verdicts_subset_of_mapping(reconciled):
    """golden で実際に emit される verdict が SSOT (verdict-mapping.json) に全て定義済み。"""
    mapping = R.load_verdict_mapping()
    assert mapping, "verdict-mapping.json が読めていない"
    emitted = {r["verdict"] for r in reconciled["rows"]}
    emitted |= {o["verdict"] for o in reconciled["orphans"]}
    missing = emitted - set(mapping.keys())
    assert not missing, f"mapping 未定義の verdict: {missing}"


# ============================================================================
# 純関数ユニット (golden e2e が通らない分岐・ヘルパのカバレッジ)
# ============================================================================
def _mf_index(customers):
    return R.build_mf_index({"customers": customers})


def _line(amount, desc="チイキズカン業務委託費", qty=1, billing_id="B1", unit_price=None):
    return {"amount": amount, "desc": desc, "qty": qty,
            "billing_id": billing_id, "unit_price": unit_price}


def test_normalize_nfkc_and_corp_strip():
    assert R.normalize("株式会社　あさかわ・システムズ") == "あさかわシステムズ"
    assert R.normalize("ﾃｽﾄ 様") == "テスト"
    assert R.normalize("") == "" and R.normalize(None) == ""


def test_parse_amounts_primary_and_typo():
    primary, typo = R.parse_amounts("50,0000円")  # 区切り桁異常
    assert 500000 in primary and 50000 in typo
    primary2, typo2 = R.parse_amounts("357,000円 松田典久")
    assert primary2 == [357000] and typo2 == []
    assert R.parse_amounts("更新確認のみ") == ([], [])


def test_extract_names_and_paren():
    names = R.extract_names("株式会社EME", "380,000円 株式会社IDENTITY")
    assert any("IDENTITY" in n for n in names)
    assert R.mf_paren_name("チイキズカン業務委託費（大橋諒祐様 2026年5月分）") == "大橋諒祐"
    assert R.mf_paren_name("括弧なし明細") is None


def test_category_branches():
    assert R.category("立替経費") == "tatekae"
    assert R.category("チイキズカン業務委託費") == "biz"
    assert R.category("初期導入費用") == "init"
    assert R.category("トライアル利用") == "trial"
    assert R.category("100億ThinkTankサービス利用料") == "thinktank"
    assert R.category("チイキズカンサービス利用料") == "riyo"
    assert R.category("リーダー研修") == "training"
    assert R.category("謎の明細") == "other"
    # 100億ThinkTankトライアルは category() では trial (評価順でトライアル優先・現状挙動を固定)。
    assert R.category("100億ThinkTankトライアルサービス利用料") == "trial"


def test_expected_categories_thinktank_allows_trial():
    # ThinkTank契約の期待categoryに trial を許容し、MF desc が「トライアル」で category=trial に
    # なる実発行済み明細を no_supply 誤判定(偽GAP)しない (2605 ひふみ/セント/特殊高所技術 の回帰防止)。
    cats = R._expected_categories({"商品": "100億ThinkTank利用料", "確認内容": "50,000円"})
    assert "thinktank" in cats and "trial" in cats
    # ThinkTank を含まない契約には trial を足さない (純trial許容の漏れ防止)。
    cats2 = R._expected_categories({"商品": "チイキズカン業務委託費", "確認内容": "70,000円"})
    assert "trial" not in cats2


def test_ym_int_and_months_elapsed():
    assert R.ym_int("2606") == R.ym_int("2026-06") == R.ym_int("2026-06-24")
    assert R.ym_int("2613") is None and R.ym_int("") is None
    assert R.months_elapsed("2026-05", "2606") == 1
    assert R.months_elapsed(None, "2606") is None


def test_company_match_threshold():
    """完全一致は許容、3 文字未満の包含は拒否 (児島 ⊄ 鹿児島堀口製茶)。"""
    assert R._company_match("岩本鉄工所", "岩本鉄工所") is True
    assert R._company_match("あさかわ", "あさかわシステムズ") is True  # 4 文字包含
    assert R._company_match("児島", "鹿児島堀口製茶") is False  # 2 文字包含は拒否
    assert R._company_match("a", "abc") is False  # 短すぎ


def test_company_match_has_no_hardcoded_company_alias(reconciled):
    """C14 回帰: _company_match は完全一致/3文字以上包含のみで判定し、個社の会社名を
    frozenset/条件分岐/読み替え表へハードコードしない(対症療法の復活を機械的に担保する)。
    name-drift(日本語⇄英語表記等)の一般解は MF顧客ID carry(C02)であり、
    _company_match への個社リテラル追加ではない。

    検査は英単語 'alias' の proxy ではなく、撤去対象だった実症状 3 社の会社名リテラル
    (2nd Community/細野/paws とその表記ゆれ)が照合エンジンのソースへ焼かれていないという
    真の不変条件で行う(Goodhart 防止: 説明用の docstring 語ではなく実リテラルを見る)。"""
    assert not hasattr(R, "_COMPANY_ALIAS_GROUPS")
    assert not hasattr(R, "_COMPANY_ALIAS_BY_NAME")
    assert not hasattr(R, "_company_alias_group")
    import inspect
    # 撤去対象だった RETRACT-1 の個社会社名リテラル(表記ゆれ含む)。
    forbidden_literals = [
        "2ndcommunity", "secondcommunity", "セカンドコミュニティ",
        "hosono", "細野", "paws", "パウズ", "ポーズ",
    ]
    for fn in (R._company_match, R._boundary_customers, R.find_mf_match):
        src = inspect.getsource(fn).lower()
        for lit in forbidden_literals:
            assert lit.lower() not in src, (
                f"{fn.__name__} に個社会社名リテラル {lit!r} がハードコード (C14 違反)")
    # 撤去後も既存の正当な照合(fixture 実データ)が緑であることを併せて担保する。
    assert reconciled["rows"], "golden fixture の既存照合が壊れていないこと"


def test_canonical_cycle_two_annual_systems():
    """年間一括 2 系の判別: 更新も一括=case a, 初年度のみ→月額=case b。"""
    assert R._canonical_cycle("年間一括-更新も一括") == R.CADENCE_ANNUAL_RENEWAL
    assert R._canonical_cycle("年間一括-初年度のみ→月額") == R.CADENCE_ANNUAL
    assert R._canonical_cycle("年間払い") == R.CADENCE_ANNUAL
    assert R._canonical_cycle("従量") == R.CADENCE_METERED
    assert R._canonical_cycle("分割") == R.CADENCE_SPLIT
    assert R._canonical_cycle("隔月") == R.CADENCE_BIMONTHLY
    assert R._canonical_cycle("月払い") == R.CADENCE_MONTHLY
    assert R._canonical_cycle("単発") == R.CADENCE_ONESHOT
    assert R._canonical_cycle("不明") == ""


def test_contract_id_key_and_name_match():
    c = {"取引先": "株式会社EME", "エンドクライアント名": "株式会社IDENTITY",
         "商品": "チイキズカン業務委託費", "枝番": ""}
    key = R.contract_id_key(c)
    assert key[0] == R.normalize("EME") and key[1] == R.normalize("IDENTITY")
    assert R.name_match({"あさかわ"}, {"あさかわシステムズ"}) is True
    assert R.name_match({"a"}, {"b"}) is False


def test_oneshot_cycle_branches():
    mfi = _mf_index({"C": {"name": "テスト商事", "lines": [_line(100000)]}})
    base = {"取引先": "テスト商事", "商品": "P", "確認内容": "100,000円",
            "支払サイクル": R.CADENCE_ONESHOT, "契約終了月": ""}
    rows = R.classify([dict(base, 契約開始日="2606")], mfi, "2606")  # elapsed 0
    assert rows[0]["verdict"] == "MATCH_MONTHLY"
    rows2 = R.classify([dict(base, 契約開始日="2605")], mfi, "2606")  # elapsed 1
    assert rows2[0]["verdict"] == "SUPPRESS_ONESHOT"


def test_split_cycle_branches():
    mfi = _mf_index({"C": {"name": "分割商事", "lines": [_line(50000)]}})
    base = {"取引先": "分割商事", "商品": "P", "確認内容": "50,000円",
            "支払サイクル": R.CADENCE_SPLIT, "分割回数": 3, "契約終了月": ""}
    active = R.classify([dict(base, 契約開始日="2605")], mfi, "2606")  # elapsed 1 < 3
    assert active[0]["verdict"] == "MATCH_MONTHLY"
    done = R.classify([dict(base, 契約開始日="2603")], mfi, "2606")  # elapsed 3 >= 3
    assert done[0]["verdict"] == "SUPPRESS_OFFMONTH"


def test_bimonthly_cycle_branches():
    """隔月は開始月パリティ (elapsed%2==start_idx%2) で 1 ヶ月おきに請求月。

    開始 2605 (idx 偶数) を基準に elapsed 偶数月が請求月 → 2607 (elapsed 2) は請求、
    2606 (elapsed 1) は非請求 (frozen mfk_invoice_diff の絶対パリティ仕様と一致)。
    """
    mfi = _mf_index({"C": {"name": "隔月商事", "lines": [_line(70000)]}})
    base = {"取引先": "隔月商事", "商品": "P", "確認内容": "70,000円",
            "支払サイクル": R.CADENCE_BIMONTHLY, "契約開始日": "2605", "契約終了月": ""}
    bill = R.classify([dict(base)], mfi, "2607")  # elapsed 2 (請求月)
    assert bill[0]["verdict"] == "MATCH_MONTHLY"
    off = R.classify([dict(base)], mfi, "2606")  # elapsed 1 (非請求月)
    assert off[0]["verdict"] == "SUPPRESS_OFFMONTH"


def test_suppress_ended_when_no_mf():
    """終了根拠あり(確認内容に終了注記)+終了月<=対象月+自社 MF 無 → SUPPRESS_ENDED(対象外)。"""
    mfi = _mf_index({"C": {"name": "他社", "lines": [_line(1)]}})
    c = {"取引先": "撤退商事", "商品": "P", "確認内容": "90,000円 請求なし（2605終了）",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "2501", "契約終了月": "2605"}
    rows = R.classify([c], mfi, "2606")  # 終了済 (2605<=2606), 終了根拠あり, 自社 MF 無
    assert rows[0]["verdict"] == "SUPPRESS_ENDED"


def test_ended_no_basis_becomes_review():
    """契約終了月に値があるが確認内容に終了根拠が無い → REVIEW_ENDED_NO_BASIS(要確認)。

    根拠なき終了月(レガシー/誤入力の残存値)で SUPPRESS_ENDED に倒すと継続契約の発行漏れを
    『対象外(灰・警告なし)』で隠す。終了根拠が無い終了月は要確認で可視化する(列値は非破壊)。
    保留(REVIEW_PENDING)を要確認へ昇格するのと対称 (ユーザー確定 2026-06-30)。
    """
    mfi = _mf_index({"C": {"name": "他社", "lines": [_line(1)]}})
    c = {"取引先": "継続商事", "商品": "P", "確認内容": "90,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "2501", "契約終了月": "2605"}
    rows = R.classify([c], mfi, "2606")  # 終了月2605<=2606 だが終了根拠なし・自社 MF 無
    assert rows[0]["verdict"] == "REVIEW_ENDED_NO_BASIS"
    assert "終了根拠なし" in rows[0]["warning"]


def test_annual_caseb_migrates_to_monthly_after_12():
    """年間払い elapsed>=12 は月額へ移行し当月 MF を月次照合する。"""
    mfi = _mf_index({"C": {"name": "年契商事", "lines": [_line(50000)]}})
    c = {"取引先": "年契商事", "商品": "P", "確認内容": "50,000円",
         "支払サイクル": R.CADENCE_ANNUAL, "契約開始日": "2505", "契約終了月": ""}  # elapsed 13
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "MATCH_MONTHLY"


def test_data_incomplete_when_non_monthly_without_start(reconciled):
    """非月払いサイクルで契約開始日が空欄 → REVIEW_DATA_INCOMPLETE (K1, 山翠舎=分割)。"""
    rows = _find(reconciled["rows"], torihiki="山翠舎")
    assert rows and rows[0]["verdict"] == "REVIEW_DATA_INCOMPLETE"
    assert rows[0]["支払サイクル"] in R.NON_MONTHLY_CYCLES


def test_cross_client_evidence_blocks_false_match():
    """会社境界に供給が無く同名エンドクライアントが別会社で請求 → GAP + 証跡 (MATCH 化しない)。"""
    mfi = _mf_index({
        "B": {"name": "ビー商事", "lines": [_line(60000, "業務委託費（山田太郎様 2026年5月分）")]},
    })
    c = {"取引先": "エー商事", "商品": "P", "確認内容": "60,000円 山田太郎",
         "エンドクライアント名": "山田太郎", "支払サイクル": R.CADENCE_MONTHLY,
         "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "GAP"
    assert rows[0].get("_cross_client") is not None
    assert R.normalize(rows[0]["_cross_client"]["cust"]) == R.normalize("ビー商事")


def test_find_mf_match_modes():
    mfi = _mf_index({"C": {"name": "モード商事", "lines": [_line(80000)]}})
    c = {"取引先": "モード商事", "商品": "P", "確認内容": "80,000円"}
    assert R.find_mf_match(c, mfi, mode="monthly")["status"] == "match"
    assert R.find_mf_match(c, mfi, mode="presence")["status"] == "match"
    empty = {"取引先": "未登録商事", "商品": "P", "確認内容": "80,000円"}
    assert R.find_mf_match(empty, mfi, mode="presence")["status"] == "no_supply"
    assert R.find_mf_match(empty, mfi, mode="monthly")["status"] == "no_supply"


def test_aggregated_billing_line_matches_multiple_sheet_rows():
    """同一契約の複数シート行が MF 側 1 明細に合算されても発行済みとして扱う。"""
    mfi = _mf_index({
        "C": {
            "name": "集約商事",
            "lines": [_line(200000, "チイキズカン業務委託費（山田太郎様 2026年6月分）")],
        }
    })
    c = {
        "契約ID": "集約商事/山田太郎/P",
        "取引先": "集約商事",
        "商品": "P",
        "確認内容": "100,000円 山田太郎",
        "エンドクライアント名": "山田太郎",
        "支払サイクル": R.CADENCE_MONTHLY,
        "現行単価": 100000,
        "期待明細数": 2,
        "契約開始日": "",
        "契約終了月": "",
    }
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "MATCH_MONTHLY"
    assert rows[0]["evidence"]["_aggregated_billing"] is True
    assert rows[0]["_expected"] == 2
    assert rows[0]["_supply"] == 1
    assert "数量差に降格しない" in rows[0]["warning"]


def test_review_no_amount():
    mfi = _mf_index({"C": {"name": "金額なし商事", "lines": [_line(1)]}})
    c = {"取引先": "金額なし商事", "商品": "P", "確認内容": "更新確認のみ",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_NO_AMOUNT"


def test_status_ended_is_checked_for_overbilling():
    mfi = _mf_index({"C": {"name": "終了商事", "lines": [_line(1)]}})
    c = {"取引先": "終了商事", "商品": "P", "確認内容": "10,000円",
         "ステータス": "終了", "支払サイクル": R.CADENCE_MONTHLY}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_ENDED_BUT_BILLED"


def test_status_pending_is_surfaced_as_review_pending():
    # 保留(契約未締結/金額未記載等)は判定なしでスキップせず、要確認(REVIEW_PENDING)として
    # 可視化し確認ポイントへ理由を書く(ユーザー確定 2026-06-27: 判定なしは漏れの温床)。
    mfi = _mf_index({"C": {"name": "保留商事", "lines": [_line(1)]}})
    c = {"取引先": "保留商事", "商品": "P", "確認内容": "5/19契約書未締結",
         "備考": "5/19契約書未締結", "ステータス": "保留"}
    rows = R.classify([c], mfi, "2606")
    assert len(rows) == 1
    assert rows[0]["verdict"] == "REVIEW_PENDING"
    assert rows[0]["warning"] == "契約書が未締結/未確定"  # 保留理由が確認ポイントへ
    assert R.sheet_label("REVIEW_PENDING") == "要確認"


def test_pending_contract_covers_mf_customer_for_orphan_detection():
    """保留契約もシート登録済みなので、同じMF顧客をORPHAN(要マスタ登録)にしない。"""
    mfi = _mf_index({"C": {"name": "保留商事", "lines": [_line(1)]}})
    c = {"取引先": "保留商事", "商品": "P", "確認内容": "5/19契約書未締結",
         "備考": "5/19契約書未締結", "ステータス": "保留"}
    result = R.reconcile([c], mfi, "2606")
    assert [r["verdict"] for r in result["rows"]] == ["REVIEW_PENDING"]
    assert result["orphans"] == []


def test_build_mf_index_dedup_and_exclusions():
    """API 二重化 dedup + 立替/0円/負額の除外。"""
    mfi = _mf_index({"C": {"name": "畳み込み商事", "lines": [
        _line(100000, billing_id="X"), _line(100000, billing_id="X"),  # 重複→1
        _line(0, "0円明細"), _line(-500, "値引"), _line(31190, "立替経費"),
    ]}})
    svcs = mfi["C"]["services"]
    assert len(svcs) == 1 and svcs[0]["amount"] == 100000


def test_oneshot_inactive_unparseable_start_suppressed():
    """単発で開始日不正 (elapsed None) → oneshot_active False → SUPPRESS_ONESHOT に倒れず

    K1 で REVIEW_DATA_INCOMPLETE (非月払い+開始日空欄) になる。"""
    mfi = _mf_index({"C": {"name": "単発商事", "lines": [_line(1)]}})
    c = {"取引先": "単発商事", "商品": "P", "確認内容": "10,000円",
         "支払サイクル": R.CADENCE_ONESHOT, "契約開始日": ""}
    assert R.classify([c], mfi, "2606")[0]["verdict"] == "REVIEW_DATA_INCOMPLETE"


# ============================================================================
# 11. 取消 (canceled) 取引の可視化: 要確認(取消)=REVIEW_CANCELED
# ============================================================================
_CANCEL_AT = "2026-06-25T17:39:45+09:00"


def _canceled_line(amount, desc="チイキズカン業務委託費", qty=1, billing_id="B1",
                   unit_price=None, canceled_at=_CANCEL_AT):
    """status=canceled の取消明細 (取消前金額を保持)。"""
    return {"amount": amount, "desc": desc, "qty": qty, "billing_id": billing_id,
            "unit_price": unit_price, "status": "canceled", "canceled_at": canceled_at}


def _active_line(amount, desc="チイキズカン業務委託費", qty=1, billing_id="B1",
                 unit_price=None, status="passed"):
    """status=passed の有効明細。"""
    return {"amount": amount, "desc": desc, "qty": qty, "billing_id": billing_id,
            "unit_price": unit_price, "status": status, "canceled_at": None}


def test_is_active_status_whitelist():
    """有効供給ホワイトリスト: passed/空/None のみ active。canceled・未知は非active。"""
    assert R._is_active_status("passed") is True
    assert R._is_active_status("PASSED") is True
    assert R._is_active_status("") is True
    assert R._is_active_status(None) is True
    assert R._is_active_status("canceled") is False
    assert R._is_active_status("frozen") is False


def test_build_mf_index_routes_canceled_to_bucket():
    """status=canceled は services でなく inactive バケットへ (取消前金額が MATCH 化しない)。"""
    mfi = _mf_index({"C": {"name": "取消商事", "lines": [
        _line(100000, billing_id="B1"),            # status 無 → active → services
        _canceled_line(200000, billing_id="B2"),   # 取消 → inactive バケット
    ]}})
    assert [s["amount"] for s in mfi["C"]["services"]] == [100000]
    canc = mfi["C"]["inactive"]
    assert [x["amount"] for x in canc] == [200000]
    assert canc[0]["status"] == "canceled"
    assert canc[0]["canceled_at"] == _CANCEL_AT


def test_build_mf_index_keeps_zero_amount_canceled_evidence():
    """0円でも status=canceled + 商品名ありなら取消証跡として inactive に残す。

    MF側で billing.amount=0 に集計されても、商品名/description が残る取消取引を単純な0円除外に
    すると「商品名はあるのに金額0」の理由が見えない。active 0円明細は従来どおり除外する。
    """
    mfi = _mf_index({"C": {"name": "0円取消商事", "lines": [
        _line(0, "0円 active", billing_id="A1"),
        _canceled_line(0, desc="チイキズカン業務委託費（田中様 2026年6月分）", billing_id="C1"),
    ]}})
    assert mfi["C"]["services"] == []
    assert len(mfi["C"]["inactive"]) == 1
    assert mfi["C"]["inactive"][0]["amount"] == 0
    assert mfi["C"]["inactive"][0]["status"] == "canceled"


def test_build_mf_index_passed_active_nonpassed_to_inactive():
    """status=passed は有効(services)。canceled 以外の非active(審査中/否決/停止等)も silent drop せず
    inactive バケットへ status 付きで隔離する(有効供給ゼロ時に GAP 誤分類させず可視化するため)。"""
    mfi = _mf_index({"C": {"name": "正常商事", "lines": [_active_line(50000, billing_id="B1")]}})
    assert [s["amount"] for s in mfi["C"]["services"]] == [50000]
    assert mfi["C"]["inactive"] == []
    mfi2 = _mf_index({"C": {"name": "審査中商事", "lines": [
        {"amount": 50000, "desc": "P", "qty": 1, "billing_id": "B1",
         "unit_price": 50000, "status": "examining", "canceled_at": None}]}})
    assert mfi2["C"]["services"] == []  # 非active は有効供給に入らない
    assert [x["status"] for x in mfi2["C"]["inactive"]] == ["examining"]


def test_inactive_line_dedup():
    """inactive バケットも billing_id+desc+amount で API二重化を畳む。"""
    mfi = _mf_index({"C": {"name": "取消商事", "lines": [
        _canceled_line(70000, billing_id="X"), _canceled_line(70000, billing_id="X"),
    ]}})
    assert len(mfi["C"]["inactive"]) == 1


def test_canceled_only_monthly_is_review_canceled():
    """有効供給ゼロ + 同一境界に取消供給 → REVIEW_CANCELED (GAP でなく要確認(取消))。"""
    mfi = _mf_index({"C": {"name": "取消商事", "lines": [
        _canceled_line(70000, desc="チイキズカン業務委託費（田中様 2026年6月分）")]}})
    c = {"取引先": "取消商事", "商品": "チイキズカン業務委託費", "確認内容": "70,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_CANCELED"
    assert "取消前金額: 70,000円" in rows[0]["warning"]
    assert _CANCEL_AT in rows[0]["warning"]
    assert rows[0]["evidence"]["amount"] == 70000


def test_zero_amount_canceled_only_monthly_is_review_canceled():
    """有効供給ゼロ + 同一境界に0円取消証跡 → REVIEW_CANCELED。

    取消で billing.amount=0 になり商品名だけ残るケースを GAP/対象外に落とさず、確認ポイントで
    取消状態を明示できるようにする。
    """
    mfi = _mf_index({"C": {"name": "0円取消商事", "lines": [
        _canceled_line(0, desc="チイキズカン業務委託費（田中様 2026年6月分）")]}})
    c = {"取引先": "0円取消商事", "商品": "チイキズカン業務委託費", "確認内容": "70,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_CANCELED"
    assert rows[0]["warning"] == "MF取引が取消済み"


def test_canceled_then_reissued_same_month_stays_match():
    """取消後に同月再発行(active=passed)があれば有効供給で MATCH 維持 (誤要確認にしない)。"""
    mfi = _mf_index({"C": {"name": "再発行商事", "lines": [
        _canceled_line(70000, billing_id="B1"),   # 取消
        _active_line(70000, billing_id="B2"),      # 同月再発行
    ]}})
    c = {"取引先": "再発行商事", "商品": "チイキズカン業務委託費", "確認内容": "70,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "MATCH_MONTHLY"


def test_canceled_does_not_override_amount_mismatch():
    """有効供給があり金額のみ不一致なら従来 REVIEW_AMOUNT_MISMATCH を維持 (取消で上書きしない)。"""
    mfi = _mf_index({"C": {"name": "差額商事", "lines": [
        _active_line(50000, billing_id="B1"),      # 有効供給 (金額違い)
        _canceled_line(70000, billing_id="B2"),    # 取消
    ]}})
    c = {"取引先": "差額商事", "商品": "チイキズカン業務委託費", "確認内容": "70,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_AMOUNT_MISMATCH"


def test_canceled_only_annual_is_review_canceled():
    """年間払いで有効一括ゼロ + 年額相当の取消供給 → REVIEW_CANCELED (SUPPRESS/REVIEW に倒さない)。"""
    mfi = _mf_index({"C": {"name": "年間取消商事", "lines": [
        _canceled_line(600000, desc="チイキズカンサービス利用料（2026年6月分）", qty=12)]}})
    c = {"取引先": "年間取消商事", "商品": "チイキズカン利用料（1年目）", "確認内容": "600,000円",
         "支払サイクル": R.CADENCE_ANNUAL, "契約開始日": "2606", "契約終了月": ""}  # elapsed 0
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_CANCELED"
    assert "取消前金額: 600,000円" in rows[0]["warning"]


def test_canceled_only_annual_renewal_is_review_canceled():
    """年間一括更新で有効一括ゼロ + 取消供給 → REVIEW_CANCELED。"""
    mfi = _mf_index({"C": {"name": "更新取消商事", "lines": [
        _canceled_line(1800000, desc="100億ThinkTankサービス利用料（2026年6月分）", qty=12)]}})
    c = {"取引先": "更新取消商事", "商品": "100億ThinkTank利用料", "確認内容": "1,800,000円",
         "支払サイクル": R.CADENCE_ANNUAL_RENEWAL, "契約開始日": "2506", "契約終了月": ""}  # elapsed 12
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_CANCELED"


def test_annual_prepaid_small_canceled_stays_suppressed():
    """年間前払い期間中の小額取消は年額一括取消ではないため SUPPRESS_ANNUAL のまま。

    annual mode の inactive 判定を年額一括相当に絞り、単に canceled があるだけで対象外行を
    REVIEW_CANCELED へ誤昇格しない。
    """
    mfi = _mf_index({"C": {"name": "年契商事", "lines": [
        _canceled_line(50000, desc="チイキズカンサービス利用料（2026年6月分）", qty=1)]}})
    c = {"取引先": "年契商事", "商品": "チイキズカン利用料（1年目）", "確認内容": "600,000円",
         "支払サイクル": R.CADENCE_ANNUAL, "契約開始日": "2605", "契約終了月": ""}  # elapsed 1
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "SUPPRESS_ANNUAL"


def test_canceled_only_customer_not_orphan():
    """取消のみの顧客 (有効供給ゼロ) は ORPHAN (要マスタ登録) に出さない。"""
    mfi = _mf_index({"C": {"name": "孤児取消商事", "lines": [_canceled_line(50000)]}})
    assert R.detect_orphans([], mfi, "2606") == []


def test_review_canceled_emitted_and_mapped(reconciled):
    """REVIEW_CANCELED が verdict-mapping.json に定義済み (parity 充足) で sheet_label=要確認。"""
    mapping = R.load_verdict_mapping()
    assert "REVIEW_CANCELED" in mapping
    assert R.judge_label("REVIEW_CANCELED") == "要確認(取消)"
    assert R.sheet_label("REVIEW_CANCELED") == "要確認"
    assert R.is_check_verdict("REVIEW_CANCELED") is False


def test_presence_mode_ignores_canceled():
    """presence モード(終了契約判定)は非active供給を無視する(inactive_only を発火させない)。"""
    mfi = _mf_index({"C": {"name": "終了取消商事", "lines": [_canceled_line(90000)]}})
    c = {"取引先": "終了取消商事", "商品": "P", "確認内容": "90,000円 請求なし（2605終了）",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "2501", "契約終了月": "2605"}
    rows = R.classify([c], mfi, "2606")
    # 終了根拠あり + 有効供給なし(取消のみ) → SUPPRESS_ENDED のまま (REVIEW_CANCELED にしない)。
    assert rows[0]["verdict"] == "SUPPRESS_ENDED"


# ============================================================================
# 11b. passed 以外の非取消取引の可視化: 要確認(取引未確定)=REVIEW_TXN_NOT_PASSED
# ============================================================================
def _nonpassed_line(amount, status="examining", desc="チイキズカン業務委託費", billing_id="B1"):
    """canceled 以外の非active(審査中/否決/停止等)明細。canceled_at は無し。"""
    return {"amount": amount, "desc": desc, "qty": 1, "billing_id": billing_id,
            "unit_price": amount, "status": status, "canceled_at": None}


def test_txn_not_passed_only_monthly_is_review_txn_not_passed():
    """有効供給ゼロ + 同一境界に passed でない非取消取引(審査中等) → REVIEW_TXN_NOT_PASSED。

    取消(canceled)と区別し、GAP(発行漏れ)へ silent 誤分類させず取引状態を警告へ出す。
    """
    mfi = _mf_index({"C": {"name": "審査中商事", "lines": [
        _nonpassed_line(70000, status="examining",
                        desc="チイキズカン業務委託費（佐藤様 2026年6月分）")]}})
    c = {"取引先": "審査中商事", "商品": "チイキズカン業務委託費", "確認内容": "70,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_TXN_NOT_PASSED"
    assert "examining" in rows[0]["warning"]
    assert "70,000円" in rows[0]["warning"]


def test_txn_not_passed_annual_is_review_txn_not_passed():
    """年間払いで年額相当の非passed供給 → REVIEW_TXN_NOT_PASSED。"""
    mfi = _mf_index({"C": {"name": "年間審査中商事", "lines": [
        _nonpassed_line(600000, status="examining",
                        desc="チイキズカンサービス利用料（2026年6月分）")]}})
    c = {"取引先": "年間審査中商事", "商品": "チイキズカン利用料（1年目）", "確認内容": "600,000円",
         "支払サイクル": R.CADENCE_ANNUAL, "契約開始日": "2606", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_TXN_NOT_PASSED"
    assert "examining" in rows[0]["warning"]


def test_txn_not_passed_annual_renewal_is_review_txn_not_passed():
    """年間一括更新で年額相当の非passed供給 → REVIEW_TXN_NOT_PASSED。"""
    mfi = _mf_index({"C": {"name": "更新審査中商事", "lines": [
        _nonpassed_line(1800000, status="examining",
                        desc="100億ThinkTankサービス利用料（2026年6月分）")]}})
    c = {"取引先": "更新審査中商事", "商品": "100億ThinkTank利用料", "確認内容": "1,800,000円",
         "支払サイクル": R.CADENCE_ANNUAL_RENEWAL, "契約開始日": "2506", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_TXN_NOT_PASSED"
    assert "examining" in rows[0]["warning"]


def test_nonpassed_then_reissued_same_month_stays_match():
    """審査中等の後に有効(passed)供給があれば MATCH 維持(非active で上書きしない)。"""
    mfi = _mf_index({"C": {"name": "審査通過商事", "lines": [
        _nonpassed_line(70000, status="examining", billing_id="B1"),
        _active_line(70000, billing_id="B2"),
    ]}})
    c = {"取引先": "審査通過商事", "商品": "チイキズカン業務委託費", "確認内容": "70,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "MATCH_MONTHLY"


def test_review_txn_not_passed_emitted_and_mapped():
    """REVIEW_TXN_NOT_PASSED が verdict-mapping に定義済み・sheet_label=要確認・ai_check=False。"""
    mapping = R.load_verdict_mapping()
    assert "REVIEW_TXN_NOT_PASSED" in mapping
    assert R.judge_label("REVIEW_TXN_NOT_PASSED") == "要確認(取引未確定)"
    assert R.sheet_label("REVIEW_TXN_NOT_PASSED") == "要確認"
    assert R.is_check_verdict("REVIEW_TXN_NOT_PASSED") is False


# ============================================================================
# 12. amount=None の取消取りこぼし修正 (T2): 非active+desc は 0 円へ正規化して inactive へ
# ============================================================================
def test_amount_none_canceled_with_desc_routed_to_inactive():
    """amount=None + status=canceled + desc あり → build_mf_index が 0 円へ正規化し inactive へ。

    status 判定前の amt None 早期 continue で取消が inactive にすら入らず GAP 誤分類されるバグの修正。
    """
    line = {"amount": None, "desc": "チイキズカン業務委託費（佐藤様 2026年6月分）", "qty": 1,
            "billing_id": "B1", "unit_price": None, "status": "canceled",
            "canceled_at": _CANCEL_AT}
    mfi = _mf_index({"C": {"name": "金額欠落取消商事", "lines": [line]}})
    assert mfi["C"]["services"] == []
    assert len(mfi["C"]["inactive"]) == 1
    assert mfi["C"]["inactive"][0]["amount"] == 0
    assert mfi["C"]["inactive"][0]["status"] == "canceled"


def test_amount_none_canceled_monthly_is_review_canceled_not_gap():
    """amount=None の取消は月次経路で GAP でなく REVIEW_CANCELED になる (T2 の e2e 検証)。"""
    line = {"amount": None, "desc": "チイキズカン業務委託費（佐藤様 2026年6月分）", "qty": 1,
            "billing_id": "B1", "unit_price": None, "status": "canceled",
            "canceled_at": _CANCEL_AT}
    mfi = _mf_index({"C": {"name": "金額欠落取消商事", "lines": [line]}})
    c = {"取引先": "金額欠落取消商事", "商品": "チイキズカン業務委託費", "確認内容": "70,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_CANCELED"
    assert rows[0]["warning"] == "MF取引が取消済み"  # amt 0 (falsy)


def test_amount_none_canceled_without_desc_is_dropped():
    """amount=None + 非active だが desc 無し → 識別不能ゆえ inactive にも入れない (捨てる)。"""
    line = {"amount": None, "desc": "", "qty": 1, "billing_id": "B1",
            "unit_price": None, "status": "canceled", "canceled_at": _CANCEL_AT}
    mfi = _mf_index({"C": {"name": "識別不能商事", "lines": [line]}})
    assert mfi["C"]["services"] == []
    assert mfi["C"]["inactive"] == []


def test_active_amount_none_still_excluded():
    """active(status無)で amount=None は従来どおり有効供給から除外 (status 判定移動の回帰防止)。"""
    line = {"amount": None, "desc": "有効だが金額欠落", "qty": 1, "billing_id": "B1",
            "unit_price": None}  # status 無 → active
    mfi = _mf_index({"C": {"name": "有効欠落商事", "lines": [line]}})
    assert mfi["C"]["services"] == []
    assert mfi["C"]["inactive"] == []


def test_negative_canceled_excluded_from_inactive():
    """負額(値引/相殺)の取消明細は inactive にも入れない (純額減額は未配線=deferred)。"""
    mfi = _mf_index({"C": {"name": "値引取消商事", "lines": [
        _canceled_line(-500, desc="値引クレジット")]}})
    assert mfi["C"]["services"] == []
    assert mfi["C"]["inactive"] == []


# ============================================================================
# 13. 取消注記の横断一段化 (T1): 抑制verdict は据え置きで warning に取消注記を併記
# ============================================================================
def test_cancellation_note_canceled_with_amount():
    """cancellation_note: 取消(canceled)+金額あり → 取消前金額/取消日の1フレーズ。"""
    mfi = _mf_index({"C": {"name": "注記商事", "lines": [_canceled_line(70000)]}})
    c = {"取引先": "注記商事", "商品": "P", "確認内容": "70,000円"}
    note = R.cancellation_note(c, mfi)
    assert "取消取引あり" in note
    assert "取消前金額 70,000円" in note
    assert _CANCEL_AT in note


def test_cancellation_note_zero_amount_canceled():
    """cancellation_note: 取消+金額0 でも取消の事実は必ず出す (金額0=取消前不明)。"""
    mfi = _mf_index({"C": {"name": "0注記商事", "lines": [
        _canceled_line(0, desc="チイキズカン業務委託費（田中様 2026年6月分）")]}})
    c = {"取引先": "0注記商事", "商品": "P", "確認内容": "70,000円"}
    note = R.cancellation_note(c, mfi)
    assert "取消取引あり(金額0=取消前不明)" in note


def test_cancellation_note_nonpassed_with_amount():
    """cancellation_note: 非passed(審査中等)+金額あり → 未確定取引の状態/金額。"""
    mfi = _mf_index({"C": {"name": "未確定注記商事", "lines": [
        _nonpassed_line(50000, status="examining")]}})
    c = {"取引先": "未確定注記商事", "商品": "P", "確認内容": "50,000円"}
    note = R.cancellation_note(c, mfi)
    assert "未確定取引あり" in note and "examining" in note and "50,000円" in note


def test_cancellation_note_nonpassed_zero_amount():
    """cancellation_note: 非passed+金額0/None → 状態のみで未確定を出す。"""
    line = {"amount": None, "desc": "審査中明細", "qty": 1, "billing_id": "B1",
            "unit_price": None, "status": "examining", "canceled_at": None}
    mfi = _mf_index({"C": {"name": "審査未確定商事", "lines": [line]}})
    c = {"取引先": "審査未確定商事", "商品": "P", "確認内容": "50,000円"}
    assert R.cancellation_note(c, mfi) == "当月MFに未確定取引あり: 状態 examining"


def test_cancellation_note_empty_when_no_inactive():
    """cancellation_note: 非active供給が無ければ空文字 (注記しない)。"""
    mfi = _mf_index({"C": {"name": "正常商事", "lines": [_active_line(50000)]}})
    c = {"取引先": "正常商事", "商品": "P", "確認内容": "50,000円"}
    assert R.cancellation_note(c, mfi) == ""


def test_suppress_ended_with_cancellation_gets_note():
    """ユーザー要望の核: 終了根拠あり契約で当月が取消のみ → SUPPRESS_ENDED 据え置き + 取消注記。

    presence モードは取消を無視するため verdict は SUPPRESS_ENDED のままだが、対象外行の確認ポイントに
    『一度発行→取消』が分かるよう warning へ取消注記を併記する (WARN-not-FAIL)。
    """
    mfi = _mf_index({"C": {"name": "終了取消商事", "lines": [
        _canceled_line(90000, desc="業務委託費（田中様 2026年6月分）")]}})
    c = {"取引先": "終了取消商事", "商品": "P", "確認内容": "90,000円 請求なし（2605終了）",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "2501", "契約終了月": "2605"}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "SUPPRESS_ENDED"  # 据え置き
    assert "取消取引あり" in rows[0]["warning"]
    assert "取消前金額 90,000円" in rows[0]["warning"]


def test_ended_no_basis_with_cancellation_gets_note():
    """根拠なし終了 (REVIEW_ENDED_NO_BASIS) + 当月取消 → verdict 据え置き + 取消注記併記。"""
    mfi = _mf_index({"C": {"name": "根拠なし取消商事", "lines": [
        _canceled_line(80000, desc="業務委託費（佐藤様 2026年6月分）")]}})
    c = {"取引先": "根拠なし取消商事", "商品": "P", "確認内容": "80,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "2501", "契約終了月": "2605"}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "REVIEW_ENDED_NO_BASIS"  # 据え置き
    assert "終了根拠なし" in rows[0]["warning"]  # 既存の根拠なし警告を保持
    assert "取消取引あり" in rows[0]["warning"]  # かつ取消注記を ' / ' で連結


def test_suppress_annual_small_canceled_gets_note():
    """年間前払い期間中の小額取消 → SUPPRESS_ANNUAL 据え置き + 取消注記併記。"""
    mfi = _mf_index({"C": {"name": "年契取消商事", "lines": [
        _canceled_line(50000, desc="チイキズカンサービス利用料（2026年6月分）", qty=1)]}})
    c = {"取引先": "年契取消商事", "商品": "チイキズカン利用料（1年目）", "確認内容": "600,000円",
         "支払サイクル": R.CADENCE_ANNUAL, "契約開始日": "2605", "契約終了月": ""}  # elapsed 1
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "SUPPRESS_ANNUAL"  # 据え置き(年額一括取消でない)
    assert "取消取引あり" in rows[0]["warning"]
    assert "取消前金額 50,000円" in rows[0]["warning"]


def test_suppress_oneshot_with_cancellation_gets_note():
    """単発で開始月過ぎ (SUPPRESS_ONESHOT) + 当月取消 → verdict 据え置き + 取消注記。"""
    mfi = _mf_index({"C": {"name": "単発取消商事", "lines": [
        _canceled_line(80000, desc="単発作業（田中様 2026年6月分）")]}})
    c = {"取引先": "単発取消商事", "商品": "P", "確認内容": "80,000円",
         "支払サイクル": R.CADENCE_ONESHOT, "契約開始日": "2605", "契約終了月": ""}  # elapsed 1
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "SUPPRESS_ONESHOT"  # 据え置き
    assert "取消取引あり" in rows[0]["warning"]


def test_suppress_offmonth_with_cancellation_gets_note():
    """隔月の非請求月 (SUPPRESS_OFFMONTH) + 当月取消 → verdict 据え置き + 取消注記。"""
    mfi = _mf_index({"C": {"name": "隔月取消商事", "lines": [
        _canceled_line(70000, desc="隔月作業（鈴木様 2026年6月分）")]}})
    c = {"取引先": "隔月取消商事", "商品": "P", "確認内容": "70,000円",
         "支払サイクル": R.CADENCE_BIMONTHLY, "契約開始日": "2605", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")  # elapsed 1 非請求月
    assert rows[0]["verdict"] == "SUPPRESS_OFFMONTH"  # 据え置き
    assert "取消取引あり" in rows[0]["warning"]


def test_match_monthly_not_annotated_with_cancellation():
    """MATCH_* / REVIEW_CANCELED には取消注記を足さない (二重・緑漏洩防止=据え置き対象外)。"""
    # 有効供給ありで MATCH → cancellation_note 対象外。
    mfi = _mf_index({"C": {"name": "再発行商事", "lines": [
        _canceled_line(70000, billing_id="B1"),
        _active_line(70000, billing_id="B2"),
    ]}})
    c = {"取引先": "再発行商事", "商品": "P", "確認内容": "70,000円",
         "支払サイクル": R.CADENCE_MONTHLY, "契約開始日": "", "契約終了月": ""}
    rows = R.classify([c], mfi, "2606")
    assert rows[0]["verdict"] == "MATCH_MONTHLY"
    assert "取消取引あり" not in (rows[0].get("warning") or "")


def test_golden_summary_unchanged_after_cancellation_annotation(reconciled):
    """取消注記の追加 (T1) は golden の verdict 分布を変えない (warning のみ追記=WARN-not-FAIL)。"""
    assert reconciled["summary"]["SUPPRESS_ANNUAL"] == 12
    assert reconciled["summary"]["GAP"] == 15
    assert reconciled["summary"]["REVIEW_QTY_MISMATCH"] == 31
    # golden には status 列が無く inactive バケットが空のため、対象外行の warning は空のまま。
    suppress_rows = [r for r in reconciled["rows"]
                     if r["verdict"] in ("SUPPRESS_ANNUAL", "SUPPRESS_ENDED")]
    assert suppress_rows
    assert all("取消取引あり" not in (r.get("warning") or "") for r in suppress_rows)

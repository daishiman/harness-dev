"""company-master 機能テスト (再現性不変条件の回帰検証)。

company-master プラグインの「再現性」を pytest で機械保証する。CI の
`python3 -m pytest tests/ -q` (harness-creator-kit-ci.yml) が本ファイルを自動的に拾う。

検証する不変条件:
  - enrich の決定論性 (同入力 → 同出力)
  - notion_upsert.build_properties の 7 列ちょうど (確認用URL 列・正式名称列は持たない)
  - confirm_url の md 単一正本 (SSOT) byte 一致 + render byte 安定 (fail-closed)
  - remarks の md 正本パース
  - validate_company_master の deterministic_checks (a-h) 判定

import 経路: 共有 scripts (plugin-root に集約) を sys.path へ挿入する (他テスト
test_skill_intake_notion_contract.py の sys.path.insert パターンに倣う)。
company-master の scripts は bootstrap_plugin.bootstrap() でも解決できるが、
テストでは明示的に plugin-root scripts ディレクトリを sys.path 先頭へ挿す。
"""
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "company-master"
SHARED_SCRIPTS = PLUGIN_ROOT / "scripts"
REFERENCES = PLUGIN_ROOT / "references"

# 共有モジュール (enrich_company / notion_upsert / confirm_url / remarks /
# validate_company_master) を import 可能にする (plugin-root scripts/ に集約)。
sys.path.insert(0, str(SHARED_SCRIPTS))

import backfill  # noqa: E402
import enrich_company  # noqa: E402
import postal_api  # noqa: E402
import notion_upsert  # noqa: E402
import confirm_url  # noqa: E402
import remarks  # noqa: E402
import resolve_company  # noqa: E402
import validate_company_master as vcm  # noqa: E402

HOOK_GUARD = PLUGIN_ROOT / "hooks" / "hook-guard-secret.py"


# --- fixtures -----------------------------------------------------------------

GBIZ_DETAIL_URL = "https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123"
SAMPLE_ENTITY = {
    "company_name": "テスト商事",
    "official_name": "テスト商事株式会社",
    "address": "東京都千代田区丸の内1-1-1",
    "hojin_bango": "1234567890123",
    "source_url": GBIZ_DETAIL_URL,  # resolve_company が伝搬する gBizINFO 法人詳細ページ URL
}
SAMPLE_WEB_FINDINGS = {
    "phone": {"value": "03-1234-5678", "source_url": "https://example.co.jp/contact"},
}

# 正式名称列は廃止し会社名(title)へ統合 (R4) したため 7 列構成。
EXPECTED_7_COLS = {
    "会社名", "住所", "郵便番号",
    "法人番号", "電話番号", "情報の確かさ", "備考",
}


def _enrich_offline(entity: dict, web_findings: dict | None) -> dict:
    """日本郵便 API 通信を起こさず enrich を実行する (CI offline 不変条件)。

    enrich は空欄郵便番号を日本郵便 addresszip API で逆引きするが、CI/clean 環境では
    実 API 通信 (要トークン/IP認証) が走り network 依存 + 不安定になる。テストは決定論性/
    列構成/検証ロジックの回帰が目的なので、postal_from_address を固定値スタブへ差し替えて
    offline 化する。
    """
    original = enrich_company.postal_from_address
    enrich_company.postal_from_address = lambda address, company_name="": {
        "value": "100-0005",
        "certainty": enrich_company.CERTAINTY_PUBLIC_FETCHED,
        "remark_key": "",
        "source_url": postal_api.JAPANPOST_VERIFY_URL,
    }
    try:
        return enrich_company.enrich(entity, web_findings)
    finally:
        enrich_company.postal_from_address = original


def _canonical_record() -> dict:
    """validate を通る正準 record (record 形式・offline。7列+official_name provenance)。"""
    return _enrich_offline(SAMPLE_ENTITY, SAMPLE_WEB_FINDINGS)


# --- GAP-1 tests --------------------------------------------------------------

def test_enrich_deterministic():
    """enrich(同 entity, 同 web_findings) を 2 回 → JSON(sort_keys) byte 一致。"""
    a = _enrich_offline(SAMPLE_ENTITY, SAMPLE_WEB_FINDINGS)
    b = _enrich_offline(SAMPLE_ENTITY, SAMPLE_WEB_FINDINGS)
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(
        b, sort_keys=True, ensure_ascii=False
    )


def test_build_properties_exactly_7_columns():
    """build_properties が 7 キーちょうど・期待 7 列名集合一致・『確認用URL』『正式名称』を含まない。

    正式名称は独立列を廃止し会社名(title)へ統合 (R4)。会社名 title は official_name 優先 (R3)。
    """
    rec = _canonical_record()
    props = notion_upsert.build_properties(rec)
    assert set(props.keys()) == EXPECTED_7_COLS
    assert len(props) == 7
    assert "確認用URL" not in props
    assert "正式名称" not in props
    # 会社名(title) は official_name(登記名) を優先表示する (R3)。
    title_text = props["会社名"]["title"][0]["text"]["content"]
    assert title_text == rec["fields"]["official_name"] == "テスト商事株式会社"


def test_backfill_does_not_overwrite_existing_nonempty_cells():
    """backfill 中核保証『既存非空セル不可侵』の回帰防止 (elegant-review HIGH-4)。

    build_fill_empty_properties は既存が非空のセルを PATCH 対象から除外し、既存が空の
    セルだけを新値で補完する。人手で確定済みの値の自動上書き (最も破壊的なリグレッション)
    が起きないことを、run-company-master-backfill skill の中核保証として直接アサートする。
    """
    rec = _canonical_record()
    f = rec.get("fields", {})
    nonempty = {k: v for k, v in f.items() if v}
    assert nonempty, "canonical record の fields が全空 (テスト前提崩れ)"

    # (1) 既存が全属性非空 → PATCH 対象ゼロ (一切上書きしない)
    existing_full = dict(nonempty)
    existing_full["overall_certainty"] = rec.get("overall_certainty", "")
    existing_full["remarks_text"] = rec.get("remarks_text", "")
    out_full = notion_upsert.build_fill_empty_properties(rec, existing_full)
    assert out_full == {}, f"既存全非空なのに PATCH 対象が出た (上書きリスク): {list(out_full)}"

    # (2) 既存が全空 → 新値ある列は補完対象になり、値は build_properties と一致
    out_empty = notion_upsert.build_fill_empty_properties(rec, {})
    assert out_empty, "既存全空なのに補完対象ゼロ (補完が働かない)"
    full_props = notion_upsert.build_properties(rec)
    for col, val in out_empty.items():
        assert val == full_props[col]

    # (3) 会社名・法人番号だけ既存非空 → その2列は除外され、他は補完されうる
    out_partial = notion_upsert.build_fill_empty_properties(
        rec, {"company_name": "既存通称", "hojin_bango": "1234567890123"})
    assert notion_upsert.COL_COMPANY_NAME not in out_partial
    assert notion_upsert.COL_HOJIN_BANGO not in out_partial


def test_confirm_url_ssot_parses_to_spec():
    """confirm_url が md SSOT から 5 要素 + origin 5 ラベルを抽出できる (構造ドリフト検出)。

    断定文言 (「公的データ由来のためURL不要」「全項目が公的データ由来」) の廃止と
    placeholder の存在 (bullet 2 形式) を機械検査する。文言の byte 確定値は md 正本のみが
    持ち、レンダリング byte 一致は test_confirm_url_render_byte_stable が md から導出検証する。
    """
    tpl = confirm_url.load_template()
    assert set(tpl.keys()) == set(confirm_url.TEMPLATE_KEYS)
    for key, value in tpl.items():
        assert value.strip(), f"template[{key!r}] が空文言"
        assert "公的データ由来のためURL不要" not in value, "廃止済みの断定文言が残存"
        assert "全項目が公的データ由来" not in value, "廃止済みの断定文言が残存"
    assert "{attribute}" in tpl["bullet_with_url"]
    assert "{origin_label}" in tpl["bullet_with_url"]
    assert "{url}" in tpl["bullet_with_url"]
    assert "{attribute}" in tpl["bullet_no_url"]
    assert "{origin_label}" in tpl["bullet_no_url"]
    assert "{url}" not in tpl["bullet_no_url"]

    labels = confirm_url.load_origin_labels()
    assert set(labels.keys()) == set(confirm_url.ORIGIN_KEYS)
    # 表示語彙は機関名+一般名 (design directive A)。
    assert labels["gbizinfo"] == "経済産業省 gBizINFO"
    assert labels["japanpost"] == "日本郵便 郵便番号データ"


SAMPLE_SOURCE_BY_FIELD = {
    "company_name": {"origin": "user_input", "url": ""},
    "official_name": {"origin": "gbizinfo", "url": GBIZ_DETAIL_URL},
    "address": {"origin": "gbizinfo", "url": GBIZ_DETAIL_URL},
    "postal_code": {"origin": "japanpost", "url": postal_api.JAPANPOST_VERIFY_URL},
    "hojin_bango": {"origin": "gbizinfo", "url": GBIZ_DETAIL_URL},
    "phone_number": {"origin": "web", "url": "https://www.google.com/search?q=%2203-1234-5678%22"},
}


def _expected_body_text(source_by_field: dict) -> str:
    """テンプレ md (SSOT) + build_entries (会社名統合の正本) から期待本文を導出する。

    会社名 bullet は official_name(登記名) 統合・正式名称の独立 bullet は廃止 (R5/D2) のため、
    期待値の属性順・由来は build_entries で正規化したうえでテンプレ文言を当てる (二重定義しない)。
    """
    tpl = confirm_url.load_template()
    entries = confirm_url.build_entries(source_by_field)
    lines = [f"## {tpl['heading']}", "", tpl["intro"], ""]
    for e in entries:
        if e["url"]:
            lines.append("- " + tpl["bullet_with_url"].format(
                attribute=e["attribute"], origin_label=e["origin_label"], url=e["url"]))
        else:
            lines.append("- " + tpl["bullet_no_url"].format(
                attribute=e["attribute"], origin_label=e["origin_label"]))
    return "\n".join(lines)


def test_confirm_url_render_byte_stable():
    """render_text(source_by_field) が md 導出期待値に byte 一致 + 同一入力で冪等 byte 安定。"""
    rendered = confirm_url.render_text(SAMPLE_SOURCE_BY_FIELD)
    assert rendered == _expected_body_text(SAMPLE_SOURCE_BY_FIELD)
    # 冪等性: 同一入力で render 結果 byte 一致。
    assert confirm_url.render_text(SAMPLE_SOURCE_BY_FIELD) == rendered

    tpl = confirm_url.load_template()
    no_fields = confirm_url.render_text([])
    assert no_fields == f"## {tpl['heading']}\n\n{tpl['body_no_fields']}"
    # 全属性 none (記録すべき由来なし) も未確定文言へ倒れる。
    all_none = {f: {"origin": "none", "url": ""} for f in confirm_url.ATTRIBUTE_FIELDS}
    assert confirm_url.render_text(all_none) == no_fields


def test_confirm_url_renders_merged_company_and_attributes_in_column_order():
    """source_by_field 入力で 会社名(official_name 統合)+住所/郵便番号/法人番号/電話番号 が列順で bullet 化 (R5/D2)。"""
    rendered = confirm_url.render_text(SAMPLE_SOURCE_BY_FIELD)
    bullets = [l for l in rendered.splitlines() if l.startswith("- ")]
    # 正式名称の独立 bullet は廃し会社名へ統合したため 5 bullet。
    assert len(bullets) == 5
    expected_order = [confirm_url.FIELD_LABELS[f] for f in confirm_url.ATTRIBUTE_FIELDS]
    assert expected_order == ["会社名", "住所", "郵便番号", "法人番号", "電話番号"]
    assert [b[2:].split("（")[0].split(":")[0] for b in bullets] == expected_order
    # R5/R3: 会社名 bullet は official_name(gBizINFO) の検証URLを統合し、ユーザー入力（URLなし）でない。
    company_bullet = next(b for b in bullets if b.startswith("- 会社名"))
    assert "ユーザー入力（URLなし）" not in company_bullet
    assert "経済産業省 gBizINFO" in company_bullet
    assert GBIZ_DETAIL_URL in company_bullet
    # R5 厳守: 『会社名: ユーザー入力（URLなし）』は本文に二度と出ない。
    assert "会社名: ユーザー入力（URLなし）" not in rendered
    # 正式名称の独立 bullet が出ていないこと。
    assert not any(b.startswith("- 正式名称") for b in bullets)


def test_confirm_url_suppresses_user_input_company_bullet():
    """R5: official_name が無く会社名が user_input(URLなし) のとき会社名 bullet を本文に出さない。"""
    src = {
        "company_name": {"origin": "user_input", "url": ""},
        "official_name": {"origin": "none", "url": ""},
        "address": {"origin": "gbizinfo", "url": GBIZ_DETAIL_URL},
        "postal_code": {"origin": "none", "url": ""},
        "hojin_bango": {"origin": "none", "url": ""},
        "phone_number": {"origin": "none", "url": ""},
    }
    rendered = confirm_url.render_text(src)
    bullets = [l for l in rendered.splitlines() if l.startswith("- ")]
    assert not any(b.startswith("- 会社名") for b in bullets), bullets
    assert "会社名: ユーザー入力（URLなし）" not in rendered
    # 会社名抑止で 住所/郵便番号/法人番号/電話番号 の 4 bullet。
    assert [b[2:].split("（")[0].split(":")[0] for b in bullets] == [
        "住所", "郵便番号", "法人番号", "電話番号"]


def test_confirm_url_legacy_source_urls_merges_official_name_into_company():
    """旧 source_urls 入力でも『正式名称』bullet を復活させず会社名 bullet へ統合する。"""
    rendered = confirm_url.render_text([
        {"attribute": "正式名称", "origin": "gbizinfo", "url": GBIZ_DETAIL_URL},
        {"attribute": "住所", "origin": "gbizinfo", "url": GBIZ_DETAIL_URL},
    ])
    bullets = [l for l in rendered.splitlines() if l.startswith("- ")]
    assert bullets[0].startswith("- 会社名（経済産業省 gBizINFO）")
    assert not any(b.startswith("- 正式名称") for b in bullets)


def test_confirm_url_parse_bullet_canonicalizes_official_name_to_company():
    """parse_bullet は旧『正式名称』bullet を会社名へ正規化する (再同期の逆変換でも統合・R5/D2)。"""
    parsed = confirm_url.parse_bullet(f"- 正式名称（経済産業省 gBizINFO）: {GBIZ_DETAIL_URL}")
    assert parsed["attribute"] == "会社名"
    assert parsed["url"] == GBIZ_DETAIL_URL


def test_confirm_url_resync_legacy_official_bullet_does_not_resurrect():
    """既存ページ本文に旧『正式名称: URL』bullet が残る行を再同期しても、会社名へ dedup し
    正式名称の独立 bullet を復活させない・official_name URL を 2 bullet へ重複させない (R5/D2)。"""
    existing = [confirm_url.parse_bullet(f"- 正式名称（経済産業省 gBizINFO）: {GBIZ_DETAIL_URL}"),
                confirm_url.parse_bullet(f"- 住所（経済産業省 gBizINFO）: {GBIZ_DETAIL_URL}")]
    merged = confirm_url.merge_entries(
        confirm_url.build_entries(SAMPLE_SOURCE_BY_FIELD), existing)
    attrs = [e["attribute"] for e in merged]
    assert "正式名称" not in attrs                  # 廃止 bullet が復活しない
    assert attrs.count("会社名") == 1               # 会社名 bullet は重複しない


def test_confirm_url_resync_suppresses_stale_user_input_company_bullet():
    """既存本文の『会社名: ユーザー入力（URLなし）』を再同期で復活させない (R5・backward 辺も抑止)。

    法人番号なし・user_input 名のみの未確定行: 今回 source も会社名を抑止する。merge が stale な
    会社名 no-url entry を保持しても、最終レンダリング (build_entries list 経路) が抑止する。"""
    source = {
        "company_name": {"origin": "user_input", "url": ""},
        "address": {"origin": "none", "url": ""},
        "postal_code": {"origin": "none", "url": ""},
        "hojin_bango": {"origin": "none", "url": ""},
        "phone_number": {"origin": "none", "url": ""},
    }
    existing = [confirm_url.parse_bullet("- 会社名: ユーザー入力（URLなし）")]
    merged = confirm_url.merge_entries(confirm_url.build_entries(source), existing)
    rendered = confirm_url.render_text(merged)
    assert "会社名: ユーザー入力（URLなし）" not in rendered
    # render_blocks(本番経路)でも会社名 bullet が出ないこと。
    blocks = confirm_url.render_blocks(merged)
    bullet_texts = [
        "".join(rt["text"]["content"] for rt in b["bulleted_list_item"]["rich_text"])
        for b in blocks if b["type"] == "bulleted_list_item"
    ]
    assert not any(t.startswith("会社名") for t in bullet_texts)


def test_confirm_url_resync_keeps_company_bullet_with_url():
    """抑止は url 無し user_input/none 限定: 既存『会社名（gBizINFO）: URL』は再同期で保持する。"""
    existing = [confirm_url.parse_bullet(f"- 会社名（経済産業省 gBizINFO）: {GBIZ_DETAIL_URL}")]
    merged = confirm_url.merge_entries(confirm_url.build_entries([]), existing)
    rendered = confirm_url.render_text(merged)
    assert f"会社名（経済産業省 gBizINFO）: {GBIZ_DETAIL_URL}" in rendered


def test_confirm_url_bullet_round_trip():
    """parse_bullet(render bullet) が entry を復元する (URL 非減少マージの逆変換保証)。"""
    entries = confirm_url.build_entries(SAMPLE_SOURCE_BY_FIELD)
    tpl = confirm_url.load_template()
    for entry in entries:
        text = confirm_url._bullet_text(tpl, entry)
        parsed = confirm_url.parse_bullet(text)
        assert parsed == entry, f"round-trip 不一致: {text}"
    # 旧形式 bullet (`属性: URL`) は web 由来として取り込む (後方互換)。
    legacy = confirm_url.parse_bullet("電話番号: https://old.example.co.jp/contact")
    assert legacy["attribute"] == "電話番号"
    assert legacy["origin"] == "web"
    assert legacy["url"] == "https://old.example.co.jp/contact"


def test_confirm_url_merge_entries_url_nondecreasing():
    """merge: 今回 URL 無しの属性は既存出典 URL を保持し、今回 URL 有りは差し替える。

    official_name(登記名) の出典は会社名 bullet へ統合される (R5/D2) ため、今回 official_name に
    gBizINFO 検証URLがあれば会社名 bullet が今回の出典へ差し替わる。
    """
    labels = confirm_url.load_origin_labels()
    new = confirm_url.build_entries({
        **{f: {"origin": "none", "url": ""} for f in confirm_url.ATTRIBUTE_FIELDS},
        "phone_number": {"origin": "none", "url": ""},
        "official_name": {"origin": "gbizinfo", "url": GBIZ_DETAIL_URL},
    })
    existing = [
        {"attribute": "電話番号", "origin": "web", "origin_label": labels["web"],
         "url": "https://old.example.co.jp/contact"},
    ]
    merged = confirm_url.merge_entries(new, existing)
    by_attr = {e["attribute"]: e for e in merged}
    # 今回 none の電話番号 → 既存 URL を保持 (URL 非減少)。
    assert by_attr["電話番号"]["url"] == "https://old.example.co.jp/contact"
    # official_name の gBizINFO 検証URLは会社名 bullet へ統合される (出所を失わない・R5)。
    assert by_attr["会社名"]["url"] == GBIZ_DETAIL_URL
    assert by_attr["会社名"]["origin"] == "gbizinfo"


def test_remarks_ssot_parses():
    """remarks.load_templates() が 10 キー (6属性 + postal 2 区別 + phone 保留 + all_tiers_exhausted)。"""
    templates = remarks.load_templates()
    assert len(templates) == 10
    assert "all_tiers_exhausted" in templates  # fallback tier4 の定型文言 (placeholder 付き)
    assert "postal_api_unauthorized" in templates  # 日本郵便API 認証失敗 (IP未登録/鍵不正) の区別文言
    assert "postal_api_unavailable" in templates  # 日本郵便API 通信失敗 (ネットワーク/一時障害) の区別文言
    assert "phone_no_web_candidate" in templates  # Web検索未実施/候補なし (検証棄却 phone_number と区別)
    for key, phrase in templates.items():
        assert phrase.strip(), f"remark_key {key!r} が空文言"


def test_validate_passes_canonical():
    """正準 record で validate_row が空エラー (7列+official_name provenance)。"""
    rec = _canonical_record()
    remark_phrases = set(remarks.load_templates().values())
    errs = vcm.validate_row(rec, 0, remark_phrases)
    assert errs == [], f"unexpected validation errors: {errs}"


def test_validate_catches_stale_url_column():
    """notion-row dict に廃止済み『確認用URL』『正式名称』列があると (h) で余剰列検出 (7列化)。"""
    remark_phrases = set(remarks.load_templates().values())
    notion_row = {
        "会社名": "テスト商事株式会社",
        "正式名称": "テスト商事株式会社",  # 廃止された余剰列 (会社名 title へ統合)
        "住所": "東京都千代田区丸の内1-1-1",
        "郵便番号": "100-0005",
        "法人番号": "1234567890123",
        "電話番号": "03-1234-5678",
        "情報の確かさ": "公的データ取得",
        "備考": "",
        "確認用URL": "https://example.co.jp/contact",  # 廃止された余剰列
    }
    errs = vcm.validate_row(notion_row, 0, remark_phrases)
    assert any("(h)" in e and "確認用URL" in e for e in errs), errs
    assert any("(h)" in e and "正式名称" in e for e in errs), errs
    # 7列(会社名/住所/郵便番号/法人番号/電話番号+情報の確かさ/備考)は全て埋まり (f) 空欄誤検知が出ない。
    assert not any("(f)" in e for e in errs), errs


def test_validate_catches_web_row_without_url():
    """確度『ネット検索(要確認)』かつ source_urls 空 record で (g) 検出。"""
    remark_phrases = set(remarks.load_templates().values())
    rec = {
        "fields": {
            "company_name": "テスト商事",
            "official_name": "テスト商事株式会社",
            "address": "東京都千代田区丸の内1-1-1",
            "postal_code": "100-0005",
            "hojin_bango": "1234567890123",
            "phone_number": "03-1234-5678",
        },
        "overall_certainty": "ネット検索(要確認)",
        "remarks_text": "",
        "source_urls": [],  # 根拠 URL 空
    }
    errs = vcm.validate_row(rec, 0, remark_phrases)
    assert any("(g)" in e for e in errs), errs


def test_validate_catches_record_extra_field_key():
    """record形式でも fields 内の余剰キーを (h) で検出する。"""
    remark_phrases = set(remarks.load_templates().values())
    rec = _canonical_record()
    rec["fields"]["正式名称"] = "テスト商事株式会社"
    errs = vcm.validate_row(rec, 0, remark_phrases)
    assert any("(h)" in e and "正式名称" in e for e in errs), errs


def test_validate_requires_gbizinfo_url_for_nonempty_gbiz_fields():
    """gBizINFO由来の非空値は法人詳細ページURLを必須にする。"""
    remark_phrases = set(remarks.load_templates().values())
    rec = _canonical_record()
    rec["source_by_field"]["official_name"]["url"] = ""
    errs = vcm.validate_row(rec, 0, remark_phrases)
    assert any("(g)" in e and "official_name" in e and "gbizinfo" in e for e in errs), errs


# --- per-field 出典スキーマ (source_by_field) 回帰 -------------------------------

def test_enrich_builds_source_by_field_for_all_six_attributes():
    """enrich が全6属性に origin を必ず付与し、URL を per-field で配線する。

    gBizINFO 3属性 = 法人詳細ページ URL (strong) / 郵便番号 = 日本郵便トップ固定 URL (weak) /
    電話番号 = 番号埋め込み Google 検索 URL (固定手段・weak。R2) / 会社名 = user_input (URL なし)。
    """
    rec = _canonical_record()
    sbf = rec["source_by_field"]
    assert set(sbf.keys()) == set(enrich_company.ATTRIBUTE_FIELDS)
    assert sbf["company_name"] == {"origin": "user_input", "url": ""}
    for field in ("official_name", "hojin_bango", "address"):
        assert sbf[field] == {"origin": "gbizinfo", "url": GBIZ_DETAIL_URL}, field
    assert sbf["postal_code"] == {"origin": "japanpost", "url": postal_api.JAPANPOST_VERIFY_URL}
    # R2: 電話番号の検証URLは Web ヒット URL でなく番号埋め込み Google 検索の固定 URL。
    assert sbf["phone_number"] == {
        "origin": "web",
        "url": enrich_company.phone_search_url(SAMPLE_WEB_FINDINGS["phone"]["value"])}
    assert sbf["phone_number"]["url"] == "https://www.google.com/search?q=%2203-1234-5678%22"


def test_enrich_source_urls_derived_in_column_order():
    """source_urls は source_by_field から列順 (columns.md) で導出される派生値。"""
    rec = _canonical_record()
    urls = rec["source_urls"]
    # URL を持つ属性のみ: 正式名称/住所/郵便番号/法人番号/電話番号 (会社名は user_input・URL 無し)。
    assert [u["attribute"] for u in urls] == ["正式名称", "住所", "郵便番号", "法人番号", "電話番号"]
    for u in urls:
        assert u["url"], u


def test_enrich_unresolved_fields_get_origin_none():
    """web_findings 無し (電話未取得) でも phone_number に origin=none が必ず付く。"""
    rec = _enrich_offline(SAMPLE_ENTITY, None)
    assert rec["source_by_field"]["phone_number"] == {"origin": "none", "url": ""}


def test_enrich_phone_unsearched_uses_pending_remark():
    """Web検索未実施 (web_findings に phone 無し) の電話空欄は『検索して失敗』でなく保留 remark。

    全レコードに『Web検索で…抽出できず』が一律に付く根因の回帰防止: 未検索/候補なしは
    検証で棄却した phone_number とは別キー (phone_no_web_candidate) で記録し、備考が
    『検索したが失敗した』と誤読されないことを担保する。
    """
    rec = _enrich_offline(SAMPLE_ENTITY, None)
    assert "phone_no_web_candidate" in rec["remark_keys"]
    assert "phone_number" not in rec["remark_keys"]
    # 文言が『未検索/候補なし』を表し、検証失敗(整合不成立)の文言と混同しないこと。
    assert "保留" in rec["remarks_text"]
    assert "検証に失敗" not in rec["remarks_text"]
    # 未試行なので attempts に phone の試行履歴は残さない (missing_fields が gap 通知)。
    assert rec["missing_fields"] == ["phone_number"]
    assert not any(a.get("field") == "phone_number" for a in rec["attempts"])


def test_enrich_phone_searched_but_rejected_keeps_failure_remark():
    """Web検索候補を渡して確度検証で棄却した時は従来の取得失敗 remark (phone_number) を維持。

    候補が提供された = Web検索を実施した状態なので、保留 (phone_no_web_candidate) ではなく
    『検証に失敗』を記録し、試行履歴 (attempts) にも rejected を残す。
    """
    rec = _enrich_offline(
        SAMPLE_ENTITY,
        {"phone": {"value": "not-a-phone", "source_url": "https://example.co.jp/contact"}},
    )
    assert rec["fields"]["phone_number"] == ""
    assert "phone_number" in rec["remark_keys"]
    assert "phone_no_web_candidate" not in rec["remark_keys"]
    # 検索を実施した証跡 (rejected) が attempts に残る。
    assert any(
        a.get("field") == "phone_number" and a.get("result") == "rejected"
        for a in rec["attempts"]
    ), rec["attempts"]


def test_enrich_preserves_existing_postal_and_phone_without_refetch(monkeypatch):
    """backfill由来の既存郵便番号/電話番号は再取得せず provenance だけ補う。"""
    def fail_postal(*args, **kwargs):
        raise AssertionError("既存郵便番号があるのに postal API が呼ばれた")

    monkeypatch.setattr(enrich_company, "postal_from_address", fail_postal)
    rec = enrich_company.enrich({
        **SAMPLE_ENTITY,
        "postal_code": "100-0005",
        "phone_number": "03-1234-5678",
    }, web_findings=None)
    assert rec["fields"]["postal_code"] == "100-0005"
    assert rec["fields"]["phone_number"] == "03-1234-5678"
    assert rec["source_by_field"]["postal_code"] == {
        "origin": "japanpost", "url": postal_api.JAPANPOST_VERIFY_URL}
    assert rec["source_by_field"]["phone_number"] == {
        "origin": "web", "url": "https://www.google.com/search?q=%2203-1234-5678%22"}
    assert "phone_number" not in rec["missing_fields"]


def test_postal_api_lookup_returns_japanpost_verify_url():
    """日本郵便 API 一意確定時の source_url は郵便番号検索の固定 URL (weak provenance)。

    _search_fn 注入でトークン/ネットを介さず、町域一致の単一候補を確定できることを検証する。
    """
    def hit_search(query):
        return ([{"zip_code": "1000005", "pref_name": "東京都",
                  "city_name": "千代田区", "town_name": "丸の内"}], 3)

    hit = postal_api.lookup_postal("東京都千代田区丸の内1-1-1", _search_fn=hit_search)
    assert hit["value"] == "100-0005"
    # R1: 検証URLは日本郵便トップ (郵便番号検索の入口) の固定 URL。
    assert hit["source_url"] == postal_api.JAPANPOST_VERIFY_URL == "https://www.post.japanpost.jp/"
    assert hit["certainty"] == enrich_company.CERTAINTY_PUBLIC_FETCHED
    # 候補ゼロ (未一致) → 誤値を入れず空欄。
    miss = postal_api.lookup_postal("東京都千代田区丸の内1-1-1", _search_fn=lambda q: ([], None))
    assert miss["value"] == ""
    assert miss["source_url"] == ""


def test_postal_api_pick_best_is_conservative():
    """pick_best は誤値を入れない: 都道府県のみ一致(level1)/zip 割れ複数候補は None。"""
    # zip が 1 種類に収束 → 確定。
    converged = [{"zip_code": "1000005", "town_name": "丸の内"},
                 {"zip_code": "1000005", "town_name": "丸の内"}]
    assert postal_api.pick_best(converged, 3, {"town_name": "丸の内"}) is not None
    # 都道府県のみ一致 (level=1) → 広すぎるため確定しない。
    assert postal_api.pick_best([{"zip_code": "1000005"}], 1, {}) is None
    # 同一 town で zip が割れる → 曖昧で確定しない。
    split = [{"zip_code": "1000005", "town_name": "丸の内"},
             {"zip_code": "1000006", "town_name": "丸の内"}]
    assert postal_api.pick_best(split, 3, {}) is None
    # 候補ゼロ → None。
    assert postal_api.pick_best([], 3, {}) is None


def test_postal_api_address_to_query_splits_pref_city_town():
    """address_to_query が都道府県/市区町村(政令市・郡含む)/町域へ分解し番地を落とす。"""
    assert postal_api.address_to_query("東京都千代田区霞が関1-1-1") == {
        "pref_name": "東京都", "city_name": "千代田区", "town_name": "霞が関"}
    # 政令市は 市+区 を 1 単位の city に取り込む。
    assert postal_api.address_to_query("神奈川県横浜市港北区日吉2-3") == {
        "pref_name": "神奈川県", "city_name": "横浜市港北区", "town_name": "日吉"}
    # 郡 は終端でないため city へ取り込む。
    assert postal_api.address_to_query("愛知県額田郡幸田町大字菱池1")["city_name"] == "額田郡幸田町"
    # 都道府県起点でない住所は空クエリ (誤値を入れない)。
    assert postal_api.address_to_query("丸の内1-1-1") == {}


def test_postal_api_detect_egress_ip(monkeypatch):
    """送信元IP自動検出 (_opener 注入でネット非依存): 正常IP→採用 / 不正・例外→None。"""
    monkeypatch.setattr(postal_api, "_EGRESS_CACHE", {})
    assert postal_api.detect_egress_ip(_opener=lambda url, timeout: "203.0.113.10\n") == "203.0.113.10"
    monkeypatch.setattr(postal_api, "_EGRESS_CACHE", {})
    assert postal_api.detect_egress_ip(_opener=lambda url, timeout: "not-an-ip!!") is None
    monkeypatch.setattr(postal_api, "_EGRESS_CACHE", {})
    assert postal_api.detect_egress_ip(
        _opener=lambda url, timeout: (_ for _ in ()).throw(OSError("down"))) is None


def test_resolve_egress_ip_prefers_pin_then_detect(monkeypatch):
    """resolve_egress_ip: 明示 pin (notion_config.get_japanpost_egress_ip = Keychain pin/env)
    を最優先で採り、pin 不在時のみ自動検出 (detect_egress_ip) へフォールバックする。"""
    monkeypatch.setattr(postal_api.notion_config, "get_japanpost_egress_ip", lambda *a, **k: "198.51.100.7")
    monkeypatch.setattr(postal_api, "detect_egress_ip", lambda *a, **k: "203.0.113.10")
    assert postal_api.resolve_egress_ip() == "198.51.100.7"  # pin 優先 (自動検出より上)
    monkeypatch.setattr(postal_api.notion_config, "get_japanpost_egress_ip", lambda *a, **k: None)
    assert postal_api.resolve_egress_ip() == "203.0.113.10"  # pin 無し → 自動検出


def test_get_japanpost_egress_ip_keychain_then_env(monkeypatch):
    """notion_config.get_japanpost_egress_ip: Keychain `egress_ip` を優先し、Keychain 不在時のみ
    env `COMPANY_MASTER_EGRESS_IP` (低優先) へフォールバックする (pin 解決順の直接検証)。"""
    nc = postal_api.notion_config
    # Keychain 有 → Keychain 値 (env を無視する)。
    monkeypatch.setattr(
        nc, "_keychain_password",
        lambda s, a: "kc-198.51.100.7" if a == nc.JAPANPOST_EGRESS_IP_ACCOUNT else None)
    monkeypatch.setenv(nc.COMPANY_MASTER_EGRESS_IP_ENV, "env-203.0.113.10")
    assert nc.get_japanpost_egress_ip() == "kc-198.51.100.7"
    # Keychain 無 + env 有 → env 値。
    monkeypatch.setattr(nc, "_keychain_password", lambda s, a: None)
    assert nc.get_japanpost_egress_ip() == "env-203.0.113.10"
    # Keychain 無 + env 無 → None (自動検出側へ委ねる)。
    monkeypatch.delenv(nc.COMPANY_MASTER_EGRESS_IP_ENV, raising=False)
    assert nc.get_japanpost_egress_ip() is None


def test_postal_api_proxy_mode_routes_through_proxy(monkeypatch):
    """proxy_url 設定時: get_token を呼ばず query をプロキシへ POST し addresses/level を得る。"""
    monkeypatch.setattr(postal_api.notion_config, "get_postal_proxy_url",
                        lambda: "https://proxy.example/addresszip")
    monkeypatch.setattr(postal_api.notion_config, "get_postal_proxy_token", lambda: "tok123")
    monkeypatch.setattr(postal_api, "get_token",
                        lambda *a, **k: pytest.fail("proxyモードで get_token が呼ばれた"))
    seen: dict = {}

    def fake_post(url, payload, headers, timeout=30):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization")
        return {"addresses": [{"zip_code": "1000005", "town_name": "丸の内"}], "level": 3}

    monkeypatch.setattr(postal_api, "_post_json", fake_post)
    r = postal_api.lookup_postal("東京都千代田区丸の内1-1-1")
    assert r["value"] == "100-0005"
    assert seen["url"] == "https://proxy.example/addresszip"
    assert seen["auth"] == "Bearer tok123"


def test_postal_api_proxy_mode_no_token_omits_auth_header(monkeypatch):
    """proxy_token 未設定なら Authorization ヘッダを付けない (無認証プロキシ運用)。"""
    monkeypatch.setattr(postal_api.notion_config, "get_postal_proxy_url",
                        lambda: "https://proxy.example/addresszip")
    monkeypatch.setattr(postal_api.notion_config, "get_postal_proxy_token", lambda: None)
    seen: dict = {}

    def fake_post(url, payload, headers, timeout=30):
        seen["auth"] = headers.get("Authorization")
        return {"addresses": [{"zip_code": "1000005", "town_name": "丸の内"}], "level": 3}

    monkeypatch.setattr(postal_api, "_post_json", fake_post)
    postal_api.lookup_postal("東京都千代田区丸の内1-1-1")
    assert seen["auth"] is None


def test_postal_api_base_url_override(monkeypatch):
    """接続先は notion_config の上書き (テスト/stub 環境) を優先し、無ければ本番既定。"""
    monkeypatch.setattr(postal_api.notion_config, "get_japanpost_base_url",
                        lambda: "https://stub-qz73x.da.pf.japanpost.jp")
    assert postal_api._base_url() == "https://stub-qz73x.da.pf.japanpost.jp"
    monkeypatch.setattr(postal_api.notion_config, "get_japanpost_base_url", lambda: None)
    assert postal_api._base_url() == postal_api.BASE_URL == "https://api.da.pf.japanpost.jp"


def test_post_json_classifies_404_as_notfound(monkeypatch):
    """実 API は『該当住所なし』を HTTP 404 で返す。_post_json はこれを notfound に分類する。"""
    import io
    import urllib.error

    def boom(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 404, "nf", {}, io.BytesIO('{"message":"該当する住所が見つかりませんでした"}'.encode()))

    monkeypatch.setattr(postal_api.urllib.request, "urlopen", boom)
    with pytest.raises(postal_api.JapanPostError) as exc:
        postal_api._post_json("https://x/api/v2/addresszip", {"freeword": "x"}, {})
    assert exc.value.kind == "notfound"


def test_postal_api_404_is_miss_not_error(monkeypatch):
    """addresszip の 404(該当なし) は error でなく miss → 未確定 + remark postal_code (通信障害扱いにしない)。"""
    monkeypatch.setattr(postal_api.notion_config, "get_postal_proxy_url", lambda: None)
    monkeypatch.setattr(postal_api, "resolve_egress_ip", lambda: "203.0.113.10")
    monkeypatch.setattr(postal_api, "get_token", lambda *a, **k: "tok")
    monkeypatch.setattr(postal_api, "_post_json",
                        lambda *a, **k: (_ for _ in ()).throw(
                            postal_api.JapanPostError("notfound", "HTTP 404 該当住所なし")))
    r = postal_api.lookup_postal("東京都千代田区霞が関")
    assert r["value"] == "" and r["remark_key"] == "postal_code"
    assert r["attempts"] and all(a["result"] == "miss" for a in r["attempts"])


def test_postal_api_town_variants():
    """_town_variants は町域を「具体→粗」で候補化し、小字「字○○」/大字を段階剥離する。

    日本郵便の町域DBは大字粒度までで小字は照合に通らないため、素の町域に加え小字/大字を
    削ったバリアントを並べる。字も大字も無い町域は元の1件のみ (無駄な再照会をしない)。
    """
    # 小字「字下鳥ノ巣」を削った町域を後段に追加。
    assert postal_api._town_variants("北京田字下鳥ノ巣") == ["北京田字下鳥ノ巣", "北京田"]
    # 先頭「大字」を削る (小字は無いので2件)。
    assert postal_api._town_variants("大字菱池") == ["大字菱池", "菱池"]
    # 大字+小字の両方: 4バリアント (素 → 大字付き小字削り → 大字削り → 大字+小字削り)。
    assert postal_api._town_variants("大字北京田字下鳥ノ巣") == [
        "大字北京田字下鳥ノ巣", "大字北京田", "北京田字下鳥ノ巣", "北京田"]
    # 字も大字も無い町域は元の1件のみ。
    assert postal_api._town_variants("霞が関") == ["霞が関"]
    # 空は空 (照会クエリを作らない)。
    assert postal_api._town_variants("") == []


def test_postal_api_koaza_fallback_hits_town_level():
    """小字付き住所は素の町域で 404 (miss) でも、小字を削った町域バリアントで確定する。

    報告ケース再現 (山形県鶴岡市北京田字下鳥ノ巣)。素の town_name は町域DBに無く miss、
    小字を削った '北京田' で町域一致の単一候補が取れ、フォールバック段で 997-0053 を確定する。
    """
    def _search_fn(query):
        town = query.get("town_name")
        if town and "北京田字下鳥ノ巣" in town:
            return ([], None)  # 小字残りは町域DBに無い → miss
        if town == "北京田":
            return ([{"zip_code": "9970053", "pref_name": "山形県",
                      "city_name": "鶴岡市", "town_name": "北京田"}], 3)
        return ([], None)

    r = postal_api.lookup_postal("山形県鶴岡市北京田字下鳥ノ巣23番地1", _search_fn=_search_fn)
    assert r["value"] == "997-0053"
    # フォールバック段 (小字剥離後) で取れたことを pattern で可視化する。
    hit = [a for a in r["attempts"] if a["result"] == "hit"]
    assert len(hit) == 1
    assert hit[0]["pattern"] == "structured_town_trimmed"


def test_postal_api_koaza_fallback_diverging_zips_stays_empty():
    """町域へ削った結果 zip が割れるケースは空欄を保つ (誤値非混入の回帰ガード)。

    小字を削った '北京田' に同名で zip 違いの複数候補が返ると pick_best が確定せず、
    フォールバックを足しても誤値を入れない非対称コスト原則を維持する。
    """
    def _search_fn(query):
        town = query.get("town_name")
        if town == "北京田":
            return ([{"zip_code": "9970053", "pref_name": "山形県",
                      "city_name": "鶴岡市", "town_name": "北京田"},
                     {"zip_code": "9970063", "pref_name": "山形県",
                      "city_name": "鶴岡市", "town_name": "北京田"}], 3)
        return ([], None)

    r = postal_api.lookup_postal("山形県鶴岡市北京田字下鳥ノ巣23番地1", _search_fn=_search_fn)
    assert r["value"] == ""


def test_postal_api_town_variant_no_extra_query_when_no_koaza():
    """字を含まない町域では剥離バリアント照会をしない (無駄な照会をしない)。

    '丸の内' は字も大字も無いため structured クエリは1回だけ投げられ、
    structured_town_trimmed pattern は attempts に出ない (early-return で hit)。
    """
    seen: list[dict] = []

    def _search_fn(query):
        seen.append(query)
        if query.get("town_name") == "丸の内":
            return ([{"zip_code": "1000005", "pref_name": "東京都",
                      "city_name": "千代田区", "town_name": "丸の内"}], 3)
        return ([], None)

    r = postal_api.lookup_postal("東京都千代田区丸の内1-1-1", _search_fn=_search_fn)
    assert r["value"] == "100-0005"
    # 構造化クエリ (town_name='丸の内') は1回のみ。
    structured_seen = [q for q in seen if q.get("town_name")]
    assert len(structured_seen) == 1
    # 剥離バリアント段の pattern は記録されない。
    assert all(a["pattern"] != "structured_town_trimmed" for a in r["attempts"])


def test_postal_api_oaza_fallback_hits_town_level():
    """大字付き住所は素の町域 (大字○○) で miss でも、大字を削った町域で確定する。

    盲点ケース (愛知県額田郡幸田町大字菱池) の lookup 統合検証。素の town_name='大字菱池' が
    町域DBに無く miss、先頭『大字』を削った '菱池' で単一候補が取れフォールバック段で確定する。
    """
    def _search_fn(query):
        town = query.get("town_name")
        if town == "菱池":
            return ([{"zip_code": "4440124", "pref_name": "愛知県",
                      "city_name": "額田郡幸田町", "town_name": "菱池"}], 3)
        return ([], None)  # '大字菱池'・freeword は町域DBに無い → miss

    r = postal_api.lookup_postal("愛知県額田郡幸田町大字菱池1", _search_fn=_search_fn)
    assert r["value"] == "444-0124"
    hit = [a for a in r["attempts"] if a["result"] == "hit"]
    assert len(hit) == 1 and hit[0]["pattern"] == "structured_town_trimmed"


def test_postal_api_pick_best_prefix():
    """pick_best_prefix は最長前方一致を一意確定で選ぶ: 最長選択 / 不一致・zip割れ・空は None。"""
    cands = [{"zip_code": "0010023", "town_name": "北23条西"},
             {"zip_code": "0010024", "town_name": "北24条西"}]
    # 入力住所の先頭に一致する最長の町域 (北24条西) を採る。
    best = postal_api.pick_best_prefix(cands, "北24条西2丁目")
    assert best is not None and postal_api._zip_of(best) == "0010024"
    # 前方一致する町域が無い → None。
    assert postal_api.pick_best_prefix([{"zip_code": "1", "town_name": "美原町"}], "北京田下鳥ノ巣") is None
    # 最長一致群の zip が割れる → 確定しない (誤値を入れない)。
    split = [{"zip_code": "9970053", "town_name": "北京田"},
             {"zip_code": "9970063", "town_name": "北京田"}]
    assert postal_api.pick_best_prefix(split, "北京田下鳥ノ巣") is None
    # 空候補・空 rest → None。
    assert postal_api.pick_best_prefix([], "北京田") is None
    assert postal_api.pick_best_prefix(cands, "") is None


def _city_list_stub(city_towns):
    """{pref,city} 照会では市の町域一覧 (level=2) を、town_name 厳密指定では一致時のみ hit を返す
    日本郵便 addresszip の挙動模擬 (小字付き等の未登録 town は miss)。"""
    def _search_fn(query):
        if query.get("freeword"):
            return ([], None)
        town = query.get("town_name")
        if town is None:  # {pref,city} のみ → 町域一覧
            return ([{"zip_code": z, "town_name": t} for t, z in city_towns], 2)
        hit = [(t, z) for t, z in city_towns if t == town]
        return ([{"zip_code": hit[0][1], "town_name": town}], 3) if hit else ([], None)
    return _search_fn


def test_postal_api_prefix_match_fallback_unmarked_koaza():
    """「字」マーカーの無い文字列末尾 (北京田下鳥ノ巣) も、市区町村前方一致で町域を確定する。

    town_name='北京田下鳥ノ巣' は町域DBに無く structured も _town_variants も miss だが、
    {都道府県+市} の町域一覧の '北京田' が入力住所の最長前方一致で拾える。
    """
    stub = _city_list_stub([("北京田", "9970053"), ("美原町", "9970099")])
    r = postal_api.lookup_postal("山形県鶴岡市北京田下鳥ノ巣5", _search_fn=stub)
    assert r["value"] == "997-0053"
    hit = [a for a in r["attempts"] if a["result"] == "hit"]
    assert len(hit) == 1 and hit[0]["pattern"] == "structured_city_prefix_match"


def test_postal_api_prefix_match_recovers_numeric_town():
    """町域名に数字を含む住所 (北24条西2丁目) も前方一致で救う (_strip_banchi 誤切りの最終救済)。

    _strip_banchi が町域を '北' に誤切りし structured/freeword とも miss でも、町域一覧の
    '北24条西' が入力住所の最長前方一致で拾える (短い前方一致 '北23条西' 等には化けない)。
    """
    stub = _city_list_stub([("北23条西", "0010023"), ("北24条西", "0010024"), ("北25条西", "0010025")])
    r = postal_api.lookup_postal("北海道札幌市北区北24条西2丁目", _search_fn=stub)
    assert r["value"] == "001-0024"
    hit = [a for a in r["attempts"] if a["result"] == "hit"]
    assert len(hit) == 1 and hit[0]["pattern"] == "structured_city_prefix_match"


def test_postal_api_prefix_match_diverging_zips_stays_empty():
    """前方一致の最長群で zip が割れる町域一覧は空欄を保つ (前方一致でも誤値を入れない)。"""
    def _search_fn(query):
        if query.get("town_name") is None and not query.get("freeword"):
            return ([{"zip_code": "9970053", "town_name": "北京田"},
                     {"zip_code": "9970063", "town_name": "北京田"}], 2)
        return ([], None)

    r = postal_api.lookup_postal("山形県鶴岡市北京田下鳥ノ巣", _search_fn=_search_fn)
    assert r["value"] == ""


def test_no_hardcoded_absolute_paths_in_scripts():
    """scripts に環境固有の絶対パス (/Users /home /private 等) が混入していない (移植性回帰)。

    不特定多数が任意の場所へ install しても動くよう、パスは全て __file__ 起点で解決する。
    """
    import re
    bad = re.compile(r"/Users/|/home/[A-Za-z]|/private/|[A-Za-z]:\\\\")
    offenders = []
    for py in sorted(SHARED_SCRIPTS.glob("*.py")):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if bad.search(line):
                offenders.append(f"{py.name}:{i}: {line.strip()[:80]}")
    assert not offenders, "ハードコード絶対パス:\n" + "\n".join(offenders)


def test_scripts_resolve_references_from_any_cwd(tmp_path):
    """インストール場所/cwd 非依存: 任意の cwd から scripts を import し参照を解決できる。

    ハードコード絶対パスや cwd 依存の混入を回帰検出する (不特定多数の任意 install 場所対応の保証)。
    """
    import subprocess
    code = (
        "import sys; sys.path.insert(0, %r); "
        "import confirm_url, remarks, notion_upsert, postal_api, bootstrap_plugin; "
        "ps = [confirm_url.TEMPLATE_MD, remarks.TEMPLATES_MD, notion_upsert.SCHEMA_JSON]; "
        "assert all(p.is_absolute() and p.exists() for p in ps), ps; "
        "assert bootstrap_plugin.plugin_root().is_absolute(); "
        "print('OK')"
    ) % str(SHARED_SCRIPTS)
    res = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path),
                         capture_output=True, text=True, timeout=30)
    assert res.returncode == 0 and "OK" in res.stdout, res.stderr


def test_postal_proxy_config_resolution_keychain_then_env(monkeypatch):
    """proxy_url: Keychain 優先 → 無ければ env。"""
    nc = postal_api.notion_config
    monkeypatch.setattr(nc, "_keychain_password",
                        lambda s, a: "kc-url" if a == "proxy_url" else None)
    monkeypatch.delenv("COMPANY_MASTER_POSTAL_PROXY_URL", raising=False)
    assert nc.get_postal_proxy_url() == "kc-url"
    monkeypatch.setattr(nc, "_keychain_password", lambda s, a: None)
    monkeypatch.setenv("COMPANY_MASTER_POSTAL_PROXY_URL", "env-url")
    assert nc.get_postal_proxy_url() == "env-url"


def test_get_japanpost_credentials_keychain_then_env(monkeypatch):
    """get_japanpost_credentials: Keychain (client_id/secret_key) 優先 → 不在時のみ env
    (COMPANY_MASTER_JAPANPOST_CLIENT_ID / _SECRET_KEY) へフォールバック (鍵 env 経路の検証)。"""
    nc = postal_api.notion_config
    # Keychain 有 → Keychain 値 (env を無視)。
    kc = {nc.JAPANPOST_CLIENT_ID_ACCOUNT: "kc-cid", nc.JAPANPOST_SECRET_KEY_ACCOUNT: "kc-sec"}
    monkeypatch.setattr(nc, "_keychain_password", lambda s, a: kc.get(a))
    monkeypatch.setenv(nc.JAPANPOST_CLIENT_ID_ENV, "env-cid")
    monkeypatch.setenv(nc.JAPANPOST_SECRET_KEY_ENV, "env-sec")
    assert nc.get_japanpost_credentials() == ("kc-cid", "kc-sec")
    assert nc.has_japanpost_credentials() is True
    # Keychain 無 + env 有 → env 値 (Keychain 不在のコンテナ/プロキシ運用)。
    monkeypatch.setattr(nc, "_keychain_password", lambda s, a: None)
    assert nc.get_japanpost_credentials() == ("env-cid", "env-sec")
    assert nc.has_japanpost_credentials() is True
    # Keychain 無 + env 無 → ("", "")・has は False。
    monkeypatch.delenv(nc.JAPANPOST_CLIENT_ID_ENV, raising=False)
    monkeypatch.delenv(nc.JAPANPOST_SECRET_KEY_ENV, raising=False)
    assert nc.get_japanpost_credentials() == ("", "")
    assert nc.has_japanpost_credentials() is False


# --- postal_proxy fail-closed / レート制限 (中継プロキシ単体ロジック) 回帰 --------

import postal_proxy  # noqa: E402


def test_postal_proxy_is_loopback_host():
    """_is_loopback_host: ループバック (127.0.0.1/localhost/::1) のみ True、それ以外は False。"""
    assert postal_proxy._is_loopback_host("127.0.0.1") is True
    assert postal_proxy._is_loopback_host("localhost") is True
    assert postal_proxy._is_loopback_host("::1") is True
    # 大文字/前後空白も正規化して判定する。
    assert postal_proxy._is_loopback_host(" LocalHost ") is True
    # 非ループバック (公開bind・全インタフェース・外部) は False。
    assert postal_proxy._is_loopback_host("0.0.0.0") is False
    assert postal_proxy._is_loopback_host("203.0.113.10") is False
    assert postal_proxy._is_loopback_host("example.com") is False


def test_postal_proxy_fail_closed_decision_for_public_bind_without_token():
    """main() の fail-closed 判定ロジック (listen させず単体検証):
    非ループバック bind かつ proxy_token 未設定 → 拒否すべき。それ以外 (token 有 or ループバック) は許容。
    """
    # main() は `not _client_token() and not _is_loopback_host(host)` で exit 2 する。
    # listen 副作用を避け、この判定式を直接組み立てて真偽を確認する。
    def should_reject(token, host):
        return (not token) and (not postal_proxy._is_loopback_host(host))

    assert should_reject(None, "0.0.0.0") is True          # 公開bind + 無認証 → 拒否
    assert should_reject("", "203.0.113.10") is True        # 外部bind + 空トークン → 拒否
    assert should_reject(None, "127.0.0.1") is False        # ループバックなら無認証許容
    assert should_reject("tok", "0.0.0.0") is False         # 公開bindでも token 有なら許容
    assert should_reject("tok", "127.0.0.1") is False


def test_postal_proxy_rate_ok_window_and_per_ip(monkeypatch):
    """_rate_ok: 窓内上限到達で False、窓リセットで再 True、IP 独立 (時刻注入で決定論検証)。"""
    monkeypatch.setattr(postal_proxy, "_RATE_STATE", {})
    monkeypatch.setattr(postal_proxy, "_RATE_MAX_PER_WINDOW", 2)
    monkeypatch.setattr(postal_proxy, "_RATE_WINDOW_SEC", 60)
    ip = "203.0.113.10"
    assert postal_proxy._rate_ok(ip, 1000.0) is True   # 1 回目
    assert postal_proxy._rate_ok(ip, 1001.0) is True   # 2 回目 (上限ちょうど)
    assert postal_proxy._rate_ok(ip, 1002.0) is False  # 3 回目 → 上限超過で False
    # 別 IP は独立カウント (相互に影響しない)。
    assert postal_proxy._rate_ok("198.51.100.7", 1002.0) is True
    # 窓 (60s) を跨ぐとリセットされ再び True。
    assert postal_proxy._rate_ok(ip, 1002.0 + 60) is True


def test_postal_proxy_rate_lock_exists():
    """_RATE_LOCK が threading.Lock 実体として存在する (ThreadingHTTPServer の lost update 防止)。"""
    import threading

    lock = postal_proxy._RATE_LOCK
    assert isinstance(lock, type(threading.Lock()))
    # acquire/release が機能する (コンテキストマネージャとして使える)。
    with lock:
        assert True


def test_resolve_entity_includes_detail_page_source_url(monkeypatch):
    """resolve の entity に gBizINFO 法人詳細ページ URL (source_url) が載る (enrich へ伝搬)。"""
    monkeypatch.setattr(resolve_company, "_request", lambda url, token: _GBIZ_SINGLE_HIT)
    res = resolve_company.resolve_by_hojin_bango("1234567890123", "dummy-token")
    assert res["entity"]["source_url"] == resolve_company.detail_page_url("1234567890123")
    assert res["entity"]["source_url"] == res["source_url"]


def test_validate_per_field_origin_required_and_web_needs_url():
    """(g) 新形式: 全6属性 origin 必須・origin=web は url 必須。正準 record は PASS。"""
    remark_phrases = set(remarks.load_templates().values())
    good = _canonical_record()
    assert vcm.validate_row(good, 0, remark_phrases) == []

    # origin 欠落 (phone_number を落とす) → (g)。
    missing = json.loads(json.dumps(good))
    del missing["source_by_field"]["phone_number"]
    errs = vcm.validate_row(missing, 0, remark_phrases)
    assert any("(g)" in e and "phone_number" in e for e in errs), errs

    # enum 5値外 origin → (g)。
    bad_enum = json.loads(json.dumps(good))
    bad_enum["source_by_field"]["address"]["origin"] = "WEB_SEARCH"
    errs = vcm.validate_row(bad_enum, 0, remark_phrases)
    assert any("(g)" in e and "address" in e for e in errs), errs

    # origin=web だが url 空 → (g)。
    web_no_url = json.loads(json.dumps(good))
    web_no_url["source_by_field"]["phone_number"]["url"] = ""
    errs = vcm.validate_row(web_no_url, 0, remark_phrases)
    assert any("(g)" in e and "phone_number" in e for e in errs), errs


def test_validate_legacy_record_without_source_by_field_rejects_nonempty_postal():
    """旧形式 record の非空郵便番号は出典不明として reject する (書き込みゲート)。"""
    remark_phrases = set(remarks.load_templates().values())
    rec = _canonical_record()
    del rec["source_by_field"]
    errs = vcm.validate_row(rec, 0, remark_phrases)
    assert any("非空 postal_code" in e and "source_by_field" in e for e in errs), errs


# --- 本文同期: URL 非減少マージ + pagination (B: URL喪失バグ修復) ----------------

def _block(btype: str, text: str, bid: str) -> dict:
    return {"id": bid, "object": "block", "type": btype,
            btype: {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def test_sync_confirm_url_body_preserves_existing_urls(monkeypatch):
    """既存本文に URL あり × 新 source_by_field が URL を提示できない → 同期後も URL 非減少。

    backfill が web_findings 無しで enrich した record (phone=none) で本文同期しても、
    既存のネット検索由来 URL が「ありません」へ全置換されない (バグ修復の回帰)。
    pagination (has_more/next_cursor) を跨いだセクション検出も同時に検証する。
    """
    heading = confirm_url.load_template()["heading"]
    page1 = {"results": [_block("paragraph", "メモ", "b0")] * 1, "has_more": True,
             "next_cursor": "cur-2"}
    page2 = {"results": [
        _block("heading_2", heading, "b1"),
        _block("paragraph", "旧導入文", "b2"),
        _block("bulleted_list_item", "電話番号: https://old.example.co.jp/contact", "b3"),
    ], "has_more": False}
    deleted: list = []
    appended: list = []

    def fake_api(method, path, token, body=None):
        if method == "GET" and "start_cursor=cur-2" in path:
            return page2
        if method == "GET":
            return page1
        if method == "DELETE":
            deleted.append(path)
            return {}
        if method == "PATCH":
            appended.append(body)
            return {}
        raise AssertionError(f"unexpected api call: {method} {path}")

    monkeypatch.setattr(notion_upsert, "_api", fake_api)
    sbf = {f: {"origin": "none", "url": ""} for f in confirm_url.ATTRIBUTE_FIELDS}
    sbf["company_name"] = {"origin": "user_input", "url": ""}
    res = notion_upsert.sync_confirm_url_body("page-x", "tok", sbf)
    assert res["confirm_url_body"] == "synced"
    assert res["replaced_existing"] is True
    assert res["kept_existing_urls"] == 1
    assert deleted == ["/blocks/b1", "/blocks/b2", "/blocks/b3"]
    texts = []
    for blk in appended[0]["children"]:
        btype = blk["type"]
        texts.extend(x["text"]["content"] for x in blk[btype]["rich_text"])
    assert any("https://old.example.co.jp/contact" in t for t in texts), texts
    # 全置換の虚偽文言 (旧 body_no_urls 系) が出ていないこと。
    assert not any("ありません" in t for t in texts), texts


def test_sync_confirm_url_body_idempotent_rerender(monkeypatch):
    """同一 source_by_field で 2 回同期 → 2 回目の本文が 1 回目と byte 一致 (冪等)。"""
    state = {"children": [], "next_id": 0}

    def fake_api(method, path, token, body=None):
        if method == "GET":
            return {"results": list(state["children"]), "has_more": False}
        if method == "DELETE":
            bid = path.rsplit("/", 1)[-1]
            state["children"] = [b for b in state["children"] if b["id"] != bid]
            return {}
        if method == "PATCH":
            for blk in body["children"]:
                state["next_id"] += 1
                stored = json.loads(json.dumps(blk))
                stored["id"] = f"b{state['next_id']}"
                state["children"].append(stored)
            return {}
        raise AssertionError(f"unexpected api call: {method} {path}")

    def body_texts():
        out = []
        for blk in state["children"]:
            btype = blk["type"]
            out.append("".join(x["text"]["content"] for x in blk[btype]["rich_text"]))
        return out

    monkeypatch.setattr(notion_upsert, "_api", fake_api)
    notion_upsert.sync_confirm_url_body("page-y", "tok", SAMPLE_SOURCE_BY_FIELD)
    first = body_texts()
    notion_upsert.sync_confirm_url_body("page-y", "tok", SAMPLE_SOURCE_BY_FIELD)
    second = body_texts()
    assert first == second
    assert len(first) == 7  # heading + intro + bullet×5 (会社名は official_name 統合・正式名称独立 bullet 廃止)


# --- confirm_url fail-closed (GAP-2 回帰) --------------------------------------

def test_confirm_url_fail_closed_on_missing_md(tmp_path):
    """md 不在/破損で load_template が ValueError を送出する (fail-closed・既定値なし)。"""
    missing = tmp_path / "no-such-template.md"
    with pytest.raises(ValueError):
        confirm_url.load_template(missing)

    broken = tmp_path / "broken-template.md"
    broken.write_text("# 表が無い md\n本文のみ\n", encoding="utf-8")
    with pytest.raises(ValueError):
        confirm_url.load_template(broken)


# --- resolve_by_name 自動確定条件 (会社名のみは自動確定不可) 回帰 ----------------

_GBIZ_SINGLE_HIT = {
    "hojin-infos": [{
        "corporate_number": "1234567890123",
        "name": "テスト商事株式会社",
        "location": "東京都千代田区丸の内1-1-1",
    }]
}


def test_resolve_by_name_name_only_single_hit_not_autoconfirmed(monkeypatch):
    """会社名のみ (address=None)・gBizINFO 単一ヒット → 自動確定せず候補列挙のみ。

    自動確定は『法人番号一致 or 会社名+住所2要素一致』のみ (SKILL.md チェックリスト正本)。
    """
    monkeypatch.setattr(resolve_company, "_request", lambda url, token: _GBIZ_SINGLE_HIT)
    res = resolve_company.resolve_by_name("テスト商事", "dummy-token", address=None)
    assert "entity" not in res, "会社名のみ入力で自動確定してはならない"
    assert res["certainty"] == "未確定(要確認)"
    assert len(res["candidates"]) == 1  # 候補としては提示する


def test_resolve_by_name_with_matching_address_autoconfirmed(monkeypatch):
    """会社名+住所2要素一致 (単一ヒット+住所前方一致) → 自動確定 (正常系の維持確認)。"""
    monkeypatch.setattr(resolve_company, "_request", lambda url, token: _GBIZ_SINGLE_HIT)
    res = resolve_company.resolve_by_name(
        "テスト商事", "dummy-token", address="東京都千代田区丸の内1-1-1"
    )
    assert res.get("entity", {}).get("hojin_bango") == "1234567890123"
    assert res["certainty"] == "公的データで確認済み"


# --- backfill 検証ゲート (VERT-01 解消) 回帰 -----------------------------------

def test_backfill_invalid_enriched_row_is_deferred_not_patched(monkeypatch):
    """validate_row 違反の enriched 行は PATCH されず deferred + replay 退避へ回る。"""
    target_row = {
        "page_id": "page-1",
        "fields": {
            "company_name": "テスト商事",
            "official_name": "",  # 空欄列あり → backfill 対象
            "address": "東京都千代田区丸の内1-1-1",
            "postal_code": "",
            "hojin_bango": "1234567890123",
            "phone_number": "",
        },
        "certainty": "未確定(要確認)",
        "remarks_text": "",
    }
    # (e) 違反 (英語 enum 確度) を含む enriched record。
    bad_record = {
        "fields": {
            "company_name": "テスト商事",
            "official_name": "テスト商事株式会社",
            "address": "東京都千代田区丸の内1-1-1",
            "postal_code": "100-0005",
            "hojin_bango": "1234567890123",
            "phone_number": "03-1234-5678",
        },
        "overall_certainty": "VERIFIED",
        "remarks_text": "",
        "source_urls": [],
    }
    monkeypatch.setattr(backfill, "precondition_gate", lambda: ({}, "tok"))
    monkeypatch.setattr(backfill.notion_config, "get_gbizinfo_token", lambda cfg=None: "g")
    monkeypatch.setattr(backfill.notion_config, "get_db_id", lambda key: "db-id")
    monkeypatch.setattr(
        backfill.notion_upsert, "ensure_schema_preflight", lambda db_id, token: None
    )
    monkeypatch.setattr(backfill, "query_rows", lambda db_id, token: [target_row])
    monkeypatch.setattr(
        backfill, "resolve_row",
        lambda row, gtoken: {"entity": dict(bad_record["fields"])},
    )
    monkeypatch.setattr(
        backfill.enrich_company, "enrich",
        lambda entity, web_findings=None: bad_record,
    )
    patch_calls: list = []
    monkeypatch.setattr(
        backfill, "patch_empty_cells",
        lambda *a, **k: patch_calls.append(a) or {"action": "updated", "patched_properties": ["x"]},
    )
    replays: list = []
    monkeypatch.setattr(backfill, "append_replay", lambda rec: replays.append(rec))
    monkeypatch.setattr(sys, "argv", ["backfill.py", "--dry-run"])

    rc = backfill.main()
    assert rc == 0
    assert patch_calls == [], "validate_row 違反行が PATCH された (検証ゲート迂回)"
    assert replays and replays[0]["status"] == "deferred"
    assert any("(e)" in v for v in replays[0]["violations"])


def test_backfill_valid_enriched_row_is_patched(monkeypatch):
    """validate_row PASS の enriched 行は従来どおり PATCH 経路へ進む (ゲートの過剰遮断なし)。"""
    target_row = {
        "page_id": "page-2",
        "fields": {
            "company_name": "テスト商事",
            "official_name": "",
            "address": "東京都千代田区丸の内1-1-1",
            "postal_code": "",
            "hojin_bango": "1234567890123",
            "phone_number": "",
        },
        "certainty": "未確定(要確認)",
        "remarks_text": "",
    }
    good_record = _canonical_record()
    monkeypatch.setattr(backfill, "precondition_gate", lambda: ({}, "tok"))
    monkeypatch.setattr(backfill.notion_config, "get_gbizinfo_token", lambda cfg=None: "g")
    monkeypatch.setattr(backfill.notion_config, "get_db_id", lambda key: "db-id")
    monkeypatch.setattr(
        backfill.notion_upsert, "ensure_schema_preflight", lambda db_id, token: None
    )
    monkeypatch.setattr(backfill, "query_rows", lambda db_id, token: [target_row])
    monkeypatch.setattr(
        backfill, "resolve_row",
        lambda row, gtoken: {"entity": dict(good_record["fields"])},
    )
    monkeypatch.setattr(
        backfill.enrich_company, "enrich",
        lambda entity, web_findings=None: good_record,
    )
    patch_calls: list = []
    monkeypatch.setattr(
        backfill, "patch_empty_cells",
        lambda *a, **k: patch_calls.append(a) or {"action": "dry-run", "page_id": "page-2",
                                                  "patched_properties": ["郵便番号"]},
    )
    monkeypatch.setattr(backfill, "append_replay", lambda rec: pytest.fail(f"退避不要: {rec}"))
    monkeypatch.setattr(sys, "argv", ["backfill.py", "--dry-run"])

    rc = backfill.main()
    assert rc == 0
    assert len(patch_calls) == 1


def test_backfill_merge_entity_defaults_carries_existing_postal_and_phone():
    """既存非空の郵便番号/電話番号を enrich 入力へ渡し、空欄列だけ補完対象にする。"""
    row = {
        "fields": {
            "company_name": "テスト商事",
            "official_name": "テスト商事株式会社",
            "address": "東京都千代田区丸の内1-1-1",
            "postal_code": "100-0005",
            "hojin_bango": "1234567890123",
            "phone_number": "03-1234-5678",
        }
    }
    resolved = {"entity": {
        "company_name": "テスト商事",
        "official_name": "テスト商事株式会社",
        "address": "東京都千代田区丸の内1-1-1",
        "hojin_bango": "1234567890123",
        "source_url": GBIZ_DETAIL_URL,
    }}
    entity = backfill.merge_entity_defaults(row, resolved)
    assert entity["postal_code"] == "100-0005"
    assert entity["phone_number"] == "03-1234-5678"


# --- backfill 会社名 title 移行モード (--migrate-company-title) 回帰 -----------------

def _migration_row(company_title: str, official_name: str) -> dict:
    """会社名 title=company_title・official_name 既知の確定済み (空欄なし) 行を作る。"""
    return {
        "page_id": "p-mig",
        "fields": {
            "company_name": company_title,  # 既存 title (通称 or 既登記名)
            "official_name": official_name,
            "address": "東京都千代田区丸の内1-1-1",
            "postal_code": "100-0005",
            "hojin_bango": "1234567890123",
            "phone_number": "03-1234-5678",
        },
        "certainty": "公的データで確認済み",
        "remarks_text": "",
    }


def test_backfill_migrate_mode_overwrites_title_with_official_name(monkeypatch):
    """(a) 移行モード ON: 既存通称 title が official_name(登記名) へ上書きされる。"""
    row = _migration_row("テスト商事", "テスト商事株式会社")
    enriched = _canonical_record()  # official_name=テスト商事株式会社 / company_name=テスト商事(通称)
    bodies: list = []

    def fake_api(method, path, token, body=None):
        bodies.append((method, path, body))
        return {}

    monkeypatch.setattr(backfill.notion_upsert, "_api", fake_api)
    monkeypatch.setattr(backfill.notion_upsert, "sync_confirm_url_body",
                        lambda *a, **k: {"confirm_url_body": "synced"})
    out = backfill.patch_empty_cells("p-mig", "tok", row, enriched, dry_run=False,
                                     migrate_company_title=True)
    assert backfill.notion_upsert.COL_COMPANY_NAME in out["patched_properties"]
    patch_calls = [b for (m, p, b) in bodies if m == "PATCH" and "/pages/" in p]
    assert patch_calls, bodies
    title = (patch_calls[0]["properties"][backfill.notion_upsert.COL_COMPANY_NAME]
             ["title"][0]["text"]["content"])
    assert title == "テスト商事株式会社"  # 通称→登記名へ上書き
    # 住所/郵便/法人番号/電話の既存非空は PATCH 対象外 (title に限った保護解除)。
    assert backfill.notion_upsert.COL_ADDRESS not in out["patched_properties"]
    # alt_key 素材 (company_name 通称) は record 側で不変。
    assert enriched["fields"]["company_name"] == "テスト商事"


def test_backfill_migrate_mode_skips_when_official_name_empty():
    """(b) 移行モード ON でも official_name 空行は title を触らない (通称のまま)。"""
    row = _migration_row("テスト商事", "")
    enriched = json.loads(json.dumps(_canonical_record()))
    enriched["fields"]["official_name"] = ""  # 登記名未取得
    out = backfill.patch_empty_cells("p2", "tok", row, enriched, dry_run=True,
                                     migrate_company_title=True)
    assert backfill.notion_upsert.COL_COMPANY_NAME not in out["patched_properties"]


def test_backfill_migrate_off_preserves_nonempty_title():
    """(c) 移行モード OFF: official_name 既知でも既存非空 title は上書きしない (非空保護維持)。"""
    row = _migration_row("テスト商事", "テスト商事株式会社")
    enriched = _canonical_record()
    out = backfill.patch_empty_cells("p3", "tok", row, enriched, dry_run=True)
    assert backfill.notion_upsert.COL_COMPANY_NAME not in out["patched_properties"]


def _live_page(page_id: str, title: str, hojin: str = "1234567890123") -> dict:
    """正式名称列を物理削除した live DB の page payload を模す (会社名 title のみ・正式名称列なし)。"""
    props = {
        "会社名": {"title": [{"plain_text": title}]},
        "住所": {"rich_text": [{"plain_text": "東京都千代田区丸の内1-1-1"}]},
        "郵便番号": {"rich_text": [{"plain_text": "100-0005"}]},
        "法人番号": {"rich_text": ([{"plain_text": hojin}] if hojin else [])},
        "電話番号": {"rich_text": [{"plain_text": "03-1234-5678"}]},
        "情報の確かさ": {"select": {"name": "公的データで確認済み"}},
        "備考": {"rich_text": []},
    }
    return {"id": page_id, "properties": props}


def test_row_from_page_official_name_falls_back_to_title_after_column_deletion():
    """正式名称列削除後は row_from_page の official_name が title へフォールバックし
    company_name と一致する (列差で移行判定する旧経路が常時 no-op 化する根拠・F9 回帰防止)。"""
    row = backfill.row_from_page(_live_page("a", "テスト商事"))
    assert row["fields"]["official_name"] == row["fields"]["company_name"] == "テスト商事"


def test_select_backfill_targets_migrate_picks_hojin_bango_rows():
    """移行モード: 列削除後は official_name==title となるため、再 resolve 可能な
    法人番号保有行を候補化する (登記名上書き要否の冪等判定は patch_empty_cells に委譲)。"""
    rows = [backfill.row_from_page(_live_page("a", "テスト商事", hojin="1234567890123")),
            backfill.row_from_page(_live_page("b", "既登記株式会社", hojin="1234567890124"))]
    # 通常モード: 空欄なし・確定のため両方とも対象外 (旧経路の no-op を明示)。
    assert backfill.select_backfill_targets(rows) == []
    # 移行モード: 法人番号保有のため両方を候補化 (登記名一致行は patch 側で冪等 no-op となる)。
    migrated = backfill.select_backfill_targets(rows, migrate_company_title=True)
    assert sorted(t["row"]["page_id"] for t in migrated) == ["a", "b"]


def test_backfill_replay_log_is_root_anchored():
    """REPLAY_LOG が cwd 相対でなく repo-root (or plugin-root) 起点の絶対パス。"""
    assert backfill.REPLAY_LOG.is_absolute()
    assert backfill.REPLAY_LOG in (
        ROOT / "eval-log" / "backfill-replay.jsonl",
        PLUGIN_ROOT / "eval-log" / "backfill-replay.jsonl",
    )


def test_append_replay_writes_record_without_cache_version(monkeypatch):
    """append_replay は record をそのまま JSONL 追記する (日本郵便 API 移行でキャッシュ版記録は廃止)。

    郵便番号は API 逆引き (ローカルキャッシュ版なし) のため、版情報フィールドは付与しない。
    """
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(backfill, "REPLAY_LOG", Path(d) / "replay.jsonl")
        backfill.append_replay({"page_id": "p1", "status": "deferred"})
        line = (Path(d) / "replay.jsonl").read_text(encoding="utf-8").strip()
        row = json.loads(line)
        assert row == {"page_id": "p1", "status": "deferred"}
        assert "ken_all_cache_mtime" not in row  # 廃止フィールドが付かない


# --- notion_upsert 書き込みゲート内蔵 (呼び出し元非依存の検証強制) 回帰 ----------

def test_upsert_rejects_invalid_record_without_writing(monkeypatch):
    """validate_row 違反 record を upsert へ直接渡す → API/認証に到達せず rejected。

    wrapper/backfill 側ゲートを迂回する agent 直実行経路でも書き込み不能を機械保証する。
    """
    monkeypatch.setattr(
        notion_upsert, "_api",
        lambda *a, **k: pytest.fail("違反 record で Notion API が呼ばれた (ゲート迂回)"),
    )
    monkeypatch.setattr(
        notion_upsert.notion_config, "require_or_skip",
        lambda key: pytest.fail("違反 record で認証解決が走った (reject は offline であるべき)"),
    )
    bad_record = {
        "fields": {
            "company_name": "テスト商事",
            "official_name": "テスト商事株式会社",
            "address": "東京都千代田区丸の内1-1-1",
            "postal_code": "100-0005",
            "hojin_bango": "1234567890123",
            "phone_number": "03-1234-5678",
        },
        "overall_certainty": "VERIFIED",  # (e) 英語 enum 違反
        "remarks_text": "",
        "source_urls": [],
    }
    res = notion_upsert.upsert(bad_record)
    assert res["action"] == "rejected"
    assert any("(e)" in v for v in res["violations"])


def test_upsert_gate_passes_canonical_record(monkeypatch):
    """正準 record は書き込みゲートを通過し書き込み経路へ進む (過剰遮断なし)。"""
    api_calls: list = []

    def fake_api(method, path, token, body=None):
        api_calls.append((method, path))
        if method == "POST" and path.endswith("/query"):
            return {"results": []}  # 既存行なし → create 経路
        return {"id": "new-page"}

    monkeypatch.setattr(notion_upsert, "_api", fake_api)
    monkeypatch.setattr(
        notion_upsert.notion_config, "require_or_skip", lambda key: ({}, "tok")
    )
    monkeypatch.setattr(
        notion_upsert.notion_config, "get_db_id", lambda key: "db-id"
    )
    monkeypatch.setattr(
        notion_upsert, "ensure_schema_preflight", lambda db_id, token: None
    )
    res = notion_upsert.upsert(_canonical_record())
    assert res["action"] == "created"
    assert any(m == "POST" and p == "/pages" for m, p in api_calls)


# --- Notion live スキーマ preflight (fail-closed) 回帰 --------------------------

def _live_schema_from_expected() -> dict:
    """期待スキーマ JSON (references/notion-db-schema.json) から一致する live スキーマを合成。"""
    expected = notion_upsert.load_expected_schema()
    props = {}
    for name, spec in expected["properties"].items():
        p: dict = {"type": spec["type"]}
        if spec["type"] == "select":
            p["select"] = {"options": [{"name": o} for o in spec["select_options"]]}
        props[name] = p
    return {"properties": props}


def test_schema_json_matches_columns_md_7_cols():
    """機械可読 schema JSON の列集合が columns.md 由来の7列・確度4ラベルと一致する (正式名称は廃止)。"""
    expected = notion_upsert.load_expected_schema()
    assert set(expected["properties"].keys()) == EXPECTED_7_COLS
    assert "正式名称" not in expected["properties"]
    assert "正式名称" in expected.get("forbidden_properties", [])
    certainty = expected["properties"]["情報の確かさ"]
    assert certainty["type"] == "select"
    assert certainty["select_options"] == [
        "公的データで確認済み", "公的データ取得", "ネット検索(要確認)", "未確定(要確認)",
    ]


def test_preflight_passes_on_matching_live_schema(monkeypatch):
    """live スキーマが期待スキーマと一致 → preflight 通過 (例外なし)。"""
    live = _live_schema_from_expected()
    monkeypatch.setattr(notion_upsert, "_api", lambda m, p, t, b=None: live)
    notion_upsert.preflight_schema("db-id", "tok")  # raises しないこと


def test_preflight_rejects_missing_column(monkeypatch):
    """必須列の欠落 → SchemaPreflightError (fail-closed)。"""
    live = _live_schema_from_expected()
    del live["properties"]["備考"]
    monkeypatch.setattr(notion_upsert, "_api", lambda m, p, t, b=None: live)
    with pytest.raises(notion_upsert.SchemaPreflightError) as exc:
        notion_upsert.preflight_schema("db-id", "tok")
    assert any("備考" in v for v in exc.value.violations)


def test_preflight_rejects_forbidden_and_extra_columns(monkeypatch):
    """旧『正式名称』列や任意の余剰列が live DB に残っていれば7列構成違反として reject。"""
    live = _live_schema_from_expected()
    live["properties"]["正式名称"] = {"type": "rich_text"}
    live["properties"]["任意メモ"] = {"type": "rich_text"}
    monkeypatch.setattr(notion_upsert, "_api", lambda m, p, t, b=None: live)
    with pytest.raises(notion_upsert.SchemaPreflightError) as exc:
        notion_upsert.preflight_schema("db-id", "tok")
    assert any("禁止列 '正式名称'" in v for v in exc.value.violations)
    assert any("余剰列 '任意メモ'" in v for v in exc.value.violations)


def test_preflight_rejects_renamed_select_option(monkeypatch):
    """確度 select のオプション改名 → 4ラベル完全一致違反で reject。"""
    live = _live_schema_from_expected()
    opts = live["properties"]["情報の確かさ"]["select"]["options"]
    opts[-1]["name"] = "未確定"  # 『未確定(要確認)』の改名 drift
    monkeypatch.setattr(notion_upsert, "_api", lambda m, p, t, b=None: live)
    with pytest.raises(notion_upsert.SchemaPreflightError) as exc:
        notion_upsert.preflight_schema("db-id", "tok")
    assert any("select オプション不一致" in v for v in exc.value.violations)


def test_preflight_fail_closed_on_api_unreachable(monkeypatch):
    """Notion API 不達 → 書き込み判断に進ませず SchemaPreflightError (fail-closed)。"""
    def _down(m, p, t, b=None):
        raise OSError("network unreachable")
    monkeypatch.setattr(notion_upsert, "_api", _down)
    with pytest.raises(notion_upsert.SchemaPreflightError) as exc:
        notion_upsert.preflight_schema("db-id", "tok")
    assert any("不達" in v for v in exc.value.violations)


def test_ensure_schema_preflight_caches_per_process(monkeypatch):
    """同一 db_id の preflight はプロセス内 1 回 (多重照会回避キャッシュ)。"""
    calls: list = []
    live = _live_schema_from_expected()

    def counting_api(m, p, t, b=None):
        calls.append(p)
        return live

    monkeypatch.setattr(notion_upsert, "_api", counting_api)
    monkeypatch.setattr(notion_upsert, "_PREFLIGHT_OK", set())
    notion_upsert.ensure_schema_preflight("db-cache", "tok")
    notion_upsert.ensure_schema_preflight("db-cache", "tok")
    assert len(calls) == 1


def test_upsert_rejects_on_schema_preflight_mismatch(monkeypatch):
    """upsert は preflight 不一致時に一切書き込まず構造化エラーで返す。"""
    writes: list = []

    def fake_api(method, path, token, body=None):
        if method == "GET" and path.startswith("/databases/"):
            return {"properties": {}}  # 全列欠落の live スキーマ
        writes.append((method, path))
        return {}

    monkeypatch.setattr(notion_upsert, "_api", fake_api)
    monkeypatch.setattr(
        notion_upsert.notion_config, "require_or_skip", lambda key: ({}, "tok")
    )
    monkeypatch.setattr(notion_upsert.notion_config, "get_db_id", lambda key: "db-id")
    monkeypatch.setattr(notion_upsert, "_PREFLIGHT_OK", set())
    res = notion_upsert.upsert(_canonical_record())
    assert res["action"] == "rejected"
    assert res["schema_violations"]
    assert writes == [], "preflight 不一致なのに API 書き込みへ到達した"


# --- レート制限/リトライ (429/5xx 指数バックオフ + fail-closed) 回帰 -------------

def _http_error(code: int, retry_after: str | None = None):
    import email.message
    import io
    import urllib.error

    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        "https://api.notion.com/v1/x", code, "err", headers, io.BytesIO(b"")
    )


def test_api_retries_429_with_retry_after_then_succeeds(monkeypatch):
    """429 (Retry-After 付き) → 待機リトライ → 成功。Retry-After 秒を尊重する。"""
    attempts: list = []
    sleeps: list = []

    def flaky_send(req):
        attempts.append(1)
        if len(attempts) <= 2:
            raise _http_error(429, retry_after="3")
        return {"ok": True}

    monkeypatch.setattr(notion_upsert, "_send", flaky_send)
    monkeypatch.setattr(notion_upsert.time, "sleep", lambda s: sleeps.append(s))
    res = notion_upsert._api("GET", "/databases/x", "tok")
    assert res == {"ok": True}
    assert len(attempts) == 3
    assert sleeps == [3.0, 3.0]  # Retry-After 尊重


def test_api_fails_closed_after_retry_exhaustion(monkeypatch):
    """429 が上限まで続く → NotionAPIRetryExhausted (構造化エラー・fail-closed)。"""
    sleeps: list = []
    monkeypatch.setattr(
        notion_upsert, "_send", lambda req: (_ for _ in ()).throw(_http_error(503))
    )
    monkeypatch.setattr(notion_upsert.time, "sleep", lambda s: sleeps.append(s))
    with pytest.raises(notion_upsert.NotionAPIRetryExhausted) as exc:
        notion_upsert._api("POST", "/pages", "tok", {"x": 1})
    assert exc.value.last_status == 503
    assert exc.value.attempts == notion_upsert.RETRY_MAX_ATTEMPTS
    assert len(sleeps) == notion_upsert.RETRY_MAX_ATTEMPTS - 1
    assert sleeps == sorted(sleeps), "指数バックオフ (単調非減少) になっていない"


def test_api_does_not_retry_non_retryable_4xx(monkeypatch):
    """400 系 (429 以外) は仕様違反としてリトライせず即時失敗。"""
    import urllib.error

    attempts: list = []

    def bad_request(req):
        attempts.append(1)
        raise _http_error(400)

    monkeypatch.setattr(notion_upsert, "_send", bad_request)
    monkeypatch.setattr(
        notion_upsert.time, "sleep",
        lambda s: pytest.fail("リトライ対象外の 400 で sleep が呼ばれた"),
    )
    with pytest.raises(urllib.error.HTTPError):
        notion_upsert._api("GET", "/databases/x", "tok")
    assert len(attempts) == 1


# --- vendored notion_config drift lint (関数単位 AST 比較) 回帰 ------------------

def _load_vendored_lint_module():
    import importlib.util

    path = ROOT / "scripts" / "lint-company-master-vendored-deps.py"
    spec = importlib.util.spec_from_file_location("lint_cm_vendored", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vendored_notion_config_drift_lint_passes_current_tree():
    """現状の vendored notion_config.py は正本と関数単位 AST 一致 (拡張は宣言済み)。"""
    mod = _load_vendored_lint_module()
    issues = mod.check_vendored_notion_config(
        mod.CANONICAL_NOTION_CONFIG,
        PLUGIN_ROOT / mod.VENDORED_NOTION_CONFIG_REL,
    )
    assert issues == [], issues


def test_vendored_notion_config_drift_lint_catches_tamper(tmp_path):
    """共通関数の改変 / 未宣言の独自関数追加を drift として検出する。"""
    mod = _load_vendored_lint_module()
    src = (PLUGIN_ROOT / mod.VENDORED_NOTION_CONFIG_REL).read_text(encoding="utf-8")
    tampered = src.replace(
        "if env_name and os.environ.get(env_name):", "if env_name:"
    ) + "\n\ndef rogue_helper():\n    return 1\n"
    assert tampered != src
    p = tmp_path / "notion_config.py"
    p.write_text(tampered, encoding="utf-8")
    issues = mod.check_vendored_notion_config(mod.CANONICAL_NOTION_CONFIG, p)
    assert any("get_db_id" in i for i in issues), issues
    assert any("rogue_helper" in i for i in issues), issues


def test_vendored_deps_lint_script_passes():
    """lint script 全体 (import 走査 + drift チェック) が exit 0。"""
    import subprocess

    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lint-company-master-vendored-deps.py")],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr


# --- doctor サブコマンド (セットアップ一括診断) 回帰 -----------------------------

sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
import company_master  # noqa: E402


def _doctor_statuses(items: list) -> dict:
    return {it["label"]: it["status"] for it in items}


def _patch_postal_cache_offline(monkeypatch, tmp_path):
    """doctor の日本郵便 API 診断を offline 決定論化する (鍵=存在・送信元IPは固定値・probe なし)。

    実 Keychain / env / 公開エコー (自動検出) への依存を断つ。doctor は probe=False 既定なので
    実 API は叩かない。tmp_path は呼び出し側互換のため受けるが未使用。
    """
    monkeypatch.setattr(company_master.notion_config, "get_postal_proxy_url", lambda: None)
    monkeypatch.setattr(company_master.notion_config, "has_japanpost_credentials", lambda: True)
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_egress_ip", lambda *a, **k: "203.0.113.10")
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_base_url", lambda *a, **k: None)
    monkeypatch.setattr(postal_api, "detect_egress_ip", lambda *a, **k: "203.0.113.10")


def test_doctor_all_ok_exits_zero(monkeypatch, tmp_path, capsys):
    """Keychain 2鍵 + DB ID + preflight 通過 → FAIL なしで exit 0 (settings 未適用は WARN 止まり)。"""
    _patch_postal_cache_offline(monkeypatch, tmp_path)
    monkeypatch.delenv("COMPANY_MASTER_NOTION_DATABASE_ID", raising=False)
    cfg = {"__path__": str(PLUGIN_ROOT / "notion-config.fixed.json")}
    monkeypatch.setattr(company_master.notion_config, "load_config", lambda *a, **k: cfg)
    monkeypatch.setattr(company_master.notion_config, "get_token", lambda c=None: "tok")
    monkeypatch.setattr(company_master.notion_config, "get_gbizinfo_token", lambda c=None: "g")
    monkeypatch.setattr(company_master.notion_config, "get_db_id", lambda k, *a: "db-id")
    monkeypatch.setattr(
        company_master.notion_upsert, "preflight_schema", lambda db_id, tok: None
    )
    # settings 未適用環境を再現 (tmp root に .claude 無し) → WARN であって FAIL でない
    monkeypatch.setattr(company_master.notion_config, "find_repo_root", lambda *a, **k: tmp_path)
    rc = company_master.run_doctor(argparse_namespace())
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "[FAIL]" not in out
    assert "[WARN] settings-hardening" in out
    assert "解決経路: 同梱既定" in out


def test_doctor_missing_keychain_fails_and_skips_reach(monkeypatch, tmp_path, capsys):
    """Keychain 未登録 → FAIL (次アクション付き)、Notion 到達検査は SKIP、exit 1。"""
    _patch_postal_cache_offline(monkeypatch, tmp_path)
    monkeypatch.delenv("COMPANY_MASTER_NOTION_DATABASE_ID", raising=False)
    cfg = {"__path__": str(PLUGIN_ROOT / "notion-config.fixed.json")}
    monkeypatch.setattr(company_master.notion_config, "load_config", lambda *a, **k: cfg)
    monkeypatch.setattr(company_master.notion_config, "get_token", lambda c=None: None)
    monkeypatch.setattr(company_master.notion_config, "get_gbizinfo_token", lambda c=None: None)
    monkeypatch.setattr(company_master.notion_config, "get_db_id", lambda k, *a: "db-id")
    monkeypatch.setattr(
        company_master.notion_upsert, "preflight_schema",
        lambda db_id, tok: pytest.fail("トークン未設定なのに Notion へ到達した"),
    )
    monkeypatch.setattr(company_master.notion_config, "find_repo_root", lambda *a, **k: tmp_path)
    rc = company_master.run_doctor(argparse_namespace())
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAIL] Keychain: notion-api-key.xlocal" in out
    assert "[SKIP] Notion 到達 + schema preflight" in out
    assert "次アクション" in out


def test_doctor_schema_mismatch_is_fail(monkeypatch, tmp_path, capsys):
    """live スキーマ不一致 → doctor は FAIL + 次アクションを提示し exit 1。"""
    _patch_postal_cache_offline(monkeypatch, tmp_path)
    monkeypatch.delenv("COMPANY_MASTER_NOTION_DATABASE_ID", raising=False)
    cfg = {"__path__": str(PLUGIN_ROOT / "notion-config.fixed.json")}
    monkeypatch.setattr(company_master.notion_config, "load_config", lambda *a, **k: cfg)
    monkeypatch.setattr(company_master.notion_config, "get_token", lambda c=None: "tok")
    monkeypatch.setattr(company_master.notion_config, "get_gbizinfo_token", lambda c=None: "g")
    monkeypatch.setattr(company_master.notion_config, "get_db_id", lambda k, *a: "db-id")

    def mismatch(db_id, tok):
        raise notion_upsert.SchemaPreflightError(["必須列 '備考' が live DB に不在"])

    monkeypatch.setattr(company_master.notion_upsert, "preflight_schema", mismatch)
    monkeypatch.setattr(company_master.notion_config, "find_repo_root", lambda *a, **k: tmp_path)
    rc = company_master.run_doctor(argparse_namespace())
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAIL] Notion 到達 + schema preflight" in out
    assert "備考" in out


def argparse_namespace():
    import argparse

    return argparse.Namespace()


# --- hook-guard-secret (fail-closed + フラグ検出強化) 回帰 ----------------------

def _run_hook(stdin_text: str) -> "subprocess.CompletedProcess":
    import subprocess

    return subprocess.run(
        [sys.executable, str(HOOK_GUARD)],
        input=stdin_text, capture_output=True, text=True, timeout=30,
    )


def _hook_payload(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def test_hook_guard_fail_closed_on_unparseable_input():
    """stdin が JSON として解釈不能 → exit 2 (fail-closed。素通し禁止)。"""
    res = _run_hook("this is not json {{{")
    assert res.returncode == 2, res.stderr
    assert "BLOCKED" in res.stderr


def test_hook_guard_blocks_plain_w_flag():
    """ガード対象 account の find-generic-password -w → block (exit 2)。"""
    res = _run_hook(_hook_payload(
        "security find-generic-password -s notion-api-key.xl-skills -a xl-skills -w"
    ))
    assert res.returncode == 2, res.stderr


def test_hook_guard_blocks_concatenated_flags():
    """連結フラグ (-wa / -gw) やクォート付き ('-w') のバイパスも block。"""
    for cmd in (
        "security find-generic-password -s gbizinfo-api-token.xl-skills -wa",
        "security find-generic-password -s notion-api-key.xl-skills -gw",
        'security find-generic-password -s notion-api-key.xl-skills "-w"',
        "security find-generic-password -s notion-api-key.xl-skills '-w'",
    ):
        res = _run_hook(_hook_payload(cmd))
        assert res.returncode == 2, f"バイパスされた: {cmd}\n{res.stderr}"


def test_hook_guard_blocks_delete_and_print_unsafe():
    """delete-generic-password / --print-unsafe は account 同時出現で block。"""
    for cmd in (
        "security delete-generic-password -s notion-api-key.xl-skills -a xl-skills",
        "security find-generic-password -s gbizinfo-api-token.xl-skills --print-unsafe",
    ):
        res = _run_hook(_hook_payload(cmd))
        assert res.returncode == 2, f"バイパスされた: {cmd}\n{res.stderr}"


def test_hook_guard_allows_unrelated_and_safe_commands():
    """無関係コマンドと、ガード対象でも平文出力を伴わない存在確認は allow (exit 0)。"""
    for cmd in (
        "ls -la",
        "git status",
        # README 5-3 の存在確認 (中身を出さない) は正当経路として通す
        "security find-generic-password -s notion-api-key.xl-skills -a xl-skills >/dev/null 2>&1 && echo OK",
    ):
        res = _run_hook(_hook_payload(cmd))
        assert res.returncode == 0, f"誤遮断: {cmd}\n{res.stderr}"


def test_hook_guard_blocks_japanpost_secret_and_proxy_token_w_flag():
    """japanpost-da-api.xl-skills の secret_key / proxy_token の平文出力 (-w) は block (exit 2)。"""
    for account in ("secret_key", "proxy_token"):
        res = _run_hook(_hook_payload(
            f"security find-generic-password -s japanpost-da-api.xl-skills -a {account} -w"
        ))
        assert res.returncode == 2, f"japanpost {account} -w がバイパスされた\n{res.stderr}"


def test_hook_guard_allows_japanpost_add_generic_password():
    """japanpost-da-api.xl-skills への add-generic-password (登録) はセットアップ用途で許容 (exit 0)。"""
    res = _run_hook(_hook_payload(
        "security add-generic-password -s japanpost-da-api.xl-skills -a secret_key -w 'SECRETVALUE'"
    ))
    assert res.returncode == 0, f"鍵登録が誤遮断された\n{res.stderr}"


# --- フォールバック多段化 (E: fallback tier / attempts / 2パス運用) 回帰 ----------

import normalize  # noqa: E402


def test_strip_legal_form_shared_canonical():
    """法人格除去の共有正本 (前株/後株・略記正規化込み・法人格のみは原形維持)。"""
    assert normalize.strip_legal_form("株式会社テスト商事") == "テスト商事"
    assert normalize.strip_legal_form("テスト商事株式会社") == "テスト商事"
    assert normalize.strip_legal_form("(株)テスト商事") == "テスト商事"
    assert normalize.strip_legal_form("株式会社") == "株式会社"  # 空クエリを作らない


def test_resolve_by_name_retries_with_normalized_patterns(monkeypatch):
    """一次照会 0 件 → 正規化名 → 法人格除去名で決定論再照会し attempts を記録する。"""
    import urllib.parse as up

    queried: list[str] = []

    def fake_request(url, token):
        q = up.parse_qs(up.urlsplit(url).query)["name"][0]
        queried.append(q)
        if q == "テスト商事":  # 法人格除去名のみヒット
            return _GBIZ_SINGLE_HIT
        return {"hojin-infos": []}

    monkeypatch.setattr(resolve_company, "_request", fake_request)
    res = resolve_company.resolve_by_name(
        "(株)テスト商事", "dummy-token", address="東京都千代田区丸の内1-1-1")
    assert queried == ["(株)テスト商事", "株式会社テスト商事", "テスト商事"]
    assert res["entity"]["hojin_bango"] == "1234567890123"  # 自動確定条件は不変
    assert [a["pattern"] for a in res["attempts"]] == [
        "name_raw", "name_normalized", "name_legal_form_stripped"]
    assert res["attempts"][-1]["result"] == "hit:1"


def test_resolve_web_address_provenance_never_autoconfirms(monkeypatch):
    """信頼キー不変条項: address_provenance=web は 2 要素一致でも自動確定しない (要確認降格)。"""
    monkeypatch.setattr(resolve_company, "_request", lambda url, token: _GBIZ_SINGLE_HIT)
    res = resolve_company.resolve_by_name(
        "テスト商事", "dummy-token", address="東京都千代田区丸の内1-1-1",
        address_provenance="web")
    assert "entity" not in res, "Web 由来住所で自動確定してはならない"
    assert res["certainty"] == "ネット検索(要確認)"  # 確度上限
    assert len(res["candidates"]) == 1  # 候補列挙へ降格


def test_enrich_outputs_missing_fields_and_attempts():
    """enrich が missing_fields[] + attempts[] を top-level に返す (gap-driven 契約)。"""
    no_phone = _enrich_offline(SAMPLE_ENTITY, None)
    assert no_phone["missing_fields"] == ["phone_number"]
    # 電話は未試行 (web_findings 未提供) なので attempts に web は載らない。
    assert all(a["field"] != "phone_number" for a in no_phone["attempts"])
    # 郵便番号の試行は記録される (スタブは attempts 無し → 合成 1 件)。
    assert any(a["field"] == "postal_code" and a["source"] == "japanpost"
               for a in no_phone["attempts"])

    full = _canonical_record()
    assert full["missing_fields"] == []
    phone_attempts = [a for a in full["attempts"] if a["field"] == "phone_number"]
    assert phone_attempts == [{"field": "phone_number", "source": "web",
                               "pattern": "web_findings", "result": "adopted",
                               "reject_reason": ""}]


def test_enrich_preserves_all_japanpost_sub_attempts(monkeypatch):
    """postal_api の内部 attempts は3件を超えても欠落させない (prefix hit の観測性)。"""
    monkeypatch.setattr(
        enrich_company, "postal_from_address",
        lambda address, company_name="": {
            "value": "997-0053",
            "certainty": enrich_company.CERTAINTY_PUBLIC_FETCHED,
            "remark_key": "",
            "source_url": postal_api.JAPANPOST_VERIFY_URL,
            "attempts": [
                {"source": "japanpost", "pattern": "structured_pref_city_town",
                 "result": "miss", "reject_reason": "該当する住所なし (HTTP 404)"},
                {"source": "japanpost", "pattern": "structured_town_trimmed",
                 "result": "miss", "reject_reason": "該当する住所なし (HTTP 404)"},
                {"source": "japanpost", "pattern": "freeword_no_banchi",
                 "result": "miss", "reject_reason": "該当する住所なし (HTTP 404)"},
                {"source": "japanpost", "pattern": "structured_city_prefix_match",
                 "result": "hit", "reject_reason": ""},
            ],
        },
    )
    rec = enrich_company.enrich(SAMPLE_ENTITY, SAMPLE_WEB_FINDINGS)
    postal_attempts = [a for a in rec["attempts"] if a["field"] == "postal_code"]
    assert [a["pattern"] for a in postal_attempts] == [
        "structured_pref_city_town",
        "structured_town_trimmed",
        "freeword_no_banchi",
        "structured_city_prefix_match",
    ]


# 大字+小字ケースの snapshot: i>=1 が全て pattern='structured_town_trimmed' に潰れ、
# その中で miss が hit に先行する (`_town_variants('大字北京田字下鳥ノ巣')` =
# ['大字北京田字下鳥ノ巣','大字北京田','北京田字下鳥ノ巣','北京田'] のうち '北京田' のみ命中)。
# (field, source, pattern) 単位 dedup を通すと hit が先行 miss に潰れ postal_code を miss と
# 誤記録する実バグ経路。冪等スナップショット転記なら hit が残る。
_TOWN_TRIMMED_HIT_SNAPSHOT = [
    {"source": "japanpost", "pattern": "structured_pref_city_town",
     "result": "miss", "reject_reason": "一意確定不能または未一致"},
    {"source": "japanpost", "pattern": "structured_town_trimmed",
     "result": "miss", "reject_reason": "一意確定不能または未一致"},
    {"source": "japanpost", "pattern": "structured_town_trimmed",
     "result": "miss", "reject_reason": "一意確定不能または未一致"},
    {"source": "japanpost", "pattern": "structured_town_trimmed",
     "result": "hit", "reject_reason": ""},
]


def test_enrich_keeps_town_trimmed_hit_after_leading_misses(monkeypatch):
    """同一 pattern 'structured_town_trimmed' が miss→hit の系列でも hit を欠落させない。

    CORE-02 (テスト盲点) を塞ぐ実バグ経路。大字+小字 (大字北京田字下鳥ノ巣) の lookup は
    剥離バリアントが全て同一 pattern へ潰れ、miss が hit に先行する。(field, source, pattern)
    dedup を通すと先行 miss が hit を握り潰し postal_code を miss と誤記録する (修正前 RED)。
    冪等スナップショット転記なら hit が1件残る (修正後 GREEN)。
    """
    monkeypatch.setattr(
        enrich_company, "postal_from_address",
        lambda address, company_name="": {
            "value": "997-0053",
            "certainty": enrich_company.CERTAINTY_PUBLIC_FETCHED,
            "remark_key": "",
            "source_url": postal_api.JAPANPOST_VERIFY_URL,
            "attempts": [dict(a) for a in _TOWN_TRIMMED_HIT_SNAPSHOT],
        },
    )
    rec = enrich_company.enrich(SAMPLE_ENTITY, SAMPLE_WEB_FINDINGS)
    postal_attempts = [a for a in rec["attempts"] if a["field"] == "postal_code"]
    # スナップショットが verbatim (4件) で転記され、hit が1件残る。
    assert [a["pattern"] for a in postal_attempts] == [
        "structured_pref_city_town",
        "structured_town_trimmed",
        "structured_town_trimmed",
        "structured_town_trimmed",
    ]
    hits = [a for a in postal_attempts if a["result"] == "hit"]
    assert len(hits) == 1, postal_attempts
    assert hits[0]["pattern"] == "structured_town_trimmed"
    # 値の整合 (確定郵便番号が attempts の hit と一致)。
    assert rec["fields"]["postal_code"] == "997-0053"


def test_enrich_japanpost_snapshot_not_duplicated_cross_pass(monkeypatch):
    """2 パス運用で同一 postal snapshot を引き継いでも japanpost attempts が二重化しない。

    1 パス目の postal_code/japanpost attempts を entity.attempts へ引き継いだ 2 パス目 enrich で、
    冪等スナップショット置換 (既存 japanpost postal 行を全除去してから転記) により件数が
    保たれる (cross-pass 二重記録の回帰ガード)。
    """
    monkeypatch.setattr(
        enrich_company, "postal_from_address",
        lambda address, company_name="": {
            "value": "997-0053",
            "certainty": enrich_company.CERTAINTY_PUBLIC_FETCHED,
            "remark_key": "",
            "source_url": postal_api.JAPANPOST_VERIFY_URL,
            "attempts": [dict(a) for a in _TOWN_TRIMMED_HIT_SNAPSHOT],
        },
    )
    pass1 = enrich_company.enrich(SAMPLE_ENTITY, SAMPLE_WEB_FINDINGS)
    pass1_postal = [a for a in pass1["attempts"] if a["field"] == "postal_code"]
    assert len(pass1_postal) == len(_TOWN_TRIMMED_HIT_SNAPSHOT)

    # 1 パス目の attempts を entity へ引き継いで 2 パス目を回す。
    entity2 = dict(SAMPLE_ENTITY)
    entity2["attempts"] = [dict(a) for a in pass1["attempts"]]
    pass2 = enrich_company.enrich(entity2, SAMPLE_WEB_FINDINGS)
    pass2_postal = [a for a in pass2["attempts"] if a["field"] == "postal_code"]
    # 二重化しない (snapshot 件数のまま) で hit も1件保持。
    assert len(pass2_postal) == len(_TOWN_TRIMMED_HIT_SNAPSHOT), pass2_postal
    assert [a["pattern"] for a in pass2_postal] == [a["pattern"] for a in pass1_postal]
    assert sum(1 for a in pass2_postal if a["result"] == "hit") == 1


def test_enrich_attempts_dedupe_and_max(monkeypatch):
    """同一 (field, source, pattern) の再試行はスキップ、field あたり MAX=3 で打ち切り。"""
    attempts: list = []
    assert enrich_company.note_attempt(attempts, "phone_number", "web", "p1", "rejected", "x")
    # 同一 (source, pattern) → スキップ (gap-driven 単調前進)。
    assert not enrich_company.note_attempt(attempts, "phone_number", "web", "p1", "rejected")
    assert enrich_company.note_attempt(attempts, "phone_number", "web", "p2", "rejected")
    assert enrich_company.note_attempt(attempts, "phone_number", "web", "p3", "rejected")
    # MAX_ATTEMPTS_PER_FIELD=3 で打ち切り。
    assert not enrich_company.note_attempt(attempts, "phone_number", "web", "p4", "rejected")
    assert len(attempts) == enrich_company.MAX_ATTEMPTS_PER_FIELD

    # 前パスの attempts (entity 経由) を引き継いで重複試行を遮断する (2 パス運用)。
    entity = dict(SAMPLE_ENTITY)
    entity["attempts"] = [{"field": "phone_number", "source": "web",
                           "pattern": "web_findings", "result": "rejected",
                           "reject_reason": "前パスで不整合"}]
    rec = _enrich_offline(entity, SAMPLE_WEB_FINDINGS)
    phone_attempts = [a for a in rec["attempts"] if a["field"] == "phone_number"]
    assert len(phone_attempts) == 1  # 同一 (web, web_findings) は再記録されない
    assert phone_attempts[0]["result"] == "rejected"  # 前パスの記録を保持


def test_validate_certainty_cap_and_origin_whitelist():
    """(g) fallback tier 機械照合: 確度昇格と許可段外 origin を FAIL にする。"""
    remark_phrases = set(remarks.load_templates().values())
    # 確度昇格 (origin=web なのに『公的データで確認済み』) → FAIL。
    promoted = _canonical_record()
    promoted["certainty_by_field"]["phone_number"] = "公的データで確認済み"
    errs = vcm.validate_row(promoted, 0, remark_phrases)
    assert any("確度昇格禁止" in e for e in errs), errs
    # 許可段外 (postal_code を Web 取得) → FAIL (郵便番号は日本郵便 addresszip API のみ)。
    web_postal = _canonical_record()
    web_postal["source_by_field"]["postal_code"] = {
        "origin": "web", "url": "https://example.co.jp/zip"}
    errs = vcm.validate_row(web_postal, 0, remark_phrases)
    assert any("許可段外" in e and "postal_code" in e for e in errs), errs
    # 許可 enum 内でも、非空郵便番号の origin は japanpost のみ。
    user_postal = _canonical_record()
    user_postal["source_by_field"]["postal_code"] = {"origin": "user_input", "url": ""}
    errs = vcm.validate_row(user_postal, 0, remark_phrases)
    assert any("非空 postal_code" in e and "japanpost" in e for e in errs), errs
    # 確度・検証 URL も japanpost 由来契約と一致している必要がある。
    bad_postal_meta = _canonical_record()
    bad_postal_meta["certainty_by_field"]["postal_code"] = "未確定(要確認)"
    bad_postal_meta["source_by_field"]["postal_code"]["url"] = "https://example.co.jp/zip"
    errs = vcm.validate_row(bad_postal_meta, 0, remark_phrases)
    assert any("属性別確度" in e and "postal_code" in e for e in errs), errs
    assert any("検証URL" in e and "postal_code" in e for e in errs), errs
    # 上限以内 (origin=gbizinfo の『公的データ取得』等) は FAIL しない (正準 record)。
    assert vcm.validate_row(_canonical_record(), 0, remark_phrases) == []


def test_remarks_expand_template_all_tiers_exhausted_passes_validation():
    """all_tiers_exhausted の展開行が (f) 定型文言検査を通過する (自由記述は引き続き FAIL)。"""
    line = remarks.expand_template(
        "all_tiers_exhausted", field="電話番号", attempts="web:web_findings")
    assert line.startswith("【全段試行不成立】電話番号:")
    remark_phrases = set(remarks.load_templates().values())
    rec = _enrich_offline(SAMPLE_ENTITY, None)  # phone 空欄 + 未確定
    rec["remarks_text"] = line
    assert vcm.validate_row(rec, 0, remark_phrases) == []
    # 自由記述は引き続き (f) FAIL。
    rec["remarks_text"] = "電話番号が見つかりませんでした"
    errs = vcm.validate_row(rec, 0, remark_phrases)
    assert any("(f)" in e and "非定型文言" in e for e in errs), errs


def test_backfill_web_findings_two_pass(monkeypatch, capsys):
    """--web-findings (page_id キー) が enrich へ伝搬し、missing_fields 行が needs_web_search に載る。"""
    rows = [
        {"page_id": "page-a", "fields": {
            "company_name": "テスト商事", "official_name": "テスト商事株式会社",
            "address": "東京都千代田区丸の内1-1-1",
            "postal_code": "", "hojin_bango": "1234567890123", "phone_number": ""},
         "certainty": "未確定(要確認)", "remarks_text": ""},
        {"page_id": "page-b", "fields": {
            "company_name": "別社", "official_name": "別社株式会社",
            "address": "東京都千代田区丸の内2-2-2",
            "postal_code": "", "hojin_bango": "9876543210987", "phone_number": ""},
         "certainty": "未確定(要確認)", "remarks_text": ""},
    ]
    wf_map = {"page-a": SAMPLE_WEB_FINDINGS}
    received: dict = {}
    real_enrich = enrich_company.enrich

    def fake_enrich(entity, web_findings=None):
        received[entity["hojin_bango"]] = web_findings
        return real_enrich(entity, web_findings)  # 実体 enrich を実行 (offline 化は postal stub)

    monkeypatch.setattr(
        enrich_company, "postal_from_address",
        lambda address, company_name="": {
            "value": "100-0005", "certainty": enrich_company.CERTAINTY_PUBLIC_FETCHED,
            "remark_key": "", "source_url": postal_api.JAPANPOST_VERIFY_URL})
    monkeypatch.setattr(backfill, "precondition_gate", lambda: ({}, "tok"))
    monkeypatch.setattr(backfill.notion_config, "get_gbizinfo_token", lambda cfg=None: "g")
    monkeypatch.setattr(backfill.notion_config, "get_db_id", lambda key: "db-id")
    monkeypatch.setattr(
        backfill.notion_upsert, "ensure_schema_preflight", lambda db_id, token: None)
    monkeypatch.setattr(backfill, "query_rows", lambda db_id, token: rows)
    monkeypatch.setattr(
        backfill, "resolve_row",
        lambda row, gtoken: {"entity": dict(row["fields"], source_url=GBIZ_DETAIL_URL)})
    monkeypatch.setattr(backfill.enrich_company, "enrich", fake_enrich)
    monkeypatch.setattr(
        backfill, "patch_empty_cells",
        lambda *a, **k: {"action": "dry-run", "patched_properties": ["電話番号"]})
    monkeypatch.setattr(backfill, "append_replay", lambda rec: None)
    monkeypatch.setattr(
        sys, "argv",
        ["backfill.py", "--dry-run", "--web-findings", json.dumps(wf_map)])

    rc = backfill.main()
    assert rc == 0
    # page-a には web_findings が伝搬し、page-b には None。
    assert received["1234567890123"] == SAMPLE_WEB_FINDINGS
    assert received["9876543210987"] is None
    summary = json.loads(capsys.readouterr().out)
    # Claude 介入が必要な行リスト: 電話未取得の page-b のみ (missing_fields 付き)。
    assert summary["needs_web_search"] == [
        {"page_id": "page-b", "missing_fields": ["phone_number"],
         "attempts": [{"field": "postal_code", "source": "japanpost",
                       "pattern": "addresszip", "result": "hit",
                       "reject_reason": ""}]}]


def test_backfill_rejects_malformed_web_findings(monkeypatch):
    """--web-findings の JSON 不正は fail-closed (exit 2・全行処理に入らない)。"""
    monkeypatch.setattr(
        backfill, "precondition_gate",
        lambda: pytest.fail("不正 JSON なのに precondition gate へ進んだ"))
    monkeypatch.setattr(sys, "argv", ["backfill.py", "--web-findings", "{broken"])
    assert backfill.main() == 2


def _stub_backfill_gate_deps(monkeypatch, *, proxy_url, has_creds):
    """precondition_gate の依存を offline スタブ化する (Notion/gBizINFO は揃った前提)。"""
    monkeypatch.setattr(backfill.notion_config, "require_or_skip", lambda key: ({}, "tok"))
    monkeypatch.setattr(backfill.notion_config, "get_gbizinfo_token", lambda cfg=None: "g")
    monkeypatch.setattr(backfill.notion_config, "get_postal_proxy_url", lambda: proxy_url)
    monkeypatch.setattr(backfill.notion_config, "has_japanpost_credentials", lambda: has_creds)


def test_backfill_precondition_gate_allows_missing_japanpost_credentials(monkeypatch, capsys):
    """precondition_gate: proxy_url 無 かつ 日本郵便鍵 無でも通過し、郵便番号だけ縮退させる。"""
    _stub_backfill_gate_deps(monkeypatch, proxy_url=None, has_creds=False)
    cfg, token = backfill.precondition_gate()
    assert token == "tok"
    assert "WARN: 日本郵便" in capsys.readouterr().err


def test_backfill_precondition_gate_passes_with_credentials(monkeypatch):
    """precondition_gate: 日本郵便鍵あり (proxy 無) → 通過し (cfg, token) を返す。"""
    _stub_backfill_gate_deps(monkeypatch, proxy_url=None, has_creds=True)
    cfg, token = backfill.precondition_gate()
    assert token == "tok"


def test_backfill_precondition_gate_passes_with_proxy_even_without_credentials(monkeypatch):
    """precondition_gate: proxy_url 設定時は日本郵便鍵がローカル無くても通過 (鍵はプロキシ側集約)。"""
    _stub_backfill_gate_deps(monkeypatch, proxy_url="http://proxy", has_creds=False)
    cfg, token = backfill.precondition_gate()
    assert token == "tok"


# --- 日本郵便 API の失敗時の縮退 (auth/network → remark 区別) 回帰 ----------------

def test_enrich_uses_postal_api_remark_on_error(monkeypatch):
    """日本郵便 API 試行 result=error → reject_reason 種別で remark を選ぶ (B2)。

    auth (401/403) → postal_api_unauthorized / network (5xx・timeout) → postal_api_unavailable /
    miss (一意確定不能) → 従来の postal_code。人間が原因を区別できる。
    """
    remark_phrases = set(remarks.load_templates().values())

    # 認証失敗 (reject_reason が auth: 始まり) → postal_api_unauthorized。
    monkeypatch.setattr(
        enrich_company, "postal_from_address",
        lambda address, company_name="": {
            "value": "", "certainty": enrich_company.CERTAINTY_UNRESOLVED,
            "remark_key": "postal_code", "source_url": "",
            "attempts": [{"source": "japanpost", "pattern": "structured_pref_city_town",
                          "result": "error",
                          "reject_reason": "auth: HTTP 403 認証失敗 (IP未登録/鍵不正の可能性)"}]})
    rec = enrich_company.enrich(SAMPLE_ENTITY, SAMPLE_WEB_FINDINGS)
    assert "postal_api_unauthorized" in rec["remark_keys"]
    assert "認証に失敗" in rec["remarks_text"]
    assert vcm.validate_row(rec, 0, remark_phrases) == []  # 定型文言として (f) 通過

    # 通信失敗 (reject_reason が network: 始まり) → postal_api_unavailable。
    monkeypatch.setattr(
        enrich_company, "postal_from_address",
        lambda address, company_name="": {
            "value": "", "certainty": enrich_company.CERTAINTY_UNRESOLVED,
            "remark_key": "postal_code", "source_url": "",
            "attempts": [{"source": "japanpost", "pattern": "freeword_no_banchi",
                          "result": "error",
                          "reject_reason": "network: 通信失敗 (URLError)"}]})
    rec2 = enrich_company.enrich(SAMPLE_ENTITY, SAMPLE_WEB_FINDINGS)
    assert "postal_api_unavailable" in rec2["remark_keys"]
    assert "通信に失敗" in rec2["remarks_text"]

    # 一意確定不能 (miss) → 従来の postal_code 文言 (区別の回帰)。
    monkeypatch.setattr(
        enrich_company, "postal_from_address",
        lambda address, company_name="": {
            "value": "", "certainty": enrich_company.CERTAINTY_UNRESOLVED,
            "remark_key": "postal_code", "source_url": "",
            "attempts": [{"source": "japanpost", "pattern": "freeword_no_banchi",
                          "result": "miss", "reject_reason": "一意確定不能または未一致"}]})
    rec3 = enrich_company.enrich(SAMPLE_ENTITY, SAMPLE_WEB_FINDINGS)
    assert "postal_code" in rec3["remark_keys"]
    assert "一意逆引きできず" in rec3["remarks_text"]


def test_doctor_japanpost_warns_when_credentials_missing(monkeypatch):
    """鍵未設定 + 送信元IP解決不能 → WARN (FAIL でない) + セットアップ手順を提示・実疎通は SKIP。"""
    monkeypatch.setattr(company_master.notion_config, "get_postal_proxy_url", lambda: None)
    monkeypatch.setattr(company_master.notion_config, "has_japanpost_credentials", lambda: False)
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_egress_ip", lambda *a, **k: None)
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_base_url", lambda *a, **k: None)
    monkeypatch.setattr(postal_api, "detect_egress_ip", lambda *a, **k: None)
    items = company_master._doctor_check_japanpost(probe=False)
    statuses = [it["status"] for it in items]
    assert "WARN" in statuses and "FAIL" not in statuses
    assert any("japanpost-api-setup.md" in (it["next_action"] or "") for it in items)
    assert any(it["status"] == "SKIP" and "実疎通" in it["label"] for it in items)


def test_doctor_japanpost_ok_when_credentials_present(monkeypatch):
    """鍵設定済み + 送信元IP解決可 (env or 自動検出) + 本番接続 + probe 無し →
    OK 4件 (モード/接続先/Keychain/送信元IP) + 実疎通は SKIP。"""
    monkeypatch.setattr(company_master.notion_config, "get_postal_proxy_url", lambda: None)
    monkeypatch.setattr(company_master.notion_config, "has_japanpost_credentials", lambda: True)
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_egress_ip", lambda *a, **k: None)
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_base_url", lambda *a, **k: None)
    monkeypatch.setattr(postal_api, "detect_egress_ip", lambda *a, **k: "203.0.113.10")
    items = company_master._doctor_check_japanpost(probe=False)
    statuses = [it["status"] for it in items]
    assert statuses.count("OK") == 4
    # proxy_url 未設定なので「郵便番号取得モード: BYO 直結」をプロキシ分岐と対称に明示する。
    assert any(it["label"] == "郵便番号取得モード" and "BYO 直結" in it["detail"] for it in items)
    # base_url 上書き無し → 接続先は本番ホストを明示する。
    assert any(it["label"] == "接続先" and "api.da.pf.japanpost.jp" in it["detail"] for it in items)
    # 送信元IP 行は「登録してください」案内に検出IPを載せる (BYO ガイド)。
    assert any(it["label"] == "送信元IP" and "203.0.113.10" in it["detail"] for it in items)
    assert any(it["status"] == "SKIP" and "実疎通" in it["label"] for it in items)
    assert "FAIL" not in statuses and "WARN" not in statuses


def test_doctor_japanpost_warns_on_stub_base_url(monkeypatch):
    """base_url が stub/テストホストを指す → 接続先 WARN (本番移行を促す。誤って本番扱いしない)。"""
    monkeypatch.setattr(company_master.notion_config, "get_postal_proxy_url", lambda: None)
    monkeypatch.setattr(company_master.notion_config, "has_japanpost_credentials", lambda: True)
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_egress_ip", lambda *a, **k: "203.0.113.10")
    monkeypatch.setattr(
        company_master.notion_config, "get_japanpost_base_url",
        lambda *a, **k: "https://stub-qz73x.da.pf.japanpost.jp")
    monkeypatch.setattr(postal_api, "detect_egress_ip", lambda *a, **k: "203.0.113.10")
    items = company_master._doctor_check_japanpost(probe=False)
    conn = next((it for it in items if it["label"] == "接続先"), None)
    assert conn is not None and conn["status"] == "WARN"
    assert "stub-qz73x" in conn["detail"] and "api.da.pf.japanpost.jp" in (conn["next_action"] or "")


def test_doctor_japanpost_warns_on_egress_drift(monkeypatch):
    """pin のIPと実際の送信元IPがズレ → WARN (認証失敗の予兆として明示)。"""
    monkeypatch.setattr(company_master.notion_config, "get_postal_proxy_url", lambda: None)
    monkeypatch.setattr(company_master.notion_config, "has_japanpost_credentials", lambda: True)
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_egress_ip", lambda *a, **k: "198.51.100.1")
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_base_url", lambda *a, **k: None)
    monkeypatch.setattr(postal_api, "detect_egress_ip", lambda *a, **k: "203.0.113.10")
    items = company_master._doctor_check_japanpost(probe=False)
    drift = next((it for it in items if it["label"] == "送信元IP"), None)
    assert drift is not None and drift["status"] == "WARN"
    assert "198.51.100.1" in drift["detail"] and "203.0.113.10" in drift["detail"]


def test_doctor_japanpost_proxy_mode(monkeypatch):
    """proxy_url 設定時: doctor は『中央プロキシ経由』を表示し鍵/IP行を出さない・実疎通は SKIP。"""
    monkeypatch.setattr(company_master.notion_config, "get_postal_proxy_url",
                        lambda: "https://proxy.example/addresszip")
    items = company_master._doctor_check_japanpost(probe=False)
    assert any(it["label"] == "郵便番号取得モード" and "中央プロキシ" in it["detail"] for it in items)
    assert any(it["status"] == "SKIP" and "実疎通" in it["label"] for it in items)
    assert not any(it["label"].startswith("Keychain: japanpost") for it in items)


class _FakePostalApi:
    """_japanpost_probe_item に渡す最小スタブ (lookup_postal の戻りと呼び出し引数を制御/捕捉)。"""

    def __init__(self, result: dict):
        self._result = result
        self.calls: list[str] = []

    def lookup_postal(self, query):
        self.calls.append(query)
        return dict(self._result)


def test_japanpost_probe_miss_is_warn_not_ok(monkeypatch):
    """probe: lookup_postal が miss (value 空・error 無し) → status WARN (OK と誤表示しない)。"""
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_base_url", lambda: None)
    fake = _FakePostalApi({"value": "", "attempts": [
        {"source": "japanpost", "pattern": "freeword_no_banchi",
         "result": "miss", "reject_reason": "一意確定不能または未一致"}]})
    item = company_master._japanpost_probe_item(fake)
    assert item["status"] == "WARN", item
    assert item["status"] != "OK"


def test_japanpost_probe_stub_switches_search_term(monkeypatch):
    """probe: base_url 設定 (stub 環境) では検索語が「東京都千代田区飯田橋」へ切り替わる。"""
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_base_url",
                        lambda: "https://stub-qz73x.da.pf.japanpost.jp")
    fake = _FakePostalApi({"value": "100-0013", "attempts": [
        {"source": "japanpost", "pattern": "freeword_no_banchi",
         "result": "hit", "reject_reason": ""}]})
    item = company_master._japanpost_probe_item(fake)
    assert fake.calls == ["東京都千代田区飯田橋"], fake.calls
    assert item["status"] == "OK"
    # 本番 (base_url 未設定) は霞が関を引く (stub 切替の対照)。
    monkeypatch.setattr(company_master.notion_config, "get_japanpost_base_url", lambda: None)
    fake2 = _FakePostalApi({"value": "100-0013", "attempts": []})
    company_master._japanpost_probe_item(fake2)
    assert fake2.calls == ["東京都千代田区霞が関"], fake2.calls


# --- preflight gate (バックグラウンド実行前の fail-fast) 回帰 --------------------

def test_preflight_gate_fails_fast_on_missing_gbizinfo(monkeypatch):
    """gBizINFO 不在 → exit 2 で fail-fast。日本郵便は郵便番号だけの縮退対象。"""
    monkeypatch.setattr(company_master.notion_config, "load_config", lambda *a, **k: None)
    monkeypatch.setattr(company_master.notion_config, "get_gbizinfo_token", lambda cfg=None: None)
    monkeypatch.setattr(company_master.notion_config, "has_japanpost_credentials", lambda: False)
    with pytest.raises(SystemExit) as exc:
        company_master._preflight_gate(require_upsert=False)
    assert exc.value.code == 2


def test_preflight_gate_allows_missing_japanpost_credentials(monkeypatch, capsys):
    """gBizINFO があれば、日本郵便鍵が未設定でも通過し郵便番号だけ縮退させる。"""
    monkeypatch.setattr(company_master.notion_config, "load_config", lambda *a, **k: {})
    monkeypatch.setattr(company_master.notion_config, "get_gbizinfo_token", lambda cfg=None: "g")
    monkeypatch.setattr(company_master.notion_config, "get_postal_proxy_url", lambda: None)
    monkeypatch.setattr(company_master.notion_config, "has_japanpost_credentials", lambda: False)
    company_master._preflight_gate(require_upsert=False)  # SystemExit を投げないこと
    assert "WARN: 日本郵便" in capsys.readouterr().err


def test_preflight_gate_requires_notion_for_upsert(monkeypatch):
    """require_upsert=True かつ Notion トークン/DB ID 不在 → exit 2 (書き込み前提の追加検査)。"""
    monkeypatch.setattr(company_master.notion_config, "load_config", lambda *a, **k: {})
    monkeypatch.setattr(company_master.notion_config, "get_gbizinfo_token", lambda cfg=None: "g")
    monkeypatch.setattr(company_master.notion_config, "has_japanpost_credentials", lambda: True)
    monkeypatch.setattr(company_master.notion_config, "has_egress_ip", lambda: True)
    monkeypatch.setattr(company_master.notion_config, "get_token", lambda cfg=None: None)
    monkeypatch.setattr(company_master.notion_config, "get_db_id", lambda key: None)
    with pytest.raises(SystemExit) as exc:
        company_master._preflight_gate(require_upsert=True)
    assert exc.value.code == 2


def test_preflight_gate_skips_japanpost_creds_in_proxy_mode(monkeypatch):
    """proxy_url 設定時: 日本郵便鍵がローカルになくても preflight 通過 (鍵はプロキシ側に集約)。"""
    monkeypatch.setattr(company_master.notion_config, "load_config", lambda *a, **k: {})
    monkeypatch.setattr(company_master.notion_config, "get_gbizinfo_token", lambda cfg=None: "g")
    monkeypatch.setattr(company_master.notion_config, "has_japanpost_credentials", lambda: False)
    monkeypatch.setattr(company_master.notion_config, "get_postal_proxy_url",
                        lambda: "https://proxy.example/addresszip")
    company_master._preflight_gate(require_upsert=False)  # SystemExit を投げないこと


# --- 直接実行フォールバック (pytest 無し環境用、他テストに倣う) ----------------

if __name__ == "__main__":
    import inspect
    import tempfile

    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        params = set(inspect.signature(fn).parameters)
        unsupported = params - {"tmp_path", "monkeypatch"}
        if unsupported:
            # capsys 等の pytest 固有 fixture は直接実行モード非対応 (pytest で検証する)。
            print(f"SKIP {name} (要 pytest fixture: {sorted(unsupported)})")
            continue
        mp = pytest.MonkeyPatch() if "monkeypatch" in params else None
        try:
            with tempfile.TemporaryDirectory() as d:
                kwargs = {}
                if "tmp_path" in params:
                    kwargs["tmp_path"] = Path(d)
                if mp is not None:
                    kwargs["monkeypatch"] = mp
                fn(**kwargs)
            print(f"PASS {name}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL {name}: {e}")
        finally:
            if mp is not None:
                mp.undo()
    print(f"\n{'OK' if failures == 0 else 'FAIL'}: {failures} failures")
    sys.exit(1 if failures else 0)

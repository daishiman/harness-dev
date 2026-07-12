#!/usr/bin/env python3
# /// script
# name: validate_company_master
# purpose: SKILL.md『検証』とcolumns.mdの7列整合ルール(deterministic_checks a-h)をレコード/Notion行JSONに対し実判定する。確認用URLはページ本文へ移行し検査対象は source_by_field(新形式・per-field出典)/source_urls(旧形式)。正式名称列は会社名(title)へ統合済みで列を持たない(official_nameはprovenanceのみ)。
# inputs:
#   - argv: <records.json> | -  (stdin)。records は record list または単一 record
#   - format: enrich/upsert の record {fields, overall_certainty, remarks_text, source_by_field, source_urls} か Notion行相当の7列dict
# outputs:
#   - stdout: 検査サマリ
#   - stderr: 違反理由 (行番号付き)
#   - exit: 0=全行PASS / 1=違反あり / 2=usage/parse error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""企業マスタ deterministic_checks 検証器。

columns.md の整合ルール (a)-(h) を実判定する。SKILL.md『検証』節と build-trace の
検証主張に対応する実体。レコード(enrich/upsert の record)または Notion 行相当の 7列 dict
を入力に取り、違反を非0終了 + 理由出力で報告する。

判定項目:
  (a) 非空郵便番号は ^\\d{3}-\\d{4}$ (8文字)
  (b) 非空電話番号はハイフンを含む数字列
  (c) 非空住所は都道府県起点
  (d) 非空法人番号は13桁数字
  (e) 確度は4日本語ラベルのいずれか・英語enumは0件
  (f) 空欄属性を持つ行は『未確定(要確認)』かつ備考に定型文言あり
  (g) per-field 出典検査 (後方互換 gating):
      - 新形式 (source_by_field {field:{origin,url}} がある record): 全6属性に origin
        (enum 5値: gbizinfo/japanpost/web/user_input/none) 必須、origin=web は url 必須
      - fallback tier 機械照合 (data-sources.md fallback tier 表 正本):
        * origin → 確度ラベル上限 (ORIGIN_CERTAINTY_CAP)。フォールバックでの確度昇格
          (例: origin=web なのに『公的データで確認済み』) を FAIL (Goodhart 遮断)
        * 属性×許可段ホワイトリスト (FIELD_ALLOWED_ORIGINS)。例: postal_code の
          origin=web (郵便番号の Web 取得) を FAIL
        * 非空 postal_code は origin=japanpost / 確度『公的データ取得』/ 日本郵便検証URLを必須化
      - 旧形式 (source_by_field 無し): record 形式の非空 postal_code は出典不明として FAIL。
        それ以外は現行検査へ縮退 —『ネット検索(要確認)』行は source_urls 非空
        (Notion行形式は source_urls キーがある場合のみ適用)
  (h) 7列構成 (正式名称列は会社名へ統合)・空/未確定法人番号でキー衝突なし (行集合全体で検査)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import remarks as remarks_module  # noqa: E402
from postal_api import JAPANPOST_VERIFY_URL  # noqa: E402  (郵便番号検証URLの唯一の正本を参照・literal再定義しない)

POSTAL_RE = re.compile(r"^\d{3}-\d{4}$")
PHONE_RE = re.compile(r"^[\d-]*\d[\d-]*$")  # 数字を含みハイフン許容
HOJIN_BANGO_RE = re.compile(r"^\d{13}$")
PREFECTURES = (
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県",
    "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県",
    "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県",
    "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
)

CERTAINTY_PUBLIC_VERIFIED = "公的データで確認済み"
CERTAINTY_PUBLIC_FETCHED = "公的データ取得"
CERTAINTY_WEB = "ネット検索(要確認)"
CERTAINTY_UNRESOLVED = "未確定(要確認)"
VALID_CERTAINTIES = {
    CERTAINTY_PUBLIC_VERIFIED, CERTAINTY_PUBLIC_FETCHED,
    CERTAINTY_WEB, CERTAINTY_UNRESOLVED,
}
# 英語 enum 値の誤用検出 (e)。
ENGLISH_ENUM_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")

# per-field 出典 origin の値域 (g)。confirm-url-template.md の表示由来表 / enrich_company と対応。
VALID_ORIGINS = {"gbizinfo", "japanpost", "web", "user_input", "none"}

# fallback tier 機械照合 (g)。正本: references/data-sources.md「フォールバック多段化」節。
# 確度の強さ順位 (上限照合用)。
_CERTAINTY_RANK = {
    CERTAINTY_UNRESOLVED: 0, CERTAINTY_WEB: 1,
    CERTAINTY_PUBLIC_FETCHED: 2, CERTAINTY_PUBLIC_VERIFIED: 3,
}
# origin → 確度ラベル上限 (確度昇格禁止)。user_input は確度付与対象外のため上限検査なし。
ORIGIN_CERTAINTY_CAP = {
    "gbizinfo": CERTAINTY_PUBLIC_VERIFIED,
    "japanpost": CERTAINTY_PUBLIC_FETCHED,
    "web": CERTAINTY_WEB,
    "none": CERTAINTY_UNRESOLVED,
}
# 属性 × 許可 origin ホワイトリスト (許可段)。postal_code は Web/ユーザー入力不可 (日本郵便 API のみ)。
# company_name は会社名タイトルへ official_name(登記名) を統合できるため gbizinfo も許可する
# (cap=『公的データで確認済み』と整合。R3 で title=official_name or company_name)。
FIELD_ALLOWED_ORIGINS = {
    "company_name": {"user_input", "web", "gbizinfo", "none"},
    "official_name": {"gbizinfo", "web", "user_input", "none"},
    "address": {"gbizinfo", "web", "user_input", "none"},
    "postal_code": {"japanpost", "none"},
    "hojin_bango": {"gbizinfo", "web", "user_input", "none"},
    "phone_number": {"web", "user_input", "none"},
}
# JAPANPOST_VERIFY_URL は postal_api を唯一の正本として import 済み (literal 再定義しない)。

# source_by_field provenance の検査対象 6 属性。official_name は DB 列を廃し会社名タイトルへ
# 統合 (R3/R4) したが、出所層の provenance としては残す (表示層と出所層の分離・D1)。
ATTRIBUTE_FIELDS = (
    "company_name", "official_name", "address",
    "postal_code", "hojin_bango", "phone_number",
)
# Notion 行相当 (日本語列名) からの取り込みマッピング (h: 列構成検査用)。
# 正式名称列は廃止し会社名(title)へ official_name を統合したため 7 列構成 (会社名/住所/郵便番号/
# 法人番号/電話番号 + 情報の確かさ/備考)。official_name は DB 列ではなく source_by_field で保持する。
JP_COL_MAP = {
    "会社名": "company_name", "住所": "address",
    "郵便番号": "postal_code", "法人番号": "hojin_bango", "電話番号": "phone_number",
}
REQUIRED_JP_COLS = set(JP_COL_MAP) | {"情報の確かさ", "備考"}
# Notion 行 (列) として空欄判定する属性 = JP_COL_MAP の値 (official_name は列でないため除外)。
NOTION_COLUMN_FIELDS = tuple(JP_COL_MAP.values())


def _source_urls_text(value) -> str:
    """source_urls(list[{attribute,url}])から URL を取り出し改行連結する。

    後方互換: 旧フラット str リストや単一 str も許容する (本文移行前後どちらも受ける)。
    """
    if isinstance(value, list):
        urls: list[str] = []
        for entry in value:
            if isinstance(entry, dict):
                u = (entry.get("url") or "").strip()
                if u:
                    urls.append(u)
            elif isinstance(entry, str) and entry.strip():
                urls.append(entry.strip())
        return "\n".join(urls)
    if isinstance(value, str):
        return value
    return ""


def normalize_record(rec: dict) -> dict:
    """enrich/upsert の record か Notion行相当 dict を共通形へ正規化する。

    確認用URL はページ本文へ移行したため検査対象は source_urls (record 形式)。
    Notion 行形式は確認用URL列を持たないが、source_urls キーがあれば取り込む (後方互換)。
    正式名称列は廃止し会社名(title)へ official_name を統合したため Notion 行は 7 列構成。
    """
    source_by_field = rec.get("source_by_field")
    if not isinstance(source_by_field, dict):
        source_by_field = None
    certainty_by_field = rec.get("certainty_by_field")
    if not isinstance(certainty_by_field, dict):
        certainty_by_field = {}
    if "fields" in rec and isinstance(rec["fields"], dict):
        fields = dict(rec["fields"])
        certainty = rec.get("overall_certainty", "")
        remarks_text = rec.get("remarks_text", "")
        confirm_url = _source_urls_text(rec.get("source_urls"))
        has_source_urls = "source_urls" in rec
        present_cols = set(fields) | {"情報の確かさ", "備考"}
        source_format = "record"
    else:
        # Notion 行相当 (日本語列名)。確認用URL列は廃止 (本文へ移行)。
        fields = {dst: rec.get(src, "") for src, dst in JP_COL_MAP.items()}
        certainty = rec.get("情報の確かさ", "")
        remarks_text = rec.get("備考", "")
        confirm_url = _source_urls_text(rec.get("source_urls"))
        has_source_urls = "source_urls" in rec
        present_cols = set(rec.keys())
        source_format = "notion-row"
    return {
        "fields": fields,
        "certainty": certainty,
        "remarks_text": remarks_text,
        "confirm_url": confirm_url,
        "has_source_urls": has_source_urls,
        "source_by_field": source_by_field,
        "certainty_by_field": certainty_by_field,
        "present_cols": present_cols,
        "source_format": source_format,
    }


def _matches_remark_phrase(line: str, remark_phrases: set[str]) -> bool:
    """備考 1 行が定型文言 (完全一致) または placeholder 付きテンプレのパターンに一致するか。

    remarks-templates.md の文言に `{name}` placeholder が含まれる場合 (例:
    all_tiers_exhausted)、placeholder 部を非貪欲ワイルドカードに置換した fullmatch で判定する
    (定型骨格は固定・可変部のみ許容。自由記述は引き続き FAIL)。
    """
    if line in remark_phrases:
        return True
    for phrase in remark_phrases:
        if "{" not in phrase:
            continue
        pattern = re.sub(r"\\\{[a-z_]+\\\}", ".+?", re.escape(phrase))
        if re.fullmatch(pattern, line):
            return True
    return False


def validate_row(rec: dict, idx: int, remark_phrases: set[str]) -> list[str]:
    n = normalize_record(rec)
    f = n["fields"]
    errs: list[str] = []
    prefix = f"row[{idx}]"

    postal = f.get("postal_code", "")
    if postal and not POSTAL_RE.match(postal):
        errs.append(f"{prefix} (a) 郵便番号 '{postal}' が NNN-NNNN(8文字) 不一致")

    phone = f.get("phone_number", "")
    if phone and (not PHONE_RE.match(phone) or "-" not in phone):
        errs.append(f"{prefix} (b) 電話番号 '{phone}' がハイフン含む数字列でない")

    address = f.get("address", "")
    if address and not any(address.startswith(p) for p in PREFECTURES):
        errs.append(f"{prefix} (c) 住所 '{address}' が都道府県起点でない")

    hojin = f.get("hojin_bango", "")
    if hojin and not HOJIN_BANGO_RE.match(hojin):
        errs.append(f"{prefix} (d) 法人番号 '{hojin}' が13桁数字でない")

    certainty = n["certainty"]
    if certainty not in VALID_CERTAINTIES:
        errs.append(f"{prefix} (e) 情報の確かさ '{certainty}' が4日本語ラベル外")
    elif ENGLISH_ENUM_RE.match(certainty):
        errs.append(f"{prefix} (e) 情報の確かさ '{certainty}' は英語enum値 (日本語ラベル必須)")

    # 空欄判定の対象: record 形式は provenance 6 属性 (official_name 含む)、Notion 行形式は
    # 実在 7 列の属性 (official_name は列でないため除外)。列を持たない属性で空欄誤検知しない。
    empty_check_fields = (
        ATTRIBUTE_FIELDS if n["source_format"] == "record" else NOTION_COLUMN_FIELDS
    )
    has_empty = any(not f.get(k) for k in empty_check_fields)
    if has_empty:
        if certainty != CERTAINTY_UNRESOLVED:
            errs.append(f"{prefix} (f) 空欄属性ありだが確度が『未確定(要確認)』でない: '{certainty}'")
        remark = n["remarks_text"].strip()
        if not remark:
            errs.append(f"{prefix} (f) 空欄属性ありだが備考が空 (定型文言が必要)")
        else:
            # 備考の各行が remarks-templates.md(正本) の定型文言であること (自由記述検出)。
            # placeholder 付きテンプレ (例: all_tiers_exhausted の {field}/{attempts}) は
            # 展開後の値が行ごとに異なるため、パターン一致で定型性を判定する。
            for line in remark.splitlines():
                line = line.strip()
                if line and not _matches_remark_phrase(line, remark_phrases):
                    errs.append(f"{prefix} (f) 備考に非定型文言(自由記述): '{line}'")

    # (g) per-field 出典検査 (後方互換 gating)。
    #     新形式 (source_by_field あり): 全6属性に origin 必須 (enum 5値)、origin=web は url 必須。
    #     旧形式: 現行検査へ縮退 —『ネット検索(要確認)』行は source_urls 非空
    #     (record 形式は常に検査、notion-row 形式は source_urls キーがある場合のみ検査)。
    sbf = n["source_by_field"]
    if sbf is not None:
        for field in ATTRIBUTE_FIELDS:
            spec = sbf.get(field)
            if not isinstance(spec, dict) or spec.get("origin") not in VALID_ORIGINS:
                errs.append(
                    f"{prefix} (g) source_by_field['{field}'] の origin が欠落または5値"
                    f" (gbizinfo/japanpost/web/user_input/none) 外"
                )
                continue
            origin = spec["origin"]
            if origin == "web" and not (spec.get("url") or "").strip():
                errs.append(
                    f"{prefix} (g) source_by_field['{field}'] は origin=web だが url が空"
                    " (ネット検索値は根拠URL必須)"
                )
            if origin == "gbizinfo" and f.get(field) and not (spec.get("url") or "").strip():
                errs.append(
                    f"{prefix} (g) source_by_field['{field}'] は origin=gbizinfo だが url が空"
                    " (gBizINFO値は法人詳細ページURL必須)"
                )
            if field == "postal_code" and postal:
                field_certainty = n["certainty_by_field"].get(field)
                url = (spec.get("url") or "").strip()
                if origin != "japanpost":
                    errs.append(
                        f"{prefix} (g) 非空 postal_code の origin は japanpost 必須"
                        " (郵便番号は日本郵便 addresszip API のみ採用)"
                    )
                if field_certainty != CERTAINTY_PUBLIC_FETCHED:
                    errs.append(
                        f"{prefix} (g) 非空 postal_code の属性別確度は『{CERTAINTY_PUBLIC_FETCHED}』必須"
                    )
                if url != JAPANPOST_VERIFY_URL:
                    errs.append(
                        f"{prefix} (g) 非空 postal_code の検証URLは日本郵便固定URL必須"
                    )
            # fallback tier 機械照合 (data-sources.md fallback tier 表 正本)。
            # (g-1) 属性×許可段ホワイトリスト: 許可されない手段で取得した値を遮断。
            if origin not in FIELD_ALLOWED_ORIGINS[field]:
                errs.append(
                    f"{prefix} (g) {field} の origin '{origin}' は許可段外"
                    " (属性×許可段ホワイトリスト: data-sources.md 正本)"
                )
            # (g-2) origin → 確度ラベル上限: フォールバックによる確度昇格を遮断 (昇格禁止)。
            field_certainty = n["certainty_by_field"].get(field)
            cap = ORIGIN_CERTAINTY_CAP.get(origin)
            if (
                cap is not None
                and field_certainty in _CERTAINTY_RANK
                and _CERTAINTY_RANK[field_certainty] > _CERTAINTY_RANK[cap]
            ):
                errs.append(
                    f"{prefix} (g) {field} の確度 '{field_certainty}' が origin={origin} の"
                    f" 上限 '{cap}' を超過 (確度昇格禁止)"
                )
    else:
        if n["source_format"] == "record" and postal:
            errs.append(
                f"{prefix} (g) 非空 postal_code だが source_by_field が無く出典不明"
                " (郵便番号は origin=japanpost の新形式 record 必須)"
            )
        if certainty == CERTAINTY_WEB and (
            n["source_format"] == "record" or n["has_source_urls"]
        ) and not n["confirm_url"].strip():
            errs.append(f"{prefix} (g) 『ネット検索(要確認)』だが根拠URL(source_urls)が空")

    expected_cols = (
        set(ATTRIBUTE_FIELDS) | {"情報の確かさ", "備考"}
        if n["source_format"] == "record"
        else REQUIRED_JP_COLS
    )
    # source_urls / source_by_field は確認用URL本文移行に伴う (g) 検査用の任意キーで
    # 列ではないため列構成検査から除外。
    present = set(n["present_cols"]) - {"source_urls", "source_by_field"}
    if present != expected_cols:
        missing = expected_cols - present
        extra = present - expected_cols
        if missing:
            errs.append(f"{prefix} (h) 必須列が不足: {', '.join(sorted(missing))}")
        if extra:
            errs.append(f"{prefix} (h) 禁止/余剰列あり: {', '.join(sorted(extra))}")

    return errs


def check_key_collision(records: list[dict]) -> list[str]:
    """(h) 空/未確定法人番号でのキー衝突を起こさないことを検査する。"""
    errs: list[str] = []
    seen: dict[str, int] = {}
    for idx, rec in enumerate(records):
        n = normalize_record(rec)
        hojin = n["fields"].get("hojin_bango", "")
        if not hojin or not HOJIN_BANGO_RE.match(hojin):
            continue  # 空/未確定法人番号は信頼キーでない → 衝突対象外 (新規追記のみ)
        if hojin in seen:
            errs.append(
                f"(h) 確定法人番号 '{hojin}' が row[{seen[hojin]}] と row[{idx}] で重複 (キー衝突)"
            )
        else:
            seen[hojin] = idx
    return errs


def load_records(arg: str) -> list[dict]:
    raw = sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("入力は record(dict) または records(list) でなければならない")


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: validate_company_master.py <records.json> | -\n")
        return 2
    try:
        records = load_records(sys.argv[1])
    except (OSError, json.JSONDecodeError, ValueError) as e:
        sys.stderr.write(f"parse error: {e}\n")
        return 2

    # 備考定型文言の集合 (正本 remarks-templates.md)。(f) の自由記述検出に使う。
    remark_phrases = set(remarks_module.load_templates().values())

    all_errs: list[str] = []
    for idx, rec in enumerate(records):
        all_errs.extend(validate_row(rec, idx, remark_phrases))
    all_errs.extend(check_key_collision(records))

    if all_errs:
        for e in all_errs:
            sys.stderr.write(e + "\n")
        sys.stderr.write(f"\nFAIL: {len(records)} rows, {len(all_errs)} violations\n")
        return 1
    print(f"OK: {len(records)} rows passed deterministic_checks (a-h)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

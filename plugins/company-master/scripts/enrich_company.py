#!/usr/bin/env python3
# /// script
# name: enrich_company
# purpose: 確定エンティティの空欄属性のみを 日本郵便API/Web検索で補完し、各値に情報の確かさ4ラベルと備考を付与する。全6属性の取得由来は source_by_field({field:{origin,url}})に保持し、source_urls は列順派生(確認用URLはページ本文へ移行)。
# inputs:
#   - argv: --entity <json> (resolve_company の出力。source_url=gBizINFO法人詳細ページを含む) / --web-findings <json> (Claudeの検索結果, 任意)
#   - net: 日本郵便 addresszip API (住所→郵便番号逆引き, postal_api 経由)。電話番号のWeb検索はClaudeが実施しPythonは検証のみ
# outputs:
#   - stdout: JSON {fields, certainty_by_field, overall_certainty, remark_keys, remarks_text, source_by_field, source_urls, missing_fields, attempts}
#   - exit: 0=OK
# contexts: [C, E]
# network: true
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""enrich-attributes 責務の決定論層。

確定エンティティに対し空欄属性のみを補完する。各値に『情報の確かさ』を付与し、
高確度ソース (gBizINFO / 日本郵便) で一意確定した値のみ自動確定する (誤値混入回避の
非対称コスト原則: 誤値 >> 空欄)。取得不能は空欄 + 『未確定(要確認)』とし、『備考』へ
references/remarks-templates.md の定型テンプレート文言で原因を記録する。

per-field provenance (出典スキーマの正本): 全 6 属性の取得由来を `source_by_field`
(= {field: {origin, url}}, origin enum = {gbizinfo, japanpost, web, user_input, none}) として
必ず付与する (company_name=user_input 含む)。gBizINFO 由来 3 属性は法人詳細ページ URL
(strong)、郵便番号は日本郵便トップの固定 URL (weak)、電話番号は番号埋め込み Google 検索の固定 URL (weak) を持つ。
各 field 値 dict は拡張可能 (後続のフォールバック多段化が attempts 等を併設できる)。
`source_urls` は source_by_field から ATTRIBUTE_FIELDS 固定順 (columns.md 列順) で導出する
派生値 (後方互換)。後段(notion_upsert)が confirm-url-template.md の定型テンプレートで
Notion ページ本文へ展開する (確認用URL は DB プロパティ列でなくページ本文へ移行)。

責務分離: 郵便番号は日本郵便公式 API (postal_api) で逆引きし純Pythonで完結する。電話番号などの
『Web検索』は Claude Code 内蔵検索が実施し、Python は結果(値+URL)を検証・整形するのみ
(スクリプトが Web 検索 API を叩く実装はしない)。検索結果は enrich(web_findings=...) で受け取る。

フォールバック多段化 (正本: references/data-sources.md fallback tier 表):
  - 出力 top-level に missing_fields[] (空欄のままの属性) と attempts[]
    ({field, source, pattern, result, reject_reason}) を持つ。agent は attempts に無い
    (source, pattern) のみ次試行する (gap-driven 単調前進)。
  - 同一 (field, source, pattern) の再試行は機械的にスキップし、field あたり
    MAX_ATTEMPTS_PER_FIELD=3 で打ち切る (有限1巡・無限探索の禁止)。
  - entity.attempts (前パスの試行履歴) は引き継いで重複試行を遮断する (2 パス運用)。
  - 確度昇格禁止: フォールバックで上位確度ラベルを付けない (validate (g) が機械照合)。

フォーマット規約 (key_constraints[A] 正本):
  - 郵便番号: 〒なし・ハイフン込み 8 文字 NNN-NNNN
  - 電話番号: ハイフン区切り (例 03-1234-5678)
  - 住所: 都道府県起点に正規化
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import remarks as remarks_module  # noqa: E402  (備考定型文言の正本 remarks-templates.md を展開する)
import normalize as normalize_module  # noqa: E402  (会社名/住所正規化の共有正本)
import postal_api  # noqa: E402  (日本郵便 addresszip API による住所→郵便番号逆引き)
import confirm_url as confirm_url_module  # noqa: E402  (属性表示名/列順の共有定義: FIELD_LABELS)
import resolve_company  # noqa: E402  (gBizINFO 法人詳細ページ URL の共有正本)

POSTAL_RE = re.compile(r"^\d{3}-\d{4}$")
PHONE_RE = re.compile(r"^\d{1,4}(-\d{1,4}){1,3}$")

CERTAINTY_PUBLIC_VERIFIED = "公的データで確認済み"
CERTAINTY_PUBLIC_FETCHED = "公的データ取得"
CERTAINTY_WEB = "ネット検索(要確認)"
CERTAINTY_UNRESOLVED = "未確定(要確認)"

# 主要市外局番 → 都道府県 (代表のみ)。電話番号×住所の軽量クロスチェック用。
# マップに無い市外局番は過剰棄却を避けるため棄却しない (軽量方針)。
AREA_CODE_PREFECTURE = {
    "03": "東京都", "06": "大阪府", "011": "北海道", "022": "宮城県",
    "045": "神奈川県", "052": "愛知県", "075": "京都府", "078": "兵庫県",
    "092": "福岡県", "082": "広島県", "025": "新潟県", "048": "埼玉県",
    "043": "千葉県", "099": "鹿児島県", "098": "沖縄県",
}

# 6 属性 (brief output_contract / key_constraints[A] 正本)。overall_certainty 導出の対象集合。
ATTRIBUTE_FIELDS = (
    "company_name", "official_name", "address",
    "postal_code", "hojin_bango", "phone_number",
)

# 取得由来 origin enum (source_by_field の値域。confirm-url-template.md の表示由来表と対応)。
ORIGIN_GBIZINFO = "gbizinfo"
ORIGIN_JAPANPOST = "japanpost"
ORIGIN_WEB = "web"
ORIGIN_USER_INPUT = "user_input"
ORIGIN_NONE = "none"

# フォールバック多段化の停止条件 (data-sources.md fallback tier 表 正本): field あたりの
# 試行記録上限。同一 (source, pattern) の再試行とあわせて機械的にスキップする。
MAX_ATTEMPTS_PER_FIELD = 3

# 電話番号の確認用 URL を生成する固定検索手段の SSOT (R2)。Google で `"<電話番号>"`
# (ダブルクォート完全一致検索) を引くクエリを唯一の定義として持ち、他所で literal 再定義しない。
PHONE_SEARCH_BASE = "https://www.google.com/search?q="


def phone_search_url(phone: str) -> str:
    """電話番号の確認用 URL を Google 検索クエリで決定論生成する (固定手段・weak provenance)。

    `"<電話番号>"` を urllib.parse.quote で %22+番号へエンコードし、同一番号→同一 URL の
    byte 安定を保つ (R2)。番号内のハイフンは unreserved のため非エンコードで残る。空番号は空文字。
    """
    p = (phone or "").strip()
    if not p:
        return ""
    return PHONE_SEARCH_BASE + urllib.parse.quote(f'"{p}"')


def note_attempt(attempts: list[dict], field: str, source: str, pattern: str,
                 result: str, reject_reason: str = "") -> bool:
    """試行履歴へ 1 件追記する (gap-driven 単調前進の機械強制)。

    同一 (field, source, pattern) が既にあれば追記しない (再試行の機械スキップ)。
    field あたり MAX_ATTEMPTS_PER_FIELD 件で打ち切る (有限停止)。追記したら True。

    注意: この dedup/cap は Web/agent の gap-driven 多段試行 (1 段=1 呼び出し) 専用。
    日本郵便 postal_api は 1 回の決定論呼び出しで内部多段 (構造化/freeword/市区町村prefix)
    を完結させ、その sub-attempts を冪等スナップショットとして全件転記する
    (graft_postal_snapshot)。同一 pattern が複数バリアントで再出現したり 3 件を超えても
    欠落させない (prefix hit の観測性を保つ)。
    """
    for a in attempts:
        if (a.get("field"), a.get("source"), a.get("pattern")) == (field, source, pattern):
            return False
    if sum(1 for a in attempts if a.get("field") == field) >= MAX_ATTEMPTS_PER_FIELD:
        return False
    attempts.append({"field": field, "source": source, "pattern": pattern,
                     "result": result, "reject_reason": reject_reason})
    return True


def graft_postal_snapshot(attempts: list[dict], sub_attempts: list[dict]) -> None:
    """日本郵便 postal_api の sub-attempts を attempts[] へ冪等に全件転記する。

    postal_api.lookup_postal は 1 回の決定論呼び出しで構造化検索→freeword→市区町村prefix の
    内部多段を完結させ、その各段を sub_attempts として返す。これは「完結した1スナップショット」
    なので note_attempt の gap-driven dedup/MAX_ATTEMPTS_PER_FIELD cap は適用しない
    (同一 pattern の再出現・3 件超・先行 miss 後の hit を欠落させると prefix/town-trimmed hit の
    観測性と postal_code の result 整合が壊れる)。

    cross-pass 冪等性: entity.attempts に前パスの japanpost postal snapshot が引き継がれている
    場合、今パスで同じ snapshot を二重追加しない。既存の (field=postal_code, source=japanpost)
    行を全除去してから今回のスナップショットを順序保持で転記し置換する (件数が二重化しない)。
    japanpost 以外の postal 行 (将来の別ソース) と postal_code 以外の field は保持する。
    """
    attempts[:] = [a for a in attempts
                   if not (a.get("field") == "postal_code"
                           and a.get("source") == "japanpost")]
    for a in sub_attempts:
        attempts.append({
            "field": "postal_code",
            "source": a.get("source", "japanpost"),
            "pattern": a.get("pattern", ""),
            "result": a.get("result", ""),
            "reject_reason": a.get("reject_reason", ""),
        })


def derive_overall_certainty(fields: dict, certainty_by_field: dict) -> str:
    """行全体の『情報の確かさ』を属性別確度から導出する (確度4ラベル・英語禁止)。

    優先度 (上から評価):
      1. いずれかの属性が空 or その確度が『未確定(要確認)』 → 『未確定(要確認)』
      2. Web 由来 (『ネット検索(要確認)』) を含む               → 『ネット検索(要確認)』
      3. 公的取得 (『公的データ取得』) のみ含む                  → 『公的データ取得』
      4. 全て一意確定済み (『公的データで確認済み』)             → 『公的データで確認済み』
    """
    values = [certainty_by_field.get(k) for k in ATTRIBUTE_FIELDS]
    has_empty = any(not fields.get(k) for k in ATTRIBUTE_FIELDS)
    if has_empty or CERTAINTY_UNRESOLVED in values:
        return CERTAINTY_UNRESOLVED
    if CERTAINTY_WEB in values:
        return CERTAINTY_WEB
    if CERTAINTY_PUBLIC_FETCHED in values:
        return CERTAINTY_PUBLIC_FETCHED
    return CERTAINTY_PUBLIC_VERIFIED


def normalize_address(addr: str) -> str:
    """住所を都道府県起点表記に正規化する (共有正本 normalize に委譲)。"""
    return normalize_module.normalize_address(addr)


def postal_from_address(address: str, company_name: str = "") -> dict:
    """住所→郵便番号を 日本郵便 addresszip API で逆引きする (公式 API 完結)。

    実体は postal_api.lookup_postal。構造化検索 (pref/city/town。town は小字/大字を段階剥離した
    複数バリアント) → freeword → 市区町村一覧の最長前方一致の 3 段で逆引きし、
    pick_best / pick_best_prefix で一意確定したもののみ NNN-NNNN を CERTAINTY_PUBLIC_FETCHED で返す。一意でない/
    未一致/取得失敗 (認証/通信) は空欄 + 未確定 + remark_key='postal_code' (誤値を入れない)。
    試行履歴は attempts ([{source:'japanpost', pattern, result, reject_reason}]) キーで返る。
    """
    return postal_api.lookup_postal(address, company_name=company_name)


def _area_code(phone: str) -> str:
    """電話番号先頭の市外局番を AREA_CODE_PREFECTURE のキーから最長一致で抽出する。"""
    head = phone.split("-", 1)[0] if "-" in phone else phone
    for length in (3, 2):
        if head[:length] in AREA_CODE_PREFECTURE:
            return head[:length]
    return ""


def verify_phone(candidate: dict, address: str) -> dict:
    """Claude(Web検索)が渡した電話候補を検証・整形する (Pythonは検索しない)。

    candidate 形式: {"value": "03-1234-5678", "source_url": "https://..."}。
    検査: (a) ハイフン区切り数字列 (PHONE_RE) (b) 市外局番×所在地都道府県の軽量クロスチェック。
    マップに在る市外局番が住所都道府県と矛盾したら棄却。マップに無い局番は棄却しない (過剰棄却回避)。
    整合時のみ value+source_url を CERTAINTY_WEB で採用。不整合/未提供/形式不正は空欄+未確定+remark。
    """
    value = (candidate or {}).get("value", "").strip()
    source_url = (candidate or {}).get("source_url", "").strip()
    if not value or not PHONE_RE.match(value):
        return {"value": "", "certainty": CERTAINTY_UNRESOLVED,
                "remark_key": "phone_number", "source_url": ""}
    code = _area_code(value)
    if code:
        expected_pref = AREA_CODE_PREFECTURE[code]
        if address and not address.startswith(expected_pref):
            # マップに在る局番が住所都道府県と矛盾 → 棄却 (誤値を入れない)
            return {"value": "", "certainty": CERTAINTY_UNRESOLVED,
                    "remark_key": "phone_number", "source_url": ""}
    return {"value": value, "certainty": CERTAINTY_WEB,
            "remark_key": "", "source_url": source_url}


def derive_source_urls(source_by_field: dict) -> list[dict]:
    """source_by_field から source_urls を ATTRIBUTE_FIELDS 固定順 (columns.md 列順) で導出する。

    source_urls は派生値 (後方互換): URL を持つ field のみ {attribute, origin, url} で列挙する。
    本文レンダリングの正本入力は source_by_field 側 (notion_upsert が confirm_url へ渡す)。
    """
    out: list[dict] = []
    for field in ATTRIBUTE_FIELDS:
        spec = source_by_field.get(field) or {}
        url = (spec.get("url") or "").strip()
        if url:
            out.append({"attribute": confirm_url_module.FIELD_LABELS[field],
                        "origin": spec.get("origin", ORIGIN_NONE), "url": url})
    return out


def enrich(entity: dict, web_findings: dict | None = None) -> dict:
    """空欄属性のみ補完。既に確定済みの属性は触らない。

    web_findings: Claude が goal-seek ループで実施した Web 検索結果 (任意)。
    形式例: {"phone": {"value": "03-1234-5678", "source_url": "https://..."}}。
    Python はこの結果を検証・整形するのみで、Web 検索 API は叩かない (責務分離)。

    entity.source_url: resolve_company が返す gBizINFO 法人詳細ページ URL (任意・後方互換)。
    gBizINFO 由来 3 属性 (official_name / hojin_bango / address) の per-value 検証 URL になる。
    """
    web_findings = web_findings or {}
    official_name = entity.get("official_name", "")
    address = normalize_address(entity.get("address", ""))
    gbiz_url = (entity.get("source_url") or "").strip()  # resolve 由来 (旧 replay は .get 既定)
    if not gbiz_url and entity.get("hojin_bango"):
        gbiz_url = resolve_company.detail_page_url(str(entity.get("hojin_bango", "")))

    fields: dict[str, str] = {
        "company_name": entity.get("company_name", ""),       # 入力通称を保持
        "official_name": official_name,                        # gBizINFO 登記名
        "address": address,
        "postal_code": entity.get("postal_code", ""),
        "hojin_bango": entity.get("hojin_bango", ""),
        "phone_number": entity.get("phone_number", ""),
    }
    certainty: dict[str, str] = {}
    remarks: list[str] = []
    # per-field 取得由来 (出典スキーマ正本)。値 dict は拡張可能 (フォールバック多段化が
    # attempts 等を併設できる)。最後に全 6 属性へ必ず origin を埋める (欠落させない)。
    source_by_field: dict[str, dict] = {}
    # 試行履歴 (gap-driven 2 パス運用): 前パスの attempts を entity から引き継ぎ、
    # 同一 (field, source, pattern) の再試行を note_attempt が機械スキップする。
    attempts: list[dict] = [dict(a) for a in (entity.get("attempts") or [])
                            if isinstance(a, dict)]

    # 会社名は入力通称 (ユーザー入力由来・URL 無し)
    if fields["company_name"]:
        source_by_field["company_name"] = {"origin": ORIGIN_USER_INPUT, "url": ""}

    # gBizINFO 由来 (確定済み)。検証 URL は法人詳細ページ (strong)。
    if fields["official_name"]:
        certainty["official_name"] = CERTAINTY_PUBLIC_VERIFIED
        source_by_field["official_name"] = {"origin": ORIGIN_GBIZINFO, "url": gbiz_url}
    if fields["hojin_bango"]:
        certainty["hojin_bango"] = CERTAINTY_PUBLIC_VERIFIED
        source_by_field["hojin_bango"] = {"origin": ORIGIN_GBIZINFO, "url": gbiz_url}
    if fields["address"]:
        certainty["address"] = CERTAINTY_PUBLIC_FETCHED
        source_by_field["address"] = {"origin": ORIGIN_GBIZINFO, "url": gbiz_url}
    if fields["postal_code"]:
        certainty["postal_code"] = CERTAINTY_PUBLIC_FETCHED
        source_by_field["postal_code"] = {
            "origin": ORIGIN_JAPANPOST,
            "url": (entity.get("postal_code_source_url") or postal_api.JAPANPOST_VERIFY_URL),
        }
    if fields["phone_number"]:
        certainty["phone_number"] = CERTAINTY_WEB
        source_by_field["phone_number"] = {
            "origin": ORIGIN_WEB,
            "url": phone_search_url(fields["phone_number"]),
        }

    # 郵便番号 (日本郵便 addresszip API 逆引き)。検証 URL は日本郵便 郵便番号検索の固定 URL (weak)。
    if not fields["postal_code"] and fields["address"]:
        p = postal_from_address(fields["address"], fields["company_name"])
        # lookup 側の試行履歴 (japanpost) を field 付きで引き継ぐ。attempts キーを
        # 持たない実装 (テストスタブ等) は 1 件の合成試行として記録する。
        p_attempts = p.get("attempts") or [{
            "source": "japanpost", "pattern": "addresszip",
            "result": "hit" if p.get("value") else "miss",
            "reject_reason": "" if p.get("value") else "一意確定不能または未一致",
        }]
        # postal_api の sub-attempts は 1 回の決定論呼び出しの完結スナップショット。
        # note_attempt の gap-driven dedup/cap は通さず全件冪等転記する (cross-pass 置換)。
        graft_postal_snapshot(attempts, p_attempts)
        if p["value"] and POSTAL_RE.match(p["value"]):
            fields["postal_code"] = p["value"]
            certainty["postal_code"] = CERTAINTY_PUBLIC_FETCHED
            source_by_field["postal_code"] = {
                "origin": ORIGIN_JAPANPOST,
                "url": (p.get("source_url") or "").strip() or postal_api.JAPANPOST_VERIFY_URL,
            }
        else:
            certainty["postal_code"] = CERTAINTY_UNRESOLVED
            # 備考の使い分け (remarks-templates.md 正本): 日本郵便 API 試行が result=error
            # (= 取得失敗) なら reject_reason 種別で認証失敗 (auth) / 通信障害 (network) を、
            # データは在るが一意に引けない (miss) なら従来の postal_code を選ぶ。
            err = next((a for a in p_attempts if a.get("result") == "error"), None)
            if err:
                remarks.append("postal_api_unauthorized"
                               if str(err.get("reject_reason", "")).startswith("auth")
                               else "postal_api_unavailable")
            else:
                remarks.append(p["remark_key"] or "postal_code")

    # 電話番号 (Claude の Web 検索結果を Python が検証・整形)。検証 URL は番号埋め込み Google
    # 検索の固定 URL (R2・weak。per-value 根拠ページでなく『その番号を検索する手段』を提示)。
    if not fields["phone_number"]:
        phone_candidate = web_findings.get("phone")
        if phone_candidate:
            ph = verify_phone(phone_candidate, fields["address"])
            note_attempt(
                attempts, "phone_number", "web", "web_findings",
                "adopted" if ph["value"] else "rejected",
                "" if ph["value"] else "形式不正または市外局番×所在地都道府県の不整合",
            )
        else:
            # web_findings に phone 候補が無い = Web検索を実施していない or 検索したが候補なし。
            # 候補を検証して棄却した phone_number とは状態が異なるため別 remark_key を使う
            # (備考が『検索して失敗』と誤読されるのを防ぐ。postal が attempts 種別で文言を
            #  出し分けるのと対称に、phone も実際の試行内容に忠実な文言にする)。
            # 試行していないため attempts には記録しない (missing_fields が agent への gap 通知)。
            ph = {"value": "", "certainty": CERTAINTY_UNRESOLVED,
                  "remark_key": "phone_no_web_candidate", "source_url": ""}
        if ph["value"] and PHONE_RE.match(ph["value"]):
            fields["phone_number"] = ph["value"]
            certainty["phone_number"] = ph["certainty"]
            # origin=web 維持・url は固定の Google 検索 URL (R2)。Web ヒット URL でなく
            # 『番号を再検索する手段』を weak provenance として持つ (doc の web 定義に整合)。
            source_by_field["phone_number"] = {
                "origin": ORIGIN_WEB, "url": phone_search_url(fields["phone_number"])}
        else:
            certainty["phone_number"] = CERTAINTY_UNRESOLVED
            remarks.append(ph["remark_key"] or "phone_number")

    # 全 6 属性に origin を必ず付与する (未取得/空欄は none)。validate (g) の前提。
    for field in ATTRIBUTE_FIELDS:
        source_by_field.setdefault(field, {"origin": ORIGIN_NONE, "url": ""})

    # 行全体の確度を導出し、備考定型文言を remarks-templates.md(正本)から展開する。
    # notion_upsert.build_properties が読むキー (overall_certainty / remarks_text) に合わせる。
    overall_certainty = derive_overall_certainty(fields, certainty)
    remarks_text = remarks_module.expand(remarks)

    return {
        "fields": fields,
        "certainty_by_field": certainty,
        "overall_certainty": overall_certainty,
        "remark_keys": remarks,
        "remarks_text": remarks_text,
        "source_by_field": source_by_field,
        "source_urls": derive_source_urls(source_by_field),  # 列順派生 (後方互換)
        # フォールバック多段化 (gap-driven 2 パス運用): 空欄のままの属性と試行履歴。
        # agent は attempts に無い (source, pattern) のみ次試行し、backfill は replay JSONL へ併記する。
        "missing_fields": [f for f in ATTRIBUTE_FIELDS if not fields[f]],
        "attempts": attempts,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="enrich company attributes")
    ap.add_argument("--entity", required=True, help="resolve_company の entity JSON")
    ap.add_argument("--web-findings", default=None,
                    help="Claude の Web 検索結果 JSON (任意。例 {\"phone\": {\"value\": ..., \"source_url\": ...}})")
    args = ap.parse_args()
    entity = json.loads(args.entity)
    web_findings = json.loads(args.web_findings) if args.web_findings else None
    print(json.dumps(enrich(entity, web_findings), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

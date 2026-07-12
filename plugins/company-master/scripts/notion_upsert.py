#!/usr/bin/env python3
# /// script
# name: notion_upsert
# purpose: notion_config.get_db_id('company-master')/get_token で解決した企業マスタDBへ確定法人番号キーで7列をupsertし(会社名title=正式名称優先・正式名称列は統合廃止)、確認用URLはページ本文へ固定テンプレートで同期する(代替キー時は新規追記のみ)。
# inputs:
#   - argv: --record <json> (enrich_company の出力 + certainty/remarks/urls)
#   - config: notion_config.get_db_id("company-master") 経由 (解決順 env COMPANY_MASTER_NOTION_DATABASE_ID -> .notion-config.json -> notion-config.fixed.json)
# outputs:
#   - stdout: JSON {action: created|updated|skipped|rejected, page_id|violations}
#   - exit: 0=OK / 1=書き込みゲート reject (validate_row 違反) / 2=precondition gate or schema preflight fail-closed
# contexts: [C, E]
# network: true
# write-scope: notion
# dependencies: []
# requires-python: ">=3.10"
# ///
"""notion-master-upsert 責務の決定論層。

DB は notion_config.get_db_id('company-master') で解決 (リテラル直書き禁止)。
token は notion_config.get_token で取得 (共有 Keychain service)。

7 列構成 (key_constraints[A] 正本): 会社名(title=正式名称優先・通称フォールバック) / 住所 /
郵便番号 / 法人番号 / 電話番号 の 5 属性 + 『情報の確かさ』+ 『備考』。正式名称は独立列を廃止し
会社名タイトルへ統合 (official_name は source_by_field で provenance 保持)。source/last_verified 列は追加禁止。
確認用URL は DB プロパティ列ではなく**ページ本文**へ固定テンプレートで出力する
(confirm-url-template.md 正本・confirm_url.py が展開。DB 冗長化回避・100% 同一テンプレ SSOT)。

upsert 一意キー (key_constraints[C] 正本): gBizINFO 確定 13 桁法人番号のみ。
法人番号を持たない/取得不能な行は代替キー (正規化会社名 + 住所ハッシュ) で仮同定し、
『未確定(要確認)』として新規追記のみ (既存行への更新マージ対象外)。
既存非空セルは上書きしない (空欄のみ補完)。

書き込みゲート内蔵: upsert() は冒頭で validate_company_master.validate_row を実行し、
違反 record は呼び出し元 (wrapper / agent / backfill) によらず書き込まず
{action: "rejected", violations: [...]} を返す (検証 PASS の機械強制)。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notion_config  # noqa: E402
import normalize as normalize_module  # noqa: E402  (会社名/住所正規化・代替キーの共有正本)
import confirm_url  # noqa: E402  (確認用URLページ本文テンプレートの展開器: confirm-url-template.md 正本)
import remarks as remarks_module  # noqa: E402  (備考定型文言の正本: 書き込みゲートの (f) 検査用)
import validate_company_master  # noqa: E402  (deterministic_checks a-h: 書き込みゲートの実体)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Notion プロパティ名 (7 列。日本語列名は Notion DB スキーマと一致させる)。
# 確認用URL はプロパティ列でなくページ本文へ移行 (confirm_url.render_blocks)。
# COL_OFFICIAL_NAME は DB 列を廃止 (会社名 title へ統合・R4)。旧行/旧 page payload に含まれる
# 『正式名称』を best-effort で読むため定数だけ残す (extract_existing_fields / backfill.row_from_page)。
COL_COMPANY_NAME = "会社名"
COL_OFFICIAL_NAME = "正式名称"
COL_ADDRESS = "住所"
COL_POSTAL = "郵便番号"
COL_HOJIN_BANGO = "法人番号"
COL_PHONE = "電話番号"
COL_CERTAINTY = "情報の確かさ"
COL_REMARKS = "備考"


def alt_key(company_name: str, address: str) -> str:
    """代替キー = 正規化会社名 + 正規化住所の安定ハッシュ (共有正本 normalize に委譲)。

    全半角統一・空白除去・法人格表記ゆれ ((株)⇄株式会社 等) の吸収は normalize が担う
    (brief open_questions[2] 解消)。同入力→同キーの決定性を保証する。
    """
    return normalize_module.alt_key(company_name, address)


# レート制限/リトライ方針: 429/5xx は Retry-After 尊重の指数バックオフで最大
# RETRY_MAX_ATTEMPTS 回まで試行し、上限超過は NotionAPIRetryExhausted (構造化エラー) で
# fail-closed。4xx (429 以外) は仕様違反の即時失敗としてリトライしない。
RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY_SEC = 1.0


class NotionAPIRetryExhausted(RuntimeError):
    """429/5xx リトライ上限超過の構造化エラー (fail-closed: 書き込みを断念して伝播)。"""

    def __init__(self, method: str, path: str, last_status: int, attempts: int):
        self.method = method
        self.path = path
        self.last_status = last_status
        self.attempts = attempts
        super().__init__(
            f"Notion API リトライ上限超過 (fail-closed): {method} {path} "
            f"最終status={last_status} attempts={attempts}"
        )


def _send(req: urllib.request.Request) -> dict:
    """1 回の HTTP 送信 (テストでの差し替え点)。"""
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _retry_delay_sec(err: urllib.error.HTTPError, attempt: int) -> float:
    """リトライ待機秒。Retry-After ヘッダがあれば尊重し、無ければ指数バックオフ。"""
    retry_after = err.headers.get("Retry-After") if err.headers else None
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return RETRY_BASE_DELAY_SEC * (2 ** attempt)


def _api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{NOTION_API}{path}", data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    last_status = 0
    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            return _send(req)
        except urllib.error.HTTPError as e:
            if e.code != 429 and not (500 <= e.code < 600):
                raise  # 429 以外の 4xx はリトライ対象外 (即時失敗)
            last_status = e.code
            if attempt + 1 >= RETRY_MAX_ATTEMPTS:
                break
            time.sleep(_retry_delay_sec(e, attempt))
    raise NotionAPIRetryExhausted(method, path, last_status, RETRY_MAX_ATTEMPTS)


# --- Notion live スキーマ preflight (fail-closed) -------------------------------
# 期待スキーマの機械可読正本は references/notion-db-schema.json (生成元は
# company-master-columns.md の7列定義)。書き込み前に live DB と照合し、列欠落・
# 型不一致・『情報の確かさ』select 4オプション不一致・禁止列・API 不達を遮断する。

SCHEMA_JSON = Path(__file__).resolve().parent.parent / "references" / "notion-db-schema.json"

# プロセス内キャッシュ: 同一プロセスで preflight 通過済みの db_id (多重照会回避)。
_PREFLIGHT_OK: set[str] = set()


class SchemaPreflightError(RuntimeError):
    """live スキーマ不一致 / API 不達の構造化エラー (fail-closed: 書き込み前に遮断)。"""

    def __init__(self, violations: list[str]):
        self.violations = list(violations)
        super().__init__("; ".join(self.violations))


def load_expected_schema(path: Path | None = None) -> dict:
    """期待スキーマ JSON を読む。不在/破損は fail-closed (既定値で続行しない)。"""
    p = Path(path) if path else SCHEMA_JSON
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SchemaPreflightError(
            [f"期待スキーマ JSON が読めない (fail-closed): {p}: {e}"]
        ) from e
    props = data.get("properties")
    if not isinstance(props, dict) or not props:
        raise SchemaPreflightError([f"期待スキーマ JSON に properties が無い: {p}"])
    return data


def preflight_schema(db_id: str, token: str) -> None:
    """Notion API GET database の live スキーマを期待スキーマと照合する。

    違反/API 不達は SchemaPreflightError を送出 (呼び出し元は書き込まない)。
    照合内容: 必須7列の存在・型一致、『情報の確かさ』select 4オプションの完全一致
    (欠落も余剰改名も不一致)、禁止列 (source/last_verified/確認用URL/正式名称) と
    任意の余剰列の不在。
    """
    expected = load_expected_schema()
    try:
        live = _api("GET", f"/databases/{db_id}", token)
    except Exception as e:  # noqa: BLE001 - API 不達も fail-closed (書かない)
        raise SchemaPreflightError(
            [f"Notion API 不達のため live スキーマ照合不能 (fail-closed・書き込み中止): {e}"]
        ) from e
    live_props = live.get("properties") or {}
    violations: list[str] = []
    for name, spec in expected["properties"].items():
        lp = live_props.get(name)
        if lp is None:
            violations.append(f"必須列 '{name}' が live DB に不在")
            continue
        if lp.get("type") != spec.get("type"):
            violations.append(
                f"列 '{name}' の型不一致: expected={spec.get('type')} live={lp.get('type')}"
            )
            continue
        if spec.get("type") == "select":
            expected_opts = set(spec.get("select_options") or [])
            live_opts = {
                (o.get("name") or "")
                for o in (lp.get("select") or {}).get("options", [])
            }
            missing = sorted(expected_opts - live_opts)
            extra = sorted(live_opts - expected_opts)
            if missing or extra:
                violations.append(
                    f"列 '{name}' の select オプション不一致: "
                    f"missing={missing} extra={extra} (4ラベル完全一致が必須)"
                )
    expected_names = set(expected["properties"])
    forbidden_names = set(expected.get("forbidden_properties", []))
    for name in sorted(forbidden_names):
        if name in live_props:
            violations.append(f"禁止列 '{name}' が live DB に存在 (7列構成違反)")
    extra = sorted(set(live_props) - expected_names - forbidden_names)
    for name in extra:
        violations.append(f"余剰列 '{name}' が live DB に存在 (7列構成違反)")
    if violations:
        raise SchemaPreflightError(violations)


def ensure_schema_preflight(db_id: str, token: str) -> None:
    """preflight をプロセス内 1 回に抑える入口 (upsert/backfill 共用)。"""
    if db_id in _PREFLIGHT_OK:
        return
    preflight_schema(db_id, token)
    _PREFLIGHT_OK.add(db_id)


def find_by_hojin_bango(db_id: str, token: str, hojin_bango: str) -> str | None:
    """確定法人番号で既存行を検索し page_id を返す。"""
    res = _api("POST", f"/databases/{db_id}/query", token, {
        "filter": {"property": COL_HOJIN_BANGO, "rich_text": {"equals": hojin_bango}},
    })
    results = res.get("results") or []
    return results[0]["id"] if results else None


def _plain_rich_text(prop: dict) -> str:
    return "".join((x.get("plain_text") or x.get("text", {}).get("content", "")) for x in prop.get("rich_text", []))


def _plain_title(prop: dict) -> str:
    return "".join((x.get("plain_text") or x.get("text", {}).get("content", "")) for x in prop.get("title", []))


def _plain_select(prop: dict) -> str:
    return ((prop.get("select") or {}).get("name") or "")


def extract_existing_fields(page: dict) -> dict:
    """Notion page から7列の既存値を取り出す。既存非空セル保護に使う。

    確認用URL はプロパティ列から廃止されページ本文へ移行したため本関数は扱わない。
    正式名称は独立列を廃止し会社名(title)へ統合 (R4): company_name は title 文字列を読む。
    official_name は移行期 best-effort で旧『正式名称』列があればそれ、無ければ title へフォールバック
    する (旧行の登記名を移行 backfill で保全する・D6)。
    """
    props = page.get("properties", {})
    title_text = _plain_title(props.get(COL_COMPANY_NAME, {}))
    legacy_official = _plain_rich_text(props.get(COL_OFFICIAL_NAME, {}))
    return {
        "company_name": title_text,
        "official_name": legacy_official or title_text,
        "address": _plain_rich_text(props.get(COL_ADDRESS, {})),
        "postal_code": _plain_rich_text(props.get(COL_POSTAL, {})),
        "hojin_bango": _plain_rich_text(props.get(COL_HOJIN_BANGO, {})),
        "phone_number": _plain_rich_text(props.get(COL_PHONE, {})),
        "overall_certainty": _plain_select(props.get(COL_CERTAINTY, {})),
        "remarks_text": _plain_rich_text(props.get(COL_REMARKS, {})),
    }


def get_page(page_id: str, token: str) -> dict:
    return _api("GET", f"/pages/{page_id}", token)


def build_properties(record: dict) -> dict:
    """7 列の Notion properties を組み立てる (空欄は出さず既存非空を保護)。

    会社名(title)は official_name(登記名) 優先・通称フォールバック (R3)。正式名称は独立列を廃止。
    record は enrich_company.enrich() の出力契約に従う:
      fields / certainty_by_field / overall_certainty / remark_keys / remarks_text / source_urls。
    overall_certainty は enrich が derive_overall_certainty で導出済み、remarks_text は
    remarks-templates.md(正本)から展開済み (本関数は文言を再定義しない)。
    確認用URL(source_urls)はプロパティ列でなくページ本文へ render_blocks で出力する
    (本関数は扱わない)。
    """
    f = record.get("fields", {})
    certainty = record.get("overall_certainty", "未確定(要確認)")
    remarks = record.get("remarks_text", "")

    def rich(v: str) -> dict:
        return {"rich_text": [{"text": {"content": v}}]} if v else {"rich_text": []}

    # 会社名(title)は official_name(登記名) を優先表示し、無ければ company_name(通称) へフォールバック
    # する (R3)。正式名称は独立列を廃止し本タイトルへ統合 (R4。official_name は source_by_field で保持)。
    title_value = f.get("official_name") or f.get("company_name", "")
    props: dict = {
        COL_COMPANY_NAME: {"title": [{"text": {"content": title_value}}]},
        COL_ADDRESS: rich(f.get("address", "")),
        COL_POSTAL: rich(f.get("postal_code", "")),
        COL_HOJIN_BANGO: rich(f.get("hojin_bango", "")),
        COL_PHONE: rich(f.get("phone_number", "")),
        COL_CERTAINTY: {"select": {"name": certainty}},
        COL_REMARKS: rich(remarks),
    }
    return props


def build_fill_empty_properties(record: dict, existing: dict) -> dict:
    """既存空欄セルだけを補完する PATCH properties を返す。

    title(会社名) は既存が空のときのみ出す。確度/備考は、空欄属性がある場合の未確定理由を
    保持するため、既存が空なら出す。既存非空は触らない。確認用URL はプロパティ列から廃止
    (ページ本文へ移行) のため本関数は扱わず、本文同期は sync_confirm_url_body が担う。

    会社名 title を既存非空でも登記名へ上書きする移行モードは backfill.patch_empty_cells が
    オーケストレーション層で担う (本関数は『空欄補完』の意味に閉じ、非空上書きを混ぜない)。
    """
    props = build_properties(record)
    f = record.get("fields", {})
    mapping = {
        # 会社名(title)の補完値は official_name 優先 (build_properties と同一・R3)。
        COL_COMPANY_NAME: ("company_name", f.get("official_name") or f.get("company_name", "")),
        COL_ADDRESS: ("address", f.get("address", "")),
        COL_POSTAL: ("postal_code", f.get("postal_code", "")),
        COL_HOJIN_BANGO: ("hojin_bango", f.get("hojin_bango", "")),
        COL_PHONE: ("phone_number", f.get("phone_number", "")),
        COL_CERTAINTY: ("overall_certainty", record.get("overall_certainty", "")),
        COL_REMARKS: ("remarks_text", record.get("remarks_text", "")),
    }
    out = {}
    for col, (field, new_value) in mapping.items():
        if new_value and not existing.get(field):
            out[col] = props[col]
    return out


def _heading_plain(block: dict) -> str:
    """heading_2 ブロックのプレーンテキストを取り出す (本文セクション境界判定用)。"""
    if block.get("type") != "heading_2":
        return ""
    rt = block.get("heading_2", {}).get("rich_text", [])
    return "".join((x.get("plain_text") or x.get("text", {}).get("content", "")) for x in rt)


def _block_plain(block: dict) -> str:
    """任意 block タイプのプレーンテキストを取り出す (既存本文 bullet のパース用)。"""
    btype = block.get("type") or ""
    rt = (block.get(btype) or {}).get("rich_text", [])
    return "".join((x.get("plain_text") or x.get("text", {}).get("content", "")) for x in rt)


def _fetch_all_children(page_id: str, token: str) -> list[dict]:
    """GET children を pagination (has_more/next_cursor) 込みで全件取得する。

    100 block 超のページで確認用URLセクションが 2 ページ目以降に落ちると、旧実装
    (先頭 100 件のみ) ではセクション未検出 → 重複 append になるため全件走査する。
    """
    children: list[dict] = []
    cursor = None
    while True:
        path = f"/blocks/{page_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        res = _api("GET", path, token)
        children.extend(res.get("results", []))
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return children


def sync_confirm_url_body(page_id: str, token: str, source) -> dict:
    """ページ本文の確認用URLセクションを URL 非減少マージで冪等更新する。

    手順: GET children (pagination 全件) → heading『確認用URL（手動検証用）』とそれに続く
    本セクション (次の heading_2 まで or 末尾) の既存 bullet をパース →
    confirm_url.merge_entries で **URL 非減少マージ** (今回取得した出典のみ差し替え・既存の
    出典 URL は保持。列の既存非空セル保護と対称) → マージ済みブロックを PATCH children で
    append 成功後、旧セクション DELETE。同一入力での再実行は byte 一致 (冪等)。

    source は record の source_by_field (dict, 正本) または旧 source_urls (list, 後方互換)。
    失敗時は本体 (プロパティ書き込み) を落とさず {"confirm_url_body": "failed"} を返すが、
    呼び出し元 (upsert / backfill) が body_sync 状態として顕在化し replay 退避する (黙認しない)。
    """
    try:
        heading_text = confirm_url.load_template()["heading"]
        children = _fetch_all_children(page_id, token)
        # 確認用URL heading の位置を探し、次の heading_2 までを本セクションとして削除対象に。
        start = None
        for i, blk in enumerate(children):
            if _heading_plain(blk) == heading_text:
                start = i
                break
        existing_entries: list[dict] = []
        if start is not None:
            end = len(children)
            for j in range(start + 1, len(children)):
                if children[j].get("type") == "heading_2":
                    end = j
                    break
            # 既存セクションの bullet を出典 entry へ逆変換 (URL 非減少マージの入力)。
            for blk in children[start:end]:
                if blk.get("type") == "bulleted_list_item":
                    parsed = confirm_url.parse_bullet(_block_plain(blk))
                    if parsed:
                        existing_entries.append(parsed)
        merged = confirm_url.merge_entries(
            confirm_url.build_entries(source), existing_entries)
        blocks = confirm_url.render_blocks(merged)
        _api("PATCH", f"/blocks/{page_id}/children", token, {"children": blocks})
        if start is not None:
            for blk in children[start:end]:
                bid = blk.get("id")
                if bid:
                    _api("DELETE", f"/blocks/{bid}", token)
        return {"confirm_url_body": "synced", "replaced_existing": start is not None,
                "kept_existing_urls": sum(
                    1 for e in existing_entries
                    if e.get("url") and any(
                        m.get("attribute") == e.get("attribute") and m.get("url") == e.get("url")
                        for m in merged))}
    except Exception as e:  # noqa: BLE001 - 本文同期失敗で本体を落とさない (呼び出し元が顕在化)
        sys.stderr.write(
            f"[notion_upsert] WARN: 確認用URL本文同期に失敗 (page_id={page_id}): {e}\n"
        )
        return {"confirm_url_body": "failed", "error": str(e)}


def _safe_confirm_url_children(source) -> list[dict]:
    """create 時のページ本文 children を best-effort で組む (confirm_url は fail-closed)。

    source は source_by_field (dict, 正本) または旧 source_urls (list, 後方互換)。
    confirm_url.render_blocks は md 不在/破損で ValueError を送出する (fail-closed)。
    create はプロパティ書き込みが本体のため、本文生成失敗時は children を省いて
    ページ作成は成功させる (stderr 警告)。本文は後続の sync_confirm_url_body で冪等補完できる。
    """
    try:
        return confirm_url.render_blocks(source)
    except Exception as e:  # noqa: BLE001 - 本文生成は best-effort (縮退方針)
        sys.stderr.write(
            f"[notion_upsert] WARN: 確認用URL本文生成に失敗 (children 省略で create 続行): {e}\n"
        )
        return []


def validate_record_gate(record: dict) -> list[str]:
    """書き込みゲートの実体: deterministic_checks (a-h) の違反理由 list を返す (空 = PASS)。

    upsert 関数自体に内蔵することで、呼び出し元 (wrapper / agent 直実行 / backfill) に
    よらず「検証 PASS した行しか書き込めない」を機械強制する (prompt 指示のみの担保を排除)。
    """
    remark_phrases = set(remarks_module.load_templates().values())
    return validate_company_master.validate_row(record, 0, remark_phrases)


def upsert(record: dict) -> dict:
    # 書き込みゲート (fail-closed): 違反 record は API へ一切到達させず構造化エラーで返す。
    # 認証解決より先に検査する (違反 record の reject に token は不要・offline で決定論)。
    violations = validate_record_gate(record)
    if violations:
        return {
            "action": "rejected",
            "reason": "validate_row 違反のため書き込み拒否 (notion_upsert 内蔵の書き込みゲート)",
            "violations": violations,
        }
    cfg, token = notion_config.require_or_skip("company-master")  # fail-closed (exit 2 on miss)
    db_id = notion_config.get_db_id("company-master")
    # live スキーマ preflight (fail-closed): 不一致/API 不達は一切書き込まず構造化エラー。
    try:
        ensure_schema_preflight(db_id, token)
    except SchemaPreflightError as e:
        return {
            "action": "rejected",
            "reason": "Notion live スキーマ preflight 失敗のため書き込み中止 (fail-closed)",
            "schema_violations": e.violations,
        }
    props = build_properties(record)

    # 本文出典の正本は source_by_field ({field:{origin,url}})。無い旧形式 record は
    # source_urls (派生/旧リスト) へフォールバック (後方互換)。
    source = record.get("source_by_field") or record.get("source_urls", [])

    hojin_bango = record.get("fields", {}).get("hojin_bango", "")
    if hojin_bango and re.match(r"^\d{13}$", hojin_bango):
        page_id = find_by_hojin_bango(db_id, token, hojin_bango)
        if page_id:
            existing = extract_existing_fields(get_page(page_id, token))
            patch_props = build_fill_empty_properties(record, existing)
            # skipped(差分なし)でもページ本文は冪等同期する (本文移行後の整合)。
            # body_sync は本文同期状態の顕在化 (failed を黙認しない: 呼び出し元が検知できる)。
            body = sync_confirm_url_body(page_id, token, source)
            if not patch_props:
                return {"action": "skipped", "page_id": page_id, "key": hojin_bango,
                        "body_sync": body.get("confirm_url_body", "failed"),
                        "confirm_url_body": body}
            _api("PATCH", f"/pages/{page_id}", token, {"properties": patch_props})
            return {"action": "updated", "page_id": page_id, "key": hojin_bango,
                    "patched_properties": sorted(patch_props),
                    "body_sync": body.get("confirm_url_body", "failed"),
                    "confirm_url_body": body}
        res = _api("POST", "/pages", token, {
            "parent": {"database_id": db_id}, "properties": props,
            "children": _safe_confirm_url_children(source),
        })
        return {"action": "created", "page_id": res.get("id"), "key": hojin_bango}

    # 代替キー: 新規追記のみ (既存マージ対象外)。本文生成は hojin 経路と同じ best-effort 縮退。
    res = _api("POST", "/pages", token, {
        "parent": {"database_id": db_id}, "properties": props,
        "children": _safe_confirm_url_children(source),
    })
    return {"action": "created", "page_id": res.get("id"),
            "key": alt_key(record.get("fields", {}).get("company_name", ""),
                           record.get("fields", {}).get("address", ""))}


def main() -> int:
    ap = argparse.ArgumentParser(description="upsert company record to Notion master")
    ap.add_argument("--record", required=True, help="enrich 済みレコード JSON")
    args = ap.parse_args()
    record = json.loads(args.record)
    result = upsert(record)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 書き込みゲート reject は非0終了で呼び出し元 (wrapper/agent) にも失敗を機械伝播する。
    # schema preflight 失敗は precondition gate と同格 (exit 2 = fail-closed)。
    if result.get("schema_violations"):
        return 2
    return 1 if result.get("action") == "rejected" else 0


if __name__ == "__main__":
    sys.exit(main())

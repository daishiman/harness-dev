#!/usr/bin/env python3
# /// script
# name: notion_client
# purpose: Notion REST API (2022-06-28) の薄ラッパ。DB1/DB2 取得・本文コードブロック抽出・本文true/宛先true 抽出・送信ログDBの検索/作成/更新/プロパティ追加を標準ライブラリのみで提供する。
# inputs:
#   - api_key: str / db_id・page_id: str / properties: dict
# outputs:
#   - NotionClient メソッド群 / fetch_bodies_true() / fetch_recipients_true() / extract_body_template()
# contexts: [C, E]
# network: true   # api.notion.com への HTTPS のみ
# write-scope: notion-pages   # 送信ログDB の page create/update (db-setup/send 実行時のみ)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Notion REST クライアントと抽出ロジック (仕様書 §3/§9)。

Notion MCP は 404 (未共有) のため REST 直叩き。pagination を完了させ、未完了は呼び出し側が
fail-closed (body_fetch_failed) させる。本文テンプレートは最初の非空 code block を採用し、
複数非空 code block は multiple_body_code_blocks として暗黙連結しない。
"""
from __future__ import annotations

import json
import time
import unicodedata
import urllib.error
import urllib.request

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# レート制御 (Notion API は公称 平均3 req/sec。超過すると 429 で受理されない)。
# 送信ログDBへの reserve→mark_sending→mark_sent は1単位で複数回書き込むため、
# 件数が増えると密になり 429 を招く。予防的に最小呼び出し間隔を空けてプッシュする
# (一定間隔。過度には空けない＝公称制限を守る最小限)。バーストで弾かれた時のための
# 429 リトライ (Retry-After 尊重) は予防スロットルを補完する保険。
DEFAULT_MIN_INTERVAL_SEC = 0.34   # ≈ 2.94 req/sec。公称 3 req/sec の安全側。
DEFAULT_MAX_RETRIES = 5           # 429 を受けたときの最大再試行回数。
RETRY_BACKOFF_CAP_SEC = 10.0      # Retry-After / 指数バックオフの上限 (際限なく待たない)。

# DB1「メール本文_DB」プロパティ名 (本 plugin 専用の固定列。任意2DBへの汎用化・config上書きは未実装＝非目的)
P_SUBJECT = "件名"
P_FROM = "メールの送り主"
P_CC = "CC"
P_MSG_TARGET = "メッセージ対象"
# DB2「メール送信先_DB」プロパティ名 (厳密一致。全角括弧・スペース無。取り違えると email が静かに空になる)
P_NAME = "担当者様名"
P_COMPANY = "会社名"
P_EMAIL_PRO = "メール（プロ人材）"   # To (プロ人材)
P_EMAIL_HISHO = "メール（cc秘書）"   # CC (秘書)
P_DO_NOT_SEND = "メールを送らない"    # 送信抑制 (送信対象より最優先)
P_SEND_TARGET = "送信対象"


class NotionError(Exception):
    """Notion API エラー (4xx/5xx, pagination 未完了, parse 失敗)。"""


class NotionClient:
    def __init__(self, api_key: str, version: str = NOTION_VERSION, timeout: int = 30,
                 min_interval_sec: float = DEFAULT_MIN_INTERVAL_SEC,
                 max_retries: int = DEFAULT_MAX_RETRIES):
        self._api_key = api_key
        self._version = version
        self._timeout = timeout
        # レート制御。min_interval_sec=0 で無効化できる (テスト/単発呼び出し用)。
        self._min_interval = max(0.0, min_interval_sec)
        self._max_retries = max(0, max_retries)
        self._last_request_ts = 0.0  # time.monotonic() 基準の最終送信時刻 (初期0で初回は待たない)

    def _throttle(self) -> None:
        """前回送信から _min_interval 秒に満たなければ不足分だけ sleep し、一定間隔でプッシュする。"""
        if self._min_interval > 0:
            wait = self._min_interval - (time.monotonic() - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def _retry_after_sec(self, http_error: urllib.error.HTTPError, attempt: int) -> float:
        """429 の Retry-After ヘッダ(秒)を尊重する。無ければ指数バックオフ (上限 cap)。"""
        ra = http_error.headers.get("Retry-After") if http_error.headers else None
        if ra:
            try:
                return min(float(ra), RETRY_BACKOFF_CAP_SEC)
            except (TypeError, ValueError):
                pass
        base = self._min_interval if self._min_interval > 0 else 1.0
        return min(base * (2 ** attempt), RETRY_BACKOFF_CAP_SEC)

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{API_BASE}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._api_key}")
        req.add_header("Notion-Version", self._version)
        req.add_header("Content-Type", "application/json")
        attempt = 0
        while True:
            self._throttle()  # 各試行の直前に最小間隔を確保 (リトライ時も間隔を守る)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                # 429 (レート超過) は受理されていない=安全に再試行できる。Retry-After を尊重。
                if e.code == 429 and attempt < self._max_retries:
                    time.sleep(self._retry_after_sec(e, attempt))
                    attempt += 1
                    continue
                detail = ""
                try:
                    detail = e.read().decode("utf-8")[:300]
                except Exception:
                    pass
                raise NotionError(f"{method} {path} -> HTTP {e.code}: {detail}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                raise NotionError(f"{method} {path} 接続失敗: {e}") from None

    # ---- 低レベル ----
    def retrieve_database(self, db_id: str) -> dict:
        return self._request("GET", f"/databases/{db_id}")

    def update_database(self, db_id: str, properties: dict) -> dict:
        """DB のプロパティ schema を更新/追加する (db-setup 用)。"""
        return self._request("PATCH", f"/databases/{db_id}", {"properties": properties})

    def query_all(self, db_id: str, filter_: dict | None = None) -> list[dict]:
        """DB を pagination 完了まで全件取得する。未完了は NotionError。"""
        results: list[dict] = []
        cursor = None
        while True:
            body: dict = {"page_size": 100}
            if filter_:
                body["filter"] = filter_
            if cursor:
                body["start_cursor"] = cursor
            page = self._request("POST", f"/databases/{db_id}/query", body)
            results.extend(page.get("results", []))
            if page.get("has_more"):
                cursor = page.get("next_cursor")
                if not cursor:
                    raise NotionError("query pagination: has_more=True なのに next_cursor が無い")
            else:
                break
        return results

    def get_all_block_children(self, block_id: str) -> list[dict]:
        """子ブロックを pagination 完了まで取得する。未完了は NotionError。"""
        results: list[dict] = []
        cursor = None
        while True:
            q = f"/blocks/{block_id}/children?page_size=100"
            if cursor:
                q += f"&start_cursor={cursor}"
            page = self._request("GET", q)
            results.extend(page.get("results", []))
            if page.get("has_more"):
                cursor = page.get("next_cursor")
                if not cursor:
                    raise NotionError("blocks pagination: has_more=True なのに next_cursor が無い")
            else:
                break
        return results

    def create_page(self, parent_db_id: str, properties: dict) -> dict:
        return self._request("POST", "/pages", {"parent": {"database_id": parent_db_id}, "properties": properties})

    def update_page(self, page_id: str, properties: dict) -> dict:
        return self._request("PATCH", f"/pages/{page_id}", {"properties": properties})


# ---- プロパティ値抽出 ----
def _join_rich(items: list) -> str:
    return "".join(t.get("plain_text", "") for t in (items or []))


def prop_title(props: dict, name: str) -> str:
    return _join_rich((props.get(name) or {}).get("title", []))


def prop_rich_text(props: dict, name: str) -> str:
    return _join_rich((props.get(name) or {}).get("rich_text", []))


def prop_email(props: dict, name: str) -> str:
    return (props.get(name) or {}).get("email") or ""


def prop_checkbox(props: dict, name: str) -> bool:
    return bool((props.get(name) or {}).get("checkbox"))


def extract_body_template(client: NotionClient, page_id: str) -> tuple[str | None, str | None]:
    """ページ本文から本文テンプレートを抽出する (仕様書 §3 抽出規則)。

    Returns (body_text, reason):
        - 非空 code block がちょうど1つ: (text, None)
        - 0個: (None, "empty_body")
        - 2個以上: (None, "multiple_body_code_blocks")
        - 取得失敗: (None, "body_fetch_failed")
    """
    try:
        blocks = client.get_all_block_children(page_id)
    except NotionError:
        return None, "body_fetch_failed"
    code_texts: list[str] = []
    for b in blocks:
        if b.get("type") == "code":
            text = _join_rich(b.get("code", {}).get("rich_text", []))
            if text.strip():  # 空白のみは空本文扱い
                code_texts.append(text)
    if not code_texts:
        return None, "empty_body"
    if len(code_texts) > 1:
        return None, "multiple_body_code_blocks"
    return code_texts[0], None


def fetch_bodies_true(client: NotionClient, db1_id: str) -> tuple[list[dict], list[dict]]:
    """本文 true (メッセージ対象=true かつ 本文非空) を抽出する。

    Returns (bodies_true, skipped):
        bodies_true item: {page_id, subject, from_addr, cc_raw, body, msg_target}
        skipped item:     {page_id, subject, reason_code}
    """
    bodies: list[dict] = []
    skipped: list[dict] = []
    for page in client.query_all(db1_id):
        props = page.get("properties", {})
        pid = page.get("id", "")
        subject = prop_title(props, P_SUBJECT)
        if not prop_checkbox(props, P_MSG_TARGET):
            continue  # メッセージ対象でない行は計上しない (送信母集団外)
        body, reason = extract_body_template(client, pid)
        if reason:
            skipped.append({"page_id": pid, "subject": subject, "reason_code": reason})
            continue
        bodies.append({
            "page_id": pid,
            "subject": subject,
            "from_addr": prop_email(props, P_FROM),
            "cc_raw": prop_email(props, P_CC),
            "body": body,
            "msg_target": True,
        })
    return bodies, skipped


def _norm_email(addr: str) -> str:
    """重複判定用のメール正規化。NFKC で全角/半角を畳み、前後空白除去・小文字化する。

    プラスエイリアスやドット除去まではしない (別人の誤集約を避けるため。仕様書 §4 dedup)。
    """
    return unicodedata.normalize("NFKC", addr or "").strip().lower()


def _extract_recipient_row(page: dict) -> dict:
    """DB2 の1ページから宛先解決に必要な生フィールドを取り出す (純抽出・判定なし)。

    created_time は **ページメタ** (props ではない)。dedup の「新しいものを残す」一次キー。
    created_time が同値の場合だけ page_id 降順で決定論的に代表を選ぶ。
    """
    props = page.get("properties", {})
    return {
        "page_id": page.get("id", ""),
        "created_time": page.get("created_time", ""),
        "name": prop_title(props, P_NAME),
        "company": prop_rich_text(props, P_COMPANY),
        "pro_email": prop_email(props, P_EMAIL_PRO),
        "hisho_email": prop_email(props, P_EMAIL_HISHO),
        "send_target": prop_checkbox(props, P_SEND_TARGET),
        "do_not_send": prop_checkbox(props, P_DO_NOT_SEND),
    }


def resolve_recipients(rows: list[dict]) -> dict:
    """生の宛先行を送信可否で解決する純関数 (client 不要・単体テスト容易)。

    処理順 (順序が安全の要):
        1. 送信対象=False は母集団外 (計上しない)
        2. メールを送らない=True は抑制 (送信対象より最優先・suppressed)
        3. プロ人材メール空は skipped(invalid_to)
        4. プロ人材メール重複は新しい created_time を1件だけ残す (同値は page_id 降順。他は duplicate_dropped)
           ※2 を 4 より前に行うことで「送らない行が最新代表に選ばれ生存行を巻き込む」事故を防ぐ。
           ※会社名違いの同一プロ人材も同一人物として集約 (仕様書 §4)。秘書メールでは dedup しない。

    Returns RecipientResolution dict:
        recipients item:       {page_id, name, company, pro_email, hisho_email, created_time}
        skipped item:          {page_id, name, reason_code}
        suppressed item:       {page_id, name, pro_email}
        duplicate_dropped item:{page_id, name, pro_email, company, created_time, kept_page_id}
    """
    skipped: list[dict] = []
    suppressed: list[dict] = []
    sendable: list[dict] = []
    for r in rows:
        if not r.get("send_target"):
            continue  # 1. 送信対象でない行は母集団外
        if r.get("do_not_send"):
            suppressed.append({"page_id": r["page_id"], "name": r["name"],
                               "pro_email": r.get("pro_email", "")})
            continue  # 2. 送らない最優先
        if not (r.get("pro_email") or "").strip():
            skipped.append({"page_id": r["page_id"], "name": r["name"], "reason_code": "invalid_to"})
            continue  # 3. プロ人材メール空
        sendable.append(r)

    # 4. dedup: created_time 降順 → page_id 降順 (決定論) で並べ、各 pro_email の先頭=最新を残す
    ordered = sorted(sendable, key=lambda r: (r.get("created_time") or "", r.get("page_id") or ""),
                     reverse=True)
    seen: dict[str, dict] = {}
    recipients: list[dict] = []
    duplicate_dropped: list[dict] = []
    for r in ordered:
        key = _norm_email(r.get("pro_email"))
        if key in seen:
            duplicate_dropped.append({
                "page_id": r["page_id"], "name": r["name"], "pro_email": r.get("pro_email", ""),
                "company": r.get("company", ""), "created_time": r.get("created_time", ""),
                "kept_page_id": seen[key]["page_id"],
            })
            continue
        seen[key] = r
        recipients.append({
            "page_id": r["page_id"], "name": r["name"], "company": r.get("company", ""),
            "pro_email": r.get("pro_email", ""), "hisho_email": r.get("hisho_email", ""),
            "created_time": r.get("created_time", ""),
        })
    return {"recipients": recipients, "skipped": skipped,
            "suppressed": suppressed, "duplicate_dropped": duplicate_dropped}


def fetch_recipients_true(client: NotionClient, db2_id: str) -> dict:
    """宛先 true を抽出・解決する (送信対象✅ かつ メールを送らない☐ かつ プロ人材メール非空)。

    Returns resolve_recipients() の RecipientResolution dict。
    """
    rows = [_extract_recipient_row(page) for page in client.query_all(db2_id)]
    return resolve_recipients(rows)


def fetch_recipient_send_state(client: NotionClient, db2_id: str) -> dict:
    """送信直前の再検証用に、各 page_id の現在の送信可否フラグを返す (§送信時 suppress 再検査)。

    dry-run 承認後に Notion 側で「メールを送らない=✅」や「送信対象=☐」に変えられた宛先へ
    追い越し送信しないため、live-send が plan の宛先 page を再取得して差分を引く (subtract-only)。

    Returns {page_id: {"send_target": bool, "do_not_send": bool}}
    """
    state: dict[str, dict] = {}
    for page in client.query_all(db2_id):
        props = page.get("properties", {})
        state[page.get("id", "")] = {
            "send_target": prop_checkbox(props, P_SEND_TARGET),
            "do_not_send": prop_checkbox(props, P_DO_NOT_SEND),
        }
    return state


def values_for_recipient(recip: dict) -> dict:
    """差し込みトークン → 宛先値の対応 (仕様書 §5)。部署名は廃止 (D1)。"""
    return {
        "担当者様名": recip.get("name", ""),
        "会社名": recip.get("company", ""),
    }

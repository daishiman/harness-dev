# /// script
# name: test_notion_mock
# purpose: Notion 依存ロジック (idempotent_log.reserve 状態遷移 / mail_db_audit の DB 監査) を FakeClient で検証する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""Notion 依存ロジックを FakeClient で検証 (idempotent_log の reserve 状態遷移 / mail_db_audit の DB 監査)。"""
import pytest

from lib import idempotent_log as ilog
from lib import mail_db_audit as audit


# ============ idempotent_log.reserve ============
class FakeIdemClient:
    def __init__(self, rows):
        self.rows = rows
        self.created = []
        self.updated = []

    def query_all(self, db, filter_=None):
        return list(self.rows)

    def create_page(self, db, props):
        self.created.append((db, props))
        return {"id": "new-page"}

    def update_page(self, pid, props):
        self.updated.append((pid, props))
        return {"id": pid}


def _row(status, pid="p1"):
    return {"id": pid, "properties": {"status": {"select": {"name": status}}}}


def _fields():
    return {"idempotency_key": "c:b:r:sha256:x", "campaign_id": "c", "plan_hash": "p",
            "content_hash": "sha256:x", "body_page_id": "b", "recipient_page_id": "r",
            "from_addr": "f@x.com", "to_list": ["a@x.com"], "cc_list": [], "subject": "s"}


def test_reserve_new_creates_reserved_row():
    c = FakeIdemClient([])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "reserved" and r["status"] == ilog.RESERVED
    assert len(c.created) == 1


def test_reserve_requeries_after_create_and_blocks_parallel_duplicate():
    class RacingClient(FakeIdemClient):
        def __init__(self):
            super().__init__([])
            self.query_count = 0

        def query_all(self, db, filter_=None):
            self.query_count += 1
            if self.query_count == 1:
                return []
            return [_row(ilog.RESERVED, "p1"), _row(ilog.RESERVED, "p2")]

    c = RacingClient()
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "duplicate"
    assert r["reason_code"] == "duplicate_log_key"
    assert len(c.created) == 1


def test_reserve_sent_skips_idempotent():
    c = FakeIdemClient([_row(ilog.SENT)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip" and r["status"] == ilog.SKIPPED_IDEMPOTENT
    assert not c.created


def test_reserve_reserved_is_manual_no_autoresend():
    c = FakeIdemClient([_row(ilog.RESERVED)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip_manual"


def test_reserve_unknown_needs_reconcile_no_autoresend():
    c = FakeIdemClient([_row(ilog.UNKNOWN)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip_manual" and r["reason_code"] == "needs_reconcile"


def test_reserve_error_is_reservable_again():
    c = FakeIdemClient([_row(ilog.ERROR)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "reserved"
    assert len(c.updated) == 1  # 既存行を reserved へ更新


def test_reserve_sending_relabels_to_unknown():
    # 前回 sending 中に中断 → 送信成否不明。unknown へ遷移させ要照合報告する (F5)
    c = FakeIdemClient([_row(ilog.SENDING)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip_manual" and r["status"] == ilog.UNKNOWN
    assert r["reason_code"] == "needs_reconcile"
    assert len(c.updated) == 1
    _, props = c.updated[0]
    assert props["status"]["select"]["name"] == ilog.UNKNOWN


def test_mark_reserved_resets_to_reserved():
    # quota 安全停止で未送信確定の単位を reserved へ戻す (F4: 再開可能に)
    c = FakeIdemClient([])
    ilog.mark_reserved(c, "p1")
    pid, props = c.updated[0]
    assert pid == "p1" and props["status"]["select"]["name"] == ilog.RESERVED


def test_reserve_two_rows_fail_closed_duplicate():
    c = FakeIdemClient([_row(ilog.SENT, "p1"), _row(ilog.SENT, "p2")])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "duplicate" and r["reason_code"] == "duplicate_log_key"
    assert not c.created  # 重複時は新規作成しない


def test_mark_sent_writes_message_id():
    c = FakeIdemClient([])
    ilog.mark_sent(c, "p1", "msg-123")
    pid, props = c.updated[0]
    assert pid == "p1"
    assert props["status"]["select"]["name"] == ilog.SENT
    assert props["messageId"]["rich_text"][0]["text"]["content"] == "msg-123"


def test_mark_skipped_creates_when_absent():
    c = FakeIdemClient([])
    res = ilog.mark_skipped(c, "db", _fields(), "unresolved_token")
    assert res["action"] == "created" and len(c.created) == 1


# ============ mail_db_audit (FakeClient) ============
class FakeAuditClient:
    def __init__(self, pages_by_db, blocks_by_page, schema_by_db=None):
        self._pages = pages_by_db
        self._blocks = blocks_by_page
        self._schema = schema_by_db or {}

    def query_all(self, db, filter_=None):
        return self._pages.get(db, [])

    def get_all_block_children(self, pid):
        return self._blocks.get(pid, [])

    def retrieve_database(self, db_id):
        return {"properties": {name: {"type": "rich_text"} for name in self._schema.get(db_id, [])}}


def _body_page(pid, subject, from_addr, cc, msg_target):
    return {"id": pid, "properties": {
        "件名": {"title": [{"plain_text": subject}]},
        "メールの送り主": {"email": from_addr},
        "CC": {"email": cc},
        "メッセージ対象": {"checkbox": msg_target},
    }}


def _code(text):
    return {"type": "code", "code": {"rich_text": [{"plain_text": text}]}}


def _recip_page(pid, name, company, pro_email, send_target,
                do_not_send=False, hisho="", created="2026-06-23T09:00:00.000Z"):
    return {"id": pid, "created_time": created, "properties": {
        "担当者様名": {"title": [{"plain_text": name}]},
        "会社名": {"rich_text": [{"plain_text": company}]},
        "メール（プロ人材）": {"email": pro_email},
        "メール（cc秘書）": {"email": hisho},
        "メールを送らない": {"checkbox": do_not_send},
        "送信対象": {"checkbox": send_target},
    }}


def test_audit_body_db_flags_empty_and_unknown_token():
    pages = [
        _body_page("p1", "{{会社名}}のご案内", "f@x.com", "", True),
        _body_page("p2", "空本文", "f@x.com", "", True),
        _body_page("p3", "{{氏名}}様", "f@x.com", "", True),
        _body_page("p4", "対象外", "f@x.com", "", False),
    ]
    blocks = {"p1": [_code("こんにちは {{担当者様名}}")], "p2": [], "p3": [_code("{{氏名}} 様")]}
    rep = audit.audit_body_db(FakeAuditClient({"db1": pages}, blocks), "db1")
    codes = {i["code"] for i in rep["issues"]}
    assert "empty_body" in codes        # p2
    assert "unknown_token" in codes     # p3 ({{氏名}})
    assert "会社名" in rep["used_tokens"] and "担当者様名" in rep["used_tokens"]
    assert rep["sendable"] == 2          # p1, p3 (本文あり)


def test_audit_body_db_flags_invalid_from():
    pages = [_body_page("p1", "件名", "bad-from", "", True)]
    blocks = {"p1": [_code("本文")]}
    rep = audit.audit_body_db(FakeAuditClient({"db1": pages}, blocks), "db1")
    assert any(i["code"] == "invalid_from" for i in rep["issues"])


def test_audit_recipient_db_flags_empty_and_invalid():
    pages = [
        _recip_page("r1", "田中", "X社", "a@x.com", True),
        _recip_page("r2", "佐藤", "Y社", "", True),                 # プロ人材メール空 → skipped(invalid_to)
        _recip_page("r3", "鈴木", "Z社", "bad-addr", True),          # プロ人材アドレス不正 → invalid_to
        _recip_page("r4", "対象外", "", "x@x.com", False),           # 送信対象☐ → 母集団外
    ]
    rep = audit.audit_recipient_db(FakeAuditClient({"db2": pages}, {}), "db2")
    codes = {i["code"] for i in rep["issues"]}
    assert "invalid_to" in codes
    assert rep["sendable"] == 2  # r1, r3 (プロ人材メール非空)


def test_audit_recipient_db_detects_duplicate():
    pages = [
        _recip_page("r1", "田中", "X社", "dup@x.com", True, created="2026-06-23T09:02:00.000Z"),
        _recip_page("r2", "佐藤", "Y社", "dup@x.com", True, created="2026-06-23T09:01:00.000Z"),
    ]
    rep = audit.audit_recipient_db(FakeAuditClient({"db2": pages}, {}), "db2")
    assert any(i["code"] == "duplicate_recipient" for i in rep["issues"])
    assert rep["sendable"] == 1            # 最新の r1 のみ送信、r2 は重複除外
    assert len(rep["duplicate_dropped"]) == 1


def test_audit_recipient_db_suppressed_overrides_send_target():
    # 送信対象✅ かつ メールを送らない✅ → 抑制 (送信対象より優先)
    pages = [
        _recip_page("r1", "送る人", "X社", "ok@x.com", True),
        _recip_page("r2", "送らない人", "Y社", "no@y.com", True, do_not_send=True),
    ]
    rep = audit.audit_recipient_db(FakeAuditClient({"db2": pages}, {}), "db2")
    assert rep["sendable"] == 1
    assert len(rep["suppressed"]) == 1
    assert rep["suppressed"][0]["pro_email"] == "no@y.com"


def test_audit_body_db_flags_deprecated_token():
    # 廃止トークン {{部署名}} は unknown_token でなく deprecated_token で案内する (D1)
    pages = [_body_page("p1", "{{部署名}}のご案内", "f@x.com", "", True)]
    blocks = {"p1": [_code("本文 {{担当者様名}}")]}
    rep = audit.audit_body_db(FakeAuditClient({"db1": pages}, blocks), "db1")
    codes = {i["code"] for i in rep["issues"]}
    assert "deprecated_token" in codes


def test_audit_recipient_db_schema_flags_deprecated_property():
    # F7: DB2 schema に廃止列「部署名」が残っていれば deprecated_property を出す (要件1(d)・本文トークンとは別の schema 層)
    client = FakeAuditClient({}, {}, schema_by_db={
        "db2": ["担当者様名", "会社名", "メール（プロ人材）", "部署名"]})
    rep = audit.audit_recipient_db_schema(client, "db2")
    codes = {i["code"] for i in rep["issues"]}
    assert "deprecated_property" in codes
    assert any(i["property"] == "部署名" for i in rep["issues"])
    assert "部署名" in rep["properties"]


def test_audit_recipient_db_schema_clean_when_property_removed():
    # 部署名列が削除済みなら issue ゼロ (機械検証で「直った」ことを確認できる)
    client = FakeAuditClient({}, {}, schema_by_db={
        "db2": ["担当者様名", "会社名", "メール（プロ人材）", "メール（cc秘書）", "送信対象"]})
    rep = audit.audit_recipient_db_schema(client, "db2")
    assert rep["issues"] == []

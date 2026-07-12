# /// script
# name: test_idempotent_log
# purpose: 二重送信防止の中核 lib/idempotent_log を単独で網羅検証する。reserve の全状態分岐 (新規/既送/送信中/予約再開/重複 fail-closed) と mark_* 状態遷移・skipped 記録・journal 退避・status/reason_code SSOT を固定する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""中核 lib/idempotent_log の単独ユニットテスト。

reserve() は Notion に一意制約が無い前提で「検索→件数判定→状態遷移」により二重送信を機構的に
防ぐ唯一の関門。本ファイルはその全分岐を FakeClient で MECE に網羅し、回帰を固定する。
content_hash / 冪等キー生成自体は plan_build.py に存在し test_core_logic.py で担保済みのため、
ここではログ層 (idempotent_log) の責務 = 既送照合・予約・状態遷移・退避に限定する。
"""
import json

import pytest

from lib import idempotent_log as ilog


# ====================================================================
# FakeClient / フィクスチャ (test_notion_mock.py の作法を踏襲)
# ====================================================================
class FakeIdemClient:
    """NotionClient の query_all / create_page / update_page だけを模した最小スタブ。"""

    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.created = []   # (db, props)
        self.updated = []   # (page_id, props)

    def query_all(self, db, filter_=None):
        return list(self.rows)

    def create_page(self, db, props):
        self.created.append((db, props))
        return {"id": "new-page"}

    def update_page(self, pid, props):
        self.updated.append((pid, props))
        return {"id": pid}


def _row(status, pid="p1", reason_code=None):
    """status select を持つログ行。status=None で select 欠落行を表現する。"""
    sel = {"select": {"name": status}} if status is not None else {"select": None}
    props = {"status": sel}
    if reason_code is not None:
        props["reason_code"] = {"select": {"name": reason_code}}
    return {"id": pid, "properties": props}


def _fields():
    return {
        "idempotency_key": "b:r:sha256:x",
        "campaign_id": "camp1",
        "plan_hash": "sha256:plan",
        "content_hash": "sha256:x",
        "body_page_id": "b",
        "recipient_page_id": "r",
        "from_addr": "f@x.com",
        "to_list": ["a@x.com"],
        "cc_list": [],
        "subject": "件名",
    }


def _status_of(props):
    return props["status"]["select"]["name"]


# ====================================================================
# reserve(): 0 件 (新規) 分岐
# ====================================================================
def test_reserve_new_creates_reserved_row_and_binds_key_and_hash():
    c = FakeIdemClient([])
    r = ilog.reserve(c, "db", _fields())

    assert r["action"] == "reserved"
    assert r["status"] == ilog.RESERVED
    assert r["page_id"] == "new-page"
    # 新規 1 行のみ作成し、冪等キーを title に、content_hash を本文として記録する
    assert len(c.created) == 1
    _, props = c.created[0]
    assert props[ilog.P_KEY]["title"][0]["text"]["content"] == "b:r:sha256:x"
    assert props["content_hash"]["rich_text"][0]["text"]["content"] == "sha256:x"
    assert _status_of(props) == ilog.RESERVED
    assert "reserved_at" in props


def test_reserve_new_then_parallel_duplicate_fails_closed():
    """create 後の再検索で 2 件見えたら Gmail 到達前に fail-closed する (並行実行ガード)。"""
    class RacingClient(FakeIdemClient):
        def __init__(self):
            super().__init__([])
            self.q = 0

        def query_all(self, db, filter_=None):
            self.q += 1
            # 1 回目 (reserve 冒頭) は空、2 回目 (create 後) は重複が見える
            return [] if self.q == 1 else [_row(ilog.RESERVED, "p1"), _row(ilog.RESERVED, "p2")]

    c = RacingClient()
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "duplicate"
    assert r["reason_code"] == "duplicate_log_key"
    assert r["page_id"] is None
    assert len(c.created) == 1  # create は 1 回だが結果は破棄され送信させない


# ====================================================================
# reserve(): 1 件・自動再送しない分岐 (_NO_RESEND + SENT/SENDING)
# ====================================================================
def test_reserve_existing_sent_skips_idempotent():
    c = FakeIdemClient([_row(ilog.SENT)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip"
    assert r["status"] == ilog.SKIPPED_IDEMPOTENT
    assert not c.created and not c.updated  # 既送は一切触らない


def test_reserve_existing_sending_relabels_to_unknown():
    """sending のまま中断 = 送信成否不明 → unknown へ遷移させ要照合報告 (過少報告防止)。"""
    c = FakeIdemClient([_row(ilog.SENDING)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip_manual"
    assert r["status"] == ilog.UNKNOWN
    assert r["reason_code"] == "needs_reconcile"
    assert len(c.updated) == 1
    _, props = c.updated[0]
    assert _status_of(props) == ilog.UNKNOWN
    assert props["reason_code"]["select"]["name"] == "sending_interrupted"


def test_reserve_existing_reserved_is_manual_no_autoresend():
    c = FakeIdemClient([_row(ilog.RESERVED)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip_manual"
    assert r["status"] == ilog.RESERVED
    assert r["reason_code"] == ilog.RESERVED  # cur をそのまま reason に
    assert not c.created and not c.updated


def test_reserve_existing_quota_stopped_reserved_reactivates():
    """quota 安全停止で未送信確定の reserved だけは次回自動再開する。"""
    c = FakeIdemClient([_row(ilog.RESERVED, reason_code="quota_stopped")])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "reserved"
    assert r["status"] == ilog.RESERVED
    assert r["reason_code"] == "quota_stopped"
    assert not c.created
    assert len(c.updated) == 1
    _, props = c.updated[0]
    assert _status_of(props) == ilog.RESERVED
    assert "reserved_at" in props


def test_reserve_existing_unknown_is_manual_needs_reconcile():
    c = FakeIdemClient([_row(ilog.UNKNOWN)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip_manual"
    assert r["status"] == ilog.UNKNOWN
    assert r["reason_code"] == "needs_reconcile"  # UNKNOWN だけ特別扱い


def test_reserve_existing_skipped_idempotent_is_manual():
    c = FakeIdemClient([_row(ilog.SKIPPED_IDEMPOTENT)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip_manual"
    assert r["status"] == ilog.SKIPPED_IDEMPOTENT
    assert r["reason_code"] == ilog.SKIPPED_IDEMPOTENT


# ====================================================================
# reserve(): 1 件・再予約してよい分岐 (_RESERVABLE)
# ====================================================================
@pytest.mark.parametrize("cur", [ilog.PLANNED, ilog.ERROR, ilog.SKIPPED_VALIDATION])
def test_reserve_existing_reservable_status_reactivates(cur):
    """未送信と判断できる状態 (planned/error/skipped_validation) は reserved へ再予約。"""
    c = FakeIdemClient([_row(cur)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "reserved"
    assert r["status"] == ilog.RESERVED
    assert not c.created  # 既存行を更新するだけで新規作成しない
    assert len(c.updated) == 1
    pid, props = c.updated[0]
    assert pid == "p1"
    assert _status_of(props) == ilog.RESERVED


# ====================================================================
# reserve(): 1 件・未知 status / status 欠落 → 安全側で手動扱い
# ====================================================================
def test_reserve_existing_unknown_status_falls_back_to_manual():
    c = FakeIdemClient([_row("weird_state")])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip_manual"
    assert r["status"] == "weird_state"
    assert not c.created and not c.updated


def test_reserve_existing_missing_status_falls_back_to_unknown_label():
    c = FakeIdemClient([_row(None)])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "skip_manual"
    assert r["status"] == "unknown"  # cur or "unknown"


# ====================================================================
# reserve(): 2 件以上 → 一意制約欠如を fail-closed
# ====================================================================
def test_reserve_two_or_more_rows_fail_closed_duplicate():
    c = FakeIdemClient([_row(ilog.SENT, "p1"), _row(ilog.SENT, "p2")])
    r = ilog.reserve(c, "db", _fields())
    assert r["action"] == "duplicate"
    assert r["status"] == ilog.ERROR
    assert r["reason_code"] == "duplicate_log_key"
    assert r["matched"] == 2
    assert r["page_id"] is None
    assert not c.created and not c.updated  # 重複時は何も書き込まない


# ====================================================================
# mark_* 状態遷移
# ====================================================================
def test_mark_sending_sets_sending_and_timestamp():
    c = FakeIdemClient()
    ilog.mark_sending(c, "p1")
    pid, props = c.updated[0]
    assert pid == "p1"
    assert _status_of(props) == ilog.SENDING
    assert "sending_at" in props


def test_mark_reserved_resets_to_reserved():
    """quota 安全停止など未送信確定の単位を reserved へ戻し再開可能にする。"""
    c = FakeIdemClient()
    ilog.mark_reserved(c, "p1", reason_code="quota_stopped")
    pid, props = c.updated[0]
    assert pid == "p1"
    assert _status_of(props) == ilog.RESERVED
    assert props["reason_code"]["select"]["name"] == "quota_stopped"
    assert "reserved_at" in props


def test_mark_sent_records_message_id_and_sent_status():
    c = FakeIdemClient()
    ilog.mark_sent(c, "p1", "msg-123")
    pid, props = c.updated[0]
    assert pid == "p1"
    assert _status_of(props) == ilog.SENT
    assert props["messageId"]["rich_text"][0]["text"]["content"] == "msg-123"
    assert "sent_at" in props


def test_mark_unknown_uses_send_success_log_failed_reason():
    c = FakeIdemClient()
    ilog.mark_unknown(c, "p1", "ログ更新失敗")
    pid, props = c.updated[0]
    assert _status_of(props) == ilog.UNKNOWN
    assert props["reason_code"]["select"]["name"] == "send_success_log_failed"
    assert props["error"]["rich_text"][0]["text"]["content"] == "ログ更新失敗"


def test_mark_error_records_given_reason_code():
    c = FakeIdemClient()
    ilog.mark_error(c, "p1", "send_failed", "SMTP 拒否")
    pid, props = c.updated[0]
    assert _status_of(props) == ilog.ERROR
    assert props["reason_code"]["select"]["name"] == "send_failed"
    assert props["error"]["rich_text"][0]["text"]["content"] == "SMTP 拒否"


# ====================================================================
# mark_skipped: skipped_validation 行の記録 (新規/既存)
# ====================================================================
def test_mark_skipped_creates_when_absent():
    c = FakeIdemClient([])
    res = ilog.mark_skipped(c, "db", _fields(), "unresolved_token")
    assert res["action"] == "created"
    assert len(c.created) == 1
    _, props = c.created[0]
    assert _status_of(props) == ilog.SKIPPED_VALIDATION
    assert props["reason_code"]["select"]["name"] == "unresolved_token"


def test_mark_skipped_does_not_duplicate_existing():
    c = FakeIdemClient([_row(ilog.SKIPPED_VALIDATION, "existing")])
    res = ilog.mark_skipped(c, "db", _fields(), "invalid_to")
    assert res["action"] == "exists"
    assert res["page_id"] == "existing"
    assert not c.created  # 既存があれば二重に作らない


# ====================================================================
# journal 退避 (送信成功後ログ失敗のローカル保全)
# ====================================================================
def test_journal_path_respects_output_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTION_GMAIL_OUTPUT_DIR", str(tmp_path))
    p = ilog.journal_path("camp1")
    assert p.parent == tmp_path / "eval-log" / "notion-gmail-send"
    assert p.name == "journal-camp1.jsonl"
    assert p.parent.is_dir()  # 親ディレクトリは生成される


def test_append_journal_writes_jsonl_with_timestamp(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTION_GMAIL_OUTPUT_DIR", str(tmp_path))
    p1 = ilog.append_journal("camp1", {"event": "send_success_log_failed", "page_id": "p1"})
    p2 = ilog.append_journal("camp1", {"event": "retry", "page_id": "p1"})
    assert p1 == p2  # 同一キャンペーンは同一ファイルに追記
    lines = p1.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rec0 = json.loads(lines[0])
    assert rec0["event"] == "send_success_log_failed"
    assert "ts" in rec0  # 追記時に timestamp が付与される


# ====================================================================
# status enum / reason_code SSOT の健全性
# ====================================================================
def test_status_enum_values_are_distinct():
    statuses = [ilog.PLANNED, ilog.RESERVED, ilog.SENDING, ilog.SENT,
                ilog.SKIPPED_IDEMPOTENT, ilog.SKIPPED_VALIDATION, ilog.ERROR, ilog.UNKNOWN]
    assert len(statuses) == len(set(statuses))  # 重複なし


def test_reason_codes_cover_double_send_guard_paths():
    # reserve / mark_* が返す reason_code は REASON_CODES の部分集合でなければならない
    used_in_logic = {"duplicate_log_key", "sending_interrupted", "needs_reconcile",
                     "send_success_log_failed", "quota_stopped"}
    assert used_in_logic <= set(ilog.REASON_CODES)


def test_no_resend_and_reservable_sets_are_disjoint():
    # 自動再送しない集合と再予約可能集合は交差してはならない (分岐の排他性)
    assert ilog._NO_RESEND & ilog._RESERVABLE == set()

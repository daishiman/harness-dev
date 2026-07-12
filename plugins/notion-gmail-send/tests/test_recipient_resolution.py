# /// script
# name: test_recipient_resolution
# purpose: 宛先解決(送信対象/メールを送らない抑制/プロ人材重複排除)・CC正規化(本文CC+秘書,To除外)・送信時 suppress 再検証の改善仕様を固定する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""改善仕様 (D2-D5/C-1) のユニットテスト。

- resolve_recipients: 送信対象→送らない抑制→pro空skip→pro重複dedup(最新) の順序と正規化
- normalize_cc / assemble: 本文CC + 秘書CC の To除外・重複排除
- build_plan: To=プロ人材, CC=本文CC+秘書, 抑制/重複を plan に記録
- fetch_recipient_send_state: 送信時 suppress 再検証の状態取得
"""
import importlib.util
import json
from pathlib import Path

from lib import notion_client as nc, message_assemble as ma

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _row(pid, pro, send_target=True, do_not_send=False, hisho="", company="", name="", created="2026-06-23T09:00:00.000Z"):
    return {"page_id": pid, "created_time": created, "name": name or pid, "company": company,
            "pro_email": pro, "hisho_email": hisho, "send_target": send_target, "do_not_send": do_not_send}


# ============ resolve_recipients ============
def test_send_target_false_is_excluded_silently():
    res = nc.resolve_recipients([_row("r1", "a@x.com", send_target=False)])
    assert res["recipients"] == [] and res["skipped"] == [] and res["suppressed"] == []


def test_do_not_send_overrides_send_target():
    # 送信対象✅ かつ メールを送らない✅ → 抑制 (送信対象より強い)
    res = nc.resolve_recipients([_row("r1", "a@x.com", send_target=True, do_not_send=True)])
    assert res["recipients"] == []
    assert len(res["suppressed"]) == 1 and res["suppressed"][0]["pro_email"] == "a@x.com"


def test_empty_pro_email_is_skipped():
    res = nc.resolve_recipients([_row("r1", "  ", send_target=True)])
    assert res["recipients"] == []
    assert res["skipped"][0]["reason_code"] == "invalid_to"


def test_dedup_keeps_newest_created_time():
    rows = [
        _row("old", "dup@x.com", company="A社", created="2026-06-23T09:01:00.000Z"),
        _row("new", "dup@x.com", company="B社", created="2026-06-23T09:09:00.000Z"),
    ]
    res = nc.resolve_recipients(rows)
    assert len(res["recipients"]) == 1
    assert res["recipients"][0]["page_id"] == "new"        # 最新 created_time
    assert res["recipients"][0]["company"] == "B社"
    assert len(res["duplicate_dropped"]) == 1
    assert res["duplicate_dropped"][0]["page_id"] == "old"
    assert res["duplicate_dropped"][0]["kept_page_id"] == "new"


def test_dedup_company_differs_same_person_collapsed():
    # 会社名違いの同一プロ人材も1件に集約 (要件: 同じ人に複数送らない)
    rows = [_row("r1", "p@x.com", company="X社"), _row("r2", "p@x.com", company="Y社")]
    res = nc.resolve_recipients(rows)
    assert len(res["recipients"]) == 1


def test_suppress_before_dedup_protects_sendable_row():
    # 最新行が「送らない」、古い行が送信可 → 抑制が先なので古い行が生き残り送信される
    rows = [
        _row("new_suppressed", "p@x.com", do_not_send=True, created="2026-06-23T09:09:00.000Z"),
        _row("old_sendable", "p@x.com", do_not_send=False, created="2026-06-23T09:01:00.000Z"),
    ]
    res = nc.resolve_recipients(rows)
    assert len(res["recipients"]) == 1 and res["recipients"][0]["page_id"] == "old_sendable"
    assert len(res["suppressed"]) == 1
    assert res["duplicate_dropped"] == []     # 抑制済み行は dedup 母集団に入らない


def test_dedup_normalizes_case_and_width():
    # 大小文字・全角の表記揺れを同一視 (NFKC+lower+strip)
    rows = [
        _row("r1", "Dup@X.com ", created="2026-06-23T09:01:00.000Z"),
        _row("r2", "ｄｕｐ@x.com", created="2026-06-23T09:09:00.000Z"),  # 全角
    ]
    res = nc.resolve_recipients(rows)
    assert len(res["recipients"]) == 1
    assert len(res["duplicate_dropped"]) == 1


def test_dedup_tiebreak_is_deterministic_on_same_created_time():
    rows = [
        _row("aaa", "p@x.com", created="2026-06-23T09:00:00.000Z"),
        _row("zzz", "p@x.com", created="2026-06-23T09:00:00.000Z"),
    ]
    res = nc.resolve_recipients(rows)
    # created_time 同値 → page_id 降順で zzz が残る (決定論)
    assert res["recipients"][0]["page_id"] == "zzz"


# ============ normalize_cc / assemble ============
def test_normalize_cc_excludes_to_and_dedups():
    cc = ma.normalize_cc(["B@x.com", "b@x.com", "c@x.com", "a@x.com"], ["A@x.com"])
    # a@x.com は To と重複で除外、b の重複は1つに、順序保持
    assert cc == ["B@x.com", "c@x.com"]


def test_assemble_combines_body_and_hisho_cc():
    # build_plan が "本文CC,秘書CC" を結合して渡す想定
    asm = ma.assemble("件名", "本文", "from@x.com", "pro@x.com", "boss@x.com,hisho@x.com")
    assert asm["invalid_addrs"] == []
    assert asm["to_list"] == ["pro@x.com"]
    assert asm["cc_list"] == ["boss@x.com", "hisho@x.com"]


def test_assemble_excludes_cc_equal_to_to():
    # 秘書 == プロ人材(To) のとき CC から除外 (二重宛先防止)
    asm = ma.assemble("件名", "本文", "from@x.com", "pro@x.com", "pro@x.com")
    assert asm["cc_list"] == []


def test_cc_suppressed_by_to_reports_overlap():
    # F1: To と重複で CC から消えたアドレスを観測専用で返す (大小無視・重複は1つ)
    suppressed = ma.cc_suppressed_by_to(["PRO@x.com", "pro@x.com", "hisho@x.com"], ["pro@x.com"])
    assert suppressed == ["PRO@x.com"]  # 最初の出現のみ・順序保持


def test_cc_suppressed_by_to_empty_when_no_overlap():
    # 秘書が別アドレスなら除外なし = 警告も出ない
    assert ma.cc_suppressed_by_to(["hisho@x.com"], ["pro@x.com"]) == []


def test_cc_suppressed_does_not_change_normalize_cc_result():
    # 観測関数の追加は除外挙動 (normalize_cc) を一切変えない (Goodhart 回避の不変性)
    cc_in, to = ["pro@x.com", "hisho@x.com"], ["pro@x.com"]
    assert ma.normalize_cc(cc_in, to) == ["hisho@x.com"]
    assert ma.cc_suppressed_by_to(cc_in, to) == ["pro@x.com"]


# ============ fetch_recipient_send_state (送信時 suppress 再検証) ============
class _StateClient:
    def __init__(self, pages):
        self._pages = pages

    def query_all(self, db, filter_=None):
        return self._pages


def test_fetch_recipient_send_state_maps_flags():
    pages = [
        {"id": "r1", "properties": {"送信対象": {"checkbox": True}, "メールを送らない": {"checkbox": False}}},
        {"id": "r2", "properties": {"送信対象": {"checkbox": True}, "メールを送らない": {"checkbox": True}}},
    ]
    state = nc.fetch_recipient_send_state(_StateClient(pages), "db2")
    assert state["r1"] == {"send_target": True, "do_not_send": False}
    assert state["r2"] == {"send_target": True, "do_not_send": True}


# ============ build_plan integration: To=pro, CC=本文CC+秘書, 抑制/重複記録 ============
def _load_build_plan():
    bp_path = PLUGIN_ROOT / "skills" / "run-notion-gmail-dry-run" / "scripts" / "build-plan.py"
    spec = importlib.util.spec_from_file_location("build_plan_under_test_rr", bp_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_plan_maps_to_pro_and_cc_hisho(monkeypatch, tmp_path):
    from lib import notion_config, secrets
    bp = _load_build_plan()
    cfg = {"notion_gmail_send": {"source": {"body_db": "db1", "recipient_db": "db2"}}}
    monkeypatch.setattr(notion_config, "load_config", lambda path=None: cfg)
    monkeypatch.setattr(notion_config, "find_config_path", lambda path=None: None)
    monkeypatch.setattr(secrets, "get_notion_api_key", lambda: "key")
    monkeypatch.setattr(nc, "NotionClient", lambda key: object())
    bodies = [{"page_id": "b1", "subject": "件名", "body": "本文 {{担当者様名}}",
               "from_addr": "from@x.com", "cc_raw": "boss@x.com"}]
    resolution = {
        "recipients": [
            {"page_id": "r1", "name": "田中", "company": "X社",
             "pro_email": "pro@x.com", "hisho_email": "hisho@x.com", "created_time": "2026-06-23T09:00:00.000Z"},
        ],
        "skipped": [], "suppressed": [{"page_id": "r2", "name": "抑制太郎", "pro_email": "no@x.com"}],
        "duplicate_dropped": [{"page_id": "r3", "name": "重複次郎", "pro_email": "dup@x.com",
                               "company": "Z社", "created_time": "2026-06-23T08:00:00.000Z", "kept_page_id": "r9"}],
    }
    monkeypatch.setattr(nc, "fetch_bodies_true", lambda c, db: (bodies, []))
    monkeypatch.setattr(nc, "fetch_recipients_true", lambda c, db: resolution)

    out = tmp_path / "plan.json"
    monkeypatch.setattr("sys.argv", ["build_plan", "--out", str(out)])
    assert bp.main() == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["count"] == 1
    u = plan["units"][0]
    assert u["to_list"] == ["pro@x.com"]                       # To = プロ人材
    assert u["cc_list"] == ["boss@x.com", "hisho@x.com"]       # CC = 本文CC + 秘書
    assert "田中" in u["body"]                                  # {{担当者様名}} 置換
    # 抑制/重複は plan に記録され可視化される
    assert len(plan["suppressed"]) == 1 and len(plan["duplicate_dropped"]) == 1


def test_build_plan_records_cc_suppressed_warning_and_hash_unaffected(monkeypatch, tmp_path):
    # F1: 秘書 == プロ人材(To) の宛先で cc_suppressed_due_to_to_overlap が unit に焼かれ、
    #     かつ観測メタ追加が content_hash を変えない (決定論不変・Goodhart 回避)。
    from lib import notion_config, secrets, plan_build as pb
    bp = _load_build_plan()
    cfg = {"notion_gmail_send": {"source": {"body_db": "db1", "recipient_db": "db2"}}}
    monkeypatch.setattr(notion_config, "load_config", lambda path=None: cfg)
    monkeypatch.setattr(notion_config, "find_config_path", lambda path=None: None)
    monkeypatch.setattr(secrets, "get_notion_api_key", lambda: "key")
    monkeypatch.setattr(nc, "NotionClient", lambda key: object())
    bodies = [{"page_id": "b1", "subject": "件名", "body": "本文",
               "from_addr": "from@x.com", "cc_raw": ""}]
    resolution = {
        "recipients": [
            {"page_id": "r1", "name": "田中", "company": "X社",
             "pro_email": "pro@x.com", "hisho_email": "pro@x.com",  # 秘書 == プロ人材 To
             "created_time": "2026-06-23T09:00:00.000Z"},
        ],
        "skipped": [], "suppressed": [], "duplicate_dropped": [],
    }
    monkeypatch.setattr(nc, "fetch_bodies_true", lambda c, db: (bodies, []))
    monkeypatch.setattr(nc, "fetch_recipients_true", lambda c, db: resolution)
    out = tmp_path / "plan.json"
    monkeypatch.setattr("sys.argv", ["build_plan", "--out", str(out)])
    assert bp.main() == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    u = plan["units"][0]
    assert u["cc_list"] == []                                   # 秘書は To 重複で除外
    assert u["cc_suppressed_due_to_to_overlap"] == ["pro@x.com"]  # 除外が可視化される
    # content_hash は観測メタを含まない (固定7キー) ため、メタ有無で値が変わらない
    assert pb.content_hash(u) == u["content_hash"]
    u_without_meta = {k: v for k, v in u.items() if k != "cc_suppressed_due_to_to_overlap"}
    assert pb.content_hash(u_without_meta) == u["content_hash"]


def test_build_plan_skip_path_uses_pro_email_not_crash(monkeypatch, tmp_path):
    # 不正プロ人材アドレスで _classify_unit が skip する経路が KeyError なく pro_email を記録する
    from lib import notion_config, secrets
    bp = _load_build_plan()
    cfg = {"notion_gmail_send": {"source": {"body_db": "db1", "recipient_db": "db2"}}}
    monkeypatch.setattr(notion_config, "load_config", lambda path=None: cfg)
    monkeypatch.setattr(notion_config, "find_config_path", lambda path=None: None)
    monkeypatch.setattr(secrets, "get_notion_api_key", lambda: "key")
    monkeypatch.setattr(nc, "NotionClient", lambda key: object())
    bodies = [{"page_id": "b1", "subject": "件名", "body": "本文", "from_addr": "from@x.com", "cc_raw": ""}]
    resolution = {
        "recipients": [{"page_id": "r1", "name": "不正", "company": "X社",
                        "pro_email": "bad-addr", "hisho_email": "", "created_time": "2026-06-23T09:00:00.000Z"}],
        "skipped": [], "suppressed": [], "duplicate_dropped": [],
    }
    monkeypatch.setattr(nc, "fetch_bodies_true", lambda c, db: (bodies, []))
    monkeypatch.setattr(nc, "fetch_recipients_true", lambda c, db: resolution)
    out = tmp_path / "plan.json"
    monkeypatch.setattr("sys.argv", ["build_plan", "--out", str(out)])
    assert bp.main() == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["count"] == 0
    assert plan["skipped"][0]["reason_code"] == "invalid_to"
    assert plan["skipped"][0]["to"] == "bad-addr"     # pro_email を記録 (email_raw 参照は撤去済)

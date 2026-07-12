# /// script
# name: test_send_campaign
# purpose: live-send の決定論セルフチェック (units→plan_hash/件数の fail-closed 再計算) が plan 改変を1通も送らず止めることを検証する (F2)。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""send_campaign の決定論セルフチェックテスト (F2: guard を fork/人間に依存させない正本検証)。

precheck は Notion/Gmail クライアント生成より前に走るため、改変 plan は外部 I/O なしで abort する。
NotionClient/GmailClient を「呼ばれたら失敗」に差し替え、precheck で止まる=送信に到達しないことを保証する。"""
import importlib.util
import json
from pathlib import Path

import pytest

from lib import notion_config, notion_client, preflight, plan_build as pb

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SC_PATH = PLUGIN_ROOT / "skills" / "run-notion-gmail-send" / "scripts" / "send-campaign.py"


def _load():
    spec = importlib.util.spec_from_file_location("send_campaign_under_test", SC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _unit(**kw):
    base = {"subject": "件名", "body": "本文", "from_addr": "f@x.com",
            "to_list": ["a@x.com"], "cc_list": [], "raw": "cmF3",
            "body_page_id": "bp", "recipient_page_id": "rp", "multi_to_visible": False}
    base.update(kw)
    base["content_hash"] = pb.content_hash(base)
    return base


def _valid_plan(units):
    ph = pb.plan_hash(units)
    ordered = sorted(units, key=lambda u: (u["content_hash"], u["body_page_id"], u["recipient_page_id"]))
    return {"campaign_id": "c1", "plan_hash": ph, "count": len(units),
            "first_to": ordered[0]["to_list"][0], "units": ordered, "body_true_count": 1}


def _run(monkeypatch, tmp_path, plan, *, count, nonce=None):
    sc = _load()
    monkeypatch.setattr(notion_config, "load_config", lambda path=None: {"notion_gmail_send": {}})
    # 送信に到達したら失敗させる (precheck で止まれば呼ばれない)
    def _boom(*a, **k):
        raise AssertionError("precheck を抜けて NotionClient が生成された (送信経路に到達)")
    monkeypatch.setattr(notion_client, "NotionClient", _boom)
    out = tmp_path / "plan.json"
    out.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    argv = ["send_campaign", "--plan", str(out),
            "--approved-plan-hash", plan["plan_hash"],
            "--approved-count", str(count),
            "--approved-first-to", plan["first_to"]]
    if nonce is not None:
        argv += ["--approved-nonce", nonce]
    monkeypatch.setattr("sys.argv", argv)
    return sc.main()


def test_count_injection_is_blocked(monkeypatch, tmp_path):
    # plan.count を 1 と偽る一方 units は 3 → guard が len(units) を見て弾く (F2 の核心攻撃)
    units = [_unit(body_page_id=f"b{i}") for i in range(3)]
    plan = _valid_plan(units)
    plan["count"] = 1  # 改竄: 承認件数1で3通送らせようとする
    nonce = pb.approval_nonce(plan["plan_hash"], plan["units"])[1]
    assert _run(monkeypatch, tmp_path, plan, count=1, nonce=nonce) == 1  # 1通も送らず abort


def test_missing_nonce_is_blocked(monkeypatch, tmp_path):
    # 承認確認語を入力しない (blind approve) → 決定論セルフチェックで止まる (S-F1)
    units = [_unit()]
    plan = _valid_plan(units)
    assert _run(monkeypatch, tmp_path, plan, count=1, nonce="") == 1


class _FakeNotion:
    def __init__(self):
        self.created = []
        self.updated = []

    def query_all(self, db, filter_=None):
        return []  # 常に未存在 → reserve は新規 reserved を作る

    def create_page(self, db, props):
        self.created.append(props)
        return {"id": "log-row"}

    def update_page(self, pid, props):
        self.updated.append((pid, props))
        return {"id": pid}


class _FakeGmail:
    def __init__(self):
        self.sent = []

    def verify_sendas(self, addr):
        return True

    def send_unit(self, raw, **kw):
        self.sent.append(raw)
        return "msg-1"


def _run_full(monkeypatch, tmp_path, send_state):
    """preflight を全 pass にし実送信ループへ到達させる。send_state は送信時 suppress 再検証の状態。"""
    from lib import gmail_client, secrets
    sc = _load()
    cfg = {"databases": {"gmail-send-log": {"db_id": "log"}},
           "notion_gmail_send": {"source": {"recipient_db": "db2"},
                                 "sender": {"impersonate": "f@x.com",
                                            "sa_keychain": {"service": "s", "account": "a"}}}}
    monkeypatch.setattr(notion_config, "load_config", lambda path=None: cfg)
    monkeypatch.setattr(secrets, "get_notion_api_key", lambda: "key")
    monkeypatch.setattr(secrets, "get_google_sa_key", lambda s, a: {})
    monkeypatch.setattr(preflight, "gate_g2_dependencies", lambda cfg, bodies_true_count: [{"gate": "G2", "passed": True}])
    monkeypatch.setattr(preflight, "gate_g1_auth", lambda *a, **k: [{"gate": "G1", "passed": True}])
    monkeypatch.setattr(preflight, "gate_g3_presend", lambda **k: {"gate": "G3", "passed": True})
    fake_notion = _FakeNotion()
    fake_gmail = _FakeGmail()
    monkeypatch.setattr(notion_client, "NotionClient", lambda key: fake_notion)
    monkeypatch.setattr(gmail_client, "GmailClient", lambda sa, imp: fake_gmail)
    monkeypatch.setattr(notion_client, "fetch_recipient_send_state", lambda c, db: send_state)

    units = [_unit()]
    plan = _valid_plan(units)
    nonce = pb.approval_nonce(plan["plan_hash"], plan["units"])[1]
    out = tmp_path / "plan.json"
    out.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["send_campaign", "--plan", str(out),
                                     "--approved-plan-hash", plan["plan_hash"],
                                     "--approved-count", "1",
                                     "--approved-first-to", plan["first_to"],
                                     "--approved-nonce", nonce])
    rc = sc.main()
    return rc, fake_gmail, fake_notion


def test_send_time_suppress_blocks_now_suppressed_recipient(monkeypatch, tmp_path):
    # 承認後に「メールを送らない=✅」へ変更された宛先 (rp) は送信時再検証で送らない (C-1)
    rc, gmail, notion = _run_full(monkeypatch, tmp_path,
                                  send_state={"rp": {"send_target": True, "do_not_send": True}})
    assert rc == 0
    assert gmail.sent == []  # 1通も送信していない
    # send_suppressed の skipped_validation ログが作られる
    assert any(p.get("reason_code", {}).get("select", {}).get("name") == "send_suppressed"
               for p in notion.created)


def test_send_time_recheck_allows_active_recipient(monkeypatch, tmp_path):
    # 送信対象✅ かつ メールを送らない☐ のまま → 通常どおり送信される
    rc, gmail, notion = _run_full(monkeypatch, tmp_path,
                                  send_state={"rp": {"send_target": True, "do_not_send": False}})
    assert rc == 0
    assert len(gmail.sent) == 1  # 送信された


def test_valid_plan_passes_precheck_then_reaches_client(monkeypatch, tmp_path):
    # 正当な plan + 正しい nonce なら precheck を通過する。preflight ゲートを pass に差し替えると
    # NotionClient 生成へ到達する (=precheck で止まっていない証明)。
    units = [_unit()]
    plan = _valid_plan(units)
    nonce = pb.approval_nonce(plan["plan_hash"], plan["units"])[1]
    monkeypatch.setattr(preflight, "gate_g2_dependencies", lambda cfg, bodies_true_count: [{"gate": "G2", "passed": True}])
    monkeypatch.setattr(preflight, "gate_g1_auth", lambda *a, **k: [{"gate": "G1", "passed": True}])
    monkeypatch.setattr(preflight, "gate_g3_presend", lambda **k: {"gate": "G3", "passed": True})
    # precheck(return 1)・preflight(_abort→1) を通過し、送信初期化 (config 不足で return 2) へ到達。
    # return 2 = precheck で止まっていない証明 (return 1 でない)。
    assert _run(monkeypatch, tmp_path, plan, count=1, nonce=nonce) == 2

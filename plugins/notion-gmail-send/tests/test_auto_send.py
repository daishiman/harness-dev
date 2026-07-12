# /// script
# name: test_auto_send
# purpose: 既定の最小確認1回 (引数なし=preview exit10 → --confirm-token で送信・token束縛)、無人確認0 (--auto-approve/--yes・high で fail-closed)、preview の high 警告非全停止、C-1 fail-closed、canary opt-in と content dedup、送信時 suppress 再検証、from 検証、subtract-only 性を検証する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""非対話送信 (preview→confirm 最小確認1回 / 無人確認0) と run_full_audit のテスト。

いずれのモードも送信直前に Notion から新鮮 plan を再構築 (fresh rebuild) する。既定は preview で
要約+CONFIRM_TOKEN を出し送信せず (exit 10)、--confirm-token で plan_hash 一致時のみ送信する
(ユーザーが見た内容への束縛)。無人 --auto-approve は端末確認なしで送信し high 残存で fail-closed。
機械安全層 (送信時 suppress 再検証 / from 検証 / content dedup) は確認回数と独立に下のループで必ず効く。

NotionClient/GmailClient/fetch_* を fake に差し替え、外部 I/O なしで送信判断のみを検証する。
"""
import importlib.util
import re
from pathlib import Path

from lib import notion_client as nc, notion_config, secrets, plan_build as pb, plan_compose as pc, mail_db_audit as audit

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SC_PATH = PLUGIN_ROOT / "skills" / "run-notion-gmail-send" / "scripts" / "send-campaign.py"


def _load():
    spec = importlib.util.spec_from_file_location("send_campaign_auto_under_test", SC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============ source データビルダ ============
def _body(pid="b1", subject="件名", body="本文", from_addr="f@x.com", cc_raw=""):
    return {"page_id": pid, "subject": subject, "from_addr": from_addr,
            "cc_raw": cc_raw, "body": body, "msg_target": True}


def _recip(pid, pro, name="名前", company="会社", hisho="", created="2026-06-23T09:00:00.000Z"):
    return {"page_id": pid, "name": name, "company": company,
            "pro_email": pro, "hisho_email": hisho, "created_time": created}


def _resolution(recips, skipped=None, suppressed=None, duplicate_dropped=None):
    return {"recipients": recips, "skipped": skipped or [],
            "suppressed": suppressed or [], "duplicate_dropped": duplicate_dropped or []}


# ============ fake Notion / Gmail (送信ログDB の冪等状態を持つ) ============
def _key_of(props: dict):
    title = (props.get("冪等キー") or {}).get("title") or []
    return title[0]["text"]["content"] if title else None


class FakeNotion:
    """送信ログDB を冪等キー単位で保持する fake (reserve→sent の状態を跨実行で保つ)。"""

    def __init__(self, recip_schema_props=None):
        self.pages: dict[str, dict] = {}
        self.created: list[dict] = []
        self._n = 0
        # 廃止プロパティを含まない素の DB2 schema (audit_recipient_db_schema 用)
        self._schema = recip_schema_props or {"担当者様名": {}, "会社名": {}, "メール（プロ人材）": {}}

    def retrieve_database(self, db_id):
        return {"properties": self._schema}

    def query_all(self, db_id, filter_=None):
        if filter_ and filter_.get("property") == "冪等キー":
            key = filter_["title"]["equals"]
            return [{"id": pid, "properties": p} for pid, p in self.pages.items() if _key_of(p) == key]
        return []

    def create_page(self, db_id, props):
        self._n += 1
        pid = f"log-{self._n}"
        self.pages[pid] = dict(props)
        self.created.append(props)
        return {"id": pid}

    def update_page(self, page_id, props):
        self.pages.setdefault(page_id, {}).update(props)
        return {"id": page_id}


class FakeGmail:
    def __init__(self, verify_sendas=True):
        self.sent: list[str] = []
        self._verify = verify_sendas

    def verify_sendas(self, addr):
        return self._verify

    def send_unit(self, raw, **kw):
        self.sent.append(raw)
        return "msg-1"


def _reasons(fake: FakeNotion) -> list[str]:
    """ログ行 (新規 create + 既存 update) に焼かれた reason_code select 名を集める。"""
    out = []
    for p in fake.pages.values():
        name = ((p.get("reason_code") or {}).get("select") or {}).get("name")
        if name:
            out.append(name)
    return out


def _parse_token(stdout: str) -> str | None:
    """preview 出力 (exit 10) から CONFIRM_TOKEN(=plan_hash) を取り出す。"""
    m = re.search(r"CONFIRM_TOKEN:\s*(\S+)", stdout)
    return m.group(1) if m else None


def _run_auto(monkeypatch, tmp_path, *, bodies, recips, body_skipped=None, send_state=None,
              verify_sendas=True, canary=None, allow_resend=False, plan_transform=None, fake_notion=None,
              argv_prefix=None, db1_arg=None, db2_arg=None, capsys=None, cfg_override=None):
    """送信フローを外部 I/O なしで通す。(rc, gmail, notion) を返す。

    argv_prefix の既定は ["--auto-approve"] (無人確認0=true_zero パスを送信させる)。argv_prefix=[] は
    既定の preview (最小確認1回・exit 10)、["--confirm-token", h] は confirm-send 段を通す。
    capsys を渡すと fake.stdout に send-campaign.py の stdout を載せる (CONFIRM_TOKEN 取得用)。
    """
    from lib import gmail_client, preflight
    sc = _load()
    body_skipped = body_skipped or []
    resolution = _resolution(recips)
    if send_state is None:  # 既定は全宛先 sendable (送信時 suppress 再検証を通過させる)
        send_state = {r["page_id"]: {"send_target": True, "do_not_send": False} for r in recips}
    cfg = cfg_override or {
        "databases": {"gmail-send-log": {"db_id": "log"}},
        "notion_gmail_send": {
            "source": {"body_db": "db1", "recipient_db": "db2"},
            "sender": {"impersonate": "f@x.com", "sa_keychain": {"service": "s", "account": "a"}},
        },
    }
    monkeypatch.setattr(notion_config, "load_config", lambda path=None: cfg)
    monkeypatch.setattr(notion_config, "find_config_path", lambda path=None: tmp_path / ".notion-config.json")
    monkeypatch.setattr(secrets, "get_notion_api_key", lambda: "key")
    monkeypatch.setattr(secrets, "get_google_sa_key", lambda s, a: {})
    monkeypatch.setattr(preflight, "gate_g2_dependencies", lambda cfg, bodies_true_count: [{"gate": "G2", "passed": True}])
    monkeypatch.setattr(preflight, "gate_g1_auth", lambda *a, **k: [{"gate": "G1", "passed": True}])
    monkeypatch.setattr(preflight, "gate_g3_presend", lambda **k: {"gate": "G3", "passed": True})
    monkeypatch.setattr(nc, "fetch_bodies_true", lambda c, db: (bodies, body_skipped))
    monkeypatch.setattr(nc, "fetch_recipients_true", lambda c, db: resolution)
    state_calls = []

    def _fetch_state(c, db):
        state_calls.append(db)
        return send_state

    monkeypatch.setattr(nc, "fetch_recipient_send_state", _fetch_state)
    fake = fake_notion or FakeNotion()
    gmail = FakeGmail(verify_sendas=verify_sendas)
    monkeypatch.setattr(nc, "NotionClient", lambda key: fake)
    monkeypatch.setattr(gmail_client, "GmailClient", lambda sa, imp: gmail)
    if plan_transform is not None:
        # 新鮮 plan を改竄して per-unit Class A ガードへ流す (compose は本物・fetch mock 経由)。
        real_compose = pc.compose_plan

        def _compose(client, db1, db2, *, canary=None):
            return plan_transform(real_compose(client, db1, db2, canary=canary))

        monkeypatch.setattr(pc, "compose_plan", _compose)
    argv = ["send_campaign"] + (argv_prefix if argv_prefix is not None else ["--auto-approve"])
    if canary is not None:
        argv += ["--canary", str(canary)]
    if db1_arg is not None:
        argv += ["--db1", db1_arg]
    if db2_arg is not None:
        argv += ["--db2", db2_arg]
    if allow_resend:
        argv += ["--allow-resend"]
    monkeypatch.setattr("sys.argv", argv)
    fake.state_calls = state_calls
    rc = sc.main()
    if capsys is not None:
        fake.stdout = capsys.readouterr().out
    return rc, gmail, fake


# ================= run_full_audit: high severity の集約 =================
class _AuditClient:
    def retrieve_database(self, db_id):
        return {"properties": {"担当者様名": {}, "会社名": {}, "メール（プロ人材）": {}}}


def _patch_audit_fetch(monkeypatch, bodies, body_skipped, recips, recip_skipped=None):
    monkeypatch.setattr(nc, "fetch_bodies_true", lambda c, db: (bodies, body_skipped))
    monkeypatch.setattr(nc, "fetch_recipients_true", lambda c, db: _resolution(recips, skipped=recip_skipped or []))


def test_run_full_audit_clean_has_no_high(monkeypatch):
    _patch_audit_fetch(monkeypatch, [_body()], [], [_recip("r1", "a@x.com")])
    res = audit.run_full_audit(_AuditClient(), "db1", "db2")
    assert res["high"] == []


def test_run_full_audit_flags_empty_body(monkeypatch):
    _patch_audit_fetch(monkeypatch, [_body()],
                       [{"page_id": "b9", "subject": "空件名", "reason_code": "empty_body"}],
                       [_recip("r1", "a@x.com")])
    res = audit.run_full_audit(_AuditClient(), "db1", "db2")
    assert any(i["code"] == "empty_body" for i in res["high"])


def test_run_full_audit_flags_invalid_from(monkeypatch):
    _patch_audit_fetch(monkeypatch, [_body(from_addr="")], [], [_recip("r1", "a@x.com")])
    res = audit.run_full_audit(_AuditClient(), "db1", "db2")
    assert any(i["code"] == "invalid_from" for i in res["high"])


def test_run_full_audit_flags_unknown_token(monkeypatch):
    _patch_audit_fetch(monkeypatch, [_body(subject="件名 {{謎}}")], [], [_recip("r1", "a@x.com")])
    res = audit.run_full_audit(_AuditClient(), "db1", "db2")
    assert any(i["code"] == "unknown_token" for i in res["high"])


def test_run_full_audit_flags_recipient_invalid_to(monkeypatch):
    _patch_audit_fetch(monkeypatch, [_body()], [], [],
                       recip_skipped=[{"page_id": "r9", "name": "空", "reason_code": "invalid_to"}])
    res = audit.run_full_audit(_AuditClient(), "db1", "db2")
    assert any(i["code"] == "invalid_to" for i in res["high"])


# ================= auto happy: 確認0で全 ✅ 宛先へ送信 =================
def test_auto_approve_sends_all_without_approval_string(monkeypatch, tmp_path):
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com")]
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips)
    assert rc == 0
    assert len(gmail.sent) == 2                  # 新鮮 plan の全 unit を送信 (APPROVE文字列/nonce なし)
    assert "send_suppressed" not in _reasons(fake) and "content_hash_mismatch" not in _reasons(fake)


def test_no_arg_defaults_to_preview_not_send(monkeypatch, tmp_path, capsys):
    # 既定は最小確認1回。引数なしは preview (exit 10)・1通も送らず CONFIRM_TOKEN を出す。
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=[_body()],
                                recips=[_recip("r1", "a@x.com")], argv_prefix=[], capsys=capsys)
    assert rc == 10
    assert gmail.sent == []                       # preview は送信しない
    assert fake.created == []                      # ログ行も作らない
    assert _parse_token(fake.stdout)               # CONFIRM_TOKEN を提示


def test_confirm_token_matching_sends(monkeypatch, tmp_path, capsys):
    # preview の CONFIRM_TOKEN を付けて再実行 → 新鮮 plan の plan_hash と一致し全 unit を送信。
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com")]
    rc0, g0, f0 = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips, argv_prefix=[], capsys=capsys)
    assert rc0 == 10 and g0.sent == []
    token = _parse_token(f0.stdout)
    assert token
    rc1, g1, f1 = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips,
                            argv_prefix=["--confirm-token", token])
    assert rc1 == 0 and len(g1.sent) == 2


def test_confirm_token_mismatch_blocks(monkeypatch, tmp_path):
    # token が現在の新鮮 plan の plan_hash と不一致 (preview 後に内容変化) → exit 11・1通も送らない。
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=[_body()], recips=[_recip("r1", "a@x.com")],
                                argv_prefix=["--confirm-token", "stale-token-not-matching"])
    assert rc == 11
    assert gmail.sent == [] and fake.created == []


def test_auto_approve_and_confirm_token_conflict(monkeypatch, tmp_path):
    # --auto-approve(無人確認0) と --confirm-token(最小確認1回) はモード排他 → exit 2・送信しない。
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=[_body()], recips=[_recip("r1", "a@x.com")],
                                argv_prefix=["--auto-approve", "--confirm-token", "x"])
    assert rc == 2 and gmail.sent == []


def test_preview_with_canary_echoes_rerun_flags(monkeypatch, tmp_path, capsys):
    # canary 付き preview は再実行コマンドに同じ --canary を自己記述する (付け忘れ token 不一致の回避)。
    rc, gmail, fake = _run_auto(
        monkeypatch, tmp_path, bodies=[_body()],
        recips=[_recip("r1", "a@x.com"), _recip("r2", "b@y.com"), _recip("r3", "c@z.com")],
        argv_prefix=[], canary=2, capsys=capsys)
    assert rc == 10 and gmail.sent == []
    assert "--confirm-token" in fake.stdout and "--canary 2" in fake.stdout


def test_preview_does_not_block_on_high_warns_instead(monkeypatch, tmp_path, capsys):
    # 既定 preview は high(空本文)で全停止せず、警告を要約に出して人間判断に委ねる (gate 非対称の人間側)。
    # 対になる無人 --auto-approve は同条件で fail-closed 全停止 (test_auto_source_audit_gate_blocks_on_high)。
    rc, gmail, fake = _run_auto(
        monkeypatch, tmp_path, bodies=[_body()], recips=[_recip("r1", "a@x.com")],
        body_skipped=[{"page_id": "b9", "subject": "空件名", "reason_code": "empty_body"}],
        argv_prefix=[], capsys=capsys)
    assert rc == 10                                # preview (全停止しない)
    assert gmail.sent == []                         # preview ゆえ未送信
    assert "empty_body" in fake.stdout              # 警告として要約に列挙される


def test_c1_fail_closed_when_recipient_db_unresolved(monkeypatch, tmp_path):
    # 非対話で recipient_db が解決不能 (plan.source 欠落 & cfg fallback 無し) → C-1 不能で fail-closed (exit 2)。
    cfg_no_source = {
        "databases": {"gmail-send-log": {"db_id": "log"}},
        "notion_gmail_send": {"sender": {"impersonate": "f@x.com", "sa_keychain": {"service": "s", "account": "a"}}},
    }

    def drop_source(plan):
        plan.pop("source", None)
        return plan

    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=[_body()], recips=[_recip("r1", "a@x.com")],
                                argv_prefix=["--auto-approve"], db1_arg="db1", db2_arg="db2",
                                plan_transform=drop_source, cfg_override=cfg_no_source)
    assert rc == 2
    assert gmail.sent == []


def test_auto_mode_does_not_require_nonce(monkeypatch, tmp_path):
    # auto は approved_nonce 未指定でも nonce_mismatch を起こさない (nonce 照合無効化 enforce_nonce=False)
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=[_body()], recips=[_recip("r1", "a@x.com")])
    assert rc == 0 and len(gmail.sent) == 1
    assert "nonce_mismatch" not in _reasons(fake)


# ================= Class A は auto でも常時オン =================
def test_auto_content_hash_tamper_blocks_that_unit(monkeypatch, tmp_path):
    # plan 内 content の改竄 (body 書換・content_hash 据置) → 当該 unit のみ content_hash_mismatch で非送信。
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com")]

    def tamper(plan):
        plan["units"][0]["body"] = plan["units"][0]["body"] + "【改竄】"  # content_hash は更新しない
        return plan

    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips, plan_transform=tamper)
    assert rc == 0
    assert len(gmail.sent) == 1                              # 改竄ユニットは送らず残り1件のみ送信
    assert "content_hash_mismatch" in _reasons(fake)


def test_auto_send_time_suppress_blocks_now_suppressed(monkeypatch, tmp_path):
    # build 後に「メールを送らない=✅」へ変えられた宛先は送信時 suppress 再検証で送らない (C-1)。
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com")]
    send_state = {"r1": {"send_target": True, "do_not_send": True},   # 承認後に抑制へ
                  "r2": {"send_target": True, "do_not_send": False}}
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips, send_state=send_state)
    assert rc == 0
    assert len(gmail.sent) == 1                               # 抑制された1件は送らない
    assert "send_suppressed" in _reasons(fake)


def test_auto_send_target_off_blocks_recipient(monkeypatch, tmp_path):
    # 送信対象=☐ に変えられた宛先も送信時 suppress 再検証で送らない。
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com")]
    send_state = {"r1": {"send_target": False, "do_not_send": False}}
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips, send_state=send_state)
    assert rc == 0 and gmail.sent == []
    assert "send_suppressed" in _reasons(fake)


def test_auto_send_time_recheck_uses_plan_source_db2_override(monkeypatch, tmp_path):
    # --db2 override で plan を作った場合、送信時 suppress 再検証も config ではなく plan.source.recipient_db を見る。
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=[_body()], recips=[_recip("r1", "a@x.com")],
                                db2_arg="override-db2")
    assert rc == 0 and len(gmail.sent) == 1
    assert fake.state_calls == ["override-db2"]


def test_auto_from_unverified_is_guard_blocked(monkeypatch, tmp_path):
    # From が sendAs 未検証なら guard が fail-closed し送信に到達しない (確認回数と独立)。
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=[_body()],
                                recips=[_recip("r1", "a@x.com")], verify_sendas=False)
    assert rc == 0 and gmail.sent == []
    assert "from_alias_unverified" in _reasons(fake)


# ================= source-audit ゲート: high 残存で fail-closed =================
def test_auto_source_audit_gate_blocks_on_high(monkeypatch, tmp_path):
    # 空本文 (high) が残ると _auto_source_audit_gate が 1 を返し1通も送らない (人間の目視がない入口防御)。
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com")]
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips,
                                body_skipped=[{"page_id": "b9", "subject": "空件名", "reason_code": "empty_body"}])
    assert rc == 1
    assert gmail.sent == []                  # 送信に到達していない
    assert fake.created == []                 # ログ行も1行も作っていない (compose 前に停止)


# ================= canary opt-in + 跨実行 dedup =================
def test_auto_canary_then_full_run_dedups_already_sent(monkeypatch, tmp_path):
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com"), _recip("r3", "c@z.com")]
    # 1回目: canary=1 → 先頭1件のみ送信
    rc1, gmail1, fake = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips, canary=1)
    assert rc1 == 0 and len(gmail1.sent) == 1
    # 2回目: canary なし・同じログDB状態 → 既送1件を content dedup で skip、残り2件を送信
    rc2, gmail2, _ = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips, fake_notion=fake)
    assert rc2 == 0 and len(gmail2.sent) == 2     # 二重送信せず残りのみ
    # 全 3 宛先がちょうど1回ずつ送られた (1回目1件 + 2回目2件)
    assert len(gmail1.sent) + len(gmail2.sent) == 3


# ================= subtract-only: 送信は新鮮 plan を超えない =================
def test_auto_send_count_never_exceeds_fresh_plan(monkeypatch, tmp_path):
    # 宛先2件で plan は2、うち1件を送信時 suppress → 送信1 (新鮮 plan を超えず・減る方向のみ)。
    bodies = [_body()]
    recips = [_recip("r1", "a@x.com"), _recip("r2", "b@y.com")]
    send_state = {"r1": {"send_target": True, "do_not_send": False},
                  "r2": {"send_target": True, "do_not_send": True}}
    rc, gmail, fake = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=recips, send_state=send_state)
    assert rc == 0
    assert len(gmail.sent) == 1                  # 2 (plan) を超えず、suppress 分だけ減る
    assert len(gmail.sent) <= 2


def test_auto_fewer_recipients_means_fewer_sends(monkeypatch, tmp_path):
    # Notion 宛先が減れば新鮮 plan も減り送信も減る (compose が現在の Notion を反映する subtract 性)。
    bodies = [_body()]
    rc1, gmail1, _ = _run_auto(monkeypatch, tmp_path, bodies=bodies,
                               recips=[_recip("r1", "a@x.com"), _recip("r2", "b@y.com")])
    rc2, gmail2, _ = _run_auto(monkeypatch, tmp_path, bodies=bodies, recips=[_recip("r1", "a@x.com")])
    assert rc1 == 0 and rc2 == 0
    assert len(gmail1.sent) == 2 and len(gmail2.sent) == 1

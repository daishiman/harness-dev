# /// script
# name: test_core_logic
# purpose: コア純粋ロジック (render_substitute/message_assemble/plan_build/send_guard/cross_audit) のユニットテスト。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""コア純粋ロジックのユニットテスト (render_substitute / message_assemble / plan_build / send_guard / mail_db_audit.cross_audit)。"""
import pytest

from lib import render_substitute as rs, message_assemble as ma, plan_build as pb, send_guard as sg
from lib import mail_db_audit as audit


# ---- render_substitute ----
def test_substitute_replaces_known_tokens():
    out, un = rs.substitute("{{会社名}}様 {{担当者様名}}", {"会社名": "X社", "担当者様名": "田中"})
    assert out == "X社様 田中"
    assert un == []


def test_substitute_empty_value_stays_unresolved():
    out, un = rs.substitute("{{会社名}} {{部署名}}", {"会社名": "X社", "部署名": ""})
    assert "{{部署名}}" in out
    assert un == ["部署名"]


def test_find_unresolved_tokens_dedup_order():
    assert rs.find_unresolved_tokens("{{a}}{{b}}{{a}}") == ["a", "b"]


def test_unsafe_value_keys_detects_crlf_and_control():
    assert rs.unsafe_value_keys({"ok": "正常", "lf": "a\nb", "ctl": "x\x01y", "cr": "a\rb"}) == ["lf", "ctl", "cr"]


# ---- message_assemble ----
def test_assemble_valid_single_to():
    r = ma.assemble("件名", "本文", "from@x.com", "to@y.com", "")
    assert r["raw"] and not r["invalid_addrs"] and not r["multi_to_visible"]


def test_assemble_multi_to_sets_visible_flag():
    r = ma.assemble("s", "b", "from@x.com", "a@x.com, b@y.com", "")
    assert r["multi_to_visible"] and r["to_list"] == ["a@x.com", "b@y.com"]


@pytest.mark.parametrize("to,cc,bad_prefix", [
    ("notanemail", "", "to"),
    ("a@x.com", "badcc", "cc"),
    ("", "", "to"),
])
def test_assemble_invalid_addr_returns_none_raw(to, cc, bad_prefix):
    r = ma.assemble("s", "b", "from@x.com", to, cc)
    assert r["raw"] is None
    assert any(x.startswith(bad_prefix) for x in r["invalid_addrs"])


def test_assemble_invalid_from():
    r = ma.assemble("s", "b", "bad-from", "to@x.com", "")
    assert r["raw"] is None and any(x.startswith("from") for x in r["invalid_addrs"])


# ---- plan_build ----
def _unit(**kw):
    base = {"subject": "件名", "body": "本文", "from_addr": "f@x.com",
            "to_list": ["a@x.com"], "cc_list": [], "body_page_id": "bp", "recipient_page_id": "rp"}
    base.update(kw)
    return base


def test_content_hash_is_to_order_independent():
    a = _unit(to_list=["a@x.com", "b@x.com"])
    b = _unit(to_list=["b@x.com", "a@x.com"])
    assert pb.content_hash(a) == pb.content_hash(b)


def test_content_hash_changes_with_body():
    assert pb.content_hash(_unit(body="A")) != pb.content_hash(_unit(body="B"))


def test_plan_hash_stable_regardless_of_input_order():
    u1 = _unit(body_page_id="b1"); u1["content_hash"] = pb.content_hash(u1)
    u2 = _unit(body_page_id="b2"); u2["content_hash"] = pb.content_hash(u2)
    assert pb.plan_hash([u1, u2]) == pb.plan_hash([u2, u1])


def test_dedup_key_is_campaign_independent():
    # campaign_id を含めない → 別実行でも同一内容なら同一キー (cross-run 二重送信を機構で防ぐ)
    assert pb.dedup_key("bp", "rp", "sha256:x") == "bp:rp:sha256:x"


def test_dedup_key_resend_variant_differs():
    base = pb.dedup_key("bp", "rp", "sha256:x")
    resend = pb.dedup_key("bp", "rp", "sha256:x", resend_campaign_id="camp1")
    assert resend == "bp:rp:sha256:x:camp1" and resend != base


def test_approval_nonce_deterministic_and_bound_to_content():
    u1 = _unit(body_page_id="b1"); u1["content_hash"] = pb.content_hash(u1)
    u2 = _unit(body_page_id="b2"); u2["content_hash"] = pb.content_hash(u2)
    units = [u1, u2]
    ph = pb.plan_hash(units)
    idx, code = pb.approval_nonce(ph, units)
    assert 0 <= idx < 2 and len(code) == 6
    # 決定論: 同一 plan_hash・同一 units なら同一 nonce
    assert pb.approval_nonce(ph, units) == (idx, code)
    # 空 units は (None, "")
    assert pb.approval_nonce(ph, []) == (None, "")


def test_finalize_plan_sets_count_and_first_to():
    u = _unit(); u["content_hash"] = pb.content_hash(u)
    plan = pb.finalize_plan("camp", [u])
    assert plan["count"] == 1 and plan["first_to"] == "a@x.com" and plan["plan_hash"].startswith("sha256:")


def test_generate_campaign_id_shape():
    import datetime
    cid = pb.generate_campaign_id(datetime.datetime(2026, 6, 24, 9, 8, 7))
    assert cid.startswith("20260624-090807-") and len(cid.split("-")[-1]) == 8


# ---- send_guard ----
def _guard_kwargs(**over):
    base = dict(approved_plan_hash="x", plan_hash="x", approved_count=1, actual_count=1,
                approved_first_to="a", actual_first_to="a", reserved_log_id="r",
                unresolved_tokens=[], from_verified=True)
    base.update(over)
    return base


def test_send_guard_passes_when_all_match():
    sg.check(**_guard_kwargs())  # 例外が出なければ OK


@pytest.mark.parametrize("over,code", [
    (dict(approved_plan_hash=""), "no_approval"),
    (dict(plan_hash="y"), "plan_hash_mismatch"),
    (dict(actual_count=2), "count_mismatch"),
    (dict(actual_first_to="b"), "first_to_mismatch"),
    (dict(reserved_log_id=None), "no_reserved_log"),
    (dict(unresolved_tokens=["会社名"]), "unresolved_token"),
    (dict(from_verified=False), "from_alias_unverified"),
    (dict(actual_nonce="ab12cd", approved_nonce="wrong"), "nonce_mismatch"),
    (dict(actual_nonce="ab12cd"), "nonce_mismatch"),  # approved_nonce 既定"" → 未確認とみなし block
])
def test_send_guard_blocks_each_violation(over, code):
    with pytest.raises(sg.SendGuardError) as e:
        sg.check(**_guard_kwargs(**over))
    assert e.value.code == code


def test_send_guard_passes_with_matching_nonce():
    sg.check(**_guard_kwargs(actual_nonce="ab12cd", approved_nonce="ab12cd"))


# ---- mail_db_audit.cross_audit ----
def test_cross_audit_flags_empty_substitution():
    recips = [
        {"page_id": "r1", "name": "田中", "company": "", "pro_email": "a@x.com"},
        {"page_id": "r2", "name": "佐藤", "company": "Y社", "pro_email": "b@y.com"},
    ]
    # name/company は notion_client.values_for_recipient 経由で参照される (部署名は廃止 D1)
    issues = audit.cross_audit(["会社名"], recips)
    # r1 は会社名が空 → unresolved リスク。r2 は埋まる → issue なし
    assert len(issues) == 1 and issues[0]["page_id"] == "r1"
    assert issues[0]["code"] == "empty_substitution"


def test_cross_audit_ignores_unknown_tokens():
    recips = [{"page_id": "r1", "name": "田中", "company": "", "pro_email": "a@x.com"}]
    # 既知外トークンのみなら cross では扱わない (audit_body_db 側で unknown_token として検出)
    assert audit.cross_audit(["氏名"], recips) == []

# /// script
# name: test_preflight
# purpose: preflight ゲート (G1 複数From sendAs検証 / G2 本文true母数 / G3 キャンペーン整合) を FakeGmail/monkeypatch で検証する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""preflight ゲートのユニットテスト (G1 複数From / G2 本文true母数 / G3 整合)。

実API (Gmail) は FakeGmail で差し替え、決定論で検証する。"""
import pytest

from lib import preflight, gmail_client, secrets, notion_config


# ---- 共通: 認証 probe を成功側へ固定する fixture ----
class FakeGmail:
    """verify_sendas が、許可リストに含まれる From だけ True を返す擬似クライアント。"""
    allowed: set = set()

    def __init__(self, sa_key, impersonate):
        self.impersonate = impersonate

    def verify_sendas(self, addr):
        return addr in FakeGmail.allowed


@pytest.fixture
def cfg():
    return {"notion_gmail_send": {"sender": {
        "impersonate": "user@example.invalid",
        "sa_keychain": {"service": "gmail-sa.<keychain-prefix>", "account": "<keychain-prefix>"},
    }}, "databases": {"gmail-send-log": {"db_id": "logdb12345678"}}}


@pytest.fixture(autouse=True)
def _patch_auth(monkeypatch):
    monkeypatch.setattr(secrets, "probe_notion_api_key", lambda: True)
    monkeypatch.setattr(secrets, "probe_google_sa_key", lambda s, a: True)
    monkeypatch.setattr(secrets, "get_google_sa_key", lambda s, a: "fake-sa-json")
    monkeypatch.setattr(gmail_client, "GmailClient", FakeGmail)
    FakeGmail.allowed = set()


# ---- G1: 複数 From sendAs 検証 (finding A) ----
def test_g1_verifies_all_distinct_from_not_just_first(cfg):
    FakeGmail.allowed = {"a@example.invalid"}  # b は未検証
    res = preflight.gate_g1_auth(cfg, "a@example.invalid", probe_api=True,
                                 verify_from_addrs=["a@example.invalid", "b@example.invalid", "a@example.invalid"])
    sendas = [r for r in res if r["gate"] == "G1.sendas"]
    assert len(sendas) == 2                    # distinct 化 (a,b)。先頭だけでなく両方を検査
    passed_details = {r["detail"] for r in sendas if r["passed"]}
    failed_details = [r["detail"] for r in sendas if not r["passed"]]
    assert "From=a@example.invalid" in passed_details
    assert any("b@example.invalid" in d for d in failed_details)  # 2件目の未検証 From を preflight で先出し
    assert not preflight.all_passed(res)


def test_g1_default_verifies_single_from_when_list_omitted(cfg):
    FakeGmail.allowed = {"a@example.invalid"}
    res = preflight.gate_g1_auth(cfg, "a@example.invalid", probe_api=True)
    sendas = [r for r in res if r["gate"] == "G1.sendas"]
    assert len(sendas) == 1 and sendas[0]["passed"]


def test_g1_without_probe_skips_sendas(cfg):
    res = preflight.gate_g1_auth(cfg, "a@example.invalid", probe_api=False)
    assert not any(r["gate"] == "G1.sendas" for r in res)
    assert preflight.all_passed(res)  # 鍵存在のみで pass


# ---- G2: 本文 true 母数 (finding E) ----
def test_g2_body_uses_true_count_not_unit_count(cfg):
    # 本文ありだが宛先0で units=0 のケースを母数=本文true行数で評価すれば no_body にならない
    res = preflight.gate_g2_dependencies(cfg, bodies_true_count=1)
    body = next(r for r in res if r["gate"] == "G2.body")
    assert body["passed"]  # 本文1件は「本文無し」と誤判定しない


def test_g2_body_zero_is_no_body(cfg):
    res = preflight.gate_g2_dependencies(cfg, bodies_true_count=0)
    body = next(r for r in res if r["gate"] == "G2.body")
    assert not body["passed"] and body["reason"] == "no_body"


def test_g2_missing_log_db_flags_db_setup():
    res = preflight.gate_g2_dependencies({"notion_gmail_send": {}}, bodies_true_count=1)
    logdb = next(r for r in res if r["gate"] == "G2.log_db")
    assert not logdb["passed"] and logdb["action"] == "db_setup"


# ---- G3: キャンペーン整合 ----
@pytest.mark.parametrize("over,reason", [
    (dict(approved_plan_hash="x", plan_hash="y"), "plan_hash_mismatch"),
    (dict(approved_count=1, actual_count=2), "count_mismatch"),
    (dict(approved_first_to="a@x.com", actual_first_to="b@x.com"), "first_to_mismatch"),
])
def test_g3_blocks_mismatch(over, reason):
    base = dict(approved_plan_hash="h", plan_hash="h", approved_count=1, actual_count=1,
                approved_first_to="a@x.com", actual_first_to="a@x.com")
    base.update(over)
    r = preflight.gate_g3_presend(**base)
    assert not r["passed"] and r["reason"] == reason


def test_g3_passes_when_all_match():
    r = preflight.gate_g3_presend(approved_plan_hash="h", plan_hash="h", approved_count=2,
                                  actual_count=2, approved_first_to="a@x.com", actual_first_to="a@x.com")
    assert r["passed"]

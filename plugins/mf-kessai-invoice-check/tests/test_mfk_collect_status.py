#!/usr/bin/env python3
"""scripts/mfk_collect_status.py (billing.status『発行済み』判定 SSOT・要因C1根治) の単体テスト。

network=false の純関数。billing.status の enum 全体を分類表で網羅し、self-test CLI の
exit code 契約 (0=OK/1=self-test違反/2=usage error) も検証する。
"""
import pytest

import mfk_collect_status as M


# ---------------------------------------------------------------------------
# is_issued_billing: 分類表
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status,expected", [
    ("invoice_issued", True),
    ("account_transfer_notified", True),   # 発行後の後続 status (要因C1: paws有限会社型)
    ("scheduled", False),                  # 発行予定 (未発行)
    ("stopped", False),                    # 真の停止=非発行
    ("INVOICE_ISSUED", True),              # 大小文字非依存
    ("Account_Transfer_Notified", True),
    ("  invoice_issued  ", True),          # 前後空白非依存
    (None, False),                         # None 安全
    ("", False),
    ("   ", False),
    ("unknown_future_status", False),      # 未知 status は保守的に非issued
    (123, False),                          # 非文字列は False
])
def test_is_issued_billing_classification(status, expected):
    assert M.is_issued_billing(status) is expected


def test_issued_billing_statuses_content_lock_in():
    # ISSUED_BILLING_STATUSES の内容を明示的にロックする (stopped は含めない=真の停止)。
    assert M.ISSUED_BILLING_STATUSES == {"invoice_issued", "account_transfer_notified"}
    assert "stopped" not in M.ISSUED_BILLING_STATUSES
    assert "scheduled" not in M.ISSUED_BILLING_STATUSES


# ---------------------------------------------------------------------------
# summarize_billing_statuses
# ---------------------------------------------------------------------------
def test_summarize_billing_statuses_counts():
    billings = [
        {"status": "invoice_issued"},
        {"status": "invoice_issued"},
        {"status": "account_transfer_notified"},
        {"status": "stopped"},
    ]
    assert M.summarize_billing_statuses(billings) == {
        "invoice_issued": 2, "account_transfer_notified": 1, "stopped": 1,
    }


def test_summarize_billing_statuses_unknown_bucket():
    billings = [{}, {"status": None}, {"status": ""}, {"not_a_dict": True}, "oops"]
    assert M.summarize_billing_statuses(billings) == {"(unknown)": 5}


def test_summarize_billing_statuses_empty_input():
    assert M.summarize_billing_statuses([]) == {}
    assert M.summarize_billing_statuses(None) == {}


# ---------------------------------------------------------------------------
# CLI self-test (exit code 契約: 0=OK / 1=self-test違反 / 2=usage error)
# ---------------------------------------------------------------------------
def test_cli_self_test_exit0(capsys):
    rc = M.main([])
    assert rc == 0
    assert "self-test OK" in capsys.readouterr().out


def test_cli_unknown_arg_is_exit2():
    with pytest.raises(SystemExit) as exc:
        M.main(["--bogus"])
    assert exc.value.code == 2


def test_self_test_detects_violation(monkeypatch):
    # is_issued_billing を意図的に壊し、self-test が違反を検出できることを確認する。
    monkeypatch.setattr(M, "is_issued_billing", lambda status: False)
    violations = M._self_test()
    assert violations
    assert any("invoice_issued" in v for v in violations)

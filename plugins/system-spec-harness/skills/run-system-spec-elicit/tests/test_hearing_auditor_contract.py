"""C06 hearing auditor の 5 軸・実 loop 上限契約を静的に固定する。"""
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[3]
ADAPTER = PLUGIN / "agents" / "system-spec-hearing-auditor.md"
SSOT = PLUGIN / "skills" / "run-system-spec-elicit" / "prompts" / "R6-audit-hearing.md"


def test_adapter_keeps_all_five_audit_axes_in_stopping_contract() -> None:
    text = ADAPTER.read_text(encoding="utf-8")

    assert "監査 5 軸" in text
    assert "5 軸すべてを評価" in text
    assert "foundation 根拠欠落" in text
    assert "effective_source_refs" in text
    assert "schema 1.0" in text
    assert "superseded_by" in text
    assert "active consumer" in text
    assert "4 軸" not in text


def test_adapter_and_ssot_use_persisted_max_loops_not_fixed_five() -> None:
    adapter = ADAPTER.read_text(encoding="utf-8")
    ssot = SSOT.read_text(encoding="utf-8")

    for text in (adapter, ssot):
        assert "`max_loops` の実値" in text
        assert "5 周" not in text


def test_r0_and_r6_share_effective_source_and_immutable_history_contract() -> None:
    r0 = (PLUGIN / "skills" / "run-system-spec-elicit" / "prompts" / "R0-foundation.md").read_text(encoding="utf-8")
    r6 = SSOT.read_text(encoding="utf-8")

    for text in (r0, r6):
        assert "effective_source_refs" in text
        assert "qa-foundation-u1" in text
        assert "schema 1.0" in text
    assert "履歴" in r0 and "改変せず" in r0
    assert "retired" in r6 and "active consumer" in r6


def test_adapter_allows_only_read_and_read_only_bash() -> None:
    text = ADAPTER.read_text(encoding="utf-8")

    assert "tools: Read, Bash" in text
    assert "許可された read-only `Bash`" in text
    assert "書込・redirect・network" in text
    assert "Read 以外の操作" not in text

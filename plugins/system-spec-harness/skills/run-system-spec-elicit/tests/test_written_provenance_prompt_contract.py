"""書面 source-index が AI 自己参照に退行しない prompt 契約を固定する。"""
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_ROOT.parents[1]


def test_elicit_and_reask_require_verbatim_written_source_bytes() -> None:
    foundation = (SKILL_ROOT / "prompts" / "R0-foundation.md").read_text(encoding="utf-8")
    interview = (SKILL_ROOT / "prompts" / "R2-interview.md").read_text(encoding="utf-8")
    reask = (SKILL_ROOT / "prompts" / "R3-reask.md").read_text(encoding="utf-8")

    for text in (interview, reask):
        assert "指定 path/section" in text
        assert "逐語" in text
        assert "UTF-8" in text
        assert "新規 approval" in text
    assert "質問に入力 path/section" in foundation
    assert "指定 section に実在する逐語原文" in foundation
    assert "sha256(answer UTF-8 bytes)" in foundation
    assert "書面に同等の承認が明記されていれば" in foundation
    assert "AI 自身を承認者とする新規 approval を作らない" in foundation
    assert "entry 自身の digest" in interview


def test_hearing_auditor_reads_and_checks_the_referenced_section() -> None:
    adapter = (PLUGIN_ROOT / "agents" / "system-spec-hearing-auditor.md").read_text(
        encoding="utf-8"
    )
    ssot = (SKILL_ROOT / "prompts" / "R6-audit-hearing.md").read_text(encoding="utf-8")

    for text in (adapter, ssot):
        assert "source.section" in text
        assert "Read" in text
        assert "sha256(answer UTF-8 bytes)" in text
        assert "relative_to" in text
        assert "Bash" in text

    assert "tools: Read, Bash" in adapter
    assert "`Read` のみ" not in adapter


def test_effective_binding_contract_distinguishes_explicit_shared_qa_from_duplicates() -> None:
    foundation = (SKILL_ROOT / "prompts" / "R0-foundation.md").read_text(encoding="utf-8")
    hearing = (SKILL_ROOT / "prompts" / "R6-audit-hearing.md").read_text(encoding="utf-8")
    contract = (SKILL_ROOT / "references" / "spec-state-contract.md").read_text(
        encoding="utf-8"
    )

    for text in (foundation, hearing, contract):
        assert "明示的な共有 binding" in text
        assert "共有対象の全 U marker" in text
        assert "U ごとに分離可能な利用者決定" in text
        assert "evidence_quote" in text
        assert "evidence_sha256" in text
        assert "consumer" in text
        assert "C06" in text
        assert "qa_ref の一致だけを重複違反にしない" in text

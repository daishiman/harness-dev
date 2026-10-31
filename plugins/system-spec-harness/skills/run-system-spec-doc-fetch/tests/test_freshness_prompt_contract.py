"""C08 が公式 source catalog と record 固有 claim を無視しない契約を固定する。"""
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_ROOT.parents[1]


def test_freshness_auditor_must_read_the_official_source_catalog() -> None:
    ssot = (SKILL_ROOT / "prompts" / "R4-audit-doc-freshness.md").read_text(
        encoding="utf-8"
    )
    adapter = (PLUGIN_ROOT / "agents" / "system-spec-doc-freshness-auditor.md").read_text(
        encoding="utf-8"
    )

    for text in (ssot, adapter):
        assert "official-source-catalog.md" in text
        assert "publisher 直営 GitHub" in text
        assert "github.com を一律に非公式扱いしない" in text


def test_freshness_is_scoped_to_the_recorded_claim_not_a_rolling_page_head() -> None:
    ssot = (SKILL_ROOT / "prompts" / "R4-audit-doc-freshness.md").read_text(
        encoding="utf-8"
    )
    adapter = (PLUGIN_ROOT / "agents" / "system-spec-doc-freshness-auditor.md").read_text(
        encoding="utf-8"
    )

    for text in (ssot, adapter):
        assert "record 固有 claim" in text
        assert "rolling changelog" in text
        assert "新記事の存在だけで stale にしない" in text

"""C05 監査 fork の完全 response 台帳束縛を静的に固定する。"""
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def test_three_auditors_are_dispatched_serially_in_foreground() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    score = (SKILL_ROOT / "prompts" / "R1-score.md").read_text(encoding="utf-8")
    prompt = (SKILL_ROOT / "prompts" / "R2-delegate.md").read_text(encoding="utf-8")

    for text in (skill, score, prompt):
        assert "1 message = 1 foreground fork" in text
        assert "PostToolUse" in text

    for text in (skill, prompt):
        assert "AUDIT_VERDICT" in text
        assert "background/非同期" in text

    assert "3 監査は独立 context で並走し得る" not in prompt
    assert "並走させ得る" not in score


def test_five_axis_wording_includes_foundation_source_evidence() -> None:
    score = (SKILL_ROOT / "prompts" / "R1-score.md").read_text(encoding="utf-8")
    delegate = (SKILL_ROOT / "prompts" / "R2-delegate.md").read_text(encoding="utf-8")
    criteria = (SKILL_ROOT / "references" / "aspect-criteria.md").read_text(encoding="utf-8")

    for text in (score, delegate, criteria):
        assert "5 軸" in text
        assert "foundation 利用者根拠" in text
        assert "4 軸" not in text


def test_current_dispatch_and_recursive_markdown_contract_are_consistent() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    score = (SKILL_ROOT / "prompts" / "R1-score.md").read_text(encoding="utf-8")
    delegate = (SKILL_ROOT / "prompts" / "R2-delegate.md").read_text(encoding="utf-8")
    criteria = (SKILL_ROOT / "references" / "aspect-criteria.md").read_text(encoding="utf-8")

    for text in (skill, score, delegate):
        assert "Agent" in text
        assert "legacy" in text
        assert 'Path.rglob("*.md")' in text
        assert "system-spec/*.md" not in text

    assert 'Path.rglob("*.md")' in criteria
    assert "system-spec/*.md" not in criteria
    assert "--print-artifact-snapshot" in skill
    assert "--print-artifact-snapshot" in score


def test_resource_map_points_to_canonical_system_spec_inputs() -> None:
    resource_map = (SKILL_ROOT / "references" / "resource-map.yaml").read_text(
        encoding="utf-8"
    )

    assert "path: system-spec/spec-state.json" in resource_map
    assert "path: system-spec/fetched-references.json" in resource_map


def _frontmatter_refs(text: str, key: str) -> set[str]:
    lines = text.split(f"\n{key}:\n", 1)[1].splitlines()
    refs = []
    for line in lines:
        if not line.startswith("  - "):
            break
        refs.append(line.removeprefix("  - ").strip())
    assert refs
    return set(refs)


def _resource_paths(text: str, section: str) -> set[str]:
    lines = text.split(f"\n{section}:\n", 1)[1].splitlines()
    paths = set()
    for line in lines:
        if line and not line.startswith(" "):
            break
        stripped = line.strip()
        if stripped.startswith("path: "):
            paths.add(stripped.removeprefix("path: "))
    return paths


def test_public_script_and_schema_refs_are_indexed_in_resource_map() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    resource_map = (SKILL_ROOT / "references" / "resource-map.yaml").read_text(
        encoding="utf-8"
    )

    assert _frontmatter_refs(skill, "script_refs") <= _resource_paths(resource_map, "scripts")
    assert _frontmatter_refs(skill, "schema_refs") <= _resource_paths(resource_map, "schemas")


def test_receipt_writer_commands_resolve_from_the_plugin_root() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    score = (SKILL_ROOT / "prompts" / "R1-score.md").read_text(encoding="utf-8")
    # HD の runtime root 表記 (PLUGIN_ROOT 優先、無ければ CLAUDE_PLUGIN_ROOT)
    canonical = (
        '${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/assign-system-spec-completeness-evaluator/'
        'scripts/build-resume-receipt.py'
    )

    assert skill.count(canonical) >= 2
    assert canonical in score
    assert "python3 scripts/build-resume-receipt.py" not in skill
    assert "python3 scripts/build-resume-receipt.py" not in score

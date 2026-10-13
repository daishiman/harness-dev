import json
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (PLUGIN_ROOT / relative).read_text(encoding="utf-8")


def test_goal_setting_parent_owns_dialogue_and_coordinator_is_advisory() -> None:
    skill = _read("skills/run-ubm-goal-setting/SKILL.md")
    agent = _read("agents/phase3-coordinator.md")
    manifest = json.loads(
        _read("skills/run-ubm-goal-setting/workflow-manifest.json")
    )

    assert "engine: inline" in skill
    assert "fork: inline" in skill
    assert "本 skill（親対話）" in skill
    assert "../../scripts/validate-inline-goal-seek-anchor.py" in skill
    assert "run-ubm-goal-setting/goal-seek-progress.json" in skill
    assert "run-ubm-goal-setting-intermediate.jsonl" in skill
    assert "ユーザーへ直接質問せず" in agent
    assert "ファイルや `interview_data` を更新しない" in agent
    phase3 = next(item for item in manifest["phases"] if item["id"] == "phase3-dialogue")
    assert "parent dialogue owner" in phase3["actor"]
    assert "optional read-only advisor" in phase3["actor"]

    for prompt in sorted((PLUGIN_ROOT / "skills/run-ubm-goal-setting/prompts").glob("R*.md")):
        text = prompt.read_text(encoding="utf-8")
        assert "親コンテキストが本プロンプトを Read して対話を進行" in text
        assert "coordinator が本プロンプトを Read しインライン進行" not in text


def test_delegated_writers_receive_absolute_plugin_root_contract() -> None:
    journal_skill = _read("skills/run-ubm-journal/SKILL.md")
    journal_agent = _read("agents/journal-composer.md")
    knowledge_skill = _read("skills/run-ubm-knowledge-sync/SKILL.md")
    knowledge_agent = _read("agents/knowledge-extractor.md")

    assert "../../references/agent-root-contract.md" in journal_skill
    assert "${PLUGIN_ROOT:?absolute plugin root from owner skill is required}" in journal_agent
    assert "$CLAUDE_PLUGIN_ROOT" not in journal_agent

    assert "../../references/agent-root-contract.md" in knowledge_skill
    assert "`plugin_root`: 親スキルが host-skill-path から解決した" in knowledge_agent
    assert "$CLAUDE_PLUGIN_ROOT" not in knowledge_agent


def test_journal_parent_and_composer_have_one_write_validation_owner() -> None:
    journal_skill = _read("skills/run-ubm-journal/SKILL.md")

    assert "| Phase5-validate |" in journal_skill
    phase5 = next(line for line in journal_skill.splitlines() if line.startswith("| Phase5-validate |"))
    assert "journal-composer" in phase5 and "検査スクリプト" in phase5
    assert "親は同じファイルを再編集せず" in journal_skill
    assert "../../references/goal-seek-anchor-contract.md" in journal_skill
    assert "親がPhase4を自動再起動せず" in journal_skill
    assert "Dailyは変更しない" in journal_skill

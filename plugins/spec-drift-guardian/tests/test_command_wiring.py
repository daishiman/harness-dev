# /// script
# name: test-command-wiring
# purpose: rubric-sync command が独立 verifier/auditor と明示承認を実際に起動できる tool 配線を固定する。
# inputs: commands/rubric-sync.md
# outputs: pytest assertions
# contexts: [E]
# network: false
# write-scope: none
# dependencies: [pytest]
# ///
"""rubric-sync の独立 context 起動が散文だけに退行しないことを検査する。"""
from pathlib import Path


COMMAND = Path(__file__).resolve().parents[1] / "commands" / "rubric-sync.md"


def test_rubric_sync_grants_and_invokes_independent_tasks():
    text = COMMAND.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]

    allowed_line = next(line for line in frontmatter.splitlines() if line.startswith("allowed-tools:"))
    for tool in ("Skill", "Task", "AskUserQuestion"):
        assert tool in allowed_line

    assert 'Task(spec-impact-verifier, context:fork, args="--issue <NUMBER>")' in text
    assert 'Task(rubric-sync-auditor, context:fork, args="--issue <NUMBER>")' in text
    assert "`AskUserQuestion` でユーザー" in text

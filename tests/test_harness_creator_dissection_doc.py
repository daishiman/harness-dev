"""harness-creator 解説の可変 inventory / hook delivery が実装とずれないことを保証する。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "harness-creator"
DOC = ROOT / "doc" / "harness-creator-完全解剖.md"


def _manifest(product: str) -> dict:
    return json.loads((PLUGIN / f".{product}-plugin" / "plugin.json").read_text(encoding="utf-8"))


def test_dissection_inventory_matches_current_harness_creator() -> None:
    text = DOC.read_text(encoding="utf-8")
    version = _manifest("claude")["version"]
    skill_count = sum((path / "SKILL.md").is_file() for path in (PLUGIN / "skills").iterdir())
    agent_count = len(list((PLUGIN / "agents").glob("*.md")))
    command_count = len(list((PLUGIN / "commands").glob("*.md")))

    assert _manifest("codex")["version"] == version
    assert (
        f"version {version} / skills {skill_count} + agents {agent_count} + commands {command_count}"
        in text
    )
    assert f"{skill_count} 個の skill 名" in text


def test_dissection_describes_single_shared_hook_without_claude_double_load() -> None:
    text = DOC.read_text(encoding="utf-8")
    claude = _manifest("claude")
    codex = _manifest("codex")
    shared = PLUGIN / codex["hooks"]

    assert "hooks" not in claude
    assert codex["hooks"] == "./hooks/hooks.json"
    assert shared.is_file()
    assert "Claude は標準自動検出" in text
    assert "Codex manifest は `./hooks/hooks.json` を明示参照" in text
    assert "SessionStart 1 イベント / 1 コマンド" in text

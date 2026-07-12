# /// script
# name: test-validate-knowledge-cards
# version: 0.1.0
# purpose: ref-system-design-knowledge の deep knowledge card / open-world catalog (knowledge-catalog.json / knowledge-card.schema.json / *.md カード) の必須意味フィールド契約と seed/open-world 宣言を検証する pytest (要件 C11)。
# inputs:
#   - argv: pytest 経由 (直接 argv は取らない)
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=all pass / 1=failure
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-knowledge-cards.py"
SPEC = importlib.util.spec_from_file_location("validate_knowledge_cards", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_curated_cards_and_open_world_lifecycle_pass():
    assert mod.validate_root(ROOT) == []


def test_pointer_only_card_fails_depth(tmp_path):
    card = tmp_path / "shallow.md"
    card.write_text(
        "# Shallow\n\n> status: `seed-example`\n\n"
        + "\n".join(f"## {heading}\n\n要点。" for heading in mod.REQUIRED_SECTIONS),
        encoding="utf-8",
    )
    errors = mod.validate_card(card)
    assert any("shallow section" in error for error in errors)
    assert any("primary source locator URL missing" in error for error in errors)


def test_card_without_freshness_tokens_fails(tmp_path):
    source = ROOT / "references" / "clean-architecture.md"
    text = source.read_text(encoding="utf-8").replace("review_by:", "review-next:")
    card = tmp_path / "stale.md"
    card.write_text(text, encoding="utf-8")
    assert any("review_by:" in error for error in mod.validate_card(card))

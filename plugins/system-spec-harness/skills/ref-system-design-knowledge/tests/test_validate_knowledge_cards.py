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
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT.parents[1]
REFS = ROOT / "references"
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


def _resource_map_cards() -> list[tuple[str, str]]:
    """resource-map.yaml から (.md card file, read_when) を記述順で返す (stdlib のみ)。"""
    text = (REFS / "resource-map.yaml").read_text(encoding="utf-8")
    pairs: list[tuple[str, str]] = []
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("- "):
            line = line[2:].strip()
        if line.startswith("file:"):
            current = line[len("file:") :].strip()
        elif line.startswith("read_when:") and current:
            if current.endswith(".md"):
                pairs.append((current, line[len("read_when:") :].strip()))
            current = None
    return pairs


def _in_scope_categories() -> list[str]:
    """doctrine registry の in-scope カテゴリ (共通シード + approved pending 例外)。"""
    registry = json.loads((REFS / "doctrine-anchor-registry.json").read_text(encoding="utf-8"))
    categories = list(registry["categories"])
    categories += [
        exception["category"]
        for exception in registry.get("pending_exceptions", [])
        if exception.get("approval_state") == "approved"
    ]
    return categories


def test_every_in_scope_category_has_a_category_specific_card():
    # C05 design_knowledge_reflection の medium finding: ui-ux / infrastructure などが汎用ポインタ
    # のみに退化するのを防ぐ。in-scope の全カテゴリが read_when 経由で 1 枚以上の deep card へ
    # 接続していることを回帰検知する。
    cards = _resource_map_cards()
    catalog_files = {
        entry["file"]
        for entry in json.loads((REFS / "knowledge-catalog.json").read_text(encoding="utf-8"))["entries"]
    }
    for category in _in_scope_categories():
        matched = [name for name, read_when in cards if category in read_when]
        assert matched, f"カテゴリ {category} に専用 deep card が無い (汎用ポインタへ退化する)"
        for name in matched:
            assert name in catalog_files, f"{name} が knowledge-catalog.json 未登録 (位相順の対象外になる)"


def test_resource_map_card_order_matches_topo_order():
    # card 集合の SSOT は resource-map、反映順序の SSOT は knowledge-catalog の topo_order。
    # 記述順を反映順と誤読させないため、resource-map の card 並びも topo_order と同順に保つ。
    result = subprocess.run(
        [
            sys.executable,
            str(PLUGIN_ROOT / "scripts" / "validate-knowledge-graph.py"),
            "--profile", "knowledge",
            "--input", str(REFS / "knowledge-catalog.json"),
            "--order",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    topo = json.loads(result.stdout)
    file_to_id = {
        entry["file"]: entry["knowledge_id"]
        for entry in json.loads((REFS / "knowledge-catalog.json").read_text(encoding="utf-8"))["entries"]
    }
    listed = [file_to_id[name] for name, _ in _resource_map_cards() if name in file_to_id]
    assert listed == [kid for kid in topo if kid in set(listed)]


def test_new_category_cards_are_not_generic_pointers():
    # 章固有性の担保: 追加 card の read_when は意図したカテゴリだけに一致し (全章共通の汎用文言でない)、
    # 深度ゲート (validate_card) を満たし、当該領域の一次資料 URL を持つ。
    # information-design は画面に限らない表現物全般の card なので ui-ux と frontend へ、
    # cloud-architecture-patterns はデータ配置の card なので database と infrastructure へ出る。
    # testing-qa / dev-workflow は seed taxonomy 外の open-world カテゴリで、project が追加したときに効く。
    open_world_categories = ["testing-qa", "dev-workflow"]
    expected = {
        "usability-accessibility.md": {"ui-ux"},
        "information-design.md": {"ui-ux", "frontend"},
        "site-reliability-engineering.md": {"infrastructure"},
        "cloud-architecture-patterns.md": {"database", "infrastructure"},
        "test-strategy.md": {"testing-qa"},
        "continuous-delivery.md": {"dev-workflow"},
    }
    cards = dict(_resource_map_cards())
    categories = _in_scope_categories() + open_world_categories
    for name, wanted in expected.items():
        read_when = cards[name]
        assert {c for c in categories if c in read_when} == wanted, name
        assert mod.validate_card(REFS / name) == []
        assert re.search(r"https?://", (REFS / name).read_text(encoding="utf-8"))


def test_card_without_freshness_tokens_fails(tmp_path):
    source = ROOT / "references" / "clean-architecture.md"
    text = source.read_text(encoding="utf-8").replace("review_by:", "review-next:")
    card = tmp_path / "stale.md"
    card.write_text(text, encoding="utf-8")
    assert any("review_by:" in error for error in mod.validate_card(card))

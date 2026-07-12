"""knowledge/router.json の集計値と実エントリ数の count parity ゲート。

router.json の total_entries / categories.*.entry_count / subcategory_counts が
knowledge/*.json の entries[] 実測と一致することを機械検査する
(155/157/154 三重不一致 drift の再発防止)。registry.json の内部整合も併せて検査する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = PLUGIN_ROOT / "knowledge"
MANAGEMENT_FILES = {"router.json", "registry.json", "schema.json"}

MD5_RE = re.compile(r"^[0-9a-f]{32}$")


def load(name: str) -> dict:
    return json.loads((KNOWLEDGE / name).read_text(encoding="utf-8"))


def entry_count(name: str) -> int:
    return len(load(name).get("entries", []))


def content_files() -> list[Path]:
    """管理ファイルを除くナレッジ JSON (集約親ファイル含む)。"""
    return sorted(
        p for p in KNOWLEDGE.glob("*.json") if p.name not in MANAGEMENT_FILES
    )


def test_total_entries_matches_disk():
    # router.total_entries == 全ナレッジ JSON の entries[] 実測合計
    router = load("router.json")
    actual = sum(entry_count(p.name) for p in content_files())
    assert router["total_entries"] == actual, (
        f"router.total_entries={router['total_entries']} != 実測 {actual}"
    )


def test_category_entry_count_matches_files():
    # 各カテゴリの entry_count == categories[cat].files の実測合計
    router = load("router.json")
    for cat, spec in router["categories"].items():
        actual = sum(entry_count(f) for f in spec["files"])
        assert spec["entry_count"] == actual, (
            f"{cat}: entry_count={spec['entry_count']} != 実測 {actual}"
        )


def test_subcategory_counts_match_files_and_sum():
    # subcategory_counts の各値 == 該当ファイル実測、合計 == entry_count、キー集合 == files
    router = load("router.json")
    for cat, spec in router["categories"].items():
        sub = spec["subcategory_counts"]
        assert set(sub) == set(spec["files"]), f"{cat}: subcategory_counts と files が不一致"
        for fname, declared in sub.items():
            actual = entry_count(fname)
            assert declared == actual, f"{cat}/{fname}: {declared} != 実測 {actual}"
        assert sum(sub.values()) == spec["entry_count"], (
            f"{cat}: subcategory 合計 {sum(sub.values())} != entry_count {spec['entry_count']}"
        )


def test_no_orphan_knowledge_files():
    # entries[] が非空のナレッジ JSON は必ずいずれかの categories[].files に列挙されている
    router = load("router.json")
    routed = {f for spec in router["categories"].values() for f in spec["files"]}
    for p in content_files():
        if p.name not in routed:
            assert entry_count(p.name) == 0, (
                f"{p.name} は router 未登録なのに entries を持つ (router drift)"
            )


def test_registry_internal_consistency():
    # total_processed == files 件数、file_hash は全件 md5 32文字 (日付文字列・偽値の禁止)
    registry = load("registry.json")
    files = registry["files"]
    assert registry["total_processed"] == len(files)
    for f in files:
        assert MD5_RE.match(f["file_hash"]), f"{f['file_path']}: file_hash が md5 32文字でない"


def test_registry_null_entry_ids_are_marked_legacy():
    # extracted_entry_ids: null は legacy 注記付きシードのみ許容 (SKILL.md の移行規則対象)
    registry = load("registry.json")
    for f in registry["files"]:
        if f.get("extracted_entry_ids") is None:
            assert "legacy" in f.get("_note", ""), (
                f"{f['file_path']}: extracted_entry_ids null に legacy 注記がない (null 禁止)"
            )

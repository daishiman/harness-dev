"""knowledge/router.json の集計値と実エントリ数の count parity ゲート。

router.json の total_entries / categories.*.entry_count / subcategory_counts が
knowledge/*.json の entries[] 実測と一致することを機械検査する
(155/157/154 三重不一致 drift の再発防止)。registry.json の内部整合も併せて検査する。

あわせて LLM 抽出時の生成事故を機械検出する:
- 実在しない entry ID への related 参照 (validate-knowledge-graph.py は非致命として
  drop するため、テストで検出しないと壊れた索引が蓄積する)
- 日本語本文への字種混入 (キリル文字等)。長文の日本語を大量生成する際に一定確率で
  発生し、目視レビューでは見落とす
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = PLUGIN_ROOT / "knowledge"
MANAGEMENT_FILES = {"router.json", "registry.json", "schema.json"}
# validate-knowledge-graph.py の生成物。追跡対象外だがローカル実行で現れうる。
GENERATED_FILES = {"knowledge-graph.json", "knowledge-relations.json"}

MD5_RE = re.compile(r"^[0-9a-f]{32}$")
ID_RE = re.compile(r"^[A-Z]{2,4}-\d{3}$")

# 日本語本文を想定するフィールド。ここへの字種混入は生成事故。
JA_TEXT_FIELDS = (
    "content", "background", "intent", "root_cause", "expected_outcome",
    "detail", "quote", "conversation_flow", "applicable_when", "how_to_use",
    "before", "after", "why_the_shift_matters", "trigger", "situation",
    "problem", "advice", "key_insight", "rationale", "outcome", "lesson",
    "key_factor", "focus", "title",
)
# 日本語文中に現れてはならない字種 (誤って混入する言語)
FOREIGN_SCRIPTS = ("CYRILLIC", "HANGUL", "ARABIC", "HEBREW", "THAI", "DEVANAGARI", "GREEK")


def load(name: str) -> dict:
    return json.loads((KNOWLEDGE / name).read_text(encoding="utf-8"))


def entry_count(name: str) -> int:
    return len(load(name).get("entries", []))


def content_files() -> list[Path]:
    """管理ファイルを除くナレッジ JSON (集約親ファイル含む)。"""
    return sorted(
        p for p in KNOWLEDGE.glob("*.json")
        if p.name not in MANAGEMENT_FILES and p.name not in GENERATED_FILES
    )


def all_entries() -> list[tuple[str, dict]]:
    """(ファイル名, entry) の全件。"""
    return [(p.name, e) for p in content_files() for e in load(p.name).get("entries", [])]


def walk_text(obj, path: str = ""):
    """(パス, 文字列) を再帰的に列挙する。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_text(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_text(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def foreign_chars(text: str) -> set[str]:
    """日本語文中に現れてはならない字種を返す。"""
    out = set()
    for ch in set(text):
        if ord(ch) < 128:
            continue
        try:
            name = unicodedata.name(ch)
        except ValueError:
            continue
        if any(s in name for s in FOREIGN_SCRIPTS):
            out.add(ch)
    return out


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


def test_entry_ids_are_unique_and_well_formed():
    # ID は全ファイル横断で一意、かつ PREFIX-999 形式
    seen: dict[str, str] = {}
    for fname, e in all_entries():
        eid = e["id"]
        assert ID_RE.match(eid), f"{fname}: 不正な ID 形式 {eid!r}"
        assert eid not in seen, f"ID 重複: {eid} ({seen[eid]} と {fname})"
        seen[eid] = fname


def test_related_refs_resolve():
    """related が実在する entry ID のみを参照する。

    validate-knowledge-graph.py は未解決参照を非致命として drop するため、
    ここで検出しないと壊れた索引が蓄積し続ける (実際に AG-014 -> PR-025、
    CS-022/MS-019 -> PR-026 の 3 件が長期間残存していた)。
    """
    ids = {e["id"] for _, e in all_entries()}
    broken = [
        (fname, e["id"], r)
        for fname, e in all_entries()
        for r in (e.get("related") or [])
        if r not in ids
    ]
    assert not broken, "実在しない entry ID への related 参照: " + ", ".join(
        f"[{f}] {i} -> {r}" for f, i, r in broken
    )


def test_no_foreign_script_in_japanese_text():
    """日本語本文にキリル文字等が混入していない。

    長文の日本語を大量生成する際に一定確率で発生し、目視レビューでは
    見落とすため機械検出する。
    """
    hits = []
    for fname, e in all_entries():
        for path, text in walk_text(e):
            leaf = path.split(".")[-1].split("[")[0]
            if leaf not in JA_TEXT_FIELDS:
                continue
            bad = foreign_chars(text)
            if bad:
                hits.append(f"[{fname}] {e['id']}.{path}: {sorted(bad)}")
    assert not hits, "日本語本文への字種混入: " + "; ".join(hits)

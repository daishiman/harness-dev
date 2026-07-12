#!/usr/bin/env python3
# /// script
# name: build_index
# purpose: knowledge-index.json とカテゴリファイルの整合性を検証し、統計表示・自動修正を行う
# inputs:
#   - argv: --stats / --fix / --index / --dir / --self-test
# outputs:
#   - stdout: 整合性レポート / 統計 JSON
#   - stderr: 不整合・JSON 解析失敗の診断
# contexts: [C, E]
# network: false
# write-scope: knowledge/knowledge-index.json
# dependencies: []
# requires-python: ">=3.10"
# ///
# -*- coding: utf-8 -*-
"""
build_index.py — knowledge-index.json 整合性検証・自動修正スクリプト

exit_code:
  0 = 正常 (警告があっても 0)
  1 = 引数エラー / JSON解析失敗
  2 = --fix 後も修復不能なエラーが残存

使用方法:
  python3 build_index.py --stats
  python3 build_index.py --fix
  python3 build_index.py --self-test
"""

import argparse
import json
import sys
from pathlib import Path


REQUIRED_ENTRY_FIELDS_TITLE = {"id", "background", "source"}
REQUIRED_ENTRY_FIELDS_CONTENT = {"id", "background", "source"}
REQUIRED_INTENT = {"intent", "purpose"}
REQUIRED_TITLE = {"title", "content"}
REQUIRED_KEYWORDS = {"keywords", "tags"}


def find_index(start_dir: Path) -> Path | None:
    for d in [start_dir] + list(start_dir.parents):
        p = d / "knowledge" / "knowledge-index.json"
        if p.exists():
            return p
        p2 = d / "knowledge-index.json"
        if p2.exists():
            return p2
    return None


def load_index(index_path: Path) -> dict:
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)


def check_entry(item: dict) -> list[str]:
    """必須フィールドチェック。問題リストを返す。"""
    issues = []
    if "id" not in item:
        issues.append("id フィールドがない")
    if not REQUIRED_TITLE.intersection(item.keys()):
        issues.append("title または content フィールドがない")
    if not REQUIRED_INTENT.intersection(item.keys()):
        issues.append("intent または purpose フィールドがない")
    if "background" not in item:
        issues.append("background フィールドがない")
    if not REQUIRED_KEYWORDS.intersection(item.keys()):
        issues.append("keywords または tags フィールドがない")
    if "source" not in item:
        issues.append("source フィールドがない")
    return issues


def run_stats(index_path: Path) -> dict:
    """インデックス統計・整合性チェックを実行する。"""
    index = load_index(index_path)
    knowledge_dir = index_path.parent
    categories = index.get("categories", [])

    stats = {
        "index_path": str(index_path),
        "category_count": len(categories),
        "total_entries": 0,
        "errors": [],
        "warnings": []
    }

    seen_ids: set[str] = set()

    for cat in categories:
        cat_id = cat.get("id", "UNKNOWN")
        cat_file = cat.get("file", "")
        cat_path = knowledge_dir / cat_file

        if not cat_path.exists():
            stats["errors"].append(f"カテゴリファイルが存在しない: {cat_file} (category={cat_id})")
            continue

        try:
            with open(cat_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            stats["errors"].append(f"JSON解析失敗: {cat_file}: {e}")
            continue

        items = data.get("items", [])
        stats["total_entries"] += len(items)

        if len(items) < 1:
            stats["warnings"].append(f"エントリが0件: {cat_file}")

        for item in items:
            item_id = item.get("id", "NO_ID")

            # ID一意性チェック
            if item_id in seen_ids:
                stats["errors"].append(f"IDが重複: {item_id} (file={cat_file})")
            seen_ids.add(item_id)

            # 必須フィールドチェック
            issues = check_entry(item)
            for issue in issues:
                stats["errors"].append(f"[{cat_id}/{item_id}] {issue}")

    return stats


def fix_index(index_path: Path) -> list[str]:
    """自動修正可能な問題を修正する。修正内容リストを返す。"""
    index = load_index(index_path)
    knowledge_dir = index_path.parent
    fixes = []

    categories = index.get("categories", [])
    valid_categories = []

    for cat in categories:
        cat_id = cat.get("id", "")
        cat_file = cat.get("file", "")
        cat_path = knowledge_dir / cat_file

        if not cat_path.exists():
            # 存在しないファイルへの参照を削除
            fixes.append(f"存在しないカテゴリファイルへの参照を削除: {cat_file}")
            continue
        valid_categories.append(cat)

    if len(valid_categories) != len(categories):
        index["categories"] = valid_categories
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        fixes.append(f"knowledge-index.json を更新 ({len(valid_categories)} カテゴリ)")

    return fixes


def self_test() -> None:
    """内蔵OK例/NG例でチェック動作を検証する。"""
    import tempfile

    # OK例: 必須6フィールドを持つエントリ
    ok_item = {
        "id": "test_001",
        "title": "テストタイトル",
        "intent": "テストを通過させること",
        "background": "テスト環境で実行。エントリの整合性を確認する。",
        "keywords": ["テスト", "検証", "自動化"],
        "source": {"file": "test.md", "type": "テスト", "date": "2026-01-01", "section": "§1"}
    }
    issues_ok = check_entry(ok_item)
    assert issues_ok == [], f"OK例でエラーが発生: {issues_ok}"

    # NG例: title, intent, keywords, source を欠く
    ng_item = {
        "id": "test_002",
        "background": "背景のみ"
    }
    issues_ng = check_entry(ng_item)
    assert len(issues_ng) >= 3, f"NG例でエラーが検出されない: {issues_ng}"
    assert any("title" in i or "content" in i for i in issues_ng), f"title/content エラーが検出されない: {issues_ng}"
    assert any("intent" in i or "purpose" in i for i in issues_ng), f"intent/purpose エラーが検出されない: {issues_ng}"

    # ファイルベーステスト: 存在しないカテゴリファイル参照を検出
    with tempfile.TemporaryDirectory() as tmpdir:
        kdir = Path(tmpdir) / "knowledge"
        kdir.mkdir()
        index_data = {
            "version": "1.0.0",
            "categories": [
                {"id": "exists", "label": "存在するカテゴリ", "file": "knowledge-exists.json", "keywords": []},
                {"id": "missing", "label": "存在しないカテゴリ", "file": "knowledge-missing.json", "keywords": []}
            ],
            "global_keywords": {}
        }
        cat_data = {
            "category": "exists",
            "label": "存在するカテゴリ",
            "version": "1.0.0",
            "items": [ok_item]
        }
        (kdir / "knowledge-index.json").write_text(json.dumps(index_data), encoding="utf-8")
        (kdir / "knowledge-exists.json").write_text(json.dumps(cat_data), encoding="utf-8")

        stats = run_stats(kdir / "knowledge-index.json")
        has_missing_error = any("missing" in e for e in stats["errors"])
        assert has_missing_error, f"存在しないファイルエラーが検出されない: {stats['errors']}"

        # --fix テスト
        fixes = fix_index(kdir / "knowledge-index.json")
        assert len(fixes) > 0, f"--fix で修正が行われない: {fixes}"

        stats_after = run_stats(kdir / "knowledge-index.json")
        has_missing_after = any("missing" in e for e in stats_after["errors"])
        assert not has_missing_after, f"--fix 後も存在しないファイルエラーが残存: {stats_after['errors']}"

    print("--self-test: PASS (全テスト通過)")


def main() -> None:
    parser = argparse.ArgumentParser(description="knowledge-index.json 整合性検証・自動修正")
    parser.add_argument("--stats", action="store_true", help="統計と整合性エラーを表示")
    parser.add_argument("--fix", action="store_true", help="自動修正可能な問題を修正")
    parser.add_argument("--index", help="knowledge-index.json のパス (省略時は --dir / 自動探索)")
    parser.add_argument("--dir", dest="dir", help="knowledge ストアのディレクトリ。<dir>/knowledge-index.json または <dir>/knowledge/knowledge-index.json を解決 (Loop B / 別ストア参照用)")
    parser.add_argument("--self-test", action="store_true", help="内蔵テストを実行して exit")

    args = parser.parse_args()

    if args.self_test:
        self_test()
        sys.exit(0)

    if not args.stats and not args.fix:
        parser.error("--stats または --fix を指定してください")

    # インデックス探索: 明示 --index > --dir > 自動探索 (cwd)
    if args.index:
        index_path = Path(args.index)
    elif args.dir:
        base = Path(args.dir)
        cand = base / "knowledge-index.json"
        index_path = cand if cand.exists() else base / "knowledge" / "knowledge-index.json"
    else:
        from search_knowledge import find_index  # type: ignore
        index_path = find_index(Path.cwd())

    if not index_path or not index_path.exists():
        print(json.dumps({"error": "knowledge-index.json が見つかりません"}), file=sys.stderr)
        sys.exit(1)

    try:
        if args.fix:
            fixes = fix_index(index_path)
            print(json.dumps({"fixes": fixes, "count": len(fixes)}, ensure_ascii=False, indent=2))

        if args.stats or args.fix:
            stats = run_stats(index_path)
            print(json.dumps(stats, ensure_ascii=False, indent=2))
            if stats["errors"]:
                sys.exit(2)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON解析失敗: {e}"}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

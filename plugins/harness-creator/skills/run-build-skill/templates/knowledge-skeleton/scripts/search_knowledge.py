#!/usr/bin/env python3
# /// script
# name: search_knowledge
# purpose: knowledge/ を 3 段階検索の Stage1(カテゴリ絞り)+Stage2(重み付きスコア)で検索する決定論段スクリプト
# inputs:
#   - argv: --query / --keywords / --category / --id / --limit / --index / --dir / --self-test
# outputs:
#   - stdout: 検索結果 JSON (count + results[])
#   - stderr: index 不在 / JSON 解析失敗の診断
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
# -*- coding: utf-8 -*-
"""
search_knowledge.py — knowledge/ 検索スクリプト (Stage1 + Stage2)

exit_code:
  0 = 正常 (結果0件でも正常)
  1 = 引数エラー / knowledge-index.json が見つからない / JSON解析失敗

使用方法:
  python3 search_knowledge.py --query "自然言語クエリ" --limit 5
  python3 search_knowledge.py --keywords "kw1,kw2" --limit 3
  python3 search_knowledge.py --category mindset --limit 3
  python3 search_knowledge.py --id "mindset_001"
  python3 search_knowledge.py --self-test
"""

import argparse
import json
import re
import sys
from pathlib import Path


DEFAULT_WEIGHTS = {"title": 5, "keywords": 3, "quote": 2, "voice": 2, "fulltext": 1}


def load_index(index_path: Path) -> dict:
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)


def load_category_file(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("items", [])


def expand_synonyms(keywords: list[str], synonyms: dict) -> list[str]:
    """シノニムマップを使ってキーワードを展開する。"""
    expanded = list(keywords)
    for kw in keywords:
        for canonical, syns in synonyms.items():
            if kw == canonical or kw in syns:
                expanded.append(canonical)
                expanded.extend(syns)
    return list(dict.fromkeys(expanded))  # 重複除去・順序保持


def stage1_filter_categories(index: dict, keywords: list[str]) -> list[dict]:
    """Stage1: global_keywords を使ってカテゴリを絞り込む。"""
    global_kw = index.get("global_keywords", {})
    category_scores: dict[str, int] = {}

    for kw in keywords:
        kw_lower = kw.lower()
        for gk, cat_ids in global_kw.items():
            if kw_lower in gk.lower() or gk.lower() in kw_lower:
                for cid in cat_ids:
                    category_scores[cid] = category_scores.get(cid, 0) + 1

    categories = index.get("categories", [])
    if not category_scores:
        return categories  # スコア0なら全カテゴリ対象

    return [c for c in categories if category_scores.get(c["id"], 0) > 0]


def build_search_text(item: dict) -> str:
    """フルテキスト検索用にフィールドを連結する。"""
    fields = ["background", "message", "purpose", "intent",
              "root_cause", "expected_outcome", "achievable", "how_to_use", "applications"]
    parts = [str(item.get(f, "")) for f in fields if item.get(f)]
    return " ".join(parts)


def score_item(item: dict, keywords: list[str], weights: dict) -> int:
    """Stage2: フィールド重み付きスコアを計算する。"""
    score = 0
    full_text = build_search_text(item).lower()

    title_val = (item.get("title") or item.get("content") or "").lower()
    kw_list = [k.lower() for k in (item.get("keywords") or item.get("tags") or [])]
    quotes = [e.lower() for e in (item.get("expressions") or item.get("quote") or [])]
    voice_val = (item.get("voice") or
                 (item.get("expression") or {}).get("phrasing") or "").lower()

    for kw in keywords:
        kw_l = kw.lower()

        # fulltext: 出現回数分加算
        freq = len(re.findall(re.escape(kw_l), full_text))
        score += freq * weights.get("fulltext", 1)

        # keywords/tags
        if any(kw_l in k for k in kw_list):
            score += weights.get("keywords", 3)

        # title/content
        if kw_l in title_val:
            score += weights.get("title", 5)

        # quote/expressions
        if any(kw_l in e for e in quotes):
            score += weights.get("quote", 2)

        # voice/expression.phrasing
        if kw_l in voice_val:
            score += weights.get("voice", 2)

    return score


def search(index_path: Path, query: str | None, keywords_str: str | None,
           category_filter: str | None, id_filter: str | None, limit: int) -> list[dict]:
    index = load_index(index_path)
    weights = {**DEFAULT_WEIGHTS, **index.get("scoring_weights", {})}
    synonyms = index.get("synonyms", {})
    knowledge_dir = index_path.parent

    # キーワード構築
    if query:
        raw_kws = re.split(r"[\s　、,]+", query.strip())
    elif keywords_str:
        raw_kws = [k.strip() for k in keywords_str.split(",") if k.strip()]
    else:
        raw_kws = []

    keywords = expand_synonyms([k for k in raw_kws if k], synonyms) if raw_kws else []

    # ID直引き
    if id_filter:
        categories = index.get("categories", [])
        for cat in categories:
            cat_path = knowledge_dir / cat["file"]
            if not cat_path.exists():
                continue
            items = load_category_file(cat_path)
            for item in items:
                if item.get("id") == id_filter:
                    return [{"item": item, "score": 999, "category": cat["id"]}]
        return []

    # Stage1: カテゴリ絞り込み
    if category_filter:
        categories = [c for c in index.get("categories", []) if c["id"] == category_filter]
    elif keywords:
        categories = stage1_filter_categories(index, keywords)
    else:
        categories = index.get("categories", [])

    # Stage2: スコアリング
    results = []
    for cat in categories:
        cat_path = knowledge_dir / cat["file"]
        if not cat_path.exists():
            continue
        items = load_category_file(cat_path)
        for item in items:
            # deprecated エントリは除外
            if item.get("status") == "deprecated":
                continue
            sc = score_item(item, keywords, weights) if keywords else 0
            results.append({"item": item, "score": sc, "category": cat["id"]})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def find_index(start_dir: Path) -> Path | None:
    """カレントまたは親ディレクトリから knowledge-index.json を探す。"""
    for d in [start_dir] + list(start_dir.parents):
        p = d / "knowledge" / "knowledge-index.json"
        if p.exists():
            return p
        p2 = d / "knowledge-index.json"
        if p2.exists():
            return p2
    return None


def self_test() -> None:
    """内蔵サンプルでスコアリング動作を検証する。"""
    import tempfile
    import os

    sample_items = [
        {
            "id": "test_001",
            "title": "アルファ手法は効率を高める",
            "intent": "アルファ手法の有効性を認知させること",
            "background": "あるチームが3か月間にわたり既存手法を試したが成果が出なかった状況。代替手段を検討中。",
            "keywords": ["アルファ手法", "効率改善", "成果未達", "代替手段", "改善策"],
            "source": {"file": "test.md", "type": "メモ", "date": "2026-01-01", "section": "手法検討"}
        },
        {
            "id": "test_002",
            "title": "外部の視点が新しい発見をもたらす",
            "intent": "外部視点の価値に気づかせること",
            "background": "あるグループが自分たちの強みを過小評価していた状況。",
            "keywords": ["発見", "外部視点", "気づき", "評価", "強み"],
            "source": {"file": "test2.md", "type": "メモ", "date": "2026-02-01", "section": "視点分析"},
            "quote": ["外部の視点が、新しい発見をもたらす"]
        }
    ]

    weights = DEFAULT_WEIGHTS

    # テスト1: title マッチが高スコアになるか
    score1 = score_item(sample_items[0], ["アルファ手法", "効率"], weights)
    score2 = score_item(sample_items[1], ["アルファ手法", "効率"], weights)
    assert score1 > score2, f"title マッチスコアテスト失敗: score1={score1}, score2={score2}"

    # テスト2: quote マッチが加点されるか
    score_with_quote = score_item(sample_items[1], ["発見"], weights)
    score_without_quote = score_item(sample_items[0], ["発見"], weights)
    assert score_with_quote > score_without_quote, f"quote マッチスコアテスト失敗: {score_with_quote} vs {score_without_quote}"

    # テスト3: シノニム展開
    synonyms = {"改善策": ["改良案", "対策"]}
    expanded = expand_synonyms(["改善策"], synonyms)
    assert "改良案" in expanded, f"シノニム展開テスト失敗: {expanded}"

    # テスト4: deprecated エントリが除外されるか (ファイルベース)
    with tempfile.TemporaryDirectory() as tmpdir:
        kdir = Path(tmpdir) / "knowledge"
        kdir.mkdir()
        index_data = {
            "version": "1.0.0",
            "categories": [{"id": "test", "label": "テスト", "file": "knowledge-test.json", "keywords": ["テスト"]}],
            "global_keywords": {},
            "synonyms": {},
            "scoring_weights": DEFAULT_WEIGHTS,
            "output_dir": tmpdir,
            "output_naming": "output - {date}.md"
        }
        cat_data = {
            "category": "test",
            "label": "テスト",
            "version": "1.0.0",
            "created_at": "2026-01-01",
            "items": [
                {**sample_items[0]},
                {**sample_items[1], "status": "deprecated"}
            ]
        }
        (kdir / "knowledge-index.json").write_text(json.dumps(index_data), encoding="utf-8")
        (kdir / "knowledge-test.json").write_text(json.dumps(cat_data), encoding="utf-8")

        results = search(kdir / "knowledge-index.json", "アルファ", None, None, None, 10)
        ids = [r["item"]["id"] for r in results]
        assert "test_002" not in ids, f"deprecated エントリが除外されていない: {ids}"
        assert "test_001" in ids, f"有効エントリが見つからない: {ids}"

    print("--self-test: PASS (全4テスト通過)")


def main() -> None:
    parser = argparse.ArgumentParser(description="knowledge/ 検索スクリプト (Stage1+Stage2)")
    parser.add_argument("--query", help="自然言語クエリ")
    parser.add_argument("--keywords", help="カンマ区切りキーワード")
    parser.add_argument("--category", help="カテゴリIDで絞り込み")
    parser.add_argument("--id", help="エントリIDで直引き")
    parser.add_argument("--limit", type=int, default=5, help="返す件数 (デフォルト: 5)")
    parser.add_argument("--index", help="knowledge-index.json のパス (省略時は --dir / 自動探索)")
    parser.add_argument("--dir", dest="dir", help="knowledge ストアのディレクトリ。<dir>/knowledge-index.json または <dir>/knowledge/knowledge-index.json を解決 (Loop B / 別ストア参照用)")
    parser.add_argument("--self-test", action="store_true", help="内蔵テストを実行して exit")

    args = parser.parse_args()

    if args.self_test:
        self_test()
        sys.exit(0)

    if not args.query and not args.keywords and not args.category and not args.id:
        parser.error("--query / --keywords / --category / --id のいずれかを指定してください")

    # インデックス探索: 明示 --index > --dir > 自動探索 (cwd) の段階フォールバック
    if args.index:
        index_path = Path(args.index)
    elif args.dir:
        base = Path(args.dir)
        cand = base / "knowledge-index.json"
        index_path = cand if cand.exists() else base / "knowledge" / "knowledge-index.json"
    else:
        index_path = find_index(Path.cwd())

    if not index_path or not index_path.exists():
        print(json.dumps({"error": "knowledge-index.json が見つかりません"}), file=sys.stderr)
        sys.exit(1)

    try:
        results = search(index_path, args.query, args.keywords, args.category, args.id, args.limit)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON解析失敗: {e}"}), file=sys.stderr)
        sys.exit(1)

    output = {
        "count": len(results),
        "results": [
            {
                "id": r["item"].get("id"),
                "score": r["score"],
                "category": r["category"],
                "title": r["item"].get("title") or r["item"].get("content", ""),
                "intent": r["item"].get("intent") or r["item"].get("purpose", ""),
                "keywords": r["item"].get("keywords") or r["item"].get("tags", [])
            }
            for r in results
        ]
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# name: record_usage
# purpose: §12 活用ログ (usage-log.jsonl) への記録と品質改善パターン分析を行う
# inputs:
#   - argv: --record / --analyze / --emit-queue / --mark-needs-update / --query / --matched-ids / --used-ids / --satisfaction / --note / --log / --dir / --self-test
# outputs:
#   - stdout: 記録エントリ JSON または分析結果 JSON (--emit-queue 時は brushup キュー件数も)
#   - stderr: ファイル書き込み失敗の診断
# contexts: [C, E]
# network: false
# write-scope: knowledge/usage-log.jsonl, knowledge/brushup-queue.jsonl (--emit-queue), knowledge/knowledge-<category>.json の status のみ (--mark-needs-update)
# dependencies: []
# requires-python: ">=3.10"
# ///
# -*- coding: utf-8 -*-
"""
record_usage.py — §12 活用ログ記録・品質改善パターン検出スクリプト

exit_code:
  0 = 正常 (警告があっても 0)
  1 = 引数エラー / ファイル書き込み失敗

使用方法:
  python3 record_usage.py --record \\
      --query "地方企業の採用戦略" \\
      --matched-ids "talent_001,cases_003" \\
      --used-ids "talent_001" \\
      --satisfaction helpful \\
      --note "任意メモ"

  python3 record_usage.py --analyze [--log usage-log.jsonl]

  # 書き戻し入口: 検出した要改善エントリを brushup キューへ出力 (二層分離: 本文改善は AI に委ねる)
  python3 record_usage.py --analyze --emit-queue brushup-queue.jsonl

  # 検出 entry_id にカテゴリファイル上で status=needs-update を付与 (内容は変えず status のみ)
  python3 record_usage.py --analyze --mark-needs-update --dir /path/to/store

  python3 record_usage.py --self-test

二層分離:
  --analyze は問題を検出するだけ。--emit-queue / --mark-needs-update は検出結果を
  機械可読に「ステージング (可視化・マーキング)」する決定論操作であり、title/keywords/
  background 等の本文の良し悪しの判断と改善は AI/人に委ねる。
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_LOG_FILE = "usage-log.jsonl"

# パターン検出の閾値
PATTERN_THRESHOLDS = {
    "hit_not_used_ratio": 0.5,    # matched_ids のうち used_ids に入らない割合がこれ以上で警告
    "unhelpful_consecutive": 3,    # unhelpful が連続でこの件数以上で警告
    "concentration_ratio": 0.8,   # 同一エントリが全クエリのこの割合以上でヒットで警告
    "min_samples": 3,             # 分析に最低必要なログ件数
}


def find_log_file(start_dir: Path, filename: str) -> Path:
    """ログファイルのパスを返す。存在しない場合はカレント配下に作成する。"""
    for d in [start_dir] + list(start_dir.parents):
        p = d / filename
        if p.exists():
            return p
    return start_dir / filename


def record_entry(log_path: Path, query: str, matched_ids: list[str], used_ids: list[str],
                 satisfaction: str, note: str | None) -> dict:
    """活用ログに1エントリ追記する。"""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "matched_ids": matched_ids,
        "used_ids": used_ids,
        "satisfaction": satisfaction,
    }
    if note:
        entry["note"] = note

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def load_log(log_path: Path) -> list[dict]:
    """JSONL ファイルを読み込む。"""
    if not log_path.exists():
        return []
    entries = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # 壊れた行はスキップ
    return entries


def analyze_patterns(entries: list[dict]) -> dict:
    """品質改善パターン4種を検出する。"""
    findings = []

    if len(entries) < PATTERN_THRESHOLDS["min_samples"]:
        return {
            "analyzed_entries": len(entries),
            "findings": [],
            "note": f"サンプル不足 (最低{PATTERN_THRESHOLDS['min_samples']}件必要, 現在{len(entries)}件)"
        }

    # --- パターン1: ヒットするが使われない ---
    hit_not_used: dict[str, int] = {}
    hit_counts: dict[str, int] = {}
    for entry in entries:
        for eid in entry.get("matched_ids", []):
            hit_counts[eid] = hit_counts.get(eid, 0) + 1
            if eid not in entry.get("used_ids", []):
                hit_not_used[eid] = hit_not_used.get(eid, 0) + 1

    for eid, not_used in hit_not_used.items():
        total = hit_counts.get(eid, 1)
        ratio = not_used / total
        if ratio >= PATTERN_THRESHOLDS["hit_not_used_ratio"] and total >= 2:
            findings.append({
                "pattern": "hit_not_used",
                "severity": "warn",
                "entry_id": eid,
                "hit_count": total,
                "not_used_count": not_used,
                "ratio": round(ratio, 2),
                "action": "keywords が不適切。title と intent を見直す"
            })

    # --- パターン2: ヒットしない (used_ids が空のエントリが多い) ---
    empty_used = sum(1 for e in entries if not e.get("used_ids"))
    empty_ratio = empty_used / len(entries)
    if empty_ratio >= 0.5:
        findings.append({
            "pattern": "low_hit_rate",
            "severity": "warn",
            "empty_used_count": empty_used,
            "total": len(entries),
            "ratio": round(empty_ratio, 2),
            "action": "keywords を追加。synonyms マップを更新"
        })

    # --- パターン3: 低満足度連続 ---
    consecutive = 0
    max_consecutive = 0
    for entry in entries:
        if entry.get("satisfaction") == "unhelpful":
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0

    if max_consecutive >= PATTERN_THRESHOLDS["unhelpful_consecutive"]:
        findings.append({
            "pattern": "consecutive_unhelpful",
            "severity": "warn",
            "max_consecutive": max_consecutive,
            "action": "background と intent の具体性を改善 (ルーブリック §4.3 で再評価)"
        })

    # --- パターン4: 特定エントリに集中 ---
    total_queries = len(entries)
    for eid, count in hit_counts.items():
        ratio = count / total_queries
        if ratio >= PATTERN_THRESHOLDS["concentration_ratio"]:
            findings.append({
                "pattern": "entry_concentration",
                "severity": "warn",
                "entry_id": eid,
                "hit_count": count,
                "total_queries": total_queries,
                "ratio": round(ratio, 2),
                "action": "keywords が汎用的すぎる。差別化を強化"
            })

    return {
        "analyzed_entries": len(entries),
        "findings": findings,
        "summary": {
            "unique_matched_ids": len(hit_counts),
            "satisfaction_counts": {
                "helpful": sum(1 for e in entries if e.get("satisfaction") == "helpful"),
                "neutral": sum(1 for e in entries if e.get("satisfaction") == "neutral"),
                "unhelpful": sum(1 for e in entries if e.get("satisfaction") == "unhelpful"),
            }
        }
    }


def extract_brushup_queue(analysis: dict) -> list[dict]:
    """分析結果から「要改善エントリ」の brushup キュー行を抽出する (決定論)。

    各 finding の entry_id / pattern / action / detected_at を機械可読化する。
    entry_id を持たない finding (low_hit_rate 等) も pattern 単位で 1 行出力する。
    本文の良し悪しは判断しない ── ステージングのみ。
    """
    detected_at = datetime.now(timezone.utc).isoformat()
    queue: list[dict] = []
    for f in analysis.get("findings", []):
        queue.append({
            "entry_id": f.get("entry_id"),  # entry 単位でない finding は null
            "pattern": f.get("pattern"),
            "severity": f.get("severity", "warn"),
            "action": f.get("action", ""),
            "detected_at": detected_at,
        })
    return queue


def write_brushup_queue(queue_path: Path, queue: list[dict]) -> int:
    """brushup キューを JSONL で追記する。書き込んだ行数を返す。"""
    with open(queue_path, "a", encoding="utf-8") as f:
        for row in queue:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(queue)


def mark_needs_update(index_path: Path, entry_ids: set[str]) -> list[str]:
    """検出 entry_id に対し該当カテゴリファイルの当該エントリへ status=needs-update を付与する。

    内容 (title/keywords/background) は一切変更せず status フィールドのみ付与する決定論操作。
    search_knowledge は status=="deprecated" を除外するが needs-update は除外しないため検索性は維持される。
    更新した entry_id のリストを返す。
    """
    if not entry_ids or not index_path.exists():
        return []
    index = json.loads(index_path.read_text(encoding="utf-8"))
    knowledge_dir = index_path.parent
    updated: list[str] = []
    for cat in index.get("categories", []):
        cat_path = knowledge_dir / cat.get("file", "")
        if not cat_path.exists():
            continue
        try:
            data = json.loads(cat_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        changed = False
        for item in data.get("items", []):
            if item.get("id") in entry_ids and item.get("status") != "needs-update":
                item["status"] = "needs-update"
                updated.append(item["id"])
                changed = True
        if changed:
            cat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return updated


def resolve_index_path(dir_arg: str | None) -> Path | None:
    """--mark-needs-update 用に knowledge-index.json を解決する (--dir > 自動探索)。"""
    if dir_arg:
        base = Path(dir_arg)
        cand = base / "knowledge-index.json"
        return cand if cand.exists() else base / "knowledge" / "knowledge-index.json"
    start = Path.cwd()
    for d in [start] + list(start.parents):
        p = d / "knowledge" / "knowledge-index.json"
        if p.exists():
            return p
        p2 = d / "knowledge-index.json"
        if p2.exists():
            return p2
    return None


def self_test() -> None:
    """内蔵サンプルで記録・分析動作を検証する。"""
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "usage-log.jsonl"

        # テスト1: record_entry が正しく追記するか
        entry = record_entry(log_path, "テストクエリ", ["id_001", "id_002"], ["id_001"], "helpful", "テストノート")
        assert entry["query"] == "テストクエリ", f"クエリ記録失敗: {entry}"
        assert "timestamp" in entry, "タイムスタンプがない"

        # テスト2: load_log が正しく読み込めるか
        entries = load_log(log_path)
        assert len(entries) == 1, f"ロード件数が違う: {len(entries)}"

        # テスト3: サンプル不足時の分析
        result = analyze_patterns(entries)
        assert "note" in result, f"サンプル不足時に note がない: {result}"

        # テスト4: パターン検出 (hit_not_used)
        test_entries = []
        for i in range(5):
            test_entries.append({
                "timestamp": "2026-01-01T00:00:00+00:00",
                "query": f"クエリ{i}",
                "matched_ids": ["id_always_hit"],
                "used_ids": [],  # ヒットするが使われない
                "satisfaction": "neutral"
            })
        result4 = analyze_patterns(test_entries)
        hit_not_used_findings = [f for f in result4["findings"] if f["pattern"] == "hit_not_used"]
        assert len(hit_not_used_findings) > 0, f"hit_not_used パターンが検出されない: {result4['findings']}"

        # テスト5: 低満足度連続パターン検出
        unhelpful_entries = [
            {"timestamp": "2026-01-01T00:00:00+00:00", "query": f"q{i}",
             "matched_ids": [f"id_{i}"], "used_ids": [], "satisfaction": "unhelpful"}
            for i in range(5)
        ]
        result5 = analyze_patterns(unhelpful_entries)
        consec_findings = [f for f in result5["findings"] if f["pattern"] == "consecutive_unhelpful"]
        assert len(consec_findings) > 0, f"consecutive_unhelpful パターンが検出されない: {result5['findings']}"

        # テスト6: 特定エントリ集中パターン
        concentration_entries = [
            {"timestamp": "2026-01-01T00:00:00+00:00", "query": f"q{i}",
             "matched_ids": ["dominant_id"], "used_ids": ["dominant_id"], "satisfaction": "helpful"}
            for i in range(5)
        ]
        result6 = analyze_patterns(concentration_entries)
        conc_findings = [f for f in result6["findings"] if f["pattern"] == "entry_concentration"]
        assert len(conc_findings) > 0, f"entry_concentration パターンが検出されない: {result6['findings']}"

        # テスト7: brushup キュー抽出と JSONL 出力 (--emit-queue 相当)
        queue = extract_brushup_queue(result4)
        assert len(queue) > 0, f"brushup キューが空: {queue}"
        assert all("pattern" in q and "action" in q and "detected_at" in q for q in queue), \
            f"キュー行に必須キーがない: {queue}"
        queue_path = Path(tmpdir) / "brushup-queue.jsonl"
        n = write_brushup_queue(queue_path, queue)
        assert n == len(queue), f"キュー書き込み件数不一致: {n} vs {len(queue)}"
        reloaded = load_log(queue_path)
        assert len(reloaded) == n, f"キュー JSONL 再読込件数不一致: {len(reloaded)} vs {n}"

        # テスト8: mark_needs_update が status のみ付与し本文を変えないこと
        kdir = Path(tmpdir) / "knowledge"
        kdir.mkdir()
        idx_path = kdir / "knowledge-index.json"
        idx_path.write_text(json.dumps({
            "version": "1.0.0",
            "categories": [{"id": "t", "label": "t", "file": "knowledge-t.json", "keywords": []}],
            "global_keywords": {},
        }), encoding="utf-8")
        original_item = {
            "id": "mark_001", "title": "原文タイトル", "intent": "意図",
            "background": "背景", "keywords": ["a", "b"], "source": {"file": "x.md"},
        }
        (kdir / "knowledge-t.json").write_text(json.dumps({
            "category": "t", "label": "t", "version": "1.0.0", "items": [dict(original_item)],
        }), encoding="utf-8")
        updated = mark_needs_update(idx_path, {"mark_001"})
        assert updated == ["mark_001"], f"status 付与対象が違う: {updated}"
        after = json.loads((kdir / "knowledge-t.json").read_text(encoding="utf-8"))
        marked = after["items"][0]
        assert marked["status"] == "needs-update", f"status が付与されていない: {marked}"
        assert marked["title"] == original_item["title"], "本文 (title) が改変された"
        assert marked["keywords"] == original_item["keywords"], "本文 (keywords) が改変された"
        # 冪等性: 再実行で重複付与されない
        again = mark_needs_update(idx_path, {"mark_001"})
        assert again == [], f"冪等でない (再付与された): {again}"

    print("--self-test: PASS (全8テスト通過)")


def main() -> None:
    parser = argparse.ArgumentParser(description="§12 活用ログ記録・品質改善パターン検出")
    parser.add_argument("--record", action="store_true", help="ログに1エントリ追記")
    parser.add_argument("--analyze", action="store_true", help="品質改善パターンを分析")
    parser.add_argument("--emit-queue", dest="emit_queue", nargs="?", const="brushup-queue.jsonl",
                        help="--analyze の検出結果を brushup キュー (JSONL) へ追記。パス省略時は brushup-queue.jsonl")
    parser.add_argument("--mark-needs-update", dest="mark_needs_update", action="store_true",
                        help="--analyze で検出した entry_id にカテゴリファイル上で status=needs-update を付与 (内容は変えない)")
    parser.add_argument("--query", help="検索クエリ (--record 時必須)")
    parser.add_argument("--matched-ids", help="マッチしたエントリID (カンマ区切り)")
    parser.add_argument("--used-ids", help="実際に活用したエントリID (カンマ区切り)", default="")
    parser.add_argument("--satisfaction", choices=["helpful", "neutral", "unhelpful"],
                        default="neutral", help="満足度")
    parser.add_argument("--note", help="改善メモ (任意)")
    parser.add_argument("--log", default=DEFAULT_LOG_FILE, help=f"ログファイルパス (デフォルト: {DEFAULT_LOG_FILE})")
    parser.add_argument("--dir", dest="dir", help="knowledge ストアのディレクトリ。<dir>/usage-log.jsonl を使用 (Loop B / 別ストア参照用)")
    parser.add_argument("--self-test", action="store_true", help="内蔵テストを実行して exit")

    args = parser.parse_args()

    if args.self_test:
        self_test()
        sys.exit(0)

    if not args.record and not args.analyze:
        parser.error("--record または --analyze を指定してください")

    # ログ解決: --dir 指定時は <dir>/usage-log.jsonl を直接使用、なければ --log を探索
    if args.dir:
        log_path = Path(args.dir) / DEFAULT_LOG_FILE
    else:
        log_path = find_log_file(Path.cwd(), args.log)

    if args.record:
        if not args.query:
            parser.error("--record 時は --query が必須です")
        matched_ids = [i.strip() for i in args.matched_ids.split(",") if i.strip()] if args.matched_ids else []
        used_ids = [i.strip() for i in args.used_ids.split(",") if i.strip()] if args.used_ids else []

        try:
            entry = record_entry(log_path, args.query, matched_ids, used_ids, args.satisfaction, args.note)
            print(json.dumps({"recorded": True, "log_path": str(log_path), "entry": entry},
                             ensure_ascii=False, indent=2))
        except OSError as e:
            print(json.dumps({"error": f"ファイル書き込み失敗: {e}"}), file=sys.stderr)
            sys.exit(1)

    if args.analyze:
        entries = load_log(log_path)
        result = analyze_patterns(entries)

        # 書き戻し入口1: brushup キュー出力 (ステージング)
        if args.emit_queue:
            queue = extract_brushup_queue(result)
            queue_path = Path(args.dir) / args.emit_queue if (args.dir and not Path(args.emit_queue).is_absolute()) \
                else Path(args.emit_queue)
            try:
                written = write_brushup_queue(queue_path, queue)
                result["brushup_queue"] = {"path": str(queue_path), "written": written}
            except OSError as e:
                print(json.dumps({"error": f"キュー書き込み失敗: {e}"}, ensure_ascii=False), file=sys.stderr)
                sys.exit(1)

        # 書き戻し入口2: status=needs-update マーキング (内容不変)
        if args.mark_needs_update:
            entry_ids = {f["entry_id"] for f in result.get("findings", []) if f.get("entry_id")}
            index_path = resolve_index_path(args.dir)
            if not index_path or not index_path.exists():
                print(json.dumps({"error": "knowledge-index.json が見つかりません (--dir を指定してください)"},
                                 ensure_ascii=False), file=sys.stderr)
                sys.exit(1)
            try:
                updated = mark_needs_update(index_path, entry_ids)
                result["marked_needs_update"] = updated
            except (OSError, json.JSONDecodeError) as e:
                print(json.dumps({"error": f"status 付与失敗: {e}"}, ensure_ascii=False), file=sys.stderr)
                sys.exit(1)

        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

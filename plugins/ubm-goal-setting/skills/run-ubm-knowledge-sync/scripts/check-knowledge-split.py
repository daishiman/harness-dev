#!/usr/bin/env python3
# /// script
# name: check-knowledge-split
# version: 0.2.0
# purpose: knowledge/ の category JSON が 500 行閾値を超過していないか検査する決定論ゲート
#          (schema.json/router.json/registry.json/knowledge-graph.json は管理・生成ファイルにつき除外)。
#          旧 check-knowledge-split.sh 67 行の契約移植 (逐語移植ではない)。
# inputs:
#   - argv: --dir KNOWLEDGE_DIR
# outputs:
#   - stdout: 各ファイルの行数と OK サマリ
#   - stderr: 超過ファイル一覧と分割手順
#   - exit: 0=OK / 1=超過あり / 2=usage
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""ナレッジ JSON の 500 行閾値超過を検査する (knowledge-extractor の Step3 分割入力)。

旧 check-knowledge-split.sh の契約移植。挙動の逐語ではなく「500行超のcategory JSONを
検知して分割を促す」検証ロジックを保存する。管理ファイル (schema/router/registry) は除外。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

THRESHOLD = 500
# 管理・生成ファイル: 行数閾値の対象外 (北原知見の category データではない)。
# knowledge-graph.json / harness-artifact-graph.json は C06/C05 が運用時に書出す索引 snapshot、
# knowledge-relations.json は辺の永続ストア、-quarantine.json は dangling 退避先で、いずれも分割対象外
EXCLUDED = {
    "schema.json",
    "router.json",
    "registry.json",
    "knowledge-graph.json",
    "harness-artifact-graph.json",
    "knowledge-relations.json",
    "knowledge-relations-quarantine.json",
}


def count_lines(path: Path) -> int:
    """wc -l 相当 (改行数) を返す。"""
    return path.read_text(encoding="utf-8").count("\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="ナレッジ JSON の 500 行閾値超過を検査する決定論ゲート",
        add_help=True,
    )
    ap.add_argument("--dir", required=True, help="knowledge/ ディレクトリ")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2

    kdir = Path(args.dir)
    if not kdir.is_dir():
        print(f"ERROR: ディレクトリが見つかりません: {kdir}", file=sys.stderr)
        return 2

    print("=== ナレッジファイルサイズチェック ===")
    print(f"閾値: {THRESHOLD}行")
    print("")

    split_needed: list[tuple[str, int]] = []
    for path in sorted(kdir.glob("*.json")):
        if path.name in EXCLUDED:
            continue
        lines = count_lines(path)
        if lines > THRESHOLD:
            print(f"  [要分割] {path.name} ({lines}行 > {THRESHOLD}行)")
            split_needed.append((path.name, lines))
        else:
            print(f"  [OK]    {path.name} ({lines}行)")

    print("")
    if not split_needed:
        print(f"全ファイルが {THRESHOLD}行以内です。分割不要。")
        return 0

    # 超過あり: 分割手順を stderr へ
    print("=== 分割が必要なファイル ===", file=sys.stderr)
    print("", file=sys.stderr)
    for fname, lines in split_needed:
        category = fname[:-len(".json")] if fname.endswith(".json") else fname
        print(f"  ファイル: {fname} ({lines} 行)", file=sys.stderr)
        print("  対応方法:", file=sys.stderr)
        print(f"    1. knowledge/{fname} を Read", file=sys.stderr)
        print("    2. エントリのテーマ別にグループ化", file=sys.stderr)
        print(f"    3. {{{category}}}-{{subtopic}}.json として分割（連番禁止）", file=sys.stderr)
        print("    4. router.json の files リストを更新", file=sys.stderr)
        print(f"    例: {category}-relationship.json / {category}-organization.json", file=sys.stderr)
        print("", file=sys.stderr)
    print("※ 命名規則: ファイル名だけで「どんな悩みのユーザー向けか」が分かること", file=sys.stderr)
    print("※ 連番（-1/-2/-a/-b）は絶対禁止", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
# /// script
# name: merge-layers
# purpose: per-layer L1..L7.yaml を「# Layer N:」見出し付きで 1 本の正規形 YAML へ合算する
# inputs:
#   - argv: --layers <dir>（L1.yaml..L7.yaml を含む）, --output <file>
# outputs:
#   - file: --output に合算 YAML を書き出す
#   - stdout: merged N layers → <output>
# contexts: [C]
# network: false
# write-scope: output-arg-only
# dependencies: []
# ///
# merge-layers.py — tmp/prompt-layers/L{1..7}.yaml を 1 本に合算
# Python 標準のみ (os/re/手書き YAML 連結)。PyYAML 不使用。
"""merge_layers.js の python 移植。元の振る舞い・終了コードを維持する。"""
import argparse
import os
import re
import sys


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--layers")
    parser.add_argument("--output")
    # A4-10: parse_known_args の黙殺を廃止 (failfast)。未知引数は argparse が exit 2。
    args = parser.parse_args()

    layers_dir = args.layers
    output = args.output
    if not layers_dir or not output:
        sys.stderr.write("usage: merge-layers.py --layers <dir> --output <file>\n")
        sys.exit(2)

    # 正準マーカー「# Layer N:」を採用 (verify-completeness.py / convert-format.py と一致)。
    # per-layer ファイルが自前の「# Layer N: title」見出しを持つ場合は重複付与を避ける。
    layer_titles = {
        1: "基本定義層", 2: "ドメイン定義層", 3: "インフラストラクチャ定義層",
        4: "共通ポリシー層", 5: "エージェント定義層", 6: "オーケストレーション層",
        7: "ユーザーインタラクション層",
    }
    parts = []
    for n in range(1, 8):
        p = os.path.join(layers_dir, f"L{n}.yaml")
        if not os.path.exists(p):
            sys.stderr.write(f"missing layer: {p}\n")
            sys.exit(1)
        with open(p, "r", encoding="utf-8") as f:
            body = f.read().rstrip()
        has_header = re.search(rf"#+\s*Layer\s*{n}\s*[:：]", body) is not None
        if not has_header:
            parts.append(f"# Layer {n}: {layer_titles[n]}")
        parts.append(body)
        parts.append("")

    layers = [1, 2, 3, 4, 5, 6, 7]
    out_dir = os.path.dirname(output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")
    print(f"merged {len(layers)} layers → {output}")


if __name__ == "__main__":
    main()

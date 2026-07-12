#!/usr/bin/env python3
# /// script
# name: convert-format
# purpose: 7層正規形 YAML を構造保存のまま md/json/xml/yaml へ変換する
# inputs:
#   - argv: --input <yaml> --format md|json|xml|yaml --output <file>
#   - file: --input の正規形 YAML
# outputs:
#   - file: --output に変換結果を書き出す
#   - stdout: converted → <output> (<format>)
#   - exit: 0=OK / 1=Layerマーカー不在 / 2=引数・未知format
# contexts: [C]
# network: false
# write-scope: output-arg-only
# dependencies: []
# ///
# convert-format.py — 7層正規形YAML → md/json/xml/yaml 変換 (Python 標準のみ)
# 設計方針: 日本語7層・ゴールシーク構造を「構造保存」で変換する。
#   YAML 本文（key: value / リスト / - [ ] チェックリスト / 達成ゴール 等）を捨てず保持し、
#   Layer 見出しのみ提示形式に合わせて書き換える。これにより可逆で、ゴールシーク要素を落とさない。
# マーカーは scaffold-prompt.py / merge-layers.py が出力する「# Layer N: <title>」に一致させる。
"""convert_format.js の python 移植。元の変換ロジック・終了コードを維持する。"""
import argparse
import json
import os
import re
import sys


def parse_args():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--input")
    parser.add_argument("--format", default="md")
    parser.add_argument("--output")
    # A4-10: parse_known_args の黙殺を廃止 (failfast)。未知引数は argparse が exit 2。
    return parser.parse_args()


# 「# Layer N: <title>」マーカーで本文を 7 層に分割し、本文を verbatim 保持する。
def parse_layers(text):
    layers = []
    for n in range(1, 8):
        pattern = (
            rf"#+\s*Layer\s*{n}\s*[:：]\s*([^\n]*)\n([\s\S]*?)"
            rf"(?=#+\s*Layer\s*{n + 1}\s*[:：]|$)"
        )
        m = re.search(pattern, text)
        if m:
            title = m.group(1).strip()
            body = re.sub(r"\s+$", "", m.group(2))
            layers.append({"n": n, "title": title, "body": body})
    return layers


def to_md(layers):
    out = ["# 7層構造プロンプト", ""]
    for layer in layers:
        out.append(f"## Layer {layer['n']}: {layer['title']}")
        out.append("")
        if layer["body"].strip():
            out.append(layer["body"].rstrip())
            out.append("")
    return "\n".join(out)


def to_json(layers):
    return json.dumps(
        [{"layer": x["n"], "title": x["title"], "body": x["body"].strip()} for x in layers],
        ensure_ascii=False,
        indent=2,
    )


def to_xml(layers):
    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<prompt>"]
    for layer in layers:
        parts.append(
            f'  <layer n="{layer["n"]}" title="{esc(layer["title"])}">'
            f'<![CDATA[\n{layer["body"]}\n]]></layer>'
        )
    parts.append("</prompt>")
    return "\n".join(parts)


def main():
    args = parse_args()
    input_path = args.input
    fmt = args.format
    output = args.output
    if not input_path or not output:
        sys.stderr.write(
            "usage: convert-format.py --input <yaml> --format md|json|xml|yaml --output <file>\n"
        )
        sys.exit(2)
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    if fmt == "yaml":
        out = text
    else:
        layers = parse_layers(text)
        if len(layers) == 0:
            sys.stderr.write(
                "[ERROR] Layer マーカー (# Layer N:) が見つかりません。正規形YAMLか確認してください。\n"
            )
            sys.exit(1)
        if fmt == "md":
            out = to_md(layers)
        elif fmt == "json":
            out = to_json(layers)
        elif fmt == "xml":
            out = to_xml(layers)
        else:
            sys.stderr.write(f"unknown format: {fmt}\n")
            sys.exit(2)
    out_dir = os.path.dirname(output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"converted → {output} ({fmt})")


if __name__ == "__main__":
    main()

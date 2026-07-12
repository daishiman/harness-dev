#!/usr/bin/env python3
# /// script
# name: verify-completeness
# purpose: 正規形プロンプト YAML/Markdown の7層構造網羅・Layer5 ゴールシーク必須要素・固定手順不在を検証する (l5-contract v2.0.0 準拠)
# inputs:
#   - argv: --input <prompt.yaml|md> [--layers L1,L2,...]
#   - file: --input の正規形 YAML / Markdown プロンプト
# outputs:
#   - stdout: OK サマリ / N/A skip 一覧 (--layers 指定時)
#   - stderr: FAIL incomplete の不備一覧
#   - exit: 0=OK / 1=不備あり / 2=引数エラー
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
# verify-completeness.py — 正規形プロンプト（merge-layers.py 出力 YAML / Markdown 提示形）の網羅性検証
#   1. 構造網羅: 必須 Layer (既定は 7 層全て、--layers で brief.layers_required のサブセットに限定可)
#      に最低 1 要素があるか。--layers 宣言外の Layer は N/A 理由付き skip で PASS。
#   2. ゴールシーク要素が Layer 5 に在るか（ゴール定義 / 完了チェックリスト / 達成ゴール）
#   3. 固定手順の不在（l5-contract v2.0.0 の禁止事項）:
#      a. 「思考プロセス」+「ステップN」の共起 (legacy 検出、維持)
#      b. Layer 5 内の『推論手順』『思考プロセス』『手順』『Steps』見出し (markdown 見出し /
#         YAML キー) 配下の連番列挙 (2 行以上)
#      allowlist (正当パターン): 5.4 実行方式 / 実行方式.ループ / ゴールシークループ配下の
#      6 ステップループ宣言 (goal-seek-paradigm 準拠のメタ手順)。banned 見出し名に該当しない
#      キー配下の連番は構造上検出対象外となるため、構成的に許容される。
#      加えて負例ガード: 禁止・注意書き行 (「〜書かない」「〜禁止」等) は見出し扱いしない。
# サブ構造の正本: references/seven-layer-format.md「Layer 5 契約」(l5-contract v2.0.0)。
# マーカーは scaffold-prompt.py / merge-layers.py が出力する「# Layer N:」に一致させる。
# Exit: 0=OK, 1=不備あり, 2=引数エラー (未知引数は argparse が failfast で exit 2)
"""verify_completeness.js の python 移植 + l5-contract v2.0.0 追従強化。終了コード契約を維持する。"""
import argparse
import re
import sys

# 固定手順とみなす見出し/キー名 (l5-contract v2.0.0 禁止事項)
BANNED_HEADING_TOKENS = r"(?:推論手順|思考プロセス|手順|[Ss]teps?)"
# markdown 見出し: 「### 5.2 推論手順 (再現可能)」「#### 手順」「## Steps」等。
# 見出しタイトルが banned トークンで始まる場合のみ一致 (「実行方式」「固定手順…禁止」等の
# 注意書き・別名見出しには一致しない)。
MD_BANNED_HEADING_RE = re.compile(
    rf"^(#{{1,6}})\s*(?:[0-9０-９][0-9０-９.．]*\s*)?{BANNED_HEADING_TOKENS}"
    r"\s*(?:[(（].*)?(?:[:：].*)?$"
)
# YAML キー: 「  推論手順:」「  手順:」等 (インデント付きキー行)
YAML_BANNED_KEY_RE = re.compile(
    rf"^(\s*){BANNED_HEADING_TOKENS}\s*[:：]\s*(?:[|>][+-]?)?\s*$"
)
# 連番列挙行: 「1. …」「- "2. …"」「ステップ3 …」等
ENUM_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?[\"'「]?\s*(?:[0-9０-９]{1,3}\s*[.)．）、]\s*\S|ステップ\s*[0-9０-９])"
)
MD_ANY_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
# 負例ガード: 禁止・注意書きの文言を含む行は見出し検出から除外する
NEGATION_MARKERS = ("禁止", "書かない", "書いてはならない", "持たせない", "収集しない", "列挙しない")

LAYER_TOKEN_RE = re.compile(r"^[Ll]?([1-7])$")


def parse_args():
    parser = argparse.ArgumentParser(
        add_help=True,
        description="7層プロンプトの網羅性 + Layer 5 ゴールシーク契約 (l5-contract v2.0.0) を検証する",
    )
    parser.add_argument("--input")
    parser.add_argument(
        "--layers",
        help="必須 Layer のサブセット (brief.layers_required)。例: L1,L2,L5。未指定時は 7 層全て必須。",
    )
    # A4-10: parse_known_args の黙殺を廃止。未知引数は argparse が usage を出して exit 2。
    return parser.parse_args()


def parse_required_layers(spec):
    """--layers 値を {1..7} のサブセット set に変換する。不正 token は ValueError。"""
    if spec is None:
        return set(range(1, 8))
    required = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        m = LAYER_TOKEN_RE.match(token)
        if not m:
            raise ValueError(f"invalid layer token: {token!r} (expected L1-L7)")
        required.add(int(m.group(1)))
    if not required:
        raise ValueError("--layers must declare at least one of L1-L7")
    return required


# 「# Layer N:」マーカーで本文を 7 層に分割する。
# 半角/全角コロン・# の個数（# / ##）の揺れを許容する。
def split_layers(text):
    sections = {}
    for n in range(1, 8):
        pattern = (
            rf"#+\s*Layer\s*{n}\s*[:：][^\n]*\n([\s\S]*?)"
            rf"(?=#+\s*Layer\s*{n + 1}\s*[:：]|$)"
        )
        m = re.search(pattern, text)
        sections[n] = m.group(1) if m else None
    return sections


def non_comment_body(body):
    out = []
    for line in body.split("\n"):
        s = line.strip()
        if len(s) > 0 and not s.startswith("#"):
            out.append(line)
    return out


def _block_after_md_heading(lines, idx):
    """markdown 見出し行 idx の配下ブロック (次の見出しまで) を返す。"""
    block = []
    for line in lines[idx + 1:]:
        if MD_ANY_HEADING_RE.match(line):
            break
        block.append(line)
    return block


def _block_after_yaml_key(lines, idx, key_indent):
    """YAML キー行 idx の配下ブロック (同じ以下のインデントの非空行まで) を返す。"""
    block = []
    for line in lines[idx + 1:]:
        stripped = line.strip()
        if stripped and (len(line) - len(line.lstrip(" "))) <= key_indent:
            break
        block.append(line)
    return block


def detect_fixed_procedure_headings(layer5_text):
    """l5-contract v2.0.0 禁止事項: banned 見出し/キー配下の連番列挙 (2 行以上) を検出する。

    実行方式 / ループ / ゴールシークループ (6 ステップのメタ手順) は banned 見出し名に
    該当しないため検出されない (allowlist は構成で担保)。
    戻り値: 違反見出し名のリスト。
    """
    violations = []
    lines = layer5_text.split("\n")
    for i, line in enumerate(lines):
        if any(marker in line for marker in NEGATION_MARKERS):
            continue  # 「固定手順を書かない」等の注意書き
        block = None
        md = MD_BANNED_HEADING_RE.match(line)
        if md:
            block = _block_after_md_heading(lines, i)
        else:
            ym = YAML_BANNED_KEY_RE.match(line)
            if ym:
                block = _block_after_yaml_key(lines, i, len(ym.group(1)))
        if block is None:
            continue
        enum_count = sum(1 for b in block if ENUM_LINE_RE.match(b))
        if enum_count >= 2:
            violations.append(line.strip())
    return violations


def main():
    args = parse_args()
    input_path = args.input
    if not input_path:
        sys.stderr.write("usage: verify-completeness.py --input <prompt.yaml|md> [--layers L1,L2,...]\n")
        sys.exit(2)
    try:
        required_layers = parse_required_layers(args.layers)
    except ValueError as e:
        sys.stderr.write(f"usage: --layers L1,L2,... — {e}\n")
        sys.exit(2)
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    sections = split_layers(text)
    problems = []
    skipped = []

    # 1. 構造網羅: 必須 Layer が存在し本文が空でない。宣言外 Layer は N/A skip。
    for n in range(1, 8):
        body = sections[n]
        present = body is not None and len(non_comment_body(body)) > 0
        if n in required_layers:
            if body is None:
                problems.append(f"Layer {n}: section missing")
            elif not present:
                problems.append(f"Layer {n}: empty body")
        elif not present:
            skipped.append(f"Layer {n}: N/A skip (--layers 宣言外のため必須としない)")

    # 2. ゴールシーク要素: Layer 5 にゴール定義・完了チェックリスト・達成ゴールが在る
    #    (Layer 5 が必須宣言されている場合のみ)
    layer5 = sections[5] or ""
    if 5 in required_layers:
        goal_seek_required = [
            {"key": "ゴール定義", "label": "ゴール定義（目的・背景・達成ゴール）"},
            {"key": "完了チェックリスト", "label": "完了チェックリスト（停止条件）"},
            {"key": "達成ゴール", "label": "達成ゴール（成果状態）"},
        ]
        for r in goal_seek_required:
            if sections[5] is not None and r["key"] not in layer5:
                problems.append(f"Layer 5: {r['label']} がない（ゴールシーク必須要素）")

    # 3a. 固定手順の不在 (legacy): 「思考プロセス」+「ステップN」列挙はゴールシーク違反
    #     実行方式.ループ の箇条書きは許容（「思考プロセス」キーを伴わない）。
    if re.search(r"思考プロセス", layer5) and re.search(r"ステップ\s*[0-9０-９]", layer5):
        problems.append(
            "Layer 5: 固定手順（思考プロセスのステップ列挙）が検出された "
            "— ゴール定義+完了チェックリストに置換すること"
        )

    # 3b. 固定手順の不在 (l5-contract v2.0.0): banned 見出し配下の連番列挙。
    #     Layer 5 の内容が存在する限り、--layers 宣言に関わらず禁止事項として検査する。
    for heading in detect_fixed_procedure_headings(layer5):
        problems.append(
            f"Layer 5: 固定手順（『{heading}』見出し配下の連番列挙）が検出された "
            "— l5-contract v2.0.0 では 5.2 ゴール定義 / 5.3 完了チェックリスト / "
            "5.4 実行方式 (ゴールシークループ) に置換すること"
        )

    if len(problems) > 0:
        sys.stderr.write("FAIL incomplete:\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        sys.exit(1)
    for s in skipped:
        print(f"SKIP {s}")
    verified = ",".join(f"L{n}" for n in sorted(required_layers))
    print(f"OK layers verified ({verified}; goal-seek 要素確認済み / l5-contract v2.0.0)")


if __name__ == "__main__":
    main()

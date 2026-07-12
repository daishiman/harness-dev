#!/usr/bin/env python3
# /// script
# name: generate-sheet
# purpose: ヒアリング結果 JSON から Prompt作成シート（ゴール・完了チェックリスト等）Markdown を生成する
# inputs:
#   - argv: <hearing-result.json> [--output <path>]
#   - file: 位置引数の hearing-result JSON
# outputs:
#   - file/stdout: Prompt作成シート Markdown（--output 指定時はファイル、未指定は stdout）
#   - exit: 0=OK / 1=JSONエラー / 2=引数エラー / 3=ファイル不在
# contexts: [C]
# network: false
# write-scope: output-arg-only
# dependencies: []
# ///
# generate-sheet.py - ヒアリング結果JSONからPrompt作成シートMarkdownを生成
# Usage: python3 generate-sheet.py <hearing-result.json> [--output <path>]
# Exit: 0=成功, 1=一般エラー, 2=引数エラー, 3=ファイル不在
"""generate_sheet.js の python 移植。元の生成ロジック・終了コードを維持する。"""
import json
import os
import sys


def get_arg(name):
    argv = sys.argv
    flag = f"--{name}"
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv) and argv[idx + 1]:
            return argv[idx + 1]
    return None


def generate_sheet(data):
    # ゴールシーク型: 固定手順ではなく達成ゴール（成果状態）を列挙する。
    goals = "\n".join(
        f"{i + 1}. {g if isinstance(g, str) else (g.get('description') or '未定義')}"
        for i, g in enumerate(data.get("goals") or [])
    )

    # 完了チェックリスト（ゴール到達の停止条件）
    checklist_items = []
    for c in data.get("checklist") or []:
        item = c if isinstance(c, str) else (c.get("item") or "未定義")
        judge = ""
        if isinstance(c, dict) and c.get("judgement"):
            judge = f" — 判定: {c['judgement']}"
        checklist_items.append(f"- [ ] {item}{judge}")
    checklist = "\n".join(checklist_items)

    # 成果物フォーマット（ゴールに紐づく場合のみ）
    output_format_items = []
    fmt_idx = 0
    for g in data.get("goals") or []:
        if isinstance(g, dict) and g.get("output_format"):
            output_format_items.append(
                f"## ゴール{fmt_idx + 1}の成果物\n```\n{g['output_format']}\n```"
            )
            fmt_idx += 1
    output_formats = "\n\n".join(output_format_items)

    challenges = "\n".join(f"- {c}" for c in data.get("challenges") or []) or "- 未定義"

    required_info = "\n".join(f"- {r}" for r in data.get("required_info") or []) or "- 未定義"

    # 固定先頭行は l5-contract v2.0.0 追従: 「各ステップ毎」(固定手順前提) ではなく
    # ゴールシークループの周回末アンカー (Step 5=Anchor) を成果物確認点とする。
    constraints = "\n".join(
        ["- 各周回末に中間成果物アンカーを記録し、完了チェックリストで充足を確認する"]
        + [f"- {c}" for c in data.get("constraints") or []]
    )

    test_cases = "\n\n".join(
        f"# 想定するユーザー入力{i + 1}\n```\n{tc.get('input') or '未定義'}\n```\n\n"
        f"# 期待される出力{i + 1}\n```\n{tc.get('expected_output') or '未定義'}\n```"
        for i, tc in enumerate(data.get("test_cases") or [])
    )

    output_formats_block = output_formats or "```\n未定義\n```"
    goals_block = goals or "1. 未定義"
    checklist_block = checklist or "- [ ] 未定義"

    test_cases_fallback = (
        "# 想定するユーザー入力1\n```\n未定義\n```\n\n"
        "# 期待される出力1\n```\n未定義\n```"
    )
    test_cases_block = test_cases or test_cases_fallback

    return f"""# Prompt作成シート

# Next Action
- [ ] フォーマットを具体的な内容で埋める

# プロンプト名
> 素人でもこれを見ただけで分かるこのプロンプトを命名
- {data.get("prompt_name") or "未定義"}

# プロンプトの想定利用者
> このプロンプトを実際に使う人物像や役割
- {data.get("target_user") or "未定義"}

# プロンプト作成の目的
> このプロンプトを作ることで達成したい最終ゴール
- {data.get("purpose") or "未定義"}

# プロンプト作成の背景
> なぜこのプロンプトが必要になったのか、その経緯や状況
- {data.get("background") or "未定義"}

# 完了条件（成功基準）
> どのような状態になれば「このプロンプトは完成した」と判断できるか
- {data.get("success_criteria") or "未定義"}

# 達成ゴール（成果状態）
> 何が出来上がれば到達か。手順ではなく成果状態で記述する。手順は実行時にAIが自律生成する。
{goals_block}

# 完了チェックリスト（ゴール到達の停止条件）
> 第三者がYES/NOで判定できる達成条件。これが満たされるまでAIはゴールに向け反復する。
{checklist_block}

# 成果物フォーマット
> ゴール達成時に出力してほしい形式

{output_formats_block}

# 解決すべき課題
> プロンプトが解消するべき問題点や現状の不便
{challenges}

# 目的を達成するために必要な情報
> プロンプトが高品質な出力を行うために、事前に準備・入力しておくべき具体的な情報。
{required_info}

# 注意点・制約条件
> プロンプト設計時に守るべき条件や避けたい出力
{constraints}

# プロンプトに対する課題
- {data.get("prompt_issues") or "未定義"}

{test_cases_block}
"""


def main():
    argv = sys.argv
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("Usage: python3 generate-sheet.py <hearing-result.json> [--output <path>]")
        print("  Generates Prompt作成シート Markdown from hearing result JSON.")
        print("  If --output is not specified, prints to stdout.")
        print("  Exit codes: 0=OK, 1=error, 2=args error, 3=file not found")
        sys.exit(0 if (len(argv) >= 2 and argv[1] in ("-h", "--help")) else 2)

    input_path = os.path.abspath(argv[1])
    if not os.path.exists(input_path):
        sys.stderr.write(f"[ERROR] File not found: {input_path}\n")
        sys.exit(3)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        sys.stderr.write(f"[ERROR] Invalid JSON: {e}\n")
        sys.exit(1)

    sheet = generate_sheet(data)
    output_path = get_arg("output")

    if output_path:
        resolved_output = os.path.abspath(output_path)
        with open(resolved_output, "w", encoding="utf-8") as f:
            f.write(sheet)
        print(f"[OK] Prompt作成シートを出力: {resolved_output}")
    else:
        sys.stdout.write(sheet)

    sys.exit(0)


if __name__ == "__main__":
    main()

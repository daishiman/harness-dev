#!/usr/bin/env python3
# /// script
# name: validate-sheet
# purpose: Prompt作成シート JSON の必須/推奨/オプション各フィールドの充足度と達成ゴール記述を検証する
# inputs:
#   - argv: <hearing-result.json>
#   - file: 位置引数の hearing-result JSON
# outputs:
#   - stdout: 充足/未充足/警告/ゴール問題サマリと JSON 結果
#   - exit: 0=全充足 / 4=未充足あり / 2=引数エラー / 3=ファイル不在
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
# validate-sheet.py - Prompt作成シートの全フィールド充足度検証
# Usage: python3 validate-sheet.py <hearing-result.json>
# Exit: 0=全充足, 4=未充足あり, 2=引数エラー, 3=ファイル不在
"""validate_sheet.js の python 移植。元の検証ロジック・終了コードを維持する。"""
import json
import os
import re
import sys

# 手順列挙の疑いパターン (l5-contract v2.0.0: goals は成果状態で記述し手順で書かない)
STEP_TOKEN_RE = re.compile(r"(?:ステップ|[Ss]teps?)\s*[0-9０-９]")
INLINE_ENUM_RE = re.compile(r"(?:^|\s)1\s*[.)．、].+2\s*[.)．、]", re.DOTALL)

# 必須フィールド定義
REQUIRED_FIELDS = [
    {"key": "prompt_name", "label": "プロンプト名", "priority": "必須"},
    {"key": "target_user", "label": "想定利用者", "priority": "必須"},
    {"key": "purpose", "label": "目的", "priority": "必須"},
    {"key": "background", "label": "背景", "priority": "必須"},
    {"key": "success_criteria", "label": "完了条件", "priority": "必須"},
    {"key": "goals", "label": "達成ゴール", "priority": "必須", "isArray": True, "minLength": 1},
    {"key": "checklist", "label": "完了チェックリスト", "priority": "推奨", "isArray": True, "minLength": 1},
    {"key": "challenges", "label": "課題", "priority": "必須", "isArray": True, "minLength": 1},
    {"key": "required_info", "label": "必要情報", "priority": "推奨", "isArray": True, "minLength": 1},
    {"key": "constraints", "label": "制約条件", "priority": "推奨", "isArray": True, "minLength": 1},
    {"key": "prompt_issues", "label": "プロンプト課題", "priority": "推奨"},
    {"key": "test_cases", "label": "テストケース", "priority": "オプション", "isArray": True, "minLength": 1},
]


# 達成ゴールの検証（ゴールシーク型: 成果状態で記述され、手順列挙でないこと）
# l5-contract v2.0.0 追従: 空チェックに加え、手順列挙 (ステップN / 連番チェーン) の
# 疑いを検出する（docstring 主張と実装能力の一致）。
def validate_goals(goals):
    issues = []
    if not isinstance(goals, list):
        issues.append({"field": "goals", "message": "配列ではありません"})
        return issues
    for i, goal in enumerate(goals):
        if isinstance(goal, str):
            desc = goal
        elif isinstance(goal, dict):
            desc = goal.get("description") or ""
        else:
            desc = ""
        if not desc or desc.strip() == "":
            issues.append({"field": f"goals[{i}]", "message": f"ゴール{i + 1}の記述が空"})
            continue
        if STEP_TOKEN_RE.search(desc) or INLINE_ENUM_RE.search(desc):
            issues.append(
                {
                    "field": f"goals[{i}]",
                    "message": (
                        f"ゴール{i + 1}が手順列挙の疑い — 成果状態（何が出来上がれば到達か）で"
                        "記述する。手順は実行時に AI が自律生成する"
                    ),
                }
            )
    return issues


def validate(data):
    results = {"filled": [], "missing": [], "warnings": [], "goalIssues": []}

    for field in REQUIRED_FIELDS:
        value = data.get(field["key"])

        if value is None or value == "":
            if field["priority"] == "オプション":
                results["warnings"].append(
                    {"field": field["key"], "label": field["label"], "message": "未入力（オプション）"}
                )
            else:
                results["missing"].append(
                    {"field": field["key"], "label": field["label"], "priority": field["priority"]}
                )
            continue

        if field.get("isArray"):
            min_length = field["minLength"]
            if not isinstance(value, list) or len(value) < min_length:
                current = len(value) if isinstance(value, list) else 0
                results["missing"].append(
                    {
                        "field": field["key"],
                        "label": field["label"],
                        "priority": field["priority"],
                        "message": f"最低{min_length}件必要（現在: {current}件）",
                    }
                )
                continue

        results["filled"].append({"field": field["key"], "label": field["label"]})

    # 達成ゴール詳細検証
    if data.get("goals") is not None and isinstance(data.get("goals"), list):
        results["goalIssues"] = validate_goals(data["goals"])

    return results


def main():
    argv = sys.argv
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("Usage: python3 validate-sheet.py <hearing-result.json>")
        print("  Validates Prompt作成シート field completeness.")
        print("  Exit codes: 0=OK, 2=args error, 3=file not found, 4=validation failed")
        sys.exit(0 if (len(argv) >= 2 and argv[1] in ("-h", "--help")) else 2)

    file_path = os.path.abspath(argv[1])
    if not os.path.exists(file_path):
        sys.stderr.write(f"[ERROR] File not found: {file_path}\n")
        sys.exit(3)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        sys.stderr.write(f"[ERROR] Invalid JSON: {e}\n")
        sys.exit(1)

    results = validate(data)

    # 出力
    print("=== Prompt作成シート 検証結果 ===\n")
    print(f"充足: {len(results['filled'])}/{len(REQUIRED_FIELDS)}")
    print(f"未充足: {len(results['missing'])}")
    print(f"警告: {len(results['warnings'])}")
    print(f"ゴール問題: {len(results['goalIssues'])}\n")

    if len(results["missing"]) > 0:
        print("--- 未充足フィールド ---")
        for m in results["missing"]:
            msg = ": " + m["message"] if m.get("message") else ""
            print(f"  [{m['priority']}] {m['label']} ({m['field']}){msg}")
        print()

    if len(results["warnings"]) > 0:
        print("--- 警告 ---")
        for w in results["warnings"]:
            print(f"  [オプション] {w['label']} ({w['field']}): {w['message']}")
        print()

    if len(results["goalIssues"]) > 0:
        print("--- ゴール詳細問題 ---")
        for s in results["goalIssues"]:
            print(f"  {s['field']}: {s['message']}")
        print()

    # JSON出力（LLMが解釈用）
    print("--- JSON結果 ---")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # 必須フィールドが全て埋まっているかで終了コード決定
    required_missing = [m for m in results["missing"] if m["priority"] == "必須"]
    sys.exit(4 if (len(required_missing) > 0 or len(results["goalIssues"]) > 0) else 0)


if __name__ == "__main__":
    main()

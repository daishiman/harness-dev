#!/usr/bin/env python3
# /// script
# name: scaffold-prompt
# purpose: ヒアリング結果 JSON から7層構造（Layer5 ゴールシーク型）プロンプト骨格を yaml/markdown/json/xml で決定論的に生成する
# inputs:
#   - argv: <hearing-result.json> --format yaml|markdown|json|xml [--agents N] [--output path]
#   - file: 位置引数の hearing-result JSON
# outputs:
#   - file/stdout: 生成した7層骨格（--output 指定時はファイル、未指定は stdout）
#   - stderr: LLM_FILL 統計（自動充填項目数 / LLM必要箇所数）
#   - exit: 0=OK / 1=JSONエラー / 2=引数エラー / 3=ファイル不在
# contexts: [C]
# network: false
# write-scope: output-arg-only
# dependencies: []
# ///
# scaffold-prompt.py - ヒアリングJSONから7層構造プロンプトの骨格を決定論的に生成
# Layer 5 はゴールシーク型（固定手順を持たず、ゴール定義+完了チェックリスト+実行方式）。
# Usage: python3 scaffold-prompt.py <hearing-result.json> --format yaml|markdown|json|xml [--agents N] [--output path]
# Exit: 0=成功, 1=エラー, 2=引数エラー, 3=ファイル不在
"""scaffold_prompt.js の python 移植。元の生成ロジック・終了コードを維持する。"""
import json
import math
import os
import re
import sys


def _parse_int(s):
    # JS parseInt(s, 10) を模倣: 先頭の符号付き整数のみ抽出。解釈不能なら None (NaN 相当)。
    m = re.match(r"\s*([+-]?\d+)", s)
    return int(m.group(1)) if m else None


def get_arg(name):
    argv = sys.argv
    flag = f"--{name}"
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv) and argv[idx + 1]:
            return argv[idx + 1]
    return None


# 7層マッピングテーブル（generate-prompt.md 4.2 を決定論的に実装）
# Prompt作成シート項目 → 7層構造の配置先
# ゴールシーク化: steps（固定手順）は廃止し、goal/checklist（ゴール・完了条件）を配置する。
LAYER_MAPPING = {
    "prompt_name": {"layer": 1, "path": "基本定義.メタ情報.プロジェクトID"},
    "target_user": {"layer": 1, "path": "基本定義.プロジェクト概要.想定利用者"},
    "purpose": {"layer": 1, "path": "基本定義.プロジェクト概要.最上位目的"},
    "background": {"layer": 1, "path": "基本定義.プロジェクト概要.背景コンテキスト"},
    "success_criteria": {"layer": 1, "path": "基本定義.プロジェクト概要.成功基準"},
    # Layer 2: ドメイン定義 - steps内の専門用語・ルールから抽出（LLM判断必要）
    "challenges": {"layer": 2, "path": "ドメイン定義.ビジネスルール.課題"},
    # Layer 4: 共通ポリシー
    "constraints": {"layer": 4, "path": "共通ポリシー.セキュリティ/品質"},
    # Layer 5: エージェントの達成ゴール・完了チェックリスト（固定手順ではない）
    "goal": {"layer": 5, "path": "エージェント定義.エージェント.ゴール定義.達成ゴール"},
    "checklist": {"layer": 5, "path": "エージェント定義.エージェント.完了チェックリスト"},
    # Layer 7
    "test_cases": {"layer": 7, "path": "ユーザーインタラクション"},
    "required_info": {"layer": 7, "path": "ユーザーインタラクション.初回質問の設計材料"},
}


def _slice(arr, idx, total):
    if total == 1:
        return list(arr)
    start = math.floor(idx * len(arr) / total)
    end = math.floor((idx + 1) * len(arr) / total)
    return arr[start:end]


# ヒアリング由来の「達成ゴール候補」を取り出す。
# 後方互換: 旧 steps があれば、その説明を達成ゴールのヒントとして流用する（手順としては展開しない）。
def goal_hints_for(data, idx, total):
    goals = data.get("goals")
    if isinstance(goals, list) and len(goals) > 0:
        sl = _slice(goals, idx, total)
        return [g if isinstance(g, str) else (g.get("description") or "") for g in sl if (g if isinstance(g, str) else (g.get("description") or ""))]
    steps = data.get("steps")
    if isinstance(steps, list) and len(steps) > 0:
        sl = _slice(steps, idx, total)
        return [s.get("description") or "" for s in sl if (s.get("description") or "")]
    return []


# ヒアリング由来の「完了チェックリスト候補」を取り出す。
def checklist_hints_for(data, idx, total):
    checklist = data.get("checklist")
    if isinstance(checklist, list) and len(checklist) > 0:
        sl = _slice(checklist, idx, total)
        return [c if isinstance(c, str) else (c.get("item") or "") for c in sl if (c if isinstance(c, str) else (c.get("item") or ""))]
    return []


# === YAML骨格生成 ===
def scaffold_yaml(data, agent_count):
    constraints = data.get("constraints") or []
    challenges = data.get("challenges") or []
    required_info = data.get("required_info") or []
    test_cases = data.get("test_cases") or []

    # Layer 4 制約条件をYAML形式に
    constraint_lines = "\n".join(
        f'      - ID: "CONST_{str(i + 1).zfill(3)}"\n        内容: "{c}"'
        for i, c in enumerate(constraints)
    )

    # Layer 2 課題をYAML形式に
    challenge_lines = "\n".join(
        f'      - ID: "CHAL_{str(i + 1).zfill(3)}"\n        内容: "{c}"'
        for i, c in enumerate(challenges)
    )

    # Layer 5 エージェントブロック生成（ゴールシーク型）
    agent_blocks = []
    for i in range(agent_count):
        goal_hints = goal_hints_for(data, i, agent_count)
        checklist_hints = checklist_hints_for(data, i, agent_count)

        goal_text = (
            " / ".join(goal_hints)
            if len(goal_hints) > 0
            else "{{LLM_FILL: 何が出来上がれば到達か。成果状態で記述、手順では書かない}}"
        )

        checklist_source = checklist_hints if len(checklist_hints) > 0 else ["{{LLM_FILL: 検証可能な達成条件}}"]
        checklist_lines = "\n".join(
            f'          - 項目: "{item}"\n            判定: "{{{{LLM_FILL: 第三者がYES/NOを判定できる基準}}}}"'
            for item in checklist_source
        )

        input_provider = "外部/ユーザー" if i == 0 else "{{LLM_FILL: 前エージェント名}}"
        output_receiver = "ユーザー" if i == agent_count - 1 else "{{LLM_FILL: 後続エージェント名（並列含む）}}"
        prereq = "なし" if i == 0 else "{{LLM_FILL: 前エージェント名}}"
        successor = "なし" if i == agent_count - 1 else "{{LLM_FILL: 後続エージェント名}}"

        agent_blocks.append(
            f"""    - 番号: {i + 1}
      名前: "{{{{LLM_FILL: 実在する専門家の名前}}}}"

      プロフィール:
        背景: |
          {{{{LLM_FILL: なぜこの人物が適しているか}}}}

      知識ベース:
        参考文献:
          - 書籍: "{{{{LLM_FILL: 書籍名1}}}}"
            適用方法: |
              {{{{LLM_FILL: この知識をゴール達成にどう用いるか}}}}

      ゴール定義:
        目的: |
          {{{{LLM_FILL: このエージェントが存在する目的}}}}
        背景: |
          {{{{LLM_FILL: その目的が必要になった背景・前提}}}}
        達成ゴール: |
          {goal_text}

      完了チェックリスト:
{checklist_lines}
          - 項目: "事実確認: 推測を事実として述べていないか"
            判定: "不確実な情報に限定詞が使われている"

      実行方式:
        方針: |
          固定手順を持たない。ゴール定義と完了チェックリストを唯一の指針とし、
          入力・状況に応じて必要な手順をその都度自ら設計して実行する。
        # ループは goal-seek-paradigm 正本の 6 ステップ（Step 5=Anchor Step）に追従（l5-contract v2.0.0）。
        ループ:
          - "1. 現状評価: 完了チェックリストの未充足項目を特定する（全充足なら完了）"
          - "2. 手順生成: 直前周回の中間成果物（original_goal + merged_directive_for_next）を必須入力に、未充足を解消する手順をその場で立案する"
          - "3. 実行: 立案した手順を実行し、成果物を更新する"
          - "4. 検証: 完了チェックリストで自己評価し、充足項目を更新する"
          - "5. 中間成果物アンカー: 周回末に original_goal（不変）/ current_goal_snapshot / delta_from_original / merged_directive_for_next / drift_signal を記録する"
          - "6. 反復/逸脱: 全項目充足まで 1→5 を反復する（上限: Layer 4 最大反復回数）。上限到達・drift 継続時は逸脱時対応へ"
        逸脱時: |
          {{{{LLM_FILL: 上限到達・解消不能時の対応}}}}

      インターフェース:
        入力:
          - データ名: "{{{{LLM_FILL}}}}"
            提供元: "{input_provider}"
            検証ルール: |
              {{{{LLM_FILL}}}}
        出力:
          - 成果物名: "{{{{LLM_FILL}}}}"
            受領先: "{output_receiver}"
            引き渡し形式: |
              {{{{LLM_FILL: 受け手がそのまま入力として実行できる形式・粒度}}}}

      依存関係:
        前提エージェント:
          - 名前: "{prereq}"
        後続エージェント:
          - 名前: "{successor}"

      ポリシー:
        セキュリティ:
          許可アクション: ["{{{{LLM_FILL}}}}"]
          禁止アクション: ["{{{{LLM_FILL}}}}"]
          データアクセス: "read_write"
        品質基準:
          必須フィールド: ["{{{{LLM_FILL}}}}"]
          信頼度スコア閾値: 0.8"""
        )

    # Layer 7 テストケース
    if len(test_cases) > 0:
        test_case_lines = "\n".join(f'      - "{tc.get("input") or "{{LLM_FILL}}"}"' for tc in test_cases)
    else:
        test_case_lines = '      - "{{LLM_FILL: ユーザー入力例}}"'

    if len(required_info) > 0:
        required_info_lines = "\n".join(f'      - "{r}"' for r in required_info)
    else:
        required_info_lines = '      - "{{LLM_FILL}}"'

    # 課題からLayer 2 ビジネスルールのヒントを生成
    if len(challenges) > 0:
        challenge_hints = "\n".join(f"    # 課題: {c}" for c in challenges)
    else:
        challenge_hints = "    # {{LLM_FILL: 課題から用語・ルールを抽出}}"

    prompt_name = data.get("prompt_name") or "{{プロンプト名}}"
    purpose_short = data.get("purpose")[:60] if data.get("purpose") else "{{1行で概要説明}}"
    constraint_block = constraint_lines or '      - ID: "CONST_001"\n        内容: "{{LLM_FILL}}"'
    challenge_block = challenge_lines or '      - ID: "CHAL_001"\n        内容: "{{LLM_FILL}}"'
    agent_blocks_joined = "\n\n".join(agent_blocks)
    trailing_test = test_case_lines + "\n" if len(test_cases) > 0 else ""

    return f"""# {prompt_name}
# {purpose_short}

# Layer 1: 基本定義層（最上位の不変定義）
基本定義:
  メタ情報:
    プロジェクトID: "{data.get("prompt_name") or "{{プロジェクトID}}"}"

  プロジェクト概要:
    想定利用者: |
      {data.get("target_user") or "{{LLM_FILL: 想定利用者}}"}
    最上位目的: |
      {data.get("purpose") or "{{LLM_FILL: 最上位目的}}"}
    背景コンテキスト: |
      {data.get("background") or "{{LLM_FILL: 背景}}"}
    期待される成果: |
      {{{{LLM_FILL: 期待される成果物・結果}}}}
    成功基準: |
      {data.get("success_criteria") or "{{LLM_FILL: 成功基準}}"}
    スコープ:
      含む: [{{{{LLM_FILL: スコープ}}}}]
      含まない: [{{{{LLM_FILL: 除外範囲}}}}]

# Layer 2: ドメイン定義層（ビジネスロジックの定義）
ドメイン定義:
{challenge_hints}
  用語集:
    "{{{{LLM_FILL: 用語名}}}}":
      定義: |
        {{{{LLM_FILL: 定義}}}}
      使用コンテキスト: ["{{{{LLM_FILL}}}}"]

  ビジネスルール:
    プロセス制約:
{constraint_block}
    課題:
{challenge_block}
    出力制約:
      ID: "OUTPUT_CONST"
      内容: |
        各エージェントの出力タイミングと確認方法を記述

# Layer 3: インフラストラクチャ定義層（外部システムとの接続）
インフラストラクチャ:
  ツール:
    "{{{{LLM_FILL: ツール名}}}}":
      説明: |
        {{{{LLM_FILL: ツールの機能と用途}}}}
      実行条件:
        トリガー条件: ["{{{{LLM_FILL}}}}"]
        スキップ条件: ["{{{{LLM_FILL}}}}"]
      インターフェース:
        パラメータ:
          "{{{{LLM_FILL}}}}":
            既定値: "{{{{LLM_FILL}}}}"
            説明: "{{{{LLM_FILL}}}}"
      エラーハンドリング:
        最大リトライ数: 3
        フォールバック処理: "{{{{LLM_FILL}}}}"

# Layer 4: 共通ポリシー層（横断的関心事）
共通ポリシー:
  システム設定:
    信頼度スコア閾値: 0.8
    最大反復回数: 5

  セキュリティ:
    許可アクション:
      グローバル: ["{{{{LLM_FILL}}}}"]
    禁止アクション:
      グローバル: ["{{{{LLM_FILL}}}}"]

  品質基準:
    事実確認:
      ルール: |
        {{{{LLM_FILL: 推測と事実を区別する方法}}}}
      検証方法: ["{{{{LLM_FILL}}}}"]

  エスカレーション:
    共通条件:
      - "{{{{LLM_FILL}}}}"
    通知先: "ユーザー"

# Layer 5: エージェント定義層（ゴール駆動の自律実行単位）
# 固定手順（ステップ列挙）は持たせない。
# 目的・背景・達成ゴール・完了チェックリストを宣言し、手順は実行方式に委ねる。
エージェント定義:
  共通構造:
    - プロフィール
    - 知識ベース
    - ゴール定義
    - 完了チェックリスト
    - 実行方式
    - インターフェース
    - 依存関係
    - ツール利用
    - ポリシー

  エージェント:
{agent_blocks_joined}

# Layer 6: オーケストレーション層（ゴールシーク制御）
オーケストレーション:
  実行原則: |
    各エージェントは自分の完了チェックリストを唯一の停止条件とし、
    ゴール到達まで手順を自律生成・実行・自己評価する。
    オーケストレーターは固定実行順を持たず、依存関係と現状から
    次に動かすエージェント（直列/並列）を都度決定する。

  選択基準:
    参照元: "Layer 5 各エージェントのゴール定義（目的・達成ゴール）"
    判断方式: "現在未達のゴールに最も寄与するエージェントを選択"
    実行形態: "依存関係に応じて 直列/並列/反復 を都度決定。固定順序を書かない"

  ハンドオフ:
    直列: "前エージェントの出力(受領先)を後続の入力(提供元)に接続"
    並列: "独立ゴールを持つエージェントへ配布し結果を統合"
    統合: "{{{{LLM_FILL: 並列結果のマージ・コンフリクト解決}}}}"

  # goal-seek-paradigm 正本の 6 ステップ（Step 5=Anchor Step）に追従
  ゴールシークループ:
    - "1. 現状評価: 全体ゴール（Layer 1 成功基準）の未達分を特定"
    - "2. 選択: 直前周回の中間成果物（original_goal + merged_directive_for_next）を必須入力に、担当エージェントへ委譲（チェックリスト充足まで）"
    - "3. ハンドオフ: 出力を後続/並列エージェントへ引き渡す"
    - "4. 検証: Layer 1 成功基準で再評価"
    - "5. 中間成果物アンカー: 周回末に original_goal（不変）/ current_goal_snapshot / delta_from_original / merged_directive_for_next / drift_signal を記録"
    - "6. 反復: 未達なら 1→5 を反復"
    上限: "Layer 4 最大反復回数"

  完了判定:
    参照元: "Layer 1 成功基準 + 全エージェントの完了チェックリスト"
    判定方式: "全エージェントのチェックリスト充足 かつ 成功基準の全項目達成で完了"
    未達時: "不足要素を特定し、担当エージェントを再選択"

# Layer 7: ユーザーインタラクション層（初回入力の取得）
ユーザーインタラクション:
  初回質問:
    概要: |
      {{{{LLM_FILL: 初回質問の説明}}}}

    質問:
{required_info_lines}

    回答例:
      - |
        {{{{LLM_FILL: 回答例}}}}
{trailing_test}"""


# === Markdown骨格生成 ===
def scaffold_markdown(data, agent_count):
    agent_sections = []
    for i in range(agent_count):
        goal_hints = goal_hints_for(data, i, agent_count)
        checklist_hints = checklist_hints_for(data, i, agent_count)
        goal_text = (
            " / ".join(goal_hints)
            if len(goal_hints) > 0
            else "{{LLM_FILL: 成果状態で記述。手順では書かない}}"
        )
        checklist_source = checklist_hints if len(checklist_hints) > 0 else ["{{LLM_FILL: 検証可能な達成条件}}"]
        checklist_lines = "\n".join(f"- [ ] {item} — 判定: {{{{LLM_FILL}}}}" for item in checklist_source)
        input_provider = "外部/ユーザー" if i == 0 else "{{LLM_FILL: 前エージェント}}"
        output_receiver = "ユーザー" if i == agent_count - 1 else "{{LLM_FILL: 後続エージェント（並列含む）}}"
        agent_sections.append(
            f"""### エージェント{i + 1}: {{{{LLM_FILL: 名前}}}}

**プロフィール**: {{{{LLM_FILL}}}}

**ゴール定義**
- 目的: {{{{LLM_FILL}}}}
- 背景: {{{{LLM_FILL}}}}
- 達成ゴール: {goal_text}

**完了チェックリスト**（ゴール到達の停止条件）
{checklist_lines}
- [ ] 事実確認: 不確実な情報に限定詞を使用

**実行方式**: 固定手順を持たない。現状評価→手順を都度立案→実行→検証→中間成果物アンカー記録（original_goal 不変+delta_from_original+merged_directive_for_next+drift_signal）→全項目充足まで反復（6 ステップ・Step 5=Anchor。上限: Layer 4 最大反復回数）。

**ハンドオフ**
- 入力(提供元): {input_provider}
- 出力(受領先): {output_receiver}
"""
        )
    agent_sections_joined = "\n".join(agent_sections)

    constraints_md = "\n".join(
        f"- CONST_{str(i + 1).zfill(3)}: {c}" for i, c in enumerate(data.get("constraints") or [])
    ) or "- {{LLM_FILL}}"
    challenges_md = "\n".join(
        f"- CHAL_{str(i + 1).zfill(3)}: {c}" for i, c in enumerate(data.get("challenges") or [])
    ) or "- {{LLM_FILL}}"
    required_info_md = "\n".join(f"- {r}" for r in data.get("required_info") or []) or "- {{LLM_FILL}}"

    return f"""<!-- scaffold-prompt.py auto-generated: Markdown format -->
<!-- LLM_FILL マーカーの箇所をLLMが埋めてください -->

# {data.get("prompt_name") or "{{プロンプト名}}"}

## Layer 1: 基本定義層

### メタ情報
- プロジェクトID: {data.get("prompt_name") or "{{LLM_FILL}}"}

### プロジェクト概要
- **想定利用者**: {data.get("target_user") or "{{LLM_FILL}}"}
- **最上位目的**: {data.get("purpose") or "{{LLM_FILL}}"}
- **背景コンテキスト**: {data.get("background") or "{{LLM_FILL}}"}
- **成功基準**: {data.get("success_criteria") or "{{LLM_FILL}}"}
- **期待される成果**: {{{{LLM_FILL}}}}

## Layer 2: ドメイン定義層

### 用語集
| 用語 | 定義 | 使用コンテキスト |
|------|------|-----------------|
| {{{{LLM_FILL}}}} | {{{{LLM_FILL}}}} | {{{{LLM_FILL}}}} |

### ビジネスルール
{constraints_md}

### 課題
{challenges_md}

## Layer 3: インフラストラクチャ定義層

### ツール定義
| ツール名 | 説明 | トリガー条件 |
|---------|------|-------------|
| {{{{LLM_FILL}}}} | {{{{LLM_FILL}}}} | {{{{LLM_FILL}}}} |

## Layer 4: 共通ポリシー層

### セキュリティ
- 許可アクション: {{{{LLM_FILL}}}}
- 禁止アクション: {{{{LLM_FILL}}}}

### 品質基準
- 事実確認ルール: {{{{LLM_FILL}}}}

### システム設定
- 最大反復回数: 5

## Layer 5: エージェント定義層（ゴール駆動）
> 固定手順は書かない。ゴール定義・完了チェックリストを宣言し、手順は実行方式に委ねる。

{agent_sections_joined}

## Layer 6: オーケストレーション層（ゴールシーク制御）

- **実行原則**: 各エージェントは完了チェックリストを停止条件に、ゴール到達まで手順を自律生成・実行・自己評価
- **選択基準**: 未達ゴールに最も寄与するエージェントを都度選択（固定順序なし）
- **ハンドオフ**: 直列=出力→次の入力に接続 / 並列=配布して結果統合
- **完了判定**: 全エージェントのチェックリスト充足 かつ Layer 1成功基準の全項目達成

## Layer 7: ユーザーインタラクション層

### 初回質問
{required_info_md}

### 回答例
```
{{{{LLM_FILL: 回答例}}}}
```
"""


# === JSON骨格生成 ===
def scaffold_json(data, agent_count):
    agents = []
    for i in range(agent_count):
        goal_hints = goal_hints_for(data, i, agent_count)
        checklist_hints = checklist_hints_for(data, i, agent_count)
        checklist_source = checklist_hints if len(checklist_hints) > 0 else ["{{LLM_FILL}}"]
        agents.append(
            {
                "番号": i + 1,
                "名前": "{{LLM_FILL}}",
                "プロフィール": "{{LLM_FILL}}",
                "ゴール定義": {
                    "目的": "{{LLM_FILL}}",
                    "背景": "{{LLM_FILL}}",
                    "達成ゴール": " / ".join(goal_hints) if len(goal_hints) > 0 else "{{LLM_FILL: 成果状態で記述}}",
                },
                "完了チェックリスト": [{"項目": item, "判定": "{{LLM_FILL}}"} for item in checklist_source],
                "実行方式": {
                    "方針": "固定手順を持たない。ゴールとチェックリストを指針に手順を都度生成・実行・自己評価",
                    "ループ": [
                        "1. 現状評価: 未充足項目を特定",
                        "2. 手順生成: 直前周回の中間成果物(original_goal+merged_directive_for_next)を必須入力に手順を立案",
                        "3. 実行",
                        "4. 検証: チェックリストで自己評価",
                        "5. 中間成果物アンカー: original_goal(不変)/current_goal_snapshot/delta_from_original/merged_directive_for_next/drift_signal を記録",
                        "6. 反復: 全項目充足まで 1→5 を反復（上限: 最大反復回数）",
                    ],
                },
                "インターフェース": {
                    "入力": [{"提供元": "外部/ユーザー" if i == 0 else "{{LLM_FILL}}"}],
                    "出力": [
                        {
                            "受領先": "ユーザー" if i == agent_count - 1 else "{{LLM_FILL}}",
                            "引き渡し形式": "{{LLM_FILL}}",
                        }
                    ],
                },
            }
        )

    scaffold = {
        "layer1_基本定義": {
            "メタ情報": {"プロジェクトID": data.get("prompt_name") or "{{LLM_FILL}}"},
            "プロジェクト概要": {
                "想定利用者": data.get("target_user") or "{{LLM_FILL}}",
                "最上位目的": data.get("purpose") or "{{LLM_FILL}}",
                "背景コンテキスト": data.get("background") or "{{LLM_FILL}}",
                "成功基準": data.get("success_criteria") or "{{LLM_FILL}}",
                "期待される成果": "{{LLM_FILL}}",
            },
        },
        "layer2_ドメイン定義": {
            "用語集": {"{{LLM_FILL: 用語名}}": {"定義": "{{LLM_FILL}}", "使用コンテキスト": ["{{LLM_FILL}}"]}},
            "ビジネスルール": [
                {"ID": f"CONST_{str(i + 1).zfill(3)}", "内容": c} for i, c in enumerate(data.get("constraints") or [])
            ],
            "課題": [
                {"ID": f"CHAL_{str(i + 1).zfill(3)}", "内容": c} for i, c in enumerate(data.get("challenges") or [])
            ],
        },
        "layer3_インフラストラクチャ": {
            "ツール": {"{{LLM_FILL: ツール名}}": {"説明": "{{LLM_FILL}}", "トリガー条件": ["{{LLM_FILL}}"]}},
        },
        "layer4_共通ポリシー": {
            "セキュリティ": {"許可アクション": ["{{LLM_FILL}}"], "禁止アクション": ["{{LLM_FILL}}"]},
            "品質基準": {"事実確認": "{{LLM_FILL}}"},
            "システム設定": {"最大反復回数": 5},
        },
        "layer5_エージェント定義": {"エージェント": agents},
        "layer6_オーケストレーション": {
            "実行原則": "各エージェントはチェックリストを停止条件にゴール到達まで手順を自律生成・実行・自己評価",
            "ハンドオフ": {"直列": "出力→次の入力に接続", "並列": "配布して結果統合"},
            "完了判定": "全エージェントのチェックリスト充足 かつ Layer 1成功基準の全項目達成",
        },
        "layer7_ユーザーインタラクション": {
            "初回質問": data.get("required_info") or ["{{LLM_FILL}}"],
            "回答例": ["{{LLM_FILL}}"],
        },
    }
    return json.dumps(scaffold, ensure_ascii=False, indent=2)


# === XML骨格生成 ===
def scaffold_xml(data, agent_count):
    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    constraints = data.get("constraints") or []

    business_rules = "\n".join(
        f'      <rule id="CONST_{str(i + 1).zfill(3)}"><![CDATA[{esc(c)}]]></rule>'
        for i, c in enumerate(constraints)
    ) or '      <rule id="CONST_001"><![CDATA[{{LLM_FILL}}]]></rule>'

    challenges_xml = "\n".join(
        f'      <challenge id="CHAL_{str(i + 1).zfill(3)}"><![CDATA[{esc(c)}]]></challenge>'
        for i, c in enumerate(data.get("challenges") or [])
    ) or '      <challenge id="CHAL_001"><![CDATA[{{LLM_FILL}}]]></challenge>'

    agents_xml_parts = []
    for i in range(agent_count):
        goal_hints = goal_hints_for(data, i, agent_count)
        checklist_hints = checklist_hints_for(data, i, agent_count)
        goal_text = " / ".join(goal_hints) if len(goal_hints) > 0 else "{{LLM_FILL: 成果状態で記述}}"
        checklist_source = checklist_hints if len(checklist_hints) > 0 else ["{{LLM_FILL}}"]
        checklist_xml = "\n".join(
            f'        <item judgement="{{{{LLM_FILL}}}}"><![CDATA[{esc(item)}]]></item>'
            for item in checklist_source
        )
        input_from = "外部/ユーザー" if i == 0 else "{{LLM_FILL}}"
        output_to = "ユーザー" if i == agent_count - 1 else "{{LLM_FILL}}"
        agents_xml_parts.append(
            f"""    <agent number="{i + 1}" name="{{{{LLM_FILL}}}}">
      <profile><![CDATA[{{{{LLM_FILL}}}}]]></profile>
      <goal>
        <purpose><![CDATA[{{{{LLM_FILL}}}}]]></purpose>
        <background><![CDATA[{{{{LLM_FILL}}}}]]></background>
        <target-state><![CDATA[{esc(goal_text)}]]></target-state>
      </goal>
      <completion-checklist>
{checklist_xml}
      </completion-checklist>
      <execution-mode><![CDATA[固定手順なし。現状評価→手順を都度立案→実行→検証→中間成果物アンカー記録(original_goal不変/current_goal_snapshot/delta_from_original/merged_directive_for_next/drift_signal)→全項目充足まで反復(6ステップ・Step 5=Anchor。上限: 最大反復回数)]]></execution-mode>
      <handoff>
        <input from="{input_from}"/>
        <output to="{output_to}"/>
      </handoff>
    </agent>"""
        )
    agents_xml = "\n".join(agents_xml_parts)

    initial_questions = "\n".join(
        f"      <question><![CDATA[{esc(r)}]]></question>"
        for r in (data.get("required_info") or ["{{LLM_FILL}}"])
    )

    prompt_name = esc(data.get("prompt_name") or "{{プロンプト名}}")
    project_id = esc(data.get("prompt_name") or "{{LLM_FILL}}")
    target_user = data.get("target_user") or "{{LLM_FILL}}"
    purpose = data.get("purpose") or "{{LLM_FILL}}"
    background = data.get("background") or "{{LLM_FILL}}"
    success_criteria = data.get("success_criteria") or "{{LLM_FILL}}"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<prompt name="{prompt_name}">

  <layer1 name="基本定義層">
    <meta>
      <project-id>{project_id}</project-id>
    </meta>
    <overview>
      <target-user><![CDATA[{target_user}]]></target-user>
      <purpose><![CDATA[{purpose}]]></purpose>
      <background><![CDATA[{background}]]></background>
      <success-criteria><![CDATA[{success_criteria}]]></success-criteria>
      <expected-outcome><![CDATA[{{{{LLM_FILL}}}}]]></expected-outcome>
    </overview>
  </layer1>

  <layer2 name="ドメイン定義層">
    <glossary>
      <term name="{{{{LLM_FILL}}}}">
        <definition><![CDATA[{{{{LLM_FILL}}}}]]></definition>
      </term>
    </glossary>
    <business-rules>
{business_rules}
    </business-rules>
    <challenges>
{challenges_xml}
    </challenges>
  </layer2>

  <layer3 name="インフラストラクチャ定義層">
    <tools>
      <tool name="{{{{LLM_FILL}}}}">
        <description><![CDATA[{{{{LLM_FILL}}}}]]></description>
      </tool>
    </tools>
  </layer3>

  <layer4 name="共通ポリシー層">
    <security>
      <allowed-actions>{{{{LLM_FILL}}}}</allowed-actions>
      <prohibited-actions>{{{{LLM_FILL}}}}</prohibited-actions>
    </security>
    <quality>
      <fact-check><![CDATA[{{{{LLM_FILL}}}}]]></fact-check>
    </quality>
    <system><max-iterations>5</max-iterations></system>
  </layer4>

  <layer5 name="エージェント定義層">
{agents_xml}
  </layer5>

  <layer6 name="オーケストレーション層">
    <execution-principle><![CDATA[各エージェントはチェックリストを停止条件にゴール到達まで手順を自律生成・実行・自己評価]]></execution-principle>
    <handoff serial="出力→次の入力に接続" parallel="配布して結果統合"/>
    <completion-criteria><![CDATA[全エージェントのチェックリスト充足 かつ Layer 1成功基準の全項目達成]]></completion-criteria>
  </layer6>

  <layer7 name="ユーザーインタラクション層">
    <initial-questions>
{initial_questions}
    </initial-questions>
    <answer-examples>
      <example><![CDATA[{{{{LLM_FILL}}}}]]></example>
    </answer-examples>
  </layer7>

</prompt>
"""


SCAFFOLDERS = {
    "yaml": scaffold_yaml,
    "markdown": scaffold_markdown,
    "json": scaffold_json,
    "xml": scaffold_xml,
}


def main():
    argv = sys.argv
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("Usage: python3 scaffold-prompt.py <hearing-result.json> --format yaml|markdown|json|xml [--agents N] [--output path]")
        print("  Generates 7-layer (goal-seek) prompt scaffold from hearing result JSON.")
        print("  Layer 5 agents declare goal + checklist (no fixed steps).")
        print("  {{LLM_FILL}} markers indicate sections requiring LLM creative input.")
        print("  Exit codes: 0=OK, 1=error, 2=args error, 3=file not found")
        sys.exit(0 if (len(argv) >= 2 and argv[1] in ("-h", "--help")) else 2)

    input_path = os.path.abspath(argv[1])
    if not os.path.exists(input_path):
        sys.stderr.write(f"[ERROR] File not found: {input_path}\n")
        sys.exit(3)

    fmt = get_arg("format")
    if not fmt or fmt not in SCAFFOLDERS:
        sys.stderr.write("[ERROR] --format required: yaml|markdown|json|xml\n")
        sys.exit(2)

    # JS parseInt(x, 10) 相当: 先頭の整数部分のみ解釈し、非数値なら NaN→比較 false。
    agent_count = _parse_int(get_arg("agents") or "1")
    if agent_count is None or agent_count < 1:
        sys.stderr.write("[ERROR] --agents must be >= 1\n")
        sys.exit(2)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        sys.stderr.write(f"[ERROR] Invalid JSON: {e}\n")
        sys.exit(1)

    scaffold = SCAFFOLDERS[fmt](data, agent_count)
    output_path = get_arg("output")

    if output_path:
        resolved = os.path.abspath(output_path)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(scaffold)
        print(f"[OK] 7層骨格を出力: {resolved}")
        print("[INFO] {{LLM_FILL}} マーカー箇所をLLMが埋めてください")
    else:
        sys.stdout.write(scaffold)

    # LLM_FILL統計
    fill_count = len(re.findall(r"\{\{LLM_FILL[^}]*\}\}", scaffold))
    filled_count = len([k for k in LAYER_MAPPING if data.get(k) and data.get(k) != ""])
    sys.stderr.write(f"\n[STATS] 自動充填: {filled_count}項目, LLM必要: {fill_count}箇所\n")

    sys.exit(0)


if __name__ == "__main__":
    main()

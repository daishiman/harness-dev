---
name: section-completeness-rules
description: intake.md の各セクションの「必要十分」基準
type: reference
---

# セクション必要十分ルール

> 【重要】本ファイルは `references/section_canonical_map.json` (schema_version 2.0.0, §0〜§11 の12章) の**人間可読ガイド(派生・非機械)**であり正本ではない。機械検証の正本は `section_canonical_map.json`、実装は `scripts/check_completeness.py`。章の必要十分の唯一正本は canonical_map の `required_fields` / `absence_behavior` である。本ファイルの記述と canonical_map が食い違う場合は canonical_map を正とする。

ヒアリングシート `intake.md` の各セクションは以下の必要十分基準を満たす。これらは canonical_map の `required_fields` として機械検証される(実装: `scripts/check_completeness.py`)。`scripts/render-intake-final.py` は展開のみを担い、機械検証は canonical_map required_fields に一本化される。

## 必要十分の構成要素

各セクションは以下を含む。

| 要素 | 個数 | 用途 |
|------|------|------|
| 図解 | 1〜3 | 視覚化 |
| 説明文 | 200 字 | 文脈と意図 |
| 質問 | 2〜3 | ヒアリング質問の正本 |
| 選択肢 | 3〜7 ＋「その他」＋「わからない」 | option-presenter 用 |
| サンプル | 1 | google-forms-generator の例 |
| アンチパターン | 1 | 失敗例 |
| 補足（任意） | 0〜1 | 注意事項 |

## セクション一覧（intake.md の章構成）

| # | セクション名 | 主な内容 |
|---|--------------|----------|
| 1 | 目的 | stated / excavated / jtbd |
| 2 | ユーザー像 | user_profile 6 軸 |
| 3 | 5 軸回答 | 出力先・情報源・共有相手・真の課題 |
| 4 | 外部連携 | integration-catalog から選択 |
| 5 | 想定フロー | 起動から完了までの流れ |
| 6 | 価値・KPI | 時間短縮／品質向上／露出 |
| 7 | 既存スキル類似 | similar_skills |
| 7.5 | ナレッジ資産（MUST） | knowledge_assets |
| 8 | 未解決事項 | open_questions |

### 本ファイル9章体系 → canonical_map 12章 (§0〜§11) 対応表

本ファイルの9章 (旧体系) は正本ではない。以下は canonical_map の `section_key` へのマップである。canonical_map にのみ存在する章 (§0/§7/§9/§10/§11) は本ファイル未収載であり、正本は canonical_map を参照すること。

| 本ファイル # | canonical §key |
|---|---|
| 1 目的 | §3 `3_purpose_excavator` |
| 2 ユーザー像 | §2 `2_user_profile` |
| 3 5軸回答 | §6 `6_five_axes_summary` (input_from/output_to は §6 `intent_contract` から派生) |
| 4 外部連携 | §4 `4_option_presenter` (connectors) |
| 5 想定フロー | §5 `5_visualizer` |
| 6 価値・KPI | §1 `1_assumption_challenger` (time_freed_intent) / §10 `10_self_updater` (value_realized_score) |
| 7 既存スキル類似 | §3 `3_purpose_excavator` (differentiation) |
| 7.5 ナレッジ資産 | §6 `6_five_axes_summary` (axes[knowledge_asset] / knowledge_pipeline) |
| 8 未解決事項 | §8 `8_open_questions` |
| (本ファイル未収載) | §0 `0_executive_summary` / §7 `7_design_decisions` / §9 `9_handoff_contract` / §11 `11_artifact_index` |

---

## 各セクションの必要十分

### 1. 目的

| 要素 | 内容 |
|------|------|
| 図解 | mindmap（表層→深層）または flowchart |
| 説明文 | 「stated と excavated の差を強調する」200 字 |
| 質問 | 「最初の言葉と本当の理由は同じですか？」「次の朝に何が違っていますか？」「これが解決したら次は？」 |
| 選択肢 | （JTBD 雛形を選択肢化）|
| サンプル | google-forms-generator の jtbd |
| アンチパターン | 「とりあえず作りたい」型 |

### 2. ユーザー像

| 要素 | 内容 |
|------|------|
| 図解 | persona-card（独自 SVG） |
| 説明文 | 6 軸の意義 200 字 |
| 質問 | 「ご自身の業種は？」「コードは書けますか？」「これは仕事？個人？」 |
| 選択肢 | 熟練度 3／役割 4／文脈 4／共有意図 4 |
| サンプル | 中級・個人事業主・業務・不特定多数 |
| アンチパターン | 「他の人もやってる」型 |

### 3. 5 軸回答

| 要素 | 内容 |
|------|------|
| 図解 | comparison-table（5 軸 × 深度） |
| 説明文 | 5 軸の意義 200 字 |
| 質問 | 「どこに出る？」「どこから取る？」「誰に届く？」「何が浮く？」 |
| 選択肢 | 各軸 4〜7 択 |
| サンプル | google-forms 5 軸 |
| アンチパターン | 「一人でできる」型 |

### 4. 外部連携

| 要素 | 内容 |
|------|------|
| 図解 | icon-grid（連携先一覧） |
| 説明文 | 「制約に応じた候補」200 字 |
| 質問 | 「Google アカウント使える？」「他に普段使うサービスは？」 |
| 選択肢 | integration-catalog 全 13 サービスからフィルタ |
| サンプル | Forms + Sheets + Drive |
| アンチパターン | 「全部自動化」型 |

### 5. 想定フロー

| 要素 | 内容 |
|------|------|
| 図解 | numbered-steps（非技術者）／flowchart（中級以上） |
| 説明文 | 起動契機→処理→結果の流れ 200 字 |
| 質問 | 「いつ起動？」「処理中に確認する？」「終わったら何が手元に？」 |
| 選択肢 | 起動契機 4 種、確認形態 3 種 |
| サンプル | 「告知 3 日前→対話→Forms 生成→クリップボード」 |
| アンチパターン | 「マルチスキル混在」型 |

### 6. 価値・KPI

| 要素 | 内容 |
|------|------|
| 図解 | before-after（独自 SVG） |
| 説明文 | Output と Outcome の区別 200 字 |
| 質問 | 「いま何分？」「何になる？」「浮いた時間で何？」 |
| 選択肢 | 時間／品質／露出 のいずれか以上 |
| サンプル | 90 分→10 分、月 320 分削減 |
| アンチパターン | 「便利にしたい」型 |

### 7. 既存スキル類似

| 要素 | 内容 |
|------|------|
| 図解 | quadrant（類似度 × 独自性） |
| 説明文 | 流用／拡張／新規 の判定 200 字 |
| 質問 | 「既存の同じようなスキル、知ってますか？」 |
| 選択肢 | 既存スキル名 + 「知らない」 |
| サンプル | google-forms-generator 既存→拡張提案 |
| アンチパターン | 重複作成 |

### 7.5 ナレッジ資産（MUST）

| 要素 | 内容 |
|------|------|
| 図解 | flowchart（取り込み→解析→保存→検索） |
| 説明文 | ナレッジ資産軸の意義 200 字 |
| 質問 | 「考え方をスキルに食わせる必要は？」「既存ナレッジは？」「外部参照ファイル不在時は (a) 停止/(b) 警告継続/(c) 既定値生成 どれ？」「上流スキル資産は (a) 都度同期/(b) 凍結/(c) hash 差分 どれで追従？」 |
| 選択肢 | 不在時挙動 3 択 + 上流連携 3 択 + 「該当なし」 |
| サンプル | 「Notion 過去 30 本 + 書籍 2 冊。不在時=停止。上流=hash 差分」 |
| アンチパターン | 「不在時挙動が未決定のまま生成へ進む」型 |

**追加完全性条件**:

- 外部リソースを参照する場合、各リソースについて「不在時挙動が決定済」（block / warn-fallback / default-generate のいずれかが明示）
- 上流スキル資産を参照する場合、追従ポリシー（都度同期／凍結／hash 差分）が明示

### 8. 未解決事項

| 要素 | 内容 |
|------|------|
| 図解 | traffic-light（解決状態） |
| 説明文 | blocking / deferred の区別 200 字 |
| 質問 | 「いま決められないことは？」 |
| 選択肢 | 「無し」「後で決める」「harness-creator に任せる」 |
| サンプル | 「フォーム閉鎖後の自動アーカイブは v2」 |
| アンチパターン | 「完璧主義」型 |

---

## 検証ルール

```javascript
function checkSection(section) {
  return {
    diagrams:    section.visualizations.length >= 1 && section.visualizations.length <= 3,
    description: section.description.length >= 100 && section.description.length <= 300,
    questions:   section.questions.length >= 2 && section.questions.length <= 3,
    options:     section.options.length >= 3 && section.options.length <= 7
              && section.options.includes("その他")
              && section.options.includes("わからない"),
    sample:       !!section.sample,
    anti_pattern: !!section.anti_pattern
  };
}
```

上記は人間可読の概念図であり、機械検証の正本ではない。実際の PASS/FAIL は canonical_map の `required_fields` / `absence_behavior` として機械検証される(実装: `scripts/check_completeness.py`)。

## 一括テンプレ展開

`scripts/render-intake-final.py` が `intake-final-template.md.tmpl` を context で展開する(展開のみ)。SubAgent が各 phase JSON を埋め、必要十分の機械検証は canonical_map required_fields に一本化される。

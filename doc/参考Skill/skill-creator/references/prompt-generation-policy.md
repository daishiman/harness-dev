# エージェントプロンプト生成ポリシー

skill-creatorがエージェントプロンプトを生成する際、prompt-creatorスキルの7層構造Markdownフォーマットを使用して生成するためのポリシー定義。

---

## Layer 1: 基本定義層

### プロジェクト概要

- **最上位目的**: skill-creatorが生成する全てのエージェントプロンプトを、prompt-creatorスキルの7層Markdownフォーマットで統一的に生成し、品質と再現性を確保する
- **背景コンテキスト**: エージェントプロンプトの品質はスキル全体の実行品質を決定する。フォーマットが統一されていない場合、エージェント間のI/O不整合・責務の肥大化・保守性の低下が発生する。prompt-creatorの7層構造を標準フォーマットとすることで、これらの問題を構造的に解決する
- **成功基準**:
  - 全エージェントプロンプトが7層Markdownフォーマットに準拠している
  - 各プロンプトがSRP 3テスト（説明・変更理由・入出力）に合格している
  - 各プロンプトが5000文字以内に収まっている
  - マルチエージェント構成時、data-contract.mdでI/Oが一元管理されている
- **スコープ**:
  - 含む: agents/*.md、agents/steps/*.mdの生成・改善・フォーマット変換
  - 含まない: SKILL.md（skill-creator独自フォーマット）、references/*.md、data-contract.md

---

## Layer 2: ドメイン定義層

### 用語集

| 用語 | 定義 |
|------|------|
| 7層Markdownフォーマット | prompt-creatorが定義するLayer 1〜7の階層構造。各LayerはMarkdownの`##`見出しで区切る |
| SRP（単一責務原則） | 1プロンプト=1責務。説明テスト・変更理由テスト・入出力テストの3テストで判定 |
| 5000文字上限 | 1プロンプトファイルあたりの本文上限。超過時は構成パターンで分割 |
| 構成パターン | プロンプト分割の4パターン: A（Step分割）、B（パイプライン）、C（SubAgent並列）、D（単一完結） |
| Layer 5サブセット | coordinatorの子Stepが使用する簡略フォーマット。プロフィール・実行仕様・I/O・依存関係のみ |

### 評価基準

#### SRP 3テスト

| テスト | 合格条件 | 不合格例 |
|--------|----------|----------|
| **説明テスト** | 「このプロンプトは◯◯する」と1文で説明できる | 「◯◯して、かつ△△もする」（動詞2つ以上） |
| **変更理由テスト** | 変更する理由が1種類しかない | I/O仕様変更とUI変更が同じファイルに影響 |
| **入出力テスト** | 入力→処理→出力が1つの流れ | 複数の独立した入出力パスが存在 |

### ビジネスルール

- **RULE_001**: agents/*.md（トップレベル）はprompt-creatorで7層Markdown全層を生成する
- **RULE_002**: agents/steps/*.md（サブStep）はprompt-creatorでLayer 5サブセットを生成する
- **RULE_003**: 1プロンプトあたり5000文字を超過する場合、責務を分割する
- **RULE_004**: マルチエージェント構成時、data-contract.mdをI/OのSingle Source of Truthとして作成する
- **RULE_005**: SKILL.md・references/*.mdはskill-creatorが直接生成する（prompt-creator不使用）

---

## Layer 3: インフラストラクチャ定義層

### ツール

| ツール | 用途 | 使用タイミング |
|--------|------|---------------|
| prompt-creator skill | 7層Markdownプロンプトの生成・改善 | エージェントプロンプト生成時 |
| Read | 既存プロンプト・テンプレートの読み込み | 改善・参照時 |
| Write | 生成したプロンプトの保存 | 生成完了後 |
| Bash（`wc -m`） | プロンプトの文字数計測 | 品質チェック時 |

---

## Layer 4: 共通ポリシー層

### 品質基準

生成されたプロンプトは以下4カテゴリの全項目を満たすこと。

#### 構造チェック

- [ ] 7層Markdownフォーマットに準拠（またはsub-stepのLayer 5サブセット）
- [ ] 各Layerの必須セクションが存在する
- [ ] 内部参照（相対パス）がリンク切れしていない

#### 責務チェック

- [ ] 説明テスト合格: 1文で責務を説明できる
- [ ] 変更理由テスト合格: 変更理由が1種類のみ
- [ ] 入出力テスト合格: 入力→処理→出力が1つの流れ

#### 文字数チェック

- [ ] 本文が5000文字以内
- [ ] 超過している場合は構成パターンで分割済み

#### 連携チェック（マルチエージェント時）

- [ ] data-contract.mdが定義されている
- [ ] 各エージェントのI/Oがdata-contractのフィールド順序と一致
- [ ] coordinator → agent → stepの依存関係が明示されている

### 出力評価基準

評価優先度: SRP準拠 > フォーマット準拠 > 文字数制限

| 項目 | 合格条件 | 不合格時アクション |
|------|----------|-------------------|
| SRP 3テスト | 3テスト全合格 | 責務を分割して再生成 |
| 7層フォーマット | 全必須Layerが存在 | prompt-creatorで再生成 |
| 文字数 | 5000文字以内 | 構成パターンで分割 |
| I/O整合性 | data-contractと一致 | フィールド順序を修正 |

**最大改善回数**: 3回

---

## Layer 5: エージェント定義層

### プロフィール

- **役割**: エージェントプロンプト生成コントローラー
- **背景**: skill-creatorのワークフロー内で、エージェントプロンプトの設計→粒度判定→prompt-creator呼び出し→品質検証を一貫して制御する
- **目的**: 入力された責務定義とI/O仕様から、7層Markdown準拠・SRP合格・5000文字以内のプロンプトを生成する
- **責務**: 粒度判定、prompt-creator連携、品質チェック、ファイル保存

### 実行仕様

#### 思考プロセス

**Step 1: 粒度判定**

1. エージェントの責務を箇条書きで列挙
2. SRP 3テストを実施
3. 責務が2つ以上 → 責務ごとに分割
4. 5000文字に収まるか見積もり → 超過見込みならStep 2へ

**完了条件**: 各プロンプトの責務が1つに確定し、5000文字以内の見積もり

**Step 2: 構成パターン選択**

```
Q1: 順次実行か並列実行か？
  → 並列 → パターンC（SubAgent並列）
  → 順次 → Q2へ

Q2: ユーザー対話を含むか？
  → 対話あり → パターンA（Step分割）
  → 対話なし → Q3へ

Q3: 1方向のデータ変換か？
  → はい → パターンB（パイプライン）
  → いいえ → パターンA（Step分割）
```

| パターン | 構成 | 使用場面 |
|---------|------|---------|
| D: 単一完結 | single-agent.md | 責務1つ・5000文字以内 |
| A: Step分割 | coordinator.md + steps/step*.md | 順次実行の対話フロー |
| B: パイプライン | collector → processor → formatter | データ変換チェーン |
| C: SubAgent並列 | orchestrator.md + sub-agents/*.md | 独立した並列処理 |

**完了条件**: 構成パターンが確定している

**Step 3: prompt-creator呼び出し**

各プロンプトについてprompt-creatorを起動:

```
- 形式: Markdown
- 構造: 7層アーキテクチャ
- 文字数制限: 5000文字/プロンプト
- Layer省略: sub-stepの場合はLayer 5サブセットを指定
- 参照: 既存の同種エージェントがあればFew-shot例として提供
```

トップレベル/SubAgent → 7層全層（Layer 1〜7）で生成
sub-step → Layer 5サブセット（プロフィール・実行仕様・I/O・依存関係）で生成

**完了条件**: prompt-creatorが7層Markdownプロンプトを生成

**Step 4: 品質検証**

1. Layer 4の品質基準（4カテゴリ）を全て確認
2. `wc -m` で文字数を計測
3. 不合格項目があれば修正して再検証（最大3回）
4. マルチエージェント構成時、data-contract.mdとのI/O整合性を確認

**完了条件**: 全品質チェック項目に合格

### インターフェース

#### 入力

| データ名 | 提供元 | 説明 |
|---------|--------|------|
| responsibility_definition | skill-creator | エージェントの責務定義（1文） |
| io_specification | skill-creator | 入力データ・出力データの仕様 |
| dependencies | skill-creator | 前提・後続エージェントとの依存関係 |
| reference_knowledge | skill-creator | 参照すべきナレッジ・原則 |
| prompt_type | skill-creator | `top-level` / `sub-agent` / `sub-step` |

#### 出力

| 成果物 | 受領先 | 説明 |
|--------|--------|------|
| generated_prompt | skill-creator | 7層Markdown形式のプロンプトファイル |
| quality_report | skill-creator | 品質チェック結果（PASS/FAIL + 詳細） |
| data_contract | skill-creator | マルチエージェント時のI/O仕様（該当時のみ） |

---

## Layer 6: オーケストレーション層

### 実行原則

Step 1〜2（粒度判定・パターン選択）は前処理として連続実行する。
Step 3（prompt-creator呼び出し）はマルチエージェント構成時、各プロンプトを並列で生成可能。
Step 4（品質検証）はStep 3完了後に順次実行する。

### 実行フロー

| フェーズ | 内容 | 完了条件 |
|----------|------|----------|
| Step 1 | 粒度判定 | 各プロンプトの責務が1つに確定 |
| Step 2 | 構成パターン選択 | パターンA〜Dが確定 |
| Step 3 | prompt-creator呼び出し | 7層Markdownプロンプトが生成 |
| Step 4 | 品質検証 | 全品質チェック項目に合格 |

### 新規生成 / 改善 / マルチエージェントの分岐

| シナリオ | フロー |
|---------|--------|
| 新規・単一 | Step 1→3→4 |
| 新規・マルチ | Step 1→2→data-contract作成→Step 3（並列）→Step 4 |
| 改善 | 既存プロンプト分析→SRP/文字数/フォーマット判定→Step 3（improve-prompt）→Step 4 |

---

## Layer 7: ユーザーインタラクション層

### 起動方法

本ポリシーはskill-creatorの内部プロセスとして適用される。skill-creatorがエージェントプロンプトを生成する際、以下のタイミングで参照する:

1. **新規スキル作成時**: Phase 3（設計）でエージェント構成を決定後、本ポリシーのStep 1〜4を実行
2. **既存スキル改善時**: improve-promptモードで本ポリシーの改善フローを適用
3. **マルチエージェント設計時**: design-orchestration.mdと連携し、data-contract + 各プロンプトを生成

### prompt-creator呼び出し時の入力テンプレート

```
エージェントプロンプトを生成してください。

## 仕様
- 責務: {{responsibility_definition}}
- 種別: {{prompt_type}}（top-level / sub-agent / sub-step）
- 形式: Markdown、7層構造
- 文字数制限: 5000文字以内

## I/O仕様
### 入力
{{io_specification.input}}

### 出力
{{io_specification.output}}

## 依存関係
{{dependencies}}

## 参照ナレッジ
{{reference_knowledge}}

## 制約
- sub-stepの場合はLayer 5サブセット（プロフィール・実行仕様・I/O・依存関係）のみ
- 既存の同種エージェントがあれば構造を参考にする
```

### 適用事例（Few-shot）

ubm-goal-settingスキルで本ポリシーを適用した結果:

| ファイル | 種別 | 層 | 文字数 |
|---------|------|-----|--------|
| phase3-coordinator.md | coordinator | 全層 | 約4500 |
| steps/step1〜5.md | sub-step | Layer 5サブセット | 約2000〜3000 |
| info-collector.md | SubAgent | 全層 | 約4000 |
| output-formatter.md | SubAgent | 全層 | 約4500 |

設計判断: coordinator+5 stepはパターンA、SubAgentはパターンD、Phase間I/OはData Contract。

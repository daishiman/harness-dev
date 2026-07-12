# prompt-creator 用途プロンプト（単一集約版）

> **これは何か**: `plugins/prompt-creator/` に散在する「prompt-creator 自身を定義するプロンプト群」（生成プロンプト `R1-main.md` / 7 層フォーマット / L5 契約 / 記述スタイル / 冪等更新 / 品質 4 パス / C1-C4 評価基準）を、**1 枚の貼り付け可能な用途プロンプト**へ集約したドキュメント。冒頭で参照した `/plugin-dev-plan` 用途プロンプトと同じ「① 起動 → ② 構造化プロンプト本体」形式に揃える。
>
> **位置づけ (SSOT 非置換)**: 本ファイルは各正本の**可搬な集約・読み物**であり、機械検証・drift 追跡の正本ではない。逐語再掲でなく統合記述とし、権威定義は下表の各正本を参照する（正本更新時は本ファイルを追従）。lint-ssot-duplication の DUP-PASSAGE を避けるため、定義本体は正本へ参照化している。

## SSOT 正本対応表（本書の各節 → 権威ソース）

| 本書の節 | 権威正本 (これが SSOT) |
|---|---|
| ② Layer 1-7 本体 / 生成プロンプト | `skills/run-prompt-creator-7layer/prompts/R1-main.md` |
| 付録 A 7 層フォーマット / DDD マッピング | `skills/run-prompt-creator-7layer/references/seven-layer-format.md` |
| 付録 A Layer 5 契約 (l5-contract v2.0.0) | `seven-layer-format.md`「Layer 5 契約」節 |
| 付録 B 記述スタイル | `skills/run-prompt-creator-7layer/references/writing-style-principles.md` |
| 付録 B 冪等更新・セッション分離 | `skills/run-prompt-creator-7layer/references/idempotent-update-policy.md` |
| 付録 B 品質 4 パス・原子性・動的評価 | `skills/run-prompt-creator-7layer/references/quality-criteria.md` |
| 付録 B C1-C4 設計評価 | `skills/assign-prompt-design-evaluator/references/c1-c4-criteria.md` |
| 付録 C SubAgent ハイブリッド契約 | `skills/run-prompt-creator-7layer/references/subagent-hybrid-format.md` |
| フロー / フェーズ / 完了条件 | `skills/run-prompt-creator-7layer/SKILL.md` |
| ゴールシーク 6 ステップ正本 | `plugins/harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md` |

---

## ① 起動方法（まずこれを打つ）

prompt-creator は「7 層構造プロンプトを生成・更新する」メタスキル。実態は `run-prompt-create`（オーケストレータ）が `run-prompt-elicit`（ヒアリング）→ `run-prompt-creator-7layer`（Layer 単位生成）→ `assign-prompt-design-evaluator`（C1-C4 設計ゲート）を束ねる。

### 新規プロンプトをヒアリングから作る場合

```bash
/run-prompt-create "<作りたいプロンプトの用途を自然文で>"
```

会話で Prompt 作成シート（目的 / 背景 / 完了条件 / 想定利用者 / ドメイン用語 / 制約 / ゴール材料 / 出力フォーマット / ハンドオフ / 想定入力例 / evaluation_priorities）を埋め、7 層プロンプト（Markdown 既定）+ `prompt-build-trace.json` を生成する。

### 既存プロンプトを改善する場合（冪等更新）

```bash
/run-prompt-creator-7layer --responsibility-id <R-id> --output <path> --skill-brief <brief.json>
```

既存を**闇雲に追加せず**、原子要素へ分解 → 類似は上書き統合・無ければ新規（重複ゼロ）で更新する（付録 B「冪等更新」）。

### SubAgent (`agents/*.md`) を作る場合

frontmatter（plugin YAML）+ 本文 7 層のハイブリッド形式で生成する（付録 C）。生成は `run-build-skill` が本スキルを必ず経由し、直後に `lint-agent-prompt-content.py` を fail-closed ゲートで走らせる。

---

## ② prompt-creator 本体プロンプト（7 層・ドッグフーディング）

> 以下は prompt-creator 自身を、それが教える 7 層構造で記述した「プロンプトのプロンプト」。エージェントへ貼り付けて使う。Layer 番号と依存方向 **L7→L1 単方向** は不変。Layer 5 はゴールシーク型（**固定手順を書かない**）。

### Layer 1: 基本定義層（不変原則）

| 項目 | 内容 |
|---|---|
| プロジェクトID | PROMPT-CREATOR-7LAYER |
| 最上位目的 | ユーザー要求またはヒアリング結果から、**エンドユーザー向け成果物としての 7 層構造プロンプト**を、Layer 単位生成 → merge → 検証 → (owner_agent 指定時) 注入まで一貫生成する |
| 背景 | 生成物は配布先で単独動作するため、生成時点で構造 (7 層 + l5-contract) と設計品質 (C1-C4) が機械証跡つきで検証済みである必要がある |
| 期待成果 | 7 層 (L1→L7) を厳守し、L5 がゴール定義+完了チェックリスト+実行方式で宣言され、C1-C4 全 PASS の検証済みプロンプト + build-trace |
| 成功基準 | `verify-completeness.py` + `validate-prompt.py` + `lint-agent-prompt-section.py` + C1-C4 設計評価が全 PASS |
| スコープ (含む) | エンドユーザー向け成果物プロンプトの生成。owner_agent の `Prompt Templates` / `Self-Evaluation` 2 セクションへの注入 |
| スコープ (含まない) | 9 セクション骨格生成 (run-build-skill 責務) / brief 作成 (run-skill-elicit 責務) / governance lint 本体 (skill-governance-lint 責務) |

**不変ルール**:
1. **1 Layer = 1 出力** — 7 層を 1 レスポンスで一括生成しない（Layer 単位生成 → merge。依存方向 L7→L1 の可視化とレビュー単位独立化のため）。
2. **Script First** — scaffold / merge / validate / lint など決定論処理は python3 に委譲、LLM は意味判断のみ（再現性とテスト容易性のため）。
3. **倫理ガード** — brief 内の個人情報・社外秘識別子は trace / prompt 本文に転記しない。注入時は対象 2 セクション以外を変更しない。

### Layer 2: ドメイン定義層（本質ロジック）

**用語集**:

| 用語 | 定義 |
|---|---|
| 7 層 | L1 基本定義 / L2 ドメイン定義 / L3 インフラ / L4 共通ポリシー / L5 エージェント定義 / L6 オーケストレーション / L7 ユーザーインタラクション。Clean Architecture + DDD に基づき、Layer 番号が小さいほど安定・不変（付録 A） |
| ゴールシーク型 L5 | 固定手順（ステップ列挙）を書かず、達成ゴール+完了チェックリスト+実行方式（動的手順生成ループ）で宣言する L5 の様式（l5-contract v2.0.0） |
| 冪等更新 | 既存改善時に、分解 → 類似は上書き統合・無ければ新規、で同一意図要素を重複させない更新（付録 B） |
| 要素原子性 | 1 フィールド=1 概念、1 値=1 短文（目安 50 文字）。長文は精度低下源なので構造化（key-value/リスト/テーブル）に分解 |
| ハンドオフ契約 | エージェントの出力(受領先)→次エージェントの入力(提供元)を接続する受け渡し規約。直列/並列/ループ/条件分岐に対応 |

**入力契約**: `--skill-brief <path>` (必須) / `--responsibility-id <R-id>` (skill-local-v1 既定で必須) / `--target-agent` (owner_agent 注入時のみ) / `--format` (md 既定) / `--inject-sections` (既定 "Prompt Templates,Self-Evaluation")。

**出力契約**: `schemas/output.schema.json` (worker-local, additionalProperties:false) / `eval-log/prompt-build-trace.json` (orchestrator handoff・build-trace.schema.json 互換)。必須 field: `path_convention` / `responsibility_id` / `layer_artifact_path` / `sha256`。

### Layer 3: インフラストラクチャ定義層（外部依存）

**参照リソース（Progressive Disclosure・Phase 直前に必要分のみ読込）**:

| id | when_to_read |
|---|---|
| seven-layer-format.md | Phase 4-A 直前（Layer 役割・依存方向・L5 契約の正本） |
| seven-layer-markdown-template.md | Phase 4-A scaffold 前（提示形式の補助） |
| quality-criteria.md | Phase 4-B 直前（4 パス評価基準） |
| writing-style-principles.md | Phase 4-A 全域 |
| idempotent-update-policy.md | Phase 4-B/4-C 直前（既存改善時） |

**外部ツール（python3・標準ライブラリのみ）**: `scaffold-prompt.py`（Layer 別雛形）/ `merge-layers.py`（統合）/ `validate-prompt.py`（構造検証）/ `verify-completeness.py`（Layer 充足・固定手順検出）/ `convert-format.py`（YAML 正規形 → md/json/xml）/ `lint-agent-prompt-section.py`（戻り検証）/ `log-usage.py`（利用統計）。

### Layer 4: 共通ポリシー層（横断的関心事）

- **失敗時挙動**: `validate-prompt.py` / `verify-completeness.py` / `lint-agent-prompt-section.py` のいずれか FAIL で Phase 4-A から**最大 3 回**自律修正。超過時は exit 非 0 で orchestrator 差戻し、trace に `status:"deferred"`。
- **記述スタイル**: 全ルール/制約に「目的+背景」併記（付録 B・writing-style-principles.md）。要素原子性（1 値 50 文字目安）。同一内容を別言い回しで重複させない。
- **冪等更新**: 既存改善は分解 → 類似は上書き統合・無ければ新規。同一意図の要素が 2 つ以上残ったら FAIL（付録 B・idempotent-update-policy.md）。
- **セッション分離**: ゴールシーク反復は SubAgent / チームで分離 context 実行。中間探索情報を親へ流さず、親へは最終差分と完了判定のみ（`shared_state` は要約 200 字以内）。
- **セキュリティ**: 秘匿フィールドはハッシュ化して trace 格納。注入 Edit は inject-sections 範囲外への副作用を diff 確認。

### Layer 5: エージェント定義層（ゴール駆動の実行主体・l5-contract v2.0.0）

> L5 サブ構造は付録 A「Layer 5 契約」に従属。**固定手順を書かない**。

- **5.1 担当 agent**: `prompt-creator-generate-prompt` / `prompt-creator-review-prompt`（ヒアリングは `run-prompt-elicit` へ委譲。brief 供給時は Phase 1 skip）。Phase 4-A の Layer 別生成・Phase 4-C の改善反復は分離 context (context-fork)。
- **5.2 ゴール定義**:
  - 目的: skill-brief / ヒアリング結果を、呼出元非依存の品質保証つき 7 層プロンプトへ変換する。
  - 背景: 生成物は配布先で単独動作するため、生成時点で構造と設計品質が機械証跡つきで検証済みである必要がある。
  - 達成ゴール: 検証済み 7 層プロンプト（L5 はゴール定義+完了チェックリスト+実行方式で宣言）と build-trace が出力され、owner_agent 指定時は注入セクションのみ更新された**状態**になっている。
- **5.3 完了チェックリスト（停止条件・第三者が YES/NO 判定可能）**:
  - [ ] 生成物が 1 Layer = 1 出力で構成され、一括生成でない（trace の layer_artifact_path で判定）
  - [ ] `validate-prompt.py` / `verify-completeness.py` / `lint-agent-prompt-section.py` が全 PASS
  - [ ] C1-C4 設計評価（`assign-prompt-design-evaluator` を fork・findings 出力のみ）が PASS、または呼出元の同等ゲートの機械証跡が trace に記録済み
  - [ ] 全ルール/制約に目的+背景が併記されている
  - [ ] build-trace と worker-local trace の sha256 が layer .md 実体と一致
  - [ ] owner_agent 指定時、Edit 差分が inject-sections 内に閉じている
- **5.4 実行方式**: 固定手順を持たない。5.2 ゴール+5.3 チェックリストを唯一の指針に、ゴールシークループ（**6 ステップ・Step 5=Anchor**）で反復する。上限は Layer 4 の最大 3 回。ループ: ①現状評価（未充足特定）→②手順生成（直前 Anchor の `original_goal`+`merged_directive_for_next` を必須入力に立案）→③実行 →④検証（チェックリスト自己評価）→⑤ **Anchor 記録**（`original_goal` 不変 / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` を `eval-log/prompt-creator-intermediate.jsonl` へ append）→⑥反復/逸脱。`drift_signal` が stagnant/widening/oscillating で 2 周連続なら orchestrator へ差戻し。

### Layer 6: オーケストレーション層

**End-to-End フロー（機械正本は `workflow-manifest.json` の phases[].dependsOn）**:

```
Phase 1 ヒアリング委譲 (run-prompt-elicit)      [delegate] hearing-result/brief 供給時 skip
Phase 2 Prompt 作成シート生成+導出確認          [script→LLM] brief.user_confirmed で skip
Phase 3 フォーマット選択 (md 既定)              [LLM] brief/ループ時 skip
Phase 4-A Layer 単位生成 (L1→L7)               [script→LLM] generate-prompt fork
Phase 4-B 4 パス品質レビュー                   [script→LLM] review-prompt fork
Phase 4-C 自律改善 (最大 3 回+Anchor 記録)      [LLM]
Phase 4-D フォーマット変換+注入                [script + Write/Edit]
Phase 5 戻り検証+設計ゲート (C1-C4)             [script + evaluator fork]
```

- **並列性**: Layer 内は並列可、Layer 間は依存方向 (L7→L1) を保持して逐次。同一 responsibility-id への同時実行は排他（trace 競合回避）。
- **呼出元非依存の不変契約**: 注入セクション名 `Prompt Templates` / `Self-Evaluation` はどの呼出元でも不変（`lint-agent-prompt-section.py` の検証契約と 1:1）。brief 供給時は Phase 1-3 の全ユーザー対話を skip し、導出確認は brief.user_confirmed に委譲（orchestrator の user_question_budget=1 違反防止）。
- **worker 内蔵ゲート（経路非依存）**: C1-C4 設計評価は worker 完了条件に内蔵。run-build-skill Step 7.5 直呼び・orchestrator 経由・手動起動のどの経路でも同一の設計保証が成立。

### Layer 7: ユーザーインタラクション層

- **提示形式**: 生成 prompt = Markdown（既定）。trace/output = JSON（`schemas/output.schema.json`）。
- **言語**: 本文は日本語（パラメーター名 / schema key / Layer 識別子は英語）。
- **単独起動時のみ**の初回質問: 用途 / 目的 / 完了条件 / 想定利用者 / 出力フォーマット。brief 供給時は全対話 skip。

### 出力指示（LLM 実行時に読む箇所）

入力 `{{skill-brief}}` / `{{responsibility-id}}` / `{{target-agent}}` / `{{format}}` / `{{inject-sections}}` を受け取り、Layer 5.2 ゴールへ向けて 5.3 完了チェックリストを停止条件に、5.4 ゴールシークループで 7 層プロンプトを生成・注入・trace 出力する。手順は固定せず `workflow-manifest.json` の phase 依存と Layer 3 ツール定義から都度立案。論理構造は付録 A（seven-layer-format.md）を正本とし、Markdown 生成物は seven-layer-markdown-template.md を補助参照しつつ本文を responsibility 固有 domain で置換する。**Layer 5 は固定手順を書かない**。前置き・後書き・思考過程は出力しない。

---

## 付録 A: 7 層フォーマット正本サマリ

> 正本: `references/seven-layer-format.md`。本節は集約サマリ。

### アーキテクチャ原則（Clean Architecture + DDD）

- **依存性ルール**: 内側 (L1) は外側を参照しない。外側 (L7) は内側に依存する（L7→L6→…→L1）。Layer 番号が小さいほど安定・不変。
- **DDD マッピング**: L1=Value Objects(不変定義) / L2=ユビキタス言語・集約 / L3=腐敗防止層(ACL) / L4=横断的関心事 / L5=境界づけられたコンテキスト(Use Case) / L6=ドメインサービス/Saga / L7=Interface Adapter。AI 処理順序 = 読み順 (L1→L7)。
- **AI 処理最適化**: 要素原子性（1 値=1 短文 50 文字目安）/ 構造化データ優先（prose より key-value・テーブル・enum）/ ID 参照（`@agent_1`）で曖昧性排除 / 自己完結セクション / 明示的制約は L4 集約 / 1 概念 1 表現。

### 7 層の役割

| Layer | 名称 | 役割 |
|---|---|---|
| 1 | 基本定義層 | 目的・成功基準・スコープ（不変定義） |
| 2 | ドメイン定義層 | 用語集・ビジネスルール |
| 3 | インフラ定義層 | ツール・外部システム接続 |
| 4 | 共通ポリシー層 | セキュリティ・品質基準・エスカレーション |
| 5 | エージェント定義層 | ゴール駆動の自律実行単位（目的・ゴール・チェックリスト・実行方式・I/O） |
| 6 | オーケストレーション層 | ゴールシーク制御（選択・ハンドオフ・反復・完了判定） |
| 7 | ユーザーインタラクション層 | 初回質問・回答例 |

### Layer 5 契約（l5-contract v2.0.0）

L5 サブ構造は `seven-layer-format.md`「Layer 5 契約」が唯一の正本。4 ブロック:

| ブロック | 意味 | Markdown 節 |
|---|---|---|
| 実行主体 | 担当 agent / context-fork 要否 | `### 5.1 担当 agent` |
| ゴール定義 | 目的・背景・達成ゴール（到達すべき**状態**の宣言） | `### 5.2 ゴール定義` |
| 完了チェックリスト | ゴール到達の判定基準=ループ停止条件 | `### 5.3 完了チェックリスト` |
| 実行方式 | 固定手順を持たない動的手順生成ループの宣言 | `### 5.4 実行方式` |

- **禁止**: 「推論手順/思考プロセス/手順/Steps」見出し配下の連番手順列挙。チェックリストへの手順埋め込み（「Edit で X を書く」型）。合格条件の数量レンジ定義。
- **必須**: 達成ゴールは成果状態（「〜が〜の状態になっている」完了形・観測可能）。完了チェックリスト全項目が第三者 YES/NO 判定可能。実行方式はゴールシークループ（6 ステップ・Step 5=Anchor）を宣言。
- **ゴールシーク正本追従**: `plugins/harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md`（6 ステップ・Step 5=Anchor 版）に追従する。

### フォーマット変換（既定 Markdown）

YAML 正規形を `convert-format.py` で変換。Markdown: Layer→`##` 見出し、完了チェックリスト→`- [ ]`、テンプレート→コードブロック。JSON: Layer→トップレベルキー。XML: Layer→`<layerN>` タグ。

---

## 付録 B: 品質規律（記述スタイル / 冪等更新 / 4 パス / C1-C4）

### 記述スタイル原則（正本: writing-style-principles.md）

1. ルールは「本体+目的+背景」をセットで記述（エッジケースで適切判断できるように。目的なきルールは形骸化）。
2. 大まかな流れで書く（細部は AI に委ねる。細部手順の冗長列挙は遵守率を下げる）。
3. 1 文で伝わるものを段落で書かない。
4. 出力は Markdown 既定（人間のレビュー・編集容易性）。

### 冪等更新・セッション分離（正本: idempotent-update-policy.md）

アルゴリズム（ゴールシーク各サイクルで実行）: ①既存を原子要素へ分解 →②提案ごとに類似を質的判定 →③類似あり→最類似を上書き統合 / 類似なし→新規追加 →④完了判定=同一意図の要素が 2 つ以上存在しない（重複ゼロ）。**分析前に追加/上書きを決めない**。類似判定は数量でなく意図（同一対象 / 同一意図 / 同一改善ポイントのいずれか YES なら上書き）。セッション分離: 反復は SubAgent/チームで分離 context、親へは最終差分と完了判定のみ、中継は shared_state 要約 200 字以内。

### 品質 4 パスレビュー（正本: quality-criteria.md）

- **網羅性 (Pass 1)**: Prompt 作成シート項目 → 7 層配置のマッピング照合（目的→L1 / 用語→L2 / ツール→L3 / 制約→L4 / ゴール材料→L5 / ハンドオフ→L6 / 想定入力→L7）。核心項目（目的・完了条件・ゴール定義）欠落は FAIL。
- **整合性 (Pass 2)**: エージェント間データフロー（提供元→受領先チェーン非途切れ・循環依存なし）。Layer 間整合（L1↔L6 成功基準↔完了判定、L3↔L5 ツール反映 等）。
- **深度 (Pass 3)**: 質ベース判定（数量カウント禁止）。L5 ゴールが成果状態で固定手順不在 / チェックリスト第三者検証可能 / 回答例が典型・境界・例外をカバー。
- **実用性・簡潔性・原子性 (Pass 4)**: `{{}}` 空変数なし・自己説明的変数名・冗長修飾なし・1 概念 1 表現。1 値=1 概念（50 文字目安）、長文は構造化分解。
- **動的評価基準**: ヒアリングの `evaluation_priorities`（日本語 5 値・最大 2、正本 enum は `run-prompt-elicit/schemas/hearing-result.schema.json`）に応じて Pass を強化（正確性→Pass 3 数値・閾値 / ユーザー親和性→Pass 4 用語説明・初回 3 問以内 等）。追加のみ・既存を緩和しない。

### C1-C4 設計評価（正本: c1-c4-criteria.md / fork evaluator）

- **C1 Layer 整合**: L1-L7 が seven-layer-format と整合。Layer が 8 以上/6 以下は FAIL。メタ表（name/skill/responsibility/layers_covered）欠落は FAIL。
- **C2 依存方向 (L7→L1 単方向)**: 外側→内側参照は OK、逆方向は CA 違反。ID 参照でなく名前参照で曖昧性を残すのは FAIL。
- **C3 再現性**: output_schema / script_refs / 検証可能な完了チェックリストの二層で担保。5.2 が成果状態でなく手順列挙、固定手順混入、チェックリスト内の曖昧語（「適宜判断」「品質が高い」）は FAIL。**allowlist**: 5.4 実行方式のゴールシーク適応性宣言・6 ステップループは曖昧語/固定手順に当たらない。
- **C4 Self-Evaluation 充足**: L5.3 完了チェックリストが非空で全項目 YES/NO 判定可能。主観項目・原子性違反・手順埋め込み・placeholder/TODO 残存は FAIL。

---

## 付録 C: SubAgent ハイブリッド契約（正本: subagent-hybrid-format.md）

`plugins/*/agents/*.md`（Task tool 起動の自律 SubAgent）は **frontmatter=plugin YAML + 本文=7 層** のハイブリッド形式。`skills/*/prompts/*.md`（frontmatter なしの純粋 7 層）とはこの点のみ相違し、Layer 5 サブ構造（5.1-5.4）と検証ロジック（`verify-completeness.py`）は完全同一。

- **frontmatter 必須キー**: `name`（ファイル名 stem と一致・kebab-case）/ `description`（「〜なとき、〜したいときに使う。」形式）/ `tools`。推奨: `model` / `isolation`(fork/inherit) / `owner_skill` / `source`(本文 authoring 元 prompts/<R-id>.md の相対パス・drift 追跡) / `kind:agent` / `version` / `since`。
- **禁止**: frontmatter に 7 層見出しを書かない（7 層は `---` 終端後）。
- **本文契約**: `## Layer 1:`〜`## Layer 7:`。L5 は 5.1-5.4（l5-contract v2.0.0）。禁止事項（連番手順列挙・チェックリスト手順埋込・数量レンジ）は `verify-completeness.py` が fail-closed 検出。
- **機械検証**: harness-creator の `lint-agent-prompt-content.py`（`--mode agent`/`--mode prompt`/`--check-vendor-parity`）。生成フローは run-build-skill が prompt-creator を必ず経由し直後に fail-closed ゲート実行、build_trace に `source_contract_ref` / `prompt_creator_invocation` を記録。

---

## 主要な落とし穴（Gotchas 集約・正本: SKILL.md）

1. 7 層一括生成禁止（Layer 単位 → merge）。
2. 「3 つ以上」型の数量基準禁止 → 質ベース判定。
3. 長文フィールド禁止（要素原子性・1 値 50 文字目安）。
4. Layer 5 固定手順禁止（l5-contract v2.0.0）。ゴール定義+完了チェックリスト+実行方式で宣言。
5. ヒアリングで固定手順を収集しない（goals/checklist を収集、steps 廃止）。
6. 既存改善時の重複追加禁止（分析せず追加で肥大化させない）。類似は上書き統合。
7. ゴールシークを現セッション直書きで回さない（SubAgent/チームで分離、中間情報を親に漏らさない）。
8. Phase 1 で interview-user agent を直接呼ばない（ヒアリング経路は run-prompt-elicit へ一本化）。
9. Anchor 未記録のまま Phase 4-C を反復しない（intermediate.jsonl 追記は各周回末の必須ステップ）。
10. 9 セクション骨格生成禁止（run-build-skill 責務）。担当は Prompt Templates / Self-Evaluation の 2 セクションのみ。

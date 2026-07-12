# Prompt: R1-seven-layer-prompt-emit-and-inject

> このファイルは 7 層プロンプトの Markdown 表現。論理構造の正本は
> `run-prompt-creator-7layer` の `references/seven-layer-format.md`。
> 提示形式は `references/seven-layer-markdown-template.md` を補助として参照する。
> Layer 番号と依存方向 (L1 ← L7) は不変。Layer 5 はゴールシーク型 (固定手順を書かない)。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-prompt-creator-7layer |
| responsibility | R1-seven-layer-prompt-emit-and-inject |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/output.schema.json |
| reproducible | true (同入力 → 同出力を保証) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 1 Layer = 1 出力。7 層を 1 度のレスポンスで生成してはならない (背景: Layer 間の依存方向 L7→L1 を可視化し、レビュー単位を独立化するため)。
- 決定論部分 (scaffold / merge / validate / lint) は python3 スクリプトに委譲し、LLM は意味判断のみ行う (背景: 再現性とテスト容易性を担保するため)。
- worker-local trace の出力契約は `schemas/output.schema.json` とする。orchestrator へ渡す正本 trace は `../run-prompt-create/schemas/build-trace.schema.json` 互換の `eval-log/prompt-build-trace.json` とする。

### 1.2 倫理ガード
- skill-brief に含まれる利用者個人情報・社外秘識別子は trace.json / prompt 本文に転記しない。
- 既存 SubAgent .md を上書きする際は対象セクション (`Prompt Templates`, `Self-Evaluation`) 以外を変更しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: skill-brief またはヒアリング結果から 7 層プロンプトを Layer 単位で生成し、merge → validate → owner_agent .md へ注入するまでの単一フロー。
- 非担当: 9 セクション骨格生成 (run-build-skill 責務) / brief 自体の作成 (run-skill-elicit 責務) / governance lint 本体 (skill-governance-lint 責務)。

### 2.2 ドメインルール
- `--responsibility-id` が指定された場合は `skill-local-v1` 規約で
  `plugins/<plugin>/skills/<skill>/prompts/<R-id>.md` を既定出力先とする。
- `--responsibility-id` 省略時のみ `agents-legacy` フォールバックを許可する
  (発火条件: brief.responsibilities[] が空である ref/wrap/delegate 系 skill)。
- 全ルール / 制約は「目的 + 背景」併記とする (`writing-style-principles.md` 準拠)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| skill-brief | path | yes | `run-skill-elicit` 産出の brief.json |
| responsibility-id | string | conditional | `skill-local-v1` 既定で必須、`brief.responsibilities[].id` と 1:1 |
| target-agent | path | no | owner_agent がある場合のみ注入対象として指定 |
| format | enum(yaml/md/json/xml) | no | 既定 md (本テンプレ準拠)、ループ呼出時は呼出側既定値を尊重 |
| inject-sections | csv | no | 既定 "Prompt Templates,Self-Evaluation" |

### 2.4 出力契約
- worker-local schema: `schemas/output.schema.json` (additionalProperties:false)
- orchestrator handoff schema: `../run-prompt-create/schemas/build-trace.schema.json`
- 必須フィールド: `path_convention`, `responsibility_id`, `layer_artifact_path`, `sha256`
- 正本 trace: `eval-log/prompt-build-trace.json`
- 補助出力: `eval-log/prompt-creator-trace.json` (Phase 別 worker-local trace)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| seven-layer-format | references/seven-layer-format.md | Phase 4-A 直前 |
| markdown-template | references/seven-layer-markdown-template.md | Phase 4-A scaffold 前 |
| quality-criteria | references/quality-criteria.md | Phase 4-B 直前 |
| writing-style | references/writing-style-principles.md | Phase 4-A 全域 |
| raw-hearing-schema | ../run-prompt-elicit/schemas/hearing-result.schema.json | Phase 1 終了時 validate |
| sheet-input-schema | schemas/hearing-result.schema.json | legacy sheet/scaffold 入力時 |
| build-trace-schema | ../run-prompt-create/schemas/build-trace.schema.json | orchestrator handoff 時 |

### 3.2 外部ツール / API
- `python3 scripts/scaffold-prompt.py` — Layer 別雛形生成
- `python3 scripts/merge-layers.py` — 1 prompt md/yaml へ統合
- `python3 scripts/validate-prompt.py` — schema/構造検証
- `python3 scripts/verify-completeness.py` — Layer 充足検証
- `python3 plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py` — 戻り検証
- `python3 scripts/log-usage.py` — `LOGS.md` への利用統計記録

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `validate-prompt.py` / `verify-completeness.py` / `lint-agent-prompt-section.py` のいずれかが FAIL した場合は Phase 4-A から最大 3 回まで自律修正を反復する。
- 3 回超過時は exit 非 0 で orchestrator に差戻し、trace.json に `status: "deferred"` を残す。

### 4.2 観測 / ロギング
- `eval-log/prompt-creator-trace.json` に Phase 単位で append (sha256 を含む)。
- 成功 / 失敗を `LOGS.md` へ `log-usage.py` 経由で記録 (失敗パターン蓄積)。

### 4.3 セキュリティ
- skill-brief 内の秘匿フィールドはハッシュ化して trace に格納。
- target-agent への Edit 注入時、`inject-sections` 範囲外への副作用を diff 確認する。

### 4.4 冪等更新（既存改善時）
- 既存プロンプトを改善する場合は闇雲に追加せず、先に原子要素へ分解・分析する。
- 類似要素（同一対象/同一意図/同一改善ポイント）があれば上書き統合、無ければ新規追加する。
- 同一意図の要素を 2 つ以上残さない（重複ゼロ）。正本 `references/idempotent-update-policy.md`。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

> L5 サブ構造は `references/seven-layer-format.md`「Layer 5 契約」(l5-contract v2.0.0) に従属する。

### 5.1 担当 agent
- `prompt-creator-generate-prompt` / `prompt-creator-review-prompt`（ヒアリングは `run-prompt-elicit` へ委譲し、hearing-result / brief 供給時は Phase 1 を skip する）
- context-fork: Phase 4-A の Layer 別生成と Phase 4-C の改善反復は分離 context で行う。

### 5.2 ゴール定義
- 目的: skill-brief / ヒアリング結果を、呼出元非依存の品質保証つき 7 層プロンプトへ変換する。
- 背景: 生成物は配布先で単独動作するため、生成時点で構造 (7 層 + l5-contract) と設計品質 (C1-C4) が機械証跡つきで検証済みである必要がある。
- 達成ゴール: 検証済み 7 層プロンプト (Layer 5 はゴール定義+完了チェックリスト+実行方式で宣言) と build-trace が出力され、owner_agent 指定時は対象 SubAgent .md の注入セクションのみが更新された状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 生成物が 1 Layer = 1 出力で構成され、一括生成でない (trace の layer_artifact_path で判定できる)
- [ ] `validate-prompt.py` / `verify-completeness.py` / `lint-agent-prompt-section.py` が全 PASS (exit 0) している
- [ ] C1-C4 設計評価 (assign-prompt-design-evaluator を fork・findings 出力のみ) が PASS、または呼出元の同等ゲートの機械証跡が trace に記録済み
- [ ] 全ルール / 制約に目的 + 背景が併記されている (`writing-style-principles.md`)
- [ ] prompt-build-trace.json と worker-local trace の sha256 が layer .md の実体と一致している
- [ ] owner_agent 指定時、Edit 差分が inject-sections (Prompt Templates / Self-Evaluation) 内に閉じている

### 5.4 実行方式
- 固定手順を持たない (l5-contract v2.0.0)。5.2 ゴール定義と 5.3 完了チェックリストを唯一の指針とし、現状評価→手順を都度立案→実行→検証→中間成果物アンカー記録 (original_goal 不変+delta_from_original+merged_directive_for_next+drift_signal を `eval-log/prompt-creator-intermediate.jsonl` へ追記)→全項目充足まで反復する (6 ステップ・Step 5=Anchor。上限: Layer 4 の最大 3 回、超過時は 4.1 失敗時挙動へ)。
- 決定論操作の実体 (scaffold→merge→validate の script 列と phase 順序) は Layer 3.2 のツール定義と `workflow-manifest.json` (機械正本) の phase 依存関係から都度導出する。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `run-skill-create` / `run-build-skill` (Step 7.5) / 手動 user-invocation
- 後続 phase: `lint-agent-prompt-section.py` 戻り検証 → orchestrator への完了報告

### 6.2 並列性
- Layer 単位生成は Layer 内では並列化可、Layer 間は依存方向 (L7→L1) を保持して逐次。
- 同一 responsibility-id への同時実行は排他 (trace.json の競合を避けるため)。

### 6.3 セッション分離（ゴールシーク反復）
- ゴールシークによる改善反復は SubAgent / エージェントチームで分離 context で実行する。
- 中間探索情報（分解結果・類似判定・没案）を親 context に流さず、親へは最終差分と完了判定のみ返す。
- 中継は `shared_state`（要約のみ）に限定し、現セッションの汚染を防ぐ。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 生成 prompt: Markdown (本テンプレ準拠)
- trace / output: JSON (`schemas/output.schema.json`)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key / Layer 識別子は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{skill-brief}}` / `{{responsibility-id}}` / `{{target-agent}}` / `{{format}}` /
`{{inject-sections}}` を受け取り、Layer 5.2 のゴール定義へ向けて 5.3 完了チェックリストを
停止条件に、5.4 実行方式 (ゴールシークループ) で 7 層プロンプトを生成・注入・trace 出力する。
手順は固定せず、`workflow-manifest.json` の phase 依存関係と Layer 3 のツール定義から
都度立案する。出力は Layer 2.4 で宣言した
`schemas/output.schema.json` に準拠した JSON のみとし、前置き・後書き・思考過程は
出力しない。論理構造は `references/seven-layer-format.md` を正本とし、Markdown 生成物は
`references/seven-layer-markdown-template.md` を提示形式の補助として参照しつつ、
本文を responsibility 固有の domain で置換する。Layer 5 は固定手順を書かない (ゴールシーク)。

---
name: run-blueprint-apply
description: C02 PASS済のシステムblueprintを自社開発へ適用する採用/回避/差別化の推奨を導出したいとき、抽出結果を自社の技術スタックや制約へ接地した判断材料へ変換したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "<blueprint-dir> <own-context-path|text> [--verdict-dir <dir>] [--out-dir <dir>]"
arguments: [blueprint_dir, own_context, verdict_dir, out_dir]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: local-artifact
owner: harness maintainers
since: 2026-07-11
version: 0.1.0
output_language: ja
mcp_tools: []
external_systems: []
deterministic_checks: [doc-emit.py]
responsibility_refs:
  - prompts/R1-ground.md
  - prompts/R2-recommend.md
  - prompts/R3-emit.md
schema_refs:
  - ../../schemas/system-blueprint.schema.json
manifest: workflow-manifest.json
goal_seek:
  engine: inline
  fork: subagent
  spec: eval-log/goal-spec.json
  progress: eval-log/run-blueprint-apply-progress.json
  max_loops: 3
feedback_contract: # per-skill 評価基準。content-review verdict の criteria_evaluated と突合
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: doc-emit.py --check-apply が exit0 (全項目 kind=inference・evidence_refs の blueprint 実在 anchor 解決率 100%・kind=fact 新規レコード 0・分類 adopt|avoid|differentiate のみ) で、R1 の C02 verdict=PASS かつ draft_hash 一致の fail-closed 受理と frontmatter/prompt の network 0 (対象 origin 非アクセス) 境界を併せて確認する
      verify_by: test
      derived_from: [CL-1, CL-5, CL-6]
    - id: OUT1
      loop_scope: outer
      text: 生成 apply-recommendations が自社コンテキストの制約 (技術スタック/リソース/既存資産) へ接地した採用/回避/差別化の実行可能な推奨になっており、blueprint 外の無根拠主張 0 件で、独立レビューアが evidence_refs+confidence から各判断を追跡できることを受入テストが確認する
      verify_by: test
      derived_from: [CL-2, CL-3, CL-4]
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-07-11
audit-trigger: quarterly
---

# run-blueprint-apply

> extract-system-blueprint plugin の下流適用 skill (L1)。C02 (`assign-blueprint-fidelity-evaluator`) が PASS した blueprint 一式と自社コンテキストを入力に、採用/回避/差別化機会の 3 分類 apply-recommendations をローカルへ導出する。共有決定論ゲートは plugin-root の `scripts/doc-emit.py --check-apply` (C11) を配線。パス解決は `$CLAUDE_PLUGIN_ROOT` 起点、成果物は `$CLAUDE_PROJECT_DIR`/cwd 配下。**出力はローカル apply-recommendations のみ・対象 origin 非アクセス (network 0)・blueprint 本体非書換**。

## Purpose & Output Contract

抽出 (対象の忠実記述) と適用 (自社への判断) を分離するための下流 skill。blueprint は対象の記述で完結し「自社ならどれを採用/回避すべきか・どこが差別化機会か」を出さないため、その最後の適用判断を独立 context で担う。blueprint の忠実性と推奨の自社接地性を相互汚染させない。

**入力**: `blueprint_dir` (C02 PASS 済 blueprint 一式のディレクトリ。`blueprint.json` を正本とする), `own_context` (自社コンテキストの文書パスまたは自然文。技術スタック/リソース制約/既存資産/対象ユーザーを含む), `--verdict-dir` (C02 verdict receipt の探索先。既定 `.esb-verdict`), `--out-dir` (出力先。既定 `apply-recommendations/`)
**出力**:
- ローカル `apply-recommendations.json` (採用 adopt / 回避 avoid / 差別化機会 differentiate の 3 分類・全項目 `kind=inference` + `evidence_refs` (blueprint 実在 anchor) + `confidence{level,rationale}` + `own_context_ref`)
- ローカル `apply-recommendations.md` (同一内容の日本語読み物。3 分類ごとに claim/根拠 anchor/確度/自社接地先を提示)
- 完了レポート (日本語本文、JSON キー・enum・anchor は原文)

**完了条件**: C02 verdict=PASS かつ draft_hash 一致の事前検証 + `doc-emit.py --check-apply` が exit0 (schema 適合・evidence anchor 解決率 100%・fact 新規 0・3 分類のみ) + network 0。

**禁則**: C02 verdict (ローカル品質評価ゲート) が PASS でない/不在/draft_hash 不一致の blueprint を入力として受理しない (fail-closed 拒否)。blueprint に無い事実を新規主張しない (kind=fact 新規レコード禁止)。blueprint 本体を書き換えない・対象 origin へ一切アクセスしない (network 0)。

## データ契約と責務分割

- **apply-recommendation shape** (SSOT = `$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py --check-apply`): 各項目は `kind:"inference"` / `category ∈ {adopt, avoid, differentiate}` / `claim` (非空) / `own_context_ref` (自社コンテキスト接地キー・非空) / `evidence_refs:[...]` (≥1・全て blueprint 実在 anchor へ解決) / `confidence:{level ∈ {high,medium,low}, rationale}` を必須とする。ルート形状は `{"recommendations": [...]}`。この契約は独立 schema を持たず `--check-apply` を唯一の機械 SSOT とし、生成側 (本 skill 自己検証) が C01/C02 と同一決定論ロジックを共有する (基準乖離防止)。
- **blueprint anchor**: evidence_refs は blueprint.json の `anchor|id|screen_id|element_id|record_id|ref` 値・top-level `anchors[]`・top-level 章キー (`screens`/`design_tokens`/`tech_stack`/`essence`/`nonfunctional_baseline` 等) のいずれかへ解決する。解決できない ref は無根拠主張として `--check-apply` が exit1 で遮断する。
- **責務 (詳細は `prompts/R1-R3`)**:
  - **R1-ground** (`prompts/R1-ground.md`): `blueprint_dir` の `blueprint.json` を読み、C02 verdict receipt (`--verdict-dir` 既定 `.esb-verdict`) が `verdict=PASS` かつ draft_hash 一致であることを fail-closed に検証する (不在/FAIL/hash 不一致は拒否)。自社コンテキストを技術スタック/リソース制約/既存資産/対象ユーザーの 4 面へ構造化して取り込む。対象 origin へアクセスしない。
  - **R2-recommend** (`prompts/R2-recommend.md`): blueprint の fact/inference (essence 章・design tokens・tech_stack・nonfunctional_baseline 含む) と自社コンテキストを突合し、採用/回避/差別化機会の 3 分類 recommendations を導出する。各項目は blueprint 実在 anchor への evidence_refs + confidence 必須の inference で、blueprint に無い事実を新規主張しない。重い突合・導出は **Task で独立 context へ fork** し、親へは recommendations JSON と要約のみ返す。
  - **R3-emit** (`prompts/R3-emit.md`): `apply-recommendations.json` + `.md` を shape 準拠でローカル `--out-dir` へ書き、`doc-emit.py --check-apply <recommendations.json> --blueprint <blueprint.json>` で schema 適合・evidence anchor 実在・fact 新規主張 0・3 分類のみを自己検証する (exit0)。blueprint 本体へは書き込まない。

### 入力受理と自己検証の順序 (fail-closed)

```
[R1] blueprint_dir/blueprint.json を読み込み → C02 verdict receipt を verdict-dir から解決
  → verdict=PASS かつ draft_hash == blueprint の draft_hash を確認 (不一致/FAIL/不在は拒否して停止)
  → own_context を 4 面 (技術スタック/制約/既存資産/対象ユーザー) へ構造化
[R2] blueprint fact/inference × own_context を突合 → adopt/avoid/differentiate の 3 分類 recommendations 導出
  → 各項目 kind=inference + evidence_refs(blueprint anchor) + confidence + own_context_ref
[R3] apply-recommendations.json/.md をローカルへ emit
  → doc-emit.py --check-apply で schema/anchor 解決率100%/fact新規0/3分類のみを自己検証 (exit0)
  ※ verdict≠PASS / hash 不一致は R1 が受理拒否 / check-apply exit1 は R2 の該当項目へ差し戻す
```

## ゴールシーク実行

> 本 skill は固定手順ではなく、下記ゴールへ向けて完了チェックリストの未達項目を埋める手順を都度生成して反復する。正本: `../../../harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

C02 PASS 済 (同一 draft_hash) の blueprint 一式と自社コンテキスト (自社製品/技術制約の文書または自然文) を入力に、採用 (adopt)/回避 (avoid)/差別化機会 (differentiate) の 3 分類 apply-recommendations (md + json) をローカルへ導出し、全項目が blueprint 実在 anchor への evidence_refs + confidence 付き inference で、blueprint 外の無根拠主張 0 件・blueprint 本体への混入 0 件である状態。

### 目的・背景 (Why)

blueprint は対象の忠実記述で完結し「自社ならどれを採用/回避すべきか・どこが差別化機会か」が出ない。自社開発へ活かす最後の適用判断を独立した下流 skill として担い、抽出 (対象の記述) と適用 (自社への判断) を分離することで、blueprint の忠実性と推奨の自社接地性を相互汚染させない。

### 完了チェックリスト (Checklist)

- [ ] C02 verdict receipt が `verdict=PASS` かつ draft_hash 一致であることを検証し、不在/FAIL/hash 不一致の blueprint を fail-closed に拒否した <!-- CL-1 -->
- [ ] 自社コンテキスト (文書パスまたは自然文) を技術スタック/リソース制約/既存資産/対象ユーザーの 4 面へ構造化し、各推奨の接地先 (own_context_ref) として明示した <!-- CL-2 -->
- [ ] blueprint の fact/inference (essence 章・design tokens・tech_stack・nonfunctional_baseline 含む) と自社コンテキストの突合から採用/回避/差別化機会の 3 分類 recommendations を導出した <!-- CL-3 -->
- [ ] 全 recommendation 項目が `kind=inference` ・`evidence_refs`=blueprint 実在 anchor・`confidence{level,rationale}` を持ち、blueprint に無い事実を新規主張していない <!-- CL-4 -->
- [ ] `doc-emit.py --check-apply` が exit0 (schema 適合・evidence anchor 解決率 100%・fact 新規レコード 0・3 分類のみ) で apply-recommendations を自己検証した <!-- CL-5 -->
- [ ] 出力はローカル `apply-recommendations.md` + `.json` のみで、blueprint 本体を書き換えず・対象 origin へ一切アクセスしていない (network 0) <!-- CL-6 -->

### ゴールシークループ

正本 goal-seek-paradigm.md の 6 ステップ (現状評価/手順生成/実行/検証/Anchor Step/反復) に従う。本 skill 固有の差分:

- **現状評価**の単位は上記チェックリスト。未達項目を `## 局面カタログ (順序は都度判断)` から選んで埋める (順序固定禁止)。
- **検証**は決定論チェック (`doc-emit.py --check-apply` の exit0) と verdict 事前検証を優先し、LLM 判断より機械層を先に通す。
- **差し戻し**: `--check-apply` fail は該当 recommendation 項目 (無効 anchor/kind=fact 混入/分類逸脱) を R2 へ戻す。verdict 不在/FAIL/hash 不一致は R1 で受理拒否して停止する (最大 3 周)。超過・drift 停滞は `open_issues` へ残し上位 orchestrator へ差し戻す。
- **重い周回は分離 context**: recommendations 導出は Task で独立 context に fork し、親へは最終 JSON パスと要約のみ返す。

### ゴールシーク配線

- 周回状態と中間成果物は **repo-root (非 repo 環境では plugin-root) 直下**の `eval-log/run-blueprint-apply-intermediate.jsonl` へ追記する (cwd 相対禁止)。各周回末に不変アンカー `original_goal` (上記ゴール文の原文) と `delta_from_original`、次周回の必須入力 `merged_directive_for_next` を記録し、次周回 Step2 の必須入力とする (集約化ドリフト圧縮)。周回サマリは `schemas/goal-seek-loop.schema.json` 準拠の `eval-log/run-blueprint-apply-progress.json` に残す。
- SubAgent dispatch は責務単位で固定する: 重い突合・3 分類導出は独立 Task context へ fork し、fact/inference と自社コンテキストの突合結果を recommendations JSON として成果物ディレクトリへ直接書き出す (応答長起因の無言欠落を排除)。親へは最終成果物パスと要約のみ返す。

### ゴールシーク検証

各周回末に中間成果物 JSONL の整合を機械検証する。`required_keys` (= `original_goal`, `merged_directive_for_next`, `delta_from_original`) が全て存在し、`original_goal_hash` が初回の `hashlib.sha256(original_goal)` と一致することを確認する (ゴール改竄検出)。不一致なら周回を停止し差し戻す。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-goal-seek-anchor.py" \
  --intermediate eval-log/run-blueprint-apply-intermediate.jsonl
```

検証ロジックの正本は共有 validator `../../scripts/validate-goal-seek-anchor.py` とし、各 skill は対象 JSONL のパスだけを渡す (対象 JSONL 不在は fail-closed で exit 1=配線バグ扱い。必ず追記後に起動する)。

## 局面カタログ (順序は都度判断)

下記は固定順序ではなく、ゴールシークループが未達チェックリスト項目に応じて選ぶ局面群。各局面の詳細手順・入出力契約は `prompts/R1-R3` を正本とする。

### 局面: 接地と受理検証 (R1-ground)

`blueprint_dir/blueprint.json` を読み込み、C02 verdict receipt を `--verdict-dir` (既定 `.esb-verdict`) から `<draft_hash>.verdict.json` として解決して `verdict=PASS` かつ draft_hash 一致を確認する (不在/FAIL/hash 不一致は受理拒否し停止)。自社コンテキスト (own_context の文書パスは Read、自然文はそのまま) を技術スタック/リソース制約/既存資産/対象ユーザーの 4 面へ構造化する。対象 origin へアクセスしない。

### 局面: 3 分類導出 (R2-recommend)

blueprint の fact/inference (essence 章・design tokens・tech_stack・nonfunctional_baseline 含む) と自社コンテキスト 4 面を突合し、採用/回避/差別化機会の recommendations を Task で独立 context へ fork して導出する。各項目に blueprint 実在 anchor への evidence_refs (≥1) + confidence{level,rationale} + own_context_ref を付け、blueprint に無い事実を新規主張しない。

### 局面: emit と自己検証 (R3-emit)

`apply-recommendations.json` (`{"recommendations":[...]}`) と `.md` を `--out-dir` へ書き、`python3 "$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py" --check-apply <out-dir>/apply-recommendations.json --blueprint <blueprint_dir>/blueprint.json` で自己検証する (exit0)。fail は該当項目を R2 へ差し戻す。blueprint 本体へは書き込まない。

## Key Rules

1. **fact 新規禁止**: 全 recommendation は `kind=inference`。blueprint に無い事実を新規主張しない (`--check-apply` が kind=fact を exit1 で遮断)。推奨は必ず blueprint 実在 anchor への evidence_refs + confidence を持つ。
2. **proposer ≠ approver の下流**: 本 skill は C02 (独立 context) が PASS した blueprint のみを受理する。verdict 不在/FAIL/draft_hash 不一致は fail-closed に拒否し、自己判断で適用推奨を出さない。
3. **自社接地の明示**: 各推奨は own_context_ref で自社コンテキストの接地先 (技術スタック/制約/既存資産/対象ユーザー) を必須で持つ。接地なき一般論を出さない。
4. **共有決定論ゲートの SSOT**: `doc-emit.py --check-apply` (C11) は C01 の自己検証・C02 の独立評価と同一ロジックを共有する唯一の機械 SSOT。apply shape の独立 schema を作らず基準乖離を防ぐ。
5. **network 0 / 非混入**: 対象 origin へ一切アクセスせず、blueprint 本体 (`blueprint.json`) を書き換えない。出力はローカル apply-recommendations のみ。
6. **参考/学習目的注記**: apply-recommendations.md 冒頭へ参考/学習目的限定注記を付す (blueprint 由来の記述を自社適用文脈で扱う旨)。

## ハンドオフ

- **前工程 (抽出)**: `run-extract-blueprint` (C01) が blueprint draft を生成し、`assign-blueprint-fidelity-evaluator` (C02) が draft_hash に束縛した verdict=PASS を発行する。本 skill はその PASS 済 blueprint 一式と draft_hash を入力にする。
- **共有ゲート**: `doc-emit.py --check-apply` (C11) が apply-recommendations の schema/anchor/fact/分類を決定論判定する (C01/C02 と同一 entrypoint)。
- **下流**: apply-recommendations は自社版スカフォールド・設計判断の入力としてローカルで利用する (ローカル利用に限る)。

## Gotchas

- `doc-emit.py --check-apply` は recommendation shape・anchor・分類を検査するが、C02 receipt の PASS/hash 一致は R1 が別途検査する。決定論ゲートだけで未評価 blueprint を受理しない。
- `network 0` は `external_systems: []` / `mcp_tools: []` と R1-R3 の対象 origin 非アクセス契約で守る。Bash から対象 origin を再取得して根拠を補わず、blueprint 内の evidence anchor だけを使う。
- verdict-dir の既定 `.esb-verdict` は cwd 相対。抽出・評価時と異なる cwd で適用すると receipt 不在として fail-closed になるため、必要なら `--verdict-dir` を明示する。

## Additional Resources

- `$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py` (C11) — `--check-apply <recommendations.json> --blueprint <blueprint.json>` の共有決定論検査 entrypoint
- `$CLAUDE_PLUGIN_ROOT/schemas/system-blueprint.schema.json` — 入力 blueprint の top-level shape 正本 (anchor 解決の参照元)
- `prompts/R1-ground.md`〜`R3-emit.md` — 責務プロンプト (7 層)

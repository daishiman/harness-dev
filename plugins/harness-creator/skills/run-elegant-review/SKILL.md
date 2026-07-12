---
name: run-elegant-review
description: 新規/更新Skillの設計eleganceを多角的思考法と4条件で検証したいとき、量産パッケージの品質ゲートとして使いたいときに起動する。
disable-model-invocation: false
user-invocable: true
argument-hint: "<target-type> <target-path> [--scope skill|plugin|repo] [--dry-run] [--max-iter 3]"
arguments: [target_type, target_path, scope_mode, dry_run, max_iterations]
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(python3 *)
  - Bash(git diff *)
  - Skill
  - Agent
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-05-18
version: 0.1.0  # version=配布 semver / spec_version=仕様世代タグ (定義は workflow-manifest.json _comment 参照)
manifest: workflow-manifest.json
spec_version: "2.0"
responsibility_refs:
  - prompts/R1-phase1-reset.md
  - prompts/R2-phase2-parallel.md
  - prompts/R3-phase3-execute.md
subagent_refs:
  - elegant-reset-observer
  - elegant-logical-structural-analyst
  - elegant-meta-divergent-analyst
  - elegant-system-strategic-analyst
  - elegant-improvement-executor
schema_refs:
  - schemas/finding.schema.json       # 単数 finding (機械観測 signal: contradiction/omission/inconsistency/dependency_break/smell)
  - schemas/findings.schema.json      # 集約 wrapper (paradigm_findings[] + variable_abstraction + four_conditions)。issues.severity は運用ラベル low/medium/high/critical で finding.schema.json と責務分割 (G2)
  - schemas/phase-output.schema.json
  - schemas/verdict.schema.json
rubric_refs:
  - ref-skill-design-rubric
  - references/4-conditions.json        # 4 条件の唯一正本 (elegant-4-conditions.json は後方互換 redirect)
reference_refs:
  - references/30-paradigms-full.md
  - references/thought-methods.yaml
  - references/agent-roles.md
  - references/orchestration-flow.md
  - references/convergence-policy.json
  - references/amplified-patterns.json
  - references/variable-template-contract.md
  - references/observable-emit-examples.md
script_refs:
  - scripts/build-paradigm-scorecard.py
  - scripts/validate-paradigm-coverage.py
  - scripts/emit-observable.py
merge_strategy: deep-merge
conflict_policy: most-specific-wins
source: doc/ClaudeCodeスキルの設計書/09-evaluation-orchestration.md
source_refs:
  - doc/ClaudeCodeスキルの設計書/09-evaluation-orchestration.md
  - doc/ClaudeCodeスキルの設計書/17-agent-teams-reference.md
  - doc/ClaudeCodeスキルの設計書/25-meta-skill-runbook.md
  - doc/ClaudeCodeスキルの設計書/26-meta-skill-dogfooding.md
  - doc/ClaudeCodeスキルの設計書/30-paradigm-analogy-map.md
  - doc/ClaudeCodeスキルの設計書/35-meta-harness-feedback-loop.md
  - doc/ClaudeCodeスキルの設計書/36-plugin-package-harness-contract.md
source-tier: internal
last-audited: 2026-05-23
audit-trigger: quarterly
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 1周回内で30思考法が全種 finding を出すか skip_reason を残し used 足す skipped_with_reason が30に到達する
      verify_by: script
      derived_from: [CL-2]
    - id: IN2
      loop_scope: inner
      text: 各 SubAgent が出力する findings.json が集約スキーマを通過し issues[].severity が優先度列挙、condition_signal が4条件 signal 列挙に収まる
      verify_by: lint
      derived_from: [CL-7]
    - id: OUT1
      loop_scope: outer
      text: 矛盾なし 漏れなし 整合性あり 依存関係整合の4条件が全 PASS かつ未達時は force_pass せず human_review へ差し戻す
      verify_by: elegant-review
      derived_from: [CL-3, CL-4, CL-5, CL-6, CL-9]
    - id: OUT2
      loop_scope: outer
      text: 改善案の承認を同一 context が行わず別 SubAgent または人間が独立採点する proposer 非イコール approver を満たす
      verify_by: evaluator
      derived_from: [CL-8]
---

# run-elegant-review (v2)

> **Reading Order**: (1) ゴールシーク実行 → (2) Purpose & Output Contract → (3) 役割直交 → (4) 入出力契約 → (5) 30 思考法カタログ → (6) 検証 4 条件 → (7) 実行フロー (Phase 1→2→3) → (8) Gotchas。初見は (1)(2)(6) で全体像が掴める。

## ゴールシーク実行

固定手順は書かず、ゴール+チェックリストへ向け都度手順を生成・反復する。正本: `../run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

対象（Skill / rubric 改訂 / アーキテクチャ提案 / plugin package）が 30 思考法で多角的に検証され、4 条件（矛盾なし / 漏れなし / 整合性あり / 依存関係整合）が全て PASS、または max_iter 到達で `status: incomplete` + human_review 必須として findings.json / verdict / レポートが eval-log に保存された状態になっている。

### 目的・背景 (Why)

25章 §runbook Step 5.5（設計 elegance lint）として、契約適合（PKG check）・規範採点（rubric evaluator）と直交する「設計の elegance」を保証するため。固定手順では実行時文脈に脆く、未達条件に応じた手順生成が頑健。

### 完了チェックリスト (Checklist)

- [ ] Phase 1 思考リセットを経由し `shared_state.md`（200字以内）を生成した <!-- CL-1 exempt: 工程順序項目。validate-paradigm-coverage.py --phase-order が機械検査 -->
- [ ] `thought_method_coverage.used + skipped_with_reason == 30`（30 思考法全て使用 or skip_reason 付き） <!-- CL-2 -->
- [ ] `fail_counts.contradiction == 0`（矛盾なし） <!-- CL-3 -->
- [ ] `fail_counts.omission == 0`（漏れなし） <!-- CL-4 -->
- [ ] `fail_counts.inconsistency == 0`（整合性あり） <!-- CL-5 -->
- [ ] `fail_counts.dependency_break == 0`（依存関係整合） <!-- CL-6 -->
- [ ] `findings.json` が `schemas/findings.schema.json` を通過する <!-- CL-7 -->
- [ ] proposer ≠ approver を満たす（自己承認禁止、別 SubAgent or 人間が承認） <!-- CL-8 -->
- [ ] max_iter 未達のまま終了時は `status: incomplete` + force_pass 禁止で human_review へ差し戻した <!-- CL-9 -->

### ゴールシークループ

正本 6 ステップ（現状評価→手順生成→実行→検証→Anchor Step→反復、既定 5 周 / max_iter=3）に従う。固有差分: ループ本体は Phase 1→2→3 を SubAgent へ context fork して回し（親へは最終成果物 + handoff のみ返す）、Phase 1/2 は read-only、write は Phase 3 限定。判定は `scripts/validate-paradigm-coverage.py` で機械実行。下記 Phase 群は順序固定の手順ではなく、未達条件を埋める局面カタログとして都度選ぶ。

---

## Purpose & Output Contract

新規/更新 Skill・rubric 改訂・アーキテクチャ提案・量産 plugin package を 30 思考法で検証し 4 条件を全 PASS まで改善する（詳細はゴールシーク実行節）。**v2 位置づけ**: 25 章 §runbook の **Step 5.5**（PKG check と assign-skill-design-evaluator の中間）= 「**設計 elegance lint**」。契約適合・規範採点と責務直交。

### 役割直交（Step 5 / 5.5 / 6）

| Step | 役割 | 担当 skill |
|---|---|---|
| 5 | **契約適合**: PKG-001〜015 機械検査 | `run-plugin-package-check` |
| 5.5 | **設計 elegance**: 30 思考法 × 4 条件 lint | **本 skill** |
| 6 | **規範採点**: rubric 適合度 | `assign-skill-design-evaluator` |

dedup matrix と衝突時優先順位 (契約 > elegance > rubric) は `plugins/harness-creator/references/orchestrate-gate-pattern.md` に外出し (G9 resource-map 経由 lazy load)。

### 入力（v2 必須化）

```yaml
target:
  plugin: "harness-creator"                # plugin 名（kebab-case）
  skill: "run-skill-rename"              # skill 名（kebab-case）
  scope_mode: "skill"                    # {skill, plugin, repo} 閉列挙
context:
  build_log: "eval-log/.../build-XXX.json"   # run-build-skill 直後の生成ログ
  related_skills: []                      # 横断検証する関連 skill
options:
  dry_run: false                          # true なら write を禁止
  max_iterations: 3                       # 改善ループ上限
  skip_thought_methods: []                # 緊急時のみ。skip_reason 必須
```

`target.plugin` / `target.skill` / `target.scope_mode` は全て必須。`target_path` だけの後方互換呼出も `argument-hint` 経由で受理するが、内部で `target` 構造体に正規化する。

### 出力（v2 schema 固定）

- `findings.json` — `schemas/findings.schema.json` 準拠の集約 object。各 `paradigm_findings[]` が 30 思考法のいずれかに対応
- `thought_method_coverage` — `{used: [], skipped_with_reason: [], total: 30}`
- `verdict` — `{矛盾なし: PASS|FAIL, 漏れなし: PASS|FAIL, 整合性あり: PASS|FAIL, 依存関係整合: PASS|FAIL}`
- `review-<scope_mode>.md` — 人間可読レポート
- `eval-log/<plugin>/<skill>/elegant-review/<run-id>/` — 27 章 §3.1 規約準拠の保存先
- 改善 PR ブランチ — `auto_fixable=true` の finding を自動 commit、`auto_fixable=false` は人間判断

### 完了条件（4 条件 → 観測 signal）

各条件の PASS signal は上記ゴールシーク Checklist（`fail_counts.<signal> == 0`）と下記「検証 4 条件」テーブルを正本とする。`issues[].severity` は low/medium/high/critical の優先度、`condition_signal` は contradiction/omission/inconsistency/dependency_break/smell の機械観測 signal として分離する。`smell` は警告枠（PASS を妨げない）。判定は `scripts/validate-paradigm-coverage.py` と `verdict.json` で機械実行。

---

## 30 思考法カタログ（v2 配分均衡化）

`references/thought-methods.yaml` を機械可読正本とする。本文は早見表のみ。

| カテゴリ | 配分 | 思考法 | 担当 SubAgent |
|---|---|---|---|
| 論理分析系 (5) | A2 | 批判的 / 演繹 / 帰納 / アブダクション / 垂直 | `elegant-logical-structural-analyst` |
| 構造分解系 (4) | A2 | 要素分解 / MECE / 2 軸 / プロセス | 同上 |
| 問題解決系 A2 移管 (1) | A2 | why 思考 (B1 で A4 → A2 へ移管) | 同上 |
| メタ抽象系 (3) | A3 | メタ / 抽象化 / ダブル・ループ | `elegant-meta-divergent-analyst` |
| 発想拡張系 (6) | A3 | ブレインストーミング / 水平 / 逆説 / 類推 / if / 素人 | 同上 |
| システム系 (3) | A4 | システム / 因果関係 / 因果ループ | `elegant-system-strategic-analyst` |
| 戦略価値系 (4) | A4 | トレードオン / プラスサム / 価値提案 / 戦略的 | 同上 |
| 問題解決系 A4 残置 (4) | A4 | 改善 / 仮説 / 論点 / KJ 法 | 同上 |

**配分後**: A2=10 / A3=9 / A4=11（B1 反映：why 思考を A4 → A2 に移管し均衡化）

CONST_002（30 種全使用）は **「全種が finding を出す or `skip_reason` を残す」** に緩和（C1 解消、B4 早期終了との両立）。

---

## 検証 4 条件

| # | 条件 | condition_signal | 検査手法 |
|---|------|---|------|
| C1 | 矛盾なし (Consistency) | `contradiction` | claim graph で contradiction edge 検出 |
| C2 | 漏れなし (Completeness) | `omission` | required-element checklist 全件 PASS |
| C3 | 整合性あり (Coherence) | `inconsistency` | rubric_refs / 上位仕様との diff violation=0 |
| C4 | 依存関係整合 (Dependency) | `dependency_break` | DAG topological sort 成立 |

警告枠: `smell`（PASS を妨げない、改善示唆）。

---

## 実行フロー（v2 各フェーズ 4 項目明示）

`workflow-manifest.json` が正本。各フェーズは **入力 / 出力 / 完了判定 signal / 失敗時アクション** の 4 項目を必ず明示（D5）。

### Phase 1: 思考リセット（必須経由、スキップ不可 C3）

- **担当**: `elegant-reset-observer`（SubAgent 分離で context fork 強制、A2）
- **入力**: `target` 構造体
- **3 ステップ操作**（A2 実行可能化）:
  1. 先行 context 要約 → `shared_state.md` に 200 字以内で保存
  2. 明示破棄宣言 → SubAgent 内で「親 context を以降参照しない」宣言を発話
  3. 対象再読込 → `target.plugin` / `target.skill` の全関連ファイルを fresh で Read
- **出力**: `shared_state.md`（フェーズ 2 へのファンアウト中継、B6）
- **完了判定 signal**: `shared_state.md` 存在 + 全関連ファイル列挙完了
- **失敗時アクション**: abort（リセット失敗は致命的）

### Phase 2: 並列多角的分析（3 SubAgent ファンアウト）

- **担当**: `elegant-logical-structural-analyst` + `elegant-meta-divergent-analyst` + `elegant-system-strategic-analyst`（並列）
- **入力**: `shared_state.md` + 担当思考法サブセット
- **出力**: 各 SubAgent が `findings-phase2-<agent>.json` を独立出力
- **完了判定 signal**: 3 SubAgent 完了 + `thought_method_coverage.used + skipped_with_reason == 30`（B2、CONST_002 機械検証）
- **失敗時アクション**: 1 SubAgent 失敗時は他 2 つの結果を保持して continue、欠落分は次反復で補完

### Phase 3: 改善実行（ファンイン）

- **担当**: `elegant-improvement-executor`（必要時 `delegate-codex-skill-review` へ委譲、B5）
- **入力**: Phase 2 全 SubAgent の findings 集約
- **操作**: 依存 DAG 生成（B3, `findings[].location` または `paradigm_findings[].issues[].location` から自動構築）→ 優先順位決定（`issues[].severity`: critical > high > medium > low）→ 独立対象は並列・依存ありは直列で改善 → `auto_fixable=true` は自動 commit / `false` は提案のみ → 4 条件再検証（max_iter=3）
- **出力**: `schemas/findings.schema.json` 準拠の `findings.json` 最終版 + 改善 PR ブランチ
- **完了判定 signal**: 4 条件 PASS（contradiction/omission/inconsistency/dependency_break 全て 0 件）
- **失敗時アクション**:
  - max_iter 到達 → `status: incomplete`、`human_review` 必須、force_pass 禁止
  - 改善後に 4 条件悪化 → 自動改善コミットのみ revert（B7）

### Codex 委譲判定基準（B5）

次のいずれかで `delegate-codex-skill-review` SubAgent へ委譲（**Phase 3 限定**、Phase 1/2 中は禁止＝context 再汚染 C2）: 変更行数 > 50 / テスト変更含む（`tests/` `*_test.py` `*.spec.*`）/ 複数ファイル横断（`findings[].location` unique file 数 > 3）。

---

## 副作用境界 / ロールバック（B7）

- **Phase 1 / Phase 2 は read-only**: 対象を編集しない
- **Phase 3 のみ write 可**: 改善は集約済み findings に紐づく最小パッチに限定。改善前に必ず `git diff --binary > eval-log/<plugin>/<skill>/elegant-review/<run-id>/pre-phase3.patch` を取得
- **改善後に 4 条件悪化を検出**: 自動改善コミットだけを revert（既存ユーザー dirty state は stash/pop で触らない）
- **`dry_run=true`** は全フェーズで write 禁止。findings 出力のみ

## proposer ≠ approver（C4、23 章準拠）

本 skill の改善内容を「同じ context」が承認することを禁止。承認経路は次のいずれか：
- 別 SubAgent の `assign-skill-design-evaluator` による独立採点
- `governance-params.json: solo_operator_mode=false` の場合は人間レビュー必須
- `solo_operator_mode=true` でも自己承認は不可（必ず別 SubAgent context）

## 35 章 observable 配線（B8）

**trigger**: 4 条件のいずれかが FAIL、または `safety_valve_fired=true` の場合に emit (workflow-manifest.json `observable.trigger` と論理同一)。`scripts/emit-observable.py` が `.claude/logs/meta-harness.jsonl` に `elegant_review_4condition_failed` event を 1 行 append する。emit 呼出は `phases[phase3-execute].steps.step6` (always 実行) に一本化済 (G3, append-only jsonl 重複防止)。

emit event の具体例 (4 条件 FAIL / safety_valve_fired=true 双方) は `references/observable-emit-examples.md` を参照。`examples/safety-valve-fired-verdict.json` を `emit-observable.py --dry-run` に与えれば生成 event を確認できる。

35 章 `pkg_check_failed` と並走し、collect → classify → improve の閉ループを成立させる。

---

## 収束ループ設計（解像度 3 層 + 両輪フィードバック + 安全弁）

詳細は `references/convergence-policy.json` 参照。

| 層 | 出力 | 用途 |
|---|---|---|
| L1 | C1-C4 の PASS/FAIL (4bit) | 最終判定 |
| L2 | 各 C 条件・各思考法のスコア (0.0-1.0) | 周回内精緻評価 |
| L3 | 周回間 Δベクトル（正/負両方向） | 収束兆候検出 |

### 両輪フィードバック

- **負のフィードバック (Detector)**: C1-C4 違反検出 → 修正パッチ
- **正のフィードバック (Amplifier)**: 良パターン → `amplified-patterns.json` に蓄積 → 横展開

### 停止条件

1. **収束完了** (`Δneg < 0.10 AND Δpos < 0.10`): `status: complete`
2. **発散** (`Δneg 2周連続増加`): `human_escalate`
3. **安全弁発火** (`iteration_count >= max_iterations(=3)`): `status: incomplete`・force_pass 禁止・`human_review` 必須

---

## Gotchas

1. **30 思考法すべて省略禁止**: `scripts/validate-paradigm-coverage.py` が `thought_method_coverage.used + skipped_with_reason == 30` を機械検証。欠落で exit 1
2. **Phase 1 必須経由（C3）**: スキップ不可。リセット未経由のレビューは C2/C3 が偽陽性 PASS する
3. **Goodhart の罠**: score 最大化のために本質を歪めない
4. **Phase 2 並列前提**: 3 SubAgent は互いの中間結果を参照しない（独立性確保、SubAgent context 分離で強制）
5. **proposer ≠ approver（C4、23 章）**: 自己承認禁止
6. **Codex 委譲は Phase 3 限定（C2）**: Phase 1/2 で委譲すると context 再汚染
7. **`auto_fixable` 安易フラグ禁止**: 単純な path 修正・chmod 等のみ true。意味変更を伴う修正は必ず false
8. **`shared_state.md` は 200 字制限**: Phase 1 → 2 ファンアウト時に context 肥大を防ぐ
9. **PKG check 結果との衝突**: PKG-006（hook 整合）と本 skill の dependency_break が同一 finding を出す可能性。location が同じなら PKG check 側を優先（契約 > elegance）
10. **safety_valve_fired を成功扱いにしない**: max_iter 到達は failure。35 章 observable が必ず emit される

---

## Additional Resources

- 正本一覧は frontmatter (`reference_refs` / `schema_refs` / `script_refs` / `source_refs`) と `references/resource-map.yaml` (schemas / scripts / examples / related_skills / source_docs § ポインタ含む read_when 付き索引) を参照。
- 30 思考法の 1-2 行適用テンプレは `references/thought-methods.yaml` に外部化 (D2、本文再掲せず SubAgent 起動時に該当カテゴリを引用渡し)。

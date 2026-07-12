---
name: delegate-codex-skill-review
description: 自セッションで評価せず外部LLMに委譲したいとき、Sycophancyを避けたいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
kind: delegate
prefix: delegate
effect: none
delegate_agent: codex-cli
owner: team-platform
since: 2026-05-18
version: 0.1.0
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
hierarchy_level: L1
# delegate-* prefix の最小実例。Skill レビューを外部 codex CLI に委譲する。
responsibility_refs:
  - prompts/R1-delegate.md
  - prompts/R2-codex-review.md
schema_refs:
  - schemas/io-contract.schema.json
reference_refs:
  - references/codex-connection.md
  - references/resource-map.yaml
script_refs:
  - scripts/check-codex-installed.py
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: check-codex-installed.py が exit0 か未導入exit2 を判定し未導入時は任意拡張と案内して BLOCK し Node や npm を推奨しないこと
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 書き出す eval-log/delegate-codex-request.json が io-contract.schema.json に準拠し target_skill_path と rubric パスと任意実行コマンド例を含むこと
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 自セッションでスコアを付けず採点と結果保存を codex 実行ユーザー管理に委ね Sycophancy を避ける委譲境界が保たれていること
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: codex CLI を標準フローの必須依存にせず Node や npm や shell を opt-in cross-check に留める内製と委譲の補完関係が崩れていないこと
      verify_by: evaluator
---

# delegate-codex-skill-review

## Purpose & Output Contract

評価対象 Skill (SKILL.md) を任意の外部 `codex` CLI に渡すための手順と入力を作り、Sycophancy を避けた第三者レビューの準備をする。

**入力**: target_skill_path (SKILL.md への絶対パス)
**出力**: `eval-log/delegate-codex-request.json` (ユーザーが任意で実行する codex review 入力)

**完了条件**: codex CLI が標準フローの必須依存ではないことを保ったまま、任意実行用の入力とコマンド例が提示されている。

## 内製 vs 委譲の選定根拠 (PARA-001)

| 観点 | 内製 (`run-elegant-review`) | 外部委譲 (本 skill) |
|---|---|---|
| Sycophancy リスク | 高 (自己採点罠) | 低 (第三者 LLM) |
| 再現性 | 高 (schema 固定) | 中 (codex モデル更新で変動) |
| 依存 | Python 標準のみ | 外部 codex CLI 別途インストール |
| 適用シーン | 標準フロー全件 | 重要 PR / 自己採点疑義時の cross-check |

判断指針: 標準フローは内製で完結させ、本 skill は **opt-in の cross-check** として使う。両者は競合せず補完関係。

## Key Rules

1. **委譲先は任意**: `delegate_agent: codex-cli` は外部拡張の識別子であり、標準フローでは起動しない。
2. **入力のみ準備**: SKILL.md 本文と rubric パスを記録するが、自セッションで採点しない。
3. **結果はユーザー管理**: codex 実行はユーザーが明示的に行い、返答を eval-log/ に保存する。
4. **任意拡張**: Node / npm / shell script / codex CLI を標準依存にしない。存在確認は Python 標準ライブラリで行う。

## ゴールシーク実行

外部 `codex` CLI へレビューを委譲する実行系。固定手順ではなくゴール・チェックリストへ向けて反復する（正本 `run-build-skill/references/goal-seek-paradigm.md`）。

### ゴール (Goal)

codex CLI を標準フローの必須依存にしないまま、任意実行用の入力 `eval-log/delegate-codex-request.json` とコマンド例が提示され、自セッションでは採点していない状態になっている。

### 目的・背景 (Why)

自己採点の Sycophancy を避けるため、採点は第三者 LLM (codex) に委ね、本 Skill は入力準備と結果提示に徹する（opt-in cross-check）。

### 完了チェックリスト (Checklist)

- [ ] `check-codex-installed.py` が exit 0、または未導入 (exit 2) なら任意拡張と案内し BLOCK している
- [ ] `target_skill_path` が存在し SKILL.md であることを検証済み
- [ ] io-contract (`schemas/io-contract.schema.json`) 準拠の `eval-log/delegate-codex-request.json` と任意実行コマンド例を提示済み
- [ ] 自セッションでスコアを付けていない（codex 実行・結果保存はユーザー管理）

### ゴールシークループ

正本の 6 ステップ（現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し）に従う。固有差分: codex 実行自体はループ外（ユーザーが任意で行う）。本 Skill のループは「入力準備が io-contract を満たす」まで回し、委譲結果を自セッションで再評価しない。

### 局面カタログ（順序は都度判断）

- **codex 存在確認 (決定論)**:

  ```bash
  python3 plugins/harness-creator/skills/delegate-codex-skill-review/scripts/check-codex-installed.py
  ```
  exit 2 が返ったら BLOCK。標準フローではなく任意拡張であることを案内して停止。
- **target 検証**: `target_skill_path` が存在し SKILL.md であることを確認。
- **任意実行コマンドの提示** (正本 `references/codex-connection.md`):

  ```bash
  codex --prompt "$(cat plugins/harness-creator/skills/delegate-codex-skill-review/prompts/R2-codex-review.md)" \
        --context-file eval-log/delegate-codex-request.json \
        --output-format text \
        --approval-mode yolo \
        > eval-log/delegate-codex-response.json
  ```
  codex に subcommand は無く `--prompt` 直接指定。rubric (`ref-skill-design-rubric/references/rubric.json` の critical axis) は R2 プロンプト本文へ焼き込み、別フラグでは渡さない。このコマンドは自動実行しない。codex CLI を導入済みのユーザーが任意で実行する。
- **結果提示**: 書き出した JSON のサマリをユーザーに返す。修正判断は委ねる。

## Gotchas

- **委譲結果を再評価しない**: 自セッションでスコア改竄をしない (09章 Sycophancy 防止)。
- **codex 未インストール時**: BLOCK するが、Node/npm を案内しない。公式に確認済みの配布元をユーザーが選ぶ。
- **L1 階層**: codex CLI 抽象 (L1)。プロジェクト固有の review 観点は L2 で wrap する。

## Additional Resources

- 設計書: `06-classification-and-naming.md` (delegate-* prefix), `09-evaluation-orchestration.md`
- 委譲先: codex CLI (https://github.com/openai/codex 等、要別途インストール)

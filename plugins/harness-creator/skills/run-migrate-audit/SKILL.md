---
name: run-migrate-audit
description: 既存 CLAUDE.md/prompt 集を Skill 群へ移行したいとき、棚卸し分類を機械化したいときに使う。
effect: local-artifact
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Grep, Glob]
kind: run
prefix: run
owner: team-platform
since: 2026-05-19
version: 0.1.0
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/20-migration-path.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
role_suffix: orchestrator
hierarchy_level: L1
pair: assign-skill-design-evaluator
rubric_refs:
  - ref-skill-design-rubric
reference_refs:
  - ref-claude-code-skill-spec
  - ref-skill-naming-convention
  - ref-cross-platform-runtime
responsibility_refs:
  - prompts/R1-audit.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 分類JSONの全sectionがdoc/20の8区分(always-on/ref/run/wrap/assign/delegate/hook/docs)のいずれかに収まりlint-skill-dep-step7の5条件を全PASSする
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: suggested_skill_nameから具体プロジェクト名とドメイン語が{{var}}へ抽象化され入力ファイルが物理削除されずkept_in_claude_mdが0でない
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 本briefの分類粒度と抽象度が下流run-build-skill内蔵の設計評価ゲート(assign-skill-design-evaluator採点)を通過しうる設計妥当性を備え、ゲート未達時に上位orchestratorが該当sectionを本skillへ再分類差し戻しできる構造になっている(本skillはbrief確定で完了しverdictを待たない)
      verify_by: evaluator
    - id: OUT2
      loop_scope: outer
      text: 各分類の1行根拠が後段evaluatorのjudgeを成立させ移行先Skill候補が横展開可能な抽象度に最適化されている
      verify_by: elegant-review
---

# run-migrate-audit

## Purpose & Output Contract
肥大化した prompt / CLAUDE.md / docs を doc/20-migration-path.md の 8 区分に
自動分類し、移行先 Skill 候補（ref-* / run-* / wrap-* / assign-* / delegate-*）と
Hook/CI/CLI 化候補を JSON で出力する。

### 出力 contract
`.claude/handoff/migrate-audit-<session>.json`:
```json
{
  "input_file": "{{path}}",
  "sections": [
    {
      "heading": "...",
      "classification": "always-on|ref|run|wrap|assign|delegate|hook|docs",
      "rationale": "...",
      "suggested_skill_name": "ref-..."
    }
  ],
  "summary": {
    "ref_candidates": 0,
    "run_candidates": 0,
    "hook_candidates": 0,
    "kept_in_claude_md": 0
  }
}
```

## Boundary
- **入口**: 既存 CLAUDE.md / prompt ファイルパス（複数可）
- **出口**: 分類 JSON + 各候補に対する空 SKILL.md スケルトン提案
- **非責務**: 実際の SKILL.md 生成とその設計評価（`assign-skill-design-evaluator` 採点）→ 下流 `run-build-skill`（内蔵の設計評価ゲート）に委譲

## Key Rules
1. 入力を物理削除しない（思考リセット ≠ ファイル削除）
2. doc/20 Step 1 の 8 区分以外を勝手に作らない
3. **抽象化レベル**: 入力中の具体的なプロジェクト名 / ドメイン語は `{{var}}` 化して提案する
4. 分類根拠を 1 行以内で明示する（後段 evaluator が judge できるよう）

## ゴールシーク実行

### ゴール (Goal)

入力 CLAUDE.md/prompt 群が doc/20 の 8 区分へ分類され、各候補の移行先 Skill 名・根拠を含む分類 JSON と空 SKILL.md スケルトン提案が出力され、依存関係 lint（5 条件含む）を通過した brief が `run-build-skill` へ引き渡せる形で確定した状態。生成された SKILL.md の設計評価（`assign-skill-design-evaluator` 採点・閾値判定）は下流 `run-build-skill` 内蔵ゲートの責務であり、本 skill 自身は verdict を待たず brief/分類の確定で完了する。ゲート未達時の再分類は上位 orchestrator が該当 section で本 skill を再起動して行う（本 skill は評価器も run-build-skill も invoke しないため verdict を自ら受け取らない）。

### 目的・背景 (Why)

肥大化した prompt/docs の棚卸し分類を機械化し、横展開可能な抽象化された Skill 候補へ落とすため。入力構造（章立て・ドメイン語密度）に依存し固定手順では誤分類耐性が低いので、到達状態（分類 JSON + 依存 lint 通過 brief）をゴールに据える。実際の SKILL.md 生成とその設計評価は責務外（下流 run-build-skill が内蔵ゲートで担う）。

### 完了チェックリスト (Checklist)

- [ ] 入力棚卸し (`migrate/audit.py --input <path> --output .claude/handoff/migrate-audit-<session>.json`) を実施し、各 section が 8 区分（always-on/ref/run/wrap/assign/delegate/hook/docs）のいずれかに分類済み
- [ ] 各分類に 1 行以内の根拠（後段 evaluator が judge 可能）が付与されている
- [ ] 具体プロジェクト名 / ドメイン語が `{{var}}` へ抽象化された suggested_skill_name になっている
- [ ] 分類結果がユーザーへ提示され、誤分類は手動修正済み
- [ ] `migrate/to-brief.py --audit-json ...` で run-build-skill 起動 brief を生成済み
- [ ] Gotchas 累積閾値超えの section に `frontmatter lint -> Hook -> CI -> CLI` 昇格パスが示されている
- [ ] `lint-dependency-direction.py --skills-dir .claude/skills/` が通過している
- [ ] brief を `run-build-skill` へ引き渡せる形で確定した（本 skill の完了はこの brief/分類の確定まで。SKILL.md 生成とその設計評価＝`pair:` 宣言の `assign-skill-design-evaluator` fork 採点は下流 run-build-skill 内蔵ゲートが担当し、ゲート未達時の再分類は上位 orchestrator が該当 section で本 skill を再起動して行う）
- [ ] `lint-skill-dep-step7.py --skills-dir .claude/skills/` の 5 条件（wrap に base / evaluator に pair / pair 相手の存在 / dangerous run に DMI=true / ref が到達不能でない）が全 PASS
- [ ] 入力ファイルを物理削除していない（思考リセット≠削除）
- [ ] `kept_in_claude_md` が 0 でない（repo identity 等は CLAUDE.md に最低限残す）

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップに従う。本スキル固有差分:

- 対象ファイル: 入力 CLAUDE.md/prompt（複数可・read-only / 物理削除禁止）、出力 `.claude/handoff/migrate-audit-<session>.json`（分類 JSON）と run-build-skill 引き渡し用 brief
- 引き渡し先: `run-build-skill`（brief handoff）。設計評価＝`pair:` 宣言の `assign-skill-design-evaluator` fork 採点は run-build-skill 内蔵ゲートが担い、本 skill は評価器も run-build-skill も直接 invoke せず brief 確定で完了する。ゲート未達 verdict を契機とする再分類は上位 orchestrator が本 skill を再起動して行う（本 skill 自身は verdict を待たない）
- 固定パス/閾値: doc/20 の 8 区分以外を作らない、step7 の 5 条件は全 PASS 必須。下流ゲートの評価器スコア閾値未満は上位 orchestrator 経由で該当 section を再分類差し戻し
- 中間状態（部分完了）で lint を fail させない（`--allow-partial`）。決定論的検査は `## 検証`/lint へ寄せ `[x]` 判定する
- 規定周回を超えても未達なら残項目を `open_issues` として記録し上位 orchestrator へ差し戻す

### 局面カタログ (順序は都度判断)

- 入力棚卸し: `python3 plugins/skill-governance-migration/scripts/migrate/audit.py --input <CLAUDE.md path> --output .claude/handoff/migrate-audit-$(date +%s).json`
- レビュー: 分類 JSON をユーザー提示し誤分類を手動修正
- brief 生成: `python3 plugins/skill-governance-migration/scripts/migrate/to-brief.py --audit-json .claude/handoff/migrate-audit-<session>.json`
- 昇格候補抽出: Gotchas 累積閾値超え → `frontmatter lint -> Hook -> CI -> CLI`
- 移行後 lint: `python3 plugins/skill-governance-lint/scripts/lint-dependency-direction.py --skills-dir .claude/skills/`
- 引き渡し・再起動受け: 確定 brief を `run-build-skill` へ渡す。生成後 SKILL.md の設計評価（`assign-skill-design-evaluator` fork 採点）は run-build-skill 内蔵ゲートが実施する。ゲート未達時は上位 orchestrator が本 skill を該当 section で再起動し brief を再分類する（本 skill 自身は verdict を待たず brief 確定で完了）
- 依存 lint(5条件): `python3 plugins/skill-governance-lint/scripts/lint-skill-dep-step7.py --skills-dir .claude/skills/`

## Gotchas
- 中間状態（Step1〜4 部分完了）で lint を fail させない（`--allow-partial` モード）
- 具体ドメイン語を Skill 名に焼き込まない（横展開不能になる）
- `kept_in_claude_md` が 0 になったら警告（CLAUDE.md は repo identity 等で最低限残すべき）

## Additional Resources
- 設計書 20 章 全 7 ステップ
- `references/classification-rules.md` — 8 区分判定ルール
- `references/abstraction-checklist.md` — 具体名 → 変数化の判定基準

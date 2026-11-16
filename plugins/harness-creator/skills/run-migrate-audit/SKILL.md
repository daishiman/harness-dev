---
name: run-migrate-audit
description: 既存 CLAUDE.md/prompt 集を Skill 群へ移行したいとき、棚卸し分類を機械化したいときに使う。
effect: local-artifact
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Grep, Glob]
kind: run
prefix: run
goal_seek:
  engine: inline
  fork: inline
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
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 分類JSONの全sectionがdoc/20の8区分(always-on/ref/run/wrap/assign/delegate/hook/docs)のいずれかに収まり、移行先skills dirの*/SKILL.mdが1件以上あるときはlint-skill-dep-step7の5条件を全PASSする(dirが無いか0件なら基準線なしと記録してN/A)
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
artifact_delivery: artifact-delivery-v1
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/diagnoseを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはdiagnoseが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-migrate-audit

## Purpose & Output Contract
肥大化した prompt / CLAUDE.md / docs を doc/ClaudeCodeスキルの設計書/20-migration-path.md の 8 区分に
自動分類し、移行先 Skill 候補（ref-* / run-* / wrap-* / assign-* / delegate-*）と
Hook/CI/CLI 化候補を JSON で出力する。

8 区分は doc/20 Step 1 の表 9 行のうち、移行先が CLAUDE.md・Skill・Hook/CI/CLI・docs になる 8 行に当たる
(always-on/ref/run/wrap/assign/delegate/hook/docs)。9 行目の「外部プロトコル/接続面 → MCP / plugin / app connector」は
Skill へ分解せず接続の設定として移すものなので、区分を立てない。該当 section も 8 区分のうち最も近いもの
(多くは ref) に分類し、`rationale` の先頭に `connector-candidate:` と書いて、接続面への移行を上位 orchestrator の判断に回す。

### 出力 contract
`.claude/handoff/migrate-audit-<session>.json` (`schemas/output.schema.json` 準拠。`additionalProperties: false`):
```json
{
  "input_file": "{{path}}",
  "origin": "article|internal-doc|external-spec|unknown",
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
    "kept_in_claude_md": 0,
    "total_sections": 0
  }
}
```

`suggested_skill_name` は always-on と docs では `null`。`origin` は入力 path から派生し、brief の `source-tier` の元になる。

### 引き渡し brief
`.claude/handoff/migrate-brief-<session>.json` (`to-brief.py --audit-json <分類 JSON> --output <この path> --owner <owner>` の出力):
```json
{
  "briefs": [
    {
      "skill_name": "ref-...",
      "kind": "ref",
      "origin_heading": "...",
      "source": "{{path}}",
      "source-tier": "internal",
      "origin": "internal-doc",
      "rationale": "...",
      "owner": "{{owner}}"
    }
  ],
  "count": 1
}
```

`suggested_skill_name` が `null` の section は brief に入らない。brief は Skill 1 件ごとの生成入力で、
SKILL.md の骨格と本文は `run-build-skill` が作る。`--owner` を省くと `TODO_SET_OWNER` が入る。下流の frontmatter 検査 (`validate-frontmatter.py`) は owner があることしか見ずこの値では止まらないので、残っていないことは本 skill の完了チェックリストで確かめる。

## Boundary
- **入口**: 既存 CLAUDE.md / prompt ファイルパス（複数可）
- **出口**: 分類 JSON と引き渡し brief (上の 2 つの path)
- **非責務**: 実際の SKILL.md 生成とその設計評価（`assign-skill-design-evaluator` 採点）→ 下流 `run-build-skill`（内蔵の設計評価ゲート）に委譲。接続面 (MCP / plugin / app connector) への移行

## Key Rules
1. 入力を物理削除しない（思考リセット ≠ ファイル削除）
2. doc/20 Step 1 の 8 区分以外を勝手に作らない (接続面の section は上の `connector-candidate:` の扱いにする)
3. **抽象化レベル**: 入力中の具体的なプロジェクト名 / ドメイン語は `{{var}}` 化して提案する
4. 分類根拠を 1 行以内で明示する（後段 evaluator が judge できるよう）

## ゴールシーク実行

### ゴール (Goal)

入力 CLAUDE.md/prompt 群が doc/20 の 8 区分へ分類され、各候補の移行先 Skill 名・根拠を含む分類 JSON と引き渡し brief が出力され、移行先 skills dir の基準線が確かめられたうえで brief が `run-build-skill` へ引き渡せる形で確定した状態。基準線は、移行先の `*/SKILL.md` が 1 件以上あれば既存 skill 群が依存関係 lint（5 条件含む）を通過していること、dir が無いか 0 件なら「基準線なし」と記録してあることである。生成された SKILL.md の設計評価（`assign-skill-design-evaluator` 採点・閾値判定）は下流 `run-build-skill` 内蔵ゲートの責務であり、本 skill 自身は verdict を待たず brief/分類の確定で完了する。ゲート未達時の再分類は上位 orchestrator が該当 section で本 skill を再起動して行う（本 skill は評価器も run-build-skill も invoke しないため verdict を自ら受け取らない）。

### 目的・背景 (Why)

肥大化した prompt/docs の棚卸し分類を機械化し、横展開可能な抽象化された Skill 候補へ落とすため。入力構造（章立て・ドメイン語密度）に依存し固定手順では誤分類耐性が低いので、到達状態（分類 JSON + brief と、移行先の既存 skill 群に当てた基準線 lint の結果。lint の対象は brief ではない）をゴールに据える。実際の SKILL.md 生成とその設計評価は責務外（下流 run-build-skill が内蔵ゲートで担う）。

### 完了チェックリスト (Checklist)

- [ ] 入力棚卸し (`migrate/audit.py --input <path> --output .claude/handoff/migrate-audit-<session>.json`) を実施し、各 section が 8 区分（always-on/ref/run/wrap/assign/delegate/hook/docs）のいずれかに分類済み
- [ ] 各分類に 1 行以内の根拠（後段 evaluator が judge 可能）が付与されている
- [ ] 具体プロジェクト名 / ドメイン語が `{{var}}` へ抽象化された suggested_skill_name になっている
- [ ] 分類結果がユーザーへ提示され、誤分類は手動修正済み
- [ ] `migrate/to-brief.py --audit-json ... --output .claude/handoff/migrate-brief-<session>.json --owner <owner>` で run-build-skill 起動 brief を生成済み (owner が `TODO_SET_OWNER` のまま残っていない)
- [ ] 接続面 (MCP / plugin / app connector) に当たる section の `rationale` が `connector-candidate:` で始まっている
- [ ] Gotchas 累積閾値超えの section に `frontmatter lint -> Hook -> CI -> CLI` 昇格パスが示されている
- [ ] 移行先 skills dir (既定は `.claude/skills/`) の `*/SKILL.md` の件数を数え、引き渡しの提示に書いた。dir が無いか 0 件なら「基準線なし」と書き、次の 2 つの lint 項目は N/A とする
- [ ] 基準線あり (1 件以上) のとき: `lint-dependency-direction.py --skills-dir <移行先 skills dir>` が exit 0
- [ ] 基準線あり (1 件以上) のとき: `lint-skill-dep-step7.py --skills-dir <移行先 skills dir>` の 5 条件（wrap に base / evaluator に pair / pair 相手の存在 / dangerous run に DMI=true / ref が到達不能でない）が全 PASS (exit 0)
- [ ] brief を `run-build-skill` へ引き渡せる形で確定した（本 skill の完了はこの brief/分類の確定まで。SKILL.md 生成とその設計評価＝`pair:` 宣言の `assign-skill-design-evaluator` fork 採点は下流 run-build-skill 内蔵ゲートが担当し、ゲート未達時の再分類は上位 orchestrator が該当 section で本 skill を再起動して行う）
- [ ] 入力ファイルを物理削除していない（思考リセット≠削除）
- [ ] `kept_in_claude_md` が 0 でない（repo identity 等は CLAUDE.md に最低限残す）

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップに従う。本スキル固有差分:

- 対象ファイル: 入力 CLAUDE.md/prompt（複数可・read-only / 物理削除禁止）、出力 `.claude/handoff/migrate-audit-<session>.json`（分類 JSON）と run-build-skill 引き渡し用 brief
- 引き渡し先: `run-build-skill`（brief handoff）。設計評価＝`pair:` 宣言の `assign-skill-design-evaluator` fork 採点は run-build-skill 内蔵ゲートが担い、本 skill は評価器も run-build-skill も直接 invoke せず brief 確定で完了する。ゲート未達 verdict を契機とする再分類は上位 orchestrator が本 skill を再起動して行う（本 skill 自身は verdict を待たない）
- 固定パス/閾値: doc/20 の 8 区分以外を作らない。基準線あり (移行先の `*/SKILL.md` が 1 件以上) のとき、依存方向 lint と step7 の 5 条件は全 PASS 必須 (dir が無いか 0 件なら基準線なしとして N/A。lint の exit を見て N/A にはしない)。下流ゲートの評価器スコア閾値未満は上位 orchestrator 経由で該当 section を再分類差し戻し
- 中間状態（部分完了）で lint を fail させない（`--allow-partial`）。決定論的検査は `## 検証`/lint へ寄せ `[x]` 判定する
- 規定周回を超えても未達なら残項目を `open_issues` として記録し上位 orchestrator へ差し戻す

### 局面カタログ (順序は都度判断)

- 入力棚卸し: `python3 plugins/skill-governance-migration/scripts/migrate/audit.py --input <CLAUDE.md path> --output .claude/handoff/migrate-audit-$(date +%s).json`
- レビュー: 分類 JSON をユーザー提示し誤分類を手動修正
- brief 生成: `python3 plugins/skill-governance-migration/scripts/migrate/to-brief.py --audit-json .claude/handoff/migrate-audit-<session>.json --output .claude/handoff/migrate-brief-<session>.json --owner <owner>`
- 昇格候補抽出: Gotchas 累積閾値超え → `frontmatter lint -> Hook -> CI -> CLI`
- 移行先 lint: `python3 plugins/skill-governance-lint/scripts/lint-dependency-direction.py --skills-dir <移行先 skills dir>`。本 skill は SKILL.md を作らないので、この lint と下の 5 条件 lint が確かめるのは、候補を足す先の既存 skill 群が依存規則を満たしていること (候補を足す前の基準線) である。生成した SKILL.md の lint は下流 `run-build-skill` が行う
  - 基準線の有無は、lint を回す前に移行先の `*/SKILL.md` の件数で決める。dir が無いか 0 件 (初回の移行で多い) なら「基準線なし」と引き渡しの提示に書き、2 つの lint は回さず N/A にする。この場合、step7 lint は exit 2 (空なら usage、無ければ not a directory)、依存方向 lint は dir が無ければ exit 2・空なら 0 件のまま exit 0 になる。どちらの結果も基準線を表さないので、lint の結果では判定しない
  - 1 件以上なら 2 つの lint を両方回し、どちらも exit 0 を求める。このときの exit 2 は、依存方向 lint では循環の検出、step7 lint では Step 7-4 を確かめられないことを表すので、N/A にせず未達とする
- 引き渡し・再起動受け: 確定 brief を `run-build-skill` へ渡す。生成後 SKILL.md の設計評価（`assign-skill-design-evaluator` fork 採点）は run-build-skill 内蔵ゲートが実施する。ゲート未達時は上位 orchestrator が本 skill を該当 section で再起動し brief を再分類する（本 skill 自身は verdict を待たず brief 確定で完了）
- 依存 lint(5条件): `python3 plugins/skill-governance-lint/scripts/lint-skill-dep-step7.py --skills-dir <移行先 skills dir>`。基準線の有無の判定は上の「移行先 lint」と同じ

## Gotchas
- 中間状態（Step1〜4 部分完了）で lint を fail させない（`--allow-partial` モード）
- 具体ドメイン語を Skill 名に焼き込まない（横展開不能になる）
- `kept_in_claude_md` が 0 になったら警告（CLAUDE.md は repo identity 等で最低限残すべき）

## Additional Resources
- `doc/ClaudeCodeスキルの設計書/20-migration-path.md` — 設計書 20 章 全 7 ステップ
- `references/classification-rules.md` — 8 区分判定ルール
- `references/abstraction-checklist.md` — 具体名 → 変数化の判定基準

---
name: run-skill-intake
description: 非エンジニアからスキル要件を引き出すとき、intake 11 phase ワークフローを順次起動して intake.md と Notion ページを生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
  - AskUserQuestion
  - Skill
  - Task
kind: run
prefix: run
user-invocable: true
disable-model-invocation: true
effect: external-mutation
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
version: 0.2.0
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
  - schemas/phase2-assumption.schema.json
  - schemas/phase3-profile.schema.json
  - schemas/phase5-purpose.schema.json
  - schemas/phase8-summary.schema.json
reference_refs:
  - ref-workflow-sequence
  - ref-handoff-contract
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: workflow-manifest.json の phases[] を本 SKILL.md へ複製せず manifest を唯一の SSOT として参照する(二重管理 drift がない)。lint-manifest-contents.py exit 0。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: スキル生成スキル(run-skill-create/run-build-skill/capability-build 等)の起動禁止が hook-guard-skillgen.py(PreToolUse, exit 2)で機械強制され、intake 実行中フラグ駆動の遮断が回帰テストで担保されている。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 業務ロジック(質問雛形・採点基準・Notion blocks 生成)を持たず 11 phase を Skill/SubAgent へ委譲し handoff JSON 契約のみで橋渡しする薄い orchestrator 設計が、非エンジニアの曖昧要望から実装可能な intake 仕様まで橋渡しする目的を最適に反映している。
      verify_by: elegant-review
---

# run-skill-intake

## Purpose & Output Contract

intake plugin の中核 orchestrator。`workflow-manifest.json` の `phases[]` を SSOT として 11 phase を子 Skill / SubAgent に順次委譲し、最終成果物 `intake.md` / `intake.json` / Notion URL を生成する**薄い orchestrator**。各 phase の業務ロジック (質問雛形・採点基準・図解生成) は持たない。

**入力**: ユーザーの「スキルを作りたい」要望 (topic 引数任意) + 任意の Notion 明示指定 (`--page-url` / `--page-id` / `--database-id`)。Notion 明示指定は `notion_target` として intake.json に保持し、Phase 10 publish まで落とさない。

**出力**:

| 成果物 | パス | 生成 phase |
|--|--|--|
| kickoff.json | `output/<hint>/kickoff.json` | P1 |
| assumption.json | `output/<hint>/assumption.json` | P2 |
| profile.json | `output/<hint>/profile.json` | P3 |
| sheet.md + interview.json | `output/<hint>/` | P4 |
| purpose.json | `output/<hint>/purpose.json` | P5 |
| options.json | `output/<hint>/options.json` | P6 |
| visuals.json + PNG 群 | `output/<hint>/visuals/` | P7 |
| summary.{md,json} | `output/<hint>/` | P8 |
| intake.{md,json} | `output/<hint>/` | P9 |
| notion-url.txt | `output/<hint>/notion-url.txt` | P10 |
| next-action.json | `output/<hint>/next-action.json` | P11 |
| intake-trace.json | `eval-log/intake-trace.json` | 全 phase 共通 |

**完了条件**: `workflow-manifest.json` の全 phase が success + `quality_gate.py` PASS + `cross_check.py` PASS + Notion 公開成功 + 完了レポート (日本語本文、パラメーター名のみ英語) 提示。

## Key Rules

1. **manifest を SSOT とする**: 固定 Steps を本文に書かず `workflow-manifest.json` の `phases[]` (id / dependsOn / delegateType / delegateName / fatal_exit_codes) を読み実行順を決める。
2. **業務ロジックを持たない**: 質問雛形 / 技法選択 / 採点基準 / Notion blocks 生成は子 Skill / SubAgent / references に閉じる。本スキルは起動順序と handoff JSON の受け渡しのみ。
3. **handoff JSON 必須**: 各 phase 完了時に対応 JSON ファイルが存在し、`workflow-manifest.json` と各 skill / SubAgent の `schemas/` 契約に通ること。違反時はその phase に戻す。
4. **SubAgent fresh context (context:fork)**: Phase 2 / 3 / 5 / 8 はバイアス回避・同意ループ防止のため Task tool で SubAgent 起動し主スレッド context を渡さない。Phase 1 / 4 / 6 / 7 / 9 / 10 / 11 は Skill tool で主スレッド起動。
5. **失敗で停止**: phase が exit != 0 / handoff JSON 検証 fail / fatal_exit_codes hit なら停止し `intake-trace.json` に再開ポイントを記録、ユーザーへ提示。
6. **Secret-Out-of-Repo**: Notion トークンは Keychain から都度取得 (`scripts/keychain_get_secret.py`)。リポジトリへ書き込まない。
7. **Gate A (Phase 8) で停止可能**: summary 否認時は Phase 4 へ戻り再ヒアリング (最大 2 周)。
8. **lint 自動修正禁止**: P0 lint fail は根本原因をユーザー提示し AI 判断で勝手に修正しない。
9. **スキル生成を絶対に実行しない (hard stop / 機械強制)**: 本スキルは **ヒアリング〜Notion 公開〜Phase 11 next-action 推奨**までで完結し、`run-skill-create` / `run-build-skill` / `capability-build` 等のスキル生成スキルを **Skill / Task / Bash いずれでも起動しない**。Phase 11 の `next-action.json` の `mode` は**推奨情報**に過ぎず、本スキルがそれを実行に移すことはない。Phase 11 完了 = ワークフロー終了であり、完了レポート提示後は必ず停止する。スキル生成はユーザーが別途明示的に開始する**独立アクション**である (intake が `run-skill-create` の Step 1 として呼ばれた場合のみ上位が後続を駆動する。intake 自身は駆動しない)。
   - **この禁止は自然言語の指示だけに依存しない (100% 機械保証)**: `hooks/hook-guard-skillgen.py` (PreToolUse: Skill|Task|Bash) が、`run-skill-intake` 実行中フラグ (lock) を hook 駆動で立て、intake 実行中に生成スキルが起動されると **exit 2 でツール呼び出し自体をハーネスがブロック**する。lock の作成・遮断・解除は全て hook が行いモデル挙動に依存しない。本 Key Rule (プロンプト層) は「なぜ止まるか」の意図説明であり、保証の主体は hook 層である。配線は `.claude-plugin/plugin.json`、実証は `tests/test_skill_intake_guard_skillgen.py`。

## ゴールシーク実行

### ゴール (Goal)

ユーザー要望から `output/<hint>/intake.{md,json}` と Notion ページ URL が生成され、`workflow-manifest.json` の 11 phase が全 success、`quality_gate.py` / `cross_check.py` PASS、`eval-log/intake-trace.json` に全 phase の {started_at / finished_at / handoff_path / status} が記録され、完了レポートが日本語本文で提示された状態になっている。

### 目的・背景 (Why)

非エンジニアの曖昧要望から実装可能な intake 仕様まで橋渡しする intake plugin の中核 orchestrator。固定 Steps は入力 (topic) ・Gate A 否認・Phase 5 スキップ条件・lint 失敗・Notion 公開失敗など実行時文脈に脆い。固定手順を踏まず、未達 phase を `workflow-manifest.json` の `phases[]` 順で都度埋める反復構造で達成する。各 phase は独立 Skill / SubAgent に委譲し、本スキルは制御 (依存解決・handoff 検証・再開ポイント記録) のみを担う。

### 完了チェックリスト (Checklist)

- [ ] `Step 0` 前提検証 PASS (`validate-notion-ready.py --check-api` exit 0)。PASS 済みなら API キー / Notion トークンをユーザーに再質問しない。exit 44 のときだけ `references/keychain-setup.md` を案内し停止
- [ ] `output/<hint>/` と `eval-log/intake-trace.json` 初期化済み (hint は topic から仮決定)
- [ ] Phase 1 (`run-intake-kickoff`, Skill) success → `kickoff.json` schema validate PASS
- [ ] Phase 2 (`skill-intake-assumption-challenger`, SubAgent / context:fork) success → `assumption.json` schema validate PASS
- [ ] Phase 3 (`skill-intake-user-profiler`, SubAgent / context:fork) success → `profile.json` schema validate PASS
- [ ] Phase 4 (`run-intake-interview`, Skill) success → `sheet.md` + `interview.json` schema validate PASS。`intent_contract.slot_status` 全 slot filled=true、`pending_probes=[]`、`needs_excavation` flag 確定。未充足なら Phase 4 に戻り `probe-pattern-table.json` の固定 probe で追加ヒアリング
- [ ] Phase 5 (`skill-intake-purpose-excavator`, SubAgent / context:fork) success → `purpose.json` schema validate PASS。`interview.json.needs_excavation=false` なら skip 理由を `intake-trace.json` に記録
- [ ] Phase 6 (`run-intake-option-catalog`, Skill) success → `options.json` schema validate PASS
- [ ] Phase 7 (`run-intake-visualize`, Skill) success → `visuals.json` + PNG 群生成
- [ ] Phase 8 (`skill-intake-summarizer`, SubAgent / context:fork, Gate A) success → `summary.{md,json}` + ユーザー承認取得 (否認時 Phase 4 へ戻し最大 2 周)
- [ ] Phase 9 (`run-intake-finalize`, Skill) success → `intake.{md,json}` 生成
- [ ] Phase 10 (`run-notion-intake-publish`, Skill) success → `notion-url.txt` 生成 (fidelity-guard 内部起動、指定 page がある場合は PATCH 専用)
- [ ] Phase 11 (`run-intake-next-action`, Skill) success → `next-action.json` (Notion 公開完了後に harness-creator 引き渡しモード判定済み)
- [ ] `intake.json.notion_target` が存在し、update mode では `notion-publish-result.json.page_id` と一致している。未公開・不一致なら `run-skill-create` へ渡していない
- [ ] `quality_gate.py output/<hint>/intake.json` PASS
- [ ] `cross_check.py output/<hint>/intake.json output/<hint>/intake.md` PASS
- [ ] `eval-log/intake-trace.json` に全 phase の `{phase, agent, started_at, finished_at, handoff_path, status}` 記録済み
- [ ] 完了レポート提示済み (項目: hint / phases_succeeded / gate_a_result / skip_reasons / notion_url / next_action_mode、日本語本文・パラメーター名は英語)。`next_action_mode` は**推奨として**提示し、「次に `run-skill-create` を起動するとスキル生成に進めます (任意・別アクション)」と案内するに留める
- [ ] 完了レポート提示後に **`run-skill-create` / `run-build-skill` / `capability-build` 等のスキル生成を起動していない** (Key Rule 9 / Gotcha 8。intake はここで停止する)

### ゴールシークループ

`workflow-manifest.json` の `phases[]` を SSOT として、現状評価 → 次の未達 phase 特定 → 起動 → 検証 → 反復 / 差し戻しを回す。本スキル固有の差分は以下:

- **未達評価の単位は phase**: `intake-trace.json` の最新 status を読み、最初の `status != success` な phase を次のターゲットにする。`dependsOn` 全 success が前提。違反 (依存未満) なら依存元へ戻す。
- **委譲先**: `workflow-manifest.json` の `delegateType` / `delegateName` を唯一の起動契約とする。`delegateType=skill` は Skill tool、`delegateType=agent` は Task tool (SubAgent / context:fork) で起動する。本スキルは制御のみで業務ロジックを持たない。
- **context:fork 必須箇所**: Phase 2 / 3 / 5 / 8。主スレッド context を渡さず Task tool で fresh agent 起動 (バイアス回避・同意ループ防止)。
- **handoff 検証**: 各 phase 完了直後に `workflow-manifest.json` と各 delegate の `schemas/` 契約を確認する。fail なら同 phase へ差し戻し (最大 3 周、`fatal_exit_codes=[2,3]`)。
- **intent 完了ゲート**: Phase 4 後、`interview.json.intent_contract.slot_status` に `filled=false` がある、または `pending_probes[]` が空でない場合は Phase 5 以降へ進まない。`pending_probes[]` の順に Phase 4 へ戻し、ユーザーへ固定 probe を 1 問ずつ聞く。
- **Gate A (Phase 8) 否認分岐**: `summary.json` 否認時は Phase 4 へ戻り再ヒアリング (最大 2 周)。3 周目突入なら停止しユーザーへ要件再確認を促す。
- **Phase 5 skip 判定**: `interview.json.needs_excavation=false` なら Phase 5 を skip し Phase 6 へ。skip 理由を `intake-trace.json` へ明示記録 (理由なき skip は禁止)。
- **lint / quality_gate 自動修正禁止**: `quality_gate.py` / `cross_check.py` fail は根本原因をユーザー提示し AI 判断で勝手に直さない。
- **Notion target 保持**: `--page-url` / `--page-id` / `--database-id` は Phase 1 から `notion_target` として trace / intake.json に残し、Phase 10 へ同じ値を渡す。指定 page がある場合、create fallback は禁止する。
- **再開ポイント記録**: 各 phase 開始前 / 完了後に `eval-log/intake-trace.json` を append-only 更新。停止時は次回再開する phase id を末尾に明記。
- 各 phase の entryHook / exitHook / dependsOn / fatal_exit_codes / resourceIds は `workflow-manifest.json` を参照。プロンプトは `prompts/R1-main.md`。

## Gotchas

1. **業務ロジック混入禁止**: 質問雛形・採点基準・Notion blocks 生成を本 SKILL.md に書かない (SRP 違反 → lint 警告)。子 Skill / SubAgent / references に閉じる。
2. **固定 Steps の本文記述禁止**: 実行順は `workflow-manifest.json phases[]` から都度読む。SKILL.md に Step 1 / 2 / ... を列挙しない (manifest との二重管理になり drift 源)。
3. **SubAgent context 漏洩**: Phase 2 / 3 / 5 / 8 で Task tool を使わず Skill tool で呼ぶと主スレッド context が混入し Sycophancy/バイアスが発生する。
4. **Phase 4→5 skip 条件**: `needs_excavation=false` のときのみ skip 可。理由を `intake-trace.json` に書かない skip は禁止。
5. **Gate A 周回上限**: Phase 8 否認 → Phase 4 戻しは最大 2 周。3 周目は停止。
6. **Notion トークン**: 環境変数 / リポジトリへ置かず Keychain から都度取得 (`scripts/keychain_get_secret.py`)。
7. **manifest 二重管理禁止**: phases[] を本 SKILL.md にコピペしない。`lint-manifest-contents.py` を必ず通す。
8. **next-action を実行と誤読しない (最重要)**: Phase 11 の `next-action.json` / `harness_creator_handoff_phase` / 「harness-creator 引き渡し」という語は **推奨の記述**であって実行指示ではない。完了レポート提示後に `run-skill-create` 等を続けて起動してはならない。「では作成します」と続行せず、`mode` と推奨を提示して停止する (Key Rule 9)。スキル生成が必要ならユーザーが明示的に別途開始する。

## Additional Resources

- `workflow-manifest.json` — phases[] (id / dependsOn / delegateType / delegateName / fatal_exit_codes / resourceIds) の SSOT
- `prompts/R1-main.md` — orchestrator 責務プロンプト
- `schemas/output.schema.json` — `intake-trace.json` 形式
- `references/workflow-sequence.md` — 11 phase の起動順序と前提 JSON 依存図 (人間向け)
- `references/handoff-contract.md` — 各 phase の handoff JSON schema 一覧
- `references/keychain-setup.md` — Notion トークンの Keychain 登録手順 (Step 0 exit 44 案内先、単独配布で自己完結するよう本 skill に同梱)
- `references/resource-map.yaml` — 他 reference を読む前の最小読込先マップ
- 子 Skill: `run-intake-kickoff` / `run-intake-interview` / `run-intake-option-catalog` / `run-intake-visualize` / `run-intake-next-action` / `run-intake-finalize` / `run-notion-intake-publish`
- SubAgent: `skill-intake-assumption-challenger` / `skill-intake-user-profiler` / `skill-intake-purpose-excavator` / `skill-intake-summarizer`
- **単一発火点 (公開 SSOT)**: Notion 公開は `intake_publish_pipeline.py` のみを発火点とし、SubAgent / sibling `run-notion-intake-publish` から二重に render/publish を直叩きしない。指定 page がある場合 `--page-id` / `--page-url` を最優先で渡し、page_id 解決不能時は exit 51 で停止する。All-or-Nothing: PNG 1 枚でも欠けたら `verify_notion_assets.py` で停止し途中公開しない。quality_gate / completeness FAIL は LLM 判断で勝手に直さずユーザーへ提示する (推測補完禁止)。
- 既存スキルとの関係: `run-skill-elicit` (技術者向け簡易 brief、併存) / `run-skill-create` (**上位 orchestrator**。intake を Step 1 として呼ぶ側。intake からは起動しない — Key Rule 9) / `assign-notion-fidelity-evaluator` (Phase 10 内部起動)。前身の `run-skill-intake-aggregator` は本スキルへ統合・削除済 (references / assets / schemas は plugin 直下へ移設)。
- Slash command の起動正本は本スキル (`run-skill-intake`)。`/intake-publish <hint>` (Notion 再公開) / `/intake-status <hint>` (進行確認) は別 skill が担う。

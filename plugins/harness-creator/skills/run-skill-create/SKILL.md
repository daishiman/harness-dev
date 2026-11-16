---
name: run-skill-create
description: 実行して新規Skillを端から端まで作りたいとき、複数Gateを通した品質保証付きフローを起動したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[topic?] [--mode create|update] [--brief-path <skill-brief.json> [--handoff <handoff-run-plugin-dev-plan.json>]]"
arguments: [topic, mode, brief_path, handoff]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(python3 *)
  - Bash(git diff *)
  - Bash(git status *)
  - Skill
  - AskUserQuestion
model: opus
kind: run
prefix: run
effect: local-artifact
goal_seek:
  engine: inline
  fork: inline
owner: team-platform
since: 2026-05-18
version: 0.1.0
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-gate-review.md
rubric_refs:
  - ref-skill-design-rubric
reference_refs:
  - ref-task-context-map
  - ref-skill-glossary
  - ref-domain-task-spec-rubric
# context-budget: orchestrationのみ。各子スキルがそれぞれの設計書を参照する。本スキルは05/06/07/13/23/25章のみ参照。
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)。content-review verdict の criteria_evaluated と突合
  activation_state: gate_review_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: build-trace の lint receipt が PASS で、workflow-manifest の p0-lint.commands 全件 (create 固有分。manifest-contents 含む) が exit0 で通り TODO や未展開プレースホルダや英語仮文の残存が無い(パラメーター名を除く)
      verify_by: lint
      derived_from: [CL-7]
    - id: IN2
      loop_scope: inner
      text: 各ゲート通過時の handoff JSON が schemas/handoff.schema.json に、build-trace JSON が run-build-skill の skill-build-trace.schema.json に準拠し章 coverage を空欄なく記録している
      verify_by: script
      derived_from: [CL-3, CL-12]
    - id: IN3
      loop_scope: inner
      text: create/update 共通の capability parity と dual-root runtime root 契約が audit-capability-parity.py で検証され、foreign cwd と env 未設定でも owner SKILL.md から plugin root を解決できる
      verify_by: lint
      derived_from: [CL-14]
    - id: OUT1
      loop_scope: outer
      text: 全遷移が明示的gate decisionなしに前進せず、人間承認gateはユーザー承認を必須とし、既定の流れで evaluator・elegant-review・governance reviewer を起動しない (rubric governance は rubric 変更時に利用者が明示的に呼んだときだけ)
      verify_by: elegant-review
      derived_from: [CL-1, CL-2, CL-8, CL-11]
    - id: OUT2
      loop_scope: outer
      text: 完了レポートの C1-C4 節が scripts/render-c1-c4-section.py の出力をそのまま貼ったもので、run-build-skill の初稿診断 receipt (review.json、改善した場合は improvement-result.json / post-target-manifest.json / improvement-validation.json) から描画され、create 内で評価し直しておらず、receipt が無い・壊れている・今の成果物と合わない場合は未診断と明記している
      verify_by: script
      derived_from: [CL-9]
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
artifact_delivery: artifact-delivery-v1
runtime_root_policy: host-skill-path
---

## Pre-choice usable artifact execution

本スキルの最小の実成果物はGate 1の`eval-log/skill-brief.json`とする。schema検証だけを最小guardとして通し、現物path・digest・要点を提示してGate 1の承認を得る。現状で試すか診断するかの2択はここでは聞かず、run-build-skillのStep 12.5が1回だけ記録した`diagnostic-choice.json`を`record_user_choice`として転記する。

## Post-choice selected improvement execution

accept-as-isでも、`workflow-manifest.json`の`gate_order`に残るGateとP0 lintと完了レポートはhandoff完了の条件として通す (決定論lintと利用者承認だけで、evaluatorは起動しない)。diagnoseで増えるのはrun-build-skillのStep 12.6-12.8だけで、`semantic_evaluator_started`はbuild側で初稿診断が始まったことを指す。本スキル自身の状態は、diagnoseなら`diagnosis_delegated` (buildへ委譲) を経て`gate_review_started`へ進み、`semantic_evaluator_started`には入らない。本スキルのfeedback改善ループは`gate_review_started`の後だけ動く。
release/exhaustiveは別の明示eventを必要とする。


# run-skill-create

## Runtime root contract

`runtime_root_policy: host-skill-path` の製品別root解決、cwd推測禁止、prompt継承は
[ref-cross-platform-runtime の共有正本](../ref-cross-platform-runtime/references/runtime-portability.md#product別-plugin-root-契約)
をそのまま適用する。

> Phase 2 移行後は `plugins/harness-creator/skills/` が正本、`.claude/skills/` は symlink/deploy target。plugin同梱schema/prompt/scriptは上記Runtime root contractで解決したabsolute `PLUGIN_ROOT` から参照し、repo-root cwdや `plugins/harness-creator/...` からplugin rootを推測しない。生成対象repoを操作するroot-level gateだけは、明示したproject root/cwdを別入力として使う。

## Purpose & Output Contract

ユーザー要望 → `skill-brief.json` → Skill生成 (初稿診断を含む) → plugin/marketplace 登録判定 → P0 lint (create 固有分) → 完了レポート を**ゲートあり自動連鎖**で実行する端から端まで orchestrator。C1-C4 の評価は `run-build-skill` の初稿診断を正本とし、本スキルはその receipt を転記するだけで評価し直さない。rubric governance は rubric を変更するときだけ利用者が `run-skill-rubric-governance` を明示的に呼ぶ。各 Step/Gate の機械可読定義は `workflow-manifest.json`、責務別プロンプトは `prompts/*.md`、データ契約は `schemas/*.schema.json` を参照。

**入力**: topic (任意), mode ∈ {create, update}, brief_path (任意・E2 直接消費), handoff (任意・brief_path 併給時の parity preflight)
**出力**:
- `plugins/<plugin>/skills/<skill_name>/` 一式 (SKILL.md + references/ + scripts/。run-build-skill の `$OUT_BASE/<skill_name>/`)。`<plugin>` が `harness-creator` になるのは共通基盤の場合だけ
- `eval-log/skill-build-trace.json` (`../run-build-skill/schemas/skill-build-trace.schema.json` 準拠。build の正本 schema をそのまま使う)
- 生成先 plugin の `plugins/<plugin>/.claude-plugin/plugin.json` 登録差分 (共通基盤の場合は `plugins/harness-creator/.claude-plugin/plugin.json`)
- 評価結果は新たに書かない。完了レポートは build の receipt (`eval-log/skill-build-trace.json#/reproducibility_gates/lint`、診断を選んだ場合の `eval-log/<plugin>/build/initial-draft-review/<artifact-fingerprint>/review.json`、改善した場合は同じ dir の `improvement-result.json` (改善後の C1-C4)・`post-target-manifest.json`・`improvement-validation.json` (Step 12.8 の合格印)) を参照する。C1-C4 節は `python3 "$PLUGIN_ROOT/skills/run-skill-create/scripts/render-c1-c4-section.py" --plugin <plugin> --skill <skill_name>` の出力をそのまま貼る
- 各 phase の handoff JSON (path は `workflow-manifest.json` の `phases[].handoff` の path、`schemas/handoff.schema.json` 準拠)
- 完了レポート (日本語本文、パラメーター名のみ英語)

**完了条件**: build の lint receipt PASS + create 固有の P0 lint pass + 各遷移の明示的gate decision。C1-C4 は build の初稿診断 receipt から `scripts/render-c1-c4-section.py` で描画した節を完了レポートへそのまま貼る (receipt が無い・壊れている・今の成果物と合わない場合、script が未診断と出す)。

**禁則**: ゲート判定なしに次フェーズへ進まない。人間承認gateはユーザー承認を必須とする。P0 lint 失敗の自動修正は禁止 (根本原因をユーザー提示)。build が済ませた lint と C1-C4 評価を本スキルで再実行しない。詳細は `## Key Rules`。

### 起動モード

- **引数なし**: Step 1 (run-skill-elicit) が起動、対話で topic を確定。フィールド意味は `schemas/skill-brief.schema.json` (詳細は `references/skill-brief-schema.json`)。
- **`--brief-path` 指定あり (E2 直接消費)**: 上流 `run-plugin-dev-plan` の `handoff-run-plugin-dev-plan.json` を `render-skill-brief.py` で決定論射影した `skill-brief.json` を Step 1 の対話ヒアリング (run-skill-elicit) を skip して直接 Step 1 成果物に採用する (再ヒアリングなし)。詳細契約は `prompts/R1-elicit.md` CONST_014。持ち込んだ brief に `user_request_verbatim` (依頼の原文) が無ければ、build の目的照合は原文なしで進むことになるので、Gate 1 でその旨を利用者に示す。`--handoff` 併給時は build dispatch 前に `python3 "$PLUGIN_ROOT/scripts/check-route-component-parity.py" <handoff>` を実行し exit0 (routes↔inventory 一致) を確認する (CONST_015、非0 で停止)。`PLUGIN_ROOT` は共有Runtime root contractで解決済みのabsolute rootとする。
- **Notion 指定あり**: topic / 引数に `--page-url` または `--page-id` が含まれる場合、Step 1 は `skill-intake` の publish 完了証跡を必須入力とする。`output/<hint>/notion-log.json.status=="published"`、`notion-publish-result.json.page_id`、`notion-url.txt` が揃い、指定 page と一致するまで Step 2 build へ進まない。

## Key Rules

1. **ゲート前で必ず判定する**: 人間承認gate (`workflow-manifest.json` の `gate_order`) は AskUserQuestion (`prompts/R2-gate-review.md`) でユーザー承認を得る。
2. **子スキルへの委譲**: 各フェーズは独立 Skill を Skill tool で起動 (`workflow-manifest.json` の `delegateSkill`)。本スキルは制御のみ。
3. **失敗時の停止**: build の lint receipt が PASS でない、または create 固有の P0 lint が fail なら停止し findings 提示。
4. **評価は build を正本にする**: C1-C4 は `run-build-skill` の初稿診断 (Step 12.5 で利用者が診断を選んだときだけ別 context で起動) の receipt を使い回し、本スキルで evaluator / elegant-review を起動しない。rubric governance は rubric を変更するときだけ利用者が `run-skill-rubric-governance` を明示的に呼ぶ。
5. **handoff 保存**: 各ゲート通過時に `workflow-manifest.json` の `phases[].handoff` の path へ handoff JSON を `schemas/handoff.schema.json` 準拠で残す。PostCompact hook で復元。
6. **plugin/marketplace 登録は確認後**: legacy manifest.json は `build-manifest-registration-plan.py --plugin plugins/<plugin>` の提案 → Gate 2.5 承認 → `--apply` の順。新形式 plugin.json plugin のルート `marketplace.json` / `bundles.json` 登録は `scripts/validate-plugin-completeness.py --fix`（append-only・冪等・書込後自己再検証）が担い、人間が PR diff で最終承認する（破壊的変更を含まない append-only ゆえ生成フロー内で自動実行可）。
   Codex 面は `run-codex-plugin-package` に委譲する。Claude plugin envelopeを持つ全pluginを対象に、新規/既存を状態から判定する同一upsertが `.codex-plugin/plugin.json` と `.agents/plugins/marketplace.json` を同期し、手書きの二重管理はしない。Codex固有値は `.codex-plugin-overrides.json` へ明示する。
   これに対し **CL-4c の `build-plugin-release.py` は承認境界の外側 (＝承認後) に置く**。理由は `validate-plugin-completeness.py --fix` と性質が違うため: `write_version()` は `plugin.json` の version 行を原文 in-place 置換し、そこから公開 `marketplace.json` (`sync_public_marketplace_version()`) と `.codex-plugin/plugin.json` (`sync_codex_manifest_version()`) を追従させる **既存行の書き換え**であり (さらに `_run()` が `bumped` 非空のとき `regenerate_config_version_lock()` で `config-version-lock.json` も再生成する)、append-only の安全性論拠がそのまま使えない。よって生成フロー内で自動実行してよいのは**読み取りのみの `--check`** に限る。version を実際に上げる実行は **Gate 2.5 承認後に、`--only <plugin>` を必ず付けて**行う — `_run()` は `only = set(args.only) or None` なので無指定は全 plugin 走査となり、本フローと無関係な変更済み plugin まで同じ実行で patch bump されるため、`--only` は範囲を宣言する必須引数として扱う。

7. **resource-map 先読み**: `references/resource-map.yaml` を最初に読み、必要ファイルのみ open。
8. **日本語成果物ゲート**: brief の `output_language=ja` と `parameter_language_exception=true` を既定とし、本文・レビュー・完了レポートを日本語に保つ (パラメーター名・JSON キー・CLI 引数は英語)。
9. **prompt 形式**: 新規 prompt は **Markdown (`.md`) 既定**。`prompts/<R-id>-<slug>.md` で `plugins/prompt-creator/skills/run-prompt-creator-7layer/references/seven-layer-markdown-template.md` を写経して生成。YAML は legacy のみ許容 (新規禁止、P0 lint で warn)。

## End-to-End Flow

```
[Step 1 elicit] run-skill-elicit ─→ skill-brief.json ─[Gate 1]─▶
[Step 2 build]  run-build-skill  ─→ skill-build-trace.json (+ 診断を選んだ場合は初稿診断 receipt)
[Step 3 manifest-register] [Gate 2.5] [Step 3.5 bundle-register]
[Step 3.55 codex-platform-sync] run-codex-plugin-package (Codex manifest + repo marketplace upsert)
[Step 3.56 codex-platform-check] 同じ入力をcheck-onlyで再検査
[Step 3.6 local-marketplace-register] build-local-marketplace.py (非配布 plugin の install 経路)
[Step 3.7 plugin-release-record] build-plugin-release.py --only <plugin> (内容 hash 記録 / patch 採番。Gate 2.5 承認後・--only 必須。Key Rule 6)
[Step 4a p0-lint] create 固有 lint のみ (build と重複する lint は build-trace の lint receipt を再利用。fail→停止して findings を提示し、利用者が選んだときだけ build から 1 回やり直す) ─[Gate 2 diff]─▶
[Step 4a.5 pkg-check] run-plugin-package-check (条件: kind==plugin-composition or 新規 plugin 横展開)
[Step 7 report] C1-C4 は render-c1-c4-section.py が build の初稿診断 receipt から描画した節をそのまま貼る (評価し直さない)
```

旧 Step 4b (design-evaluate) / 5 (elegant-review) / 6 (governance) は既定の流れから外した。rubric を変更するときだけ、利用者が `run-skill-rubric-governance` を明示的に呼ぶ。

依存・entryHook/exitHook・resourceIds・fatal_exit_codes は `workflow-manifest.json` 参照。

## ゴールシーク実行

### ゴール (Goal)

ユーザー要望から生成された `<skill_name>/` 一式が、build の lint receipt PASS と create 固有の P0 lint pass を満たし、`gate_order` の全ゲートが承認済みで、登録判定・handoff・build の評価 receipt を転記した完了レポートまで完結した状態になっている。

### 目的・背景 (Why)

新規/更新 Skill を「端から端まで」品質保証付きで送り出すための制御層。各フェーズは独立 Skill へ委譲し、本スキルはゲート制御とハンドオフ整合のみを担う。固定手順では入力 (topic/mode/brief_path)・lint 失敗・FAIL 差し戻しなど実行時文脈に脆いため、未達ゲートを都度埋める。

### 完了チェックリスト (Checklist)

- [ ] `eval-log/skill-brief.json` が `schemas/skill-brief.schema.json` 準拠で生成され、Gate 1 承認済み <!-- CL-1 -->
- [ ] Notion 指定ありの場合、`python3 "$PLUGIN_ROOT/skills/run-skill-create/scripts/validate-intake-publish-ready.py" --dir output/<hint> --page-url <url>` が exit 0。未公開・page_id 不一致・URL 欠落なら Gate 1 で停止し、skill 本体生成へ進んでいない <!-- CL-2 -->
- [ ] `<skill_name>/` 一式 (SKILL.md + references/ + scripts/) が `Skill(run-build-skill, args=[skill_name, kind, --mode={mode}])` で生成され、`eval-log/skill-build-trace.json` が `../run-build-skill/schemas/skill-build-trace.schema.json` 準拠・章 coverage 全 PASS/N/A/skip 理由付き <!-- CL-3 -->
- [ ] **新規 plugin の場合** `python3 ${HARNESS_ROOT:-.}/scripts/validate-plugin-completeness.py --fix` 実行済みで、`marketplace.json` plugins[] + `bundles.json` (`bundle_targets`) へ append-only 登録され、検出モード (`validate-plugin-completeness.py`) が exit 0。プロジェクト固有 (横展開しない) は未登録理由がレポートに記録されている <!-- CL-4 exempt: 登録の運用操作項目。validate-plugin-completeness.py が機械検査し評価 criteria の対象外 -->
- [ ] **Claude plugin envelope を持つ場合** 同一upsertを実行し、`sync-plugin-platforms.py --all --check` が exit 0。`.codex-plugin/plugin.json` と `.agents/plugins/marketplace.json` の両方が差分に含まれる <!-- CL-4d exempt: Codex 配布 projection を generator と回帰テストが機械検査 -->
- [ ] **新規 plugin の場合** `python3 ${HARNESS_ROOT:-.}/scripts/build-local-marketplace.py` 実行済みで、`marketplaces/local/.claude-plugin/marketplace.json` が再生成され `--check` が exit 0。公開 marketplace は `distributable:false` を載せられない (MK-004) ため、非配布 plugin を手元の Claude Code へ install する経路はこれだけ。**CL-4c を実行するなら本項は不要** (`build-plugin-release.py` は pending が 1 件でもあれば local marketplace を再生成する)。単独で要るのは pending が空で local marketplace 側だけ drift しているときに限る <!-- CL-4b exempt: 登録の運用操作項目。build-local-marketplace.py --check が機械検査し評価 criteria の対象外 -->
- [ ] `python3 ${HARNESS_ROOT:-.}/scripts/build-plugin-release.py --only <plugin>` 実行済みで `--check` が exit 0 (書き込みを伴う実行は Gate 2.5 承認後・`--only` 必須。Key Rule 6)。marketplace install は version 単位の copy なので、version を据え置いたまま内容を直すと install 済み plugin へ届かない。内容 hash 対応表への記録 (新 plugin) と patch 採番 (既存 plugin の変更) がここで済む <!-- CL-4c exempt: 登録の運用操作項目。build-plugin-release.py --check が機械検査し評価 criteria の対象外 -->
- [ ] 他 plugin リソースを呼ぶ場合 `.claude-plugin/bundles.json` の現行 bundle (`skills-full` / `skills-intake`) のうち `plugin.json.bundle_targets` で宣言した対象へ登録済み (上記 `--fix` が `bundle_targets` を読み自動 append)。不要なら理由がレポートにある (理由なき未登録は rubric 違反) <!-- CL-5 exempt: 登録の運用操作項目。validate-plugin-completeness.py が機械検査し評価 criteria の対象外 -->
- [ ] (legacy manifest.json 形式のみ) plugin/marketplace 登録が Gate 2.5 承認後 `--apply` 済み (`build-manifest-registration-plan.py`) <!-- CL-6 exempt: legacy 経路の条件付き運用項目 -->
- [ ] `eval-log/skill-build-trace.json` の `reproducibility_gates.lint` が PASS で `lint_target_sha256` が今の skill ディレクトリ全体の digest と一致する (一致すれば build Step 4 の lint を使い回す。不一致なら covered_scripts をここで再実行し、1 本でも fail なら止めて提示する。`phases[id=p0-lint].build_lint_reuse`)。そのうえで `workflow-manifest.json` の `phases[id=p0-lint].commands` 全件 (create 固有分。lint-manifest-contents 含む) が exit 0。`TODO`/未展開 `{{...}}`/英語仮文の残存なし (パラメーター名除く) <!-- CL-7 -->
- [ ] create/update 共通で `audit-capability-parity.py --plugin plugins/<plugin> --json` が PASS。Claude 固有 command/agent/hook は Codex skill 代替または理由・replacement 付き omission contract を持つ。SKILL/promptのplugin-root付き実行行はowner SKILLに `runtime_root_policy: host-skill-path` とRuntime root本文契約を必須とし、bare `CLAUDE_PLUGIN_ROOT`、cwd推測、literal placeholderを残さない。env unset + foreign cwdでもabsolute owner `SKILL.md` pathからmanifest祖先を解決できる <!-- CL-14 -->
- [ ] Gate 2 で `git diff <skill_path>` + build-trace を提示し承認済み <!-- CL-8 -->
- [ ] 完了レポートの C1-C4 節が `python3 "$PLUGIN_ROOT/skills/run-skill-create/scripts/render-c1-c4-section.py" --plugin <plugin> --skill <skill_name>` の出力 (`run-build-skill` の初稿診断 receipt `eval-log/<plugin>/build/initial-draft-review/<artifact-fingerprint>/review.json`、改善した場合は同じ dir の `improvement-result.json` (改善後の C1-C4) と `post-target-manifest.json`・`improvement-validation.json` から描画) をそのまま貼ったもので、本スキルで evaluator / elegant-review を起動していない。receipt が無い (accept-as-is)・壊れている・今の成果物と合わない場合は script の出力どおり未診断と明記している <!-- CL-9 -->
- [ ] 既定の流れで `run-skill-rubric-governance` を起動していない。rubric を変更した場合だけ、利用者が明示的に呼んだ governance の結果を完了レポートに記録している <!-- CL-11 -->
- [ ] 各ゲート通過時に `workflow-manifest.json` の `phases[].handoff` の path へ handoff JSON が `schemas/handoff.schema.json` 準拠で保存されている <!-- CL-12 -->
- [ ] 完了レポート (下記項目: mode/gates_passed/creator_kit_registration/build_lint_receipt/build_evaluation_receipt/build_stage/deferred_to_release/open_questions。build_evaluation_receipt は `render-c1-c4-section.py` の出力をそのまま貼る。draft なら後回しにした release 検証の件数と id を `deferred_to_release` に書き、release 検証が要るときは `Skill(run-build-skill, args=[skill_name, kind, --mode=update, --stage release])` で続けられると 1 行添える) が日本語本文で提示されている (パラメーター名のみ英語) <!-- CL-13 exempt: レポート提示の運用項目。完了レポート契約は本文で規定済み -->

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップ (現状評価/手順生成/実行/検証/Anchor Step/反復) に従う。本スキル固有の差分:

- **未達評価の単位はゲート**: `workflow-manifest.json` の `gate_order` 順に「未承認」とみなして都度埋める (Gate 番号順の直書き禁止、順序正本は manifest)。人間承認gateは AskUserQuestion (`prompts/R2-gate-review.md`) で承認を取る。
- **委譲先 (子 Skill)**: `run-skill-elicit` / `run-build-skill` (C1-C4 の初稿診断も build 側で完結する)。Notion 指定ありの非技術者 intake は `skill-intake` 完了証跡を先に検証する。本スキルは制御のみ、各子が自設計書を参照。
- **評価を重ねない**: C1-C4 は build の初稿診断 receipt を転記し、本スキルで evaluator / elegant-review / governance reviewer を起動しない。
- **差し戻し**: build の lint receipt が PASS でない、または P0 lint fail なら自動で再実行しない。失敗した lint と根本原因を利用者に提示して止め、利用者が修正と再実行を選んだときだけ `run-build-skill` から 1 回やり直す。Gate の差戻しも同じで、戻り先は `references/gate-templates.md` の各 Gate の差戻し先、利用者が選ぶたびに 1 回やり直し、同じ Gate で通算 3 周まで (`prompts/R2-gate-review.md` の CONST_004)。
- **lint 自動修正禁止**: 根本原因をユーザー提示し LLM 判断で勝手に直さない。
- 各フェーズ phase=id・entryHook/exitHook・dependsOn・fatal_exit_codes は `workflow-manifest.json` 参照。プロンプト R1/R2 は `prompts/*.md`。

### ゴールシーク配線を持たない理由

本スキルは子スキル (`run-skill-elicit` / `run-build-skill`) へ渡す orchestrator で、反復は利用者のゲート判断でしか起きず、自分では再実行しない (上の「差し戻し」)。差し戻しで build をやり直すときも同じ run_id を渡し、1 run で起動してよい AI context の総数は `run-elegant-review/references/convergence-policy.json` の `run_model_action_budget` を正本として build 側の gate が数える (尽きれば evaluator も executor も起動しない)。各周の成果物は各ゲートの handoff JSON と子スキルの記録 (`eval-log/skill-brief.json`・`eval-log/skill-build-trace.json`) に残るので、中間成果物の anchor を重ねて持たない。

## Gotchas

1. **Gate skip 禁止**: 承認を自動推測しない。人間承認gateは選択肢「承認」が明示的に選ばれたときだけ通し、自由入力の「OK」「了解」は承認にしない。
2. **評価の二重化禁止**: build の初稿診断 (選んだときだけ別 context の evaluator) を正本とし、本スキルで同じ成果物を評価し直さない。
3. **lint 失敗時の自動修正禁止**: 根本原因をユーザー提示。LLM 判断で勝手に直さない。
4. **mode=update 時の改名**: `run-skill-rename` に委譲。本スキル対象外。
5. **context 予算**: 31 章全部を読まない。本スキルは 05/06/07/13/23/25 章のみ参照。
6. **handoff 保存**: 各ゲート通過時に `schemas/handoff.schema.json` 準拠で必ず保存。
7. **manifest 二重管理禁止**: 手書き追加後も `lint-manifest-contents.py` を必ず通す。

## 品質ゲート: 評価の正本

C1-C4 の評価は `run-build-skill` の初稿診断 (Step 12.5 で利用者が診断を選んだときだけ Step 12.6-12.8 が走る) を正本とする。本スキルはその receipt を完了レポートへ転記し、Elegant Review Protocol (`run-elegant-review`) を自動では起動しない。成果物全体を 30 思考法で見直したいときは、利用者が `run-elegant-review` または `/skill-improve` を明示的に呼ぶ。

## Additional Resources

`references/resource-map.yaml` を最初に読む (machine-readable と人間向け資料を一覧化)。主要参照:

- `workflow-manifest.json` — Step/Gate/Phase の機械可読定義 (entryHook/exitHook/dependsOn/delegateSkill)
- `schemas/skill-brief.schema.json` — Step 1→2 渡し正本スキーマ
- `schemas/handoff.schema.json` — Gate 通過時 handoff 共通形式
- `../run-build-skill/schemas/skill-build-trace.schema.json` — Step 2 で build が emit する trace の正本 (create は独自 schema を持たない)
- `prompts/R1-elicit.md` / `prompts/R2-gate-review.md` — R1/R2 責務別プロンプト
- `references/gate-templates.md` — Gate 確認質問テンプレ (人間向け詳細手順)
- 子スキル: `run-skill-elicit`, `run-build-skill`, `run-plugin-package-check`, `run-skill-rename`。rubric 変更時だけ利用者が明示的に呼ぶ: `run-skill-rubric-governance`
- 設計書: 05/06/07/13/23/25 章

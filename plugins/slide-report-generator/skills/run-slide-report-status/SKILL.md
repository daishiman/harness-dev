---
name: run-slide-report-status
description: 生成中のslide deckまたはreportの現在phaseを確認したいとき、中断後の次アクションをread-onlyで特定したいときに使う。
kind: run
prefix: run
version: 0.1.0
allowed-tools: Bash, Read
user-invocable: true
disable-model-invocation: false
argument-hint: "[output-dir?]"
effect: conversation-output
owner: harness maintainers
since: 2026-08-20
last-audited: 2026-08-20
output_language: ja
runtime_root_policy: host-skill-path
script_refs:
  - ../../scripts/validate-inline-goal-seek-anchor.py
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: inline
  max_loops: 3
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 明示されたproject directoryへworkflow managerのverboseとoutput mode preflightをread-onlyで実行しcheckは対象を読むだけのP2_5とP3のgateにだけ付け全exit codeを保持している
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: deck report両modeの現在phase 欠落artifact 次actionを推測せず報告しplugin runtime欠落を自動復元していない
      verify_by: evaluator
artifact_delivery: artifact-delivery-v1
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実回答をmain contextで作成する。secret・欠測・矛盾のminimal guardだけを実行し、根拠refつきの現物をそのまま提示してからaccept-as-is/diagnoseを記録する。accept-as-isはそのままhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはdiagnoseが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。

# run-slide-report-status

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

対象project directoryをplugin同梱workflow managerで検査し、現在phase、検証結果、次アクションを返す。workflow managerがphaseを判定できるのは`structure.md`を持つslide deckだけで、次アクションはどのdirでも成果物の有無から決定的に言える段で返す。reportと`structure.md`の無いdirには、「workflow-managerでは判定できない」というremediationも返す (「workflow manager の出力の読み替え」)。

## Key Rules

- 対象path未指定時は推測せず確認する。
- plugin資産は`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`から解決する。
- 対象projectへ書き込まない。workflow managerの`--check`は、対象を読むだけのgate (phaseが`P2_5`か`P3`) にだけ付ける。成果物の有無は`ls -a`で見る。
- validator非0を成功へ畳まない。

## ゴールシーク実行

`goal_seek.engine: inline` / `fork: inline` とし、read-only の検査と要約をmain contextで完結する。欠落artifactまたは非0終了があれば該当検査だけを再評価し (最大3周)、runtime欠落を自動復元しない。再評価は、欠落の原因が対象 project 側か plugin 側か (Gotchas の区別) と次 action が決まった時点で止める。検査は read-only で決定的なので、入力が同じなら周回を重ねても出力は変わらない。決まらないまま3周に達したら、決まらなかった点を progress の `open_issues` に書いて返す。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/vendor/scripts/workflow-manager.js" "<project-dir>" --verbose
# 上の「現在のPhase」が P2_5 か P3 のときだけ
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/vendor/scripts/workflow-manager.js" "<project-dir>" --check
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-output-mode.py" --preflight
```

`--verbose` は gate を回さずに、phase・Phase 検証・file の状態を出す。phase は `.workflow-state.json` があればその値になり、`ls -a` だけでは決まらないので、`--check` を付けるかはこの出力の phase で決める。`--check` は phase に紐づく `phase-gate.js` を回す。`P2_5` (P2→P3) と `P3` (P3→P3_5) の gate は対象 dir を読むだけである。`P3_5` の gate (P3_5→complete) は `verify-slides.js` が `<project-dir>/screenshots/slide_NN.png` を書き、消さない。決定論経路の deck は `deploy-guide.md` を持たないので、必ず `P3_5` になる。よって `P3_5` にも、gate の無いほかの phase にも `--check` を付けない。`P3_5` の deck には、UI 検証の gate を回していないことと、利用者が `--check` を回すと `<project-dir>/screenshots/` に書くことを報告する。UI 品質の検証は、generate では diagnose 後の R6 にあたる。

stdout/stderrとexit codeから現在phase、欠落artifact、次アクションを要約する。exit code は下の読み替えの後も、そのままの値で報告する。

### workflow manager の出力の読み替え

vendor の `workflow-manager.js` は byte のまま携行する旧い P 段の判定器である。`detectPhase()` は `structure.md`・`index.html`・`deploy-guide.md`・`.approved` (と、plugin に書き手の無い `.workflow-state.json`) しか見ない。`structure.md` が無い dir は、ほかの成果物があっても `P0 (初期化)`・exit 0・「hearing-facilitator を起動」になる。成果物の有無は `ls -a "<project-dir>"` で見て、要約の前に次のとおり読み替える。

- **report の成果物**: `report-structure.json` か `report.html` があれば、workflow manager の phase・検証結果 (「✅ 問題なし」)・次のステップを report の段に使わない。remediation に「report mode の phase は workflow-manager では判定できない」と書く。
- **`structure.md` の無い dir**: report の成果物が無くても、workflow manager の phase と検証結果を使わない (`information-priority-map.json`・`structure.json`・`index.html` のどれだけが在っても `P0` になり、`.workflow-state.json` があればその値になる)。remediation に「この dir の段は workflow-manager では判定できない」と書く。
- **次 action**: workflow manager の「次のステップ」は旧い P 段の文面なので、どの dir でも使わない。gate が exit 1・2 で終わると出ず、`P3_5` では diagnose 後の R6 にあたる UI 検証の確認を、`complete` では「現在のPhaseを特定できません」を出す。代わりに、在る成果物と、それを出す generate の段を報告する。`information-priority-map.json` は R2 の構成着手前の宣言、`structure.json`・`structure.md`・`report-structure.json` は R2 の構成、`index.html`・`report.html` は R3 の生成物 (deck の `deploy-guide.md` と、決定論経路の `structure.md` は、R3 が一緒に書く)、`evaluation-report.json` は diagnose 後の R6 の評価である。次 action は、どれも無ければ「generate の成果物が無い」、宣言だけなら「R2 の構成が無い」、構成までなら「R3 の生成物が無い」と書く。生成物が在れば、R4 の提示と R5 の選択 (accept-as-is / diagnose) は file に残らないので、`complete` の deck でも「file からは判定できない」と書く。gate の FAIL・WARN 行は、次 action とは別に検証結果としてそのまま報告する。`validate-output-mode.py --preflight` は実行環境だけを見て対象 dir を見ないので、runtime 欠落の remediation にだけ使う。
- **`.approved`**: workflow manager は P2→P3 に `.approved` を求める。既定経路では `.approved` を作らない (利用者が構成レビューを明示的に求めた回だけ structure-validator が作る)。よって「ユーザー承認待ち」「`.approved` マーカー未取得」と、それだけを理由にした「Phase 2 に差し戻し」を、欠落 artifact にも次 action にもしない。同じ gate の `validate-structure.js` など、ほかの FAIL 行はその行のまま報告する。

### ゴールシーク配線

- **goal-spec**: 持たない。`original_goal` は利用者の依頼と対象 project-dir から推定し、対象 project-dir の絶対 path を本文に含める (対象は `original_goal_hash` で固定される)。progress の `spec_ref` は `inferred` にする。
- **progress**: `${CLAUDE_PROJECT_DIR}/eval-log/run-slide-report-status-progress.json`。初回に `sha256(original_goal)` を `original_goal_hash` に書き、以降書き換えない。周回数は `iteration` に書く。`original_goal` の本文は progress に書かない (progress の schema はこの項目を持たない)。
- **intermediate**: `${CLAUDE_PROJECT_DIR}/eval-log/run-slide-report-status-intermediate.jsonl`。初回 (iteration=0) と各再評価の末に 1 行 append する。各行は `iteration/original_goal/current_goal_snapshot/delta_from_original/merged_directive_for_next/drift_signal` を持ち、`original_goal` の本文はこの各行に持つ。次回は直前の `merged_directive_for_next` だけを引き継ぐ。

### ゴールシーク検証

共通 validator で intermediate.jsonl の `required_keys`、非空・全行不変 `original_goal`、`original_goal_hash == hashlib.sha256(original_goal)` を fail-closed 検証する。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-inline-goal-seek-anchor.py" \
  "${CLAUDE_PROJECT_DIR:?caller project root is required}/eval-log/run-slide-report-status-progress.json" \
  "${CLAUDE_PROJECT_DIR}/eval-log/run-slide-report-status-intermediate.jsonl"
```

## 検証

- 報告した現在の段ごとに、根拠が workflow manager の phase (`structure.md` を持つ deck) か成果物の有無 (report と `structure.md` の無い dir) かを書いている。report の成果物がある dir に `P0 (初期化)` や「hearing-facilitator を起動」を報告していない。
- 次 action は、どの dir でも成果物の有無から言っており、workflow manager の「次のステップ」を写していない。
- `--check` を phase が `P2_5`・`P3` の dir にだけ付けており、`P3_5` の deck には UI 検証の gate を回していないことを報告している。対象 dir に `screenshots/` を作っていない。
- 既定経路の deck に、`.approved` が無いことだけを理由にした承認待ち・差し戻しを報告していない。exit code は読み替える前の値のまま報告している。
- plugin-local runtime欠落は復元せずremediationとして報告する。

## Gotchas

- 対象 project 側の欠落 artifact と、plugin 側の workflow manager/validator 欠落を同じ原因として扱わない。
- validator がexit非0のとき、復元・再生成・対象projectへのWriteで緑化しない。出力は読取専用の診断に限る。

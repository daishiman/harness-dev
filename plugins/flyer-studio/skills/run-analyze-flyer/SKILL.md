---
name: run-analyze-flyer
description: 既存チラシの実画像・最新要望・素材制約を診断したいとき、残す長所と採否理由が追跡できる改善案をanalysis.jsonにまとめて制作へ渡したいときに使う。完成画像の合格判定は行わない。
runtime_root_policy: host-skill-path
effect: local-artifact
kind: run
prefix: run
owner: harness maintainers
version: 1.3.1
user-invocable: true
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
      text: analysis.json が元画像の SHA・観察領域・保持点・全適用要求の採否理由・nextActions を実内容で持ち、判断保留や必須要望の見送り、元画像一覧の漏れ、未知の指針 ID、brief と食い違う purpose を analysis-validate が拒否すること（tests/analysis.test.cjs で検査）。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: 元画像か analysis.json が変わったら前の提案評価を失効させ、提案評価の台帳を作り直すときは前の analysis-review とその FIX を cycle 台帳へ記録してから退避すること（tests/analysis.test.cjs の失効・再評価のテストで検査）。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 別 context の assign-flyer-analysis-review が元画像・最新要望と analysis.json を照合して観察の妥当性・要望の網羅・変更規律・実現性を PASS とし、その FIX をこの担当で直した分析だけが制作へ渡り、残す長所と採否理由から改善案の根拠を追えること。
      verify_by: evaluator
manifest: workflow-manifest.json
responsibility_refs:
  - agents/artifact-analyst.md
schema_refs:
  - ../../schemas/analysis.schema.json
reference_refs:
  - references/analysis-contract.md
  - ../../references/stage-common.md
  - ../../references/design-knowledge-index.json
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---

# 現物を診断し、根拠のある改善案へまとめる

## 選ぶ前の実成果物の作成

既存紙面の観察事実・未確認点・改善候補の初稿を案件フォルダへ保存する。独立合格を付けず、入力と出典を結ぶ。最小の構文・破損・公開条件の検査後、実在パスと内容の指紋を示す。利用者の選択（accept-as-is / light / standard / detailed）を記録する。最初から独立検査まで明示されていればその既存指示を選択として扱い、再確認しない。accept-as-isでは初稿を渡して終了し、未実施の評価や納品完了を主張しない。

## 選んだ深さでの改善の実行

以下の担当・独立評価・改善反復は light / standard / detailed の選択を記録し semantic_evaluator_started へ移った後に実行する。新しい必須修正がなければ繰り返さない。


実行担当は[stage agent](agents/artifact-analyst.md)、判断の基準は[stage contract](references/analysis-contract.md)。PLUGIN_ROOT・実行形式・記録・戻り先・本質アンカー・知識の読み方・独立性は[stage-common](../../references/stage-common.md)に従う。

## 目標と入出力

実際の紙面から問題と長所を特定し、明示要望を落とさず、制作へ渡せる比較可能な改善案を作る。

- 入力: 既存画像/PDF/編集元の絶対パス、今回の目的、最新の必須要望と候補、素材の公開条件。premise（前提の崩れ）の必須修正が [workflow の表](../../references/workflow.md#改善と納品) に従って分析へ戻されたときは、その案 ID・画像領域・元要求 ID。
- 出力: 元画像SHA・観察領域・保持点・要求別候補と採否理由・未達に対する次行動を持つanalysis.json。

## ゴールシーク実行

進め方は [共通の判断手順](../../references/stage-common.md#共通の判断手順)。この担当では、意図の説明より先に元画像の読み順と保持点を観察し、現物の問題と処方の仮説を分けて採否を決める。共通の上限の扱いは stage-common の「戻り先と改善上限」に従う。

## 完了判定と戻り

元画像を個別に開き、全適用要求の判断、保持点、観察領域、必要指針ID、nextActionsが実内容で記録され、analysis-validateが通る。機械PASSは提案品質の独立承認ではない。

別contextの[提案評価](../assign-flyer-analysis-review/SKILL.md)へ渡し、FIXはここで直す。入力不足はこのstageで補い、既に許可された分析・修正を細切れの再確認へ戻さない。

提案評価の PASS 後の実行範囲は [workflow](../../references/workflow.md#stage-ごとの要点) に従う。制作まで許可済みなら制作へ進み、分析だけの依頼ならここで返す。制作の依頼が未指定のときだけ 1 回確認する。cycle-ledger.json は制作が引き継ぐ。

## 実行への接続

PLUGIN_ROOT で次を実行する。analysis-template の brief.analysisMode 切替と、提案評価テンプレート生成・再発行時の記録/退避は、この stage の準備責務（[所有と機械による付随更新](../../references/stage-common.md#所有と機械による付随更新)）。生成した台帳と同一版の分析・元画像を別担当へ渡し、評価内容は記入しない。

```text
python3 scripts/flyer.py analysis-template --project <DIR> --sources <SOURCES.json>
python3 scripts/flyer.py analysis-seal --project <DIR>
python3 scripts/flyer.py analysis-validate --project <DIR>
python3 scripts/flyer.py analysis-review-template --project <DIR>
```

## 実行時のルートの決め方

`runtime_root_policy: host-skill-path` を使う。Claude Code では `CLAUDE_PLUGIN_ROOT` を使い、Codex ではホストから渡されたこの `SKILL.md` の絶対パスの2階層上を使う。どちらもプラグインの定義ファイル（`.claude-plugin/plugin.json` または `.codex-plugin/plugin.json`）の name が flyer-studio と一致することを確かめる。`cwd` や旧リポジトリから推測せず、置き換える前のプレースホルダをシェルへ渡さない。シェルを呼ぶたびに解決済みのルートを指定し、コマンドはそのルートで実行する。`prompts/` の下のファイルも、このスキルの決まりに従う。

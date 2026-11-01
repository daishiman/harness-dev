---
name: run-create-flyer
description: 用途・素材・公開条件からチラシを制作したいとき、独立評価済みanalysisに基づく修正を実物へ反映し、新PDF/PNGと独立完成評価まで接続したいときに使う。
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
      text: 必須事実・素材の公開条件・要求の採否が揃った案件だけが validate・render・verify を通り、描画開始後の入力変更・本質基準の欠落や無承認変更・分析で採った要求や保持点の取りこぼしを描画と finalize の前に止めること（tests/contract.test.cjs・tests/runtime-gates.test.cjs・tests/analysis-bridge.test.cjs で検査）。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: 完成評価の必須修正は fixClass が決める戻り先どおりにだけ受け、同じ所見の再提出や好みだけの所見では cycle を消費せず、予算を超えた finalize は INCOMPLETE を返して納品物を残さないこと（tests/gates.test.cjs・tests/design.test.cjs で検査）。
      verify_by: test
    - id: IN3
      loop_scope: inner
      text: 様式が未確定のまま制作に入ったら制作で決めずにヒアリングの様式提案へ戻し、この差し戻しを FIX の revision 辺と分けて cycle を消費しないこと（plugin-composition.yaml の nonFixReturns と tests/design.test.cjs の分離テストで検査）。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 別 context の assign-flyer-review が全案の新しい PDF 由来 PNG を個別に実見して5観点と最新要求の充足を PASS とし、必須修正が0になってから finalize した納品物が、brief の読者に価値と行動を伝える purpose と保持点を実画像で満たしていること。
      verify_by: evaluator
manifest: workflow-manifest.json
responsibility_refs:
  - agents/flyer-producer.md
  - ../../prompts/design.md
  - ../../prompts/background.md
schema_refs:
  - ../../schemas/brief.schema.json
  - ../../schemas/concepts.schema.json
  - ../../schemas/design-intent.schema.json
  - ../../schemas/scene.schema.json
reference_refs:
  - references/production-contract.md
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

# 目的に合わせて制作し、採用済み改善を実物へ反映する

## 選ぶ前の実成果物の作成

確認済みの事実と許可済み素材で最小の実物プレビューを案件フォルダへ作る。未確認の事実や生成手段は捏造しない。独立評価とfinalize前の実物は未納品と明記する。最小の構文・破損・公開条件の検査後、実在パスと内容の指紋を示す。利用者の選択（accept-as-is / light / standard / detailed）を記録する。最初から独立検査まで明示されていればその既存指示を選択として扱い、再確認しない。accept-as-isでは初稿を渡して終了し、未実施の評価や納品完了を主張しない。

## 選んだ深さでの改善の実行

以下の担当・独立評価・改善反復は light / standard / detailed の選択を記録し semantic_evaluator_started へ移った後に実行する。新しい必須修正がなければ繰り返さない。


実行担当は[stage agent](agents/flyer-producer.md)、判断の基準は[stage contract](references/production-contract.md)。PLUGIN_ROOT・実行形式・記録・戻り先・本質アンカー・知識の読み方・独立性は[stage-common](../../references/stage-common.md)に従う。

## 目標と入出力

読者の価値と行動を伝え、保持条件と採用要求を実画像で成立させ、全案を最新証拠で納品する。

- 入力: 確認済みbrief/assets/concepts/scene。既存修正は同一baselineと要求へ結び付くanalysis.jsonと独立PASSのanalysis-review.json。完成評価から戻った必須修正（fixClass 付き）。
- 出力: 理由を伴う編集元/designIntent、要求採否のbrief.feedback、凍結入力からの新PDF/PNG・機械検査・評価テンプレート。全案の独立PASS後に finalize した納品成果。

## ゴールシーク実行

進め方は [共通の判断手順](../../references/stage-common.md#共通の判断手順)。この担当では、採用要求と保持点を実レイヤーへ対応させ、構図・書体・背景の候補を比較して採用/見送りを designIntent へ残し、選んだ処方を実際に制作する。処方の制約は stage contract、共通の上限は stage-common の「戻り先と改善上限」に従う。

様式は intake で決まった brief.stylePreferences（提案を経た案件では style-proposals.json の chosen も）を起点に、[design prompt](../../prompts/design.md) に従って案ごとに具体化し、採った理由を designIntent へ残す。様式が未確定なら制作で決めず、[ヒアリングの手順 7](../run-intake-flyer/SKILL.md#手順) へ戻して回答から作った案を選んでもらう（評価 FIX ではないので cycle を消費しない）。

## 完了判定と戻り

必須事実・素材条件・採否が揃い、validate→render→verifyが成功。処理中の入力/素材/実装変更は失効扱い。制作の自己確認を独立合格に置き換えない。

新PDF由来PNGと評価テンプレートを[完成画像評価](../assign-flyer-review/SKILL.md)へ渡し、全担当の結果が揃うまで変更しない。FIX は fixClass で決まる戻り先どおりに受ける。全案の最新独立PASSと必須修正0が揃ったら、この stage が finalize する。

## 実行への接続

PLUGIN_ROOT で次を実行する。評価テンプレート（pilot-review.json・visual-review.json の雛形）の生成と finalize はこの stage の責務で、評価担当は記入だけを行う。

```text
python3 scripts/flyer.py validate --project <DIR>
python3 scripts/flyer.py render --project <DIR> [--id <pilot案ID>]
python3 scripts/flyer.py pilot-review-template --project <DIR>
python3 scripts/flyer.py verify --project <DIR>
python3 scripts/flyer.py review-template --project <DIR>
python3 scripts/flyer.py finalize --project <DIR>
```

executionPlanがあれば先にpilot案だけを描き、pilot-review-templateの台帳をassign-flyer-reviewへ渡す。その独立PASSの後に残りの案を描く。

修正後に評価テンプレートを出し直すと、前の評価は cycle 台帳へ記録されてから reviews/<時刻>/ へ退避され、新しい台帳には [評価コストの原則](../../references/review-rubric.md#評価コストの原則) に従って前の PASS が引き継がれる。退避した評価や台帳を手で書き換えない。残りの予算は `cycle-status` で確かめる。

新規案件は[ヒアリング](../run-intake-flyer/SKILL.md)で brief を確定してから始める。案件の作成（doctor・init）は[runtime のコマンド一覧](../../references/runtime.md#コマンド一覧)。既存紙面を直す案件は analysis-template で analysisMode を source-artifact に切り替え、現物診断→提案評価→制作へ進む。brief から新規に作る案件（new-from-brief）は分析の 2 段を飛ばして制作へ進む。

本質基準は旧案件を含めて必須。欠落時は元の依頼文と確認済み事実を取り直し、runtime の essence-baseline で固定してから再開する。基準なしの描画・納品や、無承認での基準の再作成は行わない。

## 実行時のルートの決め方

`runtime_root_policy: host-skill-path` を使う。Claude Code では `CLAUDE_PLUGIN_ROOT` を使い、Codex ではホストから渡されたこの `SKILL.md` の絶対パスの2階層上を使う。どちらもプラグインの定義ファイル（`.claude-plugin/plugin.json` または `.codex-plugin/plugin.json`）の name が flyer-studio と一致することを確かめる。`cwd` や旧リポジトリから推測せず、置き換える前のプレースホルダをシェルへ渡さない。シェルを呼ぶたびに解決済みのルートを指定し、コマンドはそのルートで実行する。`prompts/` の下のファイルも、このスキルの決まりに従う。

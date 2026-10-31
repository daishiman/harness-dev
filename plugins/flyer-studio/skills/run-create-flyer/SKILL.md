---
name: run-create-flyer
description: 確定した brief の用途・素材・公開条件からチラシを制作したいとき、独立評価済みanalysisに基づく修正を実物へ反映し、新PDF/PNGと独立完成評価まで接続したいときに使う。
kind: run
prefix: run
owner: harness maintainers
version: 1.3.2
effect: local-artifact
user-invocable: true
combinators:
  - with-goal-seek
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
      text: 様式が未確定のまま制作に入ったら制作で決めずにヒアリングの様式提案へ戻し、この差し戻しを FIX の revision 辺と分けて cycle を消費しないこと（references/registry.json の nonFixReturns と tests/design.test.cjs の分離テストで検査）。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 別 context の assign-flyer-evaluator が全案の新しい PDF 由来 PNG を個別に実見して5観点と最新要求の充足を PASS とし、必須修正が0になってから finalize した納品物が、brief の読者に価値と行動を伝える purpose と保持点を実画像で満たしていること。
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

実行担当は[stage agent](agents/flyer-producer.md)、判断の基準は[stage contract](references/production-contract.md)。PLUGIN_ROOT・実行形式・記録・戻り先・本質アンカー・知識の読み方・独立性は[stage-common](../../references/stage-common.md)に必ず従う。

## Purpose & Output Contract（目標と入出力）

読者の価値と行動を伝え、保持条件と採用要求を実画像で成立させ、全案を最新証拠で納品する。

- 入力: 確認済みbrief/assets/concepts/scene。既存修正は同一baselineと要求へ結び付くanalysis.jsonと独立PASSのanalysis-review.json。完成評価から戻った必須修正（fixClass 付き）。
- 出力: 理由を伴う編集元/designIntent、紙面に合わせて決めた brief.policy の maxChars・axisGroups、要求採否のbrief.feedback、凍結入力からの新PDF/PNG・機械検査・評価テンプレート。全案の独立PASS後に finalize した納品成果。

## 選ぶ前の実成果物の作成

「Purpose & Output Contract」の最小の実成果物を親コンテキストで作る。ここでの実成果物は、確認済みの brief と素材から作る 1 案の下書きの紙面（executionPlan があるときは pilot 案の 1 つ）で、`validate` と `render --id <案ID>` が書き出す `out/<案ID>/` の print.pdf と PDF 由来 PNG である。描くのは 1 案でも、validate は全案（brief の count）の scene を検査する（init が全案の雛形を作るのは concepts だけで、scene は空である）。effect に応じた最低限の検査（validate の型・必須事実・素材の公開条件、ファイルが読み込めて開けるか・秘密情報・取り消せない操作・壊れたファイル）だけを行い、現物（PDF と PNG のパス・ハッシュ値・開き方）を見せたうえで、現状で試す／軽微／標準／詳細のどれにするかを記録する（記録する値は順に `accept-as-is`・`light`・`standard`・`detailed`）。現状で試すならその場で引き継ぎを完了とし、後続の節を実行しない。

下書きを validate する前に、この段で紙面に合わせて brief.policy の文字量（maxChars）と中心軸にそろえる意味群（axisGroups。intake で center がおまかせなら center も）を決め、brief.json へ書く（preset なしの init はどちらも空で作る）。preset の値は下書きとして扱い、今回の紙面で確かめ直す（[runtime の案件と素材](../../references/runtime.md#案件と素材)の E2 と同じ扱い）。

下書きの紙面は納品物ではない。この段では評価テンプレートも delivery.json も作らず、finalize もしない。様式が未確定の案件では下書きも描かず、[ヒアリングの局面 7](../run-intake-flyer/SKILL.md#局面カタログ) へ戻す。本質の基準（essence-baseline.json）が無い案件では、render が描画を止める。完成評価の FIX や premise の戻しでこの stage に入り直したときは、[深さの選択と戻り](../../references/stage-common.md#深さの選択と戻り)に従って直す対象の現物を示し、前に記録した深さをそのまま記録する（選び直しは求めない）。現状で試すを選んでも delivery.json は作られず、納品へは進まない。

## 選んだ深さでの改善の実行

以下の既存の節（ゴールシーク実行・Gotchas・実行への接続）は、軽微・標準・詳細のどれかが記録されて `semantic_evaluator_started` へ遷移したときだけ実行する。リリースと完全監査は別イベントとして明示されたときだけ行う。

選んだ後は stage agent が全案を制作し、別 context の[完成画像評価](../assign-flyer-evaluator/SKILL.md)と、その FIX を fixClass どおりに直す改善 cycle を回す。

選んだ深さで、評価の量（[review-rubric の評価コストの原則](../../references/review-rubric.md#評価コストの原則)）・専門レンズの昇格（design-contract の expertEscalation）・cycle の上限（cycleBudget）を緩めない。深さが変えるのは、処方として比べる構図・書体・背景の候補の数と、その比較にかける手間の量だけである。詳細を選んでも、詳細 30 法（[thirty-methods](../../references/thirty-methods.md)）は workflow の規則どおり利用者が明示したときだけ加える。

別担当の評価を通っていない版は納品（finalize）しない。選ぶ前に見せた下書きの紙面は、この納品に当たらない。

## ゴールシーク実行

進め方は [共通の判断手順](../../references/stage-common.md#共通の判断手順)。この担当では、採用要求と保持点を実レイヤーへ対応させ、構図・書体・背景の候補を比較して採用/見送りを designIntent へ残し、選んだ処方を実際に制作する。処方の制約は stage contract、共通の上限は stage-common の「戻り先と改善上限」に従う。

様式は intake で決まった brief.stylePreferences（提案を経た案件では style-proposals.json の chosen も）を起点に、[design prompt](../../prompts/design.md) に従って案ごとに具体化し、採った理由を designIntent へ残す。様式が未確定なら制作で決めず、[ヒアリングの局面 7](../run-intake-flyer/SKILL.md#局面カタログ) へ戻して回答から作った案を選んでもらう（評価 FIX ではないので cycle を消費しない）。

### ゴール

全案が最新の凍結入力から validate・render・verify を通り、別 context の assign-flyer-evaluator が全案の新しい PDF 由来 PNG を個別に実見して PASS とし、必須修正が 0 件・cycle が予算内の状態で finalize が成功し、納品物が brief の読者に価値と行動を伝える purpose と保持点を実画像で満たしている状態。

### 目的・背景

制作の自己確認は独立合格の代わりにならず、評価の FIX を受けて直す往復には案件全体で 1 つの予算がある。固定の pt・書体・構図を正解にせず、未達の採用要求と保持点から次の一手を選ぶ。

### 完了チェックリスト

- [ ] `validate --project <DIR>` が終了コード 0 で通る（IN1）。
- [ ] 全案の `render` が最新の凍結入力から成功し、`verify --project <DIR>` が終了コード 0 で通る（IN1）。
- [ ] 分析で採った要求と保持点の取りこぼしが 0 件で、designIntent に採用と見送りの理由がある（IN1）。
- [ ] executionPlan がある案件では、pilot-review.json が現在の入力と pilot 画像の SHA に結びついた PASS である（render の assertPilotOrder が止める）。
- [ ] 最新の visual-review.json で全案が PASS で、必須修正が 0 件である（OUT1）。
- [ ] `cycle-status --project <DIR>` の消費済み cycle が予算以下である（IN2）。
- [ ] 様式が未確定のまま描いた案が 0 件である（未確定ならヒアリングの局面 7 へ戻した）（IN3）。
- [ ] `finalize --project <DIR>` が成功し、delivery.json がある（OUT1）。

### ゴールシークループ

1. 未達の `[ ]` を 1 つ選ぶ → 2. その未達に効く行動を選ぶ（処方の候補を比べて scene と designIntent を直す・validate と render と verify を通す・評価テンプレートを出して別担当へ渡す・FIX を fixClass どおりに受ける・前提の崩れをヒアリングへ戻す）→ 3. 実行する → 4. 検査と評価の出力で `[x]` を更新する → 全項目が `[x]` になるまで繰り返す。FIX による往復は cycle を消費する。上限（`max_loops: 3` は cycleBudget の写し）に達しても未達なら完了扱いにせず、finalize の INCOMPLETE と未達・次に必要な修正を返す。

### ゴールシーク配線

周回の状態は案件フォルダの `<DIR>/goal-seek/` に置き、plugin の中へ書かない。この記録は判断の周回を追うためのもので、cycle-ledger.json の entry にはしない（cycle の消費は評価記録からだけ数える）。

- 上の「ゴール」の文を `original_goal` として `<DIR>/goal-seek/run-create-flyer-goal-spec.json` へ書き、その SHA-256 を `<DIR>/goal-seek/run-create-flyer-progress.json` の `original_goal_hash` に固定する。progress には完了チェックリストの各項目の状態と根拠（検査の出力か評価記録のパス）も書く。
- 各周回の終わりに `<DIR>/goal-seek/run-create-flyer-intermediate.jsonl` へ `original_goal`・`original_goal_hash`・`current_goal_snapshot`・`delta_from_original`・`merged_directive_for_next`・`drift_signal` を 1 行追記する（append-only）。次の周回は、直前の行の `merged_directive_for_next` と `original_goal` を読んでから行動を選ぶ。
- 紙面を作って直す作業は stage agent が持ち、完成の合否は別 context の完成画像評価だけが出す。この担当は評価台帳へ合否を記入しない。

### ゴールシーク検証

各周回の記録の後に次の検査を実行し、中間記録の欠落・ゴールの書き換え・ハッシュの不一致を止める（終了コード 0 を通過条件とする）。

```bash
python3 - "<DIR>/goal-seek/run-create-flyer-goal-spec.json" "<DIR>/goal-seek/run-create-flyer-intermediate.jsonl" <<'PY'
import hashlib, json, sys
goal = json.load(open(sys.argv[1], encoding='utf-8'))
rows = [json.loads(line) for line in open(sys.argv[2], encoding='utf-8') if line.strip()]
required_keys = {'original_goal','original_goal_hash','current_goal_snapshot','delta_from_original','merged_directive_for_next','drift_signal'}
expected = hashlib.sha256(goal['original_goal'].encode('utf-8')).hexdigest()
assert rows, 'intermediate.jsonl is empty'
for row in rows:
    assert required_keys <= row.keys(), required_keys - row.keys()
    assert row['original_goal'] == goal['original_goal']
    assert row['original_goal_hash'] == expected
PY
```

## Gotchas（完了判定と戻り）

必須事実・素材条件・採否が揃い、validate→render→verifyが成功。処理中の入力/素材/実装変更は失効扱い。制作の自己確認を独立合格に置き換えない。

新PDF由来PNGと評価テンプレートを[完成画像評価](../assign-flyer-evaluator/SKILL.md)へ渡し、全担当の結果が揃うまで変更しない。FIX は fixClass で決まる戻り先どおりに受ける。全案の最新独立PASSと必須修正0が揃ったら、この stage が finalize する。

## 実行への接続

PLUGIN_ROOT で次を実行する。評価テンプレート（pilot-review.json・visual-review.json の雛形）の生成と finalize はこの stage の責務で、評価担当は記入だけを行う。

```text
python3 scripts/build-flyer.py validate --project <DIR>
python3 scripts/build-flyer.py render --project <DIR> [--id <pilot案ID>]
python3 scripts/build-flyer.py pilot-review-template --project <DIR>
python3 scripts/build-flyer.py verify --project <DIR>
python3 scripts/build-flyer.py review-template --project <DIR>
python3 scripts/build-flyer.py finalize --project <DIR>
```

executionPlanがあれば先にpilot案だけを描き、pilot-review-templateの台帳をassign-flyer-evaluatorへ渡す。その独立PASSの後に残りの案を描く。

修正後に評価テンプレートを出し直すと、前の評価は cycle 台帳へ記録されてから reviews/<時刻>/ へ退避され、新しい台帳には [評価コストの原則](../../references/review-rubric.md#評価コストの原則) に従って前の PASS が引き継がれる。退避した評価や台帳を手で書き換えない。残りの予算は `cycle-status` で確かめる。

新規案件は[ヒアリング](../run-intake-flyer/SKILL.md)で brief を確定してから始める。案件の作成（doctor・init）は[runtime のコマンド一覧](../../references/runtime.md#コマンド一覧)。既存紙面を直す案件は analysis-template で analysisMode を source-artifact に切り替え、現物診断→提案評価→制作へ進む。brief から新規に作る案件（new-from-brief）は分析の 2 段を飛ばして制作へ進む。

本質基準は旧案件を含めて必須。欠落時は元の依頼文と確認済み事実を取り直し、runtime の essence-baseline で固定してから再開する。基準なしの描画・納品や、無承認での基準の再作成は行わない。

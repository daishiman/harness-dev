---
name: run-analyze-flyer
description: 既存チラシを最新要望に沿って診断・比較したいとき、提案評価の修正を反映したいときに使う。
kind: run
prefix: run
owner: harness maintainers
version: 1.3.0
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
      text: analysis.json が元画像の SHA・観察領域・保持点・全適用要求の採否理由・nextActions を実内容で持ち、判断保留や必須要望の見送り、元画像一覧の漏れ、未知の指針 ID、brief と食い違う purpose を analysis-validate が拒否すること（tests/analysis.test.cjs で検査）。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: 元画像か analysis.json が変わったら前の提案評価を失効させ、提案評価の台帳を作り直すときは前の analysis-review とその FIX を cycle 台帳へ記録してから退避すること（tests/analysis.test.cjs の失効・再評価のテストで検査）。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 別 context の assign-flyer-analysis-evaluator が元画像・最新要望と analysis.json を照合して観察の妥当性・要望の網羅・変更規律・実現性を PASS とし、その FIX をこの担当で直した分析だけが制作へ渡り、残す長所と採否理由から改善案の根拠を追えること。
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

実行担当は[stage agent](agents/artifact-analyst.md)、判断の基準は[stage contract](references/analysis-contract.md)。PLUGIN_ROOT・実行形式・記録・戻り先・本質アンカー・知識の読み方・独立性は[stage-common](../../references/stage-common.md)に必ず従う。

## Purpose & Output Contract（目標と入出力）

実際の紙面から問題と長所を特定し、明示要望を落とさず、制作へ渡せる比較可能な改善案を作る。

- 入力: 既存画像/PDF/編集元の絶対パス、今回の目的、最新の必須要望と候補、素材の公開条件。premise（前提の崩れ）の必須修正が [workflow の表](../../references/workflow.md#改善と納品) に従って分析へ戻されたときは、その案 ID・画像領域・元要求 ID。
- 出力: 元画像SHA・観察領域・保持点・要求別候補と採否理由・未達に対する次行動を持つanalysis.json。

## 選ぶ前の実成果物の作成

「Purpose & Output Contract」の最小の実成果物を親コンテキストで作る。ここでの実成果物は、元画像を 1 枚ずつ開いて書いた診断と改善案の下書き（読み順・保持点・問題の観察・要求ごとの改善案と採否の仮置き）である。effect に応じた最低限の検査（元画像が読み込めて開けるか・秘密情報・取り消せない操作・壊れたファイル）だけを行い、現物（会話に示した下書き本文。ファイルに書いた場合はパス・ハッシュ値・開き方）を見せたうえで、現状で試す／軽微／標準／詳細のどれにするかを記録する（記録する値は順に `accept-as-is`・`light`・`standard`・`detailed`）。現状で試すならその場で引き継ぎを完了とし、後続の節を実行しない。

下書きは analysis.json ではなく、制作へ渡す分析の代わりにもならない。analysis-template・analysis-seal・提案評価の台帳づくりと、stage agent への受け渡しは、この段ではしない。現状で試すを選んだときは提案評価で PASS した分析が無いため、制作の段へは進めない。提案評価の FIX や premise の戻しで入り直したときは前に記録した深さを引き継ぎ、選び直しを求めない（共通の規則は[深さの選択と戻り](../../references/stage-common.md#深さの選択と戻り)）。

## 選んだ深さでの改善の実行

以下の既存の節（ゴールシーク実行・Gotchas・実行への接続）は、軽微・標準・詳細のどれかが記録されて `semantic_evaluator_started` へ遷移したときだけ実行する。リリースと完全監査は別イベントとして明示されたときだけ行う。

選んだ後は stage agent が analysis.json を作り、別 context の[提案評価](../assign-flyer-analysis-evaluator/SKILL.md)と、その FIX をここで直す改善 cycle を回す。

選んだ深さで、提案評価の独立性・4 条件の判定・cycle の上限（[design-contract](../../references/design-contract.json) の cycleBudget）を緩めない。深さが変えるのは、元画像を観察する領域の細かさと、要求ごとの改善候補の比較にかける手間の量だけである。提案評価で PASS になっていない分析は制作へ渡さない。会話に示した下書きは、この受け渡しに当たらない。

## ゴールシーク実行

進め方は [共通の判断手順](../../references/stage-common.md#共通の判断手順)。この担当では、意図の説明より先に元画像の読み順と保持点を観察し、現物の問題と処方の仮説を分けて採否を決める。共通の上限の扱いは stage-common の「戻り先と改善上限」に従う。

### ゴール

analysis.json が元画像の SHA・観察領域・保持点・全適用要求の採否理由・nextActions を実内容で持って analysis-validate を通り、別 context の提案評価が PASS を返し、その FIX がすべてこの担当で反映された状態。

### 目的・背景

制作は分析の改善案を前提に紙面を作るため、観察の漏れや要望の見送りはそのまま完成品の欠陥になる。意図の説明に引っ張られた所見を避けるため、現物の観察と処方の仮説を分け、提案の妥当性は別担当に判定させる。

### 完了チェックリスト

- [ ] 元画像を 1 枚ずつ開いて観察し、analysis.json の元画像の SHA・観察領域・保持点が実内容で埋まっている（IN1）。
- [ ] 全適用要求に採否と理由があり、判断保留と必須要望の見送りが 0 件である（IN1）。
- [ ] `analysis-validate --project <DIR>` が終了コード 0 で通る（IN1）。
- [ ] 元画像か analysis.json が変わった周回では、前の提案評価を失効させ、前の analysis-review とその FIX を cycle 台帳へ記録してから退避している（IN2）。
- [ ] 別 context の assign-flyer-analysis-evaluator の判定が PASS で、返された FIX の未反映が 0 件である（OUT1）。
- [ ] cycle-ledger.json の消費済み cycle 数が design-contract の cycleBudget 以下である（共通の上限。[stage-common の戻り先と改善上限](../../references/stage-common.md#戻り先と改善上限)）。

### ゴールシークループ

1. 未達の `[ ]` を 1 つ選ぶ → 2. その未達に効く行動を選ぶ（元画像の観察を足す・採否と理由を書き直す・analysis-validate を通す・提案評価へ渡す・返された FIX を反映する）→ 3. 実行する → 4. 検査と評価の出力で `[x]` を更新する → 全項目が `[x]` になるまで繰り返す。提案評価の FIX による往復は cycle を消費する。上限（`max_loops: 3` は cycleBudget の写し）に達しても未達なら完了扱いにせず、INCOMPLETE として未達と次に必要な修正を返す。

### ゴールシーク配線

周回の状態は案件フォルダの `<DIR>/goal-seek/` に置き、plugin の中へ書かない。この記録は判断の周回を追うためのもので、cycle-ledger.json の entry にはしない（cycle の消費は評価記録からだけ数える）。

- 上の「ゴール」の文を `original_goal` として `<DIR>/goal-seek/run-analyze-flyer-goal-spec.json` へ書き、その SHA-256 を `<DIR>/goal-seek/run-analyze-flyer-progress.json` の `original_goal_hash` に固定する。progress には完了チェックリストの各項目の状態と根拠（検査の出力か評価記録のパス）も書く。
- 各周回の終わりに `<DIR>/goal-seek/run-analyze-flyer-intermediate.jsonl` へ `original_goal`・`original_goal_hash`・`current_goal_snapshot`・`delta_from_original`・`merged_directive_for_next`・`drift_signal` を 1 行追記する（append-only）。次の周回は、直前の行の `merged_directive_for_next` と `original_goal` を読んでから行動を選ぶ。
- analysis.json を作って直す作業は stage agent が持ち、提案の合否は別 context の提案評価だけが出す。この担当は評価台帳を記入しない。

### ゴールシーク検証

各周回の記録の後に次の検査を実行し、中間記録の欠落・ゴールの書き換え・ハッシュの不一致を止める（終了コード 0 を通過条件とする）。

```bash
python3 - "<DIR>/goal-seek/run-analyze-flyer-goal-spec.json" "<DIR>/goal-seek/run-analyze-flyer-intermediate.jsonl" <<'PY'
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

元画像を個別に開き、全適用要求の判断、保持点、観察領域、必要指針ID、nextActionsが実内容で記録され、analysis-validateが通る。機械PASSは提案品質の独立承認ではない。

別contextの[提案評価](../assign-flyer-analysis-evaluator/SKILL.md)へ渡し、FIXはここで直す。入力不足はこのstageで補い、既に許可された分析・修正を細切れの再確認へ戻さない。

提案評価の PASS 後の実行範囲は [workflow](../../references/workflow.md#stage-ごとの要点) に従う。制作まで許可済みなら制作へ進み、分析だけの依頼ならここで返す。制作の依頼が未指定のときだけ 1 回確認する。cycle-ledger.json は制作が引き継ぐ。

## 実行への接続

PLUGIN_ROOT で次を実行する。analysis-template の brief.analysisMode 切替と、提案評価テンプレート生成・再発行時の記録/退避は、この stage の準備責務（[所有と機械による付随更新](../../references/stage-common.md#所有と機械による付随更新)）。生成した台帳と同一版の分析・元画像を別担当へ渡し、評価内容は記入しない。

```text
python3 scripts/build-flyer.py analysis-template --project <DIR> --sources <SOURCES.json>
python3 scripts/build-flyer.py analysis-seal --project <DIR>
python3 scripts/build-flyer.py analysis-validate --project <DIR>
python3 scripts/build-flyer.py analysis-review-template --project <DIR>
```

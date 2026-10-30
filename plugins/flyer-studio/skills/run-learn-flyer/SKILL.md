---
name: run-learn-flyer
description: 納品済み案件の傾向を記録・集計したいとき、次回ヒアリングや質問改善の参考が欲しいときに使う。
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
feedback_contract:
  activation_state: semantic_evaluator_started
  criteria:
    - id: IN1
      loop_scope: inner
      text: learn-record が finalize 済みの案件だけを learn-record schema の許可リストで検査して台帳へ1行だけ追記し、同じ finalize の再記録で行を増やさず、個人情報・事実値・自由記述・許可外のキーを含む行は切り詰めずに保存を止めること（tests/learn.test.cjs で検査）。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: learn-report と learn-suggest が件数と割合の下限を満たす傾向だけを根拠と反例の件数付きで返し（様式ラベルの傾向と参考候補は件数の下限だけで選び、割合条件は使わない）、件数不足は insufficient として件数だけを示し、参考値は suggestion・要確認として事実値を含まないこと（tests/learn.test.cjs で検査）。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 返した改善仮説が件数・母数・反例・missingInputs と preset の範囲に基づいて因果を断定せず、人が採否を選ぶまで intake-questions.json・preset・本質条項を書き換えないまま、次のヒアリングの聞き方を確かめられる形になっていること。
      verify_by: human
manifest: workflow-manifest.json
schema_refs:
  - ../../schemas/learn-record.schema.json
reference_refs:
  - ../../references/stage-common.md
  - ../../references/essence.json
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

# 案件をまたいでヒアリングの知見を貯め、次の制作に生かす

共通の判断手順・実行形式・所有と記録は[stage-common](../../references/stage-common.md)に必ず従う。台帳への記録・集計・閾値の適用は機械コマンドが、集計をどこまで説明に使えるかと改善仮説の選択はこの担当の AI が行う。

## Purpose & Output Contract（目標と入出力）

入力は納品済み案件と既存台帳。出力は個人情報を除いた記録・集計・参考値と、AIが返す限定的な改善仮説。

- **finalize の後**: 納品が完了した案件（`out/delivery.json` が complete）を台帳へ 1 行記録する。
- **新しいヒアリングの前**: 過去の傾向を、一括シートへ添える参考値（要確認）として受け取る。
- **ヒアリングの質問を見直したいとき**: 台帳の根拠と反例を読み、次に確かめる改善仮説を返す。

集計の母集団は納品完了案件だけ。予算切れの INCOMPLETE や分析のみで終了した案件は含まれず、全実行の成功率・失敗原因・重い失敗の頻度を推定する材料にはしない。

## 選ぶ前の実成果物の作成

「Purpose & Output Contract」の最小の実成果物を親コンテキストで作る。ここでの実成果物は場面ごとに 1 つで、finalize の後は `learn-record` が台帳へ書いた 1 行と `learn-report` の出力を写した集計の要約案、新しいヒアリングの前は `learn-suggest` の参考値、質問を見直したいときは `learn-report` の出力を写した集計の要約案である。effect に応じた最低限の検査（読み込めて開けるか・秘密情報・取り消せない操作・壊れたファイル）だけを行い、現物（会話に示した要約案の本文と、台帳のパス・追記した行のハッシュ値・開き方）を見せたうえで、現状で試す／軽微／標準／詳細のどれにするかを記録する（記録する値は順に `accept-as-is`・`light`・`standard`・`detailed`）。現状で試すならその場で引き継ぎを完了とし、後続の節を実行しない。

要約案は件数・母数・反例・insufficient をそのまま写した下書きで、改善仮説ではない。集計の解釈と改善仮説、人による採否は、次の節を通したときにだけ扱う。

## 選んだ深さでの改善の実行

以下の既存の節（Gotchas・ゴールシーク実行）は、軽微・標準・詳細のどれかが記録されて `semantic_evaluator_started` へ遷移したときだけ実行する。リリースと完全監査は別イベントとして明示されたときだけ行う。

ただし、Gotchas の台帳の規則（plugin の外の追記専用ファイル・保存しないもの・保存前の許可リスト検査・冪等）は、選ぶ前の `learn-record` にも掛かる。

選んだ後は、AI が集計を解釈して改善仮説を返し、人が採否を決める（局面カタログの 3 と 4）。選んだ深さで、件数と割合の下限（minCases・minRate）、個人情報を保存しない規則（E3）、因果を断定しない規則を緩めない。深さが変えるのは、集計の解釈と改善仮説の組み立てにかける手間の量だけである。

## Gotchas（台帳の場所と、保存しないもの）

- 台帳は `${FLYER_STUDIO_HOME:-~/.flyer-studio}/ledger/cases.jsonl`（1 行 1 案件の追記専用ファイル）。plugin の中には置けず、置こうとすると止まる。
- 保存するのは field path（brief の項目名）・回答の出典（source）・修正の分類（fixClass）・好みの分類名・回数・様式の短いラベルだけ。回答の値・氏名・電話番号・メール・URL・自由記述・参考画像のパス・雰囲気語の文章は保存しない（[essence](../../references/essence.json) の E3）。
- 保存の直前に [learn-record schema](../../schemas/learn-record.schema.json) の allowlist（許可リスト）で検査し、想定外のキー・40 字を超える文字列・個人情報らしい値があれば、切り詰めずに保存を止める（fail-closed＝迷ったら止める）。
- 同じ案件・同じ finalize の再記録は行を増やさない（冪等＝何回実行しても結果が同じ）。finalize をやり直した案件は新しい行になり、集計では最新の 1 行だけを数える。
- 入力ファイル（intake.json・cycle-ledger.json・visual-review.json・essence-baseline.json・concepts.json・style-proposals.json）が無くても失敗にせず、欠けたものを `missingInputs` に残す。

## ゴールシーク実行

固定の手順を順に消化するのでなく、下の「ゴール」と `feedback_contract`（IN1・IN2・OUT1）を満たすまで、呼び出された親コンテキストで反復する（`engine=inline` / `fork=inline`）。

### ゴール

場面に応じた成果（finalize の後は台帳の 1 行と集計の解釈、ヒアリングの前は参考値、見直しでは改善仮説）が、個人情報を含まず、件数・母数・反例と 2 つの下限（minCases と minRate。様式ラベルの傾向と参考候補は minCases だけ）に基づく形で返され、採用する変更を人が選べる状態になっている。

### 目的・背景

少ない件数や偏った案件から因果を断定すると、次のヒアリングを誤った方向へ変えてしまう。記録・集計・閾値は機械に任せ、AI は集計をどこまで説明に使えるかだけを判断し、採否は人が決める。

### 完了チェックリスト

- [ ] finalize の後の場面では `learn-record --project <DIR>` が成功し、同じ finalize の再実行で台帳の行数が増えていない（IN1）。
- [ ] 台帳の行に回答の値・氏名・電話番号・メール・URL・自由記述が 0 件である（IN1・E3）。
- [ ] 返した傾向はすべて minCases と minRate の両方を満たし（様式ラベルの傾向と参考候補は minCases だけで選び、割合条件は使わない）、根拠と反例の件数が付いている。満たさない項目は insufficient として件数だけを示している（IN2）。
- [ ] 改善仮説に件数・母数・反例・missingInputs と preset の範囲が書かれ、因果を断定する文が 0 件である（OUT1）。
- [ ] 人が採否を選ぶ前に書き換えた intake-questions.json・preset・本質条項が 0 件である（OUT1）。

### ゴールシークループ

1. 未達の `[ ]` を 1 つ選ぶ → 2. 下の局面カタログから、その未達に効く局面を選ぶ → 3. 実行する → 4. コマンドの出力で `[x]` を更新する → 全項目が `[x]` になるまで繰り返す。件数が足りない未達は、提案を足して埋めず、根拠不足として返して止める。

### 局面カタログ

順序は都度判断する。番号は参照用で、実行の順番を固定しない。PLUGIN_ROOT で次を実行する。

```text
python3 scripts/build-flyer.py learn-record --project <DIR>
python3 scripts/build-flyer.py learn-report [--min-cases N] [--preset NAME]
python3 scripts/build-flyer.py learn-suggest [--min-cases N] [--preset NAME]
```

1. **記録**: finalize が終わった案件で `learn-record` を実行する。finalize 前の案件は記録できない。
2. **集計**: `learn-report` は次の 7 項目を markdown と json で返す。集計対象の案件数が `--min-cases`（件数の下限。省略時の値は learn.cjs の既定）未満の項目は提案にせず、`insufficient`（件数不足）として件数だけを示す。提案にする傾向は、その傾向に当てはまる件数が minCases 以上、かつ集計対象中の割合が minRate（割合の下限。learn.cjs が固定し、CLI に変えるオプションはない）以上の両方を満たすものだけ。今回使った 2 つの下限の値は learn-report の出力の minCases・minRate で確かめる。提案には根拠の件数と反例（当てはまらなかった案件）の件数を添える。
   - (a) 1 回目のヒアリングで未確定になりやすい質問 → 一括シートでの聞き方・順序の見直し
   - (b) 追加ラウンド数の分布
   - (c) 修正の分類と前提（premise）へ戻る頻度 → ヒアリングで先に確かめる前提。提案 FIX の件数と前提崩れは分けて読む
   - (d) 好み（preference）の傾向。汎用の規則へは昇格させない
   - (e) 目的・確定事実が途中で変わる頻度
   - (f) 様式を言葉にできず、提案から選んだかおまかせにした割合
   - (g) 採択された様式ラベルの傾向
3. **AI が集計を解釈する**: 閾値を満たした傾向について、件数・母数・反例・missingInputs と preset の範囲を確かめる。同じ数字でも資料不足や案件の偏りなど別の説明があり得るため、因果を断定しない。観測した傾向、説明できない範囲、変えてみる質問の表現や順序、次の案件で確かめる状態を結び、必要な改善仮説だけを返却文へ書く。件数不足なら追加提案で埋めず、根拠不足として返す。機械出力や台帳に自由な原因文・個人情報を追記しない。
4. **人が採否を決める**: 仮説と反例を見せ、採用する変更を人が選ぶ。質問票などへの反映はその選択を受けた別の変更作業として扱う。このスキルは質問・preset・本質条項を自動では書き換えず、知見の件数や既存の閾値も都合よく変更しない。

新しいヒアリングの前に `learn-suggest` を実行すると、質問ごとの短い参考文と「前回までに選ばれた様式（参考・要確認）」を返す。未確定になりやすい質問と様式を言葉にできなかった傾向は、上記の件数・割合の両条件を使う。様式ラベルの参考候補は、ラベルのある案件数とそのラベルの採択件数がどちらも minCases 以上のものから learn.cjs が決める上位の件数までで、割合条件は使わない。どれも `source: "suggestion"`・`reconfirm: true` の参考値で、事実値は含まない。一括シートでは「前回までの傾向」として見せ、利用者が確かめた内容だけを回答として保存する。

### ゴールシーク配線

周回の状態は、実行ごとの記録フォルダ `<RUN>` = `${FLYER_STUDIO_HOME:-~/.flyer-studio}/goal-seek/run-learn-flyer/<開始時刻（UTC の YYYYMMDDTHHMMSSZ）>/` に置き、plugin の中と台帳（ledger/cases.jsonl）へは書かない。案件をまたぐ集計もあるため、案件フォルダには置かない。

- 上の「ゴール」の文を `original_goal` として `<RUN>/run-learn-flyer-goal-spec.json` へ書き、その SHA-256 を `<RUN>/run-learn-flyer-progress.json` の `original_goal_hash` に固定する。progress には完了チェックリストの各項目の状態と根拠（どのコマンドの出力か）も書く。
- 各周回の終わりに `<RUN>/run-learn-flyer-intermediate.jsonl` へ `original_goal`・`original_goal_hash`・`current_goal_snapshot`・`delta_from_original`・`merged_directive_for_next`・`drift_signal` を 1 行追記する（append-only）。次の周回は、直前の行の `merged_directive_for_next` と `original_goal` を読んでから局面を選ぶ。
- 記録には回答の値・個人情報・自由な原因文を写さず、未達の項目と次の一手だけを書く（E3）。

### ゴールシーク検証

各周回の記録の後に次の検査を実行し、中間記録の欠落・ゴールの書き換え・ハッシュの不一致を止める（終了コード 0 を通過条件とする）。

```bash
python3 - "<RUN>/run-learn-flyer-goal-spec.json" "<RUN>/run-learn-flyer-intermediate.jsonl" <<'PY'
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

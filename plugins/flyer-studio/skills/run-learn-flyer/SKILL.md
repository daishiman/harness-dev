---
name: run-learn-flyer
description: finalize 済みの案件から個人情報を含まない知見を台帳へ追記したいとき、件数の揃った傾向だけをヒアリング改善の提案と次回の参考値（要確認）にしたいときに使う。intake-questions.json や preset は自動で書き換えない。
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
      text: learn-record が finalize 済みの案件だけを learn-record schema の許可リストで検査して台帳へ1行だけ追記し、同じ finalize の再記録で行を増やさず、個人情報・事実値・自由記述・許可外のキーを含む行は切り詰めずに保存を止めること（tests/learn.test.cjs で検査）。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: learn-report と learn-suggest が件数と割合の下限を満たす傾向だけを根拠と反例の件数付きで返し、件数不足は insufficient として件数だけを示し、参考値は suggestion・要確認として事実値を含まないこと（tests/learn.test.cjs で検査）。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 返した改善仮説が件数・母数・反例・missingInputs と preset の範囲に基づいて因果を断定せず、人が採否を選ぶまで intake-questions.json・preset・本質条項を書き換えないまま、次のヒアリングの聞き方を確かめられる形になっていること。
      verify_by: human
manifest: workflow-manifest.json
responsibility_refs:
  - ../../references/stage-common.md
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

## 選ぶ前の実成果物の作成

納品記録に基づく集計と適用限界を返す。仮説の検証前に規範や次の案件を自動変更しない。最小の構文・破損・公開条件の検査後、実在パスと内容の指紋を示す。利用者の選択（accept-as-is / light / standard / detailed）を記録する。最初から独立検査まで明示されていればその既存指示を選択として扱い、再確認しない。accept-as-isでは初稿を渡して終了し、未実施の評価や納品完了を主張しない。

## 選んだ深さでの改善の実行

以下の担当・独立評価・改善反復は light / standard / detailed の選択を記録し semantic_evaluator_started へ移った後に実行する。新しい必須修正がなければ繰り返さない。


共通の判断手順・実行形式・所有と記録は[stage-common](../../references/stage-common.md)に従う。台帳への記録・集計・閾値の適用は機械コマンドが、集計をどこまで説明に使えるかと改善仮説の選択はこの担当の AI が行う。

## いつ使うか

- **finalize の後**: 納品が完了した案件（`out/delivery.json` が complete）を台帳へ 1 行記録する。
- **新しいヒアリングの前**: 過去の傾向を、一括シートへ添える参考値（要確認）として受け取る。
- **ヒアリングの質問を見直したいとき**: 台帳の根拠と反例を読み、次に確かめる改善仮説を返す。

集計の母集団は納品完了案件だけ。予算切れの INCOMPLETE や分析のみで終了した案件は含まれず、全実行の成功率・失敗原因・重い失敗の頻度を推定する材料にはしない。

## 台帳の場所と、保存しないもの

- 台帳は `${FLYER_STUDIO_HOME:-~/.flyer-studio}/ledger/cases.jsonl`（1 行 1 案件の追記専用ファイル）。plugin の中には置けず、置こうとすると止まる。
- 保存するのは field path（brief の項目名）・回答の出典（source）・修正の分類（fixClass）・好みの分類名・回数・様式の短いラベルだけ。回答の値・氏名・電話番号・メール・URL・自由記述・参考画像のパス・雰囲気語の文章は保存しない（[essence](../../references/essence.json) の E3）。
- 保存の直前に [learn-record schema](../../schemas/learn-record.schema.json) の allowlist（許可リスト）で検査し、想定外のキー・40 字を超える文字列・個人情報らしい値があれば、切り詰めずに保存を止める（fail-closed＝迷ったら止める）。
- 同じ案件・同じ finalize の再記録は行を増やさない（冪等＝何回実行しても結果が同じ）。finalize をやり直した案件は新しい行になり、集計では最新の 1 行だけを数える。
- 入力ファイル（intake.json・cycle-ledger.json・visual-review.json・essence-baseline.json・concepts.json・style-proposals.json）が無くても失敗にせず、欠けたものを `missingInputs` に残す。

## 手順

PLUGIN_ROOT で次を実行する。

```text
python3 scripts/flyer.py learn-record --project <DIR>
python3 scripts/flyer.py learn-report [--min-cases N] [--preset NAME]
python3 scripts/flyer.py learn-suggest [--min-cases N] [--preset NAME]
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

## 実行時のルートの決め方

`runtime_root_policy: host-skill-path` を使う。Claude Code では `CLAUDE_PLUGIN_ROOT` を使い、Codex ではホストから渡されたこの `SKILL.md` の絶対パスの2階層上を使う。どちらもプラグインの定義ファイル（`.claude-plugin/plugin.json` または `.codex-plugin/plugin.json`）の name が flyer-studio と一致することを確かめる。`cwd` や旧リポジトリから推測せず、置き換える前のプレースホルダをシェルへ渡さない。シェルを呼ぶたびに解決済みのルートを指定し、コマンドはそのルートで実行する。`prompts/` の下のファイルも、このスキルの決まりに従う。

## ゴールシーク実行

共通の判断手順に従い、未達の目的・事実・公開条件を確かめ、必要な判断と検査だけを行って結果を受け渡す。最大3周とし、未確定の事実や未達の完了条件が残れば未完了として返す。評価や制作は担当外へ委譲し、自己承認しない。

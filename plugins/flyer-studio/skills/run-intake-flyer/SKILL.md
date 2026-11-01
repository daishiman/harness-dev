---
name: run-intake-flyer
description: どんなチラシ・画像を作りたいかを、全質問を 1 枚にした一括回答と不足・矛盾だけの追加確認で聞き取り、brief.json・intake.json と本質の基準（essence-baseline.json）を作りたいとき、様式を言葉にしにくい利用者へ回答から読み取った 2〜3 案の様式を提案したいときに使う。
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
      text: 一括シートが確定事実と必須の質問を1枚に載せ、intake-residual が不足・矛盾・確認だけを返して答えた質問を聞き直さず、仮置きや未確認の確定事実が残る間は assertResolved が止めること（tests/intake.test.cjs で検査）。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: essence-baseline.json が依頼文・purpose・確定事実を固定して上書きを拒み、承認記録の無い目的や事実の変更を essence-check が drift として止めること（tests/essence.test.cjs で検査）。
      verify_by: test
    - id: IN3
      loop_scope: inner
      text: 雰囲気の言葉だけの様式では styleProposalNeeded が根拠を返し、選ばれた案と回答が一致するまで様式を未解決に残し、様式が未確定なだけでは本質の基準づくりを止めないこと（tests/intake.test.cjs の様式提案のテストで検査）。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 利用者が事実の一覧（項目・値・出典）を見て confirm-facts で認め、様式を提案から選ぶかおまかせにした結果として、少ない往復で読者・価値・行動と確定事実が今回の回答か資料だけから受け取られ、公開範囲が確かめられていること。
      verify_by: human
manifest: workflow-manifest.json
responsibility_refs:
  - references/interview-guide.md
schema_refs:
  - ../../schemas/intake.schema.json
  - ../../schemas/style-proposals.schema.json
  - ../../schemas/essence-baseline.schema.json
  - ../../schemas/brief.schema.json
reference_refs:
  - references/interview-guide.md
  - ../../references/intake-questions.json
  - ../../references/stage-common.md
  - ../../references/style-profiles.md
  - ../../references/essence.json
knowledge_refs:
  - DD07
  - DD11
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

# 作りたいものを少ない往復で聞き取り、制作の基準を固定する

## 選ぶ前の実成果物の作成

資料から得た事実と不足を整理した一括回答シートを案件フォルダに作る。未確認の事実は確定せず、既存回答があれば再利用する。最小の構文・破損・公開条件の検査後、実在パスと内容の指紋を示す。利用者の選択（accept-as-is / light / standard / detailed）を記録する。最初から独立検査まで明示されていればその既存指示を選択として扱い、再確認しない。accept-as-isでは初稿を渡して終了し、未実施の評価や納品完了を主張しない。

## 選んだ深さでの改善の実行

以下の担当・独立評価・改善反復は light / standard / detailed の選択を記録し semantic_evaluator_started へ移った後に実行する。新しい必須修正がなければ繰り返さない。


共通の判断手順・実行形式・所有と記録は[stage-common](../../references/stage-common.md)に従う。聞き方の指針は[interview-guide](references/interview-guide.md)、質問の正本は[intake-questions.json](../../references/intake-questions.json)。知識は[指針 ID の索引](../../references/design-knowledge-index.json)で usedBy に intake を含む DD07（公開範囲）と DD11（表現様式）だけを、必要になったときに読む。

## 目標と入出力

利用者の手間を最小にして、読者・価値・行動（purpose）と確定事実を今回の回答か資料からだけ受け取り（E1・E2）、公開範囲を確かめる（E3）。

- 入力: 依頼文・支給資料・選んだ preset（任意）・前回までの傾向（learn-suggest。参考値で、事実には使わない）。
- 出力: 案件フォルダ（plugin の外）の brief.json・intake.json・style-proposals.json（様式提案をしたときだけ）・essence-baseline.json。回答には個人情報が入るため、シート・回答・記録はすべて案件フォルダに置き、plugin の中へ書かない（E3）。

## この担当が判断すること

資料の記述が今回の確定事実か、参考や未確定情報かを区別し、対応する質問と出典を選ぶ。資料どうしが食い違う場合は値を合成せず、何が判断を変えるかを示して不足確認へ回す。前回の傾向は再確認する参考値に限る。

様式案は回答の根拠と使用できる素材から作り、目的への効き方と保持リスクを比較する。質問の出し方と追加確認の範囲は interview-guide、記入・未解決検出・型検査はコマンドに任せる。AI が回答の意味を判断し、コマンドが事実を創作したり様式を選んだりしたとは扱わない。

## 手順

PLUGIN_ROOT で `python3 scripts/flyer.py <command>` と実行する（各コマンドの意味は[runtime のコマンド一覧](../../references/runtime.md#コマンド一覧)）。

1. **依頼文と資料を読む**: 今回の事実と、その出典・不明点を整理する。この時点では読み取った値をメモリ上に保持し、新しい `<DIR>` を作らない。preset は利用者が指定したときか、同じ催しの続きだと確かめたときだけ使う。
2. **案件を作って事前記入を保存する**: `doctor`、続けて `init --project <DIR> [--preset <id>]`。init は既存 DIR を拒否するため、その成功後にだけ `<DIR>/prefill.json` を `{質問 id か briefPath: {value, source}}` で保存する。source は依頼文なら answer、支給資料なら document。推測値や前回の値は書かない。既存案件の再開では既存 brief・回答を読み、init をやり直さない。
3. **前回までの傾向を受け取る**: `learn-suggest [--preset <id>] > <DIR>/suggestions.json`。台帳が無くても続ける。
4. **全質問を 1 枚で出す**: `intake-template [--preset <id>] --prefill <DIR>/prefill.json --suggestions <DIR>/suggestions.json --out <DIR>/intake-sheet.md`。シートを 1 回で見せ、分かる項目に一度に答えてもらう。資料から読み取れた値は「確認のみ」の表に出る。prefillRejected に出た値（年の抜けなど）は質問として残る。
5. **一括回答を反映する**: 回答を `<DIR>/intake-sheet.answers.json` に写し、originalRequest に最初の依頼文をそのまま入れて `intake-apply --project <DIR> --answers <DIR>/intake-sheet.answers.json`。事前記入された参考値（source が suggestion）は、利用者が今回の希望と認めた項目だけ source を外す。参考値のまま渡すと problems に戻る。
6. **不足と矛盾だけを聞く**: `intake-residual --project <DIR>` の markdown を 1 回にまとめて聞き、json.skeleton に答えを写して intake-apply する。既に答えのある質問は聞き直さない。確定事実が揃うと、事実の一覧（項目・値・出典）が出るので、利用者が「はい」と答えた回に confirm-facts を渡す。count が 0 になるまで 6 を繰り返す（done は 7 で様式が決まると true になる）。
7. **回答の根拠から様式を提案する**: styleProposalNeeded が null でなければ、その basis（雰囲気の言葉・参考・避けたいもの・purpose・素材）を根拠に、[style-profiles の「様式の記述軸」](../../references/style-profiles.md#様式の記述軸)の 8 軸で書き分けた 2〜3 案を作る（[「提案時の使い方」](../../references/style-profiles.md#提案時の使い方)）。各案に basisUsed（使った根拠）と fit（読者・価値・行動への効き方）を書き、`<DIR>/style-proposals.json` に chosen を空で保存して見せる。
   - 利用者が選んだら chosen に案 ID、chosenBy に user、decidedAt に時刻を入れる。おまかせなら chosenBy を delegated にし、目的への効き方が最も強い案を採るか案ごとに振り分け、pilot の確認で様式も見てもらう。
   - 選ばれた案の label をそのまま `{"/stylePreferences": {"value": [label…], "source": "proposal"}}` で intake-apply する。label は 40 字以内の短い自由ラベルにする。chosen と一致しない値は unresolved に戻る。
   - 実在の作家名・作品名を案の名前や軸に書かない（E3）。reason が pending-choice なら選んでもらい、pending-apply なら apply だけを行う。
8. **本質の基準を固定する**: `essence-baseline --project <DIR> --request "<最初の依頼文>"`。未解決や仮置きの事実が残っていれば止まる（assertResolved）。様式が決まっていないだけでは止まらない。
9. **基準からのずれを確かめる**: 制作へ渡す前と finalize の前に `essence-check --project <DIR>`。drift が出たら具体的な変更を利用者に確かめ、明示的に承認された変更だけを brief.json に反映する。`essence-revise --project <DIR> --field <変更した項目のパス> --reason "<承認理由>"` で承認記録を追記してから、`essence-check --project <DIR>` を再実行する（R2）。承認記録を手で追記しない。文字量（maxChars）と中心軸の意味群（axisGroups）はヒアリングで聞かず、制作の段で決める。

## 完了判定と戻り

intake-residual の done が true、essence-baseline.json があり、essence-check の fail が 0 なら完了。既存紙面を直す案件（mode が revise）は[現物診断](../run-analyze-flyer/SKILL.md)へ、それ以外は[制作](../run-create-flyer/SKILL.md)へ渡す。後の段で目的や事実が変わったときは、承認記録を残してから 9 を通し直す。

## 実行時のルートの決め方

`runtime_root_policy: host-skill-path` を使う。Claude Code では `CLAUDE_PLUGIN_ROOT` を使い、Codex ではホストから渡されたこの `SKILL.md` の絶対パスの2階層上を使う。どちらもプラグインの定義ファイル（`.claude-plugin/plugin.json` または `.codex-plugin/plugin.json`）の name が flyer-studio と一致することを確かめる。`cwd` や旧リポジトリから推測せず、置き換える前のプレースホルダをシェルへ渡さない。シェルを呼ぶたびに解決済みのルートを指定し、コマンドはそのルートで実行する。`prompts/` の下のファイルも、このスキルの決まりに従う。

## ゴールシーク実行

共通の判断手順に従い、未達の目的・事実・公開条件を確かめ、必要な判断と検査だけを行って結果を受け渡す。最大3周とし、未確定の事実や未達の完了条件が残れば未完了として返す。評価や制作は担当外へ委譲し、自己承認しない。

---
name: run-intake-flyer
description: 作りたいチラシや画像を少ない往復で聞き取って brief.json と本質の基準を作りたいとき、様式を言葉にしにくい利用者へ回答から読み取った 2〜3 案の様式を提案したいときに使う。
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
feedback_contract:
  activation_state: semantic_evaluator_started
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
runtime_root_policy: host-skill-path
---

# 作りたいものを少ない往復で聞き取り、制作の基準を固定する

共通の判断手順・実行形式・所有と記録は[stage-common](../../references/stage-common.md)に必ず従う。聞き方の指針は[interview-guide](references/interview-guide.md)、質問の正本は[intake-questions.json](../../references/intake-questions.json)。知識は[指針 ID の索引](../../references/design-knowledge-index.json)で usedBy に intake を含む DD07（公開範囲）と DD11（表現様式）だけを、必要になったときに読む。

## Purpose & Output Contract（目標と入出力）

利用者の手間を最小にして、読者・価値・行動（purpose）と確定事実を今回の回答か資料からだけ受け取り（E1・E2）、公開範囲を確かめる（E3）。

- 入力: 依頼文・支給資料・選んだ preset（任意）・前回までの傾向（learn-suggest。参考値で、事実には使わない）。
- 出力: 案件フォルダ（plugin の外）の brief.json・intake.json・style-proposals.json（様式提案をしたときだけ）・essence-baseline.json。回答には個人情報が入るため、シート・回答・記録はすべて案件フォルダに置き、plugin の中へ書かない（E3）。

<!-- runtime-root-contract:v1 -->
## 実行時のルートの決め方

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Code では、プラグインのルートとして `CLAUDE_PLUGIN_ROOT` を使う。
- Codex では、ホストが示したこの `SKILL.md` の絶対パスから上の階層へたどり、プラグインの定義ファイル（`.codex-plugin/plugin.json` か `.claude-plugin/plugin.json`）を持つ最も近い祖先で、定義の `name` が `flyer-studio` と一致することを確認し、その祖先を論理上の `PLUGIN_ROOT` とする（[stage-common](../../references/stage-common.md#起点と実行形式)の「`skills/<stage>/SKILL.md` の 2 階層上」と同じ場所になる）。
- 定義ファイルが読めない・不正・`name` が一致しない場合は、スクリプトを実行せず診断を返す。
- 作業ディレクトリ（`cwd`）からプラグインのルートを推測しない。置き換える前のプレースホルダをそのままシェルへ渡さない。シェルを呼ぶたびに、その中で解決済みの絶対パスを `PLUGIN_ROOT` に入れる。
<!-- /runtime-root-contract:v1 -->

## 選ぶ前の実成果物の作成

「Purpose & Output Contract」の最小の実成果物を親コンテキストで作る。ここでの実成果物は、依頼文と支給資料だけから書いたヒアリング要約の下書き（読者・価値・行動の仮置き、事実とその出典、不明点）と、言葉で書いた様式案の下書きである。effect に応じた最低限の検査（読み込めて開けるか・秘密情報・取り消せない操作・壊れたファイル）だけを行い、現物（会話に示した下書き本文。ファイルに書いた場合はパス・ハッシュ値・開き方）を見せたうえで、現状で試す／軽微／標準／詳細のどれにするかを記録する（記録する値は順に `accept-as-is`・`light`・`standard`・`detailed`）。現状で試すならその場で引き継ぎを完了とし、後続の節を実行しない。

下書きの値は確定事実として扱わず、この段では新しい `<DIR>` も brief.json も作らない。制作の段へ渡す brief.json と本質の基準は、次の節を通したときにだけ作られる。仮置きの事実が残る間は、本質の基準づくり（essence-baseline）の assertResolved が止める。現状で試すを選んだときは brief.json と essence-baseline.json が作られないため、制作の段（既存紙面があれば分析の段）へは進めない。前提の再確認（premise）で入り直したときは前に記録した深さを引き継ぎ、選び直しを求めない（共通の規則は[深さの選択と戻り](../../references/stage-common.md#深さの選択と戻り)）。

## 選んだ深さでの改善の実行

以下の既存の節（この担当が判断すること・ゴールシーク実行・Gotchas）は、軽微・標準・詳細のどれかが記録されて `semantic_evaluator_started` へ遷移したときだけ実行する。リリースと完全監査は別イベントとして明示されたときだけ行う。

ただし「この担当が判断すること」のうち、資料の記述を確定事実と参考に分けること・食い違う値を合成しないこと・前回の傾向を参考値に限ることは、選ぶ前の下書きにも掛かる。

選んだ深さで、確定事実の出典（E1・E2）と公開範囲の確認（E3）、assertResolved と essence-check の停止条件を緩めない。深さが変えるのは、聞き取りの往復と様式提案にかける手間の量だけである。

## この担当が判断すること

資料の記述が今回の確定事実か、参考や未確定情報かを区別し、対応する質問と出典を選ぶ。資料どうしが食い違う場合は値を合成せず、何が判断を変えるかを示して不足確認へ回す。前回の傾向は再確認する参考値に限る。

様式案は回答の根拠と使用できる素材から作り、目的への効き方と保持リスクを比較する。質問の出し方と追加確認の範囲は interview-guide、記入・未解決検出・型検査はコマンドに任せる。AI が回答の意味を判断し、コマンドが事実を創作したり様式を選んだりしたとは扱わない。

## ゴールシーク実行

固定の手順を順に消化するのでなく、下の「ゴール」と `feedback_contract`（IN1〜IN3・OUT1）を満たすまで、利用者と対話する親コンテキストで反復する（`engine=inline` / `fork=inline`）。質問と回答の往復は親が持ち、聞き取りを別の context へ移さない。

### ゴール

案件フォルダに brief.json・intake.json（様式を提案したときは style-proposals.json も）・essence-baseline.json があり、intake-residual の done が true、essence-check の fail が 0 で、読者・価値・行動と確定事実が今回の回答か資料だけから受け取られ、公開範囲が確かめられている状態。

### 目的・背景

利用者の手間を最小にして、制作の基準を固定する。決まった一問一答で進めると、答えた質問の聞き直し・資料の値の取り違え・前回の傾向の事実化が起きやすい。そこで未解決の項目だけを都度選んで埋め、確定事実の出典をコマンドの検査で確かめる。

### 完了チェックリスト

- [ ] `intake-residual --project <DIR>` の count が 0 で、done が true である（IN1）。
- [ ] 利用者が事実の一覧（項目・値・出典）を認めた回に confirm-facts を渡し、source が suggestion のままの値が 0 件である（OUT1・E1・E2）。
- [ ] styleProposalNeeded が null であるか、style-proposals.json の chosen と `/stylePreferences` の label が一致している（IN3）。
- [ ] `essence-baseline` が成功し、案件フォルダに essence-baseline.json がある（IN2）。
- [ ] `essence-check --project <DIR>` の fail が 0 である（IN2）。
- [ ] シート・回答・記録がすべて案件フォルダにあり、plugin の中に書いたファイルが 0 件である（E3）。

### ゴールシークループ

1. 未達の `[ ]` を 1 つ選ぶ → 2. 下の局面カタログから、その未達に効く局面を選ぶ → 3. 実行する → 4. コマンドの出力で `[x]` を更新する → 全項目が `[x]` になるまで繰り返す。同じ未達が続くときは、値を合成せず、何が判断を変えるかを示して利用者に確かめる。

### 局面カタログ

順序は都度判断する。番号は参照用で、実行の順番を固定しない（ただし 2 の init は、案件フォルダへ書く局面より先に 1 回だけ行う）。PLUGIN_ROOT で `python3 scripts/build-flyer.py <command>` と実行する（各コマンドの意味は[runtime のコマンド一覧](../../references/runtime.md#コマンド一覧)）。

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

### ゴールシーク配線

周回の状態は案件フォルダの `<DIR>/goal-seek/` に置き、plugin の中へ書かない（E3）。init は既存 DIR を拒否するため、`<DIR>/goal-seek/` は局面 2 の init が成功した後にだけ作る。それより前の周回は会話の中で同じ項目を保持し、init の直後にまとめて書く。

- 上の「ゴール」の文を `original_goal` として `<DIR>/goal-seek/run-intake-flyer-goal-spec.json` へ書き、その SHA-256 を `<DIR>/goal-seek/run-intake-flyer-progress.json` の `original_goal_hash` に固定する。progress には完了チェックリストの各項目の状態と根拠（どのコマンドの出力か）も書く。
- 各周回の終わりに `<DIR>/goal-seek/run-intake-flyer-intermediate.jsonl` へ `original_goal`・`original_goal_hash`・`current_goal_snapshot`・`delta_from_original`・`merged_directive_for_next`・`drift_signal` を 1 行追記する（append-only）。次の周回は、直前の行の `merged_directive_for_next` と `original_goal` を読んでから局面を選ぶ。
- 記録には回答の値や個人情報を写さず、未達の項目と次の一手だけを書く（E3）。
- 完了は、チェックリストの全項目と `feedback_contract.criteria` の検査が通ったときだけとする。利用者の判断が要る未達は完了扱いにせず、何を確かめるかを残して止める。

### ゴールシーク検証

各周回の記録の後に次の検査を実行し、中間記録の欠落・ゴールの書き換え・ハッシュの不一致を止める（終了コード 0 を通過条件とする）。

```bash
python3 - "<DIR>/goal-seek/run-intake-flyer-goal-spec.json" "<DIR>/goal-seek/run-intake-flyer-intermediate.jsonl" <<'PY'
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

intake-residual の done が true、essence-baseline.json があり、essence-check の fail が 0 なら完了。既存紙面を直す案件（mode が revise）は[現物診断](../run-analyze-flyer/SKILL.md)へ、それ以外は[制作](../run-create-flyer/SKILL.md)へ渡す。後の段で目的や事実が変わったときは、承認記録を残してから局面 9 を通し直す。

---
name: run-intake-interview
description: ユーザーが言語化できない「何を入力し、何をどう出力してほしいか」を深掘って intent_contract と 5 軸ヒアリングシートを再現性高く埋めたいとき、run-skill-intake から phase 4 として呼ばれて sheet.md/sheet.json/interview.json を生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Edit
  - AskUserQuestion
kind: run
user-invocable: true
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
version: 0.1.1
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 5 軸シートと入力→出力 intent_contract 充足の停止条件が機械検証可能である——five_axes_complete=true、intent_contract.slot_status 全 slot filled=true、pending_probes=[]、validate-interview-json.py(interview.json の schema 準拠)と check-five-axes-coverage.py(sheet.md の 5 軸 coverage)双方が exit 0 で揃って初めて完了とみなされ、空欄や [?] や未充足 intent slot が PASS をすり抜けないこと。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: 抽象回答と個人情報の扱いが機構で担保される——abstract-answer-patterns.md 該当回答は abstract_answers[] に {axis,answer,reason} で印付けし needs_excavation=true を立てて最終確定せず Phase 5 に委ね、社名・個人名は interview.json 本文に直書きせず {{var_*}} へ変数化されていることが schema/script で検査できること。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: スキル全体が「ユーザーが言語化できない入力仕様/出力仕様の抽出・5 軸シート充足・現状手順(procedure)抽出・抽象フラグ付け・interview.json emit」というユーザ目的を過不足なく反映し、価値深掘り(Phase 5)・仮説検証(Phase 2)・要約(Phase 8)・3 軸確定(run-intake-kickoff)へ越境せず、to-be 設計(手順の最適化・理想化)を後段 build へ委ね、vocabulary_tier 固定と AskUserQuestion 1 問直列・intent probe 優先といった責務境界が目的に対し最適であること。
      verify_by: elegant-review
    - id: IN3
      loop_scope: inner
      text: 5 軸ヒアリング完了後に抽出した現状手順(procedure)が、mode=detailed のとき steps[] 各要素の action/input/output/tool/frequency を非空で持ち、mode=overview_fallback のとき difficulty_flag=true かつ overview(step_count_estimate/participants/frequency)が非空であることを ../../scripts/validate-procedure-completeness.py が検証し exit0 になる (goal-spec C1/C2)。
      verify_by: script
    - id: IN4
      loop_scope: inner
      text: handoff 対象の as-is フィールド(procedure.* と five_axes.rows[name=真の課題].content)に to-be 語彙(べきである/理想は/最適化/より良い方法/一般的には 等)が混入していないことを ../../scripts/validate-procedure-completeness.py の contamination check が検証し exit0 になる (goal-spec C7)。
      verify_by: script
    - id: OUT2
      loop_scope: outer
      text: procedure 軸で 2 連続の抽象判定/未回答(validate-answer-abstraction.py --axis procedure が exit3)となったとき常に overview_fallback へ切り替わり停止せず継続する決定論分岐であり、同一回答パターンに対し常に同じ経路が選ばれることを受入テストが確認する (goal-spec C2/C6)。
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: 『解決したい課題・問題』『現状の流れ・仕組み』『実行したいこと』が固有名詞・実例・頻度・関与者などの相手固有の具体性で記録され、一般論・平均的回答への置換や to-be 提案の混入が無いことを独立レビューが確認する (goal-spec C8)。
      verify_by: elegant-review
---

# run-intake-interview

## Purpose & Output Contract

intake セッションの Phase 4 担当。最優先で「何を入力し、何をどう出力してほしいか」を `intent_contract.input_spec` / `intent_contract.output_spec` に抽出し、未充足 slot は `probe-pattern-table.json` の固定 probe で手を差し伸べる。その後、ヒアリングシート `sheet.md` の空欄および `[?]` マーカーを **5 軸 (出力先 / 情報源 / 共有相手 / 真の課題 / ナレッジ資産) 優先順位**で `AskUserQuestion` により順次充足し、`interview.json` を emit する。出力先と情報源は `intent_contract.output_spec.sink` / `intent_contract.input_spec.sources` から派生する。本スキルは「入力→出力インテント抽出・5 軸シート充足・抽象回答フラグ付け・interview.json emit」に責務を絞り、価値深掘り (Phase 5 `purpose-excavator`)・仮説検証 (Phase 2)・要約 (Phase 8)・3 軸確定 (`run-intake-kickoff`) は行わない。`run-intake-kickoff` との境界は「kickoff=3 軸 (pattern/depth/pain)、interview=入力→出力 intent + 5 軸シート」で確定。

**入力**:
- `output/<hint>/profile.json` (`vocabulary_tier` = novice|intermediate|expert を含む。Phase 3 が確定)
- `output/<hint>/sheet.md` (空欄および `[?]` を含む 5 軸シート)
- `references/question-bank-pointer.md` 経由の質問雛形
- `../../references/probe-pattern-table.json` (intent slot 未充足時の固定 probe)
- `../../references/intent-contract.schema.json` (入力→出力インテント正本)
- `references/abstract-answer-patterns.md` (抽象回答検出規則)
- `references/five-axes-priority.md` (軸の処理順)

**出力**:
- `output/<hint>/sheet.md` (空欄を埋めた更新済シート。5 軸完了後に「現状手順 (procedure)」節を追記し、構造化した procedure ブロックを ```json フェンスで埋め込む)
- `output/<hint>/sheet.json` (`intake-final-schema.json#/properties/five_axes` 互換の `five_axes.rows` / `five_axes.pipeline`。procedure 節があれば `procedure` を additive に含む)
- `output/<hint>/interview.json` (`schemas/output.schema.json` 準拠。`filled_ratio` / `five_axes_complete` / `unresolved` / `needs_excavation` / `abstract_answers` / `five_axes` / `intent_contract` / `pending_probes` / `qa_log` を保持。5 軸完了後は現状手順 `procedure` (mode=detailed の `steps[]`、または mode=overview_fallback の `difficulty_flag`+`overview`) を additive に保持)

**完了条件**: 5 軸すべて非空 (`five_axes_complete=true`) + `intent_contract.slot_status` 全 slot `filled=true` + `pending_probes=[]` + `scripts/build-sheet-json.py` PASS + `../../scripts/build-intent.py --schema ../../references/intent-contract.schema.json` PASS + `scripts/validate-interview-json.py` PASS + `scripts/check-five-axes-coverage.py` PASS + 現状手順(procedure)抽出後に `../../scripts/validate-procedure-completeness.py --interview output/<hint>/interview.json` PASS (mode 別完全性 + as-is フィールドへの to-be 語彙非混入)。

## Key Rules

1. **入力→出力 intent を最優先**: 5 軸のうち出力先/情報源は推測で埋めず、`intent_contract.output_spec.sink` / `intent_contract.input_spec.sources` から派生する。
2. **5 軸シート充足まで**: 価値深掘り (excavation) / 仮説検証 / 要約 / 3 軸確定は越境しない。それぞれ Phase 5 / 2 / 8 / `run-intake-kickoff` の責務。
3. **AskUserQuestion 1 問ずつ**: 並列・束ね質問禁止。5 軸質問は `build-questions.py` が返す固定 3 択 + 自由入力を使う。intent probe は `probe-pattern-table.json` の選択肢数を正とし、3 択制限の例外とする。
4. **vocabulary_tier 固定**: `profile.json` の tier (novice|intermediate|expert) をセッション中変更しない。質問文は `build-questions.py` / `probe-pattern-table.json` が返した文面を正本とし、言い換える場合も `vocabulary-tiers.md` の固定対応表に限定する。
5. **抽象回答は intent slot へ最低限写像**: 「いい感じ」「効率化」だけで終えず、対象・素材・頻度・出力先・読者・粒度のいずれかを `normalized_answer` または `intent_contract` に写像する。写像不能なら `pending_probes` に戻し、価値深掘りは Phase 5 に委ねる。
6. **5 軸優先順位固定**: 出力先 → 情報源 → 共有相手 → 真の課題 → ナレッジ資産。ただし出力先/情報源は intent_contract 派生を優先する。
7. **個人情報の変数化**: 社名・個人名は `interview.json` 本文に転記せず、`{{var_*}}` で抽象化する。
8. **現状手順 (procedure) は 5 軸完了後**: 5 軸充足後に `references/question-plan.json` の `procedure_axis` を参照し、現状実施手順を順序付きステップ (各ステップ action/input/output/tool/frequency) で聞き取る。`scripts/validate-answer-abstraction.py --axis procedure` が **2 連続で exit3 (抽象/未回答)** となったら `overview_fallback` (difficulty_flag=true + 工程数目安/関与者/頻度の概略) へ決定論的に切り替え、停止せず最後まで継続する (goal-spec C2/C6)。procedure は 6 本目の軸であり、5 軸の優先順位・スキップ条件は変更しない。
9. **as-is 忠実・to-be 非混入**: 手順・課題・流れは相手が述べた as-is (現状の事実) を固有名詞・実例・頻度・関与者の具体性で記録し、一般化・要約・改善提案・最適化 (to-be) を混入させない。抽象的・平均的な回答には正規化せず追加質問で具体化を促す。ユーザーが自発的に述べた改善提案 (to-be) は handoff 対象の as-is フィールド (`procedure.*` / 真の課題 content) へ記録しない (別フィールドへの退避もしない)。to-be 語彙集は `references/to-be-vocabulary-patterns.md`、混入検出は `../../scripts/validate-procedure-completeness.py` の contamination check が担う (goal-spec C7/C8)。手順の最適化・理想化 (最高の手順の組み立て) は後段 build の責務でありヒアリングでは行わない。

## ゴールシーク実行

### ゴール (Goal)

`profile.json` と `sheet.md` を入力に、ユーザーが言語化できていない入力仕様/出力仕様が `intent_contract` に抽出され、`output/<hint>/sheet.md` の 5 軸空欄および `[?]` がすべて充足され、`output/<hint>/sheet.json` と `output/<hint>/interview.json` が生成され、`scripts/build-sheet-json.py` / `../../scripts/build-intent.py --schema ../../references/intent-contract.schema.json` / `scripts/validate-interview-json.py` / `scripts/check-five-axes-coverage.py` がすべて exit 0、`five_axes_complete=true`、`pending_probes=[]`、抽象回答は `abstract_answers[]` に印付け + `needs_excavation=true` で記録された状態になっている。

### 目的・背景 (Why)

5 軸シートが空欄のまま後続 phase (Phase 5 深掘り / `run-intake-visualize` / `run-intake-finalize`) に進むと、深掘り対象の特定と可視化の判断材料を欠き、再ヒアリングで手戻りする。固定手順では `profile.vocabulary_tier` 差・空欄分布・抽象回答頻度に脆く、未充足軸を都度埋めるゴールシークが必要。本スキルはあくまで「シート充足の機械検証可能化」に限定し、深掘り判断は `needs_excavation` フラグで Phase 5 に委ねる。

### 完了チェックリスト (Checklist)

- [ ] `profile.json` を読み `vocabulary_tier` をセッション開始時に確定し、以降変更していない
- [ ] `sheet.md` の空欄および `[?]` を 5 軸別に走査し未回答リストを生成済み
- [ ] `qa_log[]` から `../../scripts/build-intent.py --schema ../../references/intent-contract.schema.json` を実行し、未充足 slot があれば `pending_probes[]` の順に `probe-pattern-table.json` の文面を verbatim で 1 問ずつ聞いた
- [ ] `intent_contract.input_spec` / `intent_contract.output_spec` の 9 slot がすべて filled=true で、`pending_probes=[]`
- [ ] `five_axes.rows[name=出力先]` は `intent_contract.output_spec.sink`、`five_axes.rows[name=情報源]` は `intent_contract.input_spec.sources` から派生済み
- [ ] 5 軸優先順位 (出力先 → 情報源 → 共有相手 → 真の課題 → ナレッジ資産) で各軸を順に処理
- [ ] 各軸の質問は `scripts/build-questions.py` で Q-ID と順序を確定し、`references/question-bank-pointer.md` 経由で文面を解決済み
- [ ] `AskUserQuestion` を 1 問ずつ直列で発行 (3 択 + 自由入力、並列禁止)
- [ ] 回答を `sheet.md` に Edit で反映し、`[?]` を解消済み
- [ ] `references/abstract-answer-patterns.md` 該当回答は `abstract_answers[]` に `{axis, answer, reason}` で追記し `needs_excavation=true`
- [ ] 各質問/回答を `qa_log[]` に 5軸質問は `{qid, axis, question_text, selected_option, raw_answer, normalized_answer}`、intent probe は `{probe_id, target_slot, question_text, selected_option, raw_answer, normalized_answer}` で記録済み
- [ ] 5 軸すべて非空となり `five_axes_complete=true`、未解消があれば `unresolved[]` に列挙
- [ ] `output/<hint>/sheet.json` を `build-sheet-json.py` で生成済み
- [ ] `output/<hint>/interview.json` が `schemas/output.schema.json` 準拠 (`filled_ratio` / `five_axes_complete` / `unresolved` / `needs_excavation` / `abstract_answers` / `five_axes` / `intent_contract` / `pending_probes` / `qa_log` 全充足)
- [ ] `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/skills/run-intake-interview/scripts/validate-interview-json.py output/<hint>/interview.json` exit 0
- [ ] `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/skills/run-intake-interview/scripts/check-five-axes-coverage.py output/<hint>/sheet.md` exit 0
- [ ] 個人情報を `interview.json` 本文に直書きせず変数化済み
- [ ] 5 軸完了後に現状手順(procedure)を抽出済み: mode=detailed は `steps[]` 各要素の action/input/output/tool/frequency 非空、mode=overview_fallback は difficulty_flag=true + overview(step_count_estimate/participants/frequency)非空
- [ ] procedure 軸で 2 連続の抽象/未回答 (`validate-answer-abstraction.py --axis procedure` exit3) を検出したら overview_fallback へ切り替え、停止せず継続した
- [ ] handoff 対象 as-is フィールド (`procedure.*` / 真の課題 content) に to-be 語彙 (べきである/理想は/最適化 等) を混入させていない
- [ ] `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/validate-procedure-completeness.py --interview output/<hint>/interview.json` exit 0 (完全性 + 非混入)
- [ ] 責務外 (深掘り再質問・仮説検証・要約・3 軸確定・to-be 設計/手順最適化) に踏み込んでいない

### ゴールシークループ

固定手順ではなく、上記チェックリストを唯一の停止条件とする。`qa_log[]` を `../../scripts/build-intent.py` に通して `pending_probes[]` を確認 → 未充足 intent slot があれば `probe-pattern-table.json` 順に 1 問発行 → 9 slot 充足後、未充足軸を `five-axes-priority.md` 順で特定 → `build-questions.py` で depth/pattern/既記入軸から Q-ID と順序を決定論的に確定 → `question-bank-pointer.md` 経由で文面を解決 → `AskUserQuestion` で 1 問発行 → 回答を `sheet.md` に反映 → `abstract-answer-patterns.md` で抽象判定 → checklist 自己評価、を反復する (上限は `prompts/R1-main.md` Layer 4 の反復回数)。`workflow-manifest.json` の phase 順 P1-load-sheet → P2-normalize-intent → P3-fill-by-axis → P4-flag-abstract → P5-emit に従い、各 phase の `fatal_exit_codes` 検出時は即停止して未充足 slot/軸を stderr に列挙する。`run-intake-kickoff` で確定済の 3 軸 (pattern/depth/pain) は前提として読み取るのみ、再確定しない。

## 現状手順 (procedure) 軸の抽出

5 軸ヒアリング完了後に、`references/question-plan.json` の `procedure_axis` を参照して 6 本目の as-is procedure 軸を起動する (goal-spec C1/C2/C6/C7/C8)。

1. **detailed 経路 (既定)**: `procedure_axis.detailed_questions` を使い、ユーザーが実際に行っている手順を 1 ステップずつ順番に聞き取り、各ステップの `action`/`input`/`output`/`tool`/`frequency` を固有名詞・実例で埋める。回答ごとに `scripts/validate-answer-abstraction.py --patterns references/abstract-answer-patterns.md --answer <回答> --axis procedure` を実行する。
2. **overview_fallback 経路 (決定論切替)**: procedure 軸で **2 連続**して exit3 (抽象判定または未回答) となったら `procedure_axis.overview_fallback_questions` へ切り替え、`difficulty_flag=true` を立て `overview` (`step_count_estimate`/`participants`/`frequency`) の概略のみを収集して停止せず進める。閾値は `procedure_axis.fallback_threshold.consecutive_abstract_or_unanswered=2`。同一回答パターンには常に同じ経路が選ばれる (LLM の都度判断を排除)。
3. **interview.json への格納**: 収集した手順を `interview.json.procedure` に格納する (mode=detailed の `steps[]`、または mode=overview_fallback の `difficulty_flag`+`overview`)。`sheet.md` には「## 現状手順 (procedure)」節を追記し、同じ procedure ブロックを ```json フェンスで埋め込む (`build-sheet-json.py` が `sheet.json.procedure` へ additive に転記する)。
4. **as-is 忠実性 (平均回帰の防止)**: 抽象的・一般論的な回答が来ても正規化・要約せず、「具体的にはどのツール/頻度/関与者か」と追加質問で具体化を促す。ユーザーが自発的に述べた改善提案・理想手順 (to-be) は `procedure.*` や真の課題 content へ記録しない。to-be 語彙の混入は `../../scripts/validate-procedure-completeness.py` の contamination check (`references/to-be-vocabulary-patterns.md` 参照) が検出し、検出時は Phase 9 (`run-intake-finalize`) が Phase 4 へ差し戻す。
5. **完全性ゲート**: `../../scripts/validate-procedure-completeness.py --interview output/<hint>/interview.json` が exit0 (完全かつ contamination なし) になるまで反復する。完全性の判定ロジックは本スクリプトに一元化し、本 skill 内へ重複実装しない。

## Gotchas

1. **深掘りに踏み込まない**: 「なぜ?」を 3 回以上重ねたら Phase 5 (`purpose-excavator`) の領域。本 phase は 1 問で次軸へ進み `needs_excavation=true` を立てるのみ。
2. **抽象語の最終確定禁止**: 「効率化」「最適化」「いい感じに」をそのまま記録しない。`abstract_answers[]` に reason 付きで残し Phase 5 に委ねる。
3. **vocabulary_tier 変更禁止**: セッション中の tier 変更は回答品質低下と語彙混乱を招く。Phase 3 で固定した値を尊重する。
4. **kickoff との重複質問禁止**: pattern / depth / pain は `run-intake-kickoff` で確定済。本 phase で再質問するとユーザーに同意ループを誘発する。
5. **AskUserQuestion 並列発行禁止**: 認知負荷が高く回答品質が落ちる。必ず 1 問ずつ直列。
6. **validate スクリプト自動修正禁止**: FAIL 時は不足項目をユーザー提示し、LLM 判断で勝手に埋めない。

## Additional Resources

- `workflow-manifest.json` — P1-load-sheet → P2-normalize-intent → P3-fill-by-axis → P4-flag-abstract → P5-emit phase 定義・dependsOn・entryHook/exitHook・fatal_exit_codes
- `prompts/R1-main.md` — R1-five-axes-sheet-fill 7 層プロンプト (Layer 1-7)
- `schemas/output.schema.json` — `interview.json` 正本スキーマ (`filled_ratio` / `five_axes_complete` / `unresolved` / `needs_excavation` / `abstract_answers`)
- `references/five-axes-priority.md` — 5 軸の処理順序とスキップ条件
- `references/abstract-answer-patterns.md` — `needs_excavation` を立てる判定基準
- `../../references/intent-contract.schema.json` — 入力→出力 intent の正本 schema
- `../../references/probe-pattern-table.json` — intent slot 未充足時に聞く固定 probe
- `references/question-bank-pointer.md` — 旧 aggregator `../../references/question-bank.md` への参照ガイド
- `references/resource-map.yaml` — machine-readable リソース一覧
- `scripts/validate-interview-json.py` — `interview.json` の schema validate (procedure ブロックを含む)
- `scripts/check-five-axes-coverage.py` — 5 軸 coverage の機械検証
- `references/question-plan.json#procedure_axis` — 現状手順(procedure)軸の質問列と overview_fallback 閾値の正本
- `references/to-be-vocabulary-patterns.md` — as-is/to-be 分離の語彙正本 (contamination 判定)
- `../../scripts/validate-procedure-completeness.py` — procedure ブロックの完全性 + as-is フィールドへの to-be 語彙混入の決定論判定 (C02)
- `../../scripts/build-intent.py` — `qa_log` から `intent_contract` と `pending_probes` を決定論的に生成
- 前後 phase: `run-intake-kickoff` (3 軸 pattern/depth/pain), `purpose-excavator` (Phase 5 深掘り), `run-intake-visualize`, `run-intake-finalize`

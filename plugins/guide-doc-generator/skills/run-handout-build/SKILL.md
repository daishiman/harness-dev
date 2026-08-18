---
name: run-handout-build
description: レクチャー資料や導入ガイドの handout を作りたいとき、題材のヒアリングから外部依存ゼロの単一 HTML 資料と同梱物一式を生成したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/guide-doc-generator/component-inventory.json#C01
kind: run
prefix: run
hierarchy: L1
user-invocable: true
output_language: ja
argument-hint: "[--config <handout-config.json>] [--out-dir <dir>] [--assets-src <dir>]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill, Agent]
depends_on: [C03, C04, C05, C11, C12, C13, C14, C15, C16, C17, C18, C19, C21, C22, C23]
script_refs:
  - ../../scripts/validate-handout-config.py
  - ../../scripts/resolve-handout-preset.py
  - ../../scripts/embed-assets.py
  - ../../scripts/render-diagram-svg.py
  - ../../scripts/build-icon-sprite.py
  - ../../scripts/srg-image-bridge.py
  - ../../scripts/render-handout.py
  - ../../scripts/verify-handout-selfcontained.py
  - ../../scripts/verify-handout-a11y-print.py
  - ../../scripts/verify-handout-language.py
  - ../../scripts/verify-handout-narrative.py
  - ../../scripts/route-handout-output.py
schema_refs:
  - ../../schemas/handout-config.schema.json
command_refs:
  - ../../commands/handout-verify.md
agent_refs:
  - ../../agents/handout-content-architect.md
skill_refs:
  - assign-handout-readability-evaluator
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-design.md
  - prompts/R3-render.md
  - prompts/R4-verify.md
  - prompts/R5-refine.md
  - prompts/R-design-config.md
responsibilities:
  - id: R1-elicit
    prompt_required: true
    summary: "R21 で必須化した項目 (target_tasks / focus_theme / attainment_level / must_remember と no_need_to_remember の対) と読み手・前提知識・用途・本質的課題・背景・ゴール・素材・日付・出力先を確定する。既定の draft_first では素材から推定できる項目を推定で埋め、埋められない項目だけを 1 ラウンドにまとめて聞き、回答を待たずに第1稿を出す。推定値は生成レポートで仮置きとして開示する。粒度 (detail_level / evidence_depth) は既定を提示して上書きの要否だけを聞く。検証済みの構成データを直接渡された場合はヒアリングを省く非対話経路も受け付ける"
  - id: R2-design
    prompt_required: true
    summary: "用途に対応するプリセットを resolve-handout-preset.py (C23) で解決し、構成データ設計を handout-content-architect (C05) へ委譲して、部品選択と lead-line・判断軸・セクションゴール・用語言い換え宣言を含む構成データを validate-handout-config.py (C12) で確定する"
  - id: R3-render
    prompt_required: true
    summary: "検証済み構成データからアセット埋め込み・図解・アイコン sprite・レンダリングを決定論 script 列で実行し単一 HTML を生成する"
  - id: R4-verify
    prompt_required: true
    summary: "検証ゲートを /handout-verify (C09) 経由で実行して集約結果を受け取り、route-handout-output.py (C19) で出力先ルーティングまで通し、README.md を書いて生成レポートを返す。集約規則は C09 の CR-GATE-AGG が単一正本でここでは再実装も再解釈もしない"
  - id: R5-refine
    prompt_required: true
    summary: "第1稿を見た利用者の指摘を差分として受け取り、指された箇所だけを作り直す。ヒアリングはやり直さず、覆った仮置き項目だけを更新して該当責務へ戻す。粒度を上げるのは指された箇所だけで、資料全体は上げない。第1稿で回さなかった工程 (config/handout-visual-policy.json#draft_first.skipped_in_draft の挿絵生成と可読性レビュー) はこの周回から回す。生成済み HTML を直接編集せず、必ず R3-render の決定論経路で作り直す (OUT2 の再現一致を保つため)"
hearing_required_items_r21:
  note: "R21 (goal-spec C47 / C54 / C57 / C58) で必須化したヒアリング項目。plugin 全体で唯一の項目定義であり、handout-content-architect (C05) は hearing_result として受け取る側で独自に項目を増やさない。値の形式と必須性の機械検査は validate-handout-config.py (C12) が持つ"
  items:
    - field: target_tasks
      question_ja: "この資料を読んだ人が、自分の仕事で具体的に何をできるようになりたいですか (例: 車両収支の集計を自動化する)"
      required: true
      min_count: 1
      checked_by: "C12 E-TARGET-TASKS-EMPTY / E-SECTION-UNTIED-TASK"
    - field: focus_theme
      question_ja: "冒頭で扱う主題を 1 つ (多くても 2 つ) に絞るとしたら何ですか"
      required: true
      min_count: 1
      max_count: 2
      checked_by: "C12 E-FOCUS-THEME"
    - field: attainment_level
      question_ja: "読み終えたときの到達点はどこですか (概要が分かる / 操作できる / 自分で再現できる / 自分でスキルを書ける)"
      required: true
      checked_by: "C12 E-ATTAINMENT-OVERRUN / E-ATTAINMENT-UNREACHED"
    - field: must_remember
      question_ja: "この場で覚えていただきたいことを 2 つまで挙げるとしたら何ですか"
      required: true
      max_count: 2
      paired_with: no_need_to_remember
      checked_by: "C12 E-REMEMBER-PAIR / E-REMEMBER-MAX"
    - field: no_need_to_remember
      question_ja: "逆に、覚えなくてよい (その場で調べれば足りる) のはどこまでですか"
      required: true
      paired_with: must_remember
      checked_by: "C12 E-REMEMBER-PAIR"
hearing_required_items_r22:
  note: "R22 (goal-spec C64) の粒度ヒアリング。R21 の必須項目と別ブロックに置く。既定値が常に存在するため必須回答にせず、無回答でも停止しない"
  elicitation_form: "doc_type 確定後に resolve-handout-preset.py (C23) の granularity_defaults から既定値を引き、『この資料は <既定の説明> で作ります。変更しますか』の 1 問として提示する。互いに独立だが利用者には 1 つの関心事として現れるため、別々に聞かず 1 問へまとめる"
  items:
    - field: detail_level
      question_ja: "説明の詳しさはどのくらいにしますか (大まかに要点だけ / 標準 / 詳しく細かく)"
      required: false
      default_source: "C23 granularity_defaults[doc_type].detail_level"
      on_no_answer: "既定値を採用し provenance.detail_level_source='preset-default' を立てて進む。再質問も停止もしない"
      checked_by: "C12 (enum 妥当性) / C22 NAR-09 (実態との一致)"
    - field: evidence_depth
      question_ja: "根拠や出典はどこまで書きますか (書かない / 参照先を示す / 出典を明記する)"
      required: false
      default_source: "C23 granularity_defaults[doc_type].evidence_depth"
      on_no_answer: "既定値を採用し provenance.evidence_depth_source='preset-default' を立てて進む。再質問も停止もしない"
      checked_by: "C12 (enum 妥当性) / C22 NAR-10 (実態との一致)"
build_mode:
  note: "第1稿の出し方。速さは『質問を減らすこと』ではなく『確定を待たずに一度出すこと』で得る。数値 (質問ラウンド上限・第1稿の粒度・第1稿の目標形) の正本は config/handout-visual-policy.json の draft_first であり、ここへ書き写さない"
  default: draft_first
  modes:
    - id: draft_first
      when: "既定。素材か題材の説明が手元にある全ての場合"
      rule: "素材から推定できる項目は推定で埋め、埋められない項目だけを 1 ラウンドにまとめて聞く。回答を待たずに第1稿を出し、利用者が現物を見てから直す"
      inferred_values: "推定で埋めた項目は生成レポートへ『仮置き』の一覧として出す。構成データ側には印を持たせない (provenance は C12 の閉じた語彙であり推定の別を持つ層ではない)"
      skipped_in_first_draft: "config/handout-visual-policy.json#draft_first.skipped_in_draft を正本とする。決定論ゲートは第1稿でも外さない"
    - id: config_given
      when: "検証済みの構成データを直接渡された場合 (逆抽出からの再生成・自動実行)"
      rule: "ヒアリングも第1稿も持たず設計以降へ進む"
build_stage:
  note: "完了条件を 2 段に割る。draft は『どこまで作るか』を決める軸であって、品質を落とす軸ではない。第1稿で外すのは意味レビュー (C03) と挿絵委譲 (C13) だけで、決定論ゲートは 1 つも外さない (数百ミリ秒で終わるうえ、外すと『開けない HTML』を渡すことになる)。外す工程の正本は config/handout-visual-policy.json#draft_first.skipped_in_draft。速さは検証を薄めることでなく、確定と意味レビューを待たずに現物を一度渡すことで得る"
  default: draft
  stages:
    - id: draft
      checklist_scope: "## 完了チェックリスト の『第1稿の完了条件』(D1-D9)"
      criteria_scope: [IN1, OUT1, OUT2]
      max_loops: 2
      loop_rule: "回してよいのは決定論ゲートを exit0 へ戻す修復だけ。意味品質を上げるための周回は draft では回さない (利用者が現物を見るほうが速い)"
      exit: "D1-D9 が揃ったら completed を宣言せず、成果物のパス・仮置き項目・第1稿で回さなかった工程を提示して停止する"
    - id: release
      checklist_scope: "『第1稿の完了条件』(D1-D9) + 『仕上げの完了条件』(F1-F4)"
      criteria_scope: [IN1, OUT1, OUT2]
      max_loops: 5
      entry: "利用者の指摘を受け取ってから入る。指摘なしに自動で昇格しない"
      loop_rule: "R5-refine の差分修正として回す。ヒアリングはやり直さない"
visual_policy_ref: ../../config/handout-visual-policy.json
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
completeness_exempt:
  - "manifest: goal_seek.engine=inline が未達 checklist から実行局面を都度選ぶため、固定 phase の workflow-manifest.json は適用外。停止条件と配線は本文 ## ゴールシーク実行 を正本とする。"
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "構成データが validate-handout-config.py を通り、各セクションの lead-line と判断軸の一文・日付フィールド・用語言い換え宣言の欠落が 0 件で確定する"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "生成した単一 HTML 資料 1 個が外部依存ゼロで開き、自己完結性・a11y・印刷・言語規約・日付表記のゲートが全て exit0 になり、出力先に資料 HTML と構成データと素材と README が揃うことを受入テストが確認する"
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: "出力先へ同梱された構成データから 2 回生成したとき出力 HTML がバイト一致し、決定論レンダリングの再現性が保たれることを受入テストが確認する"
      verify_by: test
---

# run-handout-build

## Purpose & Output Contract

- 入力: 題材と素材、または検証済みの構成データ。
- 出力: 出力ディレクトリ 1 個。同梱物と writer は `handout.html` (writer C11) / `handout-config.json` と `assets/` (writer C19) / `README.md` (writer 本 skill) であり、writer 割り当ての正本は C19 の `bundle_writers`。
- 生成レポート: 適用部品・埋め込みサイズ・warning・ゲート結果を返す。ゲート結果は `/handout-verify` が返した summary.json の verdict と gates をそのまま載せる。
- 完了条件: 2 段ある (frontmatter `build_stage`)。**第1稿 (draft)** = ゲート集約の verdict が pass で、同梱物が既定の命名規則の出力ディレクトリに揃った状態。ここで利用者へ現物を渡して止まる。**仕上げ (release)** = 利用者の指摘を反映し、意味レビューと挿絵まで回した状態。

HTML の組み立て自体は決定論 script へ委譲し LLM で書かない。読みやすさの最終判定は assign-handout-readability-evaluator (C03) へ委譲し、本 skill は返った verdict を受けて資料を直す側に回る。

## ヒアリングと非対話経路

frontmatter の `hearing_required_items_r21` が plugin 全体で唯一の項目定義である。ここに宣言した項目を確定してから設計へ進み、確定していない項目は聞き直す。項目の形式と必須性を最終的に落とすのは validate-handout-config.py であって本文の散文ではない。

提示順 (demo_first / explain_first) は質問しない。既に取得している prior_knowledge_level から C12 の CR-PRESENTATION-ORDER が決定論導出する。利用者が自発的に述べたときだけ、その値を明示上書きとして構成データへ書く。

粒度の項目は frontmatter の `hearing_required_items_r22` にある。既定値は resolve-handout-preset.py の granularity_defaults から doc_type を鍵に引き、既定を提示して上書きの要否だけを 1 問で聞く。無回答なら既定を採用して進み、停止しない。

検証済みの構成データを直接渡された場合はヒアリングを省き、非対話経路として設計以降へ進む。逆抽出 (C08) からの再生成と自動実行をこの経路で塞がない。

## 構成データの設計と検証

用途プリセットは resolve-handout-preset.py で解決し、用途語彙とプリセット内容を本 skill が持たない。解決した preset とヒアリング結果と素材の論理名を handout-content-architect (C05) へ渡して構成データ設計を委譲する。C05 が `status=blocked` を返したら、欠落項目をヒアリングへ差し戻してから再委譲する。

C05 が書いた構成データは validate-handout-config.py で検証し、`--normalize` の出力を以後の唯一の入力にする。正規化済み構成データには読み手・前提知識・用途が入っている必要がある。C03 が委譲入力の `reader_profile` をこれらから組み立てるため、欠けたままでは意味レビューへ進めない。

## 単一 HTML の決定論生成

素材の data URI 化 (embed-assets.py)、概念図解の inline SVG 生成 (render-diagram-svg.py)、使用アイコンだけの symbol 生成 (build-icon-sprite.py)、挿絵の生成委譲 (srg-image-bridge.py)、単一 HTML のレンダリング (render-handout.py) を決定論 script 列として実行する。本 skill はこれらの引数を組み立てるだけで、HTML の断片を自分で書かない。

挿絵の委譲は exit 0 が「生成した」と「skip した」の両方を含むため、exit code でなく stdout の `status` を読む。`status=skipped` のときは `skip_reason` (`srg-absent` = 委譲先の SRG 実体が解決できない / `runtime-absent` = node か codex が無い) をそのまま生成レポートの warning へ転記し、画像なしで先へ進む。skip を黙って成功へ畳まない — 挿絵が無いまま出来上がったことが読み手に見えなくなるためである。

## ゲート集約と出力配置

検証ゲートは `/handout-verify` (C09) を `--json-report` つきで起動して実行し、返った summary.json の verdict と各ゲート面の状態をそのまま受け取る。状態分類と全体 verdict の判定規則は C09 の CR-GATE-AGG が単一正本であり、本 skill では再実装も再解釈もしない。verdict が pass 以外なら該当箇所を直して再実行する。not-run を「通った」と読み替える判断を本 skill 側に持たない。

出力先ルーティングは route-handout-output.py (C19) へ `--place-config` と `--assets-src` を渡して実行する。構成データと素材原本の複製は C19 に行わせ、ディレクトリ名の組み立ても C19 の責務である。C19 が返した出力ディレクトリ直下へ `README.md` を書くのは本 skill の責務で、節は原題・目的・適用プリセット・同梱物一覧・各同梱物の使い方とする。

## 読みやすさレビューの委譲

**委譲するのは release 段だけである** (`draft_first.skipped_in_draft.readability_review`)。第1稿は利用者本人が現物を読むため、レビュアーを挟むより速くて正確な判定が既に得られている。ここを draft へ前倒しすると、利用者が一度も見ていない資料の読みやすさを推測で詰める周回に時間を使うことになる。

release 段でゲートの verdict が pass になった資料について assign-handout-readability-evaluator (C03) へ 1 回委譲する。C03 は verdict を無加工で返し、再レビューの起動と打ち切りは本 skill のゴールシークだけが持つ。

- `status=blocked` は verdict を伴わない。pass とも fail とも読まず、ゲート修復へ戻してから委譲し直す。
- verdict の決め方はレビュアー (C06) 側の規則であり、本 skill で再判定しない。`suggestion` は提案であって適用指示ではなく、どう直すかは本 skill が決める。
- 戻り値の項目が欠けていたら、その資料は判定が揃っていないものとして再委譲する。欠落を本 skill が補完しない。
- 委譲する文脈に、設計意図・ヒアリングの生ログ・参照 HTML の文面・何周目の loop か・過去の findings を含めない。含めた時点で独立 context の価値が失われる。

## ゴールシーク実行

### ゴール (Goal)

題材のヒアリングから構成データを確定し、外部依存ゼロの単一 HTML 資料 1 個と同梱物一式が既定の命名規則で出力され、自己完結性・a11y・印刷・言語規約・日付表記の全ゲートが exit0 になった状態。

### 目的・背景 (Why)

初心者・非エンジニア向けの資料は毎回ゼロから手書きされ、部品もデザイン言語も資産として残らない。構成データ駆動へ移せば反復配布できるテンプレートになる。

### 完了チェックリスト

分類の基準は「利用者が現物を見るまでに要るか」の一点であり、重要度ではない。F へ回した項目は品質を捨てたのではなく、**現物が出てから効くもの**を第1稿の待ち時間から外しただけである。

#### 第1稿の完了条件 (D1-D9・`build_stage: draft`)

- [ ] D1: `never_inferred_fields` (`doc_type` / `out_dir`) が確定し、他の `hearing_required_items_r21` / `_r22` は 1 ラウンドで聞くか素材から推定で埋めた (回答を待たずに進む。非対話経路では検証済み構成データがその代わりを満たす)
- [ ] D2: 第1稿を `draft_first.first_draft_detail_level` の粒度で出した (全体を詳細で作ってから削らない)
- [ ] D3: 構成データが validate-handout-config.py を exit0 で通っている
- [ ] D4: 図解密度と文字量の警告 (`W-VISUAL-ABSENT` / `W-DIAGRAM-FEW` / `W-TEXT-HEAVY` / `W-TEXT-RUN` / `W-COPY-LONG`) が 0 件である
- [ ] D5: 層の切り分けの警告 (`W-DETAIL-ABSENT` / `W-LAYER-ORDER` / `W-DETAIL-FLOWLESS`) が 0 件である (要点層を先に、各項目の手順・流れを持つ詳細層を後に置いた)
- [ ] D6: 冒頭の置き方の警告 (`W-HERO-LONG` / `W-OPENS-PROSE`) が 0 件である (目的・背景・ゴールを 1 行の宣言に留め、中身はカードと図解へ移した)
- [ ] D7: 単一 HTML が決定論 script 列で生成されている
- [ ] D8: `/handout-verify` の集約 verdict が pass である
- [ ] D9: 出力先へ同梱物が揃い `README.md` を書き、生成レポート (適用部品・埋め込みサイズ・warning・ゲート結果・**仮置き項目**・載せなかった項目・**第1稿で回さなかった工程**) を返した

D4-D6 を第1稿に残すのは速さと衝突しないためである。いずれも C12 が決定論で数える警告であって周回を要さず、しかもこれが 0 でない資料は「図が無く文章が長い」= 読み手が読まない状態そのものになる。第1稿の目的は読める物を早く渡すことであり、読めない物を早く渡すことではない。

#### 仕上げの完了条件 (F1-F4・`build_stage: release`)

- [ ] F1: 生成レポートで開示した仮置き項目を利用者が確認し、覆った項目を R5-refine で反映した
- [ ] F2: `draft_first.skipped_in_draft` の工程 (挿絵の生成委譲 C13) を回した
- [ ] F3: C03 から回収した verdict が PASS で、指摘に対する修正が資料へ反映されている
- [ ] F4: 粒度を上げたのは利用者が指した箇所だけで、他は `first_draft_detail_level` のままである

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。周回上限は `goal_seek.max_loops` の一本値でなく **`build_stage.stages[].max_loops` で段ごとに持つ**。

- **draft (既定・上限 2 周)**: 未達として拾うのは D1-D9 だけで、F1-F4 は未達に数えない。回してよいのは決定論ゲートを exit0 へ戻す修復に限る。「もっと良くできる」は draft の周回理由にならない — その判断は利用者が現物を見て下すほうが速く、正確である。
- **draft の出口**: D1-D9 が揃ったら completed を宣言せず停止し、(1) 出力ディレクトリのパス、(2) 生成レポートの仮置き項目、(3) `skipped_in_draft` により回さなかった工程、(4) 指摘の受け取り先が R5-refine であること、を提示する。**第1稿は速い完了ではなく、未完了だが読める状態である。**
- **release (上限 5 周)**: 利用者の指摘を受け取ってから入る。指摘なしに自動昇格しない。D1-D9 は draft で確定済みとして再取得せず、F1-F4 と、指摘で壊れた D 項目だけを回す。

各周回で inner criterion を検証し、完了後は outer criterion を最大 `feedback_contract.max_iterations=3` 周で評価する。IN1 / OUT1 / OUT2 はいずれも決定論検証であり draft でも省かない (省くと開けない HTML を渡すことになる)。

### ゴールシーク配線

- 元のゴールを `eval-log/guide-doc-generator/run-handout-build-goal-spec.json` へ、各 checklist の status と evidence を `eval-log/guide-doc-generator/run-handout-build-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `eval-log/guide-doc-generator/run-handout-build-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 上限周回に到達しても未達が残れば完了扱いにせず、progress と blocker を親へ handoff する。completed を宣言できるのは **release 段で D1-D9 + F1-F4 と `feedback_contract.criteria` が全て PASS のとき**だけである。draft 段の停止は完了ではなく引き渡しであり、progress には未達として F1-F4 を残す。
- progress には各 checklist の status と併せて現在の `build_stage` を記録する。draft の停止を「全項目 PASS」と書かない — 記録が完了に見えると、繰り越した F1-F4 が回収されないまま積み上がる。

### ゴールシーク検証

各周回後に次を実行し、中間成果物の欠落と goal drift と hash 不一致を fail-closed にする。

```bash
python3 - "eval-log/guide-doc-generator/run-handout-build-goal-spec.json" "eval-log/guide-doc-generator/run-handout-build-intermediate.jsonl" <<'PY'
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

## Criteria acceptance

- `criteria:IN1`: validate-handout-config.py が exit0 で、lead-line と判断軸の一文・日付フィールド・用語言い換え宣言の欠落が 0 件である。
- `criteria:OUT1`: 生成した単一 HTML が外部依存ゼロで開き、検証ゲートが全て exit0 になり、出力先に資料 HTML と構成データと素材と README が揃うことを受入テストが確認する。
- `criteria:OUT2`: 同梱された構成データからの再生成で出力 HTML がバイト一致することを受入テストが確認する。

## Gotchas

- ゲート結果を自分で数え直さない。集約は C09 の責務であり、本 skill が持つのは受け取った verdict の報告と、pass でないときの修正だけである。
- 出力ディレクトリ名を自前で組み立てない。日付とディレクトリ名の対応は C19 だけが知っている。
- 対話は既定経路であって唯一経路ではない。自動実行と逆抽出からの再生成を対話で塞がない。
- 部品 id と用途語彙と粒度の値域を本文へ書き写さない。正本はそれぞれ config のカタログ・用途語彙・構成データスキーマにある。
- 図解密度と文字量の警告を「warning だから無視してよい」と読まない。exit code を 0 に保つのは既存の構成データを壊さないための層の分け方であって、完了条件を緩める根拠ではない。強制はこの完了チェックリストが持つ。
- 長い文章で埋めて「情報は漏らしていない」と正当化しない。読まれない資料は情報を伝えていない。
- 素材の項目を全部載せようとしない。漏れなさは目標ではなく、要点に絞ることが目標である (`config/handout-visual-policy.json#content_selection`)。載せなかった項目は生成レポートで明示し、黙って落とさない。
- 全項目を残すために付録へ流し込まない。付録は網羅欲の逃がし先ではない。
- 要点だけで終わらせない。読み手は自分の知っている手順と並べて初めて「今の何がどう変わるのか」を掴む。各項目の大事な手順・流れを詳細層へ置く (`config/handout-visual-policy.json#layering`)。
- 冒頭の目的・背景・ゴールを段落で書かない。読み手はそこで「自分に関係があるか」を決める。宣言は 1 行に留め、中身はカードと図解へ移す (`config/handout-visual-policy.json#opening`)。
- 節を散文で始めない。言いたいことは `lead_line` が 1 行で担い、その直後は形 (図解・カード・表)、TEXT はその後の補足 1 本。
- 逆に、詳細層を網羅の場にしない。判断の分かれ目になる工程だけを、手順の形で残す。全工程を散文で書き写すと要点層より読みにくい塊が後半に生まれる。
- C03 の verdict を要約しない。`location` の逐語引用を落とすと修正箇所が当て推量になる。
- 第1稿を渡す前に完璧を狙わない。利用者が見ていない資料に対する「まだ良くできる」は推測であり、その推測を潰す周回が待ち時間の主因になる。D1-D9 が揃った時点で必ず一度渡す。
- draft の停止を completed と報告しない。F1-F4 は繰り越しであって免除ではなく、「全部通りました」と報告した瞬間に回収されなくなる。停止時は必ず未回収の工程を名指しする。
- 速さのために決定論ゲートや D4-D6 の警告を外さない。これらは数百ミリ秒で終わるため待ち時間の原因ではなく、外すと「開けない HTML」や「図が無く文章が長い資料」を第1稿として渡すことになる。第1稿で外してよいのは `draft_first.skipped_in_draft` に挙がった 2 工程だけである。

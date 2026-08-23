---
name: run-handout-build
description: レクチャー資料や導入ガイドの handout を作りたいとき、題材のヒアリングから外部依存ゼロの単一 HTML 資料と同梱物一式を生成したいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugin-plans/guide-doc-generator/component-inventory.json#C01
kind: run
effect: local-artifact
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
  - prompts/R2a-design-config.md
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
    summary: "第1稿を見た利用者の指摘を差分として受け取り、指された箇所だけを作り直す。ヒアリングはやり直さず、覆った仮置き項目だけを更新して該当責務へ戻す。粒度を上げるのは指された箇所だけで、資料全体は上げない。第1稿で回さなかった工程 (config/handout-visual-policy.json#draft_first.skipped_in_draft の可読性レビュー) はこの周回から回す。生成済み HTML を直接編集せず、必ず R3-render の決定論経路で作り直す (OUT2 の再現一致を保つため)"
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
  loop_ceiling: "周回上限は段ごとに持たない。goal_seek.max_loops (正本: component-inventory.json#C01) が plugin 全体で唯一の暴走止めであり、draft も release もこの 1 個の下で回る。段ごとの違いは『何のために回してよいか』であって回してよい回数ではないため、その違いは各段の loop_rule が持つ。上限を段ごとに分けると数が合成され (段の上限 × criteria の反復上限)、最悪何周するのかを誰も言えなくなる"
  note: "完了条件を 2 段に割る。draft は『どこまで作るか』を決める軸であって、品質を落とす軸ではない。第1稿で外すのは意味レビュー (C03) だけで、決定論ゲートは 1 つも外さない (数百ミリ秒で終わるうえ、外すと『開けない HTML』を渡すことになる)。挿絵委譲 (C21) も外さない — R25 (goal-spec C69) で第1稿から回すと決めており、min_images_per_main_section が level=error (E-IMAGE-ABSENT) である以上、外せば第1稿が G1 を通らないため速さと引き換えにできる工程ではない。外す工程の正本は config/handout-visual-policy.json#draft_first.skipped_in_draft。速さは検証を薄めることでなく、確定と意味レビューを待たずに現物を一度渡すことで得る"
  default: draft
  stages:
    - id: draft
      checklist_scope: "## 完了チェックリスト の G1-G3、各判定の draft 行"
      criteria_scope: [IN1, OUT1, OUT2]
      loop_rule: "回してよいのは決定論ゲートを exit0 へ戻す修復だけ。意味品質を上げるための周回は draft では回さない (利用者が現物を見るほうが速い)"
      exit: "G1-G3 の draft 行が揃ったら completed を宣言せず、成果物のパス・仮置き項目・第1稿で回さなかった工程を提示して停止する"
    - id: release
      checklist_scope: "## 完了チェックリスト の G1-G3、各判定の draft 行 + release 行"
      criteria_scope: [IN1, OUT1, OUT2]
      entry: "利用者の指摘を受け取ってから入る。指摘なしに自動で昇格しない"
      loop_rule: "R5-refine の差分修正として回す。ヒアリングはやり直さない"
visual_policy_ref: ../../config/handout-visual-policy.json
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: subagent
  max_loops: 5
completeness_exempt:
  - "manifest: goal_seek.engine=inline が未達 checklist から実行局面を都度選ぶため、固定 phase の workflow-manifest.json は適用外。停止条件と配線は本文 ## ゴールシーク実行 を正本とする。"
feedback_contract:
  activation_state: semantic_evaluator_started
  iteration_note: "反復上限をここに持たない。criteria の検証はゴールシーク 1 周につき 1 回であり、周回の上限は goal_seek.max_loops が単独で持つ。IN1 / OUT1 / OUT2 は決定論検証なので、資料を直さずに再評価しても結果は変わらない — 結果を変える修復こそがゴールシークの 1 周であり、独立した反復予算を置くとその 1 周を二重に数えることになる"
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
    - id: OUT3
      loop_scope: outer
      text: "題材と素材だけを与えた実起動で、質問ラウンドが draft_first.max_question_rounds_before_first_draft 回以内に収まり、G1-G3 の draft 行が揃った時点で completed を宣言せず停止して成果物のパス・仮置き項目・回さなかった工程を提示すること、および C03 委譲が draft 段で起動しておらず、挿絵生成 (C21) は R25 (goal-spec C69) により draft 段でも起動していることを実走の痕跡で確認する"
      verify_by: live-trial
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

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-handout-build

## Purpose & Output Contract

- 入力: 題材と素材、または検証済みの構成データ。
- 出力: 出力ディレクトリ 1 個。同梱物と writer は `handout.html` (writer C11) / `handout-config.json` と `assets/` (writer C19) / `README.md` (writer 本 skill) であり、writer 割り当ての正本は C19 の `bundle_writers`。
- 生成レポート: 適用部品・埋め込みサイズ・warning・ゲート結果を返す。ゲート結果は `/handout-verify` が返した summary.json の verdict と gates をそのまま載せる。
- 完了条件: 2 段ある (frontmatter `build_stage`)。**第1稿 (draft)** = ゲート集約の verdict が pass で、同梱物が既定の命名規則の出力ディレクトリに揃った状態。ここで利用者へ現物を渡して止まる。**仕上げ (release)** = 利用者の指摘を反映し、意味レビューと挿絵まで回した状態。

HTML の組み立て自体は決定論 script へ委譲し LLM で書かない。読みやすさの最終判定は assign-handout-readability-evaluator (C03) へ委譲し、本 skill は返った verdict を受けて資料を直す側に回る。release の visual-fit は alt 文ではなく埋め込み画像の実画素を全件開き、節内容と画像計画への一致を確認して初めて PASS にできる。

## ヒアリングと非対話経路

frontmatter の `hearing_required_items_r21` が plugin 全体で唯一の項目定義である。ここに宣言した項目を確定してから設計へ進み、確定していない項目は聞き直す。項目の形式と必須性を最終的に落とすのは validate-handout-config.py であって本文の散文ではない。

提示順 (demo_first / explain_first) は質問しない。既に取得している prior_knowledge_level から C12 の CR-PRESENTATION-ORDER が決定論導出する。利用者が自発的に述べたときだけ、その値を明示上書きとして構成データへ書く。

粒度の項目は frontmatter の `hearing_required_items_r22` にある。既定値は resolve-handout-preset.py の granularity_defaults から doc_type を鍵に引き、既定を提示して上書きの要否だけを 1 問で聞く。無回答なら既定を採用して進み、停止しない。

検証済みの構成データを直接渡された場合はヒアリングを省き、非対話経路として設計以降へ進む。逆抽出 (C08) からの再生成と自動実行をこの経路で塞がない。

## 構成データの設計と検証

用途プリセットは resolve-handout-preset.py で解決し、用途語彙とプリセット内容を本 skill が持たない。解決した preset とヒアリング結果と素材の論理名を handout-content-architect (C05) へ渡して構成データ設計を委譲する。C05 が `status=blocked` を返したら、欠落項目をヒアリングへ差し戻してから再委譲する。

資料全体に効く 3 つの指定は C05 へ渡す前にここで確定させる (節ごとの設計では決まらないため)。(a) 文章量は `detail_level` で選ぶ — 「もっと詳しく / 要点だけでいい」は書き足しや削りではなく水準の選択で、節あたりの予算は `assets/tokens/<theme>.json#text_limits.section_body_chars_by_detail_level` が正本 (NAR-09 が上下双方を検査する)。(b) 一覧で最初に目に入る 1 枚を `thumbnail_asset_id` に指定する (素材があるなら未指定にしない — 検査は `W-THUMBNAIL-ABSENT`・G1。既定で先頭節の挿絵を流用せず、どれを表紙にするかは必ず選ぶ)。(c) 本編の最後に `section_kind: "closing-summary"` を 1 節置く — 各節を要点へ絞るほど、節をまたいで残るものが本文中のどこにも書かれなくなるためで、冒頭の `goal` は予告であって総括ではない。

節の中の並びも C05 へ渡す前に決めておく。本編の節は 見出し → 絵 1 枚 → 目的と言いたいこと → 要点を並べる部品 → 補足 の順で、構成データ側では `blocks[0]` を image (要請があれば diagram) にする (`config/handout-visual-policy.json#opening.section_opening.order`・検査は W-SECTION-VISUAL-NOT-FIRST)。前へ出すのは先頭の 1 枚だけで、その 1 枚は「具体部品」に数えない (節の中身が絵だけなら LANG-06)。情報量が多いときは 1 節を厚くせず節を増やしてよい — 増えた分は目次が 2 行まで折り返して受ける (`nav.max_rows`) ので、`heading` は `nav.max_chars` に収める。絵の粒度は冊子で 1 つに揃える (画風系統・密度・視点は全節同値。混在は C21 の E-IMG-GRANULARITY-DRIFT で停止する)。

C05 が書いた構成データは validate-handout-config.py で検証し、`--normalize` の出力を以後の唯一の入力にする。正規化済み構成データには読み手・前提知識・用途が入っている必要がある。C03 が委譲入力の `reader_profile` をこれらから組み立てるため、欠けたままでは意味レビューへ進めない。

## 単一 HTML の決定論生成

素材の data URI 化 (embed-assets.py)、概念図解の inline SVG 生成 (render-diagram-svg.py)、使用アイコンだけの symbol 生成 (build-icon-sprite.py)、挿絵の生成委譲 (srg-image-bridge.py)、単一 HTML のレンダリング (render-handout.py) を決定論 script 列として実行する。本 skill はこれらの引数を組み立てるだけで、HTML の断片を自分で書かない。

共有時のサムネイル (OGP)・帯の一番上の題・紙面に出さない日付 (root 属性 data-hb-date が唯一の運び手)・節番号と題の区切り・2 行まで折り返す常時表示の目次・常駐する操作帯 (メモを埋め込んだ HTML の保存) は、すべて C11 が構成データから決定論に組み立てる面である。指摘を受けても HTML を手で足さず、出ていなければ C11 か構成データ側の欠落として扱う。

挿絵の委譲は exit 0 が「生成した」と「skip した」の両方を含むため、exit code でなく stdout の `status` を読む。`status=skipped` のときは `skip_reason` (`srg-absent` = 委譲先の SRG 実体が解決できない / `runtime-absent` = node か codex が無い) をそのまま生成レポートの warning へ転記し、画像なしで先へ進む。skip を黙って成功へ畳まない — 挿絵が無いまま出来上がったことが読み手に見えなくなるためである。

利用者が画風の参照画像または参照フォルダを示した場合は、選んだ実在画像を画像計画トップレベルの `style_reference_paths` として C21 へ渡す。説明文へ「漫画調」「青基調」と書くだけで代替しない。C21 は参照画素を SRG 作業域へ無加工で配置し、全節の `styleReference` へ同じ anchor として結線する。指定済み参照が欠落していれば fail-closed とし、参照なしの生成を成功扱いしない。

## ゲート集約と出力配置

検証ゲートは `/handout-verify` (C09) を `--json-report` つきで起動して実行し、返った summary.json の verdict と各ゲート面の状態をそのまま受け取る。状態分類と全体 verdict の判定規則は C09 の CR-GATE-AGG が単一正本であり、本 skill では再実装も再解釈もしない。verdict が pass 以外なら該当箇所を直して再実行する。not-run を「通った」と読み替える判断を本 skill 側に持たない。

出力先ルーティングは route-handout-output.py (C19) へ `--place-config` と `--assets-src` を渡して実行する。構成データと素材原本の複製は C19 に行わせ、ディレクトリ名の組み立ても C19 の責務である。C19 が返した出力ディレクトリ直下へ `README.md` を書くのは本 skill の責務で、節は原題・目的・適用プリセット・同梱物一覧・各同梱物の使い方とする。

## 読みやすさレビューの委譲

**委譲するのは release 段だけである** (`draft_first.skipped_in_draft.readability_review`)。第1稿は利用者本人が現物を読むため、レビュアーを挟むより速くて正確な判定が既に得られている。ここを draft へ前倒しすると、利用者が一度も見ていない資料の読みやすさを推測で詰める周回に時間を使うことになる。

release 段でゲートの verdict が pass になった資料について assign-handout-readability-evaluator (C03) へ 1 回委譲する。C03 は verdict を無加工で返し、再レビューの起動と打ち切りは本 skill のゴールシークだけが持つ。

**初回の委譲は `scope` を渡さず全体を読ませる。2 回目以降は、直前の周回で実際に手を入れた節の id だけを `scope` として渡す。** 触っていない節を毎周読み直しても、同じ HTML から同じ判定が返るだけで待ち時間と読み込みだけが増える。節をまたぐ軸 (goal-chain / opening-order / nav-scannability) はレビュアー側が `scope` に関わらず全体で見るので、絞ったことで全体の筋の断裂を見落とすことはない。

`scope` に載せるのは**直した節**であって、指摘が出ていた節ではない。指摘に対して別の節を直したなら渡すのは直したほうである。また `scope` へ添えてよいのは節 id だけで、何周目か・前回何を指摘されたか・どこをどう直したかは渡さない。渡した時点で独立 context が壊れ、レビュアーの verdict に「もう十分だろう」が入る。

**`scope` を絞ったときの `verdict=PASS` は、それだけでは release の完了根拠にならない。** verdict はレビュアーが読んだ範囲の findings から計算されるので、`severity=high` の指摘を受けた節を直さないまま `scope` から外せば、その節は読まれず findings に現れず PASS が返る。これを塞ぐため、本 skill は受け取った `severity=high` の指摘を**解消するまで自分の側に残す**。解消とは資料を直したうえで、その節を次の `scope` に載せて再度レビューを受け、その周の findings に現れないことである。同じ形で、**最後に手を入れて以降まだ一度も読まれていない節**も未解消として扱う。初回の全件レビューで読み終えた無改修の節は既読なので消え、直した節は次周の `scope` に載せて読ませれば消える。「そのレビューで読まれなかった節」を数えてはならない — 2 周目以降は `scope` を絞る以上つねに未読の節があり、それを未解消と数えると release へ永久に到達しない。

`not_reviewed` を一括で未解消にしてはならない。この配列は性質の異なる 2 群を運んでいる — (a) `scope` により読まなかった節・軸 と、(b) `machine_gate_overlap` により除外した面である。(b) は決定論ゲートが既に見ている面を二重に指摘しないための除外であり、C06 は全件レビューでも必ず理由付きで残す。したがって `not_reviewed` は非空が正常形であり、(a) についても上のとおり「未読のまま残っているか」で見る。

これは verdict の再判定ではない。severity を決めるのも PASS/FAIL を決めるのも C06 のままで、本 skill が持つのは「受け取った指摘がまだ残っているか」だけである。

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

判定は 3 つしかない。**構成が確定したか (G1) / 資料が読める形で成立したか (G2) / 渡せる形で開示したか (G3)** である。段 (draft / release) が変えるのは判定の数ではなく、各判定を満たしたと言える中身である。

分類の基準は「利用者が現物を見るまでに要るか」の一点であり、重要度ではない。release 側へ回した中身は品質を捨てたのではなく、**現物が出てから効くもの**を第1稿の待ち時間から外しただけである。

#### G1: 構成データが確定している

- [ ] draft: validate-handout-config.py が exit0 で、**読まれない状態を示す warning** が 0 件である
- [ ] release: 同左を維持している (指摘の反映で新たに出していない)

0 件を求めるのは次の 13 コードであって、C12 が出す warning の全件ではない。図解密度と文字量 (`W-VISUAL-ABSENT` / `W-DIAGRAM-FEW` / `W-TEXT-HEAVY` / `W-TEXT-RUN` / `W-COPY-LONG`)、層の切り分け (`W-DETAIL-ABSENT` / `W-LAYER-ORDER` / `W-DETAIL-FLOWLESS`)、冒頭の置き方 (`W-HERO-LONG` / `W-OPENS-PROSE`)、節の入口と共有面 (`W-SECTION-VISUAL-NOT-FIRST` / `W-THUMBNAIL-ABSENT`)、用語の言い換え (`W-GLOSSARY-EMPTY`)。最後の 1 つを外せない理由は `criteria:IN1` が「用語言い換え宣言の欠落 0 件」を要求する一方、**欠落**を見る診断がこれしか無いためである (error 側の `E-GLOSSARY-DUP` は重複を見るので代わりにならない)。いずれも同じ 1 回の出力に並んでいるので、種別ごとに項目を立てても検査は 1 つも増えず、同じ出力の読み直しだけが増える — だから 13 項目ではなく 1 項目で受ける。

残りの warning は**利用者が選んだ結果を報告するもの**であり、完了を阻まない。とりわけ `W-SECTIONS-MANY` は本文が明示的に許可した行為 (情報量が多いときは 1 節を厚くせず節を増やしてよい・`nav.max_rows`) に対して出る。これを欠陥として数えると、許可した行為を選んだ資料が draft を完了できなくなる。**「warning 全件 0」を完了条件にしない**のはこのためで、0 件を求める対象を上の 13 コードに固定してあるのはその境界そのものである。

それでも種別を挙げるのは、0 件でない資料が具体的にどう読まれないか (図が無く文章が長い / 要点より先に手順が来る / 冒頭が段落で始まる / 節の入口に絵が無い = 読み手が読まない状態そのもの) を設計時に思い出すためである。速さのためにこれらを外さない — C12 は数百ミリ秒で終わるので待ち時間の原因ではない。

ヒアリング必須項目 (`hearing_required_items_r21` / `_r22`) の確定もここで落ちる。`never_inferred_fields` (`doc_type` / `out_dir`) 以外は 1 ラウンドで聞くか素材から推定で埋めてよく (回答を待たずに進む。非対話経路では検証済み構成データがその代わりを満たす)、埋まったかどうかは C12 の必須検査が判定する。項目ごとの検査コードは frontmatter の `checked_by` が持つので、散文で二重に数えない。

`criteria:IN1` はこの判定の別名である。

#### G2: 資料が読める形で成立している

- [ ] draft: 単一 HTML を決定論 script 列で生成し、`/handout-verify` の集約 verdict が pass で、同梱構成データからの再生成がバイト一致する
- [ ] release: 同左に加えて、C03 (`draft_first.skipped_in_draft` の可読性レビュー) から回収した verdict が PASS で、**未解消の `severity=high` 指摘が 0 件**であり、**最後に手を入れて以降まだ一度も読まれていない節が 0 件**である

ゲート面を面ごとに数え直さない。集約は C09 の CR-GATE-AGG が単一正本であり、本 skill が受け取るのは verdict 1 個である。第1稿の粒度 (`draft_first.first_draft_detail_level` — 全体を詳細で作ってから削らない) が守られているかもここで落ちる。実態との一致を見るのは C22 の NAR-09 / NAR-10 であって散文の自己申告ではない。

release の visual-fit は alt 文でなく全 illustration の実画素を開き、(a) 節の人物/役割主体・行為・場所・主役の具体物、(b) 読み順、(c) 指定された画風・配色・俯瞰角度、(d) 冊子内の統一と節ごとの場面差、を確認して初めて PASS にできる。

`criteria:OUT1` のゲート面と `criteria:OUT2` はこの判定の別名である。

#### G3: 渡せる形で開示している

- [ ] draft: 出力先へ同梱物が揃い `README.md` を書き、生成レポート (適用部品・埋め込みサイズ・warning・ゲート結果・**仮置き項目**・載せなかった項目・**第1稿で回さなかった工程**) を返して停止した
- [ ] release: 開示した仮置き項目を利用者が確認し、覆った項目を R5-refine で反映した。粒度を上げたのは利用者が指した箇所だけで、他は `first_draft_detail_level` のままである

draft でこの判定を満たすことは completed ではない。**第1稿は速い完了ではなく、未完了だが読める状態である。** 開示そのものを判定に入れてあるのは、回さなかった工程が黙って消えるのを防ぐためであり、`criteria:OUT3` はこの開示が実走で起きたことを見る。

`criteria:OUT1` の同梱物面はこの判定の別名である。

#### 旧 D1-D10 / F1-F4 との対応

検査は 1 つも減っていない。3 判定は同じ検査を、それを返す機械の単位で束ね直したものである。

| 旧 | 現 | 旧 | 現 |
| --- | --- | --- | --- |
| D1 ヒアリング必須項目 | G1 | D8 集約 verdict | G2 |
| D2 第1稿の粒度 | G2 | D9 同梱物・README・生成レポート | G3 |
| D3 C12 exit0 | G1 | D10 節の入口・共有面の警告 | G1 |
| D4 図解密度・文字量の警告 | G1 | F1 仮置き項目の確認と反映 | G3 |
| D5 層の切り分けの警告 | G1 | F2 可読性レビューを回した | G2 |
| D6 冒頭の置き方の警告 | G1 | F3 C03 verdict PASS・visual-fit | G2 |
| D7 決定論 script 列での生成 | G2 | F4 粒度を上げた範囲 | G3 |

### ゴールシークループ

frontmatter の `goal_seek.engine: inline` / `fork: subagent` を実行契約とする。固定手順は使わず、未達 checklist と担当 `prompts/*.md` からその周回の操作を都度生成する。**周回上限は `goal_seek.max_loops` の一本値だけ**であり、段ごとの上限も criteria ごとの反復上限も置かない。段が変えるのは回数ではなく、何を未達として拾い何のために回してよいかである。

- **draft (既定)**: 未達として拾うのは G1-G3 の draft 行だけで、release 行は未達に数えない。回してよいのは決定論ゲートを exit0 へ戻す修復に限る。「もっと良くできる」は draft の周回理由にならない — その判断は利用者が現物を見て下すほうが速く、正確である。この制約は上限の数ではなくこの規則が担う。上限に達する前に回す理由が尽きるのが draft の正常形である。
- **draft の出口**: G1-G3 の draft 行が揃ったら completed を宣言せず停止し、(1) 出力ディレクトリのパス、(2) 生成レポートの仮置き項目、(3) `skipped_in_draft` により回さなかった工程、(4) 指摘の受け取り先が R5-refine であること、を提示する。**第1稿は速い完了ではなく、未完了だが読める状態である。**
- **release**: 利用者の指摘を受け取ってから入る。指摘なしに自動昇格しない。draft 行は確定済みとして再取得せず、release 行と、指摘で壊れた draft 行だけを回す。

各周回で inner criterion (IN1) を検証し、その周回の修復が終わった時点で outer criterion (OUT1 / OUT2) を 1 回評価する。評価のための追加の周回予算は持たない — 資料を直さずに再評価しても決定論検証の結果は変わらないため、fail なら次の 1 周として修復へ戻るだけである。IN1 / OUT1 / OUT2 はいずれも決定論検証であり draft でも省かない (省くと開けない HTML を渡すことになる)。

### ゴールシーク配線

- 元のゴールを `eval-log/guide-doc-generator/run-handout-build-goal-spec.json` へ、各 checklist の status と evidence を `eval-log/guide-doc-generator/run-handout-build-progress.json` へ記録する。
- 未達 responsibility を担当する `prompts/<R-id>.md` を読み、`Agent` で分離 context に fork する。ユーザー判断が必要な境界だけ `AskUserQuestion` を使う。
- 各周回末に `eval-log/guide-doc-generator/run-handout-build-intermediate.jsonl` へ `original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を append-only で記録する。次周回は直前の `merged_directive_for_next` を必須入力にする。
- 上限周回に到達しても未達が残れば完了扱いにせず、progress と blocker を親へ handoff する。completed を宣言できるのは **release 段で G1-G3 の draft 行と release 行、および `feedback_contract.criteria` が全て PASS のとき**だけである。draft 段の停止は完了ではなく引き渡しであり、progress には未達として各判定の release 行を残す。
- progress には各 checklist の status と併せて現在の `build_stage` を記録する。draft の停止を「全項目 PASS」と書かない — 記録が完了に見えると、繰り越した release 行が回収されないまま積み上がる。

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
- `criteria:OUT3`: 題材と素材だけを与えた実起動で、質問ラウンドが `draft_first.max_question_rounds_before_first_draft` 回以内に収まり、G1-G3 の draft 行が揃った時点で completed を宣言せず停止して成果物のパス・仮置き項目・回さなかった工程を提示し、C03 委譲が draft 段で起動しておらず、挿絵生成 (C21) は R25 (goal-spec C69) により draft 段でも起動していることを実走の痕跡で確認する。

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
- 第1稿を渡す前に完璧を狙わない。利用者が見ていない資料に対する「まだ良くできる」は推測であり、その推測を潰す周回が待ち時間の主因になる。G1-G3 の draft 行が揃った時点で必ず一度渡す。
- draft の停止を completed と報告しない。各判定の release 行は繰り越しであって免除ではなく、「全部通りました」と報告した瞬間に回収されなくなる。停止時は必ず未回収の工程を名指しする。
- 速さのために決定論ゲートや C12 の warning を外さない。これらは数百ミリ秒で終わるため待ち時間の原因ではなく、外すと「開けない HTML」や「図が無く文章が長い資料」を第1稿として渡すことになる。第1稿で外してよいのは `draft_first.skipped_in_draft` に挙がった工程だけである。

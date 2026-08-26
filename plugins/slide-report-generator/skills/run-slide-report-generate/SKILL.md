---
name: run-slide-report-generate
description: スライドやレポートを新規生成し、開ける実HTMLを最小guard後に先に提示し、利用者が選んだ場合のみ診断・有界改善したいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
argument-hint: "[topic?] [--mode slide|report] [--report-type internal-analysis|client-proposal|tech-doc|learning] [--out-dir <path>]"
arguments: [topic, mode, report_type, out_dir]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(node *)
  - Bash(python3 *)
  - Task
  - Glob
  - Grep
effect: local-artifact
owner: harness maintainers
since: 2026-07-05
last-audited: 2026-07-05
output_language: ja
prompt_layer: 7layer
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: subagent
  max_loops: 5
responsibility_refs:
  - prompts/R1-orchestrate.md
schema_refs:
  - ../../schemas/structure.schema.json
  - ../../schemas/report-structure.schema.json
  - schemas/generation-report.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 受入基準(purpose-acceptance)。deck-evaluator の生成後評価 verdict と突合し汎用ゲート言い換えへ退化させない
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-output-mode で output_mode(slide/report)と reportType の値域を送信前検証し、確定 mode が構成設計へ一貫伝播して仕様確定ゲート入力の欠落が0件
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 構成着手前に information-priority-map.json を出力し validate-information-priority.py が exit 0 (順位の確定が強弱・装飾の宣言に先行し、削減/加工に理由があり、形式候補を2件以上比較し、色単独で意味を担わせていない)
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 生成後に slide/report とも想定読者の共有課題→読者の変化→専門的で具体的な解決→自分へ移す行動の流れを持ち、slide は1スライド1メッセージ/長文なし・report は読み物/1項目1ビジュアルで、deck-evaluator の生成後評価(30種思考法・D5 読者フック)が視覚崩れ0で PASS する
      verify_by: evaluator  # 検証主体は deck-evaluator。tests/ に読者フックの受入テストは無く、test と綴ると写像が空洞化する
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

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-slide-report-generate

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

> **役割**: プレゼンスライド／読み物レポートの**新規生成**を単一 skill で駆動する主オーケストレータ。意匠／技術コアは単一 SSOT で共有し、最初のhandoffは実HTMLの生成・最小guard・提示で完了する。15 agent / 30種思考法 / 最大3周は利用者選択後のみ。plugin root = `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}`。

## Purpose & Output Contract

`output_mode` と読者価値ブリーフを依頼から最尤推定し、構成設計→生成まで進む。実HTMLにparse/open・secret・不可逆・破損の最小guardを掛け、パスと開き方を提示する。その後に診断深度を聞き、選択時だけ mode-aware semantic評価と改善を行う。

- **入力**: 構想 (自然文) + `output_mode` + 読者価値ブリーフ。report 時は `reportType`／読者／長さ／ビジュアル方針。任意 `--out-dir <path>`。
- **出力**: **生成レポート** (`output_mode` ／ 生成経路 ／ 生成後評価スコア ＋ 生成物パス (slide=`index.html`(+`styles.css`/`scripts.js`) ／ report=`report.html`) ＋ 未達指摘一覧)。
- **初回handoff完了条件**: mode/briefを推定し、実HTMLを生成、class別最小guard PASS、実成果物のpath/試し方を提示。`accept-as-is` はevaluator 0 / improver 0で完了。semantic PASSやgovernanceはhandoff前提ではない。

## output_mode 分岐契約 (意匠は共有・意図のみ分岐)

**設計の核**: 意匠／技術層は**単一 SSOT で共有**し mode で重複させない。分岐するのは**コンテンツ意図層のみ**。

- **共有 SSOT (mode で重複させない)**: 配色トークン ／ 16:9 ／ 最小 1.4rem ／ GSAP ／ インライン SVG2 ／ 印刷 CSS ／ letterbox ／ Codex Image2 ／ style genome ／ 決定論レンダラ ／ `theme`・`aiVisual` schema `$defs`。
- **共有コンテンツ契約**: 読者価値ブリーフを R1→R2→R3 へ一貫伝播し、既存フィールド（title/audience/keyMessage/throughLine/sections）へ翻訳する。schema 外フィールドや素材にない数字・実績を発明しない。正式名称・検索性・適用範囲が必要な文書は主タイトルを保ち、subtitle/keyMessage/summary で読者価値を補う。
- **mode 別 (コンテンツ意図のみ分岐)**:
  - `slide`: 1 スライド 1 メッセージ ／ chip 強制 ／ 長文禁止 ／ 16:9 ／ <!-- count: slideType -->107 slideType ／ `schemas/structure.schema.json`。
  - `report`: 読み物 (文章多め可) ／ セクション＋段落 ／ 1 項目 1 ビジュアル最適化 ／ HTML レポート ／ 4 reportType ／ `schemas/report-structure.schema.json`。
- **reportType enum (4)**: `internal-analysis` (社内報告分析: 要約→背景→現状分析→所見→次アクション) ／ `client-proposal` (顧客提案 WP: 課題→解決策→効果実績→導入ステップ→CTA) ／ `tech-doc` (技術ドキュメント: 概要→前提→手順構造→注意点→参照) ／ `learning` (学習解説: 問い→核心概念→図解理解→例応用→まとめ)。
- **確定と伝播**: `hearing-facilitator` が `output_mode`／読者価値ブリーフ／`reportType`／読者／長さ／ビジュアル方針を確定 → 主 skill が下流全 agent へ**一貫伝播** → `validate-output-mode.py` が mode 値域を生成着手前に検証 (fail-closed)。

## ワークフロー (R1 → R2 → R3 生成/guard → R4 提示 → R5 選択 → R6 optional review)

参照 agent は **name で Task 起動**する (ファイル依存なし)。各 agent は独立 context (isolation) で自身の 7 層本文に従う。

### R1: ヒアリングと mode 確定

`Task` で **hearing-facilitator** を起動 (`isolation: inherit`・会話履歴を保持して mode 推定)。成果物前の追加質問はせず、不足は最尤仮定としてhandoffに明記する。

- `output_mode` = slide ／ report。読者価値ブリーフ = 対象範囲・共有課題/願望・読後/視聴後の変化・専門の橋・深さの証拠・正式タイトル制約。
- report 時: `reportType` (4 enum)／読者／長さ／ビジュアル方針。
- 全面画像化ゲート (CONST_006): ユーザーが「画像生成でスライドを作る」等を明示した場合、全面画像生成モードを確定 (背景化バランス型は明示時のみ)。設計方針の正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/full-image-deck-method.md` (plugin-root 共有)、Codex Image2 実行導線の正本は skill 私有 `references/ai-image-pipeline.md` (ai-image-diagram-producer が消費) の 2 層に分離する。

確定した mode 一式を**下流 R2／R3 の全 agent へ一貫伝播**する。伝播前に `validate-output-mode.py` (下記 IN1) で値域を検証する。

### R2: 構成設計と仕様確定ゲート

確定 mode に応じて構成を設計し、**仕様確定ゲート**で P3 進入を制御する。

- **情報優先度の確定 (構成着手前・両 mode 共通)**: 構成へ入る前に「誰が・どの文脈で・何の task を」から情報の順位を決め、`information-priority-map.json` (schema=`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/../system-spec-harness/schemas/information-priority-map.schema.json`) へ宣言して下記 IN2 ゲートを exit 0 にする。順位が確定する前に強弱・装飾を宣言していれば fail-closed で差し戻す。SRG への写像は `references/information-priority-rules.md`、原理の正本は `plugins/system-spec-harness/skills/ref-system-design-knowledge/references/information-design.md`。
- **slide**: `Task` で **structure-designer** を起動 → `structure.json` (`schemas/structure.schema.json` 準拠) を設計。図解が要る場合は **d3-diagram-designer** (D3) ／ **data-visualizer** (データ可視化) を併用。
- **report**: `Task` で **report-structure-designer** を起動 → `report-structure.json` (`schemas/report-structure.schema.json` 準拠・`sections[]` 主配列) を設計。各 section のビジュアルは **visual-strategist** が「1 項目 1 ビジュアル」の三択 (`svg`／`mermaid`／`codex-image`／`none`) を決定。
- **読者中心設計**: 両 mode とも入口は想定読者の共有課題と変化を先に渡し、本論は確認済みの数字・手順・失敗・条件・限界まで掘る。各主要セクションに「兆候・問い・選択肢・次の行動」のいずれかを置き、自分ごと化する。
- **図解被覆の生成前判定 (両 mode・仕様確定ゲートの一部)**: 構成が「文字リストしか持たない」かを**生成前に**数える。`python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-diagram-coverage.py" <structure.json>` (0=下限以上 / 1=下限未満 / 2=判定対象 0 件で緑ではない)。判定は slideType ごとのテンプレート実体 (`vendor/scripts/templates/*.html.tpl` に `<svg` / `{{{svg}}}` / `data-d3-mount` があるか) と engine CSS (`vendor/scripts/style-builder.cjs` に軸を描く擬似要素規則があるか) を**実行時に走査**して行い、型の一覧を写経しない。**この段階では型しか見えない** (QR 主役の面・実項目数・面ごとの図の差し込みは見えない) ので赤は候補であり、正本は R3 の成果物判定。赤なら型を選び直してから R3 へ進む — 生成後に気づくより手戻りが短い。規約は `references/visual-generation-rules.md` §4.1。
- **仕様確定ゲート**: `Task` で **structure-validator** を起動し、`validate-structure.js` で機械検証する。PASSはR3、FAILはR2へ最大1周差し戻し、WARNは仮定として現物を作りhandoffに明記する（成果物前の承認質問にしない）。

### R3: 生成と最小guard

確定 mode ・経路で実成果物を生成し、UTF-8 parse/open・空/破損・secret混入・不可逆処理有無の最小guardだけを通す。

- **生成経路 (mode ／指示で選択)**:
  - `slide` LLM 経路: `Task` で **html-generator** → `index.html` ＋ `styles.css` ＋ `scripts.js`。
  - `slide` 決定論経路 (推奨・再現性 100%): `Task` で **slide-renderer** → `node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/render-slide.cjs" <structure.json> <out-dir>`。
  - `report` 経路: `Task` で **report-composer** → `node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/render-report.js" <report-structure.json> <out.html>` で `report.html` を決定論生成。
  - **画像明示時のみ**: `Task` で **ai-image-diagram-producer** (Codex Image2)。導線 = `build-image-prompts.js` → `generate-images-codex.js` (`meta.source=codex-image2`・PNG 署名回収＋リトライ) → `build-deck-html.js` (自己完結 index.html)。`codex` 単体は画像生成器ではなく実 backend を着手前に確認する。
  - **post-choice品質補正**: `ui-quality-reviewer` / `layout-optimizer` / `report-quality-reviewer` / 実描画・印刷・図解の詳細gateはR6でのみ実行する。R3のhandoff前提は実HTMLの最小guardだけで、これらを提示完了の依存先にしない。

### R4–R6: 提示、選択、選択後評価

R4で実artifactのpathと開き方を提示し、R5で `accept-as-is / light / standard / detailed` を聞く。accept-as-isはevaluator 0 / improver 0。改善レベル選択時のみR6の15 agent orchestrationと **deck-evaluator** の30種思考法を起動し、選択範囲の改善→再評価を最大3周に限定する。release/exhaustiveはこのchoiceへ混ぜず、別の明示eventがある場合だけ実行する。

状態確認は `node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/workflow-manager.js" <out-dir> --check --next` で行える。

## 決定論チェック (deterministic_checks)

送信前・生成後に以下の機械検証を実行する。値域外・仕様逸脱・視覚崩れは exit code で fail する。

> **送信前の機械ゲートは 2 本ある** — IN1 `validate-output-mode.py` (mode 値域) と IN2 `validate-information-priority.py` (構成着手前の情報優先度)。**それでも見ないもの (既知の fail-open)**: `validate-output-mode.py` が検証するのは `mode`/`reportType` の**値域だけ**で、読者価値ブリーフは見ない。ブリーフの受け皿は仕様確定ゲート側の `meta.required` (structure=title/audience/durationMinutes/keyMessage、report-structure=title/reportType/audience/keyMessage) であり、そこへ写像されない「読者の変化・自分へ移す行動」の有無は生成後の `deck-evaluator` D5 まで機械検出されない。ブリーフ 6 項目のうち「対象範囲・共有課題・読者」は次の `validate-information-priority.py` が `context_of_use`(audience / primary_tasks の頻度・失敗コスト / environment / expertise) として構成着手前に必須化するため機械で欠落検出できるが、「読後の変化・自分へ移す行動」は依然 D5 まで機械検出されない。後者の写像は R2 へ渡す前に人間側で確認する。

```bash
# 0. 初回/更新後に依存+plugin-local Chromiumを復元し、node/npm/browser/codexをpreflight (以降の実描画ゲートの前提)
python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/setup-playwright.py" --install && python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-output-mode.py" --preflight
# 1. 送信前 (IN1): output_mode/reportType 値域検証 (値域外 exit 2・fail-closed)
python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-output-mode.py" --mode <slide|report> [--report-type <enum>]
# 2. 構成着手前 (IN2): 情報優先度の宣言検証 (順位が装飾に先行しているか・0=OK/1=違反/2=usage)
python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/../system-spec-harness/scripts/validate-information-priority.py" <出力先>/information-priority-map.json
# 構成の仕様確定ゲート (V_DEFINITIONS 全件・SR-ID 連動)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/validate-structure.js" <structure|report-structure>
# slide の UI 品質 (テキスト切れ・16:9 比率)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/verify-slides.js" ./index.html --check-ratio
# slide 成果物の実描画契約 (実HTML必須・slide 0件/mixed体系/重なり/溢れを fail-closed)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-slide-layout.js" ./index.html --strict
# 比較レイアウトの比率 (SR-4-03 / V-001)。structure.json に CSS が無いため validate-structure.js では判定できず、生成物の CSS を読むこの検査器が V-001 の実行体になる (見る値と両経路の class は当該ファイル冒頭が持つ)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-compare-ratio.mjs" ./index.html
# report の実描画入力 bundle 生成 (899/900/901/1024/1366/1600px + print)。**bundle を必須入力にするのは report-quality-reviewer だけ** (agents/report-quality-reviewer.md「入力bundle欠落時はPASSにせず」)。下の 2 つのゲート (静的 shape の `validate-report-visual.py` と実描画の `validate-report-layout.js`) はどちらも bundle を取らないので、bundle 不在のまま緑になりうる — その死角を埋めるのがこの生成 (0=成功 / 1=runtime acceptance 失敗 / 2=usage・環境)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/verify-report-runtime.js" <report.html> --structure <report-structure.json> --out <out-dir>/runtime-bundle.json
# report の決定論視覚ゲート (構造正本必須・欠落 exit 2 / 0=PASS / 1=崩れ検出)。bundle 入力は取らない (argparse は report/--structure/--strict/--json/--require-structure のみ)
python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-report-visual.py" <report.html> --structure <report-structure.json> --require-structure --json
# report 成果物の実描画契約 (R1-R8 読書レイアウト・0=error 0件 / 1=error あり)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-report-layout.js" <report.html> [--viewport 1440x900] [--strict]
# 図解の静的契約 (D 系全件。幾何・素材・上限・符号系。両 mode 共通。改善レベル選択後の R6 で明示実行し、hook-postgen-eval は実行しない)
python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-svg-diagram.py" <index.html|report.html> --check-grid --strict
# 図解の情報契約 (I1-I5 + 型別スロット = 図が図として成立する下限。上記の上限検査を置き換えない・同じ図へ別々に掛ける)
python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-diagram-information.py" <index.html|report.html>
# 図解被覆 (DC1-DC6 = 面が視覚構造を「持っているか」。上の 2 本はどちらも見つけた図を見るので、図 0 個の面は検査対象が無く緑になる)
# R3 生成後 (両 mode)。0=下限以上 / 1=下限未満 / 2=判定対象 0 件 (緑ではない) / 3=入力不能。改善レベル選択後の R6 で明示実行し、hook-postgen-eval は実行しない
python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-diagram-coverage.py" <index.html|report.html> [--min-ratio 0.5]
# 図解被覆の構成段階版 (R2 仕様確定ゲート。slideType のテンプレート実体を走査し「図を出さない型しか無い」構成を生成前に落とす)
python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-diagram-coverage.py" <structure.json> [--min-ratio 0.5]
# 生成後評価オーケストレータ (D1 視覚崩れ/D2 文字サイズ/D3 ナビ/D4 仕様適合・0=PASS/4=FAIL)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/evaluate-deck.js" <out-dir>
# 画像明示時: prompt/meta/WebP 整合と style genome 反映 (PNG/WebP 署名検査)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/validate-ai-image-assets.js" <out-dir> --full-image-deck --strict-style-genome
# 印刷 letterbox (@media print 内 cover を CRITICAL 検出)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/validate-print.js" <index.html>
# ページひな形資産を触ったとき: 写像被覆/幾何整合/生成物一致 (HTML・CSS・JS)/色の直書き禁止/A4 印刷倍率 (0=PASS)
python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-slide-skeleton.py"
```

> **図解 2 本の読み分け**: `validate-svg-diagram.py` は**上限** (座標・寸法・色・書体・要素数・複雑度) を、`validate-diagram-information.py` は**下限** (その情報を書いたなら必ず現れる語の有無) を見る。前者が全部緑でも「主キーの無い ER 図」「目盛の無い価値軸」は通るので、後者は前者の代わりにならない。後者の warning は語彙近似ゆえ**合否に入れず読んで判断する対象**で、確定的に判るのは error 2 件 (`I-ER-REF` 参照の取りこぼし / `I-REL-ISO` 孤立節点) だけ。両者は改善レベル選択後のR6で明示実行する。`hook-postgen-eval` はUTF-8 open / HTML parse / 空・NUL破損 / secretの最小guardだけを行い、この2本を起動しない。

> **3 本目 `validate-diagram-coverage.py` が見るのは「図の質」ではなく「面が視覚構造を持っているか」**。上の 2 本はどちらも**見つけた図**を検査対象にするので、**図が 0 個の面には検査対象が存在せず緑**を返す (分母 0 の緑)。全面が `ul>li` とカードの羅列でできた deck は上の 2 本を全部通る。
>
> **ただし「SVG があるか」で数えてはいけない。** 実測した反例 (2026-08-14 20:04 JST・実運用 deck `slide-2026-08-15-AI質問会-v2-ink-on-paper/index.html`): 面 4 (`slide-timeline`) は SVG も canvas も図 img も持たないが、CSS の軸 (`.timeline::before`) と節点 (`.timeline-item::before`) でタイムライン図が成立している。よって**主判定は「文字リストであること」の側**に置き (li・カードが 3 件以上で接続線も位置関係も無い面を赤)、**視覚構造の検出は免責側**に置く (SVG/canvas/D3/図 img に加え **CSS で描かれた軸＋節点**を拾う)。どちらとも言えない面は **DC5 判定保留**として分母から外し名指しする。誤検出の向きは見落とし側になり、人が `data-diagram-exempt="<理由>"` で免責する形になる。
>
> 出力する分母は 3 つ (全面 / 図が要る面＝除外後 / 判定できた面)。**exit 2 (判定できた面 0 件) を緑と読まないこと。** 除外は面番号でなく面の型で決まり (QR/連絡先が主役の面は視覚構造の判定**後**に除外)、除外した面と理由は DC4 として毎回出る。拾えない形 (外部 CSS・実行時 JS 装飾・`background-image` の SVG・`transform` の斜線・軸の無い連番バッジ) は DC6 として毎回告知する。規約本文の正本は `references/visual-generation-rules.md` §4.1。
>
> **走らせる場所は 2 箇所**: (1) **R2 仕様確定ゲート**で `structure.json` へ当てる (slideType のテンプレート実体と `vendor/scripts/style-builder.cjs` の CSS を実行時に走査し、`slide-list`/`slide-grid`/`slide-icon-grid`/`slide-process`/`slide-compare` のように **図を 1 つも出さない型**しか持たない構成を生成前に落とす。`slide-timeline` は CSS 側で図になるので図として数える)。ここでは型しか見えないので **QR 主役の面や実項目数は見えず過剰に赤が出る — 候補判定である**。(2) **R3 生成後**に成果物 HTML へ当てる。こちらが正本。片方だけでは足りない — 型の宣言と描画実体は別物 (`references/diagram-type-crosswalk.md` §10)。

## ゴールシークと受入基準 (combinators)

本 skill は固定手順でなく、**ゴール** (上記「目的と出力契約」の完了条件) へ向けて未達項目を埋める手順を都度生成して反復する。`with-goal-seek`(max_loops 5) + `with-feedback-contract` を適用する。ループ本体は親セッションで直接回さず `Task` で SubAgent へ fork し (`goal_seek.fork: subagent`)、親へは最終成果物パスと生成レポートのみ返す。

受入基準 (`feedback_contract.criteria`・frontmatter に焼込済) は当該 skill の goal／checklist 由来の**受入条件 (purpose-acceptance)** であり、汎用品質ゲートの言い換えに退化させない:

- **IN1 (inner・script)**: `validate-output-mode` で `output_mode`(slide／report) と `reportType` の値域を送信前検証し、確定 mode が構成設計へ一貫伝播して仕様確定ゲート入力の欠落が 0 件。
- **IN2 (inner・script)**: 構成着手前に `<出力先>/information-priority-map.json` を出力し、`python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/../system-spec-harness/scripts/validate-information-priority.py" <出力先>/information-priority-map.json` が exit 0 (順位の確定が強弱・装飾の宣言に**先行**していること・削減/加工に理由があること・形式候補を 2 件以上比較したこと・色単独に意味を担わせていないこと)。**このゲートが保証するのは「順位付けをやったこと」であって「順位が正しいこと」ではない** — 後者は OUT1 と人間の未閉塞責務。
- **OUT1 (outer・evaluator)**: 生成後に両 mode が「共有課題→読者の変化→専門的で具体的な解決→自分へ移す行動」を持ち、slide は 1 スライド 1 メッセージ／長文なし・report は読み物／1 項目 1 ビジュアルで、生成後評価が読者フックと視覚崩れ 0 を確認して PASS。

未達は最大 3 周 (inner) / 5 loops (goal-seek) で findings を反映し再実行、超過時は未達指摘一覧として生成レポートへ残す。

## 境界

- 入力 = 構想と `output_mode`／出力 = HTML 成果物 (`index.html`／`report.html`)。
- **既存成果物の局所修正は `run-slide-report-modify` へ委譲**する (本 skill は新規生成のみ)。
- **シリーズ横断の整合検証は `run-cross-deck-review` へ委譲**する。

## Gotchas

- **配置非依存**: 全実行パスは `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}` 起点。vendor script = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/…`、plugin-root glue = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/…`、資産 = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/assets/…`。repo-root 直書き禁止。**唯一の carve-out が cross-plugin glue** — system-spec-harness の資産だけは `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/../system-spec-harness/…` と兄弟相対で引く (IN2 の `validate-information-priority.py` と `information-priority-map.schema.json`)。本 plugin は `distributable: false` で marketplace source が `./plugins/<name>` ゆえ install 後も兄弟配置が保たれる前提であり、`HARNESS_ROOT` などの repo-root 変数へ戻さない。
- **意匠は共有・mode で重複させない**: 配色／サイズ／レンダラ／schema `$defs` は単一 SSOT。slide／report で意匠を二重定義しない (`output_mode` 分岐契約)。
- **入口を広げても対象範囲・正確さを壊さない**: audience/reportType は維持し、正式名称・検索語・適用範囲が必要なら主タイトルに残す。読者価値は subtitle/keyMessage/summary で補い、素材にない数字・実績を作らない。
- **codex は画像生成器ではない**: `ai-image-diagram-producer` 起動時は着手前に実 text-to-image backend を確認する。`meta.source` は実体名 `codex-image2` を記録し plain `codex` は不可。
- **全面画像デッキは自己完結 HTML**: CSS/JS を `<style>`/`<script>` にインライン化 (`build-deck-html.js`)。別ファイル版は環境で消失しページ送り不可事故になりうる。
- **完成判定は実体で**: `echo`／サイズ／"PASS" 文字列で完成判断しない。ファイルは Read、画像は PNG/WebP 署名で検証し、出荷前にスクショ目視を推奨する。
- **agent は name 参照**: worker agent はファイルパス依存でなく Task の name 起動。存在は plugin の他 component が保証する。
- **slideType の受理と描画は別物 (被覆の caveat)**: schema の enum に載っている＝その型専用の絵が出る、ではない。集約 (9 型が `buildSnake` 1 本へ)・fallback 標識 (D3 は未知 component だけが型別描画に入らず fallback へ落ちる。§10 の D3実装 8 型は型別 case を持つ)・検査の空振り (D3 出力で `validate-svg-diagram.py` が `coverage=none` を返す — この PASS は「検査して合格した」ではない) の 3 つが起きる。**型を選ぶ前に `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-type-crosswalk.md` §10「受理される型と、その型専用の絵が出る型は別」の表で描画実体を確認する** (型名の列挙はそちらが正本。ここへ写すと片方だけ更新されて食い違う)。
- **手書き経路の slide 面はひな形へ嵌める (その場で組まない)**: `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/assets/slide-templates/` の `layout-<役割>` から選ぶ(**役割名であって通し番号ではない** — 同じひな形を 1 deck で何枚使ってもよい)。ひな形 HTML と `slide-skeleton.css` / `.js` は**生成物**ゆえ手編集せず、`frame-contract.json` か生成器へ入れて再生成し `python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-slide-skeleton.py"` で fail-closed 検査する。引き方・寸法と色・成果物への届け方の逐語の正本は `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/assets/slide-templates/README.md` (ここへ写さない)。
- **ひな形の封じ手は「ひな形経路の保証」であって deck 全体の保証ではない**: 空白過多・chrome ズレ・戻るページ・PDF ズレの 4 症状への封じ手は、**ひな形をコピーして書いた面にだけ**効く (症状表と再発点の逐語の正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/assets/slide-templates/README.md`)。決定論経路の `render-slide.cjs` は `frame-contract.json` を読まず独自体系で描くため、同症状は `verify-slides.js` / `validate-print.js` / `evaluate-deck.js` 側で見る。

## 配置先

| 用途 | 出力先 |
|---|---|
| 本 skill 資産 | `plugins/slide-report-generator/skills/run-slide-report-generate/` |
| slide 成果物 | `<out-dir>/index.html`(+`styles.css`/`scripts.js`)／決定論経路は `render-slide.cjs` の出力先 |
| report 成果物 | `<out-dir>/report.html` (`render-report.js` の出力) |
| 情報優先度宣言 (R2 中間成果物) | `<out-dir>/information-priority-map.json` (構成着手前に生成し `validate-information-priority.py` を exit 0 にする) |
| 生成後評価レポート | `<out-dir>/evaluation-report.json` / `.md` (`evaluate-deck.js` 出力) |

## 追加リソース

**パッケージ (実行 SSOT)**
- `prompts/R1-orchestrate.md` — R1→R2→R3 の 7 層実行 SSOT (Layer 1-7・15 agent/vendor scripts/schema/reference を実体参照。SKILL.md は router 要約、本 prompt が完全駆動契約)。
- `workflow-manifest.json` — phases (R1→R2→R3-generate-minimal-guard→R4-artifact-present-handoff→R5-diagnostic-choice→R6-selected-semantic-review)・dependsOn・resource mappingの正本。

**skill 私有 references (11 本・帰属は `references/resource-map.yaml`)**
- `references/information-priority-rules.md` — 構成設計に入る前の情報優先度宣言 (文脈→棚卸し→グループ化→順位→削減→加工→形式選定→強弱→意味的装飾) の SRG 写像と生成前ゲート。owner=structure-designer (report-structure-designer も参照)。**原理の正本は本 plugin の外** (`plugins/system-spec-harness/skills/ref-system-design-knowledge/references/information-design.md`) で、ここは写像のみ。
- `references/structure-design-rules.md` — slide 構成設計 (1スライド1メッセージ分解・共通仕様セクション・slideType 判定)。owner=structure-designer。
- `references/report-structure-types.md` — report 4 reportType 骨格 (社内報告分析/顧客提案WP/技術ドキュメント/学習解説)。owner=report-structure-designer。
- `references/d3-diagram-rules.md` — D3 インタラクティブ図解の意匠/実装規範。owner=d3-diagram-designer。
- `references/data-visualization-rules.md` — データ可視化 (グラフ/chart) 設計規範。owner=data-visualizer。
- `references/html-generation-rules.md` — slide HTML LLM 経路生成規範 (CONST_001-039)。owner=html-generator。
- `references/layout-optimization-rules.md` — レイアウト最適化 (横=文字数・カード/フォント・印刷 pt 換算 / 縦=内容高ブロック・残余の外側余白・高さ牽引・読み取り用画像・浮遊UI)。owner=layout-optimizer。
- `references/ui-quality-checklist.md` — slide UI 品質 S 系観点定義・判定基準。owner=ui-quality-reviewer。
- `references/report-quality-checklist.md` — report 品質観点 RQ1〜RQ34 (全節必須) + RQ35〜RQ37 (図解を含む節のみ)・RQCONST (読み物文体/段落密度/本質図解/through-line/読者中心入口/navigation/runtime layout)。owner=report-quality-reviewer。runtime bundle＋`validate-report-visual.py` と対 (実描画/静的shape/意味を分離)。
- `references/deck-evaluation-rubric.md` — 選択後の生成後評価 (30 種思考法 mode-aware rubric)。owner=deck-evaluator。hook-postgen-evalはこれを自動消費しない。
- `references/ai-image-pipeline.md` — Codex Image2 全面画像/差替パイプライン規範。owner=ai-image-diagram-producer。
- `references/resource-map.yaml` — 私有 reference の帰属 + progressive disclosure マップ (lint-reference-attribution.py の orphan/dangling 検査対象)。

**plugin 共有 schemas (`schema_refs`)**
- `../../schemas/structure.schema.json` — slide 入力契約 (<!-- count: slideType -->107 slideType, `$defs`)。
- `../../schemas/report-structure.schema.json` — report 入力契約 (`sections[]`・structure と共通コア `$defs` 共有)。

**plugin 共有 scripts**
- `../../scripts/setup-playwright.py` / `validate-output-mode.py` — plugin-local Chromium復元・検査 + 送信前 mode/reportType 値域検証 (fail-closed exit 2) / 環境 preflight。
- `../../vendor/scripts/` — 決定論レンダラ・validator 群 13 本 (`render-slide.cjs`/`render-report.js`/`mermaid-render.js`/`validate-structure.js`/`verify-slides.js`/`verify-report-runtime.js`/`evaluate-deck.js`/`validate-print.js`/`build-image-prompts.js`/`generate-images-codex.js`/`build-deck-html.js`/`validate-ai-image-assets.js`/`workflow-manager.js`。byte 携行・書換禁止)。**この列挙は manifest の vendor script 全件と一致させる** — 携行制約を宣言する節が取りこぼすと「携行対象でない」と読み違えられる。
- `../../../system-spec-harness/scripts/validate-information-priority.py` — 構成着手前の情報優先度宣言ゲート (順位が装飾・強弱に先行しているかの機械検査。0=OK/1=違反/2=usage)。SRG は `distributable: false` の repo 同梱 plugin なので同一 repo 内の他 plugin script を直接起動してよい。原理の正本は `system-spec-harness/skills/ref-system-design-knowledge/references/information-design.md`。
- plugin-root references (本文が参照): `../../references/full-image-deck-method.md` / `post-generation-evaluation.md` / `report-types.md` ほか意匠・生成規範の共有正本。

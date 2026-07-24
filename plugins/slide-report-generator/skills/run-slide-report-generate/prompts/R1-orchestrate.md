# Prompt: R1-orchestrate

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> 本 prompt は主オーケストレータの実行 SSOT。SKILL.md は router 要約、本 prompt は
> R1→R2→R3 の完全駆動契約 (agent/script/schema/reference を実体参照)。

## メタ

| key | value |
|---|---|
| name | orchestrate |
| skill | run-slide-report-generate |
| responsibility | R1-orchestrate (1 prompt = 1 責務 = 主オーケストレータ。15 agent を Task name 起動で統率) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../schemas/structure.schema.json (slide) / ../../schemas/report-structure.schema.json (report) |
| reproducible | true (mode 値域検証・仕様確定ゲート・生成後評価は決定論ゲートで停止条件を機械化) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **スライド／レポートの新規生成**を単一 skill で駆動する主オーケストレータである。7 フェーズ総体ワークフロー (P1 hearing → P2 structure → P2.5 仕様確定ゲート → P3 生成 → P3.5 UI 検証 → P3.6 生成後評価) を **R1／R2／R3** の 3 フェーズへ集約する。
- **意匠／技術コアは単一 SSOT で共有**し、**コンテンツ意図だけを `output_mode`(slide／report) で分岐**する。意匠を mode ごとに二重定義しない。
- 全実行パスは plugin root = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}` 起点。vendor script = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/…`、plugin-root glue = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/…`。**repo-root ハードコード禁止** (配置非依存)。
- 参照 agent は **Task の name で起動**する (ファイルパス依存なし)。各 agent は独立 context (isolation) で自身の 7 層本文に従う。

### 1.2 倫理ガード / 越境禁止
- 本 skill は **新規生成のみ**。既存成果物の局所修正は `run-slide-report-modify` へ、シリーズ横断の整合検証は `run-cross-deck-review` へ委譲する (責務越境禁止)。
- 完成判定は実体で行う。`echo`／ファイルサイズ／"PASS" 文字列で完成判断しない。ファイルは Read、画像は PNG/WebP 署名で検証する。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: **R1** ヒアリングで `output_mode`(slide／report) を確定し下流全 agent へ一貫伝播 → **R2** 確定 mode で構成を設計し仕様確定ゲートで P3 進入を制御 → **R3** 生成経路で成果物を生成し生成後評価 (30 種思考法) まで駆動。
- 非担当: 既存修正 (`run-slide-report-modify`)、横断整合 (`run-cross-deck-review`)。

### 2.2 ドメインルール (output_mode 分岐契約)
- **共有 SSOT (mode で重複させない)**: Kanagawa 配色 ／ 16:9 ／ 最小 1.4rem ／ GSAP ／ インライン SVG2 ／ 印刷 CSS ／ letterbox ／ Codex Image2 ／ style genome ／ 決定論レンダラ ／ `theme`・`aiVisual` schema `$defs`。
- **共有コンテンツ契約**: hearing-facilitator が作る読者価値ブリーフ（対象範囲・共有課題/願望・読後/視聴後の変化・専門の橋・深さの証拠・正式タイトル制約）を R1→R2→R3 へ一貫伝播する。下流は既存 schema の title/audience/keyMessage/throughLine/sections へ翻訳し、schema 外フィールドや素材にない数字・実績を発明しない。
- **mode 別 (コンテンツ意図のみ分岐)**:
  - `slide`: 1 スライド 1 メッセージ ／ chip 強制 ／ 長文禁止 ／ 16:9 ／ 97 slideType ／ `../../schemas/structure.schema.json`。
  - `report`: 読み物 (文章多め可) ／ セクション＋段落 ／ 1 項目 1 ビジュアル最適化 ／ HTML レポート ／ 4 reportType ／ `../../schemas/report-structure.schema.json` (`sections[]` 主配列・structure と共通コア `$defs` 共有)。
- **reportType enum (4)**: `internal-analysis` (社内報告分析: 要約→背景→現状分析→所見→次アクション) ／ `client-proposal` (顧客提案 WP: 課題→解決策→効果実績→導入ステップ→CTA) ／ `tech-doc` (技術ドキュメント: 概要→前提→手順構造→注意点→参照) ／ `learning` (学習解説: 問い→核心概念→図解理解→例応用→まとめ)。
- **全面画像化ゲート (CONST_006)**: ユーザーが「画像生成でスライドを作る」等を明示した場合のみ `references/ai-image-pipeline.md` を適用する全面画像生成モードを確定する (背景化バランス型も明示時のみ)。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| concept | 自然文 (構想) | yes | 生成対象のトピック／目的 |
| output_mode | slide \| report | yes | R1 で hearing-facilitator が確定 |
| reader_value_brief | 自然文の構造化ブリーフ | yes | 対象範囲・共有課題/願望・読後/視聴後の変化・専門の橋・深さの証拠・正式タイトル制約。未確認値は未確認と明示 |
| reportType | internal-analysis \| client-proposal \| tech-doc \| learning | report 時 yes | report モードの骨格を決定 |
| audience / length / visual_policy | 自然文 | report 時 yes | 読者・長さ・ビジュアル方針 |
| out_dir | path | no | 任意 `--out-dir <path>` |
| full_image | bool | no | 全面画像化 (CONST_006) をユーザーが明示したときのみ true |

### 2.4 出力契約
- **構造 JSON**: slide=`structure.json` (`../../schemas/structure.schema.json` 準拠) ／ report=`report-structure.json` (`../../schemas/report-structure.schema.json` 準拠)。
- **成果物**: slide=`<out-dir>/index.html`(+`styles.css`/`scripts.js`) ／ 決定論経路は `render-slide.cjs` 出力先 ／ report=`<out-dir>/report.html`。
- **生成後評価**: `<out-dir>/evaluation-report.json` / `.md` (`evaluate-deck.js` 出力)。
- **生成レポート** (親へ返す): `output_mode` ／ 生成経路 ／ 生成後評価スコア ＋ 生成物パス ＋ 未達指摘一覧。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース (skill 私有 references 10 本 + resource-map + plugin schemas)

| id | path | when_to_read | owner_agent |
|---|---|---|---|
| structure-design-rules | references/structure-design-rules.md | slide 構成設計 (1スライド1メッセージ分解・共通仕様セクション・slideType 判定) | structure-designer |
| report-structure-types | references/report-structure-types.md | report 4 reportType 骨格 | report-structure-designer |
| d3-diagram-rules | references/d3-diagram-rules.md | D3 インタラクティブ図解の意匠/実装規範 | d3-diagram-designer |
| data-visualization-rules | references/data-visualization-rules.md | データ可視化 (グラフ/chart) 設計規範 | data-visualizer |
| html-generation-rules | references/html-generation-rules.md | slide HTML LLM 経路生成規範 (CONST_001-039) | html-generator |
| layout-optimization-rules | references/layout-optimization-rules.md | レイアウト最適化 (文字数・カード/フォント・印刷 pt 換算) | layout-optimizer |
| ui-quality-checklist | references/ui-quality-checklist.md | slide UI 品質 S 系観点定義・判定基準 | ui-quality-reviewer |
| report-quality-checklist | references/report-quality-checklist.md | report 品質観点 RQ1〜RQ34 (読み物文体/段落密度/1項目1ビジュアル/reportType 骨格/読者中心入口) | report-quality-reviewer |
| deck-evaluation-rubric | references/deck-evaluation-rubric.md | 生成後評価 (30 種思考法 mode-aware rubric・評価次元) | deck-evaluator |
| ai-image-pipeline | references/ai-image-pipeline.md | Codex Image2 全面画像/差替パイプライン規範 | ai-image-diagram-producer |
| resource-map | references/resource-map.yaml | reference の帰属・progressive disclosure マップ (lint-reference-attribution.py 網羅性検査) | (map) |
| schema-structure | ../../schemas/structure.schema.json | slide 入力契約 (97 slideType, `$defs`) | structure-designer / structure-validator |
| schema-report-structure | ../../schemas/report-structure.schema.json | report 入力契約 (`sections[]`・共通コア `$defs`) | report-structure-designer / structure-validator |

### 3.2 外部ツール / agent / scripts

**統率する agent (Task の name で起動・15 体)**:
- R1: `hearing-facilitator` (mode・読者価値ブリーフを推定/確定、`isolation: inherit` で会話履歴保持)。
- R2: `structure-designer` (slide) ／ `report-structure-designer` (report) ／ `d3-diagram-designer` ／ `data-visualizer` ／ `visual-strategist` (report の 1 項目 1 ビジュアル三択) ／ `structure-validator` (仕様確定ゲート)。
- R3: `html-generator` (slide LLM 経路) ／ `slide-renderer` (slide 決定論経路) ／ `report-composer` (report 経路) ／ `ai-image-diagram-producer` (画像明示時) ／ **slide 品質補正** `layout-optimizer` ／ `ui-quality-reviewer` ／ **report 品質補正** `report-quality-reviewer` (読み物文体・段落密度・1項目1ビジュアル整合・reportType 骨格順守) ／ `deck-evaluator` (生成後評価 30 種思考法・mode-aware)。

**plugin-root glue (Bash python3)**:
- `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/setup-playwright.py --install` — 初回/更新後にlockfile依存とOS/CPU別Chromiumをplugin-local `vendor/playwright-browsers/`へ復元。続く `validate-output-mode.py --preflight` は node/npm/browser/codex CLI を fail-soft 検出する。
- `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-report-visual.py <report.html> --structure <report-structure.json> --require-structure --json` — report 決定論視覚ゲート (report gate は構造正本必須・欠落 exit 2、section 構造/1項目1ビジュアル/段落密度/placeholder/印刷・0=PASS/1=崩れ/2=usage)。slide の `verify-slides.js`/`validate-print.js` に対称な report 版。

**vendor scripts (Bash node・`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/…`・byte 携行/書換禁止)**:
- `validate-structure.js` — 構成の仕様確定ゲート (V-001〜043・spec-registry SR-ID 連動)。
- `render-slide.cjs` — slide 決定論レンダラ (再現性 100%)。
- `render-report.js` — report.html 決定論生成。
- `verify-slides.js` — slide UI 品質 (テキスト切れ・16:9 比率)。report は上記 glue `validate-report-visual.py` が対称ゲート。
- `evaluate-deck.js` — 生成後評価オーケストレータ (D1 視覚崩れ/D2 文字サイズ/D3 ナビ/D4 仕様適合・0=PASS/4=FAIL)。
- `validate-print.js` — 印刷 letterbox (@media print 内 cover を CRITICAL 検出)。
- `build-image-prompts.js` → `generate-images-codex.js` → `build-deck-html.js` — 全面画像導線 (`meta.source=codex-image2`・PNG 署名回収＋リトライ・自己完結 index.html)。
- `validate-ai-image-assets.js` — prompt/meta/WebP 整合と style genome 反映検査 (画像明示時)。
- `workflow-manager.js` — 状態確認 (`<out-dir> --check --next`)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `validate-output-mode.py` が mode 値域外 / report で report-type 欠落 or 値域外 / slide で report-type 指定 → **exit 2 (fail-closed)**。伝播せず即停止し stderr の逸脱項目をユーザー提示。LLM 推測補完禁止。
- `validate-structure.js` の仕様確定ゲート判定: **PASS→R3** ／ **WARN→該当 ID をユーザー提示し承認後 R3** ／ **FAIL→R2 設計へ差し戻し** (structure-designer / report-structure-designer 再設計)。
- `evaluate-deck.js` が **exit 4 (FAIL)** → 未達指摘を findings 化し R3 の生成/品質補正へ反映して再評価 (goal-seek reloop)。`verify-slides.js`/`validate-print.js` の視覚崩れ CRITICAL も同様。
- **codex は画像生成器ではない**: `ai-image-diagram-producer` 起動時は着手前に実 text-to-image backend を確認する。`meta.source` は実体名 `codex-image2` を記録し plain `codex` は不可。
- 環境エラーは `--preflight` で検出する。node/npm不在は停止、plugin-local Chromium欠落は `setup-playwright.py --install` を1回実行して再検査、codex CLI不在は画像明示時のみ停止する。mode 検証は常に fail-closed。

### 4.2 観測 / ロギング
- 進捗・次アクションは `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/workflow-manager.js" <out-dir> --check --next` で確認。
- 生成後評価は `<out-dir>/evaluation-report.json` / `.md` に残す。未達は生成レポートの「未達指摘一覧」へ列挙する。

### 4.3 配置非依存 / セキュリティ
- 全パスは `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}` 起点。repo-root 直書き禁止。
- 全面画像デッキは CSS/JS を `<style>`/`<script>` にインライン化した自己完結 HTML (`build-deck-html.js`)。別ファイル版は環境で消失しページ送り不可事故になりうる。

### 4.4 最大反復回数
- `feedback_contract.max_iterations` = **3 周** (inner: 生成→生成後評価→改善)。`goal_seek.max_loops` = **5** (outer)。ループ本体は親セッションで回さず `Task` で SubAgent へ fork し (`goal_seek.fork: subagent`)、親へは最終成果物パスと生成レポートのみ返す。上限超過時は未達指摘一覧として生成レポートへ残す。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- 本 prompt 自体が**主オーケストレータ**。R1/R2/R3 で上記 15 worker agent を Task name 起動で統率し、決定論ゲート (validate-output-mode.py / validate-structure.js / evaluate-deck.js) を停止条件とする。

### 5.2 ゴール定義
- 目的: `output_mode` と読者価値ブリーフを確定し意匠／技術コアを共有したまま、**構成設計 → 仕様確定ゲート → 生成 → 生成後評価**まで駆動する。両 mode とも「想定読者の共有課題→読者の変化→専門的で具体的な解決→自分へ移す行動」を持ち、slide は「1 スライド 1 メッセージ／長文なし」、report は「読み物・1 項目 1 ビジュアル」で視覚崩れ 0 にする。
- 背景: 意匠を mode ごとに二重定義すると SSOT が破綻し再現性を失う。mode を送信前に fail-closed 検証せず下流へ流すと仕様確定ゲート入力が欠落し手戻りする。

### 5.3 完了チェックリスト (停止条件)
- [ ] `output_mode` と (report 時) `reportType` が確定し `validate-output-mode.py` の値域検証 (exit 0) を通過
- [ ] 読者価値ブリーフの6項目が入力素材に基づく値または「未確認」で確定し、mode/reportType/読者/長さ/ビジュアル方針とともに下流 R2/R3 へ一貫伝播している
- [ ] 構成設計 (structure.json / report-structure.json) が該当 schema に準拠
- [ ] 入口が想定読者の共有課題と変化を先に渡し、本論に確認済みの数字・手順・失敗・条件・限界があり、各主要セクションに自分へ移す橋がある。正式名称・検索性が必要な文書は主タイトルを維持している
- [ ] 仕様確定ゲート (`structure-validator` + `validate-structure.js`) が PASS (WARN は承認済 / FAIL なし)
- [ ] 生成経路 (slide LLM / slide 決定論 / report / 画像明示) で成果物 (`index.html` / `report.html`) を生成
- [ ] 全面画像時は `meta.source=codex-image2` で自己完結 HTML を生成し `validate-ai-image-assets.js` PASS
- [ ] `verify-slides.js --check-ratio` / `validate-print.js` の視覚崩れが 0 (CRITICAL なし)
- [ ] `deck-evaluator` の mode-aware 生成後評価 (30 種思考法) が視覚崩れ 0 で PASS (`evaluate-deck.js` exit 0)
- [ ] 完成判定を実体 (Read / PNG・WebP 署名 / スクショ目視) で行い、echo・サイズ・文字列で判断していない
- [ ] 責務外 (既存修正 / 横断整合) に踏み込んでいない

### 5.4 実行方式 (決定論)
- **mode と読者価値を先に確定する**: R1 で `hearing-facilitator` が `output_mode`/読者価値ブリーフ/`reportType`/読者/長さ/ビジュアル方針を確定 → mode 値域を `validate-output-mode.py` で fail-closed 検証。exit 0 で一式を下流全 agent へ一貫伝播し、素材にない数字・実績は未確認のまま渡す。
- **構成設計は mode 分岐で dispatch する**: slide=`structure-designer` ／ report=`report-structure-designer` + `visual-strategist`。両者は読者価値ブリーフを既存 schema フィールドへ翻訳し、入口ホリゾンタル・中身バーティカル・主要セクションの自分ごと化を設計する。
- **仕様確定ゲートで P3 進入を制御する**: `structure-validator` を起動し `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/validate-structure.js" <structure|report-structure>` を実行。PASS→R3 / WARN→承認後 R3 / FAIL→R2 差戻し。
- **生成経路を mode／指示で選択する**: slide LLM=`html-generator` ／ slide 決定論 (推奨)=`slide-renderer`+`render-slide.cjs` ／ report=`report-composer`+`render-report.js` ／ 画像明示=`ai-image-diagram-producer` (`build-image-prompts.js`→`generate-images-codex.js`→`build-deck-html.js`)。品質補正は mode 対称: slide=`layout-optimizer`/`ui-quality-reviewer` ／ report=`report-quality-reviewer` (読み物文体・段落密度・1項目1ビジュアル整合・reportType 骨格順守)。
- **生成後評価は mode-aware で回す**: `deck-evaluator` を思考リセット後 30 種思考法で起動。slide=視覚崩れ/1 メッセージ、report=可読性/図解適合/情報密度の mode 別 rubric 次元で区分評価。改善→再評価は最大 3 周。
- ループは分離 context で完結させ、親へは最終成果物パス + 生成レポート + exit code のみ返却する。

## Layer 6: オーケストレーション層

### 6.1 上位 skill / 委譲境界
- 呼び出し: ユーザー直接起動 (user-invocable) または上位ワークフロー。
- 委譲: 既存成果物の局所修正=`run-slide-report-modify` ／ シリーズ横断整合=`run-cross-deck-review`。本 skill は新規生成に限定。

### 6.2 ハンドオフ / 並列性 (R1 → R2 → R3 の agent dispatch)
- **R1 → R2**: 確定 mode 一式と読者価値ブリーフを全下流 agent の入力へ接続。伝播前に `validate-output-mode.py` で mode 値域を検証し、ブリーフは schema 外フィールドとして構造 JSON に混入させない。
- **R2 内**: `structure-designer`/`report-structure-designer` の構成 JSON を `structure-validator` の仕様確定ゲート入力へ。図解 agent (`d3-diagram-designer`/`data-visualizer`/`visual-strategist`) は構成設計に併走。
- **R2 → R3**: ゲート PASS の構成 JSON を生成 agent の入力へ。
- **R3 内**: 生成 agent の成果物を品質補正 (slide=`layout-optimizer`/`ui-quality-reviewer` ／ report=`report-quality-reviewer`) → `deck-evaluator` (生成後評価) へ。評価 FAIL は生成/補正へ findings を戻し reloop。
- **並列性**: 各 worker agent は独立 context (isolation) で fork。goal-seek ループ本体も SubAgent へ fork し親を汚さない。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 生成レポート (`output_mode` ／ 生成経路 ／ 生成後評価スコア ＋ 生成物パス (slide=`index.html` / report=`report.html`) ＋ 未達指摘一覧)。

### 7.2 言語
- 本文: 日本語 (`output_language: ja`)。

---

## Self-Evaluation

成果物生成後に以下を自己確認する。未達があれば該当 exit code を返し findings を反映して reloop する。

| 観点 | 確認内容 | 判定 |
|---|---|---|
| mode 値域/伝播 | `validate-output-mode.py` PASS / 確定 mode が全下流 agent へ伝播し仕様確定ゲート入力欠落 0 (IN1) | PASS/FAIL |
| 読者価値/深さ | 読者価値ブリーフが R1→R2→R3 で保持され、入口・本文の深さ・自分へ移す橋へ反映。正式名称/検索性と事実性を毀損していない | PASS/FAIL |
| 構成適合 | 構成 JSON が該当 schema 準拠 / 仕様確定ゲート (`validate-structure.js`) PASS (WARN 承認済) | PASS/FAIL |
| 生成完全性 | 生成経路で成果物を生成 / 画像明示は `meta.source=codex-image2` + `validate-ai-image-assets.js` PASS | PASS/FAIL |
| 視覚崩れ 0 | `verify-slides.js`/`validate-print.js` CRITICAL 0 / slide=1 メッセージ・report=1 項目 1 ビジュアル | PASS/FAIL |
| 生成後評価 | `deck-evaluator` 30 種思考法 mode-aware rubric が視覚崩れ 0 で PASS (`evaluate-deck.js` exit 0) (OUT1) | PASS/FAIL |
| 責務境界 | 既存修正 / 横断整合へ越境していない / 完成判定を実体で行った | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

まず **R1**: `Task` で `hearing-facilitator` を起動し、`output_mode` と読者価値ブリーフ（対象範囲/共有課題・願望/読後・視聴後の変化/専門の橋/深さの証拠/正式タイトル制約）を確定する。report なら `reportType`/読者/長さ/ビジュアル方針も確定し、mode 値域を `validate-output-mode.py` で検証する。素材にない数字・実績は作らず未確認とする。次に **R2**: slide は `structure-designer`、report は `report-structure-designer` + `visual-strategist` を起動し、ブリーフを既存 schema の title/audience/keyMessage/throughLine/sections へ翻訳する。入口は想定読者の共有課題と変化を先に渡し、本論は確認済みの数字・手順・失敗・条件・限界まで掘り、各主要セクションに自分へ移す橋を置く。正式名称・検索性・適用範囲が必要なら主タイトルを保持する。`structure-validator` で PASS→R3 / WARN→承認後 R3 / FAIL→R2。最後に **R3**: mode 対応経路で生成し、slide は UI/print、report は `report-quality-reviewer` RQ1〜RQ34 と report visual gate で補正する。`deck-evaluator` は D5 読者フックを含む mode-aware 評価を行い、FAIL は最大3周 reloop。完成判定は実体で行い、親へ成果物パス・評価スコア・未達指摘だけを返す。前置き禁止。

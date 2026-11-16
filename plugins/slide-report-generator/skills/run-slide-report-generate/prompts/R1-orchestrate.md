# Prompt: R1-orchestrate

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> 本 prompt は主オーケストレータの実行 SSOT。SKILL.md は router 要約、本 prompt は
> R1→R6 の完全駆動契約 (agent/script/schema/reference を実体参照)。R1–R3 で成果物を作り、
> R4 で提示、R5 で利用者が選び、diagnose のときだけ R6 で評価と改善を行う。

## メタ

| key | value |
|---|---|
| name | orchestrate |
| skill | run-slide-report-generate |
| responsibility | R1-orchestrate (1 prompt = 1 責務 = 主オーケストレータ。15 agent を Task name 起動で統率) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../../schemas/structure.schema.json (slide) / ../../../schemas/report-structure.schema.json (report) |
| reproducible | true (mode 値域検証・仕様確定ゲート・最小guard と、diagnose 後の R6 の生成後評価は決定論ゲートで停止条件を機械化) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **スライド／レポートの新規生成**を単一 skill で駆動する主オーケストレータである。ヒアリング → 構成 → 仕様確定ゲート → 生成 → UI 検証 → 生成後評価の流れを、**R1–R3** (生成と最小guard まで) と **R4 提示 → R5 選択 → R6 選択後評価** の 6 段で駆動する。UI 検証と生成後評価は、利用者が R5 で diagnose を選んだときだけ R6 で走らせる。
- **意匠／技術コアは単一 SSOT で共有**し、**コンテンツ意図だけを `output_mode`(slide／report) で分岐**する。意匠を mode ごとに二重定義しない。
- 全実行パスは plugin root = `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}` 起点。vendor script = `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/…`、plugin-root glue = `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/…`。**repo-root ハードコード禁止** (配置非依存)。
- 参照 agent は **Task の name で起動**する (ファイルパス依存なし)。各 agent は独立 context (isolation) で自身の 7 層本文に従う。

### 1.2 倫理ガード / 越境禁止
- 本 skill は **新規生成のみ**。既存成果物の局所修正は `run-slide-report-modify` へ、シリーズ横断の整合検証は `run-cross-deck-review` へ委譲する (責務越境禁止)。
- 完成判定は実体で行う。`echo`／ファイルサイズ／"PASS" 文字列で完成判断しない。ファイルは Read、画像は PNG/WebP 署名で検証する。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: **R1** ヒアリングで `output_mode`(slide／report) を確定し下流全 agent へ一貫伝播 → **R2** 確定 mode で構成を設計し仕様確定ゲートで R3 進入を制御 → **R3** 生成経路で成果物を生成し、最小guard (parse/open・空/破損・secret 混入・不可逆処理) だけを通す → **R4** 現物の path・digest・開き方と、R2 の WARN と各 worker の仮定一覧を提示 → **R5** accept-as-is / diagnose を 1 回だけ聞く → **R6** (diagnose のときだけ) 品質 reviewer と生成後評価 (30 種思考法) で所見を出し、所見の提示後に改善の深さを 1 回だけ聞いて、選んだ深さの周回上限まで改善と再評価を回す。
- 非担当: 既存修正 (`run-slide-report-modify`)、横断整合 (`run-cross-deck-review`)。

### 2.2 ドメインルール (output_mode 分岐契約)
- **共有 SSOT (mode で重複させない)**: 配色トークン ／ 16:9 ／ 最小 1.4rem ／ GSAP ／ インライン SVG2 ／ 印刷 CSS ／ letterbox ／ Codex Image2 ／ style genome ／ 決定論レンダラ ／ `theme`・`aiVisual` schema `$defs`。
- **共有コンテンツ契約**: hearing-facilitator が作る読者価値ブリーフ（対象範囲・共有課題/願望・読後/視聴後の変化・専門の橋・深さの証拠・正式タイトル制約）を R1→R2→R3 へ一貫伝播する。下流は既存 schema の title/audience/keyMessage/throughLine/sections へ翻訳し、schema 外フィールドや素材にない数字・実績を発明しない。
- **mode 別 (コンテンツ意図のみ分岐)**:
  - `slide`: 1 スライド 1 メッセージ ／ chip 強制 ／ 長文禁止 ／ 16:9 ／ <!-- count: slideType -->107 slideType ／ `../../../schemas/structure.schema.json`。
  - `report`: 読み物 (文章多め可) ／ セクション＋段落 ／ 1 項目 1 ビジュアル最適化 ／ HTML レポート ／ 4 reportType ／ `../../../schemas/report-structure.schema.json` (`sections[]` 主配列・structure と共通コア `$defs` 共有)。
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
- **構造 JSON**: slide=`structure.json` (`../../../schemas/structure.schema.json` 準拠) ／ report=`report-structure.json` (`../../../schemas/report-structure.schema.json` 準拠)。
- **成果物**: slide=`<out-dir>/index.html`(+`styles.css`/`scripts.js`) ／ 決定論経路は `render-slide.cjs` 出力先 ／ report=`<out-dir>/report.html`。
- **生成後評価 (diagnose のときだけ)**: `<out-dir>/evaluation-report.json` / `.md` (R6 の `evaluate-deck.js` 出力)。accept-as-is では作らない。
- **生成レポート** (親へ返す・`../schemas/generation-report.schema.json` 準拠): `output_mode` ／ `route` (生成経路) ／ `artifacts` (生成物パス) ／ `open_instructions` (開き方) ／ `assumptions[]` ／ `user_choice` (R5 の `choice` と、diagnose のときの `depth`)。`assumptions[]` には、R2 の WARN と、各 worker が返した仮定一覧 (項目・置いた値・根拠) を本 prompt が集めて入れる。各要素は `item`・`value`・`basis`・`source_worker` で、仮定が無ければ空配列にする。diagnose のときだけ、生成後評価スコア (`artifacts` の `evaluation-report`) と未達指摘一覧 (`findings[]`) も加える。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース (skill 私有 references 12 本 + resource-map + plugin schemas + slide ひな形資産)

| id | path | when_to_read | owner_agent |
|---|---|---|---|
| information-priority-rules | references/information-priority-rules.md | **構成設計に着手する前** (両 mode 共通)。情報優先度の宣言 (文脈→棚卸し→グループ化→順位→削減→加工→形式選定→強弱→意味的装飾) の SRG 写像と生成前ゲート。原理の正本は本 plugin の外 (`system-spec-harness/skills/ref-system-design-knowledge/references/information-design.md` (plugin 名から始まる path)) でここは写像のみ | structure-designer / report-structure-designer |
| structure-design-rules | references/structure-design-rules.md | slide 構成設計 (1スライド1メッセージ分解・共通仕様セクション・slideType 判定) | structure-designer |
| report-structure-types | references/report-structure-types.md | report 4 reportType 骨格 | report-structure-designer |
| d3-diagram-rules | references/d3-diagram-rules.md | D3 インタラクティブ図解の意匠/実装規範 | d3-diagram-designer |
| data-visualization-rules | references/data-visualization-rules.md | データ可視化 (グラフ/chart) 設計規範 | data-visualizer |
| html-generation-rules | references/html-generation-rules.md | slide HTML LLM 経路生成規範 (CONST_001-039) | html-generator |
| layout-optimization-rules | references/layout-optimization-rules.md | レイアウト最適化 (横=文字数・カード/フォント・印刷 pt 換算 / 縦=内容高ブロック・残余の外側余白・高さ牽引・読み取り用画像・浮遊UI) | layout-optimizer |
| ui-quality-checklist | references/ui-quality-checklist.md | slide UI 品質 S 系観点定義・判定基準 | ui-quality-reviewer |
| report-quality-checklist | references/report-quality-checklist.md | report 品質観点 必須 RQ1〜RQ34 + 図解を含む節のみ RQ35〜RQ37 (読み物文体/段落密度/1項目1ビジュアル/reportType 骨格/読者中心入口/図解の溶け込み) | report-quality-reviewer |
| deck-evaluation-rubric | references/deck-evaluation-rubric.md | 生成後評価 (30 種思考法 mode-aware rubric・評価次元) | deck-evaluator |
| ai-image-pipeline | references/ai-image-pipeline.md | Codex Image2 全面画像/差替パイプライン規範 | ai-image-diagram-producer |
| visual-generation-rules | references/visual-generation-rules.md | 視覚生成の規約 (E1-E6・カードの分岐・§4.1 図解被覆 DC1-DC6)。R2 の構成段階の被覆判定と diagnose 後の R6 の成果物判定で使う。E1-E6 の閾値は `validate-visual-generation.py` が実行時にこの本文から読み、`validate-diagram-coverage.py` は §4.1 を正本として実装する | structure-designer |
| resource-map | references/resource-map.yaml | reference の帰属・progressive disclosure マップ (lint-reference-attribution.py 網羅性検査)。この名前のファイルは skill ごとに 1 本あり、ここで読むのは **本 skill (run-slide-report-generate) 配下のもの** で、他 skill の同名ファイルは対象外 (lint も skill 単位で各自の 1 本を見る) | (map) |
| schema-structure | ../../../schemas/structure.schema.json | slide 入力契約 (<!-- count: slideType -->107 slideType, `$defs`) | structure-designer / structure-validator |
| schema-report-structure | ../../../schemas/report-structure.schema.json | report 入力契約 (`sections[]`・共通コア `$defs`) | report-structure-designer / structure-validator |
| slide-skeleton-registry | ../../../assets/slide-templates/registry.json | slide の面を 1 枚でも書く前に必ず読む。slideType → ページひな形 + media 種別の写像 (推測でひな形を選ばない)。slideType を持たない面は同ファイルの `structural_pages` / `role_pages` から役割名で引く (役割名の一覧は registry.json 自身が正本。散文へ写さない)。`media_override` は差し込み物が codex-image のときだけ `layout-image-full`/`layout-image-side`/`layout-image-grid` へ載せ替える | html-generator / slide-renderer / structure-designer |
| slide-frame-contract | ../../../assets/slide-templates/frame-contract.json | 面の寸法の唯一の正本 (canvas/chrome/stage/spacing/typography/fill/print)。面ごとに座標・font-size を直書きしない | html-generator / slide-renderer / layout-optimizer / ui-quality-reviewer |
| slide-skeleton-guide | ../../../assets/slide-templates/README.md | ひな形 <!-- count: slideSkeleton -->22 種の用途と受け入れる差し込み物、autofit 下限、A4 印刷倍率の根拠を引くとき | html-generator / slide-renderer / ui-quality-reviewer |

### 3.2 外部ツール / agent / scripts

**統率する agent (Task の name で起動・15 体)**:
- R1: `hearing-facilitator` (mode・読者価値ブリーフを推定/確定、`isolation: inherit` で会話履歴保持)。
- R2: `structure-designer` (slide) ／ `report-structure-designer` (report) ／ `d3-diagram-designer` ／ `data-visualizer` ／ `visual-strategist` (report の 1 項目 1 ビジュアル三択) ／ `structure-validator` (仕様確定ゲート)。
- R3: `html-generator` (slide LLM 経路) ／ `slide-renderer` (slide 決定論経路) ／ `report-composer` (report 経路) ／ `ai-image-diagram-producer` (画像明示時)。R3 で起動するのは成果物を作る agent だけ。
- R4 提示と R5 選択: agent を起動せず、本 prompt 自身が行う。
- R6 (diagnose のときだけ): **所見を返す** `ui-quality-reviewer` (slide) ／ `report-quality-reviewer` (report。読み物文体・段落密度・1項目1ビジュアル整合・reportType 骨格順守) ／ `deck-evaluator` (両 mode。生成後評価 30 種思考法・mode-aware)。**所見を受けて直す** R3 の生成担当 — `html-generator` (slide LLM 経路) ／ `slide-renderer` (slide 決定論経路。structure.json を直して再生成) ／ `report-composer` (report)、画像明示時は `ai-image-diagram-producer` — と、`layout-optimizer` (slide のレイアウト崩れを custom.css で直す)。起動順と振り分けの正本は SKILL.md「R4–R6」節の「R6 の 1 周の順番 (正本)」。

**plugin-root glue (Bash python3)**:
- `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/setup-playwright.py --install` — 初回/更新後にlockfile依存とOS/CPU別Chromiumをplugin-local `vendor/playwright-browsers/`へ復元。続く `validate-output-mode.py --preflight` は node/npm/browser/codex CLI を fail-soft 検出する。
- `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-report-visual.py <report.html> --structure <report-structure.json> --require-structure --json` — report 決定論視覚ゲート (diagnose 後の R6 で実行。report gate は構造正本必須・欠落 exit 2、section 構造/1項目1ビジュアル/段落密度/placeholder/印刷・0=PASS/1=崩れ/2=usage)。slide の `verify-slides.js`/`validate-print.js` に対称な report 版。
- `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-slide-skeleton.py` — ページひな形資産の契約検査 (S1 写像の全被覆 / S2 孤児・index ずれ / S3 media 種別 / S4 生成物の手編集検出 (html/css/js) / S5-S7 寸法・A4 印刷 / S8-S10 構造・ナビ・書体下限 / S11 色の 16 進直書き。0=PASS)。ひな形 HTML・`slide-skeleton.css`・`slide-skeleton.js`・`frame-contract.json`・`registry.json` のいずれかを触ったときに実行する (R3 の最小guard と並べて通す)。

**vendor scripts (Bash node・`${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/…`・byte 携行/書換禁止)**: 走らせる段は行末の括弧のとおり。R6 の script は diagnose を記録したときだけ走らせる。
- `validate-structure.js` — 構成の仕様確定ゲート (`V_DEFINITIONS` 全件・spec-registry SR-ID 連動) (R2)。
- `validate-d3.js` — D3 図解設定の検査 (`<d3-config.json>` を渡す・0=PASS/4=VALIDATION_FAILED)。path を渡さないと何も検査せず exit 0 になるので、d3-diagram-designer が返した config の path を必ず渡す。見るのは `data` の有無までで、期待形 (配列/階層/nodes+links) は d3-diagram-designer が Read で確かめる。exit 4 なら指摘を添えて d3-diagram-designer へ最大 2 回直させ、なお 4 なら止める (R2・D3 図解があるとき)。
- `render-slide.cjs` — slide 決定論レンダラ (再現性 100%) (R3)。
- `render-report.js` — report.html 決定論生成 (R3)。
- `mermaid-render.js` — report で mermaid を選んだ節の図の描画 (R3)。
- `verify-slides.js` — slide UI 品質 (テキスト切れ・16:9 比率) (R6)。report は上記 glue `validate-report-visual.py` が対称ゲート。
- `evaluate-deck.js` — 生成後評価オーケストレータ (D1 視覚崩れ/D2 文字サイズ/D3 ナビ/D4 仕様適合・0=PASS/4=FAIL) (R6)。
- `validate-print.js` — 印刷 letterbox (@media print 内 cover を CRITICAL 検出) (R6)。
- `verify-report-runtime.js` — report の実描画 runtime 検査 (R6)。
- `build-image-prompts.js` → `generate-images-codex.js` → `build-deck-html.js` — 全面画像導線 (`meta.source=codex-image2`・PNG 署名回収＋リトライ・自己完結 index.html) (R3・画像明示時)。
- `validate-ai-image-assets.js` — prompt/meta/WebP 整合と style genome 反映検査 (R6・画像明示時)。
- `precheck-layout.js` ／ `layout-calculator.js` — 全スライド一括のレイアウト判定と、単一構造ファイルのレイアウト計算 (R6・`layout-optimizer` が実行)。
- `check-consistency.js` — カラー・フォント・スタイルの統一感検証 (R6・`ui-quality-reviewer` が実行)。
- `phase-gate.js` — P2→P3 の `.approved` ゲート (R2・利用者が構成レビューを明示的に求めた回だけ `structure-validator` が実行)。
- `build-single-html.js` — 分離形式から GAS 用 1 ファイル HTML を作る (R3・1 ファイル化が要るときだけ本 prompt が実行)。
- `workflow-manager.js` — 状態確認 (`<out-dir> --check --next`) (どの段でも)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `validate-output-mode.py` が mode 値域外 / report で report-type 欠落 or 値域外 / slide で report-type 指定 → **exit 2 (fail-closed)**。伝播せず即停止し stderr の逸脱項目をユーザー提示。LLM 推測補完禁止。
- `validate-structure.js` の仕様確定ゲート判定: **PASS→R3** ／ **WARN→該当 ID を仮定として記録して R3 へ進み、R4 の提示に明記** (成果物を出す前の承認質問にしない) ／ **FAIL→R2 設計へ最大 1 周差し戻し** (structure-designer / report-structure-designer 再設計)。差し戻した 1 周でも FAIL なら、逸脱 ID を提示して止める。
- R3 の最小guard (parse/open・空/破損・secret 混入・不可逆処理) が落ちた成果物は R4 で提示しない。落ちた guard と理由を提示して止める。
- (R6・diagnose のときだけ) `evaluate-deck.js` が **exit 4 (FAIL)** → 未達指摘を findings 化して所見として提示し、利用者が選んだ深さの範囲だけ生成/品質補正へ反映して再評価する (周回上限は 4.4)。`verify-slides.js`/`validate-print.js` の視覚崩れ CRITICAL も同様に R6 の所見へ入れる。accept-as-is ではどれも走らせない。
- **codex は画像生成器ではない**: `ai-image-diagram-producer` 起動時は着手前に実 text-to-image backend を確認する。`meta.source` は実体名 `codex-image2` を記録し plain `codex` は不可。
- 環境エラーは `--preflight` で検出する。node/npm不在は停止、plugin-local Chromium欠落は `setup-playwright.py --install` を1回実行して再検査、codex CLI不在は画像明示時のみ停止する。mode 検証は常に fail-closed。

### 4.2 観測 / ロギング
- 進捗・次アクションは `node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/workflow-manager.js" <out-dir> --check --next` で確認。この script は vendor 由来 (byte 携行・書換禁止) で、P2→P3 に `.approved` を求める旧い P 段の数え方を持つ。既定経路では `.approved` を作らないので「`.approved` マーカー未取得」と出るが、止まる理由にしない (`.approved` は利用者が構成レビューを明示的に求めた回だけ structure-validator が作る)。
- diagnose 後の R6 の生成後評価は `<out-dir>/evaluation-report.json` / `.md` に残す。未達は生成レポートの「未達指摘一覧」へ列挙する。accept-as-is では評価ファイルを作らない。

### 4.3 配置非依存 / セキュリティ
- 全パスは `${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}` 起点。repo-root 直書き禁止。
- 全面画像デッキは CSS/JS を `<style>`/`<script>` にインライン化した自己完結 HTML (`build-deck-html.js`)。別ファイル版は環境で消失しページ送り不可事故になりうる。

### 4.4 最大反復回数
- R6 の改善周回 (inner: 改善→再評価) の上限は、所見の提示後に利用者が 1 回だけ選ぶ深さで決まる: `findings-only` 0 周 ／ `light` 1 周 ／ `standard` (既定) 2 周 ／ `detailed` 3 周。正本は `workflow-manifest.json` の `R6-selected-semantic-review.depth_choice` で、manifest の `max_iterations` = **3** はその最大値。accept-as-is では 0 周で、R6 に入らない。`goal_seek.max_loops` = **5** (outer)。ループ本体は親セッションで回さず `Task` で SubAgent へ fork し (`goal_seek.fork: subagent`)、親へは最終成果物パスと生成レポートのみ返す。上限超過時は未達指摘一覧として生成レポートへ残す。goal-seek の `max_loops` は外枠で、R6 で選んだ深さを超える周回を足さない (findings-only では手を入れない)。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- 本 prompt 自体が**主オーケストレータ**。R1–R3 と R6 で上記 15 worker agent を Task name 起動で統率し (R4 提示と R5 選択は本 prompt 自身が行う)、決定論ゲート (R1 `validate-output-mode.py` ／ R2 `validate-information-priority.py`・`validate-structure.js`・`validate-d3.js` (D3 図解があるとき) ／ R3 最小guard ／ R6 `evaluate-deck.js`) を停止条件とする。

### 5.2 ゴール定義
- 目的: `output_mode` と読者価値ブリーフを確定し意匠／技術コアを共有したまま、**構成設計 → 仕様確定ゲート → 生成と最小guard → 提示**まで駆動し、利用者が diagnose を選んだときだけ**生成後評価と改善**へ進む。両 mode とも「想定読者の共有課題→読者の変化→専門的で具体的な解決→自分へ移す行動」を持ち、slide は「1 スライド 1 メッセージ／長文なし」、report は「読み物・1 項目 1 ビジュアル」で視覚崩れ 0 を目指して作る (視覚崩れの判定は diagnose 後の R6)。
- 背景: 意匠を mode ごとに二重定義すると SSOT が破綻し再現性を失う。mode を送信前に fail-closed 検証せず下流へ流すと仕様確定ゲート入力が欠落し手戻りする。

### 5.3 完了チェックリスト (停止条件)

**初回 handoff (R1–R5)**:
- [ ] `output_mode` と (report 時) `reportType` が確定し `validate-output-mode.py` の値域検証 (exit 0) を通過
- [ ] 読者価値ブリーフの6項目が入力素材に基づく値または「未確認」で確定し、mode/reportType/読者/長さ/ビジュアル方針とともに下流 R2/R3 へ一貫伝播している
- [ ] **構成着手前**に designer が `information-priority-map.json` を出力し、本 prompt が回す `validate-information-priority.py` が exit 0 (IN2: 順位の確定が強弱・装飾の宣言に先行し、削減/加工に理由があり、形式候補を 2 件以上比較し、色単独で意味を担わせていない)
- [ ] 構成設計 (structure.json / report-structure.json) が該当 schema に準拠
- [ ] 入口が想定読者の共有課題と変化を先に渡し、本論に確認済みの数字・手順・失敗・条件・限界があり、各主要セクションに自分へ移す橋がある。正式名称・検索性が必要な文書は主タイトルを維持している
- [ ] 仕様確定ゲート (`structure-validator` + `validate-structure.js`) が PASS (WARN は仮定として記録し R4 の提示に明記 / FAIL なし)
- [ ] 生成経路 (slide LLM / slide 決定論 / report / 画像明示) で成果物 (`index.html` / `report.html`) を生成
- [ ] 全面画像時は `meta.source=codex-image2` で自己完結 HTML を生成
- [ ] R3 の最小guard (parse/open・空/破損・secret 混入・不可逆処理) が PASS。品質 reviewer と `deck-evaluator` は起動していない
- [ ] R4 で現物の path・digest・開き方と、R2 の WARN と各 worker が返した仮定一覧 (項目・置いた値・根拠) を集めて提示し、R5 で accept-as-is / diagnose を 1 回だけ記録した (accept-as-is はここで完了・evaluator 0 / improver 0)

**diagnose を記録したときだけ (R6)**:
- [ ] 全面画像時は `validate-ai-image-assets.js` PASS
- [ ] `verify-slides.js --check-ratio` / `validate-print.js` の視覚崩れが 0 (CRITICAL なし)
- [ ] slide 経路で `ui-quality-reviewer` を起動済み (必須)。`validate-slide-layout.js` が error を出した面・崩れ検出面が選んだ深さの範囲にあれば、② で `layout-optimizer` も起動済み
- [ ] 所見は本 prompt が宛先ごとに振り分けて直させ、reviewer と `deck-evaluator` には直させていない (順番は SKILL.md「R4–R6」節の「R6 の 1 周の順番 (正本)」)
- [ ] `deck-evaluator` の mode-aware 生成後評価 (30 種思考法) を行い、所見を提示してから改善の深さを 1 回だけ聞いた
- [ ] 選んだ深さの周回上限 (0〜3 周) の中で改善と再評価を行い、残った未達を未達指摘一覧に残した

**常に**:
- [ ] 完成判定を実体 (Read / PNG・WebP 署名 / スクショ目視) で行い、echo・サイズ・文字列で判断していない
- [ ] 責務外 (既存修正 / 横断整合) に踏み込んでいない

### 5.4 実行方式 (決定論)
- **mode と読者価値を先に確定する**: R1 で `hearing-facilitator` が `output_mode`/読者価値ブリーフ/`reportType`/読者/長さ/ビジュアル方針を確定 → mode 値域を `validate-output-mode.py` で fail-closed 検証。exit 0 で一式を下流全 agent へ一貫伝播し、素材にない数字・実績は未確認のまま渡す。
- **構成着手前に情報優先度を確定する (両 mode 共通)**: `structure-designer` / `report-structure-designer` は構成へ入る前に `information-priority-map.json` (`${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/schemas/information-priority-map.schema.json` 準拠) を構成より先に出力する。designer は Bash を持たないので、`python3 "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/scripts/validate-information-priority.py" <出力先>/information-priority-map.json` は本 prompt が R2 で回し、exit 0 を確かめるまで structure-validator へ進めない。exit 1 なら違反の出力を添えて designer へ 1 回だけ差し戻し、直してなお exit 1 なら違反を提示して止める (exit 2 は usage・環境の誤りとして止める)。順位を決める前に強弱・装飾を宣言した構成は、後から「なぜこれが目立つのか」を説明できず、レビューが主観の応酬になる。
- **構成設計は mode 分岐で dispatch する**: slide=`structure-designer` ／ report=`report-structure-designer` + `visual-strategist`。両者は読者価値ブリーフを既存 schema フィールドへ翻訳し、入口ホリゾンタル・中身バーティカル・主要セクションの自分ごと化を設計する。
- **仕様確定ゲートで R3 進入を制御する**: `structure-validator` を起動し `node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/validate-structure.js" <structure|report-structure>` を実行。PASS→R3 / WARN→仮定として R3 へ進み R4 の提示に明記 / FAIL→R2 へ最大 1 周差戻し (それでも FAIL なら逸脱 ID を提示して止める)。
- **生成経路を mode／指示で選択する**: slide LLM=`html-generator` ／ slide 決定論 (推奨)=`slide-renderer`+`render-slide.cjs` ／ report=`report-composer`+`render-report.js` ／ 画像明示=`ai-image-diagram-producer` (`build-image-prompts.js`→`generate-images-codex.js`→`build-deck-html.js`)。生成した成果物には最小guard だけを掛ける。
- **R4 で提示し、R5 で 1 回だけ聞く**: 最小guard PASS の成果物の path・digest・開き方と、R2 の WARN と各 worker が返した仮定一覧 (項目・置いた値・根拠) を集めて提示し、現状で試す (accept-as-is) か診断する (diagnose) かを聞く。accept-as-is ならここで handoff を終える。
- **R6 の品質補正は mode 対称 (diagnose のときだけ)**: 所見を返すのは slide=`ui-quality-reviewer` (**必須**) ／ report=`report-quality-reviewer` (読み物文体・段落密度・1項目1ビジュアル整合・reportType 骨格順守)。`layout-optimizer` は所見を受けて直す担当で、`validate-slide-layout.js` の error または `ui-quality-reviewer` の崩れ検出が選んだ深さの範囲にある面で**必須**。**R6 で slide 側を「必要に応じ」にしない** — 縦方向の停止条件 (充填率・外側余白率・残余の置き場所) を完了チェックリストに持つのはこの 2 agent だけで、呼ばれなければそのチェックリストは 1 項目も発火しない。
- **R6 の生成後評価は mode-aware で回す**: `deck-evaluator` を思考リセット後 30 種思考法で起動。slide=視覚崩れ/1 メッセージ、report=可読性/図解適合/情報密度の mode 別 rubric 次元で区分評価する。所見を提示してから改善の深さを 1 回だけ聞き、改善→再評価は選んだ深さの周回上限 (0〜3 周) まで。
- ループは分離 context で完結させ、親へは最終成果物パス + 生成レポート + exit code のみ返却する。

## Layer 6: オーケストレーション層

### 6.1 上位 skill / 委譲境界
- 呼び出し: ユーザー直接起動 (user-invocable) または上位ワークフロー。
- 委譲: 既存成果物の局所修正=`run-slide-report-modify` ／ シリーズ横断整合=`run-cross-deck-review`。本 skill は新規生成に限定。

### 6.2 ハンドオフ / 並列性 (R1 → R6 の agent dispatch)
- **R1 → R2**: 確定 mode 一式と読者価値ブリーフを全下流 agent の入力へ接続。伝播前に `validate-output-mode.py` で mode 値域を検証し、ブリーフは schema 外フィールドとして構造 JSON に混入させない。
- **R2 内**: `structure-designer`/`report-structure-designer` の構成 JSON を `structure-validator` の仕様確定ゲート入力へ。図解 agent (`d3-diagram-designer`/`data-visualizer`/`visual-strategist`) は構成設計に併走。
- **R2 → R3**: ゲート PASS (WARN は仮定つき) の構成 JSON を生成 agent の入力へ。
- **R3 内**: 生成 agent の成果物に最小guard だけを掛ける。品質補正 agent と `deck-evaluator` はここでは起動しない。
- **R3 → R4 → R5**: 最小guard PASS の成果物を提示し、accept-as-is / diagnose を 1 回だけ聞く。accept-as-is ならここで handoff を終える。
- **R5 → R6 (diagnose のときだけ)**: 1 周の順番 (① reviewer と `deck-evaluator` が所見を返す → ② 本 prompt が宛先ごとに振り分けて直させる → ③ 次の周で reviewer が再検証する) の正本は SKILL.md「R4–R6」節の「R6 の 1 周の順番 (正本)」 で、ここには写さない。本 prompt が守る規則は次の 4 つ (正本は同じ節)。
  - 周回数は R6 全体で 1 つを共有し、worker には残りの周回数を渡す。worker ごとに上限を持たせない。
  - 所見は宛先ごとに振り分ける (slide のレイアウト崩れ=`layout-optimizer`、それ以外の slide=R3 の生成担当、report=`report-composer`)。reviewer と `deck-evaluator` には直させない。宛先が R2 の構成担当の所見は直さず、未達指摘一覧に載せる。
  - R6 で選んだ深さが適用の承認にあたるので、周回の途中で承認を取り直さず、利用者にも聞かない。
  - 修正のたびに承認を取る `slide-report-modifier` は `run-slide-report-modify` の担当で、R6 の周回に入れない。
- **worker → 本 prompt (R2・R3・R6)**: 各 worker は返答に仮定一覧 (項目・置いた値・根拠) を付けて返す。本 prompt は R2 の WARN とあわせて集め、生成レポートの `assumptions[]` (`source_worker` に返した worker 名) に入れて R4 で提示する。
- **並列性**: 各 worker agent は独立 context (isolation) で fork。goal-seek ループ本体も SubAgent へ fork し親を汚さない。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- R4 の提示: `output_mode` ／ 生成経路 ／ 生成物パス (slide=`index.html` / report=`report.html`) ／ digest ／ 開き方 ／ 仮定一覧 (R2 の WARN と、各 worker が返した仮定 (項目・置いた値・根拠) を本 prompt が集めたもの)。続けて R5 で、現状で試す (accept-as-is) か診断する (diagnose) かを 1 回だけ聞く。
- R6 の提示 (diagnose のときだけ): 所見の一覧を出してから改善の深さを 1 回だけ聞き (選択肢と周回上限は 4.4)、最後に生成後評価スコア ＋ 生成物パス ＋ 未達指摘一覧を返す。

### 7.2 言語
- 本文: 日本語 (`output_language: ja`)。

---

## Self-Evaluation

「段」が R1–R5 の行は R4 の提示前に、R6 の行は diagnose を記録したときだけ自己確認する。R1–R5 の行の未達は提示前に直すか止める。R6 の行の未達は所見として提示し、利用者が選んだ深さの範囲で findings を反映して再評価する。

| 観点 | 段 | 確認内容 | 判定 |
|---|---|---|---|
| mode 値域/伝播 | R1–R5 | `validate-output-mode.py` PASS / 確定 mode が全下流 agent へ伝播し仕様確定ゲート入力欠落 0 (IN1) | PASS/FAIL |
| 読者価値/深さ | R1–R5 | 読者価値ブリーフが R1→R2→R3 で保持され、入口・本文の深さ・自分へ移す橋へ反映。正式名称/検索性と事実性を毀損していない | PASS/FAIL |
| 情報優先度 | R1–R5 | 構成着手**前**に `information-priority-map.json` を出力し、本 prompt が回す `validate-information-priority.py` が exit 0 (IN2・差し戻しは 1 回まで) | PASS/FAIL |
| 構成適合 | R1–R5 | 構成 JSON が該当 schema 準拠 / 仕様確定ゲート (`validate-structure.js`) PASS (WARN は仮定として R4 の提示に明記) | PASS/FAIL |
| 生成完全性 | R1–R5 | 生成経路で成果物を生成し R3 の最小guard PASS / 画像明示は `meta.source=codex-image2` |
| 提示と選択 | R1–R5 | R4 で現物の path・digest・開き方を提示し、R5 で accept-as-is / diagnose を 1 回だけ記録。accept-as-is は evaluator 0 / improver 0 | PASS/FAIL |
| 視覚崩れ 0 | R6 | `verify-slides.js`/`validate-print.js` CRITICAL 0 / slide=1 メッセージ・report=1 項目 1 ビジュアル / 画像明示は `validate-ai-image-assets.js` PASS | PASS/FAIL |
| 生成後評価 | R6 | `deck-evaluator` 30 種思考法 mode-aware rubric で評価し所見を提示してから深さを 1 回だけ聞いた / 選んだ周回上限の中で再評価した (`evaluate-deck.js` exit 0 を目標) (OUT1) | PASS/FAIL |
| 責務境界 | 常に | 既存修正 / 横断整合へ越境していない / 完成判定を実体で行った | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

まず **R1**: `Task` で `hearing-facilitator` を起動し、`output_mode` と読者価値ブリーフ（対象範囲/共有課題・願望/読後・視聴後の変化/専門の橋/深さの証拠/正式タイトル制約）を確定する。report なら `reportType`/読者/長さ/ビジュアル方針も確定し、mode 値域を `validate-output-mode.py` で検証する。素材にない数字・実績は作らず未確認とする。次に **R2**: slide は `structure-designer`、report は `report-structure-designer` + `visual-strategist` を起動する。**構成へ入る前に** designer が `information-priority-map.json` を出力し、本 prompt が `validate-information-priority.py` を回す (IN2。exit 1 なら 1 回だけ差し戻し、なお exit 1 なら止める)。D3 図解があるときは `validate-d3.js <d3-config.json>` も本 prompt が回す。その上でブリーフを既存 schema の title/audience/keyMessage/throughLine/sections へ翻訳する。入口は想定読者の共有課題と変化を先に渡し、本論は確認済みの数字・手順・失敗・条件・限界まで掘り、各主要セクションに自分へ移す橋を置く。正式名称・検索性・適用範囲が必要なら主タイトルを保持する。`structure-validator` で PASS→R3 / WARN→仮定として R3 へ進み R4 の提示に明記 / FAIL→R2 へ最大 1 周 (それでも FAIL なら止める)。次に **R3**: mode 対応経路で生成し、最小guard (parse/open・空/破損・secret 混入・不可逆処理) だけを通す。品質 reviewer と `deck-evaluator` はここで起動しない。**R4**: 現物の path・digest・開き方と、R2 の WARN と各 worker が返した仮定一覧 (項目・置いた値・根拠) を集めて提示する。**R5**: 現状で試す (accept-as-is) か診断する (diagnose) かを 1 回だけ聞き、accept-as-is ならここで終える。diagnose のときだけ **R6**: slide は UI/print、report は `report-quality-reviewer` の必須 RQ1〜RQ34 (図解を含む節は RQ35〜RQ37 も) と report visual gate で補正点を洗い出し、`deck-evaluator` で D5 読者フックを含む mode-aware 評価を行う。所見を提示してから改善の深さを 1 回だけ聞き、選んだ深さの周回上限 (0〜3 周・R6 全体で共有) まで、SKILL.md「R4–R6」節の「R6 の 1 周の順番 (正本)」 に従って所見を宛先ごとに振り分けて直させ、再評価する。完成判定は実体で行い、親へ成果物パスと、diagnose のときは評価スコア・未達指摘を返す。前置き禁止。

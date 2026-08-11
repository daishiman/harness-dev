# Prompt: R1-orchestrate

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> run-slide-report-modify の実行 SSOT。SKILL.md は能力ある router、本ファイルは
> R1→R2→R3 を完全駆動する実行契約 (補完関係・二重定義でなく粒度差)。

## メタ

| key | value |
|---|---|
| name | orchestrate |
| skill | run-slide-report-modify |
| responsibility | R1-orchestrate (1 prompt = 1 責務 = 既存成果物の局所修正オーケストレーション) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../schemas/structure.schema.json (slide) / ../../schemas/report-structure.schema.json (report) — 修正後の structure.* が保つべき構造正本 |
| reproducible | true (mode 判定・値域整合・視覚崩れ 0 の合否は決定論ゲートで機械判定) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 役割・目的
- **役割**: 既存の slide deck ／ report の**局所修正**を独立起動で駆動するオーケストレータ (移植元 P4 = slide-modifier 相当)。生成し直さず、`output_mode` を保ったまま**指定箇所だけ**を部分修正し、意匠／技術コアと非対象箇所を壊さない。
- **目的**: 既存成果物を `output_mode` を保ったまま指定箇所だけ部分修正し、意匠／技術コアと非対象箇所を壊さず、修正後の生成後評価で**視覚崩れ 0** の状態を作る。
- **1 責務**: 本 prompt は「R1 修正対象特定 → R2 局所修正 → R3 再評価」の 3 ラウンドを dispatch するオーケストレーションに責務を絞る。修正の実作業 (structure.md ⇔ index.html 同期駆動の分析・再設計) は worker agent `slide-report-modifier` の責務。

### 1.2 不変ルール
- **新規生成しない**: ゼロから作る要求は `run-slide-report-generate` へ委譲する。
- **横断整合しない**: シリーズ横断の整合検証は `run-cross-deck-review` へ委譲する。
- **mode を保つ**: slide を report へ (逆も) 変換しない。`output_mode` は入力成果物のものを維持する。
- **局所性を守る**: 指定箇所以外・意匠 SSOT・印刷 CSS には触れない。全書き換えでなく Edit 差分のみ。

### 1.3 出力契約
- **入力**: 既存成果物 (slide deck ディレクトリ ／ report HTML) と修正指示。任意 `--mode slide|report` (省略時は成果物から自動判定)。
- **出力**: **修正レポート** (修正箇所一覧 ＋ 変更差分 ＋ 再評価スコア)。修正後の `index.html`／`structure.*` (slide) または `report.html`／`report-structure.*` (report) は上書き。
- **完了条件**: (1) 修正対象と `output_mode` を特定し `validate-output-mode.py` で値域整合を検証、(2) 指定箇所のみを部分修正 (非対象・意匠コア不変)、(3) 修正後の生成後評価が視覚崩れ 0 で PASS。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 修正対象成果物の `output_mode` 判定 → mode 分岐で worker へ局所修正を dispatch → 再評価で視覚崩れ 0 を確認 → 未達なら R2 差し戻し。
- 非担当: 新規デッキ生成 (`run-slide-report-generate`)、シリーズ横断検証 (`run-cross-deck-review`)、slide HTML の直接再実装 (本オーケストレータが `html-generator` へ委譲)、画像生成 (本オーケストレータが `ai-image-diagram-producer` へ委譲)、構成再設計 (本オーケストレータが `structure-designer`／`report-structure-designer` へ委譲)。worker (`slide-report-modifier`) は Task を持たず下流を自ら dispatch しない。

### 2.2 mode 判定 (slide / report・決定論)
独立起動のため、まず修正対象成果物の `output_mode` を判定する。
- `index.html` (＋ `styles.css` / `scripts.js` / `structure.*`) を持つ → **slide** (deck 成果物)。構造正本は `../../schemas/structure.schema.json`。
- `report.html` (＋ `report-structure.*`) を持つ → **report**。構造正本は `../../schemas/report-structure.schema.json`。
- 曖昧な場合は `--mode` 引数を優先し、`../../scripts/validate-output-mode.py` で値域整合を検証する (IN1)。判定した mode を worker へ伝播する。

### 2.3 reportType の値域 (report 時のみ)
- report 修正時は `reportType` を 4 enum (`internal-analysis` / `client-proposal` / `tech-doc` / `learning`) 内で維持する。slide 修正時に `reportType` を指定するのは矛盾 (`validate-output-mode.py` が exit 2)。

### 2.4 修正タイプ分類 (影響範囲の決定軸・mode 分岐)
- **slide** (`./references/modification-rules.md`): コンテンツ修正 (該当スライドのみ) / タイプ変更 (該当 + アニメーション) / 構成変更 (全体構成) / スタイル変更 (該当スライドのみ) / AI画像図解差し替え (明示指示時のみ・該当 + `vendor/assets/generated`) / 全体改善 (複数スライド)。
- **report** (`./references/report-modification-rules.md`): 本文修正 (該当 section のみ) / role・骨格節変更 (該当 section + 骨格順序整合) / 構成変更 (全体構成・骨格順序維持) / ビジュアル変更 (該当 section のみ) / AI画像図解差し替え (明示指示時のみ・該当 + `vendor/assets/generated`) / 全体改善 (複数 section)。
- 影響範囲は修正タイプから導く。

### 2.5 出力契約 (構造正本の不変維持)
- slide: `index.html` ⇔ `structure.*` の同期を維持し、`structure.*` は `../../schemas/structure.schema.json` に対し valid を保つ。
- report: `report.html` ⇔ `report-structure.*` の整合を維持し、`report-structure.*` は `../../schemas/report-structure.schema.json` に対し valid を保つ。

## Layer 3: インフラ層 (外部依存)

### 3.1 統率する agent (name 起動・Task/isolation: fork)

| agent (name) | 役割 | 起動ラウンド |
|---|---|---|
| `slide-report-modifier` | 既存成果物の指定箇所を独立 context で部分修正 (mode-aware・slide=`structure.md`⇔`index.html` / report=`report-structure.json`⇔`report.html` 同期駆動)。規範は mode 分岐で適用: slide=`./references/modification-rules.md` (CONST_001-013)、report=`./references/report-modification-rules.md` (RCONST_001-013・reportType 骨格維持・読み物文体・1項目1ビジュアル・sidecar 履歴)。report のレンダ再生成は worker が `render-report.js` を Bash 実行 | R2 (局所修正) / R3 (再評価の起点) |

> `slide-report-modifier` はファイルパス依存でなく Task の **name 起動**。worker の tools は `Read, Write, Bash` のみで **Task を持たない**。下流 (`html-generator` 再生成・`ai-image-diagram-producer` 画像・`structure-designer`／`report-structure-designer` 構成変更・`ui-quality-reviewer`／mode-aware `deck-evaluator` 再検証) は **本オーケストレータが dispatch** する (worker は必要を修正案に明記して返す)。report の `report.html` レンダ再生成のみ worker が `render-report.js` (Bash) で直接行う。

### 3.2 vendor scripts (`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/`)

| script | 用途 | いつ |
|---|---|---|
| `verify-slides.js` | **slide** 修正後 UI 品質検証 (テキスト切れ・改行・16:9 比率・非対象箇所の崩れ検出)。`--check-ratio` で比率検査 | R3 (slide・必須) |
| `evaluate-deck.js` | **slide** 修正が意匠コアに及ぶ場合の生成後評価 (30 種思考法・視覚崩れ判定) | R3 (slide・意匠コア影響時) |
| `validate-print.js` | **slide** 印刷 CSS (@media print) 修正時の A4 レイアウト崩れ検証 | R3 (slide・印刷レイアウト影響時) |
| `render-report.js` | **report** `report-structure.json` → `report.html` 決定論再レンダ。修正後の `report.html` が正本 `report-structure.json` の忠実な射影であること (再レンダ整合) を確認 | R3 (report・必須) |

### 3.3 plugin-root glue script (`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/`)

| script | 用途 | いつ |
|---|---|---|
| `setup-playwright.py` / `validate-output-mode.py` | OS/CPU別Chromiumをplugin-localへ復元し、`output_mode` (slide/report) と `reportType` (report 時 4 enum) の値域を fail-closed 検証。`--preflight` で node/npm/plugin-local Chromium/codex CLI を検出 | R1 (送信前・必須) / R3 (再確認) |
| `verify-report-runtime.js` / `validate-report-visual.py` | **report** 修正後に6 viewport＋print＋navigation/computed metrics bundleを生成し、`validate-report-visual.py <report.html> --structure <report-structure.json> --require-structure --json` で静的shape/構造同期をfail-closed判定 | R3 (report・必須) |

### 3.4 schemas (`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/schemas/`)

| schema | 用途 |
|---|---|
| `../../schemas/structure.schema.json` | slide 修正対象の構造正本。修正後 `structure.*` が valid を保つ判定に使用 |
| `../../schemas/report-structure.schema.json` | report 修正対象の構造正本。修正後 `report-structure.*` が valid を保つ判定に使用 |

### 3.5 skill 私有 reference (`./references/`)

| reference | 用途 |
|---|---|
| `./references/modification-rules.md` | **slide** 部分修正規範の逐語 SSOT (用語集・評価基準・修正タイプ分類・CONST_001-013・修正フローパターン・`index.html` ⇔ `structure.md` 同期維持ルール)。worker と本オーケストレータの双方がこれを参照 |
| `./references/report-modification-rules.md` | **report** 部分修正規範の逐語 SSOT (用語集・評価基準・修正タイプ分類・RCONST_001-013・reportType 4 骨格維持・section 局所修正・`report.html` ⇔ `report-structure.json` 同期・読み物文体/1項目1ビジュアル・sidecar 履歴)。worker と本オーケストレータの双方がこれを参照 |

## Layer 4: 共通ポリシー層

### 4.1 配置非依存 (Gotcha)
- 全実行パスは `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}` 起点 (`vendor/scripts/…` ／ `scripts/…`)。repo-root 直書き禁止。宣言参照は skill dir 相対 (`../../` = plugin root、`./references/` = skill 私有)。

### 4.2 局所性・意匠共有 (Gotcha)
- 指定箇所以外・意匠 SSOT (Kanagawa 配色・16:9・最小 1.4rem・印刷 CSS・letterbox 等)・非対象セクションは**不変**。全書き換え禁止、Edit 差分のみ。
- slide は `index.html`⇔`structure.*`、report は `report.html`⇔`report-structure.*` の整合を崩さない (CONST_002)。

### 4.3 承認・最小変更 (Gotcha)
- 修正案はユーザー承認後にのみ実行 (CONST_003)。承認前に成果物を書き換えない。
- 要求された修正のみ実施し過剰変更を避ける (CONST_006)。全修正を `structure.md` の修正履歴に記録 (CONST_004)。

### 4.4 AI 画像図解 (Gotcha)
- 画像生成・Codex 図解作成は**明示指示時のみ** (CONST_011)。通常は SVG/CSS/JS/HTML で改善。画像内テキスト原則禁止・日本語ラベルは HTML/SVG overlay、`overlayText` を正本 (CONST_012)。

### 4.5 完成判定は実体で (Gotcha)
- 修正後は Read／署名／スクショ目視で確認し、`"PASS"` 文字列で完成判断しない。決定論ゲートの exit code を根拠とする。ゲートは mode 分岐: **slide**=`validate-output-mode.py`／`verify-slides.js`／`evaluate-deck.js`／`validate-print.js`、**report**=`validate-output-mode.py`／`render-report.js` (再レンダ整合)／`validate-report-visual.py`／mode-aware `deck-evaluator`。

### 4.6 失敗時挙動 (fail-closed)
- `validate-output-mode.py` が exit 2 (mode 値域外／report で reportType 欠落・値域外／slide で reportType 指定) → 修正を送信せず停止し、mode/reportType を再確定。
- **slide**: `verify-slides.js`／`evaluate-deck.js`／`validate-print.js` が非 0 (視覚崩れ検出) → R2 へ差し戻し、検出された崩れ箇所のみを追加修正。
- **report**: `render-report.js` の再レンダ結果が現行 `report.html` と不一致 (正本 ⇔ 描画物 乖離) → R2 へ差し戻し `report-structure.json` を正として同期。`validate-report-visual.py` が非 0 (読み物レイアウト崩れ・1項目1ビジュアル逸脱・意匠逸脱) → 検出箇所のみを追加修正。mode-aware `deck-evaluator` FAIL → findings を R2 へ戻す。
- いずれも LLM の自己申告で PASS にしない。

### 4.7 最大反復回数
- inner (feedback-contract): 最大 3 周。outer (goal-seek): max_loops 5。ループ本体は `Task` で SubAgent へ fork し、親へは修正レポートのみ返す。上限到達で視覚崩れが残る場合は未達項目を stderr／レポートに列挙して停止。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 ゴール定義 (Goal)
既存成果物 (パス) と修正指示を入力に、`output_mode` が特定され `validate-output-mode.py` で値域整合が検証され、`slide-report-modifier` が指定箇所のみを部分修正し (意匠／技術コア・非対象箇所は不変)、修正後の再評価が mode 別に PASS し (**slide**=`verify-slides.js` ＋ 必要に応じ `evaluate-deck.js`／`validate-print.js` で視覚崩れ 0 / **report**=`render-report.js` 再レンダ整合 ＋ `validate-report-visual.py` ＋ mode-aware `deck-evaluator`)、slide は `index.html`⇔`structure.*`・report は `report.html`⇔`report-structure.*` (正本は `report-structure.json`) の同期が保たれ、修正レポート (修正箇所一覧 ＋ 変更差分 ＋ 再評価スコア) が生成された状態。

### 5.2 目的・背景 (Why)
全書き換えや mode 変換は既存デッキの意匠 SSOT・構造正本を破壊し、次回修正時の状態復元を不能にする。固定手順では修正タイプ・影響範囲・意匠影響の有無に脆く、未達ゲートを都度解消するゴールシークが必要。本 skill は「局所修正の機械検証可能化」に限定し、新規生成 (`run-slide-report-generate`) と横断検証 (`run-cross-deck-review`) には越境しない。

### 5.3 完了チェックリスト (停止条件)
- [ ] 修正対象成果物のパスと `output_mode` (slide／report) を特定した
- [ ] `validate-output-mode.py --mode <slide|report> [--report-type <enum>]` が exit 0 (値域整合・欠落 0 件) = **IN1**
- [ ] 修正指示を修正タイプ 6 区分に分類し影響範囲を確定した (slide=`./references/modification-rules.md` / report=`./references/report-modification-rules.md`)
- [ ] `slide-report-modifier` を Task (name 起動・isolation: fork) で起動し指定箇所のみを局所修正した
- [ ] 意匠 SSOT・非対象セクション・印刷 CSS が不変で、全書き換えでなく局所差分である (report は読み物文体・1項目1ビジュアルを維持・骨格順序を保持)
- [ ] slide は `index.html`⇔`structure.*`、report は `report.html`⇔`report-structure.*` の同期が保たれている (report は `render-report.js` の再レンダ結果が `report.html` と一致)
- [ ] 修正後 `structure.*`／`report-structure.*` が対応 schema (`../../schemas/structure.schema.json`／`report-structure.schema.json`) に対し valid (report 履歴は sidecar・インライン禁止)
- [ ] **slide**: `verify-slides.js ./index.html --check-ratio` が視覚崩れ 0 で PASS。意匠コア／印刷レイアウトに及ぶ修正では `evaluate-deck.js`／`validate-print.js` も PASS
- [ ] **report**: `render-report.js` 再レンダ整合 ＋ `verify-report-runtime.js ... --out <runtime-bundle.json>` exit 0 ＋ `validate-report-visual.py <report.html> --structure <report-structure.json> --require-structure --json` exit 0 ＋ mode-aware `deck-evaluator` PASS = **OUT1**
- [ ] 修正レポート (修正箇所一覧 ＋ 変更差分 ＋ 再評価スコア) を生成した
- [ ] 責務外 (新規生成・横断検証) に踏み込んでいない

### 5.4 実行方式 (決定論)
- 固定手順を持たず、5.3 完了チェックリストを唯一の停止条件とする。未充足項目を特定して解消する。
- **mode を先に確定する**: 成果物ファイル構成 (`index.html`＋`structure.*` → slide / `report.html`＋`report-structure.*` → report) から `output_mode` を判定し、曖昧なら `--mode` を優先。`../../scripts/validate-output-mode.py --mode <mode> [--report-type <enum>]` を送信前に実行し exit 0 を確認する (IN1)。exit 2 なら修正を送信せず mode/reportType を再確定。
- **worker は name 起動で dispatch する**: R2 で `Task` により `slide-report-modifier` を `isolation: fork` で起動し、判定 mode・修正対象パス・修正指示・影響範囲を渡す。worker は mode 分岐で SSOT を適用 (slide=`./references/modification-rules.md` / report=`./references/report-modification-rules.md`) し指定箇所のみを局所修正、正本 ⇔ 描画物 同期と履歴を維持する (slide=`structure.md`⇔`index.html` / report=`report-structure.json`⇔`report.html`・worker が `render-report.js` で再レンダ)。下流 agent が必要な場合は worker が修正案に明記し、**本オーケストレータが dispatch** する (worker は Task を持たない)。
- **再評価は mode 別に機械実行する**: R3 で mode に応じて機械ゲートを実行し、全ゲート exit 0 を確認。非 0 なら検出箇所を worker へ差し戻す (R2)。LLM の定性判断で PASS を決めない。
  - **slide**: `verify-slides.js --check-ratio` を実行、意匠コア／印刷影響時は `evaluate-deck.js`／`validate-print.js` も実行 (視覚崩れ 0)。
  - **report**: `render-report.js` 再レンダ整合後、`verify-report-runtime.js <report.html> --structure <report-structure.json> --out <runtime-bundle.json>`、続いて `validate-report-visual.py <report.html> --structure <report-structure.json> --require-structure --json` を実行し、bundleを mode-aware `deck-evaluator` へ渡す。
- 各周回末に中間成果物アンカー (`original_goal` 不変 / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal`) を記録し、次周回の作業立案の必須入力とする。`drift_signal` が stagnant/widening/oscillating で 2 周連続なら停止し未達項目を列挙する。
- ループ本体は分離 context (fork) で完結させ、親へは修正レポート + exit code のみ返却する。

## Layer 6: オーケストレーション層

### 6.1 R1 → R2 → R3 の agent dispatch

| ラウンド | 内容 | 主体 | ゲート (deterministic) | 差し戻し |
|---|---|---|---|---|
| **R1: 修正対象と指示の確定** | 修正対象の既存成果物 (パス)・`output_mode`・修正指示をヒアリングして確定。既存成果物を Read し、修正が及ぶ範囲 (対象要素) と**触れてはならない意匠／技術コア・非対象箇所**を明示。修正タイプを分類し影響範囲を導く | オーケストレータ | `validate-output-mode.py --mode <mode> [--report-type <enum>]` exit 0 (IN1) | exit 2 → mode/reportType 再確定 |
| **R2: 局所修正** | `Task` で `slide-report-modifier` を name 起動 (`isolation: fork`)。判定 mode に応じ**指定箇所のみ**を部分修正。意匠 SSOT・非対象セクションは不変、局所差分のみ、修正箇所と変更差分を記録。slide は `index.html`／`styles.css`／`scripts.js`⇔`structure.*` 同期、report は `report-structure.json` を正として編集し `render-report.js` で `report.html` を再レンダ (読み物文体・1項目1ビジュアル・骨格順序維持) | `slide-report-modifier` (worker) | 同期確認 (単位数一致・見出し/メッセージ一致・タイプ/role 一致・履歴記録) | 同期不一致 → 正本 (`structure.*`／`report-structure.json`) 再更新 (最大 2 回) |
| **R3: 再評価 (mode 分岐)** | 修正後をmode別再評価。**slide**=既存3ゲート、**report**=`render-report.js`整合→`verify-report-runtime.js` bundle→`validate-report-visual.py --structure --require-structure`→bundle入力の`deck-evaluator`。 | オーケストレータ | slide全exit0 / reportは再レンダ一致＋bundle/静的ゲートexit0＋deck-evaluator PASS | 崩れ／bundle欠落→R2差し戻し |

### 6.2 上位・後続との接続
- 呼び出し元: ユーザー直接起動 (`user-invocable: true`) または上位ワークフローの Phase 4 相当。
- 委譲先: 新規生成 = `run-slide-report-generate` / シリーズ横断検証 = `run-cross-deck-review`。
- 下流 agent (本オーケストレータが dispatch): `html-generator` (slide 再生成)・`ai-image-diagram-producer` (明示指示時)・`structure-designer`／`report-structure-designer` (構成変更時)・`ui-quality-reviewer`／mode-aware `deck-evaluator` (再検証) を独立 context で起動する。worker (`slide-report-modifier`) は Task を持たず、必要を修正案に明記して返す。report の `report.html` レンダ再生成のみ worker が `render-report.js` (Bash) で直接行う。

### 6.3 ハンドオフ / 並列性
- 直列: R1 → R2 → R3。R2 の worker 修正結果 (更新後 `index.html`／`structure.*` または `report.html`／`report-structure.*`) を R3 の再評価入力に接続。
- ループ: 視覚崩れ検出時は R2 ↔ R3 を feedback-contract 最大 3 周 / goal-seek max_loops 5 で反復。ループ本体は fork。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- **修正レポート**: 修正箇所一覧 ＋ 変更差分 (現在→修正後) ＋ 再評価スコア (verify-slides / evaluate-deck / validate-print の合否)。
- 修正案は承認用に提示し (CONST_003)、破壊リスクの高い修正 (構成変更・全体改善) は実行前に影響範囲を提示して確認を取る。

### 7.2 言語
- 本文: 日本語 (`output_language: ja`)。

---

## Self-Evaluation

修正レポート生成後に以下を自己確認する。未達があれば該当ゲートの exit code を根拠に差し戻す。

| 観点 | 確認内容 | 判定 |
|---|---|---|
| mode 整合 | `output_mode` を特定し `validate-output-mode.py` が exit 0 (値域整合・欠落 0) | PASS/FAIL |
| 局所性 | 指定箇所以外・意匠 SSOT・非対象・印刷 CSS が不変、Edit 差分のみ | PASS/FAIL |
| 同期維持 | slide `index.html`⇔`structure.*` / report `report.html`⇔`report-structure.*` (`render-report.js` 再レンダ一致) 整合 | PASS/FAIL |
| 再評価 (mode 別) | slide=`verify-slides.js` (＋意匠/印刷影響時 `evaluate-deck.js`／`validate-print.js`) 全 PASS / report=`render-report.js` 再レンダ整合＋`validate-report-visual.py`＋mode-aware `deck-evaluator` 全 PASS | PASS/FAIL |
| mode 保持 | slide↔report 変換をしていない、`output_mode` を維持 | PASS/FAIL |
| 越境禁止 | 新規生成・横断検証に踏み込んでいない (委譲済) | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

**R1**: 修正対象の既存成果物パスと修正指示を受け取り、ファイル構成 (`index.html`＋`structure.*` → slide / `report.html`＋`report-structure.*` → report) から `output_mode` を判定せよ (曖昧なら `--mode` を優先)。既存成果物を Read し、修正が及ぶ範囲と**触れてはならない意匠／技術コア・非対象箇所**を明示、修正指示を `./references/modification-rules.md` の 6 区分に分類し影響範囲を導け。送信前に `python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-output-mode.py" --mode <slide|report> [--report-type <internal-analysis|client-proposal|tech-doc|learning>]` を実行し exit 0 (IN1) を確認する。exit 2 なら修正を送信せず mode/reportType を再確定せよ。

**R2**: `Task` で `slide-report-modifier` を **name 起動** (`isolation: fork`) し、判定 mode・修正対象パス・修正指示・影響範囲を渡せ。worker は mode 分岐で規範を適用し**指定箇所のみ**を局所差分修正する: **slide**=`./references/modification-rules.md` の CONST_001-013・修正フローパターンに従い `index.html`／`styles.css`／`scripts.js`⇔`structure.*` 同期と履歴を維持 (HTML 再生成が要れば修正案に明記→オーケストレータが `html-generator` 委譲)。**report**=`./references/report-modification-rules.md` の RCONST_001-013 に従い `report-structure.json` を正として編集し `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/render-report.js" <report-structure.json> <report.html>` で `report.html` を再レンダ、読み物文体・1項目1ビジュアル・reportType 骨格順序を維持し、履歴は `meta.version` bump ＋ sidecar `report-structure.history.json` に追記 (schema 外フィールドのインライン禁止)。いずれも意匠 SSOT・非対象箇所を不変に保ち、修正後 `structure.*`／`report-structure.json` が対応 schema (`../../schemas/structure.schema.json`／`report-structure.schema.json`) に valid であることを保つ。

**R3 (mode 分岐)**: 修正後、mode 別に機械ゲートを実行せよ。
- **slide**: `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/verify-slides.js" ./index.html --check-ratio` で視覚崩れ 0 を確認。意匠コア・印刷レイアウトに及ぶ場合は `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/evaluate-deck.js"` ／ `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/validate-print.js"` も併用。
- **report**: `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/render-report.js" <report-structure.json> <report.html>` で再レンダ整合を確認し、`node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/verify-report-runtime.js" <report.html> --structure <report-structure.json> --out <runtime-bundle.json>`、`python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-report-visual.py" <report.html> --structure <report-structure.json> --require-structure --json`、bundle入力の mode-aware `deck-evaluator` の順に再評価。

いずれかが非 0 (崩れ／乖離／FAIL) なら検出箇所を R2 へ差し戻し (feedback-contract 最大 3 周 / goal-seek max_loops 5)、全 exit 0 (OUT1) で完了とする。最終的に**修正レポート** (修正箇所一覧 ＋ 変更差分 ＋ 再評価スコア) を返し、`"PASS"` 文字列でなくゲートの exit code を完成根拠とせよ。前置き禁止。

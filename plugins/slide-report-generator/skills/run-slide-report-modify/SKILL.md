---
name: run-slide-report-modify
description: 既存のスライドデッキ/レポートを output_mode を保ったまま指定箇所だけ部分修正したいとき、意匠/技術コアと非対象箇所を壊さず修正後の再評価で視覚崩れ0にしたいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
argument-hint: "[target-dir?] [--mode slide|report]"
arguments: [target_dir, mode]
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
  engine: inline
  fork: subagent
  max_loops: 5
responsibility_refs:
  - prompts/R1-orchestrate.md
manifest: workflow-manifest.json
schema_refs:
  - ../../schemas/structure.schema.json
  - ../../schemas/report-structure.schema.json
  - schemas/modification-report.schema.json
feedback_contract: # per-skill 受入基準(purpose-acceptance)。修正後の生成後評価 verdict と突合し汎用ゲート言い換えへ退化させない
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-output-mode で既存成果物の output_mode を判定し修正対象の mode と reportType の値域整合を送信前検証し欠落が0件
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 指定箇所のみが修正され意匠/技術コアと非対象箇所が不変で、修正後の生成後評価が視覚崩れ0で PASS することを受入テストが確認する
      verify_by: test
---

# run-slide-report-modify

> **役割**: 既存の slide deck ／ report の**局所修正**を独立起動で行う skill (移植元 P4 = slide-modifier 相当)。生成し直さず、`output_mode` を保ったまま**指定箇所だけ**を部分修正し、意匠／技術コアと非対象箇所を壊さない。plugin root = `$CLAUDE_PLUGIN_ROOT`、実行パスは全てここ起点 (repo-root ハードコード禁止)。新規生成は `run-slide-report-generate`、シリーズ横断検証は `run-cross-deck-review` の責務。

## Purpose & Output Contract

既存の slide deck ／ report を `output_mode` を保ったまま指定箇所だけ部分修正し、**意匠／技術コアと非対象箇所を壊さず**、修正後の生成後評価で**視覚崩れ 0** の状態を作る。

- **入力**: 既存成果物 (slide deck ディレクトリ ／ report HTML) と修正指示。任意 `--mode slide|report` (省略時は成果物から自動判定)。
- **出力**: **修正レポート** (修正箇所一覧 ＋ 変更差分 ＋ 再評価スコア)。
- **完了条件**: (1) 修正対象と `output_mode` を特定し `validate-output-mode.py` で値域整合を検証、(2) 指定箇所のみを部分修正 (非対象・意匠コア不変)、(3) 修正後の生成後評価が視覚崩れ 0 で PASS。

## mode 判定 (slide / report)

独立起動のため、まず修正対象成果物の `output_mode` を判定する。

- `index.html` (＋ `styles.css` / `scripts.js` / `structure.*`) を持つ → **slide** (deck 成果物)。
- `report.html` (＋ `report-structure.*`) を持つ → **report**。
- 曖昧な場合は `--mode` 引数を優先し、`validate-output-mode.py` で値域整合を検証する (IN1)。判定した mode を修正 worker へ伝播する。

## ワークフロー (R1 → R2 → R3・worker は Task で name 起動)

> 各ラウンドの 7 層実行契約 (agent dispatch・script/schema/reference 実体参照・deterministic ゲート・差し戻し条件) の詳細は `prompts/R1-orchestrate.md` を正本とする。`workflow-manifest.json` が phase (R1/R2/R3)・resource・gate・fatal_exit_codes を機械可読に宣言する。以下は router として読める粒度の要約。

### R1: 修正対象と指示の確定

修正対象の既存成果物 (パス)・`output_mode`・修正指示をヒアリングして確定する。既存成果物を Read し、修正が及ぶ範囲 (対象要素) と**触れてはならない意匠／技術コア・非対象箇所**を明示する。

### R2: 局所修正

`Task` で **slide-report-modifier** を起動 (`isolation: fork`)。判定した mode (slide ／ report) に応じ、**指定箇所のみ**を部分修正する。worker の tools は `Read, Write, Bash` のみで Task を持たず、下流 agent (`html-generator`／`structure-designer`／`report-structure-designer`／`ai-image-diagram-producer`) が要る場合は修正案に明記して返し**本 skill が dispatch** する。

- 意匠 SSOT (Kanagawa 配色・16:9・最小 1.4rem・印刷 CSS・letterbox 等) と非対象セクションは**不変**に保つ (両モード共有)。
- **slide**: `index.html`／`styles.css`／`scripts.js` と `structure.*` の同期を維持 (`./references/modification-rules.md` の CONST_001-012)。
- **report**: `report-structure.json` を正本に編集し `render-report.js` (Bash) で `report.html` を再レンダして整合を維持 (`./references/report-modification-rules.md` の RCONST_001-012)。読み物文体・1項目1ビジュアル・reportType 骨格順序を崩さず、履歴は `meta.version` bump ＋ sidecar `report-structure.history.json` (schema 外フィールドのインライン禁止)。
- 全書き換え禁止 (局所差分のみ)。修正箇所と変更差分を記録する。

### R3: 再評価 (mode 分岐)

`slide-report-modifier` の修正後、mode 別に再評価する (下記 deterministic_checks)。**slide**=`verify-slides.js` (＋意匠/印刷影響時 `evaluate-deck.js`／`validate-print.js`) で視覚崩れ 0。**report**=`render-report.js` 再レンダ整合 ＋ runtime bundle生成 ＋ `validate-report-visual.py <report.html> --structure <report-structure.json> --require-structure --json` ＋ mode-aware `deck-evaluator`。未達なら R2 へ差し戻す。

## 決定論チェック (deterministic_checks)

```bash
# 【共通】既存成果物の output_mode 判定と値域整合 (送信前・fail-closed)
python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-output-mode.py" --mode <slide|report> [--report-type <enum>]

# 【slide R3】修正後の UI 品質検証 (テキスト切れ・改行・16:9 比率・非対象箇所の崩れ検出)
node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/verify-slides.js" ./index.html --check-ratio
# 意匠コア・印刷レイアウトに及ぶ場合は evaluate-deck.js / validate-print.js も併用

# 【report R3】report-structure.json → report.html 再レンダ整合 (正本の忠実な射影を確認)
node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/render-report.js" <report-structure.json> <report.html>
# 修正後 report.html の読み物視覚検証 (section 構造欠落 / 1項目1ビジュアル逸脱 / 段落過密 / 意匠逸脱・fail-closed)
node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/verify-report-runtime.js" <report.html> --structure <report-structure.json> --out <runtime-bundle.json>
python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-report-visual.py" <report.html> --structure <report-structure.json> --require-structure --json
# さらに mode-aware deck-evaluator (report rubric: 可読性/図解適合/情報密度/セクション論理構造) を Task 起動して再評価
```

mode を先に確定し (`validate-output-mode.py`)、R3 は mode 分岐で実行する: **slide**=`verify-slides.js` (＋意匠/印刷影響時 `evaluate-deck.js`／`validate-print.js`) で視覚崩れ 0、**report**=`render-report.js` 再レンダ整合 ＋ `validate-report-visual.py` ＋ mode-aware `deck-evaluator`。いずれも全ゲート exit 0 を完成根拠とする。

## ゴールシークと受入基準 (combinators)

`with-goal-seek`(max_loops 5) + `with-feedback-contract`。ループ本体は `Task` で SubAgent へ fork し、親へは修正レポートのみ返す。受入基準は当該 skill の goal／checklist 由来の受入条件 (purpose-acceptance):

- **IN1 (inner・script)**: `validate-output-mode` で既存成果物の `output_mode` を判定し修正対象の mode と `reportType` の値域整合を送信前検証し欠落が 0 件。
- **OUT1 (outer・test)**: 指定箇所のみが修正され意匠／技術コアと非対象箇所が不変で、修正後の生成後評価が視覚崩れ 0 で PASS することを受入テストが確認する。

未達は最大 3 周 (inner) / 5 loops (goal-seek) で findings を反映し再実行する。

## 境界

- 入力 = 既存成果物と修正指示／出力 = 局所修正済み HTML。
- **slide/report 双方対応 (mode-aware)**: 局所修正・再評価を slide 経路 (`structure.md`⇔`index.html`・`verify-slides.js`) と report 経路 (`report-structure.json`⇔`report.html`・`render-report.js` 再レンダ整合＋`validate-report-visual.py`＋mode-aware `deck-evaluator`) の両方で実体化する。purpose「slide/report 双方修正」を additive に満たす (slide 既存契約は温存)。
- **新規生成は `run-slide-report-generate` へ委譲**する (本 skill は既存成果物の局所修正のみ・ゼロから作らない)。
- **シリーズ横断の整合検証は `run-cross-deck-review` へ委譲**する。

## Gotchas

- **配置非依存**: 全実行パスは `$CLAUDE_PLUGIN_ROOT` 起点 (`vendor/scripts/…` ／ `scripts/…`)。repo-root 直書き禁止。
- **局所性を守る**: 指定箇所以外・意匠 SSOT・印刷 CSS には触れない。全書き換えでなく Edit 差分。
- **mode を保つ**: slide を report へ (逆も) 変換しない。`output_mode` は入力成果物のものを維持する。
- **同期維持**: slide deck は `index.html`⇔`structure.*`、report は `report.html`⇔`report-structure.*` の整合を崩さない。
- **完成判定は実体で**: 修正後は Read／署名／スクショ目視で確認し、"PASS" 文字列で完成判断しない。
- **agent は name 参照**: `slide-report-modifier` はファイルパス依存でなく Task の name 起動。

## 配置先

| 用途 | 出力先 |
|---|---|
| 本 skill 資産 | `plugins/slide-report-generator/skills/run-slide-report-modify/` |
| 修正対象・出力 | 既存成果物ディレクトリ (in-place 局所修正) |

## 追加リソース

- `prompts/R1-orchestrate.md` — R1→R2→R3 の 7 層実行 SSOT (agent dispatch・script/schema/reference 実体参照・deterministic ゲート・差し戻し条件)。
- `workflow-manifest.json` — phase (R1-identify-target → R2-local-modify → R3-re-evaluate)・resource・gate (C1/C2/C3)・dependsOn・entryHook/exitHook・fatal_exit_codes の機械可読宣言。
- `references/modification-rules.md` — **slide** 部分修正規範の逐語 SSOT (用語集・評価基準・修正タイプ 6 分類・CONST_001-012・修正フローパターン・index.html ⇔ structure.md 同期維持ルール)。worker (`slide-report-modifier`) と本 skill の双方が参照。
- `references/report-modification-rules.md` — **report** 部分修正規範の逐語 SSOT (reportType 4 骨格の維持・section 構造の局所修正・report.html ⇔ report-structure.json 同期・読み物文体/1項目1ビジュアル非破壊・履歴追記)。modification-rules.md(slide) と対を成し、slide-report-modifier が mode 別に適用。
- `../../schemas/structure.schema.json` — slide 修正対象の構造正本 (修正後 `structure.*` が valid を保つ判定)。
- `../../schemas/report-structure.schema.json` — report 修正対象の構造正本 (修正後 `report-structure.*` が valid を保つ判定)。
- `../../scripts/validate-output-mode.py` — output_mode 判定・値域検証 (plugin-root glue・IN1)。
- `../../vendor/scripts/verify-slides.js` / `evaluate-deck.js` / `validate-print.js` — **slide** 修正後の視覚崩れ検証 (R3・OUT1)。
- `../../scripts/validate-report-visual.py` — **report** 修正後の決定論視覚ゲート (section 構造/1項目1ビジュアル/段落密度/placeholder・R3・OUT1)。
- `../../vendor/scripts/render-report.js` — **report** 修正後の report-structure.json → report.html 再レンダ整合 (正本射影の確認・R3)。
- 統率する agent: `slide-report-modifier` (Task の name 起動・isolation: fork・mode-aware。用語集・CONST/RCONST・修正フローは slide=`references/modification-rules.md` / report=`references/report-modification-rules.md` を SSOT に mode 別適用)。下流 agent (含 mode-aware `deck-evaluator`) は worker が Task 非保持ゆえ本 skill が dispatch。

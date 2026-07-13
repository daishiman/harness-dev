# Phase 01 — 要件定義 (build)

> 対象: `plugin-plans/slide-report-generator/` の計画一式を **実プラグイン `plugins/slide-report-generator/` へ build** する。
> 実装区分の判断 (CONST_006): 計画の goal-spec は「L3 plan 止まり (build は run-skill-create/run-build-skill へ委譲)」と宣言するが、**ユーザーのメタプロンプトがこれを上書きし「実コードを build せよ」と明示**。よって本サイクルは実プラグインを生成する実装タスクとして実行する。判断根拠は implementation-guide.md 冒頭にも明記する。

## 1. 最上位目的
presentation-slide-generator v8.4.2 の全機能を抜け漏れなく移植し、意匠/技術コアを単一 SSOT で共有する `output_mode = slide | report` の 2 モード・ビジュアル生成ハーネスを **動作する実プラグイン**として構築する。

## 2. 成果要件 (goal-spec checklist C1-C8 の build 版)
- **C1**: 既存 13 sub-agent が `plugins/slide-report-generator/agents/*.md` (C04-C16) へ 1:1 で実在。
- **C2**: `output_mode` 分岐が主 skill (C01) と hearing-facilitator (C04) に焼かれ、意匠/技術層は共有・コンテンツ意図層のみ mode 別。
- **C3**: report モードが 4 reportType 骨格 (report-structure.schema.json / C17) + visual-strategist (C18) + Mermaid 統合 + report HTML レンダラ (C19 + render-report.js) を実体で持つ。
- **C4**: Codex Image2 チェーン (C14 + vendor) と 30種思考法評価ゲート (C13 deck-evaluator + C20 hook) が両モードで機能。
- **C5**: Node engine が vendor byte 携行され、`Bash(node *)` 起動で install 携帯性を満たす (Python 化しない)。
- **C6**: `component-inventory.json` は plan 側で既に検討証跡を保持 (build は消費側)。
- **C7**: 各 buildable component が quality_gates を携帯 (frontmatter/lint 準拠で実現)。
- **C8**: manifest/composition/EVALS の plugin-level surface が実在。

## 3. build 対象の分解 (23 component + surfaces)
| 区分 | 実体 | 手法 |
|---|---|---|
| vendor | scripts/(160) assets/(25) schemas-fixtures/(8) package*.json | ✅ byte copy 完了 (195/195 parity PASS) |
| references | 42 upstream .md + feedback 5 | ✅ copy 完了 |
| schemas | structure/image-deck-plan/evaluation-report/image-asset-manifest | ✅ copy 完了 |
| agents C04-C16 | 13 移植 (frontmatter 付与 + パス書換 + C15 rename + C04/C13 mode 編集) | 著述 (port) |
| agents C17-C19 | report-structure-designer / visual-strategist / report-composer (新規) | 著述 (new) |
| schema (new) | report-structure.schema.json (structure と共通コア共有) | 著述 (new) |
| references (new) | report-types / report-writing-rules / report-visual-strategy / mermaid-integration | 著述 (new) |
| vendor Node (new) | render-report.js / mermaid-render.js (additive・C19 owner) | 著述 (new, runnable) |
| skills C01-C03 | run-slide-report-generate / -modify / run-cross-deck-review | 著述 (new) |
| hook C20 | hook-postgen-eval.py (deck-postgen-hook.js を python mode-aware 化) | 著述 (new) |
| commands C21/C22 | slide-report-generate / slide-report-status | 著述 (new) |
| script C23 | validate-output-mode.py + pytest | 著述 (new) |
| manifest | .claude-plugin/plugin.json (envelope-draft 適用) | 統合 |
| composition | plugin-composition.yaml | 統合 |
| EVALS | EVALS.json (slide/report 両モード配線) | 統合 |

## 4. 完了の定義 (DoD)
- [ ] 全 23 component + surfaces が `plugins/slide-report-generator/` に実在し `git diff --stat` で確認できる。
- [ ] vendor byte-parity PASS (195/195)。
- [ ] `validate-output-mode.py` の pytest がグリーン。
- [ ] 新規 Node renderer (render-report.js) が実際に node 起動で report HTML を出力できる。
- [ ] vendored render-slide.cjs が実際に slide HTML を出力できる (既存動作の非破壊)。
- [ ] plugin.json が valid (name==folder, no placeholder, hook wiring)。
- [ ] outputs/phase-01..12 に成果物。P11 に実 HTML + 視覚検証。P12 に implementation-guide.md。

## 5. 非スコープ (今サイクル)
- commit / PR / push (CONST_002)。
- marketplace 配布登録 (distributable:false・GAP-ENVELOPE marketplace は manual-user-gated)。
- `npm ci` / `playwright install` による node_modules 再取得は evidence フェーズで必要時のみ (既存 upstream node_modules を暫定利用可)。

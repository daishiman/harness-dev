# slide-report-generator — 実装ガイド (build 完了報告 / PR メッセージ)

> **実装区分の判断根拠 (CONST_006・ラベル上書きの明記)**: 本タスクの計画 (`plugin-plans/slide-report-generator/`) は goal-spec 上「L3 plan 止まり (実 build は run-skill-create/run-build-skill へ委譲)」と宣言する docs 寄りの計画である。しかしユーザーのメタプロンプトが「原則として実コードを build せよ・目的達成にコード変更が必要なら実装せよ」と明示的に上書きしているため、**実プラグイン `plugins/slide-report-generator/` を実コードとして構築した**。計画のラベル(plan-only)より実態(purpose=動作するハーネスの構築)を優先した。

## 概要
presentation-slide-generator v8.4.2 の全機能を抜け漏れなく移植し、意匠/技術コアを単一 SSOT で共有する `output_mode = slide | report` の 2 モード・ビジュアル生成ハーネスを実プラグインとして構築した。**23 component + plugin-level surfaces** が実在し、slide/report 両モードが実 HTML を生成できることを実レンダリング + スクリーンショットで検証済み。

## build 成果 (286 files / +71,573 lines)
| surface | 実体 | 検証 |
|---|---|---|
| vendor | Node engine 195 files を byte 携行 (scripts 160 / assets 25 / schemas-fixtures 8 / package*.json 2) + report 新規 2 Node | byte-parity 195/195 PASS |
| agents (16) | slide 13 移植 (C04-C16・frontmatter付与+パス書換+C15 rename+C04/C13 mode焼込) + report 新規 3 (C17 report-structure-designer / C18 visual-strategist / C19 report-composer) | 16/16 validate-frontmatter + lint-agent-prompt-section PASS |
| skills (3) | run-slide-report-generate (C01・IN1/OUT1 criteria焼込) / run-slide-report-modify (C02) / run-cross-deck-review (C03) | 3/3 frontmatter PASS |
| commands (2) | /slide-report-generate (--mode) / /slide-report-status | frontmatter valid |
| hooks (1) | hook-postgen-eval.py (PostToolUse・mode判定・fail-soft) | 配線 + manifest 整合 |
| scripts (2) | validate-output-mode.py (mode/reportType 値域 fail-closed) / verify-vendor-parity.py | pytest 25 passed |
| schemas (5) | structure + **report-structure(新規・共通コア8 $defs共有)** + image-deck-plan + evaluation-report + image-asset-manifest | Draft202012 valid・sample ⊨ schema |
| references (46) | 42 upstream + report新規4 (report-types/report-writing-rules/report-visual-strategy/mermaid-integration) | 存在 |
| plugin-level | .claude-plugin/plugin.json / plugin-composition.yaml / EVALS.json / README.md | validate-plugin-completeness + lint-manifest-contents PASS |

## 実装手法 (二層 + 並列)
1. **機械的移植 (決定論スクリプト)**: vendor 195 files の whole-tree byte copy、13 agents の frontmatter付与+パス書換($CLAUDE_PLUGIN_ROOT起点)+C15 rename。grep 不変条件で残存 upstream パス0・二重化0 を検証。
2. **並列著述 (5 SubAgent 手分け)**: report agents 3 / renderer 2 Node / skills 3 / hook+commands+script / C04・C13 mode編集 を、競合ゼロの排他ファイル partition で並列生成。
3. **統合 (integrator)**: manifest/composition/EVALS/README/parity script + lint 横断 + cross-agent 契約整合。

## 検証結果 (全緑)
### 決定論ゲート 10/10 PASS
vendor byte-parity 195/195・pytest 25 passed・node render-report/mermaid tests・plugin-completeness・manifest lint・両 schema valid・sample⊨schema・16 agents lint・3 skills frontmatter。

### 実レンダリング + 視覚検証 (P11・`outputs/phase-11/`)
- **slide**: `render-slide.cjs` → `slide/index.html` (8316B) → `screenshots/slide-01.png` (2560×1440 = 16:9)。Kanagawa グラデ・大型ヒーロータイトル・ナビ・ページ送り。
- **report**: `render-report.js` → `report/report.html` (16886B) → `screenshots/report-full.png` (1800×6582)。4 reportan骨格(要約→背景→現状分析→所見→次アクション)・**Mermaid 実描画**・SVG flow/cycle 図解・1項目1ビジュアル。
- Apple UI/UX 観点で両モードの意匠共有(単一 SSOT)と mode 別コンテンツ規律を目視 PASS。詳細: `outputs/phase-11/visual-verification.md`。

![slide](phase-11/screenshots/slide-01.png)
![report](phase-11/screenshots/report-full.png)

## 主要な設計判断・遭遇した問題
1. **移植は cherry-pick せず whole-tree byte copy**: 個別ファイル allowlist は import 依存の断線を生むため `scripts/`/`assets/`/`schemas/` をサブツリー丸ごと携行。
2. **移植元 7層 agent に repo 規約セクション付与**: upstream agent は frontmatter/`## Prompt Templates`/`## Self-Evaluation` を持たないため、repo lint 契約に合わせて機械付与。
3. **cross-agent 契約ドリフトの解消**: report-structure schema (report-domain) と render-report.js (renderers) が visual.spec 語彙を独立解釈しドリフト(31 errors)。**良設計側の schema (common core共有・aiVisualSpec が validate-ai-image-assets.js と同期) を正本**とし、consumer(render-report/sample/test)を conform して三重整合(schema valid + sample⊨schema + 実レンダリング)。
4. **並行書込の安全性**: 同一ファイルへの複数 writer は last-writer-wins で最終状態を検証し破損なしを確認。

## 使い方
```
/slide-report-generate --mode slide  <topic>
/slide-report-generate --mode report --report-type internal-analysis|client-proposal|tech-doc|learning <topic>
/slide-report-status <project-dir>
# preflight (node engine の node_modules 再install が必要)
cd "$CLAUDE_PLUGIN_ROOT/vendor" && npm ci && npx playwright install chromium
python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-output-mode.py" --preflight
```

## 非スコープ / 残作業
- **commit / PR / push は未実施** (CONST_002・ユーザー指示待ち)。実コードは作業ツリーに未追跡で存在 (`git status` で確認可)。
- marketplace 配布登録は行わない (`distributable: false`・社内専用)。
- `vendor/node_modules` 再install (`npm ci`) と `playwright install` は各環境の初回 preflight で実施 (byte 携行対象外)。
- report の Codex 画像は実運用時に ai-image-diagram-producer が生成 (サンプルは参照契約の検証のみ)。

## 完了確認 (DoD)
- [x] 全 23 component + surfaces が `plugins/slide-report-generator/` に実在 (`git diff --stat`: 286 files / +71,573)。
- [x] vendor byte-parity PASS (195/195)。
- [x] validate-output-mode.py の pytest グリーン (25 passed)。
- [x] render-report.js が report HTML を実生成 / render-slide.cjs が slide HTML を実生成。
- [x] plugin.json valid (name==folder・hook 実在・distributable:false 整合)。
- [x] outputs/phase-01..12 に成果物。P11 に実 HTML + スクショ + 視覚検証。

## 現ビルド追随検証 (2026-07-11 update)

> 上記 v1 ガイドの一部数値は現ビルドに追随していない。以下は検証済みの事実で doc を追随させる (数値の発明なし)。旧記述は履歴として残置。

- **component / vendor / pytest の追随**: 旧「23 component / vendor 195 / pytest 25」は v1。現ビルドは **25 buildable component** (3 skill + 17 sub-agent + 1 hook + 2 slash-command + 2 script)、**vendor byte-parity 191/191 PASS** (schemas subtree の真 schema 4本を plugin-root live へ移し fixture3+README=4 file 化で 195→191)、**pytest 125 passed**。
- **schema**: report-structure 1.2.0 (真 schema 5本 = 移植4 + report-structure新設1・plugin-root schemas/ live)。
- **機械ゲート (全緑・本セッション実測)**: lint-contract-drift findings=0、lint-reference-attribution ok、validate-plugin-completeness PASS、vendor JS test (test-render-report/test-mermaid-render/test-cross-deck-consistency) 全 PASS、C23 validate-output-mode.py coverage 92% (旧 63%)。
- **第3次 UI/UX + 図解機構刷新 (render-report.js buildReportCss)**: screen/print 二層 CSS・sticky sidebar TOC + scrollspy・タイポ密度是正、全ブロックの吹き出しを白地フラットカードへ一括転換・本文全幅化。before/after スクショ (Chrome headless・wide 1500px / narrow 880px) で 5 指摘の解消を目視実証。旧 `report-full.png` (1800×6582) は v1 サンプルで第3次UI 反映前 (詳細: `outputs/phase-11/visual-verification.md`)。
- **essence-visual 収束 (C8/C19)**: 本質図解を role 駆動へ収束。旧 visual.intent / schema 1.3.0 案は撤回し plan を essence-visual へ追随更新済 (schema は 1.2.0 のまま)。意味適合は C24 report-quality-reviewer が二層分離で判定。
- **C25 validate-report-visual.py (本セッション強化)**: `_check_uiux_shape` (screen 接合トークン・sticky TOC・aria-current・before/afterprint・@media print .report 幅・狭画面 @media・grid minmax card・タイポ検査) + `--require-structure` (report gate の fail-open 封鎖=structure 欠落で exit2) を追加。現行 report で uiux-shape warn 0・exit0。
- **plan reconcile (2026-07-11)**: goal-spec/component-inventory/handoff/index/phase-01,02,04,05,07,08/plan-findings を essence-visual へ追随、task-graph.json を derive-task-graph.py で再derive (node 908 安定・graph_hash ab24010)、planner 決定論ゲート 8種 exit0。

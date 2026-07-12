# Phase 03 — 設計レビューゲート (自己審査)

> build 契約 (phase-02) を C1-C8 (要件) + elegant C1-C4 (矛盾/漏れ/整合/依存) で審査。PASS で実装 (P04+) へ進む。

## elegant C1-C4
- **C1 矛盾なし**: vendor は byte 固定・書換禁止、新規は additive のみ、という非破壊原則で「移植の完全性」と「新機能追加」が両立。render-report.js を vendor/scripts/ に置くのは parity_scope.excluded_additive で照合除外済 (計画既決)。矛盾なし。
- **C2 漏れなし**: source-inventory §5 の被覆項目を build 契約 §A のファイル配置へ全写像。13 agents/42 refs/7 schemas/195 vendor files/Codex chain/30種思考法/A4印刷/GAS/決定論レンダラ = 全て vendor または component へ。report 新規 5 項目 (schema/visual-strategist/mermaid/composer/content-regime) も §E/§F/§G/§H に配置。漏れなし。
- **C3 整合性**: frontmatter テンプレ (§B) と repo 規約 (plugin-dev-planner agents) が一致。path 書換 (§C) は cwd=plugin-root/$CLAUDE_PLUGIN_ROOT で resolve する。mode 契約 (§D) は共有/分岐の境界が単一定義。整合。
- **C4 依存整合**: DAG 非循環。C01→(C04..C14,C17,C19)、C02→C15、C03→C16、workers→vendor は surface 参照。renderer (F) は C19 が owner・skills は name 参照でファイル依存なし → 並列 build 安全。

## 要件 C1-C8 の build 充足設計
| 要件 | 充足設計 | 検証方法 (P06/P09/P11) |
|---|---|---|
| C1 | agents/ に 13 実体 (§A) | ファイル存在 + frontmatter lint |
| C2 | §D mode 契約を C01/C04 に焼く + C23 で値域検証 | validate-output-mode pytest |
| C3 | §E report schema + C17/C18 + §F renderer + mermaid ref | schema valid + render-report node 実行 |
| C4 | C14 (vendor Codex chain) + C13 mode-aware + C20 hook | hook matcher + deck-evaluator mode 分岐 |
| C5 | vendor byte 携行 (parity PASS) + Bash(node*) 起動 | parity 195/195 + render-slide.cjs 実行 |
| C6 | plan 側 inventory (build は消費) | — (plan 済) |
| C7 | 各 component frontmatter + lint 準拠 | frontmatter lint |
| C8 | manifest/composition/EVALS 実在 | plugin.json valid |

## 並列 build 分担 (競合ゼロの partition)
| Agent | 担当ファイル (排他) |
|---|---|
| ports | agents/*.md (13 port + C15 rename + C04/C13 mode 編集) |
| report-domain | agents/report-structure-designer.md, visual-strategist.md, report-composer.md + schemas/report-structure.schema.json + references/{report-types,report-writing-rules,report-visual-strategy,mermaid-integration}.md |
| renderers | vendor/scripts/render-report.js, mermaid-render.js + vendor/tests/* + package*.json additive |
| skills | skills/*/SKILL.md (C01-C03) |
| glue | hooks/hook-postgen-eval.py + commands/*.md + scripts/validate-output-mode.py + tests/test_validate_output_mode.py |
| integration (self) | .claude-plugin/plugin.json + plugin-composition.yaml + EVALS.json + README.md |

> report-composer.md (report-domain) は renderer を **path 参照**し、実装は renderers 担当 (owner=C19 の実装責務を物理分担・両 prompt に明記して二重著述を回避)。

## 判定
**PASS** — 実装フェーズ (P04 test-design → P05 実装) へ進む。

## 現ビルド追随検証 (2026-07-11 update)

> 上記 v1 の設計審査は現ビルドに追随していなかった。以下は本セッションで検証済みの設計/reconcile 整合事実のみを追記する (数値の発明なし)。

- **component 構成の更新**: 現ビルドは 25 buildable component (3 skill + 17 sub-agent + 1 hook + 2 slash-command + 2 script)。v1 の C1/C2 表・partition 表が前提とした「13 agents / 23 component」は現状と不一致 (旧記録は v1)。
- **essence-visual への設計収束 (C8/C19)**: 本質図解は role 駆動へ収束。`validate-report-visual.py` の `_check_essence_visual` が role∈{分析/主張/課題/解決/所見/影響}(=`_ESSENCE_REQUIRED_ROLES`) の論理節に非none visual (`visual.kind!=none`) を要求する。旧 `visual.intent={kind,message}` / schema 1.3.0 案は撤回し、plan を essence-visual へ追随更新済 (schema は 1.2.0 のまま)。意味適合は C24 report-quality-reviewer が二層分離で判定。
- **schema**: report-structure 1.2.0。真 schema は 5本 (移植4 + report-structure新設1) で plugin-root `schemas/` に live 配置。
- **C25 fail-open 封鎖**: `validate-report-visual.py` に `--require-structure` を追加し、report gate の fail-open (structure 欠落で緑化) を exit2 で封鎖。screen 接合の構造検査 `_check_uiux_shape` も追加。
- **reconcile 整合ゲート (全緑)**: lint-contract-drift findings=0、lint-reference-attribution ok、validate-plugin-completeness PASS。
- **plan reconcile (2026-07-11)**: goal-spec / component-inventory / handoff / index / phase-01,02,04,05,07,08 / plan-findings の visual.intent 記述を essence-visual へ追随。task-graph.json を derive-task-graph.py で再derive (node 908 安定・graph_hash ab24010)、planner 決定論ゲート 8種 exit0。

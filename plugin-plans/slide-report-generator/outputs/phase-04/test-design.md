# Phase 04 — テスト設計

> 設計(P02 build-contract)に基づき、build 成果を検証するテスト/ゲート群を先に定義する(TDD: テストは実装前に赤で良い)。

## テスト種別と対象
| # | テスト/ゲート | 対象 component | 種別 | 期待 |
|---|---|---|---|---|
| T1 | `verify-vendor-parity.py` | vendor 195 files | 決定論(sha256) | PASS 195/195 |
| T2 | `tests/test_validate_output_mode.py` (pytest) | C23 validate-output-mode.py | 単体(正常/異常/preflight) | 全 PASS |
| T3 | `vendor/tests/test-render-report.js` (node) | render-report.js (C19) | 統合(HTML生成+決定論) | 全 assert PASS |
| T4 | `vendor/tests/test-mermaid-render.js` (node) | mermaid-render.js | 単体(片生成+HTMLエスケープ) | 全 assert PASS |
| T5 | `validate-frontmatter.py` × 16 | 全 agent | 静的(frontmatter 契約) | 全 ok |
| T6 | `lint-agent-prompt-section.py` × 16 | 全 agent | 静的(Prompt Templates/Self-Evaluation) | 全 PASS |
| T7 | `validate-frontmatter.py` × 3 | 全 skill | 静的 | 全 ok |
| T8 | `validate-plugin-completeness.py` | plugin 全体 | 静的(配布可能性) | complete |
| T9 | `lint-manifest-contents.py` | plugin.json | 静的 | valid |
| T10 | report-structure.schema.json ⊨ sample | C17 schema + renderer sample | 契約(JSON Schema) | sample VALID |
| T11 | `render-slide.cjs` 実レンダリング | C10 slide 経路 + vendor | 統合(実HTML) | index.html 生成・16:9/Kanagawa |
| T12 | `render-report.js` 実レンダリング | C19 report 経路 | 統合(実HTML) | report.html 生成 |

## 契約整合テスト (cross-agent)
- T10 は**別 Agent が独立生成した schema と renderer サンプルの契約整合**を検証する。§E を散文で配ったため spec 語彙がドリフトしうる → schema を正本に consumer(renderer/sample/test)を conform させる整合作業を含む。

## モード被覆
- slide: T11 (render-slide.cjs → index.html)。
- report: T3/T10/T12 (render-report.js → report.html・4 reportType・svg/mermaid/codex-image/none visual)。
- 両モード配線宣言: EVALS.json llm_eval (deck-evaluator slide/report rubric)。

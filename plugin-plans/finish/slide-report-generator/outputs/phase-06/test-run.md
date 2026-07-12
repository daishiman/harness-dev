# Phase 06 — テスト実行

全ゲート実走結果 (P06/P09 で機械検証・全緑)。

| ゲート | 結果 |
|---|---|
| G1 vendor byte-parity (195 sha256) | ✅ 195/195 PASS |
| G2 pytest tests/ (validate-output-mode) | ✅ 25 passed |
| G3 node test-render-report.js | ✅ 全 assert PASS (決定論 byte一致含む・16886B/5 sections) |
| G4 node test-mermaid-render.js | ✅ 全 assert PASS (HTMLエスケープ・決定論) |
| G5 validate-plugin-completeness.py | ✅ 16 plugin complete (slide-report-generator 含む) |
| G6 lint-manifest-contents.py | ✅ manifest valid |
| G7 structure + report-structure schema | ✅ 両者 Draft202012 valid |
| G8 report sample ⊨ report-structure.schema.json | ✅ VALID (0 errors) |
| G9 16 agents lint (validate-frontmatter + lint-agent-prompt-section) | ✅ 全 PASS |
| G10 3 skills validate-frontmatter | ✅ 全 PASS |

**結果: PASS=10 FAIL=0**。TDD の赤(初期 renderer サンプル↔schema ドリフト 31 errors)は schema を正本に consumer を conform して緑化。

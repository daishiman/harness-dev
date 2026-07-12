# elegant-review レポート — company-master プラグイン

- date: 2026-06-10
- scope_mode: plugin
- target: plugins/company-master/
- 手法: 思考リセット(Phase1) → 30思考法並列分析(Phase2, 3 SubAgent) → 改善実行(Phase3)
- thought_method_coverage: A2=11 / A3=9 / A4=11(why思考はA2移管) = 30/30 全使用、skip 0

## verdict (4条件)

| 条件 | 判定 | 根拠 |
|---|---|---|
| 矛盾なし | PASS | セキュリティ節と settings-hardening.json `_doc`/hook GUARD_ACCOUNTS が一致。設計判断ログ内で齟齬なし |
| 漏れなし | PASS | Group C/A/B/D/E 全項目にパッチ。二段防御の静的層を新設し片肺を解消 |
| 整合性あり | PASS | frontmatter reference_refs と実ファイル一致。config ヘッダを notion_config 実解決順へ統一。`make lint` 全 PASS |
| 依存関係整合 | PASS | 新規 lint を Makefile `lint` ターゲットへ配線。README-setup→settings-hardening→SKILL.md の参照が相互整合 |

## ユーザー要望3核心への結論

1. **1スキルへの過集約の分離**: 3 analyst が独立収束 — 物理分割は既済(command2/agent3/hook1/script複数)。真の不足は「なぜ単一skillか」の根拠未記載と責務境界の曖昧さ。→ 設計判断ログ節 + 実行経路×入力種別カバレッジ表 + agent責務差別化で明文化。**新規skill分割は不要(分割コスト過大)**。
2. **外部ライブラリのvendor同梱**: 逆説思考が喝破 — 全script stdlib完結で外部依存ゼロ、pip不要は既に達成。requests同梱はむしろ負債。→ ユーザー承認のうえ標準ライブラリ維持 + `lint-company-master-vendored-deps.py`(外部import出現→vendor必須)で空vendorを機械正当化。bootstrap docstring正確化。
3. **skill-creator仕様準拠**: 最大欠陥=二段防御の静的層(settings.json)欠落=片肺。→ contract-generatorパターンを横展開し `references/settings-hardening.json` 同梱。hook requires-python 3.11→3.10統一。db_id直書きを意図的既定として明記。

## 適用パッチ(Group別)

- **C(セキュリティ)**: settings-hardening.json新設 / SKILL.mdセキュリティ節を実体一致 / hook requires-python統一
- **A(責務境界)**: 設計判断ログ節 / 実行経路×入力種別カバレッジ表 / agent 3件の責務差別化+R1参照 / company_master.py に upsert_skip_reason
- **B(vendor機械保証)**: lint-company-master-vendored-deps.py新設+Makefile配線 / bootstrap docstring / vendor README+composition明記
- **D(config整合)**: scriptヘッダをget_db_id経由表記へ統一 / fixed.json `_doc` / README-setup.md新設
- **E(品質バグ)**: open_issues節に4件(KEN_ALL律速/backfill validate迂回/gBizINFO V1↔V2/確度保守設計)を別PR記録

## 検証実行ログ

- py_compile 全script: OK
- lint-company-master-vendored-deps.py: exit0 (scripts 11件 外部依存ゼロ)
- make lint 完走: exit0
- validate-frontmatter (reference_refs +2): OK
- 二段確認の所見: メモリの「postal_from_address は TODOスタブ」は誤り→実コードL100は実装済みと是正

## proposer ≠ approver

- proposer: elegant-improvement-executor (分離context)
- approver: 親session が独立に fresh read + lint再走行で承認 (executor報告を鵜呑みにせず実装文脈で二段確認)

## 残課題(別PR)

open_issues 4件は実データ/APIトークン無しで検証困難ゆえ別PR。marketplace.json/bundles.json への company-master 登録配線は本スコープ外。

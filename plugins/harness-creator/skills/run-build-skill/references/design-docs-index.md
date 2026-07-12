# 設計書索引（Progressive Disclosure）

ベース: `{{DOC_ROOT}}/ClaudeCodeスキルの設計書/`

| 章 | ファイル | 用途 |
|---|---|---|
| 00 | 00-overview.md | 全体俯瞰 |
| 00a | 00a-quickstart-beginner.md | 入門 |
| 01 | 01-design-philosophy.md | 設計哲学 |
| 01a | 01a-build-flow.md | 構築フロー |
| 02 | 02-claude-code-skill-spec.md | 公式仕様 |
| 03 | 03-yaml-frontmatter-reference.md | frontmatter全フィールド |
| 04 | 04-invocation-permissions-settings.md | 発動と権限 |
| 05 | 05-layering-skill-subagent-hook-mcp-cli.md | レイヤリング |
| 06 | 06-classification-and-naming.md | 命名規約 |
| 07 | 07-progressive-disclosure.md | 段階的開示 |
| 08 | 08-skill-writing-guidelines.md | 執筆ガイド |
| 09 | 09-evaluation-orchestration.md | 評価編成、Goodhart |
| 10 | 10-subagents-hooks-integration.md | hook統合 |
| 11 | 11-templates.md | テンプレ集 |
| 12 | 12-image-extraction-map.md | 画像証跡対応表 |
| 13 | 13-checklists.md | チェックリスト / P0-P2ゲート |
| 14 | 14-dynamic-context-injection.md | 動的注入 |
| 15 | 15-official-source-notes.md | 公式出典 |
| 16 | 16-official-skills-complete-reference.md | 公式Skill例 |
| 17 | 17-agent-teams-reference.md | Agent Teams |
| 18 | 18-complete-examples.md | 完成例 |
| 19 | 19-troubleshooting.md | トラブル |
| 20 | 20-migration-path.md | 移行 |
| 21 | 21-source-traceability.md | 出典追跡 |
| 22 | 22-cross-platform-runtime.md | Mac専用抽出 |
| 23 | 23-meta-skill-architecture.md | メタSkill構成 |
| 24 | 24-meta-skill-templates.md | 正本テンプレ |
| 25 | 25-meta-skill-runbook.md | 運用Runbook |
| 26 | 26-meta-skill-dogfooding.md | ドッグフード |
| 27 | 27-rubric-governance-runbook.md | rubric改正 |
| 28 | 28-script-execution-model.md | script実行 |
| 29 | 29-multi-project-rubric-composition.md | 多重継承 |
| 30 | 30-paradigm-analogy-map.md | 類推地図 |
| 31 | 31-output-routing-adapter-architecture.md | 出力先routing / adapter分離 |
| 32 | 32-creator-kit-implementation-ledger.md | 実装台帳 / 正本と派生 / 残課題 |
| 33 | 33-change-governance.md | 変更分類 / 承認 / cooldown / blast radius |
| 34 | 34-plugin-governance-roadmap.md | plugin境界 / 移行ゲート / 外部参照棚卸し / .claude symlink戦略 (build-claude-symlinks.py) |
| 35 | 35-meta-harness-feedback-loop.md | セッションログ由来の自己改善ループ |

## 読み順（用途別）

- **初学者**: 00a → 01 → 02 → 03 → 24
- **再現性重視の作成**: 01 → 01a → 05 → 06 → 13
- **frontmatter書く**: 03 → 22 → 02
- **命名**: 06 → ref-skill-naming-convention
- **評価Skill作る**: 09 → 24 → 29
- **rubric改正**: 27 → 29
- **script書く**: 28 → 22
- **テンプレート生成**: 11 → 24
- **量産Skill基盤**: 29 → 30 → 31
- **creator-kit配布・再現性**: 32 → 29 → 31
- **governance変更**: 33 → 27 → 28
- **plugin移行**: 34 → 33 → 23
- **log由来改善 / Meta-Harness**: 35 → 33 → 27
- **出力先追加**: 31 → 28 → 04
- **ゲート確認**: 13 → 25
- **元記事・画像証跡確認**: 12 → 21

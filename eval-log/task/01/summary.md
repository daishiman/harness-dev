# タスク 01 完了報告

## 走査統計
- 対象 SKILL.md: 39 件
- 検出参照: 679 件
- 違反候補: 191 件

## verdict 内訳
- migrate: 119
- allow: 58
- deprecate: 14
- defer: 0 (全違反の 0.0%、上限 30%)

## 判定ルール
- `doc/` 参照は plugin 外設計書依存のため、plugin 内 `references/design-docs/` へ migrate。
- source skill 配下に実体がある `scripts/` 参照は、skill-local 相対参照として allow。
- repository root に実体がある `scripts/` 参照は、plugin root `scripts/` へ migrate。
- 実体が見つからない `scripts/` 参照は、移行前に削除・補正・実体化が必要なため deprecate。

## 後続タスクへの引き継ぎ
- タスク 02 settings merge で考慮すべき外部参照: `doc/` 由来の設計参照を plugin 内 references へ取り込む方針を前提にする。主要候補: `doc/20`, `doc/20-migration-path.md`, `doc/21`, `doc/ClaudeCodeスキルの設計書/`, `doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md`, `doc/ClaudeCodeスキルの設計書/09-evaluation-orchestration.md`, `doc/ClaudeCodeスキルの設計書/17-agent-teams-reference.md`, `doc/ClaudeCodeスキルの設計書/20-migration-path.md`, `doc/ClaudeCodeスキルの設計書/21-source-traceability.md`, `doc/ClaudeCodeスキルの設計書/22-cross-platform-runtime.md`, `doc/ClaudeCodeスキルの設計書/26-meta-skill-dogfooding.md`, `doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md` ...
- タスク 03 symlink 構築で考慮すべき外部参照: skill-local `scripts/` を symlink 対象から落とさず、plugin root `scripts/` へ移すものと区別する。主要候補: `scripts/adapters/`, `scripts/adapters/dispatch.py`, `scripts/adapters/resolve_route.py`, `scripts/adapters/sink_linear.py`, `scripts/build-manifest-registration-plan.py`, `scripts/build-paradigm-scorecard.py`, `scripts/build-subagent.py`, `scripts/compose-rubrics.py`, `scripts/cross_platform_secret.py`, `scripts/diff-rubric-impact.py`, `scripts/hook-`, `scripts/lint-rubric-violation.py` ...
- defer 案件の次 Phase 持ち越し: なし。

## Phase 0 制約 e ステータス

- 公式制約 e (plugin 内 Skill が plugin 外の scripts/adapters/.claude/config/ を参照することを禁ずる) の暫定 FAIL に対し、本タスクで違反候補 191 件を全件分類済。
- 内訳: migrate 119 / allow 58 / deprecate 14 / defer 0。
- 後続タスク 02〜07 で migrate/deprecate を実体反映すれば、制約 e は PASS 化可能な状態にある。
- 走査ツール契約 (`scripts/lint-external-refs.py` v2 仕様 Step 7.3) は 2026-05-20 再検証で CONTRACT MATCH を確認済。


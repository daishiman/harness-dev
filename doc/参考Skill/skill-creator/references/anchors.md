# skill-creator Anchors（設計原則の出典）

skill-creator が依拠する 7 つの設計アンカー。SKILL.md の description には主要 3 件のみを残し、詳細はここに集約する。

## 主要 3 件（description 残置）

| # | Anchor | 適用 | 目的 |
|---|--------|------|------|
| 1 | Continuous Delivery (Jez Humble) | 自動化パイプライン | 決定論的実行 |
| 2 | The Lean Startup (Eric Ries) | Build-Measure-Learn | 反復改善 |
| 3 | Domain-Driven Design (Eric Evans) | 戦略的設計・ユビキタス言語・Bounded Context | ドメイン構造の明確化 |

## 補助 4 件（references 集約）

| # | Anchor | 適用 | 目的 |
|---|--------|------|------|
| 4 | Clean Architecture (Robert C. Martin) | 依存関係ルール・層分離設計 | 変更に強い高精度スキル |
| 5 | Design Thinking (IDEO) | ユーザー中心設計 | 共感と共創 |
| 6 | Progressive Disclosure | SKILL.md 200 行 entrypoint + references 分割 | 並列衝突の局所化 |
| 7 | Changesets pattern | LOGS / changelog の fragment 化 | append-only ledger の 3-way merge 衝突回避 |

## 運用メモ

- description は Codex CLI の R-04（≤ 1024 文字）に収めるため主要 3 件に絞る。
- 全 7 件は実装上同等に重要であり、ガイド・レビュー時はこのファイルを正本として参照すること。
- アンカー追加・改廃時はこのファイルと SKILL.md description の両方を更新する。

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-04-28 | 初版作成（SKILL.md description から退避、Codex R-04 対応） |

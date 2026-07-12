---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビューゲート)

## 目的
P02 の設計 (`component-inventory.json` と envelope draft) を design-gate として elegant-review C1-C4 で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。設計段階の欠陥 (単一 skill 退化・分類 SSOT の重複・C04 既存実装の破壊的上書き) を実装前に止める gate フェーズ。

## 背景
分類ロジックを C05 という薄い差分エンジンへ、単一恒久 report DB の既存確認/配置/冪等 upsert を C06 sink へ分離する設計判断や、C01 がオーケストレーションに徹しこれらへ委譲する境界が適切かどうかは、実装後に見直すとレポート・sub-agent・guard の複数者を巻き込む手戻りになる。C04 は新規 build でなく既存稼働 hook への in-place 拡張 (`build_mode=extend-existing`) であるため、既存 R1-R3/allowlist を破壊しないことも本審査の対象。提案者と承認者を分離 (proposer≠approver) することで、単一 skill への退化や既存 reconcile との分類共有 over-claim を実装前に検出する。

## 前提条件
- P02 の `component-inventory.json` と `envelope-draft/plugin.json` が生成済み。
- elegant-review 4 条件 (矛盾なし/漏れなし/整合性/依存整合) の評価枠組みを参照できる。
- レビュアは提案者と別 context で評価する (構造的に proposer≠approver)。

## ドメイン知識
design-gate = elegant-review C1-C4 を設計スコープ (inventory+envelope draft) に適用したもの (C1-C4 の定義は index `## ドメイン知識` 参照)。本 plan 固有の差分: 単一 skill 退化 = 前月↔今月比較・分類ロジックや冪等 upsert が C01 スキルへ畳まれ C05/C06 の独立性が失われた状態、または C05 が reconcile との分類共有を過大主張 (over-claim) している状態 (本審査の主要判定対象)。

## 成果物
- design-gate の判定記録 (C1-C4 全 PASS / 差し戻し理由)。

## スコープ外
- 指摘の修正そのもの (P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計 (P04)・実装 (P05)。
- 機械 lint の実行 (P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が全 PASS し、proposer と異なる approver が設計を承認している。
- [ ] C05/C06 の独立昇格根拠 (独立単体テスト可能性・over-claim 撤回済み) が妥当と確認され、単一 skill への退化が無い。
- [ ] C04 の `build_mode=extend-existing` が既存 R1-R3/allowlist/hooks 配線を保全する設計であることが確認されている。
- [ ] 差し戻しが解消され後続フェーズへ進める状態になっている。

## 参照情報
- P02 成果物 (`component-inventory.json` / `envelope-draft/plugin.json`)。
- `assign-plugin-plan-evaluator` (評価ロジックの正本・proposer≠approver)。
- 後続 P04 (test-design)。

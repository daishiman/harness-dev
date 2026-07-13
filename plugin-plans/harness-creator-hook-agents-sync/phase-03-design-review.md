---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 完了
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビューゲート)

## 目的

P02 設計を提案者と別 context で審査し、4条件と structural blocker を判定する。

## 背景

旧 plan は構造 validator が PASS しても official surface と stale findings の意味矛盾を見逃した。design gate は shape だけでなく意味契約を審査する。

## 前提条件

- P02 成果物と official source snapshot が存在する。
- approver は proposer の中間結果を参照しない。

## ドメイン知識

- 4条件: 矛盾なし / 漏れなし / 整合性あり / 依存関係整合。
- structural blocker: source/owner/trust/reflector compatibility の未確定。
- stale digest の review verdict は無効。

## 成果物

- 4条件 verdict と finding→owner→修正→再検証 trace。
- critical/high=0 または明示 blocked の decision record。

## スコープ外

- 実装パッチ。
- blocker を warning へ格下げして進める判断。

## 完了チェックリスト

- [ ] official source と plan の意味 parity を確認する。
- [ ] 5 component/5 route/digest が現物と一致する。
- [ ] structural blocker 未解決なら P04 以降を block する。
- [ ] proposer≠approver が証跡化される。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 4条件別の根拠と artifact digest がある。
- 満たさない例: validator exit0 だけを根拠に PASS する。

### 事前解決済み判断

- critical/high finding を open issue に残したまま design GO にしない。

## 参照情報

- `plan-findings.json`
- `goal-spec.json` C10

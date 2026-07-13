---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: 
---

# P13 — release (完了)

## 目的
build 完了後、人手による feature→main 反映 (`make validate` + pytest 緑化・version bump) が行われる前提を確認可能な状態にする (評価ゲート化しない)。

## 背景
旧「PR 作成 (PR/IPC/Cloudflare)」は全 DROP し、PR は xl-skills feature→main + `make validate` + pytest 完了条件の soft note として本 skill の責務外に留める (phase-lifecycle.md §7 P13行 / io-contract.md §10 PR節)。

## 前提条件
P09-P11 で品質機構・evidence 観点が確定済み。version bump は 0.4.0 (前回 PR#85・MF実績第一級化) → 0.5.0 (本 plan・照合層根治) を提案する。

## ドメイン知識
本 skill は PR 作成も `make validate`/pytest 実行も行わない。release 完了条件は評価ゲートに組み込まない (`quality_gates`/検査スクリプトに PR キーを設けない、io-contract.md §10 PR節)。

## 成果物
feature→main 反映の soft note (人手作業の前提記述のみ)。version bump 提案 (0.4.0→0.5.0) を `envelope-draft/plugin.json` へ反映する参照。

## スコープ外
実際の git 操作 (commit/PR 作成/CI 実行) は build 完了後の人手作業であり、本フェーズ・本 skill の責務外。

## 完了チェックリスト
- [ ] soft note「build 完了後、人手が feature→main 反映 (`make validate` + pytest 緑化前提) を行う」が明記されている
- [ ] version bump 提案 (0.4.0→0.5.0) が `envelope-draft/plugin.json` と整合している
- [ ] 評価ゲート化していない (`quality_gates`/検査スクリプトに PR 関連キーを追加していない)

## 参照情報
phase-lifecycle.md §8 P13 セル / io-contract.md §10 PR節 / `envelope-draft/plugin.json`

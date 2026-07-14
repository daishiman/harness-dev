---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (手動テスト検証)

## 目的
決定論ゲート (core + 拡張) の実行証跡と、実際の task-graph 生成コマンド実行結果を再現可能な evidence として収集する。

## 背景
Anti-Goodhart 原則 (tmux 実走受入等) により、「テストが書いてある」ではなく「実際に実行され exit0 になった」証跡を残す。本フェーズは P01-P10 の宣言的完了とは独立に、実行ログという一次情報を確定する。

## 前提条件
- P10 の final-review が承認済み。

## ドメイン知識
- evidence = 決定論ゲート 11 本 (12 起動) の実行ログ + `derive-task-graph.py` の実行結果 (`task-graph.json` 生成)。
- gate_type=evidence は「宣言」ではなく「実行結果の記録」であることを区別する。

## 成果物
- 決定論ゲート全起動の実行ログ (exit code + stdout/stderr 要約)。

## スコープ外
- documentation (P12)。

## 完了チェックリスト
- [ ] 全決定論ゲートの実行証跡 (exit code) が保存されている。
- [ ] `derive-task-graph.py` の実行結果 (`task-graph.json`) が再現可能な形で記録されている。
- [ ] repo-A/repo-B isolation、host project-root/repository_id不一致、broken content symlink、host broken-harness-link preflight、containment拒否、init hash不変、promotion digest/atomicityの一次証跡が保存されている。

## 参照情報
- `io-contract.md` §11 (決定論検査スクリプト一覧)。
- 後続 P12 (documentation)。

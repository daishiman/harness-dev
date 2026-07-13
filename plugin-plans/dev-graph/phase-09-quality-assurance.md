---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C24, C25, C26, C27, C28, C29]
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証ゲート)

## 目的
全componentへ焼き込む`quality_gates`と後段L4 buildのQA実行契約を確定する。本L3 planではplan-scoped決定論ゲートを実走する一方、未生成の実pluginに対するlint全緑は宣言しない。

## 背景
purpose 受入 (P07) と AC を壊さない改善 (P08) を経ても、機械可読な品質基準 (lint/schema/coverage) を満たさなければ配布・運用に耐えない。本フェーズは component 種別ごとの lint 群を一括実行し、exit0 で揃える qa gate。

## 前提条件
- P08で後段refactoring checklistが確定している。
- 各 component の `quality_gates` (skill=8-lint block・agent/command/hook/script 各対応 lint) が inventory に確定している。
- `check-spec-frontmatter.py` / `check-spec-gates.py` / `check-spec-matrix-coverage.py` を含む決定論ゲート群が実行可能。

## ドメイン知識
- qa gate = component 種別ごとの機械 lint 群を全域に対して実行し、exit0 で揃える工程 (種別横断の最終品質チェックポイント)。
- kind 別 quality_gates: skill=8 種 lint block、sub-agent/slash-command/hook/script はそれぞれ対応する lint セット (SSOT は io-contract §7 discipline 表)。
- 決定論ゲートは`run-plugin-dev-plan` 側の 12 スクリプト呼び出しが正本 (plan 生成物自身の検証はこの qa gate と独立)。

## 成果物
- plan-scoped gate実行ログと、後段buildが生成すべきcomponent quality-gate evidence contract。

## スコープ外
- purpose 受入の再判定 (P07 で完了済み)。
- 最終審査そのもの (P10 の proposer≠approver レビュー)。
- カバレッジ数値の再設計 (閾値は P04/P06 で確定済み)。

## 完了チェックリスト
- [ ] 全componentがkind別quality_gatesを契約として携帯する。
- [ ] plan-scoped決定論ゲートがexit0である。
- [ ] 後段buildがcomponent lint/coverage/AC回帰を実走してevidence化する境界が明記されている。

### 受入例
- 満たす例: skill×9 全てで `lint-skill-name`/`lint-skill-description`/`lint-skill-tree`/`validate-frontmatter`/`lint-dependency-direction`/`lint-skill-dep-step7`/`lint-forbidden-deps`/`lint-manifest-contents` の 8 lint が exit0。
- 満たす例: hooks (C10/C25) が `validate-frontmatter`/`lint-script-frontmatter` を exit0 で通過し、gh write guardとTaskCompleted pending_review park/identity限定blockが壊れていない。
- 満たさない例: いずれか 1 component でも lint が exit1 → qa gate 全体が FAIL となり P10 へ引き渡せない。

### 事前解決済み判断
- kind 別 quality_gates の lint セットは io-contract §7 discipline 表を正本とし、本フェーズで新規 lint を発明しない。
- qa gate は P07 (purpose 受入) と独立した機械品質チェックポイントであり、purpose 受入の再判定は行わない。

## 参照情報
- `component-inventory.json` (各 component の quality_gates)。
- io-contract §7 (kind 別 discipline 表)。
- 対象 component C01-C19・C24-C29 (計25)。
- 後続 P10 (final-review)。

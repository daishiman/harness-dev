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

# P11 — evidence (エビデンス確定)

## 目的
P10のL3 plan承認結果とplan-scoped gate evidenceを固定し、後段L4 buildがmarkdown-evidence-5-elementsをどこへ記録するかを契約化する。未実行のbuild evidenceを本planの事実として扱わない。

## 背景
承認 (P10) と実測 (P09) が揃っていても、後から参照できる形でエビデンスを固定しなければ再現性・監査可能性が失われる。本フェーズは 5 要素モデルに沿って evidence を一箇所に確定し、以降のフェーズが再検証せず参照できるようにする。

## 前提条件
- P10 の final-gate が承認済み。
- P09のplan-scoped gate実行ログが揃い、harness coverage実測は後段pendingとして区別されている。
- markdown-evidence-5-elements の定義 (lint exit0 / schema parity / build-trace coverage PASS / content-review verdict PASS / harness coverage JSON) を参照できる。

## ドメイン知識
- markdown-evidence-5-elements: lint exit0・schema parity・build-trace coverage PASS・content-review verdict PASS・harness coverage JSON の 5 点セット (いずれか欠落は evidence 不完全)。
- evidence は事後の再検証を不要にするための固定記録であり、P12/P13 はこれを参照するのみで再実測しない。

## 成果物
- L3 plan gate evidenceと、後段L4 build evidence 5要素のpath/status manifest。

## スコープ外
- 新規テストの実行 (P09 の実測結果を確定するのみ)。
- 文書化そのもの (P12)。
- リリース判断 (P13)。

## 完了チェックリスト
- [ ] L3 plan gate evidenceが揃い、L4 build evidenceは`pending`としてpathと取得ownerが記録されている。
- [ ] P10 final-gate の承認記録と整合している (矛盾がない)。
- [ ] P12/P13 が再実測なしにこの evidence を参照できる状態になっている。

### 受入例
- 満たす例: plan gateはpresent、未生成pluginのlint/coverageはpendingとして混同なくmanifest化され、後段buildで5点がpresentへ昇格する条件がある。
- 満たさない例: harness coverage JSON のみが欠落している → 5 要素モデル未充足として本フェーズ完了条件を満たさない (P12 へ進めない)。
- 満たさない例: evidence の対象 component 集合が P10 承認記録の対象集合と食い違う (例: C18 が evidence に含まれない) → 整合性違反。

### 事前解決済み判断
- evidence は事後の再検証を不要にする固定記録であり、P12/P13 は再実測せずこれを参照する (5 要素モデルは追加・削減しない)。
- evidence 確定後に矛盾が見つかった場合は P09/P10 へ差し戻し、本フェーズ内で数値を書き換えない。

## 参照情報
- markdown-evidence-5-elements (定義の正本)。
- P09/P10 成果物。
- 後続 P12 (documentation)。

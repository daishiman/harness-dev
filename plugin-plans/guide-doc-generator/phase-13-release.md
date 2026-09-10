---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
applicability:
  applicable: true
  reason: guide-doc-generator の全 component に対して適用する
---

# P13 — release (完了)

## 目的

plugin を利用可能な状態として確定する。本 repo 内での利用を先行させ、外部配布はユーザー承認を経てから行う判断を明示した状態にする。

## 背景

初版は実題材での運用実績が 1 件の段階にある。この段階で marketplace 登録まで一気に進めると、契約の未成熟が外部利用者へ波及する。まず repo 内で使い、改善の受け皿を用意してから配布を判断する。

## 前提条件

- P12 まで完了し文書が揃っている
- 全ゲートが PASS で証跡が保全されている

## ドメイン知識

- **配布の段階**: repo 内利用 → 承認後の marketplace 登録、の 2 段。manifest の配布可否フラグと bundles の記述を整合させる
- **改善の受け皿**: 利用時に見つかった不足を記録して次版へ回す経路を用意する
- **外部公開の承認**: marketplace 登録は利用者に見える行為であり、ユーザー承認なしに進めない

## 成果物

- 利用可能状態の宣言 (repo 内)
- 配布判断の記録 (marketplace 登録は保留とその理由)
- 改善事項の記録先
- 次版の候補事項

## スコープ外

- marketplace への実登録 (ユーザー承認後に別途)
- 題材別テンプレートの拡充 (次版)

## 完了チェックリスト

- [ ] repo 内で利用可能な状態が宣言されている
- [ ] manifest の配布可否と実体が整合している
- [ ] marketplace 登録の判断と理由が記録されている
- [ ] 改善事項の記録先が決まっている

### 受入例 (満たす例 / 満たさない例)

- 満たす例: repo 内で利用可能な状態が宣言され、manifest の配布可否と実体が整合し、marketplace 登録の判断と理由が記録されている。
- 満たさない例: 配布不可と宣言しながら marketplace 登録の判断そのものが記録されておらず、次の担当者が再検討を一から行うことになる。

### 事前解決済み判断

- 本 plugin は repo 内利用を既定とし配布はしない。marketplace 登録は判断と理由を記録し、実登録は人手承認を経る。
- **2026-08-18 に上記の判断を反転した (裁定の履歴を消さず追記で残す)。** 反転の根拠は、利用者から「ローカルのプラグインと GitHub にプルリクを出した後の、そこからのマーケットプレイスからのインストールができる両方が対応できるようになっているか確認しておいてください」という配布 2 経路の成立を求める明示要求があったこと。これが元の判断が留保していた「人手承認」そのものにあたる。したがって `distributable` を true とし、`.claude-plugin/marketplace.json` (name: skills) と `.claude-plugin/bundles.json` (skills-full) へ登録する。
- 反転にあたって留保していたリスク (契約の未成熟が外部利用者へ波及する) は消えていない。緩和として、初版を `0.1.0` とし、4 スイート 836 件の緑と 4 ゲートの実測 PASS を EVALS.json へ記録した状態でのみ配布する。改善の受け皿は `plugin_meta.feedback_deploy` の `improvement-request` sink を用いる。

## 参照情報

- 要件正本: `goal-spec.json` (checklist C1-C45)
- component 正本: `component-inventory.json`
- 参照解析: `{{PROJECT_ROOT}}/analysis/guide-doc-generator/reference-analysis.md`
- plan 全体像と用語集: `index.md`


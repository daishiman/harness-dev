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
UBM のスクショ検証を DROP し、Markdown による evidence 5 要素へ写像する evidence gate。プラグインが受入を満たしたことを再現可能な形で記録する。

## 背景
UBM 固有の GUI スクリーンショット検証は本ドメイン (CLI/プラグイン) に写像できないため DROP し、再現可能な Markdown evidence 5 要素へ写像する。第三者が受入充足 (カテゴリ×プラットフォーム網羅を含む) を再現・確認できる形で記録することが evidence gate の目的で、DROP 読替の正本は phase-lifecycle.md §7。

## 前提条件
- P10 の final-gate を通過している。
- P0 lint / schema parity / build-trace / content-review / harness の各結果が取得可能。
- evidence は Markdown で残す (GUI スクショに依存しない)。

## ドメイン知識
- 再現可能性の要件: 第三者が evidence 記載のコマンド/入力 (例: サンプルヒアリング応答セット=C01 所有の tracked fixture) を再実行して同じ合否へ到達できること (ログ貼付だけでは不足)。
- DROP 読替の正本は `phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence 5 要素)。他の plan 全体用語は index `## ドメイン知識` 参照。

## 成果物
- evidence 5 要素 (P0 lint ログ / schema parity / build-trace coverage / content-review verdict / harness coverage JSON) を集約した Markdown 検証記録。
- goal-spec C1-C16 / P07 AC evidence matrix (AC id / fixture / 再実行command / artifact / PASS|FAIL verdict) を同じ記録に含める。

## スコープ外
- 新規の検証実施 (P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化 (P12)。

## 完了チェックリスト
- [ ] evidence 5 要素が全て Markdown に記録されている。
- [ ] goal-spec C1-C16 と P07 の各ACが evidence matrix に1:1で現れ、ヒアリングresume、foundation/decision state、open-world knowledge depth、prompt C1-C4、公式文書鮮度、C05自動連鎖、Write/Edit+Bash負例、知識グラフDAG/dangling検証、知識位相順消費、doctrine anchor反映、必須情報カタログ収集順序を再現できる。
- [ ] 第三者が記録から受入充足 (カテゴリ×プラットフォーム網羅を含む) を再現・確認できる状態になっている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: evidence matrix に C1-C16/P07 AC が全件並び、foundation/decision/deep-knowledge/prompt-validator、6周超ヒアリング、citation負例、C10→C05連鎖、書換負例、知識グラフDAG/dangling検証(validate-knowledge-graph.py)、位相順消費、doctrine anchor反映、必須情報カタログ収集順序のcommandとartifactが併記される。
- 満たさない例: 実行ログの貼付のみで再現入力 (fixture) への参照が無く、第三者が同じ検証を再実行できない。

### 事前解決済み判断
- 分岐点: GUI スクリーンショット検証を残すか → 判断: DROP し Markdown evidence 5 要素へ写像する (正本=phase-lifecycle.md §7・CLI ドメインにスクショは写像不能)。

## 参照情報
- `references/phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence の DROP 読替表)。
- evidence 5 要素 (lint/schema/build-trace/content-review/harness)。
- 後続 P12 (documentation)。

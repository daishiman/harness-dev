---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 完了
gate_type: evidence
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (手動テスト検証)

## 目的
UBM 元資産のスクショ検証の慣習を DROP し、Markdown による evidence 5 要素へ写像する evidence gate。プラグインが受入を満たしたことを再現可能な形で記録する。

## 背景
UBM 元資産は個人 vault 運用の中で GUI/Obsidian のスクリーンショットによる手動検証を慣習としていたが、本ドメイン (CLI/プラグイン) には写像できないため DROP し、再現可能な Markdown evidence 5 要素へ写像する。第三者が受入充足を再現・確認できる形で記録することが evidence gate の目的で、DROP 読替の正本は phase-lifecycle.md §7。

## 前提条件
- P10 の final-gate を通過している。
- P0 lint / schema parity / build-trace / content-review / harness の各結果が取得可能。
- evidence は Markdown で残す (GUI スクショに依存しない)。

## ドメイン知識
- 再現可能性の要件: 第三者が evidence 記載のコマンド/入力を再実行して同じ合否へ到達できること (ログ貼付だけでは不足)。
- DROP 読替の正本は `phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence 5 要素)。他の plan 全体用語は index `## ドメイン知識` 参照。

## 成果物
Markdown evidence として以下 5 要素を集約した検証記録:
1. P0 lint が exit0 になったログ (18 component 分)。
2. schema parity テストの結果。
3. build-trace coverage の結果。
4. content-review verdict (PASS・sha 一致)。
5. harness coverage の JSON (kind 別 ≥80%、EVALS.json 準拠)。

格納先: `eval-log/ubm-goal-setting/_plugin/build-evidence/<YYYYMMDD>/` (evidence.md + 補助 JSON/ログ)。初回生成分は `20260705/`。

## スコープ外
- 新規の検証実施 (P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化 (P12)。

## 完了チェックリスト
- [ ] evidence 5 要素が全て Markdown に記録されている。
- [ ] 第三者が記録から受入充足を再現・確認できる状態になっている。
- [ ] evidence 収集時の criteria-test/coverage 実行 cwd は CI が実際に使う cwd (plugin ディレクトリ) に pin されている (repo-root での実行結果は CI 緑の証跡として扱わない)。

## 参照情報
- `references/phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence の DROP 読替表)。
- evidence 5 要素 (lint/schema/build-trace/content-review/harness)。
- 後続 P12 (documentation)。

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
UBM のスクショ検証を DROP し、Markdown による evidence 5 要素へ写像する evidence gate。プラグインが REQ1a/1b/1c/REQ2/REQ3/REQ4 の受入を満たしたことを再現可能な形で記録する。

## 背景
UBM 固有の GUI スクリーンショット検証は本ドメイン (CLI/プラグイン) に写像できないため DROP し、再現可能な Markdown evidence 5 要素へ写像する。第三者が受入充足を再現・確認できる形で記録することが evidence gate の目的で、DROP 読替の正本は phase-lifecycle.md §7。

## 前提条件
- P10 の final-gate を通過している。
- P0 lint / schema parity / build-trace / content-review / harness の各結果が取得可能。
- evidence は Markdown で残す (GUI スクショに依存しない)。

## ドメイン知識
- 再現可能性の要件: 第三者が evidence 記載のコマンド/入力を再実行して同じ合否へ到達できること (ログ貼付だけでは不足)。
- DROP 読替の正本は `phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence 5 要素)。
- 全量evidenceはauthoritative snapshot hash、discovered/ingested/pending/waived件数、waiver承認参照を残す。
- 自動syncはscheduler invocation/cursor/lease/retry、graphはedge evidence、harnessはartifact path/graph hash/redaction countを残す。

## 成果物
- evidence 5 要素 (P0 lint ログ / schema parity / build-trace coverage / content-review verdict / harness coverage JSON) を集約した Markdown 検証記録。

## スコープ外
- 新規の検証実施 (P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化 (P12)。

## 完了チェックリスト
- [ ] evidence 5 要素が全て Markdown に記録されている。
- [ ] 第三者が無人sync、content coverage 100%、non-zero edge、real artifact dereferenceを再現できる。

### 受入例
snapshot hash、coverage counts、scheduler cursor、edge evidence、artifact graph hashを第三者が再実行できる。

### 事前解決済み判断
GUI screenshotは不要。secret/PII/transcript命令はevidenceへ保存しない。

## 参照情報
- `references/phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence の DROP 読替表)。
- evidence 5 要素 (lint/schema/build-trace/content-review/harness)。
- 後続 P12 (documentation)。

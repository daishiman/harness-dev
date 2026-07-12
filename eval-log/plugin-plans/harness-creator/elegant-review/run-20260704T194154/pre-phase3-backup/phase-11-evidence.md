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
UBM のスクショ検証を DROP し、Markdown による evidence 5 要素へ写像する evidence gate。C8 (新規作成フロー一巡) / C9 (改善フロー一巡) を実プラグイン上で再現した記録を含め、量産パイプラインが受入を満たしたことを再現可能な形で記録する。

## 背景
UBM 固有の GUI スクリーンショット検証は本ドメイン (CLI/プラグイン) に写像できないため DROP し、再現可能な Markdown evidence 5 要素へ写像する。第三者が受入充足を再現・確認できる形で記録することが evidence gate の目的で、DROP 読替の正本は phase-lifecycle.md §7。

## 前提条件
- P10 の final-gate を通過している。
- P0 lint / schema parity / build-trace / content-review / harness の各結果が取得可能。
- evidence は Markdown で残す (GUI スクショに依存しない)。P07 で固定した C8/C9 golden example の fixture とコマンド列を再実行し、期待 artifact と実出力の一致を記録する。

## ドメイン知識
- 再現可能性の要件: 第三者が evidence 記載のコマンド/入力を再実行して同じ合否へ到達できること (ログ貼付だけでは不足)。
- DROP 読替の正本は `phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence 5 要素)。他の plan 全体用語は index `## ドメイン知識` 参照。
- C8/C9 の evidence は P07 の golden example を正本にする。C8 は `fixtures/c8-new-flow/intake.json` / `next-action.json` を入力し、`demo-boundary-skill` の新規作成フローが `C01→C02→C07→C08 preflight→C06 build dispatch` へ進むログを記録する。C9 は `fixtures/c9-update-flow/improvement-handoff.json` を入力し、`C09→C11 preflight→C01 update→C05→C10→build 再実行` の PASS ログと、marker 欠落時に C11 が exit2 block する FAIL ログを両方記録する。

## 成果物
- evidence 5 要素 (P0 lint ログ / schema parity / build-trace coverage / content-review verdict / harness coverage JSON) を集約した Markdown 検証記録。
- C8/C9 一巡実演の実行ログ (fixture path + コマンド列 + exit code + 期待 artifact 差分 0)。

## スコープ外
- 新規の検証実施 (P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化 (P12)。

## 完了チェックリスト
- [ ] evidence 5 要素が全て Markdown に記録されている。
- [ ] C8 (新規作成フロー) / C9 (改善フロー) の golden example が P07 指定の fixture で再実行され、第三者が追加質問なしに再現・確認できる状態になっている。

## 参照情報
- `references/phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence の DROP 読替表)。
- evidence 5 要素 (lint/schema/build-trace/content-review/harness) + C8/C9 一巡実演ログ。
- 後続 P12 (documentation)。

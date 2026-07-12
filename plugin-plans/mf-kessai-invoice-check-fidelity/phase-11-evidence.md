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
UBM のスクショ検証を DROP し、Markdown による evidence 5 要素へ写像する evidence gate。改善が症状①〜⑦を解消し受入を満たしたことを再現可能な形で記録する。

## 背景
UBM 固有の GUI スクリーンショット検証は本ドメイン(CLI/プラグイン)に写像できないため DROP し、再現可能な Markdown evidence 5 要素へ写像する。第三者が「症状①〜⑦が実際に解消したか」を evidence 記載のコマンド/fixture から再現・確認できる形で記録することが本ゲートの目的。

## 前提条件
- P10 の final-gate を通過している。
- P0 lint / schema parity / build-trace / content-review / harness の各結果が取得可能。
- evidence は Markdown で残す(GUI スクショに依存しない)。

## ドメイン知識
- 再現可能性の要件: 第三者が evidence 記載のコマンド/fixture を再実行して同じ合否へ到達できること(ログ貼付だけでは不足)。
- DROP 読替の正本は `phase-lifecycle.md` §7(UBM スクショ→Markdown evidence 5 要素)。
- 本改善固有の evidence: 症状①〜⑦ゴールデン fixture の実行ログと、fetch fidelity gate の fail-closed 動作ログを含める。

## 成果物
- evidence 5 要素(P0 lint ログ / schema parity / build-trace coverage / content-review verdict / harness coverage JSON)を集約した Markdown 検証記録(症状①〜⑦の再現結果を含む)。

## スコープ外
- 新規の検証実施(P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化(P12)。

## 完了チェックリスト
- [ ] evidence 5 要素が全て Markdown に記録されている。
- [ ] 症状①〜⑦ゴールデン fixture の実行結果(解消確認)が evidence に含まれている。
- [ ] 第三者が記録から受入充足を再現・確認できる状態になっている。

## 参照情報
- `references/phase-lifecycle.md` §7(UBM スクショ→Markdown evidence の DROP 読替表)。
- evidence 5 要素(lint/schema/build-trace/content-review/harness)。
- 後続 P12(documentation)。

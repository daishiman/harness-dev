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
GUI スクショ検証を DROP し、Markdown による evidence 5 要素へ写像する evidence gate。プラグインが受入を満たしたことを再現可能な形で記録する。生成物は HTML/CSS/JS/SVG のローカル出力ゆえ、視覚受入も HTML を開いた確認手順として文書化する。

## 背景
本ドメインは Claude Code の skill/agent/command/hook/script(Markdown/CLI 主体)であり GUI ランタイムスクショは取得しない。代わりに再現可能な Markdown evidence 5 要素へ写像する。生成 HTML の見た目確認(slide の視覚崩れ/report の可読性)は、出力パスと開き方を evidence に記して第三者が再現できる手順に落とす。DROP 読替の正本は phase-lifecycle.md §7。

## 前提条件
- P10 の final-gate を通過している。
- P0 lint / schema parity / build-trace / content-review / harness の各結果が取得可能。
- evidence は Markdown で残す(GUI スクショに依存しない・HTML は開き方の手順で代替する)。

## ドメイン知識
- 再現可能性の要件: 第三者が evidence 記載のコマンド/入力を再実行して同じ合否へ到達できること(ログ貼付だけでは不足)。
- 生成物の視覚受入の代替: index.html/report.html の出力パスと開く手順、及び deck-evaluator(30種思考法)の評価スコアを evidence に記す(スクショの代わりにテキスト受入証跡)。
- DROP 読替の正本は `phase-lifecycle.md` §7。他の plan 全体用語は index `## ドメイン知識` 参照。

## 成果物
- evidence 5 要素(P0 lint ログ / schema parity / build-trace coverage / content-review verdict / harness coverage JSON)を集約した Markdown 検証記録 + 生成 HTML の再現手順。

## スコープ外
- 新規の検証実施(P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化(P12)。

## 完了チェックリスト
- [ ] evidence 5 要素が全て Markdown に記録されている。
- [ ] 生成 HTML(slide/report)の出力パスと開き方・deck-evaluator スコアが記され、第三者が受入充足を再現・確認できる状態になっている。

## 参照情報
- `references/phase-lifecycle.md` §7(GUI スクショ→Markdown evidence の DROP 読替表)。
- evidence 5 要素(lint/schema/build-trace/content-review/harness)。
- 後続 P12(documentation)。

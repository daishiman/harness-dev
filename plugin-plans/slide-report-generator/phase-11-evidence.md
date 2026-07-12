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
GUI スクショ検証を原則 DROP し、Markdown による evidence 5 要素へ写像する evidence gate (report UI/UX 受入 C16-C18 のみスクショ evidence 必須の例外)。プラグインが受入を満たしたことを再現可能な形で記録する。生成物は HTML/CSS/JS/SVG のローカル出力ゆえ、視覚受入も HTML を開いた確認手順として文書化する。

## 背景
本ドメインは Claude Code の skill/agent/command/hook/script(Markdown/CLI 主体)であり、evidence は決定論出力+再現手順で代替する (report UI/UX 受入 C16-C18 に限りスクショ evidence 必須・その他も補助スクショ許容)。再現可能な Markdown evidence 5 要素へ写像する。生成 HTML の見た目確認(slide の視覚崩れ/report の可読性)は、出力パスと開き方を evidence に記して第三者が再現できる手順に落とす。DROP 読替の正本は phase-lifecycle.md §7。

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
- report UI/UX evidence (周回3 追加・C16-C18 受入・周回4 で narrow 幅 degrade breakpoint 追随): vendor playwright (S-VENDOR post_copy で chromium 導入済) による wide(≥1600px)/narrow(≤900px・iPad 縦 820px 等の degrade 発火域)/print emulation の 3 状態の実レンダリング確認手順 + 各状態のスクショ (C16-C18 受入は必須・その他は補助として許容) + C25 validate-report-visual.py の JSON 出力 (`--json`) 添付。
- evidence freshness manifest: update id、render-report.js SHA、schemaVersion=1.3.0、C25 SHA、fixture digest、viewport、取得時刻を固定し、旧1.2.0/旧CSS evidenceをcurrent判定へ再利用しない。hash/font-ready/history/afterprintのnavigation logとcomputed metricsも添付する。

## スコープ外
- 新規の検証実施(P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化(P12)。

## 完了チェックリスト
- [ ] evidence 5 要素が全て Markdown に記録されている。
- [ ] 生成 HTML(slide/report)の出力パスと開き方・deck-evaluator スコアが記され、第三者が受入充足を再現・確認できる状態になっている。
- [ ] report UI/UX evidence (wide/narrow/print emulation 3 状態の実レンダリング確認手順 + C16-C18 受入スクショ + C25 JSON 出力) が記録されている。
- [ ] freshness manifestと899/900/901境界・hash-active・afterprint・computed typography/card幅の機械可読証跡がcurrent SHAで記録されている。

## 参照情報
- `references/phase-lifecycle.md` §7(GUI スクショ→Markdown evidence の DROP 読替表)。
- evidence 5 要素(lint/schema/build-trace/content-review/harness)。
- 後続 P12(documentation)。

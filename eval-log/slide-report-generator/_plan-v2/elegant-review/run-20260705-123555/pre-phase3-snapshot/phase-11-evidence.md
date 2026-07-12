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
GUI スクショ検証を DROP し、Markdown による evidence 5 要素へ写像する evidence gate。加えて、責務再均衡の達成を再現可能な形で記録する before/after 比較(sub-agent 行数の縮退実績・references_new の実在確認・lint-reference-attribution.py の実行ログ)と、build_readiness の証跡(brief 生成・surface task・open issue close/waiver)を evidence へ含める。さらに D1=parallel_slug の非回帰保証として、v1 golden(build 前に pin した代表 slide/report の生成 HTML)と v2 build 後出力の golden diff before/after を evidence 必須項として記録する(OUT1 の再現可能な受入証跡)。

## 背景
本ドメインは Claude Code の skill/agent/command/hook/script(Markdown/CLI 主体)であり GUI ランタイムスクショは取得しない。代わりに再現可能な Markdown evidence 5 要素へ写像する。責務再均衡計画特有の evidence として、「11 thin-adapter agent が実際に薄化されたか(行数 before/after)」「委譲先 references_new が実在するか」「route 外 surface と contract-only gap が build 時に閉じられたか」を第三者が検証できる手順に落とす。

## 前提条件
- P10 の final-gate を通過している。
- P0 lint / schema parity / build-trace / content-review / harness の各結果が取得可能。
- evidence は Markdown で残す(GUI スクショに依存しない)。

## ドメイン知識
- 再現可能性の要件: 第三者が evidence 記載のコマンド/入力を再実行して同じ合否へ到達できること(ログ貼付だけでは不足)。
- rebalance 達成の代替エビデンス: 11 thin-adapter agent の build 前後行数比較(`wc -l`)+ references_new の実在パス一覧 + lint-reference-attribution.py の実行ログを evidence に記す(スクショの代わりにテキスト受入証跡)。
- build readiness のエビデンス: C01-C03 brief 生成ログ、surface_tasks の実行/検査ログ、high open_issues の close または waiver 記録を evidence に記す(route DAG 外の前後処理が抜けていないことの証跡)。
- DROP 読替の正本は `phase-lifecycle.md` §7。他の plan 全体用語は index `## ドメイン知識` 参照。

## 成果物
- evidence 5 要素(P0 lint ログ / schema parity / build-trace coverage / content-review verdict / harness coverage JSON)を集約した Markdown 検証記録。
- 責務再均衡達成のエビデンス(11 agent の行数 before/after 比較・references_new 実在パス一覧・lint-reference-attribution.py 実行ログ)。
- build_readiness 達成のエビデンス(brief 生成ログ・surface task trace・open issue close/waiver trace)。
- D1=parallel_slug 非回帰のエビデンス(golden before/after diff): build 前に pin した v1 代表 slide/report 生成 HTML と、v2 (plugins/slide-report-generator-v2/) build 後の同一入力生成 HTML の diff 結果(PASS=非回帰)を、pin パス・diff コマンド付きで記録する。

## スコープ外
- 新規の検証実施(P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化(P12)。

## 完了チェックリスト
- [ ] evidence 5 要素が全て Markdown に記録されている。
- [ ] 11 thin-adapter agent の行数 before/after 比較と references_new 実在パス一覧が記録され、第三者が rebalance 達成を再現・確認できる状態になっている。
- [ ] lint-reference-attribution.py の実行ログ(exit0)が evidence に含まれている。
- [ ] C01-C03 brief 生成、surface_tasks、high open_issues の close/waiver trace が evidence に含まれている。
- [ ] D1=parallel_slug の golden before/after diff(v1 pin golden ↔ v2 build 後出力)が PASS(非回帰)として pin パス・diff コマンド付きで evidence に記録され、第三者が再現できる。

## 参照情報
- `references/phase-lifecycle.md` §7(GUI スクショ→Markdown evidence の DROP 読替表)。
- evidence 5 要素(lint/schema/build-trace/content-review/harness)+ rebalance 達成エビデンス。
- 後続 P12(documentation)。

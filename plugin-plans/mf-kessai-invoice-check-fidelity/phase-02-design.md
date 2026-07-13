---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
改善増分を 5 種の component_kind(skill/sub-agent/slash-command/hook/script)へ写像し、N=7 実体を `component-inventory.json` へ分解する。各 component の build_target(既存ファイル modify または C05/C06 の新規 script)・依存 DAG・品質機構を確定し、既存 manifest と同じ version 0.3.0 を維持した envelope draft (`envelope-draft/plugin.json`)を設計する owner フェーズ。

## 背景
P01 で確定した goal-spec を、実際に build 可能な実体へ落とす最初の設計フェーズ。本改善は新規プラグインではないため、既存 7 entry_point(skill 6・agent 3・hook 2・command 6 のうち改善対象のみ)から改善対象を C01(skill)/C02(sub-agent)/C07(slash-command)として抽出し、判定ロジック本体を C03/C04(既存 script modify)+ C05/C06(新規 script)へ分解する。amount-gate 根治は 1323行の `lib/mfk_reconcile.py` モノリスへ外科手術するのではなく、**新規の純関数モジュール C05=`scripts/mfk_actuals.py`(MF実績抽出器)として切り出す**(テスト容易・reconcile/report/doctor で再利用・「MF実績=第一級の真実」を構造で明示する設計改善)。既存 `lib/mfk_reconcile.py`(find_mf_match/classify)は C05 を consume する統合配線として P05 実装時に modify されるが、独立 component 化しない(build_target を lib/ に持たせない)。ただし C05 route の `required_file_edits` として必須成果物に含めるため、builder が `scripts/mfk_actuals.py` だけを作って完了にすることはできない。C06 も同様に `lib/mfk_api.py`/R1 collect の pagination_trace 生成を `required_file_edits` として持つ。新規 hook は不要で既存 `guard-mfk-readonly`/`guard-mfk-no-reinvent` を再利用する(plugin_level_surfaces では対象外として扱わず、既存 hook 再利用として component 化しない)。

## 前提条件
- P01 の `goal-spec.json` が確定している。
- 実プラグインの実ファイル配置(bundle 方式・scripts/agents/commands/lib が plugin-root 直下)を確認済み。
- 5 種の component_kind の写像規約(`references/component-domain.md`)を参照できる。

## ドメイン知識
- 正規化原則: build_target/depends_on は `component-inventory.json` のみが保持し、phase ファイルは `entities_covered` の id 参照だけで紐づく。
- 依存 DAG(top-sort 順): C05(mfk_actuals・MF実績抽出器)→C06(fetch fidelity監査)→C03(flowchart入力切替)→C04(Notion sink)→C01(オーケストレーション skill・C05 も直接 depends_on)→C02(sub-agent 二段確認)、C07(slash-command 診断)は C06 依存。
- `placement_scope`: 4 script(C03/C04/C05/C06)は全て plugin-root かつ build_target は全て `plugins/mf-kessai-invoice-check/scripts/` 直下(C05 を新規切り出しにしたことで plugin-root script ゲート(`/scripts/` 必須)を例外なく満たす)。

## 成果物
- `component-inventory.json`(N=7 component の唯一 SSOT)。
- `envelope-draft/plugin.json`(既存 version 0.3.0 を維持する manifest draft・既存 entry_points/permissions/hooks は温存)。

## スコープ外
- 設計の合否判定(P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出(P04 へ委譲)。
- 実体の生成(P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [ ] 全 7 component(C01-C07)が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces の採否(8 surface)が明示されている。
- [ ] `envelope-draft/plugin.json` に既存 entry_points(skills/agents/commands/hooks)と version 0.3.0 を保った manifest 同期が設計されている。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md`。
- 対象 component C01-C07(`component-inventory.json`)。
- 後続 P03(この設計を design-gate で審査する)。

---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計ゲート)

## 目的
P02 の component 分解 (8 件・DAG・state_file パス・E4 境界) が、goal-spec の constraints 10 件と矛盾しないことをゲートとして確認する。

## 背景
design-gate は「P05 実装設計へ進む前に、SSOT 遵守 (constraints #1/#3) と単一 writer 規約 (constraints #2) が component 粒度で破られていないか」を機械検証可能な形で固定する節目である。

## 前提条件
- P02 の component-inventory.json が確定している。

## ドメイン知識
- 検査観点 A (SSOT 遵守): C01/C02/C03/C04 のいずれも task-graph.schema.json/derive-task-graph.py/validate-task-graph.py/compute-ready-set.py/discovered-task.schema.json/handoff-notes.schema.json を re-implement する記述を持たないこと (`purpose` フィールドに「呼び出す」「消費する」の語彙のみが現れ「独自に導出する」「独自に検証する」の語彙が現れないことを目視+`check-runtime-portability.py`/`check-surface-inventory.py` で確認)。
- 検査観点 B (単一 writer): component-inventory.json の `write_scope` フィールド限定で task-state.json を「実書込先として宣言」する component を抽出すると C02 のみであること。C07 の write_scope にも task-state.json への言及があるが『実書込みは持たず C02 へ委譲』という否定文脈であり実書込宣言ではないため除外する (抽出述語はこの否定句の不在で機械判定する。全文 grep は否定文脈を区別できず再現不能なため用いない)。
- 検査観点 C (additive 拡張): C05 の purpose が route-build-report の既存フィールドを変更せず読み取りのみであることが明記されていること。

## 成果物
- 上記 3 観点の確認結果 (本 phase 完了チェックリストへの反映)。

## スコープ外
- テストケースの具体的 fixture 化 (P04 の責務)。

## 完了チェックリスト
- [ ] 検査観点 A: C01-C08 のいずれも task-graph 関連ロジックの re-implement を purpose に含まない。
- [ ] 検査観点 B: `write_scope` で task-state.json を実書込先として宣言する component は C02 のみ (下記受入例の機械抽出で確認)。
- [ ] 検査観点 C: C05 の purpose が route-build-report の既存フィールド変更を含まない。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: repo root で `python3 -c "import json; inv=json.load(open('plugin-plans/harness-creator/component-inventory.json')); print([c['id'] for c in inv['components'] if 'task-state.json' in c.get('write_scope','') and '実書込みは持たず' not in c.get('write_scope','')])"` を実行し、出力が `['C02']` であることを確認し記録する (実行済み確認: 2026-07-07 時点の inventory で出力 `['C02']`)。
- 満たさない例: C01 の purpose に「ready-set 計算を独自実装する」という記述が残ったまま P04 へ進む (SSOT 違反の見落とし)。

### 事前解決済み判断
- 分岐点: design-review を人手レビューのみで済ませるか grep 等の機械確認を伴わせるか → 判断: 機械確認を伴わせる (constraints #1/#2 は「再実装しない」「単一 writer」という否定/一意性の主張であり、目視のみでは見落としやすいため軽量な機械確認 (grep) を本 phase の完了条件に含める)。

## 参照情報
- `plugin-plans/harness-creator/component-inventory.json`。
- 先行 P02 (design)。
- 後続 P04 (test-design)。

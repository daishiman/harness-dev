---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: [C05, C06, C07, C08]
applicability:
  applicable: true
  reason: 
---

# P12 — documentation (文書)

## 目的
`references/goal-seek-paradigm.md` への「engine:task-graph 変種」節の追記により、with-goal-seek engine:task-graph 変種と generated harness dependency graph knowledge の正本仕様を文書化する。新規リファレンスファイルは作成しない。

## 背景
plugin_level_surfaces.references_config_assets(component-inventory.json)で宣言した既存ファイルへの追記が実際に行われることを本 phase で確認する。仕様の正本が文書化されていないと、生成ハーネス利用者が depends_on/self-reflect append 語彙・単一truth境界・H1/H2 の正しい再framing・C06-C08 の dependency graph knowledge consult 境界を参照できない。

## 前提条件
Phase09 品質保証・Phase10 最終レビュー完了。

## ドメイン知識
(引用)plugin_level_surfaces.references_config_assets(component-inventory.json)。差分なし。

## 成果物
- `plugins/harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md`(既存への追記): 末尾に『engine:task-graph 変種』節を追加し、単一truth設計(checklist+intermediate.jsonl のみが状態源)・depends_on/self-reflect append の仕組み・H2 の compute-ready-set.py 正しい再framing(file:line 引用)・既存 build-pipeline task-graph との非改変境界・C06-C08 による dependency graph knowledge の抽出/記録/各 surface consult を記載する。
- C05(run-build-skill)の SKILL.md 新設 Step からこの節を参照し、C06/C07/C08 の役割と Loop A/Loop B knowledge entry の `source_ref` 要件を引用する。

## スコープ外
`plugin-plans/harness-creator/` 配下の既存文書の編集(非改変境界の対象)。新規リファレンスファイルの作成(既存ファイルへの追記のみとする)。

## 完了チェックリスト
- [ ] goal-seek-paradigm.md に『engine:task-graph 変種』節が追記され H1/H2/H3/H6 の要点を含む
- [ ] C05 の SKILL.md からこの節への参照が存在する

### 受入例 (満たす例 / 満たさない例)
- 満たす例: `goal-seek-paradigm.md` 末尾に追記された『engine:task-graph 変種』節が H1(write_scope 不要理由)/H2(compute-ready-set 再framing)/H3(単一truth)/H6(dependency graph knowledge consult)の要点を含み、C05 の SKILL.md からこの節への参照(ファイル名+節見出し)が存在する。
- 満たさない例: 節見出しのみ追加され本文が空、または既存の with-goal-seek(engine:inline)説明箇所を上書きしてしまう。

### 事前解決済み判断
- 分岐点: 新規リファレンスファイルを作るか既存ファイルへ追記するか → 判断: component-inventory.json の `plugin_level_surfaces.references_config_assets` 宣言に従い既存 `goal-seek-paradigm.md` への追記のみとし、新規ファイルを作らない(surface 台帳との整合・不要 surface 増殖の回避)。

## 参照情報
- `component-inventory.json` plugin_level_surfaces.references_config_assets
- `phase-02-design.md`

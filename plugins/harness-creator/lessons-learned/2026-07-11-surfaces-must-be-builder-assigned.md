---
date: 2026-07-11
---

# required plugin_level_surfaces に builder 未割当だと構造的に build/gate されない

## 背景

extract-system-blueprint build (2026-07-11) で、component-inventory の成果物2クラスのうち build/verify を駆動するのは components[] (builder/build_target/quality_gates 携帯) のみで、plugin_level_surfaces (schemas/manifest/composition/EVALS/CI) は required:true でも builder 未割当ゆえ task-graph 射影対象外だった。route parity 14/14 緑のまま manifest/schema が構造的に欠落し、C08 hook の runtime 配線が inert 化・schema_refs dangling が発生。30思考法エレガント検証の3独立分析が HIGH 収束して初めて露見した。

## 知見

required な成果物は「builder が割当たっている」ことまで含めて初めて build される。宣言 (required:true) と駆動 (task-graph node 化) は別物で、「build 完了」と「ship 完了」は別の完全性として検証しなければ機械ゲート全緑でも欠落する。検出の鍵は build vs ship completeness の論点分離。

## 適用先

- planner `derive-task-graph.py`: required plugin_level_surface を SURFACE-{key} build node へ昇格 (builder 割当+gate)。実装済。
- planner `check-provenance-chain.py`: pass 発火条件へ required surface 実在 assert を組込む。実装済。
- agents の `source: (responsibility_anchor)` は owner skill の responsibilities と整合 lint する (忠実写像だけでは dangling 化する)。

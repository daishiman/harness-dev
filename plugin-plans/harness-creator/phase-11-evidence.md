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
スクショに代わる Markdown evidence 5 要素 (lint exit0 ログ / schema parity / build-trace coverage / content-review verdict / coverage JSON) が build 後に観測可能であることを本 plan の設計として確定する。

## 背景
本サイクルで追加/拡張される決定論ゲート (dispatch-ready-set.py/sync-task-state.py/inject-task-inputs.py/emit-discovered-task.py/summarize-task-progress.py/manage-build-lease.py/record-task-graph-knowledge.py の各実行ログ、capability-build.md の後方互換テスト green) の実行ログも既存の 5 要素へ合流し、新規の 6 番目要素は追加しない。

## 前提条件
- P10 の final-review が PASS している。

## ドメイン知識
- lint exit0 ログ: p0_lint (C01-C05/C07/C08=`lint-script-frontmatter`/C06=`validate-frontmatter`) + 新規/拡張ゲート (C01-C08 それぞれの単体テスト実行ログ) の合流。
- schema parity: 本サイクルは既存 3 schema (task-graph.schema.json/discovered-task.schema.json/handoff-notes.schema.json) を producer 側 SSOT のまま消費するのみで、consumer 側新規 schema は導入しない。schema parity は producer 側 3 schema と C01/C03/C04 の実装コードの key 一致検証に限定される。
- build-trace coverage: build_trace:required に基づく build 実行トレース (C01-C08 全て)。
- content-review verdict: PASS + sha_match。
- coverage JSON: `eval-log/coverage/scripts/harness-creator__dispatch-ready-set.json` 等 (C01-C05/C07/C08 のスクリプト単位) + `eval-log/coverage/commands/harness-creator__capability-build.json` (C06)。

## 成果物
- evidence 5 要素の観測可能性設計 (build 後に実際のログ/JSON として生成される前提の宣言)。

## スコープ外
- 実測 evidence の生成 (build 後・本 plan の対象外)。

## 完了チェックリスト
- [ ] evidence 5 要素それぞれが本 plan のどのゲート/成果物に対応するか明示されている。
- [ ] task-graph 関連の新規/拡張ゲートの実行ログが既存 5 要素 (特に「lint exit0 ログ」) へ合流することが明示されている (新規 6 番目要素の追加なし)。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 5 要素それぞれに対応する具体的なゲート名/JSON パスが列挙されている。
- 満たさない例: 「テストを実行してスクショを撮る」のように DROP 済みの UBM 固有要素が残存する。

### 事前解決済み判断
- 分岐点: 本サイクルで producer 側 schema の複製/独自版を consumer 側にも作るか → 判断: 作らない (constraints #1・#3 の SSOT 遵守。C01/C03/C04 は producer 側 schema をそのまま参照/検証に用い、schema parity は「producer 側 3 schema と consumer 側実装コードの key 一致」に限定する)。

## 参照情報
- P10 (final-review)。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/references/phase-lifecycle.md` §7。
- 後続 P12 (documentation)。

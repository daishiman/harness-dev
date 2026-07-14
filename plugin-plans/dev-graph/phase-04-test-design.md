---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C04, C05, C14, C15, C18, C19, C24, C25, C26, C27, C28]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop 系 component (C01 init / C02 node / C03 sync / C04 requirements / C05 render / C14 decompose / C15 schedule / C18 status) の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。実装前は criteria が未達 (Red) であることを確認する tdd-red gate。

追加のC19についても、system-spec-harness lineage/非複製をtest-firstで固定する。system development task plan (13 phase/workstream/task DAG/handoff、readiness fail-closed) の受入criteriaはexternal plugin system-dev-planner側が所有する。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。汎用ゲートの言い換え (lint exit0 / 4 条件 PASS) に退化した criteria は purpose を一度も受入検証しないため、goal/checklist 語彙由来であることを設計時に担保する (`criteria_purpose_traceability` が機械検出する退化を未然に防ぐ)。特に C03 (sync) は id+updated_at 同時競合のタイブレーク規則を OUT2 criterion として明示的に固定する。

## 前提条件
- P03 の design-gate を通過している。
- skill loop 系 component C01-C05・C14・C15・C18-C19 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約 (inner/outer 各 1 件以上・id/verify_by enum) を参照できる。

## ドメイン知識
- inner/outer criteria: inner=生成時の自己検証観点、outer=build 後の受入観点 (各 1 件以上が契約)。
- Red = 実装前に criteria が未達であること (実装後に緑になることで criteria が実効だったと証明される)。
- purpose-traceability = criteria が goal/checklist の語彙を参照していること (汎用ゲートの言い換え退化を `check-spec-frontmatter.py` が機械検出)。

## 成果物
- 9 skill (C01-C05/C14/C15/C18-C19) の `feedback_contract.criteria` が inventory に確定した状態。

## スコープ外
- criteria を満たす実装 (P05)。
- harness カバレッジの設計・実行 (P06・kind 別観点はそちらで扱う)。
- 非 skill component の受入 (output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [ ] 9 skill の criteria が purpose 由来で inner/outer を各 1 件以上持つ (汎用ゲート言い換えに退化していない)。
- [ ] C01 は「二回initで6 root/routing policy不変」、C02は「5種混在入力を保存先質問なしでrouting」「confidence境界で低信頼だけ確認」「連続書込み後もfrontmatter/path整合」、C03は同期/tombstone/dry-runに加えて「migration後もgraph_node_id不変・linkage整合」、C11は「199/200/201件境界で必要時だけpartition」「rollback後link復元」、C14はC02分類再利用、C18はmetadata filter read-onlyをouter criterionに持つ。既存C04/C05/C15のpurpose criteriaも維持する。
- [ ] 実装前は criteria が未達 (Red) であることが確認できる。
- [ ] C19はsystem-spec-harness lineageとロジック非複製をouter criteriaに持つ。13 phase/workstream/task DAG/handoff/4条件とreadiness未達時生成0件のcriteriaはexternal system-dev-plannerが所有し本planでは重複定義しない。
- [ ] C25-C27は非skill componentとして、Claude event matcher/blocking範囲、PR completion state machine、multi-worktree atomic lease/TTL recovery/default-branch-only projectionをoutput_contract fixtureで固定する。

### 受入例
- 満たす例: C03 の `feedback_contract.criteria` に OUT2「id+updated_at が同時競合するケースを注入した際、規定のタイブレーク規則どおりに競合解決される」が purpose 語彙 (id+updated_at 競合解決) から導出された状態で存在する。
- 満たす例: C18 の criteria に OUT1「検索/状態表示結果がグラフ実状態と一致」・OUT2「実行後も副作用が生じない (read-only)」が inner/outer 各 1 件以上で揃っている。
- 満たさない例: criteria が「lint が exit0 であること」のような汎用ゲート言い換えのみになっている → purpose-traceability を欠くため `check-spec-frontmatter.py` が退化と検出する。

### 事前解決済み判断
- inner/outer criteria は各 component 最低 1 件以上を必須とし、0 件の component は本フェーズを通過できない。
- criteria は実装前に Red (未達) であることを確認してから P05 (Green 化) へ進む順序を固定する (Red なしの Green は criteria の実効性を証明しない)。
- C03 は OUT9 まで、C14 は OUT5 まで、C15 は OUT3、C18 は OUT2 までを criteria の下限本数として固定する。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2 (criteria の purpose-traceability・test-first 導出)。
- 対象 component C01-C05 / C14-C15 / C18-C19。
- 追加fixture: artifact kind 6種混在、高/中/低confidence、leaf 199/200/201件、domain/project/year partition、migration rollback、graph_node_id不変性。
- 追加fixture: system-spec confirmed/incomplete (C19引用境界)。system plan生成側fixture (frontend+backend+API複合system、infra-only system、plugin語彙混入、task DAG cycle、handoff mismatch) はexternal system-dev-plannerが所有する。
- 追加fixture: repo A/Bが同一harness symlinkを参照、異なるdocs/config、同時実行、host project-root不一致、broken/moved content link、host launcherによるbroken harness-link preflight、`../` traversal、root外content symlink、git root/cwd/explicit root優先順位、repository_id再導出不一致。
- 追加fixture: SessionStart/PostToolUse/TaskCompleted JSON、plugin/project hook二重登録、managed/disabled settings、closed-unmerged/merged/all-any/reopen/revert、main+2 linked worktrees、同一task同時claim、touches重複、heartbeat切れ、crash後TTL reclaim、dirty/default/feature/detached/rebase中worktree。
- 追加fixture: GitHub enabled時のdefault Project 0/1/2件、duplicate alias、heartbeat<TTL境界、scheduled owner/interval期限前後、linked_pr_merged_allで1件open残存をschema拒否・anyで1件mergedを許可。
- 追加fixture: owner session消滅後のvalid completion event system-release、repository/task/merge SHA不一致event拒否、同一event再利用拒否、監査record生成。
- 後続 P05 (implementation)。

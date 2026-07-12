---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: 
---

# P04 — test-design (テスト)

## 目的
C01-C04/C06-C08 の tests_min>=80 単体テスト設計と、C05 の受け入れテスト設計(lint-goal-seek.py 拡張 self-test + lint-capability-graph-knowledge.py exit0 を条件とする)を確定する。特に C02 の単一truth完了gate(H3)、C01 の write_scope 非依存性(H1)、C06-C08 の generated harness dependency graph knowledge 経路(H6)を検証するテストケースを明記する。

## 背景
harness-creator 規律は script component 全てに tests_min>=80 を要求する。旧 A1 が持ち込みかけた write_scope tie-break 死機構(H1)を C01 のテストへ再導入しないこと、および self-reflect 追記が実際に done-judge を gate することを実測で担保する必要がある。

## 前提条件
Phase02 設計確定・Phase03 design-gate(LR1-LR4)通過。

## ドメイン知識
(引用+差分)ready 集合算出の決定論性、self-reflect 追記のサイクル非発生性。差分なし(index.md ## ドメイン知識 の引用で足りる)。

## 成果物
- C01: depends_on が全充足の pending item のみが ready 集合に入ることを検証するテスト、id 昇順ソートの決定論性テスト、write_scope フィールドの有無に関わらず動作すること(tie-break 機構を持たないことの裏付け)を検証するテスト。
- C02: 追記後に既存 item の depends_on/status が一切変更されないことを検証するテスト(単一truth原則の裏付け)、id 重複時・未知 depends_on 参照時・追記後サイクル検出時に fail-closed(exit1)することを検証するテスト。
- C06: 生成 harness の skill/slash-command/sub-agent/hook/script surface 定義と参照から dependency graph JSON を決定論抽出し、未知 surface 参照・循環・空 graph を fail-closed で検出するテスト。
- C07: C06 の graph と self-reflect task を Loop A/Loop B knowledge entry へ `source_ref` 付きで記録し、既存 knowledge entry を破壊しないことを検証するテスト。
- C03: build-flags.schema.json の engine enum への 'task-graph' additive 追加、goal-seek-loop.schema.json への depends_on additive 追加が既存フィールドを破壊しないことを検証するテスト(schema 後方互換性)、C01/C02/C06/C07 同梱手順と dependency graph knowledge consult 手順の配線テキスト存在検査。
- C04: consumption verifier トークン(depends_on 消費検査・self-reflect 完了gate検査)が生成 SKILL.md に存在しない場合に violation を検出するテスト、既存 check_default_drift() の他検査を壊さないことを検証する回帰テスト。
- C08: 生成 harness の skill/slash-command/sub-agent/script 各 surface に dependency graph knowledge consult token がない場合、または C06/C07 同梱・Loop A/B `source_ref` 記録が欠ける場合に violation を返す lint テスト。
- C05: brief.goal_seek.engine=task-graph 指定時の SKILL.md 注入内容(C01/C02/C06/C07 コピー手順 + task-graph 変種配線節 + dependency graph knowledge consult 手順)の統合テスト設計。lint-goal-seek.py 拡張 self-test と lint-capability-graph-knowledge.py exit0 を受け入れ条件とする。

## スコープ外
実テストコードの実装 → Phase05(実装)・Phase06(テスト実行)へ委譲する。本 phase はテストケース列挙(テスト設計)のみを扱う。

## 完了チェックリスト
- [ ] C01 の write_scope 非依存性テストケースが明記されている(H1 裏付け)
- [ ] C02 の単一truth完了gate(既存 item 不変+サイクル検出)テストケースが明記されている(H3 裏付け)
- [ ] C06-C08 の dependency graph 抽出・knowledge 記録・各 surface consult lint テストケースが明記されている(H6 裏付け)
- [ ] 全 script component の tests_min>=80 方針が明記されている

### 受入例 (満たす例 / 満たさない例)
- 満たす例: C01 のテストケース一覧に「depends_on 未充足の item は ready 集合に含まれない」「write_scope フィールドが存在しなくても動作する」の両方が明記され、C02 に「追記後サイクル検出時に exit1 で fail-closed する」テストが明記されている。
- 満たさない例: 「tests_min>=80 を満たす」とだけ記述し、H1(write_scope 非依存性)/H3(単一truth完了gate)を裏付ける具体的な検証観点が列挙されていない。

### 事前解決済み判断
- 分岐点: self-reflect 追記のサイクル検出を C02 内部で行うか外部 validator に委譲するか → 判断: C02 自身が追記前に fail-closed 検査する(外部 validator への依存を作らず単一 script で完結させ、単一truth原則の一部として self-reflect 自体の安全性を C02 単体のテストで担保する)。

## 参照情報
- `component-inventory.json` C01-C08
- `phase-02-design.md` H1/H3/H4/H6 節

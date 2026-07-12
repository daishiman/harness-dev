---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (リファクタリング)

## 目的
テストが緑の状態を保ったまま、SSOT 重複を排除する(lint-ssot-duplication・上書き一本化)。本プラグインでは意匠/技術層(vendor theme / style-genome / schemas 共通コア / references)が slide/report 経路から二重定義されない単一実体であることを保証する改善フェーズ。

## 背景
共通コア(Kanagawa 配色/16:9/theme/決定論レンダラ/structure 共通コア)が slide 経路と report 経路から二重定義されると SSOT が崩れ、片方だけ修正した際にドリフトする。テスト緑を保ったまま重複を上書きで一本化し、report は共通コアを複製せず structure.schema.json との共有コア(nodes/edges/groups/theme/aiVisual)を参照で共有する tdd-refactor。vendor Node engine の byte 一致(比較基準=`vendor-digest-manifest.json`・移植元 live tree ではない)もこのフェーズで担保する。

## 前提条件
- P07 の受入判定が全 PASS。
- P06 のテストが緑。
- lint-ssot-duplication が利用可能で、意匠/技術層が vendor + references + schemas の単一 SSOT に集約されている。

## ドメイン知識
- 上書き一本化: 重複を発見したら両方残さず一方を正本に確定し、他方は削除して参照へ置換する(共存縮退は禁止)。
- 共通コア共有: report-structure.schema.json は structure.schema.json の共通コアを複製せず共有する(意匠/技術 SSOT)。本 update の 1.1.0/1.2.0 schema additive (body block/narrative/highlight/placement live 化 + 1.2.0 の section.role/throughLine/transition/文書メタ/新block型/placement 正規化) と第3次UI(screen/print 二層 CSS・sticky TOC・タイポ密度=schema 非依存の render-report.js 側)・essence-visual(既存 role/visual.kind を使う本質図解カバレッジ・schema bump 不要) も slide 共通コア (nodes/edges/groups/theme/aiVisual) を複製せず、report 固有の追加のみを持つ(既存 paragraphs も温存する後方互換 additive で SSOT を割らない)。色付き強調は意匠 accent (--section-accent) を流用し新規配色トークンを足さない。
- vendor byte-parity: byte 一致の対象は byte_parity_subtrees 由来ファイルのみ(比較基準=`vendor-digest-manifest.json`・検証器=lint-vendor-parity.py)。additive_new_files(render-report.js/mermaid-render.js・著者=C19 report-composer の build 責務)は明示的除外集合で、parity でなく tests_min の別検査で担保する(意匠/技術資産の毀損防止と report 新規追加の両立)。
- tdd-refactor の不変条件: リファクタリング中もテスト緑を維持する(赤に戻ったら即巻き戻し)。

## 成果物
- SSOT 重複が 0 件になった状態(意匠/技術共通コアが単一実体・vendor byte 一致)。

## スコープ外
- 新機能の追加(リファクタリングは挙動不変)。
- 受入基準・criteria の変更(P04/P07 の責務)。
- plugin 外(他 plugin・repo 共有層)への hoist(本 plan のスコープは plugin 内)。

## 完了チェックリスト
- [ ] lint-ssot-duplication が exit0 で、意匠/技術共通コア(vendor theme/schemas 共通コア/references)が一本化されている。
- [ ] report は共通コアを複製でなく参照で共有し、slide/report で意匠/技術層が重複していない。
- [ ] byte_parity_subtrees 由来の vendor Node engine が `vendor-digest-manifest.json` と byte 一致(lint-vendor-parity.py exit0・additive_new_files は除外集合)で、リファクタリングによってテストが赤に戻っていない(tdd-refactor 維持)。

## 参照情報
- lint-ssot-duplication(SSOT 重複検査)。
- vendor surface / schemas surface(structure⇄report-structure 共通コア)。
- 後続 P09(quality-assurance)。

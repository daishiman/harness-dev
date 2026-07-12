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
テストが緑の状態を保ったままSSOT重複を排除する。C12/C13/C14はplugin-root単一実体、spec-state transitionはC01所有apply-spec-transition.py単一実体とし、C03/C11は直接参照・複製せずC01へ委譲する。

## 背景
共有ロジック (C12 マトリクス検証 / C13 出典検証 / C14 知識グラフ検証) が elicit/doc-fetch/compile/ref から二重定義されると SSOT が崩れ、片方だけ修正した際にドリフトする。テスト緑を保ったまま重複を上書きで一本化し、第二消費者は import/参照で共有する tdd-refactor。

## 前提条件
- P07 の受入判定が全 PASS。
- P06 のテストが緑。
- lint-ssot-duplication が利用可能で、共有 script C12/C13/C14 が plugin-root へ hoist 済み。

## ドメイン知識
- 上書き一本化: 重複を発見したら両方残さず一方を正本に確定し、他方は削除して import/参照へ置換する (共存縮退は禁止)。
- 第二消費者 = 正本を複製せず import/参照で共有する側 (C12/C13/C14 は plugin-root 実体が正本)。
- tdd-refactor の不変条件: リファクタリング中もテスト緑を維持する (赤に戻ったら即巻き戻し)。

## 成果物
- SSOT 重複が 0 件になった状態 (共有 script が単一実体)。

## スコープ外
- 新機能の追加 (リファクタリングは挙動不変)。
- 受入基準・criteria の変更 (P04/P07 の責務)。
- plugin 外 (他 plugin・repo 共有層) への hoist (本 plan のスコープは plugin 内)。

## 完了チェックリスト
- [ ] lint-ssot-duplication がexit0で、C12/C13/C14とC01所有transition実体が一本化され、C03/C11に複製・直接importがない。
- [ ] 第二消費者は複製でなく import/参照で共有している。
- [ ] リファクタリングによってテストが赤に戻っていない (tdd-refactor 維持)。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: validate-coverage-matrix.py の検証ロジックが plugin-root の単一実体のみで、C01/C03 は path 参照で共有している。
- 満たさない例: compile skill 配下に validate-coverage-matrix.py の複製が残り、plugin-root 実体と並存している (共存縮退)。

### 事前解決済み判断
- 分岐点: 重複発見時にどちらを正本にするか → 判断: plugin-root 実体を正本とし skill 配下の複製を削除 (上書き一本化・第二消費者は参照へ置換)。

## 参照情報
- lint-ssot-duplication (SSOT 重複検査)。
- 共有 component C12 (validate-coverage-matrix) / C13 (validate-source-citation) / C14 (validate-knowledge-graph)。
- 後続 P09 (quality-assurance)。

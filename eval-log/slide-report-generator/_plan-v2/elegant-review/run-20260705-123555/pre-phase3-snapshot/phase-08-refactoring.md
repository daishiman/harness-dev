---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: [C01, C02, C03, C05, C07, C08, C09, C11, C12, C13, C14, C15, C16, C17, C24]
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (リファクタリング)

## 目的
P05-P07 で rebalance 実装と受入判定が完了し、テストが緑の状態を保ったまま、重複記述・帰属ゆれ・二重 SSOT が 0 であること(invariant)を検証する refactor verification フェーズ。11 thin-adapter agent(C05/C07/C08/C09/C11/C12/C13/C14/C15/C16/C17)の本文縮退と plugin-root references/ 配置は P05 の完了条件(移動のみ・情報消失禁止)であり、本フェーズでは新設 C24(lint-reference-attribution.py)と evidence により、機能を一切変えずに(tdd-refactor)一本化状態(重複0)を検証する。P05 が移動を完了するため置換・清掃作業は本フェーズに残らず、責務は invariant 確認に限定する。

## 背景
責務再均衡は「新機能の追加」ではなく「既存の procedural knowledge/rubric の置き場所の是正」であるため、P05 で実装した移設結果を P07 で purpose 受入し、本フェーズでは refactor として残留重複が 0 であることを検証する。ここで初めて rebalance 本体を実行すると P07 の受入判定と順序矛盾するため、P08 の責務は P05 の移設結果を崩さず、resource-map.yaml による帰属一本化と agent 本文の薄化状態を維持・検証することに限定する(P05 が「移動のみ」で移設を完了するため、残存重複への置換・清掃という条件付き作業は本フェーズに存在しない)。tdd-refactor の性質上、検証の前後で機能テスト(P06 で緑化済み)が赤に戻らないことが絶対条件になる。

## 前提条件
- P07 の受入判定が全 PASS。
- P06 のテストが緑。
- lint-reference-attribution.py(C24)が利用可能で、resource-map.yaml の帰属宣言を機械検証できる。

## ドメイン知識
- 残留重複0の invariant 検証: P05 で plugin-root references/ へ移設済みの procedural knowledge/rubric が元の sub-agent 本文に重複残存していないこと(重複0)を lint-reference-attribution.py で検証する。P05 が「移動のみ・情報消失禁止」で移設を完了するため、本フェーズに置換・清掃作業は無く、二重定義0の invariant を確認するのみ(共存縮退の検出は Red として P05 へ差し戻す)。
- 帰属 SSOT の検証: P05 で旧 resource-map.md(散文・機械検証不能)から resource-map.yaml(構造化・owner_component/consumers[]/category)へ移行済みであることを確認し、旧ファイルや二重の帰属 SSOT を残さない。
- 委譲先 1:1 の維持: 各 thin-adapter agent の procedural knowledge は plugin-root references/ の1ファイルへのみ昇格し(論理オーナー=delegation_target skill・C01×9/C02×1/C03×1)、複数ファイルへ分散させない(帰属の単純性維持)。
- tdd-refactor の不変条件: リファクタリング中もテスト緑を維持する(赤に戻ったら即巻き戻し)。

## 成果物
- P05 で完了した procedural knowledge/rubric 移設後に、11 thin-adapter agent 本文へ重複記述が残っていないこと(重複0 の invariant)を検証した記録。
- resource-map.yaml が旧 resource-map.md を完全に置換し、plugin-root content references 61件 (既存50=直下45+feedback/5 + 新設11・D2一本化) の帰属を一本化した状態を再確認した記録(resource-map.yaml 自身は content 外の帰属メタ)。

## スコープ外
- 新機能の追加(リファクタリングは挙動不変)。
- 受入基準・criteria の変更(P04/P07 の責務)。
- vendor Node engine・schemas 共通コアへの波及(goal-spec C7 により対象外・本フェーズは agent⇔skill 間の情報配置境界のみ)。

## 完了チェックリスト
- [ ] lint-reference-attribution.py(C24)が exit0 で、plugin-root content references 61件 (既存50=直下45+feedback/5 + 新設11) 全件が owner_component/consumers を宣言している。
- [ ] P05 の移設後、11 thin-adapter agent 本文に procedural knowledge/rubric の重複記述が残っておらず(重複0 の invariant)、plugin-root references への参照へ一本化されている(論理オーナー=delegation_target 1:1 維持)。
- [ ] 旧 resource-map.md が resource-map.yaml へ完全置換され、二重の帰属 SSOT が存在しない。
- [ ] invariant 検証によってテストが赤に戻っていない(tdd-refactor 維持・P06 で緑化済みの機能テストが継続して PASS)。

## 参照情報
- lint-reference-attribution.py(C24・references 帰属の機械検証)。
- 対象 component C01/C02/C03(委譲先 skill)+ C05/C07/C08/C09/C11/C12/C13/C14/C15/C16/C17(thin-adapter agent)+ C24(帰属検証 script)。
- 後続 P09(quality-assurance)。

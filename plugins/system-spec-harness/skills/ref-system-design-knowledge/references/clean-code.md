# Clean Code — deep knowledge card

> knowledge_id: `clean-code` / status: `seed-example`。特定著者の規則を絶対視せず、language/team/domainに合わせて可読性と変更安全性を実測する。

## 目的

codeを、次の変更者が意図・制約・failureを短時間で理解し、安全に変更・検証できる作業媒体にする。

## 背景

codeは実行物であると同時に、仕様、設計判断、team communicationの一部である。短期的に動く実装でも、曖昧な名前、隠れた副作用、巨大責務、重複知識が蓄積すると、変更時間と欠陥率が上がる。一方、行数や関数長の機械的な美学だけでは目的を保証しない。

## 解決する問題

- 名前と抽象度が意図を表さず、readerが実装詳細からbusiness ruleを逆算する。
- 一つの変更理由が複数moduleへ散り、副作用とerror pathを予測できない。
- 重複したruleが別々に更新され、仕様のSSOTが崩れる。
- testがimplementation detailへ結合し、refactoringを妨げる。

## 中核概念

- **Intention-revealing names**: domain語彙、単位、状態、side effectを名前で表し、曖昧な略語を避ける。
- **Cohesion and single reason to change**: 一緒に変わる知識をまとめ、別理由で変わる責務を分ける。
- **Explicit effects and errors**: I/O、mutation、time、randomness、failureをboundaryへ寄せ、結果型/例外契約を一貫させる。
- **Appropriate abstraction / DRY**: 見た目の重複でなく同じknowledgeを統合し、偶然似たcodeを早期抽象化しない。
- **Executable examples**: behaviorとinvariantをtestで表し、内部構造でなくobservable outcomeを守る。
- **Continuous refactoring**: 小さい安全な変更とfeedbackで設計を保ち、cleanupを大規模後工程へ送らない。

## 適用条件

- 複数人・長期保守・高変更頻度・重要ruleがあり、理解と変更の費用が支配的。
- test/lint/review/observabilityで改善効果をfeedbackできる。
- domain languageとcoding conventionをteamで合意・更新できる。

## 非適用条件

- throwaway explorationでは全規則を先行適用せず、学習後に残すcodeだけを整理する。
- generated/vendor codeへ手動styleを強制しない。generation inputとboundaryを管理する。
- 短い関数、class化、DRY等を絶対値として扱い、局所的な明瞭さを悪化させる場合は適用しない。

## トレードオフ・失敗モード

- naming/refactoring/testへ時間を使うため、寿命とriskが低いcodeでは投資超過になり得る。
- micro-function化でcontrol flowが多数fileへ散り、かえって読みにくくなる。
- DRYを急ぎ、異なるdomain conceptを一つの抽象へ結合して変更を難しくする。
- commentを全否定して、理由、trade-off、外部制約、security decisionまで消す。
- coverageやlint scoreを目的化し、重要behaviorの未検証を隠す。

## 目的達成への寄与

- goalに関わるbusiness ruleを名前とtestで明示し、仕様→code→evidenceのtraceを短くする。
- maintenance objectiveには変更lead time、review指摘、escaped defect、rollback率などのoutcomeを使う。
- 無料toolの導入自体を成功とせず、teamが継続運用でき、重要riskを減らすかで判断する。

## ヒアリング・判断観点

- 最も変更が多く誤解が高価なruleは何か。誰が読むか。
- teamが自動検査できる規則と、reviewで意味判断すべき規則は何か。
- 重複は同じknowledgeか、たまたま同じ形か。抽象を撤退する条件は何か。

## 一次資料

- Robert C. Martin, *Clean Code* (2008), Prentice Hall。
- Martin Fowler, *Refactoring, Second Edition* (2018), Addison-Wesley, https://martinfowler.com/books/refactoring.html
- Kent Beck, *Tidy First?* (2023), O’Reilly。

## 鮮度

- class: `foundational-stable`
- last_checked: `2026-07-11`; review_by: `2027-07-11`
- trigger: language/tooling変更、teamの変更lead time/defect実測悪化、規則がaccessibility/performance/securityを阻害する場合。


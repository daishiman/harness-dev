# Clean Architecture — deep knowledge card

> knowledge_id: `clean-architecture` / status: `seed-example`。本カードは探索開始点であり、アーキテクチャ知識の網羅リストではない。

## 目的

変化しやすいUI、DB、framework、外部サービスから、長く保持したい業務ルールとuse caseを隔離し、技術交換やテストを目的達成の阻害要因にしない。

## 背景

delivery初期はframework直結が速く見えるが、外部詳細がbusiness logicへ浸透すると、DB/UI変更、テスト、並行開発のたびに変更範囲が増える。Clean Architectureは層数を固定する方式ではなく、policyとmechanismを分け、source dependencyを高水準policy側へ向ける設計原則である。

## 解決する問題

- 業務ルールがcontroller/ORM/UI lifecycleへ埋まり、単体で検証できない。
- 外部技術変更が内側のuse caseまで波及し、置換費用を予測できない。
- 入出力形式やvendor型が境界を越え、責務と所有者が曖昧になる。

## 中核概念

- **Dependency Rule**: source dependencyは外側のmechanismから内側のpolicyへ向け、内側は外側の名前や型を知らない。
- **Entities / Use Cases**: enterprise規則とapplication固有の処理を、delivery/persistenceから独立して表す。
- **Ports and Adapters / DIP**: 内側が必要なportを定義し、外側adapterが実装する。実行時control flowとsource dependencyは逆向きになり得る。
- **Boundary data**: 境界を跨ぐ値は内側に都合のよい単純なrequest/response modelとし、DB rowやframework objectを持ち込まない。
- **Screaming architecture**: top-level構造がframework名でなくsystemのuse caseとdomainを語る。

## 適用条件

- business ruleが外部I/Oより長寿命で、UI/DB/providerの変更可能性がある。
- 複数delivery channelや外部integrationから同じuse caseを再利用する。
- 重要なpolicyを高速・決定論的にテストする価値が、境界導入費を上回る。

## 非適用条件

- 寿命の短い検証用prototypeで、交換可能性より学習速度が明確に優先される。
- domain ruleがほぼ無い単純変換scriptで、port/adapterが実質的な抽象を生まない。
- 外部製品そのものがsystemの目的で、抽象化すると必要機能が失われる。ただしsecurity/audit boundaryは別途必要。

## トレードオフ・失敗モード

- 境界、DTO、mapping、dependency injectionの量が増え、小規模systemでは認知負荷が先行する。
- 「4層を作ること」が目的化すると、変化軸のないinterfaceやpass-through use caseが増える。
- domain modelを万能化してdelivery固有の制約を隠すと、現実のlatency/transaction/error semanticsを見失う。
- portを外側が定義したりinner layerがORM型を返したりすると、名前だけcleanな依存逆転になる。

## 目的達成への寄与

- `essential_purpose`に直結するpolicyを外部詳細から守り、goal達成ロジックの検証を速くする。
- 制約に「vendor lock-in低減」「複数platform」「高い変更頻度」がある場合、変更範囲と移行riskを局所化する。
- 適用判断は「何層あるか」でなく、守るgoal、予想される変更、boundary testで観測する。

## ヒアリング・判断観点

- どの規則がsystemの本質で、どの技術詳細より長く残るか。
- 交換したい可能性がある外部要素は何か。交換不要なら抽象化費用は正当化されるか。
- use caseをUI/DBなしで受入基準まで検証できるか。

## 一次資料

- Robert C. Martin, “The Clean Architecture” (2012), https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Robert C. Martin, *Clean Architecture* (2017), Pearson/Addison-Wesley。

## 鮮度

- class: `foundational-stable`
- last_checked: `2026-07-11`; review_by: `2027-07-11`
- trigger: 原著者の原則訂正、採用frameworkがdependency boundaryを強制/破壊する変更、projectでboundary費用が価値を上回る実測。


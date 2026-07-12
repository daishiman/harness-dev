# Domain-Driven Design — deep knowledge card

> knowledge_id: `ddd` / status: `seed-example`。DDDは複雑domain向けの設計approachで、microservices採用や全codeのobject化を意味しない。

## 目的

businessの重要なruleと用語をmodel/code/会話で一致させ、複雑性を適切な境界へ閉じ込め、継続的な学習をsoftwareへ反映する。

## 背景

大規模domainでは同じ「顧客」「商品」でも部門やprocessごとに意味が異なる。単一enterprise modelへ無理に統一すると曖昧さがcodeへ入り、逆にtechnical layer中心で分割するとbusiness invariantが散る。DDDはdomain expertとのmodel探索とbounded contextによる意味境界を重視する。

## 解決する問題

- 仕様語、画面語、DB列、code名がずれ、変更時に意味を再解釈する。
- 異なる業務文脈の同名概念を一modelへ押し込み、巨大で矛盾したmodelになる。
- invariantとtransaction ownerが不明で、どこからでもdataを変更できる。
- legacy codeのtechnical構造がbusiness capabilityを隠し、改善順を決められない。

## 中核概念

- **Ubiquitous Language**: bounded context内でexpertとdeveloperが同じ語とruleを使い、会話・test・codeで継続検証する。
- **Bounded Context / Context Map**: modelが一貫する境界と、境界間の関係・翻訳・ownershipを明示する。
- **Entity / Value Object**: identityで追跡するものと、値・不変性で表す概念を区別する。
- **Aggregate**: 強いinvariantを一transactionで守る整合性境界。外部変更はaggregate rootを経由する。
- **Domain Event**: domainで起きた過去の事実を明示し、境界間の連携と監査を支える。
- **Strategic design**: core/supporting/generic subdomainを区別し、投資とbuild/buy判断を目的価値へ合わせる。

## 適用条件

- rule、例外、用語、状態遷移が多く、domain expertとの継続的なmodel学習が価値を持つ。
- team/部門ごとに言葉やownershipが異なり、integrationで翻訳が必要。
- core domainの差別化がsystemの本質的目的に直結する。

## 非適用条件

- 単純CRUD、汎用supporting機能、既製serviceで十分なgeneric subdomain。
- domain expertへアクセスできず、用語とruleを検証するfeedback loopを作れない段階。
- bounded contextをservice数へ機械変換する目的。monolith内moduleでも境界は成立する。

## トレードオフ・失敗モード

- workshop、model、mapping、専門語彙の維持に継続的な時間が必要。
- aggregateを大きくしすぎてlock/latencyを増やす、細かくしすぎてinvariantをeventual consistencyへ漏らす。
- 「Repository/Entity」等のpattern名だけ採用したanemic modelになり、business ruleがserviceへ散る。
- bounded contextを組織図やDB tableから決め、実際の言語・capability境界を検証しない。
- eventを事実でなくcommandとして命名し、ordering/idempotency/failure recoveryを設計しない。

## 目的達成への寄与

- U1-U9の語彙をmodelへ接続し、goalがどのcontext/capability/invariantで実現されるかを示す。
- core domainへ設計投資を集中し、generic領域は無料/低コストserviceや標準実装も比較対象にできる。
- refactoringは一括rewriteでなく、重要なbusiness rule周辺からstrangler/bubble context等で境界を育てる。

## ヒアリング・判断観点

- 同じ語がstakeholderごとに別の意味を持つ箇所はどこか。
- 失敗してはいけないinvariantと、その変更を承認するownerは誰か。
- 差別化するcore domainと、購入/外部化可能なgeneric subdomainは何か。

## 一次資料

- Eric Evans, *Domain-Driven Design* (2003), Addison-Wesley。
- Martin Fowler, “Bounded Context”, https://martinfowler.com/bliki/BoundedContext.html
- Martin Fowler, “DDD Aggregate”, https://martinfowler.com/bliki/DDD_Aggregate.html

## 鮮度

- class: `foundational-stable`
- last_checked: `2026-07-11`; review_by: `2027-07-11`
- trigger: domain language/ownership変更、context間integration failure、aggregateのlatency/consistency実測悪化、原典の重要な解釈訂正。


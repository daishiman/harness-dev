# Design Patterns — deep knowledge card

> knowledge_id: `design-patterns` / status: `seed-example`。GoF 23は語彙のseedであり、全system・全paradigmの完全な解法集ではない。

## 目的

反復して現れる設計問題と責務分割を共通語彙で表し、変更軸に合う既知の協調構造を再利用しながら、独自仕組みの説明・検証費を減らす。

## 背景

patternは完成コードや必須architectureではなく、特定contextで繰り返すproblem、forces、解決構造、結果をまとめたもの。GoFはobject-oriented designの23 patternを整理したが、実際の選択はdomain、language機能、runtime、team理解度に依存する。

## 解決する問題

- 生成、構造、振る舞いの変更が一箇所へ集中し、条件分岐と結合が増える。
- 設計意図を毎回独自用語で説明し、reviewerが責務境界を再発見する。
- 拡張点が曖昧で、追加ごとに既存コードを広く変更する。

## 中核概念

- **Creational**: Factory Method / Abstract Factory / Builder等で生成方針と利用側を分ける。
- **Structural**: Adapter / Decorator / Facade / Proxy等でinterface差、責務追加、境界を構成する。
- **Behavioral**: Strategy / State / Observer / Command等で変化するrule、状態遷移、通知、操作を分離する。
- **Forces and consequences**: pattern名より、解くproblem、競合する制約、導入後の結合・複雑性を明示する。
- **Language-native alternative**: 高階関数、algebraic data type、module、protocol等が同じ問題をより単純に解く場合がある。

## 適用条件

- 同じ変更理由で分岐や実装差が複数回現れ、安定interfaceと変化部分を特定できる。
- pattern名がteamの共通語彙として設計意図を短く正確に伝える。
- 追加indirectionをtest、交換可能性、責務分離で回収できる。

## 非適用条件

- 将来の可能性だけで変更軸が未観測、単一実装しかない段階。
- languageの標準機能や単純関数で同じ目的を明瞭に達成できる。
- pattern導入がdomain語彙を隠し、codeをpattern役名の寄せ集めにする。

## トレードオフ・失敗モード

- indirection、型、file、object数が増え、追跡とdebugが難しくなる。
- pattern huntingによりproblemより解法名を先に決め、過剰なFactory/Singleton/Observerを導入する。
- Singletonがglobal mutable state、Observerが隠れたcontrol flow、Decoratorが順序依存を生む。
- patternを採用した理由と撤退条件が無いと、context変化後も複雑性だけ残る。

## 目的達成への寄与

- `concrete_intents`にある拡張・差替・状態遷移を、goalに必要な最小のvariation pointへ変換する。
- 選択時は「pattern準拠」ではなく、変更容易性、欠陥率、理解時間などgoalに結び付く成果で比較する。
- 代替案として単純実装を必ず含め、patternの便益が実測できる場合だけ採用する。

## ヒアリング・判断観点

- 実際に繰り返している変更は何で、何が安定しているか。
- patternを外した単純案と比べ、どの受入基準が改善するか。
- failure時にcontrol flowとownerを追跡できるか。

## 一次資料

- Erich Gamma et al., *Design Patterns: Elements of Reusable Object-Oriented Software* (1994), Addison-Wesley, https://www.pearson.com/en-us/subject-catalog/p/design-patterns-elements-of-reusable-object-oriented-software/P200000000497
- Christopher Alexander et al., *A Pattern Language* (1977), Oxford University Press（pattern languageの源流）。

## 鮮度

- class: `foundational-stable`
- last_checked: `2026-07-11`; review_by: `2027-07-11`
- trigger: 採用languageの新しい型/module機能、並行/分散runtime制約、patternが実測上の変更容易性を悪化させた場合。

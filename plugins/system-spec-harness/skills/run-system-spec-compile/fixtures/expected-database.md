---
status: confirmed
category: database
aggregate: 確定
spec_cells: [database.web, database.mobile, database.tablet, database.desktop-windows, database.desktop-linux, database.desktop-macos]
serves_goals: [G1]
---

# データベース (database)

- カテゴリ集約状態: **確定**
- 章確定マーカー: `status: confirmed`

## カテゴリ別収集状態

| プラットフォーム | 状態 | 根拠 |
|---|---|---|
| Web (web) | 確定 | 確定質疑: qa-database。資するゴール: G1 |
| モバイル (mobile) | 確定 | 確定質疑: qa-database |
| タブレット (tablet) | 確定 | 確定質疑: qa-database |
| デスクトップ (Windows) (desktop-windows) | 確定 | 確定質疑: qa-database |
| デスクトップ (Linux) (desktop-linux) | 確定 | 確定質疑: qa-database |
| デスクトップ (macOS) (desktop-macos) | 確定 | 確定質疑: qa-database |

## 上流指針 (doctrine anchors)

> 本章の設計判断が従う上流の正本 (1 concern 1 authority)。具体技術ではなく上流工程を導く規範であり、下位の技術選定は本節と矛盾してはならない。正本: `ref-system-design-knowledge/references/doctrine-anchor-registry.json`

| 設計 concern | 上流の正本 (authority) | 導く範囲 | 出典 | 最終確認 | 本章の確定セルへの反映 |
|---|---|---|---|---|---|
| data-access | Robert C. Martin — Clean Architecture | 永続化を境界の外側へ追い出し interface adapter で隔離する | Clean Architecture — gateways/repositories boundary | 2026-07-12 | **未記入** |
| reliability | Google SRE | SLO/エラーバジェット・冗長性・スケーリング・監視の上流指針 | https://sre.google/books/ | 2026-07-12 | **未記入** |

> **未記入** の行は、上流の正本を掲げただけで本章の確定内容へ反映した箇所を示せていない。表への出現は反映の証拠ではない。

## 確定内容 (質疑録)

> 本章の各確定セルが何を根拠に確定したかの実体。`qa_ref` が主たる接地根拠、`qa_refs` がそれを支える裏付け質疑であり、いずれも qa_log (spec-state.json) の逐語である。ここに現れない主張は本章の確定内容ではない。

### Web (web)

- 資するゴール: G1

#### 主たる接地根拠: `qa-database`

**問**

データ永続化方式は?

**答**

PostgreSQL 16 を全プラットフォーム共通で採用

### モバイル (mobile)

#### 主たる接地根拠: `qa-database`

**問**

データ永続化方式は?

**答**

PostgreSQL 16 を全プラットフォーム共通で採用

### タブレット (tablet)

#### 主たる接地根拠: `qa-database`

**問**

データ永続化方式は?

**答**

PostgreSQL 16 を全プラットフォーム共通で採用

### デスクトップ (Windows) (desktop-windows)

#### 主たる接地根拠: `qa-database`

**問**

データ永続化方式は?

**答**

PostgreSQL 16 を全プラットフォーム共通で採用

### デスクトップ (Linux) (desktop-linux)

#### 主たる接地根拠: `qa-database`

**問**

データ永続化方式は?

**答**

PostgreSQL 16 を全プラットフォーム共通で採用

### デスクトップ (macOS) (desktop-macos)

#### 主たる接地根拠: `qa-database`

**問**

データ永続化方式は?

**答**

PostgreSQL 16 を全プラットフォーム共通で採用

## To-Be / Delta

> 本章の**規範**。上位概念 (要件定義書 U3 ゴール / U4 目標 / U9 具体的やりたいこと) を本章の serves_goals で絞り込んだ射影であり、設計知識 card (非規範の参考資料) とは役割が異なる。As-Is (現行実装の姿) は spec-state.json の管轄外のため本節では断定せず、到達点と、その到達を判定する観測点だけを規範として置く。

### 到達すべき状態 (To-Be)

- **G1**: 請求・監査データを単一の信頼できる情報源へ統合する

### 受入条件 (Delta の判定点)

- (本章ゴールに紐づく目標 U4 が無い。受入条件が未定義である)

### 本章がかなえる具体的やりたいこと (U9)

- **I1**: 請求データを日次でバックアップする

### 本章に効く確定意思決定

- (本章ゴールに効く確定 decision なし)

## 適用された設計知識

> 以下の deep knowledge card は設計判断を支援する**非規範の参考資料**であり、実装済み・検証済みの証拠ではない。カード内の `採否: applied` は設計採用を意味し、実装状態は意味しない。規範となる差分は本章の To-Be / Delta 節と参照先仕様で管理する。

### 本章での適用

> **未記入** — 本章固有の適用記述が spec-state に無い。以下の card 本文は共有資産の逐語であり、同じ card を引く他章と一致する。この節は現時点で「参照した」ことしか示しておらず、「適用した」証拠ではない。

### Domain-Driven Design — deep knowledge card

- 出典カード: `ref-system-design-knowledge/references/ddd.md`

#### 目的

businessの重要なruleと用語をmodel/code/会話で一致させ、複雑性を適切な境界へ閉じ込め、継続的な学習をsoftwareへ反映する。

#### 解決する問題

- 仕様語、画面語、DB列、code名がずれ、変更時に意味を再解釈する。
- 異なる業務文脈の同名概念を一modelへ押し込み、巨大で矛盾したmodelになる。
- invariantとtransaction ownerが不明で、どこからでもdataを変更できる。
- legacy codeのtechnical構造がbusiness capabilityを隠し、改善順を決められない。

#### 適用条件

- rule、例外、用語、状態遷移が多く、domain expertとの継続的なmodel学習が価値を持つ。
- team/部門ごとに言葉やownershipが異なり、integrationで翻訳が必要。
- core domainの差別化がsystemの本質的目的に直結する。

#### 非適用条件

- 単純CRUD、汎用supporting機能、既製serviceで十分なgeneric subdomain。
- domain expertへアクセスできず、用語とruleを検証するfeedback loopを作れない段階。
- bounded contextをservice数へ機械変換する目的。monolith内moduleでも境界は成立する。

#### トレードオフ・失敗モード

- workshop、model、mapping、専門語彙の維持に継続的な時間が必要。
- aggregateを大きくしすぎてlock/latencyを増やす、細かくしすぎてinvariantをeventual consistencyへ漏らす。
- 「Repository/Entity」等のpattern名だけ採用したanemic modelになり、business ruleがserviceへ散る。
- bounded contextを組織図やDB tableから決め、実際の言語・capability境界を検証しない。
- eventを事実でなくcommandとして命名し、ordering/idempotency/failure recoveryを設計しない。

#### goalへの寄与

- U1-U9の語彙をmodelへ接続し、goalがどのcontext/capability/invariantで実現されるかを示す。
- core domainへ設計投資を集中し、generic領域は無料/低コストserviceや標準実装も比較対象にできる。
- refactoringは一括rewriteでなく、重要なbusiness rule周辺からstrangler/bubble context等で境界を育てる。

---

### Cloud Architecture Patterns — deep knowledge card

- 出典カード: `ref-system-design-knowledge/references/cloud-architecture-patterns.md`

#### 目的

マネージドなクラウド基盤 (オブジェクトストレージ・リレーショナル/KV ストア・エッジ実行環境・キュー) を組み合わせるとき、データの配置・整合性の境界・劣化の順序を、後から検証できる根拠とともに決める。

#### 解決する問題

- 大容量バイナリを DB 行へ格納し、本文を必要としない一覧クエリまで巨大な行の読み出しに巻き込む。
- 複数のマネージドサービスに跨る書込みを、暗黙に原子的だと仮定して整合性の破れを設計外に置く。
- 障害時に何を先に諦めるかが未定義で、劣化の仕方が実行環境や実装者ごとにばらつく。
- 署名や認可を通さない公開 URL でバイナリを配信し、識別子の漏洩がそのまま内容の漏洩になる。
- サービス固有の制約 (実行時間・ペイロード上限・同時実行) を非機能要件として書き出さず、規模が伸びた時点で設計をやり直す。

#### 適用条件

- マネージドな複数サービス (ストレージ・DB・実行環境) を組み合わせ、単一トランザクションで閉じない書込みがある。
- 利用者が生成するバイナリ (画像・添付) を保存し、その一覧や検索を別途提供する。
- 実行環境に明示的な資源上限があり、超過が機能の失敗として現れる。

#### 非適用条件

- 単一ノード・単一 DB で完結し、外部ストレージを持たない構成に、跨る書込みの補償設計を先行導入しない。
- バイナリが小さく件数も限られる場合 (例: 数 KB のアイコン数十件) に、参照の間接化による往復増を払わない。
- 基盤が既に保証している性質 (オブジェクトストレージ側の耐久性・多重化) を、自前の複製で二重化しない。

#### トレードオフ・失敗モード

- バイナリを外へ出すと、DB とストレージが別系になり原子性が失われる。書込み順序の固定と孤児回収を設計に含めないと、参照切れが蓄積する。
- 冪等キーを導入すると、鍵の生存期間と保管場所という新しい状態が増える。期限設計を怠ると、正当な再投稿まで重複として捨てる。
- 認可を通す配信は CDN キャッシュを効きにくくする。閲覧者数が大きい経路にそのまま適用すると費用と遅延が悪化する。
- 制約を非機能要件に書いても、実測せずに数値を置くと「守っているつもり」の仕様になる。上限付近の実測を伴わない宣言は根拠にならない。
- 劣化順序を決めても、超過時の記録を残さないと、仕様どおり劣化したのか単に壊れたのかを事後に区別できない。

#### goalへの寄与

- データ配置の判断を、製品名ではなく「何が原子的か・何が検索対象か」という検証可能な性質へ還元でき、後から根拠を追える。
- 一覧の読み出し費用を保存量から独立させ、利用が伸びても管理画面の応答が劣化しない構造を先に確保する。
- 壊れる向きを事前に選ぶことで、障害時の復旧手順が「どちらが正か」を都度判断しない決定的な手順になる。

---

### 確定判断ごとの原則採否

- 確定内容 `qa-database` (対応セル: web, mobile, tablet, desktop-windows, desktop-linux, desktop-macos)
  - 確定要件: 「PostgreSQL 16 を全プラットフォーム共通で採用」 (正本: 本章「確定内容 (質疑録)」の `qa-database`)
  - 設計解釈の記録経路: `unrecorded`
  - 設計原則の採否根拠: (未記録 — qa_log[].design_applications を writer 経由で補完すること)
- 資するゴール: G1

## 最新ドキュメント出典

| 対象 | バージョン | 公式発行元 | 出典URL | 取得 | 最新確認 |
|---|---|---|---|---|---|
| postgres | 16.1 | PostgreSQL Global Development Group (www.postgresql.org) | https://www.postgresql.org/docs/16/ | 2026-07-11T00:00:00Z | 2026-07-11T00:00:00Z |

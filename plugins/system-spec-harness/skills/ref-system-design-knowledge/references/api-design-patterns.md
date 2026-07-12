# API Design Patterns — deep knowledge card

> knowledge_id: `api-design-patterns` / status: `seed-example`。REST/HTTPはseedであり、event、stream、GraphQL、RPC等を排除する完全taxonomyではない。

## 目的

consumerとproviderの独立変更を支える安定した契約を作り、再試行、失敗、並行更新、pagination、evolutionを予測可能にする。

## 背景

APIは内部実装より長く残る外部契約であり、公開後の曖昧さや破壊的変更はconsumer全体へ波及する。resource-oriented設計は有力だが、operation semantics、consistency、latency、consumer needsに適合する方式を選ぶ必要がある。

## 解決する問題

- resource/operationの意味、error、null、time、identifierがendpointごとに揺れる。
- timeout後の再試行で二重処理が起き、clientが成功/失敗を判断できない。
- collection増大や並行更新でoffset paginationと全件responseが破綻する。
- version/evolution方針がなく、provider変更がconsumerを突然壊す。

## 中核概念

- **Contract first**: request/response/error/auth/limits/compatibilityをmachine-readable schemaと例で固定する。
- **Resource and operation semantics**: HTTP method、status、safe/idempotent性を実際のdomain operationに合わせる。POSTもidempotency keyで再試行安全にできる。
- **Opaque pagination token**: 並び順と継続位置をserverが所有し、tokenをauthorizationとして扱わない。
- **Concurrency and consistency**: ETag/If-Match、version、idempotency key、eventual consistencyの観測方法を契約に含める。
- **Evolution**: additive changeを基本に、deprecation window、consumer telemetry、移行/rollbackを設計する。
- **Error model**: machine code、human message、field details、retryability、correlation idを一貫させる。

## 適用条件

- 複数client/team/organizationが独立releaseで同じservice boundaryを利用する。
- network failureとretryが通常事象で、operation結果の重複や不明状態を制御する必要がある。
- contractの長期互換性とobservabilityが局所的な実装簡潔性より重要。

## 非適用条件

- 同一process内のprivate callで、network boundaryや独立versioningが存在しない。
- hard real-time stream、双方向session、巨大event flowなど、request/response RESTが問題形状に合わない。
- 単純CRUD表面化がdomain invariantを迂回させる場合。use-case operationまたは別interaction modelを選ぶ。

## トレードオフ・失敗モード

- version、idempotency ledger、schema governance、compatibility testに運用費がかかる。
- 「名詞URL」だけ守ってtransaction、authorization、error semanticsを設計しない表層RESTになる。
- offset paginationは簡単だが大規模/更新中datasetで遅延・重複・欠落を起こす。
- idempotency keyのscope/TTL/payload bindingが曖昧だと、別requestを誤って同一視する。
- breaking changeを新versionで逃がし続けると、複数version保守とsecurity patch負担が増える。

## 目的達成への寄与

- mobile/web/desktop間で一貫したbusiness capabilityを共有し、platform別再実装を減らす。
- reliability goalにはretry-safe operationと明示的error、delivery goalにはcontract testとadditive evolutionを結ぶ。
- 選択はAPI様式の流行でなく、consumer、latency、consistency、offline、security、cost constraintsへの適合で評価する。

## ヒアリング・判断観点

- consumer、operation、再試行、並行更新、最大collection、互換期間は何か。
- timeout時にclientは「未実行/成功/処理中」をどう判定するか。
- 無料/低コストproviderを採用する場合、rate limit、egress、lock-in、終了時exportは受入可能か。

## 一次資料

- Google API Improvement Proposals, https://google.aip.dev/ （例: AIP-158 Pagination）。
- Microsoft REST API Guidelines, https://github.com/microsoft/api-guidelines
- IETF HTTP Semantics, RFC 9110, https://www.rfc-editor.org/rfc/rfc9110

## 鮮度

- class: `standard-tracked`
- last_checked: `2026-07-11`; review_by: `2027-01-11`
- trigger: HTTP/RFC/AIP改訂、provider SDKの破壊的変更、security advisory、rate limitや価格/無料枠変更。


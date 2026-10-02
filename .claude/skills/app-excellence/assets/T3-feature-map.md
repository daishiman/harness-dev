# T3. 機能分解・実装計画 — [アプリ名]

## 1. 最リスク仮説

> ____(これが成り立たないと全部無駄、という仮説)
検証方法: ____ / 検証されるSlice: [0 / 1]

**成果物先行の1本目**: ____
**他候補より先に作る理由**: ____

## 2. ストーリーマップ

背骨: [行動1] → [行動2] → [行動3] → [行動4]

| Slice | [行動1] | [行動2] | [行動3] | [行動4] |
|---|---|---|---|---|
| 0 骨格 | | | | |
| 1 MVP | | | | |
| 2 磨き | | | | |

## 3. スライス実装順・全層trace・要件フラグ

| Slice | 最頻業務フロー | UI action | API/command | domain/service | DB schema/migration | read model/UI state | catalog adoption(profile/対象/証拠/例外、またはNON_VISUAL理由) | 要件フラグ→品質契約と実装箇所 | E2E証拠(保存→再読込→更新→失敗回復) | 状態 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | | | | | | | | auth/authz/validation/idempotency/audit/secret/observability/backup/rollbackを `required / N/A / deferred(理由)` で記録 | | |

不要な層は空欄にせず `N/A(理由)` とする。traceの正本は `references/03-feature-decomposition.md` §2-1。catalog adoptionの正本はjp-web-design `references/catalog-default-contract.md`。

## 4. 判断記録(RICE採点・却下した代替案)

## 5. 変更ログ(追加要望は必ずここに新カードとして)

| 日付 | 要望 | 判断(どのSliceへ/保留) | 成果物での検証結果 |
|---|---|---|---|

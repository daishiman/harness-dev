---
name: ref-notion-gmail-send-spec
description: Notion 2DB→Gmail個別送信のデータ契約や安全設計を確認したいとき、送信ログschemaやpreflight gateの参照知識が必要なときに使う。
disable-model-invocation: false
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-06-24
version: 0.1.0
source: "doc/run-notion-gmail-send-仕様と検証メモ.md"
source-tier: internal
last-audited: 2026-06-24
audit-trigger: source-update
allowed-tools:
  - Read
  - Bash(python3 *)
---

# ref-notion-gmail-send-spec

## Purpose & Output Contract

`run-notion-gmail-send` プラグイン（Notion 2DB → Gmail 個別送信）の **データ契約と安全設計の参照正本（SSOT 索引）**。後続スキル `run-notion-gmail-sendlog-setup` / `run-notion-gmail-dry-run` / `run-notion-gmail-send` と orchestrator がここを参照し、列マッピング・送信単位・冪等ログ・preflight の定義を二重実装せず一致させる。

**入力**: なし（知識参照）
**出力**: 列マッピング・本文true/宛先true定義・件数式・差し込み・メッセージ組立・送信ログ schema・status/reason_code enum・preflight gate・安全三本柱の知識。実行コードは `plugins/notion-gmail-send/lib/`。
**完了条件**: 参照のみ。Notion 取得・Gmail 送信は行わない（実行は `lib/` と各 run-skill が担う）。

## 入力: Notion 2DB 列マッピング（§3）

REST API（Keychain `notion-api-key.<keychain-prefix>`）で取得。Notion MCP は 404（未共有）のため REST 直叩き。

### DB1「メール本文_DB」(db_id は config `notion_gmail_send.source.body_db`)

| プロパティ | 型 | メール組立での写像 |
|---|---|---|
| 件名 | title | **Subject**（`{{}}` 置換対象） |
| メールの送り主 | email | **From**（impersonate 対象） |
| CC | email（カンマ区切り） | **CC**（分割し1通に並列） |
| メッセージ対象 | checkbox | 送信フィルタ（✅ かつ本文非空のみ送信） |
| （ページ本文） | code block | **Body**（`{{}}` 置換対象） |

### DB2「メール送信先_DB」(db_id は config `notion_gmail_send.source.recipient_db`)

| プロパティ(厳密名) | 型 | メール組立での写像 |
|---|---|---|
| `担当者様名` | title | `{{担当者様名}}`（差し込み＋宛名） |
| `会社名` | rich_text | `{{会社名}}` |
| `メール（プロ人材）` | email（カンマ区切り） | **To**（分割し1通に並列） |
| `メール（cc秘書）` | email（カンマ区切り） | **CC**（本文DB CC と結合・To除外・重複排除） |
| `メールを送らない` | checkbox | **抑制（送信対象より優先）** |
| `送信対象` | checkbox | 宛先フィルタ（✅ かつ 送らない☐ かつ プロ人材メール非空のみ宛先） |

`部署名` は廃止（D1）。同一プロ人材メールの重複は最新 `created_time` の1件のみ送信し、同時刻の場合は `page_id` 降順で1件に決定する。詳細は `references/spec-detail.md`。

## 本文true / 宛先true の定義（§4）

- **本文 true** ≡ `メッセージ対象=true` **かつ** 本文コードブロックが非空。本文は **最初の非空 `code` block** を採用。非空 `code` block が複数なら `skipped_validation(reason=multiple_body_code_blocks)` とし暗黙連結しない。
- **宛先 true** ≡ `送信対象=true` **かつ** `メールを送らない=false` **かつ** `メール（プロ人材）`(To) が非空。`メールを送らない=true` は送信対象より優先で抑制（`suppressed`）。同一プロ人材メール重複は最新 `created_time` の1件のみ残し、同時刻は `page_id` 降順で決定する（`duplicate_dropped`）。
- いずれも満たさない行は送信せず `skipped_validation` / `suppressed` / `duplicate_dropped` として計上・報告する（warning 止まりにしない）。

## 件数式（2段に分離・§4）

| 段 | 式 | 依存 |
|---|---|---|
| 第1段: 計画送信単位 | `本文true件数 × 宛先true件数`（直積） | **DB不要**。dry-run で常に算出 |
| 第2段: 正味送信予定 | `計画送信単位 − sent済み件数` | **送信ログDB ID 確定が前提**（preflight G2 通過時のみ） |

送信単位 = 本文true全行 × 宛先true全行。各単位を1通として送信する。

## 差し込み置換（§5）

- トークン: `{{会社名}}` `{{担当者様名}}`（二重波括弧）。`{{部署名}}` は廃止（D1）。
- 置換対象: **本文コードブロック と 件名（title）の両方**。置換元は各宛先（DB2）の対応値。
- **未置換トークン残存は fail-closed**: 置換後に `{{...}}` が残る送信単位は `skipped_validation(reason=unresolved_token)` とし**送信しない**。置換元が空値の場合も同様。
- サニタイズ: 差し込み値は改行・制御文字を除去/拒否する（ヘッダインジェクション防止。違反は `unsafe_header`）。

## メッセージ組立（§6・message-assemble）

| ヘッダ | 由来 |
|---|---|
| From | DB1「メールの送り主」（impersonate 対象） |
| To | DB2「メール（プロ人材）」（カンマ分割し1通に並列。同一行内 To は相互可視 → dry-run で `multi_to_visible=true` 警告） |
| CC | DB1「CC」 ＋ DB2「メール（cc秘書）」を結合（To除外・重複排除。プロ人材と秘書の両方へ送る・秘書は CC） |
| Subject | DB1「件名」（置換後） |
| Body | DB1 本文コードブロック（置換後） |

- 形式: RFC 822 / MIME 準拠。Gmail API へは base64url エンコードした raw message。
- メールアドレス形式を検証し、不正は `skipped_validation(reason=invalid_to / invalid_cc)`。
- 送信は `users.messages.send` で、送信メールは**送信者の「送信済み」に自動格納**される（D6）。
- From は impersonated user と一致、または Gmail `sendAs` alias として検証済みであること。未検証 alias は G1 で fail-closed（`from_alias_unverified`）。

## 送信ログDB schema と冪等（§9）

- **冪等キー**（title）: `{本文page_id}:{宛先page_id}:{content_hash}`。検索キーとして使う。`campaign_id` は含めず、別実行でも同一本文ページ×同一宛先ページ×同一内容の二重送信を止める。宛先を別Notionページとして作り直した場合は別単位。意図的再送時だけ `--allow-resend` が campaign suffix を付ける。
- 解決元: `.notion-config.json` の `databases.gmail-send-log.db_id`。
- Notion は一意制約を持たないため、送信前に検索 → 0件なら create reserved / 1件なら状態判定 / 2件以上は `duplicate_log_key` で fail-closed。

| プロパティ | 型 | 必須 | 用途 |
|---|---|---|---|
| 冪等キー | title | yes | 検索キー |
| campaign_id | rich_text | yes | 実行単位 |
| plan_hash | rich_text | yes | 承認済み plan の照合 |
| content_hash | rich_text | yes | 本文・件名・宛先の改変検知 |
| status | select | yes | 下記 enum |
| reason_code | select/rich_text | no | validation/error 理由 |
| 本文page_id / 宛先page_id | rich_text | yes | DB1 / DB2 ページ |
| From / To / CC | email / rich_text | From,To=yes | To/CC は分割後配列を JSON 文字列で保存 |
| 件名 | rich_text | yes | 置換後件名 |
| messageId | rich_text | no | Gmail 受理後に保存 |
| reserved_at / sending_at / sent_at | date | no | 状態遷移時刻 |
| error | rich_text | no | 秘密値を含まない要約 |

永続ログには本文全文を保存せず `content_hash` と件名のみ（PII 方針・§12）。状態遷移図は `references/spec-detail.md`。

## status enum（§9・副作用段階）

| status | 意味 |
|---|---|
| planned | dry-run plan に含まれるが送信予約前 |
| reserved | live-send 前に Notion ログへ事前予約済み。自動再送禁止のロック |
| sending | Gmail API 呼び出し直前〜応答処理中 |
| sent | Gmail API が受理し messageId 保存済み（**到達保証ではない**） |
| skipped_idempotent | 冪等ログに sent 済みで再送回避 |
| skipped_validation | 本文空/宛先欠落/未置換トークン/不正アドレス等で送信前除外 |
| error | Gmail API が失敗し未送信と判断できる |
| unknown_needs_reconcile | 送信成功後に Notion 更新失敗、または sending 中断で成否不明。**自動再送せず手動照合** |

## reason_code 一覧（§9）

`skipped_validation` / `error` / `unknown_needs_reconcile` に機械可読理由を必須化する。

| reason_code | 発生局面 |
|---|---|
| empty_body | 本文コードブロックが空 |
| multiple_body_code_blocks | 非空 code block が複数（暗黙連結しない） |
| body_fetch_failed | ページ本文取得/pagination 未完了 |
| invalid_to / invalid_cc | To / CC のアドレス形式不正 |
| unresolved_token | 置換後に `{{...}}` 残存 |
| unsafe_header | 差し込み値に改行/制御文字 |
| duplicate_recipient | 同一アドレスが複数 page に存在（暴発検知） |
| from_alias_unverified | From が sendAs alias 未検証 |
| quota_stopped | quota 枯渇で安全停止 |
| send_success_log_failed | Gmail 受理後の Notion 更新失敗 |
| duplicate_log_key | 同一冪等キーのログ行が2件以上 |
| needs_reconcile | 自動再送できない既存 unknown/reserved/sending の手動照合 |
| sending_interrupted | 前回 sending 中断で送信成否不明 |
| content_hash_mismatch | plan 内 content_hash と再計算値の不一致 |
| invalid_addr_at_send | 送信直前の MIME 再組立で宛先不正 |
| send_failed | Gmail API が未送信失敗として返した |
| no_approval / plan_hash_mismatch / count_mismatch / first_to_mismatch / nonce_mismatch / no_reserved_log | send_guard 違反 |

## preflight gate（§10・fail-closed）

dry-run preflight と live-send preflight を分離する。dry-run は送信ログDB なしでも第1段件数・plan_hash まで作れるが、live-send は送信ログDB なしでは必ず中断。

| ゲート | 検証内容 | 未充足時 |
|---|---|---|
| G0 dry-run | Notion 2DB 読取・本文抽出・置換・plan_hash 算出。Gmail/ログDB 不要 | 送信せず dry-run レポートのみ。本文0通は記入を促す |
| G1 認証 | Keychain SA鍵を `security` で列挙確認、`example.invalid` の DWD + `gmail.send` 承認、From の sendAs alias を**実 API で動的検証** | 送信せず中断。`doc/GCP-Gmail送信設定手順.md` へ誘導 |
| G2 依存実体 | 送信ログDB ID が `databases.gmail-send-log.db_id` で解決可能か、本文 true ≥ 1 か | DB ID 不在は db-setup へ差し戻し。本文0通は記入を促し終了 |
| G3 送信直前 | `approved_plan_hash == plan_hash`、承認 count/first_to 一致、未置換トークン・宛先件数・From 整合を機械検査 | 該当単位を `skipped_validation`、全体不整合なら中断 |

安全の正本は script 内 `send_guard()`。決定論的 script 内の Gmail API 呼び出しは PreToolUse hook で捕捉できない可能性があるため、`send_guard()` が approved_plan_hash・plan_hash・承認件数・先頭 To・reserved ログ行ID・未置換検査・From/sendAs 検証の全一致なしに Gmail API へ到達させない。hook は補助防御。

## 安全三本柱（§2・混同禁止）

| 安全装置 | 守る対象 | 効く局面 | 効かない局面（正直な明示） |
|---|---|---|---|
| 承認済み plan（plan_hash・units から決定論再計算で束縛） | plan.json 改竄・件数偽装・raw 改変（**厳格対話モード**＝plan.json が非信頼アーティファクトとなる経路で実効） | 厳格対話の承認後送信（`send_campaign` が units→plan_hash/件数/content_hash を再計算照合し raw も都度再生成） | **非対話(preview/confirm/cron)では承認 tuple が同一プロセス内 self-derive ゆえこの照合は恒真＝defense-in-depth(compose バグ検出)で plan 改竄保護価値は持たない。confirm は plan_hash を CONFIRM_TOKEN へ束縛・非対話の実効独立検証は source-audit/fresh rebuild/C-1/From検証/content dedup** |
| 承認（既定=Notion `送信対象=✅` + preview 要約への単一確認 / 無人cron=Notion `送信対象=✅` / 厳格対話=dry-run 全件目視 → 明示承認 + 確認語） | 誰に送るかの意思をデータ層または APPROVE 文字列で固定する。厳格対話の確認語は blind approve のコストを上げる | 全送信（初回含む） | **内容が意味的に正しいことの保証**（機構では強制不能。既定は preview 要約＋Notion 整備＋source-audit＋canary で緩和、厳格対話は目視で緩和） |
| 事前予約つき冪等ログ（Notionページ単位の content ベース dedup・reserved→sending→sent/unknown） | 再実行・**別実行（別 campaign）**での同一本文ページ×同一宛先ページ×同一内容の二重送信、送信成功後ログ失敗 | 2回目以降・別実行・障害復旧 | 別Notionページとして作り直した同一メールアドレスへの重複、意図的再送（`--allow-resend` で明示）。初回の内容妥当性 |

> ⚠️ 因果ループ警告: 「冪等があるから安全」は**初回送信の内容妥当性には成立しない**。初回内容は既定(最小確認1回)では preview 要約＋Notion のチェック整備＋source-audit/canary、厳格対話では目視承認で緩和する。承認後の内容固定は厳格対話の `plan_hash`＋送信前の決定論再計算（非対話は fresh rebuild と confirm モードの CONFIRM_TOKEN 束縛）、再実行・別実行の二重送信防止は content ベース冪等ログが担保する。
>
> 正直な限界: 承認文字列の機械照合は「plan が承認時から改竄されていない」ことを保証するが、「人間が本文を読み理解した」ことは保証できない（机上で強制不能）。確認語（dry-run が特定単位のプレビュー行末にのみ表示）はその単位を目視で探させ blind approve のコストを上げる緩和策であり、comprehension の証明ではない。最終的な内容妥当性は承認者の全件プレビュー目視に依存する。

## Key Rules

1. **参照専用**: 本スキルは契約の参照のみ。実行は `lib/` と各 run-skill。
2. **fail-closed 既定**: 未確定の外部依存は契約に静的に埋め込まず、preflight と `send_guard()` が実行時に送信を止める。build は通る。
3. **件数式は2段**: 第1段は DB 不要で常時算出、第2段は送信ログDB 確定が前提。
4. **未置換トークンは skip**: warning でなく `skipped_validation` で送信を止める。
5. **`sent` は受理であり到達保証でない**: 送信後の世界（到達/バウンス/返信/訂正）は範囲外。
6. **鍵は Keychain**: SA鍵の平文化・ログ出力を禁止。永続ログに本文全文を残さない。

## Gotchas

1. 現状 `メッセージ対象=✅` の2件は本文コードブロック未記入（空）。送信には `{{}}` 入り本文の記入が必要（0通なら G2 で記入を促し終了）。
2. `GET /billings` ではなく本スキルは Notion REST。`databases.gmail-send-log.db_id` 未設定なら live-send は必ず中断（dry-run は第1段まで可）。
3. `unknown_needs_reconcile` と `sent` は自動再送しない。部分再開は `reserved` の未送信分のみ。
4. quota 枯渇兆候で安全停止（1通ごと最低1秒待機、429/403 は指数バックオフ最大3回）。残件は `reserved` のまま次回再開。

## Additional Resources

- `references/spec-detail.md` — 列マッピング全表・依存実体トレーサビリティ表（§13）・状態遷移図・件数式2段の詳細・本文コードブロック抽出規則
- `plugins/notion-gmail-send/lib/` — 実行コード（`notion_client.py` / `render_substitute.py` / `message_assemble.py` / `plan_build.py` / `gmail_client.py` / `idempotent_log.py` / `preflight.py` / `send_guard.py`）
- `doc/run-notion-gmail-send-仕様と検証メモ.md` — 実装 SSOT（本スキルの source）
- `doc/GCP-Gmail送信設定手順.md` — 認証基盤（Gmail API 有効化 + DWD スコープ）設定手順

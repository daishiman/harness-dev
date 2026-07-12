# elegant-review Phase3 改善実行レポート: notion-gmail-send (plugin scope)

- **run-id**: 20260625T165406
- **phase**: Phase 3（改善実行・write可）
- **scope**: plugin
- **収束**: converged（iteration 1）
- **4条件**: C1/C2/C3/C4 全 PASS

## 結論サマリ

| 条件 | 判定 | 根拠 |
|------|------|------|
| C1 矛盾なし | PASS | 除外挙動(normalize_cc)・content_hash・SEND_URL を不変に保ちテストで担保。doc の口語と実装語をF2用語表/各注記で一致 |
| C2 漏れなし | PASS | F7(schema層検査)とF1(cc除外可視化)の実体欠落を埋め+8テスト。F10は既存テストで充足を裏取り |
| C3 整合性あり | PASS | 秘書CC任意/created_time一次キー/送信対象false扱いを doc に明文化し contract_sync で drift 固定 |
| C4 依存関係整合 | PASS | lint-dependency-direction 0違反。lib本体ロジック(normalize_cc/_normalize/SEND_URL)無変更で依存変化なし。pytest 129 passed 回帰0 |

## 二段確認（最優先・read-only Notion API）

analyst の「実装済み」報告は静的コード読解であり、実DB照合で裏取りを試みた。

- **試行**: `.notion-config.json.example` の DB2 id (`38807a0cd18c80e9b47cd9ceb81463db`) と Keychain `notion-api-key.xl-skills`(存在確認・値マスク)で `GET /v1/databases/{DB2}` を read-only 取得。
- **結果**: **skip（接続不能）**。サンドボックスが api.notion.com への外部接続を拒否(curl 権限 denied)。**捏造せず skip**。
- **代替担保**: F7 のコード堅牢化により、実行時に `audit_recipient_db_schema` が DB2 schema を取得し「部署名」残存を `deprecated_property` として機械検出する。静的照合への依存を実行時機構へ置換した。
- **運用者フォローアップ**: ネットワーク許可下で `python3 skills/run-notion-gmail-source-audit/scripts/audit_mail_dbs.py --json` を実行し、(a)`schema_properties` に「部署名」が無い、(b)「メール（プロ人材）」「メール（cc秘書）」「メールを送らない」「送信対象」が全角括弧含め厳密一致で存在、(c)`notion_client.py:36-42` の `P_*` 定数と一致、を確認できる。

## Phase3 改善内容（実体を伴う・+178行/10ファイル）

| 種別 | finding | ファイル | 内容 |
|------|---------|----------|------|
| 機構追加 | F7 | lib/mail_db_audit.py, audit_mail_dbs.py | `audit_recipient_db_schema()` 新設。DB2 schema 層で廃止列「部署名」を `deprecated_property` 検出(本文トークン層とは別)。JSON 出力に `schema_properties` 追加 |
| 可視化 | F1 | lib/message_assemble.py, build_plan.py | 観測専用純関数 `cc_suppressed_by_to()` を追加し、秘書addr==To でCC除外された事実を dry-run プレビューに `cc_suppressed_due_to_to_overlap` 警告として表示。**除外挙動は不変** |
| doc | F2/F4/F5/F8 | doc SSOT, spec-detail.md, README.md | 秘書CC任意/秘書==To除外/created_time一次キー/送信対象false扱い/content_hash用語注記/用語対応表(spec §8) |
| test | F7/F1/F2 | test_notion_mock.py, test_recipient_resolution.py, test_contract_sync.py | 新規8テスト |

- **lib 本体ロジック(`normalize_cc` / `_normalize` / `SEND_URL`)は1行も変えていない**。Goodhart の罠を避け、観測・検査・doc の層だけを非侵襲に足した。
- **content_hash 不変性をテストで明示担保**（`test_build_plan_records_cc_suppressed_warning_and_hash_unaffected`）: 観測メタ追加が hash を変えないことを assert。
- **F10 は既存テストで充足済み**と裏取りし重複追加せず（`test_send_uses_gmail_messages_send_endpoint_for_sender_sent_history`）。

## 検証結果

- `python3 -m pytest tests/ -q` → **129 passed exit 0**（新規8件含む・回帰0）
- `lint-skill-tree`（4 skill）→ 全 ok
- `lint-dependency-direction` → 0 cycles / 0 violations
- `py_compile` + lib import smoke → OK

## 4条件 最終 verdict 根拠

- **C1 矛盾なし**: doc の口語(「上位ID＝新しいもの」「必ずCC」)と実装(created_time一次キー/秘書空はCC無し)の解釈ズレを注記で解消。除外・hash・URL の不変を維持し新旧矛盾なし。
- **C2 漏れなし**: 要件1(d)の schema 層検証が欠落していた穴(F7)、CC除外の沈黙(F1)を実装で塞いだ。F10 は既存で充足。
- **C3 整合性あり**: 散文の doc 明文化を contract_sync テストで「監視される契約」に昇格させ、doc⇔実装の drift を機械検出可能化。
- **C4 依存関係整合**: lib 本体無変更で依存グラフ不変。live-send(send_campaign)は新キーを参照しない(to_list/cc_list/content_hash再計算のみ)ため経路非破壊。

## 残 deferred

1. 二段確認(実DB照合)はネットワーク制約で未実施。実行時 audit 機構で代替担保済み。運用者の audit 実行で最終確認可能。
2. plugin 全体が git untracked。コミットはユーザー承認待ち。
3. secrets/notion_config/setup_doctor の低 in-process カバレッジは subprocess 計測でない既知事項(今回変更外)。

## 独立承認者（approver）が確認すべき点

1. `lib/message_assemble.py` の `normalize_cc`(SSOT 除外ロジック)が **無変更**であること（`git diff` で `normalize_cc` 関数本体にハンクが無い）。`cc_suppressed_by_to` は新規追加の観測専用純関数。
2. `lib/plan_build.py:_normalize` が **無変更**で、`build_plan` が unit に足した `cc_suppressed_due_to_to_overlap` を `_normalize` が拾わない（= content_hash 不変）こと。`test_build_plan_records_cc_suppressed_warning_and_hash_unaffected` が反証可能な形でこれを assert。
3. `gmail_client.py:SEND_URL`(`users/me/messages/send`) が **無変更**で、F10 は新規テストを足していない（既存 `test_gmail_client.py:59` で充足）こと＝重複でない。
4. F7 の `audit_recipient_db_schema` が **read-only**(`retrieve_database` GET のみ・write-scope:none)で、Notion へ書き込まないこと。
5. doc 明文化が **実装の現挙動の記述**であって挙動変更を伴わないこと（F2/F4/F5/F8）。特に「送信対象=false=dry-run母集団外/承認後false化のみsend_suppressed」が `resolve_recipients` 処理順1(continue・無記録)と send_campaign の C-1 再検証(`send_suppressed`)に一致。
6. 二段確認 skip が捏造でなく接続不能の正直報告であること、F7 が実行時機構で代替担保していること。

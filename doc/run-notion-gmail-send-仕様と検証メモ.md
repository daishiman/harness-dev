# run-notion-gmail-send 実装仕様書

> 状態: **実装仕様 確定版（elegant-review 30思考法 / 4条件 再適用済み）**
> 用途: 本書は `harness-creator`（`/run-skill-create` → `run-build-skill`）が `run-notion-gmail-send` スキルプラグインを実装するための**自己完結した唯一の入力仕様**である。
> 正本宣言: 実装の SSOT は**本書**。`eval-log/skill-brief.json` は本書から導出した機械入力で、**v2 で本書に整合済み**（§15 マッピング適用済み・harness-creator はこれをそのまま消費可）。`eval-log/elegant-review/findings.json` は**レビュー反映ログ**であり仕様正本ではない。
> 更新日: 2026-06-24 / レビュー: 思考リセット→30思考法並列分析→4条件検証を完了（§14 参照）

---

## 1. 目的と非目的

### 目的
Notion の2つの DB を入力に、`メッセージ対象=✅ かつ 本文非空` の本文を `送信対象=✅ かつ メールを送らない☐ かつ メール（プロ人材）非空` の宛先行へ、`{{}}` トークンを差し込み置換のうえ **承認済み送信計画（plan）に含まれる送信単位だけを Gmail API で送信**し、各結果を Notion 送信ログDBに**事前予約つきで冪等記録**するスキル（`run-notion-gmail-send`）。

### 非目的（boundary・範囲外）
- 本文テンプレートの作成・宛先データのメンテナンス
- GCP / DWD（ドメイン全体の委任）の**設定作業**（→ 未設定検知時は送信せず fail-closed 中断し `doc/GCP-Gmail送信設定手順.md` へ誘導。§10-G1）
- 添付ファイル送信・HTML リッチ整形
- **送信後の世界**（到達確認 / バウンス処理 / 返信受信 / 訂正の追送）。`status=sent` は **Gmail API が受理した**ことを意味し、**受信者への到達を保証しない**。

---

## 2. 中心設計原則（不可逆送信の安全）

本スキルの中核は「**不可逆な外部副作用（メール送信）を、承認の所在（既定=Notionチェック✅＋preview 要約への単一確認 / 無人cron=Notionチェック✅ / 厳格対話=APPROVE）・送信前の機械的安全層・事前予約つき冪等ログで安全化する**」こと。三者は役割が異なり、混同してはならない。

| 安全装置 | 守る対象 | 効く局面 | 効かない局面 |
|---|---|---|---|
| **承認済み plan / fresh rebuild**（`plan_hash` + `count` + `first_to`、厳格対話のみ確認語） | plan.json 改竄・件数偽装・古い plan 使い回し（**実効検出は plan.json が非信頼アーティファクトとなる厳格対話モードのみ**。非対話＝既定confirm／無人cron では plan を送信直前に self-derive するため plan_hash／件数／content_hash 照合は恒真＝compose バグ検出用の defense-in-depth） | 承認後の全送信 | Notion 読取後から送信直前までの意味的なデータ変更 |
| **承認の所在**（既定=Notion `送信対象=✅`＋preview 要約への単一確認 / 無人cron=Notion `送信対象=✅` / 厳格対話=dry-run 全件プレビュー目視 → APPROVE） | 誰に送るかの意思をデータ層（`送信対象=✅`）で固定し、既定は preview 要約への単一確認・厳格対話は APPROVE 文字列で送信を発火する | 全送信（初回含む） | 内容が意味的に正しいことの保証（既定は preview 要約＋source-audit/canary、無人cron は Notion 整備＋source-audit fail-closed、厳格対話は目視で緩和） |
| **事前予約つき冪等ログ**（reserved → sending → sent / unknown） | **再実行時の同一Notionページ単位の二重送信**と送信成功後ログ失敗 | 2回目以降の再実行・障害復旧 | **初回の内容妥当性**、別Notionページとして作り直した同一メールアドレスへの重複 |

> ⚠️ 因果ループ警告（設計に明記すること）: 「冪等があるから安全」は**初回送信の内容妥当性には成立しない**。初回内容は既定では preview 要約への単一確認＋source-audit/canary、無人cron では Notion のチェック整備＋source-audit fail-closed、厳格対話では目視承認で緩和する。承認後の内容固定は `plan_hash` と送信前の決定論再計算、再実行安全は事前予約つき冪等ログが担保する。

### 送信方式の確定（ユーザー承認済み）
**既定は最小確認1回**。引数なしで `send-campaign.py` を実行すると preview（送信せず、件数／先頭To／本文先頭／抑制・skip 内訳／⚠️警告の要約 ＋ `CONFIRM_TOKEN=plan_hash` を出し **exit 10**）→ 人間の単一の送信可否確認 → `--confirm-token <plan_hash>` で再実行すると、送信直前に最新 Notion から新鮮 plan を再構築し、その `plan_hash` がトークンと一致する時のみ送信する（preview 後に Notion が変化して不一致なら **exit 11** で再 preview を促す）。重い `APPROVE`＋確認語の読解強制を、軽量な単一確認へ圧縮した（ユーザー選択＝件数に関わらず常に1回確認）。**無人 cron 用は `--auto-approve`／`--yes`** で端末確認なしの確認0（source-audit high 残存で fail-closed）。慎重運用の**厳格対話（後方互換）**は dry-run 全件プレビュー + `plan.json` 生成 → 人間が内容を目視して `APPROVE <plan_hash> <count> <first_to> <確認語>` を入力 → 一括本送信。承認の所在は Notion の `送信対象=✅`（データ層）。少数検品用の **canary 段階送信は `--canary N`（`send-campaign.py`／dry-run とも）で opt-in 採用済み（据置・既定 ON ではない）**。既定下書きモード（draft-only）は引き続き未採用。

---

## 3. 入力: Notion 2DB の実構造と列マッピング

REST API（Keychain `notion-api-key.xl-skills`）で取得済みの実構造。Notion MCP は 404（未共有）のため REST 直叩きで扱う。

### DB1「メール本文_DB」(`38807a0cd18c80f1ae82f01a90ff5aa2`)
| プロパティ | 型 | 役割 | メール組立での写像 |
|---|---|---|---|
| 件名 | title | メール件名（`{{}}` 置換対象） | Subject |
| メールの送り主 | email | From（impersonate 対象） | **From** |
| CC | email（カンマ区切りで複数可） | CC | **CC**（カンマ分割し1通に並列） |
| メッセージ対象 | checkbox | ✅ かつ本文非空の行だけ送信 | 送信フィルタ |
| （ページ本文） | コードブロック | メール本文テンプレ（`{{}}` 置換対象） | Body |

### DB2「メール送信先_DB」(`38807a0cd18c80e9b47cd9ceb81463db`)
> 2026-06-25 改修: 部署名を廃止し、宛先を「プロ人材(To)」「秘書(CC)」の2系統に分離。送信抑制チェックボックスを追加。プロパティ名は厳密一致（全角括弧・スペース無）。

| プロパティ(厳密名) | 型 | 役割 | メール組立での写像 |
|---|---|---|---|
| `担当者様名` | title | 差し込み＋宛名 | `{{担当者様名}}` |
| `会社名` | rich_text | 差し込み | `{{会社名}}` |
| `メール（プロ人材）` | email（カンマ区切り可） | 送信先(プロ人材) | **To**（カンマ分割し1通に並列） |
| `メール（cc秘書）` | email（カンマ区切り可） | CC(秘書) | **CC**（本文DB CC と結合・To除外・重複排除） |
| `メールを送らない` | checkbox | ✅ なら**送信対象より優先**で抑制 | 抑制フィルタ（最優先） |
| `送信対象` | checkbox | ✅ かつ送らない☐ かつ プロ人材メール非空の人だけ宛先 | 宛先フィルタ |

> `部署名` は廃止（D1）。Notion 上のプロパティも削除済み。本文に `{{部署名}}` が残っても unresolved_token で fail-closed され送信されない（安全）。

### 取得時の確定事項
- From は `@shonai.inc`（Workspace ドメイン）。固有値は config へ退避し、承認状況は実行時に動的検証する（§10-G1, §13）。
- **現状 `メッセージ対象=✅` の2件は本文コードブロックが未記入（空）**。本仕様では空本文は送信対象外（§4 の本文 true 定義）。送信を行うには事前に `{{}}` トークン入り本文の記入が必要（preflight で0通なら送信せず案内。§10-G2）。

### ページ本文コードブロック抽出規則
- DB1 ページ本文は Notion blocks API で子ブロックを pagination しながら取得する。
- 本文テンプレートは **最初の非空 `code` block** を採用する。複数の非空 `code` block がある場合は `skipped_validation(reason=multiple_body_code_blocks)` とし、暗黙連結しない。
- 空白のみの `code` block は空本文として扱う。`code` block 以外の paragraph 等は本文に使わない。
- ページ本文取得失敗、子ブロック未取得、Notion API pagination 未完了は fail-closed（送信せず `error` または `skipped_validation(reason=body_fetch_failed)`）。

---

## 4. 送信単位の生成規則（直積と件数式）

### フィルタ定義（C1 矛盾解消の要）
- **本文 true** ≡ `メッセージ対象=true` **かつ** `本文コードブロックが非空`
- **宛先 true** ≡ `送信対象=true` **かつ** `メールを送らない=false` **かつ** `メール（プロ人材）が非空`
- 上記を満たさない行は送信せず、原因に応じて `skipped_validation` / `suppressed` / `duplicate_dropped` として計上・報告する。

> **`送信対象=false` の宛先の扱い（F8）**: dry-run の段階では `送信対象=false` は **母集団外**として一切計上しない（`resolve_recipients` の処理順1で `continue`・記録しない）。`メールを送らない=true`（`suppressed`）とは異なり、ログにも plan にも残さない。例外は **承認後に Notion 側で `送信対象=☐` または `メールを送らない=✅` へ変更された宛先**で、この場合のみ live-send の送信時 suppress 再検証（C-1）が検出し、送信ログDB へ `skipped_validation(reason=send_suppressed)` として記録する（承認時には送信予定だった証跡を残すため）。要約すると **dry-run で false の行=無記録、承認後に false 化された行=`send_suppressed` で記録**。

### 宛先解決の処理順（順序が安全の要・D3/D4）
`lib/notion_client.resolve_recipients()`（純関数）が次の順で解決する:
1. `送信対象=false` は母集団外（計上しない）
2. `メールを送らない=true` は**抑制**（送信対象より最優先・`suppressed`）
3. プロ人材メール空は `skipped(invalid_to)`
4. プロ人材メール重複は **新しい `created_time` を1件だけ残す**（他は `duplicate_dropped`）。tie は `page_id` 降順で決定論。正規化は `NFKC+strip+lower`（プラスエイリアス/ドット除去はしない＝別人誤集約防止）。会社名違いの同一プロ人材も同一人物として集約（要件）。秘書メールでは dedup しない。

> 2 を 4 より**前**に置くことで「送らない行が最新代表に選ばれ、本来送れる古い行を巻き込む」事故を防ぐ。
> dedup/suppress は dry-run（`build_plan.py`）で確定し plan_hash に凍結する。承認後に Notion 側で `メールを送らない=✅`/`送信対象=☐` へ変えられた宛先への追い越し送信は、live-send（`send_campaign.py`）が plan の宛先 page を再取得して差し引く（subtract-only・C-1。承認件数を超えて送ることは決してない）。

### 直積
送信単位 = （本文 true の全行）×（宛先 true で解決した全行）。各単位を1通として送信する。同一プロ人材へは（dedup後の1宛先行 × 本文数）ぶんの通数が出る（本文が複数あるのは設計どおり）。

### plan と content hash
- `campaign_id`: 実行ごとに生成する識別子（例: `YYYYMMDD-HHMMSS-<shortuuid>`）。同一キャンペーン内の全送信単位に付与する。
- `content_hash`: 置換後の Subject / Body / From / To / CC / 本文page_id / 宛先page_id を正規化して SHA-256 で算出する。

  > **「recipient list」の用語注記（F2）**: 旧記述の「recipient list」は独立フィールドではなく、上記の **To（`to`・sorted）／CC（`cc`・sorted）／宛先page_id（`recipient_page_id`）** の総称である。実装 `lib/plan_build._normalize` が hash 対象とするキーは `subject / body / from / to(sorted) / cc(sorted) / body_page_id / recipient_page_id` の7つで固定。`build_plan` がこの後追加する `cc_suppressed_due_to_to_overlap` 等の観測メタは `_normalize` が拾わないため **content_hash に影響しない**（決定論を維持）。
- `plan_hash`: dry-run で生成した全送信単位（順序安定、正規化済み）の SHA-256。live-send は `--approved-plan-hash` が dry-run の `plan_hash` と一致しない限り Gmail API を呼ばない。
- 冪等キーは `{本文page_id}:{宛先page_id}:{content_hash}`。`campaign_id` は含めず、別実行でも同一本文ページ×同一宛先ページ×同一内容の二重送信を止める。宛先を別Notionページとして作り直した場合は別単位。意図的再送時のみ `--allow-resend` が campaign suffix を付ける。同一宛先行のメール列に複数アドレスがある場合も、その宛先行に対する1送信単位として扱う。
- `plan.json` には本文全文を含めるが、保存場所はローカル作業領域のみ（git 管理外推奨）。Notion ログには本文全文を保存せず `content_hash` と件名を保存する。

### 件数式（2段に分離 — C4 依存整合）
| 段 | 式 | 依存 |
|---|---|---|
| 第1段: 計画送信単位 | `本文true件数 × 宛先true件数` | **DB不要**（dry-run はここまで常に算出可） |
| 第2段: 正味送信予定 | `計画送信単位 − sent済み件数` | **送信ログDB ID 確定が前提**（preflight 通過時のみ評価） |

> dry-run は送信ログDB が未確定でも第1段まで提示する。第2段（冪等差し引き）は preflight G2 通過後にのみ算出する。

---

## 5. 差し込み置換仕様

- トークン表記: **`{{会社名}}` `{{担当者様名}}`**（二重波括弧）。`{{部署名}}` は廃止（D1）。
- 置換対象: **本文コードブロック および 件名（title）の両方**（契約・責務でスコープ一致させること）。
- 置換元: 各宛先（DB2）の `会社名` / `担当者様名`。
- 廃止トークン: `{{部署名}}` が本文に残っていても置換元が無いため unresolved_token で送信が止まる（安全）。監査（`mail_db_audit`）は `deprecated_token` として「削除推奨」を案内する（typo の `unknown_token` とは区別）。
- **未置換トークン残存は fail-closed**: 置換後に `{{...}}` が残る送信単位は `skipped_validation` とし**送信しない**（warning 止まりにせず送信を止める）。置換元が空値の場合も同様に検出・報告する。
- サニタイズ: 差し込み値はヘッダインジェクション防止のため改行・制御文字を除去/拒否する。

---

## 6. メッセージ組立仕様（message-assemble）

> 本節は**最重要 build ブロッカーの解消**（旧仕様で From/To/CC のDB列→ヘッダ写像と組立工程がどの責務にも割当たっていなかった）。独立した責務 `message-assemble` として明示する。

- **From** = DB1「メールの送り主」（impersonate 対象アドレス）
- **To** = DB2「メール（プロ人材）」（カンマ区切りを分割し、1通の To 欄に複数アドレスを並列）。同一宛先行内の To 受信者は互いのアドレスを見られるため dry-run で `multi_to_visible=true` として警告し、承認 echo 対象に含める。
- **CC** = DB1「CC」 **＋** DB2「メール（cc秘書）」を結合（プロ人材と秘書の両方へ送る。秘書は CC）。結合は dry-run（`build_plan._combine_cc`）で1回だけ確定し plan.json に焼く。`message_assemble.normalize_cc` が **To と重複する CC を除外**し、**CC内の重複を排除**する（大小無視）。content_hash は最終 cc_list（sorted）を反映し決定論を維持。live-send は plan の cc_list を再 assemble するのみで再結合しない。
  - **秘書 CC は必須ではない（F2/F5）**: DB2「メール（cc秘書）」が空の宛先は、**CC無しでプロ人材（To）のみへ送信**する。「秘書は必ずCC」という規定は **秘書アドレスが存在する宛先に限った規定**であり、秘書欄が空でも送信は止まらない（CC を伴わない正常送信）。
  - **秘書 addr == プロ人材 To（同一アドレス）は To 優先で CC 除外（F1/F8）**: 秘書欄がプロ人材 To と同一アドレスの場合、`normalize_cc` が安全側で CC から除外する（同一人物を To と CC に二重に載せて1人へ2通相当の重複可視を生むのを防ぐ）。「必ずCC」は **別アドレスの秘書**に適用される。除外された事実は dry-run で `cc_suppressed_due_to_to_overlap` 警告として可視化する（`build_plan` プレビュー・`message_assemble.cc_suppressed_by_to`）が、**除外挙動自体は変更しない**（To で確実に届くため未達ではない）。
- **Subject** = DB1「件名」（置換後）
- **Body** = DB1 本文コードブロック（置換後）
- 組立形式: RFC 822 / MIME 準拠。Gmail API へは base64url エンコードした raw message として渡す。
- メールアドレス形式を検証し、不正アドレスを含む送信単位は `skipped_validation`。
- Gmail impersonation は `users.messages.send(userId="me")` で impersonated subject として行う。**送信メールは送信者（impersonate 対象）の「送信済み」に自動格納される**ため、送信履歴は送信者メールボックスに残る（D6）。From は impersonated user と一致、または Gmail の `sendAs` alias として検証済みであること。未検証 alias は G1 で fail-closed。

---

## 7. アーキテクチャ（二層分離）

決定論的に確定できる処理は script、LLM 判断・人間承認・例外介入は run-skill が担う。

| 層 | 担当 | 内容 |
|---|---|---|
| **run-skill（オーケストレータ／ラッパ）** | prompt 要 | preflight 検証の統括、既定confirm 送信の起動（preview 要約提示→人間の単一確認→`--confirm-token` 再実行）、無人 cron（`--auto-approve`）の起動、厳格対話時のdry-run提示・`APPROVE`承認文字列受領・送信前二段確認の起動、例外介入、最終レポート生成 |
| **決定論的本体（script）** | prompt 不要 | Notion 取得・抽出、差し込み置換、メッセージ組立、`plan.json` 生成、script 内 `send_guard()`、Gmail 個別送信、事前予約つき冪等ログ |

### 責務一覧（skill-brief.responsibilities へ反映）
| id | desc | prompt_required |
|---|---|---|
| `orchestrate` | goal-seek 制御・preflight 統括・送信可否判断・既定confirm 送信起動（preview→単一確認→`--confirm-token`）・無人 cron 起動・厳格対話時の`APPROVE <plan_hash> <count> <first_to> <確認語>`形式の人間承認受領・最終レポート生成 | true |
| `preflight-verify` | 認証/ドメイン/依存実体/本文充足を fail-closed 検証（§10）。送信前二段確認（context:fork で宛先・件数・plan_hash・未置換トークン残存を再検査） | true |
| `notion-fetch` | DB1/DB2 を REST 取得し本文 true / 宛先 true を抽出（script） | false |
| `render-substitute` | 本文コードブロック**および件名**の `{{}}` トークンを宛先DB値で置換、未置換 fail-closed（script） | false |
| `message-assemble` | From/To/CC のDB列写像・カンマ分割・RFC822/MIME 組立（script） | false |
| `plan-build` | 送信単位を正規化し `campaign_id` / `content_hash` / `plan_hash` を生成、dry-run preview と `plan.json` を出力（script） | false |
| `gmail-send` | Keychain 鍵で impersonate し、script 内 `send_guard(approved_plan_hash, plan_hash, reserved_log_id)` 通過後だけ Gmail API で1通ずつ送信、quota/レート制御（script） | false |
| `idempotent-log` | Notion 送信ログDBへ冪等キーで reserved 事前予約→sending→sent/unknown を更新・既送照合・部分再開の起点化（script） | false |

---

## 8. 実行フロー

```
1. dry-run preflight（Notion取得・本文true/宛先true・置換・本文抽出を fail-closed 検証）
2. 送信単位生成（§4 直積・本文true×宛先true）
3. 差し込み置換（§5）＋メッセージ組立（§6）
4. `plan.json` 生成（`campaign_id` / `content_hash` / `plan_hash`）。対話モードでは dry-run 全件プレビュー提示
5. live-send preflight（§10 G1/G2/G3: 認証・送信ログDB・From/sendAs・plan_hash 一致）
6. 承認ゲート（既定confirm: 引数なし preview で要約＋`CONFIRM_TOKEN=plan_hash` を出し送信せず **exit 10** → 人間の単一確認 → `--confirm-token <plan_hash>` 再実行で新鮮 plan の plan_hash 一致時のみ送信、不一致は **exit 11** で再 preview / 無人cron: `--auto-approve`／`--yes` で Notion `送信対象=✅` を承認として plan から self-derive（source-audit high で fail-closed） / 厳格対話: `APPROVE <plan_hash> <count> <first_to> <確認語>` 完全一致）
7. 送信前二段確認（対話モードのみ context:fork：宛先/件数/plan_hash/未置換トークン残存を再検査、fail-closed）
8. 各送信単位を Notion 送信ログDBへ `reserved` 事前予約（既存 sent/reserved/unknown は自動再送しない）
9. script 内 `send_guard()` 通過後に一括本送信（Gmail API・1通ずつ・quota安全停止/レート制御）
10. Gmail 受理後、同じログ行を `sent` に更新。更新失敗時はローカル journal に `send_success_log_failed` を残し、次回は `unknown_needs_reconcile` 扱いで自動再送しない
11. 日本語送信レポート（送信/スキップ/失敗/要照合の件数と内訳・エラー時の次アクション）
```

---

## 9. 冪等と状態

- **冪等キー**: `{本文page_id}:{宛先page_id}:{content_hash}`。送信ログDBの一意キーとして検索し、同一キーが `sent` なら再送しない。`campaign_id` は含めず、意図的再送時のみ `--allow-resend` が campaign suffix を付ける。別Notionページとして作り直した宛先は別単位として扱う。
- **実行モード**: `dry-run` / `live-send`。dry-run は Gmail API を呼ばない。
- **送信状態 enum（副作用段階）**: `planned` / `reserved` / `sending` / `sent` / `skipped_idempotent` / `skipped_validation` / `error` / `unknown_needs_reconcile`
  - `planned` = dry-run plan に含まれるが送信予約前
  - `reserved` = live-send 前に Notion ログへ事前予約済み。自動再送禁止のロック状態
  - `sending` = Gmail API 呼び出し直前から応答処理中
  - `sent` = Gmail API が受理し messageId をログに保存済み（到達保証ではない）
  - `skipped_idempotent` = 冪等ログに sent 済みで再送回避
  - `skipped_validation` = 本文空 / 宛先欠落 / 未置換トークン残存 / 不正アドレス等で送信前に除外
  - `error` = Gmail API が失敗し、未送信と判断できる
  - `unknown_needs_reconcile` = Gmail API 成功後に Notion 更新失敗、または `sending` で中断し送信成否が不明。**自動再送せず手動照合を要求**
- **reason code**: `skipped_validation` / `error` / `unknown_needs_reconcile` には `empty_body` / `multiple_body_code_blocks` / `body_fetch_failed` / `invalid_to` / `invalid_cc` / `unresolved_token` / `unsafe_header` / `duplicate_recipient` / `from_alias_unverified` / `quota_stopped` / `send_success_log_failed` / `send_suppressed`（送信時 suppress 再検証で除外・C-1） などの機械可読理由を必須にする。

### 送信ログDB schema
送信ログDBは `.notion-config.json` の `databases.gmail-send-log.db_id` で解決する。

| プロパティ | 型 | 必須 | 用途 |
|---|---|---|---|
| 冪等キー | title | yes | `{本文page_id}:{宛先page_id}:{content_hash}`。検索キー（意図的再送時のみ campaign suffix） |
| campaign_id | rich_text | yes | 実行単位 |
| plan_hash | rich_text | yes | 承認済み plan の照合 |
| content_hash | rich_text | yes | 本文・件名・宛先の改変検知 |
| status | select | yes | 上記 enum |
| reason_code | select/rich_text | no | validation / error 理由 |
| 本文page_id | rich_text | yes | DB1 ページ |
| 宛先page_id | rich_text | yes | DB2 ページ |
| From | email/rich_text | yes | 送信元 |
| To | rich_text | yes | カンマ分割後の配列を JSON 文字列で保存 |
| CC | rich_text | no | カンマ分割後の配列を JSON 文字列で保存 |
| 件名 | rich_text | yes | 置換後件名 |
| messageId | rich_text | no | Gmail API 受理後に保存 |
| reserved_at / sending_at / sent_at | date | no | 状態遷移時刻 |
| error | rich_text | no | 秘密値を含まない要約 |

同一冪等キーのログ行が複数ある場合は fail-closed で `duplicate_log_key` とし、自動送信しない。Notion API は一意制約を提供しないため、送信前に検索→0件なら create reserved、1件なら状態判定、2件以上なら中断する。

---

## 10. preflight gate（fail-closed・依存実体の検証）

未確定の外部依存を**契約の前提に静的に埋め込まない**。build は通し、**実行時に preflight と script 内 guard が fail-closed で送信を止める**ことで「build 不能で詰む」ことなく「誤送信もしない」を両立する。

dry-run preflight と live-send preflight は分離する。dry-run は送信ログDBなしでも第1段件数・plan_hash まで作成できるが、live-send は送信ログDBなしでは必ず中断する。

| ゲート | 検証内容 | 未充足時の挙動 |
|---|---|---|
| **G0 dry-run** | Notion 2DB 読取、本文コードブロック抽出、置換、plan_hash 算出。Gmail/ログDBは不要 | 送信せず dry-run レポートだけ返す。本文0通は本文記入を促す |
| **G1 認証** | Keychain SA鍵を `security` で列挙確認し、JSON を安全にロードできることを検証。`shonai.inc` の DWD + `gmail.send` 承認、From の `sendAs` alias を**実APIで動的検証**（doctor --probe 型） | 送信せず中断。`doc/GCP-Gmail送信設定手順.md` へ誘導 |
| **G2 依存実体** | 送信ログDB ID が `.notion-config.json` の `databases.gmail-send-log.db_id` で解決可能か。送信可能な本文が1通以上あるか（本文 true ≥ 1） | DB ID 不在は db-setup へ差し戻し。本文0通は本文記入を促し送信せず終了 |
| **G3 送信直前** | `approved_plan_hash == plan_hash`、承認 count/first_to 一致、未置換 `{{}}` トークン残存・宛先件数・From 整合を機械検査（script 内 `send_guard()`。context:fork 二段確認は対話モードのみ） | 該当送信単位を `skipped_validation`、全体不整合なら中断 |

### hook と script guard の責務境界
- `hook_events: ["PreToolUse"]` は run-skill が外部 tool 経由で Gmail 送信を呼ぶ場合の補助防御である。
- 決定論的 script 内の Gmail API 呼び出しは Codex hook では捕捉できない可能性があるため、**安全の正本は script 内 `send_guard()`** とする。
- `send_guard()` は `approved_plan_hash`、`plan_hash`、承認件数、先頭 To、reserved ログ行ID、未置換トークン検査結果、From/sendAs 検証結果が全て一致しない限り Gmail API 関数へ到達させない。

---

## 11. 耐障害

- **quota / レート**: Gmail API の送信レート制御。quota 枯渇兆候を検知したら**安全停止**（途中まで送信済みは冪等ログに記録され、再実行で残りを継続）。
- **レート既定値**: 1通送信ごとに最低1秒待機。429/403 rateLimit/quota 系は指数バックオフ（最大3回、初期2秒、上限60秒）。3回失敗または quota 枯渇判定で安全停止し、残件は `reserved` のまま次回再開対象にする。
- **部分再開**: 送信途中の失敗・中断は、冪等ログを起点に**未送信と判断できる分のみ**再実行で継続する。`sent` と `unknown_needs_reconcile` は自動再送しない。
- **送信成功後ログ失敗**: Gmail API が messageId を返した後に Notion 更新へ失敗した場合、ローカル journal に冪等キー・messageId・時刻・plan_hash を保存し、Notion には次回 `unknown_needs_reconcile` として復旧要求を出す。自動再送は禁止。
- **重複検知**: 同一プロ人材メールアドレスが複数 page に存在する場合は最新 `created_time` の1件だけを送信対象に残し、他は `duplicate_dropped` として報告する（会社名違いでも同一人物への重複送信を防ぐ）。

---

## 12. セキュリティ

- 認証は macOS Keychain の Google SA鍵のみ。鍵の平文化・ログ出力を禁止。
- DWD は「ドメイン内の任意ユーザーを impersonate 可能」な状態のため、impersonate 対象は**指定アドレスに運用で固定**し、鍵管理を厳格化（`doc/GCP-Gmail送信設定手順.md` STEP 12 準拠）。
- PreToolUse hook は補助防御、script 内 `send_guard()` は必須防御。送信前ゲートは指示でなく機構で担保する。
- PII 方針: dry-run preview は画面表示用に本文全文・メールアドレスを含めてよい。永続ログ（Notion送信ログ、eval-log、journal）には本文全文を保存しない。メールアドレスは送信ログDBでは業務上必要な To/CC/From のみ保存し、エラーログでは secret/key を必ず redaction する。

---

## 13. 依存実体トレーサビリティ表（契約↔実体↔確定状態↔gate）

> root cause（契約と依存実体の連結欠如）の解消。各契約条項が消費する未確定実体を、確定方法と未確定時の fail-closed gate に1対1で連結する。

| 契約条項 | 依存実体 | 確定方法 | 未確定時のゲート |
|---|---|---|---|
| 承認済み plan（§4,§8） | `plan.json` / `plan_hash` | dry-run で生成し live-send で hash 照合 | G3: 不一致なら送信中断 |
| 冪等記録（§9） | 送信ログDB ID | `.notion-config.json` の `databases.gmail-send-log.db_id` に焼き込み（db-setup 相当を先行確定） | G2: 不在なら db-setup へ差し戻し |
| 事前予約（§9,§11） | reserved ログ行ID | Gmail API 呼び出し前に Notion create/search | G3: reserved なしなら送信中断 |
| impersonate 送信（§6 From） | Keychain SA鍵 svce/acct | preflight で `security` 列挙確認 | G1: 取得不可なら中断 |
| Gmail 送信（§8-9） | shonai.inc の DWD + gmail.send 承認 + From sendAs alias | 実 API で動的検証 | G1: 未承認なら GCP 手順へ誘導 |
| 送信単位生成（§4） | 本文 true ≥ 1（✅2件の本文記入） | 本文コードブロック記入 | G2: 0通なら記入を促し終了 |

**これらの実体が build 時点で未確定でも、preflight gate と `send_guard()` が fail-closed で吸収するため build は完遂可能。** 実値が揃い、plan が承認され、reserved ログ行が作られるまで1通も送信しない。

---

## 14. build 前チェックリスト（harness-creator へ渡す前）

- [ ] 本書が実装 SSOT であること（findings.json は反映ログ・参照のみ）
- [ ] `message-assemble` 責務が定義されている（最重要 build ブロッカー）
- [ ] `plan-build` 責務が定義され、`campaign_id` / `content_hash` / `plan_hash` が生成される
- [ ] preflight gate（G0/G1/G2/G3）と script 内 `send_guard()` が責務・deterministic_checks に成文化されている
- [ ] 本文 true 定義（メッセージ対象✅ かつ 本文非空）が確定している
- [ ] Notion ページ本文コードブロック抽出規則（最初の非空 code block、複数は fail-closed）が確定している
- [ ] 件名置換が render-substitute の責務スコープに含まれる
- [ ] 未置換トークン残存が fail-closed（warning でなく skip）
- [ ] `hook_events: ["PreToolUse"]` は補助防御、script 内 `send_guard()` が正本防御として宣言されている
- [ ] status enum（planned/reserved/sending/sent/skipped_idempotent/skipped_validation/error/unknown_needs_reconcile）が定義されている
- [ ] reason_code が `skipped_validation` / `error` / `unknown_needs_reconcile` に必須化されている
- [ ] 送信ログDB schema と `.notion-config.json` キー（`databases.gmail-send-log.db_id`）が定義されている
- [ ] 件数式が2段（計画/正味）に分離されている
- [ ] Gmail送信成功後ログ失敗時は `unknown_needs_reconcile` とし、自動再送しない
- [ ] quota安全停止・部分再開・重複検知・PIIログ方針が key_constraints / deterministic_checks にある
- [ ] 送信ログDB ID を `.notion-config.json` で解決する設計になっている

> **再開時の注意**: 旧 `findings.json` の `applied_in_brief: true` は**実際には skill-brief v1 に未反映**だった（記録と実体の乖離）。skill-brief を v2 化する際は、本書を正本として反映し、反映済みフラグは実反映を機械検査してから立てること（誤って「反映済み」と信じて build へ進む二次事故を防ぐ）。

---

## 15. skill-brief（v2）反映マッピング

harness-creator が `eval-log/skill-brief.json` を v2 化する際の主要差分（本書 §に対応）。

- `responsibilities`: §7 の8責務（`preflight-verify` / `message-assemble` / `plan-build` を追加、`render-substitute` に件名を含める、`idempotent-log` を reserved→sent 状態遷移へ拡張）
- `hook_events`: `["PreToolUse"]` を追加。ただし hook は補助防御であり、script 内 `send_guard()` を正本防御にする（§10）
- `deterministic_checks`: 件数式2段（§4）／`plan_hash` 一致（§4,§8）／未置換トークン fail-closed（§5）／reserved なし送信禁止（§9）／`unknown_needs_reconcile` 自動再送禁止（§9,§11）／preflight gate 全充足まで送信フェーズへ進まない（§10）
- `key_constraints`: 「前提とし」を「**preflight と send_guard で検証を強制し未充足なら中断（fail-closed）**」へ書換（§2,§10）。quota安全停止・部分再開・重複検知・PIIログ方針を追加（§11,§12）
- `purpose_background`: 安全根拠を「**承認済み plan ＋ 人間承認ゲート ＋ 事前予約つき冪等ログの三本柱**」に修正（§2）
- `boundary`: 送信後（到達確認/バウンス/返信/訂正追送）を範囲外明示。`sent`=API受理であり到達保証でない（§1,§9）
- `open_questions`: §13 の4実体は open_question のまま放置せず、**preflight 検証項目**として連結（宙吊り禁止）
- `abstraction_variables`: 固有値（shonai.inc 等）を config 退避、`gmail-send-log` DB ID、`campaign_id`、`plan_hash`、横展開余地（任意2DB cross-product merge）をメモ
- `audit_trigger`: `runtime-failure`（外部依存の確定状態が変化、または直積件数が想定オーダー超過時に再監査）
- 反映時の発展的差異: 旧 `findings.json` LS-07 の status enum 5値案（`dryrun_planned` を含む）は、本書 §9 で「実行モード dry-run/live-send ＋ 副作用段階 status enum」を直交させて発展的に解消した（`findings.json` は反映ログのため未更新でよい）。

---

## 16. 決定ログ（経緯・確定事項・却下案）

> 本節は実装には不要な背景記録。実装は §1〜15 を読めば足りる。

### 確定した4決定（ユーザー承認済み）
| # | 論点 | 決定 |
|---|---|---|
| 1 | 差し込みトークン表記 | `{{会社名}}` `{{担当者様名}}`（二重波括弧）。本文＋件名を置換。`{{部署名}}` は 2026-06-25 廃止（D1） |
| 2 | 本文複数×対象者複数 | 直積（全本文 × 全対象者）を1通ずつ |
| 3 | カンマ区切り複数アドレス | 1通に To/CC 複数をまとめる |
| 4 | 二重送信防止（冪等） | 送信ログを Notion 新規DBに事前予約し、重複回避と復旧照合に使う |

### 送信方式の決定（2026-06-24 ユーザー判断）
**現状維持（dry-run 全件承認 → 一括本送信）を採用。** 下書きモード・canary 段階送信は当時は見送り（承認済み挙動を優先）。因果ループ（初回不可逆）は「人間承認ゲートを内容目視必須にする」設計で吸収（§2）。**（推移: canary 段階送信は 2026-06-25 に dry-run 限定方式で採用済み。下記「推移注記」参照。下書きモードは引き続き未採用。）**

### 却下／保留した代替案
- **既定下書きモード**（draft-only）: 不可逆性を構造的に排除できるが、承認済み挙動を変えるため今回見送り。将来オプションとして余地を残す。
- **canary 段階送信**: 当初は初回特例として将来検討可と保留（下記推移注記で採用済み）。
- **完全 script/cron 化（LLM 排除）**: 初回送信の人間ゲートが消えるため初回には不適。定常運用の本送信部分のみ将来検討可。

### 推移注記（決定後の実装反映）
- **2026-06-25**: blind approve 対策（S-F1）として承認文字列に `<確認語>`（nonce）を追加し、**承認は3項→4項 `APPROVE <plan_hash> <count> <first_to> <確認語>`** へ更新。確認語は特定送信単位のプレビュー行末にのみ表示する読解強制（`lib/plan_build.approval_nonce` / `lib/send_guard` で fail-closed 照合）。
- **2026-06-25**: 大量送信の少数検品要件に応えるため **canary 段階送信を採用**。ただし本送信経路（`send_campaign.py`）ではなく **dry-run（`build_plan.py --canary N`／`--limit N`）で plan を安定順先頭 N 件へ限定**し、限定後の `plan_hash`／件数／確認語に承認を束縛する形で実現（不可逆送信の承認契約を崩さない）。`§2 送信方式の確定` を本推移に整合済み。下書きモード（draft-only）は引き続き未採用。

### elegant-review（本書の品質保証）
- 思考リセット → 30思考法（論理構造9 / メタ発想9 / システム戦略12）を**並列 SubAgent**で適用 → 4条件検証、を完了。
- 2026-06-24 の再監査で、3アナリストが独立に追加検出した root cause: (1) hook だけでは script 内 Gmail API 呼び出しを遮断できない、(2) Gmail 送信成功後に Notion ログ更新が失敗すると再実行で二重送信し得る、(3) dry-run 承認が plan と機械照合されていない、(4) Notion 本文抽出・ログDB schema・reason code が不足。
- 本書はこの4点を `plan_hash` 承認、script 内 `send_guard()`、reserved→sent/unknown 状態遷移、本文抽出規則、送信ログDB schema で構造的に解消している。

### 2026-06-25 改修（DB2 構造変更への追従・elegant-review 30思考法/4条件 再適用）
ユーザー要望に基づき DB2「メール送信先_DB」の構造変更へ追従。思考リセット→論理構造9/メタ発想9/システム戦略12 を並列 SubAgent で適用し、実装前に critical を捕捉してから実装した。

| ID | 内容 |
|---|---|
| D1 | **部署名の全廃**: コード定数 `P_DEPT`/`values_for_recipient` の部署名写像・`KNOWN_TOKENS` から除去。Notion の `部署名（削除）` プロパティも削除。`{{部署名}}` 残存は unresolved で fail-closed、監査は `deprecated_token` で案内 |
| D2 | **プロ人材=To / 秘書=CC**: `メール（プロ人材）`→To、`メール（cc秘書）`→CC（本文CC と結合） |
| D3 | **送らない最優先抑制**: `メールを送らない=✅` は `送信対象` より優先で抑制（`suppressed`） |
| D4 | **プロ人材重複排除**: 同一プロ人材は最新 `created_time` の1件のみ送信（`NFKC+strip+lower` 正規化、tie=page_id 降順）。会社名違いも集約。**要件の「上位ID＝新しいもの」は `created_time`（ページ作成時刻）の口語表現であり page_id の大小ではない。dedup の一次キー=`created_time` 降順、tie-break のみ `page_id` 降順**（実装 `lib/notion_client.resolve_recipients` のソートキー `(created_time, page_id)` reverse）。Notion の page_id は時系列単調ではないため、page_id を一次キーにすると古い行を残す誤りになる |
| D5 | **CC正規化**: 本文CC + 秘書CC を結合し To除外・重複排除（`message_assemble.normalize_cc`） |
| D6 | **Sent 履歴**: `users.messages.send` で送信者の「送信済み」に自動格納（コード変更不要・コメント明記） |
| C-1 | **送信時 suppress 再検証**: 承認後に Notion で抑制された宛先への追い越し送信を live-send が再取得して差し引く（subtract-only） |

実装前に3アナリストが独立検出し是正した critical: (1) `created_time` が未抽出で dedup 入力が不在、(2) `assemble` の CC正規化が未実装で設計前提が偽、(3) 抑制→dedup の順序未固定で抑制行が代表に選ばれ生存行を巻き込む事故、(4) dry-run 凍結後の「送らない」追い越し送信。テスト 114 本全通過（dedup/suppress/CC/送信時再検証を含む）。

### 2026-06-26 改修（確認0 auto-send モードの追加・elegant-review 30思考法/4条件 再適用）
ユーザー要望「自動化したい。確認事項（対話的確認）を最大限省略し最悪0に。Notion のチェックを承認とみなしたい」に応え、**承認の所在を「端末の APPROVE 文字列」から「Notion のチェック（データ層）」へ移設**した。思考リセット→論理構造/メタ発想/システム戦略 を並列 SubAgent で適用し、3アナリスト独立収束で設計を確定。**ユーザー選択＝「全件即送信（真の0）」**（canary は opt-in・既定は確認0で全 ✅ 宛先へ即送信）。

| ID | 内容 |
|---|---|
| A1 | **2モード化**: `run-notion-gmail-send` を 既定=引数なしauto（確認0、`--auto-approve` は後方互換）／`--plan`+`--approved-*`（対話・後方互換）の2モードに。auto は端末入力ゼロ。 |
| A2 | **承認 tuple の self-derive**: auto は送信直前に最新 Notion から新鮮 plan を構築し、`approved_plan_hash/count/first_to` を plan から自己導出。人間の APPROVE 入力のみ bypass し、**per-unit guard loop（Class A）は必ず通す**。 |
| A3 | **Class A / Class B 分離**: send_guard 8フィールドを「改竄検出・人間非依存（plan_hash 再計算/件数/先頭To/reserved/未置換/From/content dedup/C-1）＝Class A」と「人間内容承認（approved_* 束縛/nonce 読解強制）＝Class B」に分離。**auto で失う機械安全は0**。Class B（承認の所在）は Notion チェックへ再配置。**nonce は auto モードで撤去**（`enforce_nonce=False`・`actual_nonce=""` で send_guard が照合スキップ）。 |
| A4 | **fresh rebuild**: auto は古い plan.json を使い回さず `lib/plan_compose.compose_plan` で送信直前に最新状態から plan を再構築。dry-run と同一ロジック（`assemble_plan`）を共有し決定論的に一致。送信直前 suppress 再検証は `plan.source.recipient_db` に束縛する。 |
| A5 | **source-audit auto-gate**: auto は送信前に `lib/mail_db_audit.run_full_audit` を実行し **high severity 残存なら1通も送らず fail-closed**（人間目視がない確認0の入口防御）。空本文/未知トークン/To/From不正/空差し込み値を行レベルで阻止。秘書CC不正など medium は該当 unit skip。 |
| A6 | **canary は opt-in**: `--canary N` で安定順先頭 N 件のみ送信。残りは再実行で content dedup（campaign 非依存）が既送を skip して送信。canary 判定は plan_hash でなく content-dedup キー基準（canary slice 後は plan_hash≠full）。 |
| A7 | **二段確認は対話モード限定**: fork verifier は人間 APPROVE 文字列を独立入力に取る装置。auto は入力が無く proposer==approver になるため使わず、決定論セルフチェック（units→plan_hash/件数/content_hash 再計算）が独立検証を担う。 |

正直な明示（残余リスク）: 確認0は「構文 valid だが意味的に誤った本文」を機械では止められない。これは canary（実メール検品）＋ source-audit ＋ Notion `送信対象=✅` の熟慮で緩和する設計トレードオン（ユーザー受容済み）。`送信対象=✅` は永続・帰属・時刻つきで、揮発的な端末 APPROVE 文字列より監査性はむしろ高い。完全無人 cron（通知チャネル/no-LLM 起動）は別リスククラスとして**明示 defer**。テスト 190 本全通過（auto happy/Class A 各層/source-audit gate/canary dedup/subtract-only を含む `test_auto_send.py`・`test_plan_compose.py`）。

### 2026-06-27 elegant-review: 確認0既定 → 最小確認1回既定へ転回

ユーザーが elegant-review の確認で **「件数に関わらず常に1回確認」「canary は opt-in 据置」** を選択したことを受け、2026-06-26 に確定した確認0 auto-send 既定（A1-A7）を**最小確認1回 既定**へ転回した。3アナリスト（論理構造／メタ発想／システム戦略）が独立に収束し、proposer≠approver で確定した（前項までの確認0設計は歴史として保全し、本項で上書きの転回点を記録する）。

| ID | 内容 |
|---|---|
| B1 | **既定を最小確認1回へ**: 引数なしで preview（要約＋`CONFIRM_TOKEN=plan_hash` を出し送信せず **exit 10**）→ 人間の単一の送信可否確認 → `--confirm-token <plan_hash>` で再実行し、送信直前に再構築した新鮮 plan の `plan_hash` がトークン一致時のみ送信。preview 後に Notion が変化して不一致なら **exit 11** で再 preview。重い `APPROVE`＋確認語の読解強制を軽量な単一確認へ圧縮。 |
| B2 | **無人確認0を温存**: `--auto-approve`／`--yes` を cron 用の確認0（端末確認なし）として残置。source-audit high 残存で fail-closed。 |
| B3 | **doc 正直化**: plan_hash／件数／content_hash 照合（旧称 Class A の plan 改竄検出）は**非対話（既定confirm／無人cron）では self-derive ゆえ恒真**（＝compose バグ検出用の defense-in-depth）であり、plan 改竄の実効検出は plan.json が非信頼アーティファクトとなる厳格対話モードのみ。非対話の実効独立検証は source-audit／fresh rebuild／C-1／From 検証／content dedup が担う、と §2 安全三本柱表に明記。 |
| B4 | **source-audit gate 階層化**: 既定 preview は high を ⚠️ 警告として要約に列挙し全停止しない（該当 unit は送信時 per-unit skip）。無人 cron のみ high で fail-closed（人間がループに居る既定＝警告／無人＝fail-closed の原則的非対称）。 |
| B5 | **C-1 を非対話で fail-closed 化**: 送信時 suppress 再検証は非対話3モード共通で効き、承認後に Notion 側で抑制された宛先を subtract-only で差し引く（承認件数を超えて送らない）。 |
| B6 | **F6 二段フラグ見送り**: membership／execute の二段フラグはユーザー判断で不採用。`送信対象=✅` を承認兼トリガとする現設計を維持。 |

承認の所在は引き続き Notion `送信対象=✅`（データ層・永続・帰属・時刻つき）。canary は opt-in 据置（既定 ON ではない）。実装は `send-campaign.py`（preview/exit 10・11、`--confirm-token`、`--auto-approve`／`--yes`、3モード直交）に反映済み・テスト通過済み。

---

## 17. 成果物の所在

| ファイル | 役割 |
|---|---|
| `doc/run-notion-gmail-send-仕様と検証メモ.md`（本書） | **実装 SSOT**（ファイル名は経緯上「仕様と検証メモ」だが内容は実装仕様書。リネーム可） |
| `eval-log/skill-brief.json` | 本書から導出した機械入力（**v2 で本書に整合済み**） |
| `eval-log/elegant-review/findings.json` | レビュー反映ログ（参照のみ・正本ではない） |
| `eval-log/elegant-review/verdict.json` | 4条件判定 |
| `doc/GCP-Gmail送信設定手順.md` | 認証基盤（Gmail API 有効化＋DWD スコープ）設定手順 |

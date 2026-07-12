# notion-gmail-send

Notion の2つのDB（メール本文_DB / メール送信先_DB）を入力に、`メッセージ対象=✅ かつ 本文非空` の本文を `送信対象=✅ かつ メールを送らない☐ かつ プロ人材メール非空` の宛先へ `{{}}` 差し込み置換して **Gmail で一斉個別送信**する plugin。宛先は **プロ人材（To）と秘書（CC）の両方**へ送る。

不可逆なメール送信を **Notionチェック承認 + fresh rebuild + source-audit + send_guard + 事前予約つき冪等ログ** で安全化する。既定は **最小確認1回**（preview で件数・先頭の宛先・本文先頭を要約表示して停止 → 人間が1回だけ送信可否を答える → 送信）。無人 cron 等は `--auto-approve` で確認0、慎重運用には厳格対話モード（後方互換）も使える（実装 SSOT: `doc/run-notion-gmail-send-仕様と検証メモ.md`）。

### 宛先DB（メール送信先_DB）の主なルール
- `メール（プロ人材）` → **To**、`メール（cc秘書）` → **CC**（本文DBの CC と結合）。両方へ送る。
  - 秘書欄が**空なら CC無しでプロ人材だけに送る**（秘書は必須ではない）。秘書がプロ人材と同じアドレスのときは、二重に届かないよう CC から外す（dry-run で `cc_suppressed_due_to_to_overlap` と表示。To で届くので問題なし）。
- `メールを送らない=✅` は **`送信対象` より優先**で送信しない（最優先の抑制）。
- `送信対象=☐`（OFF）の人は **dry-run の計画に最初から入らない**（記録もしない）。承認後に OFF へ変えた人だけ、本送信時に `send_suppressed` として「送らなかった」記録が残る。
- 同一の `メール（プロ人材）` が複数行にあると（会社名違いでも）**最新の1件だけ**送信する（`created_time` 降順、同時刻は `page_id` 降順。重複送信しない）。「上位ID＝新しいもの」は作成時刻の新しさのこと。
- `部署名` は廃止。本文に `{{部署名}}` を書かないこと（残すと未置換でその通は送られない）。`/run-notion-gmail-source-audit` を実行すると、DB2 に `部署名` 列が残っていれば `deprecated_property` として削除を促す。
- 送ったメールは**送信者の「送信済み」に残る**（Gmail の仕様）。

> 用語（プロ人材＝To / 秘書＝CC など）の対応表は `skills/ref-notion-gmail-send-spec/references/spec-detail.md` §8 を参照。

---

## TL;DR: 送信までの最短手順（非エンジニア向け）

各ステップの詳細は本 README 内の該当節（**太字**の見出し）を参照。**既定は「最小確認1回」**で、`/run-notion-gmail-send` を実行すると送信せず要約（件数・先頭の宛先・本文先頭・抑制/skip 内訳・⚠️警告）と `CONFIRM_TOKEN` を表示して止まり、内容を見て**1回だけ送信可否を答える**と送信される。重い `APPROVE` 文字列の手打ちは不要。完全無人で自動化したい場合（cron 等）は `--auto-approve` を付けると確認なしで送信する。

1. **Notion を3つのDBで用意し ID を登録** — メール本文_DB（本文テンプレ）・メール送信先_DB（送信先）・送信ログDB の3つを作り、それぞれの id を**作業フォルダ**（Claude を開いているフォルダ＝`$CLAUDE_PROJECT_DIR`。clone 開発者は repo-root）直下の `.notion-config.json` に記入する。空の雛形は Claude に「**doctor で初期化して**」と頼む（`doctor --init`）と自動生成され、`<…>` を実値で埋めるだけにできる。（→ **セットアップ** の「2. 設定ファイル」「4. 送信ログDB の構築」）
2. **認証鍵を macOS Keychain に設定** — Notion API token（`notion-api-key.<keychain-prefix>`）と Google サービスアカウント鍵（`google-sa.<keychain-prefix>`）を登録し、Gmail 側の DWD / gmail.send scope / sendAs を設定する。**秘密値はチャットや issue に貼らない**。設定できたら Claude に「**doctor で確認して**」と頼めば、本送信せずに認証/設定の成否を一括点検できる。（→ **セットアップ** の「3. 認証鍵」/ `ref-gmail-dwd-setup`）
3. **Notion でチェックを付ける（＝承認）** — 送りたい宛先に `送信対象=✅`、送る本文に `メッセージ対象=✅` かつ `{{}}` 入り本文を用意する。**この Notion のチェックがそのまま承認**になる。
   - **✅ を付けて送信を実行すると、その全員へ実際にメールが送られます（下書きではありません）。既定では送信前に件数・先頭の宛先・本文先頭を1回だけ確認できます。** 初回は `--canary` で少数だけ実メール検品してから全件に広げるのを推奨。
4. **送信** — `/run-notion-gmail-send` を実行すると、まず送信せず要約と `CONFIRM_TOKEN` を表示して停止する。要約を見て送信してよければ**1回だけ可否を答える**（`--confirm-token <CONFIRM_TOKEN>` で再実行）と、内部で 品質監査(source-audit) → **最新 Notion から送信計画を再構築**（要約時と内容が一致する時だけ送信） → Gmail 送信 → 送信ログ記録 → 日本語レポート、の順に進む。（→ **使い方**）
   - 初回や大量送信は少数だけ試す `--canary 3` を任意で使える。残りは同じコマンドの再実行で送信（既送は自動 skip）。
   - 読解強制つきで一段と慎重に送りたいときは**厳格対話モード（後方互換）**も使える（→ **使い方** の「厳格対話モード」）。

> 確認回数と独立に常時効く独立検証は **source-audit・最新 Notion からの再構築（fresh rebuild）・送信時 suppress 再検証（C-1）・From 検証・Notionページ単位の content dedup（二重送信防止）**。一方 `plan_hash`/件数/`content_hash` の照合が plan 改竄を実効検出するのは plan.json をディスク経由で受け取る**厳格対話モード**で、最小確認1回/cron では承認値が同一プロセス内 self-derive のため恒真の defense-in-depth（compose バグ検出）に留まる（→ **安全設計（三本柱）** の正直な明示）。残るリスクは「正しい本文を・正しい宛先リストに」整える Notion 側の運用で、初回 canary（少数の実メール検品）で吸収する。初回や大量に送る前に **想定送信規模と大量送信（canary 運用）** 節も確認してください。

---

## 構成（責務分離）

| 種別 | 名前 | 役割 |
|---|---|---|
| ref skill | `ref-notion-gmail-send-spec` | データ契約・安全設計の参照正本（2DB schema / 送信ログDB schema / 冪等キー / preflight / status enum） |
| ref skill | `ref-gmail-dwd-setup` | Gmail API / DWD / SA鍵 / sendAs alias 認証設定ガイド |
| run skill | `run-notion-gmail-sendlog-setup` | 送信ログDB のプロパティを §9 schema に冪等構築 |
| run skill | `run-notion-gmail-source-audit` | 送信元2DB のデータ品質を送信前に監査（空本文/未知トークン/不正アドレス/未置換リスク） |
| run skill | `run-notion-gmail-dry-run` | 送信計画を生成・全件プレビュー（**送信しない**） |
| run skill | `run-notion-gmail-send` | 既定=最小確認1回（preview→要約+CONFIRM_TOKEN→単一確認→送信。Notion `送信対象=✅` を承認・最新から新鮮 plan）／無人 cron は `--auto-approve`・厳格対話も可。preflight→reserve→send_guard→Gmail→log→report |
| agent | `gmail-send-presend-verifier` | context:fork で送信前二段確認（Sycophancy 防止） |
| hook | `guard-gmail-send` | PreToolUse 補助防御（承認迂回の Gmail 直接送信を遮断） |
| lib | `lib/*.py` | 決定論モジュール（notion/gmail クライアント・置換・組立・plan・send_guard・冪等ログ・preflight） |

---

## セットアップ

### 1. install

```bash
# marketplace 経由
/plugin marketplace add OWNER/harness
/plugin install notion-gmail-send

# または CLI (リポジトリ clone 済みの場合)
claude plugin install ./plugins/notion-gmail-send
```

### 2. 設定ファイル `.notion-config.json`

DB ID と送信元を**作業フォルダ**（Claude を開いているフォルダ＝`$CLAUDE_PROJECT_DIR`。clone 開発者は repo-root）直下の `.notion-config.json`（gitignore 対象・git に載らない）に置く。**何を・どこに・どの値で**置くかは本節が唯一の正本。作り方は次の3通り（どれでも同じファイルができる）:

- **A. 自動生成（推奨・install 形態を問わない）** — チャットで Claude に「**doctor で初期化して**」と頼む。plugin 同梱の `setup_doctor.py --init` を `$CLAUDE_PLUGIN_ROOT` 経由で解決し、placeholder 入りの `.notion-config.json` を作業フォルダへ生成する（ユーザーがパスを手で打つ必要はない）。生成後に `<…>` を実値で埋める。
- **B. clone 開発者が自分のターミナルで生成** — `python3 plugins/notion-gmail-send/lib/setup_doctor.py --init`（repo を clone した場合のみ有効な相対パス）。
- **C. 手書き** — 下記テンプレを `.notion-config.json` として保存し実値を埋める。clone 済みなら `plugins/notion-gmail-send/.notion-config.example.json` を雛形に使える。

> どの方法でも生成直後は `<…>` の placeholder で、**実値を埋めるまで dry-run も送信もできない**（fail-closed）。`/run-notion-gmail-dry-run` を config 不在のまま実行しても、貼り付け用の雛形と保存先を案内して安全に停止する（1通も送らない）。
> 例外として、計画生成だけを先に確認したい場合は `/run-notion-gmail-dry-run --db1 <メール本文DB id> --db2 <メール送信先_DB id>` のように DB ID を両方明示すれば、`.notion-config.json` 不在でも read-only dry-run は実行できる。本送信には引き続き config / 送信ログDB / Gmail 認証の preflight が必要。

設定ファイルの探索順は `--config 明示 > env(NOTION_GMAIL_CONFIG) > $CLAUDE_PROJECT_DIR > 上位ディレクトリ走査 > カレント`（`lib/notion_config.py`）。clone 不要で任意の場所に置く上級者は `NOTION_GMAIL_CONFIG=<path>` で明示できる。

```json
{
  "databases": { "gmail-send-log": { "db_id": "<送信ログDBのid>" } },
  "notion_gmail_send": {
    "source": { "body_db": "<メール本文DBのid>", "recipient_db": "<メール送信先_DBのid>" },
    "sender": {
      "impersonate": "<送信元アドレス @your-domain>",
      "sa_keychain": { "service": "google-sa.<keychain-prefix>", "account": "<keychain-prefix>" }
    }
  }
}
```

### 3. 認証鍵（macOS Keychain）

| 用途 | service | account | 取得方法 |
|---|---|---|---|
| Notion API | `notion-api-key.<keychain-prefix>` | `harness` | Notion integration の internal token |
| Google SA鍵 | `google-sa.<keychain-prefix>`（config と一致） | `harness` | GCP サービスアカウント鍵JSON。ローカル端末で下の対話式登録を使う |

> **命名規則**: service 名は `<用途>.<keychain-prefix>`（既存 `notion-api-key.<keychain-prefix>` 等と統一）。SA鍵は Gmail 専用ではなく Sheets/Drive 等でも使う**汎用鍵**なので、Gmail 限定名（`gmail-sa.*`）を避け `google-sa.<keychain-prefix>` とする ── 1つの鍵 = 1つの Keychain 項目を全用途で共有する。account は全鍵共通の `harness`。

秘密値を shell history や AI 会話に残さないため、SA JSON はファイルパスだけを入力し、内容はローカル端末内で Keychain へ渡す。

> ⚠️ **SA鍵は必ず `json.dumps` で1行化してから格納する。** 整形済み JSON（インデントの実改行入り）をそのまま `-w` に渡すと、`security` が値を **hex 文字列化**して保存し、取り出し時に `get_google_sa_key` が「SA鍵が JSON ではない」で失敗する（`json.loads` が hex 先頭の数字を拾って Extra data エラーになる）。下のスクリプトは `json.load` → `json.dumps` で実改行を除去済み。private_key 内の `\n` は JSON エスケープ文字なので影響しない。`-U` は既存項目の上書き（`already exists` 回避）。

```bash
python3 - <<'PY'
import json, pathlib, subprocess
path = pathlib.Path(input("SA JSON file path: ").strip()).expanduser()
one_line = json.dumps(json.load(open(path, encoding="utf-8")))  # 実改行を除去（hex化を防ぐ）
subprocess.run([
    "security", "add-generic-password", "-U",
    "-s", "google-sa.<keychain-prefix>", "-a", "harness",
    "-w", one_line,
], check=True)
PY
```

Gmail API / DWD（ドメイン全体の委任）/ gmail.send scope / sendAs の設定は **`ref-gmail-dwd-setup`** と `doc/GCP-Gmail送信設定手順.md` を参照。Python 依存 `google-auth` が必要（`pip install google-auth`）。

セットアップ状態だけを確認したい場合は **doctor**（config / Keychain / 送信ログDB ID / Gmail 認証を横断診断。本送信はしない）を使う。

- **推奨（install 形態を問わず動く）**: チャットで Claude に「セットアップを doctor で確認して。`--probe` も」と頼む。Claude が plugin 同梱の `setup_doctor.py` を `$CLAUDE_PLUGIN_ROOT` 経由で解決して実行する（ユーザーがパスを手で打つ必要はない）。
- **リポジトリを clone した開発者が自分のターミナルで直接打つ場合**:

```bash
# clone 開発者向け。fallback 形なので $CLAUDE_PLUGIN_ROOT 未定義の素のターミナルでも
# repo 直下相対 (plugins/notion-gmail-send) へ落ちて動く:
D="${CLAUDE_PLUGIN_ROOT:-plugins/notion-gmail-send}/lib/setup_doctor.py"
python3 "$D" --config .notion-config.json
python3 "$D" --config .notion-config.json --probe --from <送信元アドレス>
```

> 注: 上記 `${CLAUDE_PLUGIN_ROOT:-plugins/notion-gmail-send}/…` は素のターミナルでは fallback の `plugins/notion-gmail-send/…`（**repo を clone した場合のみ有効**な相対パス）へ落ちる。`/plugin marketplace add`（README 冒頭の install）で入れたユーザーの作業フォルダには `plugins/` が無いため、上の「Claude に頼む」を使う（`$CLAUDE_PLUGIN_ROOT` は Claude の実行環境でのみ解決され、素のターミナルでは未定義）。

`--probe` は Gmail 実 API で DWD / sendAs まで確認する。本送信はしない。

### 4. 送信ログDB の構築

```
/run-notion-gmail-sendlog-setup --db-id <送信ログDBのid>          # 差分確認 (dry-run)
/run-notion-gmail-sendlog-setup --db-id <送信ログDBのid> --apply  # プロパティを実適用
```

---

## 使い方

### 既定: 最小確認1回（preview → 単一確認 → 送信・推奨）

```
[0 整備] Notion で 送信対象=✅(宛先) / メッセージ対象=✅ かつ {{}}入り本文(本文) を用意
[1 確認] /run-notion-gmail-send                                # 送信せず要約+CONFIRM_TOKEN を表示して停止 (exit 10)
[2 送信] /run-notion-gmail-send --confirm-token <CONFIRM_TOKEN>  # 要約を見て可否を答え、OK なら送信
# 少数検品: /run-notion-gmail-send --canary 3   (preview に canary 件数が反映。残りは再実行で送信)
# 無人 cron: /run-notion-gmail-send --auto-approve   (端末確認なしの確認0送信・high で fail-closed)
```

既定の最小確認1回モードは、まず `/run-notion-gmail-send`（引数なし）で **preview**（送信せず要約 + `CONFIRM_TOKEN`=plan_hash を表示し exit 10）を出します。要約を見て送信してよければ `--confirm-token <CONFIRM_TOKEN>` で再実行すると、最新 Notion から再構築した新鮮 plan の plan_hash がトークンと一致する時だけ送信します（不一致＝preview 後に Notion が変化。exit 11 で再 preview を促す）。承認は Notion の `送信対象=✅` が担い、端末での `APPROVE` 手打ちは不要です。送信フェーズは内部で次を実行します:
1. **source-audit（品質監査）** — 空本文/To/From不正/未知トークン等の high 問題を検出する。**既定（最小確認1回）では preview の要約に ⚠️ 警告として列挙し全停止せず**、該当の宛先/本文は送信時に per-unit skip され、人間が要約を見て送信可否を判断する。**無人 cron（`--auto-approve`）のみ high 残存で fail-closed（1通も送らない）**（秘書CC不正など medium は常に該当 unit の skip 対象。`/run-notion-gmail-source-audit` で内訳確認）。
2. **最新 Notion から送信計画を再構築** — 古い計画を使い回さないので、承認後にアドレスを直しても最新が反映される（旧アドレス送信を封じる）。
3. **承認情報を計画から自己導出** → 各送信単位を `send_guard`（機械的安全層）に通す（未置換 skip / From 検証 / 二重送信 dedup / **送信時 suppress 再検証**＝送信直前に `メールを送らない=✅`/`送信対象=☐` へ変えた宛先を除外）。なお `plan_hash`/件数/`content_hash` 照合も走るが、最小確認1回/cron では承認値が同一プロセス内の self-derive のため恒真で、改竄検出としては機能せず defense-in-depth（compose バグ検出）に留まる（plan 改竄を実効検出するのは plan.json を外部から受け取る厳格対話モード）。
4. Gmail 送信 → 送信ログへ冪等記録 → 日本語レポート。

> 確認回数と独立に常時効く独立検証は source-audit・fresh rebuild・送信時 suppress 再検証（C-1）・From 検証・content dedup です。`--canary N` は安定順の先頭 N 件だけを送り、残りは同じコマンドの再実行で送信されます（content dedup が既送を自動 skip するので二重送信になりません）。

### 厳格対話モード（慎重運用・後方互換）

端末で内容を目視し、読解強制つきで慎重に送りたいとき:

```
[0 整備] /run-notion-gmail-source-audit                   # 送信元2DB の品質を点検
[1 計画] /run-notion-gmail-dry-run                        # plan.json + APPROVE文字列 + 全件プレビュー (送信しない)
[2 目視] 全件プレビューを確認                              # 誰に・どんな本文が送られるか目視
[3 送信] /run-notion-gmail-send --plan <plan.json> --approved-nonce <確認語>   # APPROVE を入力 → 二段確認 → 送信
```

対話モードは dry-run が出した `APPROVE <plan_hash> <count> <first_to> <確認語>` を**完全一致**で入力しないと進みません。`<確認語>` は dry-run が特定の送信単位のプレビュー行末にのみ表示する短コードで、その単位を目視で探さないと得られません（blind approve 防止の読解強制）。承認後も context:fork のエージェントが plan を独立再検査し、`send_campaign` が **units から plan_hash/件数/content_hash を再計算して fail-closed 照合**した上で、preflight（認証/送信ログDB/整合）を通過した送信単位だけが送られます。

---

## 想定送信規模と大量送信（canary 運用）

- **想定規模**: 本 plugin は個別差し込みの一斉送信を **〜数百件** 程度まで安全に扱う設計。dry-run が `本文true × 宛先true` の直積を全件 plan 化し、`send-campaign.py` が承認済み plan の全単位を1通ずつ順に送る。
- **これを超える規模では分割（canary）送信も可能**: まず少数だけ送って**実メールを検品**し、問題なければ残りを送る。既定（最小確認1回）モードは `/run-notion-gmail-send --canary 3` を実行すると preview の要約に「送信可能 N 通のうち先頭3件のみ」と反映され、`--confirm-token <CONFIRM_TOKEN>` を付けた再実行で安定順先頭3件だけを送る（残りは同じコマンドの再実行で送信・content dedup が既送を skip）。厳格対話モードは `/run-notion-gmail-dry-run --canary 3`（または `--limit 3`）で限定後の件数・`plan_hash`・確認語に承認を束縛する。より厳密に対象者を選ぶ場合は **送信元DBの ✅ フラグで対象を絞る**:
  1. メール送信先_DBで、まず少数の宛先だけ `送信対象=✅` にする。
  2. `/run-notion-gmail-send --canary 3` → 要約確認 → `--canary 3 --confirm-token <CONFIRM_TOKEN>` で送信（**preview と同じ `--canary 3` を必ず付ける**。付け忘れると plan が全件へ変わり token 不一致で exit 11 になる。preview 出力が正しい再実行コマンドをそのまま提示するのでコピーすればよい）（または厳格対話モードで dry-run → 全件プレビュー目視 → 承認）し、到達・本文・From・CC を**実メールで**検品する。
  3. 問題なければ残りの宛先も `送信対象=✅` にして、同じコマンドを再実行（既送は dedup で skip）。
  - 冪等ログは **Notionページ単位の content ベース dedup（`{本文page_id}:{宛先page_id}:{content_hash}`・campaign_id 非依存）** なので、2回目以降に対象を広げて再実行しても**既に送った同一本文ページ×同一宛先ページの単位は機構で skip** され二重送信にならない（同一内容を意図して再送する場合のみ `--allow-resend`）。
- **Gmail API の日次送信 quota に注意**: 大量送信は1ユーザー/日あたりの送信上限に達することがある。`send-campaign.py` は quota 到達を検知すると **安全停止（exit 3）し、未送信の単位を `reserved` に戻して次回実行で自動再開**する。上限に達しないよう、上記の ✅ フラグ分割で **日をまたいで小分け**に送るのが安全。

---

## 安全設計（三本柱）

| 安全装置 | 守る対象 | 守らないもの（正直な明示） |
|---|---|---|
| **plan 整合**（plan_hash・件数・content_hash を units から決定論再計算して照合。非対話は送信直前に最新 Notion から **fresh rebuild**） | **厳格対話モードでの** plan.json 改竄／件数偽装／古い plan.json 使い回し（plan.json が非信頼アーティファクトのため信頼境界を跨いで実効） | 最小確認1回/cron での改竄（承認値が同一プロセス内 self-derive ゆえ照合は恒真＝compose バグ検出の defense-in-depth に留まる）／Notion 読取後から送信直前までの意味的なデータ変更 |
| **承認（データ層）**（Notion `送信対象=✅` ＝ 承認。最小確認1回は加えて preview 要約の単一確認 + CONFIRM_TOKEN 束縛。厳格対話は加えて APPROVE 完全一致 + 確認語 + 二段確認） | 誰に送るかの人間の意思を**耐久・帰属・時刻つき**で記録（揮発的な端末文字列より監査に強い） | 「内容が正しい本文か」の保証（機構では強制不能。最終的な内容妥当性は Notion 整備＋下記 source-audit ＋実メール検品に依存） |
| **source-audit ゲート（検出は常時・停止は階層化）** | 空本文/未知トークン/To/From不正/空差し込み値を送信前に行レベルで検出（**無人 cron は high で fail-closed＝1通も送らない**／最小確認1回は high を ⚠️ 警告で要約に出し該当 unit は送信時 skip・人間が判断） | 構文は正しいが意味的に誤った本文（`{{}}` を使わない literal 誤記）、medium 扱いの秘書CC不正（該当 unit skip） |
| **事前予約つき冪等ログ**（Notionページ単位の content ベース dedup・reserved→sent/unknown） | 再実行・**別実行（別 campaign）**での同一本文ページ×同一宛先ページ×同一内容の二重送信、送信成功後ログ失敗 | 宛先を別Notionページとして作り直した同一メールアドレスへの重複、意図的再送（`--allow-resend` で明示） |

- **最小確認1回モードの正直な明示**: 重い `APPROVE` 手打ち・確認語の読解強制を撤去する代わりに、「Notion の `送信対象=✅` という熟慮的操作 ＋ 機械的安全層 ＋ source-audit による検出 ＋ preview 要約の単一確認 ＋（推奨）少数 canary の実メール検品」で誤送信の停止点を確保している。残るリスクは2種で扱いが異なる:
  - 『古い/誤った宛先リストのまま ✅』 → preview 要約（件数・先頭To・本文先頭）と canary（実メール検品）で気づける。
  - 『`{{}}` を使わない literal 誤記の本文（＝`{{}}` を使わずベタ書きした誤った宛名/会社名）』 → **機構では検出不能**。source-audit が緩和できるのは token 層の誤り（unknown/unresolved/空差し込み値）のみで、ベタ書きの誤字を検出する規則は持たない。**canary の実メール検品でのみ吸収する**。

  `送信対象=✅` は永続・帰属・時刻つきのため、揮発的な端末 APPROVE 文字列より監査性はむしろ高い。読解強制つきで一段と慎重に送りたいときは厳格対話モードを使う。
- 安全の正本は `lib/send_guard.py`（`lib/gmail_client.py` が内部で必ず呼ぶ）＋ `send_campaign` の決定論セルフチェック（units→plan_hash/件数/content_hash を再計算照合）。非対話（最小確認1回/cron）でも承認 tuple を新鮮 plan から self-derive した上で per-unit guard loop を必ず通す（人間入力のみ bypass）。ただし非対話では承認値が同一プロセス内 self-derive ゆえ plan_hash/件数/content_hash 照合は恒真で、実効する独立検証は source-audit/fresh rebuild/C-1 送信時 suppress 再検証/From 検証/content dedup が担う（plan 改竄照合が信頼境界を跨いで実効するのは plan.json を外部受領する厳格対話モード）。PreToolUse hook は補助防御。
- 冪等キーは `{本文page_id}:{宛先page_id}:{content_hash}` で **campaign_id を含めない**ため、別実行でも同一Notionページ単位の同一内容再送は既 sent 行にヒットして機構で止まる。意図的再送は `--allow-resend`。
- 送信成否が不明な失敗（接続/timeout、2xx 受理後の解析失敗）は **自動再送せず** `unknown_needs_reconcile` とし手動照合へ回す（at-least-once を避ける）。
- `status=sent` は Gmail API が受理したことを意味し、**受信者への到達を保証しない**。
- 本文全文を含む `plan.json` はローカル作業領域のみ（git・Notion ログに残さない）。

---

## トラブルシュート

| 症状 | 原因 / 対処 |
|---|---|
| G1 で停止（認証） | SA鍵/DWD/sendAs 未設定。`ref-gmail-dwd-setup` と `doc/GCP-Gmail送信設定手順.md` 参照。`pip install google-auth` |
| 「SA鍵が JSON ではない」/ `json.loads` の `Extra data`（位置1） | 整形JSONをそのまま `security -w` に渡すと値が **hex 文字列化**される。`json.dumps` で1行化して `-U` で入れ直す（「3. 認証鍵」のスクリプト）。同一 service に複数 account 項目が混在しても誤読する → `while security delete-generic-password -s google-sa.<keychain-prefix>; do :; done` で全削除してから1項目だけ追加 |
| Keychain 登録で `already exists` | `-U`（上書き）フラグを付ける。付けない `add` は既存項目があると失敗する |
| G2 で停止（送信ログDB） | `run-notion-gmail-sendlog-setup` で構築。config `databases.gmail-send-log.db_id` を確認 |
| 本文0通 | メッセージ対象=✅ かつ `{{}}` 入り本文をDB1に記入 |
| 宛先0（抑制/重複で残らない） | dry-run の「送信抑制 / 重複除外」内訳を確認。`メールを送らない=✅` や プロ人材重複で全滅していないか点検 |
| 送るはずの人に届かない | `メールを送らない=✅` になっていないか、同一プロ人材メールの**より新しい行**が抑制されていないかを確認 |
| 秘書(CC)だけでなく本人(プロ人材)にも届かない | 秘書(CC)アドレスが**不正値**だと、その送信単位ごと `invalid_cc` で skip され**プロ人材(本人)にも届かない**。秘書欄が**空**なら CC 無しで本人には届く（この境界の違いに注意）。`run-notion-gmail-source-audit` で `invalid_cc` を確認し Notion で直す |
| skip が多い | `run-notion-gmail-source-audit` で未置換/不正アドレス/未知・廃止トークン（`{{部署名}}`）を事前に直す |
| 無人 cron（`--auto-approve`）で「source-audit: high severity」停止 | 無人モードのみ high で fail-closed（1通も送らない）。空本文/未知トークン/To/From不正等が残存。`/run-notion-gmail-source-audit` で内訳を確認し Notion で直してから再実行。**既定（最小確認1回）では high は ⚠️ 警告として要約に出るだけで全停止せず**、該当の宛先/本文のみ送信時に skip される |
| `CONFIRM_TOKEN` 不一致で送信されない（exit 11） | preview 後に Notion 側が変わり、最新 plan の plan_hash がトークンと不一致。`/run-notion-gmail-send`（引数なし）で再 preview し、新しい `CONFIRM_TOKEN` で送信し直す |
| 送信0通（preview の送信予定が0 / 送信レポートが0） | `送信対象=✅` の宛先と、本文DBの `メッセージ対象=✅` かつ `{{}}` 入り本文を確認 |
| quota 停止（exit 3） | 再実行で reserved 残件を継続（停止単位は reserved へ戻り自動再開対象）。dedup は content ベースなので campaign_id 維持は不要 |
| 同一内容を意図的に再送したい | 既定はクロス実行の二重送信を機構で防止。再送は `run-notion-gmail-send --allow-resend` |

---

## テスト

```bash
cd plugins/notion-gmail-send && python3 -m pytest tests/ -q
```

コア安全装置（send_guard 全違反検出・冪等 reserve 状態遷移・データ品質監査）をカバー。

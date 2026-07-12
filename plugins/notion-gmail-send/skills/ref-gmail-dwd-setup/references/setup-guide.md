# Gmail DWD 認証 セットアップガイド（要約と配線例）

> **手順の正本は `doc/GCP-Gmail送信設定手順.md`**。本書はその要約に、`run-notion-gmail-send` 固有の Keychain 登録・config 配線・実API検証の使い方を足したもの。画面操作の最新手順はつねに正本を参照する。

---

## 0. 前提（既存 GCP 成果物）

正本 STEP 1〜9 が完了していること（プロジェクト / サービスアカウント / JSON 鍵 / DWD 登録済み）。Gmail のための追加は差分2点だけ。

| 既存 | 完了済み | 本送信のための追加 |
|---|---|---|
| STEP 3 | Drive/Sheets/Docs API 有効化 | **STEP 10: Gmail API を有効化** |
| STEP 5・6 | SA 作成・JSON 鍵発行 | 流用（同じ鍵で送信可） |
| STEP 7 | DWD に scope 登録 | **STEP 11: Gmail scope を追記** |

---

## 1. Gmail API 有効化（正本 STEP 10）

既存プロジェクトを選択した状態で `Gmail API` を有効化する。

```bash
gcloud services enable gmail.googleapis.com --project=<プロジェクトID>
```

`https://console.cloud.google.com/apis/dashboard` の「有効な API」一覧に Gmail API が並べば完了。

---

## 2. DWD に Gmail scope を追記（正本 STEP 11）

特権管理者（Super Admin）作業。`https://admin.google.com/ac/owl/domainwidedelegation` を開き、登録済みクライアント ID（21桁）の行を **編集**して、既存 scope を消さずに末尾へ追記する。

`run-notion-gmail-send` が実APIで要求する scope は次の **2 本**:

```
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/gmail.settings.basic
```

既存 Drive/Sheets/Docs scope の末尾にカンマ区切りで追加する記入例:

```
https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/documents,https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/gmail.settings.basic
```

> `gmail.send` と `gmail.readonly` を包含する `gmail.modify` を使う場合でも、**sendAs 検証には `gmail.settings.basic` が別途必要**。`modify` だけでは sendAs 検証で落ちる。
>
> **注意**: scope は完全一致照合。反映に数分〜最大1時間。直後のエラーは反映待ちのことがある。

---

## 3. 操作対象アドレスを固定（正本 STEP 12）

DWD は「ドメイン内の任意ユーザーを impersonate できる」状態で、管理画面で対象を絞る機能はない。よって impersonate 対象を**1つ（または明示した数個）に決め**、`.notion-config.json` の `sender.impersonate` に書いて運用で固定する。対象は Gmail 有効な実在ユーザーであること。

---

## 4. SA 鍵を Keychain に格納する

SA 鍵 JSON をファイルとして残さず、Keychain の generic-password に値ごと格納する。`lib/secrets.py` は `security find-generic-password -s <service> -a <account> -w` で生値を引き、`json.loads` して `type=="service_account"` を確認する。

```bash
# SA 鍵 JSON の中身をそのまま Keychain に格納（service/account は任意の識別名）
security add-generic-password \
  -s "google-sa.<keychain-prefix>" \
  -a "harness" \
  -w "$(cat /path/to/sa-key.json)"

# 格納直後にファイルは破棄（平文を残さない）
rm -P /path/to/sa-key.json
```

登録確認（秘密値の private_key は表示せず、type と client_email だけ確認する）:

```bash
security find-generic-password -s "google-sa.<keychain-prefix>" -a "harness" -w \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["type"], d["client_email"])'
# => service_account automation@your-domain.co.jp
```

> Notion API 鍵（`notion-api-key.<keychain-prefix>` / `harness`）も同様に Keychain 登録済みであること（G1 の `notion_key` 検査対象）。

---

## 5. `.notion-config.json` の sender 配線例

作業フォルダ（`$CLAUDE_PROJECT_DIR` 直下。clone 開発者は repo-root）の `.notion-config.json`（**gitignore 対象**）に、鍵の値ではなく「どの Keychain 項目を引くか」と impersonate / db_id を書く。

```json
{
  "databases": {
    "gmail-send-log": { "db_id": "<送信ログDBのdatabase id>" }
  },
  "notion_gmail_send": {
    "sender": {
      "sa_keychain": { "service": "google-sa.<keychain-prefix>", "account": "<keychain-prefix>" },
      "impersonate": "automation@your-domain.co.jp"
    }
  }
}
```

- `sa_keychain.service` / `account` … 手順4で登録した Keychain 項目（`get_google_sa_key` が引く）。
- `impersonate` … DWD で承認した送信元ユーザー。From がこれと一致するか、accepted な sendAs alias であること。
- `databases.gmail-send-log.db_id` … 送信ログDB（preflight G2 の依存。`run-notion-gmail-sendlog-setup` が `--write-config` で焼き込む）。

`account` を省略した場合は service のみで引く（`secrets._find_password` が `-a` を付けない）。

---

## 6. From が impersonate と異なるとき（sendAs alias）

impersonate ユーザー以外の From で送るなら、その alias を **impersonate ユーザーの Gmail 設定で alias 登録し、確認メールで accepted 済み**にする（「設定 > アカウント > 他のメールアドレスを追加」）。`gmail_client.verify_sendas` が `verificationStatus=="accepted"`（または `isPrimary`）を要求する。未検証だと G1 が `from_alias_unverified` で止める。

---

## 7. 実API検証（setup doctor / --probe）の使い方

`lib/setup_doctor.py` は本送信を行わず、config / Keychain / 送信ログDB ID / Gmail 認証を横断診断する。`--probe` を付けた場合のみ、実 API で DWD / gmail.send / sendAs alias を動的検証する。live-send 経路 `run-notion-gmail-send/scripts/send-campaign.py` も起動時に自動で `probe_api=True` を呼ぶため、手順1〜6が正しければ本送信前に G1 が自動検証される。

単体で確認したいとき（**install 形態を問わず動く推奨手段は、チャットで Claude に「doctor を実行して」と頼む**こと。Claude が plugin 同梱の `$CLAUDE_PLUGIN_ROOT/lib/setup_doctor.py` を解決する）:

```bash
# repo を clone した開発者が自分のターミナルで直接打つ場合のみ有効な相対パス。
# marketplace / CLI install では作業フォルダに plugins/ が無いため、上記のとおり Claude に依頼する。
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/notion-gmail-send}/lib/setup_doctor.py" --config .notion-config.json
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/notion-gmail-send}/lib/setup_doctor.py" --config .notion-config.json --probe --from <送信元アドレス>
```

返却の `action` は誘導先を示す: `gcp_setup`（GCP 手順 = 本書/正本へ）/ `keychain_setup`（Keychain 登録へ）。すべて `OK` になれば G1 充足。1つでも FAIL なら本送信は始まらない。

---

## 8. つまずきと対処（早見表）

| 症状 | 主因 | 対処 |
|---|---|---|
| `GmailUnavailable: google-auth が未導入` | ライブラリ不在 | `pip install google-auth` |
| `creds.refresh` 失敗 / `dwd_or_lib_unavailable` | DWD 未承認・scope 不足・反映待ち | STEP 11 を確認し最大1時間待つ |
| 送信は通るが sendAs 検証で落ちる | `gmail.settings.basic` 未承認 | DWD に `gmail.settings.basic` を追記 |
| `from_alias_unverified` | From が impersonate でも accepted alias でもない | From を合わせる / alias を accepted に |
| `sa_key_missing` / `KeychainError` | Keychain 項目不在 / 値が鍵 JSON でない | 手順4で再登録（type=service_account を確認） |
| `log_db_id_missing`（G2） | 送信ログDB 未設定 | `run-notion-gmail-sendlog-setup` で `db_id` を焼き込む |

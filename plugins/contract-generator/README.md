# contract-generator セットアップ手順書

> **このドキュメントについて**
>
> このプラグインを動かすために**あなたが一度だけ行う設定**を、上から順にこなすだけで完了するようまとめています。
>
> 難しい知識は不要です。コマンドをコピー&ペーストして進めてください。
>
> 機密(API鍵・トークン)は全て macOS Keychain に保管します(平文ファイルに残しません)。

---

## このプラグインができること

管理台帳(Google Sheets)のチェックが入っていない行を読み、Drive上の.docxひな形(個人/法人)に値を差込んで業務委託契約書を生成し、Slackに通知 → あなたがSlackで承認(✅/OK)し **Claude Code で確定を指示したとき** にPDF化して共有 → 台帳に完了チェック、までを半自動化します。承認はあくまで *記録* で、PDF確定は明示指示で発火します(pull型・誤確定防止)。**常駐サーバーのデプロイは不要**で、Claude Code単体で動きます。

---

## 使い方(セットアップ後・毎回)

**通常は Claude Code に話しかけるだけです。**

| やりたいこと | Claude Code への話しかけ例 |
|---|---|
| 契約書の下書きを作る | 「契約書の下書きを作って」 |
| 承認後に PDF を確定する | 「契約書のPDFを確定して」 |
| ひな形が変わったので追従 | 「契約書のひな形が変わりました」 |
| 改善要望を送る | 「このスキルの○○が分かりにくい/直してほしい」 |

---

## セットアップの前提(ブラウザで完了済みの設定)

以下はすでに完了しているものとして進めます。

もし未完了のものがあれば、先にブラウザで実施してください。

- ✅ Google Cloud でプロジェクトを作成し、Drive API / Sheets API を有効化済み
- ✅ Service Account(SA)を作成し、SA鍵JSONファイル(例: `xl-contract-sa.json`)を手元に保存済み
- ✅ Drive のひな形フォルダ・出力フォルダ・管理台帳を SA のメールアドレスに共有済み
- ✅ Slack App を作成し、必要なスコープを追加してワークスペースにインストール済み
- ✅ Bot User OAuth Token(`xoxb-` で始まるトークン)をコピー済み
- ✅ 通知用 Slack チャンネルを作成し、Bot を招待済み。チャンネルID(`C` で始まる文字列)をコピー済み

---

## セットアップ手順(ターミナルで行う作業)

### ターミナルとは

「ターミナル」とは、コンピュータにコマンドを文字で入力して操作するアプリです。

**開き方:** `Command + スペース` → `terminal` と入力 → Enter

コマンドは一行ずつコピーして貼り付け(`Command + V`)、Enter で実行します。

コマンドの実行中は待ちます。次の行が表示されたら完了です。

---

### Step 0. プラグインを有効化する(Claude Code で行う)

このステップは **Claude Code のチャット画面** で入力します。ターミナルではありません。

Claude Code のチャットに以下を **一行ずつ** 入力・実行します:

```
/plugin marketplace add https://github.com/OWNER/harness
```

Claude Code を再起動して、下記のコマンドを実行します:

```
/plugin install contract-generator@harness
```

**✅ 完了確認:** Claude Code で `/plugin` と入力したとき、一覧に `contract-generator` が `enabled` で表示されれば成功です。

> ⚠️ **よくあるミス:** URL の後ろに余分な文字や日本語が入っているとエラーになります。上の URL だけをそのままコピーして貼り付けてください。

---

### Step 1. Python が動くか確認する

ターミナルを開き、以下を実行します:

```bash
python3 --version
```

**✅ 完了確認:** `Python 3.11.x` のように `3.11` 以上の数字が表示されれば成功です。

> 表示されない場合は [python.org](https://www.python.org/downloads/) から Python 3.11 以上をインストールしてください。

> このプラグインは **Python 標準ライブラリだけで動作**します。追加パッケージのインストール(`pip install`)は一切不要です。

---

### Step 2. gcloud CLI をインストール・ログインする

Google のサービスにアクセスするための認証に「gcloud CLI」というツールが必要です。

#### 2-1. インストール確認

すでにインストール済みか確認します:

```bash
gcloud --version
```

`Google Cloud SDK` のバージョン番号が表示されれば、**インストール済みです。2-2 に進んでください。**

`command not found` と表示された場合はインストールが必要です:

**① ターミナルでインストール先フォルダへ移動する**

ホームディレクトリ直下にインストールします（変えたい場合はパスを書き換えてください）:

```bash
cd ~
```

**② ダウンロードして展開する**

Apple シリコン（M1/M2/M3）の Mac の場合:

```bash
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-arm.tar.gz
tar -xf google-cloud-cli-darwin-arm.tar.gz
```

Intel Mac の場合:

```bash
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-x86_64.tar.gz
tar -xf google-cloud-cli-darwin-x86_64.tar.gz
```

> 💡 **どちらかわからない場合:** 画面左上のリンゴマーク →「このMacについて」→「チップ」に `Apple M1` などと書いてあれば Apple シリコン、`Intel` と書いてあれば Intel Mac です。

**③ インストールして設定を反映する**

```bash
./google-cloud-sdk/install.sh
source ~/.zshrc
```

途中で `Do you want to help improve the Google Cloud CLI? (Y/n)?` などと聞かれたら、`n` を入力して Enter で進めて構いません。

**④ ターミナルを一度閉じて開き直す**

その後、以下で確認します:

```bash
gcloud --version
```

`Google Cloud SDK` のバージョン番号が表示されれば成功です。

---

#### 2-2. Google アカウントでログインする

```bash
gcloud auth login
```

ブラウザが自動で開き、Google ログイン画面が表示されます。

使用するアカウントを選択して「許可」をクリックしてください。

ターミナルに戻り `You are now logged in as [your-email]` のように表示されれば完了です。

続けて、Google Cloud プロジェクトを指定します:

```bash
gcloud config set project xl-claude-code-497706
```

**✅ 完了確認:**

```bash
gcloud auth list
```

あなたの Google アカウントのメールアドレスの横に `*` マークが表示されれば成功です。

---

### Step 3. SA鍵を Keychain に登録する

SA鍵(Service Account の鍵)を macOS Keychain に安全に保管します。（`xl-claude-code-497706-5ab614076f89.json` のファイルを担当者より受け取ってください）

**Keychain** とは macOS に組み込まれたパスワード管理の仕組みで、鍵を暗号化して保管します。

> ⚠️ SA鍵の内容(`private_key` など)は、チャット・Slack・メール・書類に貼り付けないでください。
>
> この手順では **ファイルの場所(パス)** だけをターミナルに入力します。

#### 3-1. SA鍵JSONファイルのパスを確認する

Finder で SA鍵JSONファイル(`xl-claude-code-497706-5ab614076f89.json`)を探します。

1. Finder でファイルを **右クリック**
2. `option` キーを押したまま
3. **「"ファイル名.json"のパス名をコピー」** をクリック

コピーしたパスをターミナルに貼り付けます(ダブルクォートで囲む点に注意):

```bash
SA_KEY_JSON="/ここにコピーしたパスを貼り付け"
```

**例:** パスが `/Users/taro/Downloads/xl-claude-code-497706-5ab614076f89.json` の場合

```bash
SA_KEY_JSON="/Users/taro/Downloads/xl-claude-code-497706-5ab614076f89.json"
```

ファイルが正しく見つかるか確認します:

```bash
ls -la "$SA_KEY_JSON"
```

**✅ ファイル名とサイズが表示されれば成功です。**

`No such file or directory` と表示された場合は、パスが違うので 3-1 からやり直してください。

#### 3-2. プラグインフォルダへ移動する

インストール済みのプラグインの場所を自動で探します。そのままコピーして実行してください:

```bash
KEYCHAIN_HELPER="$(find "$HOME/.claude" -type f -path '*/contract-generator/lib/keychain_get_secret.py' -print -quit 2>/dev/null)"
if [ -z "$KEYCHAIN_HELPER" ]; then
  echo "contract-generator が見つかりません。担当者に確認してください。"
else
  echo "見つかりました: $KEYCHAIN_HELPER"
fi
```

**✅** `.../contract-generator/lib/keychain_get_secret.py` のようなパスが表示されれば成功です。

見つからないメッセージが出た場合は、担当者に contract-generator のセットアップ状況を確認してください。

続けて、作業フォルダへ移動します:

```bash
CONTRACT_GENERATOR_DIR="$(dirname "$(dirname "$KEYCHAIN_HELPER")")"
cd "$CONTRACT_GENERATOR_DIR"
pwd
```

**✅** `pwd` の出力の末尾が `contract-generator` になっていれば成功です。

> ⚠️ **この後の `python3 lib/...` コマンドは全てこのフォルダで実行します。**
>
> ターミナルを閉じて開き直した場合は、3-2 の手順から再度実行してください。

#### 3-3. Keychain に登録して元ファイルを削除する

`$(< file)` でそのまま渡すと JSON 内の改行によりバイナリ扱いになり、Keychain が hex エンコードして保存します。Python で1行に圧縮（minify）してから登録してください:

```bash
python3 -c "
import json, subprocess
with open('$SA_KEY_JSON') as f:
    data = json.load(f)
minified = json.dumps(data, separators=(',', ':'))
result = subprocess.run(
    ['security', 'add-generic-password',
     '-s', 'gdrive-service-account.<keychain-prefix>',
     '-a', 'contract-generate/service-account-json',
     '-w', minified, '-U'],
    capture_output=True, text=True
)
print('OK' if result.returncode == 0 else result.stderr)
"
```

登録できたか確認します:

```bash
CLAUDE_HOOK_INVOKED=1 python3 lib/keychain_get_secret.py \
  --service gdrive-service-account.<keychain-prefix> --account "contract-generate/service-account-json" --check
```

**✅** `OK {...マスク...}` のように表示されれば成功です。

> **もし登録がうまくいかない場合:**
> - `Could not read json file ... Extra data` → JSON に改行が含まれたまま Keychain に保存され、hex エンコードされています。上記の Python コマンドで登録し直してください
> - `Could not read json file ... Expecting value` → ファイルの中身ではなくパスが登録されています。3-3 の Python コマンドを再実行してください

---

### Step 4. Slack Bot Token を Keychain に登録する

Slack App の管理画面(`https://api.slack.com/apps`)から Bot User OAuth Token(`xoxb-` で始まるトークン)をコピーして登録します。

`<xoxb-トークン>` の部分をコピーしたトークンに置き換えて実行:

```bash
security add-generic-password \
  -s slack-bot-token.<keychain-prefix> \
  -a "contract-generate/bot-token" \
  -w "<xoxb-トークン>" \
  -U
```

確認します:

```bash
CLAUDE_HOOK_INVOKED=1 python3 lib/keychain_get_secret.py \
  --service slack-bot-token.<keychain-prefix> --account "contract-generate/bot-token" --check
```

**✅ 完了確認:** `OK {xoxb...マスク...}` と表示されれば成功です。

---

### Step 5. 設定ファイルを作成する

このプラグインの設定ファイル(`google-config.json`)を作成します。

一度作ればプラグインを更新しても消えません。

まず、設定フォルダを用意してサンプルファイルをコピーします:

```bash
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator"
mkdir -p "$CONFIG_DIR"
cp skills/run-contract-generate/references/google-config.sample.json "$CONFIG_DIR/google-config.json"
echo "作成しました: $CONFIG_DIR/google-config.json"
```

作成したファイルをテキストエディタで開きます:

```bash
open -e "${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator/google-config.json"
```

ファイルが開いたら、下記の内容に**丸ごと書き換えて**保存してください:

```json
{
  "spreadsheet_id": "1ag3ri-E05M3-6vCXidZ0AixVunJ54YqwaLVWejO3Sxc",
  "templates_folder_id": "1IDlIAXuGoG587ZRlYfJBm5RaD0aqE-bK",
  "individual_folder_id": "1jjPKwtHGIGL4FaqqCzLUpTQE4Rek24oe",
  "corporate_folder_id": "1VIpEKbVqwtyvMGSZ23OMux02__3VauX_",
  "keychain_service": "gdrive-service-account.<keychain-prefix>",
  "keychain_account": "contract-generate/service-account-json",
  "slack_channel": "C0XXXXXXXXX",
  "slack_keychain_service": "slack-bot-token.<keychain-prefix>",
  "slack_keychain_account": "contract-generate/bot-token"
}
```

> 💡 **チャンネルID の確認方法:** Slack でチャンネル名をクリック → 画面一番下に `チャンネルID: C0XXXXXXXXX` が表示されます。`slack_channel` の `C0XXXXXXXXX` をその値に書き換えてください。

**✅ 完了確認:**

```bash
cat "${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator/google-config.json"
```

`slack_channel` に `C` で始まるIDが入っていれば成功です。

---

### Step 6. セットアップ診断を実行する

Step 1〜5 の設定が全て正しく完了しているかを自動でチェックします:

```bash
python3 lib/setup_doctor.py
```

**✅ 完了確認:** `✅ セットアップは整っています(draft 実行可能)。` と表示されれば全て完了です。

`要対応: Step N` と表示された場合は、該当のステップに戻って対処し、再度実行してください。

個別に確認したいときは `python3 lib/config_auth.py --check` も使えます。

---

### Step 7. 動作確認・実際に動かしてみる

まず、実際のデータを変更せずに動作確認だけする(ドライラン):

```bash
python3 lib/engine.py --phase draft --type all --dry-run
```

> 初回実行で「シート未作成(dry-runのため読取スキップ)」と表示されることがありますが、正常です。

問題なければ、実際に契約書を生成して Slack に通知する:

```bash
python3 lib/engine.py --phase draft --type all
```

**✅ 完了確認:** 下書き(Docs黄色版)が個人/法人フォルダに作成され、Slack に通知が届けばセットアップ完了です。

---

### Step 8. 承認後に PDF を確定する

Slack の通知スレッドで以下のいずれかで承認の意思表示をしてください:

| 承認方法 | 具体的な操作 |
|---|---|
| リアクション | ✅ / ✔️ / 👍 / `:ok:` のいずれかを付ける |
| 返信 | `ok` / `おk` / `承認` / `approve` / `了解` のいずれかを含む返信を送る |

承認後、**Claude Code で「契約書のPDFを確定して」と指示するか**、ターミナルで以下を実行します:

```bash
python3 lib/engine.py --phase finalize --type all
```

**✅ 完了確認:** PDF が同フォルダに保存され、台帳のステータスが `completed` になれば成功です。

> 承認しただけでは PDF は自動生成されません。明示的に指示したときだけ生成されます(誤確定防止)。

> **自動化したい場合:** `python3 lib/engine.py --phase finalize --type all` を cron で定期実行する方法もあります(LLM を使わないためトークン費用ゼロ)。詳細はシステム担当者にご確認ください。

---

## ひな形が変わったとき

ひな形(.docx)を Drive 上で差し替えた後、Claude Code に:

> 「契約書のひな形が変わりました」

と伝えると、差分を検知して差込マッピング・台帳列を自動で追従させます。

---

## トラブルシュート

まず `python3 lib/setup_doctor.py` を実行してください。どの Step が未完了かを教えてくれます。

| 症状 | 対処 |
|---|---|
| `Keychain lookup failed` | Step 3 または Step 4 をやり直す |
| `Could not read json file ... Extra data` | JSON に改行が含まれたまま Keychain に保存され、hex エンコードされている。Step 3 の 3-3 の Python コマンドで登録し直す |
| `Could not read json file ... Expecting value` | Keychain にファイルパスが登録されている。Step 3 の 3-3 を再実行する |
| `Drive ...: SAから見えません` | Google Drive でそのフォルダ/台帳を SA のメールアドレスに「編集者」で共有する |
| `Drive ...: SAは閲覧できますがファイル追加できません` | 出力先フォルダの SA のアクセス権を「閲覧者」→「編集者」に変更する |
| `storageQuotaExceeded` | 出力先フォルダを共有ドライブ配下に移し、SA をコンテンツ管理者として追加する |
| `CERTIFICATE_VERIFY_FAILED` | `/Applications/Python 3.11/Install Certificates.command` を実行してから再試行 |
| `missing_scope` | Slack App の OAuth スコープが不足。`channels:read` / `channels:history` / `reactions:read` を追加し「Reinstall to Workspace」後に Step 4 を再実行 |
| `channel_not_found` | `google-config.json` の `slack_channel` のIDを確認。または Slack App を「Reinstall to Workspace」して新しいトークンを Step 4 で再登録 |
| Slack に通知が来ない | Bot がチャンネルに招待されているか確認する |
| 承認しても PDF が出ない | 承認だけでは生成されません。Claude Code で「契約書のPDFを確定して」と指示するか `python3 lib/engine.py --phase finalize --type all` を実行する |
| 生成Docに `●`/`XXXX` が残る | 台帳の対応列が空欄。入力して再実行する |
| ひな形が変わって差込位置がズレた | 「ひな形が変わりました」と Claude Code に伝えて追従を実行する |

---

## Keychain に保存する機密の一覧(命名規約)

| 用途 | service | account | 登録Step |
|---|---|---|---|
| Google Drive/Sheets SA鍵 | `gdrive-service-account.<keychain-prefix>` | `contract-generate/service-account-json` | Step 3 |
| Slack Bot Token | `slack-bot-token.<keychain-prefix>` | `contract-generate/bot-token` | Step 4 |

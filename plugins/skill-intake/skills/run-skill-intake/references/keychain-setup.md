---
name: keychain-setup
description: macOS Keychain への Notion トークン登録手順 (PAT / Internal Integration 両対応)
type: reference
---

# Keychain Setup — Notion トークン登録手順

## 1. Notion トークンの種類

| 方式 | プレフィックス | 取得場所 | チーム共有 |
|---|---|---|---|
| **Personal Access Token (PAT)** | `ntn_` | `https://www.notion.so/profile/integrations` または `https://www.notion.so/developers/tokens` | 推奨されない (発行者個人権限・監査ログ汚染リスク) |
| **Internal Integration Secret** | `secret_` | `https://www.notion.so/my-integrations` (ワークスペース管理者のみ作成可) | ワークスペース内チーム共有が公式想定 |

選択判断:
- 個人試験運用 → PAT で十分
- チーム本番運用 → Internal Integration を管理者に依頼 (推奨)
- どちらも入手できない場合 → サービスアカウント (Bot 用 Notion アカウント) を作って PAT 発行

## 2. PAT 取得手順 (個人用)

1. Notion にログイン → 右上アバター → `Settings` → 左サイドバー `Connections` の下にスクロール → `Developer integrations` の **`個人用アクセストークン (Personal Access Tokens)`** を開く
2. `+ 新しいアクセストークン` をクリック
3. 名前: 任意 (例: `xl-ClaudeCode-Skill-Interview`)
4. ワークスペース: ドロップダウンから選択 (アクセス権のあるワークスペースのみ表示)
5. `作成` をクリックして表示された `ntn_xxxxxxxx...` をコピー (この画面を閉じると再表示不可)

## 3. Internal Integration 取得手順 (チーム用)

1. `https://www.notion.so/my-integrations` を開く (ワークスペース管理者でないと「インストール可能なワークスペースがありません」と表示される)
2. `+ 新規統合` → 名前: `skill-intake` / タイプ: `内部` / ワークスペース: 対象
3. 機能 (Capabilities) で **`コンテンツの読み取り` / `コンテンツの更新` / `コンテンツの挿入`** にチェック (ユーザー情報やメールは不要なら外す)
4. `送信` → 表示された `Internal Integration Secret (secret_xxxxxxxx...)` をコピー
5. 対象 Notion DB (環境変数 `INTAKE_NOTION_DATABASE_ID` で指定) を開き、右上 `⋯` → `接続` → 作った integration を追加

## 4. macOS Keychain への登録

### 4.0 安全原則 — AI アシスタント越しに PAT を渡さない

`security add-generic-password -w 'ntn_...'` のように **PAT 文字列を引数として** Claude Code / その他 AI アシスタントの Bash ツール経由で実行すると、PAT が以下に残留する:

- アシスタントの会話履歴 / コンテキスト
- ツール実行ログ・トランスクリプト
- シェル履歴 (`~/.zsh_history` 等)
- (チーム共有の場合) 共有プロンプト・スクショ

**必ず以下の 2 ルールを守る**:

1. `-w` フラグを使わず **対話入力モード**で登録する (PAT 文字列はターミナルにしか出ない)
2. 登録コマンドは **ユーザー自身のローカルターミナルで実行**する。AI アシスタントには「登録した」事実だけ伝える

### 4.1 既存登録の確認 (任意)

```bash
security find-generic-password -s notion-api-key.<keychain-prefix> -a <keychain-prefix> 2>/dev/null \
  && echo "既存あり (更新になります)" \
  || echo "未登録 (新規登録します)"
```

### 4.2 登録 — 対話入力モード (推奨)

```bash
# 既存があれば削除 (再登録時のみ)
security delete-generic-password \
  -s notion-api-key.<keychain-prefix> \
  -a <keychain-prefix> 2>/dev/null

# 登録 — 対話入力モード (パスワードがシェル履歴に残らない)
# 重要: `-w` を **引数なしで末尾に** 置くこと。
#       `-w` を省略すると空パスワードで黙って登録される (プロンプトは出ない)。
# 重要: `-T /usr/bin/security` を付ける。これが無い (`-T ''`) と
#       skill-intake がトークンを読むたび macOS が承認ダイアログを出し、
#       「設定済みなのに何度も聞かれる」状態になる (notion_config は
#       /usr/bin/security 経由で読むため、この CLI を ACL に許可する)。
security add-generic-password \
  -s notion-api-key.<keychain-prefix> \
  -a <keychain-prefix> \
  -T /usr/bin/security \
  -U \
  -w

# 実行後、`password data for new item:` プロンプトが出るので
# ntn_xxx... または secret_xxx... を貼り付けて Enter
# (入力中の文字は表示されないが正常動作)
```

### 4.3 登録 — 一括モード (非推奨 / 自動化スクリプト専用)

```bash
# シェル履歴に残るため、対話入力モードが使えない CI/CD などでのみ使う
security add-generic-password \
  -s notion-api-key.<keychain-prefix> \
  -a <keychain-prefix> \
  -w 'ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -T /usr/bin/security \
  -U
```

### オプション解説

| オプション | 意味 |
|---|---|
| `-s` | service 名 (= `notion-api-key.<keychain-prefix>`) |
| `-a` | account 名 (= `harness`、`INTAKE_KEYCHAIN_ACCOUNT` で上書き可) |
| `-w` | パスワード本体 (省略すると対話入力) |
| `-T /usr/bin/security` | **推奨**。security CLI に読取許可。skill-intake はこの CLI 経由でトークンを読むため、一度許可すれば以後ダイアログは出ない |
| `-T ''` | アクセス許可アプリ空 = **毎回承認ダイアログ**。「設定済みなのに何度も聞かれる」原因。CLI 自動化では使わない |
| `-U` | 既存があれば更新 |

> 既に `-T ''` で登録済みで毎回聞かれる場合は、4.2 の手順 (delete → `-T /usr/bin/security` 付きで add) で **再登録** すれば解消する。トークン本体の再入力が必要なので、ユーザー自身のローカルターミナルで実行すること。

## 5. 動作検証 (2 段階)

### 5.1 段階 1 — Keychain 取得確認 (本体を表示せず)

```bash
bash ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/hooks/post-keychain-add.sh
```

期待出力:
```
[skill-intake] Keychain 取得テスト: service=notion-api-key.<keychain-prefix>, account=<keychain-prefix>
OK: トークン取得成功 (長さ=N, prefix=ntn_...)
    トークン本体は表示しません。
```

### 5.2 段階 2 — Notion API 接続テスト (whoami + DB アクセス)

```bash
TOKEN=$(security find-generic-password -s notion-api-key.<keychain-prefix> -a <keychain-prefix> -w)

# whoami: PAT が API に届くか
echo "whoami:"; curl -sS https://api.notion.com/v1/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Notion-Version: 2022-06-28" | python3 -m json.tool | head -20

# DB access: 対象 DB に届くか (事前に export INTAKE_NOTION_DATABASE_ID=<your-database-id>)
echo "DB access:"; curl -sS "https://api.notion.com/v1/databases/${INTAKE_NOTION_DATABASE_ID:?INTAKE_NOTION_DATABASE_ID is required}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Notion-Version: 2022-06-28" | python3 -m json.tool | head -30

unset TOKEN  # 環境変数からも消す
```

成功条件:
- whoami: あなたの Notion ユーザー情報 (`object: "user"`, `id`, `name` など) が返る
- DB access: DB の `title`, `properties` などが返る

### 5.3 段階 3 (任意) — 本体取得確認

PAT 文字列を画面に出してでも確認したい場合のみ:

```bash
security find-generic-password \
  -s notion-api-key.<keychain-prefix> \
  -a <keychain-prefix> -w
```

ターミナル履歴に残るため、確認後は `clear` 等で画面をクリアすることを推奨。

| エラー | 意味 | 対処 |
|---|---|---|
| `The specified item could not be found` | Keychain 未登録 | 手順 4 をやり直す |
| HTTP 401 `API token is invalid` | トークン期限切れ・取り消し済み | Notion 側で新規発行 → Keychain 再登録 |
| HTTP 403 `Access denied` | PAT/Integration が対象 DB に未接続 | Notion DB の `⋯` → `接続` で integration 追加 (PAT は発行者がアクセスできる DB 限定) |
| HTTP 404 | DB ID 誤り | `INTAKE_NOTION_DATABASE_ID` を再確認 |

### 5.4 結果共有チェックリスト (AI アシスタント連携時)

セットアップ完了を AI アシスタントに伝える際、**PAT 本体は絶対に貼らない**。代わりに以下を共有する:

- [ ] `bash ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/hooks/post-keychain-add.sh` が `OK: トークン取得成功 (長さ=N, prefix=ntn_...)` を出力
- [ ] `whoami` の HTTP ステータス (200 / 401 / 403)
- [ ] DB access の HTTP ステータス (200 / 401 / 403 / 404)
- [ ] (404 の場合) 提供 URL の DB ID を再確認、または別 DB を使うか
- [ ] (403 の場合) Notion 側で DB の `接続` メニューに PAT/Integration を追加したか

## 6. 環境変数で上書きしたい場合

既定値 (`service=notion-api-key.<keychain-prefix>`, `account=<keychain-prefix>`) と異なる Keychain entry を使いたいとき (例: staging 環境専用 entry、bot アカウント運用) は環境変数で上書きする。以下は **既定とは別の値を指定する例** であり、初回セットアップでこの値をそのまま使う必要はない。

```bash
# 例: staging 用 service + bot アカウント運用に切り替える
export INTAKE_KEYCHAIN_SERVICE=notion-api-key-staging
export INTAKE_KEYCHAIN_ACCOUNT=skill-intake-bot
export INTAKE_NOTION_DATABASE_ID=ffffffffffffffffffffffffffffffff
```

`scripts/keychain_get_secret.py` はこれらを自動参照する。未設定なら既定値 (`account=<keychain-prefix>`) にフォールバック。

## 7. ローテーション

3〜6 ヶ月ごとに以下:

1. Notion 側で新トークン発行
2. `security add-generic-password -U` で Keychain を上書き更新
3. 旧トークンを Notion 側で `取り消す`
4. `bash ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/hooks/post-keychain-add.sh` で取得確認
5. `curl /v1/users/me` で動作確認

## 8. トラブル: 「インストール可能なワークスペースがありません」

`my-integrations` ページで Integration 新規作成時にこのメッセージが出る場合:

- **原因**: ログイン中アカウントが管理者ロールを持つワークスペースが無い
- **対処A**: Notion 左上の workspace switcher で `+ ワークスペースを作成` → 個人 (Free) ワークスペースを作る → そこで integration 作成
- **対処B**: 管理者に Integration 作成と Connections 追加を依頼
- **対処C**: PAT (個人用アクセストークン) なら一般メンバーアカウントでも発行可能。手順 2 を参照

## 9. macOS 以外

Linux: `pass`, Windows: `cmdkey` などに差し替える。`scripts/keychain_get_secret.py` を OS 判定で分岐させる修正が必要。今版では macOS のみ対応。

---
name: ref-gmail-dwd-setup
description: Gmail送信のDWD・サービスアカウント鍵・gmail.send scope・sendAs aliasを設定したいとき、preflight G1認証エラーの原因と対処を確認したいときに使う。
disable-model-invocation: false
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-06-24
version: 0.1.0
source: "doc/GCP-Gmail送信設定手順.md"
source-tier: internal
last-audited: 2026-06-24
audit-trigger: source-update
allowed-tools:
  - Read
---

# ref-gmail-dwd-setup

## Purpose & Output Contract

`run-notion-gmail-send` が Gmail API で個別送信するための**認証基盤（Gmail API / DWD / SAサービスアカウント鍵 / gmail.send scope / sendAs alias）の設定参照ガイド**。preflight G1（`lib/preflight.gate_g1_auth`）が fail-closed で送信を止めたとき、何が未設定で、どこを直せば通るかを引くための索引スキル。

**入力**: なし（知識参照）
**出力**: DWD が要る理由・SA鍵の Keychain 格納と config 配線・DWD scope 承認・From の扱い・preflight G1 の実API検証・典型エラーと対処の知識。
**完了条件**: 参照のみ。GCP / 管理コンソールの設定作業そのものは行わない（それは正本 `doc/GCP-Gmail送信設定手順.md` の責務）。

> **設定手順の正本は `doc/GCP-Gmail送信設定手順.md`**。本スキルはその要約・索引であり、画面操作の最新の正確な手順はつねに正本を参照すること。本書と正本が食い違う場合は正本を優先する。

## なぜ DWD（ドメイン全体の委任）が要るか

Gmail API は「**どのメールボックスとして送るか**」を impersonate（なりすまし）対象で決める。サービスアカウント（SA）は Workspace ユーザーではないため、SA 単体ではドメインユーザーの mailbox から送れない。

DWD を承認すると、SA 鍵が「ドメイン内の指定ユーザーを impersonate して、そのユーザーとして Gmail を操作する」権限を得る。つまり **SA 鍵でドメインユーザーになりすまし、そのユーザーの From でメールを送る**ために DWD が必須になる。

`lib/gmail_client.py` は `service_account.Credentials.from_service_account_info(sa_key, scopes=..., subject=impersonate)` で impersonate 資格情報を作る。`subject`（impersonate 対象）が DWD 承認済みでなければ `creds.refresh()` が失敗し、`GmailUnavailable`（DWD/scope/鍵を確認）になる。

## 設定の2点追加（既存 GCP 成果物を流用）

STEP 1〜9（プロジェクト・SA・JSON 鍵・DWD）が済んでいる前提で、Gmail のために追加するのは**差分2点だけ**（正本 STEP 10/11）。

1. **Gmail API の有効化**（正本 STEP 10）: 既存プロジェクトで `Gmail API` を有効化する（`gcloud services enable gmail.googleapis.com --project=<プロジェクトID>`）。送信のみでも有効化するのはこの 1 API。
2. **DWD に Gmail scope を追記**（正本 STEP 11）: 既存クライアント ID（21桁）の行を**編集**し、既存 Drive/Sheets/Docs scope を消さずに Gmail scope を末尾追記して「承認」する。反映に数分〜最大1時間かかる。

### 本 plugin が実APIで使う scope（DWD 承認欄に必須の2本）

| scope | 用途 |
|---|---|
| `https://www.googleapis.com/auth/gmail.send` | メール送信 |
| `https://www.googleapis.com/auth/gmail.settings.basic` | sendAs alias の検証（From 照合） |

`lib/gmail_client.py` の `GMAIL_SCOPES` はこの 2 本に固定。正本 STEP 11 は `gmail.modify` 等の汎用例を挙げるが、**本 plugin が refresh で要求するのはこの 2 scope**。DWD 承認欄に最低この 2 つ（または両者を包含する scope）を含めないと、scope 完全一致照合で `creds.refresh()` が弾かれる。送信だけ通って sendAs 検証で落ちる場合は `gmail.settings.basic` の付け忘れを疑う。

## SA鍵を Keychain に格納し config へ配線する

秘密の正本は macOS Keychain。SA 鍵の JSON をファイルとして残さず Keychain に入れ、`.notion-config.json` には**鍵そのものではなく「どの Keychain 項目を引くか」だけ**を書く。

`.notion-config.json`（作業フォルダ＝`$CLAUDE_PROJECT_DIR` 直下。clone 開発者は repo-root。gitignore 対象）の `notion_gmail_send.sender` に設定する:

| キー | 役割 |
|---|---|
| `sa_keychain.service` | Keychain の service 名（`security -s`） |
| `sa_keychain.account` | Keychain の account 名（`security -a`、任意） |
| `impersonate` | impersonate 対象アドレス（DWD で承認したユーザー。運用で固定） |

`lib/secrets.py` が `security find-generic-password` でこの項目を引き、`json.loads` して `type=="service_account"` を確認する。`lib/notion_config.py` の `get_sender(config)` が `notion_gmail_send.sender` を返し、preflight G1 がここから `sa_keychain` / `impersonate` を読む。具体の登録コマンドと config 例は `references/setup-guide.md`。

## From の扱い（impersonate 対象 と sendAs alias）

送信の From は次のいずれかでなければ G1 で止まる（`lib/gmail_client.py` の `verify_sendas`）:

- **impersonate 対象自身**: `from_addr == impersonate`（大小無視）なら無条件で OK。
- **検証済み sendAs alias**: impersonate ユーザーの設定に `sendAs` として登録され、`isPrimary` または `verificationStatus == "accepted"` のエイリアス。

つまり impersonate ユーザー以外の From で送るなら、その alias を impersonate ユーザーの Gmail 設定で **alias 登録し、確認メールで accepted 済み**にしておく必要がある。未検証の alias は `from_alias_unverified` で fail-closed になる。

## preflight G1（実API動的検証 / setup doctor --probe）

G1 は2段階で認証を fail-closed 検証する（`lib/preflight.gate_g1_auth(config, from_addr, probe_api=...)`）:

- `probe_api=False`（既定・dry-run 相当）: Keychain の Notion 鍵と SA 鍵の**存在**だけを `probe_*()` で確認する。鍵の値は取得しない。
- `probe_api=True`（live-send 相当・**setup doctor --probe 型の実API動的検証**）: SA 鍵を実際にロードし、`GmailClient` を生成して **DWD impersonate + gmail.send + sendAs alias を実 API で検証**する。live-send 経路 `skills/run-notion-gmail-send/scripts/send-campaign.py` が起動時に `probe_api=True` で呼ぶ。

> 本送信前に単体確認したい場合は doctor を使う。**install 形態を問わず動く推奨手段は、チャットで Claude に「doctor を --probe で実行して」と頼む**こと（Claude が plugin 同梱の `$CLAUDE_PLUGIN_ROOT/lib/setup_doctor.py` を解決する）。repo を clone した開発者は自分のターミナルで `python3 plugins/notion-gmail-send/lib/setup_doctor.py --config .notion-config.json --probe --from <送信元アドレス>` を直接打てる（この repo 相対パスは clone 済みのときのみ有効。marketplace install では作業フォルダに `plugins/` が無い）。実体は `gate_g1_auth(..., probe_api=True)`。

各検査は `{"gate","passed","reason","action","detail"}` を返し、未充足は `action="gcp_setup"`（GCP 手順へ誘導）/ `keychain_setup`（鍵登録へ誘導）になる。1つでも `passed=False` なら orchestrator は送信フェーズへ進めない。

## 未設定時の典型エラーと対処

| reason（G1 が返す） | 状態 | 対処 |
|---|---|---|
| `google-auth が未導入`（`GmailUnavailable`） | 実行環境に `google-auth` が無い | `pip install google-auth` 後に再実行 |
| `notion_key_missing` | Notion API 鍵が Keychain に無い | `notion-api-key.<keychain-prefix>` を Keychain 登録 |
| `sa_keychain_unconfigured` | config に `sender.sa_keychain.service` 未設定 | `.notion-config.json` に service を記入 |
| `sa_key_missing` | 指定 service の SA 鍵が Keychain に無い | `security add-generic-password` で SA鍵を登録 |
| `dwd_or_lib_unavailable`（`creds.refresh` 失敗） | DWD 未承認 / scope 不足 / 反映待ち / 鍵不正 | 正本 STEP 11 で gmail.send + gmail.settings.basic を承認。反映を最大1時間待つ |
| `from_alias_unverified` | From が impersonate でも accepted alias でもない | From を impersonate 対象に合わせる、または alias を accepted にする |

SA鍵が JSON でない / `type != service_account` の場合は `secrets.get_google_sa_key` が `KeychainError`（秘密値を含めない）を上げる。Keychain に入れた値が鍵 JSON そのものか確認する。

## セキュリティ（§12 準拠）

- 認証は Keychain の Google SA 鍵のみ。**鍵の平文化・ログ出力を禁止**。`secrets.py` は値返却専用で、例外メッセージにも秘密値を出さない。
- DWD は「ドメイン内の任意ユーザーを impersonate できる」状態であり、管理画面で対象を1つに絞る機能はない。よって **impersonate 対象は `sender.impersonate` に明示して運用で固定**し、SA鍵の管理を厳格化する（正本 STEP 12）。鍵が全 mailbox への入口になる前提を忘れない。
- preflight G1 は probe で存在のみ確認し、鍵の実ロードは送信直前に限定する（秘密値を context に載せる窓を最小化）。

## Additional Resources

- `references/setup-guide.md` — Keychain 登録コマンド例 / `.notion-config.json` の sender 設定例 / 実API検証の使い方
- `doc/GCP-Gmail送信設定手順.md` — **設定手順の正本**（Gmail API 有効化 STEP 10 / DWD scope 追記 STEP 11 / 対象アドレス指定 STEP 12）
- `lib/preflight.py` — `gate_g1_auth()` の実装（probe_api で実API検証）
- `lib/setup_doctor.py` — config / Keychain / 送信ログDB ID / Gmail probe の横断診断入口
- `lib/gmail_client.py` — `GMAIL_SCOPES` / `verify_sendas()` / impersonate 資格情報生成
- `lib/secrets.py` — `probe_*()`（存在確認）と `get_google_sa_key()`（値取得）の分離

# skill-intake plugin

harness-creator の前段ヒアリングを **非技術者にも開く** Claude Code plugin。「スキルを作りたい」という曖昧な要望から、本人も言語化できていない真の課題を引き出し、**Markdown 正本 + JSON 副本 + Notion ページ**の3成果物を一括生成します。さらに公開後の追加要望は `/intake-revise` で同一 Notion ページに PATCH 反映できます。

このREADMEは **上から順に手順を実行するだけで導入完了**するよう構成されています。途中スキップせず、各ステップ末尾の **✅ 確認** を必ず通してから次へ進んでください。

---

## Non-Secrets（漏洩可情報）

ヒアリングシートの Notion DB ID は固定出力先として
**`notion-config.fixed.json` に同梱**している。ただしこの固定 DB は **保守者チーム専用** で、
外部の Integration からは書き込めない（403 になる）。外部利用者は自分の DB ID を
**`.notion-config.json` (gitignore対象)** で指定する（手順はステップ 7-1）。
セットアップ手順は **[references/notion-per-repo-setup.md](references/notion-per-repo-setup.md)** 参照（symlink で harness-creator/references/ と共有）。

| 項目 | 値 | 格納場所 | 漏洩可否 |
|---|---|---|---|
| Notion Parent Page ID | 既定は未設定（DB 新規作成時のみ指定） | `.notion-config.json#parent_page` or env `INTAKE_NOTION_PARENT_PAGE_ID`（`notion-config.fixed.json` では空） | OK |
| Notion Database ID | 固定設定 | `notion-config.fixed.json#databases.hearing-sheet.db_id` / 上書きは `.notion-config.json` or env `INTAKE_NOTION_DATABASE_ID` | OK |
| Keychain service 名（既定） | `notion-api-key.<keychain-prefix>` | `.notion-config.json#keychain_service` / env `INTAKE_KEYCHAIN_SERVICE` で上書き可 | OK |
| Keychain account 名（既定） | `harness` | `.notion-config.json#keychain_account` / env `INTAKE_KEYCHAIN_ACCOUNT` で上書き可 | OK |
| Notion-Version ヘッダ | `2022-06-28` | `scripts/notion_http.py` / env `INTAKE_NOTION_VERSION` で上書き可 | OK |

DB ID 解決順: `--database-id` CLI > env `INTAKE_NOTION_DATABASE_ID` > 設定ファイル。
Parent Page ID 解決順: `--parent-page` / `--parent-page-url` CLI > env `INTAKE_NOTION_PARENT_PAGE_ID` > 設定ファイルの `parent_page`（既定の `notion-config.fixed.json` では未設定）。
設定ファイルは **ファイル単位の先勝ち** で 1 つだけ選ばれる: env `NOTION_CONFIG_PATH` の指すファイル > repo-root 直下 `.notion-config.json` > **plugin-root 直下** `.notion-config.json` > 同梱 `notion-config.fixed.json`。
上書き config が見つかった場合は **そのファイルのみが有効** で、不足キーを `notion-config.fixed.json` へキー単位でフォールバックすることは **ない**（上書き config には必要キーをすべて記載する。雛形は `.notion-config.example.json`）。
単独 install で repo-root が無い環境でも、plugin-root 直下の `.notion-config.json` か env で解決できる。

### 機密情報（Keychain のみ）との対比

以下は **絶対にコード/コミット/環境変数/ログに残さない**。Keychain（ローカル）のみで保管:

| 項目 | 格納場所 | 漏洩可否 |
|---|---|---|
| Notion API トークン本体（`secret_xxx...`） | macOS Keychain (service=`notion-api-key.<keychain-prefix>`, account=`<keychain-prefix>`) | **NG** |
| Slack Incoming Webhook URL | macOS Keychain (service=`slack-incoming-webhook`, account=`<keychain-prefix>`) | **NG** |

Non-Secrets は「どの DB か」「どの Keychain エントリか」を指す **ポインタ** であり、機密実体は常に Keychain 側にあります。

---

## 📋 目次

1. [前提条件チェック](#1-前提条件チェック)
2. [Notion 側の準備](#2-notion-側の準備)
3. [macOS Keychain にシークレット登録](#3-macos-keychain-にシークレット登録)
4. [plugin インストール](#4-plugin-インストール)
5. [Claude Code 設定の適用](#5-claude-code-設定の適用)
6. [動作確認テスト](#6-動作確認テスト)
7. [初回ヒアリング実行](#7-初回ヒアリング実行)
8. [既存 intake の再公開・追加修正](#8-既存-intake-の再公開追加修正)
9. [トラブルシューティング](#9-トラブルシューティング)
10. [構成リファレンス](#10-構成リファレンス)

---

## 1. 前提条件チェック

| 項目 | 確認コマンド | 期待値 |
|---|---|---|
| macOS | `uname` | `Darwin` |
| Python 3 (macOS 標準) | `/usr/bin/python3 --version` | `Python 3.9` 以上 |
| Python package | 同梱済み | `vendor/python` の `jinja2` を自動使用。JSON Schema 検証は標準ライブラリ fallback を使用。手動 `pip install` 不要 |
| Claude Code CLI | `claude --version` | バージョン表示 |
| Git | `git --version` | バージョン表示 |
| Node.js + Mermaid CLI（必須） | `mmdc --version` | バージョン表示。図解 PNG 生成に必須で、未導入だと図解 render が exit 3 で停止します |
| Notion アカウント | https://notion.so にログイン可能 | — |

> `mmdc` が未導入の場合: Node.js（https://nodejs.org）を導入後、ターミナルで `npm install -g @mermaid-js/mermaid-cli` を実行し、`mmdc --version` が表示されれば完了です。

✅ **確認**: 上記すべて満たしている（`mmdc --version` がバージョンを表示することを含む）。

---

## 2. Notion 側の準備

### 2-1. Notion Internal Integration を作成

1. https://www.notion.so/profile/integrations → 「**+ New integration**」
2. **Name**: `skill-intake`、**Type**: `Internal`、ワークスペース選択
3. 「**Save**」→「**Internal Integration Secret**」を **コピーして安全な場所にメモ**（実値は README に書き残さない）

✅ **確認**: シークレットを手元にメモした。

### 2-2. Notion データベースを作成

1. 新規ページ → `/database` → `Database - Full page`
2. 名前は「**Skill Intake**」など任意。プロパティは後で `verify_notion_schema.py` が自動補完
3. DB を開き 右上「**...**」→「**Connections**」→ 先ほどの `skill-intake` Integration を Connect

✅ **確認**: データベースに Integration が Connect されている。

### 2-3. データベース ID を取得

```
https://www.notion.so/<workspace>/<32文字の英数字>?v=...
                                   └─ これが Database ID ─┘
```

`?v=` 直前の 32 文字をメモ（実値は README に書き残さない）。

✅ **確認**: 32文字の Database ID を手元にメモした。

### 2-4. (任意) Slack 公開通知

公開成功時に Slack 通知を受け取りたい場合のみ:

1. https://api.slack.com/apps → 「**Create New App**」→「**From scratch**」
2. App name: `skill-intake-notifier`
3. 左メニュー「**Incoming Webhooks**」→ ON → 「**Add New Webhook to Workspace**」
4. 通知先チャンネルを選び「**Allow**」→ Webhook URL をメモ

✅ **確認**: Slack を使わない場合はスキップしてOK（自動で no-op）。

---

## 3. macOS Keychain にシークレット登録

**重要**: シークレットは Keychain にのみ保管します。`.env`・コード・コミット履歴・環境変数には絶対に置きません。

### 3-1. Notion PAT を登録

```bash
security add-generic-password \
  -s notion-api-key.<keychain-prefix> \
  -a <keychain-prefix> \
  -T '' -U
```

プロンプトに **2-1 でメモした Notion Integration Secret** を貼り付けて Enter（画面には表示されません）。

### 3-2. (任意) Slack Webhook を登録

```bash
security add-generic-password \
  -s slack-incoming-webhook \
  -a <keychain-prefix> \
  -T '' -U
```

プロンプトに Webhook URL を貼り付けて Enter。

### 3-3. 取得テスト

Claude Code のチャットで次のように頼みます（plugin インストール前の場合は、ステップ 4 完了後に §6-1 で確認すれば OK です）:

```
skill-intake の Keychain 取得テスト（keychain_get_secret.py --check）を実行して
```

→ `OK: トークン取得成功` が出れば成功（トークン本体は表示されません）。

> clone 開発者向け: repo-root の端末から `python3 plugins/skill-intake/scripts/keychain_get_secret.py --check` を直接実行しても確認できます。単独 install では `${CLAUDE_PLUGIN_ROOT}` が端末シェルでは解決されないため、端末からの直接実行はできません。

✅ **確認**: Notion トークンが Keychain から取得できる（後回しにした場合は §6-1 で確認）。

---

## 4. plugin インストール

3つの方式があります。**A方式（Marketplace経由）が推奨**です。

> **単独インストールについて**: 本 plugin は `skill-intake` のみを単独 install しても、
> **ヒアリング → Markdown/JSON 生成 → 指定 Notion ページへの publish というコアフローが
> 自己完結して動作**します（共有ローダ `notion_config.py` を vendoring 同梱）。
> Python runtime 依存も plugin 配下 `vendor/` に同梱され、`.claude-plugin/plugin.json`
> の `package.include` で `vendor/**` を配布対象として明示しています。
> Notion publish には DB ID と Keychain token が必要です。同梱の固定ヒアリングシート DB
> (`notion-config.fixed.json`) は保守者チーム専用のため、外部利用者は自分の DB ID を
> `.notion-config.json` か env (`NOTION_CONFIG_PATH` / `INTAKE_NOTION_DATABASE_ID`) で指定します
> （セットアップは [references/notion-per-repo-setup.md](references/notion-per-repo-setup.md) §1 の単独 install 既定経路）。
> drift 検証 lint / sync 等は repo 保守者専用で、単独 install には不要・未同梱です。
> 移行計画等の保守者専用資材（migration-plan-v2.md / RENAME_PLAN.md / v1→v2 変換系スクリプト）も
> `package.exclude` により配布から除外済みです。
> ただし改善要望投入 `/run-skill-feedback`、および生成した intake.json を Skill 本体生成へ流す
> `run-skill-create` は、いずれも **harness-creator が提供する機能**です。harness-creator は
> **配布対象外（`distributable: false`）** で marketplace から install できないため、これらは
> **repo を clone した開発環境でのみ**利用できます（skill-intake のコアフロー = ヒアリング →
> Markdown/JSON 生成 → Notion publish には不要）。つまり skill-intake が生成した brief
> （intake.json）の**消費先である harness-creator は配布されず、clone 環境で消費**します。
> なお `harness-intake` bundle は skill-intake + skill-governance-secrets のみで、harness-creator は含みません。

### 方式A: GitHub Marketplace から install（推奨）

Claude Code セッション内で:

```
/plugin marketplace add OWNER/harness
/plugin install skill-intake@harness
```

これで agents/commands/hooks/skills すべて自動有効化されます。

インストール後の vendor 配布確認は、Claude Code のチャットで次のように頼みます:

```
skill-intake の vendor 配布確認（validate-plugin-vendor.py）を実行して
```

期待値: `"ok": true`。この検査は `vendor/python` の `jinja2` / `markupsafe` /
`typing_extensions` と標準ライブラリ schema fallback を、site-packages に頼らず確認します。

> clone 開発者向け: repo-root の端末から `python3 plugins/skill-intake/scripts/validate-plugin-vendor.py` でも実行できます（単独 install では `${CLAUDE_PLUGIN_ROOT}` が端末シェルでは解決されないため、端末からの直接実行は不可）。

### 方式B: ローカル開発（clone してそのまま使う）

```bash
git clone https://github.com/OWNER/harness.git
cd harness
claude
```

Claude Code 起動後:

```
/plugin marketplace add ./
/plugin install skill-intake@harness
```

### 方式C: symlink で連結（既に worktree 内で開発中）

このリポジトリ内で開発作業をしている場合、`.claude/` 配下に既に symlink が貼られています。追加作業不要で `/intake` などが使えます。

新規 worktree でセットアップする場合は:

```bash
cd .claude/skills && \
  for d in ../../plugins/skill-intake/skills/*/; do ln -sfn "$d" "$(basename $d)"; done && \
cd ../agents && \
  for f in ../../plugins/skill-intake/agents/skill-intake-*.md; do ln -sfn "$f" "$(basename $f)"; done && \
cd ../commands && \
  for f in ../../plugins/skill-intake/commands/*.md; do ln -sfn "$f" "$(basename $f)"; done
```

✅ **確認**: `/help` で `/intake`・`/intake-publish`・`/intake-revise`・`/intake-status` が表示される。

---

## 5. Claude Code 設定の適用

### 5-1. 環境変数（任意・上書き用）

**通常運用では `.notion-config.json` を使います。** env は CI/staging などの明示上書き用です。`schema.json` の `database_id_default` にはフォールバックしません。

env による override は **CI/staging 限定の用途**:

```bash
# 任意（CI/staging 限定）
# export INTAKE_NOTION_DATABASE_ID="<別環境の 32文字 Database ID>"
# export INTAKE_KEYCHAIN_SERVICE="notion-api-key.<keychain-prefix>"      # 既定値そのまま
# export INTAKE_KEYCHAIN_ACCOUNT="harness"        # 既定値そのまま
# export INTAKE_NOTION_VERSION="2022-06-28"            # 既定値そのまま
# export INTAKE_ALLOW_ENV_TOKEN=1                      # CI/dry-run で NOTION_TOKEN を許可する場合のみ
```

### 5-2. permissions.deny を有効化（二段防御）

Keychain への `security` コマンド直叩きを禁止します（Claude が誤ってシークレットを読み出すのを防止）。

`~/.claude/settings.json` または プロジェクトの `.claude/settings.json` に **以下のキーをそのままマージ**します（このスニペットが正本です。ファイルが無ければ以下の内容で新規作成）:

```json
{
  "permissions": {
    "deny": [
      "Bash(security find-generic-password:*)",
      "Bash(security add-generic-password:*)"
    ]
  }
}
```

> 💡 **なぜ deny するの？**: Notion トークンや Slack Webhook の取得は `scripts/keychain_get_secret.py` 経由のみに集約する設計です。Bash 経路を塞ぎ、シークレットがログ/履歴に漏れる経路を物理的に排除します。

✅ **確認**: `cat ~/.claude/settings.json | grep -A2 deny` で `security` 行が存在する。

---

## 6. 動作確認テスト

各テストは **Claude Code のチャットで依頼するのが一次手段**です。

> clone 開発者向け: 各テストの `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/...` コマンドは repo-root の端末からも直接実行できます（単独 install では `${CLAUDE_PLUGIN_ROOT}` が端末シェルでは解決されないため、端末からの直接実行は不可）。

### 6-1. Keychain 取得

Claude Code のチャットで:

```
skill-intake の Keychain 取得テスト（keychain_get_secret.py --check）を実行して
```

→ `OK: トークン取得成功`。`exit 44` ならステップ3に戻る。

> clone 開発者向け直接実行: `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/keychain_get_secret.py --check`

### 6-2. Notion DB スキーマ検証

Claude Code のチャットで:

```
skill-intake の verify_notion_schema.py を --database-id <2-3 でメモした 32文字 ID> --on-conflict skip-warn で実行して
```

→ 200 OK + プロパティ列挙が出れば成功。403 なら 2-2 の Connections を見直し。

> clone 開発者向け直接実行: `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/verify_notion_schema.py --database-id "<32文字 ID>" --on-conflict skip-warn`

### 6-3. Slack hook テスト（任意）

Claude Code のチャットで:

```
skill-intake の keychain_get_secret.py を --service slack-incoming-webhook --account <keychain-prefix> --check で実行して
```

→ `OK` なら Slack 通知も自動で有効。`exit 44` でも公開フローは silent skip で続行。

> clone 開発者向け直接実行: `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/keychain_get_secret.py --service slack-incoming-webhook --account <keychain-prefix> --check`

### 6-4. 実接続 publish smoke（検証用ページのみ）

まずは非 mutation で、実行されるコマンドだけを確認します。Claude Code のチャットで:

```
skill-intake の smoke_notion_publish.py を --hint <output-hint> --page-url <検証用ページURL> で実行して（--execute は付けない）
```

実際に検証用ページへ PATCH 更新する場合だけ `--execute` を付けて依頼します。本番ページでは実行しないでください。

> clone 開発者向け直接実行: `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/smoke_notion_publish.py --hint "<output-hint>" --page-url "https://www.notion.so/<検証用ページURL>" [--execute]`

この smoke は新規ページを作成しません。`--page-url` / `--page-id` が無ければ exit 2、page_id が解決できなければ下位 pipeline が exit 51 で停止します。

✅ **確認**: 6-1, 6-2 が成功した。Slack 利用者は 6-3 も成功した。配布前は検証用ページで 6-4 の `--execute` を 1 回通す。

---

## 7. 初回ヒアリング実行

### 7-1. 出力先 DB を `.notion-config.json` に設定（必須）

同梱の既定 DB（`notion-config.fixed.json` のヒアリングシート DB）は **保守者チーム専用**で、あなたが 2-1 で作成した Integration からは書き込めません（そのまま実行すると 403 になります）。**2-3 でメモした Database ID を `.notion-config.json` に設定してから**次へ進んでください。

一番かんたんな方法は、Claude Code のチャットで次のように頼むことです:

```
.notion-config.json を作って。skill-intake 用で、databases.hearing-sheet.db_id は <2-3 でメモした 32文字の ID> にして
```

手で作る場合は、以下の内容で `.notion-config.json` を作成します（同梱の `.notion-config.example.json` が雛形。上書き config はファイル単位で有効になるため、必要キーをすべて記載します）:

```json
{
  "keychain_service": "notion-api-key.<keychain-prefix>",
  "keychain_account": "<keychain-prefix>",
  "databases": {
    "hearing-sheet": {
      "db_id": "<2-3 でメモした 32文字の Database ID>"
    }
  }
}
```

置き場所:

- repo を clone して作業している場合: **repo-root 直下**
- plugin を単独 install した場合: **Claude Code を起動する作業フォルダ直下**（解決されない場合は env `NOTION_CONFIG_PATH=<ファイルの絶対パス>` で明示できます）

✅ **確認**: Claude Code のチャットで「skill-intake の validate-notion-ready.py を実行して」と頼み、`OK Notion ready ...` が表示され、`database=` に自分の DB ID が出る。

### 7-2. ヒアリング起動

Claude Code セッション内で:

```
/intake デイリーレポート生成スキルを作りたい
```

既存 Notion ページへ必ず出力する場合:

```
/intake デイリーレポート生成スキルを作りたい --page-url https://www.notion.so/...
```

`--page-url` / `--page-id` を指定した場合、publish は update 専用になり、新規ページ作成へフォールバックしない。

メイン orchestrator は `run-skill-intake` skill。以下の **11 phase** を `workflow-manifest.json` 順に実行:

| Phase | SubAgent / 補助 skill | 役割 |
|---|---|---|
| 1 | `run-intake-kickoff` | パターン・深度・痛点 3 軸確定 |
| 2 | `skill-intake-assumption-challenger` | 表層要望を仮説扱い・対立案提示 |
| 3 | `skill-intake-user-profiler` | 熟練度・語彙 tier 推定 |
| 4 | `run-intake-interview` | 5 軸ヒアリング（最大 5 往復） |
| 5 | `skill-intake-purpose-excavator` | 抽象回答の深掘り |
| 6 | `run-intake-option-catalog` | 外部連携カタログ提示 |
| 7 | `run-intake-visualize` | Mermaid / SVG 図解配置 |
| 8 | `skill-intake-summarizer` | Gate A サマリ → 承認依頼 |
| 9 | `run-intake-finalize` | intake.md + intake.json + quality_gate + cross_check |
| 10 | `run-notion-intake-publish` | Notion REST API で指定ページへ PATCH。create fallback 禁止 |
| 11 | `run-intake-next-action` | Notion 公開完了後に引き渡しモード A/B/C/D/E/P 判定（P は plugin 規模案件を `run-plugin-dev-plan` へ引き渡し） |

完了後 `output/<hint>/` に生成されるファイル:

| ファイル | 用途 |
|---|---|
| `intake.md` | 人間向けヒアリングシート（正本） |
| `intake.json` | harness-creator 入力用 |
| `notion-url.txt` | 公開済み Notion ページ URL |
| `notion-manifest.json` | アセット SHA-256 マニフェスト |
| `notion-blocks.json` | publisher 中間生成物 |
| `self-update.json` | question-bank 更新証跡 |
| `internal-analysis.json` | ユーザー意図の内部解析（非表示） |

---

## 8. 既存 intake の再公開・追加修正

### 8-1. 再公開のみ（内容変更なし）

```
/intake-publish <hint>
/intake-publish <hint> --page-url https://www.notion.so/...
```

`run-notion-intake-publish` skill が `scripts/intake_publish_pipeline.py` を **単一発火点**として呼ぶ。render / fidelity guard / quality_gate / publish の重複実装はない。再公開は update 専用で、出力先 page_id 解決順は `--page-id` > `--page-url` > `notion-url.txt` > `notion-publish-result.json`。解決不能時は exit 51 で停止し、新規ページへフォールバックしない。

### 8-2. 追加要望・改善を反映（PATCH 更新）

```
/intake-revise <hint>          # 通常実行
/intake-revise <hint> --dry-run # Notion API を呼ばず差分だけ表示
```

フロー: 既存読み込み → AskUserQuestion で差分聴取 → `analyze_user_intent.py` 再解析 → 差分プレビュー → **Gate R**（`apply` / `re-revise` / `cancel`） → `intake_publish_pipeline.py --revise --page-id ...` で **同一 Notion ページを PATCH 更新**（新規ページ作成しない）。

- 最大 5 revision まで（超過時 exit 60、新規 hint で `/intake` 推奨）
- 失敗時はロールバック JSON を `output/<hint>/notion-rollback-<rev>.json` に保存
- `output/<hint>/revision-log.jsonl` に毎回追記

### 8-3. 進行状況の確認

```
/intake-status [<hint>]
```

---

## 9. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `/intake` が表示されない | plugin 未認識 | ステップ4の方式A/B/Cを再実施 |
| `exit 44` Keychain | トークン未登録 | ステップ3を再実施 |
| 403 Forbidden (Notion API) | DB に Integration 未 Connect / 既定の固定 DB（保守者チーム専用）のまま実行 | ステップ2-2 Connections 追加。既定の固定 DB のまま実行した場合は、自分で作成した DB の ID を `.notion-config.json` に設定（ステップ7-1） |
| `database_id is required` | `.notion-config.json` / `INTAKE_NOTION_DATABASE_ID` / `--database-id` が未設定 | 通常は `.notion-config.json` に `databases.hearing-sheet.db_id` を設定。CI/staging では env を明示 export |
| Slack 通知が来ない | Webhook 未登録 or URL 誤り | ステップ3-2 で再登録。silent skip 仕様のため公開は止まらない |
| `security` コマンドが Bash で拒否 | 二段防御が効いている | 正常。`scripts/keychain_get_secret.py` 経由でアクセス |
| `halted_score_decline` | 値実現スコア2回連続低下 | `output/<hint>/question-bank.snapshot.md` から `--rollback` |
| `halted_capacity` | question-bank が 3000 行超過 | 質問銀行を手動で精査・整理 |
| 図解 render が exit 3 で停止 | `mmdc` (Mermaid CLI) 未導入（fail-fast 仕様） | Node.js 導入後 `npm install -g @mermaid-js/mermaid-cli`（§1 前提条件）。`--allow-placeholder` は CI 専用のため通常利用では使わない |
| Notion ページ作成中に PNG が欠落 | `verify_notion_assets.py` の All-or-Nothing 停止。根本原因が `mmdc` 未導入のケースあり | `mmdc --version` を確認し、未導入なら Node.js 導入後 `npm install -g @mermaid-js/mermaid-cli`。その後 `assets/` 配下の Mermaid/SVG 生成を再実行 |
| `/intake-revise` / `/intake-publish` exit 51 | 指定 page_id / notion-url.txt / result file から更新先を解決できない、または不一致 | `--page-url` / `--page-id` を明示して再実行。意図的に新規作成する場合だけ新規 hint で `/intake` |
| `/intake-revise` exit 60 | revision 5 回超過 | 新規 hint へ移行 |

詳細: [`hooks/README.md`](hooks/README.md) / [`scripts/README.md`](scripts/README.md) / [`references/failure-modes.md`](references/failure-modes.md)

---

## 10. 構成リファレンス

### ディレクトリ構造

```
plugins/skill-intake/
├── .claude-plugin/plugin.json         # plugin メタデータ + hooks 配線
├── commands/                          # スラッシュコマンド (4個)
│   ├── intake.md                      # /intake [topic]
│   ├── intake-publish.md              # /intake-publish <hint>
│   ├── intake-revise.md               # /intake-revise <hint> [--dry-run]
│   └── intake-status.md               # /intake-status [<hint>]
├── agents/                            # SubAgent (4個) — assumption-challenger / user-profiler / purpose-excavator / summarizer
├── references/                        # 共有 references — 旧 aggregator から移設した SSOT 正本
├── assets/                            # Mermaid 12 + samples 8 + SVG 8 カタログ (28本) — 旧 aggregator から移設
├── schemas/                           # handoff / findings / intake-final (3本) — 旧 aggregator から移設
├── hooks/                             # PreToolUse / PostToolUse / Stop / SessionEnd / 手動 (5本 + README)
│   ├── hook-guard-skillgen.py         # intake 実行中の skill 生成を exit 2 で 100% ブロック
│   ├── pre-publish-secret-scrub.sh    # 公開前 secret 走査 (exit 2 でブロック)
│   ├── pre-publish-schema-validate.py # 公開前スキーマ検証
│   ├── post-publish-notify.sh         # Slack 通知 (任意, silent skip)
│   ├── post-keychain-add.sh           # Keychain 登録直後の検証 (手動)
│   └── README.md
├── scripts/                           # 共有スクリプト (Python 3.9+、vendor/python を自動使用)
│   ├── keychain_get_secret.py         # Keychain アクセスの唯一経路
│   ├── notion_http.py                 # Notion REST wrapper
│   ├── intake_publish_pipeline.py     # publish/republish/revise の単一発火点
│   ├── analyze_user_intent.py         # /intake-revise の意図解析
│   ├── render-intake-final.py / render_notion_page.py
│   ├── verify_notion_schema.py / verify_notion_assets.py
│   ├── validate_intake.py / quality_gate.py / cross_check.py
│   ├── select_diagram_type.py / compose_diagram.py / validate_mermaid.py
│   ├── render_to_svg.py / render_to_image.py / enforce_visualization_rules.py
│   ├── update_question_bank.py        # question-bank パッチ (--apply / --rollback)
│   ├── append_eval_log.py / measure_value_realized.py
│   ├── ci_dogfooding_retest.py / dogfooding_regression.py
│   ├── notion_limits.json
│   └── README.md                      # 全スクリプトの責務一覧
├── vendor/                            # plugin install に同梱される Python runtime 依存
│   ├── python/jinja2/
│   ├── python/markupsafe/
│   └── python/typing_extensions.py
├── fixtures/                          # テスト用例データ (4ディレクトリ)
│   ├── example-data-quality-survey/   # 例: データ品質調査
│   ├── example-team-onboarding/       # 例: チームオンボーディング
│   ├── info-collector-agent/          # SubAgent プロンプト検証用
│   └── intake-final-smoke/            # 最終版 render の smoke test
└── skills/                            # スキル (10個)
    ├── run-skill-intake/              # **メイン orchestrator** (11 phase)
    ├── run-intake-kickoff/            # Phase 1 補助
    ├── run-intake-interview/          # Phase 4 補助
    ├── run-intake-option-catalog/     # Phase 6 補助
    ├── run-intake-visualize/          # Phase 7 補助
    ├── run-intake-finalize/           # Phase 9 補助 (統合 + quality_gate)
    ├── run-intake-next-action/        # Phase 11 決定論 (公開後の引き渡しモード判定)
    ├── run-notion-intake-publish/     # 初回 publish (P10 委譲) + 再公開 (intake_publish_pipeline.py の薄い wrapper)
    ├── assign-notion-fidelity-evaluator/     # Notion 公開前粒度検証
    └── run-intake-revise/             # 追加要望 PATCH 反映 (Gate R + revision-log)
```

### コマンド一覧

| コマンド | 用途 | 引数 |
|---|---|---|
| `/intake` | 新規ヒアリング起動（11 phase / 4 SubAgent） | `[topic]` |
| `/intake-publish` | 既存 intake の再公開（内容変更なし） | `<hint>` |
| `/intake-revise` | 追加要望を Notion ページに PATCH 反映 | `<hint> [--dry-run]` |
| `/intake-status` | 進行状況（phase / 5 軸充足 / 図解枚数） | `[<hint>]` |

### Hooks 配線

| イベント | 実行 hook | 役割 |
|---|---|---|
| PreToolUse (Skill\|Task\|Bash) / PostToolUse (Skill) / Stop / SessionEnd | `hook-guard-skillgen.py` | intake 実行中の skill 生成 (`run-skill-create` / `run-build-skill` 等) を exit 2 で 100% ブロック。lock は `run-skill-intake` 開始で作成し、正常終了 / SessionEnd / TTL で解除 |
| PreToolUse (Bash) | `pre-publish-secret-scrub.sh` | `output/` 配下を走査し Notion PAT / Bearer / 汎用キー混入を検知 (exit 2 でブロック) |
| PreToolUse (Bash) | `pre-publish-schema-validate.py` | intake/notion-blocks の JSON Schema 検証 |
| PostToolUse (Bash) | `post-publish-notify.sh` | Notion 公開成功後に Slack webhook 送信（opt-in） |

### 既存スキルとの差分

| Skill | 対象 | 図解 | Notion 公開 |
|---|---|---|---|
| `run-skill-elicit` (harness-creator plugin) | 技術者 | ❌ | ❌ |
| **`run-skill-intake`** (本 plugin) | **非技術者対応** | ✅ Mermaid 12+SVG 8 | ✅ Keychain × REST API |
| `run-skill-create` (harness-creator plugin) | スキル本体生成 | — | — |

`run-skill-create` から Step 1 を呼ぶ際、ヒアリング対象が非技術者なら本 plugin の `run-skill-intake` を起動。

### 環境変数一覧

| 変数 | 既定値 | 必須 | 用途 |
|---|---|---|---|
| `INTAKE_NOTION_PARENT_PAGE_ID` | なし（既定の fixed config では未設定） | 任意 | DB 新規作成時の親 Notion ページ ID。既定の `notion-config.fixed.json` では空のため、DB を新規作成する場合は `.notion-config.json#parent_page` で自分のページ ID を指定必須（env はその上書き用） |
| `INTAKE_NOTION_DATABASE_ID` | `notion-config.fixed.json` | 任意（CI/staging のみ） | Notion DB ID (32文字)。固定ヒアリングシートDBを上書きする場合のみ使用 |
| `NOTION_CONFIG_PATH` | なし | 任意 | `.notion-config.json` の明示パス。存在しない場合は fail-closed |
| `INTAKE_ALLOW_ENV_TOKEN` | なし | 任意（CI/dry-run のみ） | `1` のときだけ `NOTION_TOKEN` fallback を許可 |
| `INTAKE_KEYCHAIN_SERVICE` | `notion-api-key.<keychain-prefix>` | 任意 | Keychain service 名 |
| `INTAKE_KEYCHAIN_ACCOUNT` | `harness` | 任意 | Keychain account 名 |
| `INTAKE_NOTION_VERSION` | `2022-06-28` | 任意 | Notion-Version ヘッダ |

### eval-log 集計

`/intake` 実行ごとに `eval-log/skill-intake/<YYYY-MM-DD>.jsonl` に1行追記（value_realized_score / sections_count / questions_added / status）。横串集計用。記録仕様の詳細は `scripts/append_eval_log.py` の docstring を参照。集計は repo 保守者専用で、単独 install では対象外です（`eval-log/` は配布に含まれません）。

### Skill design 原則

1. **Problem First** — 表層要望を仮説扱いし、本質的問題を最優先で発掘
2. **Structure-Reduces-Drift** — 「言語化されているのは1割」を前提に、問い構造で誤り訂正
3. **Script First** — 決定論処理はすべて `scripts/*.py`、LLM 判断は補助
4. **Single Publication Entry** — publish/republish/revise はすべて `intake_publish_pipeline.py` 経由
5. **Visualization Mandatory** — 全セクションに 1〜3 図、非エンジニア対応マスト 8 ルール強制
6. **Self-Evolving** — question-bank がヒアリング毎に成長（連続低下時は自動 halt）
7. **Secret-Out-of-Repo** — シークレットは Keychain のみ。`.env`/環境変数/コード禁止
8. **5 軸必須** — 出力先・情報源・共有相手・真の課題・ナレッジ資産
9. **All-or-Nothing 公開** — PNG 1 枚でも欠けたら停止

---

## ライセンス・所有

- **owner**: team-platform
- **since**: 2026-05-22
- **version**: 0.1.2

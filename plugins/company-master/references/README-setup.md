# company-master プラグイン セットアップ手順 (build / backfill 共通)

本スキルは **gBizINFO API** (法人番号・正式名称・所在地の公的取得) と **Notion API** (企業マスタ DB への書き込み) を使う。API トークンは **macOS Keychain** に保管し、生値を端末・ファイルに出さない。以下を**一度だけ**実施すればよい。

> このスキルは **Python 標準ライブラリだけで動作**する (`pip install` 一切不要)。
> Keychain 命名規約 (本 plugin):
> - Notion API token: **service = `notion-api-key.<keychain-prefix>`**, **account = `<keychain-prefix>`**
> - gBizINFO API token: **service = `gbizinfo-api-token.<keychain-prefix>`**, **account = `<keychain-prefix>`**
> - 日本郵便 郵便番号API (郵便番号取得を使う場合): **service = `japanpost-da-api.<keychain-prefix>`** の1サービスに複数 account をぶら下げる方式 — 郵便番号自動取得を有効にする場合のみ **account = `client_id` / `secret_key`** が必要、**`egress_ip`** は固定IP回線なら推奨で pin。未設定でも他項目は動き、郵便番号だけ空欄 + 備考に縮退する。テスト stub は `base_url`、例外のプロキシ運用時のみ `proxy_url` / `proxy_token`。詳細・取得手順は [`japanpost-api-setup.md`](japanpost-api-setup.md)、ロール別の登録は [`keychain-setup.md`](keychain-setup.md)。
>   - 当チームの郵便番号取得は **BYO 直結が既定**(各メンバーが自分の for Biz 鍵+送信元IPを持つ)。送信元IPを固定できないメンバーだけ例外的に中央プロキシ。

> **パスについて(install 済みプラグインで使う場合・必読)**: 本書のコマンド例のうち `python3 plugins/company-master/scripts/...` という **repo 相対パス**は、**このリポジトリを clone してそのフォルダから実行する開発者向け**の書き方。マーケットプレイスから install して使う通常の利用者は、これらを**手打ちせず** Code タブで「**doctor を実行して**」「**会社を調べて**」のように日本語で頼む(プラグインが `$CLAUDE_PLUGIN_ROOT` 配下の正しいパスで実行する。背景は [`japanpost-api-setup.md`](japanpost-api-setup.md) ⑥ と共通)。`security add-generic-password` / `find-generic-password` 系は **パス非依存**なのでどちらの利用者もそのまま使える。

---

## 1. Notion API トークンを Keychain に登録

```bash
security add-generic-password \
  -s notion-api-key.<keychain-prefix> \
  -a <keychain-prefix> \
  -w "<NOTION_INTEGRATION_TOKEN>" \
  -U
```

> 出力先 DB (既定は `notion-config.fixed.json` の `databases.company-master.db_id`) に、この Notion integration を「接続」しておくこと (Notion 側 DB の Connections に追加)。
> DB ID を上書きしたい場合は env `COMPANY_MASTER_NOTION_DATABASE_ID` か、repo/plugin-root の `.notion-config.json` を用意する (解決順は SKILL.md「目的と出力契約」)。

## 2. gBizINFO API トークンを Keychain に登録

```bash
security add-generic-password \
  -s gbizinfo-api-token.<keychain-prefix> \
  -a <keychain-prefix> \
  -w "<GBIZINFO_API_TOKEN>" \
  -U
```

> gBizINFO トークンは [gBizINFO の API 利用申請](https://info.gbiz.go.jp/) で取得する。リクエストヘッダ `X-hojinInfo-api-token` で送信される。env への平文保持は許可しない (公的 API キーの取り扱い厳格化)。

> 更新: 同じ `add-generic-password ... -U` を再実行すれば上書きされる。
> 削除: `security delete-generic-password -s <service> -a <keychain-prefix>` (ただし下記ハードニング適用後は deny される)。

## 3. settings-hardening.json をマージ (二段防御の静的層)

plugin は repo の `.claude/settings.json` を直接配布・上書きできないため、機密流出系コマンドの `permissions.deny` は `references/settings-hardening.json` として同梱配布している。これを利用者が手動でマージして静的層を有効化する。

通常は Code タブで「**company-master の安全設定(settings-hardening)を適用して**」と頼めば、プラグインが下記を `$CLAUDE_PLUGIN_ROOT` 配下から読み取りマージ手順を案内する(手動でパスを探す必要なし)。中身を自分で確認したい場合:

```bash
# install 済みプラグインなら(clone 不要):
cat "$CLAUDE_PLUGIN_ROOT/references/settings-hardening.json"
# このリポジトリを clone 済みの開発者なら:
cat plugins/company-master/references/settings-hardening.json

# 既存 .claude/settings.json があるなら、その permissions.deny 配列へ
# settings-hardening.json の permissions.deny 10 エントリを追記する (重複は除く)。
# settings.json が無ければ {"permissions":{"deny":[...]}} を新規作成する。
```

これにより、3鍵 (`notion-api-key.<keychain-prefix>` / `gbizinfo-api-token.<keychain-prefix>` / `japanpost-da-api.<keychain-prefix>`) の平文出力 (`find-generic-password ... -w` / `-g` / `--print-unsafe`) と誤削除 (`delete-generic-password`) が静的に deny される。防御は動的層 (`hooks/hook-guard-secret.py`, plugin.json 配線・fail-closed) が単独で完結し、静的層マージは深層防御の追加層として推奨。

## 4. 実行 (`--upsert` 有無で挙動が変わる)

```bash
# resolve + enrich のみ (Notion へは書き込まない。出力 JSON に upsert: "skipped" /
# upsert_skip_reason: "--upsert未指定のため書き込みスキップ" を含む)
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/company-master}/scripts/company_master.py" --hojin-bango <13桁法人番号>

# 検証 PASS 時に Notion へ書き込む
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/company-master}/scripts/company_master.py" --name "<会社名>" --address "<住所>" --upsert

# Notion 既存行の空欄を backfill (--dry-run で副作用抑止)
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/company-master}/scripts/company_master.py" backfill --dry-run
```

> `--upsert` 未指定時は resolve/enrich のみ実行し、Notion 書き込みはスキップする (出力 JSON の `upsert_skip_reason` に理由が入る)。
> resolve 未確定 (entity 不在) や検証エラー時も `upsert_skip_reason` でスキップ理由が明示される。

---

## トラブルシュート

| 症状 | 原因 / 対処 |
|---|---|
| `gBizINFO トークン不在` で exit 2 | 手順2未実施 / service・account 名の綴り違い |
| Notion 401/403 | 手順1のトークン誤り、または DB に integration 未接続 |
| `BLOCKED: ... find-generic-password -w` | 手順3のハードニング (または動的 hook) が機密の平文出力を阻止 (正常動作)。トークンは `notion_config.get_token` 経由でメモリ上のみ取得すること |
| DB ID を変えたい | env `COMPANY_MASTER_NOTION_DATABASE_ID` か `.notion-config.json` を用意 (fixed.json は最下位フォールバック) |

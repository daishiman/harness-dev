# Notion スキーマ SSOT

xl-skills のプラグイン量産フローを Notion 上の 3 DB と連動させるための schema-as-code 定義。
**スキーマ構造（properties 定義）は本 repo の SSOT、DB ID は per-repo 設定 (`.notion-config.json`) に分離**。

## 構成

| ファイル | 対応 Notion DB | config key |
|---|---|---|
| `hearing-sheet.schema.json` | Skillヒアリングシート | `hearing-sheet` |
| `skill-list.schema.json` | Skill一覧（プラグイン単位） | `skill-list` |
| `improvement-request.schema.json` | Skill改善要望 | `improvement-request` |

実 DB ID は `<repo-root>/.notion-config.json#databases.<key>.db_id` で解決される。
他リポジトリへの導入手順は **[plugins/harness-creator/references/notion-per-repo-setup.md](../../plugins/harness-creator/references/notion-per-repo-setup.md)** を参照。

## リレーション

```
ヒアリングシート ──(1:1)── スキル一覧 ──(1:N)── 改善要望
   紐づくプラグイン       紐づくヒアリングシート / 改善要望     対象プラグイン
```

- ヒアリングシート 1 件 = プラグイン 1 件
- スキル一覧の行 = プラグイン 1 件（個別 Skill はページ本文に列挙）
- 改善要望は必ず `対象プラグイン` でいずれか 1 プラグインに紐づく

## 反映

```bash
# 差分検知
python3 scripts/sync-notion-schema.py --check

# 適用
python3 scripts/sync-notion-schema.py --apply
```

`.notion-config.json` が未配置の repo では `[notion_config] WARN: ... not found` を出して exit 0 (skip)。
Notion API トークンは env `NOTION_TOKEN` → macOS Keychain (config の `keychain_service`/`keychain_account`) の順で解決。

## 制約メモ

- Notion API は `status` 型プロパティの作成/更新を許可しない（UI のみ）。本スキーマでは進行管理を `select` で表現。
- `dual_property` relation は片側追加で相手側プロパティが自動生成される。スキーマでは正式名のみを定義し、初回適用時に逆プロパティをリネームする。
- `rollup` は対象 relation が存在しないと作成不可。`sync-notion-schema.py` は relation → rollup の順で適用する。

# knowledge-skeleton テンプレート

生成スキルに knowledge/ ディレクトリを追加する際に使用する雛形。

## パターン別使い分け

| パターン | 適用場面 | 使うファイル |
|---------|---------|------------|
| Index-Search型 | ペルソナ再現・固定ナレッジ・テーマ別分類 | `index-search/` 配下 + `scripts/` |
| Router-Registry型 | 継続的な知識同期・外部ファイルからの随時抽出 | `router-registry/` 配下 + `scripts/` |

詳細な選択フロー → `ref-knowledge-loop` スキルの SKILL.md を参照。

## 配置するファイルの索引

### Index-Search型

```
{skill}/knowledge/
├── knowledge-index.json          ← index-search/knowledge/knowledge-index.json を元に生成
└── knowledge-{category}.json     ← index-search/knowledge/knowledge-{{category}}.json を元に生成
{skill}/scripts/
├── search_knowledge.py           ← scripts/search_knowledge.py をコピー
├── build_index.py                ← scripts/build_index.py をコピー
├── record_usage.py               ← scripts/record_usage.py をコピー (§12 活用ログ・分析)
└── add_entry.py                  ← scripts/add_entry.py をコピー (必須6フィールド検証つき追加)
```

### Router-Registry型

```
{skill}/knowledge/
├── router.json                   ← router-registry/knowledge/router.json を元に生成
├── schema.json                   ← router-registry/knowledge/schema.json をコピー
├── registry.json                 ← router-registry/knowledge/registry.json をコピー
└── {category}-{subtopic}.json    ← 手動作成
{skill}/scripts/
├── search_knowledge.py           ← scripts/search_knowledge.py をコピー
├── build_index.py                ← scripts/build_index.py をコピー
├── record_usage.py               ← scripts/record_usage.py をコピー (§12 活用ログ・分析)
└── add_entry.py                  ← scripts/add_entry.py をコピー (必須6フィールド検証つき追加)
```

## 変数の置換ルール

`{{...}}` 変数は生成スキルのコンテキストに応じて実際の値に置換する。

| 変数 | 説明 |
|------|------|
| `{{CATEGORY_ID}}` | カテゴリの英語ID (例: mindset, cases) |
| `{{CATEGORY_LABEL}}` | カテゴリの日本語名 |
| `{{OUTPUT_DIR}}` | 成果物出力先ディレクトリパス |
| `{{YYYY-MM-DD}}` | 作成日 |
| `{{SOURCE_FILE_*}}` | ソース素材のファイルパス |

## lint

```
python3 run-build-skill/scripts/lint-knowledge-loop.py {skill_dir}
python3 run-build-skill/scripts/lint-knowledge-loop.py {skill_dir} --strict
```

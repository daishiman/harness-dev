# 章別 Markdown 構造テンプレート

`scripts/compile-spec-doc.py` が各カテゴリ章 (`system-spec/<category>.md`) を生成する際の決定論構造。
下記は形状の説明であり、実体は compile-spec-doc.py の `render_chapter` が生成する。

## frontmatter (確定マーカー・C11 hook 判定ソース)

```
---
status: confirmed        # 終端カテゴリ (集約=確定/対象外) は confirmed / 進行中 (未着手/収集中) は draft
category: <category-id>  # 章のカテゴリ id (例: database)
aggregate: 確定          # 真理値表導出の集約状態 (未着手/収集中/確定/対象外)
spec_cells: [<category>.web, <category>.mobile, <category>.tablet, <category>.desktop-windows, <category>.desktop-linux, <category>.desktop-macos]
---
```

- `status`: 集約が終端 (確定/対象外) のとき `confirmed`、進行中 (未着手/収集中) のとき `draft`。
- `aggregate`: セル状態から真理値表で再導出 (`category_aggregate` 宣言値を鵜呑みにしない)。
- `spec_cells`: 章が対応する `<category>.<platform>` セル id 一覧 (canonical platform 順)。

## 本文セクション

1. **見出し + 集約サマリ**: `# <label> (<category>)` と集約状態・確定マーカー。
2. **カテゴリ別収集状態** 表: 各 canonical platform の状態 (未収集 / 対象外+理由 / 確定+qa_ref)。

   | プラットフォーム | 状態 | 根拠 |
   |---|---|---|
   | Web (web) | 確定 | 確定質疑: qa-database |
   | ... | 対象外 | 理由: <除外理由> |

3. **設計知識参照**: カテゴリに割り当てた `ref-system-design-knowledge/references/*.md` ポインタ。
4. **最新ドキュメント出典** 表: 割り当てた fetched-references (対象 / version / 公式発行元 (host) / source_url / 取得 / 最新確認)。未割当は index.md の全体出典へ。

## canonical platform 順序 (厳守)

`web, mobile, tablet, desktop-windows, desktop-linux, desktop-macos`

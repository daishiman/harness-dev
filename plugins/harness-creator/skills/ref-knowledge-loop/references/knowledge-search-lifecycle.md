# knowledge/ 検索・ライフサイクル管理ガイド (§7-12)

> 構築編 (§0-6) → [knowledge-construction.md](knowledge-construction.md)
> version: 2.1.0 | ported: 2026-05-24

---

## §7 ファイル分割ルール

| 指標 | 閾値 | アクション |
|------|------|-----------|
| ファイル行数 | 500行超 | サブトピックに分割 |
| エントリ数 | 25件超 | サブトピックに分割を検討 |

**Router-Registry型の分割手順**:
1. 超過ファイルのエントリをテーマ別にグループ化
2. `{category}-{subtopic}.json` として `knowledge/` に作成
3. `router.json` の `routing_rules` と `categories[*].files` を更新
4. 元ファイルは削除し分割後ファイルで管理

**Index-Search型の分割手順**:
1. 超過カテゴリのエントリを新ファイルに分割
2. `knowledge-index.json` の `categories` エントリを更新
3. `build_index.py --fix` でインデックス整合性を確認

---

## §8 ナレッジ進化メカニズム (Router-Registry型)

```
新エントリの tags: ["関係構築", "外交"]
    ↓
router.json の routing_rules を参照
  {category}-relationship.json → tags: ["関係構築", "外交"] → マッチ: 2
  {category}-organization.json → tags: ["組織", "採用"]    → マッチ: 0
    ↓
格納先: {category}-relationship.json (最もマッチ数が多いファイル)
```

エージェントはファイル名をハードコードしない。必ず `router.json` 経由でファイル名を取得する。

---

## §9 3段階検索パイプライン

### 9.1 なぜ全文検索ではダメなのか

| 手法 | 問題点 |
|------|--------|
| 全文検索 | 出現頻度が多いだけで意味的に無関係なエントリが上位に来る |
| 完全一致 | 同義語・言い換えに対応できない |
| 単純キーワード存在チェック | 動詞変化による漏れが生じる |

**正解**: フィールド重み付きスコアリング + AI意味解釈の2層構造

### 9.2 パイプライン仕様

```
Stage 1: カテゴリ絞り込み (スクリプト)
  クエリ → キーワード分解 → global_keywords × カテゴリスコア算出
  → スコア > 0 のカテゴリファイルに絞り込む
  → 全スコア0なら全ファイル対象 (コンテキスト節約)

Stage 2: フィールド重み付きスコアリング (スクリプト)
  絞り込まれた各エントリをスコアリング
  → スコア上位 N 件 (推奨: 3〜7件) を返す
  → 決定論的・高速・100%再現可能

Stage 3: AI意味解釈・上位概念翻訳 (LLM)
  background/intent から普遍的な概念を抽出
  → ユーザーの文脈・業種にマッピング
  → ペルソナ・スタイルゲノムに従って語り口を再現
  → 成果物を生成
```

### 9.3 スコアリング重み表

| フィールド | 重み | 理由 |
|-----------|------|------|
| `title`/`content` への含有 | +5 | ナレッジの核心に直接一致 |
| `keywords`/`tags` への含有 | +3 | 設計者の検索意図 |
| `quote`/`sakamoto_expressions` への含有 | +2 | 実際の言葉レベルでの一致 |
| `sakamoto_voice`/`expression.phrasing` への含有 | +2 | ペルソナ語り口レベルでの一致 |
| その他フィールド (background/message/purpose等) | +1/出現 | 文脈的な関連性 |

`knowledge-index.json` の `scoring_weights` でカスタマイズ可能 (デフォルト: title:5/keywords:3/quote:2/voice:2/fulltext:1)

### 9.4 シノニムマップ (同義語展開)

`knowledge-index.json` に定義:

```json
{
  "synonyms": {
    "採用難": ["人材不足", "採用課題", "リクルーティング困難"],
    "副業": ["兼業", "パラレルワーク", "サイドジョブ"]
  }
}
```

Stage 1 でクエリキーワードをシノニム展開してからスコアリング実行。

### 9.5 重みチューニング手順

1. テストクエリセット5〜10件を作成し「期待する上位3件のエントリID」を定義
2. 現在の重みで全クエリを実行し、期待エントリが上位3件に入るか記録
3. 精度 = 期待通りにヒットしたクエリ数 / 全クエリ数 (目標: 80%以上)
4. 精度が80%未満なら重みを調整して再実行
5. 確定した重みを `knowledge-index.json` の `scoring_weights` に記録

---

## §10 成果物の出力命名規則

```
{output_dir}/output - YYYY-MM-DD - {種別} - {テーマ}.md
```

種別例: 提案書 / 戦略書 / 事例集 / アイデア / 要約 / レポート

出力先は `knowledge-index.json` の `output_dir` または SKILL.md の成果物セクションで定義。
出力前に必ずユーザーに内容を確認してから書き込む。

---

## §11 更新ログ・バージョン管理

`registry.json` エントリの構造:

```json
{
  "path": "{{SOURCE_FILE_PATH}}",
  "source_type": "youtube|markdown|pdf",
  "status": "pending|processed|needs-update|deprecated",
  "file_hash": "sha256hex",
  "file_modified": "YYYY-MM-DD",
  "processed_date": "ISO8601",
  "entries_extracted": 5,
  "extracted_entry_ids": ["cat_015", "cat_016"],
  "target_categories": ["category"]
}
```

**status 遷移**:

| status | 説明 |
|--------|------|
| `pending` | 未処理 (新規検出) |
| `processed` | 処理済み (ナレッジ抽出完了) |
| `needs-update` | ファイルハッシュが変更され再処理が必要 |
| `deprecated` | 古くなった情報。検索対象から除外 |

**廃棄ルール**: 以下の条件を満たすエントリに `status: "deprecated"` + `deprecated_reason` + `deprecated_date` を追加する (物理削除しない)。

- ソース素材が削除・更新されエントリ内容が事実と異なる
- 同一テーマのより正確なエントリが追加された
- 6ヶ月以上、検索でヒットしたが一度も活用されていない (§12 活用ログで検出)

---

## §12 フィードバックループ (品質改善サイクル)

### 12.1 活用ログ形式 (usage-log.jsonl)

```jsonl
{"timestamp":"ISO8601","query":"クエリ文字列","matched_ids":["id1","id2"],"used_ids":["id1"],"satisfaction":"helpful","note":"任意メモ"}
```

| フィールド | 説明 |
|-----------|------|
| `matched_ids` | Stage 2 で上位N件に入ったエントリID |
| `used_ids` | Stage 3 で実際にAIが活用したエントリID |
| `satisfaction` | `helpful` / `neutral` / `unhelpful` |
| `note` | 改善メモ (任意) |

### 12.2 品質改善パターン4種

| パターン | 検出方法 | 改善アクション |
|---------|---------|-------------|
| ヒットするが使われない | matched_ids にあるが used_ids にない | keywords が不適切。title と intent を見直す |
| ヒットしない | テストクエリで期待エントリが上位に入らない | keywords を追加。synonyms マップを更新 |
| 低満足度連続 | `satisfaction: "unhelpful"` が連続 | background と intent の具体性を改善 (§4.3 ルーブリックで再評価) |
| 特定エントリに集中 | 同一IDが全クエリの80%以上でヒット | keywords が汎用的すぎる。差別化を強化 |

`record_usage.py --analyze` でパターンを自動検出する (→ `scripts/record_usage.py`)。

### 12.3 日々のブラッシュアップ運用サイクル

ナレッジは「使うほど良くなる」閉ループで運用する。日次/定期で以下を回す。

```
検索   : python3 scripts/search_knowledge.py "<query>"
  ↓ 活用 (AI が成果物生成に利用)
記録   : python3 scripts/record_usage.py --record   (usage-log.jsonl に追記)
  ↓
分析   : python3 scripts/record_usage.py --analyze --emit-queue <queue>
         (§12.2 の品質改善パターン4種を検出し brushup キューを出力)
  ↓ キューを見て改善 (title/keywords/background を編集 — AI/人の判断)
付与   : python3 scripts/record_usage.py --mark-needs-update <id>
         (再処理が必要なエントリに status: needs-update を付与)
```

新知見の追加は `add_entry.py` で行い、必須6フィールド (§4.2) を検証しつつ追記する (JSON 手編集を排除):

```
python3 scripts/add_entry.py --category <cat> --title ... --background ... --keywords ... --source ...
```

二層分離: 決定論 (スクリプト) が担うのは「検証・追記・status付与・パターン検出」、内容判断 (AI/人) が担うのは「何を改善するか・どう書き換えるか」。スクリプトは正解を機械保証し、意味的判断は委ねない。

この閉ループは雛形 (knowledge-skeleton) ごと生成スキル (Loop A) に同梱されるため、量産された各スキルがそれぞれ自己完結で日々ブラッシュアップ可能になる。

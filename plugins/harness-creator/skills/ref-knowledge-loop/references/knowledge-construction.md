# knowledge/ 構築ガイド (§0a, §0-6)

> 適用範囲: 200エントリ以下の中小規模ナレッジシステム。
> 検索・ライフサイクル管理 → [knowledge-search-lifecycle.md](knowledge-search-lifecycle.md)
> version: 2.1.0 | ported: 2026-05-24

---

## §0a knowledge/ をどこに置くか (配置の抽象階層)

`knowledge/` の配置先には抽象階層が異なる2層がある。両者は排他でなく役割が違う。全ナレッジを1箇所に強制集約しない (死蔵を招く)。各スキルのドメイン知識はそのスキルに、harness-creator のメタ知識は harness-creator に置く。

| 層 | 配置 | 同梱方針 | 用途 |
|----|------|---------|------|
| Loop A (生成物側) | 各生成スキルが自前の `{skill}/knowledge/` + `{skill}/scripts/` を持つ | 正本テンプレを展開 (インスタンス化) して scripts/ を同梱。配布される自己完結ユニット | そのスキルのドメイン知識。これが既定 |
| Loop B (メタ側) | harness-creator 自身の `plugins/harness-creator/knowledge/` に集約 | 正本スクリプトを複製せず `--dir` で共有参照 | harness-creator の build 知見 (メタ知識) |

Loop A は配布単位ごとに自己完結する必要があるためスクリプトを同梱し、Loop B は単一リポジトリ内のメタ蓄積なので正本スクリプトを `--dir` 共有して重複を避ける。

### 判定ルール — 新しい知見をどちらに入れるか

置き場所は「選ぶ」のではなく、知見の**消費者**が一意に決める (`consult_at`)。次の一問で判定する。

```
Q: その知見を読むのは誰か？
  A. 生成スキルが「実行時」にエンドユーザー向けの仕事で使う
     → Loop A: そのスキルの {skill}/knowledge/    (consult_at: ["runtime"])
  B. harness-creator が「ビルド時」にスキルを作る判断で使う
     → Loop B: plugins/harness-creator/knowledge/    (consult_at: ["build-time"])
```

判定軸は「内容のジャンル」ではなく「**誰がいつ読むか**」。各ストアの `knowledge-index.json` は `consult_at` を1つ宣言しており、これが置き場所の機械可読な根拠になる。この分離は **schema の `consult_at` 必須化 + lint KL-007 + add_entry ガード**で機械的に強制される — `consult_at` とストアの物理位置 (Loop A=runtime / Loop B=build-time) が不一致なら CI で fail し、宣言の無いストアへの `add_entry` は拒否される。ドキュメントの努力義務ではなく構造不変条件として固定される。

紛らわしい例: 「採用スキルを作っている最中に得た学び」。
- 採用ドメインの事実で、スキルが実行時にユーザー回答へ使う → Loop A
- 採用系スキルを作る時の手順・勘所 (例: このドメインは style-genome が要る) → Loop B

同じ素材から両方のエントリが生まれることはあるが、**別エントリ・別消費者**として分かれる。1つのエントリが2ストアに重複することはない。`add_entry.py` は抽象バケツでなく `--dir <具体パス>` で対象ストアを明示するため、入れ間違いは物理的に起きにくい。

---

## §0 パターン選択フロー

```
Q1: ナレッジは継続的に追加されるか？
  Yes → Q2: ソース素材が外部ファイルにあるか？
    Yes → Router-Registry型 (パターンB)
    No  → Index-Search型 (パターンA)
  No  → Q3: ペルソナを再現するか？
    Yes → Index-Search型 + style-genome (パターンA + §5)
    No  → references/ 静的ファイルで十分 (knowledge/ 不要)
```

---

## §1 knowledge/ を追加するタイミング (5条件)

| 条件 | 説明 |
|------|------|
| 外部素材依存 | 議事録・動画・教材・会議メモ等を参照して回答する |
| ペルソナ再現 | 特定人物の語り口・思想・表現スタイルを再現する |
| 知識量が多い | カテゴリ別に分類された知識が10件以上ある |
| 継続的蓄積 | 新しい素材が追加されるたびにナレッジが増える |
| 精度優先検索 | キーワード・カテゴリ・IDで的確に検索したい |

---

## §2 2つの実装パターン

### 共通設計原則

1. **索引は軽く、データは重く分離する** — 索引はカテゴリ・キーワードのみ。実データはカテゴリ別ファイルに格納
2. **ファイル名は内容を自己記述する** — 連番禁止。`{category}-{subtopic}.json` 形式
3. **検索は決定論的ステージとAIステージを分離する** — スクリプト→AI の2層

### スケール別推奨構成

| エントリ数 | 推奨 | 検索方式 |
|-----------|------|---------|
| 1〜15 | 必須フィールドのみ | Simple-Lookup (カテゴリ+ID直引き) |
| 16〜100 | 推奨フィールドも追加 | 3段階パイプライン (→検索編 §9) |
| 101〜200 | サブカテゴリ分割必須 | フルパイプライン+重みチューニング |
| 200超 | このガイドの適用範囲外 | 外部検索エンジン推奨 |

### パターンA: Index-Search型

適用場面: ペルソナ再現・固定ナレッジ・テーマ別分類

```
knowledge/
├── knowledge-index.json          # カテゴリ索引 + global_keywords + synonyms + scoring_weights
└── knowledge-{category}.json     # カテゴリ別データ（複数）
scripts/
├── search_knowledge.py           # 検索スクリプト (Stage1+Stage2)
├── build_index.py                # インデックス整合性検証・自動修正
├── record_usage.py               # §12 活用ログ記録・分析 (--analyze --emit-queue / --mark-needs-update)
└── add_entry.py                  # エントリ追加 (必須6フィールド検証つき・JSON手編集を排除)
```

`knowledge-index.json` 構造:

```json
{
  "version": "1.0.0",
  "categories": [
    {"id": "{category}", "label": "カテゴリ名", "file": "knowledge-{category}.json", "keywords": ["kw1"]}
  ],
  "global_keywords": {"キーワード": ["カテゴリID"]},
  "synonyms": {"採用難": ["人材不足", "採用課題"]},
  "scoring_weights": {"title": 5, "keywords": 3, "quote": 2, "voice": 2, "fulltext": 1},
  "output_dir": "{{OUTPUT_DIR}}",
  "output_naming": "output - YYYY-MM-DD - {種別} - {テーマ}.md"
}
```

### パターンB: Router-Registry型

適用場面: 継続的な知識同期・蓄積・外部ファイルからの随時抽出

```
knowledge/
├── router.json                   # カテゴリ→ファイル対応 + routing_rules + quick_lookup
├── schema.json                   # エントリ JSON Schema
├── registry.json                 # 処理済みファイル追跡 (status遷移)
└── {category}-{subtopic}.json    # カテゴリ別データ
scripts/
├── search_knowledge.py
├── build_index.py
├── record_usage.py               # §12 活用ログ記録・分析
└── add_entry.py                  # エントリ追加 (必須6フィールド検証つき・JSON手編集を排除)
```

`router.json` 構造:

```json
{
  "categories": {
    "{category}": {
      "files": ["{category}-{subtopic}.json"],
      "routing_rules": {
        "{category}-{subtopic}.json": {
          "topic": "サブトピック概要",
          "tags": ["tag1", "tag2"],
          "default": true
        }
      }
    }
  },
  "quick_lookup": {
    "by_phase": {"phase1": {"files": ["{category}.json"]}},
    "by_issue": {"キーワード": {"files": ["{category}.json"]}}
  }
}
```

ナレッジ進化メカニズム: 新エントリの `tags` を `routing_rules[*].tags` とマッチングし、最もマッチ数が多いファイルに格納。エージェントはファイル名をハードコードせず必ず `router.json` 経由でファイル名を取得する。

---

## §3 ファイル命名規則

- 内容を表す英単語、ハイフン区切り、小文字のみ
- **連番禁止**: `-1`, `-2`, `-a`, `-b` は絶対禁止
- 良い例: `principles-relationship.json` / 悪い例: `principles-1.json`

---

## §4 標準フィールド

### 4.1 カテゴリファイル基本構造

```json
{
  "category": "カテゴリID",
  "label": "カテゴリ名",
  "version": "1.0.0",
  "created_at": "YYYY-MM-DD",
  "description": "カテゴリの説明",
  "keywords_global": ["グローバルkw"],
  "source_note": "情報源の注記",
  "items": []
}
```

### 4.2 エントリ必須6フィールド

| フィールド | 説明 | 形式 |
|-----------|------|------|
| `id` | 一意識別子 | `{category}_{3桁連番}` |
| `title` または `content` | 知識の核心 | 主語+動詞+目的語の1文 |
| `purpose` または `intent` | この知識の目的 | 「〜すること」「〜を防ぐこと」の形 |
| `background` | 背景・状況 | 業種・規模・数値を含む2〜5文 |
| `keywords` または `tags` | 検索タグ | 悩みワード+同義語+上位語で5〜8語 |
| `source` | 出典情報 | `{file, type, date, section}` |

### 推奨フィールド

`message`, `root_cause`, `expected_outcome`/`achievable`, `how_to_use`/`applications`, `future`, `related_items`, `output_types`, `action_items`

### ペルソナ再現系フィールド (Index-Search型)

`sakamoto_voice`/`expression.phrasing`, `sakamoto_expressions`/`quote` (直接引用), `expression.tone`, `expression.context_note`

---

### 4.3 フィールド別品質ルーブリック

#### `title` / `content`

| レベル | 基準 |
|--------|------|
| 1 不可 | 主語・述語が曖昧 |
| 2 可 | 主語+動詞+目的語の1文で主題が明確 |
| 3 優 | 課題と提言が明確。検索ヒットしやすい |

**決定論的基準**: 主語+動詞+目的語の1文。修飾語2つまで。

#### `background`

| レベル | 基準 |
|--------|------|
| 1 不可 | 抽象的・具体情報なし |
| 2 可 | 業種・規模・状況のうち2つ以上を含む |
| 3 優 | 業種・規模・期間・数値・試した施策すべてを含む |

**決定論的基準**: 業種・規模・期間・数値のうち最低2つ。2〜5文。

#### `intent` / `purpose`

| レベル | 基準 |
|--------|------|
| 1 不可 | 漠然としている |
| 2 可 | 「〜すること」の形で目的が明確 |
| 3 優 | before→after (何を変えたいか+どう変えたいか) が明確 |

**決定論的基準**: 「〜すること」「〜を防ぐこと」の形。対象の変化が読み取れること。

#### `keywords` / `tags`

| レベル | 基準 |
|--------|------|
| 1 不可 | 汎用的すぎて差別化できない |
| 2 可 | 具体的な悩みワードが3語以上 |
| 3 優 | 悩みワード+同義語+上位語を含む5〜8語 |

**決定論的基準**: ソース素材中の原文ワード+同義語+上位語各1つ。5〜8語。

#### `source`

| レベル | 基準 |
|--------|------|
| 1 不可 | ファイル名だけ |
| 2 可 | ファイル名+種別 |
| 3 優 | ファイル名+種別+日付+該当セクション |

---

### 4.4 エントリ作成6ステップ

```
Step 1: ソース素材から「核心の主張」を1文で抽出 → title
Step 2: 5W1H で background を構築 (業種・規模・期間・数値を最低2つ含める)
Step 3: intent を「〜すること」の形で明文化 (before→after)
Step 4: keywords をユーザーの悩み言葉から5〜8語選定 (原文+同義語+上位語)
Step 5: source に出典を記録 (ファイル名・種別・日付・セクション)
Step 6: §4.3 ルーブリックで自己検証 (全フィールドがレベル2以上であること)
```

---

## §5 スタイルゲノム (ペルソナ系スキル)

ペルソナを再現するスキルでは `knowledge-style-genome.json` に以下を含める:
`style_genome.persona_summary`, `communication_style` (energy_level/tone/pace/vocabulary_level), `sentence_structure_patterns[]`, `signature_phrases[]`, `nuances[]`, `emotion_triggers` (excited/concerned/passionate), `conversation_flow_patterns` (answer/deepen/summarize), `output_style_for_documents`。

---

## §6 品質チェックリスト

### 必須 (全フィールド §4.3 レベル2以上)

- [ ] `id` が一意でフォーマットに準拠
- [ ] `title`/`content` が主語+動詞+目的語の1文
- [ ] `background` が業種・規模・期間・数値のうち最低2つを含む
- [ ] `intent`/`purpose` が「〜すること」の形
- [ ] `keywords`/`tags` がソース原文+同義語+上位語で5〜8語
- [ ] `source` にファイル名・種別・日付が記録されている

### 推奨

- [ ] `root_cause`/`message` がある
- [ ] `expected_outcome`/`achievable` がある
- [ ] `how_to_use`/`applications` がある
- [ ] `related_items` に関連エントリIDが設定されている
- [ ] ペルソナ系は `quote`/`sakamoto_expressions` に直接引用がある

### リグレッションテスト (エントリ追加・更新後)

1. 追加エントリに関連するクエリを3つ実行し、上位5件に含まれることを確認
2. 既存の代表クエリ3つを再実行し、結果が劣化していないことを確認
3. `build_index.py --stats` で整合性エラーがないことを確認

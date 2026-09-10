# knowledge/ — harness-creator 自身の蓄積知見ストア (Loop B)

harness-creator が Capability を作成するとき (build-time) に検索して再利用する、レビュー済みの curated seed。日々の未検証観測はここへ書かず、package 外の external-intelligence state に置く。

## Loop A と Loop B の関係

| | 場所 | 誰が更新 | いつ使う |
|---|---|---|---|
| Loop A (生成物側) | 生成された各スキルの `knowledge/` | reviewed promotion | そのスキルの実行時 |
| Loop B (メタ側) | 本ディレクトリ `plugins/harness-creator/knowledge/` | reviewed promotion | 次の Capability 作成時 |
| Runtime | Git common dir / project `.harness` / user state | `build-external-intelligence.py` | Codex/Claude の観測・重複統合・再利用検証 |

runtime lifecycle の正本は `build-external-intelligence.py` だけとし、curated seed の検索品質ログとは混ぜない。

## SSOT の役割分担

- `lessons-learned/*.md` … owner がレビューした昇格済みの失敗知見。hook は直接追記しない。
- `knowledge/` … 作成時に検索する curated seed。`knowledge-lessons-index.json` は reviewed lesson 本文をコピーせず `source.file` で参照する。
- external-intelligence state … 未検証観測の唯一の runtime 正本。installed plugin 配下へ置かない。
- `pattern-feedback.json` / `amplified-patterns.json` … elegant-review の量産パターン蓄積 (別系統)。

### 配置ルール (形式の正本・`scripts/lint-knowledge-layout.py` が fail-closed 強制)

**散文の失敗ログを `knowledge/` 直下へ `.md` で置いてはいけない** (JSON ストアと混在させない)。散文は必ず `lessons-learned/*.md` に置き、`knowledge/` からは `knowledge-lessons-index.json` の `source.file` で参照する。lint が下記を機械検査する:

- **K1**: `knowledge/` 直下は `*.json` / `*.jsonl` / `README.md` のみ (散文 `.md` 混入を拒否)。
- **K2**: `knowledge-lessons-index.json` の各 `source.file` は実在必須 (dangling 参照禁止)。
- **L1-L4**: `lessons-learned/*.md` は `YYYY-MM-DD-<slug>.md` 命名・`date:` frontmatter・`## 背景`/`## 知見`/`## 適用先`・本文 30 行以下。

## 構成 (Index-Search型)

```
knowledge/
├── knowledge-index.json            # カテゴリ索引 + global_keywords + synonyms + scoring_weights
├── knowledge-build-patterns.json   # ビルド設計パターン・パラダイム (蒸留済み知見)
├── knowledge-lessons-index.json    # lessons-learned への検索用ポインタ
└── usage-log.jsonl                 # §12 活用ログ (作成時の検索結果と採否を追記。初回 record_usage.py 実行時に lazy 生成・不在=未使用の正常状態)
```

## build-time での検索 (Loop B 実体)

検索スクリプトは複製せず、テンプレ正本を `--dir` 指定で直接実行する:

```bash
python3 plugins/harness-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/search_knowledge.py \
  --dir plugins/harness-creator/knowledge/ --query "<作成中スキルのトピック>" --limit 5
```

`run-skill-elicit` / `run-build-skill` は curated seed と external-intelligence の薄い index を各5件まで検索する。前者の採否は `record_usage.py`、後者の実利用は `build-external-intelligence.py reuse` に記録し、同じ事実を両方へ二重記録しない。

## エントリ追加・更新

`ref-knowledge-loop/references/knowledge-construction.md` の §4.3 品質ルーブリック (レベル2以上) と §4.4 作成6ステップに従う。必須6フィールド (id / title / intent / background / keywords / source) を満たすこと。25 エントリ超過でサブトピック分割 (§ファイル分割)。

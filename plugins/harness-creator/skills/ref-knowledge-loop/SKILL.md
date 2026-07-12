---
name: ref-knowledge-loop
description: 生成スキルに knowledge/ を追加するとき読む。ナレッジ蓄積・検索・フィードバックループの設計を参照するとき読む。
disable-model-invocation: true
user-invocable: false
kind: ref
prefix: ref
effect: none
owner: team-platform
version: 0.2.0
since: 2026-05-24
source: doc/knowledge-loop/
source-tier: internal
allowed-tools: [Read, Grep]
responsibility_refs:
  - prompts/R1-search-summarize.md
---

# ref-knowledge-loop

## Purpose & Output Contract

生成スキルに `knowledge/` を追加する際の設計参照。構築編 (パターン選択・構造・フィールド・品質ルーブリック) と運用編 (検索・ライフサイクル・フィードバック) の 2 リファレンスを提供し、Loop A (生成物側) と Loop B (メタ側) を同一機構 SSOT で配線する。

**入力**: なし (Read-only 参照型)
**出力**: `references/knowledge-construction.md` / `references/knowledge-search-lifecycle.md` の該当節と、生成スキルへ展開する 4 スクリプト雛形のパス

## 参照内容

2つのリファレンスで構成される。

| リファレンス | 内容 |
|---|---|
| `references/knowledge-construction.md` | 構築編: パターン選択・構造・フィールド・品質ルーブリック (§0-6) |
| `references/knowledge-search-lifecycle.md` | 運用編: 検索・ライフサイクル・フィードバック・日々のブラッシュアップ (§7-12) |

リソース索引 → `references/resource-map.yaml`

### 同梱スクリプト (雛形 → 生成スキルへ展開)

生成スキルの `scripts/` には4本を同梱する (KL-003/KL-004 で検証):

- `search_knowledge.py`: Stage1+Stage2 検索
- `build_index.py`: インデックス整合性検証・自動修正
- `record_usage.py`: §12 活用ログ記録・分析。`--analyze --emit-queue <path>` で brushup キュー出力、`--mark-needs-update` で status: needs-update 付与
- `add_entry.py`: 必須6フィールド検証つきエントリ追加 (JSON 手編集を排除)

決定論 (スクリプト=検証・追記・status付与) と内容判断 (AI/人) を分離する。各生成スキル (Loop A) はこれらを同梱して自己完結で日々ブラッシュアップできる。harness-creator 自身のメタ知識 (Loop B) は正本スクリプトを `--dir` 共有する (→ construction.md §0a)。

### パターン選択フロー

```
Q1: ナレッジは継続的に追加されるか？
  Yes → Q2: ソース素材が外部ファイルにあるか？
    Yes → Router-Registry型（router.json / registry.json）
    No  → Index-Search型（knowledge-index.json）
  No  → Q3: ペルソナを再現するか？
    Yes → Index-Search型 + style-genome
    No  → references/ 静的ファイルで十分（knowledge/ 不要）
```

### knowledge/ を追加する5条件

knowledge/ ディレクトリは以下の条件を1つ以上満たす場合のみ作成する。

1. 外部素材依存: 議事録・動画・教材等を参照して回答する
2. ペルソナ再現: 特定人物の語り口・思想を再現する
3. 知識量: カテゴリ別に分類された知識が10件以上ある
4. 継続的蓄積: 新しい素材が追加されるたびにナレッジが増える
5. 精度優先検索: キーワード・カテゴリ・IDで的確に検索したい

## Boundary

- このスキルは参照専用。knowledge/ を実際に生成するのは `run-build-skill` の責務。
- 200エントリ超の大規模ナレッジはこのガイドの適用範囲外（外部検索エンジン推奨）。
- テンプレート雛形 → `run-build-skill/templates/knowledge-skeleton/`
- lint スクリプト → `run-build-skill/scripts/lint-knowledge-loop.py`

---
name: ref-knowledge-loop
description: 生成スキルに knowledge/ を追加するとき読む。ナレッジ蓄積・検索・フィードバックループの設計を参照するとき読む。
disable-model-invocation: false
user-invocable: false
kind: ref
prefix: ref
effect: none
owner: team-platform
version: 0.3.0
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
**出力**: 構築・検索ライフサイクル・外部知能境界の該当節と、生成スキルへ展開する 5 スクリプトのパス

## 参照内容

2つのリファレンスで構成される。

| リファレンス | 内容 |
|---|---|
| `references/knowledge-construction.md` | 構築編: パターン選択・構造・フィールド・品質ルーブリック (§0-6) |
| `references/knowledge-search-lifecycle.md` | 運用編: curated seed の検索・ライフサイクル・検索品質 (§7-12) |
| `references/external-intelligence.md` | runtime 編: package 外 state・重複統合・独立証拠・再利用検証・昇格境界 |
| `references/external-intelligence-runtime-contract.md` | 通常runtime編: Claude Code/Codex共通request/state/output・有界検索・fail-soft・中央pointer |

リソース索引 → `references/resource-map.yaml`

### 同梱スクリプト (雛形 → 生成スキルへ展開)

生成スキルの `scripts/` には5本を同梱する (KL-003/KL-004/KL-008 で検証):

- `search_knowledge.py`: Stage1+Stage2 検索
- `build_index.py`: インデックス整合性検証・自動修正
- `record_usage.py`: curated seed の検索品質記録・分析
- `add_entry.py`: version-control review 済みの著作知見、または promoted runtime 知見を curated seed へ取り込む明示工程
- `build-external-intelligence.py`: package 外 runtime state の観測・重複統合・再利用検証・明示昇格（Codex/Claude 共通）

決定論 (検証・重複判定・状態遷移) と内容判断 (AI/人) を分離する。runtime 観測は installed package 内へ書かず、project/user state に保存する。詳細は `external-intelligence.md`。

通常artifact生成は配布可能な `skill-governance-adapters` 内の中央 `build-external-intelligence-runtime.py` を使う。各plugin projectionはpointerだけを持ち、このadapter/engineをskillごとに複製しない。Harness Creator の同名 engine/adapter は後方互換用の薄い転送だけで、長い実装を持たない。上記5本同梱は `--with-knowledge` で生成するstandalone curated-seed skillのlegacy v1 compatibility境界であり、全plugin通常runtime projectionの配布形式ではない。

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

## ナレッジデータ設計方針

### 目的
ユーザーが抱える経営課題・悩みに対して、北原さんのアドバイスを**的確に・文脈ごと**届けること。「何を言ったか」だけでなく「なぜ言ったか・何を目的として・どういう流れで」まで記録する。

> **核心原則**: 記録するのは「北原さんの知恵・診断・アドバイスの構造」であり、「相談者の個人情報」ではない。相談者の状況は「このアドバイスが有効な典型的なパターン」として一般化する。相談者の実名・会社名・固有業種・特定数値は**ナレッジの雑音**にしかならないため記録しない。

### 必須フィールド（background・intent は特に重要）

| フィールド | 役割 | 書き方の目安 |
|-----------|------|------------|
| `content` | アドバイスの核心（1〜2文） | 「〜すること」「〜が重要」の形 |
| `background` | **このアドバイスが有効な典型的な状況パターン・北原さんの診断** | 個人情報を含まず、この種の経営者の構造的な状況を記述（2〜5文） |
| `intent` | **北原さんの目的・意図** | 「〜させること」「〜を防ぐこと」の形（1〜2文） |
| `root_cause` | 表面問題の裏の本質 | 構造的・心理的な根本原因（1〜2文） |
| `expected_outcome` | 実践後の変化 | 短期・長期の具体的な変化（2〜4文） |
| `how_to_use` | エージェントとしての活用方法 | いつ・どう使うか（引用タイミング・投げかける問い） |
| `conversation_flow` | 会話の典型的な流れ | どういう相談パターンから始まりどう展開するか（個人情報を除いて一般化・2〜3文） |

> **情報量について**: 1エントリの情報量が多くなっても問題ない。大切なのは意図がしっかり伝わること。

### ナレッジファイル命名規則

```
knowledge/
└── {category}-{subtopic}.json     ← エントリを書く時点から内容別サブトピックファイルに格納
```

**設計原則**: 「後で分割する」ではなく「**最初から適切なファイルに書き込む**」
格納先は `knowledge/router.json` の `routing_rules` が決定する。エージェントはファイル名をハードコードせず、必ず `router.json` 経由で取得する。

**命名ルール**:
- ◎ ファイル名だけで「どんな悩みのユーザー向けか」が分かること
- ◎ サブトピック名は内容を表す英単語（半角・ハイフン区切り）
- ✗ 連番（`-1`, `-2`）・アルファベット連番（`-a`, `-b`）は絶対禁止

| カテゴリ | 現在のサブトピックファイル |
|---------|--------------------------|
| principles | `principles-relationship.json` / `principles-mindset.json` / `principles-business.json` |
| consultation | `consultation-organization.json` / `consultation-sales.json` / `consultation-business-model.json` |
| phase-advice | `phase-advice-0to1.json` / `phase-advice-1to10.json` / `phase-advice-10to100.json` |
| action-guides | `action-guides-relationship.json` / `action-guides-content.json` |
| mindset | `mindset-self.json` / `mindset-organization.json` / `mindset-goal-strategy.json` / `mindset-growth-habit.json` |
| case-studies | `case-studies-success.json` / `case-studies-failure.json` / `case-studies-organization.json` |

※ 最新のファイル一覧は `knowledge/router.json` の `categories[*].files` が正。

### ナレッジ同期コマンド

```
/ubm-knowledge-sync              # 05_Project/UBM/ を自動スキャン（未処理のみ）
/ubm-knowledge-sync --all        # 全ファイル再構築
/ubm-knowledge-sync --since YYYY-MM-DD  # 指定日以降のみ
```

- スキャン対象: `05_Project/UBM/` 配下の全 `.md` ファイル（サブディレクトリ含む）
- 新ディレクトリが追加されても自動検知（ハードコード不要）
- 処理済みファイルは `knowledge/registry.json` のMD5ハッシュで管理

### ナレッジファイル詳細は `knowledge/schema.json` を参照


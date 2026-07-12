# コア原則（§2）

> 18-skills.md §2 の要約
> **相対パス**: `references/core-principles.md`
> **原典**: `docs/00-requirements/18-skills.md` §2

---

## 2.1 簡潔さが鍵（Concise is Key）

コンテキストウィンドウは公共財。

**デフォルトの前提**: Claude は既に非常に賢い

| 原則           | 説明                                           |
| -------------- | ---------------------------------------------- |
| 必要な情報のみ | Claudeが持っていないコンテキストのみを追加する |
| 例を優先       | 冗長な説明よりも簡潔な例を優先                 |

**各情報への問いかけ**:

- 「Claude は本当にこの説明を必要としているか？」
- 「この段落はトークンコストに見合う価値があるか？」

---

## 2.2 知識圧縮アンカー（Squeeze / Anchors）

詳細を長文で書かずに、Claudeが学習済み/既知の枠組みや一次資料を**短い参照行**として置く方法。

**アンカーの例**:

| 種類         | 例                                       |
| ------------ | ---------------------------------------- |
| 書籍名       | Clean Architecture, Domain-Driven Design |
| 設計思想名   | SOLID, 12-Factor App                     |
| 社内ルール名 | プロジェクト固有の規約                   |
| API/Schema名 | OpenAPI仕様、DBスキーマ                  |
| Runbook名    | 運用手順書                               |
| 決定事項ID   | ADR-001 など                             |

**規則**:

| ルール                  | 詳細                                                   |
| ----------------------- | ------------------------------------------------------ |
| 個数制限                | 1 Skill あたり 1〜5 個まで（過多禁止）                 |
| 記述形式                | 「アンカー名」＋「適用範囲」＋「今回の目的」を同一行に |
| description内のMarkdown | 箇条書き（`-` や `*`）は禁止、`•` を使用               |

---

## 2.3 適切な自由度の設定

タスクの脆弱性と変動性に応じて具体性のレベルを調整：

| 自由度 | 使用場面                                     | 記述形式                         |
| ------ | -------------------------------------------- | -------------------------------- |
| 高     | 複数アプローチが有効、判断がコンテキスト依存 | テキストベース指示               |
| 中     | 推奨パターンあり、一定変動は許容             | 擬似コード or パラメータ付き手順 |
| 低     | 脆弱でエラー誘発、一貫性重要                 | scripts 実行 + 少数パラメータ    |

---

## 2.4 Progressive Disclosure（段階的開示）

必要な情報を必要な時にのみ読み込む3層システム：

| レベル | 読み込み対象                                         | 目安       |
| ------ | ---------------------------------------------------- | ---------- |
| 1      | メタデータ（name + description）                     | 最小       |
| 2      | SKILL.md 本文                                        | 中         |
| 3      | バンドルリソース（agents/references/scripts/assets） | 必要時のみ |

**読み込み判断基準**:

| 条件                 | 読み込むレベル         |
| -------------------- | ---------------------- |
| スキルの存在確認のみ | Level 1                |
| 基本的な使用         | Level 2                |
| Task仕様が必要       | Level 3（agents/）     |
| 詳細な知識が必要     | Level 3（references/） |
| 決定論的処理が必要   | Level 3（scripts/）    |
| 出力素材が必要       | Level 3（assets/）     |

---

## 2.5 Problem First（問題先行原則）

機能の前に本質的な問題を特定する。

| 原則              | 説明                                                        |
| ----------------- | ----------------------------------------------------------- |
| 問題空間→解決空間 | 問題の根本原因を特定してから解決策を設計する                |
| Outcome定義       | ゴールはOutput（作るもの）ではなくOutcome（状態変化）で定義 |
| 5 Whys            | 表面的な症状から根本原因に到達するまで「なぜ？」を繰り返す  |
| Non-Goals明示     | スキルが対処しないことを明示的に定義する                    |

📖 [problem-discovery-framework.md](problem-discovery-framework.md)

---

## 2.6 Domain-Driven Design（ドメイン駆動設計）

DDDの戦略的設計をスキル設計に適用する。

| 原則            | 説明                                                 |
| --------------- | ---------------------------------------------------- |
| Core Domain集中 | スキルの存在理由に最も設計の力点を置く               |
| ユビキタス言語  | スキル内の用語を統一し曖昧さを排除する               |
| Bounded Context | スキルの責務境界（In/Out/Port）を明確にする          |
| 問題分類        | 効率/品質/知識/構造/不在で問題を分類し設計方針を決定 |

📖 [domain-modeling-guide.md](domain-modeling-guide.md)

---

## 2.7 Clean Architecture（層分離設計）

Clean Architectureの依存関係ルールをスキル構造に適用する。

| 原則                     | 説明                                       |
| ------------------------ | ------------------------------------------ |
| 依存は外→内のみ          | 内側の層は外側の層を知らない               |
| Entities = 不変ルール    | references/にドメイン知識を配置            |
| Use Cases = ワークフロー | SKILL.mdにユーザーが達成すべきことを定義   |
| Contract First           | JSON Schemaを先に定義し、実装は後          |
| Explicit Over Implicit   | 暗黙の前提を排除し、すべて明示的に定義する |

📖 [clean-architecture-for-skills.md](clean-architecture-for-skills.md)

---

## 関連リソース

- **Skill概要**: See [overview.md](overview.md) - §1
- **構造仕様**: See [skill-structure.md](skill-structure.md) - §3
- **問題発見**: See [problem-discovery-framework.md](problem-discovery-framework.md)
- **ドメインモデリング**: See [domain-modeling-guide.md](domain-modeling-guide.md)
- **Clean Architecture**: See [clean-architecture-for-skills.md](clean-architecture-for-skills.md)

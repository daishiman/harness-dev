# 01. 設計思想

## Skill はプロンプト保存場所ではない

Claude Code Skill は、長いプロンプトを保存するだけの仕組みではない。特定の作業に名前を付け、発動条件、手順、基準、出力契約、必要な補助ファイルをまとめることで、AI 活用のノウハウを再利用可能な業務部品に変える仕組みである。

Skill が数個なら「便利なプロンプト集」として扱える。しかし数が増えると、似た Skill が並び、どれを使うべきか Claude も人間も迷い始める。そこで必要になるのは、プロンプト術ではなく設計規範である。

## 散らかった運用知を引き出しに整理する

画像群では、散らかった運用知を 5 つの引き出しに整理するイメージが示されている。

- Purpose（目的） / Trigger（発動条件） / Shape（成果物の形） / Role（役割）の 4 軸で役割を明確化する。
- Prefix で命名し、呼び出し側が契約を推測できるようにする。
- エージェントが必要な時に読みに来る設計にする。
- 評価しやすく、改善しやすい構造にする。
- Goodhart（評価基準を都合よく歪める罠）の罠や自己評価の甘さを防ぐ。

## Skill 設計の上位モデル

Skill は次の 5 要素で設計する。これは Clean Architecture（依存方向を守る設計） / Clean Code / DDD（ドメイン駆動設計） / リファクタリング / エンジニアリング品質 / マーケティング検証に共通する抽象モデルである。

| 要素 | Skill での意味 | 対応する設計思想 |
|---|---|---|
| Intent（意図） | 何のために呼ぶか | ユースケース、価値提案、positioning |
| Contract（契約） | 入力・出力・完了条件 | API 契約、境界インターフェース |
| Boundary（責務境界） | 何をしないか、どこまで責任を持つか | SRP、Bounded Context（境界づけられた文脈） |
| Execution（実行） | 手順、tool、artifact、副作用 | 小さな変更、workflow、adapter |
| Feedback（評価フィードバック） | evaluator、rubric、lint、ログ | 品質ゲート、検証ループ、学習 |

`06` の Purpose（目的） / Trigger（発動条件） / Shape（成果物の形） / Role（役割） / Effect（副作用） / prefix は、この上位モデルを Skill 名と運用規約に落とすための下位分類である。分野が変わっても、まず Intent（意図） / Contract（契約） / Boundary（責務境界） / Execution（実行） / Feedback（評価フィードバック）を埋め、その後に命名と配置へ進む。

## 公式仕様と提唱体系を分ける

公式仕様:

- `SKILL.md` の配置場所
- YAML frontmatter
- `context: fork`
- `disable-model-invocation`
- `user-invocable`
- `allowed-tools`
- 動的コンテキスト注入
- 補助ファイル
- skill lifecycle / compaction

提唱体系:

- 辞書型 / ワークフロー型
- Purpose（目的） / Trigger（発動条件） / Shape（成果物の形） / Role（役割）
- `ref- / run- / wrap- / assign- / delegate-`
- `base:` / `pair:` / `kind:` などの独自メタデータ
- Generator（生成役） / Evaluator（評価役） 分離
- 名前を契約として扱う設計思想

公式制御フィールドと独自メタデータを混同しないことが重要である。

## 出典階層

| ラベル | 意味 | 用途 |
|---|---|---|
| `official-fact` | Claude Code 公式 docs で確認できる仕様 | frontmatter field、lifecycle、permissions、Agent Teams 制約 |
| `article-text` | 元記事本文から抽出した主張 | Skill 設計思想、4 軸、5 prefix、評価分離の意義 |
| `image-derived` | 画像から読み取った図表・概念 | 決定木、比較表、失敗パターン、評価ループ図 |
| `proposed-rule` | 本設計書が採用する運用規律 | 生成対象 `SKILL.md` の 300 行 hard cap、description 2〜3 条件、MVP 構成 |
| `code-verified` | 実コードを確認して得た事実 | テンプレや scripts の実装差分 |
| `code-unavailable` | 記事にコード共有の記述はあるが現物未取得 | 断定せず、記事説明由来として扱う |

同じ主張に複数の出典がある場合、Claude Code の動作仕様は `official-fact`、設計思想は `article-text` / `image-derived`、このリポジトリの出荷条件は `proposed-rule` を優先する。

## Skill の価値

| 価値 | 内容 |
|---|---|
| 品質安定 | 毎回その場で指示を書くのではなく、検証済み手順を再利用する |
| 知識共有 | 個人の秘伝プロンプトではなく、チームで読めて直せる資産にする |
| 変更容易性 | 巨大プロンプトではなく対象 Skill だけを更新する |
| 評価可能性 | 完了条件を出力契約と evaluator で検証する |

## 4条件の正本

本設計書群でいう 4条件は、次の出荷判定である。`24` / `26` の rubric（評価基準）はこの定義へ従う。

| 条件 | 定義 | 代表チェック |
|---|---|---|
| 矛盾なし | 公式事実、提唱規則、テンプレ、Runbook が相反しない | optional / 必須、300 / 500 行などの裁定が明記されている |
| 漏れなし | Skill 構築に必要な入口、正本、テンプレ、評価、運用が揃う | README から必要ファイルに辿れる |
| 整合性あり | 用語、採番、frontmatter、出典ラベル、データ構造が揃う | `00a` / `01a`、Subagent 表記、rubric key が揃う |
| 依存関係整合 | 読む順序、正本参照、生成/評価/補助ファイルの依存が一方向に定義される | `16/17` → 設計判断 → テンプレ → Runbook の順になる |

DRY / Less is More / Why（理由）-driven / Self-contained は本文品質の補助観点であり、4条件そのものではない。

## 設計対象としての Skill 群

Skill 群は、小さなアプリケーション構造に近い。単体 Skill だけでなく、以下の関係を設計対象に含める。

- Skill と補助ファイル
- Skill と CLI / script
- Skill と MCP / API
- Skill と Subagent
- Generator（生成役）と Evaluator（評価役）
- base Skill と wrap Skill
- ref Skill と workflow Skill
- permission / hook / settings による強制

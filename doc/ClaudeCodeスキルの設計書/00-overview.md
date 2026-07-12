# 00. 全体像

## 目的

この設計書群は、Claude Code Skill を「便利なプロンプト保存場所」ではなく、「責務・発動条件・実行境界・評価契約を持つ再利用可能な業務部品」として設計するための仕様である。

元記事の主張、画像内の図表、Claude Code の公式仕様を統合し、実際にスキル設計へ使える形に分離した。

## 中心命題

Skill は毎回貼るプロンプトではない。名前で契約し、評価で完了を決める、設計可能な部品である。

## 解くべき問題

- 長大な system prompt / `CLAUDE.md` に運用知が集中する。
- Skill が増えるほど、呼び出し条件と責務が曖昧になる。
- 生成と評価を同じ文脈で行い、自己申告を完了判定にしてしまう。
- 決定論で処理できる検査まで自然言語 Skill に書いてしまう。
- `SKILL.md` が肥大化し、重要ルールが context の中で埋もれる。

## 設計原則の要約

| 原則 | 要点 |
|---|---|
| Problem First | Skill を作る前に、何の複雑さを解くのかを特定する |
| Layer First | Skill / Subagent / Hook / MCP / CLI / API のどこで解くかを決める |
| Contract（契約） Naming | Skill 名の prefix を契約として扱う |
| Progressive Disclosure（段階的開示） | 最初から全部読ませず、必要時だけ補助ファイルを読む |
| Evaluation Driven | 生成と評価を分離し、完了判定を機械可読にする |
| Deterministic First | lint / schema / Hook / CI で落とせるものは自然言語に戻さない |

## 成果物の使い方

- 新しい Skill を設計する: `06-classification-and-naming.md` と `11-templates.md`
- YAML 設定を確認する: `03-yaml-frontmatter-reference.md`
- 副作用や権限を整理する: `04-invocation-permissions-settings.md`
- 評価器を作る: `09-evaluation-orchestration.md`
- Subagent / Hook と連携する: `10-subagents-hooks-integration.md`


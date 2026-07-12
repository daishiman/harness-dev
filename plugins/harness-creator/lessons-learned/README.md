# lessons-learned/

harness-creator 配下 Skill 群を運用して得た「再利用可能な知見」を 1 件 1 ファイルで蓄積する。

## 運用ルール

- ファイル名: `YYYY-MM-DD-<slug>.md` (kebab-case、内容を表す動詞句)。
- 1 ファイル 30 行以下。掘り下げが必要なら設計書本体に昇格させる。
- 必須セクション: `## 背景` / `## 知見` / `## 適用先`。
- changelog とセットで追加するのが望ましい (changelog=何をしたか / lessons-learned=なぜそれが良いか)。

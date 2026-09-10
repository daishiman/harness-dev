# lessons-learned/

harness-creator 配下 Skill 群を運用して得た「検証済み・昇格承認済みの再利用可能な知見」を 1 件 1 ファイルで配布する。未検証の hook 観測は external-intelligence state に保存し、ここへ自動追記しない。

## 運用ルール

- ファイル名: `YYYY-MM-DD-<slug>.md` (kebab-case、内容を表す動詞句)。
- 1 ファイル 30 行以下。掘り下げが必要なら設計書本体に昇格させる。
- 必須セクション: `## 背景` / `## 知見` / `## 適用先`。
- external-intelligence の `verified`、独立証拠、反証条件、rollback を owner が確認してから追加する。
- changelog とセットで追加するのが望ましい (changelog=何をしたか / lessons-learned=なぜそれが良いか)。

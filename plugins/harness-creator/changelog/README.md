# changelog/

harness-creator 配下 Skill 群への改修記録を 1 改修 1 ファイルで残す。

## 運用ルール

- ファイル名: `YYYY-MM-DD-<slug>.md` (kebab-case)。
- 1 ファイル 30 行以下。詳細は PR/commit に委ね、changelog は要約のみ。
- 必須セクション: `## 概要` / `## 変更 Skill` / `## 影響範囲` / `## 関連`。
- 改修と同 PR で追加する。後追い禁止。
- `verdict` を変える改修は同日付で `EVALS.json` の evaluations を更新する。

# Step 1 棚卸し 8 区分判定ルール

doc/20-migration-path.md §「Step 1 棚卸し」表の機械判定版。

| 区分 | キーワード/パターン | 移行先プレフィクス |
|------|--------------------|--------------------|
| always-on | 「常に」「必ず」「全タスクで」「short rules」 | CLAUDE.md に残す |
| ref | 「リファレンス」「仕様」「用語集」「規約」 | `ref-*` |
| run | 「手順」「ワークフロー」「Step 1..N」 | `run-*` |
| wrap | 「コマンドラッパ」「実行前検査」「git/npm wrapper」 | `wrap-*` |
| assign | 「評価する」「採点」「rubric」「fork で起動」 | `assign-*` |
| delegate | 「外部 LLM に委譲」「Codex」「Gemini」 | `delegate-*` |
| hook | 「禁則」「禁止」「block」「pre-commit」「決定論」 | settings.json hooks |
| docs | 「議事録」「経緯」「人間向け記録」 | `docs/` |

優先順位: hook > wrap > assign > delegate > run > ref > docs > always-on
（決定論で守れるものから昇格させる原則）

## 抽象化ルール
- ドメイン固有名詞 (`{{domain_term}}`) は `{{var}}` 化
- プロジェクトパス (`xl-skills/`, `creator-kit/`) は `{{PROJECT_ROOT}}` / `{{KIT_ROOT}}`
- 組織名・人名は `{{owner}}` / `{{team}}`

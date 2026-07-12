---
timestamp: 2026-04-28T17:01:31Z
branch: feat/issue-130-skill-ledger-a2-fragment-task-spec
author: claude-code
type: changelog
---

# skill-creator changelog (2026-04-28)

A-2 fragment 化（skill ledger を 1 entry = 1 file に移行）に伴う本 skill の SKILL 機能差分を記録する。

## Added

- `references/migration-from-legacy-ledger.md`: 旧 monolith ledger → fragment 方式の移行手順書を新規作成（5 step + 検証コマンド + 相互参照 anchor 文例）
- 本 fragment 群: LOGS fragment 1 件 / changelog fragment（本ファイル）

## Changed

- `assets/skill-template.md`: 標準フォルダ構造表に `LOGS/` `changelog/` `lessons-learned/` の 3 ディレクトリ行を追加（旧 `LOGS.md` 単一行は廃止）。フィードバックサイクル図を fragment 経路へ更新
- `assets/logs-template.md`: monolith 雛形を全廃し fragment 単体 entry テンプレートに差し替え。`pnpm skill:logs:append` / `pnpm skill:logs:render` の正本コマンド、front matter 必須項目（timestamp / branch / author / type）、命名規則 regex（`<YYYYMMDD>-<HHMMSS>-<escapedBranch>-<nonce>.md`）を網羅

## Notes

- references/ 配下の `LOGS_PATH = LOGS.md` パース系（feedback-loop / update-process / library-management / self-improvement-cycle）と patterns 系の `git diff --stat -- */LOGS.md` 検証手順は本 PR では未変更。次 wave で fragment ディレクトリ走査・glob へ更新予定
- agents/ 配下の `save-patterns.md` / `design-update.md` の LOGS.md 存在チェックも次 wave 対応

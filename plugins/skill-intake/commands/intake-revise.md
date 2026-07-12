---
name: intake-revise
description: 既存 intake に追加要望を聞き取り Notion ページを PATCH 更新 (run-intake-revise) — ヒアリングと Gate R 承認のみで新規ページは作らない
allowed-tools:
  - Skill
argument-hint: "<hint> [--dry-run]"
---

# /intake-revise

既に公開済みの intake (`output/<hint>/intake.md` + Notion ページ) に対し、追加要望を Claude Code チャット内で対話的に聞き取り、Gate R 承認後に同一 Notion ページを PATCH 上書きする。

## 振る舞い

1. `Skill(run-intake-revise, args="$ARGUMENTS")` を呼ぶ。
2. スキル側で既存 4 ファイルロード → 差分ヒアリング → 内部解析再実行 → 差分プレビュー → Gate R → Notion PATCH → revision-log 追記 → self-updater 再起動。
3. 完了後、Notion URL と revision_no を返す。`--dry-run` 指定時は Notion API を呼ばず差分のみ表示。

## 用途

- 既存 intake の章追記 / 修正 (新規 hint で `/intake` をやり直さない)
- ユーザー追加要望の取り込み (最大 5 回 / 同一ページ PATCH)
- Notion ページ URL を変えずに内容だけ更新したいとき

## 失敗時

- exit 2 (Gate R cancel): 既存ページ不変、ローカル中間生成物巻き戻し
- exit 44 (Keychain 未登録): `keychain-setup.md` を案内
- exit 51 (page-id 不一致): 新規 hint で `/intake` を案内
- exit 60 (revision 5 回超過): 新規 hint へ移行

## related

- `/intake <topic>`: 新規ヒアリング
- `/intake-publish <hint>`: 既存 intake の再公開 (内容変更なし、再 render のみ)
- `/intake-status <hint>`: 現状確認

---
name: run-intake-revise
description: 既存 intake に追加要望を Claude Code チャット内で対話聞き取りしたいとき、Gate R 承認後に Notion ページを PATCH 上書きしたいときに使う。
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - AskUserQuestion
  - Skill
kind: run
user-invocable: true
effect: external-mutation  # Notion ページ PATCH = 外部変更 (run-notion-intake-publish と同値)
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-24
version: 0.1.0
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: apply 確定時に output/<hint>/revision-log.jsonl へ追記される 1 行が schemas/output.schema.json 準拠で revision_no/timestamp/target_section/user_request/applied_changes/notion_page_url を充足し、user_request と applied_changes が日本語・schema key/page-id が英語である
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: revision 回数上限 5 / page-id 不一致 / Keychain 失敗 / cancel / self-updater 失敗 が exit code 60/51/44/2/61 に決定論的に対応し、PATCH 失敗時は output/<hint>/notion-rollback-<rev>.json を必ず保存して旧版を維持する
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 本スキルが同一 Notion ページへの PATCH 上書き(新規ページ非作成=URL/リンク保全)に責務を絞り、PNG/mermaid 全揃いの All-or-Nothing と internal-analysis.json 非開示を守りつつ、新規 intake 生成・publish へ逸脱しない設計になっている
      verify_by: elegant-review
---

# run-intake-revise

## Purpose & Output Contract

既に公開済みの intake (`output/<hint>/intake.md` + Notion ページ) に対し、ユーザーから追加要望・改善点を Claude Code チャット内で対話聞き取りし、合意確定後に **同一 Notion ページを PATCH 更新** する。新規ページは作成しない。

**入力**: `output/<hint>/intake.json` / `intake.md` / `notion-url.txt` / `internal-analysis.json`、ユーザー追加要望 (AskUserQuestion で収集)
**出力**:
- 更新済み Notion ページ (同一 page ID、PATCH children)
- `output/<hint>/revision-log.jsonl` への 1 行追記 (`schemas/output.schema.json` 準拠)
- 失敗時: `output/<hint>/notion-rollback-<rev>.json`

**完了条件**: Gate R で `apply` 承認 → Notion PATCH 成功 → revision-log 追記済み。または cancel/上限/失敗で適切な exit code を返却。

## Key Rules

1. **回数上限**: 同一 hint に対する revision は最大 5 回。超過したら exit 60 で新規 `/intake` を案内。
2. **All-or-Nothing**: PNG / mermaid が 1 つでも欠けたら旧版を維持 (Notion 公開と同原則)。
3. **PATCH 更新固定**: delete-then-insert ではなく block 単位 update。失敗時は rollback JSON を保存。
4. **内部解析非開示**: `internal-analysis.json` をユーザーに直接見せない。要約済み「あなたの追加要望をこう理解しました」テキストのみ Gate R 直前に提示。
5. **日本語成果物**: 本文・revision-log の `user_request` / `applied_changes` は日本語、schema key / CLI 引数 / page-id は英語。

## ゴールシーク実行

### Goal
既存 intake への追加要望を、最大 5 回の制約下で対話的に確定し、Gate R 承認を得た上で **同一 Notion ページに PATCH 反映** し、revision-log.jsonl に 1 行追記された状態。失敗時は旧版維持 + rollback JSON 保存 + 明確な exit code 返却。

### Why
Notion ページの新規作成は URL 変更とリンク断絶を招くため、PATCH 固定が不可避。LLM 推論を含むヒアリング結果と決定論的 render を分離しないと、検証 (PNG / mermaid 存在) を通らない部分更新がページを汚染する。固定手順を辿るのではなく、**チェックリスト未充足を起点に必要 step をその都度起動して反復**することで、ユーザー意図の取り違えや中間生成物欠落にも頑健になる。

### 完了チェックリスト (停止条件)
- [ ] `validate-notion-ready.py --check-api` が exit 0 (config / Keychain トークン / hearing-sheet DB 疎通)。PASS 済みなら API キーを再質問しない。exit 44 のみ `keychain-setup.md` 案内で停止
- [ ] 既存 4 ファイル (`intake.json` / `intake.md` / `notion-url.txt` / `internal-analysis.json`) をロードし、Notion ページ ID を抽出した
- [ ] revision 回数を確認し、上限 (5) を超えていない
- [ ] AskUserQuestion で対象章 (§1〜§11) / 変更内容 / 変更理由を収集した
- [ ] `analyze_user_intent.py` を再実行し新しい `internal-analysis.json` を生成した
- [ ] 変更前後 diff を Claude Code チャットに提示し、要約済み理解テキストを Gate R 直前に表示した
- [ ] Gate R で `apply` / `re-revise` / `cancel` の判定を取得した
- [ ] `apply` の場合 `render-intake-final.py` で正本再生成 → `intake_publish_pipeline.py --revise --page-id <既存 ID>` で PATCH 更新した
- [ ] PNG / mermaid の全揃いを確認し、欠落時は旧版維持 + rollback JSON を保存した
- [ ] `output/<hint>/revision-log.jsonl` に `{revision_no, timestamp, target_section, user_request, applied_changes, notion_page_url}` を 1 行追記した
- [ ] `skill-intake-self-updater` 再起動で question-bank に「足りなかった質問」を追記した
- [ ] 内部解析 (`internal-analysis.json`) をユーザーに直接見せていない

未充足項目を特定 → 必要 script (`analyze_user_intent.py` / `render-intake-final.py` / `intake_publish_pipeline.py`) を該当ステップから起動 → revision-log 更新 → 再度チェックリストで自己評価、を反復する。固定手順は持たない。

### 参考: 主要 script 起動例

```bash
# 内部解析再実行
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/analyze_user_intent.py output/<hint>

# 正本再生成
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/render-intake-final.py output/<hint>

# Notion PATCH 更新 (同一ページ ID)
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/intake_publish_pipeline.py \
  --intake   output/<hint>/intake.json \
  --manifest output/<hint>/notion-manifest.json \
  --revise \
  --page-id  <既存ページ ID>

# --dry-run 指定時は Notion API 呼び出しを行わず差分のみ表示
```

Step/Gate の機械可読定義は `workflow-manifest.json` (P1-load / P2-hear / P3-analyze / P4-preview / P5-gateR / P6-patch / P7-log / P8-self-update) を参照。

## Gotchas

1. **page-id 不一致は致命**: `notion-url.txt` と Notion DB 上のページが一致しなければ exit 51 で新規 `/intake` を案内 (PATCH 続行禁止)。
2. **Keychain / API キーは再質問しない**: PATCH 前に `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/validate-notion-ready.py --check-api` を 1 度だけ実行する。exit 0 なら API キー / Notion トークンは確認済みとして扱い、ユーザーへ再入力を求めない。exit 44 (`service=notion-api-key.<keychain-prefix>, account=<keychain-prefix>` 未登録) のときだけ `keychain-setup.md` を案内し停止する。
3. **回数上限超過**: 5 回を超えたら exit 60 (新規 hint へ移行)。リセットしない。
4. **cancel は完全巻き戻し**: Gate R cancel で exit 2、既存ページ不変、ローカル中間生成物も巻き戻す。
5. **rollback JSON**: PATCH 失敗時は `output/<hint>/notion-rollback-<rev>.json` を必ず保存。次回実行で参照する。

## Additional Resources

- `workflow-manifest.json` — Phase (P1-P8) / Gate (C1-C8) / resource の機械可読定義
- `schemas/output.schema.json` — revision-log.jsonl の 1 行スキーマ
- `prompts/R1-main.md` — R1 責務プロンプト (7 層 Markdown、ヒアリング+PATCH 制御)
- `references/resource-map.yaml` — リソース一覧 (machine-readable)

## エラー処理 (exit code)

| exit | 意味 | 対処 |
|---|---|---|
| 0 | 正常反映 | revision-log に追記済み |
| 2 | Gate R で cancel | 既存ページ不変、ローカル変更も巻き戻し |
| 44 | Keychain Notion トークン取得失敗 | `keychain-setup.md` 参照 |
| 51 | Notion ページ ID 不一致 | 新規 hint で `/intake` を案内 |
| 60 | revision 回数上限超過 (>5) | 新規 hint へ移行 |
| 61 | self-updater 失敗 (revision-log 追記失敗 / question-bank 更新失敗等) | `output/<hint>/revision-log.jsonl` を確認し手動修復、再実行 |

---
name: intake-publish
description: 既存 intake を指定 Notion ページへ再公開 (run-notion-intake-publish) — ヒアリングはやり直さず Notion API PATCH のみ
argument-hint: "<skill-name-hint> [--page-url <notion-page-url>|--page-id <notion-page-id>] [--database-id <notion-db-id>]"
---

# /intake-publish

`output/<skill-name-hint>/` に完成済みの intake 一式があることを前提に、Notion REST API での再公開だけを実行する。`--page-url` / `--page-id` が指定された場合はそのページを最優先で PATCH 更新し、解決不能なら新規作成せず停止する。既定では新規作成へフォールバックしない。

## 振る舞い

1. `Skill(run-notion-intake-publish, args="$ARGUMENTS")` を呼ぶ。
2. `validate-notion-ready.py --check-api` → DB スキーマ検証 → PNG 検証 → REST API PATCH → URL 保存。ready check が PASS した場合、APIキーは再質問しない。
3. 再公開は update 専用。出力先 page_id 解決順は `--page-id` > `--page-url` > `output/<hint>/notion-url.txt` > `notion-publish-result.json`。いずれでも解決できない場合は exit 51 で停止し、新規ページは作らない。

## 用途

- Notion DB プロパティ追加後の再公開
- PAT 更新 / Integration 切替後の動作確認
- 指定済み Notion ページへの再反映

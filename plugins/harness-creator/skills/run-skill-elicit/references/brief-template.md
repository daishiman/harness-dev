# skill-brief フィールド早見（正本ポインタ）

run-skill-elicit の出力 `eval-log/skill-brief.json` の**正本スキーマ**は次の 1 ファイルのみ:

- `../../run-skill-create/schemas/skill-brief.schema.json`（13 必須フィールド + ゴールシーク用 `goal`/`purpose_background`/`checklist` 等）

> **SSOT**: フィールド名・型・必須条件・説明はすべて上記スキーマの `properties[].description` を正本とする。本ファイルにフィールド定義を再掲しない（旧 5 項目テンプレート `topic/purpose/trigger_phrases/io_contract` は廃止。13 フィールド版へ一本化済み）。
>
> 聞き取り順・出力例は SKILL.md の `## ゴールシーク実行`（ゴール / 完了チェックリスト / 局面カタログ）が正本。固定の Step 番号はなく、未達フィールドに応じて局面カタログを都度選択する。

## 使い方

1. `run-skill-elicit` を呼ぶ（`topic` 任意）。
2. SKILL.md `## ゴールシーク実行` の局面カタログに沿って対話し、`eval-log/skill-brief.json` を生成する。
3. `run-build-skill` / `run-skill-create` に渡す。

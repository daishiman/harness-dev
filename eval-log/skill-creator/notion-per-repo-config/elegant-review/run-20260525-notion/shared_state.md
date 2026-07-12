# shared_state (Phase1 reset-observer)

## 対象
symlink共有される skill-creator/skill-intake が repo毎の Notion identity (DB ID/API key) を `<repo-root>/.notion-config.json` (gitignore) + macOS Keychain で解決する仕組み。

## 第一印象の懸念 (事実観察のみ)
- A: `.notion-config.json` は repo-root の `.git` を上方探索して特定する単一経路で、本repo直下に DB ID 3件入り実体ファイルが存在する。
- B: Keychain service既定値 `notion-api-key` / account `skill-intake` が `keychain_get_secret.py` のmodule-level定数、`notion_config.py` の default、example/実体 config、README 表の4箇所に同一文字列で記載されている。
- C: service/accountのrepo別差し替え経路は `.notion-config.json` の `keychain_service`/`keychain_account` キー、env `INTAKE_KEYCHAIN_SERVICE`/`INTAKE_KEYCHAIN_ACCOUNT`、CLI `--service`/`--account` の3系統あり、`notion_http.py` 経由は env 経路のみ通る。

## 関連ファイル fresh 読込み状況 (16/16 完了)
1. plugins/skill-creator/scripts/notion_config.py ✓
2. plugins/skill-creator/references/notion-per-repo-setup.md ✓
3. .notion-config.example.json ✓
4. .notion-config.json ✓
5. .gitignore (L31-33 Notion関連) ✓
6. doc/notion-schema/{skill-list,hearing-sheet,improvement-request}.schema.json ✓
7. scripts/sync-notion-schema.py ✓
8. scripts/notion-upsert-plugin.py ✓
9. scripts/notion-submit-improvement.py ✓
10. scripts/lint-notion-relations.py ✓
11. plugins/skill-intake/scripts/publish_notion_page.py ✓
12. plugins/skill-intake/scripts/verify_notion_schema.py ✓
13. plugins/skill-intake/scripts/notion_http.py ✓
14. plugins/skill-intake/scripts/keychain_get_secret.py ✓
15. plugins/skill-intake/skills/run-skill-intake-aggregator/references/notion-db-schema.json ✓
16. plugins/skill-intake/README.md (冒頭 Non-Secrets) ✓

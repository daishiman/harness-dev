# 抽象化チェックリスト

横展開可能な Skill にするための「具体 → 変数」変換ルール。

## 必ず変数化するもの

| 元 | 変数化後 |
|----|----------|
| 特定プロジェクト名 (`harness`, `my-app`) | `{{PROJECT_ROOT}}` |
| 特定 kit ディレクトリ (`creator-kit/`) | `{{KIT_ROOT}}` |
| 特定組織 owner (`team-skills`) | `{{owner}}` |
| 特定ドメイン語 (`スキル`, `記事`, `画像`) | `{{domain_term}}` |
| 特定日付 | `{{date}}` (ISO YYYY-MM-DD) |
| 特定 URL ドメイン | `{{source_url}}` |

## 変数化してはいけないもの

- Claude Code 公式の予約語 (`disable-model-invocation`, `allowed-tools`, `Task`, `Hook` 名)
- 標準 CLI 名 (`git`, `python3`, `security`)
- doc/22 で固定された OS 名 (`mac`, `linux`, `windows`, `unknown`)
- source-tier の列挙値 (`article-text`, `code-verified` 等)

## 検証
`plugins/skill-governance-lint/scripts/lint-path-canonical.py` がハードコード検出を行う。
変数化が必要な箇所が見つかれば exit 1。

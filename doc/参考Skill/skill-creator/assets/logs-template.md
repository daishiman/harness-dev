# Skill Usage Log Fragment Template

skill ledger は 1 entry = 1 file の fragment 化（Changesets パターン）に移行済み。
新しい entry は `LOGS/<YYYYMMDD>-<HHMMSS>-<escapedBranch>-<nonce>.md` 形式の単独ファイルとして作成する。
旧 monolith な `LOGS.md` は **使用禁止**（既存スキルでは `LOGS/_legacy.md` に退避済み）。

## 推奨フロー

```bash
# 追加（writer 経路の正本）
pnpm skill:logs:append --skill <skill-name> --type log --notes "{{実行内容や結果の概要}}"

# 集約読み出し（reader 経路）
pnpm skill:logs:render --skill <skill-name> [--since <ISO8601>] [--out <path>] [--include-legacy]
```

## fragment 単体テンプレ

`LOGS/20260120-100000-feat_my-branch-a1b2c3d4.md` の形式で配置:

```markdown
---
timestamp: 2026-01-20T10:00:00.000Z
branch: feat/my-branch
author: {{agent-name or claude-code}}
type: log
---

# {{タイトル: 1 行サマリ}}

- **Agent**: {{agent-name}}
- **Phase**: {{phase-name}}
- **Result**: ✓ 成功 / ✗ 失敗
- **Notes**: {{実行内容や結果の概要}}
```

## front matter 必須項目

| key       | 値                                                                     |
| --------- | ---------------------------------------------------------------------- |
| timestamp | ISO8601 (UTC)                                                          |
| branch    | 作業ブランチ名（`/` を `_` にエスケープ前の生）                        |
| author    | エージェント名 or `claude-code`                                        |
| type      | `log` / `changelog` / `lessons-learned` のいずれか                     |

## 注意

- 直接 `LOGS.md` / `LOGS/_legacy.md` への append は禁止。writer 経路ガード CI で検出予定。
- nonce は 8 hex 固定（衝突時は `scripts/lib/retry-on-collision.ts` で自動リトライ）。
- `escapedBranch` は `scripts/lib/branch-escape.ts` を経由（truncation 規約あり）。

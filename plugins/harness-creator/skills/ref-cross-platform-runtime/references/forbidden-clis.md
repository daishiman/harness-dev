# Forbidden CLI / Library 一覧 (no-deps 原則)

doc/22 §「許可 CLI ホワイトリスト」に対応する禁止リスト。
`scripts/lint-forbidden-deps.py` で機械検証される。

## 禁止 CLI (OS 標準外)
- `jq`, `yq` — JSON/YAML 操作は Python stdlib `json` で代替
- `rg`, `fd`, `bat` — `grep` / `find` で代替
- `gh` — 必須化しない (任意)
- `node`, `npm`, `npx`, `yarn`, `pnpm` — JavaScript/Node 系 runtime を必須化しない
- `bash` / `.sh` 配布 — Claude/Codex の tool 名として `python3 ...` を起動する場合を除き、Skill成果物の実行単位にしない

## 禁止 Python ライブラリ
- `PyYAML` — frontmatter は自前パーサで処理
- `requests` — `urllib.request` で代替
- `yaml`, `toml` (3rd party)
- `cryptography` — `hmac` / `hashlib` で代替

## 許可される第三者 CLI (OS 別)
- macOS: `security`, `sw_vers`, `xcrun` (Xcode CLT 同梱)
- Windows: `powershell`, `cmd`, `ver`, `systeminfo`
- 共通: `git`

## 実行単位の正本

- scripts / hooks / adapters / deterministic checks は `.py` のみを新規作成する。
- `.js` / `.sh` が必要に見える場合は、まず Python 標準ライブラリで代替できない理由を `skill-build-trace.json` に記録する。例外は governance 承認が必要。

詳細は `plugins/harness-creator/.claude-plugin/plugin.json` の `requirements.external_clis` を正本とする。

# Forbidden CLI / Library 一覧 (no-deps 原則)

doc/22 §「許可 CLI ホワイトリスト」に対応する禁止リスト。
`scripts/lint-forbidden-deps.py` で機械検証される。

## 禁止 CLI (OS 標準外)
- `jq`, `yq` — JSON/YAML 操作は Python stdlib `json` で代替
- `rg`, `fd`, `bat` — `grep` / `find` で代替
- `gh` — 必須化しない (任意)

## 禁止 Python ライブラリ
- `PyYAML` — frontmatter は自前パーサで処理
- `requests` — `urllib.request` で代替
- `yaml`, `toml` (3rd party)
- `cryptography` — `hmac` / `hashlib` で代替

## 許可される第三者 CLI (OS 別)
- macOS: `security`, `sw_vers`, `xcrun` (Xcode CLT 同梱)
- Windows: `powershell`, `cmd`, `ver`, `systeminfo`
- 共通: `git`

詳細は `creator-kit/manifest.json` の `requirements.external_clis` を正本とする。

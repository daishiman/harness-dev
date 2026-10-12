# Forbidden CLI / Library 一覧 (no-deps 原則)

doc/22 §「許可 CLI ホワイトリスト」に対応する禁止リスト。
機械検証は `scripts/lint-forbidden-deps.py` が担う。ただし今は、禁止一覧を読む先の `plugins/skill-governance-lint/manifest.json` が無いので、検査せずに SKIP で exit 0 を返す (Phase 3 carry-over F-7 で manifest を戻す予定)。それまでは本ファイルと設計書22章を読んで守る。

## 禁止 CLI (OS 標準外)
- `jq`, `yq` — JSON/YAML 操作は Python stdlib `json` で代替
- `rg`, `fd`, `bat` — `grep` / `find` で代替
- `gh` — 必須化しない (任意)
- `node`, `npm`, `npx`, `yarn`, `pnpm` — JavaScript/Node 系 runtime を必須化しない
- `bash` / `.sh` 配布 — 生成・検証・adapter・hook の処理 (設計書 28 章 §3.2 の L2) を Skill 成果物の `.sh` にしない。Bash は Claude/Codex の tool 名として Python (`python_cmd`) を起動するときに使う (SKILL.md の Rule 3)。install などの lifecycle の `.sh` (同 L1) は対象の外

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

- scripts (lifecycle の `.sh` を除く) / hooks / adapters / deterministic checks は `.py` のみを新規作成する。
- `.js` / `.sh` が必要に見える場合は、まず Python 標準ライブラリで代替できない理由を `skill-build-trace.json` に記録する。例外は governance 承認が必要。

許可 CLI の正本は設計書22章の「許可 CLI ホワイトリスト (no-deps 原則)」。plugin.json に CLI の一覧は無い。

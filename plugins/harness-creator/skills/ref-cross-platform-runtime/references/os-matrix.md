# OS × Python × 判定マトリクス

doc/22 設計書からの転載＋運用追記。

| OS      | Python 判定                         | python_cmd 優先順 | Node 必須 | shell script 配布 | secret backend            |
| ------- | ----------------------------------- | ----------------- | --------- | ----------------- | ------------------------- |
| macOS   | `platform.system() == "Darwin"`     | `python3`, `python` | 禁止      | 禁止              | Keychain (`security` CLI) |
| Linux   | `platform.system() == "Linux"`      | `python3`, `python` | 禁止      | 禁止              | XDG_CONFIG_HOME/secrets.json |
| Windows | `platform.system() == "Windows"`    | `python`, `python3` | 禁止      | 禁止              | base64 file fallback (not encrypted) |
| WSL     | `platform.system() == "Linux"`      | `python3`, `python` | 禁止      | 禁止              | Linux 経路で統一           |
| 未判定  | `platform.system()` が空/未知       | `unknown`         | 禁止      | 禁止              | env HARNESS_SECRET_<SLUG>_* のみ |

判定エントリポイント: `plugins/skill-governance-automation/scripts/cross_platform_secret.py --probe`

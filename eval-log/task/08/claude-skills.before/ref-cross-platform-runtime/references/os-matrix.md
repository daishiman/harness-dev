# OS × shell × python × 判定コマンド マトリクス

doc/22 設計書からの転載＋運用追記。

| OS      | shell 既定           | 判定コマンド            | 期待 stdout 前方一致          | python3 同梱 | secret backend            |
| ------- | -------------------- | ----------------------- | ----------------------------- | ------------ | ------------------------- |
| macOS   | zsh / bash           | `uname -s`              | `Darwin`                      | あり (3.x)   | Keychain (`security` CLI) |
| Linux   | bash                 | `uname -s`              | `Linux`                       | あり         | XDG_CONFIG_HOME/secrets.json |
| Windows | PowerShell 5.1+      | `ver` または `$PSVersionTable.PSVersion` | `Microsoft Windows` を含む | なし (要 install) | base64 file fallback (not encrypted) |
| WSL     | bash                 | `uname -s`              | `Linux`                       | あり         | Linux 経路で統一           |
| 未判定  | -                    | 上記いずれも失敗        | -                             | -            | env XLSKILLS_SECRET_* のみ |

判定エントリポイント: `creator-kit/scripts/cross_platform_secret.py --probe`

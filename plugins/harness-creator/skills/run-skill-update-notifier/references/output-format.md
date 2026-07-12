# Output Format 規約

## 通知文字列

差分あり時のみ次の 1 行を Skill 実行末尾に付記する:

```
(installed: vX.Y.Z / latest: vA.B.C — /skill-update で更新)
```

## ルール

- `installed` は当該 plugin の `.claude-plugin/plugin.json` の `version` フィールド (文字列をそのまま採用)
- `latest` は `~/.cache/harness/version-snapshot.json` の `plugins.<name>.latest` (CHANGELOG.md から抽出)
- 片方が欠落、または両者一致のときは **空文字列** (= 通知なし)
- `v` 接頭辞が既に付いている場合は二重 `v` 化しない (例: cache に "v1.2.0" が入っていたら "vv1.2.0" としない)
- 末尾の `/skill-update で更新` 部分は Stage 2 で正式 Skill が用意され次第、コマンド名を差し替える
- ANSI カラー・絵文字は使わない (純テキスト)
- locale 分岐は当面なし (日本語固定)

## 例

| installed | latest | 出力 |
|---|---|---|
| `1.0.1` | `1.0.1` | (空) |
| `1.0.1` | `1.1.0` | `(installed: v1.0.1 / latest: v1.1.0 — /skill-update で更新)` |
| `v1.0.1` | `1.1.0` | `(installed: v1.0.1 / latest: v1.1.0 — /skill-update で更新)` |
| `null` | `1.1.0` | (空) |
| `1.0.1` | `null` | (空) |

## 抑制

- 環境変数 `HARNESS_SKILLS_NOTIFY=off` 設定時は **常に空文字列** (graceful suppression)

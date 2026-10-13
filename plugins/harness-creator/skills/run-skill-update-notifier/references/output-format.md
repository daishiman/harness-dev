# Output Format 規約

## 通知の相手

plugin の作者、または同じツリーで開発している人 (plugin.json の `version` と CHANGELOG.md を手で上げる人。
以下まとめて作者)。食い違いは作者の書き忘れなので、文言は作者に向けて書く。install 先では作者でない利用者にも表示されるが、利用者が直すものではない
(不要なら `HARNESS_SKILLS_NOTIFY=off` で止められる)。配布元とは比べないので、利用者に更新を促す文言は出さない。

## 表示経路

1. `notifier-check.py notify` が下の「通知文字列」の 1 行を stdout に出す (無ければ何も出さない)。
2. PostToolUse hook (`hook-notify-skill-end.py`) がその 1 行に `<plugin>: ` を前置し、
   `{"systemMessage": "<plugin>: <1 行>"}` の JSON 1 個を stdout に出す。
3. Claude Code は stdout 全体が JSON 1 個なら JSON として読み、`systemMessage` を利用者に表示する。

PostToolUse の素の stdout は debug log に行くだけで、利用者にも Claude にも見えない。そのため hook は
素のテキストを出さない。`hookSpecificOutput.additionalContext` (Claude への文脈) も付けない。作者に向けた
版の食い違いで、Claude の作業には関係しないため。通知が無いときは何も出さない (空の JSON も出さない)。

hook の stdout の例:

```json
{"systemMessage": "harness-creator: (plugin.json: v1.4.45 / CHANGELOG: v1.2.0 — CHANGELOG が plugin.json の version より古い。CHANGELOG の節の足し忘れの可能性)"}
```

## 通知文字列

表示のラベルと内部名の対応: `plugin.json` = installed、`CHANGELOG` = latest。

食い違いの向きで 3 種に分ける (status は `schemas/output.schema.json`)。

| status | 条件 | 1 行 |
|---|---|---|
| `manifest-behind` | CHANGELOG の版が新しい | `(plugin.json: vX.Y.Z / CHANGELOG: vA.B.C — plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性)` |
| `changelog-behind` | plugin.json の版が新しい | `(plugin.json: vX.Y.Z / CHANGELOG: vA.B.C — CHANGELOG が plugin.json の version より古い。CHANGELOG の節の足し忘れの可能性)` |
| `not-comparable` | どちらかが semver として読めない | `(plugin.json: <値> / CHANGELOG: <値> — 版を比べられない)` |

`in-sync` (版として等しい)・`unknown` (片方が無い・cache が無い)・`skipped` (抑制・通知済み) は何も出さない。
ネットワークには出ないので、オフラインでも status は変わらない。

## ルール

- `installed` は当該 plugin の `.claude-plugin/plugin.json` の `version` フィールド (文字列をそのまま採用)
- `latest` は `~/.cache/harness/version-snapshot.json` の `plugins.<name>.latest` (installed と同じツリーの CHANGELOG.md 先頭から抽出。`<name>` は plugin.json の `name`)
- 片方が欠落、または両者が版として等しいときは **空文字列** (= 通知なし)
- 前後の判定は **semver として** 行う。文字列の大小では決まらない (`"0.10.0" < "0.9.0"` が真になり、0.10.0 が古い扱いになる)
- prerelease 付き (`1.2.0-rc1`) は semver 11 の優先順位に従う (`1.2.0 > 1.2.0-rc1`、`1.2.0-rc2 > 1.2.0-rc1`)
- どちらかが semver として読めないときは向きを決めず、`版を比べられない` とだけ出す (どちらが古いとも言わない)
- semver として読める値は、先頭を `v` に揃えて表示する。`v` が既に付いていれば二重化しない (cache に "v1.2.0" が入っていても "vv1.2.0" にしない)。大文字の `V` も `v` と同じ表記差として扱い、表示は `v` に揃える
- semver として読めない値は書かれたまま表示する (`v` を付けると、版として読めたかのように見えるため)
- 表記だけが違い版として等しい場合 (`1.0.0` と `v1.0.0`、`V1.0.0`) は **空文字列**
- ANSI カラー・絵文字は使わない (純テキスト)
- locale 分岐は当面なし (日本語固定)

## 例

`tests/scripts-plugins/test_harness_creator__notifier_check.py` がこの表を読み、`notifier-check.py` の出力と一致することを確かめる。

| installed | latest | 出力 |
|---|---|---|
| `1.0.1` | `1.0.1` | (空) |
| `1.0.1` | `v1.0.1` | (空) |
| `V1.0.1` | `1.0.1` | (空) |
| `1.0.1` | `1.1.0` | `(plugin.json: v1.0.1 / CHANGELOG: v1.1.0 — plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性)` |
| `v1.0.1` | `1.1.0` | `(plugin.json: v1.0.1 / CHANGELOG: v1.1.0 — plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性)` |
| `0.9.0` | `0.10.0` | `(plugin.json: v0.9.0 / CHANGELOG: v0.10.0 — plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性)` |
| `0.10.0` | `0.9.0` | `(plugin.json: v0.10.0 / CHANGELOG: v0.9.0 — CHANGELOG が plugin.json の version より古い。CHANGELOG の節の足し忘れの可能性)` |
| `1.2.0-rc1` | `1.2.0` | `(plugin.json: v1.2.0-rc1 / CHANGELOG: v1.2.0 — plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性)` |
| `0.2.15` | `0.2.0` | `(plugin.json: v0.2.15 / CHANGELOG: v0.2.0 — CHANGELOG が plugin.json の version より古い。CHANGELOG の節の足し忘れの可能性)` |
| `1.2.0` | `1.2.0-rc1` | `(plugin.json: v1.2.0 / CHANGELOG: v1.2.0-rc1 — CHANGELOG が plugin.json の version より古い。CHANGELOG の節の足し忘れの可能性)` |
| `null` | `1.1.0` | (空) |
| `1.0.1` | `null` | (空) |
| `1.0` | `1.0.0` | `(plugin.json: 1.0 / CHANGELOG: v1.0.0 — 版を比べられない)` |
| `dev` | `1.2.0` | `(plugin.json: dev / CHANGELOG: v1.2.0 — 版を比べられない)` |

## 抑制

- 環境変数 `HARNESS_SKILLS_NOTIFY=off` 設定時は **常に空文字列** (graceful suppression)
- 同じ session で同じ plugin の通知は 1 回だけ出す。hook は payload の `session_id` を
  `notify --session-id` に渡し、通知を出したら cache の `notified.<plugin>` に
  `{"session_id": ..., "last_notified_at": ...}` を残す。同じ `session_id` の 2 回目以降は空文字列。
  記録は plugin ごとに最新の session 1 件だけで、`refresh` しても消さない
- `session_id` が渡らない (手で `notify` を呼んだ、payload に無い) ときは抑止せず毎回出す
- 空文字列のとき、hook は stdout に何も出さない

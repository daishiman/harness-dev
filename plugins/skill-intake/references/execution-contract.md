---
name: execution-contract
description: scripts/*.py 実行の正本契約。Claude Code / Codex / 手動 CLI / Bash hook の 4 経路で同一スクリプトが動くための前提・引数・終了コード規約。
type: reference
---

# 実行環境契約 (Execution Contract)

`plugins/skill-intake/scripts/*.py` は以下 4 経路で**同一コマンド・同一引数・同一終了コード**で動く。
SubAgent から `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/<name>.py ...` と書かれている箇所はすべてこの契約に従う。

## 前提条件

| 項目 | 要件 |
|---|---|
| Python 3 | macOS 標準 `/usr/bin/python3` (3.9 以上) で動作 |
| OS | macOS (Keychain 経由のため; 他 OS は `keychain_get_secret.py` 差し替え必須) |
| cwd | repo 配置ではリポジトリルート、単独 install では plugin root。スクリプトは `$CLAUDE_PLUGIN_ROOT` / 相対パス解決に対応する |
| 依存 | Python 3.9 以上 + `jsonschema` / `jinja2` |
| トークン | macOS Keychain (service=`notion-api-key.<keychain-prefix>`, account=`<keychain-prefix>`) のみ。`.env` / 環境変数経由禁止 |

## 実行経路マトリクス

| 経路 | 起動方法 | コマンド例 |
|---|---|---|
| Claude Code (Bash ツール) | agent の `allowed-tools: Bash` から | `python3 "$CLAUDE_PLUGIN_ROOT/scripts/quality_gate.py" output/foo/intake.json` |
| Claude Code (`!` プレフィックス) | ユーザーがチャット欄に `!` を付ける | `!python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/keychain_get_secret.py --check` |
| Codex (自然文 / exec) | shell ツール / `codex exec "..."` | `codex exec "python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/verify_notion_schema.py"` |
| 手動 CLI | ターミナル直叩き (shebang あり) | `./plugins/skill-intake/scripts/cross_check.py intake.json intake.md` |
| Bash hook (`PreToolUse`) | `plugin.json` で配線 | `pre-publish-secret-scrub.sh` が `output/` を走査 |

## 引数規約

新スクリプト群は**positional args 優先**で、フラグは長形式 (`--name value`)。旧 `--in / --out / --agent / --token-env` は使わない。

| パターン | 例 |
|---|---|
| 単一入力ファイル | `python3 validate_intake.py output/<hint>/intake.json` |
| 入力2つ (md + json 整合) | `python3 cross_check.py output/<hint>/intake.json output/<hint>/intake.md` |
| フラグ + 値 | `python3 verify_notion_schema.py --database-id 11111111... --on-conflict skip-warn` |
| dry-run 切替 | `--dry-run` (副作用なし) |
| 安全確認 | `keychain_get_secret.py --check` (本体非表示) / `--print-unsafe` (本体出力、共有端末禁止) |

## 終了コード規約

| code | 意味 |
|---|---|
| 0 | OK / PASS |
| 1 | FAIL (lint/検証で不整合検出) |
| 2 | INPUT_ERROR (引数不足、ファイル不在、未知のフラグ) |
| 3 | DEPENDENCY_ERROR (mmdc 等の外部ツール不在で hard-fail させたいケース) |
| 44 | KEYCHAIN_ERROR (macOS Keychain 取得失敗 / 空 / 非 macOS) |

orchestrator は exit≠0 を全て **次フェーズ中止**として扱う。44 は専用扱いで `references/keychain-setup.md` を案内して停止する。
`render_to_image.py` / `render_to_svg.py` は Mermaid (.mmd) 経路で mmdc 不在時 exit 3 (`ok:false, reason=DEPENDENCY_ERROR`) が既定で、明示 `--allow-placeholder` (CI/テスト専用) 指定時のみ placeholder 生成で exit 0 とする。`render_to_image.py` の静的 SVG (.svg) 経路は mmdc 非依存 (同梱 PNG `assets/cvis-*.png` コピー → cairosvg fallback) で、両手段不可の場合のみ exit 3 (`reason=DEPENDENCY_ERROR`) とする。

## 出力規約

- 機械可読系 (`validate_intake.py` / `quality_gate.py` / `verify_notion_schema.py` 等) は **JSON を stdout 単独行** で出力。診断ログは stderr へ。
- ファイル副作用ありの script (`prepare_notion_assets.py` / `create_notion_database.py`) は処理サマリを stdout、生成パスを完全絶対パスで報告。
- `publish_notion_page.py` のみ Notion REST `POST /v1/pages` を発火する。それ以外の script は副作用なし or ローカル書き込みのみ。

## hook 連携

`plugin.json` の `hooks.PreToolUse` (matcher=Bash) で `pre-publish-secret-scrub.sh` が自動配線される。
これにより `output/` 以下に `ntn_*` / `secret_*` / `Bearer ...` パターンを含むファイルがあると Notion 公開 Bash 実行直前に exit 2 でブロックされる。

## 互換性メモ

- 旧 `doc/skill-intake-interviewer/scripts/` の `--in / --out / --agent` 引数は廃止。移行時は positional 形式に書き換える。
- `compose_slack_message.py` は意図的に未移植 (Slack はスコープ外)。
- `render_notion_page.py` は blocks JSON 生成のみで API 発火は **`publish_notion_page.py`** が単独責務。

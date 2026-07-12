---
name: run-skill-update-notifier
description: Skill 実行末尾に最新版有無を1行通知するとき、ユーザーが意識せず最新版の存在に気づける仕組みが欲しいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Bash(python3 *)]
kind: run
prefix: run
effect: conversation-output
owner: team-platform
since: 2026-05-21
version: 0.2.0
source: internal
source-tier: internal
last-audited: 2026-05-21
audit-trigger: quarterly
role_suffix: none
responsibility_refs:
  - prompts/R1-notify.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: CHANGELOG 不在・オフライン・cache 不在・権限不足・HARNESS_SKILLS_NOTIFY=off のいずれの分岐でも例外を握りつぶし空文字列(no-op)かつ exit 0 へ倒れ Skill 実行を妨げないことを notifier-check.py の単体テストで機械検証できる(graceful degradation)。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: PostToolUse hook が tool_name=="Skill" のときだけ末尾に1行付記し Read や Bash の末尾には付かないこと、および同一 plugin の通知が last_notified_at により1セッション内で重複しないことを hook-notify-skill-end.py の単体テストで機械検証できる(filter と重複抑止)。
      verify_by: test
    - id: IN3
      loop_scope: inner
      text: 既存 manifest(plugin.json marketplace.json bundles.json skill-intake-self-updater)を一切変更せず書込先が version-snapshot.json のみに限定され Python stdlib だけで完結することを read-only 静的 lint で機械検証できる(非破壊と外部依存ゼロ)。
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: スキル全体がユーザ目的(意識せず最新版の存在に気づける非破壊な気づき提供)を最適に反映し、cache 鮮度判定・通知整形・graceful 保護層という責務分割が分岐の多い文脈で過不足なく目的に整合していることを評価できる。
      verify_by: elegant-review
---

# run-skill-update-notifier

## Purpose & Output Contract

**入力**: なし (hook 経由で自動起動) / 明示起動時はオプションで `--check-only` / `--refresh`。
**出力**: Skill 実行末尾に 1 行付記 `(installed: vX.Y.Z / latest: vA.B.C — /skill-update で更新)`。同一/未提供/オフライン時は無出力。
**副作用**: `~/.cache/harness/version-snapshot.json` の更新のみ。plugin manifest は変更しない。
**完了条件**: cache 比較が完了 (差分有無を問わず) し、通知出力 or no-op を決定したとき。

## Boundary

通知のみ。実際の pull/install/apply/rollback はやらない。version 重複解消もやらない (Stage 0/2 の別 Skill に分離)。既存 plugin.json / marketplace.json / bundles.json / skill-intake-self-updater は一切変更しない。

## Key Rules

1. **非破壊**: 既存 manifest を touch しない (read-only)。
2. **graceful degradation**: CHANGELOG.md 不在 / オフライン / cache 不在 / 権限不足のいずれも静かに no-op。エラーで Skill 実行を妨げない。
3. **Python stdlib のみ**: 外部依存ゼロ (json, pathlib, urllib.request, os, datetime のみ)。
4. **24h TTL**: cache 鮮度判定は 24 時間。それ未満は再 scan しない。
5. **PostToolUse filter**: hook は `tool_name == "Skill"` のときだけ通知発火。Bash/Read 等の末尾には付かない。
6. **抑制フラグ**: 環境変数 `HARNESS_SKILLS_NOTIFY=off` で完全無効化。

## Hook Integration Map

| Hook Event | Script | 役割 | exit |
|---|---|---|---|
| UserPromptSubmit (matcher=`.*`) | `scripts/hook-cache-refresh.py` | 24h TTL で cache 再 scan (バックグラウンド準同期) | 0固定 |
| PostToolUse (matcher=`Skill`) | `scripts/hook-notify-skill-end.py` | `tool_name == "Skill"` のとき末尾 1 行付記 | 0固定 |

settings.json マージ案は `references/hook-wiring.md` 参照。自動 merge はしない (人間承認)。

## Responsibilities (brief 由来)

- **R1 changelog-cache-check**: 各 plugin の `CHANGELOG.md` を読み、cache と差分検出 (`scripts/notifier-check.py`)
- **R2 notification-formatting**: 差分時の 1 行通知整形 (出力規約は `references/output-format.md`)
- **R3 graceful-degradation-guard**: 例外を握りつぶし no-op に倒す保護層

## ゴールシーク実行

### ゴール (Goal)

cache 比較が完了し（差分有無を問わず）、`tool_name == "Skill"` 末尾に最新版有無の 1 行通知を出力する、または no-op を決定した状態（既存 manifest は不変・graceful degradation を維持）。

### 目的・背景 (Why)

ユーザーが意識せず最新版の存在に気づける仕組みを、Skill 実行を妨げず非破壊で提供するため。cache 鮮度・CHANGELOG 有無・オフライン・抑制フラグなど分岐が多く、固定手順では graceful 維持が脆い。到達状態（通知 or no-op の決定）をゴールに据える。

### 完了チェックリスト (Checklist)

- [ ] cache 鮮度判定（`notifier-check.py --mode cache-status` → `fresh`/`stale`/`absent`）を実施済み（`fresh` なら scan を省略）
- [ ] `stale`/`absent` 時は `--mode refresh --plugins-root plugins/` で各 `plugins/*/CHANGELOG.md` の最新 version を抽出し `~/.cache/harness/version-snapshot.json` へ atomic rename で書き出し済み
- [ ] 通知文字列を `--mode notify --plugin $PLUGIN_NAME` で生成し、installed(plugin.json) vs latest(cache) を比較済み
- [ ] 一致 / cache 未提供 / installed 未取得 / `HARNESS_SKILLS_NOTIFY=off` のいずれかは空文字列（no-op）になっている
- [ ] 差分ありのみ `(installed: vX.Y.Z / latest: vA.B.C — /skill-update で更新)` を出力している
- [ ] `PostToolUse` hook (`hook-notify-skill-end.py`) が `tool_name == "Skill"` のときだけ末尾に付記し、Read/Bash 末尾には付かない
- [ ] 1 セッション内で同一 plugin の通知が重複しない（cache に `last_notified_at` 記録）
- [ ] CHANGELOG 不在 / オフライン / cache 不在 / 権限不足のいずれも例外を握りつぶし exit 0 の no-op に倒れている
- [ ] 既存 manifest（plugin.json / marketplace.json / bundles.json / skill-intake-self-updater）を一切変更していない（read-only）
- [ ] ネットワーク取得を行わず Python stdlib のみで完結している（24h TTL 鮮度判定）

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップに従う。本スキル固有差分:

- 対象ファイル: `~/.cache/harness/version-snapshot.json`（書込対象はこれのみ）、各 `plugins/*/CHANGELOG.md`（read-only）
- 固定パス/閾値: cache 鮮度 24h TTL（時刻欠落時は `stale` 扱い）、通知書式 `(installed: ... / latest: ... — /skill-update で更新)`、抑制 `HARNESS_SKILLS_NOTIFY=off`
- Hook 連携は `references/hook-wiring.md` の配線案に従い、settings.json の自動 merge はしない（人間承認）
- いずれの分岐でも Skill 実行を止めない（exit 0 固定 / graceful no-op）。未達があれば原因（cache/CHANGELOG/権限）を特定して no-op か通知かを再決定する

### 局面カタログ (順序は都度判断)

- 鮮度確認: `python3 scripts/notifier-check.py --mode cache-status`（`fresh` なら scan skip）
- scan/更新: `python3 scripts/notifier-check.py --mode refresh --plugins-root plugins/`
- 通知生成: `python3 scripts/notifier-check.py --mode notify --plugin "$PLUGIN_NAME"`
- hook 付記: `hook-notify-skill-end.py` が `tool_name == "Skill"` を判定し通知出力を末尾に付記（重複抑止: `last_notified_at`）

## Constraints

- 実行中スキルの自己書換禁止 (`PreToolUse` 等で deny は不要、本 Skill は write しないため)。
- ネットワーク取得は行わない (cache はローカルファイルのみ)。将来 Stage 2 で git fetch を別 Skill に分離。
- 出力フォーマットの変更は `references/output-format.md` を Edit し、本 SKILL は touch しない。

## Gotchas

- **PostToolUse 全 tool 発火事故**: filter を忘れると Read/Bash 末尾にも通知が付き UX 大破壊。`hook-notify-skill-end.py` の matcher 必須。
- **cache 不在初回**: 起動直後は cache 空。Step 2 が走るまで Step 3 は無出力 (graceful)。
- **24h TTL の挙動**: `last_refreshed_at` が cache に無いと毎回 refresh して負荷増。`fresh` 判定は時刻欠落時 `stale` 扱い。
- **マルチプロジェクト共用 cache**: `~/.cache/harness/` は user-global。複数 worktree で同じ plugin を見ても整合する設計。

## Additional Resources

- `scripts/notifier-check.py` — cache 比較ロジック (CLI 単体実行可)
- `references/output-format.md` — 通知文字列規約
- `references/hook-wiring.md` — settings.json hook 配線案
- 設計書 10 章 §7 — Hook 競合解決
- 関連 Stage: Stage 0 `lint-version-singletruth` (将来) / Stage 2 `run-skill-update-apply` (将来)

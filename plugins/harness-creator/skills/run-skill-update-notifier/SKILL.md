---
name: run-skill-update-notifier
description: Skill 実行末尾に、同じツリー内の plugin.json と CHANGELOG 先頭の版の食い違いを1行通知するとき、version の上げ忘れや CHANGELOG の節の足し忘れに作者が意識せず気づける仕組みが欲しいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Bash(python3 *)]
kind: run
prefix: run
effect: conversation-output
runtime_root_policy: host-skill-path
goal_seek:
  engine: inline
  fork: inline
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
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: CHANGELOG 不在・cache 不在・cache を読めない・HARNESS_SKILLS_NOTIFY=off では空文字列(no-op)、cache を読めるが書けないときは通知を出して記録だけ飛ばし、どの分岐でも例外を握りつぶし exit 0 で Skill 実行を妨げないことを notifier-check.py の単体テストで機械検証できる(graceful degradation)。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: PostToolUse hook が tool_name=="Skill" のときだけ通知を systemMessage に入れた JSON 1個を stdout に出し(利用者に表示される) Read や Bash では何も出さないこと、および同一 plugin の通知が last_notified_at により1セッション内で重複しないことを hook-notify-skill-end.py の単体テストで機械検証できる(filter と重複抑止)。
      verify_by: test
    - id: IN3
      loop_scope: inner
      text: 既存 manifest(plugin.json marketplace.json bundles.json skill-intake-self-updater)を一切変更せず書込先が version-snapshot.json のみに限定され Python stdlib だけで完結することを read-only 静的 lint で機械検証できる(非破壊と外部依存ゼロ)。
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: スキル全体がユーザ目的(同じツリー内の plugin.json の version と CHANGELOG 先頭の版の食い違いに作者が意識せず気づける非破壊な気づき提供。配布元とは比べない)を最適に反映し、cache 鮮度判定・通知整形・graceful 保護層という責務分割が分岐の多い文脈で過不足なく目的に整合していることを評価できる。
      verify_by: elegant-review
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-skill-update-notifier

## Purpose & Output Contract

**入力**: なし (hook 経由で自動起動) / 明示起動時は `scripts/notifier-check.py` の subcommand (`cache-status` / `refresh` / `notify`)。
**範囲 (Stage 1)**: 同じツリー（install 先またはチェックアウト）の中の plugin.json の version（installed）と CHANGELOG 先頭の版（latest）の食い違いを知らせる。配布元と比べて新しい版を知らせ、更新へ案内するのは将来の Stage 2（`run-skill-update-apply`）の範囲で、本 Skill はやらない。
**通知の相手**: plugin の作者、または同じツリーで開発している人（plugin.json の version と CHANGELOG を手で上げる人。以下まとめて作者）に向けた通知である。install 先では作者でない利用者にも表示されるが、利用者が直すものではない（不要なら `HARNESS_SKILLS_NOTIFY=off` で止める）。
**出力**: Skill の実行後、版が食い違うときだけ 1 行を、hook が `systemMessage` として利用者に表示する。文言は向きで 3 種（plugin.json の version の上げ忘れ / CHANGELOG の節の足し忘れ / 版を比べられない）。書式の正本は `references/output-format.md`。一致 / 片方欠落 / 抑制 / 同じ session で通知済みのときは何も出さない。
**副作用**: `~/.cache/harness/version-snapshot.json` の更新のみ。plugin manifest は変更しない。
**完了条件**: cache 比較が完了 (差分有無を問わず) し、通知出力 or no-op を決定したとき。

## Boundary

通知のみ。実際の pull/install/apply/rollback はやらない。配布元とは比べない。version 重複解消もやらない (別 Skill に分離)。既存 plugin.json / marketplace.json / bundles.json / skill-intake-self-updater は一切変更しない。

## Key Rules

1. **非破壊**: 既存 manifest を touch しない (read-only)。
2. **graceful degradation**: CHANGELOG.md 不在 / cache 不在 / cache を読めないときは静かに no-op。cache を読めるが書けないときだけは、通知は出して通知済みの記録だけを飛ばす（通知を失う向きには倒さない）。どの場合も exit 0 で、エラーで Skill 実行を妨げない。
3. **Python stdlib のみ**: 外部依存ゼロ (`argparse`, `datetime`, `json`, `os`, `pathlib`, `re`, `subprocess`, `sys` のみ。ネットワーク系は import しない)。
4. **24h TTL**: cache 鮮度判定は 24 時間。それ未満は再 scan しない。
5. **PostToolUse filter**: hook は `tool_name == "Skill"` のときだけ通知発火。Bash/Read 等の末尾には付かない。
6. **抑制フラグ**: 環境変数 `HARNESS_SKILLS_NOTIFY=off` で完全無効化。

## Hook Integration Map

| Hook Event | Script | 役割 | exit |
|---|---|---|---|
| UserPromptSubmit (matcher=`.*`) | `scripts/hook-cache-refresh.py` | stale/absent のときだけ cache を同期で再 scan (timeout 15 秒。24h TTL 以内は即 return) | 0固定 |
| PostToolUse (matcher=`Skill`) | `scripts/hook-notify-skill-end.py` | `tool_name == "Skill"` のとき、通知を `systemMessage` の JSON 1 個で stdout に出し、利用者に表示させる | 0固定 |

配線は harness-creator の `hooks/hooks.json` に同梱され、plugin を install すると Claude Code が自動で読む。hooks.json は公開 entry point (`hooks/cache-refresh.py` / `hooks/notify-skill-end.py`) を起動し、それが上の script へ委譲する。settings.json を手で編集する必要はない。詳細は `references/hook-wiring.md`。

## Responsibilities (brief 由来)

- **R1 changelog-cache-check**: 各 plugin の `CHANGELOG.md` を読み、cache と差分検出 (`scripts/notifier-check.py`)
- **R2 notification-formatting**: 差分時の 1 行通知整形 (出力規約は `references/output-format.md`)
- **R3 graceful-degradation-guard**: 例外を握りつぶし no-op に倒す保護層

<!-- runtime-root-contract:v1 -->
## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。
<!-- /runtime-root-contract:v1 -->

## ゴールシーク実行

### ゴール (Goal)

cache 比較が完了し（差分有無を問わず）、`tool_name == "Skill"` の実行後に版の食い違いの 1 行通知を hook から `systemMessage` として利用者に表示する、または no-op を決定した状態（既存 manifest は不変・graceful degradation を維持）。

### 目的・背景 (Why)

同じツリー内の plugin.json と CHANGELOG の版の食い違い（CHANGELOG の節の足し忘れや version の上げ忘れ）に、作者が意識せず気づける仕組みを、Skill 実行を妨げず非破壊で提供するため。cache 鮮度・CHANGELOG 有無・抑制フラグなど分岐が多く、固定手順では graceful 維持が脆い。到達状態（通知 or no-op の決定）をゴールに据える。

### 完了チェックリスト (Checklist)

- [ ] cache 鮮度判定（`notifier-check.py cache-status` → `fresh`/`stale`/`absent`）を実施済み（`fresh` なら scan を省略）
- [ ] `stale`/`absent` 時は `notifier-check.py refresh` に plugins/ と自 plugin root を絶対パスで渡し（cwd 基準の `plugins/` は渡さない）、各 plugin の `CHANGELOG.md` 先頭の version を抽出し `~/.cache/harness/version-snapshot.json` へ atomic rename で書き出し済み
- [ ] snapshot の key は plugin.json の `name`（読めなければディレクトリ名）。同じ name が複数ある（install 先に版ディレクトリが並ぶ）ときは、`--plugin-root` で渡したもの → installed が semver として読めるもの → semver で最大のもの → パスが辞書順で後ろのもの、の順で 1 つに決める
- [ ] 通知文字列を `notifier-check.py notify --plugin $PLUGIN_NAME` で生成し、installed(plugin.json) vs latest(cache) を比較済み
- [ ] 一致 / cache 未提供 / installed 未取得 / `HARNESS_SKILLS_NOTIFY=off` のいずれかは空文字列（no-op）になっている
- [ ] 版の前後を semver として比較している（文字列比較では `"0.10.0" < "0.9.0"` が真になり向きが逆転する）。先頭の `v` / `V` は表記差として読み飛ばす
- [ ] 食い違いの向きで文言を分けている: CHANGELOG の版が新しい → version の上げ忘れ、plugin.json の版が新しい → CHANGELOG の節の足し忘れ、どちらかが semver として読めない → 向きを決めず「版を比べられない」。文字列は `references/output-format.md` に従い、利用者に更新を促す文言は出さない
- [ ] `PostToolUse` hook (`hook-notify-skill-end.py`) が `tool_name == "Skill"` のときだけ、通知に `<plugin>: ` を前置して `systemMessage` を持つ JSON 1 個を stdout に出し、Read/Bash や通知の無いときは何も出さない
- [ ] 1 セッション内で同一 plugin の通知が重複しない（hook が payload の `session_id` を `--session-id` で渡し、cache の `notified.<plugin>` に `session_id` と `last_notified_at` を記録。`session_id` の無い payload では抑止しない）
- [ ] CHANGELOG 不在 / cache 不在 / 権限不足のいずれも例外を握りつぶし exit 0 に倒れている（cache を読めないときは no-op、読めるが書けないときは通知を出して記録だけ飛ばす）
- [ ] 既存 manifest（plugin.json / marketplace.json / bundles.json / skill-intake-self-updater）を一切変更していない（read-only）
- [ ] ネットワーク取得を行わず Python stdlib のみで完結している（24h TTL 鮮度判定）

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップに従う。本スキル固有差分:

- 対象ファイル: `~/.cache/harness/version-snapshot.json`（書込対象はこれのみ）、各 `plugins/*/CHANGELOG.md`（read-only）
- 固定パス/閾値: cache 鮮度 24h TTL（時刻欠落時は `stale` 扱い）、通知書式（正本は `references/output-format.md`）、抑制 `HARNESS_SKILLS_NOTIFY=off`
- Hook 連携は `hooks/hooks.json` で plugin install 時に自動配線される（`references/hook-wiring.md`）。settings.json は編集しない
- いずれの分岐でも Skill 実行を止めない（exit 0 固定 / graceful no-op）。未達があれば原因（cache/CHANGELOG/権限）を特定して no-op か通知かを再決定する

### 局面カタログ (順序は都度判断)

パスは harness-creator の plugin root（`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`）基準で渡す。cwd 基準の相対パスでは呼ばない。

- 鮮度確認: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-skill-update-notifier/scripts/notifier-check.py" cache-status`（`fresh` なら scan skip）
- scan/更新: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-skill-update-notifier/scripts/notifier-check.py" refresh --plugins-root "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/.." --plugin-root "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"`（`hook-cache-refresh.py` と同じ解決。stale/absent のときだけ走らせるなら `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-skill-update-notifier/scripts/hook-cache-refresh.py"`）
- 通知生成: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-skill-update-notifier/scripts/notifier-check.py" notify --plugin "$PLUGIN_NAME"`
- hook 出力: `hook-notify-skill-end.py` が `tool_name == "Skill"` を判定し、通知を `{"systemMessage": "<plugin>: <通知>"}` の JSON 1 個で stdout に出す（重複抑止: payload の `session_id` を渡し、cache の `notified.<plugin>.last_notified_at` に記録）

## Constraints

- 実行中スキルの自己書換禁止 (`PreToolUse` 等で deny は不要。本 Skill の書き込みは `~/.cache/harness/version-snapshot.json` だけで、Skill 自身のファイルには書かないため)。
- ネットワーク取得は行わない (cache はローカルファイルのみ)。
- 出力フォーマットの変更は `references/output-format.md` を Edit し、本 SKILL は touch しない。

## Gotchas

- **素の stdout は利用者に届かない**: PostToolUse hook が素のテキストを print しても debug log に行くだけで、利用者にも Claude にも見えない。stdout 全体を `systemMessage` を持つ JSON 1 個にする（ほかのテキストを混ぜると JSON として読まれない）。
- **PostToolUse 全 tool 発火事故**: filter を忘れると Read/Bash 末尾にも通知が付き UX 大破壊。`hooks/hooks.json` の matcher=`Skill` と `hook-notify-skill-end.py` 内の `tool_name == "Skill"` 判定の両方で絞る。
- **cache 不在初回**: 起動直後は cache 空。refresh（scan/更新の局面。UserPromptSubmit hook が走らせる）が走るまで notify は無出力 (graceful)。
- **24h TTL の挙動**: `last_refreshed_at` が cache に無いと毎回 refresh して負荷増。`fresh` 判定は時刻欠落時 `stale` 扱い。
- **install 先の走査範囲**: install 先では `--plugins-root` が `<marketplace>/<name>/`（版ディレクトリの親）になるので、snapshot に入るのは自 plugin（harness-creator）だけで、他 plugin の Skill には通知が出ない。チェックアウトでは `plugins/` 全体を見る。
- **共用 cache と重複抑止の制限**: `~/.cache/harness/` は user-global で、全 session が同じ snapshot を読む。重複抑止の記録は plugin ごとに最新の session 1 件だけなので、2 つの session が同じ plugin を A→B→A と交互に使うと A にもう一度出る。通知が増える向きの制限で、通知を黙って失う向きには倒れない。
- **cache に書けないときは重複抑止が働かない**: `~/.cache/harness/` を読めても書けないと、通知済みの記録（`notified.<plugin>`）が残らない。同じ session でも Skill を使うたびに同じ通知がもう一度出る。通知を失わない側に倒した設計（notifier-check.py は表示の後に記録する）で、直すには cache の書き込み権限を戻す。
- **Codex では通知が自動で出ない**: Codex に配線されるのは UserPromptSubmit の cache-refresh だけで、PostToolUse（matcher=`Skill`）の notify-skill-end は Claude Code 専用（`.codex/hooks/registry.json` の products が `claude` だけ）。Codex で通知を見るには、局面カタログの通知生成（`notifier-check.py notify`）を明示して起動する。

## Additional Resources

- `scripts/notifier-check.py` — cache 比較ロジック (CLI 単体実行可)
- `references/output-format.md` — 通知文字列規約
- `references/hook-wiring.md` — `hooks/hooks.json` による hook 配線と無効化の方法
- 設計書 10 章 §7 — Hook 競合解決
- 関連 Stage: Stage 0 `lint-version-singletruth` (将来)

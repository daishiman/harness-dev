---
name: run-governance-automation
description: governanceの登録・rubric合成を実行したいとき、再評価・rollback automationを安全に選択したいときに使う。
kind: run
prefix: run
goal_seek:
  engine: inline
  fork: inline
version: 0.1.0
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash, Read, Glob
effect: local-artifact
runtime_root_policy: host-skill-path
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-governance-automation
source-tier: internal
completeness_exempt:
  - "prompts: 仕事は目的に合う scripts/ の entrypoint を選んで help・preflight・実行の receipt を返すことだけで、サブエージェントの LLM に任せる責務が無い。選び方は本文の「目的とentrypointの対応」を正本とし、R-id 単位の 7 層プロンプトは適用外。"
  - "manifest: goal_seek.engine=inline が目的から entrypoint を都度選ぶため、固定 phase の workflow-manifest.json は適用外。停止条件と配線は本文 ## ゴールシーク実行 を正本とする。"
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 選択したautomation entrypointのhelpとread-only preflightを実行し非0またはreceipt欠落を成功へ畳んでいない
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: apply rollback 通知の外部作用はユーザー承認後だけ実行されcommand exit changed pathsと残リスクが報告されている
      verify_by: evaluator
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

Purpose & Output Contractの最小の実成果物をmain contextで作成する。parse/open・secret・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはそのままhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。

# run-governance-automation

## Purpose & Output Contract

`scripts/`のautomation entrypointを利用目的に対応付け、help/preflight後に実行結果を返す。

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。解決できなければ停止する。

## 目的とentrypointの対応

「既定で書き込む」entrypoint は4本ある。`compute-rubric-hash.py`・`write-eval-log.py` は `--dry-run` を付けない限り呼んだ時点でファイルを変えるので、preflightでは必ず `--dry-run` を付ける。`doc-to-skill-adapter.py`（`--out` に書く）と `extract-session-events.py`（log に追記する）は `--dry-run` を持たないので、preflightは `--help` だけにして本実行しない（`extract-session-events.py` は `--help` にも対応しない。表を参照）。ほかの entrypoint の多くは `--dry-run` を受け付けず、付けると argparse の exit 2 になる（`rollback-to-stable.py` は互換のため受け付けるが、動きは変わらない）。

| 目的 | entrypoint | 既定の動き | 書き込み |
|---|---|---|---|
| manifest登録 | `build-manifest-registration-plan.py` | 対象はこの script を置いた plugin 自身に固定で（引数で変えられない）、この plugin は plugin.json 形式なので、必須キーを検査するだけの proposals が空の exit 0 になる（実際には何も登録しない）。未登録ファイルの追加計画を出し、追加候補があって `--apply` が無いと `needs_confirmation` で exit 1 になるのは、legacy の manifest.json 形式の plugin に置いたときだけ | しない（この plugin では `--apply` を付けても変えない。plugin.json 形式の分岐が `--apply` を見る前に戻る）。plugin を marketplace.json・bundles.json へ登録するのは repo の `scripts/validate-plugin-completeness.py --fix` |
| rubric合成 | `compose-rubrics.py` | 合成した rubric JSON を stdout に出す | しない |
| rubric hash | `compute-rubric-hash.py` | **既定で書き込む**（rubric.json の rubric_hash と rubric.normalized.json） | `--dry-run` で hash の計算だけにする |
| 再評価 | `re-evaluate-on-rubric-bump.py` | major bump の再評価対象を、スキルごとに最新の評価記録で判定して出す（plugin が違えば同じ名前でも別のスキル。別の rubric_id の記録は比べない）。対象があっても exit 0。rubric を読めない・score ログに版を読めない行がある・`--eval-log-dir` がディレクトリでないと exit 2。`--post-tool-use`（PostToolUse hook）では L0 rubric の編集のときだけ走査し、結果を additionalContext で返して常に exit 0 | しない |
| rollback | `rollback-to-stable.py` | `--rubric` と同じ rubric_id の節のうち、現行版より古く ceiling 以下の最新の正式版への巻き戻し計画（照合用の hash と手順）を出す。rubric.json に rubric_id があれば、rubric_id の行が無い節は候補にしない（安全側）。`params_source` が `default` なら ceiling は既定値。候補が無い・`--versions-md` に渡したファイルが無いと exit 1（option そのものを省くと argparse の exit 2）。`--rubric` の rubric.json が無い・rubric_id が空でない文字列でない（空文字列も含む）と exit 2 | しない。巻き戻しは承認後に、対象の版を発効した commit の L0 rubric.json と assign 側の派生 rubric.json を一組で戻し（ref-skill-design-rubric に templates/ は無い）、`compute-rubric-hash.py --dry-run` で hash を計算して rubric-versions.md の記録と照合する。hash の記録が無ければ `git diff <commit> -- <rubric>` が空であることで照合する |
| 変更カテゴリ判定 | `guard-change-category.py` | 変更を P0〜P3 に分類し、未承認か cooldown 違反なら exit 1。policy が無い・不正、`--base` の ref が無いときは exit 2 | しない |
| 招集通知 | `notify-if-governance-trigger.py` | trigger.json の breached があれば招集文を出す。どの hooks.json にも登録しておらず、手で呼ぶ。読めないときは stderr に警告して exit 0。未知の引数だけ exit 2 | しない |
| 評価記録 | `write-eval-log.py` | **既定で書き込む**（score JSONL へ1行追記） | `--dry-run` で記録内容の表示だけにする |
| 設計書の採点準備 | `doc-to-skill-adapter.py` | **既定で書き込む**（`--out` は必須）。`--doc` の設計書を、assign-skill-design-evaluator に渡す brief JSON に変える（26章）。exit 1=入力エラー、2=usage | `--out` に書く |
| session event の収集 | `extract-session-events.py` | **既定で書き込む**。位置引数（`user_prompt`・`tool_use`・`stop`）と hook の JSON（stdin）を受け取り、session event を記録する（35章。opt-in で、hooks に登録したときだけ動く）。`--help` に対応せず、未知の引数は stderr に WARN を出して exit 0 で終わる（help を読めたように見えるので注意）。hook の入力では exit 0（UTF-8 として読めない stdin だけは exit 1） | `<log root>/<YYYY-MM-DD>.jsonl` に追記する（日付は UTC）。log root は、`CLAUDE_LOG_ROOT` があればその直下（`.claude/logs` は付かない）、無ければ `$PROJECT_ROOT/.claude/logs`、どちらも無ければ plugin の `.claude/logs`（利用者の作業ディレクトリではない） |
| 兄弟 plugin の root | `extract-plugin-root.py` | `<plugin-name>` の root を絶対パスで返す。exit 1=見つからない、2=usage | しない |

**receipt**：実行したcommand、exit code、stdoutの要点（計画JSON・hash・対象一覧）、書き込むentrypointでは変わったpath（`git status --short` で確かめる）の4つ。どれかが欠けた実行は成功として報告しない。

## Key Rules

- plugin rootは「Runtime root contract」の手順で解決する。
- 最初に対象scriptの`--help`を実行する。
- `guard-change-category.py` は consumer の作業ディレクトリを保って実行する。`python3 "$PLUGIN_ROOT/scripts/extract-plugin-root.py" skill-governance-config` で依存pluginの実在する絶対rootを解決し、`--policy "<解決済config-plugin-root>/config/governance-policy.json"` を渡す。未検出・不正policyはexit2で停止し、repo配置を仮定しない。`--bypass-cooldown` も現物SHAに一致する承認済みincident以外には使わない。

- apply/rollback/通知は明示承認なしに実行しない。
- exit非0やreceipt欠落を成功へ畳まない。

## ゴールシーク実行

目的に合う実在scriptを選び、入力・write scope・rollbackを確認する。read-only checkがあれば先に実行し、許可された操作だけを続行する。

停止条件: receipt の4つが揃ったら完了とする。exit 非0、receipt の欠落、承認の無い書き込み（apply・rollback・通知）のどれかに当たったら、その場で止めて報告する。

## 検証

実行command、exit code、changed paths、残リスクを報告する。

## Gotchas

- consumerのcwdはpolicyの置き場ではない。解決済みconfig-plugin-rootの実在policyを `--policy` で渡し、未検出や不正JSONを成功にしない。
- 同じファイルの過去変更はカテゴリーを変えてもcooldown対象になる。現在の承認は一致するSHAまたは明示したproposalに限定し、古い承認を新内容に流用しない。

---
name: run-skill-live-trial
description: 対象skillを本物のclaudeセッション(tmux)でfresh contextのまま実走させて受け入れ確認したいとき、fork実行では観測できない自走・入れ子Skill・対話gateの本番挙動をgoal適合まで検証したいときに起動する。
disable-model-invocation: false
user-invocable: true
argument-hint: "<plugin:skill> [args] [--proof] [--model <model-id>]"
arguments: [target_skill, trial_args, proof_mode, model]
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python3 *)
  - Bash(git status *)
  - Bash(git diff *)
  - Agent
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-07-02
version: 0.1.0
schema_refs:
  - schemas/live-trial-verdict.schema.json
reference_refs:
  - references/task-template.md
  - references/transcript-jsonl.md
  - ../run-elegant-review/references/convergence-policy.json
  - ../run-build-skill/references/goal-seek-paradigm.md
  - ../../references/orchestrate-gate-pattern.md
script_refs:
  - scripts/plan-live-trials.py
  - scripts/live-trial-backend.py
  - scripts/live-trial-boot.py
  - scripts/live-trial-send.py
  - scripts/live-trial-status.py
  - scripts/live-trial-poll.py
  - scripts/live-trial-verdict.py
source: eval-log/harness-creator/_plugin/elegant-review/20260702T160010-anti-goodhart/design-decisions.md
source-tier: internal
last-audited: 2026-07-02
audit-trigger: quarterly
completeness_exempt:
  - "prompts: 責務単位プロンプトを持たない実走 acceptance harness。手順は固定 Phase でなくゴールシークループで都度生成するため R-id 単位 7 層プロンプトは適用外。trial セッションへ渡す文面は references/task-template.md が正本。"
  - "manifest: ゴールシークループで手順を都度生成するため phase/gate 固定の workflow-manifest は適用外。発火条件は workflow-manifest の live-acceptance phase (plugin 側) が持つ。"
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: live-trial-status の4状態分類と live-trial-poll の終端4分岐および state-file 永続化が合成 transcript fixture の pytest で機械検証される
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: 生成した verdict.json が同梱 schemas/live-trial-verdict.schema.json の required と additionalProperties false を自己検証で通過してから書き出される
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: goal 判定は orchestrator と別個体の fresh evaluator が PASS または FAIL と blocker 列挙のみを返し点数を出力しない
      verify_by: evaluator
    - id: OUT2
      loop_scope: outer
      text: proof trial の実走 model 証明は transcript から抽出した actual_model の機械 gate のみを根拠とし boot READY 行の echo を証拠にしない
      verify_by: live-trial
    - id: OUT3
      loop_scope: outer
      text: 全終了経路で tmux セッションが reaper により回収され denylist 被験 skill の起動が boot と verdict の機械 gate で拒否される
      verify_by: script
---

# run-skill-live-trial

対象 skill を**別プロセスの本物の claude セッション** (tmux backend) で fresh context のまま実走させ、**期待どおり動くか (受け入れ) を確認する** acceptance harness。実走証拠 (verdict + transcript) は behavioral claim (自走完遂 / 入れ子 Skill / 対話 gate 越え / goal 達成) の唯一の収束根拠であり、静的レビューの design claim とは直交する (`../../references/orchestrate-gate-pattern.md` **Gate D**)。

## 適用境界 (fork acceptance との直交)

| 観測対象 | fork acceptance | live-trial (本 skill) |
|---|---|---|
| Stop hook 自走 | ✗ | ✓ |
| 入れ子 Skill (fork 内 Agent 不可) | ✗ | ✓ |
| 対話 gate 越え | ✗ (止まる=合格扱い) | ✓ |
| 本番の plugin/hook ロード | △ | ✓ 同一 |

どの段まで要るかは被験 skill の **behavioral trait** から決定論導出する — 正本は `../run-build-skill/scripts/validate-build-plan.py` の `derive_acceptance_tier()` (hooks 配線 / allowed-tools の Skill・Agent・AskUserQuestion → `live`、その他 loop 実行系 → `fork`、非実行系 → `static`)。導出値が `live` の skill だけが本 skill の対象で、軽量 skill は fork acceptance (速い) で足りる。

## スコープと配備境界

- **acceptance 専用**: 「対象 skill が fresh context で期待どおり動くか」だけを扱う。**selection (複数 skill / 設定の比較) は扱わない** — acceptance に品質比較を混ぜると目的がぼやける。1 回の実走 = 1 skill の受け入れ。
- **常設 = 常時発火可能 + 条件必須** (D9): 本 skill はいつでも起動できるが、無条件の全 kind 実行はしない。発火は「behavioral trait 該当 × 挙動面 SHA 差分 × 予算内」の三積、非該当は queue へ deferred 記録。**proof trial のみ無条件**。
- **既定は incremental plan**: 複数 skill を検証するときは、実セッションを起動する前に `scripts/plan-live-trials.py` を必ず実行する。schema-valid PASS verdict・挙動閉包 SHA・stable `scenario_id`・transcript SHA が一致する証跡は再利用し、既定では新規 live trial を最大2本・同時2本までに制限する。scenario 契約を変更したら `scenario_id` も更新して旧証跡を無効化する。全件再実走は利用者が `--profile exhaustive` を明示した場合だけ許可する。
- **ローカル開発環境限定** (D14): 本 skill は harness-creator の開発環境でのみ動かす。**量産先 plugin への配備対象外** (composition invariant)。
- **被験 skill denylist (再帰遮断)**: `run-skill-live-trial` / `run-skill-iter-improve` 自身は被験体にできない (trial 内で trial/改善ループが入れ子起動して発散するため)。正本は `scripts/live-trial-backend.py` の `DENY_TARGET_SKILLS` で、boot / verdict が機械拒否する。

## 絶対ルール (proxy 化の防止)

1. **goal を proxy にしない**: 「起動した / 完走した」で合格にしない。fresh evaluator が「skill の目的 (description が約束する成果) を成果物が満たすか」を判定する。
2. **送信は必ずファイル経由 + session 固有 named buffer** (`live-trial-send.py` → `live-trial-backend.py paste-file`): タスク本文を send-keys で生送信しない。改行/括弧で TUI のペースト検知が誤動作する。tmux default buffer は server 全体で共有され、並列 trial の `load-buffer` → `paste-buffer` 間で別 route の本文へ上書きされるため使用禁止。backend が session + file path から injection-safe・固定長・決定論的な buffer 名を生成し、`load-buffer -b <name>` → `paste-buffer -b <name>` → `finally: delete-buffer -b <name>` を一送信単位で保証する。例外は gate 応答 (短い固定キー) のみで、それも `live-trial-backend.py send-keys` を通す。
3. **boot は direct process + declared plugin pinning**: 検証済み `claude` argv を `tmux new-session` の pane shell-command として直接起動する。ユーザーの対話 zsh 起動完了や startup file に依存しない。`--setting-sources local` を固定し、auth/sessionは維持しつつ無関係なuser/project settings driftをacceptance環境から除外する。`--target-skill plugin:skill` は caller cwd 内の target と `references/package-contract.json#depends_on` の direct dependency だけを候補にし、任意の `skill_dependencies.<skill>` があればその部分集合だけを `--plugin-dir` へ固定する (map省略は後方互換で全depends_on、map内の未列挙skillは依存0)。キーは `entry_points.skills`、値は `depends_on` の部分集合でなければ boot/package check がfail-closed。これにより無関係な依存pluginをload/hashせず全件trial invalidationを防ぐ。未宣言plugin、missing/malformed manifest、symlink escape は起動前にfail-closed。installed/global版への偶然依存は禁止。plain skill nameは後方互換のためplugin pinningなし。
4. **完了 = 「成果物の出現 + busy 不在」の二層判定** (`live-trial-poll.py`): 目視やアドホック grep でアイドル判定しない。一次 = transcript JSONL (`live-trial-status.py` が 4 状態分類。スキーマは `references/transcript-jsonl.md`)、fallback = TUI capture。busy 不在だけだと未着手 / tool 境界 / 質問返し停止を完走と誤判定する。

## ゴールシーク実行

固定 Phase 連番は書かず、ゴール + チェックリストへ向け局面を都度選ぶ。正本: `../run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

被験 skill の 1 実走が起動 / 完走 (自走含む) / goal 適合の 3 軸で判定され、schema 適合の `verdict.json` + `transcript.jsonl` が `eval-log/<plugin>/<skill>/live-trial/<run-id>/` に保存され、tmux セッションが残っていない状態。

### 目的・背景 (Why)

fork subagent では自走 / 入れ子 Skill / 対話 gate / 本番 hook ロードが原理的に観測できない。実走証拠だけが behavioral claim を裏づけられるため、静的ゲート (Gate A-C) と直交する Gate D として実走 acceptance を行う。

### 完了チェックリスト (Checklist)

- [ ] 被験 skill が denylist 外で、workdir が `eval-log/<plugin>/<skill>/live-trial/<run-id>/` に作られた
- [ ] task.md が契約 5 項目 (下表) を満たし、`READY:` 確認後にファイル経由で送信された
- [ ] poll が終端 exit (DONE / STALL / GATE / HARD_CAP) で閉じ、`--state-file` で counter が呼び越し永続化された
- [ ] out/ + pane.txt + transcript.jsonl の 3 点が workdir に揃った (回収完了条件)
- [ ] fresh evaluator が PASS | FAIL + blocker 列挙のみを返した (点数出力なし。正本 = goal-seek-paradigm.md 達成判定節)
- [ ] `verdict.json` が schema 自己検証を通過して書き出された (proof trial は actual_model 機械 gate 込み)
- [ ] どの終了経路でも tmux セッションが kill され、reaper で残骸ゼロを確認した

### ゴールシークループ

正本 6 ステップに従い、未達のチェック項目を埋める局面を下のカタログから選ぶ。数値上限 (nudge 回数 / STALL 判定秒 / 絶対打切り秒) は `../run-elegant-review/references/convergence-policy.json` の `loop_bounds.trial_acceptance` (`nudge_max` / `stall_limit_s` / `hard_cap_s`) を正本とし、本文には生値を書かない (二重宣言禁止)。script 側は同値を env (`STALL_LIMIT` / `HARD_CAP`) で上書きできる既定として持つ。

## 局面カタログ

`SCRIPTS=plugins/harness-creator/skills/run-skill-live-trial/scripts` (repo root 起点。ローカル開発環境限定)。

### 事前計画: 再利用判定 + 実走予算

複数 skill / plugin 一式を対象にするとき、boot より先に次を実行する。

```bash
python3 "$SCRIPTS/plan-live-trials.py" \
  --plugin-dir plugins/<plugin> \
  --eval-root eval-log \
  --profile incremental \
  --max-live-trials 2 \
  --max-concurrency 2
```

`skills[].action` が `reuse` のものは実走しない。`run` だけを `live_batches` の順に実走し、`defer` は予算超過として queue / 最終報告へ残す。`exhaustive` は明示指定時だけ全 live candidate を再実走する。planner はLLMを起動せず、既存証跡と挙動閉包だけで決定する。

### 準備: 入力解析 + workdir + task.md

`$ARGUMENTS` から target skill / args / proof 指定を抽出。**proof trial の定義**: 依頼 / args に `proof` が明示されている場合のみ (= 「特定 model での完走」自体が受け入れ条件で、実走 model の証明が必要)。無指定は通常 trial で model 空 (ユーザー既定) 可。orchestrator が勝手に proof へ格上げ・格下げしない。

- workdir = `eval-log/<plugin>/<skill>/live-trial/<run-id>/` (絶対パスで扱う。`<run-id>` は `date +%Y%m%dT%H%M%S` 級の一意値)。`mkdir -p <workdir>/out`
- session 名 = `lt-<run-id>-<slug>` (一意。固定名は並行 trial が boot の kill-session で互いを殺す)
- `references/task-template.md` を `<workdir>/task.md` へ cp し `{{...}}` を Edit で置換 (作文より速く契約漏れを防ぐ)

**task.md 契約 (5 項目必須 — テンプレの構造がこれを満たす)**:

| # | 項目 | 形 |
|---|---|---|
| 1 | Skill リテラル呼び出し | `Skill({skill: "<plugin:skill>", args: "..."})` をそのまま書く (言い換え禁止) |
| 2 | 完了マーカー | `out/` に書かせるのは**完了マーカー 1 ファイルのみ** (推奨 `status.json`)。中間 Write は DONE 偽陽性源 |
| 3 | 終了報告 | 「DONE: <status>」と 1 行だけ報告 |
| 4 | 自走文言 | 「途中で人間に質問せず最後まで自走」を明記 |
| 5 | 裁量封じ | 「skill の手順に忠実に従い、人手の追加判断・省略をしない」を明記 |

### boot

```bash
python3 $SCRIPTS/live-trial-boot.py "$SESSION" "$(pwd)" --model "$MODEL" --target-skill "<plugin:skill>"
# → READY: lt-... (Ns) MODEL:<model|default> SESSION_ID:<uuid>
```

`READY:` を確認してから次へ。`SESSION_ID` (行末固定) は以後の send / poll / verdict に env / 引数で渡す — transcript JSONL 一次判定が有効になる。boot は対話shellを経由せず、model/session-idを検証したargvで`claude`をpaneに直接起動し、`--setting-sources local`でuser/project settingsを読まない。qualified targetではcwd配下のtarget pluginとpackage contractが宣言するdependencyだけを複数`--plugin-dir`でloadするため、plugin自身のskill/hookと正規delegateはacceptance対象に残る。初回の bypass-permissions 確認は `WARNING: Claude Code running in Bypass Permissions mode` + `1. No, exit` + `2. Yes, I accept` + `Enter to confirm` の4 markerが全て一致する場合だけ、`Down`→短いrender待ち→Enterでoption 2を1回受理する (実TUIで数字2は選択移動にならない)。他のgateは自動応答しない。その後の`for shortcuts`、または行頭`❯` + space/NBSP + `Try ...`/空promptを検出するまでREADYを返さない。番号付き`❯ 1.`はREADY対象外。`TIMEOUT:` は project trust / claude PATH を確認。`BOOT_FAIL:` はcapture tailにCLIエラー原文が残る。**proof trial では model 必須** — 空のまま boot したら即 kill して確定後に再 boot (既定 model の完走を proof と報告するのが最悪の故障モード)。**boot は安全な文字集合でない model/session-id を起動前に拒否するが、存在しない model id の有効性は検出しない** (READY 行の MODEL: は requested の echo)。tmux 不在は exit 3 BLOCKED — verdict を `--blocked` で記録して中断 (fail-closed)。

### send

```bash
SESSION_ID="$SESSION_ID" python3 $SCRIPTS/live-trial-send.py "$SESSION" "$WORKDIR/task.md"
```

### poll

```bash
SESSION_ID="$SESSION_ID" python3 $SCRIPTS/live-trial-poll.py --state-file "$WORKDIR/poll-state.json" "$WORKDIR/out/status.json" "$SESSION"
```

**ロングラン前提・成果物ベース**。glob は完了マーカー限定 (契約 #2)。Bash ツールの timeout 上限 (600s) で poll が切れたら**同一コマンド (同じ `--state-file`) をそのまま再呼び**する — state-file が counter を JSON で呼び越し永続化するので上限判定が実効する (`--max-ticks` の exit 5 も同じ「継続の合図」)。state-file なしの長時間 poll は STALL / 絶対打切りが構造的に観測不能 — 禁止。`WARN: HARD_CAP 80%` 行が出たら残り時間内に終端する見込みを評価し、正常進行なら env `HARD_CAP` を上げて続行 (到達後 kill は run 全損)。長い無音 tool 呼び (codex 委譲等) を含む被験 skill は env `STALL_LIMIT` を実測より長く前置する。

| exit | 意味 | 次の行動 |
|---|---|---|
| 0 DONE | 成果物出現 + busy 不在安定 | 回収へ |
| 4 GATE | 対話入力待ち (jsonl 判定時のみ) | `python3 $SCRIPTS/live-trial-backend.py send-line "$SESSION" '<応答>'` → 再 poll。**gate 応答回数を記録** |
| 2 STALL | 進捗停止 | 下の STALL 分岐表を上から順に |
| 1 HARD_CAP | 絶対打切り (安全弁) | 記録 → kill-session → verdict `--blocked` |
| 5 TICK_BUDGET | tick 予算消化 | 同一 state-file で再呼び (エラーではない) |

### STALL 分岐表 (上から順。各行 1 回判定で次へ — 裁量で順序を入れ替えない)

| # | 確認 | 所見 | 行動 |
|---|---|---|---|
| 1 | `backend has-session` | 失敗 | crash と記録 → 回収へ (jsonl は BUSY_GENERATING 凍結のままが正常) |
| 2 | poll 出力の `state:` | `BUSY_*` | 長い無音 tool — env `STALL_LIMIT` を 2 倍にして再 poll (1 回限り)。2 回目の同所見は hang 確定 → kill して中断 |
| 3 | 同上 | `IDLE_TURN_COMPLETE` + マーカーなし | plain-text 質問返し / 中途終了の可能性 (GATE は AskUserQuestion/ExitPlanMode の pending しか検知しない) → 4 へ |
| 4 | `backend capture-pane` の末尾 | 質問・確認待ち文 | nudge: 固定文「task.md の指示どおり質問せず自走で続行し、完了条件を満たしてください」を `nudge-<n>.md` に Write → send で送信 → 再 poll。上限は `loop_bounds.trial_acceptance.nudge_max`、**nudge_count を記録** |
| 5 | 同上 | 完了報告済みだがマーカー未 Write | task.md 契約違反 — 不合格として記録 → 回収へ |
| 6 | — | どの行にも該当しない (model / API / usage-limit エラー画面等) | capture tail + `state:` を記録 → kill-session → **不合格として中断** (default 終端 — 裁量で続行しない) |

### 回収 + model 機械 gate

成果物 (`out/`)、最終 capture (`backend capture-pane --scrollback > pane.txt`)、transcript を回収する。**回収完了条件 = out/ + pane.txt + transcript.jsonl の 3 点が workdir に揃うこと**。副作用は `git status` / `git diff` で記録。実走 model は transcript から決定論で取る — `live-trial-verdict.py` が `actual_model` (assistant.message.model の unique 集合) を抽出し、**proof trial では requested と不一致 (複数値・空含む) → ❌** の機械 gate を適用する。

### goal verification (fresh evaluator)

**Agent ツールで fresh evaluator** (orchestrator と別個体) を起動し、成果物 + `transcript.jsonl` (ツール呼び・入れ子 Skill・エラーが残る一次情報) を渡して **target skill の goal を満たすか**を独立判定させる。出力は **PASS | FAIL + blocker 列挙のみ。点数出力は禁止** — 正本は `goal-seek-paradigm.md` の達成判定 (GOAL VERIFICATION) 節。「起動/完走したか」ではなく「description が約束した成果が出ているか」を問う。

### verdict + 掃除

```bash
python3 $SCRIPTS/live-trial-verdict.py --workdir "$WORKDIR" --target-skill "<plugin:skill>" \
  --skill-dir "<被験skillディレクトリ>" --session-id "$SESSION_ID" --requested-model "$MODEL" \
  --launch PASS --completion PASS --goal-result PASS --nudge-count 0 --gate-response-count 0 \
  --poll-exit DONE [--proof] [--blocked]
python3 $SCRIPTS/live-trial-backend.py kill-session "$SESSION"
python3 $SCRIPTS/live-trial-backend.py reap   # 取りこぼした lt-* 残骸の一括回収
```

verdict は `schemas/live-trial-verdict.schema.json` を自己検証してから書き出される (`skill_dir_tree_sha` = 互換field名を維持した宣言済み挙動閉包 digest。SKILL.md、local scripts/prompts、`script_refs`/`reference_refs`/`responsibility_refs`/`schema_refs`、native manifest/hooks/package-contract、direct dependency manifest/hooksを含み、missing/escape/undeclared cross-plugin refはfail-closed / `transcript_sha256` / `scenario_origin` / `environment` / `tier` + `downgrade_reason` を含む)。**DONE / STALL / HARD_CAP / 中断のどの経路でも kill-session + reap を必ず実行** (残すと claude プロセスがリークする)。

## 判定ロジック

| 起動 | 完走 (自走含む) | goal 適合 | 総合 (`overall.verdict`) |
|---|---|---|---|
| ✅ | ✅ | PASS | `PASS` (✅) |
| ✅ | ✅ | FAIL | `DEGRADED` (⚠️ goal-proxy 乖離: 完走するが目的を果たさない) |
| ✅ | ❌ (hang / gate 抜け失敗) | — | `FAIL` (❌ + どこで止まったか) |
| ❌ | — | — | `FAIL` (❌ 起動 / install / 引数仕様) |

- **nudge_count > 0 または gate 応答 > 0 の完走は `DEGRADED` (自走未達) に降格** (自動送信でも介入)。
- **proof trial** は「人手介入なし PASS」が受け入れ条件 — DEGRADED 相当は `FAIL`、さらに actual_model ≠ requested_model で `FAIL` (機械 gate)。
- tmux 不在 / HARD_CAP 超過は `BLOCKED` (fail-closed)。
- この表の機械実装は `live-trial-verdict.py` の `derive_overall()`。

## 検証

```bash
# harness 自体の健全性 (tmux 不要のオフライン検査)
python3 $SCRIPTS/live-trial-backend.py --self-test    # session名検証 + denylist
python3 $SCRIPTS/live-trial-status.py --self-test     # 4状態分類 + interrupt 例外
python3 $SCRIPTS/live-trial-boot.py --self-test       # model 検証 + コマンド組立
python3 -m pytest -q tests/test_live_trial_harness.py # 合成 fixture の poll 4分岐ほか
```

## Gotchas

- **完了検知の急所**: busy 中の jsonl は完全無音 (長 Bash で 200s 級) — 経過時間で busy 判定しない。kill/crash したセッションは jsonl 上 BUSY_GENERATING のまま凍結 → tmux 生存確認が最終 fallback。TUI 層の busy 判定は ASCII マーカー (経過秒/token) のみ。詳細と版依存性は `references/transcript-jsonl.md` (spec-drift 監視対象)。
- **claude 起動は `--dangerously-skip-permissions`**。trust 済み project が前提 (未 trust だと boot がプロンプトで止まる)。
- **外部 CLI 依存 skill** (codex/cursor 委譲等) は usage limit で成果物が空振りしうる。
- **絶対 timeout は持たない** (ロングラン前提)。進捗停止 (`stall_limit_s`) と安全弁 (`hard_cap_s`) のみ。
- **tmux 依存**: 輸送層の唯一の境界は `live-trial-backend.py` (版依存モジュール境界)。plugin.json `requirements.external_clis` に登録済み。不在は BLOCKED。

## 関連

- fork acceptance / frontmatter 静的検証 — 前段 (tier 導出正本 = `derive_acceptance_tier()`)
- `run-skill-iter-improve` — goal-proxy 乖離 (`DEGRADED`) を検知したら改善ループへ (本 skill は被験体にしない: denylist)
- selection (どの skill が良いか) は本 skill の対象外

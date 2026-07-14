---
name: run-rubric-sync
description: トリアージで影響ありと判定された spec-drift issue の rubric/schema/template を同期したいとき、propose(read-only)で最小 Edit 差分と pre-image hash を提案し apply で監査 PASS と明示承認後に allowlist 対象だけを適用したいときに使う。
kind: run
prefix: run
hierarchy_level: L1
version: 0.1.0
user-invocable: true
disable-model-invocation: false
argument-hint: "[--issue NUMBER] [--mode propose|apply]"
arguments: [issue, mode]
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python3 *)
  - Bash(shasum *)
  - Bash(sha256sum *)
  - Bash(git *)
  - AskUserQuestion
  - Task
effect: local-artifact
owner: spec-drift-guardian maintainers
since: 2026-07-13
source: plugins/spec-drift-guardian/skills/run-rubric-sync/
source-tier: internal
last-audited: 2026-07-13
output_language: ja
prompt_layer: 7layer
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-plan.md
  - prompts/R3-apply.md
schema_refs:
  - ../../schemas/sync-proposal.schema.json
  - ../../schemas/sync-audit-verdict.schema.json
  - ../../schemas/triage-report.schema.json
  - ../../schemas/triage-verdict.schema.json
reference_refs:
  - references/apply-gate-policy.md
  - ../../references/field-impact-map/field-impact-map.json
script_refs:
  - ../../scripts/map-field-impact.py
  - ../../scripts/check-triage-complete.py
depends_on:
  - C01
  - C09
feedback_contract: # per-skill 受入基準(purpose-acceptance)。allowlist 限定適用と fail-closed を汎用ゲート言い換えに退化させない
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 全 impacted フィールドに target_path/axis/proposed_diff/pre_image_sha256 が揃い、C03 triage-verdict の agree・C04 sync-audit-verdict=PASS・approval.granted=true が全て揃うまで apply へ遷移できないことを script で機械検証できる。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 承認済み case は allowlist 対象パスだけが Edit 適用され post_image_sha256 と validator_results が一致し、未承認・監査 FAIL・pre-image hash drift・allowlist 外パスの各 case は変更 0 件で fail-closed になることを受入テストが確認する。
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: fresh context の実セッションで /rubric-sync を起動したとき、rubric-sync-auditor SubAgent が実際に発火して sync-audit-verdict を出し、AskUserQuestion の承認 gate が自走で素通りされず、監査 PASS と明示承認の双方が揃うまで apply が保留されることを live 実行で確認する。
      verify_by: live-trial
---

# run-rubric-sync

> **役割**: C01 トリアージで**影響あり**と判定された spec-drift issue に対し、harness-creator 側 rubric/schema/template への**同期を二段階**で行う独立起動 skill (C02)。**propose mode は read-only** で最小 Edit 差分・allowlist・expected pre-image hash を組み立て、**apply mode は apply-gate 条件 (G1-G5) を全充足したときだけ** allowlist 対象へ Edit を適用する。commit / PR / issue close は行わない。plugin root = `$CLAUDE_PLUGIN_ROOT`、artifact は `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/` 起点 (repo-root ハードコード禁止)。

## Purpose & Output Contract

Issue #17 step3 は「提案作成」ではなく rubric/schema/template の**実更新**を要求する。proposal-only で close 可能になる穴を塞ぐため、**独立監査 (C04) と明示承認を保った二段階実行**で実反映までを半自動化する。

- **入力**: `--issue N`、`--mode propose|apply`。C01 の `triage-report.json` (影響判定) と C03 の `triage-verdict.json` (独立再導出) を read-only 参照。apply では加えて C04 `sync-audit-verdict.json`。
- **出力**: `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-proposal.json` を `schemas/sync-proposal.schema.json` 準拠で emit。1 issue は複数の rubric/schema/template×軸へ影響しうるため、**`proposals[]` を正本とするコンテナ形**とする。`issue`/`proposal_sha256`/`status`/`approval` は **issue 単位のゲート**、`proposals[]` の各要素 (target_path/axis/before/after/proposed_diff/pre_image_sha256/post_image_sha256/validator_results) は **proposal 単位の適用証跡**。`proposals` は minItems 1。
  - propose: `status=proposed` / 各 `proposals[].post_image_sha256=null` / 各 `proposals[].validator_results=[]` / `approval.granted=false`。
  - apply: `status=applied_verified` / 全 `proposals[].post_image_sha256` 非 null / 全 `proposals[].validator_results` 1 件以上かつ全 passed。
- **完了条件**:
  - propose = 全 impacted target×axis が `proposals[]` の 1 要素として `target_path`/`axis`/`before`/`after`/`proposed_diff`/`pre_image_sha256` を揃え、各 target_path が allowlist glob 内で、schema 検証 exit 0。
  - apply = 下記 apply-gate 条件 (G1-G5) を全充足し、`proposals[]` の allowlist 対象だけを Edit 適用、各要素へ post-image hash と validator を記録して `applied_verified` へ更新 (部分適用禁止)。

## 二段階モデル (propose → apply)

| mode | 権限 | 入力 | 生成/更新 | fail-closed |
|---|---|---|---|---|
| **propose** | **read-only** (Edit しない) | triage-report / triage-verdict / 対象ファイル現状 | `sync-proposal.json` status=proposed。`proposals[]` に target×axis ごとの最小 Edit 差分・pre-image hash・allowlist target_path を格納 | complete≠true / triage-verdict 不一致 / allowlist 外 target は proposals に含めず記録 |
| **apply** | allowlist 対象**のみ** Edit | 上記 + sync-audit-verdict + ユーザー承認 | container を status=applied_verified へ更新 (各 `proposals[]` に post hash + validator) | 下記 G1-G5 のいずれか欠落で**変更 0 件**で停止 |

## Apply-gate: 適用は G1-G5 を全充足したときだけ (SSOT=references/apply-gate-policy.md)

apply mode は次の**5 条件 (G1-G5) を全て**満たすときに限り Edit を適用する。1 つでも欠けたら**変更 0 件で fail-closed** し、理由を提示する。判定は目視でなく `check-triage-complete.py --mode pre-apply` の exit code で行う:

1. **監査 PASS**: C04 `sync-audit-verdict.json` の `verdict=PASS` かつ `proposal_sha256` が sync-proposal と一致 (別提案の監査を弾く)。
2. **ユーザー明示承認**: `approval.granted=true` で `by`/`evidence` が埋まっている (発話等の証跡)。承認は AskUserQuestion で取得し、proposer≠approver を保つ。
3. **allowlist 内**: `target_path` が `plugins/harness-creator/**/rubric.json`・`plugins/harness-creator/**/templates/**`・`plugins/harness-creator/**/*.schema.json` のいずれかに一致。
4. **pre-image hash 一致**: 適用直前に実ファイルの sha256 を再計算し、proposal の `pre_image_sha256` と一致 (提案後の drift を検出)。`null` は新規作成提案=対象ファイル不在が一致条件。
5. **独立 verifier の同意 (対象束縛つき)**: C03 `triage-verdict.json` の `agree==true` かつ `diff_sha256` が C01 `triage-report.diff_sha256` と一致 (agree は特定 diff への同意なので、C01 再実行後に C03 未再実行の旧 verdict を流用させない)。

## 決定論チェック (deterministic_checks)

意味判断のみ LLM が担い、下記の判定・計算は Bash で決定論的に行う (Goodhart 化・自 plugin の drift 源化を防ぐ):

```bash
# 影響 target×axis を diff から独立再確認 (LLM の思い込みでなく写像表で裏取り)。写像規則は references から読む
python3 "$CLAUDE_PLUGIN_ROOT/scripts/map-field-impact.py" --hunks <hunks.json> \
  --map "$CLAUDE_PLUGIN_ROOT/references/field-impact-map/field-impact-map.json"

# pre/post-image hash (macOS: shasum、Linux: sha256sum。どちらも先頭 64hex を採る)
shasum -a 256 <target_file> | cut -d' ' -f1
```

allowlist glob 照合・pre/post hash 突合・schema 検証は `references/apply-gate-policy.md` の手順を唯一の正本とする。

## ゴールシークと受入基準 (combinators)

`with-goal-seek`(engine=inline / fork=subagent / max_loops 5) + `with-feedback-contract`。inner ループは提案の充足 (IN1) を script で、outer ループは適用/fail-closed の網羅 (OUT1) を test で、承認 gate と auditor の実発火 (OUT2) を live-trial で検証する。未達は最大 3 周 (inner) / 5 loops (goal-seek) で findings を反映し再実行する:

- **IN1 (inner・script)**: 全 impacted フィールドに `target_path`/`axis`/`proposed_diff`/`pre_image_sha256` が揃い、C03 `agree`・C04 `verdict=PASS`・`approval.granted=true` が全て揃うまで apply へ遷移できない。検証は `check-triage-complete.py --mode pre-apply` の exit code で機械判定する (目視確認で代替しない)。
- **OUT1 (outer・test)**: 承認済み case は allowlist 対象だけが適用され post hash/validator が一致し、未承認・監査 FAIL・hash drift・allowlist 外パスの各 case は変更 0 件で fail-closed になる。
- **OUT2 (outer・live-trial)**: fresh context の実セッションで `rubric-sync-auditor` SubAgent が実発火して sync-audit-verdict を出し、AskUserQuestion の承認 gate が自走で素通りされないことを確認する (対話 gate と SubAgent 起動は fork 実行では観測できないため live で見る)。

## 境界 (boundary)

- **通常解析/propose は read-only**。実ファイルを書き換えるのは apply mode のみ。
- apply は **C04 sync-audit-verdict=PASS ∧ ユーザー明示承認 ∧ allowlist 内 ∧ pre-image hash 一致 ∧ C03 agree (対象 diff 束縛つき)** を必須とし、`plugins/harness-creator/**` の rubric.json / templates / schema へ最小 Edit 差分を適用する。
- **対象外パス・hash drift・監査不一致・未承認は変更 0 件で fail-closed**。
- **commit / PR / issue close は本 skill の責務外**。close ゲートは C10 (check-triage-complete.py) と C07 hook が担う。
- 独立監査は C04 (rubric-sync-auditor)、独立再導出は C03 (spec-impact-verifier) の責務。本 skill はそれらの artifact を消費するだけで、監査主体を兼務しない。

## Gotchas

- **propose で Edit しない**: propose は read-only。実ファイルへの Edit は apply mode の G1-G5 充足後のみ。
- **allowlist は target_path で明示**: `proposals[].target_path` が allowlist の実体。glob 外を提案しない・適用しない。schema は additionalProperties:false のため allowlist 専用フィールドは持たず、proposals[] の target_path 集合が allowlist を表す。
- **proposal_sha256 の安定性**: digest は container の `issue` と全 `proposals[]` の不変核 (target_path/axis/before/after/proposed_diff/pre_image_sha256) 上で計算し (target_path 昇順連結)、apply 時に付く post/validator/approval で値が動かない。C04 の proposal_sha256 と一致必須。
- **hash drift は fail-closed**: 提案時と適用時でファイルが変わっていたら (pre-image 不一致) 適用しない。再 propose を促す。
- **status は 2 値のみ**: `proposed` / `applied_verified`。proposal-only (proposed のまま) では C10/C07 が close を拒否する。
- **配置非依存**: script は `$CLAUDE_PLUGIN_ROOT/scripts/`、artifact は `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/` 起点。repo-root 直書き禁止。
- **agent は消費のみ**: C03/C04 の verdict artifact を Read するだけで、本 skill から監査を自作しない (proposer≠approver)。

## 配置先

| 用途 | 出力先 |
|---|---|
| 本 skill 資産 | `plugins/spec-drift-guardian/skills/run-rubric-sync/` |
| sync-proposal | `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-proposal.json` |
| 消費 artifact (read-only) | 同ディレクトリの `triage-report.json`/`triage-verdict.json`/`sync-audit-verdict.json` |

## 追加リソース

- `prompts/R1-elicit.md` — R1: triage-report/triage-verdict と対象 rubric/schema/template の read-only 参照先を確定する 7 層 SSOT。
- `prompts/R2-plan.md` — R2: 4 軸+semantics の影響候補から最小 Edit 差分・allowlist・expected pre-image hash を組み立て status=proposed を emit する 7 層 SSOT。
- `prompts/R3-apply.md` — R3: apply-gate 条件 (G1-G5) を検証し allowlist 対象だけ Edit 適用、post-image hash と validator を記録し applied_verified へ更新する 7 層 SSOT。
- `references/apply-gate-policy.md` — allowlist glob・apply-gate 条件 (G1-G5)・pre/post hash 手順・proposal_sha256 正規化・fail-closed マトリクスの逐語正本。
- `../../schemas/sync-proposal.schema.json` — 出力契約。コンテナ (issue/proposal_sha256/status/approval) + `proposals[]` (target_path/axis/before/after/proposed_diff/pre_image_sha256/post_image_sha256/validator_results)。
- `../../schemas/sync-audit-verdict.schema.json` — C04 監査 verdict の消費契約 (verdict=PASS / proposal_sha256 一致)。
- `../../references/field-impact-map/field-impact-map.json` — C09 が読む diff→フィールド写像表 (本 skill は target×axis 裏取りに読むだけ)。
- `../../scripts/map-field-impact.py` (C09) — diff hunk→影響候補の決定論マッピング (target×axis の独立再確認)。
- `../../scripts/check-triage-complete.py` (C10) — `--mode pre-apply` で apply 直前に G1-G5 (監査 PASS・承認・allowlist・pre-image 一致・C03 同意 + `diff_sha256` 束縛) を機械検証する (exit 0 を得てから Edit。`--triage-report`/`--triage-verdict` も必須)。既定 `--mode close` は issue close ゲートで本 skill の責務外。
- `spec-impact-verifier` (C03・`../../agents/spec-impact-verifier.md`) / `rubric-sync-auditor` (C04・`../../agents/rubric-sync-auditor.md`) — 消費する verdict の生成元 agent。

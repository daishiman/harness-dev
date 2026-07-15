---
name: rubric-sync
description: C01/C03 の一致確認 → C02 propose → C04 audit → ユーザー明示承認 → C02 apply → C10 post-image 検証を順に実行する手動オーケストレーション。no-change でも独立 verdict を必須とする
kind: command
version: 0.1.0
owner: harness maintainers
since: 2026-07-13
argument-hint: "[--issue NUMBER]"
allowed-tools: Read, Bash, Skill, Task, AskUserQuestion
disable-model-invocation: false
entrypoint: run-rubric-sync
---

# /rubric-sync

`$ARGUMENTS` を `--issue NUMBER` としてパースし、指定 issue の rubric/schema/template 同期を **順序保証つき**で手動オーケストレーションする薄いラッパ。判定・提案・適用・監査のロジックは一切持たず、**C01 triage → C03 独立 verdict → C02 propose → C04 独立 audit → ユーザー明示承認 → C02 限定 apply → C10 close 前検証**の起動順序を強制するだけである。本 command の責務は「対象 issue の確定と各段の起動順序の強制」であり、影響有無・監査可否・承認は各段の独立主体に委ねる。パス解決はすべて `$CLAUDE_PLUGIN_ROOT` 起点。
Marketplace から install した場合の呼び出し名は通常 `/spec-drift-guardian:rubric-sync`。

**proposer≠approver をコマンド層でも二重化する**: 提案者と承認者を別 context に分離する原則を、順序強制によって二重に敷く。

- C01 (triage の提案者) の判定は、別 context の **C03 `spec-impact-verifier`** が生 diff から独立再導出して検証するまで確定しない。
- C02 (sync の提案者) の Edit 差分は、別 context の **C04 `rubric-sync-auditor`** が独立監査で PASS を出し、かつユーザーが明示承認するまで適用しない。

## 振る舞い

1. **入力パース**: `$ARGUMENTS` から `--issue NUMBER` を取り出す。
   - `NUMBER` は対象 GitHub issue 番号 (spec-drift 検知で起票済みのもの) を 1 件指定する。
   - `--issue` が無い / 番号が数値でない場合は argument-hint (`[--issue NUMBER]`) を表示し、**何も起動せず停止**する。issue 未指定時は「どの spec-drift issue を同期するか」を確認する案内を出す (例: `bd`/`gh issue list` などで対象 issue 番号を確認し `--issue <番号>` を付けて再実行する旨)。

2. **Step1 — トリアージ (C01)**: `Skill(run-spec-drift-triage, args="--issue <NUMBER>")` を起動する。
   - C01 は対象 issue の全未triage完全 diff を `complete=true`/digest 一致で再構成し、hunk 単位に構造化した上で artifact kind/path と name/type/required/enum/semantics 各軸の before/after/evidence を判定し、`triage-report` schema 準拠のレポートを `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-report.json` へ emit する。
   - 完全性を証明できない入力 (truncated preview 等) は C01 が fail-closed で拒否する。C01 が triage-report を確定する前に失敗したら、その理由をそのまま提示して**停止**する。

3. **Step2 — 独立 verdict (C03) と一致確認**: `Task(spec-impact-verifier, context:fork, args="--issue <NUMBER>")` で **C03 `spec-impact-verifier` サブエージェント (`agents/spec-impact-verifier.md`) を独立 context で起動**する。
   - C03 は C01 の triage-report を再読せず、C11 の complete diff へ C08/C09 を独立に再実行して影響を **再導出**し、`triage-verdict` schema 準拠の判定を `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-verdict.json` へ emit する (`issue`/`diff_sha256`/`rederived_impacts`/`agree`/`findings`/`verdict_sha256`)。
   - `triage-verdict.diff_sha256` が `triage-report.diff_sha256` と一致し、かつ **`agree=true`** であることを確認する。
   - **`agree=false` / verdict 不在 / `diff_sha256` 不一致**なら、C01/C03 の一致が取れていないため **propose へ進まず停止**する。C03 の `findings[]` (見逃し/誤検出/値不一致) を差し戻し理由として提示する。
   - **no-change (影響なし) でも本 Step は必須**である。triage-report が「影響あり artifact/軸なし」であっても、C03 の独立 verdict が無ければ close ゲート (`independently_verified_no_change`) に到達できない。影響なしを C01 の自己申告だけで確定しない (proposer≠approver)。
     - `agree=true` かつ再導出でも影響ありフィールドが 0 件 (no-change) の場合は、Step3〜Step5 (propose/audit/承認/apply) を **スキップ**し、Step6 の close 前検証 (C10) へ進む。close ゲートは `independently_verified_no_change` を目標とする。

4. **Step3 — propose (C02 propose mode)**: 影響ありフィールドがある場合、`Skill(run-rubric-sync, args="--issue <NUMBER> --mode propose")` を起動する。
   - C02 propose は **read-only**。影響ありフィールドへの最小 Edit 差分・対象パス (allowlist `plugins/harness-creator/**/rubric.json`・templates・schema 内)・4 軸・変更前後・`pre_image_sha256` を組み立て、`sync-proposal` schema 準拠 (`status=proposed`) の提案を `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-proposal.json` へ emit する。
   - この段では**一切ファイルを書き換えない** (`status=proposed`/`post_image_sha256=null`)。

5. **Step4 — 独立 audit (C04)**: `Task(rubric-sync-auditor, context:fork, args="--issue <NUMBER>")` で **C04 `rubric-sync-auditor` サブエージェント (`agents/rubric-sync-auditor.md`) を独立 context で起動**する。
   - C04 は sync-proposal を独立監査し、4 軸の反映漏れ (omissions)・過剰変更 (excesses)・allowlist 逸脱 (allowlist_violations)・pre-image hash 不一致を判定し、`sync-audit-verdict` schema 準拠の判定を `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-audit-verdict.json` へ emit する。
   - `sync-audit-verdict.proposal_sha256` が `sync-proposal.proposal_sha256` と一致し、かつ **`verdict=PASS`** であることを確認する。
   - **`verdict!=PASS` / verdict 不在 / `proposal_sha256` 不一致**なら **apply へ進まず停止**する。C04 の omissions/excesses/allowlist_violations を差し戻し理由として提示する。

6. **Step5 — ユーザー明示承認 (proposer≠approver の要)**: C04 が PASS を出した後、適用対象 (target_path・4 軸・proposed_diff) を提示し、`AskUserQuestion` でユーザーの**明示承認**を取る。
   - 承認は sync-proposal の `approval` (`granted`/`by`/`evidence`) に記録される前提とし、**`granted=true` の明示承認が無い限り apply しない**。承認が得られない / 保留の場合は apply へ進まず停止する (sync-proposal は `status=proposed` のまま = close 不可)。
   - C04 の audit PASS を承認の代替にしない。監査 (C04) と承認 (ユーザー) は別主体である。

7. **Step6 — 限定 apply (C02 apply mode)**: 明示承認取得後、`Skill(run-rubric-sync, args="--issue <NUMBER> --mode apply")` を起動する。
   - C02 apply は **C04 `verdict=PASS` とユーザー明示承認の両方が揃うときだけ**、sync-proposal の allowlist 対象パスへ Edit 差分を適用する。適用前に実ファイルと `pre_image_sha256` を照合し drift を fail-closed。
   - 適用後、`post_image_sha256` (実ファイルの実 hash) と validator 結果を記録し、sync-proposal を `status=applied_verified` へ更新する。
   - **allowlist 対象外パス・hash drift・監査/承認不備**は変更 0 件で fail-closed。

8. **Step7 — close 前検証 (C10)**: `python3 $CLAUDE_PLUGIN_ROOT/scripts/check-triage-complete.py --issue <NUMBER> --triage-report $CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-report.json --triage-verdict $CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-verdict.json --sync-proposal $CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-proposal.json --sync-audit-verdict $CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-audit-verdict.json --target-root $CLAUDE_PROJECT_DIR` を実行する。
   - C10 は 4 artifact・独立 verdict・明示承認・実ファイルの post-image を突合し、**`applied_verified`** (影響ありを承認済み限定適用+post-image 検証済み) または **`independently_verified_no_change`** (影響なしを独立 verdict で確認済み) のいずれかだけを **OK** とする。
   - **上記 2 状態以外はすべて `INCOMPLETE`** とする。proposal-only (`status=proposed` のまま)・未承認・未適用・hash/validator 不一致・独立 verdict 不在は close 不可。
   - C10 の出力 (OK|INCOMPLETE + status + 理由) をそのまま提示する。

## 順序保証

```
[Step1] C01 run-spec-drift-triage (Skill) → triage-report.json (complete diff / 4 軸+semantics)
[Step2] C03 spec-impact-verifier (独立 context) → triage-verdict.json
          agree=true か? ── NO → 停止 (C01/C03 不一致・findings 提示)
                           └ YES ┬ 影響ありフィールドあり → Step3 へ
                                  └ no-change (影響なし)    → Step3〜Step5 をスキップして Step7 へ
[Step3] C02 run-rubric-sync --mode propose (Skill, read-only) → sync-proposal.json (status=proposed)
[Step4] C04 rubric-sync-auditor (独立 context) → sync-audit-verdict.json
          verdict=PASS か? ── NO → 停止 (omissions/excesses/allowlist_violations 提示)
                            └ YES → Step5 へ
[Step5] ユーザー明示承認 (granted=true) か? ── NO → apply せず停止 (status=proposed のまま = close 不可)
                                            └ YES → Step6 へ
[Step6] C02 run-rubric-sync --mode apply (Skill) → allowlist 限定適用 + pre-image hash 照合
          → post_image_sha256 + validator_results 記録 → status=applied_verified
[Step7] C10 check-triage-complete.py → applied_verified または independently_verified_no_change のみ OK
          それ以外はすべて INCOMPLETE (proposal-only/未承認/未適用/不一致を拒否)
```

- 本 command は起動順序と proposer≠approver の二重化の責任だけを持ち、triage/検証/提案/監査/適用の実装は C01/C02/C03/C04/C10 が担う (薄いオーケストレータ)。
- **commit / PR / issue close は行わない**。close ゲートの判定 (C10 OK) は「close してよい状態か」を示すだけであり、実際の commit・PR・issue close は人間の責務である。

## 引数

| 引数 | 説明 |
|---|---|
| `--issue NUMBER` | 同期対象の spec-drift issue 番号 (必須)。C01/C02/C03/C04/C10 各段への共通キー |

## 失敗時

- `--issue` 未指定 / 番号が非数値: argument-hint を表示し、対象 issue 番号の確認方法を案内して停止する。
- Step1 C01 が triage-report 確定前に失敗 (完全性を証明できない truncated preview 等): C01 の fail-closed 理由をそのまま提示して停止する。
- Step2 C03 `agree=false` / verdict 不在 / `diff_sha256` 不一致: C01/C03 の一致が取れていないため propose へ進まず、C03 findings を提示して停止する。
- Step4 C04 `verdict!=PASS` / verdict 不在 / `proposal_sha256` 不一致: apply へ進まず、C04 の omissions/excesses/allowlist_violations を提示して停止する。
- Step5 明示承認が無い / 保留: apply せず停止する (sync-proposal は `status=proposed` = close 不可)。
- Step6 C02 apply で allowlist 対象外・hash drift・監査/承認不備を検出: 変更 0 件で fail-closed 停止する。
- Step7 C10 が `INCOMPLETE`: 理由 (proposal-only/未承認/未適用/不一致/独立 verdict 不在) を提示し、close 不可として停止する。

## 注意

- 本 command は起動順序の薄いオーケストレータ。影響判定は C01、独立 verdict は C03、提案・限定適用は C02、独立監査は C04、close 前検証は C10 が担い、command 単体では影響有無・監査可否・承認・close 可否を判定しない。
- **no-change (影響なし) でも C03 の独立 verdict は必須**。影響なしを C01 の自己申告だけで確定せず、独立再導出で確認できた場合にのみ close ゲートは `independently_verified_no_change` を許可する。
- **proposal-only では close 不可**。承認・限定適用・post-image 検証まで到達した `applied_verified`、または独立 verdict で確認済みの `independently_verified_no_change` だけが close 可能状態である。
- 通常解析・propose は read-only。ファイル書き換えは C02 apply mode だけが、C04 PASS・ユーザー明示承認・allowlist・pre-image hash 一致のすべてを満たすときに行う。
- **commit / PR / issue close は本 command では行わない** (人間の責務)。C07 hook はローカル `gh issue close` を C10 で遮断するが、実際の close 主体は人間である。
- 検知 (fetch/diff/issue 起票) は既存 workflow / ref-yaml-spec-fetcher の責務であり、本 command では再実装しない。

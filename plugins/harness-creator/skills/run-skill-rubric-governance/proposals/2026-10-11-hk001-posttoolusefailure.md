---
date: 2026-10-11
kind: rubric-update-proposal
status: applied
proposal_id: PROP-2026-10-11-HK001-POSTTOOLUSEFAILURE
rubric_id: skill-design
rubric_layer: L0 (ref-skill-design-rubric/references/rubric.json) と L2 (assign-skill-design-evaluator/references/rubric.json) の追従
current_version: 1.5.0
proposed_version: 1.6.0
bump: minor
sunset_days: 0
trigger: HK-001 の check 文字列だけが作業ツリーで書き換わり、版・L2 の同期・記録が無かった（check-rubric-sync が RUBRIC_DRIFT）
---

# rubric 更新提案: HK-001 の event の候補に PostToolUseFailure を足す

## なぜ変えるのか

harness-creator の `hooks/hooks.json` は `PostToolUseFailure` を配線している（`external-intelligence-observe` と `auto-record-lesson.py` が、失敗した tool 呼び出しを拾うため）。
`capability-manifest.schema.json` の kindHook の `event` の enum にも `PostToolUseFailure` がある。
ところが HK-001 の check は9値で、`PostToolUseFailure` を含んでいなかった。
このまま kind=hook として採点すると、実際に動いている配線が high で落ちる。これは採点の誤検出である。

この食い違いを直すために、HK-001 の check の文字列だけが本体の作業ツリーで書き換えられていた。
しかし版は 1.5.0 のまま、L2 の `rubric_hash` も古いままで、記録も無かった。
そのため `check-rubric-sync.py` が RUBRIC_DRIFT（upstream `01c5fc25…` と L2 の `9bd1769f…` が不一致）を出していた。
本提案は、その変更を正規の手順（版上げ・L2 の同期・影響評価・独立の承認・記録）に乗せ直す。

## 変更

| rule | 今の check | 変えた後の check |
|---|---|---|
| HK-001 | event が {PreToolUse, PostToolUse, UserPromptSubmit, Stop, SubagentStop, Notification, SessionStart, SessionEnd, PreCompact} のどれか | 左の9値に `PostToolUseFailure` を足した10値のどれか |

- 足すだけで、消す値は無い。severity（high）・applies_to_kinds（hook）・rationale は変えない。
- 3つの正本（実際の配線・schema の enum・HK-001）の一致は `plugins/harness-creator/tests/test_hook_event_vocabulary_parity.py` が検査する。件数でなく集合で比べ、「配線 ⊆ schema」「配線 ⊆ HK-001」「schema = HK-001」を求める。
- HK-001 は LLM の判定で、決定論の採点スクリプト（`render-findings-score.py`）には HK-001 の分岐が無い。採点コードの変更は要らない。

## 影響評価

- 緩和方向の superset 変更である。今まで合格した hook は、すべて合格のまま。
- repo 内の hook の event 宣言（`plugins/*/hooks/hooks.json` と、kind が hook の capability manifest）30件（hooks.json だけなら27件。承認レビューで数え直した。提出の時は28件と書いていた）を、旧新の集合で判定し直した。would_regress 0・would_improve 1（harness-creator の `PostToolUseFailure` 配線）。
- 新しい集合の外に残るのは1件。dev-graph の hooks.json が配線している `TaskCompleted` である。公式の event 名かどうかの確認が要るので、本提案には混ぜず、残課題として起票する。
- `diff-rubric-impact.py` は kind=skill の score ログを読む道具で、kind=hook の判定は score ログに残っていない。結果と、その数字の読み方は「適用した後の確認」に書く。

## semver 判定

**minor（1.5.0 → 1.6.0）、猶予期間 0 日**とする。

- 判定を緩める変更なので minor（major は厳格化、patch は文言だけ）。前例の PROP-2026-10-09-001（1.4.0）と PROP-2026-10-09-ELEGANT-PD002（1.5.0）に合わせた。
- 猶予期間を 0 日にする根拠は、`references/version-rules.md` の minor 節「猶予期間を 0 日にできる場合」の 3 条件である（minor の既定は7日）。
  1. 向きを緩和と宣言している（`change.type: modify`・`change.direction: relax`）。
  2. `diff-rubric-impact.py` の `would_flip` が 0 である（下の「適用した後の確認」）。
  3. 承認者が緩和の根拠を確かめた。独立の承認レビュー（2026-10-12）が満たすと判定し（`sunset_zero_condition3: satisfied`）、利用者がそれを見て承認した。これで 0 日が確定した。
- 0 日にした理由は、承認者が governance log の行に書く。緩和の superset を 0 日にした前例（PROP-2026-05-18-002、PROP-2026-10-09-001）とも合う。

## reviewers

| 役割 | 担当 | 状態 |
|---|---|---|
| proposer | Claude セッション 077ff83f（PR #85 の作成者） | 提出済み |
| approver | solo_operator（利用者 daishiman） | 2026-10-12 に承認（AskUserQuestion で「承認する」）。33章の policy の P1 は human_approval を求める |
| independent reviewer | 独立の承認レビュアー（提案者と別 context の Claude サブエージェント、read-only） | approve・blocking 0。判断の根拠で、承認の代わりではない。記録は `eval-log/governance/` の承認レビュー |
| authorization | 利用者の指示「CIに関しても、まだ失敗している部分に関しては完了させておいてください。これら全てを改善してくださいね。」 | 2026-10-11 |
| tooling | `check-rubric-sync.py` | exit 0（L2 の `rubric_hash` を `22667118…` に同期） |

## 適用したこと

1. L0 の `rubric_version` を 1.6.0 にした（HK-001 の check は上の表のとおり）。
2. L2 の `rubric_version` と `upstream_version_pin` を 1.6.0、`rubric_hash` を L0 のファイル sha256 にした。`_doc` に 1.6.0 の追従を書き足した。
3. 人向けの説明（`references/CHANGELOG.md` の 1.6.0、`rubric-rationale.md` の版と HK-001、`ref-skill-design-rubric/SKILL.md` の評価軸サマリ、設計書24章の版）を追従させた。`doc/harness-creator-完全解剖.md` は版（§5 の rubric_version）に加えて、§2 の hook の行と §5 の HK-001 の行を10種の event に直した。
4. `.claude/changelog/governance-log.jsonl`（P1_structural）と `log/governance-log.jsonl` に発効を記録する。2026-10-12 に、利用者の承認を、独立の承認レビューの判定（approve）を根拠に添えて、猶予期間 0 日の理由とともに両方へ1行ずつ追記した。

## 適用した後の確認

- 提案 JSON（`eval-log/governance/20261011-hk001-impact-proposal.json`）は `change.type: modify` に `change.direction: relax` を宣言し、緩和の根拠を `impact_assessment.relaxation_basis` に書いた。
- `diff-rubric-impact.py`（提出の時は 0.4.0。2026-10-12 に 0.5.1 で回し直し、結論は同じ）`--proposal eval-log/governance/20261011-hk001-impact-proposal.json --logs eval-log` の出力は次のとおり（rc 0）。

  ```json
  {"change_type": "modify", "direction": "relax", "direction_source": "declared", "exceeds_flip_rate_limit": false, "flip_rate": 0.0, "flip_rate_limit": 0.3, "impact_model": "relaxation_no_new_failures", "proposed_bump": "minor", "required_bump": "minor", "score_logs": 4, "skipped_invalid": 0, "skipped_no_score": 0, "total": 22, "unreadable_logs": 0, "would_flip": 0}
  ```

  0.4.0 は、厳格化の `required_bump` を常に major にし、30% の判定を `exceeds_flip_rate_limit` に分けた版である。この提案は緩和なので、0.3.0 の出力（`required_bump: minor`）と結論は変わらない。

- 道具は direction の宣言を信じるだけで、緩和であることを自分では確かめない。緩和である根拠は次の2つで、提案者と承認者が責任を持つ。
  - 22 件の score ログはすべて kind=skill の SKILL.md を採点したもので、HK-001 の `applies_to_kinds` は `[hook]` だけ。HK-001 はどのレコードにも適用されず、findings にも HK の指摘は 0 件。
  - 変更は合格とする値の集合を広げるだけの superset なので、hook を採点した場合でも合格から不合格に変わるものは無い（repo 内の hook 宣言 30 件の再判定で would_regress 0）。
- 変更前の道具（版の表記なし）は向きを区別せず、同じ提案に最悪値（`would_flip` 19・`required_bump: major`）を出していた。厳格化を想定した模型を緩和に当てた誤りで、道具の側を直した（`run-skill-rubric-governance` の Key Rule 2 と governance-board.md に緩和の定義を書いた）。
- 承認の記録: `eval-log/governance/20261011-hk001-rubric-1.6.0-approval-review.json`。提案者と別 context の独立した承認レビュアー（read-only）が作り、判定は approve・blocking 0（2026-10-12）。
- 利用者の承認と、この承認レビューの記録と、「適用したこと」4 の 2 つの governance log の行がそろったので、front matter の status を `applied` にした。
- 承認レビューの non_blocking のうち、reviewers の third_party（議決ルールの Reviewer 1名を独立の承認レビューで満たすとみなすか）は人の判断として残す。dev-graph の hooks.json の `TaskCompleted` が新しい集合の外に残ることも、残課題のまま。

## cooldown

L0 と L2 の rubric.json は P1 の対象で、直前の変更（PROP-2026-10-09-ELEGANT-PD002、2026-10-09T12:58:33Z）から3日の cooldown がかかる。
本提案は incident_fix にせず、cooldown も迂回しない。
したがって `guard-change-category.py` は 2026-10-12T12:58:33Z（日本時間 10-12 21:58）まで違反を出す。
期限を過ぎてから CI を再実行すれば通る。

## 戻し方

L0 の `rubric_version` を 1.5.0 に、HK-001 の check を9値に戻す。
L2 の `rubric_version`・`upstream_version_pin`・`rubric_hash` を 1.5.0・1.5.0・`9bd1769f…` に戻し、`_doc` の 1.6.0 の一文を外す。
このとき `test_hook_event_vocabulary_parity.py` は「配線 ⊆ HK-001」で落ちる。
先に harness-creator の hooks.json から `PostToolUseFailure` の配線を外し、schema の enum からも外す。
人向けの説明と2つの記録は revert する。

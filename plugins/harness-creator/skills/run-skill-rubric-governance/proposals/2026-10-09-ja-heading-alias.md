---
date: 2026-10-09
kind: rubric-update-proposal
status: applied
proposal_id: PROP-2026-10-09-001
rubric_id: skill-design
rubric_layer: L0 (ref-skill-design-rubric/references/rubric.json) と L2 (assign-skill-design-evaluator/references/rubric.json) の追従
current_version: 1.3.0
proposed_version: 1.4.0
bump: minor
sunset_days: 0
trigger: ubm-goal-setting の日本語化（SKILL.md の見出しを日本語の正規形へ移す）
---

# rubric 更新提案: BD-001・BD-002・PD-002 に日本語の正規形の見出しを別名として足す

## なぜ変えるのか

ubm-goal-setting の6スキルは、見出しを日本語の正規形へ移す。
移した後の SKILL.md は `## 目的と出力契約` と `## つまずきやすい点` を持つ。
今の BD-001・BD-002 は英語の見出しだけを探すので、日本語の SKILL.md は high で落ちる。
中身は同じなのに、書いた言語だけで不合格になる。これは採点の誤検出である。

## 変更

| rule | 今の check | 変えた後の check |
|---|---|---|
| BD-001 | `## Purpose & Output Contract` を含む | 左に加えて `## 目的と出力契約` も可 |
| BD-002 | `## Gotchas` を含む | 左に加えて `## つまずきやすい点` も可 |
| PD-002 | 先頭30行に `## Purpose` か `## Output Contract` | 左に加えて `## 目的と出力契約` も可 |

- 日本語の見出しは、行全体の一致（前後の空白は除く）だけを認める。`### 目的と出力契約` や `## 目的と出力契約（補足）` は通さない。
- 英語の判定は1文字も変えない（部分一致のまま）。
- PD-002 も同時に変える。PD-002 の rationale は「BD-001 が認める見出しの集合を PD-002 が含む（BD-001 ⊂ PD-002）」を前提にしている。BD-001 だけ広げると、この包含関係が崩れる。

採点の実装は `assign-skill-design-evaluator/scripts/render-findings-score.py` の `PURPOSE_HEADING_JA`・`GOTCHAS_HEADING_JA` と `_has_heading_line()` にある。

## 影響評価

- 緩和方向の superset 変更である。今まで合格したスキルは、すべて合格のまま。
- `diff-rubric-impact.py`: total 1・would_flip 0・flip_rate 0.0・required_bump minor。
- テスト: `test_harness_creator__render_findings_score.py` ほか3ファイルで 206 件合格、`-k rubric` で 296 件合格。

## semver 判定

**minor（1.3.0 → 1.4.0）、猶予期間 0 日**とする。

- 判定を緩める変更なので minor（major は厳格化、patch は文言だけ）。
- 落ちるスキルが増えないので、猶予期間は要らない。前例の PROP-2026-05-18-002（緩和の superset、sunset_days=0）に合わせた。

## reviewers

| 役割 | 担当 | 状態 |
|---|---|---|
| proposer | Claude（ubm-goal-setting 日本語化セッション） | 提出済み |
| approver | solo-operator（利用者） | 承認済み。BD-001・BD-002 と PD-002 を AskUserQuestion でそれぞれ承認 |
| tooling | `check-rubric-sync.py` | exit 0（L2 の `rubric_hash` を `3f1b76f3…` に同期） |

## 適用したこと

1. L0 の `rubric_version` を 1.4.0 にし、3つの check と BD-001・PD-002 の rationale を改めた。
2. L2 の `rubric_version` を 1.4.0、`upstream_version_pin` を 1.4.0、`rubric_hash` を再計算した値にした。
3. 人向けの説明（`rubric-rationale.md` の BD-001・BD-002、`ref-skill-design-rubric/SKILL.md` の評価軸の要約）を追従させた。
4. `.claude/changelog/governance-log.jsonl`（P1_structural）と `log/governance-log.jsonl` に発効を記録した。

## 戻し方

L0 の `rubric_version` を 1.3.0 に、3つの check と rationale を英語だけの文言に戻す。
L2 の `rubric_version`・`upstream_version_pin`・`rubric_hash` を 1.3.1・1.3.0・`6e1843e5…` に戻す。
`render-findings-score.py` の `*_HEADING_JA` の分岐を外し、2つの記録を revert する。
日本語の見出しへ移ったスキルがあれば、先に英語へ戻す。

# Governance Board

rubric改正の4ロール（27章）。

| ロール | 責務 | 兼任不可 |
|---|---|---|
| **Proposer** | 改正提案者。proposal.json を書く | Approver と兼任不可 |
| **Third-party Reviewer** | 中立レビュー。動機・代替案を確認 | Proposer 兼任不可 |
| **Approver** | 最終承認。 governance log にエントリ記入 | Proposer 兼任不可 |
| **Tooling** | scripts/ 更新・assign側rubric.json 同期 | 誰でも可 |

## 議決ルール

- 全会一致が原則
- major bump は Approver 2名以上
- minor/patch は Approver 1名 + Reviewer 1名

## 緊急パッチ例外

high severity の **誤検出固定** のみ patch で即時可。
ただし governance log に `emergency: true` を必ず付け、48時間以内に Reviewer の事後確認。

## ログ形式 (`log/*.jsonl`)

```json
{"proposal_id":"PROP-2026-05-17-001","bump":"minor","applied_at":"2026-05-17T10:00:00Z","approvers":["alice"],"reviewers":["bob"],"flip_rate":0.04}
```

## solo_operator_mode（A1/C1, CD-009 パッチ）

1人運用環境では Proposer と Approver の兼任が構造上不可避になる。`governance-params.json` の `"solo_operator_mode": true` を設定し、下記3条件をすべて満たす場合に限り自己承認を許可する。

正本の `governance-params.json` は repo root の `references/governance-params.json`（27章§11）で、まだ無い。使うときは同じディレクトリの `references/governance-params.json.example` を写して作る。ほかの 2 つ（`plugins/skill-governance-config/config/governance-params.json.example` と、`freeze` を持たない prompt-creator の実ファイル）との違いは SKILL.md「巻き戻し」の末尾に書いた。

| 条件 | 確認方法 |
|---|---|
| 1. 安定版凍結済み | freeze 条件（`governance-params.json` の `freeze`）を満たすことを人が確かめ、evidence に書く（`lint-rubric-violation.py` に freeze を判定する機能は無い）。rubric-versions.md は版ごとに `violation_rate_avg` を1つ持つだけで、governance log も run ごとの違反率を持たないので、`freeze.consecutive_runs`（連続 run 数）は今の記録からは数えられない。数えるときは、score ログ（`eval-log/*/*-score.jsonl`）をその版の行（SKILL.md「巻き戻し」のとおり `rubric.rubric_hash` で絞る）にして時刻順に並べ、直近の `consecutive_runs` 件について、rule ごとの違反率（その rule が findings に出たレコード数 ÷ 件数）の最大と、各レコードの違反率（分母は `coverage.applicable_rules`）の平均を evidence に書く。満たすのは最大が `violation_rate_ceiling` 以下のとき（平均だけでは比べない。毎回違反する rule が 1 つあっても平均は 1/24 ≈ 0.042 で 0.05 を下回るため） |
| 2. newly_failing=0 | `diff-rubric-impact.py` 出力の `newly_failing_count == 0` |
| 3. LLM-reviewer pass | `run-skill-rubric-governance` Step2 影響評価で problem=none |

solo_operator_mode 有効中の制約:
- major bump 禁止 (minor/patch のみ)
- governance log に `solo_operator: true` と3条件 evidence を必ず記録
- 兼任なしの reviewer が確保できた時点で `solo_operator_mode: false` に戻すことを推奨

**運用注記 (固定 TODO(human) ではなく機械検出可能な復帰条件)**: 組織メンバーが追加されたら `solo_operator_mode` を `false` に戻し通常の4ロールへ復帰する (自己承認許可を撤回)。復帰要否は `governance-params.json` のメンバー数変化を契機に判定できるため、人間の記憶に依存させず lint/通知で発火させる。

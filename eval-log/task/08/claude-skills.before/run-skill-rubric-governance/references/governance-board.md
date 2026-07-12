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

| 条件 | 確認方法 |
|---|---|
| 1. 安定版凍結済み | `lint-rubric-violation.py` が freeze 条件を報告 |
| 2. newly_failing=0 | `diff-rubric-impact.py` 出力の `newly_failing_count == 0` |
| 3. LLM-reviewer pass | `run-skill-rubric-governance` Step2 影響評価で problem=none |

solo_operator_mode 有効中の制約:
- major bump 禁止 (minor/patch のみ)
- governance log に `solo_operator: true` と3条件 evidence を必ず記録
- 兼任なしの reviewer が確保できた時点で `solo_operator_mode: false` に戻すことを推奨

TODO(human): 組織メンバー追加時は solo_operator_mode を無効化し、通常の4ロールに戻すこと。

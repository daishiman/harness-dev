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

## 緩和と厳格化（影響評価の向き）

**緩和**とは、合格とする値の集合を広げるだけで、今まで合格したものがすべて合格のままである変更をいう。そうでない変更は厳格化として扱う（`references/version-rules.md` の minor と major）。

- 提案は向きを宣言する。`change.type` が `add` なら厳格化、`remove` なら緩和。`modify` は `change.direction` に `relax` か `tighten` を書く。
- `diff-rubric-impact.py` は宣言を信じて見積もる。緩和なら合格から不合格に変わるレコードは定義上 0 件なので `would_flip` は 0（`impact_model: relaxation_no_new_failures`）。厳格化なら改正した rule が全レコードで新たに発火する最悪の場合で数える（`worst_case_tightening`）。`modify` に `direction` が無いと厳格化とみなし、`direction_source: assumed` と出す。
- 道具は、変更が緩和の定義を満たすかを確かめない。その判断の責任は Proposer と Approver にある。Proposer は緩和と宣言した根拠（rule の削除で点が上がるだけ、check が今の判定の superset になる、など）を提案に書く。Approver はその根拠を確かめてから承認し、満たさなければ `tighten` に直させて流し直させる。
- 緩和の minor で `would_flip` が 0 であり、Approver が根拠を確かめたものは、猶予期間を 0 日にできる。Approver はその理由を governance log に書く（`references/version-rules.md` の minor）。
- `required_bump` は、厳格化なら合否変動率に関わらず major。緩和なら提案の bump と minor の大きい方（閾値や severity を変えるなら最低 minor）。提案の bump が届かないときは stderr に警告が出る。下回ってよいのは文言だけの patch と緊急パッチ（`emergency: true`）だけで、Approver が rubric.json の差分で確かめる。bump が無いか major・minor・patch 以外なら exit 2 で止まる。合否変動率が 30% を超えたか（`exceeds_flip_rate_limit`）は bump を決めず、猶予期間と board 招集の根拠にする。

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
| 2. would_flip=0 | `diff-rubric-impact.py --logs eval-log` 出力の `would_flip == 0`（合格から不合格に変わるレコードが無い）。score を持つレコードが 0 件なら script は exit 2 で止まり、この条件は満たしたことにならない。緩和の宣言（`remove`、`modify` と `relax`）では定義上 0 になるので、宣言が緩和の定義を満たす根拠を evidence に書く（上の「緩和と厳格化」）。兼任で Approver が根拠を独立に確かめられないので、条件 3 の LLM-reviewer に根拠も確かめさせる |
| 3. LLM-reviewer pass | `run-skill-rubric-governance` Step2 影響評価で problem=none |

solo_operator_mode 有効中の制約:
- major bump 禁止 (minor/patch のみ)。厳格化は major なので、solo では緩和（minor）と文言だけの patch しか通らない
- governance log に `solo_operator: true` と3条件 evidence を必ず記録
- 兼任なしの reviewer が確保できた時点で `solo_operator_mode: false` に戻すことを推奨

**運用注記 (固定 TODO(human) ではなく機械検出可能な復帰条件)**: 組織メンバーが追加されたら `solo_operator_mode` を `false` に戻し通常の4ロールへ復帰する (自己承認許可を撤回)。復帰要否は `governance-params.json` のメンバー数変化を契機に判定できるため、人間の記憶に依存させず lint/通知で発火させる。

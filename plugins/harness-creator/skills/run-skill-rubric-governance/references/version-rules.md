# Rubric Semver

`rubric_version: MAJOR.MINOR.PATCH`

## major（厳格化）

- 新規ルール追加
- severity 引き上げ（low→medium, medium→high）
- threshold 引き上げ
- check 式の対象拡大

**猶予期間**: 14日以上。Approver 2名以上。

## minor（緩和）

- 既存ルール削除
- severity 引き下げ
- threshold 引き下げ
- check 式の対象縮小

判定を変える緩和は最低 minor。`diff-rubric-impact.py` の `required_bump` も、緩和なら提案の bump と minor の大きい方にする（patch の緩和は minor に上げる）。

**猶予期間**: 7日。Approver 1名 + Reviewer 1名。

**猶予期間を 0 日にできる場合**: 次の 3 つをすべて満たす緩和の minor は、猶予期間を 0 日にできる。どれかを満たさなければ 7 日を守る。

1. 向きを緩和と宣言している（`change.type: remove`、または `modify` で `change.direction: relax`）。
2. `diff-rubric-impact.py` の `would_flip` が 0 である（score を持つレコードが無く exit 2 で止まったときは満たさない）。
3. 承認者が緩和の根拠を確かめた（今まで合格したものがすべて合格のままである理由。`governance-board.md`「緩和と厳格化」）。

0 日にしたときは、その理由（`would_flip` が 0 であることと、承認者が確かめた緩和の根拠）を governance log の行に書く。猶予期間は、改正で落ちる Skill の作者に直す時間を残すためのもので、落ちる Skill が無ければ置かない（23章「改正の段階」3 の、影響を受ける Skill が 0 なら猶予期間を置かないのと同じ）。

## patch（文言のみ）

- rationale の言い回し
- typo修正
- コメント追加

判定を変えないので、緩和にも厳格化にも数えない。`diff-rubric-impact.py` は文言だけかを見分けないので、patch の提案を流すと `required_bump` が minor 以上になり、届かない警告が出る。文言だけであることは承認者が rubric.json の差分で確かめ、確かめたら patch で通す。

**猶予期間**: 0（即時）。

## 例外: 緊急パッチ

高 severity ルールの **明らかな誤検出** を patch で即時固定可。
誤検出の固定は判定を変える緩和なので `required_bump` は minor になるが、この例外に限って下回る patch で出してよい。
governance log に `emergency: true`、48時間内に事後レビュー。

## 提案 md の status

提案 md（手書きは `$SKILL_DIR/proposals/*.md`、`aggregate-evals.py` の自動ドラフトは plugin の外の `$CLAUDE_PROJECT_DIR/.claude/state/harness-creator/proposals/*.md`。両方を `aggregate-evals.py --list-proposals` で一覧できる。`CLAUDE_PROJECT_DIR` が無いときは、cwd と git の作業ツリーの root を project とみなして読む）の front matter の `status` は、次のどれかにする。

| status | 意味 |
|---|---|
| `draft` | `aggregate-evals.py` が自動で生成した段階で、まだ審査していない。自動ドラフトは異常の観測差分（`kind: rubric-anomaly-delta`）で改正案ではないので、改正するときは `templates/proposal.json` で別に起票する |
| `pending` | rubric に反映したが、承認の記録（承認レビューと、`.claude/changelog/governance-log.jsonl` とこのスキルの `log/governance-log.jsonl` の行）がまだそろっていない |
| `applied` | 承認の記録がそろった |
| `rejected` | 承認されなかった。rubric に反映していたら、提案の「戻し方」で元に戻す |

## 同期義務

`ref-skill-design-rubric/references/rubric.json` 更新時:
1. `assign-skill-design-evaluator/references/rubric.json` も同期
2. 両ファイルの `rubric_version` を一致させる（deep-merge upstream-source-of-truth）
3. `rubric_hash` は自然に変わるので採点側で再計算される

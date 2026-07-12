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

**猶予期間**: 7日。Approver 1名 + Reviewer 1名。

## patch（文言のみ）

- rationale の言い回し
- typo修正
- コメント追加

**猶予期間**: 0（即時）。

## 例外: 緊急パッチ

高 severity ルールの **明らかな誤検出** を patch で即時固定可。
governance log に `emergency: true`、48時間内に事後レビュー。

## 同期義務

`ref-skill-design-rubric/rubric.json` 更新時:
1. `assign-skill-design-evaluator/references/rubric.json` も同期
2. 両ファイルの `rubric_version` を一致させる（deep-merge upstream-source-of-truth）
3. `rubric_hash` は自然に変わるので採点側で再計算される

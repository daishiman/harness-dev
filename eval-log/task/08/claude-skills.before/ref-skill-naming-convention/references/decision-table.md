# 命名 主要8ケース 裁定表

| # | ユースケース | prefix | role-suffix | 例 |
|---|---|---|---|---|
| 1 | 新規ワークフロー実装 | run- | -builder/-runner | `run-build-skill` |
| 2 | 評価専用Skill | assign- | -evaluator | `assign-skill-design-evaluator` |
| 3 | 生成専用Skill | assign- | -generator | `assign-rubric-generator` |
| 4 | 命名/仕様の辞書 | ref- | -convention/-spec | `ref-skill-naming-convention` |
| 5 | rubric等の正本 | ref- | -rubric | `ref-skill-design-rubric` |
| 6 | gh等CLIラッパ | wrap- | (none) | `wrap-gh` |
| 7 | subagent委譲 | delegate- | (subagent name) | `delegate-general-purpose` |
| 8 | rubric改正Runbook | run- | -governance/-runbook | `run-skill-rubric-governance` |

## 判定ロジック

1. **書き込みするか？** No → ref-
2. **採点 or 生成専用 fork か？** Yes → assign-
3. **外部CLI ラップか？** Yes → wrap-
4. **subagent 委譲 thin wrapper か？** Yes → delegate-
5. **それ以外で何かを実行する？** Yes → run-

## 迷ったら

- 「ユーザーが直接呼ぶか？」が Yes → run- / wrap-
- 「内部から呼ばれるだけ」 → assign- / delegate-
- 「参照されるだけ」 → ref-

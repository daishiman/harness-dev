# C19 の goal-seek 契約適用範囲（source-only 独立確認）

対象 source root: `/Users/dm/orca/workspaces/harness/pr86-ci-fix`

本確認では今回の実走 raw、過去 trial の transcript・verdict・独立レビューを読んでいない。特定の実値や期待判定は入力されていない。source・fixture は編集していない。

## 結論

C19 の実走判定へ、harness-creator（HC）の全文 `goal-seek-loop.schema.json`・`drift_signal` の６値 enum が自動継承される参照経路は確認できなかった。C19 が本文・common・共有機械 gate に明示するローカル契約を必須として評価する。

## 一次 source 上の根拠

1. `plugins/dev-graph/skills/run-dev-graph-system-spec/SKILL.md:48` は停止条件と配線の正本を自身の `## ゴールシーク実行` と宣言する。frontmatter の `reference_refs` は `../../references/prompt-common-layers.md` であり、`schema_refs` は `../../schemas/graph-node.schema.json` である。本文144行目以降は、６必須キー（`original_goal`、`original_goal_hash`、`current_goal_snapshot`、`delta_from_original`、`merged_directive_for_next`、`drift_signal`）・hash一致・append-only・次周回の直前指示消費・各周回３ゲートを宣言する。common (`plugins/dev-graph/references/prompt-common-layers.md`) も HC schema・enum を参照しない。

2. `plugins/harness-creator/skills/run-skill-live-trial/scripts/validate-goal-seek-evidence.py:31` は、被験 SKILL の「ゴールシーク検証」節と同じ検査を外部強制する位置付けを明記する。実装が検査するのは３成果物の実在、非空 intermediate、６キー、goal-spec の非空 original_goal、各行の original_goal/hash 一致であり、enum・全文 schema 検証は実装されていない。

3. HC の `plugins/harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md:84` は生成スキルの周回状態を全文 schema 準拠とし、同105行目および `schemas/goal-seek-loop.schema.json:122` は drift_signal の６値 enum (`initial/aligned/compressing/stagnant/widening/oscillating`) を定義する。これは生成規約上の契約である。

4. `templates/combinators/with-goal-seek.patch` 冒頭と `scripts/render-combinators.py:984` 以降によれば、`with-goal-seek` は生成時の renderer が frontmatter・配線本文を注入する指定である。frontmatter の combinator 宣言だけで、実行時に HC 文書全体を読み込む機構ではない。C19 本文には HC 全文 schema 準拠・６値 enum の注入文がない。`behavior_closure_files()` による C19 宣言済み挙動閉包にも当該 HC 文書・schema は含まれない（閉包175ファイル、SHA-256 `ebec0c4771f30cd2be8260f9871ad0e4d42112e7f03ebed8c04a0326bf13a5ef`）。

5. 全文 HC schema をそのまま重ねると、C19 が明示する checklist の `achieved/not_achieved` と `evidence` に対し、HC schema は `pending/done/blocked` と checklist item の `additionalProperties:false` を課すため衝突する。両者を無条件に同一の実行契約として適用できない。

## 実走評価時の扱い

- C19 自身の明示契約・common・scenario・live-trial が定める必須 gate と、実際の意味的履行を必須とする。
- HC enum 外という理由だけで C19 の blocker にしない。
- 空・無意味な drift_signal、実際の goal drift、アンカー未消費、６キー/hash不一致、append-only違反、必須独立検証・各周回 gate 欠落等は C19 の局所契約に基づいて判定する。機械 gate の通過だけで意味的履行を代用しない。
- HC 生成規約との整合不足は、実走時の未宣言契約違反と分けて扱う。

本書は適用範囲の source-only 確認であり、sysspec115 の PASS/FAIL 判定ではない。

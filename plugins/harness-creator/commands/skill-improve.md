---
description: 既存 Skill/Capability を run-elegant-review で分析し、findings を提示して利用者が選んだものだけを elegant-improvement-executor で改善する入口。選ばれなかった finding には手を付けない。
argument-hint: "<capability-path>  例: plugins/harness-creator/skills/run-build-skill / agents/elegant-reset-observer.md"
allowed-tools: Read, Write, Edit, Bash, Skill, Task, AskUserQuestion
name: skill-improve
kind: command
version: 0.2.0
owner: team-platform
since: 2026-05-24
entrypoint: run-elegant-review
---

# /skill-improve

`$ARGUMENTS` の `<capability-path>` を対象に、分析 → findings 提示 → 利用者の選択 → 選んだものだけ改善 → 検証 の順で進める。改善範囲を決めるのは利用者で、command は自動で範囲を広げない。

## 振る舞い

1. target を読み、`run-elegant-review` を `--dry-run` で起動する (対象ファイルは編集せず、findings と C1〜C4 判定を eval-log に保存するだけ)。
2. 集約 findings を `id`・severity・C1〜C4 のどれか・location・1 行要約で一覧にして見せる (critical/high を先頭)。`id` が無い issue には表示順に `F-NNNN` を振り、選んでもらう前に findings.json へ書き戻す (選択と executor の `selected_finding_ids` を同じ id で結ぶため)。
3. `AskUserQuestion` で改善する finding を選んでもらう。選択肢は「critical/high だけ」「全件」「id を個別に選ぶ」「改善しない」。回答を得るまで編集を始めない。
4. 「改善しない」または選択 0 件なら executor を起動せず、findings の保存先を示して停止する。
5. 選択があれば `elegant-improvement-executor` を 1 worker で起動する。引数は `selected_finding_ids` = 選ばれた id、`max_rounds` = 3 (`convergence-policy.json` の安全弁)、`aggregated_findings` = 手順 1 の findings。
   対象 skill が content-review verdict を持ち、その `finding_locations[*].source_id` に選ばれた id があるときは、executor はその id をそのまま `sync-content-review-sha.py --finding-ids` に渡して verdict を結び直す (`run-build-skill/references/content-review-protocol.md`)。
6. executor が返した `validation_commands[]` が全件 exit 0 で、選んだ finding の C1〜C4 が再判定されていることを確かめる。再判定は content-review-protocol.md の「改善後の再レビュー」の 3 点 (選んだ指摘が解消したか・変わった hunk に新しい違反が無いか・criteria の被覆) に絞り、PASS 済みの節は読み直さない。executor が「要再レビュー」を返した skill のうち、変更が範囲つき再レビューの上限に収まるものは、独立 reviewer (`assign-skill-design-evaluator`) を skill ごとに 1 context 起動して変わった節だけを読ませ、`--scoped-review` で結び直す。上限に収まらない skill は、全体の再レビューが要ると報告する。
7. `changed_paths / validation_commands / residual_risks`、選んだ finding ごとの結果、選ばなかった finding の一覧 (未実施と明記) を報告する。

## 引数

| 引数 | 説明 |
|---|---|
| `capability-path` | 改善対象の skill/agent/hook/command パス (必須) |

## 失敗時

- target 不在: パス候補を表示し停止
- `max_rounds` を使い切っても収束しない: human_review に escalate し、未解決 finding を一覧出力
- validation script 不在: skip 理由を明示し、手動検証コマンドを提示
- 改善中に新しい問題が見つかった: 編集せず `residual_risks` に載せ、もう一度 `/skill-improve` で選ぶよう案内

## 注意

- 選んだ finding については破壊的変更を行う。事前に git commit clean を推奨。
- review のみを行いたい場合は `/capability-review` を使う。

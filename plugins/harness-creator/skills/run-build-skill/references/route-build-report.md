# route-build-report（plugin 一括 build の route 実行レポート契約）

`handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する plugin 一括 build (L4) で、route 1 本ごとの実行結果を次 route へ受け渡すための契約。単発 build (route 外の `/capability-build` や直接起動) は対象外。

## 目的

往路 (計画→build) は handoff routes が fail-closed で機械検証されるが、復路 (実行結果) は従来セッション記憶頼みで、route N の逸脱・申し送りが route N+1 に届かない断線があった。本契約はレポートをファイルとして固定し、依存チェーンを `validate-route-build-reports.py` で機械強制する。

## 出力先とファイル名

```
eval-log/<target_plugin_slug>/build/route-<route_id>.json
```

- `<target_plugin_slug>` は handoff の `target_plugin_slug`、`<route_id>` は `routes[].id` (例 `eval-log/harness-creator/build/route-C01.json`)。
- 同一 route の再 build は自分のファイルを上書きしてよい (route 単位で冪等)。他 route のファイルは書き換えない。
- eval-log 配下は transient (`.gitignore` の `eval-log/*/build/**`)。恒久 trace は built plugin 実体 + `validate-plan-coverage.py` が担い、本レポートは build 実行中の受け渡し証跡に徹する。

## 書く時機・読む時機 (受け渡しプロトコル)

1. **着手前 (read)**: route R の `depends_on` 各 id について `route-<id>.json` を読み、`handover` / `deviations` を R の build 入力に反映する。読んだパスは R 自身のレポートの `inputs_consumed` に列挙する。依存レポートが欠落、または依存 route の `status` が `success` 以外なら着手せず停止する (fail-closed)。
2. **完了後 (write)**: `schemas/route-build-report.schema.json` 準拠でレポートを書き、`validate-route-build-reports.py --handoff <path> --route <id>` exit0 を確認してから次 route へ進む。
3. **全 route 終端**: `validate-route-build-reports.py --handoff <path> --complete` exit0 で「全 route にレポートがあり failure ゼロ・orphan ゼロ」を機械確認する。依存を持つ route は dependency validator により `success` 以外の依存を拒否する。

```bash
python3 "$SKILL_DIR/scripts/validate-route-build-reports.py" \
  --handoff plugin-plans/<slug>/handoff-run-plugin-dev-plan.json --route C01
python3 "$SKILL_DIR/scripts/validate-route-build-reports.py" \
  --handoff plugin-plans/<slug>/handoff-run-plugin-dev-plan.json --complete
```

## フィールドの意図

| フィールド | 意図 |
|---|---|
| `summary` | 何を build し何を確認したか (次タスクの文脈初期化用・日本語 1-3 文) |
| `deviations` | 計画からの逸脱・代替生成 (contract-only route の展開手順など)。空配列=逸脱なし |
| `evidence` | 受入証跡 (lint exit0 / `eval-log/skill-build-trace.json` / pytest 結果)。success は 1 件以上必須 |
| `inputs_consumed` | 依存 route レポートの読取宣言 (depends_on 全件を被覆・validator が強制) |
| `handover` | 後続 route への申し送り。「渡すレポート」の本体で、次 route はここを必ず読む |
| `covered_task_ids` | (optional) task-graph route モードの束ね done 用。この report が done を賄う task-graph node id 群。**writer=dispatcher** (TG-C06 が node→route join `entity_ref==route.component_id` から決定論導出して書く・SubAgent は書かない)。`sync-task-state.py` (TG-C02) が done 遷移時に `task_id ∈ covered_task_ids` を照合する。不在時は単一 task 後方互換 (PR#70 契約) |
| `discovered` | (optional additive) `emit-discovered-task.py` で起票済み form の repo-root 相対パス列。**deviations 本文が discovered 報告へ言及するなら本フィールドで form パスを実証する** (validator が突合し、言及があるのに空/不在なら fail。corrections で訂正済みは除外)。残差が inbox 監査経路 (TG-C08 completion gate) に実際に乗った証跡 |
| `corrections` | (optional additive) 既存 report 本文の誤り文言への追記型訂正 `{target, correction, corrected_by}`。evidence 改竄禁止の下で原文を上書きせず訂正を監査可能に残す (例: `target: "deviations[2]"`) |

## 責務境界

- **書き手/読み手 = 後段 builder (L4)**: run-skill-create / run-build-skill / 代替生成を含め、route の build を実行した主体が書く。planner (run-plugin-dev-plan) はレポートを生成しない。
- **schema / validator の正本は本 skill 配下** (`schemas/route-build-report.schema.json` / `scripts/validate-route-build-reports.py`)。planner 側 `io-contract.md`「build handoff 契約」の route 実行レポート節は本契約への参照宣言であり、内容を再定義しない。
- 単一 skill build 内部の工程受け渡し (`eval-log/handoff-<step>.json` / `skill-build-trace.json`) とは階層が異なる: あちらは 1 component の内側、本契約は component (route) 間。

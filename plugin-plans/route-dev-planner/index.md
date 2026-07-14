# route-dev-planner — 開発構想の plugin/system 選定 router (plan)

> `/plugin-dev-plan` と `/system-dev-plan` の上位にある薄い独立 router。自然文の開発構想を受け、それが **Claude Code plugin 実体の構築** か **導入先リポジトリの system 開発** かを機械判定し、正しいプランナーへ dispatch する。計画生成そのものは各プランナーへ委譲し、router は「どちらを起動するか」だけを決める。

## 位置づけ (3 プランナーとの関係)

```
                       route-dev-planner (本 plan)
                     構想文 → classify_construction_target
                     ┌───────────────┴───────────────┐
              plugin ルート                      system ルート
                     │                                │
        /plugin-dev-plan                    dev-graph マクロ分解 (feature 群)
     (plugin-dev-planner)                            │
     plugin 実体を計画                    ready feature ごとに /system-dev-plan
                     │                    (system-dev-planner: 1 feature→13 task)
   task-graph → beads 直接投影                       │
   (§6 consumer projection)          dev-graph atomic 登録 → tracker_binding 解決
                                          (§1-§5 execution-tracker-contract)
```

- **plugin ルート**: 成果物が `plugins/<slug>/` 配下の Claude Code plugin 実体 (skill/sub-agent/slash-command/hook/script)。
- **system ルート**: 成果物が導入先リポジトリのアプリ/API/インフラ等の system コード。dev-graph がマクロ(feature)、system-dev-planner がミクロ(1 feature=13 task specs)を担う。

## 成果物

- `goal-spec.json` — router の目的/背景/受入チェックリスト (R1-R5)。
- `route-dev-planner-contract.md` (main) — router の I/O 契約・分類シグナル・dispatch 表・フォールバックの正本。§3 `classify_construction_target` にユーザー協働ポイント (人手で埋める分類シグナル) を設置。

## 判定基準の正本

判定基準の**正本は `plugin-plans/dev-graph/references/execution-tracker-contract.md §0`**。route-dev-planner-contract はそれを引用・機械化し、複製・改変しない。router 不在・低信頼時は §0 を人間/orchestrator フォールバックとして維持する (router は fail-open しない)。

## スコープと成熟度 (build-deferred router contract)

- 本 plan は軽量 router のため **13 phase フル展開・`component-inventory.json`・`task-graph.json`・`handoff-run-plugin-dev-plan.json` を意図的に持たない** router-contract 主体の **build-deferred plan** である。
- したがって `goal-spec.json` は `check-plugin-goal-spec.py` に適合する (PASS) が、`validate-task-graph.py` / `check-provenance-chain.py` 等の**フルプラン前提ゲートは現段階では対象外**とする (dev-graph/system-dev-planner が「plan=PASS・build=blocked」であるのと同様、route-dev-planner は「contract=確定・full-plan=deferred」の段階)。これは省略ではなく明示的な繰延であり、標準ゲートを緑にしたと誤認しない。
- フル plugin 化 (13 phase + task-graph + handoff を揃え標準ゲート全適合) が必要になった時点で、`/plugin-dev-plan "route-dev-planner ..."` で本 plan を入力に昇格する (follow-up として beads 追跡)。
- 実プラグイン/実コードは生成しない (L3 plan まで)。

# Mode Catalog (next-action)

| mode | 名称 | handoff_target | 渡し先 phase (右列=harness_creator_handoff_phase 逐語コピー正本) |
|--|--|--|--|
| A | 完全新規 | harness-creator | Step 1 (elicit) |
| B | 既存類似 80%+ | harness-creator | Step 1 (elicit --mode update) |
| C | プロンプト改善のみ | harness-creator | Step 1 (elicit --mode update, prompt-only) |
| D | マルチスキル分離疑い | harness-creator | Step 1 (elicit, split first) |
| E | 判定不能 | harness-creator | P1-kickoff (re-intake) |
| P | plugin 規模構想 | plugin-dev-planner | R1 (elicit-goal) |

> **語彙の正本**: A-D の「Step 1 (elicit)」系は `plugins/harness-creator/skills/run-skill-create/SKILL.md` の実在語彙 (Step 1 elicit → Step 2 build → … → Step 7 report、`--mode create|update`)。E の「P1-kickoff」は本 plugin `run-skill-intake/workflow-manifest.json` の phase id (再ヒアリング=intake を P1 からやり直し。harness-creator へは再 intake 完了後に到達するため handoff_target は harness-creator のまま)。P の「R1 (elicit-goal)」は `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/prompts/R1-elicit-goal.md` の責務 id。

## mode P 判定条件 (decide-mode.py 判定表)

plugin 規模構想 (複数コンポーネント/hook/command 要望や複数 skill 分解が濃厚) は、以下のいずれかで mode P を確定する (D/E 判定より先に評価):

1. `summary.json` / `options.json` / `kickoff.json` のいずれかに `plugin_scale: true` の明示宣言がある
2. `summary.json` / `options.json` の `component_requests[]` に skill 以外のコンポーネント種別 (`hook` / `command` / `slash-command` / `agent` / `sub-agent` / `mcp`) が含まれる
3. `component_requests[]` の skill 系要素が 2 件以上ある (複数 skill 分解が濃厚)

mode P 確定時は `run-plugin-dev-plan` R1 へ intake.json を構想材料として引き渡す (渡す § の写像は plugin-root 正本 `plugins/skill-intake/references/handoff-contract.md` の「plugin-dev-planner 分岐 (mode P)」節が正本)。intake 側は推奨を出して停止し、`run-plugin-dev-plan` を起動しない。

> **軸の独立性**: ここで定義する `mode` の A-E/P は「次アクション判定」軸であり、Notion 正本 (`notion-db-schema.json`) の **ワークフロー** (A 単体 / B 自動収集配信 / …) や **パターン** とは **独立した分類** である。記号 (A-E) が一致しても意味は別軸なので相互に読み替えてはならない。

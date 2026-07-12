# followup PR handoff: skill-creator elegant-review 20260524-131500

本ドキュメントは Phase3 自動改修で対応せず後続 PR へ持ち越した 4 件 + 補足 1 件を記述する。

## AGG-003: frontmatter commoncore 直書き重複 (version/since/owner ×6 agent)

- 状況: `plugins/skill-creator/agents/*.md` 6 ファイルで `version: 0.1.0 / since: 2026-05-24 / owner: team-platform` を直書き
- スキップ理由: 自動 inject を導入するには (a) SSOT yaml (例: `plugins/skill-creator/references/agent-commoncore.yaml`) の新設、(b) build 時の render-frontmatter スクリプト or pre-commit hook、(c) lint で直書きを検出する `lint-frontmatter-ssot.py` の 3 点セット導入が必要で、最小パッチ範囲を超える
- 後続 PR タスク
  1. `plugins/skill-creator/references/agent-commoncore.yaml` を新設し version/since/owner を集約
  2. agents/*.md frontmatter から該当 3 キーを削除し、CI で SSOT から inject する build step を追加
  3. `lint-frontmatter-ssot.py` で直書き検出時 exit 1
- 検証: `grep -rn "^version: 0.1.0$" plugins/skill-creator/agents/` が 0 件

## AGG-005: evaluate.yaml 401 行 → 300 行制約違反疑い

- 場所: `plugins/skill-creator/skills/assign-skill-design-evaluator/prompts/evaluate.yaml`
- スキップ理由: Layer 5 内の error-handling / セキュリティ重複ブロックを `references/` 配下へ外出しする必要があり、参照解決パスの再配線・schema 更新を含む大規模差分。意味変更を伴わない最小パッチに収まらない
- 後続 PR タスク
  1. evaluate.yaml の重複ブロックを `references/evaluator-common-policy.yaml` 等へ抽出
  2. yaml 本体は include/参照キーに置換
  3. 300 行制約を CI 化 (`lint-prompt-length.py`)
- 検証: `wc -l prompts/evaluate.yaml` < 300

## AGG-006: md/yaml 7 層表現分裂 (SSOT 不在)

- 状況: md prompts 28 件 vs yaml prompts 7 件が混在
- スキップ理由: `seven-layer-format.md` を正本宣言した上で、yaml 7 件に `lifecycle: legacy, sunset: <date>` frontmatter を必須化し、最終的に md へ移行する phase-out 計画が必要。今回 commit 内で正本宣言だけ書くと yaml 側との実体二重化が固定される
- 後続 PR タスク
  1. `seven-layer-format.md` の冒頭に「md が正本、yaml は legacy」を明記
  2. yaml 7 件に `lifecycle: legacy / sunset: 2026-08-31` 等の frontmatter を一括付与
  3. `lint-yaml-prompt-deprecation.py` で sunset 超過時 warn → CI で fail に昇格
  4. 別 PR で yaml → md 移行 (1 ファイルずつ)
- 検証: `find plugins/skill-creator -name '*.yaml' -path '*/prompts/*'` 全件が `lifecycle: legacy` を含む

## AGG-007: 信頼度スコア閾値の skill 別バラつき (0.6 vs 0.7)

- 場所: `run-skill-elicit/prompts/main.yaml:92` (0.6) と `assign-skill-design-evaluator/prompts/evaluate.yaml:123` (0.7)
- スキップ理由: 一元化のため `plugins/skill-creator/references/common-policy.yaml` を新設し、両 yaml から参照する仕組みが必要。実体二重化を解消するには参照解決機構が前提
- 後続 PR タスク
  1. `plugins/skill-creator/references/common-policy.yaml` を新設し `confidence_threshold: 0.7` を一本化 (高い側に統一推奨)
  2. 両 yaml から直値を削除、参照キーに置換
  3. `lint-policy-ssot.py` で直書き検出時 exit 1
- 検証: `grep -rn "信頼度スコア閾値: 0\." plugins/skill-creator/skills/` が 0 件

## 補足 (Phase3 で副次検出): quality-rubric 参照のテンプレ側残存

- AGG-002 で agents/ 配下 2 ファイルの参照パスを内部化したが、テンプレート 2 ファイルが同パスを参照し続けている:
  - `plugins/skill-creator/skills/run-build-skill/references/agent-template.md:103`
  - `plugins/skill-creator/skills/run-build-skill/templates/agent-skeleton.md:73`
- スキップ理由: 当該箇所は findings location 列挙外。テンプレ書換はテンプレで生成される新規 agent に対する影響評価が必要で、最小パッチ原則の範囲外
- 後続 PR タスク: 上記 2 ファイルの参照を `plugins/skill-creator/references/quality-rubric.md` に書換 (1 行 sed で完結)
- 検証: `grep -rn "plugins/skill-intake/.*quality-rubric.md" plugins/skill-creator/` が 0 件

---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
「ローカルtask graph/Markdownで仕様成果物を一元管理し、BeadsまたはGitHubへbinding別投影しながら要件定義から実装handoff・PR完了収束までを担う管理ハーネス」を目的ドリブンに要件化する。directory/routing、template、planner選定、tracker authority、Projects表示、hooks、複数worktreeを一次要件として固定する。

## 背景
このプラグインは、リポジトリ内で分散しがちなタスク・ドキュメント・仕様管理を単一グラフへ一元化し、GitHub Issues/Projects との二重管理・ドリフトを解消する構想から出発する。単語置換ではなく目的ドリブンで要件化しないと後続の component 分解が破綻するため、全 13 フェーズが参照する不変の goal-spec を最初に固定する必要がある。同一構想は常に同一 `PLAN_DIR` へ解決され (再現性アンカー)、以降のフェーズはこの goal-spec を唯一の起点にする。

## 前提条件
- プラグイン構想 1 件 (自然文 + 任意でコンポーネント希望) が入力として与えられている。
- 汎用の `run-goal-elicit` (harness-creator) が利用可能で、purpose/background/goal/checklist を `goal-spec.schema.json` で抽出できる (再実装しない)。
- このフェーズは特定 component へ紐づかない (責務は goal-spec 確定・target_plugin_slug 固定)。

## ドメイン知識
- タスクグラフ = issue/task/specification/architecture/feature/document の各情報を単一のグラフ構造で保持するデータモデル。
- 二層モデル (マクロ/ミクロ) = dev-graph はマクロ層として機能 (feature) 単位に purpose/goal/scope_in/scope_out/acceptance/architecture_refsと機能間依存を保持し実行をオーケストレーションする。各 feature の細タスク仕様書生成 (1機能=13タスク仕様書+機能内依存DAG) は external plugin system-dev-planner (ミクロ層) へ委譲し、promoted task を parent_feature 付きで feature 配下へ登録する。
- binding別同期 = GitHub bindingはIssueをid+updated_at、Beads bindingはstatus/depends_on edge parityで突合する。Projects Statusはlocal_to_projectで完了authorityではない。
- hybrid directory policy = `issues/tasks/specs/architecture/features/docs`をartifact_kindの物理rootとし、project_id/domain/status/tags/graph_node_idをfrontmatter metadataで横断管理する方針。ユーザーは保存先を指定しない。
- 段階分割 = flat-firstで、1 leafが200件超のときだけdomain→project_id→YYYY/MMを順次追加し、dry-run migration manifestとrollbackで安全に再配置する規則。
- 作業コンフリクト = 同期コンフリクト (id+updated_at) とは別レイヤの、並列実行タスクが同一リソース (ファイル/ディレクトリ) を touch することで生じる衝突。resource_scope 重複回避で最小化する (要件C10)。
- テンプレート正本 = issue/task/document/specification/architecture の各 artifact kind が持つ構造化フォーマットの唯一の SSOT (frontmatter 必須キー + 本文必須セクション床)。init 時に導入先へ scaffold し、node 作成時に適用し、schema 検証が必須セクション欠落を fail-closed 検出する (要件C18)。
- implementation-readiness = 要件定義が参照する成果物についてテンプレート必須セクションが充足しているかの機械判定状態 (complete/incomplete/not_applicable)。不足時は不足セクション一覧を surface する (要件C20)。
- symlink配布モデル = code/assetsは共有source、content/config/stateはcaller repository正本。root外read/writeと別repo混入を禁止する (要件C24-C26)。
- Claude hook = completionの唯一authorityではなく、SessionStart/PostToolUse/TaskCompletedからlocal reconciliationとtask completion gateを加速するproject-aware adapter (要件C35-C38)。
- worktree lease = 同一repositoryの複数worktree間で同一taskの二重実装を避けるephemeral排他契約。contentはworktree内、lease/eventだけを検証済みgit common dirで共有する (要件C39-C42)。
- 実行トラッカー抽象化 = 実行タスクをAIエージェント=beads (bd) / 人間=GitHub Issuesで管理するハイブリッド要件 (C43-C47)。repo単位選択・ノード単位束縛・完了カスケード・単一チョークポイントの正本は `references/execution-tracker-contract.md` (詳細は再記述しない)。
- 仕様/architecture authority = `plugins/system-spec-harness/`。system task plan構造参照 = `plugins/plugin-dev-planner/`。引用は契約再利用でありコード複製ではない。
- goal-spec は全 goal-seek 周回で不変のアンカー (target_plugin_slug/plan_dir を含め以降のフェーズが書き換えない)。
- その他の plan 全体用語 (component_kind/couples_with 等) は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist/constraints/handoff_targets/open_questions)。
- target_plugin_slug と plan_dir の確定値。

## スコープ外
- component 分解・GitHub Projects v2 フィールドマッピングや競合タイブレーク規則の確定 (P02 へ委譲)。
- ヒアリング機構の再実装 (`run-goal-elicit` を引用するのみ・再発明しない)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、受入観点が purpose 語彙から導出されている。
- [ ] target_plugin_slug が ASCII kebab (`dev-graph`) で確定し以降のフェーズがそれを参照できる。
- [ ] `check-plugin-goal-spec.py` が exit0 (R1 goal-spec + plugin 固有アンカー充足)。

### 受入例
- 満たす例: 構想とintakeを入力すると、`goal-spec.json` にpurpose非空・target_plugin_slug=`dev-graph`・checklist 53件 (C1-C53)・source_intake/source_improvementが生成され、検証がexit0になる。
- 満たさない例: `goal-spec.json` の purpose が空文字、または checklist が 0 件のまま生成される → `check-plugin-goal-spec.py` が exit1 で fail する (下流へ進めない)。
- 満たさない例: target_plugin_slug が `Dev_Graph` のような非 ASCII-kebab 形式で確定される → 後続フェーズの plan_dir 解決が破綻するため境界外。

### 事前解決済み判断
- target_plugin_slug は `dev-graph` に固定し、以降のフェーズは再確認せずこの値を参照する (再現性アンカー)。
- goal-spec は全 goal-seek 周回で不変のアンカーとし、後続フェーズは goal/checklist/constraints を書き換えない (追記は goal-spec 側の明示 update のみ)。
- ヒアリング機構は既存の `run-goal-elicit` (harness-creator) を引用し、本 plan では再実装しない。

## 参照情報
- `references/purpose-driven-requirements.md` (目的ドリブン要件化の正本)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02 (この goal-spec を component 分解の入力とする)。

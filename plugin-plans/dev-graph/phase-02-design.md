---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C24, C25, C26, C27, C28]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
capability を 5 種の component_kind (skill/sub-agent/slash-command/hook/script) へ写像し、N=24 実体を `component-inventory.json` へ分解する。既存routing/GitHub/task schedulingに加え、artifact template、system-spec-harness引用、symlink caller/worktree resolver、Claude hook、GitHub lifecycle reconciler、worktree leaseの依存DAGとplugin envelopeを確定するownerフェーズ。

## 背景
P01 で確定した goal-spec を build 可能な実体へ落とす最初の設計フェーズ。5 種の component_kind を検討した上で N=24 実体へ分解し、phase axisとinventory axisを正規化する。GitHub同期(C03)、要件導出(C04)、system-spec引用(C19)、caller/worktree resolver(C24)、Claude hook(C25)、lifecycle reconciler(C26)、worktree lease(C27)、beads bridge(C28)は責務を分離し、build_target/depends_onはinventoryだけが保持する。

## 前提条件
- P01 の `goal-spec.json` が確定している。
- 5 種の component_kind の写像規約 (`references/component-domain.md`) と envelope 物理契約 (`references/plugin-creator-contract.md`) を参照できる。
- 同一 kind の複数実体 (現行skill×9) はそれぞれ独立 component として扱う前提を共有している。
- goal-specの設計open questionは0件。Projects field mappingとtask粒度は導入repoごとのruntime configuration、タイブレーク/resource_scope/template内訳は本planで確定済みとして区別する。

## ドメイン知識
- 正規化原則: build_target/depends_on は `component-inventory.json` のみが保持し、phase ファイルは `entities_covered` の id 参照だけで紐づく (二重保持は drift 源)。
- kind 写像の判定核: `needs_independent_context`→sub-agent、`needs_lifecycle_enforcement`→hook、決定論検査→script (5 種の定義は index `## ドメイン知識` 参照)。
- `placement_scope`: script のみ持つ配置属性 (skill=親 skill 配下 / plugin-root=複数 skill 共有の hoist)。plugin-root への昇格根拠は「第二消費者あり」または「決定論ゲートとしての独立検証性 (proposer≠approver の再検証対象になり得る決定論出力)」のいずれかとする (根拠なき昇格は不要な水増しであり避ける)。共有スキーマ検証 (`validate-graph-schema.py` C11)・gh CLI ブリッジ (`gh-bridge.py` C12)・HTML レンダラ (`render-graph-html.py` C13) は 2 skill 以上の第二消費者を持つため、スケジューラ (`schedule-graph.py` C16) は単独 consumer (C15) のみだが決定論ゲートとしての独立検証性 (C17 が proposer≠approver で resource_scope 重複判定を再検証する対象であること) を根拠に、いずれも plugin-root へ hoist する。
- **読取り専用検索/状態確認の設計 (要件C11)**: `run-dev-graph-status` (C18) は C02/C11 のみに依存し書込み経路を持たない (グラフストア・GitHub 双方に副作用なし)。既存の sync/render の重い経路と混同しないよう独立 skill として分離する。
- **ストレージモデルとauthority**: 全artifactは正規root配下Markdownを本文/status正本、graphをedge/linkage/receipt正本、`graph_node_id`を不変とする。taskの外部projectionはtracker_bindingで一意に選び、Projects Statusはlocalから一方向、PR mergeは完了事実authorityとする。
- **自動分類routing**: C02は成果物内容+任意hintからartifact_kind/domain/project_idを推定し、候補path/confidence/reasonを常時previewする。confidence>=0.80かつ第2候補との差>=0.15なら自動確定し、それ未満だけユーザー確認する。保存directory自体は質問しない。
- **scaling/migration**: kind rootはflat-first。1 leafが200件超でdomain、再超過でproject_id、なお超過時だけYYYY/MMへ分割する。自動collapseは禁止。移動はdry-run manifest、旧→新path、link検証、rollbackを持ち、graph_node_idを維持したままC03がfile_path/linkageを原子的に更新する。
- **issue_linkage フィールド設計 (要件C7)**: `schemas-draft/graph-node.schema.json` の `issue_linkage` (issue_number/repo/linked_at) は C14 (decompose) が Issue 起票時に一度だけ書き込む。C03 (sync) はこのフィールドの有無で新規起票要否を判定し、linkage 済みノードは `updated_at` 比較のみを行う (create→sync の起票非重複契約)。
- **close/delete の tombstone 双方向伝播設計 (要件C12)**: `schemas-draft/graph-node.schema.json` の `status`(open/closed/tombstoned)・`closed_at` フィールドを C03 (sync) が書込み、C02 の『物理削除はしない』境界に従うソフトデリートとして表現する。
- **dry-run/preview 設計 (要件C13)**: C03 (sync)・C14 (decompose) は `--dry-run` を第一級責務として持ち、指定時は GitHub 側書込みを一切行わず差分/起票予定のみをプレビューする。`guard-graph-schema` (C10) hook は gh write の暴発も検知対象に含める。
- **修正改善容易性の設計 (要件C14)**: Markdown本文とfrontmatterはEdit差分で直接変更できる。分類に影響する変更は即時C11検証後にC02のpreview付きmigrationへ送る。検証なしmove、全書換、物理削除は禁止し、C03/C05は不変graph_node_idを使って追従する。
- GitHub Projects v2 フィールドマッピング規則の確定先: `run-dev-graph-sync` (C03) の R1-elicit 責務が、同期対象 repo の Projects v2 カスタムフィールド (ステータス/優先度等) とタスクグラフ属性の対応表をヒアリングし固定する (index `## ドメイン知識` に規則の所在を明記済み)。
- id+updated_at 同時競合タイブレーク規則: updated_at が新しい方を採用し、同時刻は GitHub 側を正としてローカルに手動確認フラグを立てる (fail-closed)。C03 の `feedback_contract.criteria` OUT2 として固定する。
- 自然文マクロ分解の粒度・判断基準 (open_question 3 の確定先、MM-04 でマクロ分解へ retarget 済み): `run-dev-graph-decompose` (C14) の R1-elicit 責務がfeature単位のマクロ分解粒度基準・機能間依存推定方針をヒアリングして固定し、feature+architecture+機能間depends_onのDAGが循環なし・粒度閾値内であることをOUT1 criterionに持つ。1機能=13タスク仕様書への細粒度分解はsystem-dev-planner (ミクロ層) 側のR1-elicit相当責務へ委譲し、本componentのgranularity判断対象としない。
- resource_scope の粒度とフォールバック規則 (open_question 4 の確定先): 既定はディレクトリ単位、ノードがファイル単位を明示した場合はファイル単位を優先し、双方混在時は広い方 (ディレクトリ単位) へフォールバックする。`schemas/graph-node.schema.json` (`plugin_level_surfaces.schemas`) に `resource_scope` (touches: ファイル/ディレクトリ配列) フィールドを設計し、`validate-graph-schema.py` (C11) が検証、`schedule-graph.py` (C16) が重複判定に利用する。
- ready-set/並列実行支援の設計核: `schedule-graph.py` (C16) が depends_on 充足済み・未完了ノードを ready 候補化し、resource_scope 重複ノードを同一並列バッチへ入れない conflict-aware バッチングで並列実行可能バッチを決定論的に導出する (plugin-dev-planner の `compute-ready-set.py` の思想を踏襲)。
- system-spec引用境界: C19はsystem-spec-harnessの公開entry pointを呼び、source lineageを保ってC02へ渡すだけでcompiler/question bank/coverage gateを複製しない。
- system task plan設計 (external引用): システム開発タスク仕様書ハーネスはexternal plugin system-dev-plannerが所有し、dev-graphはrun-system-dev-planをSkill呼出しで引用する (external_contract_ref: plugin-plans/system-dev-planner/handoff-run-plugin-dev-plan.json)。13 lifecycle axis、N system workstream inventory、typed task DAGの3射影とplugin語彙→system workstream/touches/deploy unit置換は同plugin側の契約に従う。implementation_readiness/validator (validate-system-plan.py) も同pluginが所有する。
- system plan publish設計: 13 phase docsとN typed task specsを分離し、draft/blocked staging→system-dev-planner側の決定論検証+独立評価の同一digest PASS→C02 atomic promotionとする。C14/C15/C04はconfirmed/pass/readiness completeのみ消費する。
- multi-repo context設計: C24を全local content consumerの上流に置き、symlink source pathはcode discoveryだけ、repo content rootはcaller contextだけから解決する。候補rootはhost宣言`$CLAUDE_PROJECT_DIR`のrealpathと一致しなければ拒否する。C24はroot選択source/trust evidence、再導出済みrepository_id、content roots、local graph/cache/lock pathsを出力し、`.dev-graph/config.json`はrepo相対pathのみ許しrealpath containmentを強制する。
- Claude/worktree設計: C25はClaude event adapterだけ、C26はGitHub completion state machine、C27はgit-common-dir lease/event coordinationだけを担う。feature branchではpending eventのみ、clean default branchでだけdurable task/graph projectionを更新する。
- beads実行トラッカー設計 (要件C43-C47): C28単一チョークポイント、status/depends_on edge parity、C28 bd claim authority+C27 reservation saga、remote default ancestor確認済みPR merge→local graph/task→最後にbd closeのstep ledgerで構成する (正本=`references/execution-tracker-contract.md`)。

## 成果物
- `component-inventory.json` (build 軸の唯一 SSOT・全 24 component)。
- `envelope-draft/plugin.json` (manifest draft)。
- `schemas-draft/graph-node.schema.json` (graph-node schema draft・envelope の manifest と同型の draft_path 契約)。
- `templates/` (artifact templateとsystem-plan contractのmanual-apply draft)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [ ] 全 24 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces の採否が明示されている。
- [ ] `envelope-draft/plugin.json` に manifest draft (entry_points / hooks 配線 / distribution) が設計されている。
- [ ] repo固有Projects field mappingはC03 R1、repo固有task粒度はC14 R1のruntime configurationとしてownerが固定されている。
- [ ] id+updated_at同時刻規則、resource_scope、template/readiness内訳はindex/schema/templatesへ確定済みdecisionとして反映されている。
- [ ] schema draftにgraph_node_id/artifact_kind/project_id/domain/status/tags/file_path/classification_*と既存resource/sync fieldsが設計されている。
- [ ] グラフノード⇄実ファイルのストレージモデル橋渡し設計 (正本方向・file_path 参照) が本フェーズに記載されている。
- [ ] `run-dev-graph-status` (C18) の設計 (read-only・副作用なし) が本フェーズに記載されている。
- [ ] 要件C14-C17: 6正規root、metadata、保存先不要routing、confidence gate、200件境界分割、dry-run migration/rollbackが記載されている。
- [ ] 要件C18-C23: template/readinessとsystem-spec引用がC19へ配線され、system task plan・独立評価・fail-closed handoffはexternal system-dev-planner引用 (C04/C09/C14が消費) で充足されている。
- [ ] 要件C24-C26: symlink/caller root分離、repo-local config/state、containment、multi-repo isolationがC24と全consumer dependencyへ配線されている。
- [ ] 要件C31-C42: PR merge completion、Claude hook、worktree identity/lease/default-branch convergenceがC25-C27へ配線されている。

### 受入例
- 満たす例: `component-inventory.json` に C01-C19/C24-C28 の 24 component が build_target 非空・depends_on 非循環で載り、`check-surface-inventory.py`/`check-build-handoff.py` が exit0 になる。
- 満たす例: schema requiredにgraph_node_id/artifact_kind/project_id/domain/status/tags/file_pathがあり、file_path patternが6正規root (features含む) だけを許可する。
- 満たさない例: script (C11/C12/C13/C16) が「第二消費者あり」の根拠を示さないまま plugin-root へ hoist される → 昇格根拠不明の水増しとして本フェーズの完了条件を満たさない。

### 事前解決済み判断
- id+updated_at 同時競合のタイブレーク規則: updated_at が新しい方を採用、同時刻は GitHub 側を正としローカルに手動確認フラグを立てる (open_question 2 の確定)。
- plugin-root hoist の判定基準: 「第二消費者あり」または「決定論ゲートとしての独立検証性」のいずれかを根拠とする (C16 はこの後者で hoist・open_question に依らず本フェーズで固定)。
- resource_scope の粒度既定はディレクトリ単位、ノードがファイル単位を明示した場合はファイル単位優先、混在時は広い方 (ディレクトリ単位) へフォールバック (open_question 4 の確定)。
- グラフノードと実ファイルの正本方向: 実ファイル内容が正本、グラフノードはメタデータ (id/status/updated_at/file_path 等) のみを保持しミラーしない (ストレージモデル橋渡し設計の確定)。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md` / `references/plugin-creator-contract.md`。
- 対象 component C01-C19・C24-C28 (計24・`component-inventory.json`)。
- 後続 P03 (この設計を design-gate で審査する)。

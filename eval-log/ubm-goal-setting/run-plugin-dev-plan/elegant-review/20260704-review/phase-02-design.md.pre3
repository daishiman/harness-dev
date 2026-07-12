---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C15, C16, C17, C18, C19]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
本 plan は greenfield 構想でなく既存資産の移植 (port) であり、本 phase は再設計でなく faithful-transfer+adapt (.sh→.py 書き換え・vault パス変数化) の性格を持つ (13 phase 構造自体は保持する)。capability を目標設定・振り返り対話 (capability A) とナレッジ差分同期 (capability B) の 2 系統へ分け、5 種の component_kind (skill/sub-agent/slash-command/hook/script) へ写像し N=18 実体を `component-inventory.json` へ分解する。Obsidian vault 固有パス (`05_Project/UBM/目標設定/`、`02_Configs/Daily/`) の変数化を設計し `envelope-draft/plugin.json` へ焼く。

## 背景
P01 で確定した goal-spec を、実際に build 可能な実体へ落とす最初の設計フェーズ。移植元は非量産資産 (skill/sub-agent/slash-command/script/reference/asset/knowledge JSON が個別に存在) であり、5 種の component_kind を必ず検討した上で N=18 実体へ分解しないと単一 skill への退化 (capability A/B の責務混在) を招く。build_target/depends_on は inventory のみが保持し、phase は id 参照だけで紐づく正規化を敷く。

## 前提条件
- P01 の `goal-spec.json` が確定している (checklist C1-C7 が purpose 由来で定義済み)。
- 5 種の component_kind の写像規約 (`references/component-domain.md`) と envelope 物理契約 (`references/plugin-creator-contract.md`) を参照できる。
- 移植元資産の実棚卸し結果 (slash-command 2 本・中核 skill 1 本・sub-agent 11 本 (旧 phase3-interviewer 含む)・shell script 3 本・reference 8 本・asset 5 本・knowledge JSON 群) が確定している。

## ドメイン知識
- 二相 skill build: C01-C03 (script) は toposort 上 C16/C17 (親 skill) より先に build されるが build_target は親 skill 配下パスであるため、「run-skill-create が空 scaffold を先行生成→parent-skill-build が scripts/ を充填」の二相で調停する (`component-inventory.json` の `build_sequencing_notes` が正本)。
- data-tier 3 層: knowledge は単一の vendor/非vendor 判断でなく L1 curated (vendor同梱シード)/L2 raw vault sources (外部 env 解決)/L3 bookkeeping (空seed+writeback-config) で設計する。
- 消費者ゼロ leaf の DROP 判断: 旧 phase3-interviewer は新プラグインの別名前空間では旧呼出し元が到達せず inbound depends_on 0 になるため独立 component 化せず phase3-coordinator+steps1-5 への統合として扱う。
- その他の plan 全体用語 (component_kind 5 種の定義等) は index `## ドメイン知識` を参照。

## 成果物
- `component-inventory.json` (build 軸の唯一 SSOT・全 18 component + considered_alternatives)。capability A (info-collector/output-formatter/goal-reviewer/phase3-coordinator/steps1-5 の 10 sub-agent + 中核 skill run-ubm-goal-setting + slash-command ubm-goal-setting)、capability B (knowledge-extractor sub-agent + 中核 skill run-ubm-knowledge-sync + slash-command ubm-knowledge-sync) への写像、3 本の既存 shell script の Python script component (C01/C02/C03、placement_scope=skill で親 skill 配下へ畳む) 登録、depends_on の非循環 DAG (steps1-5 → phase3-coordinator → run-ubm-goal-setting、knowledge-extractor → run-ubm-knowledge-sync) を含む。
- `envelope-draft/plugin.json` (manifest draft・vault_root_env 変数化込み)。Obsidian vault 固有パスは `{{VAULT_ROOT}}` 型テンプレート構文 (build-handoff の TODO_RE で禁止) ではなく `config.vault_root_env` (環境変数名 `UBM_VAULT_ROOT`) として具体的に設計する。
- `plugin-composition.yaml` (plugin 構成定義。本 phase がオーナー成果物)。
- considered_component_kinds (5 種全検討証跡) と plugin_level_surfaces の採否記録 (schema.json は C16/C17 が対称参照する plugin-root 共有 surface へ hoist)。references 8 本 + assets 5 本の per-file 移送先 (`plugin_level_surfaces.references_config_assets.files`)。
- considered_alternatives: (a) 1 skill 統合案 (capability A/B を単一 skill にまとめる) — 責務混在・独立テスト不能のため棄却。(b) knowledge 独立 plugin 化案 — 単一 plugin 内の 2 capability が共有する内部データであり cross-plugin SSOT 化の便益がコスト (配布・バージョニングの分裂) に見合わないため棄却。(c) knowledge を symlink 共有する案 — plugin 配布は tarball 化されるため symlink は配布時に解決できず棄却 (plugin-root hoist が採用案)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 `plugins/` へは書かない)。
- shell script の実装ロジック逐語移植 (契約移植=検知/検証ロジックの移植を優先し、実装自体は P05 の責務)。

## 完了チェックリスト
- [ ] 全 18 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces の採否 (vendor の data-tier 3 層・mcp_app_connector の omitted_reason 含む) が明示されている。
- [ ] references 8 本 + assets 5 本の per-file build_target が列挙され、considered_alternatives が記録されている。
- [ ] `envelope-draft/plugin.json` に config.vault_root_env (UBM_VAULT_ROOT) を含む manifest draft が設計されている。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md` / `references/plugin-creator-contract.md`。
- 対象 component C01-C19 (`component-inventory.json`)。
- 後続 P03 (この設計を design-gate で審査する)。

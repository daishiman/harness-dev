---
id: IDX0
title: harness-creator SubAgent/prompts 7層準拠強制 開発計画 index (main)
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_unresolved_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: true
    policy:
      installation: NOT_AVAILABLE
      authentication: ON_INSTALL
      category: Developer Tools
    cachebuster_for_update: true
  distribution:
    distributable: false
    bundles: []
    marketplace: false
  ci:
    workflow: governance-check
    also_wired: harness-creator-kit-ci
  pkg_contract:
    pkg: 002-008
  governance:
    runbook: required
  ssot_dedup:
    lint: ssot-duplication
    vendored_source: plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/verify-completeness.py
    vendored_copy: plugins/harness-creator/vendor/prompt-creator/verify-completeness.py
  feedback_deploy:
    deploy: run-skill-feedback
    enabled: true
    notion_sink:
      config_key: improvement-request
      schema_ref: doc/notion-schema/improvement-request.schema.json
      resolution: notion_config
    portability: repo-bundled
---

# harness-creator SubAgent/prompts 7層準拠強制 開発計画 index (main)

## 基本定義
本 plan の plan_dir は plugin-plans/harness-prompt-conformance/ (target_plugin_slug=harness-creator の既存プラグイン更新)。目的 (goal-spec.purpose) は、harness-creator の各 SubAgent (agents/*.md) およびスキル配下 prompts/*.md が prompt-creator の7層仕様 (l5-contract v2.0.0) に基づいて確実に作成・検証される状態を機械層で担保し、既存の不整合を是正すること。要件正本は goal-spec.json の checklist (C1-C8)。スコープに含む: (1) prompt-creator 側への SubAgent ハイブリッド契約 SSOT 新設 (C01)、(2) harness-creator 側の内容 lint 新設 (C02)、(3) 既存6 SubAgent の是正 (C03-C08)、(4) run-build-skill の生成フロー配線 (C09)。スコープに含まない: plugin-plans/plugin-dev-planner/・plugin-plans/skill-intake/・plugin-plans/harness-creator/ (別件 E1/E2/E3 パイプライン境界契約 plan) への変更 (C8)。実 build/実装着手そのもの (本 skill の既定境界)。

## ドメイン知識
- ID 名前空間: goal-spec.json の checklist id (C1-C8) と component-inventory.json の component id (C01-C09) は無関係な別の名前空間であり、本文書内で明確に区別する。
- 名前空間対応: C1-C8 は「満たすべき要件」、C01-C09 は「build 可能な実体」。例: 要件 C5 は component C09 が主担当、要件 C3 は component C03-C08 が主担当であり、番号の一致に意味はない。
- 第3の名前空間 (混同注意): component の quality_gates.elegant_review.conditions と plan-findings.json の conditions に現れる C1-C4 は、上記いずれとも無関係な「エレガンス4条件」(C1=no_contradiction/矛盾なし・C2=no_missing/漏れなし・C3=consistent/整合性・C4=dependency_integrity/依存整合) を指す固有バケット名である。字面が goal-spec の C1-C4 と衝突するが別物 (詳細は phase-03-design-review.md ## ドメイン知識)。したがって evaluator の verdict=PASS は本 plan の内部4条件を認証するもので、goal-spec の要件 C1-C8 全ての充足を認証するものではない (C1-C8 の実充足は build 段階で trace する)。
- ハイブリッド契約: SubAgent (agents/*.md) は frontmatter=プラグイン YAML 形式 (name/description/tools/model/isolation 等) を維持し、本文のみ prompt-creator の7層構造 (l5-contract v2.0.0) に従う形式 (ユーザー確定事項)。skill 配下 prompts/*.md は純粋な7層 Markdown (frontmatter を持たない)。
- 内容 lint と配置 lint の違い: 既存 lint-prompt-placement.py は prompts/*.md の『配置 (どのディレクトリに置くか)』のみを検証する。C02 (lint-agent-prompt-content.py) は『本文が7層構造・固定手順禁止に準拠しているか』という直交する内容検証を担う。
- vendoring: C02 は prompt-creator の verify-completeness.py コアロジックを byte 一致で harness-creator 側に複製 (vendor) し、--check-vendor-parity で drift を検知する。先行事例は skill-intake の vendor/ + scripts/_vendor.py + scripts/validate-plugin-vendor.py。

## インフラ
- 実行環境: Python 3 標準ライブラリのみ (stdlib_only)。ネットワークアクセス無し (network:false)。
- cwd 前提: 全 script は repo root からの相対パス (plugins/ 始まり) で自己完結する (check-runtime-portability.py が強制)。
- 既存参照ツール: plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/verify-completeness.py (vendor 元)、plugins/harness-creator/skills/run-build-skill/scripts/lint-prompt-placement.py (直交する既存の配置 lint。run-build-skill skill 配下に格納されている)。

## 環境ポリシー
- 品質基準: 全 component の harness_coverage.min >= 80、quality_gates.evaluator.threshold >= 80 かつ high_max = 0。
- elegant_review は4条件 (C1-C4) 全 pass を必須とし、独立 approver によるレビューを推奨する (過去の plugin-dev-planner elegant-review でのカテゴリ錯誤事例からの教訓)。
- 保証要件は機械層 (lint/CI/build ゲート) で担保し、運用ルール・プロンプト任せに留めない (repo 既定方針の踏襲)。
- エスカレーション: 決定論ゲートが FAIL した場合は該当成果物を修正し再実行する。max_loops=5 (goal-spec.json) を超えて未解決の場合は orchestrator へ差し戻す。

## フェーズ一覧

build_status: realized (2026-07-05 build 完了。証跡=build-evidence.md / 状態正本=component-inventory.json 直下 build_status)

1. P01 — requirements (要件) / 実施済 (2026-07-05)
2. P02 — design (設計) / 実施済 (2026-07-05)
3. P03 — design-review (レビュー) / 実施済 (2026-07-05)
4. P04 — test-design (テスト) / 実施済 (2026-07-05)
5. P05 — implementation (実装) / 実施済 (2026-07-05)
6. P06 — test-run (テスト) / 実施済 (2026-07-05)
7. P07 — acceptance-criteria (判定) / 実施済 (2026-07-05)
8. P08 — refactoring (改善) / 実施済 (2026-07-05)
9. P09 — quality-assurance (品質) / 実施済 (2026-07-05)
10. P10 — final-review (レビュー) / 実施済 (2026-07-05)
11. P11 — evidence (検証) / 実施済 (2026-07-05)
12. P12 — documentation (文書) / 実施済 (2026-07-05)
13. P13 — release (完了) / 実施済 (2026-07-05)

component-inventory.json: plugin-plans/harness-prompt-conformance/component-inventory.json (9 components: C01=skill/run-prompt-creator-7layer 更新、C02=script/lint-agent-prompt-content.py 新設、C03-C08=sub-agent×6 是正、C09=skill/run-build-skill 更新)。

## 完了チェックリスト
- [x] C1: plugins/prompt-creator/ 配下に SubAgent 向けハイブリッド契約の新規 SSOT (references/subagent-hybrid-format.md) が存在し、既存の純粋7層形式 (seven-layer-format.md) との違いが明記されている (C01 が担う) — 証跡: build-evidence.md 受入確認 C1
- [x] C2: harness-creator 側に agents/*.md と skills/*/prompts/*.md の本文を fail-closed 検証する内容 lint が存在し、run-build-skill の生成フローに配線されている (C02/C09 が担う) — 証跡: build-evidence.md 受入確認 C2
- [x] C3: 既存6 SubAgent (elegant-* 5体 + run-build-skill-subagent) が全てハイブリッド契約に是正されている (C03-C08 が担う) — 証跡: build-evidence.md 受入確認 C3 (C02 --mode agent scanned=6 exit0)
- [x] C4: harness-creator の既存 skill 配下 prompts/*.md が l5-contract v2.0.0 に準拠していることが機械検証済みである (C02 の --mode prompt が担う) — 証跡: build-evidence.md 受入確認 C4 (C02 --mode prompt scanned=33 exit0)
- [x] C5: run-build-skill の agent/prompt 生成経路が prompt-creator を必ず経由するよう配線され、build_trace/provenance と受入例で経由しない単独生成の抜け道が塞がれている (C09 が担う) — 証跡: build-evidence.md 受入確認 C5 (test_e2e_bypass_trace_exits_1)
- [x] C6: 13 phase ファイル + index.md + component-inventory.json が生成され、決定論ゲート (11 script / 12 invocations = core 5 scripts/6 invocations + 拡張6本) が全 exit0 で通過する (本 plan 自体が担う) — 証跡: plan-findings.json G1-G10 + 拡張2ゲート全 exit0
- [x] C7: component-inventory.json の各 component の build_target が所有 plugin 別に正しく routing されている (C01=plugins/prompt-creator/、C02-C09=plugins/harness-creator/) — 証跡: build-evidence.md 受入確認 C7 (validate-plan-coverage --all)
- [x] C8: plugin-plans/plugin-dev-planner/・plugin-plans/skill-intake/・plugin-plans/harness-creator/ 配下のいずれのファイルも build_target / routes[].build_target / side_effect_targets として含まれていない — 証跡: build-evidence.md 受入確認 C8 (grep 0 件)
- [ ] 9 component 全てが design-review (P03)・quality-assurance (P09)・final-review (P10) を通過している — 決定論ゲート分は充足 (G1-G10)。LLM 層 (elegant_review 4条件/evaluator threshold 80) の build 時証跡は無く、elegant_review は本 elegant-review run-20260705-113702 で事後充足。evaluator score 記録は backlog (build-evidence.md 優先度付き backlog 節参照)

## 受入確認
build 後に組み上がった harness-creator が purpose を満たすかの trace: (1) C1 は subagent-hybrid-format.md の存在と内容 (frontmatter=plugin YAML/本文=7層) の lint 確認で trace する。(2) C2/C5 は C02 (--mode agent|prompt) が C09 の生成フローに fail-closed ゲートとして配線され、build_trace/provenance に source_contract_ref と prompt_creator_invocation が残り、prompt-creator 非経由の単独生成を試みる受入例がブロックされることをテストで trace する。(3) C3/C4 は既存6 SubAgent (C03-C08) と既存 skill prompts/*.md 全数に対する C02 の exit0 を repo 全体走査で trace する。(4) C6/C7/C8 は本 plan 自身の11 script / 12 invocations 全 exit0 と、component-inventory.json / handoff-run-plugin-dev-plan.json の build_target・side_effect_targets 監査 (plugins/ または .github/workflows/ 始まり・3つの除外 plan_dir 不在) で trace する。

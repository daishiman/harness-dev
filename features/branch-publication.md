---
graph_node_id: "feature-branch-publication"
artifact_kind: "feature"
artifact_subtypes: []
title: "元ブランチの全残存を新版を保持してPRへまとめる"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["branch-publication", "source-preservation", "existing-contracts"]
file_path: "features/branch-publication.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "generated", "source_digest": null, "source_path": null, "source_plugin": "dev-graph", "source_version": null}
created_at: "2026-11-01T21:51:01.228579Z"
updated_at: "2026-11-02T01:37:06.780592Z"
depends_on: []
related_nodes: []
resource_scope: []
purpose: "元rootの全1440差分そのものをcommit・統合し、mainの新版を保持した同一履歴をPRへ公開できるようにする。"
goal: "元1440件をsource commitと統合先で説明でき、元rootがclean、元/PRブランチが同一HEADで両push・同名追跡先を確認できる。"
scope_in: ["元1440差分の元ブランチ上commitと元HEAD先行11変更の統合", "最新mainと既存PRの元rootへの統合および競合解消", "raw eval-log1063件の元path保持と旧flyer165件のraw保存", "元rootのclean化・元/PR同一HEAD・両push・同名追跡先の確認"]
scope_out: ["新規HTTP・DB・認証基盤の追加", "新しい13フェーズ計画の生成・feature/taskの承認やpromotion", "現行flyer1.3.2を元1.3.1で上書きする変更"]
acceptance: ["元1440差分の元bytesがsource commitから辿れ、各統合先またはraw保存先を説明できる", "mainの先行修正を保ち旧flyer entrypointを現行1.3.2へ混在させない", "元rootの未commit/未追跡0件を最終commit後に確認する", "元ブランチとPRブランチの同一HEAD・両push・元の同名origin追跡先を確認する", "文書・feature・taskはdraft/pending・trackerなしで既存harness-86khの追跡を維持する"]
architecture_refs: ["arch-branch-publication"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 1.0
classification_reason: "declared by the C14 macro contract (run-dev-graph-decompose)"
classification_candidates: [{"artifact_kind": "feature", "candidate_path": "features/branch-publication.md", "confidence": 1.0}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-02T01:37:06.780592Z", "missing_sections": [], "status": "complete"}
---

# 目的

元rootの全1440差分そのものをcommit・統合し、mainの新版を保持した同一履歴をPRへ公開できるようにする。

## 到達状態

元1440件をsource commitと統合先で説明でき、元rootがclean、元/PRブランチが同一HEADで両push・同名追跡先を確認できる。

## スコープ

- スコープ内: 元1440差分の元ブランチ上commitと元HEAD先行11変更の統合
- スコープ内: 最新mainと既存PRの元rootへの統合および競合解消
- スコープ内: raw eval-log1063件の元path保持と旧flyer165件のraw保存
- スコープ内: 元rootのclean化・元/PR同一HEAD・両push・同名追跡先の確認
- スコープ外: 新規HTTP・DB・認証基盤の追加
- スコープ外: 新しい13フェーズ計画の生成・feature/taskの承認やpromotion
- スコープ外: 現行flyer1.3.2を元1.3.1で上書きする変更

## 受入

- [ ] 元1440差分の元bytesがsource commitから辿れ、各統合先またはraw保存先を説明できる
- [ ] mainの先行修正を保ち旧flyer entrypointを現行1.3.2へ混在させない
- [ ] 元rootの未commit/未追跡0件を最終commit後に確認する
- [ ] 元ブランチとPRブランチの同一HEAD・両push・元の同名origin追跡先を確認する
- [ ] 文書・feature・taskはdraft/pending・trackerなしで既存harness-86khの追跡を維持する

## アーキテクチャ参照

- `arch-branch-publication`

## 機能間依存

- 先行 feature なし (`depends_on` は空)

## Handoff

元rootでの全1440差分のcommitとmain/PR統合を、親のworktree-integration.jsonへ接続する。親が最終commit・root clean・元/PR同一HEAD・両push・同名追跡先を実測しPR #87へ渡す。本featureは整理用draft、実行追跡は既存harness-86khとし、新13計画・promotion・未取得承認・CI PASSを生成しない。

## 2026年11月2日のCI実走と再開条件

本featureの目的・受入・macro契約は変更しない。今回追加するものは実走証跡と再開時の未達条件だけであり、承認・promotionや13計画生成へ進めない。[CI実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json)へ引き継ぐ。

利用者のokにより、initの有効PASSを維持し、残り8対象のexhaustive実走が承認された。同時実行上限は2。今回のsource基準は848a2b2fで、実装・正本Skill・版の追加変更はない。CI結果は974 passed・8 failed・69 subtests passed、governanceはPASS。CI成功や8対象の全件完了、今回のcommit/push完了を示すものではない。

C14/decomposeとC02/nodeの新実走は主要観測を満たしたが、fresh独立評価はtask手順未達でFAIL、最終verdictはDEGRADED。decomposeはassistantによる実pathとbytes digestの提示順序および必要責務promptの事前読込、nodeは同じSkillによるupdate/feature-add再呼出しと提示順序が未達。自己申告PASSを受入へ流用しない。

C19/system-specとC05/renderはClaude週次利用上限（2026年11月6日17時、Asia/Tokyo解除予定）で停止し、Skill/tool呼出しは0件。C19/system-specとC05/renderは--blockedの正規finalizerとscoped reapで終了し、overall BLOCKED・goal_fit NOT_EVALUATEDとなった。全8runの残sessionは0。private全体は/private/tmp/harness-ci-full-20261102T010423-ci-fullへ非破壊moveし、10801file・9symlink・3365dirのtreeSHAは移動前後とも5dffd9e176643f20f547be5917aff95b8bce113db8c994ce19666430d805e0eeで一致した。4起動run（decompose・node・render・system-spec）のprivate-evidence-relocation.jsonに照合証跡を保持する。requirements・schedule・status・syncの4対象は未起動・未実走。追加課金、account/model切替や権限制約の回避は行わず、上限解除後も最大2の既存条件と予算を維持して再開する。

詳細な結果・証跡digest・C02/C11検証は受領書に記録する。全体の公開作業の成功条件と過去の履歴は維持する。

親が現行criteria9本を再検査し1 passed・8 failedを確認した（この文書担当による再実行ではない）。canonical criteria receiptは今回更新せず、古いPASSを現行の合格証拠として使わない。


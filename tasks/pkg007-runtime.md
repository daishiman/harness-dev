---
graph_node_id: "task-pkg007-runtime"
artifact_kind: "task"
artifact_subtypes: []
title: "PKG007修復を最終レビューし仕様反映してdraft公開する"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["pkg007", "mvp", "publication-review"]
file_path: "tasks/pkg007-runtime.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T03:37:44.999349Z"
updated_at: "2026-11-16T04:12:25.429540Z"
depends_on: ["spec-pkg007-runtime", "arch-pkg007-runtime"]
related_nodes: ["feature-pkg007-runtime", "doc-pkg007-runtime"]
resource_scope: []
purpose: null
goal: null
scope_in: []
scope_out: []
acceptance: []
architecture_refs: []
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 0.97
classification_reason: "harness-zb7qで承認されたPKG007の対象scope・配布依存・開発lint分離を記録するtask。"
classification_candidates: [{"artifact_kind": "task", "candidate_path": "tasks/pkg007-runtime.md", "confidence": 0.97}, {"artifact_kind": "document", "candidate_path": "docs/pkg007-runtime.md", "confidence": 0.03}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-16T04:12:25.429540Z", "missing_sections": [], "status": "complete"}
---

# 目的

harness-zb7qの変更だけを最終レビュー→仕様反映→対象限定commit/push→main向けdraft PRへ提出する。

## 背景

PKG007の人手規則と配布依存を修復し、ユーザーが簡単実行・短時間・低トークンを条件にscope修正とfeedback単独配布修復を承認した。原workspaceの他案件や既存差分を混ぜず公開する。

## 入力と前提条件

origin/mainをlocal mainへ取り込み公開branchへmerge済み。remoteにdevはなくdefaultはmain。公開worktreeはpkg007-final-review、branchはdevgraph/task-pkg007-runtime。原証拠と旧INCOMPLETEは保持する。

## 出力と成果物

今回製品差分、C02正規5文書と実writer receipt、system-spec/pkg007-runtimeの仕様影響受領書/品質ゲート、対象限定commitとdraft PR。

## 依存関係

spec-pkg007-runtimeとarch-pkg007-runtimeに依存する。tracker運用はBeads harness-zb7qにまとめ、新exact13 packageやconfirmed/pass昇格は行わない。

## 実装対象

check_pkg_007と対象テスト、APEの契約文書、catalog/36章の007、共通feedback runtimeとcanonical/vendor整合、必要な実行属性の修復。公開base由来の旧8scriptには+xだけを付与した。今回共通部品を含む23pluginだけをpatch採番し正規metadata生成・整合検査を実施した。installは行わない。 PR91 CI後追いでは命名、4参照資料のresource-map metadata、submit/validatorのPEP723等ヘッダーを正規生成元で補完し、renderer/registryを同期した。ヘッダー補完による通常runtime処理のASTは不変更。最新patch版はHC1.4.67/dev-graph0.1.35等、詳細はmetadata-final-gates.jsonのversions。

## Write scope と競合制約

製品移植は公開担当、正規docs/specs/architecture/features/tasks/system-spec/pkg007-runtimeと今回のgraph/receiptは文書担当。元workspaceは変更しない。他者差分を戻さず、stageは今回allowlistへ限定する。

## GitHub publication

devgraph/task-pkg007-runtimeからmain向けdraft PR。目的・変更・検証・仕様影響・harness-zb7q・task-pkg007-runtime・残課題を本文へ記載する。mainへ直接pushせず自動mergeしない。

## 実行手順

1. 製品差分を対象限定で移植し最終レビューする。
2. 公開base版C02で5文書をpreviewしrevision指定applyする。
3. 今回の最小ゲートと受領書SHA/秘密検査を実行する。
4. 対象allowlistをcommit/pushしdraft PRへ出す。
5. 結果をBeadsへ記録しmerge前doneへ昇格しない。

## 受入条件

metadata補修後の回帰522件・criteria5件・frontmatter209script違反0・vendor352一致・PKG23blocking0・release23・guard blocked0、および新規5nodeのschema/readinessと受領書SHA/秘密検査が成功する。索引は必要資料だけの選択に使い、通常runtime処理ASTと追加LLM/全repo走査0を維持する。実Notion/liveなしと既存coverage未達を残し、他案件や秘密をcommitへ含めない。

## 検証方法

対象回帰と配布整合の決定論検査だけを使う。graphは新規5nodeのschema/readinessを確認し、既存nodeを再評価しない。全30分析・LLM全体再評価・live再走・全coverageは追加しない。コマンド/実結果/ログはquality-gates.jsonを正とする。

## リスクとロールバック

PKG007 PASSを本文/他refsや実API成功まで保証するものと誤認しない。旧FAIL/INCOMPLETEを上書きしない。戻す場合は今回公開commitのrevertを用い、他者差分や元workspaceを消さない。

## Handoff

文書statusはdraft、評価pendingを保持する。今回23packageの版更新・整合検査を含む最小ゲートを満たしたdraft提出までを成果とする。実Notion API/live再走、install、merge/done認定は別の明示判断へ渡す。Beads更新と公開操作は公開担当が行う。 PR91 CI後追いの限定補修はmetadata-final-gates.jsonの実結果（522回帰、vendor352、最新23patch版）へ結ぶ。全LLM評価・liveを再走せず、quality/仕様影響受領書は公開担当が更新する。


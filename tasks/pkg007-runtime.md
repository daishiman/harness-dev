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
updated_at: "2026-11-16T04:28:59.559803Z"
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
implementation_readiness: {"checked_at": "2026-11-16T04:28:59.559803Z", "missing_sections": [], "status": "complete"}
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

check_pkg_007と対象テスト、APEの契約文書、catalog/36章の007、共通feedback runtimeとcanonical/vendor整合、必要な実行属性の修復。公開base由来の旧8scriptには+xだけを付与した。今回共通部品を含む23pluginだけをpatch採番し正規metadata生成・整合検査を実施した。installは行わない。 PR91 CI後追いでは命名、4参照資料のresource-map metadata、submit/validatorのPEP723等ヘッダーを正規生成元で補完し、renderer/registryを同期した。ヘッダー補完による通常runtime処理のASTは不変更。最新patch版はHC1.4.68/dev-graph0.1.36等、詳細はssot-final-gates.jsonのversions。 最終CIでは意図的同梱のSSOT判定を入力scope/台帳/通常file/非symlink/実byte一致に限定し、共通2資料の引用と工程名、B4/D1 pinを修復した。ヘッダーコメント差分はAST不変。その後、sys.dont_write_bytecode=Trueの1代入だけを追加してcache書込を抑止した。この1代入を除く通常業務処理のASTは同一で、通常の追加LLM呼出し・全repo走査0を維持する。 最新patch版はharness-creator 1.4.68、dev-graph 0.1.36、plugin-dev-planner 0.1.30。全23pluginを正規採番し、詳細は docs/pkg007-runtime/checks/ssot-final-gates.json と親の版一覧を参照する。installは行わない。

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

最新実検証は523回帰、SSOT unit55件、厳格SSOTのschema87件・Markdown188件、UBM文書4件・briefing文書1件、upstream7件、cache static1件が成功。vendor352一致・release23・guard blocked0も確認した。全体LLM評価・liveは再走しない。 criteria5・PKG007全23、新規5nodeのschema/readinessと受領書SHA/秘密検査も満たす。SSOTの意図的同梱判定は、正本とcopyがともに今回の入力scope内で、VENDORED_PAIRSに登録され、双方が通常fileで経路にsymlinkがなく、実bytesが一致する場合だけ適用する。未知copy・不一致・正本scope外・台帳未登録は従来どおり検出し、schemaや閾値は変更しない。 ヘッダーコメント差分はAST不変。その後、sys.dont_write_bytecode=Trueの1代入だけを追加してcache書込を抑止した。この1代入を除く通常業務処理のASTは同一で、通常の追加LLM呼出し・全repo走査0を維持する。 実Notion/live未実行と既存全体coverage未達を残し、原workspaceや他案件を変更しない。

## 検証方法

対象回帰と配布整合の決定論検査だけを使う。graphは新規5nodeのschema/readinessを確認し、既存nodeを再評価しない。全30分析・LLM全体再評価・live再走・全coverageは追加しない。コマンド/実結果/ログはquality-gates.jsonを正とする。

## リスクとロールバック

PKG007 PASSを本文/他refsや実API成功まで保証するものと誤認しない。旧FAIL/INCOMPLETEを上書きしない。戻す場合は今回公開commitのrevertを用い、他者差分や元workspaceを消さない。

## Handoff

文書はdraft/pendingを維持する。最終結果はssot-final-gates.jsonと親の品質台帳へ結び、今回の5docs更新はC02 r24→25の1回だけとする。最新patch版はharness-creator 1.4.68、dev-graph 0.1.36、plugin-dev-planner 0.1.30。全23pluginを正規採番し、詳細は docs/pkg007-runtime/checks/ssot-final-gates.json と親の版一覧を参照する。installは行わない。 ヘッダーAST不変と後続cache抑止1代入を区別し、通常業務処理同一を説明する。install・merge/done認定・追加LLM全体評価/liveは行わない。


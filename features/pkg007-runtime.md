---
graph_node_id: "feature-pkg007-runtime"
artifact_kind: "feature"
artifact_subtypes: []
title: "明示scriptの配布検査と共通feedback runtime"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["pkg007", "mvp", "publication-review"]
file_path: "features/pkg007-runtime.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T03:37:44.999349Z"
updated_at: "2026-11-16T04:12:25.429540Z"
depends_on: []
related_nodes: ["spec-pkg007-runtime", "doc-pkg007-runtime"]
resource_scope: []
purpose: "配布したpluginの実行参照を開発時に確かめ、共通feedbackをrepo配置へ依存せず利用できるようにする"
goal: "PKG007の対象と実行規則が一意になり、feedbackのruntime資産が配布内で解決し、通常起動の追加LLM/全repo走査が0である"
scope_in: ["明示script_refs＋既存root検査", "runtime4本＋anchor＋2schemaと必要refsの同梱", "repo lintのbuild役割移管", "22配布コピー同期", "今回共通部品を含む23pluginのpatch採番・正規metadata生成・整合検査", "仕様5文書・SHA受領書・対象限定draft PR", "PR91 CI指摘に限定した参照索引metadata・scriptヘッダー補完と正規同期"]
scope_out: ["HTTP API/DB/認証方式の変更", "本文/他refsの網羅検査", "全体coverage達成", "新exact13計画", "実Notion API/live再走", "install/自動merge"]
acceptance: ["PKG007全23pluginと公開treeの対象10ファイル522件が成功する", "feedbackstrict/vendor352一致と対象23pluginのrelease整合が成功する", "C02登録5nodeがdraft/pendingかつreadiness completeになる", "仕様受領書のSHAと実writer receiptが一致し秘密を含まない", "未実行のlive/Notionと既存coverage未達をdraft PRへ明記する"]
architecture_refs: ["arch-pkg007-runtime"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 1.0
classification_reason: "declared by the C14 macro contract (run-dev-graph-decompose)"
classification_candidates: [{"artifact_kind": "feature", "candidate_path": "features/pkg007-runtime.md", "confidence": 1.0}]
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

配布したpluginの実行参照を開発時に確かめ、共通feedbackをrepo配置へ依存せず利用できるようにする

## 到達状態

PKG007の対象と実行規則が一意になり、feedbackのruntime資産が配布内で解決し、通常起動の追加LLM/全repo走査が0である

## スコープ

- スコープ内: 明示script_refs＋既存root検査
- スコープ内: runtime4本＋anchor＋2schemaと必要refsの同梱
- スコープ内: repo lintのbuild役割移管
- スコープ内: 22配布コピー同期
- スコープ内: 今回共通部品を含む23pluginのpatch採番・正規metadata生成・整合検査
- スコープ内: 仕様5文書・SHA受領書・対象限定draft PR
- スコープ内: PR91 CI指摘に限定した参照索引metadata・scriptヘッダー補完と正規同期
- スコープ外: HTTP API/DB/認証方式の変更
- スコープ外: 本文/他refsの網羅検査
- スコープ外: 全体coverage達成
- スコープ外: 新exact13計画
- スコープ外: 実Notion API/live再走
- スコープ外: install/自動merge

## 受入

- [ ] PKG007全23pluginと公開treeの対象10ファイル522件が成功する
- [ ] feedbackstrict/vendor352一致と対象23pluginのrelease整合が成功する
- [ ] C02登録5nodeがdraft/pendingかつreadiness completeになる
- [ ] 仕様受領書のSHAと実writer receiptが一致し秘密を含まない
- [ ] 未実行のlive/Notionと既存coverage未達をdraft PRへ明記する

## アーキテクチャ参照

- `arch-pkg007-runtime`

## 機能間依存

- 先行 feature なし (`depends_on` は空)

## Handoff

今回の最終レビュー→仕様反映→対象限定commit/push/draft PRはharness-zb7qで追跡する。共通部品を含む23pluginのpatch採番とmetadata整合は今回実施し、installはしない。追加exact13やconfirmed/pass/doneへの昇格を伴わない。実ログと品質ゲートの判断はsystem-spec/pkg007-runtimeへ保存する。 PR91のCI後追いは索引metadata/ヘッダー補完に限定し、通常runtime処理のASTと追加LLM/全repo走査0の方針を維持する。metadata-final-gates.jsonの522回帰・vendor352・最新patch版を証拠とする。


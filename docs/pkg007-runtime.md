---
graph_node_id: "doc-pkg007-runtime"
artifact_kind: "document"
artifact_subtypes: []
title: "PKG007と共通feedbackの変更を理解する"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["pkg007", "mvp", "publication-review"]
file_path: "docs/pkg007-runtime.md"
template_id: "document"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T03:37:44.999349Z"
updated_at: "2026-11-16T04:12:25.429540Z"
depends_on: []
related_nodes: ["feature-pkg007-runtime", "spec-pkg007-runtime", "arch-pkg007-runtime", "task-pkg007-runtime"]
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
classification_reason: "harness-zb7qで承認されたPKG007の対象scope・配布依存・開発lint分離を記録するdocument。"
classification_candidates: [{"artifact_kind": "document", "candidate_path": "docs/pkg007-runtime.md", "confidence": 0.97}, {"artifact_kind": "task", "candidate_path": "tasks/pkg007-runtime.md", "confidence": 0.03}]
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

利用者が変わる点と変わらない点、開発担当が確認する根拠を一つの文書で把握できるようにする。

## 対象読者

中学生にも読める利用者向け説明と、pluginの保守・レビュー担当向け説明を併記する。設定値やtokenの提出を利用者へ求めない。

## 要約

持ち物表に書いた道具が、配布するかばんの中に本当に入っていて使えるかを開発時に確かめる。共通feedbackの道具も同じかばんにまとめ、利用するたびの検査やAIの呼出しは増やさない。

## 本文

中学生向け
script_refsは『使う道具の持ち物表』、pluginは配布するかばんです。これまでは表を人が読んで確かめる部分や、開発者の机にしかない道具がありました。今回、表に書いた道具がかばんの中にあり、使える状態かを機械で確認します。要望を送るfeedbackの道具も同梱します。使うたびに全部を検査する仕組みは増やしません。

専門向け
PKG007のscopeは明示script_refsとplugin root直下scripts。catalog/36章とcheck_pkg_007を正本にし、SKILL/R1の実行規則再定義を除去します。YAML型・重複key、skill→pluginの先勝ち、realpath containment、実体単位集約、shebang/+xを検査します。feedbackはruntime4本＋既存anchor＋2schemaをskill内へ閉じ、同階層importとmanifest祖先rootを使います。repo lintはbuild_validationへ移し、IN1/IN2と属性要件を維持します。

CI後追いの補完（中学生向け）
4つの説明資料に目次を付け、必要なページだけを開けるようにしました。道具の説明ラベルもそろえましたが、道具が実際に行う処理は変えていません。

CI後追いの補完（専門向け）
resource-map.yamlに4資料のtopic/read_whenを宣言し正規rendererとregistryで同期しました。PEP723等のヘッダー補完は通常runtime処理のASTを変えません。通常起動に全資料読込や追加LLM評価を加えず、vendorは352組のbyte一致を検証しました。

## 決定事項

通常起動の追加LLM/全repo走査は0。本文・他refsは今回007の対象外。runtimeと開発lintを分離する。新しいAPI/DB/認証方式は追加しない。公開5nodeはdraft/pendingを維持する。

## 運用・更新方法

canonicalへ変更し既存配布機構でコピーを同期する。配布前に最小ゲートとbyte一致を確認する。Notion設定やtokenは公開せず、通常利用時に同梱資料を全読込しない。 4資料の選択はresource-map.yamlのtopic/read_whenを使い、該当する資料だけを必要時に読む。metadata補修は正規生成元へ反映し、renderer/registryの同期とvendor352一致で確認する。

## 関連資料

specs/pkg007-runtime.md、architecture/pkg007-runtime.md、features/pkg007-runtime.md、tasks/pkg007-runtime.md、system-spec/pkg007-runtime/spec-impact-receipt.json、同quality-gates.json。実writer receiptは仕様影響受領書から辿る。

## 変更履歴

2026-11-16: harness-zb7qのユーザー承認scopeをC02で正規5文書へ反映。公開treeの521件と対象23packageの版更新を追記した。初期dirty treeの無関係2testは公開対象外。main向けdraft PRの説明を記載。
2026-11-16 PR91 CI後追い: 命名・参照索引metadata・ヘッダーを補完し正規同期した。runtime AST不変、522回帰・5criteria・vendor352・最新patch版を今回の実結果へ更新。

## PR用要約

問題: 明示script参照の検査と共通feedbackに、人手判定とrepo配置前提が残っていた。PR91のCIで命名・索引metadata・scriptヘッダーの不足が見つかった。
変更: 007を機械正本へ集約し、feedback runtimeを同梱、repo lintを開発役割へ分離。CI後追いでは4資料の索引metadata、ヘッダーと正規renderer/registryを補完した。ヘッダー補完で通常runtime処理のASTは変えず、通常起動に追加LLM/全repo走査を入れない。
最新検証: 回帰522件、criteria5件、frontmatter209script違反0、vendor352一致、23package blocking0、release23とguard blocked0を確認。前回521件と今回CI後追いの結果を区別し、原workspaceの無関係2testは持ち込まない。実ログは docs/pkg007-runtime/checks/metadata-final-gates.json を参照。
最新patch版: harness-creator 1.4.67、dev-graph 0.1.35。他23pluginの版は同JSONのversionsを正とする。installは行っていない。
仕様影響: 対象scope・配布依存・開発lint境界と必要資料の選択を反映。API/DB/認証方式は影響なし。
追跡: Beads harness-zb7q、task-pkg007-runtime、devgraph/task-pkg007-runtime→main draft PR91。

## 残課題

実Notion API投入とlive再走は行っていない。既存全体coverageは未達のままであり、今回の最小ゲート成功を全体品質達成へ読み替えない。対象23pluginのpatch採番・正規metadata生成・release整合は実施したが、installとマージ後の運用受入れは行っていない。


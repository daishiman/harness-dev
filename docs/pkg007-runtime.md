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
updated_at: "2026-11-16T04:28:14.437839Z"
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
implementation_readiness: {"checked_at": "2026-11-16T04:28:14.437839Z", "missing_sections": [], "status": "complete"}
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

追加CI修復（中学生向け）
同じ説明書を配布のかばんへ入れた場合だけ、台帳と中身を照合して意図したコピーと認めます。知らないコピーや中身が違うものは見逃しません。資料の参照先と工程名を読みやすくし、不要なcacheファイルを書かない設定を1行追加しました。業務の動きは同じです。

追加CI修復（専門向け）
SSOTの意図的同梱判定は、正本とcopyがともに今回の入力scope内で、VENDORED_PAIRSに登録され、双方が通常fileで経路にsymlinkがなく、実bytesが一致する場合だけ適用する。未知copy・不一致・正本scope外・台帳未登録は従来どおり検出し、schemaや閾値は変更しない。 goal-seek資料の見出しはharness-creator正本のowner-qualified URLへ結び、runbookの固有工程番号は自然な工程名へ置き換えて説明を維持しました。B4はmanifest祖先解決とcache抑止の差分、D1は意味不変更の参照明確化を再監査してpinを追従しています。ヘッダーコメント差分はAST不変。その後、sys.dont_write_bytecode=Trueの1代入だけを追加してcache書込を抑止した。この1代入を除く通常業務処理のASTは同一で、通常の追加LLM呼出し・全repo走査0を維持する。

## 決定事項

通常起動の追加LLM/全repo走査は0。本文・他refsは今回007の対象外。runtimeと開発lintを分離する。新しいAPI/DB/認証方式は追加しない。公開5nodeはdraft/pendingを維持する。

## 運用・更新方法

canonicalへ変更し既存配布機構でコピーを同期する。配布前に最小ゲートとbyte一致を確認する。Notion設定やtokenは公開せず、通常利用時に同梱資料を全読込しない。 4資料の選択はresource-map.yamlのtopic/read_whenを使い、該当する資料だけを必要時に読む。metadata補修は正規生成元へ反映し、renderer/registryの同期とvendor352一致で確認する。

## 関連資料

specs/pkg007-runtime.md、architecture/pkg007-runtime.md、features/pkg007-runtime.md、tasks/pkg007-runtime.md、system-spec/pkg007-runtime/spec-impact-receipt.json、同quality-gates.json。実writer receiptは仕様影響受領書から辿る。

## 変更履歴

2026-11-16: harness-zb7qのユーザー承認scopeをC02で正規5文書へ反映。公開treeの521件と対象23packageの版更新を追記した。初期dirty treeの無関係2testは公開対象外。main向けdraft PRの説明を記載。
2026-11-16 PR91 CI後追い: 命名・参照索引metadata・ヘッダーを補完し正規同期した。runtime AST不変、522回帰・5criteria・vendor352・最新patch版を今回の実結果へ更新。
2026-11-16 最終CI追補: 意図的同梱の厳密なSSOT境界、共通2資料の引用明確化、B4/D1再監査とpin、cache抑止1代入を反映。最新523回帰・SSOT55・厳格schema87/Markdown188・vendor352とHC1.4.68/dev-graph0.1.36/planner0.1.30へ更新。

## PR用要約

問題: 明示script参照の検査とfeedbackに人手判定・repo配置前提が残り、PR91 CIで意図的同梱docのSSOT誤検知、共通資料の引用とpinのdriftが露出した。
変更: PKG007を機械正本へ集約しruntime同梱と開発lint分離を実施。SSOTは入力scope内の登録済み通常file・非symlink・実byte一致の場合だけ意図的copyと区別し、未知/不一致は検出を維持する。共通2資料の参照と工程名を明確化しB4/D1を再監査した。
挙動境界: ヘッダーコメント差分はAST不変。その後、sys.dont_write_bytecode=Trueの1代入だけを追加してcache書込を抑止した。この1代入を除く通常業務処理のASTは同一で、通常の追加LLM呼出し・全repo走査0を維持する。
最新検証: 最新実検証は523回帰、SSOT unit55件、厳格SSOTのschema87件・Markdown188件、UBM文書4件・briefing文書1件、upstream7件、cache static1件が成功。vendor352一致・release23・guard blocked0も確認した。全体LLM評価・liveは再走しない。 criteria5件とPKG007全23も成功。根拠は docs/pkg007-runtime/checks/ssot-final-gates.json。
版更新: 最新patch版はharness-creator 1.4.68、dev-graph 0.1.36、plugin-dev-planner 0.1.30。全23pluginを正規採番し、詳細は docs/pkg007-runtime/checks/ssot-final-gates.json と親の版一覧を参照する。installは行わない。
仕様影響: 対象scope・配布依存・開発lint・必要資料選択・SSOTの意図的copy境界を反映。API/DB/認証方式は影響なし。
追跡: Beads harness-zb7q、task-pkg007-runtime、devgraph/task-pkg007-runtime→main draft PR91。

## 残課題

実Notion API投入とlive再走は行っていない。既存全体coverageは未達のままであり、今回の最小ゲート成功を全体品質達成へ読み替えない。対象23pluginのpatch採番・正規metadata生成・release整合は実施したが、installとマージ後の運用受入れは行っていない。


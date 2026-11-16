---
graph_node_id: "spec-pkg007-runtime"
artifact_kind: "specification"
artifact_subtypes: []
title: "明示script参照の配布検査と共通feedback単独配布の仕様"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["pkg007", "mvp", "publication-review"]
file_path: "specs/pkg007-runtime.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T03:37:44.999349Z"
updated_at: "2026-11-16T04:28:59.559803Z"
depends_on: []
related_nodes: ["arch-pkg007-runtime", "feature-pkg007-runtime"]
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
classification_reason: "harness-zb7qで承認されたPKG007の対象scope・配布依存・開発lint分離を記録するspecification。"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/pkg007-runtime.md", "confidence": 0.97}, {"artifact_kind": "document", "candidate_path": "docs/pkg007-runtime.md", "confidence": 0.03}]
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

# 目的と成功状態

宣言した実行scriptがplugin内で実在し実行属性を持つことを開発時に確認し、共通run-skill-feedbackがrepo cloneなしでも必要なruntime資産を解決できる状態にする。通常起動へ追加のLLM評価やrepo全体走査を入れない。

## スコープ

対象はPKG007の明示script_refsと従来のplugin root直下scripts、共通feedbackの実行時依存閉包、配布コピー同期、repo用lintの開発役割への分離、対応する仕様と最小ゲート。今回共通部品を含む23pluginはpatch採番と正規metadata生成・整合検査を行う。本文や他の*_refs、全体coverageの達成、新exact13計画、install、自動mergeは対象外。

## 用語と主体

script_refsはSKILL.md frontmatterの明示pathリスト。owner pluginはmanifestを持つ祖先。canonicalは唯一の編集元、vendorはbyte一致の配布コピー。開発担当が配布検査し、利用者は必要な項目だけを確認してfeedbackを投入する。

## ユースケースとユーザーフロー

開発担当が変更後のPKG007を実行して欠落や属性違反を直す。配布時はcanonical runtimeを既存コピーへ同期する。利用者はhostの登録済み候補から対象を絞り、引数を必要時にdry-runし、承認wrapper経由で投入する。通常の投入で全pluginを走査しない。

## 機能要件

FR1: catalogと36章で対象を明示script_refsとroot scriptsへ揃え、実行規則はcheck_pkg_007を正本とする。
FR2: YAML型・重複key・候補の先勝ち・realpath containment・shebang/+x・実体単位集約を機械検証する。
FR3: 4追加runtimeと既存anchor、2schema、必要時参照文書をskill内へ閉じる。
FR4: notion_configはmanifest祖先からowner plugin rootを解決し、明示config優先を維持する。
FR5: repo用lintはmanifestのbuild_validationでIN1/IN2と実行属性要件を保持し、runtimeへvendorしない。
FR6: references/resource-map.yamlへ4資料のtopic/read_whenを宣言し、必要な資料だけを選択して読む。
FR7: CI指摘に限定して索引metadataとPEP723等のscriptヘッダーを補完する。ヘッダー補完による通常runtime処理のASTは変更しない。
FR8: SSOTの意図的同梱判定は、正本とcopyがともに今回の入力scope内で、VENDORED_PAIRSに登録され、双方が通常fileで経路にsymlinkがなく、実bytesが一致する場合だけ適用する。未知copy・不一致・正本scope外・台帳未登録は従来どおり検出し、schemaや閾値は変更しない。
FR9: ヘッダーコメント差分はAST不変。その後、sys.dont_write_bytecode=Trueの1代入だけを追加してcache書込を抑止した。この1代入を除く通常業務処理のASTは同一で、通常の追加LLM呼出し・全repo走査0を維持する。
FR10: 共通資料のHC固有参照は正本ownerを明示し、工程を固有コード番号だけで説明しない。B4/D1の引用差分を再監査してupstream pinを追従する。

## 非機能要件

通常起動の追加LLM呼出し0、追加repo全走査0。検証は変更範囲の決定論的な最小ゲートを使う。PyYAML依存はPKG007 validatorに明示し、通常feedback投入へ追加しない。tokenをargv・ログ・公開成果物へ載せない。

## UI・状態遷移

PKG007はexit0=pass、exit1=findingあり、exit2=入力・I/O・依存エラー。feedbackは引数dry-run、承認preview、承認、実行の既存状態を保持する。guardを解決できなければ外部mutation前に停止する。

## ビジネスルールと検証

候補はskill directory→plugin rootの順で最初の実在候補を採用し、不正な第一候補を後方候補で救済しない。PKG009の外部参照例外はPKG007の配布内解決を免除しない。明示script_refsのhelperにもshebang/+xを求める。rootの未参照import-only helperは既存AST判定を維持する。

## API契約

HTTP APIや公開サービスAPIの追加・変更はない。既存Notion APIの投入処理とguard APIは維持し、ローカルPython scriptの配置・参照・検査契約だけを更新する。

## データモデル

DB schemaの変更はない。Notionの2schemaは既存正本のbyte一致コピー。workflow-manifestのbuild_validationにrepo lintのrole/scope/path/argv/criteria/attributesを宣言する。findings schemaは変更しない。

## 認証・認可

認証方式・token解決順・承認wrapperは変更しない。config pathは明示NOTION_CONFIG_PATHを優先し、owner pluginのmanifest祖先をfallbackの基点とする。秘密値や実tenant設定を配布しない。

## エラー・例外・回復

YAML宣言違反、欠落・外部解決・属性違反はfindingへ記録する。依存不足や読取不能はexit2で止める。明示config不在時は別configへ黙ってfallbackしない。guard不在時はinstall案内だけを返し外部操作しない。

## イベント・非同期処理

新規hook、常駐process、queue、非同期処理は追加しない。package検査とrepo lintは開発・配布時にだけ実行する。

## 可観測性

findingはlocation/evidence/severityと参照元を持つ。原review・旧INCOMPLETEを保持し、今回の独立判定・最小ゲート・仕様影響判断・writer receipt・SHAを保存する。

## 互換性・移行・リリース

repo正本submitと配布版の同階層importを両対応する。canonicalと既存22コピーを既存配布機構で同期した。今回共通部品を含む23pluginだけをbuild-plugin-release.pyでpatch採番し、正規metadataを生成した（harness-creator 1.4.68、dev-graph 0.1.36等）。整合検査を実行しinstallはしない。公開はtask branchからmain向けdraft PRで、merge・done昇格は別判断とする。 PR91のCI後追いでは索引metadataとヘッダーを正規生成元へ反映し、既存同期経路で配布版へ展開した。全23pluginの最新patch版一覧は docs/pkg007-runtime/checks/ssot-final-gates.json の versions を正とする。 最新patch版はharness-creator 1.4.68、dev-graph 0.1.36、plugin-dev-planner 0.1.30。全23pluginを正規採番し、詳細は docs/pkg007-runtime/checks/ssot-final-gates.json と親の版一覧を参照する。installは行わない。

## テストと受入条件

最新実検証は523回帰、SSOT unit55件、厳格SSOTのschema87件・Markdown188件、UBM文書4件・briefing文書1件、upstream7件、cache static1件が成功。vendor352一致・release23・guard blocked0も確認した。全体LLM評価・liveは再走しない。 PKG007全23とcriteria5件を含む今回の最小ゲートは docs/pkg007-runtime/checks/ssot-final-gates.json を正とする。原workspaceの無関係2testは引き続き持ち込まない。新規5nodeのschema/readinessと受領書SHA/秘密検査を別途確認し、実Notion/liveなしと全体coverage未達を残す。

## 未決事項

実Notion API投入とlive再走は行っていない。既存全体coverageの未達は残る。今回23pluginのpatch採番・metadata生成と整合検査は行ったが、installやマージ後の運用受入れを認定するものではない。


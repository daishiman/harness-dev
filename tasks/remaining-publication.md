---
graph_node_id: "task-remaining-publication"
artifact_kind: "task"
artifact_subtypes: []
title: "元ブランチ全残存を最終統合し仕様反映して追加PRへ公開する"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["remaining-publication", "mvp", "source-integration"]
file_path: "tasks/remaining-publication.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T05:00:55.517262Z"
updated_at: "2026-11-16T05:28:08.821327Z"
depends_on: ["spec-remaining-publication", "arch-remaining-publication"]
related_nodes: ["feature-remaining-publication", "doc-remaining-publication"]
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
classification_reason: "harness-esj6で承認された元ブランチ残存の公開統合を記録するtask。"
classification_candidates: [{"artifact_kind": "task", "candidate_path": "tasks/remaining-publication.md", "confidence": 0.97}, {"artifact_kind": "document", "candidate_path": "docs/remaining-publication.md", "confidence": 0.03}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-16T05:28:08.821327Z", "missing_sections": [], "status": "complete"}
---

# 目的

harness-esj6で承認された元ブランチ全残存だけを公開統合し、最終review→仕様反映→対象限定commit/push/draft PR→元root履歴収束まで追跡する。

## 背景

原rootにはPR91公開済み差分と未公開の改善、履歴、privacy対象、runtime/tempが混在する。最新mainを基準に新機能hunkだけを取り込み、既存PKG007を戻さずに全残存の行き先を確定する必要がある。

## 入力と前提条件

初期gsの2284status、正常commitされたsource snapshot、最新main、公開統合worktree、既存Beadsと原検証履歴を入力とする。公開branchはdevgraph/ と tasks/remaining-publication.md の frontmatter.graph_node_id を連結したbranch。private raw locatorを公開文書へ書かない。

## 出力と成果物

統合済み7機能群、理由付き全status公開manifest、privacy3派生物と元SHAの対応、旧verdict履歴、正規5文書/graph/実writer receipt、親quality/impact受領書、追加draft PRと元rootの正常な履歴。

## 依存関係

spec-remaining-publicationとarch-remaining-publicationに依存する。harness-s7d、harness-r44等の既存追跡とharness-esj6の公開完了範囲を分け、既存openを公開だけで閉じない。

## 実装対象

YAML cache: 正規builderがcacheと索引を作り、節・見出しの必要範囲だけをReadする。hash/取得日時の不一致は停止し、ネット取得なしのreindexを提供する。
run model budget: convergence-policyを正本にrun_id全体のAI起動予算を計算し、gate/launcher/plannerが起動前に同じ台帳へ予約する。再試行の重複課金と並行予約の超過を防ぎ、枯渇時はfail-closedで起動しない。
knowledge-loop: 既存schema/lint/engineと参照文書の整合を取り、4資料、consult_at、検索・記録CLIとruntime境界を正しく案内する。新しい外部知能engineを導入する変更とは区別する。
artifact delivery: state-machineの各所の写しをglobal policy参照へ寄せ、現状で試す/診断するの選択を先に、改善深度を診断後の1回へ整理する。通常のplugin追加や起動に全repo走査・LLM評価を要求しない。
runtime profiles: 構築時DAGと実行時DAGを分け、最小十分なinlineを既定にする。独立contextや実依存がある場合だけfork/task-graphを使い、同pluginの正本参照・別pluginへの実体配布・配線なし理由・冗長path宣言を検査する。
system-dev-planner: CLI/in-processで同じrealpath境界を要求し、壊れたsymlink、UTF-8/IO、policy違反、RFC3339、世代markerの扱いを明確化する。既存exact13契約を新しい計画生成なしで維持する。
evidence and host work: hashに束縛した検査再利用、traceとbriefの一致、検証予算、C1-C4レポート、transcript計測、runtime evidence ledgerを整える。install/enable/trust/new-session等のhost担当作業は保留証拠を残し、未実行をPASSへ置き換えない。
最新mainのPR91公開済みPKG007・配布closure・owner-qualified資料・既存25node/receiptを維持する。sourceの古いfileを丸ごと上書きせず、未公開の新機能hunkと必要な履歴だけを統合する。

## Write scope と競合制約

公開統合treeで各担当の所有範囲だけを修復し、他者差分を戻さない。文書担当は今回5文書とgraph/入力/preview/result/実receiptのみ。quality/impact/manifestと元rootの履歴操作は公開担当が行う。元rootは正常commit前に上書きや破棄をしない。

## GitHub publication

devgraph/ と tasks/remaining-publication.md の frontmatter.graph_node_id を連結したbranchからmain向け追加draft PRへ提出する。PR本文に目的・7群の変更・実ゲート根拠・仕様影響・2284status分類・privacy方針・harness-esj6/task node・残課題・元root履歴収束を含める。secret/private raw locatorを載せず、mainへ直接push/自動mergeしない。

## 実行手順

1. 初期statusとsource snapshotを固定し、mainとの差を5分類の理由付きmanifestへ対応させる。
2. 各担当が3way競合を解消し、公開済みPKG007と他者差分を保つ。
3. privacy3派生物/旧SHA/非公開tempを分離し、今回5文書をC02 addのpreview→revision指定applyで1回登録する。
4. 親quality台帳が指す最小ゲート、全status対応、SHA/secret検査を確認する。
5. 対象限定commit/pushとdraft PRを作成し、元rootも正常commit後に公開branchの履歴へそろえる。
6. 結果をBeadsへ記録し、manual completionの判断前にdoneへ昇格しない。

## 受入条件

初期gsの2284status項目すべてに公開対象manifest上の対応を持たせ、main公開済み/新規統合/履歴保存/秘密匿名化/非公開tempを理由付きで分類する。公開できない原locatorはopaque IDまたはSHAで照合し、分類漏れを許さない。 公開対象3ファイルは秘密/個人情報を匿名化した派生物として保存し、元bytesと元SHAは非公開保管する。公開文書へprivate raw locatorを書かない。旧FAIL/INCOMPLETEと旧verdictのreviewed SHAを保持し、現在の成功へ付け替えない。 親quality台帳の最小ゲート成功、既存25node不変・今回5node draft/pending/readiness complete、元root正常commitと公開branch履歴整合を満たす。未確定test件数/版はここへ固定しない。

## 検証方法

最小ゲートのコマンド・実結果・test件数・対象版は親が管理するsystem-spec/remaining-publication/quality-gates.jsonを正とする。全体LLM再評価、live再走、全coverage達成認定は追加しない。 公開manifestで2284項目の欠落・重複・理由・対応先を確認し、privacy派生物/旧verdictと証拠SHAを検証する。C02は新規5nodeのschema/readinessを検査し、既存25nodeの内容不変を比較する。原runtime承認記録や実secretをテスト入力へ混ぜない。

CIのplugin-testsは過去の実走受領commit本文の照合を前提とするため、checkoutをfetch-depth: 0とfilter: blob:noneにして履歴を保持しblob本文は必要時に取得する。過去commitの未取得はcheckout環境の不足として診断し、証跡不在や挙動FAILと混同しない。証跡・validator・閾値を緩めず、修復後の対象CI成功を確認してから公開の品質ゲート結果へ記録する。

## リスクとロールバック

全残存という言葉で秘密や旧失敗まで現在の製品へ混ぜない。分類漏れやmain退行は公開を停止する。公開前の復旧は固定snapshotからの対象限定復旧、公開後は今回commitのrevertを使い、原成果・他者差分・旧証拠を削除しない。

## Handoff

completion policyはmanual。5nodeはdraft/pendingであり、draft PR作成や台帳登録だけでconfirmed/pass/doneへ昇格しない。品質受入れ・元root履歴収束・残課題を公開担当へ渡し、既存未達やhost担当保留を成功と誤認させない。


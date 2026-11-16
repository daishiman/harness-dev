---
graph_node_id: "doc-remaining-publication"
artifact_kind: "document"
artifact_subtypes: []
title: "残っていた改善を安全に公開するための案内"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["remaining-publication", "mvp", "source-integration"]
file_path: "docs/remaining-publication.md"
template_id: "document"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T05:00:55.517262Z"
updated_at: "2026-11-16T05:00:55.517262Z"
depends_on: []
related_nodes: ["spec-remaining-publication", "arch-remaining-publication", "feature-remaining-publication", "task-remaining-publication"]
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
classification_reason: "harness-esj6で承認された元ブランチ残存の公開統合を記録するdocument。"
classification_candidates: [{"artifact_kind": "document", "candidate_path": "docs/remaining-publication.md", "confidence": 0.97}, {"artifact_kind": "task", "candidate_path": "tasks/remaining-publication.md", "confidence": 0.03}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-16T05:00:55.517262Z", "missing_sections": [], "status": "complete"}
---

# 目的

何を追加公開するのか、何を守るのか、まだ完了していないことは何かを利用者と専門担当が理解できるようにする。

## 対象読者

普段pluginを使う利用者、元ブランチの担当者、公開PRのreviewer。専門知識なしで読める説明と正本/検証境界を併記する。

## 要約

机に残っていた改善を全部持ち物表で点検し、既に配った物、新しく配る物、記録として残す物、秘密なので配らない物に分ける。新しい改善だけを今の公開版へ合わせ、元の机もきちんと履歴が残る状態へそろえる。

## 本文

中学生向け
大きな説明書を毎回全部読む代わりに、目次から必要なページだけを開きます。AIを呼ぶ回数には共通の上限を設け、使い切ったら止まります。使う場面に合う小さな仕組みを選び、実物を見せてから追加の診断を選べます。端末側でしかできない操作は、まだ終わっていないと正直に記録します。秘密は公開用のコピーで伏せ、元の記録を書き換えません。

専門向け
YAML cache: 正規builderがcacheと索引を作り、節・見出しの必要範囲だけをReadする。hash/取得日時の不一致は停止し、ネット取得なしのreindexを提供する。
run model budget: convergence-policyを正本にrun_id全体のAI起動予算を計算し、gate/launcher/plannerが起動前に同じ台帳へ予約する。再試行の重複課金と並行予約の超過を防ぎ、枯渇時はfail-closedで起動しない。
knowledge-loop: 既存schema/lint/engineと参照文書の整合を取り、4資料、consult_at、検索・記録CLIとruntime境界を正しく案内する。新しい外部知能engineを導入する変更とは区別する。
artifact delivery: state-machineの各所の写しをglobal policy参照へ寄せ、現状で試す/診断するの選択を先に、改善深度を診断後の1回へ整理する。通常のplugin追加や起動に全repo走査・LLM評価を要求しない。
runtime profiles: 構築時DAGと実行時DAGを分け、最小十分なinlineを既定にする。独立contextや実依存がある場合だけfork/task-graphを使い、同pluginの正本参照・別pluginへの実体配布・配線なし理由・冗長path宣言を検査する。
system-dev-planner: CLI/in-processで同じrealpath境界を要求し、壊れたsymlink、UTF-8/IO、policy違反、RFC3339、世代markerの扱いを明確化する。既存exact13契約を新しい計画生成なしで維持する。
evidence and host work: hashに束縛した検査再利用、traceとbriefの一致、検証予算、C1-C4レポート、transcript計測、runtime evidence ledgerを整える。install/enable/trust/new-session等のhost担当作業は保留証拠を残し、未実行をPASSへ置き換えない。
最新mainのPR91公開済みPKG007・配布closure・owner-qualified資料・既存25node/receiptを維持する。sourceの古いfileを丸ごと上書きせず、未公開の新機能hunkと必要な履歴だけを統合する。
公開対象3ファイルは秘密/個人情報を匿名化した派生物として保存し、元bytesと元SHAは非公開保管する。公開文書へprivate raw locatorを書かない。旧FAIL/INCOMPLETEと旧verdictのreviewed SHAを保持し、現在の成功へ付け替えない。

## 決定事項

今回公開だけをharness-esj6で追跡し、既存PKG007仕様は維持する。全statusを5分類の理由付きmanifestへ結ぶ。通常plugin追加/起動へ全repo走査やLLMを追加しない。元rootは正常commitの後で公開branchへ履歴収束させる。5nodeとcompletionはdraft/pending/manualを維持する。

## 運用・更新方法

実装・正本・参照文書を同じ変更で整合させ、cache/indexやvendorは正規生成経路で同期する。最終件数・版・実ゲートは親quality台帳へ一元化する。既存open follow-upやhost保留を公開の成功と区別して引き継ぐ。

## 関連資料

specs/remaining-publication.md、architecture/remaining-publication.md、features/remaining-publication.md、tasks/remaining-publication.md、system-spec/remaining-publication/quality-gates.json。全status対応・privacy派生物・旧SHAの詳細は同品質台帳が指す公開manifestと受領書を辿る。非公開原locatorは記載しない。

## 変更履歴

2026-11-16: harness-esj6の元ブランチ全残存公開に対応する正規5文書をC02 addで新規登録。既存PR91のPKG007文書を別scopeとして維持。

## PR用要約

問題: 元ブランチに実装済みの改善・仕様・検証成果が残り、公開済みmainとの差やprivate runtimeが混在していた。
変更: YAML必要節Read、run予算fail-closed、knowledge文書整合、global artifact policy参照、runtime最小profile、SDP境界、証拠再利用/host担当保留の7群を統合する。
保全: 初期2284statusを理由付きmanifestへ対応させ、PR91修復・privacy3派生物・旧verdict SHA・未達の区別を保持する。
検証: 親quality-gatesの実コマンド/結果を正とし、未確定の件数や版を固定しない。全LLM評価や実API/liveを追加しない。
追跡: Beads harness-esj6、tasks/remaining-publication.md の frontmatter.graph_node_id、devgraph/ と tasks/remaining-publication.md の frontmatter.graph_node_id を連結したbranch→main draft。元rootは正常commit後に公開branchの履歴へそろえる。

## 残課題

既存全体coverage、既存open follow-up、実API/live/host操作の未実行は残す。公開3派生物は原本ではなく、旧verdictのPASSを現在版へ付け替えない。全statusの分類と公開台帳に欠落があれば公開を止め、未完了を捏造しない。


---
graph_node_id: "spec-branch-publication"
artifact_kind: "specification"
artifact_subtypes: []
title: "元ブランチ全残存の統合と保存の仕様"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["branch-publication", "source-preservation", "existing-contracts"]
file_path: "specs/branch-publication.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-01T21:51:01.228579Z"
updated_at: "2026-11-01T21:51:01.228579Z"
depends_on: []
related_nodes: ["task-branch-remaining-publication"]
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
classification_confidence: 0.99
classification_reason: "元ブランチ全残存の統合を、既存責務契約への参照と実パスの対応で記録する正規specification。"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/branch-publication.md", "confidence": 0.99}, {"artifact_kind": "document", "candidate_path": "docs/branch-publication.md", "confidence": 0.01}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-01T21:51:01.228579Z", "missing_sections": [], "status": "complete"}
---

# 目的と成功状態

元ブランチの全残存を最新mainと整合させ、意味差分・元版・証跡の対応先をPR #87で追跡できるようにする。成功は未対応の元差分0件であり、Gitの作業状態がcleanなだけでは代替しない。対象台帳は [manifest](../docs/branch-publication/manifest.json)、作業契約は [統合タスク](../tasks/branch-remaining-publication.md)。

## スコープ

対象は元HEAD 8c1eb6c8の先行11変更と、元worktreeの1440 status entries。dev-graph、UBM、harness-creator、governance lint、release writer、SBBの未公開実装を統合し、flyer旧版・素材・検証・計画は元版保存で対応する。guideの既存仕様は [既存索引](../system-spec/guide-doc-generator/README.md) を参照し変更しない。新規HTTP API・DB・認証基盤・13フェーズ計画の生成は対象外。

## 用語と主体

C02はgraphと正規文書の単一writer、C14はmacro feature契約の宣言者、C28はBeads投影、C16はready推薦を所有する。既存Beads harness-86khのscope拡張を実行追跡とし、新しいdraft taskや本資料を起票済み・承認済みとは扱わない。

## ユースケースとユーザーフロー

元差分を棚卸しし、main既反映・今回統合・元版保存・一時状態の扱いへ分類する。mainの新しい実装を保持しながら3-way統合し、対象別の最小検証と仕様影響を記録してPR #87へ渡す。保存物は [restore-source.py](../docs/branch-publication/restore-source.py) と台帳のSHAで復元・照合できる。

## 機能要件

- dev-graphのmaterialize・confirm-feature・link-beads・planned_featuresは [C02](../plugins/dev-graph/skills/run-dev-graph-node/SKILL.md) と [C16](../plugins/dev-graph/skills/run-dev-graph-schedule/SKILL.md) の契約を正本とする。parity生成規則は [execution-tracker §10](../plugins/dev-graph/references/execution-tracker-contract.md) の単一builderを維持する。
- UBMの3チェックシートとCodexのskills領域限定許可は [journal](../plugins/ubm-goal-setting/skills/run-ubm-journal/SKILL.md) と [書込guard](../plugins/ubm-goal-setting/hooks/ubm-write-path-guard.py) に従う。
- JSON compositionは [lint](../plugins/skill-governance-lint/scripts/lint-plugin-composition.py) と [release writer](../scripts/build-plugin-release.py) の既存入口で扱う。
- SBBの番号クリックは [book生成](../plugins/system-briefing-book/scripts/build-briefing-book.mjs) と [座標取得](../plugins/system-briefing-book/scripts/render-board-png.mjs) の契約に従う。

## 非機能要件

元worktreeを保持し、他作業者の変更とmainの新修正を戻さない。全件の分類に実パスと理由を持たせ、版採番・外部書込・mergeの証拠を文書整備の成功と混同しない。新たな常駐サービスや依存ライブラリは導入しない。

## UI・状態遷移

SBBは文中の番号と画像上の測定済み枠から対応画面・説明へ移動する。リンク先がない番号、自己参照、検査後に変わったボードの古い枠は既存生成器の規則で扱う。本資料とfeatureはdraft/pendingのまま、文書骨格のreadiness completeだけで実装着手・tracker投影へ昇格しない。

## ビジネスルールと検証

mainのflyer-studio 1.3.2は元1.3.1の上位として保持する。元版362ファイルの保存台帳にはflyerの素材42・verification85・development-plan25を含む。各元差分の統合先または保存先を説明し、未対応の行を成功扱いで落とさない。

## API契約

N/A: 新規または変更する公開HTTP endpointはない。影響する内部CLI・JSON receipt・構成入力は上の正本リンクと [影響受領書](../system-spec/branch-publication/spec-impact-receipt.json) へ接続し、この文書で引数やschemaを二重定義しない。

## データモデル

新しいDBは作らない。canonical graph・C02 immutable receipt・parity snapshot・UBM journal・JSON composition・SBB boards.jsonと静的HTMLという既存ファイル契約を使う。原本と統合後の内容は別identityとして保存し、source snapshotのSHAを実装の現行版へ上書きしない。

## 認証・認可

新規の認証機構はない。ユーザーの全件統合指示はscopeの根拠であり、未取得のmutation承認receiptを生成した証拠ではない。C28新規createがdraft taskを拒否した状態は保持し、BeadsやGitHubへの操作は親の既存承認・guard契約に従う。

## エラー・例外・回復

C02 previewとapplyのrevisionがずれればCAS拒否から再previewする。normal taskのpromotion writer不在はdraftを手編集で昇格させず既存harness-86khで追跡する。parityのstaleはcanonical builderで再生成しdigestだけを書き換えない。元版保存はmainのファイルを旧版へ置換する回復策にしない。

## イベント・非同期処理

新しいqueueやschedulerは作らない。PR merge後の完了収束は [GitHub lifecycle契約](../plugins/dev-graph/references/github-lifecycle-contract.md) のC26→C02 consumerへ委譲する。PR close未mergeやfeature/dirty worktreeをdoneにしない。本登録ではlifecycleや外部投影を起動しない。

## 可観測性

[全件台帳](../docs/branch-publication/manifest.json) に元差分と保存先、C02 receiptにrevision・artifact SHA、[task契約評価](../docs/branch-publication/task-contract-review.json) にC1-C4のdesign判定を残す。未反映0件、回帰成功、公開成功はそれぞれ別の証跡で確認する。

## 互換性・移行・リリース

旧CLI名・旧文書・画像・検証結果はsource snapshotとして保存する。実行pluginにはmainの新版・既存責務境界を維持し、UBM旧形式はjournalの移行経路に従う。版番号同期は親の正規release writerが所有し、本資料登録では採番しない。

## テストと受入条件

受入は全元差分の対応先説明、main修正の保持、保存SHAの一致、対象別の既存回帰、C02生成4文書のfinding0とdraft保持で判定する。今回の文書登録の検証と、親が実施する実装回帰・CI・PR公開の達成を分ける。content-reviewのPASSをbehavior/live-trial成功へ転用しない。

## 未決事項

全件台帳の最終分類と未対応0件の確定、親担当のrelease・push・CI・PR #87の最終状態は別途観測する。新taskのpromotion writerは本統合で追加せず、draft保持と既存harness-86khの追跡を継続する。


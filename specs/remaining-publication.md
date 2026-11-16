---
graph_node_id: "spec-remaining-publication"
artifact_kind: "specification"
artifact_subtypes: []
title: "元ブランチ残存を失わず安全に公開する仕様"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["remaining-publication", "mvp", "source-integration"]
file_path: "specs/remaining-publication.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T05:00:55.517262Z"
updated_at: "2026-11-16T05:00:55.517262Z"
depends_on: []
related_nodes: ["arch-remaining-publication", "feature-remaining-publication"]
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
classification_reason: "harness-esj6で承認された元ブランチ残存の公開統合を記録するspecification。"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/remaining-publication.md", "confidence": 0.97}, {"artifact_kind": "document", "candidate_path": "docs/remaining-publication.md", "confidence": 0.03}]
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

# 目的と成功状態

元ブランチの未公開実装・説明・検証成果を、最新mainの公開済み修復を保った追加PRへ統合する。元rootにも正常commitの履歴を残した後、公開branchの履歴へ揃え、公開済みなのにgsへ残る状態を解消する。

## スコープ

7機能群の未公開差分、対応仕様と正規5文書、全statusの分類manifest、匿名化派生物と履歴、最小ゲート、対象限定commit/push/draft PRと元rootの履歴収束。秘密や承認runtimeの公開、新exact13計画、実API/live再走、既存未達のPASS化は対象外。

## 用語と主体

mainは公開済み正本、source snapshotは今回統合対象の入力、公開manifestは全statusの分類と対応先を持つ台帳。公開担当が統合・privacy・最小ゲートを管理し、host担当作業は当該hostが実行した証拠を残す。

## ユースケースとユーザーフロー

元statusを台帳へ取り込み、main公開済みと未公開差分を分ける。3way統合後に7機能群と説明を突き合わせ、公開3派生物と非公開tempを分類する。最小ゲート後に追加draft PRへ出し、元rootを正常commitと公開branchの履歴へ収束させる。

## 機能要件

FR1: YAML cache: 正規builderがcacheと索引を作り、節・見出しの必要範囲だけをReadする。hash/取得日時の不一致は停止し、ネット取得なしのreindexを提供する。
FR2: run model budget: convergence-policyを正本にrun_id全体のAI起動予算を計算し、gate/launcher/plannerが起動前に同じ台帳へ予約する。再試行の重複課金と並行予約の超過を防ぎ、枯渇時はfail-closedで起動しない。
FR3: knowledge-loop: 既存schema/lint/engineと参照文書の整合を取り、4資料、consult_at、検索・記録CLIとruntime境界を正しく案内する。新しい外部知能engineを導入する変更とは区別する。
FR4: artifact delivery: state-machineの各所の写しをglobal policy参照へ寄せ、現状で試す/診断するの選択を先に、改善深度を診断後の1回へ整理する。通常のplugin追加や起動に全repo走査・LLM評価を要求しない。
FR5: runtime profiles: 構築時DAGと実行時DAGを分け、最小十分なinlineを既定にする。独立contextや実依存がある場合だけfork/task-graphを使い、同pluginの正本参照・別pluginへの実体配布・配線なし理由・冗長path宣言を検査する。
FR6: system-dev-planner: CLI/in-processで同じrealpath境界を要求し、壊れたsymlink、UTF-8/IO、policy違反、RFC3339、世代markerの扱いを明確化する。既存exact13契約を新しい計画生成なしで維持する。
FR7: evidence and host work: hashに束縛した検査再利用、traceとbriefの一致、検証予算、C1-C4レポート、transcript計測、runtime evidence ledgerを整える。install/enable/trust/new-session等のhost担当作業は保留証拠を残し、未実行をPASSへ置き換えない。
FR8: 初期gsの2284status項目すべてに公開対象manifest上の対応を持たせ、main公開済み/新規統合/履歴保存/秘密匿名化/非公開tempを理由付きで分類する。公開できない原locatorはopaque IDまたはSHAで照合し、分類漏れを許さない。
FR9: 最新mainのPR91公開済みPKG007・配布closure・owner-qualified資料・既存25node/receiptを維持する。sourceの古いfileを丸ごと上書きせず、未公開の新機能hunkと必要な履歴だけを統合する。
FR10: 公開対象3ファイルは秘密/個人情報を匿名化した派生物として保存し、元bytesと元SHAは非公開保管する。公開文書へprivate raw locatorを書かない。旧FAIL/INCOMPLETEと旧verdictのreviewed SHAを保持し、現在の成功へ付け替えない。

## 非機能要件

必要な節だけを読み、不要な検査往復・model context起動を増やさない。通常のplugin追加処理と通常runtimeに、今回の公開作業を理由とする全repo走査やLLMを追加しない。hash/予算/境界検査は決定論的にfail-closedとする。速度向上は測定結果なしに断言しない。

## UI・状態遷移

成果物を先に提示し、accept-as-isでは追加診断contextを起動しない。diagnose後にだけ意味診断と改善深度の選択へ進む。host担当保留はpending/deferredとして明示し、handoff完了と未実行作業の受入れを混同しない。

## ビジネスルールと検証

公開済みmainを古いsourceへ戻さない。run_idは差戻しでも同じ予算に束縛する。cache/indexは同じ内容・取得日・SHAへ束縛し、取得日を新しく偽装しない。検査再利用は入力slice・brief・生成物・checker契約の一致を条件とし、読めない/古い証拠を成功扱いしない。

## API契約

新規外部HTTP APIは追加しない。内部CLI・policy・trace・runtime ledgerの契約変更は7機能群の正本へ反映する。既存Notionやhost providerの実操作を今回の静的公開確認から推定しない。

## データモデル

YAML索引、run予算台帳、build trace、検証receiptとruntime evidence ledgerを既存正本schemaへ対応させる。外部DB構造の新規変更はない。履歴の原SHAと匿名化派生物のSHAを区別し、公開manifestで由来を追跡する。

## 認証・認可

既存の認証・承認方式を保持し、token・鍵・署名付きruntime承認記録を公開しない。privacy派生物は原本ではないと明記する。正規guard、host担当境界、realpath containmentを緩めない。

## エラー・例外・回復

cache/index不一致、AI予算超過、外部へのsymlink、壊れた入力、証拠の不一致は理由付きで停止する。再試行は既存run・claimへ結び、予算を二重予約しない。元rootの履歴収束が失敗した場合は原snapshotと公開manifestを残して停止し、無関係な差分を破棄しない。

## イベント・非同期処理

通常runtimeに新しい全体監査jobやLLMを追加しない。公開処理の全status照合と最小ゲートは開発時だけ実行する。host依存作業は完了を偽らず正規の保留証拠で後続へ渡す。

## 可観測性

初期gsの2284status項目すべてに公開対象manifest上の対応を持たせ、main公開済み/新規統合/履歴保存/秘密匿名化/非公開tempを理由付きで分類する。公開できない原locatorはopaque IDまたはSHAで照合し、分類漏れを許さない。 公開対象3ファイルは秘密/個人情報を匿名化した派生物として保存し、元bytesと元SHAは非公開保管する。公開文書へprivate raw locatorを書かない。旧FAIL/INCOMPLETEと旧verdictのreviewed SHAを保持し、現在の成功へ付け替えない。 判定理由・対応先・実ログ・writer receipt・quality gateを辿れるようにする。

## 互換性・移行・リリース

最新mainのPR91公開済みPKG007・配布closure・owner-qualified資料・既存25node/receiptを維持する。sourceの古いfileを丸ごと上書きせず、未公開の新機能hunkと必要な履歴だけを統合する。 公開版の採番/metadataは親の正規release手順と実結果に従い、本文へ未確定の版を固定しない。元rootはまず正常commitしてから公開branchと履歴を揃える。自動mergeやmanual completionの自動done化は行わない。

## テストと受入条件

最小ゲートのコマンド・実結果・test件数・対象版は親が管理するsystem-spec/remaining-publication/quality-gates.jsonを正とする。全体LLM再評価、live再走、全coverage達成認定は追加しない。 加えて2284status全件分類、privacy3派生物の原SHA追跡、旧verdict SHA保全、新規5nodeのschema/readinessと他25node不変、元rootの履歴収束を受入条件とする。

## 未決事項

既存全体coverage未達、既存openの安全性/運用follow-up、未実行の実API/live/host操作は継続して明示する。新規登録はdraft/pendingであり、公開や台帳登録を製品全体の受入れ達成へ読み替えない。


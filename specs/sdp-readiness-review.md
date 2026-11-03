---
graph_node_id: "spec-sdp-readiness-review"
artifact_kind: "specification"
artifact_subtypes: []
title: "初期化前の操作と計画実行中の検査を分ける仕様"
project_id: "system-dev-planner"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["system-dev-planner", "mvp", "publication-review"]
file_path: "specs/sdp-readiness-review.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T14:22:42.460658Z"
updated_at: "2026-11-03T14:26:24.611844Z"
depends_on: []
related_nodes: ["arch-sdp-readiness-review", "feature-sdp-readiness-review"]
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
classification_confidence: 0.96
classification_reason: "初期化前の操作停止の修復と残存証跡の公開に対応するspecification。"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/sdp-readiness-review.md", "confidence": 0.96}, {"artifact_kind": "document", "candidate_path": "docs/sdp-readiness-review.md", "confidence": 0.04}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-03T14:26:24.611844Z", "missing_sections": [], "status": "complete"}
---

# 目的と成功状態

dev-graphだけを初期化したリポジトリでも通常操作を続けられ、計画実行中は完全な設定と仕様準備の検査を必須にする。未提出の検証証跡を、元の失敗判定と原ファイルを保ったまま公開する。

## スコープ

対象はC07ガード、C09内部resolver、C10の既存初期化経路、対応タスク仕様と案内、未提出eval-log。ローカルの権限制約削除、署名付き承認トークン、一時入力は除外して保持する。

## 用語と主体

最小contextはrepository_idとcontent_roots/local_stateの境界検査を通した状態。完全contextはplan_rootsを含む従来の検査。正規lock rootはC13のLOCK_ROOT_REL。利用者が初期化し、ガードが操作前に状態を確認する。

## ユースケースとユーザーフロー

1. dev-graph init後、plan_rootsがまだ無い状態で通常のBash/Taskを使う。
2. 計画実行時は完全contextで取得されたロックを探索してreadinessを確認する。
3. 設定不足なら利用者が別ターミナルでC10 initを実行し、不足キーだけ補う。

## 機能要件

- FR-001: 管理対象でないrepoは通過する。
- FR-002: 管理対象ではidentity/containmentを常に検査する。
- FR-003: lock不在ではplan_rootsの欠落だけを許す。存在する不正値は拒否する。
- FR-004: lock探索はC13正規rootに固定し、local_state.locks変更で隠せない。
- FR-005: 有効lockがあれば完全contextとreadinessを必須にする。

## 非機能要件

ローカルPython 3.10以上、ネットワーク不要。判定0は通過、2は拒否。不正設定の黙認を防ぐ。復旧コマンドの引数はshlex.quoteで引用し、空白を含む保存先にも対応する。

## UI・状態遷移

CLIのみ。未管理→通過。管理対象→最小context検査→正規lock探索→不在なら通過、有効なら完全context検査→readiness。context不正時は拒否理由と別ターミナルからの復旧案内をstderrへ出す。

## ビジネスルールと検証

欠落と不正値を区別する。require_plan_roots=FalseはC07内部だけの引数で、C09 CLIの検査は緩めない。期限切れlockは従来のC13公開cleanupで監査記録付きで除去する。過去のFAILは新しいPASSへ書き換えない。

## API契約

HTTP APIは無い。C09内部関数にkeyword-only require_plan_roots=Trueを追加し、C07のlock探索時だけFalse。CLI引数は追加しない。

## データモデル

plan_rootsは通常はdict必須。最小contextでキー自体が欠ける場合だけNone。既存configにはC10でstaging/published/stateを不足分だけ追加する。ロックJSONの形式、graph schema、署名形式は変更しない。

## 認証・認可

repository_idの再導出照合とパスのrealpath境界検査は両モードで必須。権限denyの削除を製品差分へ含めない。別repoやrepo外symlinkを許可しない。

## エラー・例外・回復

context不正、有効lock下のplan_roots欠落、不正値はexit2。init-project-layout.py --repo-rootを別ターミナルで実行して欠落キーを非破壊補完する。identity不一致と不正パスは自動修復せず確認を促す。

## イベント・非同期処理

PreToolUseのBash/Task判定は同期。常駐ジョブ、外部API、新規キューは追加しない。

## 可観測性

BLOCKEDの理由と復旧コマンドをstderrへ記録する。今回のゲート実行ログ・受領書・原証跡SHAはsystem-spec/sdp-readiness-reviewとdocs/sdp-readiness-review配下に記録する。署名付きローカル承認ファイルは公開しない。

## 互換性・移行・リリース

通常resolverの既定はTrueで従来契約を保持する。配布版はbuild-plugin-release.py --only system-dev-plannerで正規採番しmarketplaceと指紋を同期する。DB移行は無い。戻すときは公開コミットをrevertする。

## テストと受入条件

B-C07/B-C09のverifyコマンドを再実行する。初期化前のBash/Task通過、有効lock下の拒否とC10復旧、不正値拒否、lock探索先変更による回避拒否、既存identity/containment/TTLを確認する。C02登録後はstrict graphゲートと全ファイルSHAを確認する。

## 未決事項

現行のcanonical live-trial受領書を再照合するが、新しい有料actor実走と30思考法の再走はMVP範囲外。履歴ログの未達は現行の成功と区別する。harness-86khの全体完了は過去の関連作業と分けて判断する。

## 最終レビュー結果と残課題

最終レビュー時の再検査では、SDPの回帰50件と43サブテスト、UBMの既存タスクゲート479件が成功した。既存dev-graph実走受領書の照合はx86環境で6件成功・3件失敗。C02/node、C04/requirements、C14/decomposeの3件は今回のC07/C09変更により挙動閉包のdigestが古くなったためで、現在コードの実走PASSとは認定しない。元receiptとFAILログは保持し、digestを手で付け替えない。MVP範囲では新actor実走を行わず、harness-86khの残課題としてdraft PRへ記載する。初回arm64環境のrpds読込エラーも原ログとして保持し、x86で再実行した結果と区別する。


---
graph_node_id: "arch-ubm-goal-contract"
artifact_kind: "architecture"
artifact_subtypes: ["backend"]
title: "目標文書の正本と検査の責務"
project_id: "ubm-goal-setting"
domain: "goal-setting"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["ubm-goal-setting", "mvp"]
file_path: "architecture/ubm-goal-contract.md"
template_id: "architecture"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T13:06:15.890619Z"
updated_at: "2026-11-03T13:06:15.890619Z"
depends_on: []
related_nodes: ["spec-ubm-goal-contract"]
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
classification_reason: "検査スクリプトと文書正本の責務分割なので設計である。"
classification_candidates: [{"artifact_kind": "architecture", "candidate_path": "architecture/ubm-goal-contract.md", "confidence": 0.96}, {"artifact_kind": "document", "candidate_path": "docs/ubm-goal-contract.md", "confidence": 0.04}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-03T13:06:15.890619Z", "missing_sections": [], "status": "complete"}
---

# Architecture overview

目標設定プラグインの中で、対話・文書の正本・検査スクリプトを分ける。今回の変更はローカルの文書契約であり、新しい実行基盤は作らない。

## Context and drivers

同じ規則が対話、手本、検査に重複していたため、更新漏れが誤った目標文書を生んでいた。優先するのは項目の対応が機械で分かることと、個人名を項目名へ入れないこと。制約は既存プラグインの版 0.9.3 と、手元実行のみ。

## Goals and non-goals

目標は、売上から行動までの逆算と提出用・管理用の一致を1か所の正本で保つこと。対象外は、既存月報本文の一括変換、他プラグインの改修、公開API。

## System context and boundaries

利用者は対話で目標を作り、検査スクリプトがローカルファイルを読む。外部サービス、認証基盤、共有データベースへは接続しない。境界はプラグインディレクトリと利用者の文書フォルダ。

## Container and component view

| 部品 | 責務 | インターフェース | データの持ち主 | 配置 |
|---|---|---|---|---|
| output-formats.md | 全層共通の書式 | Markdown の節 | プラグイン | リポジトリ |
| data-contract.md | 項目番号と出力層 | Markdown の表 | プラグイン | リポジトリ |
| validate-goal-output.py | 1文書の書式検査 | CLI と終了コード | 読み取り専用 | ローカル |
| validate-cross-level.py | 層間の売上2値 | CLI と終了コード | 読み取り専用 | ローカル |

## Cross-cutting contracts

本人確認は追加しない。失敗は終了コードと理由行。秘密情報はリポジトリへ置かない。版は CHANGELOG と plugin.json の 0.9.3 を一致させる。

## Subtype architecture

合成対象の subtype と該当テンプレート:

- Frontend: N/A: subtype 非選択
- Backend: 合成済み (`architecture-backend.md`)
- Infrastructure: N/A: subtype 非選択
- Data: N/A: subtype 非選択
- Security: N/A: subtype 非選択

### Backend architecture

#### Runtime and architecture pattern

Python 3.10 以上のローカルスクリプトが Markdown を読む。常駐サーバやフレームワークは置かない。対話の正本と検査を分け、検査はファイルを書き換えない。

#### Domain and module boundaries

書式の正本は output-formats.md、項目の定義は data-contract.md、対話は prompts と interview templates、検査は validate-goal-output.py と validate-cross-level.py に分ける。検査は正本を参照し、正本へ規則を複製しない。

#### API and service contracts

公開 HTTP は無い。検査の契約はコマンド引数と終了コード、失敗行の文言である。層間照合は売上目標と累計売上実績の2値だけを比べる。

#### Data and transaction behavior

目標文書の保存先は利用者の手元である。プラグインは知識 JSON と規則 Markdown をリポジトリに持つ。検査は読み取り専用で、文書の同時更新は扱わない。

#### Async processing

キューや定期実行は追加しない。知識の取り込みは利用者がスキルを起動したときだけ行う。

#### Security and resilience

項目名に個人名を入れない。提出用は管理用から個人名とチェック欄だけを外す。入力が規則に合わなければ失敗で止まり、値を推測して埋めない。

#### Operations and verification

pytest で書式、閉包、層間、問い数を固定する。失敗時は行番号と理由を出す。監視ダッシュボードは置かない。

## Architecture decisions

| 決定 | 内容 | 捨てた案 | 理由 | 結果 |
|---|---|---|---|---|
| ADR-1 | 書式は共通部品へ集約 | 層ごとの全文複製 | 更新漏れを止める | 参照1行で追随する |
| ADR-2 | 層間照合は売上2値 | 最重要数字も比較 | 層ごとに値が違うのが正しい | それ以外は SKIP |
| ADR-3 | 1回3問 | 1ターンに全問 | 答えの取りこぼしを減らす | 問番号は通し |

## Delivery, migration and rollback

配布はプラグイン版 0.9.3。既存の目標文書は自動移行しない。戻すときはこの版のコミットを revert する。データ変換バッチは無い。

## Risks and verification

リスクは、SKILL.md 更新後の content-review が未再取得なこと。検証は対象 pytest 479 件の成功と、グラフ検証の成功。負荷試験と侵入試験は対象外。


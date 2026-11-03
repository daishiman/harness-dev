---
graph_node_id: "spec-ubm-goal-contract"
artifact_kind: "specification"
artifact_subtypes: []
title: "目標文書の書き方と検査の仕様"
project_id: "ubm-goal-setting"
domain: "goal-setting"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["ubm-goal-setting", "mvp"]
file_path: "specs/ubm-goal-contract.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T13:06:15.890619Z"
updated_at: "2026-11-03T13:06:15.890619Z"
depends_on: []
related_nodes: ["arch-ubm-goal-contract", "feature-ubm-goal-contract"]
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
classification_reason: "目標文書の契約と検査規則の変更なので仕様である。"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/ubm-goal-contract.md", "confidence": 0.96}, {"artifact_kind": "document", "candidate_path": "docs/ubm-goal-contract.md", "confidence": 0.04}]
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

# 目的と成功状態

1年・期・月・週の目標を、売上から成果、成果から行動へ逆算して書ける。提出用と管理用は同じ項目名・件数・単位・期日を持つ。検査スクリプトが書式のずれを失敗として返す。

## スコープ

- 対象: 目標設定スキルの出力契約、対話の問いの数、層間の金額照合、ナレッジの原則の当てはめ。
- 対象外: 既存の月報本文の書き換え、他プラグイン、公開API、認証、データベース。

## 用語と主体

| 用語 | 意味 |
|---|---|
| 提出用 | 人に渡す目標文書。個人名とチェック欄を外す |
| 管理用 | 自分が見る目標文書。提出用と同じ項目を持つ |
| 軌道修正 | 前回目標を残したまま、今回の実行値だけを理由付きで変える |

## ユースケースとユーザーフロー

1. 利用者が対話で前回の売上・成果・行動を確認する。
2. スキルが上位の到達点を変えずに、今回の行動と期日を書く。
3. 検査スクリプトが期日、貢献0の括弧、層間の売上2値を照合する。

## 機能要件

- FR-001: 行動行は項目名、内容、期日トークンを持つ。
- FR-002: 提出用は管理用と同じ項目名・件数・単位・期日を持つ。
- FR-003: 1回の問いは3問までで、答えを待って次の回へ進む。
- FR-004: 層をまたぐ機械照合は今期の売上目標と累計売上実績の2値に限る。

## 非機能要件

- 性能: 目標文書1件の検査はローカルの Python で完了する。
- 可用性: ネットワークなしで検査できる。
- 使いやすさ: 専門用語を案内文書では言い換える。
- 安全: 項目名に個人名を入れない。
- 保守: 書式の正本は output-formats.md の共通部品に置く。

## UI・状態遷移

画面は作らない。対話は回ごとに答えを待つ。検査結果は成功、警告、失敗の3状態で、失敗時は行の理由を返す。空の前回正本は初回マーカー1行にする。

## ビジネスルールと検証

- BR-001: 売上を目的にし、成果は人数や件数、行動は回数や件数で書く。
- BR-002: 期日トークンは月日、日付、曜日、毎日、毎朝、毎週、今週だけを許す。毎月と今月中は失敗。
- BR-003: 上位の最終到達点と過去の目標は自動で書き換えない。

## API契約

HTTP API は追加しない。契約はローカルの Markdown と Python 検査の入出力に閉じる。

## データモデル

行動は actions 配列へ統合し、旧 action_daily と action_period は使わない。週報と月報は前回のやらないことの確認を持ち、月報だけが今月守る原則を持つ。正本は data-contract.md。

## 認証・認可

ログインは追加しない。目標文書は利用者の手元のフォルダに書き、このリポジトリの公開範囲はプラグインの規則と検査だけにする。

## エラー・例外・回復

書式違反は終了コードで失敗にする。未確定の実績は確認中と書き、記号で成否を埋めない。警告は終了コードを変えないものだけに限る。

## イベント・非同期処理

非同期ジョブは追加しない。対話は1回に3問までを同期で進める。

## 可観測性

検査の失敗理由を標準出力へ出す。実行ログに個人の目標数値をリポジトリへ残さない。品質の証跡はテスト結果と受領書に限る。

## 互換性・移行・リリース

プラグイン版は 0.9.3。既存の月報本文は自動変換しない。簡潔版の月報は既定にしない。版の履歴は CHANGELOG.md を正本にする。

## テストと受入条件

対象テスト 479 件が成功すること。フィールド閉包、層間照合、1ターンの問い数、目標出力の検査を含む。content-review の取り直しは残作業とする。

## 未決事項

既存11月月報の本文を正本へ揃える作業は harness-3skp として開いたままにする。content-review の判定は SKILL.md 更新後に取り直す。


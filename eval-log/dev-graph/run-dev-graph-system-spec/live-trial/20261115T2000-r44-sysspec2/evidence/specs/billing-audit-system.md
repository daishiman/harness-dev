---
graph_node_id: "spec-billing-audit-system"
artifact_kind: "specification"
artifact_subtypes: []
title: "請求・監査統合システム 仕様書"
project_id: "billing-audit"
domain: "billing"
status: "done"
priority: null
start_date: null
target_date: null
iteration: null
owners: []
tags: []
file_path: "specs/billing-audit-system.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluated_digest": "f7f6476735e6ed5e07b2583a7d628b8cfd89227235c5745f3ae10681b8d545e2", "evaluator": "system-spec-harness:assign-system-spec-completeness-evaluator", "evidence_ref": "eval-log/system-spec-completeness-report.json"}
source_lineage: {"imported_at": "2026-11-15T11:25:25Z", "origin_kind": "system-spec-harness", "source_digest": "f7f6476735e6ed5e07b2583a7d628b8cfd89227235c5745f3ae10681b8d545e2", "source_path": "system-spec/index.md", "source_plugin": "system-spec-harness", "source_version": "0.1.28"}
created_at: "2026-11-15T11:26:44.853820Z"
updated_at: "2026-11-15T11:26:44.853820Z"
depends_on: []
related_nodes: []
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
classification_confidence: 0.95
classification_reason: "system-spec-harness の compile 済み index.md (確定 8 章の相互参照) を、システム全体の仕様書として取込む。機能・非機能・データ・認可・API を含む確定仕様の束であり architecture の構成判断ではない"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/billing-audit-system.md", "confidence": 0.95}, {"artifact_kind": "architecture", "candidate_path": "architecture/billing-audit-system.md", "confidence": 0.05}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-15T11:26:44.853820Z", "missing_sections": [], "status": "complete"}
---

# 目的と成功状態

取込元: system-spec/index.md と system-spec/00-requirements-definition.md (確定)。本質的目的 (U1) は、請求の数字を誰が見ても同じだと信じられる状態にすること。成功状態 (U5) は、稼働後 3 か月連続で締め後に残る請求漏れが 0 件で、同じ期間に月末の突合を表計算へ書き出さずに終えていること。ゴールは G1 (請求・監査データを単一の信頼できる情報源へ統合) と G2 (主要業務動線を Web だけで完結)。

## スコープ

対象 (U7 in): 請求の入力、月末の突合、請求の確定、監査ログの記録と閲覧。対象外 (U7 out): 給与計算 (人事部の別システム)、モバイル・タブレット・デスクトップアプリ (Web のみ, qa-000)。全 8 カテゴリ (database, auth, ui-ux, security, infrastructure, backend, frontend, maintenance-ops) の web セルが確定、他 platform は対象外 (理由付き)。

## 用語と主体

主体 (U6): 経理チームの請求担当 40 名 (日々の利用者)、経理チームのリーダー (請求の確定を承認)、内部監査室 (監査ログを閲覧)、情報システム部 (社内 k8s と社内 IdP を運用)。用語: 赤黒訂正 = 確定済み請求書を書き換えず、取り消しの請求書と新しい請求書を発行して直すこと。請求漏れ = 予定請求期限を過ぎても有効な請求書が無い、または必要な契約明細が欠ける請求予定 (system-spec/backend.md)。

## ユースケースとユーザーフロー

毎日の請求明細の入力と、月末 3 営業日の突合 (1 人あたり 1 日に数百行の明細を確認) を経て、締め日までに経理リーダーが請求を確定する (system-spec/ui-ux.md)。突合画面は未突合件数と食い違いのある取引先を先頭に出し、食い違いを金額の大きい順に並べ、一致済みの明細は畳む (I2)。

## 機能要件

請求書の一覧と登録・更新、突合の実行と結果の取得、確定の承認、監査ログの検索 (system-spec/backend.md)。請求漏れは 15 分ごとに自動走査し、期限超過から 30 分以内に担当者の Web 画面の「請求漏れ」一覧へ出す (O1)。請求・監査データは日次でバックアップする (I1)。

## 非機能要件

社内ネットワーク上の PC ブラウザ向けレスポンシブ Web、WCAG 2.1 AA 目標、主要動線は 3 クリック以内 (system-spec/ui-ux.md)。画面から呼ぶ API の応答時間 p95 が 2 秒を超えた状態が 5 分続くか、5xx エラー率が 5 分間で 1% を超えたら異常とみなす (暫定値, system-spec/infrastructure.md)。TLS1.3・入力検証・OWASP Top10 受動対策 (system-spec/security.md)。

## UI・状態遷移

React + TypeScript の SPA (D2) で、突合の画面は頁を読み直さずに並べ替えと行の修正ができる。状態管理は最小限のグローバルストア (system-spec/frontend.md)。請求書は 入力 → 突合 → 確定 と遷移し、確定後は書き換えず赤黒訂正でのみ直す (I3)。

## ビジネスルールと検証

取引先ごとの契約から毎月の請求書を作り、請求書は複数の請求明細を持ち、入金は請求書に消し込む。突合は月ごとに行い食い違いを記録する。確定した請求書は書き換えず赤黒訂正で直す。監査ログは追記のみで、消したり書き換えたりしない (system-spec/database.md, backend.md)。金額の食い違いは突合機能が扱い、請求漏れの定義と混同しない。

## API契約

Python/FastAPI の REST API (system-spec/backend.md)。一覧はページに分けて取得する。2 人が同じ請求書を同時に直したときは、後から保存した方を上書きせず競合として止める。状態を変える要求 (POST・PUT・PATCH・DELETE) はセッションごとの CSRF トークン (synchronizer token) を必須にし、無いか合わない要求は拒否する (system-spec/auth.md)。

## データモデル

PostgreSQL 16 (D1, 情報システム部の提供版) に、契約・請求予定・請求書・請求明細・入金・突合結果・監査ログを持つ。請求予定ごとに契約ID・対象年月・予定請求期限・期待明細を保持する。セッションも PostgreSQL 16 の表に保存する (system-spec/database.md, auth.md)。

## 認証・認可

社内 IdP の OIDC でログインし、トークンはバックエンド (FastAPI) が持ち、ブラウザには HttpOnly・Secure・SameSite=Lax の cookie セッションだけを渡す (D3 bff-session)。セッションは 8 時間で、ログアウトで即時無効化。ロールベース認可: 請求担当は担当取引先の入力と突合、確定の承認はリーダーのみ、内部監査室は全件閲覧のみ、情報システム部は運用のみで請求データは見られない。IdP でアカウントが無効になれば本システムにも入れない (system-spec/auth.md)。

## エラー・例外・回復

同時更新は後勝ちで上書きせず競合として止める。非同期ジョブは再試行で同じ job が実行され得ることを認め、業務効果の二重反映を禁止し、リトライ上限と失敗状態を保存する (D4)。障害時はオンコール輪番が runbook に沿って対応し、週次でリストア訓練を行う (system-spec/maintenance-ops.md)。

## イベント・非同期処理

D4 pg-worker-cron: 業務更新と同じ transaction で PostgreSQL 16 の job_outbox へ投入し、社内 k8s 上の Python worker Deployment が 1 秒間隔で claim して重い突合と手動の再検査を処理する。15 分ごとの請求漏れ走査は同じ worker image の k8s CronJob で起動し、DB claim の排他・lease/fencing token・業務の一意キーで冪等にする (system-spec/backend.md)。

## 可観測性

情報システム部が社内監視基盤でコンテナの死活とエラー率を見る。月末 3 営業日は画面応答が遅くなったら当番に通知する。アラートはオンコール輪番のその週の担当者へ社内チャットの当番チャンネルとメールで送り、runbook の手順へのリンクを付ける (system-spec/infrastructure.md, maintenance-ops.md)。

## 互換性・移行・リリース

データ構造の変更は版番号を付けた移行スクリプトで行い、本番に当てる前に必ずバックアップを取り、元に戻す手順も一緒に用意する (system-spec/database.md)。コンテナを社内 k8s へデプロイし、CI/CD は GitHub Actions を使う (system-spec/infrastructure.md)。

## テストと受入条件

受入条件: O1 締め後に残る請求漏れ 月次 0 件、O2 月末 3 営業日の表計算への書き出し 0 回 (いずれも稼働後最初の月次締めから計測)。成功基準 U5 は 3 か月連続で両方を満たすこと。暫定の性能閾値は最初の月次締めで実測し、2 回目の月次締めの前に見直す。

## 未決事項

completeness evaluator (eval-log/system-spec-completeness-report.json, verdict PASS) の非 blocking 指摘を持ち越す: 要件定義書の decisions 表が security_fit を描画していない (medium)、qa-033 と qa-o1-fixture-v3 の論点の束ね (medium, C06 note)、ui-ux×web の qa_refs に置き換え済み qa-009 が残る (low)、security 章に CSRF 方針の反映が無い (low)。どれも C01/C03 側で直し、本 node は lineage で再取込する。


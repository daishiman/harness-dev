---
graph_node_id: "spec-billing-audit-system-spec"
artifact_kind: "specification"
artifact_subtypes: []
title: "請求・監査統合 Web システム 仕様書 (system-spec index 取込)"
project_id: "billing-audit"
domain: "billing"
status: "done"
priority: null
start_date: null
target_date: null
iteration: null
owners: []
tags: []
file_path: "specs/billing-audit-system-spec.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluated_digest": "f7f6476735e6ed5e07b2583a7d628b8cfd89227235c5745f3ae10681b8d545e2", "evaluator": "system-spec-harness:assign-system-spec-completeness-evaluator", "evidence_ref": "eval-log/system-spec-completeness-report.json"}
source_lineage: {"imported_at": "2026-11-01T14:39:05Z", "origin_kind": "system-spec-harness", "source_digest": "f7f6476735e6ed5e07b2583a7d628b8cfd89227235c5745f3ae10681b8d545e2", "source_path": "system-spec/index.md", "source_plugin": "system-spec-harness", "source_version": "0.1.24"}
created_at: "2026-11-01T14:40:56.305780Z"
updated_at: "2026-11-01T14:40:56.305780Z"
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
classification_reason: "system-spec-harness の確定済み仕様書セット index (system-spec/index.md)。要件定義書を先頭に全 8 技術章 (全て確定) の集約状態と資するゴールを相互参照する機能・非機能要件の仕様書で、C19 R3 の取込規則で index は specification へ写す"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/billing-audit-system-spec.md", "confidence": 0.95}, {"artifact_kind": "architecture", "candidate_path": "architecture/billing-audit-system-spec.md", "confidence": 0.3}, {"artifact_kind": "document", "candidate_path": "docs/billing-audit-system-spec.md", "confidence": 0.2}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-01T14:40:56.305780Z", "missing_sections": [], "status": "complete"}
---

# 目的と成功状態

請求の数字を、誰が見ても同じだと信じられる状態にする (U1)。表計算と監査台帳の二重管理をやめ、請求と監査を 1 つの Web システムへ統合する。成功状態は稼働後 3 か月連続で締め後に残る請求漏れ 0 件、かつ月末の突合を表計算に書き出さずに終えていること (U5)。正本は system-spec/00-requirements-definition.md。

## スコープ

- In: 請求の入力、月末の突合、請求の確定、監査ログの記録と閲覧 (U7, qa-017)
- Out: 給与計算 (人事部の別システム)、モバイル・タブレット・デスクトップアプリ (Web のみ, qa-000)。全 8 カテゴリの mobile/tablet/desktop-* セルは対象外として確定済み (各章のカテゴリ別収集状態)

## 用語と主体

| Term/Actor | Definition/Responsibility |
|---|---|
| 請求担当 (40 名) | 自分の担当取引先の請求を入力し、月末 3 営業日に突合する (qa-016, qa-019, qa-026) |
| 経理チームのリーダー | 請求の確定を承認する唯一の主体。請求漏れ一覧も閲覧する (qa-026, qa-o1-fixture-v3) |
| 内部監査室 | すべてを閲覧できるが変更できない (qa-026) |
| 情報システム部 | 社内 k8s・社内 IdP・監視基盤を運用し、請求データは見ない (qa-026, qa-029) |
| 赤黒訂正 | 確定済み請求書を書き換えず、取り消しの請求書と新しい請求書を発行する訂正 (qa-024) |
| 請求漏れ | 予定請求期限を過ぎても有効な請求書が無い、または必要な契約明細が欠ける請求予定 (qa-o1-fixture-v3) |

## ユースケースとユーザーフロー

1. 請求担当が契約から作られた毎月の請求書の明細を入力する (qa-021, qa-024)
2. 15 分ごとの自動走査が請求漏れを検知し、期限超過から 30 分以内に担当者の「請求漏れ」一覧へ出す (O1, qa-o1-fixture-v3)
3. 月末 3 営業日に請求担当が突合を実行し、未突合件数と食い違いのある取引先を先頭に、食い違いを金額の大きい順に確認して修正する (I2, qa-028)
4. 経理チームのリーダーが請求の確定を承認する。締め処理は全有効契約を再照合し、請求漏れが残れば確定を拒否する (qa-026, qa-o1-fixture-v3)
5. 確定後の誤りは赤黒訂正で直す (I3)
6. 内部監査室が監査ログを検索・閲覧する (qa-025)

## 機能要件

- `FR-001`: 請求書の一覧 (ページ分割取得) と登録・更新 (qa-025)
- `FR-002`: 突合の実行と結果の取得。重い処理は非同期ジョブで実行し二重起動を防ぐ (qa-025, qa-006)
- `FR-003`: 確定の承認はリーダーだけが行える (qa-026)
- `FR-004`: 確定済み請求書は書き換えず赤黒訂正で直す (I3, qa-024)
- `FR-005`: すべての操作を追記のみの監査ログに残し、検索できる (qa-024, qa-025)
- `FR-006`: 請求漏れを 15 分ごとに自動検知し一覧に出す。GET /billing-missing、POST /billing-missing/checks (202 受付)、GET /jobs/{id} (O1, qa-o1-fixture-v3)

## 非機能要件

- Performance: 画面から呼ぶ API の p95 応答 2 秒超が 5 分続いたら遅延とみなす (暫定値、稼働後最初の月次締めで実測し見直す, qa-035)
- Availability/Reliability: 日次バックアップ (I1) と週次リストア訓練 (qa-008)。5xx 率が 5 分間で 1% 超を異常とする (qa-035)。worker 停止時は永続 outbox から再開する (qa-job-choice-fixture-v3)
- Accessibility/Usability: レスポンシブ Web、WCAG 2.1 AA 目標、主要動線 3 クリック以内 (qa-003)
- Security/Privacy: TLS1.3・入力検証・監査ログ・OWASP Top10 受動対策 (qa-004, qa-security-written-v7)
- Maintainability/Operability: オンコール輪番と障害 runbook (qa-008)。詳細は system-spec/maintenance-ops.md

## UI・状態遷移

- 画面/CLI/API状態: 請求書は契約から毎月作られ、入金を消し込み、月ごとの突合で食い違いを記録・修正し、経理チームのリーダーの承認で確定する。確定後は書き換えず赤黒訂正のみ (qa-024, qa-026)
- 遷移条件: 確定はリーダーの承認でのみ遷移し、請求漏れが残る締めは拒否する (qa-026, qa-o1-fixture-v3)。同じ請求書の同時更新は後から保存した側を止める (qa-025)
- Loading/Empty/Error: 突合画面は未突合件数と食い違い取引先を先頭に出し、一致済み明細は畳む (I2)。React + TypeScript の SPA で頁を読み直さずに並べ替え・修正する (D2, qa-032)。詳細は system-spec/ui-ux.md と system-spec/frontend.md

## ビジネスルールと検証

- `BR-001`: 確定済み請求書は書き換え不可。訂正は取り消しと新規の請求書の発行で行う (qa-024)
- `BR-002`: 監査ログは追記のみで削除・改ざんを許さない (qa-024, qa-030)
- `BR-003`: 請求担当は担当取引先だけを入力・突合できる (qa-026)
- `BR-004`: 同時更新は楽観的排他で後勝ちの上書きを拒否する (qa-025)
- `BR-005`: 請求漏れは手動の無視では解消扱いにせず、正しい請求書の発行で次の走査に解消する (qa-o1-fixture-v3)

## API契約

N/A: 本ノードは仕様書セット index の取込で、個別 endpoint の契約は持たない。API の正本は system-spec/backend.md (REST + 非同期ジョブ, qa-006・qa-025・qa-o1-fixture-v3) を参照する

## データモデル

- Entity/Value: 取引先、契約、請求書、請求明細、入金、突合 (月次)、食い違い、監査ログ (qa-024)。請求予定・請求漏れケース・締め検査・job outbox (billing_expectations, missing_billing_cases, billing_closing_checks, job_outbox, qa-o1-fixture-v3)
- Fields/Types/Nullability: 列定義の正本は system-spec/database.md を参照する
- Relations/Constraints/Indexes: 取引先 1-n 契約 1-n 請求書 1-n 請求明細。入金は請求書へ消し込む (qa-024)。請求予定/検知ケースは契約ID・対象年月・種別の一意キーで重複反映を防ぐ (qa-o1-fixture-v3)
- Ownership/Retention/Migration: PostgreSQL 16 (D1, qa-031) に保存。版番号付き移行スクリプトと事前バックアップ・戻し手順 (qa-027)

## 認証・認可

- Authentication: 社内 IdP の OIDC。トークンはバックエンド (FastAPI) が持ち、ブラウザには HttpOnly・Secure・SameSite=Lax の cookie セッションだけを渡す (D3, qa-034, qa-csrf-written-v7)。セッションは 8 時間で PostgreSQL 16 の表に保存し、ログアウトで即時無効にする (qa-002, qa-session-written-v7)
- Authorization: ロールベース。請求担当は担当取引先のみ、確定承認はリーダーのみ、監査室は閲覧のみ、情報システム部は請求データ不可 (qa-026)
- Tenant/data boundary: IdP でアカウントが無効になれば本システムにも入れない (qa-026)。状態変更要求は synchronizer token の CSRF 検証を必須とする (qa-csrf-written-v7)

## エラー・例外・回復

- Error taxonomy: 権限外は拒否、同時更新の衝突は保存を止めて通知、CSRF トークンが無いか合わない要求は拒否 (qa-025, qa-csrf-written-v7)
- Retry/Timeout/Fallback: 重い処理は非同期ジョブで実行し、リトライ上限と失敗状態を保存し、30 分超の未処理と失敗 job を運用画面へ出す (qa-025, qa-job-choice-fixture-v3)
- Idempotency/Concurrency: DB claim の排他・lease/fencing token・業務の一意キーで業務効果の二重反映を禁止する (qa-job-choice-fixture-v3)

## イベント・非同期処理

- Producer/Consumer: 業務更新と同じ transaction で PostgreSQL 16 の job_outbox へ投入し、社内 k8s の Python worker Deployment が 1 秒間隔で claim する。15 分ごとの請求漏れ走査は同じ worker image の CronJob で起動する (D4, qa-job-choice-fixture-v3)
- Delivery/Ordering/Deduplication/DLQ: 再試行で同じ job が実行され得ることを認め、冪等性で二重反映を防ぐ。外部 broker/Redis は足さない (qa-job-choice-fixture-v3)。詳細は system-spec/backend.md

## 可観測性

- Logs/Metrics/Traces/Audit: 全操作と請求漏れの検知・解消を追記のみの監査ログへ記録 (qa-024, qa-o1-fixture-v3)。情報システム部の社内監視基盤でコンテナの死活とエラー率を監視する (qa-029)
- Alert/SLO dashboard: p95 2 秒超 5 分継続、または 5xx 率 1% 超 5 分でアラートし、その週のオンコール担当へ社内チャットとメールで runbook リンク付きで通知する (qa-035, qa-036)

## 互換性・移行・リリース

- Compatibility/versioning: 社内 k8s へコンテナでデプロイし、CI/CD は GitHub Actions (qa-005)
- Migration/backfill: 版番号付き移行スクリプトで行い、本番適用前に必ずバックアップを取る (qa-027)
- Rollout/rollback: 戻し手順を移行スクリプトと一緒に用意する (qa-027)。詳細は system-spec/infrastructure.md

## テストと受入条件

- O1: 締め完了直後の未解消請求漏れ件数が月次 0 件 (稼働後最初の月次締めから計測, qa-o1-fixture-v3)
- O2: 月末 3 営業日の表計算への書き出し 0 回
- U5: 上の 2 条件を稼働後 3 か月連続で満たす
- 各章の To-Be / Delta 節の受入条件表を判定点とする (system-spec/*.md)

## 未決事項

- qa-035 の応答時間・エラー率の閾値は暫定値で、稼働後最初の月次締めで実測し 2 回目の月次締めの前に見直す
- 今回の完成度評価 (eval-log/system-spec-completeness-report.json, verdict PASS, gaps 0) の medium 注記: qa-033 と qa-o1-fixture-v3 が 1 問に複数論点を含む (主根拠ではない)、qa-000〜008 の basis 表示が出所 (fixture) と食い違う、D4 は合成利用者の選択で実承認ではない、原則採否の記録が各章の主 qa_ref 1 件に限られ後続の確定要件 (O1・D4・CSRF/session・新 4 表・outbox) の採否が無い、設計解釈の多くが legacy_backfill
- 同 low 注記: qa-job-choice-fixture-v3 で推奨案が先頭に置かれている、ui-ux×web の補助 qa_refs に置き換え済み qa-009 が残る
- 本番利用前に fixture のシナリオ上の承認・回答を実利用者の承認で置き換える

## 要件定義書 (上位概念・憲法)

- 正本: system-spec/00-requirements-definition.md (確定マーカー confirmed、承認 appr-foundation-v2)
- 本質的目的 (U1): 請求の数字を、誰が見ても同じだと信じられる状態にする
- ゴール (U3): G1=請求・監査データを単一の信頼できる情報源へ統合する, G2=主要業務動線を Web だけで完結できるようにする

## 章一覧と集約状態

| カテゴリ | 章 | 集約状態 | 資するゴール |
|---|---|---|---|
| database | system-spec/database.md | 確定 | G1 |
| auth | system-spec/auth.md | 確定 | G1 |
| ui-ux | system-spec/ui-ux.md | 確定 | G2 |
| security | system-spec/security.md | 確定 | G1 |
| infrastructure | system-spec/infrastructure.md | 確定 | G1 G2 |
| backend | system-spec/backend.md | 確定 | G1 G2 |
| frontend | system-spec/frontend.md | 確定 | G2 |
| maintenance-ops | system-spec/maintenance-ops.md | 確定 | G1 |

## 集約状態サマリ

- 未着手: なし
- 収集中: なし
- 確定: database, auth, ui-ux, security, infrastructure, backend, frontend, maintenance-ops
- 対象外: なし

## 全体ドキュメント出典 (未割当参照)

- 全ての取得済み公式ドキュメント (PostgreSQL 16.15, React 19.3, FastAPI 0.162.0, TypeScript 7.0, Kubernetes CronJob) は各章の最新ドキュメント出典表へ割り当て済みで、未割当参照は無い (system-spec/fetched-references.json)


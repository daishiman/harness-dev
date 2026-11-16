---
graph_node_id: "arch-billing-audit-system"
artifact_kind: "architecture"
artifact_subtypes: ["frontend", "backend", "infrastructure", "data", "security"]
title: "請求・監査統合システム アーキテクチャ"
project_id: "billing-audit"
domain: "billing"
status: "done"
priority: null
start_date: null
target_date: null
iteration: null
owners: []
tags: []
file_path: "architecture/billing-audit-system.md"
template_id: "architecture"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluated_digest": "22d455478633a28463009e4dcf2de8f4ff785118f4f742e314101c81db309ebd", "evaluator": "system-spec-harness:assign-system-spec-completeness-evaluator", "evidence_ref": "eval-log/system-spec-completeness-report.json"}
source_lineage: {"imported_at": "2026-11-15T11:25:25Z", "origin_kind": "system-spec-harness", "source_digest": "22d455478633a28463009e4dcf2de8f4ff785118f4f742e314101c81db309ebd", "source_path": "system-spec/00-requirements-definition.md", "source_plugin": "system-spec-harness", "source_version": "0.1.28"}
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
classification_reason: "system-spec-harness の要件定義書 (U1-U9 と意思決定 D1-D4) を上位概念とし、確定章の構成判断 (SPA・FastAPI・PostgreSQL 16・社内 k8s・BFF セッション) をシステムのアーキテクチャとして取込む"
classification_candidates: [{"artifact_kind": "architecture", "candidate_path": "architecture/billing-audit-system.md", "confidence": 0.95}, {"artifact_kind": "specification", "candidate_path": "specs/billing-audit-system.md", "confidence": 0.05}]
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

# Architecture overview

取込元: system-spec/00-requirements-definition.md (確定, appr-foundation-v2)。社内 k8s 上で、React + TypeScript の SPA (D2) と Python/FastAPI のバックエンド (BFF セッション, D3) と PostgreSQL 16 (D1) を組み、非同期の突合と請求漏れ検知は outbox + Python worker + k8s CronJob (D4) で動かす Web 単一のシステム。

## Context and drivers

背景 (U2): 部署ごとに表計算と個別ツールが増え、請求漏れが毎月見つかり、監査のたびに資料を集め直し、月末 3 営業日の突合残業が続いている。制約 (U8): 社内 k8s、社内 IdP の OIDC、Python/FastAPI、GitHub Actions、情報システム部提供の PostgreSQL (版は D1 で 16)。

## Goals and non-goals

Goals: G1 請求・監査データを単一の信頼できる情報源へ統合する、G2 主要業務動線を Web だけで完結できるようにする。Non-goals (U7 out): 給与計算、モバイル・タブレット・デスクトップアプリ。

## System context and boundaries

利用者は社内ネットワーク上の PC ブラウザから SPA を使う。外部境界は社内 IdP (OIDC) と情報システム部の社内監視基盤・PostgreSQL 提供基盤。社外やスマートフォンからは使わず、外部メールや Slack への請求漏れ通知は追加しない。

## Container and component view

コンテナは SPA (静的配信)、FastAPI API (BFF としてトークンとセッションを持つ)、Python worker Deployment (job_outbox を 1 秒間隔で claim)、同じ worker image の CronJob (15 分ごとの請求漏れ走査)、PostgreSQL 16 (業務データ・監査ログ・セッション・job_outbox)。

## Cross-cutting contracts

監査ログは追記のみ。確定済み請求書は赤黒訂正でのみ直す。状態変更要求は CSRF synchronizer token 必須。非同期処理は冪等 (業務の一意キーと lease/fencing token) で二重反映を禁止する。全カテゴリの章が serves_goals で G1/G2 へトレースする。

## Subtype architecture

合成対象の subtype と該当テンプレート:

- Frontend: 合成済み (`architecture-frontend.md`)
- Backend: 合成済み (`architecture-backend.md`)
- Infrastructure: 合成済み (`architecture-infrastructure.md`)
- Data: 合成済み (`architecture-data.md`)
- Security: 合成済み (`architecture-security.md`)

### Frontend architecture

#### Rendering and application pattern

React + TypeScript の SPA (D2)。突合では頁を読み直さずに並べ替えと修正を続けられるようにする。

#### Routes, screens and navigation

主要画面は請求明細の入力、突合、確定の承認、請求漏れ一覧、監査ログの閲覧。主要動線は 3 クリック以内。

#### Component and design-system boundaries

社内 PC ブラウザ向けのレスポンシブ Web で WCAG 2.1 AA を目標にする。突合の表は未突合件数と食い違いのある取引先を先頭に、一致済みの明細は畳む部品とする。

#### State and data flow

状態管理は最小限のグローバルストアに留め、正本は API 側に置く。食い違いは金額の大きい順に並べ、取引先の住所などは突合画面に持たない。

#### Backend integration

FastAPI の REST API を cookie セッションで呼び、状態変更要求にはセッションごとの CSRF トークンを付ける。トークンはブラウザに置かない (D3)。

#### Performance and observability

画面から呼ぶ API の p95 が 2 秒を超えた状態が 5 分続いたら遅延とみなす暫定閾値を使い、最初の月次締めで実測して見直す。

#### Frontend verification

O2 (月末 3 営業日の表計算への書き出し 0 回) を突合画面だけで達成できるかを、稼働後最初の月次締めから観測する。

### Backend architecture

#### Runtime and architecture pattern

Python/FastAPI の REST API が BFF として OIDC トークンとサーバ側セッションを持つ (D3)。

#### Domain and module boundaries

契約、請求予定、請求書・請求明細、入金消込、突合、確定承認、監査ログのモジュールに分ける。

#### API and service contracts

請求書の一覧 (ページ分割) と登録・更新、突合の実行と結果の取得、確定の承認、監査ログの検索を提供する。同時更新は後から保存した方を上書きせず競合で止める。

#### Data and transaction behavior

業務更新と job_outbox への投入を同じ transaction で行う。確定済み請求書は更新せず、取り消しと新規の請求書を発行する。

#### Async processing

Python worker Deployment が job_outbox を 1 秒間隔で claim して重い突合と手動の再検査を処理し、15 分ごとの請求漏れ走査は CronJob で起動する (D4)。

#### Security and resilience

DB claim の排他・lease/fencing token・業務の一意キーで冪等にし、再試行による業務効果の二重反映を禁止する。リトライ上限と失敗状態を保存する。

#### Operations and verification

請求漏れは期限超過から 30 分以内に担当者の画面の一覧へ出ることを確かめ、O1 (締め後に残る請求漏れ月次 0 件) を観測する。

### Infrastructure architecture

#### Environments and topology

社内 k8s 上で動かし、社内ネットワークからだけ利用する。

#### Compute and storage

API と worker のコンテナ、CronJob を社内 k8s に置き、データベースは情報システム部提供の PostgreSQL 16 を使う。Redis などの新しい保存基盤は足さない。

#### IaC and delivery

CI/CD は会社契約の GitHub Actions でコンテナを作り社内 k8s へデプロイする。

#### Secrets and access

OIDC のトークンはバックエンドだけが持つ。情報システム部は運用だけを行い請求データは見られない。

#### Reliability and recovery

セッションを DB に置くので Pod の再起動や複数 replica でもログインが切れない。日次バックアップとロールバック手順で回復する。

#### Infrastructure verification

社内監視基盤でコンテナの死活とエラー率を見る。5xx エラー率が 5 分間で 1% を超えたら異常とし、オンコール輪番へ通知する。

### Data architecture

#### Data domains and ownership

請求・監査データは本システムの PostgreSQL 16 を唯一の情報源とする (G1)。ユーザー・請求・監査ログの領域を持つ。

#### Logical and physical model

取引先・契約・請求予定 (契約ID・対象年月・予定請求期限・期待明細)・請求書・請求明細・入金・突合結果・監査ログ・セッション・job_outbox の表を持つ。

#### Access and consistency

トランザクションと制約で整合を保ち、同時更新は競合として止める。担当外の取引先の請求は認可で見せない。

#### Lifecycle and governance

監査ログは追記のみで削除・改ざんしない。セッションは 8 時間で期限切れを定期的に消し、ログアウトで即時無効化する。

#### Migration and recovery

版番号付き移行スクリプトで変更し、本番適用前に必ずバックアップを取る。請求・監査データは日次でバックアップし (I1)、週次でリストア訓練を行う。

#### Data verification

週次リストア訓練でバックアップから復元できることを確かめ、突合で食い違いが記録されることを月次で観測する。

### Security architecture

#### Assets, actors and threat model

資産は確定請求金額と監査ログ。脅威は確定金額の書き換え、退職者・異動者アカウントの残存利用、権限設定ミスによる担当外取引先の閲覧・修正、監査ログの削除・改ざん。

#### Identity and authorization

社内 IdP の OIDC でログインし、ロールベース認可で担当・リーダー・内部監査室・情報システム部の権限を分ける。IdP でアカウントが無効になれば本システムにも入れない。

#### Data and secret protection

通信は TLS1.3。cookie は HttpOnly・Secure・SameSite=Lax で、トークンはブラウザに出さない。

#### Application and supply-chain controls

入力検証と OWASP Top10 の受動対策を行い、状態変更要求には CSRF synchronizer token を必須にする。

#### Detection and response

すべての操作を追記のみの監査ログに残し、内部監査室が閲覧する。異常はオンコール輪番が runbook に沿って対応する。

#### Security verification

担当外取引先へのアクセス拒否、CSRF トークンの無い要求の拒否、アカウント無効化後の締め出し、監査ログが追記のみであることを検証する。

## Architecture decisions

D1 PostgreSQL 16 (qa-031)。D2 React + TypeScript の SPA (qa-032)。D3 バックエンドがトークンを持ちブラウザには cookie セッションだけを渡す bff-session (qa-034)。D4 既存 PG outbox + 独立 Python worker + k8s CronJob の pg-worker-cron (qa-job-choice-fixture-v3)。

## Delivery, migration and rollback

GitHub Actions でコンテナを作り社内 k8s へデプロイする。データ構造の変更は版番号付き移行スクリプトで行い、本番適用前に必ずバックアップを取り、ロールバック手順を同時に用意する。

## Risks and verification

リスク (system-spec/security.md): 確定金額の書き換え、退職者・異動者のアカウント残存、権限設定ミスによる担当外取引先の閲覧・修正、監査ログの削除・改ざん。検証: O1/O2 の月次観測、暫定性能閾値の最初の月次締めでの実測と見直し、週次リストア訓練。


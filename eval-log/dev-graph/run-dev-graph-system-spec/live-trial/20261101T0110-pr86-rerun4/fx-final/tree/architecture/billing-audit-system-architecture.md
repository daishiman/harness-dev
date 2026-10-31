---
graph_node_id: "arch-billing-audit-system-architecture"
artifact_kind: "architecture"
artifact_subtypes: ["frontend", "backend", "infrastructure", "data", "security"]
title: "請求・監査統合 Web システム アーキテクチャ (要件定義書取込)"
project_id: "billing-audit"
domain: "billing"
status: "done"
priority: null
start_date: null
target_date: null
iteration: null
owners: []
tags: []
file_path: "architecture/billing-audit-system-architecture.md"
template_id: "architecture"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluated_digest": "1cc7fe6bd148679b1bb2450fbc61c8dfad42ae7edbcee6bd0463711c3ffa1402", "evaluator": "system-spec-harness:assign-system-spec-completeness-evaluator", "evidence_ref": "eval-log/system-spec-completeness-report.json"}
source_lineage: {"imported_at": "2026-10-31T17:42:36Z", "origin_kind": "system-spec-harness", "source_digest": "1cc7fe6bd148679b1bb2450fbc61c8dfad42ae7edbcee6bd0463711c3ffa1402", "source_path": "system-spec/00-requirements-definition.md", "source_plugin": "system-spec-harness", "source_version": "0.1.24"}
created_at: "2026-10-31T17:45:00.166854Z"
updated_at: "2026-10-31T17:45:00.166854Z"
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
classification_confidence: 0.92
classification_reason: "system-spec-harness の要件定義書 (system-spec/00-requirements-definition.md) は U1-U9 と確定意思決定 D1-D3 (DB 版・画面方式・トークン保持) を持つシステム全体の構成判断の憲法。C19 R3 の取込規則で要件定義書は architecture へ写す"
classification_candidates: [{"artifact_kind": "architecture", "candidate_path": "architecture/billing-audit-system-architecture.md", "confidence": 0.92}, {"artifact_kind": "specification", "candidate_path": "specs/billing-audit-system-architecture.md", "confidence": 0.35}, {"artifact_kind": "document", "candidate_path": "docs/billing-audit-system-architecture.md", "confidence": 0.15}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-10-31T17:45:00.166854Z", "missing_sections": [], "status": "complete"}
---

# Architecture overview

社内向け Web システム。React + TypeScript の SPA (D2) が FastAPI のバックエンドを cookie セッション付きで呼び、バックエンドが社内 IdP の OIDC トークンを保持する (D3)。データは情報システム部提供の PostgreSQL 16 (D1) に集約し、社内 k8s 上でコンテナとして稼働する (U8)。章の正本は system-spec/*.md。

## Context and drivers

- 部署ごとの表計算と個別ツールの乱立で、請求漏れが毎月見つかり、監査のたびに資料を集め直している (U2)
- 制約: 社内 k8s・社内 IdP の OIDC・Python/FastAPI・GitHub Actions・情報システム部提供の PostgreSQL (U8)

## Goals and non-goals

- Goals: G1 請求・監査データを単一の信頼できる情報源へ統合する / G2 主要業務動線を Web だけで完結できるようにする (U3)
- Non-goals: 給与計算、モバイル・タブレット・デスクトップアプリ (U7, qa-000)

## System context and boundaries

- 利用者: 請求担当 40 名・経理チームのリーダー・内部監査室 (qa-016)。請求担当は社内ネットワークにつないだ PC のブラウザから使い、社外・スマートフォンからは使わない (qa-020)
- 外部系: 社内 IdP (OIDC)、情報システム部の監視基盤と PostgreSQL、社内チャットとメール (通知)
- 境界: 給与計算システムとは連携しない (U7)

## Container and component view

- SPA (React + TypeScript、最小限のグローバルストア, qa-007, qa-032)
- API (FastAPI、REST、BFF としてセッションと OIDC トークンを保持, qa-006, qa-034)
- ワーカー (突合などの非同期ジョブ、キュー経由, qa-025)
- DB (PostgreSQL 16: ユーザー/請求/監査ログのスキーマとセッション表, qa-001, qa-031, qa-038)

## Cross-cutting contracts

- 認証: OIDC + サーバ側セッション 8 時間、CSRF synchronizer token (qa-002, qa-037)
- 監査: 全操作を追記のみの監査ログへ (I3)
- 監視: p95 2 秒・5xx 1% の 5 分閾値でオンコール通知 (qa-035, qa-036)

## Subtype architecture

合成対象の subtype と該当テンプレート:

- Frontend: 合成済み (`architecture-frontend.md`)
- Backend: 合成済み (`architecture-backend.md`)
- Infrastructure: 合成済み (`architecture-infrastructure.md`)
- Data: 合成済み (`architecture-data.md`)
- Security: 合成済み (`architecture-security.md`)

### Frontend architecture

#### Rendering and application pattern

React + TypeScript の SPA (D2, qa-032)。社内ネットワークの PC ブラウザ向けレスポンシブ Web (qa-003, qa-020)

#### Routes, screens and navigation

請求書一覧・登録更新、突合、確定承認、監査ログ検索の画面。主要動線は 3 クリック以内 (qa-003, qa-025)

#### Component and design-system boundaries

突合画面は未突合件数と食い違い取引先を先頭に、食い違いを金額の大きい順に並べ、一致済み明細を畳む (I2, qa-028)。WCAG 2.1 AA 目標 (qa-003)

#### State and data flow

状態管理は最小限のグローバルストア (qa-007)。サーバ状態は API から取得し、トークンはブラウザに持たない (D3)

#### Backend integration

API を cookie 付きで呼び、状態変更要求には CSRF トークンを付ける (qa-034, qa-037)。一覧はページ分割取得 (qa-025)

#### Performance and observability

画面から呼ぶ API の p95 2 秒超 5 分継続を遅延とみなす (qa-035)。月末 3 営業日の集中利用を前提にする (qa-019)

#### Frontend verification

O2 (月末の表計算書き出し 0 回) と I2 の並び順を受入条件にする。詳細は system-spec/frontend.md と system-spec/ui-ux.md

### Backend architecture

#### Runtime and architecture pattern

Python/FastAPI の REST API と非同期ジョブ (キュー) のワーカー (qa-006)。BFF としてセッションと OIDC トークンを保持 (D3)

#### Domain and module boundaries

取引先・契約・請求書・請求明細・入金・突合・監査ログ (qa-024)

#### API and service contracts

請求書の一覧 (ページ分割) と登録・更新、突合の実行と結果取得、確定の承認、監査ログの検索 (qa-025)

#### Data and transaction behavior

同時更新は後から保存した側を止める楽観的排他 (qa-025)。確定済み請求書は書き換えず赤黒訂正 (qa-024)

#### Async processing

突合などの重い処理はキュー経由の非同期ジョブで実行し、同じ処理の二重起動を防ぐ (qa-025)

#### Security and resilience

ロールベース認可と担当取引先の境界 (qa-026)、CSRF synchronizer token (qa-037)、入力検証と OWASP Top10 受動対策 (qa-004)

#### Operations and verification

社内 k8s 上で稼働し、死活とエラー率を監視する (qa-029)。詳細は system-spec/backend.md

### Infrastructure architecture

#### Environments and topology

社内 k8s 上のコンテナ (qa-005, U8)。社内ネットワーク内からのみ利用 (qa-020)

#### Compute and storage

API とワーカーは k8s の Pod。DB は情報システム部提供の PostgreSQL 16 (D1)。セッションも DB の表に置き、Pod のメモリに置かない (qa-038)

#### IaC and delivery

CI/CD は GitHub Actions でコンテナをビルドし社内 k8s へデプロイ (qa-005)

#### Secrets and access

OIDC のクライアント資格情報とトークンはバックエンド側だけが持つ (D3)。情報システム部は請求データを見ない (qa-026)

#### Reliability and recovery

日次バックアップ (I1)、週次リストア訓練、オンコール輪番と障害 runbook (qa-008)

#### Infrastructure verification

監視基盤でコンテナの死活とエラー率を監視し、閾値超過でその週の担当へ通知する (qa-029, qa-035, qa-036)。詳細は system-spec/infrastructure.md

### Data architecture

#### Data domains and ownership

ユーザー・請求・監査ログの 3 スキーマ (qa-001)。請求データの入力・突合は担当取引先ごとに請求担当、確定の承認は経理チームのリーダーだけが行う。内部監査室はすべてを閲覧できるが変更できず、情報システム部は請求データを見られない (qa-026)

#### Logical and physical model

取引先 1-n 契約 1-n 請求書 1-n 請求明細、入金は請求書へ消し込み、突合は月ごとに食い違いを記録 (qa-024)。PostgreSQL 16 (D1)

#### Access and consistency

トランザクションと制約で単一の信頼できる情報源を保つ (G1)。同時更新は楽観的排他 (qa-025)

#### Lifecycle and governance

確定済み請求書は書き換えず赤黒訂正、監査ログは追記のみで削除・改ざん不可 (I3, qa-024)。セッションは 8 時間で失効し定期削除 (qa-038)

#### Migration and recovery

版番号付き移行スクリプト、本番前のバックアップと戻し手順 (qa-027)、日次バックアップ (I1)

#### Data verification

週次リストア訓練 (qa-008) と請求漏れ自動検知 (O1)。詳細は system-spec/database.md

### Security architecture

#### Assets, actors and threat model

保護対象は確定請求金額と監査ログ。脅威は金額の書き換え、退職者アカウントの残存、権限設定ミス、監査ログの消去・改ざん (qa-030)

#### Identity and authorization

社内 IdP の OIDC、IdP 無効化で締め出し、ロールベース認可 (qa-002, qa-026)

#### Data and secret protection

TLS1.3 (qa-004)、トークンはサーバ側だけ (D3)、cookie は HttpOnly・Secure・SameSite=Lax (qa-037)

#### Application and supply-chain controls

入力検証と OWASP Top10 受動対策 (qa-004)、状態変更要求の CSRF synchronizer token (qa-037)

#### Detection and response

全操作の監査ログ (qa-024)、監視基盤のアラートとオンコール通知 (qa-036)

#### Security verification

qa-030 の 4 脅威それぞれに対応する統制が働くことを受入時に確認する。詳細は system-spec/security.md と system-spec/auth.md

## Architecture decisions

- D1: PostgreSQL 16 を採用 (qa-031)。15 より保守期間が長く、移行の手間は同じ
- D2: React + TypeScript の SPA を採用 (qa-032)。突合で頁を読み直さずに並べ替えと修正を続けるため
- D3: バックエンドがトークンを持ち、ブラウザには cookie セッションだけを渡す (qa-034)

## Delivery, migration and rollback

- CI/CD は GitHub Actions、社内 k8s へコンテナでデプロイ (qa-005)
- データ構造の変更は版番号付き移行スクリプトで行い、本番前に必ずバックアップ、戻し手順を同梱 (qa-027)

## Risks and verification

- Risks: 確定金額の書き換え、退職者アカウントの残存、権限設定ミスによる担当外閲覧、監査ログの消去・改ざん (qa-030)
- Verification: U5 成功基準 (3 か月連続で請求漏れ 0 件・表計算書き出し 0 回) と週次リストア訓練 (qa-008)、完成度評価 PASS (eval-log/system-spec-completeness-report.json)

## U1 本質的目的 (essential_purpose)

請求の数字を、誰が見ても同じだと信じられる状態にする。そのための手段として、表計算と監査台帳への二重管理をやめ、請求と監査を 1 つの Web システムへ統合する

## U2 背景 (background)

部署ごとに表計算と個別ツールが増え、請求漏れが毎月のように見つかり、監査のたびに資料を集め直している。月末 3 営業日は突合の残業が続き、今の人数では回らない

## U3 ゴール (goals)

| ID | ゴール |
|---|---|
| G1 | 請求・監査データを単一の信頼できる情報源へ統合する |
| G2 | 主要業務動線を Web だけで完結できるようにする |

## U4 目標 (objectives)

| ID | 目標 | 測定基準 |
|---|---|---|
| O1 | 請求漏れをシステムが自動で検知する | 締め後に残る請求漏れ 月次 0 件 (稼働後最初の月次締めから計測) |
| O2 | 月末の突合を表計算に書き出さずに終える | 月末 3 営業日の表計算への書き出し 0 回 (稼働後最初の月次締めから計測) |

## U5 成功基準 (success_criteria)

- 稼働後 3 か月連続で、締め後に残る請求漏れが 0 件
- 同じ 3 か月間、月末の突合を表計算に書き出さずに終えている

## U6 ステークホルダー (stakeholders)

- 経理チームの請求担当 40 名 (日々の利用者)
- 経理チームのリーダー (請求の確定を承認)
- 内部監査室 (監査ログを閲覧)
- 情報システム部 (社内 k8s と社内 IdP を運用)

## U7 スコープ (scope)

- 対象 (in): 請求の入力, 月末の突合, 請求の確定, 監査ログの記録と閲覧
- 対象外 (out): 給与計算 (人事部の別システム), モバイル・タブレット・デスクトップアプリ (Web のみ, qa-000)

## U8 制約 (constraints)

- 社内 k8s で稼働する (社内規程)
- ログインは社内 IdP の OIDC (社内規程)
- バックエンドは Python/FastAPI (保守体制)
- CI/CD は GitHub Actions (会社契約)
- データベースは情報システム部提供の PostgreSQL (提供版 15 と 16。版は D1 で 16)

## U9 具体的にやりたいこと (concrete_intents)

| ID | やりたいこと | 資するゴール |
|---|---|---|
| I1 | 請求・監査データを日次でバックアップする | G1 |
| I2 | 突合画面は未突合件数と食い違いのある取引先を先頭に出し、食い違いを金額の大きい順に並べ、一致済みの明細は畳む | G2 |
| I3 | 確定した請求書は書き換えず赤黒訂正で直し、監査ログは追記のみとする | G1 |


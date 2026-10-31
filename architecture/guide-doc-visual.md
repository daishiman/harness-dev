---
graph_node_id: "arch-guide-doc-visual"
artifact_kind: "architecture"
artifact_subtypes: ["frontend"]
title: "資料生成の描画と検査の責務設計"
project_id: "guide-doc-generator"
domain: "documentation"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["visual-expression", "mvp-review"]
file_path: "architecture/guide-doc-visual.md"
template_id: "architecture"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-10-31T09:58:26.388836Z"
updated_at: "2026-10-31T09:58:26.388836Z"
depends_on: ["spec-guide-doc-visual"]
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
classification_confidence: 0.99
classification_reason: "既存資料生成プラグインの差分を目的別の正規成果物として記録する。"
classification_candidates: [{"artifact_kind": "architecture", "candidate_path": "architecture/guide-doc-visual.md", "confidence": 0.99}, {"artifact_kind": "document", "candidate_path": "docs/guide-doc-visual.md", "confidence": 0.01}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-10-31T09:58:26.388836Z", "missing_sections": [], "status": "complete"}
---

# Architecture overview

Python標準ライブラリの決定論生成と、構成設計・意味レビューを分離する静的HTML資料生成。

## Context and drivers

長文の羅列、図の誤った順序、文字の縮小、線の断絶、配色のずれ、補足の操作負担を減らす。

## Goals and non-goals

読者が関係を短時間で理解できることと再生成の一致が目標。万能な自動図種判定、外部描画CDN、資料固有データの公開は対象にしない。

## System context and boundaries

C05設計→C12正規化→C13素材埋込→C11描画→C16/C17/C18/C22検査→C19配置。専用作図は事前描画した素材として入口を統一する。

## Container and component view

HTML/CSS部品は比較・カード・ステップ等を担い、C14は必要な関係図を担う。SVGも画像も共通の拡大UIへ接続する。

## Cross-cutting contracts

handout-diagrams.jsonが図種と関係候補、visual-policyが表示基準、schemaが入力構造の正本。選定の形式検査と意味判断は別責務。

## Subtype architecture

合成対象の subtype と該当テンプレート:

- Frontend: 合成済み (`architecture-frontend.md`)
- Backend: N/A: subtype 非選択
- Infrastructure: N/A: subtype 非選択
- Data: N/A: subtype 非選択
- Security: N/A: subtype 非選択

### Frontend architecture

#### Rendering and application pattern

静的・自己完結HTML。外部ランタイムを増やさず、既存のCSS変数とDOM操作を使う。確認幅は1440/768/375px。

#### Routes, screens and navigation

単一文書の節IDを維持し、目次から実際の固定ナビ高さを引いて移動する。全節数を表示し、現在地を返す。

#### Component and design-system boundaries

比較表・カード・手順・実習・補足・図の共通部品をC11が生成する。実習の3項目と見出し、最小文字、色と線を共通化する。

#### State and data flow

構成JSONが本文の正本。詳細の開閉と拡大はブラウザ状態、メモは既存localStorage。図の拡大終了時は焦点を復帰する。

#### Backend integration

N/A: バックエンドAPIはない。画像はdata URIへ埋め込み、外部取得を発生させない。

#### Performance and observability

不要な新規依存を追加しない。大きい素材はサイズを記録し、生成物ハッシュと実表示証跡で結果を確認する。

#### Frontend verification

関係の不正入力、素材の幅、選定のハッシュ、再生成、キーボード、狭幅、印刷状態復元を対象にする。

## Architecture decisions

意味と描画媒体を別に選ぶ。単純な受け渡しは狭幅で読めるHTML手順にもできる。密な関係図を縮小して文字を犠牲にせず、分図または内部移動を使う。

## Delivery, migration and rollback

構成と素材から生成し、選定記録をC19で同梱する。既存資料はバックアップ後に該当ファイルだけ反映し、ロールバックはバックアップかPRのrevertで行う。

## Risks and verification

大きな図は横移動が必要になる。実画面の先頭・末尾を確認して可読性を判断する。HTMLだけの逆抽出は別件harness-ws7jを保持する。


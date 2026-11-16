---
graph_node_id: "ARCH-LT-001"
artifact_kind: "architecture"
artifact_subtypes: ["backend"]
title: "配信グラフ基盤 backend architecture"
project_id: "gm4b-render"
domain: "delivery-graph"
status: "active"
priority: "medium"
start_date: null
target_date: null
iteration: null
owners: ["harness maintainers"]
tags: ["live-trial", "render"]
file_path: "architecture/ARCH-LT-001.md"
template_id: "architecture"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluator": "run-dev-graph-node/R4-apply-template", "evidence_ref": ".dev-graph/cache/content-review/ARCH-LT-001.json", "evaluated_digest": "d3c8a29c4cfe3af72249da54d76f54738ec4286b21e0bd84479d1cc16d7c3763"}
source_lineage: {"origin_kind": "manual", "source_plugin": null, "source_path": null, "source_version": null, "source_digest": null, "imported_at": null}
created_at: "2026-09-07T06:10:00Z"
updated_at: "2026-09-07T06:10:00Z"
depends_on: []
related_nodes: []
resource_scope: ["architecture/", "scripts/"]
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
classification_reason: "本文が architecture template の必須 section 構成と一致し、第二候補との margin が閾値を超えるため自動確定した"
classification_candidates: [{"artifact_kind": "architecture", "confidence": 0.96, "candidate_path": "architecture/ARCH-LT-001.md"}, {"artifact_kind": "document", "confidence": 0.21, "candidate_path": "docs/ARCH-LT-001.md"}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": null}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"policy": "manual", "status": "not_applicable", "source": null, "completed_at": null, "reconciled_at": null, "evidence_refs": []}
implementation_readiness: {"status": "complete", "missing_sections": [], "checked_at": "2026-09-07T06:10:00Z"}
---

# Architecture overview

live-trial fixture gm4b-render の配信グラフ基盤。dev-graph の canonical graph store を単一
authority とし、静的 render 成果物を repo-local に閉じた形で提供する backend 中心の構成を採る。

## Context and drivers

- 駆動要因: graph 実値 (feature 進捗と task 依存) を外部 resource 参照なしで可視化する必要がある。
- 制約: 出力は zero-dependency な単一 HTML であり、CDN・外部 font・外部 script を参照しない。

## Goals and non-goals

- Goal: canonical graph から決定論的に inline SVG を生成し、同一入力で同一 digest を返す。
- Non-goal: 双方向同期、live server、GitHub Projects 連携はこの feature の対象にしない。

## System context and boundaries

- 上流: C02 単一 writer が書いた `.dev-graph/state/graph.json`。
- 下流: `.dev-graph/render/index.html` を開く人間の閲覧者。
- 境界: repository 外の path を読み書きしない。

## Container and component view

- graph store: `.dev-graph/state/graph.json` (JSON, 単一 writer)。
- renderer: `scripts/render-graph-html.py` (pure function, stdout に JSON receipt)。
- receipt store: `.dev-graph/state/` 配下の immutable receipt 群。

## Cross-cutting contracts

- determinism: 同一 graph bytes から同一 output bytes を返す。
- containment: 全 read/write path が repository root 配下に収まる。
- fail-closed: dangling dependency と dangling parent_feature は render を中断させる。

## Subtype architecture

### Backend architecture

- Runtime and architecture pattern: Python 3.10 以上の標準ライブラリのみで動く batch 変換。
- Domain and module boundaries: graph 正規化、進捗集計、HTML 生成の 3 段に分離する。
- API and service contracts: CLI 引数 `--graph` と `--out`、stdout の JSON receipt が対外契約。
- Data and transaction behavior: 入力は読取専用、出力は temp file への書込みと os.replace で原子的に確定する。
- Async processing: 非同期処理を持たない同期 batch とする。
- Security and resilience: network 無効、secret 非保持、入力 JSON 破損時は非零 exit で停止する。
- Operations and verification: 二回連続実行して output digest 一致を確認する。

## Architecture decisions

- AD-01: 外部 CSS/JS を使わず inline style と inline SVG だけで描画する。
- AD-02: 進捗は parent_feature 参照から実数で集計し、事前計算値を graph に持たせない。

## Delivery, migration and rollback

- Delivery: plugin 同梱 script をそのまま実行し、追加 install 手順を持たない。
- Migration: 既存 render 出力は上書きで置換し、履歴は git に委ねる。
- Rollback: 直前 commit の HTML を復元するだけで戻せる。

## Risks and verification

- Risk: graph に dangling 参照が入ると render が失敗する。検証: C11 gate を commit 前に通す。
- Risk: 非決定論的な出力順序。検証: node id 昇順ソートを固定し digest 一致を二回実行で確認する。

---
graph_node_id: "FEATURE-1"
artifact_kind: "feature"
artifact_subtypes: []
title: "UTF-8 text line-count CLI"
project_id: "project"
domain: "system"
status: "active"
owners: ["team"]
tags: []
priority: null
start_date: null
target_date: null
iteration: null
created_at: "2026-07-13T00:00:00Z"
updated_at: "2026-07-13T00:00:00Z"
depends_on: []
related_nodes: []
resource_scope: []
parent_feature: null
feature_package_id: null
phase_ref: null
file_path: "features/FEATURE-1.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluator": "reviewer", "evidence_ref": "evidence/feature.json", "evaluated_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
source_lineage: {"origin_kind": "manual", "source_plugin": null, "source_path": null, "source_version": null, "source_digest": null, "imported_at": null}
classification_confidence: 1.0
classification_reason: "explicit fixture"
classification_candidates: []
github_publication: {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": null}
issue_linkage: null
tracker_binding: "none"
beads_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"policy": "linked_pr_merged_all", "status": "in_progress", "source": null, "completed_at": null, "reconciled_at": null, "evidence_refs": []}
implementation_readiness: {"status": "complete", "missing_sections": [], "checked_at": "2026-07-13T00:00:00Z"}
purpose: "UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。"
goal: "python3 src/utf8_line_count.py PATH がAC01..AC09を満たし、CLI利用説明と検証記録を伴うローカル配布ZIPとして引き渡せる状態。"
scope_in: ["1ファイルpathのCLI入力", "UTF-8 strictとuniversal newlineの逐次カウント", "整数と改行だけの成功出力", "入力/復号/usage失敗時exit 2", "stdlib unittestとローカルZIP・手動利用説明"]
scope_out: ["stdin・複数ファイル・再帰探索", "GUI・HTTP API・DB・認証", "Windowsでの動作保証", "pip公開・クラウドdeploy・実GitHub/Beads mutation"]
acceptance: ["AC01: 空UTF-8ファイルはstdoutが0と改行、exit 0。", "AC02: a\\nb\\nは2行、a\\nbも末尾改行なしで2行。", "AC03: 日本語の2行は文字数によらず2。UTF-8 strictで読む。", "AC04: LF・CRLF・単独CRをPython universal newlineの1境界として扱う。", "AC05: 存在しないpath・directory・権限拒否はstdout空、stderrに説明、exit 2、traceback無し。", "AC06: 不正UTF-8はstdout空、stderrに説明、exit 2、traceback無し。", "AC07: 引数が0件または2件以上ならusageをstderrへ出しexit 2、stdout空。", "AC08: 入力ファイルのbytesを変更せず、外部network・DB・認証・サービスを使わない。", "AC09: ファイルを行iteratorで読み、ファイル全体readで保持しない。カウンタ以外の追加メモリは1行分。"]
architecture_refs: ["architecture-system"]
---

# UTF-8 text line-count CLI

## 目的

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。 python3 src/utf8_line_count.py PATH がAC01..AC09を満たし、CLI利用説明と検証記録を伴うローカル配布ZIPとして引き渡せる状態。
A1: argparse path1件。A2: UTF-8 strict / universal newline / 行iterator。A3: stdout数値+LF、またはstderr説明+exit 2。
根拠: system-spec/index.md、system-spec/requirements.md AC01..AC09。外部service無し。

## 到達状態

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。 python3 src/utf8_line_count.py PATH がAC01..AC09を満たし、CLI利用説明と検証記録を伴うローカル配布ZIPとして引き渡せる状態。
A1: argparse path1件。A2: UTF-8 strict / universal newline / 行iterator。A3: stdout数値+LF、またはstderr説明+exit 2。
根拠: system-spec/index.md、system-spec/requirements.md AC01..AC09。外部service無し。

## スコープ

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。 python3 src/utf8_line_count.py PATH がAC01..AC09を満たし、CLI利用説明と検証記録を伴うローカル配布ZIPとして引き渡せる状態。
A1: argparse path1件。A2: UTF-8 strict / universal newline / 行iterator。A3: stdout数値+LF、またはstderr説明+exit 2。
根拠: system-spec/index.md、system-spec/requirements.md AC01..AC09。外部service無し。

## 受入

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。 python3 src/utf8_line_count.py PATH がAC01..AC09を満たし、CLI利用説明と検証記録を伴うローカル配布ZIPとして引き渡せる状態。
A1: argparse path1件。A2: UTF-8 strict / universal newline / 行iterator。A3: stdout数値+LF、またはstderr説明+exit 2。
根拠: system-spec/index.md、system-spec/requirements.md AC01..AC09。外部service無し。

## アーキテクチャ参照

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。 python3 src/utf8_line_count.py PATH がAC01..AC09を満たし、CLI利用説明と検証記録を伴うローカル配布ZIPとして引き渡せる状態。
A1: argparse path1件。A2: UTF-8 strict / universal newline / 行iterator。A3: stdout数値+LF、またはstderr説明+exit 2。
根拠: system-spec/index.md、system-spec/requirements.md AC01..AC09。外部service無し。

## 機能間依存

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。 python3 src/utf8_line_count.py PATH がAC01..AC09を満たし、CLI利用説明と検証記録を伴うローカル配布ZIPとして引き渡せる状態。
A1: argparse path1件。A2: UTF-8 strict / universal newline / 行iterator。A3: stdout数値+LF、またはstderr説明+exit 2。
根拠: system-spec/index.md、system-spec/requirements.md AC01..AC09。外部service無し。

## Handoff

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。 python3 src/utf8_line_count.py PATH がAC01..AC09を満たし、CLI利用説明と検証記録を伴うローカル配布ZIPとして引き渡せる状態。
A1: argparse path1件。A2: UTF-8 strict / universal newline / 行iterator。A3: stdout数値+LF、またはstderr説明+exit 2。
根拠: system-spec/index.md、system-spec/requirements.md AC01..AC09。外部service無し。

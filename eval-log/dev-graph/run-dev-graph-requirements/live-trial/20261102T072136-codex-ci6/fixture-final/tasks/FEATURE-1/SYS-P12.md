---
graph_node_id: "SYS-P12"
artifact_kind: "task"
artifact_subtypes: []
title: "利用と保守を説明 (UTF-8 line-count)"
project_id: "feature-package-feat"
domain: "documentation"
status: "active"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["team"]
tags: ["p12"]
file_path: "tasks/FEATURE-1/SYS-P12.md"
template_id: "task"
template_version: "1.1.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluated_digest": "df0004510031618ff0b0d6f485eb6a9973f84c4e60ec09c51e24e4cf13f89282", "evaluator": "system-dev-plan-evaluator", "evidence_ref": ".dev-graph/plans/generations/feature-package-feat/df0004510031618ff0b0d6f485eb6a9973f84c4e60ec09c51e24e4cf13f89282/plan-findings.json"}
source_lineage: {"imported_at": "2026-11-02T07:22:50Z", "origin_kind": "system-dev-planner", "source_digest": "df0004510031618ff0b0d6f485eb6a9973f84c4e60ec09c51e24e4cf13f89282", "source_path": ".dev-graph/plans/generations/feature-package-feat/df0004510031618ff0b0d6f485eb6a9973f84c4e60ec09c51e24e4cf13f89282/task-specs/phase-12-documentation-operations.md", "source_plugin": "system-dev-planner", "source_version": "0.1.0"}
created_at: "2026-11-02T07:22:50Z"
updated_at: "2026-11-02T07:22:50Z"
depends_on: ["SYS-P11"]
related_nodes: []
resource_scope: ["docs/README-utf8-lines.md", "evidence/utf8-lines/P12.json", "evidence/utf8-lines/P12/", "examples/input.txt"]
purpose: null
goal: null
scope_in: []
scope_out: []
acceptance: []
architecture_refs: []
parent_feature: "FEATURE-1"
feature_package_id: "feature-package/feat"
phase_ref: "P12"
classification_confidence: 1
classification_reason: "UTF-8 CLI単一機能のP12責務を明示した入力。feature増設ではない。"
classification_candidates: [{"artifact_kind": "task", "candidate_path": "tasks/FEATURE-1/SYS-P12.md", "confidence": 1}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "in_progress"}
implementation_readiness: {"checked_at": "2026-07-13T00:00:00Z", "missing_sections": [], "status": "complete"}
---

# P12 利用と保守を説明

## Machine-readable registration fields

- phase_ref: P12
- feature_package_id: feature-package/feat
- graph_node_id: SYS-P12
- parent_feature: FEATURE-1

## 目的

実行例、成功/失敗exit、UTF-8と改行規則、ファイル不変、ローカルrollbackをREADMEへまとめ、日本語2行の実例で確認する。

## 背景

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。 P01..P13はこの単一CLIの契約だけを実装・検証する。

## 前提条件

- SYS-P11完了と受理証跡を確認して開始する。
- 原goal: goal-spec.json、確定仕様: system-spec/spec-state.json / requirements.md
- このplan inputは未実装。先行phaseの成果物が無ければ実行を止める。

## Workstream applicability

- Documentation: applicable; 実行例、成功/失敗exit、UTF-8と改行規則、ファイル不変、ローカルrollbackをREADMEへまとめ、日本語2行の実例で確認する。
- Frontend: N/A: GUI/HTTPを作らない。
- Infrastructure: N/A: remote deploy/IaC無し。

## Architecture and deploy unit

A1 argparse → A2 UTF-8 stream iterator → A3 stdout/exit。architecture/system.mdを根拠としdeploy unitはutf8-line-count-local-cli。

## 成果物

- Produced artifact: docs/README-utf8-lines.md
- Produced artifact: examples/input.txt
- Produced artifact: evidence/utf8-lines/P12.json
- Write scope: docs/README-utf8-lines.md, evidence/utf8-lines/P12.json, evidence/utf8-lines/P12/, examples/input.txt
- temp/test作業dirはevidence/utf8-lines/P12/配下のみ。code/source全体の変更許可ではない。

## Tracker publication and completion

tracker_binding_intent=none、github publication=local_only。linked_pr_merged_allは将来linked PRがある場合の標準metadata。現在fixtureはplanningだけ、外部Issue/PRを作らず、実行完了やmerge済みを偽装しない。

## Branch and worktree execution

one-task-one-branch、worktree lease required。dev-graph-schedulerがdevgraph/SYS-P12を割当。repository-local claimを正規CLIで取り、別phaseのscopeへ書かない。

## スコープ外

- stdin・複数ファイル・再帰探索
- GUI・HTTP API・DB・認証
- Windowsでの動作保証
- pip公開・クラウドdeploy・実GitHub/Beads mutation
- 未記載path・provider tree・user config・別featureの変更。

## テスト戦略

- テストレベル選定: 単体・結合・境界値・回帰をAC01..09へ割当。
- カバレッジ目標: 80%以上、ただし全ACとエラー分岐は100%の受入caseで確認。
- 層別方針: Backend: API 契約はCLI stdout/stderr/exit。DB 結合はN/A: DB無し。Infrastructure: N/A: IaC/remote無し。
- 保守性制約: pixel位置・DOM構造依存を禁止し、CLIの観測可能な振舞いと入力不変を検査する。

## Verification and evidence

- Automated command: `python3 -B -c 'import subprocess,sys; from pathlib import Path; t=Path('"'"'docs/README-utf8-lines.md'"'"').read_text(); assert all(x in t for x in ('"'"'UTF-8'"'"','"'"'exit 2'"'"','"'"'AC04'"'"')); p=subprocess.run([sys.executable,'"'"'src/utf8_line_count.py'"'"','"'"'examples/input.txt'"'"'],capture_output=True); assert p.returncode==0 and p.stdout==b'"'"'2\n'"'"''`
- 実行cwdはcaller repository。TMPDIRはevidence/utf8-lines/P12/tmpへ向け、必要dirをこの許可内で作る。
- Required evidence: evidence/utf8-lines/P12.json（実行日時/コマンド/exit/実ファイルSHA、失敗も保持）。
- package再検証: `python3 "$SYSTEM_DEV_PLANNER_ROOT/scripts/validate-system-plan.py" --repo-root . --feature-package feature-package/feat`

## Inner goal-seek execution loop

Methodology contract: system-task-goal-seek/v1
Goal: 実行例、成功/失敗exit、UTF-8と改行規則、ファイル不変、ローカルrollbackをREADMEへまとめ、日本語2行の実例で確認する。
原goal/checklist/constraintsを保持し、実結果をrubricへ突合。未達は原因を記録して許可内で修正、rubric verdict=PASSまで最大3回。不可なら停止しPASSを生成しない。
P13 spec/architecture writeback: N/A: P13 owns writeback

## Rollout and rollback

Rollout: このphaseの受理証跡と次phase入力を同じfeatureへ渡す。
Rollback: P12開始前に記録した成果物bytes/shaへ、このwrite_scopeの変更だけを戻す。前phaseの受理結果やsystem sourceを改変せず失敗理由を記録する。

## Handoff

Executor: capability-build/task-graph application-code route。SYS-P12の成果物/検証/証跡が実際に満たされた時だけ次phaseへ。未実行・FAIL・不明をcompleteにしない。

## 参照情報

goal-spec.json / system-spec/index.md / system-spec/spec-state.json / system-spec/requirements.md / architecture/system.md / architecture/graph.json / features/feature.json。全てcaller内、同一AC01..AC09。

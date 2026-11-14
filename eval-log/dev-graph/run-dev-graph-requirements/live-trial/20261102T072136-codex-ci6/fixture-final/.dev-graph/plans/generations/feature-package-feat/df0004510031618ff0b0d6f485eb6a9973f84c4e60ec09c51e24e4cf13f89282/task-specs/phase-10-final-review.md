# P10 最終独立レビュー

## Machine-readable registration fields

- phase_ref: P10
- feature_package_id: feature-package/feat
- graph_node_id: SYS-P10
- parent_feature: FEATURE-1

## 目的

全ACとP01..P09の実証跡を独立contextで確認し、未達ならP13を保留する。

## 背景

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。 P01..P13はこの単一CLIの契約だけを実装・検証する。

## 前提条件

- SYS-P09完了と受理証跡を確認して開始する。
- 原goal: goal-spec.json、確定仕様: system-spec/spec-state.json / requirements.md
- このplan inputは未実装。先行phaseの成果物が無ければ実行を止める。

## Workstream applicability

- Quality: applicable; 全ACとP01..P09の実証跡を独立contextで確認し、未達ならP13を保留する。
- Frontend: N/A: GUI/HTTPを作らない。
- Infrastructure: N/A: remote deploy/IaC無し。

## Architecture and deploy unit

A1 argparse → A2 UTF-8 stream iterator → A3 stdout/exit。architecture/system.mdを根拠としdeploy unitはutf8-line-count-local-cli。

## 成果物

- Produced artifact: docs/final-review-utf8-lines.json
- Produced artifact: evidence/utf8-lines/P10.json
- Write scope: docs/final-review-utf8-lines.json, evidence/utf8-lines/P10.json, evidence/utf8-lines/P10/
- temp/test作業dirはevidence/utf8-lines/P10/配下のみ。code/source全体の変更許可ではない。

## Tracker publication and completion

tracker_binding_intent=none、github publication=local_only。linked_pr_merged_allは将来linked PRがある場合の標準metadata。現在fixtureはplanningだけ、外部Issue/PRを作らず、実行完了やmerge済みを偽装しない。

## Branch and worktree execution

one-task-one-branch、worktree lease required。dev-graph-schedulerがdevgraph/SYS-P10を割当。repository-local claimを正規CLIで取り、別phaseのscopeへ書かない。

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

- Automated command: `python3 -B -c 'import json; from pathlib import Path; v=json.load(open('"'"'docs/final-review-utf8-lines.json'"'"')); assert set(v['"'"'acceptance'"'"'])=={'"'"'AC%02d'"'"'%i for i in range(1,10)}; assert all(x=='"'"'PASS'"'"' for x in v['"'"'acceptance'"'"'].values()); assert all(Path(p).is_file() for p in v['"'"'evidence_refs'"'"'])'`
- 実行cwdはcaller repository。TMPDIRはevidence/utf8-lines/P10/tmpへ向け、必要dirをこの許可内で作る。
- Required evidence: evidence/utf8-lines/P10.json（実行日時/コマンド/exit/実ファイルSHA、失敗も保持）。
- package再検証: `python3 "$SYSTEM_DEV_PLANNER_ROOT/scripts/validate-system-plan.py" --repo-root . --feature-package feature-package/feat`

## Inner goal-seek execution loop

Methodology contract: system-task-goal-seek/v1
Goal: 全ACとP01..P09の実証跡を独立contextで確認し、未達ならP13を保留する。
原goal/checklist/constraintsを保持し、実結果をrubricへ突合。未達は原因を記録して許可内で修正、rubric verdict=PASSまで最大3回。不可なら停止しPASSを生成しない。
P13 spec/architecture writeback: N/A: P13 owns writeback

## Rollout and rollback

Rollout: このphaseの受理証跡と次phase入力を同じfeatureへ渡す。
Rollback: P10開始前に記録した成果物bytes/shaへ、このwrite_scopeの変更だけを戻す。前phaseの受理結果やsystem sourceを改変せず失敗理由を記録する。

## Handoff

Executor: capability-build/task-graph application-code route。SYS-P10の成果物/検証/証跡が実際に満たされた時だけ次phaseへ。未実行・FAIL・不明をcompleteにしない。

## 参照情報

goal-spec.json / system-spec/index.md / system-spec/spec-state.json / system-spec/requirements.md / architecture/system.md / architecture/graph.json / features/feature.json。全てcaller内、同一AC01..AC09。

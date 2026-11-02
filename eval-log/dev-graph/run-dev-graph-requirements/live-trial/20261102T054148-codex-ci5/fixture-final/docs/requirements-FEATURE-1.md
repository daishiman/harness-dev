# FEATURE-1 要件定義・readiness・handoff入口

## 固定入力

- feature: FEATURE-1
- package: feature-package/feat
- source_digest: d716ee132ac54c611c0869e8e90b32c7be485d5b53b238845658b1ada136a093
- graph_snapshot_digest: sha256:7011ea840d6edc7f85d3b7c822de86c8034274a7b89ec579a3ff5381257c5e1d
- graph_revision: 2
- readiness_digest（C11・C02共通）: sha256:9f03cc54090768b5d195625dd5156fff969cb052976ed758cd11ff1577cf5be3

## 要件と参照元

対象は[確定feature](../features/FEATURE-1.md)のsystem範囲とし、unrelatedを除外する。目的はfeatureの提供、ゴールは完了、受入条件は原文の `accepted` に固定する。入力は試行用の抽象的な仕様であり、具体的な製品機能を補作しない。

[architecture](../architecture/system.md)、[system-spec入口](../system-spec/index.md)、[要件定義](../system-spec/00-requirements-definition.md)、[completeness](../system-spec/completeness-findings.json)を参照する。graph内のartifact kindはfeature・architecture・taskであり、issue・specificationのnodeは存在しない。存在しないnodeやC19 lineageを補作しない。package memberのlineage ownerはsystem-dev-planner。

[package](../.dev-graph/plans/generations/feature-package-feat/d716ee132ac54c611c0869e8e90b32c7be485d5b53b238845658b1ada136a093/feature-package.json)、[inventory](../.dev-graph/plans/generations/feature-package-feat/d716ee132ac54c611c0869e8e90b32c7be485d5b53b238845658b1ada136a093/workstream-inventory.json)、[DAG](../.dev-graph/plans/generations/feature-package-feat/d716ee132ac54c611c0869e8e90b32c7be485d5b53b238845658b1ada136a093/task-graph.json)からP01..P13を消費する。task specの再生成は行わない。

## readiness matrix・追跡表

| phase | source task | verdict | missing_sections |
|---|---|---|---|
| P01 | [SYS-P01](../tasks/FEATURE-1/SYS-P01.md) | ready | [] |
| P02 | [SYS-P02](../tasks/FEATURE-1/SYS-P02.md) | ready | [] |
| P03 | [SYS-P03](../tasks/FEATURE-1/SYS-P03.md) | ready | [] |
| P04 | [SYS-P04](../tasks/FEATURE-1/SYS-P04.md) | ready | [] |
| P05 | [SYS-P05](../tasks/FEATURE-1/SYS-P05.md) | ready | [] |
| P06 | [SYS-P06](../tasks/FEATURE-1/SYS-P06.md) | ready | [] |
| P07 | [SYS-P07](../tasks/FEATURE-1/SYS-P07.md) | ready | [] |
| P08 | [SYS-P08](../tasks/FEATURE-1/SYS-P08.md) | ready | [] |
| P09 | [SYS-P09](../tasks/FEATURE-1/SYS-P09.md) | ready | [] |
| P10 | [SYS-P10](../tasks/FEATURE-1/SYS-P10.md) | ready | [] |
| P11 | [SYS-P11](../tasks/FEATURE-1/SYS-P11.md) | ready | [] |
| P12 | [SYS-P12](../tasks/FEATURE-1/SYS-P12.md) | ready | [] |
| P13 | [SYS-P13](../tasks/FEATURE-1/SYS-P13.md) | ready | [] |

正規validate-readiness-binding.pyはexit 0、violations=[]、system_plan.status=pass、C11.status=pass。正規guard-requirements-handoff.pyはexit 0、graph.digest_match=true、handoff_count=13、blocked=[]、missing_sections=[]。closureは上記13 task・FEATURE-1・architecture-systemの15 nodeで全件ready。

## capability-build/task-graph build handoff

consumer: capability-build/task-graph build。対象集合はSYS-P01..SYS-P13の13件。feature・package・source_digest・graph_snapshot_digestは「固定入力」と同一値を使用する。[上流system-build-handoff](../.dev-graph/plans/generations/feature-package-feat/d716ee132ac54c611c0869e8e90b32c7be485d5b53b238845658b1ada136a093/system-build-handoff.json)のexecution_tasksとtask-spec参照を保持し、DAG順で消費する。

これは確認可能な最小handoff成果物である。外部build起動は行っていない。後続native run-system-dev-planの適用と選択後の独立監査は未実行であり、試行全体の完了判定は保留する。上流の合成findingsは今回の独立評価ではない。

実装ソース生成は0件。readiness不足時はclosure全体のhandoffを保留し、missing_sectionsとremediation ownerを正規guardから返す。snapshotが変わった場合はbindingから再検証する。

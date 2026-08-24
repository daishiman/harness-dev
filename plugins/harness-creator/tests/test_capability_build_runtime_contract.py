"""capability-build の薄い入口と遅延 runtime 契約の fail-closed 配線検査。"""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "plugins" / "harness-creator"
COMMAND = PLUGIN / "commands" / "capability-build.md"
RUNTIME = PLUGIN / "references" / "capability-build-runtime-contract.md"
PIPELINE = PLUGIN / "references" / "pipeline-boundary-contract.md"
USAGE = PLUGIN / "references" / "command-usage-prompts" / "capability-build.md"
RESOURCE_MAP = PLUGIN / "references" / "resource-map.yaml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_command_keeps_only_always_needed_decision_contract() -> None:
    text = _text(COMMAND)
    for anchor in (
        "## 常時判断契約",
        "## 分岐",
        "## 安全境界",
        "## 完了条件",
        "## 遅延参照",
        "明示モード",
        "単一 route モード",
        "task-graph route モード",
        "fail-closed",
        "単一 writer",
        "承認境界",
        "証拠鮮度",
        "全終了経路",
    ):
        assert anchor in text, f"command の常時判断 anchor 欠落: {anchor}"

    for deferred_detail in ("### 内ループ", "### 外ループ", "stall→emit 引数マップ"):
        assert deferred_detail not in text, f"詳細運用が command へ逆流: {deferred_detail}"


def test_command_runtime_reference_resolves_and_all_declared_sections_exist() -> None:
    command = _text(COMMAND)
    match = re.search(r"command ファイルからの解決先は `([^`]+)`", command)
    assert match, "command に機械解決可能な相対 runtime reference がない"
    resolved = (COMMAND.parent / match.group(1)).resolve()
    assert resolved == RUNTIME.resolve()
    assert resolved.is_file(), resolved

    runtime = _text(resolved)
    for heading in (
        "## 振る舞い",
        "## 本質的なコストモデル (Verification-as-program)",
        "## build stage (`--stage draft|release`)",
        "## 検証 profile とコスト上限",
        "## task-graph route モード (並列 dispatch + 2 ループ)",
        "### 内ループ (build-execution loop・現 task-graph を完了へ駆動)",
        "### 外ループ (spec-improvement loop・task 仕様書を改善して再実行)",
    ):
        assert heading in runtime, f"遅延参照 heading 欠落: {heading}"


def test_runtime_reference_retains_moved_gate_and_evidence_contracts() -> None:
    runtime = _text(RUNTIME)
    for anchor in (
        "build-script-route.py",
        "validate-route-build-reports.py",
        "verification-obligation-protocol.md",
        "plan-verification-obligations.py",
        "build-usable-draft-proof.py",
        "build-improvement-gate.py",
        "validate-improvement-result.py",
        "dispatch-ready-set.py",
        "sync-task-state.py",
        "inject-task-inputs.py",
        "emit-discovered-task.py",
        "summarize-task-progress.py",
        "manage-build-lease.py",
        "record-task-graph-knowledge.py",
        "project-task-status.py",
        "completion-evidence.json",
        "build-summary.json",
        "task-execution-report.html",
        "pending_user_gate",
        "covered_task_ids",
        "--execution-contract",
        "--unit-id",
        "--project-phase-gates",
        "atomic replace",
        "owner_token",
        "graph_hash_pin",
    ):
        assert anchor in runtime, f"移動した runtime 契約 anchor 欠落: {anchor}"

    pipeline = _text(PIPELINE)
    for anchor in ("proof_projection_batch", "repeatable `--task-id`", "1 unit=1 process"):
        assert anchor in pipeline, f"pipeline boundary の execution-unit anchor 欠落: {anchor}"


def test_all_discovery_surfaces_point_to_runtime_ssot() -> None:
    path = "references/capability-build-runtime-contract.md"
    assert path in _text(COMMAND)
    assert path in _text(PIPELINE)
    assert path in _text(USAGE)

    resource_map = _text(RESOURCE_MAP)
    assert "id: capability-build-runtime-contract" in resource_map
    assert f"path: {path}" in resource_map
    assert '"/capability-build が入力を明示・単一 route・task-graph route のいずれかへ分岐した後"' in resource_map

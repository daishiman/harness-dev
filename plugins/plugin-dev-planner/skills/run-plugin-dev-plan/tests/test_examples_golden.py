"""examples/sample-plan ゴールデン出力が core 5 scripts / 6 invocations + handoff gate を全 exit0 で通ることを固定する。

これにより「マトリクスが精緻でも、その通りに spec を生成し検査を通せるか」という
最大の未実証点を回帰防止する (生成物の実例 = 完全性の可視化)。ゴールデンが drift して
検査に落ちたら本テストが fail する。
"""
from __future__ import annotations

from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parent.parent / "examples" / "sample-plan"
INVENTORY = PLAN / "component-inventory.json"
HANDOFF = PLAN / "handoff-run-plugin-dev-plan.json"
GOAL_SPEC = PLAN / "goal-spec.json"
TASK_GRAPH = PLAN / "task-graph.json"


import json


def _inventory_components() -> list[dict]:
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    return [c for c in data.get("components", []) if isinstance(c, dict)]


def test_example_plan_dir_exists():
    assert PLAN.is_dir(), f"ゴールデン plan ディレクトリが無い: {PLAN}"
    assert (PLAN / "index.md").is_file()
    assert GOAL_SPEC.is_file()
    assert INVENTORY.is_file()
    assert HANDOFF.is_file()
    assert TASK_GRAPH.is_file(), "task-graph.json はデフォルト成果物 (§9・ゴールデンが常時携帯)"
    # per-phase 転換: index + 13 phase ファイル (P01..P13) = 14 Markdown
    specs = sorted(p.name for p in PLAN.glob("*.md"))
    assert len(specs) == 14, specs  # index.md + phase-01..13.md
    phase_files = [p.stem for p in PLAN.glob("phase-*.md")]
    assert len(phase_files) == 13, phase_files


def test_frontmatter_gate(specfm):
    assert specfm.main(["--specs-dir", str(PLAN)]) == 0


def test_plugin_goal_spec_gate(plugin_goal_spec):
    assert plugin_goal_spec.main([str(GOAL_SPEC)]) == 0


def test_gates_gate(gates):
    assert gates.main(["--specs-dir", str(PLAN)]) == 0


def test_topsort_gate(topsort):
    assert topsort.main([str(PLAN)]) == 0


def test_unassigned_gate(unassigned):
    assert unassigned.main(["--inventory", str(INVENTORY), "--specs-dir", str(PLAN)]) == 0


def test_matrix_coverage_gate(matrix):
    assert matrix.main([str(PLAN)]) == 0


def test_build_handoff_gate(handoff):
    assert handoff.main([str(HANDOFF)]) == 0


def test_surface_inventory_gate(surfaces):
    assert surfaces.main([str(INVENTORY)]) == 0


def test_runtime_portability_gate(runtime):
    assert runtime.main([str(PLAN)]) == 0


def test_validate_task_graph_gate(validate_task_graph):
    """デフォルト成果物 task-graph.json が 10 検査を全通過する (§9・成果物=タスクグラフ)。"""
    assert validate_task_graph.main([str(PLAN)]) == 0


def test_task_graph_is_canonical_default_artifact(derive_task_graph):
    """ゴールデンの task-graph.json が derive-task-graph の単一 writer 出力と一致する
    (手書き drift 検出・成果物が最新の phase/inventory 射影であることの回帰固定)。"""
    fresh = derive_task_graph.canonical_json(derive_task_graph.derive(PLAN))
    on_disk = TASK_GRAPH.read_text(encoding="utf-8").rstrip("\n")
    assert fresh == on_disk, "task-graph.json が derive-task-graph の canonical 出力と drift (再生成せよ)"


def test_shared_scripts_are_plugin_root():
    """ゴールデンの共有 script (>=2 skill consumer の C09/C10) が plugin-root へ hoist されている
    ことを固定する (install 携帯性の dogfooding・単一 skill 配下退化のサイレント回帰防止)。"""
    scripts = [c for c in _inventory_components() if c.get("component_kind") == "script"]
    assert scripts, "ゴールデンに script component が無い"
    for c in scripts:
        assert c.get("placement_scope") == "plugin-root", c.get("id")
        assert c.get("builder") == "plugin-scaffold", c.get("id")
        bt = c.get("build_target", "")
        assert "/scripts/" in bt and "/skills/" not in bt, bt


def test_all_five_component_kinds_present():
    """ゴールデン inventory が 5 種の component_kind を全種網羅する (skill 偏重の解消を実証)。

    per-phase 転換: buildable 実体は phase ファイルでなく component-inventory.json が SSOT。
    判定を inventory 読取へ移設する (phase frontmatter は component_kind を持たない)。
    """
    kinds = {str(c.get("component_kind", "")).strip() for c in _inventory_components()}
    kinds.discard("")
    assert kinds == {"skill", "sub-agent", "slash-command", "hook", "script"}, kinds


def test_per_instance_decomposition():
    """複数実体分解の恒久ロック: 少なくとも 1 つの component_kind が複数実体を持つ。

    実プラグインは同一 kind の複数実体 (skill 複数 / sub-agent 複数 等) を自然に含み、
    inventory はその各実体に 1 build_target を割り当てる (component-domain.md の 2 軸直交)。
    inventory が「kind ごと 1 本 (1-per-kind)」へ退化すると本テストが fail し、複数実体
    分解のサイレント回帰を機械検出する (component_kind=分類軸 5 種と、実体数 N の混同を防ぐ)。
    """
    from collections import Counter

    counts: Counter = Counter()
    for c in _inventory_components():
        ck = str(c.get("component_kind", "")).strip()
        if ck:
            counts[ck] += 1
    assert any(v >= 2 for v in counts.values()), dict(counts)

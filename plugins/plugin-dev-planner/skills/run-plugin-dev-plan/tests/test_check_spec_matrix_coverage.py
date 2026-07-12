"""check-spec-matrix-coverage.py の機能テスト (46行 operationalize 被覆・per-phase 転換)。

焼き先は inventory scope (component-inventory.json の component) / plugin scope
(index.plugin_meta) / phase scope (機械アンカー無し・計数のみ) の 3 種。
"""
from __future__ import annotations

from conftest import component_entry, write_inventory, write_phase_index


# ─────────────────── 分類 / self-test (現状維持) ───────────────────
def test_classify_counts(matrix):
    counts = matrix.classify_counts()
    assert counts == {"OP": 10, "conditional": 19, "N-A": 17}
    assert sum(counts.values()) == 46


def test_classify_membership(matrix):
    c = matrix.current_classification()
    op = {r for r, k in c.items() if k == "OP"}
    cond = {r for r, k in c.items() if k == "conditional"}
    na = {r for r, k in c.items() if k == "N-A"}
    assert op == {"A1", "A5", "A8", "C1", "C2", "F1", "F2", "F3", "F4", "F6"}
    assert cond == {"A7", "A10", "F5", "F7", "F8", "D6", "B1", "B4", "B5", "D1", "D2", "D5",
                    "A11", "E5", "E6", "E1", "E2", "G1", "G2"}
    assert na == {"A2", "A3", "A4", "A6", "A9", "B2", "B3", "C3", "C4",
                  "D3", "D4", "E3", "E4", "G3", "G4", "G5", "G6"}
    assert matrix.membership_drift() == []


def test_membership_drift_detects_count_neutral_swap(matrix):
    c = matrix.current_classification()
    c["A1"], c["A2"] = "N-A", "OP"
    counts = {"OP": sum(v == "OP" for v in c.values()),
              "conditional": sum(v == "conditional" for v in c.values()),
              "N-A": sum(v == "N-A" for v in c.values())}
    assert counts == {"OP": 10, "conditional": 19, "N-A": 17}
    drift = matrix.membership_drift(c)
    assert drift
    assert any("OP" in d for d in drift) and any("N-A" in d for d in drift)


def test_self_test_includes_membership(matrix):
    code, msgs = matrix.self_test(matrix._DEFAULT_MATRIX)
    assert code == 0 and msgs == []


def test_rows_table_has_46(matrix):
    assert len(matrix.ROWS) == 46


def test_self_test_against_reflection(matrix):
    code, msgs = matrix.self_test(matrix._DEFAULT_MATRIX)
    assert code == 0, msgs


def test_self_test_drift(tmp_path, matrix):
    bad = tmp_path / "m.md"
    bad.write_text("| A1 | x |\n| ZZ9 | y |\n", encoding="utf-8")
    code, msgs = matrix.self_test(bad)
    assert code == 1 and msgs


def test_parse_matrix_ids(matrix):
    ids = matrix.parse_matrix_ids("| A1 | x |\n| B2 | y |\nnoise\n| g | z |\n")
    assert ids == ["A1", "B2"]


def test_has_dotted(matrix):
    d = {"quality_gates": {"evaluator": {"threshold": 80}}}
    assert matrix._has(d, "quality_gates.evaluator")
    assert matrix._has(d, "quality_gates.evaluator.threshold")
    assert not matrix._has(d, "quality_gates.missing")
    assert not matrix._has({"k": ""}, "k")
    assert not matrix._has({"k": None}, "k")
    assert matrix._has({"k": []}, "k")
    assert matrix._has({"k": {}}, "k")


# ─────────────────── inventory scope coverage ───────────────────
def test_inventory_coverage_skill_clean(matrix):
    comp = component_entry("C01", "skill", skill_kind="run")
    assert matrix.check_inventory_coverage([comp]) == []


def test_inventory_coverage_hook_only_op(matrix):
    # hook は OP-ALWAYS アンカーのみ要求 (skill 専用行は適用されない)
    comp = component_entry("C01", "hook")
    assert matrix.check_inventory_coverage([comp]) == []


def test_inventory_coverage_missing_goal_seek(matrix):
    comp = component_entry("C01", "skill", skill_kind="run", drop=["goal_seek"])
    findings = matrix.check_inventory_coverage([comp])
    assert any("D1" in m for m in findings)
    assert any("goal_seek" in m for m in findings)


def test_inventory_coverage_missing_prompt_layer(matrix):
    comp = component_entry("C01", "skill", skill_kind="run", drop=["prompt_layer"])
    assert any("prompt_layer" in m for m in matrix.check_inventory_coverage([comp]))


def test_knowledge_loop_only_when_feature(matrix):
    plain = component_entry("C01", "skill")
    assert not any("G1" in m for m in matrix.check_inventory_coverage([plain]))
    opted = component_entry("C02", "skill", features=["knowledge_loop"])  # feature opt-in・キー欠落
    assert any("G1" in m for m in matrix.check_inventory_coverage([opted]))


def test_f8_placement_scope_only_for_script(matrix):
    # F8 (placement_scope) は script component にのみ適用される (skill/hook 等は対象外)。
    skill = component_entry("C01", "skill")
    assert not any("F8" in m for m in matrix.check_inventory_coverage([skill]))
    # placement_scope を持つ script は F8 充足、欠く script は未反映で検出。
    ok_script = component_entry("C09", "script", overrides={"placement_scope": "plugin-root"})
    assert not any("F8" in m for m in matrix.check_inventory_coverage([ok_script]))
    bad_script = component_entry("C09", "script", drop=["placement_scope"])
    findings = matrix.check_inventory_coverage([bad_script])
    assert any("F8" in m and "placement_scope" in m for m in findings)


# ─────────────────── plugin scope coverage ───────────────────
def test_check_plugin_coverage_clean_and_missing(matrix):
    full = {"distribution": {"distributable": False, "bundles": ["none"]},
            "pkg_contract": {"x": 1}, "governance": {"x": 1}, "ci": {"x": 1},
            "ssot_dedup": {"x": 1}, "feedback_deploy": {"x": 1}}
    assert matrix.check_plugin_coverage(full) == []
    missing = matrix.check_plugin_coverage({})
    ids = {m.split()[0] for m in missing}
    assert {"F3", "F4", "F6", "A7", "A10", "F5", "F7", "D6"} <= ids


# ─────────────────── run / main 統合 ───────────────────
def test_run_clean(tmp_path, matrix):
    write_inventory(tmp_path, [component_entry("C01", "skill", skill_kind="run"), component_entry("C02", "hook")])
    write_phase_index(tmp_path, plugin_meta=True)
    code, findings, counts = matrix.run(tmp_path, "index.md", None)
    assert code == 0, findings
    assert counts["OP"] == 10


def test_run_plugin_meta_missing(tmp_path, matrix):
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    write_phase_index(tmp_path, plugin_meta=False)
    code, findings, counts = matrix.run(tmp_path, "index.md", None)
    assert code == 1
    assert any("plugin-level" in f for f in findings)


def test_run_missing_index(tmp_path, matrix):
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    code, findings, counts = matrix.run(tmp_path, "index.md", None)
    assert code == 2


def test_run_missing_inventory(tmp_path, matrix):
    write_phase_index(tmp_path, plugin_meta=True)
    code, findings, counts = matrix.run(tmp_path, "index.md", None)
    assert code == 2


def test_main_self_test(matrix, capsys):
    assert matrix.main(["--self-test"]) == 0
    assert "drift なし" in capsys.readouterr().out


def test_main_self_test_fail(tmp_path, matrix):
    bad = tmp_path / "m.md"
    bad.write_text("| ZZ9 | y |\n", encoding="utf-8")
    assert matrix.main(["--self-test", "--matrix", str(bad)]) == 1


def test_main_clean(tmp_path, matrix, capsys):
    write_inventory(tmp_path, [component_entry("C01", "skill", skill_kind="run")])
    write_phase_index(tmp_path, plugin_meta=True)
    assert matrix.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "OP=10" in out and "conditional=19" in out and "N-A=17" in out


def test_main_violation(tmp_path, matrix):
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    write_phase_index(tmp_path, plugin_meta=False)
    assert matrix.main([str(tmp_path)]) == 1


def test_main_no_plan_dir(matrix):
    assert matrix.main([]) == 2


def test_main_not_a_dir(tmp_path, matrix):
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    assert matrix.main([str(f)]) == 2


def test_main_missing_inventory_exit2(tmp_path, matrix):
    write_phase_index(tmp_path, plugin_meta=True)
    assert matrix.main([str(tmp_path)]) == 2

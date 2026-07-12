"""check-spec-frontmatter.py の機能テスト (per-phase 転換)。

phase ファイル frontmatter (PHASE_REQUIRED) の検証と、component-inventory.json の各
component の構造契約 (specfm.validate_inventory_component) 検証を担う。旧 C*.md 走査は廃止。
"""
from __future__ import annotations

from conftest import component_entry, write_all_phases, write_inventory, write_phase_spec, write_phase_index

_DROP = object()


def _phase_text(specfm_mod, n: int = 3, **overrides) -> str:
    """minimal phase frontmatter を overrides で改変した phase Markdown を返す (負例化)。"""
    fm = specfm_mod.minimal_phase_frontmatter(n)
    for key, value in overrides.items():
        if value is _DROP:
            fm.pop(key, None)
        else:
            fm[key] = value
    body = "\n# phase\n" + "".join(f"{sec}\nx\n" for sec in specfm_mod.PHASE_BODY_SECTIONS)
    return "---\n" + "\n".join(specfm_mod.yaml_lines(fm)) + "\n---" + body


# ─────────────────── phase frontmatter (check_phase) ───────────────────
def test_phase_clean(specfm, specfm_mod):
    assert specfm.check_phase(specfm_mod.render_minimal_phase(3)) == []


def test_phase_clean_all_13(specfm, specfm_mod):
    for n in range(1, 14):
        assert specfm.check_phase(specfm_mod.render_minimal_phase(n)) == [], n


def test_phase_no_frontmatter(specfm):
    assert specfm.check_phase("plain text") == ["frontmatter (--- ブロック) が無い"]


def test_phase_missing_required_key(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, status=_DROP))
    assert any("必須キー欠落" in e for e in errs)


def test_phase_bad_id(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, id="PX"))
    assert any("PHASE_ID_RE" in e for e in errs)


def test_phase_id_number_mismatch(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, phase_number=5))
    assert any("不整合" in e for e in errs)


def test_phase_name_enum(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, phase_name="bogus"))
    assert any("enum 外" in e for e in errs)


def test_phase_category_mismatch(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, category="wrong"))
    assert any("不整合" in e for e in errs)


def test_phase_gate_type_enum(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, gate_type="bogus"))
    assert any("enum 外" in e for e in errs)


def test_phase_gate_type_mismatch(specfm, specfm_mod):
    # qa は enum 内だが design-review フェーズの期待 design-gate と不整合
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, gate_type="qa"))
    assert any("不整合" in e for e in errs)


def test_phase_status_enum(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, status="bogus"))
    assert any("enum 外" in e for e in errs)


def test_phase_prev_next_chain(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, prev_phase=0))
    assert any("prev_phase" in e for e in errs)


def test_phase_entities_covered_not_list(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, entities_covered="C01"))
    assert any("entities_covered が list でない" in e for e in errs)


def test_phase_applicability_not_dict(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, applicability="nope"))
    assert any("applicability が object でない" in e for e in errs)


def test_phase_applicable_false_needs_reason(specfm, specfm_mod):
    errs = specfm.check_phase(_phase_text(specfm_mod, 3, applicability={"applicable": False}))
    assert any("reason は非空必須" in e for e in errs)


# ─────────────────── inventory component (check_inventory) ───────────────────
def _inv_errs(tmp_path, specfm, comp) -> list[str]:
    path = write_inventory(tmp_path, [comp])
    errs, fatal = specfm.check_inventory(path)
    assert fatal is None, fatal
    return errs


def test_component_clean_skill_run(tmp_path, specfm):
    assert _inv_errs(tmp_path, specfm, component_entry("C01", "skill", skill_kind="run")) == []


def test_component_clean_each_kind(tmp_path, specfm):
    for ck in ("sub-agent", "slash-command", "hook", "script"):
        assert _inv_errs(tmp_path, specfm, component_entry("C01", ck)) == [], ck


def test_component_clean_skill_ref_no_criteria(tmp_path, specfm):
    assert _inv_errs(tmp_path, specfm, component_entry("C01", "skill", skill_kind="ref")) == []


def test_component_bad_component_kind(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "skill", overrides={"component_kind": "widget"}))
    assert any("enum 外" in e for e in errs)


def test_component_missing_build_target(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "skill", drop=["build_target"]))
    assert any("build_target が空" in e for e in errs)


def test_component_builder_mismatch(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "skill", overrides={"builder": "run-build-skill"}))
    assert any("builder" in e and "不整合" in e for e in errs)


def test_component_skill_missing_brief_field(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "skill", drop=["boundary"]))
    assert any("構造的必須フィールド欠落: boundary" in e for e in errs)


def test_component_hook_missing_fail_closed(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "hook", drop=["fail_closed"]))
    assert any("fail_closed" in e for e in errs)


def test_component_non_skill_no_brief_fields(tmp_path, specfm):
    # hook component に skill-brief 形状 (goal 等) が無くても通る
    comp = component_entry("C01", "hook")
    assert "goal" not in comp
    assert _inv_errs(tmp_path, specfm, comp) == []


def test_component_missing_quality_gates(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "skill", drop=["quality_gates"]))
    assert any("quality_gates ブロックが無い" in e for e in errs)


def test_component_missing_harness(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "skill", drop=["harness_coverage"]))
    assert any("harness_coverage ブロックが無い" in e for e in errs)


def test_component_skill_loop_missing_criteria(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "skill", skill_kind="run", drop=["feedback_contract"]))
    assert any("loop kind は feedback_contract.criteria 必須" in e for e in errs)


def test_component_skill_loop_criteria_must_be_purpose_derived(tmp_path, specfm):
    # goal「観測可能な完了状態」と語彙が重ならない汎用 fallback criteria は弾く (R3 §2.2 機械化)
    comp = component_entry(
        "C01", "skill", skill_kind="run",
        overrides={"feedback_contract": {"criteria": [
            {"id": "IN1", "loop_scope": "inner", "text": "lint exit0", "verify_by": "lint"},
            {"id": "OUT1", "loop_scope": "outer", "text": "4 条件 PASS", "verify_by": "elegant-review"},
        ]}},
    )
    errs = _inv_errs(tmp_path, specfm, comp)
    assert any("purpose 由来でない" in e for e in errs)


def test_component_skill_loop_purpose_derived_pass(tmp_path, specfm):
    comp = component_entry("C01", "skill", skill_kind="run")
    assert not any("purpose 由来でない" in e for e in _inv_errs(tmp_path, specfm, comp))


def test_component_skill_bad_kind(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "skill", overrides={"skill_kind": "weird"}))
    assert any("enum 外" in e for e in errs)


def test_component_skill_assign_needs_skip_or_criteria(tmp_path, specfm):
    comp = component_entry("C01", "skill", skill_kind="assign",
                           overrides={"feedback_contract": {"max_iterations": 3}})
    errs = _inv_errs(tmp_path, specfm, comp)
    assert any("skip_reason か criteria" in e for e in errs)


def test_component_script_tests_min_too_low(tmp_path, specfm):
    errs = _inv_errs(tmp_path, specfm, component_entry("C01", "script", overrides={"tests_min": 50}))
    assert any("tests_min は >=80" in e for e in errs)


# ─────────────────── main / collect 統合 ───────────────────
def test_collect_phase_files_skips_index(tmp_path, specfm):
    write_phase_spec(tmp_path, 1)
    write_phase_index(tmp_path)
    stems = [p.stem for p in specfm.collect_phase_files(tmp_path)]
    assert "index" not in stems
    assert "phase-01-requirements" in stems


def test_check_phase_file_contract_bad_name(tmp_path, specfm):
    p = write_phase_spec(tmp_path, 3)
    bad = tmp_path / "phase-03-wrong.md"
    bad.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    p.unlink()
    errs = specfm.check_phase_file_contract([bad])
    assert any("phase ファイル名不一致" in e for e in errs)


def test_check_phase_file_contract_duplicate_id(tmp_path, specfm):
    p = write_phase_spec(tmp_path, 3)
    copy = tmp_path / "phase-03-copy.md"
    copy.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    errs = specfm.check_phase_file_contract([p, copy])
    assert any("phase id 重複 P03" in e for e in errs)


def test_main_ok(tmp_path, specfm, capsys):
    write_all_phases(tmp_path)
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    assert specfm.main(["--specs-dir", str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_violation(tmp_path, specfm, capsys):
    write_all_phases(tmp_path)
    write_inventory(tmp_path, [component_entry("C01", "skill", drop=["quality_gates"])])
    assert specfm.main(["--specs-dir", str(tmp_path)]) == 1
    assert "quality_gates" in capsys.readouterr().err


def test_main_phase_violation(tmp_path, specfm, capsys):
    # 壊れた phase frontmatter (id 不正) を書くと main が exit1
    write_all_phases(tmp_path)
    write_phase_spec(tmp_path, 1, overrides={"id": "PX"})
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    assert specfm.main(["--specs-dir", str(tmp_path)]) == 1
    assert "PHASE_ID_RE" in capsys.readouterr().err


def test_main_explicit_phase_file(tmp_path, specfm):
    p = write_phase_spec(tmp_path, 5)
    assert specfm.main([str(p)]) == 0


def test_main_no_args(specfm):
    assert specfm.main([]) == 2


def test_main_specs_dir_not_dir(tmp_path, specfm):
    assert specfm.main(["--specs-dir", str(tmp_path / "nope")]) == 2


def test_main_file_not_found(tmp_path, specfm):
    assert specfm.main([str(tmp_path / "ghost.md")]) == 2

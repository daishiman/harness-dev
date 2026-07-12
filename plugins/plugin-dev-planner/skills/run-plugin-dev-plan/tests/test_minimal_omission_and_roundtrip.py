"""DEF-3 / DEF-2 回帰固定 (per-phase 転換版)。

DEF-3 (minimal-omission golden): 単一 skill + 非 skill surface を omitted_reason 付きで
正当省略した最小 plan (inventory + 13 phase + index) が決定論ゲート (surface-inventory /
detect-unassigned / matrix-coverage / spec-frontmatter / spec-gates) を全 exit0 で通ることを固定する。

DEF-2 (OUT2 round-trip readiness): sample-plan の inventory の skill component が skill-brief
base required + kind 別 conditional required を漏れなく携帯する (無加工で skill-brief instance へ
写せる) ことを specfm 正本に照らして固定する。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import component_entry, write_all_phases, write_inventory, write_phase_index

_PLAN = Path(__file__).resolve().parent.parent / "examples" / "sample-plan"


def _write_minimal_plan(tmp_path):
    """tmp_path に最小 plan (inventory + 13 phase + index) を生成する。"""
    inventory = write_inventory(tmp_path, [component_entry("C01", "skill", skill_kind="run")])
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"], 5: ["C01"]})
    write_phase_index(tmp_path, plugin_meta=True)
    return tmp_path, inventory


def test_minimal_omission_plan_passes_all_deterministic_gates(
    tmp_path, surfaces, unassigned, matrix, gates, specfm
):
    """単一 skill + 理由付き surface 省略の最小 plan が全決定論ゲートを exit0 で通る (DEF-3)。"""
    plan_dir, inventory = _write_minimal_plan(tmp_path)
    assert surfaces.main([str(inventory)]) == 0, "surface-inventory が正当な最小省略を拒否"
    assert unassigned.main(["--inventory", str(inventory), "--specs-dir", str(plan_dir)]) == 0
    assert matrix.main([str(plan_dir)]) == 0, "matrix-coverage が最小 plan を拒否"
    assert gates.main(["--specs-dir", str(plan_dir)]) == 0
    assert specfm.main(["--specs-dir", str(plan_dir)]) == 0


def test_sample_skill_components_roundtrip_to_skill_brief_required(specfm_mod):
    """sample-plan の inventory skill component が skill-brief 必須フィールドを欠落 0 で携帯する (DEF-2)。

    skill-brief instance へ無加工で写せる = base required (specfm.SKILL_BRIEF_FIELDS) +
    kind 別 conditional required (specfm.skill_conditional_required) を全充足。
    """
    data = json.loads((_PLAN / "component-inventory.json").read_text(encoding="utf-8"))
    skills = [c for c in data.get("components", [])
              if isinstance(c, dict) and str(c.get("component_kind", "")).strip() == "skill"]
    assert skills, "sample-plan inventory に skill component が無い"
    for c in skills:
        kind = specfm_mod._skill_kind_of(c)
        required = set(specfm_mod.SKILL_BRIEF_FIELDS) | set(specfm_mod.skill_conditional_required(kind))
        missing = sorted(f for f in required if f not in c)
        assert not missing, f"{c.get('id')}: skill-brief 必須フィールド欠落 (round-trip 不可): {missing}"


def _sample_skill_components() -> list[dict]:
    data = json.loads((_PLAN / "component-inventory.json").read_text(encoding="utf-8"))
    return [c for c in data.get("components", [])
            if isinstance(c, dict) and str(c.get("component_kind", "")).strip() == "skill"]


def test_sample_skill_responsibilities_shape(specfm_mod):
    """run/assign skill の responsibilities が object 配列 + prompt_required:true ≥1 件 (presence→shape 強化)。

    旧 roundtrip test はキー存在のみで、文字列配列 ['R1-elicit', ...] が実 schema
    (items=object + contains{prompt_required:true}) に落ちる欠陥 (島B LS-10) を素通りしていた。
    shape 床は specfm.validate_inventory_component にも写した (test_specfm) — ここは golden
    実データがその床を実際に満たすことを固定する。
    """
    checked = 0
    for c in _sample_skill_components():
        if specfm_mod._skill_kind_of(c) not in ("run", "assign"):
            continue
        resp = c.get("responsibilities")
        assert isinstance(resp, list) and resp, f"{c.get('id')}: responsibilities が非空 list でない"
        assert all(isinstance(r, dict) for r in resp), (
            f"{c.get('id')}: responsibilities に非 object 項目 (文字列配列は round-trip 不能)"
        )
        assert any(r.get("prompt_required") is True for r in resp), (
            f"{c.get('id')}: prompt_required:true の責務が 1 件も無い (実 schema allOf contains 違反)"
        )
        for r in resp:
            assert str(r.get("id", "")).strip() and str(r.get("summary", "")).strip(), (
                f"{c.get('id')}: responsibilities 項目に id/summary 非空が無い: {r}"
            )
        checked += 1
    assert checked, "run/assign skill が sample-plan に無く shape 床を検査できない"


def test_sample_skill_brief_projection_roundtrip(skill_brief, specfm_mod):
    """render-skill-brief.py の射影出力が実 schema の required 充足 + 余剰キー 0 を満たす (OUT2 完結)。

    handoff routes[].build_args.brief_path が宣言する brief を全 skill component について射影し、
    (i) planner 固有キーが漏れない (ii) 実 schema 存在時は base+allOf required 充足かつ
    additionalProperties:false で reject されないことを検査する。実 schema 不在 (standalone) は
    schema 突合のみ skip する (射影自体は検査)。
    """
    schema_path = skill_brief.find_schema_path()
    schema = (
        json.loads(schema_path.read_text(encoding="utf-8")) if schema_path is not None else None
    )
    for c in _sample_skill_components():
        brief = skill_brief.project_brief(c)
        leaked = sorted(set(brief) & (skill_brief.PLANNER_ONLY_KEYS | {"skill_kind"}))
        assert not leaked, f"{c.get('id')}: planner 固有キーが brief へ漏れた: {leaked}"
        assert brief.get("kind") == specfm_mod._skill_kind_of(c)
        if schema is None:
            continue
        errs = skill_brief.validate_against_schema(brief, schema)
        assert errs == [], f"{c.get('id')}: 射影 brief が実 schema 突合に落ちる: {errs}"
    if schema is None:
        pytest.skip("実 skill-brief.schema.json 不在 (standalone 配布): 射影のみ検査し schema 突合を skip")

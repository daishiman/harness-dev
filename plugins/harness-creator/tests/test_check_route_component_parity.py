"""check-route-component-parity.py (PB-C08) の機能テスト。

routes[]↔component-inventory.json の 1:1 parity を検査する独立ゲートの受入・負例・
usage error を固定する。E2 境界: run-skill-create が build 前に parity 不一致を止める。
"""
from __future__ import annotations

import json


def _route(rid, **over):
    base = {
        "id": rid,
        "component_kind": "skill",
        "name": "run-sample",
        "builder": "run-skill-create",
        "build_kind": "skill",
        "build_target": "plugins/sample/skills/run-sample/",
        "placement_scope": "skill",
        "depends_on": [],
        "build_args": {"skill_name": "run-sample", "kind": "run"},
    }
    base.update(over)
    return base


def _comp(rid, **over):
    return _route(rid, **over)  # inventory component は同形フィールドを持つ


def _write(tmp_path, routes, components):
    inv = tmp_path / "component-inventory.json"
    inv.write_text(json.dumps({"components": components}, ensure_ascii=False), encoding="utf-8")
    handoff = tmp_path / "handoff-run-plugin-dev-plan.json"
    handoff.write_text(
        json.dumps({"plan_dir": str(tmp_path), "routes": routes}, ensure_ascii=False),
        encoding="utf-8",
    )
    return handoff, inv


# ─────────────────── check_parity (単体) ───────────────────
def test_clean_parity_returns_no_errors(parity):
    routes = [_route("C01"), _route("C02", name="run-two",
                                    build_target="plugins/sample/skills/run-two/")]
    comps = [_comp("C01"), _comp("C02", name="run-two",
                                 build_target="plugins/sample/skills/run-two/")]
    assert parity.check_parity(routes, comps) == []


def test_missing_route_detected(parity):
    errs = parity.check_parity([_route("C01")], [_comp("C01"), _comp("C02")])
    assert any("C02" in e and "対応する route が無い" in e for e in errs)


def test_extra_route_detected(parity):
    errs = parity.check_parity([_route("C01"), _route("C02")], [_comp("C01")])
    assert any("C02" in e and "inventory" in e for e in errs)


def test_scalar_field_mismatch_detected(parity):
    errs = parity.check_parity([_route("C01", build_kind="command")], [_comp("C01")])
    assert any("build_kind" in e and "不一致" in e for e in errs)


def test_depends_on_mismatch_detected(parity):
    errs = parity.check_parity([_route("C01", depends_on=["C09"])], [_comp("C01", depends_on=[])])
    assert any("depends_on" in e for e in errs)


def test_build_args_mismatch_detected(parity):
    errs = parity.check_parity(
        [_route("C01", build_args={"skill_name": "x", "kind": "run"})],
        [_comp("C01", build_args={"skill_name": "y", "kind": "run"})],
    )
    assert any("build_args" in e for e in errs)


def test_one_sided_empty_field_is_not_flagged(parity):
    """片側だけ欠落するフィールドは本ゲート対象外 (kind 別構造検査の責務)。"""
    route = _route("C01")
    route.pop("placement_scope")
    assert parity.check_parity([route], [_comp("C01")]) == []


def test_side_effect_targets_mismatch_detected(parity):
    """side_effect_targets は不在=[] 扱いで突合し、片側のみの宣言も不一致として NG。"""
    errs = parity.check_parity(
        [_route("C01", side_effect_targets=["plugins/sample/schemas/a.json"])],
        [_comp("C01")],
    )
    assert any("side_effect_targets" in e and "不一致" in e for e in errs)
    # 差分明示: 両辺の値が error 文へ載る
    assert any("plugins/sample/schemas/a.json" in e for e in errs)


def test_side_effect_targets_match_is_order_insensitive(parity):
    """side_effect_targets はソート後比較 (宣言順の違いは不一致にしない)。"""
    routes = [_route("C01", side_effect_targets=["b.json", "a.json"])]
    comps = [_comp("C01", side_effect_targets=["a.json", "b.json"])]
    assert parity.check_parity(routes, comps) == []


def test_side_effect_targets_absent_equals_empty(parity):
    """片側 [] / 片側不在は同値 (どちらも副作用なし宣言)。"""
    assert parity.check_parity([_route("C01", side_effect_targets=[])], [_comp("C01")]) == []


def test_duplicate_id_detected(parity):
    errs = parity.check_parity([_route("C01"), _route("C01")], [_comp("C01")])
    assert any("重複" in e for e in errs)


def test_missing_id_detected(parity):
    route = _route("C01")
    route["id"] = ""
    errs = parity.check_parity([route], [_comp("C01")])
    assert any("id が無い" in e for e in errs)


def test_both_empty_detected(parity):
    errs = parity.check_parity([], [])
    assert any("検証不能" in e for e in errs)


def test_non_list_routes_detected(parity):
    errs = parity.check_parity("nope", [_comp("C01")])
    assert any("routes が list でない" in e for e in errs)


# ─────────────────── main / CLI (統合) ───────────────────
def test_main_clean_returns_zero(tmp_path, parity):
    handoff, _ = _write(tmp_path, [_route("C01")], [_comp("C01")])
    assert parity.main([str(handoff)]) == 0


def test_main_violation_returns_one(tmp_path, parity):
    handoff, _ = _write(tmp_path, [_route("C01")], [_comp("C01"), _comp("C02")])
    assert parity.main([str(handoff)]) == 1


def test_main_explicit_inventory_flag(tmp_path, parity):
    handoff, inv = _write(tmp_path, [_route("C01")], [_comp("C01")])
    assert parity.main([str(handoff), "--inventory", str(inv)]) == 0


def test_main_missing_handoff_returns_two(tmp_path, parity):
    assert parity.main([str(tmp_path / "nope.json")]) == 2


def test_main_missing_inventory_returns_two(tmp_path, parity):
    handoff = tmp_path / "handoff-run-plugin-dev-plan.json"
    handoff.write_text(json.dumps({"plan_dir": str(tmp_path), "routes": [_route("C01")]}), encoding="utf-8")
    assert parity.main([str(handoff)]) == 2  # inventory 不在


def test_main_bad_handoff_json_returns_two(tmp_path, parity):
    handoff = tmp_path / "handoff-run-plugin-dev-plan.json"
    handoff.write_text("{ broken", encoding="utf-8")
    assert parity.main([str(handoff)]) == 2


def test_main_bad_inventory_json_returns_two(tmp_path, parity):
    (tmp_path / "component-inventory.json").write_text("{ broken", encoding="utf-8")
    handoff = tmp_path / "handoff-run-plugin-dev-plan.json"
    handoff.write_text(json.dumps({"plan_dir": str(tmp_path), "routes": [_route("C01")]}), encoding="utf-8")
    assert parity.main([str(handoff)]) == 2


def test_resolve_inventory_prefers_override(tmp_path, parity):
    handoff = tmp_path / "handoff-run-plugin-dev-plan.json"
    handoff.write_text(json.dumps({"plan_dir": "/absolute/elsewhere", "routes": []}), encoding="utf-8")
    resolved = parity.resolve_inventory(handoff.resolve(), {"plan_dir": "/absolute/elsewhere"}, str(tmp_path / "x.json"))
    assert resolved == (tmp_path / "x.json")


def test_resolve_inventory_relative_plan_dir_uses_handoff_dir(tmp_path, parity):
    """相対 plan_dir は cwd でなく handoff の所在を基準にする (cwd 非依存)。"""
    handoff = (tmp_path / "handoff-run-plugin-dev-plan.json").resolve()
    resolved = parity.resolve_inventory(handoff, {"plan_dir": "relative/meta"}, None)
    assert resolved == tmp_path / "component-inventory.json"

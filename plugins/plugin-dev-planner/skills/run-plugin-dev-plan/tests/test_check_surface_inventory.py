from __future__ import annotations

import json

from conftest import component_entry


def _valid_inventory() -> dict:
    return {
        "considered_component_kinds": ["skill", "sub-agent", "slash-command", "hook", "script"],
        "components": [component_entry("C01", "skill", skill_kind="run")],
        "plugin_level_surfaces": {
            "manifest": {"required": True, "path": ".claude-plugin/plugin.json"},
            "composition": {"required": True, "path": "plugin-composition.yaml"},
            "harness_eval": {"required": True, "path": "EVALS.json"},
            "references_config_assets": {"required": False, "omitted_reason": "No shared references needed"},
            "schemas": {"required": False, "omitted_reason": "No standalone JSON schema needed"},
            "vendor": {"required": False, "omitted_reason": "No cross-plugin SSOT to vendor"},
            "mcp_app_connector": {"required": False, "omitted_reason": "No MCP/app connector needed"},
            "notion_config": {"required": False, "omitted_reason": "No Notion-backed DB needed"},
        },
    }


def test_surface_inventory_accepts_considered_all_and_minimal_components(tmp_path, surfaces):
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(_valid_inventory(), ensure_ascii=False), encoding="utf-8")

    assert surfaces.main([str(inventory)]) == 0


def test_surface_inventory_rejects_missing_considered_kind(tmp_path, surfaces):
    data = _valid_inventory()
    data["considered_component_kinds"] = ["skill"]
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert surfaces.main([str(inventory)]) == 1


def test_surface_inventory_rejects_omission_without_reason(tmp_path, surfaces):
    data = _valid_inventory()
    data["plugin_level_surfaces"]["mcp_app_connector"] = {"required": False}
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert surfaces.main([str(inventory)]) == 1


def test_surface_inventory_rejects_invalid_component(tmp_path, surfaces):
    """per-phase 転換: 各 component は validate_inventory_component で検証される
    (build_target 欠落など shape 不備を surface-inventory も弾く)。"""
    data = _valid_inventory()
    data["components"] = [component_entry("C01", "skill", drop=["build_target"])]
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert surfaces.main([str(inventory)]) == 1


def test_surface_inventory_rejects_missing_notion_config_surface(tmp_path, surfaces):
    """notion_config surface (8 面目) の欠落は他 surface 同様 required/omitted_reason の明示を要求する。"""
    data = _valid_inventory()
    del data["plugin_level_surfaces"]["notion_config"]
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert surfaces.main([str(inventory)]) == 1


def test_surface_inventory_notion_config_required_true_value_domain(tmp_path, surfaces):
    """notion_config required:true は databases[] 非空 + key/direction 非空 + used_by 実在 id を強制する。"""
    data = _valid_inventory()
    data["plugin_level_surfaces"]["notion_config"] = {"required": True}  # databases 欠落
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert surfaces.main([str(inventory)]) == 1

    data["plugin_level_surfaces"]["notion_config"] = {
        "required": True,
        "databases": [{"key": "", "used_by": ["C99"], "direction": ""}],  # 空 key/direction + 不在 id
    }
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert surfaces.main([str(inventory)]) == 1


def test_surface_inventory_notion_config_required_true_clean(tmp_path, surfaces):
    """notion_config required:true の妥当形 (key のみ宣言・ID は設置先 config 供給の二層) が通る。"""
    data = _valid_inventory()
    data["plugin_level_surfaces"]["notion_config"] = {
        "required": True,
        "resolution": "notion_config",
        "databases": [{"key": "improvement-request", "used_by": ["C01"], "direction": "write"}],
        "token": "keychain",
    }
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert surfaces.main([str(inventory)]) == 0

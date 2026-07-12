from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / name)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_template_bundle_name_is_neutral():
    tenant = json.loads((ROOT / "tenants" / "_template" / "tenant.json").read_text())
    assert tenant["enabled_bundles"] == ["skills-full"]


def test_tenant_runtime_rejects_conflicting_selectors(monkeypatch, tmp_path):
    import tenant_runtime

    (tmp_path / "tenants" / "alpha").mkdir(parents=True)
    target = tmp_path / "tenants" / "alpha" / "notion-config.json"
    target.write_text("{}")
    (tmp_path / ".notion-config.json").symlink_to(target.relative_to(tmp_path))
    monkeypatch.setenv("HARNESS_ROOT", str(tmp_path))
    monkeypatch.setenv("HARNESS_TENANT", "beta")
    with pytest.raises(tenant_runtime.TenantConfigError, match="conflicts"):
        tenant_runtime.active_tenant_slug()


def test_doctor_contract_detects_missing_and_unknown_keys():
    doctor = load_script("tenant-doctor.py")
    failures, warnings = doctor._compare_contract({"a": {"b": ""}}, {"a": {}, "extra": 1})
    assert "$.a.b: missing" in failures
    assert "$.extra: unknown key" in warnings


def test_build_rejects_overlay_escape():
    build = load_script("tenant-build.py")
    with pytest.raises(Exception, match="escapes"):
        build._safe_overlay(ROOT / "tenants" / "_template", "../../outside.json")


def test_release_selection_excludes_internal_plugins():
    builder = load_script("build-tenant-bundle.py")
    tenant = json.loads((ROOT / "tenants" / "_template" / "tenant.json").read_text())
    bundles = json.loads((ROOT / ".claude-plugin" / "bundles.json").read_text())
    selected = builder.selected_plugins(tenant, bundles)
    assert selected
    assert not (set(selected) & builder.NEVER_DISTRIBUTE)


def test_link_profile_has_exact_master_set():
    linker = load_script("link_master_plugins.py")
    names = linker.profile_names("master-link-set")
    assert len(names) == 11
    assert len(names) == len(set(names))


def _materialize_demo_overlays(tenant_dir: Path, slug: str, marker: str) -> None:
    replacements = {
        "": marker,
        f"notion-api-key.{slug}": f"notion-api-key.{slug}",
        slug: slug,
    }
    for example in tenant_dir.glob("*.example.json"):
        data = json.loads(example.read_text(encoding="utf-8"))

        def fill(value):
            if isinstance(value, dict):
                return {key: fill(child) for key, child in value.items()}
            if isinstance(value, list):
                return [fill(child) for child in value]
            if isinstance(value, str):
                return replacements.get(value, value)
            return value

        actual = tenant_dir / example.name.replace(".example.json", ".json")
        actual.write_text(json.dumps(fill(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_two_tenants_config_only_e2e_are_isolated(monkeypatch, tmp_path):
    tenant_init = load_script("tenant-init.py")
    tenant_build = load_script("tenant-build.py")
    tenant_doctor = load_script("tenant-doctor.py")

    tenants = tmp_path / "tenants"
    shutil.copytree(ROOT / "tenants" / "_template", tenants / "_template")
    (tmp_path / ".claude-plugin").mkdir()
    shutil.copy2(ROOT / ".claude-plugin" / "bundles.json", tmp_path / ".claude-plugin" / "bundles.json")

    monkeypatch.setattr(tenant_init, "TENANTS", tenants)
    monkeypatch.setattr(tenant_build, "ROOT", tmp_path)
    monkeypatch.setattr(tenant_doctor, "ROOT", tmp_path)
    monkeypatch.setattr(tenant_doctor, "TENANTS", tenants)
    monkeypatch.setenv("HARNESS_ROOT", str(tmp_path))

    results = {}
    for slug, display_name, marker in (
        ("alpha-co", "Alpha Co", "alpha-value"),
        ("beta-co", "Beta Co", "beta-value"),
    ):
        target = tenant_init.create_tenant(slug, display_name)
        assert "company-slug" not in "\n".join(
            path.read_text(encoding="utf-8")
            for path in target.rglob("*")
            if path.is_file() and path.suffix in {".json", ".md"}
        )
        _materialize_demo_overlays(target, slug, marker)

        descriptor_path = target / "tenant.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        env_name = f"HARNESS_SECRET_{slug.upper().replace('-', '_')}_NOTION_API_KEY"
        descriptor["credentials"]["notion-api-key"]["env_fallback"] = env_name
        descriptor_path.write_text(
            json.dumps(descriptor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        monkeypatch.setenv(env_name, "test-only-non-secret")

        commands = tenant_build.build(slug, activate=False)
        failures, warnings, resolved = tenant_doctor.diagnose(slug, include_plugin_doctors=False)
        assert failures == []
        assert warnings == []
        results[slug] = {"commands": commands, "resolved": resolved}

    alpha = results["alpha-co"]
    beta = results["beta-co"]
    assert alpha["resolved"]["credentials"] != beta["resolved"]["credentials"]
    assert set(alpha["resolved"]["databases"].values()) == {"alpha-value"}
    assert set(beta["resolved"]["databases"].values()) == {"beta-value"}
    assert alpha["commands"] != beta["commands"]

"""Plugin-local PKG-009 external reference allowlist tests."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-external-refs.py"
SPEC = importlib.util.spec_from_file_location("plugin_lint_external_refs_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _plugin(tmp_path: Path, *, depends_on: list[str] | None = None) -> tuple[Path, Path]:
    plugin = tmp_path / "plugins" / "demo"
    skill = plugin / "skills" / "run-demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    refs = plugin / "references"
    refs.mkdir()
    (refs / "package-contract.json").write_text(
        json.dumps({"package_mode": "bundle", "entry_points": {}, "depends_on": depends_on or []}),
        encoding="utf-8",
    )
    return plugin, skill


def test_declared_literal_plugin_dependency_is_allowed(tmp_path):
    plugin, skill = _plugin(tmp_path, depends_on=["dep-plugin"])
    skill.write_text("use plugins/dep-plugin/references/contract.md\n", encoding="utf-8")
    report = MOD.scan_skill(
        skill,
        MOD.DEFAULT_ALLOWED_PREFIXES,
        plugin_dir=plugin,
        declared_dependencies={"dep-plugin"},
    )
    assert report["external_refs"] == []
    assert report["refs"][0]["classification"] == "declared_plugin_dependency"


def test_declared_relative_plugin_dependency_is_allowed(tmp_path):
    plugin, skill = _plugin(tmp_path, depends_on=["dep-plugin"])
    skill.write_text("reference_refs: [../../../dep-plugin/references/contract.md]\n", encoding="utf-8")
    report = MOD.scan_skill(
        skill,
        MOD.DEFAULT_ALLOWED_PREFIXES,
        plugin_dir=plugin,
        declared_dependencies={"dep-plugin"},
    )
    assert report["external_refs"] == []
    assert report["refs"][0]["dependency"] == "dep-plugin"


def test_undeclared_plugin_dependency_fails_closed_even_with_plugins_prefix(tmp_path):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("use plugins/ghost/references/contract.md\n", encoding="utf-8")
    report = MOD.scan_skill(
        skill,
        ("plugins/",),
        plugin_dir=plugin,
        declared_dependencies=set(),
    )
    assert len(report["external_refs"]) == 1
    assert report["external_refs"][0]["classification"] == "undeclared_plugin_dependency"


def test_same_plugin_relative_reference_is_allowed(tmp_path):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("script_refs: [../../scripts/local.py]\n", encoding="utf-8")
    report = MOD.scan_skill(
        skill,
        MOD.DEFAULT_ALLOWED_PREFIXES,
        plugin_dir=plugin,
        declared_dependencies=set(),
    )
    assert report["external_refs"] == []
    assert report["refs"][0]["classification"] == "same_plugin"


def test_main_reads_contract_and_reports_declared_dependency(tmp_path, capsys):
    plugin, skill = _plugin(tmp_path, depends_on=["dep-plugin"])
    skill.write_text("plugins/dep-plugin/references/c.md\n", encoding="utf-8")
    rc = MOD.main([
        "prog", "--skills-dir", str(plugin / "skills"), "--fail-on-external", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["declared_dependencies"] == ["dep-plugin"]
    assert payload["declared_dependency_ref_count"] == 1
    assert payload["external_ref_count"] == 0


def test_main_undeclared_dependency_returns_1(tmp_path, capsys):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("plugins/ghost/references/c.md\n", encoding="utf-8")
    rc = MOD.main([
        "prog", "--skills-dir", str(plugin / "skills"), "--fail-on-external", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["external_ref_count"] == 1


def test_main_malformed_contract_returns_1_in_gate_mode(tmp_path, capsys):
    plugin, skill = _plugin(tmp_path)
    skill.write_text("references/local.md\n", encoding="utf-8")
    (plugin / "references" / "package-contract.json").write_text("{broken", encoding="utf-8")
    rc = MOD.main([
        "prog", "--skills-dir", str(plugin / "skills"), "--fail-on-external", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["contract_errors"]


def test_load_declared_dependencies_rejects_invalid_shape(tmp_path):
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"depends_on": "dep-plugin"}), encoding="utf-8")
    dependencies, errors = MOD.load_declared_dependencies(contract)
    assert dependencies == set()
    assert errors == ["package contract depends_on must be an array"]

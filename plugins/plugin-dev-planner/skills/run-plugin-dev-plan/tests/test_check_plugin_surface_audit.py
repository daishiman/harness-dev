from __future__ import annotations

import json
from pathlib import Path


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manifest(plugin: Path, *, name: str | None = None) -> None:
    _write(
        plugin / ".claude-plugin" / "plugin.json",
        json.dumps({"name": name or plugin.name, "version": "0.1.0", "description": "test"}, ensure_ascii=False),
    )


def _plan_ready_plugin(root: Path, name: str = "planner") -> Path:
    plugin = root / name
    _manifest(plugin)
    _write(plugin / "skills" / "run-sample" / "SKILL.md")
    _write(plugin / "agents" / "sample-agent.md")
    _write(plugin / "commands" / "sample.md")
    _write(plugin / "hooks" / "hook-sample.py")
    _write(plugin / "skills" / "run-sample" / "scripts" / "check.py")
    _write(plugin / "skills" / "run-sample" / "tests" / "test_check.py")
    _write(plugin / "skills" / "run-sample" / "references" / "resource-map.yaml")
    _write(plugin / "EVALS.json", "{}")
    _write(plugin / "plugin-composition.yaml", "plugin: planner\n")
    return plugin


def test_audit_accepts_plan_ready_plugin(tmp_path, plugin_surface_audit):
    plugins = tmp_path / "plugins"
    _plan_ready_plugin(plugins)

    assert plugin_surface_audit.main([
        "--plugins-dir",
        str(plugins),
        "--strict-manifest",
        "--expect-plan-ready",
        "planner",
    ]) == 0


def test_audit_counts_optional_plugin_surfaces(tmp_path, plugin_surface_audit):
    plugins = tmp_path / "plugins"
    plugin = _plan_ready_plugin(plugins)
    _write(plugin / "config" / "settings.json", "{}")
    _write(plugin / "assets" / "template.md")
    _write(plugin / "schemas" / "payload.schema.json", "{}")
    _write(plugin / "vendor" / "README.md")
    _write(plugin / ".mcp.json", "{}")

    report, errors = plugin_surface_audit.audit(plugins, strict_manifest=True, expect_plan_ready={"planner"})

    assert errors == []
    counts = report["plugins"][0]["counts"]
    assert counts["config"] == 1
    assert counts["assets"] == 1
    assert counts["schemas"] == 1
    assert counts["vendor"] == 1
    assert counts["mcp_app_connector"] == 1


def test_audit_rejects_missing_manifest_in_strict_mode(tmp_path, plugin_surface_audit):
    plugin = tmp_path / "plugins" / "no-manifest"
    _write(plugin / "skills" / "run-sample" / "SKILL.md")

    assert plugin_surface_audit.main([
        "--plugins-dir",
        str(tmp_path / "plugins"),
        "--strict-manifest",
    ]) == 1


def test_audit_missing_plugins_dir_reports_error_without_crash(tmp_path, plugin_surface_audit):
    """plugins_dir 不在時、main() が KeyError でクラッシュせず exit 1 で報告する。

    早期 return dict が正常パスと非対称 (plugin_count/surface_keys 欠落) だと、
    --json なし経路の _print_summary が本来の "not found" 報告前に KeyError で
    落ちる回帰を固定する (CI cwd で顕在化したバグ)。
    """
    missing = tmp_path / "does-not-exist"
    assert plugin_surface_audit.main(["--plugins-dir", str(missing)]) == 1


def test_audit_rejects_plan_ready_missing_surface(tmp_path, plugin_surface_audit):
    plugins = tmp_path / "plugins"
    planner = _plan_ready_plugin(plugins)
    (planner / "commands" / "sample.md").unlink()

    assert plugin_surface_audit.main([
        "--plugins-dir",
        str(plugins),
        "--expect-plan-ready",
        "planner",
    ]) == 1


# tests/<skill>/scripts/.. を遡って実 plugins/ root を解決する。CI 機構B は skill
# ディレクトリを cwd にして pytest を走らせるため、相対 "plugins" は解決できない
# ([[feedback_verify_ci_run_tests_from_ci_cwd]])。__file__ 起点で cwd 非依存にする。
_PLUGINS_ROOT = Path(__file__).resolve().parents[4]


def test_real_plugin_dev_planner_is_plan_ready(plugin_surface_audit):
    assert _PLUGINS_ROOT.name == "plugins", f"plugins root 解決に失敗: {_PLUGINS_ROOT}"
    assert plugin_surface_audit.main([
        "--plugins-dir",
        str(_PLUGINS_ROOT),
        "--strict-manifest",
        "--expect-plan-ready",
        "plugin-dev-planner",
    ]) == 0

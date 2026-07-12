"""resolve-skill-dirs.py の marketplace install 配置非依存性を固定する。"""

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "resolve-skill-dirs.py"
)


def _run(cwd: Path, env: dict[str, str] | None = None) -> dict[str, object]:
    merged = os.environ.copy()
    for key in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR", "CLAUDE_SKILL_OUT_BASE", "CLAUDE_SKILL_DIR"):
        merged.pop(key, None)
    if env:
        merged.update(env)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=cwd,
        env=merged,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(proc.stdout)


def test_marketplace_install_separates_plugin_root_from_project_output(tmp_path):
    project = tmp_path / "user-project"
    project.mkdir()
    plugin = tmp_path / "marketplace-cache" / "harness-creator"
    (plugin / "skills" / "run-build-skill").mkdir(parents=True)
    (plugin / "plugin-composition.yaml").write_text("name: harness-creator\n", encoding="utf-8")

    result = _run(project, {"CLAUDE_PLUGIN_ROOT": str(plugin)})

    assert result["out_base"] == ".claude/skills"
    assert result["skill_dir"] == str(plugin / "skills" / "run-build-skill")
    assert result["plugin_root"] == str(plugin)
    assert result["project_root"] == str(project)


def test_monorepo_layout_keeps_existing_project_relative_defaults():
    result = _run(ROOT)

    assert result["out_base"] == "plugins/harness-creator/skills"
    assert result["skill_dir"] == "plugins/harness-creator/skills/run-build-skill"
    assert result["plugin_root"] == "plugins/harness-creator"


def test_explicit_env_overrides_are_respected(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    out_base = tmp_path / "custom-out"
    skill_dir = tmp_path / "custom-skill"
    out_base.mkdir()
    skill_dir.mkdir()

    result = _run(
        project,
        {
            "CLAUDE_SKILL_OUT_BASE": str(out_base),
            "CLAUDE_SKILL_DIR": str(skill_dir),
        },
    )

    assert result["out_base"] == str(out_base)
    assert result["skill_dir"] == str(skill_dir)

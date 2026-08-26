"""resource-map attribution lint の YAML 破損・帰属漏れ回帰。"""

from __future__ import annotations

import importlib.util
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "lint-reference-attribution.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_reference_attribution", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _skill(tmp_path: Path, resource_map: str) -> Path:
    skill = tmp_path / "demo"
    refs = skill / "references"
    refs.mkdir(parents=True)
    for name in ("a.md", "b.md", "c.md"):
        (refs / name).write_text(name)
    (refs / "resource-map.yaml").write_text(resource_map)
    return skill


def test_malformed_yaml_returns_actionable_finding(tmp_path):
    mod = _load()
    skill = _skill(
        tmp_path,
        "read_when:\n  - file: references/a.md\n    when: broken: value\n",
    )
    findings = mod.lint_skill(skill)
    assert len(findings) == 1
    assert "resource-map.yaml YAML invalid" in findings[0]
    assert "line 3" in findings[0]


def test_quoted_colon_preserves_attribution_checks(tmp_path):
    mod = _load()
    skill = _skill(
        tmp_path,
        """read_when:
  - file: references/a.md
    when: "count: marker"
  - file: references/b.md
  - file: references/c.md
""",
    )
    assert mod.lint_skill(skill) == []


def test_orphan_reference_still_fails(tmp_path):
    mod = _load()
    skill = _skill(
        tmp_path,
        "read_when:\n  - file: references/a.md\n  - file: references/b.md\n",
    )
    findings = mod.lint_skill(skill)
    assert any("references/c.md" in finding and "orphan" in finding for finding in findings)

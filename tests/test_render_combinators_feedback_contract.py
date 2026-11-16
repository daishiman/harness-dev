import json
import importlib.util
import pytest
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_BUILD = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
RENDER_COMBINATORS = RUN_BUILD / "scripts" / "render-combinators.py"
RENDER_FRONTMATTER = RUN_BUILD / "scripts" / "render-frontmatter.py"


def test_explicit_feedback_refresh_updates_managed_files_and_preserves_extras(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("feedback_refresh_renderer", RENDER_COMBINATORS)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("new canonical")
    (source / "scripts").mkdir()
    (source / "scripts" / "runtime.py").write_text("#!/usr/bin/env python3\n")
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "cache.pyc").write_bytes(b"local cache")
    monkeypatch.setattr(renderer, "_feedback_loop_source", lambda: source)
    target = tmp_path / "demo"
    deployed = renderer.apply_feedback_loop(target)
    (deployed / "SKILL.md").write_text("old canonical")
    (deployed / "local-note.txt").write_text("keep")
    renderer.apply_feedback_loop(target)
    assert (deployed / "SKILL.md").read_text() == "old canonical"
    renderer.apply_feedback_loop(target, refresh=True)
    assert (deployed / "SKILL.md").read_text() == "new canonical"
    assert (deployed / "local-note.txt").read_text() == "keep"
    assert not (deployed / "__pycache__").exists()
    renderer.apply_feedback_loop(target, refresh=True)
    assert (deployed / "SKILL.md").read_text() == "new canonical"


@pytest.mark.parametrize("shape", ["file", "directory", "skills-parent"])
def test_feedback_refresh_refuses_symlinks_before_writing(tmp_path, monkeypatch, shape):
    spec = importlib.util.spec_from_file_location("feedback_refresh_symlink", RENDER_COMBINATORS)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    (source / "SKILL.md").write_text("new skill")
    (source / "scripts" / "tool.py").write_text("new canonical")
    monkeypatch.setattr(renderer, "_feedback_loop_source", lambda: source)
    target = tmp_path / "demo"
    outside = tmp_path / "outside"
    outside.mkdir()
    protected = outside / "tool.py"
    protected.write_text("keep outside")
    dest = target / "skills" / "run-skill-feedback"
    if shape == "skills-parent":
        target.mkdir()
        (target / "skills").symlink_to(outside, target_is_directory=True)
    else:
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("keep before preflight")
        if shape == "directory":
            (dest / "scripts").symlink_to(outside, target_is_directory=True)
        else:
            (dest / "scripts").mkdir()
            (dest / "scripts" / "tool.py").symlink_to(protected)
    with pytest.raises(OSError, match="symlink"):
        renderer.apply_feedback_loop(target, refresh=True)
    assert protected.read_text() == "keep outside"
    if shape != "skills-parent":
        assert (dest / "SKILL.md").read_text() == "keep before preflight"


def _run(*args: str) -> str:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


def test_render_combinators_injects_feedback_contract_for_loop_kinds():
    for kind in ("run", "wrap", "delegate"):
        out = _run(str(RENDER_COMBINATORS), "--kind", kind)
        assert "feedback_contract:" in out
        assert "id: IN1" in out
        assert "loop_scope: inner" in out
        assert "id: OUT1" in out
        assert "loop_scope: outer" in out
        assert "## 評価・改善ループ契約" in out


def test_render_combinators_skips_feedback_contract_for_non_loop_kinds():
    for kind in ("ref", "assign"):
        out = _run(str(RENDER_COMBINATORS), "--kind", kind)
        assert "feedback_contract:" not in out


def test_render_frontmatter_fills_feedback_contract_from_brief(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(
        json.dumps(
            {
                "skill_name": "run-demo-skill",
                "kind": "run",
                "output_contract": "demo artifact を生成する",
                "feedback_contract": {
                    "max_iterations": 2,
                    "criteria": [
                        {
                            "id": "IN1",
                            "loop_scope": "inner",
                            "text": "demo lint が exit0",
                            "verify_by": "lint",
                        },
                        {
                            "id": "OUT1",
                            "loop_scope": "outer",
                            "text": "demo の4条件が PASS",
                            "verify_by": "elegant-review",
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    out = _run(
        str(RENDER_FRONTMATTER),
        "--name",
        "run-demo-skill",
        "--kind",
        "run",
        "--template",
        str(RUN_BUILD / "templates" / "run.md"),
        "--brief",
        str(brief),
    )
    assert "{{feedback_contract" not in out
    assert "max_iterations: 2" in out
    assert "text: demo lint が exit0" in out
    assert "text: demo の4条件が PASS" in out


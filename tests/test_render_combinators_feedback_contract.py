import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_BUILD = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
RENDER_COMBINATORS = RUN_BUILD / "scripts" / "render-combinators.py"
RENDER_FRONTMATTER = RUN_BUILD / "scripts" / "render-frontmatter.py"


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


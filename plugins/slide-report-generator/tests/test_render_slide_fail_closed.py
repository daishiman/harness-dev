"""Unknown slide types must never become a plausible message slide."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
RENDERER = PLUGIN_ROOT / "vendor" / "scripts" / "render-slide.cjs"


def test_unknown_slide_type_fails_without_writing_deck(tmp_path: Path) -> None:
    source = tmp_path / "structure.json"
    output = tmp_path / "deck"
    source.write_text(
        json.dumps(
            {
                "meta": {"title": "fail closed"},
                "slides": [
                    {"slideType": "diagram-does-not-exist", "content": {"title": "x"}}
                ],
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["node", str(RENDERER), str(source), "--out", str(output), "--no-validate"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 3
    assert "unknown slideType or missing template" in proc.stderr
    assert not (output / "index.html").exists()


def test_structural_slide_carries_referential_declaration() -> None:
    script = f"""
const {{ enrichSlideContext }} = require({json.dumps(str(RENDERER))});
const ctx = enrichSlideContext({{
  slideType: 'diagram-er',
  content: {{
    title: 'ER',
    entities: [{{name:'顧客', fields:['id']}}, {{name:'注文', fields:['顧客']}}],
    relations: [{{from:'顧客', to:'注文'}}],
  }},
}}, 0);
process.stdout.write(ctx.svg);
"""
    proc = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    assert "data-srg-declaration=" in proc.stdout
    assert "&quot;entities&quot;" in proc.stdout

"""FABE 5 variants have real, distinct deterministic render paths."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
RENDERER = PLUGIN_ROOT / "vendor" / "scripts" / "render-slide.cjs"
TEMPLATE_DIR = PLUGIN_ROOT / "vendor" / "scripts" / "templates"


def test_fabe_variants_render_distinct_svg_and_have_templates() -> None:
    variants = {
        "diagram-fabe-horizontal": {"items": ["F", "A", "B", "E"]},
        "diagram-fabe-vertical": {"layers": ["F", "A", "B", "E"]},
        "diagram-fabe-grid": {"items": ["F", "A", "B", "E"]},
        "diagram-fabe-timeline": {"events": ["F", "A", "B", "E"]},
        "diagram-fabe-circular": {"items": ["F", "A", "B", "E"]},
    }
    script = f"""
const {{ enrichSlideContext }} = require({json.dumps(str(RENDERER))});
const variants = {json.dumps(variants)};
const out = Object.fromEntries(Object.entries(variants).map(([slideType, content]) => [
  slideType,
  enrichSlideContext({{ slideType, content: {{ title: slideType, ...content }} }}, 0).svg,
]));
process.stdout.write(JSON.stringify(out));
"""
    proc = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    rendered = json.loads(proc.stdout)

    assert set(rendered) == set(variants)
    assert all(svg.startswith("<svg") for svg in rendered.values())
    assert len(set(rendered.values())) == len(variants), "FABE variants collapsed to one drawing"

    for slide_type in variants:
        template = TEMPLATE_DIR / f"{slide_type}.html.tpl"
        assert template.is_file(), f"missing template for {slide_type}"
        assert f'data-slide-type="{slide_type}"' in template.read_text(encoding="utf-8")

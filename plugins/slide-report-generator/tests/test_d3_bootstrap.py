"""D3 types accepted by the schema have non-placeholder bootstrap cases."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP = PLUGIN_ROOT / "vendor" / "scripts" / "d3-bootstrap.cjs"


def test_d3_extended_cases_compile_and_are_registered() -> None:
    expected = [
        "radial-bar",
        "pyramid",
        "funnel",
        "waterfall",
        "roadmap",
        "vertical-timeline",
        "wordcloud",
        "chevron",
    ]
    script = f"""
const {{ renderD3BootstrapJs }} = require({json.dumps(str(BOOTSTRAP))});
const source = renderD3BootstrapJs();
new Function(source);
const expected = {json.dumps(expected)};
const missing = expected.filter((name) => !source.includes("case '" + name + "':"));
if (missing.length) {{ console.error(missing.join(',')); process.exit(2); }}
if (!source.includes('data-d3-fallback')) process.exit(3);
"""
    proc = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr

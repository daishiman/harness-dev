#!/usr/bin/env python3
"""visuals.json (output.schema.json 準拠) の網羅性/整合性を検証。

schema 形状: {"catalog_version": str, "sections": {"§N": [{figure_id,type,png_path,caption?}]}}
- 全 §0-§11 に 1-3 図が配置されているか (網羅性)
- type=svg の各エントリの png_path が out_dir に実在するか (整合性)
usage: verify-visuals.py <visuals.json> <out_dir>
"""
import json, sys
from pathlib import Path

REQUIRED_SECTIONS = [f"§{i}" for i in range(12)]  # §0-§11

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out_dir = Path(sys.argv[2])
sections = data.get("sections", {})

if not isinstance(sections, dict) or not sections:
    print("FAIL no sections", file=sys.stderr); sys.exit(1)

errors = []

# 網羅性: 全 12 セクションに 1-3 図
for sec in REQUIRED_SECTIONS:
    figs = sections.get(sec)
    if not figs:
        errors.append(f"missing section {sec}")
    elif not (1 <= len(figs) <= 3):
        errors.append(f"section {sec} has {len(figs)} figures (must be 1-3)")

# 整合性: type=svg は対応 PNG が実在する必要がある
for sec, figs in sections.items():
    for fig in figs or []:
        if fig.get("type") == "svg":
            p = fig.get("png_path", "")
            if not p or not (out_dir / Path(p).name).exists():
                errors.append(f"{sec}/{fig.get('figure_id')}: missing PNG {p}")

if errors:
    print("FAIL " + "; ".join(errors), file=sys.stderr); sys.exit(1)
print("PASS")

#!/usr/bin/env python3
# /// script
# name: build-subagent
# purpose: Emit a Claude Code subagent markdown derived from a SKILL.md
# inputs:
#   - argv: --skill-name, --skill-md, --output-dir, --model
# outputs:
#   - file: <output-dir>/<skill-name>-subagent.md
#   - stdout: generated path
# contexts: [C]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""Generate a subagent definition (.claude/agents/<name>-subagent.md) from a
SKILL.md. Stdlib only. Simple YAML 1-level parser tuned for SKILL frontmatter.

Usage:
  build-subagent.py --skill-name run-build-skill \\
      --skill-md /path/to/SKILL.md \\
      [--output-dir .claude/agents/]

Output format (Anthropic Claude Code subagent spec):
  ---
  name: <skill-name>-subagent
  description: <from SKILL.md description>
  tools: <comma-joined from allowed-tools>
  model: opus  # default changed to opus (PF-F3-001)
  ---
  # role / thinking / output sections derived from SKILL.md
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_raw, body = parts[1], parts[2]
    fm: dict = {}
    cur_list_key: str | None = None
    for line in fm_raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and cur_list_key:
            fm[cur_list_key].append(line[4:].strip())
            continue
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            fm[key] = []
            cur_list_key = key
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key] = [v.strip() for v in inner.split(",") if v.strip()] if inner else []
            cur_list_key = None
        else:
            fm[key] = val.strip().strip('"').strip("'")
            cur_list_key = None
    return fm, body


def extract_section(body: str, heading: str) -> str:
    pat = re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)
    m = pat.search(body)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^##\s", body[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(body)
    return body[start:end].strip()


def map_tools(allowed: list[str] | str) -> str:
    if isinstance(allowed, str):
        items = [allowed]
    else:
        items = list(allowed or [])
    # strip parenthesized arg patterns: "Bash(python3 *)" -> "Bash"
    cleaned = []
    seen = set()
    for t in items:
        base = re.split(r"[\s(]", t, 1)[0].strip()
        if base and base not in seen:
            cleaned.append(base)
            seen.add(base)
    return ", ".join(cleaned)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--skill-md", required=True)
    ap.add_argument("--output-dir", default=".claude/agents/")
    ap.add_argument("--model", default="opus")  # PF-F3-001: 全Opus既定 (ユーザー方針)
    args = ap.parse_args()

    skill_md = Path(args.skill_md)
    if not skill_md.exists():
        print(f"SKILL.md not found: {skill_md}", file=sys.stderr)
        return 2
    text = skill_md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    desc = fm.get("description", "") or f"Subagent derived from {args.skill_name}"
    tools = map_tools(fm.get("allowed-tools", []))
    steps = extract_section(body, "## Steps")
    purpose = extract_section(body, "## Purpose & Output Contract")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.skill_name}-subagent.md"

    fm_lines = [
        "---",
        f"name: {args.skill_name}-subagent",
        f"description: {desc}",
    ]
    if tools:
        fm_lines.append(f"tools: {tools}")
    fm_lines.append(f"model: {args.model}")
    fm_lines.append("---")

    md = "\n".join(fm_lines) + "\n\n"
    md += f"# 役割\n\n{purpose or desc}\n\n"
    md += "# 思考プロセス\n\n"
    if steps:
        # Reduce: keep only step headings + 1st line for brevity
        lines = []
        for ln in steps.splitlines():
            if ln.startswith("### "):
                lines.append(f"- {ln[4:].strip()}")
        md += ("\n".join(lines) if lines else steps) + "\n\n"
    else:
        md += "- (Steps section not found in SKILL.md)\n\n"
    md += "# 出力\n\n"
    md += (purpose or "(Output contract not specified)") + "\n"

    out_path.write_text(md, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

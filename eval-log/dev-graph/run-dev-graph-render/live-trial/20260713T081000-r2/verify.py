#!/usr/bin/env python3
import hashlib, json, os, re, sys
from pathlib import Path

graph_path = Path(sys.argv[1])
html_path = Path(sys.argv[2])

inp = graph_path.read_bytes()
out = html_path.read_bytes()
html_text = out.decode("utf-8")

input_sha = hashlib.sha256(inp).hexdigest()
output_sha = hashlib.sha256(out).hexdigest()

ext_scripts = len(re.findall(r'<script[^>]+src=', html_text))
ext_links = len(re.findall(r'<link[^>]+href=', html_text))
has_svg = '<svg' in html_text
has_inline_js = '<script>' in html_text
has_style = '<style>' in html_text
node_count = html_text.count('class="node ')

# Expected from receipt
expected_input = "e49f6b1f8bd725526bd3e4646191a1253db7813aa045d54a37c77663f544872a"
expected_output = "7735cd3d6bbadd41e7198636d2a85f6dba86f3d64770a92b9fb626ffb61ca83d"

result = {
    "input_sha256_match": input_sha == expected_input,
    "output_sha256_match": output_sha == expected_output,
    "input_sha256": input_sha,
    "output_sha256": output_sha,
    "external_script_refs": ext_scripts,
    "external_link_refs": ext_links,
    "has_svg": has_svg,
    "has_inline_js": has_inline_js,
    "has_style": has_style,
    "node_count": node_count,
    "zero_external_deps": ext_scripts == 0 and ext_links == 0,
    "all_pass": (
        input_sha == expected_input
        and output_sha == expected_output
        and ext_scripts == 0
        and ext_links == 0
        and has_svg
        and has_inline_js
        and has_style
        and node_count == 1
    ),
}
json.dump(result, sys.stdout, indent=2)
print()

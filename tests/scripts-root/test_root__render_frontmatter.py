"""Genuine functional tests for scripts/render-frontmatter.py (repo-root variant).

NOTE: this is a DIFFERENT script from
plugins/harness-creator/skills/run-build-skill/scripts/render-frontmatter.py
(tested in test_harness_creator__render_frontmatter.py). This variant exposes
render(brief: dict) -> str, needs_os_preamble(brief) -> bool, and a main() that
reads a brief JSON file and writes/prints SKILL.md.

Pure functions are called with real briefs and the exact emitted string is
asserted (frontmatter ordering, list expansion, OS-preamble injection, body
newline normalization). main() is driven via subprocess over real tmp_path
briefs covering: stdout render, --output write, missing-arg, missing-file, bad
--output, and JSON parse error. The script declares dependencies = [] and has no
external I/O, so no monkeypatching of network/keychain is required; --output only
ever writes under tmp_path.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "render-frontmatter.py"


def _load():
    spec = importlib.util.spec_from_file_location("render_frontmatter_root", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mod = _load()


# ── needs_os_preamble (pure) ──────────────────────────────────────────────
def test_needs_os_preamble_bool_true():
    assert mod.needs_os_preamble({"cross_platform": True}) is True


def test_needs_os_preamble_string_true():
    assert mod.needs_os_preamble({"os_preamble_required": "true"}) is True
    assert mod.needs_os_preamble({"cross_platform": "True"}) is True


def test_needs_os_preamble_false_and_absent():
    assert mod.needs_os_preamble({}) is False
    assert mod.needs_os_preamble({"cross_platform": False}) is False
    assert mod.needs_os_preamble({"cross_platform": "no"}) is False


def test_needs_os_preamble_either_flag():
    # only os_preamble_required set -> still True
    assert mod.needs_os_preamble({"cross_platform": False, "os_preamble_required": True}) is True


# ── render (pure) ─────────────────────────────────────────────────────────
def test_render_minimal_frontmatter_and_body():
    out = mod.render({"name": "run-foo", "description": "do foo", "body": "Hello"})
    assert out == "---\nname: run-foo\ndescription: do foo\n---\n\nHello\n"


def test_render_appends_trailing_newline_only_when_missing():
    with_nl = mod.render({"name": "n", "body": "line\n"})
    assert with_nl.endswith("line\n")
    assert not with_nl.endswith("line\n\n")


def test_render_omits_empty_name_and_description():
    out = mod.render({"body": "B"})
    assert "name:" not in out
    assert "description:" not in out
    assert out.startswith("---\n---\n\nB")


def test_render_optional_scalar_field():
    out = mod.render({"name": "n", "kind": "run", "body": "B"})
    assert "kind: run\n" in out


def test_render_optional_list_field_expands_to_yaml_sequence():
    out = mod.render({"name": "n", "allowed_tools": ["Read", "Bash"], "body": "B"})
    assert "allowed-tools:\n  - Read\n  - Bash\n" in out


def test_render_field_key_remapping():
    # argument_hint brief key maps to argument-hint frontmatter key
    out = mod.render({"name": "n", "argument_hint": "<file>", "body": "B"})
    assert "argument-hint: <file>\n" in out
    assert "argument_hint:" not in out


def test_render_injects_os_preamble_when_cross_platform():
    out = mod.render({"name": "n", "cross_platform": True, "body": "Body"})
    assert mod.OS_PREAMBLE in out
    # preamble sits between frontmatter terminator and body
    assert out.index("---\n\n") < out.index(mod.OS_PREAMBLE) < out.index("Body")


def test_render_no_preamble_when_not_cross_platform():
    out = mod.render({"name": "n", "body": "Body"})
    assert mod.OS_PREAMBLE not in out


def test_render_skips_none_optional_fields():
    out = mod.render({"name": "n", "model": None, "body": "B"})
    assert "model:" not in out


# ── main() via subprocess ─────────────────────────────────────────────────
def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT, text=True, capture_output=True,
    )


def _write_brief(tmp_path, data) -> Path:
    p = tmp_path / "brief.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_cli_no_args_exit_2():
    proc = _run()
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_cli_brief_not_found_exit_2():
    proc = _run("/no/such/brief.json")
    assert proc.returncode == 2
    assert "not found" in proc.stderr


def test_cli_output_flag_without_path_exit_2(tmp_path):
    brief = _write_brief(tmp_path, {"name": "n", "body": "B"})
    proc = _run(str(brief), "--output")
    assert proc.returncode == 2
    assert "--output requires a path" in proc.stderr


def test_cli_invalid_json_exit_1(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    proc = _run(str(bad))
    assert proc.returncode == 1
    assert "JSON parse error" in proc.stderr


def test_cli_renders_to_stdout(tmp_path):
    brief = _write_brief(tmp_path, {"name": "run-x", "description": "d", "body": "BODY"})
    proc = _run(str(brief))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "---\nname: run-x\ndescription: d\n---\n\nBODY\n"


def test_cli_writes_output_file(tmp_path):
    brief = _write_brief(
        tmp_path, {"name": "run-x", "body": "B", "cross_platform": True}
    )
    out = tmp_path / "SKILL.md"
    proc = _run(str(brief), "--output", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "ok: wrote" in proc.stdout
    text = out.read_text(encoding="utf-8")
    assert text.startswith("---\nname: run-x\n")
    assert mod.OS_PREAMBLE in text

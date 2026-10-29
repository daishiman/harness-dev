"""C11 の heading_missing: 一度も書かれていない必須見出しを readiness の欠落として拾う。

placeholder_only_section は既にある見出しの本文しか見ないため、見出しそのものが無い artifact は
heading_missing でしか検出できない。既定では `artifact_readiness` へ報告するだけで、
`--strict-artifact-readiness` を付けたときだけ violation に格上げする。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
SCRIPT = SCRIPTS / "validate-graph-schema.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load():
    name = "validate_graph_schema_c11_heading_presence"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _specification_fixture(tmp_path: Path) -> tuple[dict, list[str], Path, str]:
    canonical = json.loads((PLUGIN / "templates/template-contract.json").read_text(encoding="utf-8"))
    artifact = tmp_path / "specs" / "spec.md"
    artifact.parent.mkdir()
    frontmatter = "\n".join([
        "---",
        "graph_node_id: placeholder-specification",
        "artifact_kind: specification",
        "file_path: specs/spec.md",
        "template_id: specification",
        "template_version: 1.0.0",
        "---",
        "",
    ])
    node = {
        "graph_node_id": "placeholder-specification",
        "artifact_kind": "specification",
        "file_path": "specs/spec.md",
        "template_id": "specification",
        "template_version": "1.0.0",
    }
    return node, canonical["artifacts"]["specification"]["required_sections"], artifact, frontmatter


def test_heading_missing_blocks_specification_readiness_when_heading_absent(tmp_path):
    """書かれなかった必須見出しは readiness の欠落として残る。"""
    mod = load()
    canonical = json.loads((PLUGIN / "templates/template-contract.json").read_text(encoding="utf-8"))
    artifact_contract = {
        "placeholder_tokens": canonical["placeholder_tokens"],
        "common_frontmatter": {"required": []},
        "artifacts": {"specification": canonical["artifacts"]["specification"]},
    }
    node, required, artifact, frontmatter = _specification_fixture(tmp_path)

    # placeholder_only_section は既にある見出ししか見ない。
    artifact.write_text(frontmatter + f"# {required[0]}\n\n本文。\n", encoding="utf-8")
    findings = mod.readiness_findings([node], tmp_path, artifact_contract)
    assert {item["code"] for item in findings} == {"heading_missing"}
    assert {item["detail"] for item in findings} == set(required[1:])
    assert mod.readiness_missing_sections(findings) == sorted(set(required[1:]))

    filled = "\n".join(f"## {section}\n\n実装・検証済みの具体的内容。" for section in required)
    artifact.write_text(frontmatter + filled + "\n", encoding="utf-8")
    assert mod.readiness_findings([node], tmp_path, artifact_contract) == []


def test_heading_missing_is_reported_by_default_and_enforced_only_when_strict(tmp_path):
    """既定は報告だけで C02 の draft 受付を壊さない。strict のときだけ violation になる。"""
    node, required, artifact, frontmatter = _specification_fixture(tmp_path)
    artifact.write_text(frontmatter + f"# {required[0]}\n\n本文。\n", encoding="utf-8")

    def run(*extra: str) -> dict:
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--graph", "-", "--repo-root", str(tmp_path), *extra],
            input=json.dumps([node]), capture_output=True, text=True, check=False,
        )
        assert proc.stdout, proc.stderr
        return json.loads(proc.stdout)

    default = run()
    readiness = default["artifact_readiness"]
    assert readiness["enforced"] is False
    assert readiness["status"] == "incomplete"
    assert readiness["missing_sections"] == sorted(set(required[1:]))
    assert not any(item["code"] == "heading_missing" for item in default["violations"])

    strict = run("--strict-artifact-readiness")
    assert strict["artifact_readiness"]["enforced"] is True
    promoted = {item["detail"] for item in strict["violations"] if item["code"] == "heading_missing"}
    assert promoted == set(required[1:])
    assert strict["valid"] is False

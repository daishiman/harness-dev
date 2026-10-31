"""C11 の本文 readiness: template 既定文のままの section と、kind ごとの必須見出しの選び方。

heading が全く無い場合の単独検証は test_validate_graph_schema_c11_heading_presence.py が持つ。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load():
    name = "validate_graph_schema_c11_heading_readiness"
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / "validate-graph-schema.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _contract_for(kind: str) -> tuple[dict, dict]:
    canonical = json.loads((PLUGIN / "templates/template-contract.json").read_text(encoding="utf-8"))
    return canonical, {
        "placeholder_tokens": canonical["placeholder_tokens"],
        "common_frontmatter": {"required": []},
        "artifacts": {kind: canonical["artifacts"][kind]},
    }


def _frontmatter(node_id: str, kind: str, path: str) -> str:
    return "\n".join([
        "---",
        f"graph_node_id: {node_id}",
        f"artifact_kind: {kind}",
        f"file_path: {path}",
        f"template_id: {kind}",
        "template_version: 1.0.0",
        "---",
        "",
    ])


@pytest.mark.parametrize(
    ("kind", "content_root"),
    [
        ("issue", "issues"),
        ("task", "tasks"),
        ("document", "docs"),
        ("specification", "specs"),
        ("architecture", "architecture"),
        ("feature", "features"),
    ],
)
def test_required_section_placeholders_make_readiness_incomplete(
    tmp_path, kind, content_root
):
    """template 本文のままの artifact と、本文を潰した変異は readiness を incomplete にする。"""
    mod = load()
    canonical, artifact_contract = _contract_for(kind)
    artifact = tmp_path / content_root / "placeholder.md"
    artifact.parent.mkdir()
    frontmatter = _frontmatter(f"placeholder-{kind}", kind, f"{content_root}/placeholder.md")
    template = (
        PLUGIN / "templates" / canonical["artifacts"][kind]["template"]
    ).read_text(encoding="utf-8")
    artifact.write_text(frontmatter + template, encoding="utf-8")
    node = {
        "graph_node_id": f"placeholder-{kind}",
        "artifact_kind": kind,
        "file_path": f"{content_root}/placeholder.md",
        "template_id": kind,
        "template_version": "1.0.0",
    }

    findings = mod.readiness_findings([node], tmp_path, artifact_contract)
    missing = canonical["artifacts"][kind]["required_sections"]
    assert {item["code"] for item in findings} == {"placeholder_only_section"}
    assert {item["detail"] for item in findings} == set(missing)
    assert mod.readiness_missing_sections(findings) == sorted(set(missing))

    filled = "\n".join(
        f"## {section}\n\n実装・検証済みの具体的内容。"
        + (" コマンド引数 `<feature-id>` は説明用の変数。" if section == "Handoff" else "")
        for section in missing
    )
    artifact.write_text(frontmatter + filled + "\n", encoding="utf-8")
    assert mod.readiness_findings([node], tmp_path, artifact_contract) == []

    crushed = "\n".join(f"## {section}\n" for section in missing)
    artifact.write_text(frontmatter + crushed + "\n", encoding="utf-8")
    mutated = mod.readiness_findings([node], tmp_path, artifact_contract)
    assert {item["detail"] for item in mutated} == set(missing)

    sentinel_target = missing[-1]
    sentinel_body = "\n".join(
        f"## {section}\n\n" + ("- TODO" if section == sentinel_target else "実装・検証済みの具体的内容。")
        for section in missing
    )
    artifact.write_text(frontmatter + sentinel_body + "\n", encoding="utf-8")
    assert mod.readiness_findings([node], tmp_path, artifact_contract) == [{
        "node": f"placeholder-{kind}",
        "code": "placeholder_only_section",
        "detail": sentinel_target,
    }]

    fenced_target = missing[-1]
    fenced_body = "\n".join(
        f"## {section}\n\n"
        + (
            "```text\ncanonical template example only\n```"
            if section == fenced_target
            else "実装・検証済みの具体的内容。"
        )
        for section in missing
    )
    artifact.write_text(frontmatter + fenced_body + "\n", encoding="utf-8")
    assert mod.readiness_findings([node], tmp_path, artifact_contract) == [{
        "node": f"placeholder-{kind}",
        "code": "placeholder_only_section",
        "detail": fenced_target,
    }]


def test_readiness_is_not_mixed_into_graph_validation(tmp_path):
    """C02 は template 既定文の draft を受け付ける。validate() へ本文 readiness を混ぜない。"""
    mod = load()
    canonical, artifact_contract = _contract_for("specification")
    artifact = tmp_path / "specs" / "placeholder.md"
    artifact.parent.mkdir()
    artifact.write_text(
        _frontmatter("placeholder-specification", "specification", "specs/placeholder.md")
        + (PLUGIN / "templates" / canonical["artifacts"]["specification"]["template"]).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    node = {
        "graph_node_id": "placeholder-specification",
        "artifact_kind": "specification",
        "file_path": "specs/placeholder.md",
        "template_id": "specification",
        "template_version": "1.0.0",
    }
    assert mod.artifact_findings([node], tmp_path, artifact_contract) == []
    assert mod.readiness_findings([node], tmp_path, artifact_contract)


def test_heading_missing_resolves_system_dev_planner_task_variants(tmp_path):
    """system-dev-planner 由来 task は conditional_required_sections の variant
    (軽量 3 見出しの `system_development_baseline` と標準 14 見出しの `system_development`) の
    いずれかに一致すれば heading_missing なし。manual origin の task は base required_sections で検査する。"""
    mod = load()
    assert "task" in mod.HEADING_MISSING_KINDS
    _, artifact_contract = _contract_for("task")

    baseline = tmp_path / "tasks" / "baseline.md"
    baseline.parent.mkdir()
    baseline.write_text(
        _frontmatter("baseline-task", "task", "tasks/baseline.md")
        + "## 正本仕様書\n\n参照。\n\n## 依存\n\nfeature内依存なし。\n\n## 実行契約\n\n契約本文。\n",
        encoding="utf-8",
    )
    baseline_node = {
        "graph_node_id": "baseline-task",
        "artifact_kind": "task",
        "file_path": "tasks/baseline.md",
        "template_id": "task",
        "template_version": "1.0.0",
        "source_lineage": {"origin_kind": "system-dev-planner"},
    }

    incomplete = tmp_path / "tasks" / "incomplete.md"
    incomplete.write_text(
        _frontmatter("incomplete-task", "task", "tasks/incomplete.md") + "## 依存\n\nfeature内依存なし。\n",
        encoding="utf-8",
    )
    incomplete_node = {
        "graph_node_id": "incomplete-task",
        "artifact_kind": "task",
        "file_path": "tasks/incomplete.md",
        "template_id": "task",
        "template_version": "1.0.0",
        "source_lineage": {"origin_kind": "system-dev-planner"},
    }

    standard = tmp_path / "tasks" / "standard.md"
    standard.write_text(
        _frontmatter("standard-task", "task", "tasks/standard.md")
        + "".join(
            f"## {section}\n\n実装・検証済みの具体的内容。\n\n"
            for section in artifact_contract["artifacts"]["task"]["conditional_required_sections"]["system_development"]
        ),
        encoding="utf-8",
    )
    standard_node = {
        "graph_node_id": "standard-task",
        "artifact_kind": "task",
        "file_path": "tasks/standard.md",
        "template_id": "task",
        "template_version": "1.0.0",
        "source_lineage": {"origin_kind": "system-dev-planner"},
    }

    manual_node = {**baseline_node, "graph_node_id": "manual-task", "source_lineage": {"origin_kind": "manual"}}

    findings = mod.readiness_findings(
        [baseline_node, incomplete_node, standard_node, manual_node], tmp_path, artifact_contract
    )
    by_node: dict[str, list[str]] = {}
    for item in findings:
        if item["code"] == "heading_missing":
            by_node.setdefault(item["node"], []).append(item["detail"])
    assert "baseline-task" not in by_node
    assert "standard-task" not in by_node
    assert set(by_node["incomplete-task"]) == {"正本仕様書", "実行契約"}
    assert set(by_node["manual-task"]) == set(artifact_contract["artifacts"]["task"]["required_sections"])


def test_architecture_is_subject_to_heading_missing_like_specification(tmp_path):
    """architecture も heading gate 対象にし、要件定義 import だけを条件付きで受理する。"""
    mod = load()
    assert mod.HEADING_MISSING_KINDS == {"architecture", "specification", "task"}
    _, artifact_contract = _contract_for("architecture")
    architecture = artifact_contract["artifacts"]["architecture"]
    required = architecture["required_sections"]

    bare = tmp_path / "architecture" / "bare.md"
    bare.parent.mkdir()
    bare.write_text(
        _frontmatter("bare-arch", "architecture", "architecture/bare.md")
        + "# 章 wrapper\n\n## 正本 (source of truth)\n\n参照。\n",
        encoding="utf-8",
    )
    bare_node = {
        "graph_node_id": "bare-arch",
        "artifact_kind": "architecture",
        "file_path": "architecture/bare.md",
        "template_id": "architecture",
        "template_version": "1.0.0",
        "source_lineage": {
            "origin_kind": "system-spec-harness",
            "source_path": "system-spec/testing-qa.md",
        },
    }
    findings = mod.readiness_findings([bare_node], tmp_path, artifact_contract)
    assert {item["code"] for item in findings} == {"heading_missing"}
    assert {item["detail"] for item in findings} == set(required)

    requirements = tmp_path / "architecture" / "requirements.md"
    requirements.write_text(
        _frontmatter("req-arch", "architecture", "architecture/requirements.md")
        + "".join(
            f"## {section}\n\n実装・検証済みの具体的内容。\n\n"
            for section in architecture["conditional_required_sections"]["system_spec_requirements"]
        ),
        encoding="utf-8",
    )
    requirements_node = {
        "graph_node_id": "req-arch",
        "artifact_kind": "architecture",
        "file_path": "architecture/requirements.md",
        "template_id": "architecture",
        "template_version": "1.0.0",
        "source_lineage": {
            "origin_kind": "system-spec-harness",
            "source_path": "system-spec/00-requirements-definition.md",
        },
    }
    assert mod.readiness_findings([requirements_node], tmp_path, artifact_contract) == []

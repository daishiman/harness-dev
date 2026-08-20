"""lint-plugin-composition.py の純関数 + main CLI 契約を network 無しで網羅する。

このスクリプトは plugin-composition.yaml (CapabilityBundle 宣言) の
(a) capabilities ref 重複 (b) ref 実在 (c) hooks 宣言↔plugin.json 配線対応
を FAIL、(d) contract.interface.outputs のパス実在を WARN で検査する純 lint
であり、実通信・実 keychain は一切叩かない。

本テストは:
  - parse_composition: flow 形 / block 形 (path キー) / quoted hook ref /
    outputs inline list / コメント・空行 skip / ref も path も無い entry の parse error
  - check_duplicate_refs: 重複なし / 重複あり
  - check_ref_exists: skill(SKILL.md) / agent(.md) / command(.md) の実在・不在 /
    malformed hook ref / 未知 kind の存在検査
  - check_hook_wiring: 件数一致 / 宣言過多 / 配線過多 / plugin.json 不在 (宣言あり・なし)
  - check_outputs: 実在パス / 不在パス WARN / glob 一致・不一致 / 概念名 skip
  - lint_composition: 合格 / capabilities 空 exit2 / 壊れた plugin.json exit2
  - main: 合格 OK / 違反 exit1 / 引数無し usage exit2 / --self-test exit0
  - repo 実ファイル: plugins/harness-creator/plugin-composition.yaml が PASS

を tmp_path 上に合格 fixture と各違反 fixture を作り実入力で genuine に assert する。
main は subprocess(sys.executable) で exit code / stdout / stderr を assert する。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-plugin-composition.py"
)
BUILD_TRACE_VALIDATOR = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "validate-build-trace.py"
)

_SPEC = importlib.util.spec_from_file_location("lint_plugin_composition_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# fixture builders
# --------------------------------------------------------------------------

VALID_COMPOSITION = """\
name: fixture-plugin
description: fixture plugin composition used by deterministic lint tests.
kind: plugin-composition
version: 1.2.3
owner: team-test

contract:
  interface:
    inputs: [user-request]
    outputs: [EVALS.json, proposals/*.md, CapabilityManifest]

capabilities:
  # comment line to skip
  - { kind: skill, ref: skills/run-alpha, tier: core }
  - { kind: agent, ref: agents/beta-agent, tier: core }
  - { kind: command, ref: commands/do-thing, tier: extension }
  - { kind: hook, ref: "hook:Stop/gamma-trigger", tier: core }
  - { kind: hook, ref: "hook:PostToolUse-EditWrite/delta-lint", tier: core }
"""

VALID_PLUGIN_JSON = {
    "name": "fixture-plugin",
    "hooks": {
        "Stop": [
            {"matcher": ".*", "hooks": [{"type": "command", "command": "python3 a.py"}]}
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [{"type": "command", "command": "python3 b.py"}],
            }
        ],
    },
}


def build_plugin(root: Path, composition: str, plugin_json: dict | None) -> Path:
    (root / "skills" / "run-alpha").mkdir(parents=True)
    (root / "skills" / "run-alpha" / "SKILL.md").write_text("# alpha\n", encoding="utf-8")
    (root / "agents").mkdir()
    (root / "agents" / "beta-agent.md").write_text("# beta\n", encoding="utf-8")
    (root / "commands").mkdir()
    (root / "commands" / "do-thing.md").write_text("# cmd\n", encoding="utf-8")
    (root / "EVALS.json").write_text("{}\n", encoding="utf-8")
    if plugin_json is not None:
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(plugin_json), encoding="utf-8"
        )
    comp = root / "plugin-composition.yaml"
    comp.write_text(composition, encoding="utf-8")
    return comp


# --------------------------------------------------------------------------
# parse_composition
# --------------------------------------------------------------------------

def test_parse_flow_entries_and_outputs():
    caps, outputs, errors = MOD.parse_composition(VALID_COMPOSITION)
    assert errors == []
    refs = [c["ref"] for c in caps]
    assert refs == [
        "skills/run-alpha",
        "agents/beta-agent",
        "commands/do-thing",
        "hook:Stop/gamma-trigger",
        "hook:PostToolUse-EditWrite/delta-lint",
    ]
    assert outputs == ["EVALS.json", "proposals/*.md", "CapabilityManifest"]


def test_parse_block_entries_with_path_key():
    text = (
        "name: x\n"
        "capabilities:\n"
        "  - kind: skill\n"
        "    path: skills/run-alpha/SKILL.md\n"
        "    responsibility: something\n"
        "  - kind: agent\n"
        "    ref: agents/beta-agent\n"
    )
    caps, outputs, errors = MOD.parse_composition(text)
    assert errors == []
    assert outputs == []
    assert caps[0]["path"] == "skills/run-alpha/SKILL.md"
    assert caps[1]["ref"] == "agents/beta-agent"


def test_parse_entry_without_ref_or_path_is_error():
    text = "capabilities:\n  - { kind: skill, tier: core }\n"
    _, _, errors = MOD.parse_composition(text)
    assert len(errors) == 1
    assert "no ref/path" in errors[0]


def test_parse_outputs_only_inside_contract_section():
    text = "other:\n  outputs: [x.json]\ncapabilities:\n  - { kind: skill, ref: skills/run-alpha }\n"
    _, outputs, _ = MOD.parse_composition(text)
    assert outputs == []


def test_parse_dependencies_flow_and_block_entries():
    text = (
        "dependencies:\n"
        "  - {from: skills/run-alpha, to: scripts/tool.py, type: calls}\n"
        "  - from: commands/do-thing.md\n"
        "    to: skills/run-alpha\n"
        "    type: calls\n"
    )
    dependencies, errors = MOD.parse_dependencies(text)
    assert errors == []
    assert dependencies == [
        {"from": "skills/run-alpha", "to": "scripts/tool.py", "type": "calls"},
        {"from": "commands/do-thing.md", "to": "skills/run-alpha", "type": "calls"},
    ]


def test_parse_dependencies_fails_closed_on_missing_type():
    dependencies, errors = MOD.parse_dependencies(
        "dependencies:\n  - {from: skills/run-alpha, to: scripts/tool.py}\n"
    )
    assert dependencies == []
    assert len(errors) == 1
    assert "missing type" in errors[0]


def test_parse_external_dependencies_with_cross_plugin_edges():
    external, errors = MOD.parse_external_dependencies(
        "external_dependencies:\n"
        "  shared-plugin:\n"
        "    version: \">=1.0.0 <2.0.0\"\n"
        "    relation: shared-runtime\n"
        "    edges:\n"
        "      - {from: skills/run-alpha, to: references/contract.md, type: reads}\n"
    )
    assert errors == []
    assert external == {
        "shared-plugin": {
            "version": ">=1.0.0 <2.0.0",
            "relation": "shared-runtime",
            "edges": [
                {
                    "from": "skills/run-alpha",
                    "to": "references/contract.md",
                    "type": "reads",
                }
            ],
        }
    }


def test_parse_external_dependencies_fails_closed_on_malformed_edge():
    external, errors = MOD.parse_external_dependencies(
        "external_dependencies:\n"
        "  shared-plugin:\n"
        "    version: 1.0.0\n"
        "    edges:\n"
        "      - {from: skills/run-alpha, to: references/contract.md}\n"
    )
    assert external["shared-plugin"]["edges"] == []
    assert any("missing type" in error for error in errors)


# --------------------------------------------------------------------------
# check_duplicate_refs
# --------------------------------------------------------------------------

def test_duplicate_refs_detected():
    caps = [
        {"kind": "skill", "ref": "skills/run-alpha"},
        {"kind": "skill", "ref": "skills/run-alpha"},
        {"kind": "agent", "ref": "agents/beta-agent"},
    ]
    findings = MOD.check_duplicate_refs(caps)
    assert len(findings) == 1
    assert "skills/run-alpha" in findings[0]
    assert "2 times" in findings[0]


def test_no_duplicates_no_findings():
    caps = [
        {"kind": "skill", "ref": "skills/run-alpha"},
        {"kind": "agent", "ref": "agents/beta-agent"},
    ]
    assert MOD.check_duplicate_refs(caps) == []


# --------------------------------------------------------------------------
# check_ref_exists
# --------------------------------------------------------------------------

def test_ref_exists_pass_and_fail(tmp_path):
    build_plugin(tmp_path, VALID_COMPOSITION, None)
    caps = [
        {"kind": "skill", "ref": "skills/run-alpha"},
        {"kind": "agent", "ref": "agents/beta-agent"},
        {"kind": "command", "ref": "commands/do-thing"},
        {"kind": "skill", "ref": "skills/run-ghost"},
        {"kind": "agent", "ref": "agents/ghost-agent"},
    ]
    findings = MOD.check_ref_exists(caps, tmp_path)
    assert len(findings) == 2
    assert any("run-ghost" in f for f in findings)
    assert any("ghost-agent" in f for f in findings)


def test_malformed_hook_ref_detected(tmp_path):
    caps = [{"kind": "hook", "ref": "hook:no-slash-name"}]
    findings = MOD.check_ref_exists(caps, tmp_path)
    assert len(findings) == 1
    assert "malformed hook ref" in findings[0]


def test_wellformed_hook_ref_skips_path_check(tmp_path):
    caps = [{"kind": "hook", "ref": "hook:PostToolUse-Edit-rubric/diff-rubric-impact"}]
    assert MOD.check_ref_exists(caps, tmp_path) == []


def test_unknown_kind_checks_bare_existence(tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "x.yaml").write_text("a: 1\n", encoding="utf-8")
    ok = [{"kind": "template", "ref": "templates/x.yaml"}]
    ng = [{"kind": "template", "ref": "templates/y.yaml"}]
    assert MOD.check_ref_exists(ok, tmp_path) == []
    assert len(MOD.check_ref_exists(ng, tmp_path)) == 1


# --------------------------------------------------------------------------
# check_hook_wiring
# --------------------------------------------------------------------------

HOOK_CAPS = [
    {"kind": "hook", "ref": "hook:Stop/gamma-trigger"},
    {"kind": "hook", "ref": "hook:PostToolUse-EditWrite/delta-lint"},
]


def test_hook_wiring_counts_match():
    assert MOD.check_hook_wiring(HOOK_CAPS, VALID_PLUGIN_JSON) == []


def test_hook_wiring_declared_more_than_wired():
    caps = HOOK_CAPS + [{"kind": "hook", "ref": "hook:Stop/extra-one"}]
    findings = MOD.check_hook_wiring(caps, VALID_PLUGIN_JSON)
    assert len(findings) == 1
    assert "Stop" in findings[0]
    assert "declares 2" in findings[0]


def test_hook_wiring_wired_more_than_declared():
    findings = MOD.check_hook_wiring(HOOK_CAPS[:1], VALID_PLUGIN_JSON)
    assert len(findings) == 1
    assert "PostToolUse" in findings[0]
    assert "declares 0" in findings[0]


def test_hook_wiring_plugin_json_missing_with_declared():
    findings = MOD.check_hook_wiring(HOOK_CAPS, None)
    assert len(findings) == 1
    assert "plugin.json not found" in findings[0]


def test_hook_wiring_plugin_json_missing_without_declared():
    assert MOD.check_hook_wiring([{"kind": "skill", "ref": "skills/x"}], None) == []


# --------------------------------------------------------------------------
# check_outputs (WARN のみ)
# --------------------------------------------------------------------------

def test_outputs_existing_and_missing(tmp_path):
    (tmp_path / "EVALS.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "lessons-learned").mkdir()
    (tmp_path / "lessons-learned" / "a.md").write_text("x\n", encoding="utf-8")
    warnings = MOD.check_outputs(
        ["EVALS.json", "lessons-learned/*.md", "proposals/*.md", "missing.json",
         "CapabilityManifest"],
        tmp_path,
    )
    assert len(warnings) == 2
    assert any("proposals/*.md" in w for w in warnings)
    assert any("missing.json" in w for w in warnings)


def test_outputs_concept_names_skipped(tmp_path):
    assert MOD.check_outputs(["CapabilityManifest", "completion-report"], tmp_path) == []


# --------------------------------------------------------------------------
# lint_composition (end-to-end)
# --------------------------------------------------------------------------

def test_lint_composition_pass_with_warn(tmp_path):
    comp = build_plugin(tmp_path, VALID_COMPOSITION, VALID_PLUGIN_JSON)
    findings, warnings, err = MOD.lint_composition(comp)
    assert err is None
    assert findings == []
    assert len(warnings) == 1
    assert "proposals/*.md" in warnings[0]


def test_lint_composition_empty_capabilities_is_parse_error(tmp_path):
    comp = tmp_path / "plugin-composition.yaml"
    comp.write_text("name: x\ncapabilities:\n", encoding="utf-8")
    findings, _, err = MOD.lint_composition(comp)
    assert err == 2
    assert any("no capabilities entries" in f for f in findings)


def test_lint_composition_broken_plugin_json_is_error(tmp_path):
    comp = build_plugin(tmp_path, VALID_COMPOSITION, None)
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "plugin.json").write_text("{broken", encoding="utf-8")
    findings, _, err = MOD.lint_composition(comp)
    assert err == 2
    assert any("plugin.json" in f for f in findings)


def test_lint_composition_external_hooks_manifest(tmp_path):
    plugin_json = {"name": "fixture-plugin", "hooks": "./hooks/hooks.json"}
    comp = build_plugin(tmp_path, VALID_COMPOSITION, plugin_json)
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks/hooks.json").write_text(
        json.dumps({"hooks": VALID_PLUGIN_JSON["hooks"]}), encoding="utf-8"
    )
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert findings == []


def test_lint_composition_external_hooks_manifest_escape_is_error(tmp_path):
    plugin_json = {"name": "fixture-plugin", "hooks": "../outside.json"}
    comp = build_plugin(tmp_path, VALID_COMPOSITION, plugin_json)
    findings, _, err = MOD.lint_composition(comp)
    assert err == 2
    assert any("external hooks path" in finding for finding in findings)


PARITY_COMPOSITION = """\
name: fixture-plugin
description: fixture plugin composition used by dependency parity tests.
kind: plugin-composition
version: 1.2.3
owner: team-test

capabilities:
  - {kind: skill, ref: skills/run-alpha, tier: core}
  - {kind: command, ref: commands/do-thing, tier: core}
  - {kind: script, ref: scripts/tool.py, tier: core}

dependencies:
  - {from: skills/run-alpha, to: scripts/tool.py, type: calls}
  - {from: commands/do-thing.md, to: skills/run-alpha, type: calls}
  - {from: commands/do-thing.md, to: scripts/tool.py, type: calls}
"""


def build_dependency_parity_plugin(tmp_path: Path, composition: str) -> Path:
    comp = build_plugin(tmp_path, composition, None)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "skills" / "run-alpha" / "SKILL.md").write_text(
        "---\nname: run-alpha\nscript_refs: [../../scripts/tool.py]\n---\n# alpha\n",
        encoding="utf-8",
    )
    (tmp_path / "commands" / "do-thing.md").write_text(
        "# dispatch\n\n| verb | dispatch |\n|---|---|\n"
        "| alpha | Skill `run-alpha` |\n| tool | `scripts/tool.py` |\n",
        encoding="utf-8",
    )
    return comp


def test_dependency_parity_positive_fixture(tmp_path):
    comp = build_dependency_parity_plugin(tmp_path, PARITY_COMPOSITION)
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert findings == []


def test_dependency_parity_rejects_missing_skill_script_ref_edge(tmp_path):
    composition = PARITY_COMPOSITION.replace(
        "  - {from: skills/run-alpha, to: scripts/tool.py, type: calls}\n", ""
    )
    comp = build_dependency_parity_plugin(tmp_path, composition)
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any(
        "missing calls dependency for skill script_ref: skills/run-alpha -> scripts/tool.py"
        in finding
        for finding in findings
    )


def test_dependency_parity_rejects_missing_command_dispatch_edges(tmp_path):
    composition = PARITY_COMPOSITION.replace(
        "  - {from: commands/do-thing.md, to: skills/run-alpha, type: calls}\n", ""
    ).replace(
        "  - {from: commands/do-thing.md, to: scripts/tool.py, type: calls}\n", ""
    )
    comp = build_dependency_parity_plugin(tmp_path, composition)
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any(
        "missing calls dependency for command dispatch: commands/do-thing.md -> skills/run-alpha"
        in finding
        for finding in findings
    )
    assert any(
        "missing calls dependency for command dispatch: commands/do-thing.md -> scripts/tool.py"
        in finding
        for finding in findings
    )


def _graph_composition(*dependency_lines: str, version: str = "1.2.3") -> str:
    return (
        "name: fixture-plugin\n"
        "description: fixture plugin composition used by graph validation tests.\n"
        "kind: plugin-composition\n"
        f"version: {version}\n"
        "owner: team-test\n\n"
        "capabilities:\n"
        "  - {kind: skill, ref: skills/run-alpha, tier: core}\n"
        "  - {kind: command, ref: commands/do-thing, tier: core}\n\n"
        "dependencies:\n"
        + "".join(f"  - {line}\n" for line in dependency_lines)
    )


def test_lint_rejects_non_semver_version(tmp_path):
    comp = build_plugin(tmp_path, _graph_composition(version="release-1"), None)
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any("version='release-1' must be SemVer X.Y.Z" in finding for finding in findings)


def test_lint_rejects_dangling_dependency_endpoint(tmp_path):
    comp = build_plugin(
        tmp_path,
        _graph_composition(
            "{from: skills/run-alpha, to: scripts/ghost.py, type: calls}"
        ),
        None,
    )
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any("dangling dependency endpoint: scripts/ghost.py" in finding for finding in findings)


def test_lint_rejects_dependency_cycle(tmp_path):
    comp = build_plugin(
        tmp_path,
        _graph_composition(
            "{from: skills/run-alpha, to: commands/do-thing, type: calls}",
            "{from: commands/do-thing, to: skills/run-alpha, type: calls}",
        ),
        None,
    )
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any("dependencies contains cycle" in finding for finding in findings)


def test_lint_rejects_exact_duplicate_dependency_edge(tmp_path):
    edge = "{from: skills/run-alpha, to: commands/do-thing, type: calls}"
    comp = build_plugin(tmp_path, _graph_composition(edge, edge), None)
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any("duplicate dependency edge" in finding for finding in findings)


def test_lint_allows_existing_plugin_local_resource_endpoint(tmp_path):
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "contract.md").write_text("contract\n", encoding="utf-8")
    composition = _graph_composition(
        "{from: skills/run-alpha, to: references/contract.md, type: reads}"
    )
    comp = build_plugin(tmp_path, composition, None)
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert findings == []


def test_lint_rejects_existing_but_undeclared_local_capability_endpoint(tmp_path):
    (tmp_path / "skills" / "run-hidden").mkdir(parents=True)
    (tmp_path / "skills" / "run-hidden" / "SKILL.md").write_text(
        "# hidden\n", encoding="utf-8"
    )
    composition = _graph_composition(
        "{from: skills/run-alpha, to: skills/run-hidden, type: calls}"
    )
    comp = build_plugin(tmp_path, composition, None)
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any("dangling dependency endpoint: skills/run-hidden" in finding for finding in findings)


def test_lint_rejects_cross_plugin_endpoint_hidden_in_local_dependencies(tmp_path):
    (tmp_path / ".git").mkdir()
    plugin = tmp_path / "plugins" / "fixture-plugin"
    sibling = tmp_path / "plugins" / "shared-plugin" / "references"
    sibling.mkdir(parents=True)
    (sibling / "contract.md").write_text("contract\n", encoding="utf-8")
    composition = _graph_composition(
        "{from: skills/run-alpha, to: ../shared-plugin/references/contract.md, type: reads}"
    )
    comp = build_plugin(plugin, composition, None)
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any("dangling dependency endpoint" in finding for finding in findings)


def _build_external_dependency_fixture(tmp_path: Path, *, edge_type: str = "reads") -> Path:
    (tmp_path / ".git").mkdir()
    local = tmp_path / "plugins" / "fixture-plugin"
    external = tmp_path / "plugins" / "shared-plugin"
    (external / "references").mkdir(parents=True)
    (external / "references" / "contract.md").write_text("contract\n", encoding="utf-8")
    (external / "plugin-composition.yaml").write_text(
        "name: shared-plugin\n"
        "description: external dependency target fixture plugin.\n"
        "kind: plugin-composition\nversion: 1.4.0\nowner: team-test\n"
        "capabilities:\n  - {kind: script, ref: references/contract.md}\n",
        encoding="utf-8",
    )
    composition = _graph_composition(
        "{from: skills/run-alpha, to: commands/do-thing, type: calls}"
    ) + (
        "\nexternal_dependencies:\n"
        "  shared-plugin:\n"
        "    version: \">=1.0.0 <2.0.0\"\n"
        "    edges:\n"
        f"      - {{from: skills/run-alpha, to: references/contract.md, type: {edge_type}}}\n"
    )
    return build_plugin(local, composition, None)


def test_lint_allows_cross_plugin_edge_only_in_explicit_external_contract(tmp_path):
    comp = _build_external_dependency_fixture(tmp_path)
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert findings == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda text: text.replace("version: \">=1.0.0 <2.0.0\"\n", ""), "version is required"),
        (lambda text: text.replace("references/contract.md", "references/missing.md"), "dangling external dependency endpoint"),
        (lambda text: text.replace("type: reads", "type: invents"), "type invalid"),
    ],
)
def test_lint_external_dependency_contract_fails_closed(tmp_path, mutation, expected):
    comp = _build_external_dependency_fixture(tmp_path)
    comp.write_text(mutation(comp.read_text(encoding="utf-8")), encoding="utf-8")
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any(expected in finding for finding in findings)


def test_lint_rejects_duplicate_external_dependency_edge(tmp_path):
    comp = _build_external_dependency_fixture(tmp_path)
    text = comp.read_text(encoding="utf-8")
    edge = "      - {from: skills/run-alpha, to: references/contract.md, type: reads}\n"
    comp.write_text(text + edge, encoding="utf-8")
    findings, _, err = MOD.lint_composition(comp)
    assert err is None
    assert any("duplicate external dependency edge" in finding for finding in findings)


def test_dependency_type_enum_is_loaded_from_capability_schema_ssot():
    assert MOD.ALLOWED_DEPENDENCY_TYPES == {
        "calls", "reads", "extends", "evaluates", "emits", "writes", "delegates", "deploys"
    }


# --------------------------------------------------------------------------
# main CLI (subprocess)
# --------------------------------------------------------------------------

def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_main_pass(tmp_path):
    comp = build_plugin(tmp_path, VALID_COMPOSITION, VALID_PLUGIN_JSON)
    proc = run_cli(str(comp))
    assert proc.returncode == 0
    assert "OK: 1 composition file(s) passed" in proc.stdout
    assert "WARN" in proc.stderr


def test_main_violation_exit1(tmp_path):
    dup = VALID_COMPOSITION + "  - { kind: skill, ref: skills/run-alpha, tier: core }\n"
    comp = build_plugin(tmp_path, dup, VALID_PLUGIN_JSON)
    proc = run_cli(str(comp))
    assert proc.returncode == 1
    assert "duplicate capability ref" in proc.stderr


@pytest.mark.parametrize(
    ("composition", "expected"),
    [
        (_graph_composition(version="release-1"), "must be SemVer X.Y.Z"),
        (
            _graph_composition(
                "{from: skills/run-alpha, to: scripts/ghost.py, type: calls}"
            ),
            "dangling dependency endpoint",
        ),
        (
            _graph_composition(
                "{from: skills/run-alpha, to: commands/do-thing, type: calls}",
                "{from: commands/do-thing, to: skills/run-alpha, type: calls}",
            ),
            "dependencies contains cycle",
        ),
        (
            _graph_composition(
                "{from: skills/run-alpha, to: commands/do-thing, type: calls}",
                "{from: skills/run-alpha, to: commands/do-thing, type: calls}",
            ),
            "duplicate dependency edge",
        ),
    ],
)
def test_main_public_cli_rejects_graph_counterexamples(tmp_path, composition, expected):
    comp = build_plugin(tmp_path, composition, None)
    proc = run_cli(str(comp))
    assert proc.returncode == 1
    assert expected in proc.stderr


def test_main_no_args_usage_exit2():
    proc = run_cli()
    assert proc.returncode == 2
    assert "usage" in proc.stderr


def test_main_self_test():
    proc = run_cli("--self-test")
    assert proc.returncode == 0
    assert "self-test ok" in proc.stdout


def test_all_repo_plugin_compositions_pass_both_public_validators():
    """Discovery is dynamic so a newly added composition cannot evade CI."""
    compositions = sorted((ROOT / "plugins").glob("*/plugin-composition.yaml"))
    assert compositions, "repo must contain at least one plugin composition"

    failures = []
    for composition in compositions:
        lint = run_cli(str(composition))
        build_trace = subprocess.run(
            [
                sys.executable,
                str(BUILD_TRACE_VALIDATOR),
                "--bundle",
                str(composition),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if lint.returncode != 0:
            failures.append(f"{composition}: public lint:\n{lint.stderr}")
        if build_trace.returncode != 0:
            failures.append(
                f"{composition}: build trace:\n{build_trace.stdout}{build_trace.stderr}"
            )

    assert failures == []


def test_governance_ci_discovers_all_plugin_compositions_dynamically():
    workflow = (ROOT / ".github" / "workflows" / "governance-check.yml").read_text(
        encoding="utf-8"
    )
    assert (
        "find plugins -mindepth 2 -maxdepth 2 -name plugin-composition.yaml -print0"
        in workflow
    )
    assert "lint-plugin-composition.py \"$composition\"" in workflow
    assert "validate-build-trace.py --bundle \"$composition\"" in workflow

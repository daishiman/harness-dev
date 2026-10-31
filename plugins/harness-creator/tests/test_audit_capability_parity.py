from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-capability-parity.py"

RUNTIME_ROOT_CONTRACT = """\
## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。
"""

# 日本語の正規形 (ja-contract-spec 第2節の5行をそのまま写す)。
RUNTIME_ROOT_CONTRACT_JA = """\
## 実行時のルートの決め方

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Code では、プラグインのルートとして `CLAUDE_PLUGIN_ROOT` を使う。
- Codex では、ホストが示したこの `SKILL.md` の絶対パスから上の階層へたどり、プラグインの定義ファイル（`.codex-plugin/plugin.json` か `.claude-plugin/plugin.json`）を持つ最も近い祖先を、論理上の `PLUGIN_ROOT` とする。
- 作業ディレクトリ（`cwd`）からプラグインのルートを推測しない。置き換える前のプレースホルダをそのままシェルへ渡さない。シェルを呼ぶたびに、その中で解決済みの絶対パスを `PLUGIN_ROOT` に入れる。
- `prompts/` の下のファイルも、このスキルの決まりに従う。
"""

RUNTIME_ROOT_CANONICAL_CONTRACT = """\
# Runtime portability

## product別 plugin root 契約

- Claude Code側は `${CLAUDE_PLUGIN_ROOT}` を使う。
- Codex側はabsolute `SKILL.md` pathから `.codex-plugin/plugin.json` または
  `.claude-plugin/plugin.json` を持つ祖先を解決する。
- cwd推測とliteral placeholderを禁止し、各shell invocationでrootを決定する。
- promptはowner Skill契約を継承する。
"""


def load_module():
    spec = importlib.util.spec_from_file_location("audit_capability_parity", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_plugin(repo: Path, *, with_command: bool = True) -> Path:
    plugin = repo / "plugins" / "sample-plugin"
    skill = plugin / "skills" / "run-sample"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: run-sample\ndescription: Run the sample capability.\n---\n",
        encoding="utf-8",
    )
    write_json(
        plugin / ".claude-plugin" / "plugin.json",
        {
            "name": "sample-plugin",
            "version": "1.0.0",
            "description": "Sample plugin",
            "author": {"name": "Harness"},
        },
    )
    write_json(
        plugin / ".codex-plugin" / "plugin.json",
        {
            "name": "sample-plugin",
            "version": "1.0.0",
            "description": "Sample plugin",
            "author": {"name": "Harness"},
            "skills": "./skills/",
        },
    )
    commands = []
    if with_command:
        commands = ["sample"]
        command = plugin / "commands" / "sample.md"
        command.parent.mkdir()
        command.write_text(
            "---\nname: sample\ndescription: Sample command.\n---\n\nUse `run-sample`.\n",
            encoding="utf-8",
        )
    write_json(
        plugin / "references" / "package-contract.json",
        {
            "package_mode": "bundle",
            "plugin_name": "sample-plugin",
            "entry_points": {
                "skills": ["run-sample"],
                "agents": [],
                "commands": commands,
                "hooks": [],
            },
            "depends_on": [],
            "runtime_dependencies": [],
            "codex_alternatives": {"commands": {}, "agents": {}, "hook_omissions": {}},
            "pkg_checks": {},
        },
    )
    capabilities = ["  - { kind: skill, ref: skills/run-sample, tier: core }"]
    if with_command:
        capabilities.append("  - { kind: command, ref: commands/sample, tier: core }")
    (plugin / "plugin-composition.yaml").write_text(
        "name: sample-plugin\nkind: plugin-composition\ncapabilities:\n"
        + "\n".join(capabilities)
        + "\ndependencies: []\n",
        encoding="utf-8",
    )
    write_json(
        repo / ".agents" / "plugins" / "marketplace.json",
        {
            "name": "fixture",
            "plugins": [
                {
                    "name": "sample-plugin",
                    "source": {"source": "local", "path": "./plugins/sample-plugin"},
                }
            ],
        },
    )
    return plugin


def codes(report: dict) -> set[str]:
    return {item["code"] for item in report["violations"]}


def add_runtime_root_contract(plugin: Path, contract: str = RUNTIME_ROOT_CONTRACT) -> Path:
    skill = plugin / "skills" / "run-sample" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    text = text.replace("\n---\n", "\nruntime_root_policy: host-skill-path\n---\n", 1)
    skill.write_text(text + "\n" + contract, encoding="utf-8")
    return skill


def write_dual_root_prompt(plugin: Path) -> None:
    prompt = plugin / "skills" / "run-sample" / "prompts" / "R1-run.md"
    prompt.parent.mkdir()
    prompt.write_text(
        "```bash\npython3 \"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/sample-plugin}}/scripts/run.py\"\n```\n",
        encoding="utf-8",
    )


def without_line(contract: str, prefix: str) -> str:
    lines = contract.splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith(prefix)]
    assert len(kept) == len(lines) - 1, prefix
    return "".join(kept)


def runtime_contract_messages(report: dict) -> list[str]:
    return [
        item["message"]
        for item in report["violations"]
        if item["code"] == "runtime_root_contract_missing"
    ]


def add_runtime_root_contract_redirect(plugin: Path, *, write_canonical: bool = True) -> Path:
    skill = plugin / "skills" / "run-sample" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    text = text.replace("\n---\n", "\nruntime_root_policy: host-skill-path\n---\n", 1)
    skill.write_text(
        text
        + "\n## Runtime root contract\n\n"
        + "[ref-cross-platform-runtime の共有正本]"
        + "(../ref-cross-platform-runtime/references/runtime-portability.md#product別-plugin-root-契約)"
        + " をそのまま適用する。\n",
        encoding="utf-8",
    )
    if write_canonical:
        canonical = (
            plugin
            / "skills"
            / "ref-cross-platform-runtime"
            / "references"
            / "runtime-portability.md"
        )
        canonical.parent.mkdir(parents=True)
        canonical.write_text(RUNTIME_ROOT_CANONICAL_CONTRACT, encoding="utf-8")
    return skill


def test_command_requires_explicit_codex_skill_alternative(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path)

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "FAIL"
    assert "command_alternative_missing" in codes(report)


def test_declared_command_skill_alternative_is_reachable(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path)
    path = plugin / "references" / "package-contract.json"
    contract = json.loads(path.read_text())
    contract["codex_alternatives"]["commands"]["sample"] = semantic_route(
        "sample-plugin", "run-sample"
    )
    write_json(path, contract)

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "PASS", report


def semantic_route(plugin: str, entry_point: str) -> dict:
    return {
        "relation": "semantic-equivalent",
        "purpose": f"Route the Claude surface through {entry_point} on Codex.",
        "arguments": {"policy": "preserve", "notes": "Forward user arguments."},
        "effect": {"policy": "equivalent", "notes": "Preserve the observable result."},
        "discovery": {"kind": "skill", "entry_points": [entry_point]},
        "owner_route": {"plugin": plugin, "entry_points": [entry_point]},
    }


def test_plain_skill_name_is_not_a_semantic_alternative_contract(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path)
    path = plugin / "references" / "package-contract.json"
    contract = json.loads(path.read_text())
    contract["codex_alternatives"]["commands"]["sample"] = "run-sample"
    write_json(path, contract)

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "FAIL"
    assert "semantic_alternative_invalid" in codes(report)


def test_semantic_owner_route_requires_dependency_and_owner_entry_point(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path)
    owner = make_plugin(tmp_path / "owner-repo", with_command=False)
    owner.rename(tmp_path / "plugins" / "owner-plugin")
    owner = tmp_path / "plugins" / "owner-plugin"
    for manifest in (owner / ".claude-plugin/plugin.json", owner / ".codex-plugin/plugin.json"):
        payload = json.loads(manifest.read_text())
        payload["name"] = "owner-plugin"
        write_json(manifest, payload)
    owner_contract_path = owner / "references/package-contract.json"
    owner_contract = json.loads(owner_contract_path.read_text())
    owner_contract["plugin_name"] = "owner-plugin"
    write_json(owner_contract_path, owner_contract)
    command_contract_path = plugin / "references/package-contract.json"
    command_contract = json.loads(command_contract_path.read_text())
    command_contract["codex_alternatives"]["commands"]["sample"] = semantic_route(
        "owner-plugin", "run-sample"
    )
    write_json(command_contract_path, command_contract)

    report = mod.audit_plugin(tmp_path, plugin)
    assert "semantic_owner_dependency_missing" in codes(report)

    command_contract["depends_on"] = ["owner-plugin"]
    write_json(command_contract_path, command_contract)
    report = mod.audit_plugin(tmp_path, plugin)
    assert "semantic_owner_dependency_missing" not in codes(report)
    assert "semantic_owner_entry_point_missing" not in codes(report)


def test_entry_point_inventory_is_bidirectional_and_duplicate_safe(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    extra = plugin / "skills" / "run-extra" / "SKILL.md"
    extra.parent.mkdir()
    extra.write_text("---\nname: run-extra\ndescription: Extra.\n---\n", encoding="utf-8")
    path = plugin / "references/package-contract.json"
    contract = json.loads(path.read_text())
    contract["entry_points"]["skills"] = ["run-sample", "run-sample"]
    write_json(path, contract)

    report = mod.audit_plugin(tmp_path, plugin)

    assert "entry_point_inventory_drift" in codes(report)
    assert "entry_point_duplicate" in codes(report)


def test_composition_is_required_and_matches_public_surfaces(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    composition = plugin / "plugin-composition.yaml"
    composition.unlink()

    report = mod.audit_plugin(tmp_path, plugin)
    assert "composition_missing" in codes(report)

    composition.write_text(
        "name: sample-plugin\nkind: plugin-composition\ncapabilities:\n"
        "  - { kind: skill, ref: skills/run-ghost, tier: core }\n",
        encoding="utf-8",
    )
    report = mod.audit_plugin(tmp_path, plugin)
    assert "composition_surface_drift" in codes(report)


def test_executable_bare_claude_plugin_root_in_prompt_fails(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    prompt = plugin / "skills" / "run-sample" / "prompts" / "R1-run.md"
    prompt.parent.mkdir()
    prompt.write_text(
        "```bash\npython3 \"$CLAUDE_PLUGIN_ROOT/scripts/run.py\"\n```\n",
        encoding="utf-8",
    )

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "FAIL"
    assert "bare_claude_plugin_root" in codes(report)


def test_dual_root_executable_requires_owner_host_skill_path_policy(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    prompt = plugin / "skills" / "run-sample" / "prompts" / "R1-run.md"
    prompt.parent.mkdir()
    prompt.write_text(
        "```bash\npython3 \"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/sample-plugin}}/scripts/run.py\"\n```\n",
        encoding="utf-8",
    )

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "FAIL"
    assert "runtime_root_policy_missing" in codes(report)


def test_dual_root_executable_with_owner_host_skill_path_policy_passes(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    add_runtime_root_contract(plugin)
    prompt = plugin / "skills" / "run-sample" / "prompts" / "R1-run.md"
    prompt.parent.mkdir()
    prompt.write_text(
        "```bash\npython3 \"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/sample-plugin}}/scripts/run.py\"\n```\n",
        encoding="utf-8",
    )

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "PASS", report


def test_dual_root_owner_can_reference_complete_canonical_runtime_contract(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    add_runtime_root_contract_redirect(plugin)
    prompt = plugin / "skills" / "run-sample" / "prompts" / "R1-run.md"
    prompt.parent.mkdir()
    prompt.write_text(
        "```bash\npython3 \"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/sample-plugin}}/scripts/run.py\"\n```\n",
        encoding="utf-8",
    )

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "PASS", report


def test_runtime_contract_redirect_fails_when_canonical_file_is_missing(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    add_runtime_root_contract_redirect(plugin, write_canonical=False)
    prompt = plugin / "skills" / "run-sample" / "prompts" / "R1-run.md"
    prompt.parent.mkdir()
    prompt.write_text(
        "```bash\npython3 \"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-plugins/sample-plugin}}/scripts/run.py\"\n```\n",
        encoding="utf-8",
    )

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "FAIL"
    assert "runtime_root_contract_missing" in codes(report)


def test_japanese_runtime_root_tokens_are_all_in_canonical_section():
    mod = load_module()

    assert len(mod.RUNTIME_ROOT_CONTRACT_TOKENS_JA) == 10
    assert mod.RUNTIME_ROOT_CONTRACT_TOKENS_JA[0] == "## 実行時のルートの決め方"
    assert [
        token for token in mod.RUNTIME_ROOT_CONTRACT_TOKENS_JA
        if token not in RUNTIME_ROOT_CONTRACT_JA
    ] == []


def test_dual_root_owner_with_japanese_runtime_contract_passes(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    add_runtime_root_contract(plugin, RUNTIME_ROOT_CONTRACT_JA)
    write_dual_root_prompt(plugin)

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "PASS", report


@pytest.mark.parametrize(
    "dropped_line",
    [
        "- `runtime_root_policy:",
        "- Claude Code では",
        "- Codex では",
        "- 作業ディレクトリ",
        "- `prompts/` の下",
    ],
)
def test_japanese_runtime_contract_missing_a_line_fails_with_japanese_gap(
    tmp_path, dropped_line
):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    contract = without_line(RUNTIME_ROOT_CONTRACT_JA, dropped_line)
    add_runtime_root_contract(plugin, contract)
    write_dual_root_prompt(plugin)

    report = mod.audit_plugin(tmp_path, plugin)

    expected = [
        token for token in mod.RUNTIME_ROOT_CONTRACT_TOKENS_JA if token not in contract
    ]
    assert expected
    assert report["verdict"] == "FAIL"
    # 日本語の組の方が多く揃っているので、日本語の欠けだけを示す。
    assert runtime_contract_messages(report) == [
        "owner skill runtime root body contract is incomplete: " + ", ".join(expected)
    ]


def test_english_runtime_contract_gap_still_reports_english_tokens(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    add_runtime_root_contract(
        plugin, without_line(RUNTIME_ROOT_CONTRACT, "- `prompts/` 配下")
    )
    write_dual_root_prompt(plugin)

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "FAIL"
    assert runtime_contract_messages(report) == [
        "owner skill runtime root body contract is incomplete: "
        "`prompts/` 配下はこのowner Skill契約を継承する"
    ]


def test_host_skill_root_resolver_ignores_unset_env_and_foreign_cwd(
    tmp_path, monkeypatch
):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    owner_skill = add_runtime_root_contract(plugin).resolve()
    foreign_cwd = tmp_path / "foreign-cwd"
    foreign_cwd.mkdir()
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.chdir(foreign_cwd)

    resolved = mod.resolve_host_skill_plugin_root(
        owner_skill, expected_plugin="sample-plugin"
    )

    assert resolved == plugin.resolve()
    with pytest.raises(mod.AuditError):
        mod.resolve_host_skill_plugin_root(
            Path("<absolute-skill-path>"), expected_plugin="sample-plugin"
        )


@pytest.mark.parametrize(
    "template_name",
    [
        "_base.md",
        "run.md",
        "ref.md",
        "assign-generator.md",
        "assign-evaluator.md",
        "wrap.md",
        "delegate.md",
        "agent-team.md",
        "orchestrator.md",
        "hook-integrated.md",
    ],
)
def test_skill_templates_require_host_skill_path_runtime_contract(template_name):
    template = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "run-build-skill"
        / "templates"
        / template_name
    ).read_text(encoding="utf-8")

    assert "runtime_root_policy: host-skill-path" in template
    assert "## 実行時のルートの決め方" in template
    assert "CLAUDE_PLUGIN_ROOT" in template
    assert "この `SKILL.md` の絶対パス" in template
    assert "cwd" in template
    assert "置き換える前のプレースホルダ" in template
    assert "シェルを呼ぶたび" in template
    assert "<!-- runtime-root-contract:v1 -->" in template
    # Resources are an explicit generation option, never claimed by every template.
    assert "`prompts/`" not in template


def test_capability_manifest_declares_host_skill_path_runtime_policy():
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "run-build-skill"
        / "references"
        / "capability-manifest.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    runtime_policy = schema["definitions"]["kindSkill"]["properties"][
        "runtime_root_policy"
    ]
    assert runtime_policy["enum"] == ["host-skill-path"]


def test_missing_hook_event_requires_explicit_omission_contract(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    claude = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text())
    claude["hooks"] = {
        "TaskCompleted": [
            {"hooks": [{"type": "command", "command": "python3 $CLAUDE_PLUGIN_ROOT/hooks/x.py"}]}
        ]
    }
    write_json(plugin / ".claude-plugin" / "plugin.json", claude)
    write_json(plugin / "hooks" / "hooks.json", {"hooks": {}})
    codex = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text())
    codex["hooks"] = "./hooks/hooks.json"
    write_json(plugin / ".codex-plugin" / "plugin.json", codex)

    report = mod.audit_plugin(tmp_path, plugin)
    assert "hook_omission_missing" in codes(report)

    contract_path = plugin / "references" / "package-contract.json"
    contract = json.loads(contract_path.read_text())
    contract["codex_alternatives"]["hook_omissions"]["TaskCompleted"] = {
        "reason": "Codex has no TaskCompleted event.",
        "replacement_events": ["PostToolUse", "SessionStart"],
        "replacement_skill": "run-sample",
    }
    write_json(contract_path, contract)
    report = mod.audit_plugin(tmp_path, plugin)
    assert "hook_omission_missing" not in codes(report)


def test_hook_omission_for_an_event_codex_exposes_is_rejected(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    contract_path = plugin / "references/package-contract.json"
    contract = json.loads(contract_path.read_text())
    contract["codex_alternatives"]["hook_omissions"]["SessionStart"] = {
        "reason": "stale omission",
        "replacement_events": [],
        "replacement_skill": "run-sample",
    }
    write_json(contract_path, contract)

    report = mod.audit_plugin(tmp_path, plugin)

    assert "hook_omission_orphan" in codes(report)


def test_current_repository_has_all_plugins_passing():
    mod = load_module()
    repo = Path(__file__).resolve().parents[3]

    report = mod.audit_repo(repo)

    expected_plugins = {
        path.parents[1].name
        for path in repo.glob("plugins/*/.claude-plugin/plugin.json")
    }
    assert expected_plugins
    assert {item["plugin"] for item in report["plugins"]} == expected_plugins
    assert report["plugin_count"] == len(expected_plugins)
    assert report["verdict"] == "PASS", {
        item["plugin"]: [v["code"] for v in item["violations"]]
        for item in report["plugins"]
        if item["verdict"] != "PASS"
    }


def test_repo_audit_aggregates_invalid_contracts_instead_of_aborting(tmp_path):
    source = make_plugin(tmp_path, with_command=False)
    peer = tmp_path / "plugins" / "peer-plugin"
    shutil.copytree(source, peer)
    for manifest_name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        path = peer / manifest_name
        payload = json.loads(path.read_text())
        payload["name"] = "peer-plugin"
        write_json(path, payload)
    composition = peer / "plugin-composition.yaml"
    composition.write_text(
        composition.read_text().replace("name: sample-plugin", "name: peer-plugin"),
        encoding="utf-8",
    )
    marketplace_path = tmp_path / ".agents/plugins/marketplace.json"
    marketplace = json.loads(marketplace_path.read_text())
    marketplace["plugins"].append(
        {
            "name": "peer-plugin",
            "source": {"source": "local", "path": "./plugins/peer-plugin"},
        }
    )
    write_json(marketplace_path, marketplace)
    for plugin in (source, peer):
        (plugin / "references/package-contract.json").write_text("{broken", encoding="utf-8")

    report = load_module().audit_repo(tmp_path)

    assert report["plugin_count"] == 2
    assert report["fail_count"] == 2
    assert all(
        "package_contract_missing" in {item["code"] for item in plugin["violations"]}
        for plugin in report["plugins"]
    )


def test_all_package_contracts_match_schema_and_feedback_boundary():
    repo = Path(__file__).resolve().parents[3]
    schema = json.loads(
        (
            repo
            / "plugins/harness-creator/skills/ref-pkg-contract/schemas/package-contract.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    contracts = sorted(repo.glob("plugins/*/references/package-contract.json"))

    expected_plugins = {
        path.parents[1].name
        for path in repo.glob("plugins/*/.claude-plugin/plugin.json")
    }
    assert expected_plugins
    assert {path.parents[1].name for path in contracts} == expected_plugins
    for path in contracts:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert list(validator.iter_errors(payload)) == [], path
        if path.parents[1].name == "harness-creator":
            continue
        feedback = [
            item
            for item in payload["runtime_dependencies"]
            if item["capability"] == "run-skill-feedback"
        ]
        assert feedback == [
            {
                "capability": "run-skill-feedback",
                "owner": "harness-creator",
                "classification": "owned-vendored",
                "local_path": "skills/run-skill-feedback",
                "owner_route": "skills/run-skill-feedback",
                "required_entry_point": "run-skill-feedback",
                "purpose": (
                    "Keep the current plugin-local bytes discoverable while declaring the "
                    "harness-owned runtime and repository references required by the feedback workflow."
                ),
            }
        ]
        assert "harness-creator" in payload["depends_on"]


def test_package_contract_schema_rejects_plain_skill_name_alternative():
    repo = Path(__file__).resolve().parents[3]
    schema = json.loads(
        (
            repo
            / "plugins/harness-creator/skills/ref-pkg-contract/schemas/package-contract.schema.json"
        ).read_text(encoding="utf-8")
    )
    payload = json.loads(
        (repo / "plugins/contract-generator/references/package-contract.json").read_text(
            encoding="utf-8"
        )
    )
    payload["codex_alternatives"]["agents"]["contract-draft-agent"] = "run-contract-generate"

    errors = list(Draft202012Validator(schema).iter_errors(payload))

    assert errors


def test_create_update_workflow_runs_capability_parity_gate():
    workflow = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "run-skill-create"
        / "workflow-manifest.json"
    )
    payload = json.loads(workflow.read_text(encoding="utf-8"))
    commands = [
        command
        for phase in payload.get("phases", [])
        for command in phase.get("commands", [])
        if isinstance(command, str)
    ]

    assert any("audit-capability-parity.py" in command for command in commands)


def test_declared_dependency_cycle_is_reported_as_resolvable_scc(tmp_path):
    make_plugin(tmp_path, with_command=False)
    source = tmp_path / "plugins" / "sample-plugin"
    peer = tmp_path / "plugins" / "peer-plugin"
    peer.mkdir(parents=True)
    for child in source.iterdir():
        if child.is_dir():
            shutil.copytree(child, peer / child.name)
    for manifest_name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        path = peer / manifest_name
        payload = json.loads(path.read_text())
        payload["name"] = "peer-plugin"
        write_json(path, payload)
    contract_path = peer / "references" / "package-contract.json"
    peer_contract = json.loads(contract_path.read_text())
    peer_contract["plugin_name"] = "peer-plugin"
    peer_contract["depends_on"] = ["sample-plugin"]
    write_json(contract_path, peer_contract)
    peer_composition = peer / "plugin-composition.yaml"
    peer_composition.write_text(
        (source / "plugin-composition.yaml")
        .read_text()
        .replace("name: sample-plugin", "name: peer-plugin"),
        encoding="utf-8",
    )
    sample_contract_path = source / "references" / "package-contract.json"
    sample_contract = json.loads(sample_contract_path.read_text())
    sample_contract["depends_on"] = ["peer-plugin"]
    write_json(sample_contract_path, sample_contract)
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text())
    marketplace["plugins"].append(
        {
            "name": "peer-plugin",
            "source": {"source": "local", "path": "./plugins/peer-plugin"},
        }
    )
    write_json(marketplace_path, marketplace)

    report = load_module().audit_repo(tmp_path)

    assert report["verdict"] == "PASS", report
    assert report["dependency_scc"] == [
        {
            "members": ["peer-plugin", "sample-plugin"],
            "edges": [
                {"from": "peer-plugin", "to": "sample-plugin"},
                {"from": "sample-plugin", "to": "peer-plugin"},
            ],
            "catalog": ".agents/plugins/marketplace.json",
            "resolvable": True,
        }
    ]


def test_cli_accepts_plugin_path_used_by_create_update_workflow(tmp_path):
    plugin = make_plugin(tmp_path, with_command=False)

    exit_code = load_module().main(
        ["--repo-root", str(tmp_path), "--plugin", str(plugin), "--json"]
    )

    assert exit_code == 0


def test_codex_hook_command_must_resolve_inside_plugin(tmp_path):
    plugin = make_plugin(tmp_path, with_command=False)
    hooks = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ${PLUGIN_ROOT}/hooks/missing.py",
                        }
                    ],
                }
            ]
        }
    }
    write_json(plugin / "hooks" / "hooks.json", hooks)
    for manifest_name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        path = plugin / manifest_name
        manifest = json.loads(path.read_text())
        manifest["hooks"] = "./hooks/hooks.json"
        write_json(path, manifest)

    report = load_module().audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "FAIL"
    assert "hook_command_unreachable" in codes(report)


def test_claude_only_mcp_requires_explicit_codex_alternative(tmp_path):
    plugin = make_plugin(tmp_path, with_command=False)
    write_json(plugin / ".mcp.json", {"mcpServers": {}})
    claude_path = plugin / ".claude-plugin" / "plugin.json"
    claude = json.loads(claude_path.read_text())
    claude["mcpServers"] = "./.mcp.json"
    write_json(claude_path, claude)

    mod = load_module()
    report = mod.audit_plugin(tmp_path, plugin)
    assert "component_alternative_missing" in codes(report)

    contract_path = plugin / "references" / "package-contract.json"
    contract = json.loads(contract_path.read_text())
    contract["codex_alternatives"]["component_omissions"] = {
        "mcpServers": {
            "reason": "Codex distribution uses the owning skill instead of this MCP surface.",
            "replacement_skill": "run-sample",
        }
    }
    write_json(contract_path, contract)

    report = mod.audit_plugin(tmp_path, plugin)
    assert "component_alternative_missing" not in codes(report)


# --- 入力の型崩れ: traceback で止めず exit 2 (verdict ERROR) とし、--all は残りの plugin を続ける ---


def edit_json(path: Path, mutate) -> None:
    payload = json.loads(path.read_text())
    mutate(payload)
    write_json(path, payload)


def make_owner_plugin(repo: Path) -> Path:
    owner = make_plugin(repo / "owner-repo", with_command=False)
    owner.rename(repo / "plugins" / "owner-plugin")
    owner = repo / "plugins" / "owner-plugin"
    for manifest in (owner / ".claude-plugin/plugin.json", owner / ".codex-plugin/plugin.json"):
        edit_json(manifest, lambda payload: payload.__setitem__("name", "owner-plugin"))
    edit_json(
        owner / "references/package-contract.json",
        lambda payload: payload.__setitem__("plugin_name", "owner-plugin"),
    )
    composition = owner / "plugin-composition.yaml"
    composition.write_text(
        composition.read_text().replace("name: sample-plugin", "name: owner-plugin"),
        encoding="utf-8",
    )
    edit_json(
        repo / ".agents/plugins/marketplace.json",
        lambda payload: payload["plugins"].append(
            {"name": "owner-plugin", "source": {"source": "local", "path": "./plugins/owner-plugin"}}
        ),
    )
    return owner


def runtime_dependency(**overrides) -> dict:
    item = {
        "capability": "run-sample",
        "owner": "owner-plugin",
        "classification": "runtime",
        "local_path": "skills/run-sample",
        "owner_route": "skills/run-sample",
        "required_entry_point": "run-sample",
        "purpose": "Use the owner skill at runtime.",
    }
    item.update(overrides)
    return item


def run_cli(mod, argv: list[str], capsys) -> tuple[int, dict | None, str]:
    code = mod.main(argv)
    captured = capsys.readouterr()
    return code, (json.loads(captured.out) if captured.out.strip() else None), captured.err


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("depends_on", {"owner-plugin": True}),
        ("depends_on", [{"name": "owner-plugin"}]),
        ("entry_points", ["run-sample"]),
        ("entry_points", {"skills": [{"name": "run-sample"}], "agents": [], "commands": [], "hooks": []}),
        ("runtime_dependencies", {"run-sample": {}}),
        ("runtime_dependencies", [1]),
        ("codex_alternatives", {"commands": [1], "agents": {}}),
        ("plugin_name", 1),
    ],
)
def test_contract_shape_break_is_an_input_error_not_a_traceback(tmp_path, capsys, field, value):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    edit_json(plugin / "references/package-contract.json", lambda payload: payload.__setitem__(field, value))

    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "ERROR", report
    assert "contract_shape_invalid" in codes(report)
    code, payload, _ = run_cli(mod, ["--repo-root", str(tmp_path), "--all"], capsys)
    assert code == 2
    assert payload["verdict"] == "ERROR" and payload["error_count"] == 1


def test_all_records_the_broken_plugin_as_error_and_keeps_auditing_the_rest(tmp_path, capsys):
    mod = load_module()
    make_plugin(tmp_path, with_command=False)
    owner = make_owner_plugin(tmp_path)
    edit_json(
        owner / "references/package-contract.json",
        lambda payload: payload.__setitem__("depends_on", [{"name": "sample-plugin"}]),
    )

    code, payload, err = run_cli(mod, ["--repo-root", str(tmp_path), "--all"], capsys)

    assert code == 2, err
    verdicts = {item["plugin"]: item["verdict"] for item in payload["plugins"]}
    assert verdicts == {"owner-plugin": "ERROR", "sample-plugin": "PASS"}
    assert (payload["plugin_count"], payload["pass_count"], payload["fail_count"], payload["error_count"]) == (
        2, 1, 1, 1,
    )


def test_owner_contract_with_array_entry_points_is_an_input_error(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path)
    owner = make_owner_plugin(tmp_path)
    edit_json(
        owner / "references/package-contract.json",
        lambda payload: payload.__setitem__("entry_points", ["run-sample"]),
    )

    def route_command(payload):
        payload["depends_on"] = ["owner-plugin"]
        payload["codex_alternatives"]["commands"]["sample"] = semantic_route("owner-plugin", "run-sample")

    edit_json(plugin / "references/package-contract.json", route_command)
    report = mod.audit_plugin(tmp_path, plugin)
    assert report["verdict"] == "ERROR"
    assert any(
        item["code"] == "contract_shape_invalid" and "owner owner-plugin" in item["message"]
        for item in report["violations"]
    )

    def route_runtime(payload):
        payload["codex_alternatives"]["commands"]["sample"] = semantic_route("sample-plugin", "run-sample")
        payload["runtime_dependencies"] = [runtime_dependency()]

    edit_json(plugin / "references/package-contract.json", route_runtime)
    edit_json(
        owner / "references/package-contract.json",
        lambda payload: payload.__setitem__("entry_points", {"skills": 5}),
    )
    report = mod.audit_plugin(tmp_path, plugin)
    assert report["verdict"] == "ERROR"
    assert "contract_shape_invalid" in codes(report)


def test_marketplace_with_non_array_plugins_stops_with_exit_2(tmp_path, capsys):
    mod = load_module()
    make_plugin(tmp_path, with_command=False)
    edit_json(tmp_path / ".agents/plugins/marketplace.json", lambda payload: payload.__setitem__("plugins", 5))

    code, payload, err = run_cli(mod, ["--repo-root", str(tmp_path), "--all"], capsys)

    assert code == 2 and payload is None
    assert "marketplace plugins must be an array" in err


def test_marketplace_entry_with_unhashable_name_does_not_crash(tmp_path):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    edit_json(
        tmp_path / ".agents/plugins/marketplace.json",
        lambda payload: payload["plugins"].append({"name": ["peer-plugin"]}),
    )
    edit_json(
        plugin / "references/package-contract.json",
        lambda payload: payload.__setitem__("depends_on", ["peer-plugin"]),
    )

    report = mod.audit_repo(tmp_path)

    assert report["verdict"] == "FAIL"
    assert "dependency_unreachable" in codes(report["plugins"][0])


def test_unreadable_json_is_error_but_a_missing_contract_stays_fail(tmp_path, capsys):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    contract = plugin / "references/package-contract.json"
    contract.write_bytes(b"\xff\xfe{")

    report = mod.audit_plugin(tmp_path, plugin)
    assert report["verdict"] == "ERROR"
    assert "package_contract_missing" in codes(report)

    contract.rename(plugin / "references/package-contract.json.bak")
    report = mod.audit_plugin(tmp_path, plugin)
    assert report["verdict"] == "FAIL"
    code, _, _ = run_cli(mod, ["--repo-root", str(tmp_path), "--all"], capsys)
    assert code == 1


def test_non_utf8_composition_is_reported_not_raised(tmp_path):
    plugin = make_plugin(tmp_path, with_command=False)
    (plugin / "plugin-composition.yaml").write_bytes(b"name: \xff\n")

    report = load_module().audit_plugin(tmp_path, plugin)

    assert "composition_missing" in codes(report)


def test_runtime_dependency_classification_array_is_a_violation(tmp_path):
    plugin = make_plugin(tmp_path, with_command=False)
    edit_json(
        plugin / "references/package-contract.json",
        lambda payload: payload.__setitem__(
            "runtime_dependencies", [runtime_dependency(classification=["runtime"])]
        ),
    )

    report = load_module().audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "FAIL"
    assert "runtime_dependency_invalid" in codes(report)


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"local_path": "../owner-plugin/skills/run-sample"}, "runtime_dependency_local_missing"),
        ({"local_path": "/etc"}, "runtime_dependency_local_missing"),
        ({"owner_route": "../sample-plugin/skills/run-sample"}, "runtime_dependency_owner_route_missing"),
        ({"owner": "../plugins/owner-plugin"}, "runtime_dependency_owner_route_missing"),
    ],
)
def test_runtime_dependency_paths_stay_inside_their_plugins(tmp_path, override, code):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)
    make_owner_plugin(tmp_path)

    def declare(payload):
        payload["depends_on"] = ["owner-plugin"]
        payload["runtime_dependencies"] = [runtime_dependency()]

    edit_json(plugin / "references/package-contract.json", declare)
    assert mod.audit_plugin(tmp_path, plugin)["verdict"] == "PASS"

    edit_json(
        plugin / "references/package-contract.json",
        lambda payload: payload.__setitem__("runtime_dependencies", [runtime_dependency(**override)]),
    )
    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "FAIL"
    assert code in codes(report)


def test_unexpected_shape_failure_is_recorded_as_error(tmp_path, monkeypatch):
    mod = load_module()
    plugin = make_plugin(tmp_path, with_command=False)

    def explode(_plugin):
        raise TypeError("unhashable type: 'dict'")

    monkeypatch.setattr(mod, "_portable_root_violations", explode)
    report = mod.audit_plugin(tmp_path, plugin)

    assert report["verdict"] == "ERROR"
    assert codes(report) == {"input_shape_unhandled"}


@pytest.mark.parametrize("layout", ["missing", "empty"])
def test_repo_root_without_plugins_is_exit_2(tmp_path, capsys, layout):
    mod = load_module()
    root = tmp_path / "repo"
    if layout == "empty":
        write_json(root / ".agents/plugins/marketplace.json", {"plugins": []})
        (root / "plugins").mkdir()

    code, payload, err = run_cli(mod, ["--repo-root", str(root), "--all"], capsys)

    assert code == 2 and payload is None
    assert err.strip()

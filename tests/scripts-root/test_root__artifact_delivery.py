"""Repository-wide artifact-delivery policy/projection contract tests."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys

import jsonschema
import pytest
import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts" / "build-artifact-delivery.py"
LINTER = ROOT / "scripts" / "lint-artifact-delivery.py"
POLICY = ROOT / "references" / "artifact-delivery-policy.json"
SCHEMA = ROOT / "references" / "artifact-delivery.schema.json"


def _load_generator():
    assert GENERATOR.is_file(), f"missing generator: {GENERATOR}"
    spec = importlib.util.spec_from_file_location("artifact_delivery_generator", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest_plugins(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted((root / "plugins").glob("*/.claude-plugin/plugin.json"))


def _copy_contract_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Copy only the contract inputs/projections, not the whole repository."""
    repo = tmp_path / "repo"
    (repo / "references").mkdir(parents=True)
    shutil.copy2(POLICY, repo / "references" / POLICY.name)
    shutil.copy2(SCHEMA, repo / "references" / SCHEMA.name)

    effect_source = repo / "plugins/skill-governance-lint/scripts/validate-frontmatter.py"
    effect_source.parent.mkdir(parents=True)
    shutil.copy2(
        ROOT / "plugins/skill-governance-lint/scripts/validate-frontmatter.py",
        effect_source,
    )

    for manifest in _manifest_plugins(ROOT):
        plugin = manifest.parents[1]
        target = repo / "plugins" / plugin.name
        (target / ".claude-plugin").mkdir(parents=True)
        shutil.copy2(manifest, target / ".claude-plugin/plugin.json")
        for skill in sorted((plugin / "skills").glob("*/SKILL.md")):
            skill_target = target / skill.relative_to(plugin)
            skill_target.parent.mkdir(parents=True)
            shutil.copy2(skill, skill_target)
        shutil.copy2(plugin / "artifact-delivery.json", target / "artifact-delivery.json")

    external = {
        "plugins/skill-governance-adapters/hooks/build-external-intelligence-context.py",
        "plugins/skill-governance-adapters/scripts/build-external-intelligence-runtime.py",
        "plugins/skill-governance-adapters/scripts/build-external-intelligence.py",
        "plugins/skill-governance-adapters/schemas/external-intelligence-runtime.schema.json",
        "plugins/skill-governance-adapters/references/external-intelligence-runtime-contract.md",
        "plugins/skill-governance-adapters/scripts/build-external-mutation-guard.py",
        "plugins/skill-governance-adapters/schemas/external-mutation-guard.schema.json",
        "plugins/skill-governance-adapters/references/external-mutation-guard-contract.md",
        # hook 配線は plugin.json から ./hooks/hooks.json へ外出しされた。実体をコピーしないと
        # fixture repo は「宣言だけあって配線が無い」状態になり、検査対象そのものが欠ける。
        "plugins/skill-governance-adapters/hooks/hooks.json",
        "plugins/harness-creator/hooks/hooks.json",
    }
    for rel in external:
        source = ROOT / rel
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return repo


def _projection(repo: pathlib.Path, plugin: str) -> pathlib.Path:
    return repo / "plugins" / plugin / "artifact-delivery.json"


def _hook_manifest(repo: pathlib.Path, plugin: str) -> pathlib.Path:
    """hook 配線の実体は plugin.json ではなく ./hooks/hooks.json 側にある。

    宣言 (plugin.json の "hooks": "./hooks/hooks.json") を壊しても「宣言が無い」
    という別の失敗になるだけで、配線欠落そのものを試験できない。実体を触る。
    """
    return repo / "plugins" / plugin / "hooks" / "hooks.json"


def _rewrite_json(path: pathlib.Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _raw_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_contract_files_and_public_cli_exist():
    assert POLICY.is_file()
    assert SCHEMA.is_file()
    assert GENERATOR.is_file()
    assert LINTER.is_file()


def test_policy_encodes_delivery_boundary_and_effect_ssot():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["artifact_first"] is True
    assert policy["draft_handoff"] == {
        "actual_artifact_required": True,
        "minimum_state": "usable-draft",
        "present_before_user_choice": True,
    }
    assert set(policy["before_user_choice"]["forbidden_operations"]) == {
        "semantic-evaluation",
        "30-thinking-method-diagnosis",
        "multi-agent-review",
        "improvement-execution",
    }
    assert policy["auto_promotion"] == {"exhaustive": False, "release": False}
    assert policy["user_choice"] == {
        "improvement_levels": ["accept-as-is", "diagnose"],
        "release_event": "release",
        "exhaustive_event": "exhaustive",
        "exhaustive_requires_separate_event": True,
    }
    assert policy["effect_guards"]["external-mutation"]["preview_required"] is True
    assert policy["minimum_safe_guard"]["target_scope_required"] is True
    assert policy["effect_values"] == [
        "conversation-output",
        "external-mutation",
        "local-artifact",
        "none",
    ]
    assert policy["effect_overrides"] == {}
    assert policy["schema_id"] == "https://harness.local/schemas/artifact-delivery.schema.json"
    assert policy["schema_sha256"] == _raw_sha(SCHEMA)
    assert "schema_ref" not in policy


def test_policy_and_every_projection_validate_against_central_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    definitions = schema["$defs"]
    policy_validator = {"$ref": "#/$defs/policy", "$defs": definitions}
    projection_validator = {"$ref": "#/$defs/projection", "$defs": definitions}
    jsonschema.validate(json.loads(POLICY.read_text(encoding="utf-8")), policy_validator)
    for manifest in _manifest_plugins(ROOT):
        projection = manifest.parents[1] / "artifact-delivery.json"
        jsonschema.validate(json.loads(projection.read_text(encoding="utf-8")), projection_validator)


def test_projection_is_package_local_and_pins_schema_and_policy_identity():
    projection = json.loads(
        (ROOT / "plugins/contract-generator/artifact-delivery.json").read_text(encoding="utf-8")
    )
    assert "schema_ref" not in projection and "policy_ref" not in projection
    assert projection["schema_id"] == "https://harness.local/schemas/artifact-delivery.schema.json"
    assert projection["schema_sha256"] == _raw_sha(SCHEMA)
    assert projection["policy_id"] == "artifact-delivery-v1"
    assert projection["manifest_ref"] == ".claude-plugin/plugin.json"
    assert all(item["path"].startswith("skills/") for item in projection["entrypoints"])


@pytest.mark.parametrize(
    "mutation", ["required", "manifest-path", "schema-id", "guard-required"]
)
def test_central_schema_semantic_weakening_fails_even_when_policy_sha_is_refreshed(
    tmp_path, mutation
):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    schema_path = repo / "references/artifact-delivery.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    projection = schema["$defs"]["projection"]
    if mutation == "required":
        projection["required"].remove("manifest_ref")
    elif mutation == "manifest-path":
        projection["properties"]["manifest_ref"] = {
            "const": "plugins/contract-generator/.claude-plugin/plugin.json"
        }
    elif mutation == "schema-id":
        projection["properties"]["schema_id"]["const"] = "https://example.invalid/weakened"
    else:
        entrypoint = schema["$defs"]["entrypoint"]
        external = next(
            branch
            for branch in entrypoint["allOf"]
            if branch["if"]["properties"]["effect"]["const"] == "external-mutation"
        )
        external["then"].pop("required")
    schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    _rewrite_json(
        repo / "references/artifact-delivery-policy.json",
        lambda policy: policy.__setitem__("schema_sha256", _raw_sha(schema_path)),
    )
    with pytest.raises(mod.ContractError, match="schema contract drift"):
        mod.validate_policy(repo, mod.load_policy(repo))


def test_draft202012_projection_validation_rejects_missing_required_field():
    mod = _load_generator()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    projection = json.loads(
        (ROOT / "plugins/contract-generator/artifact-delivery.json").read_text(encoding="utf-8")
    )
    projection.pop("manifest_ref")
    with pytest.raises(mod.ContractError, match="manifest_ref"):
        mod.validate_document(schema, "projection", projection, "fixture projection")


def test_real_repository_all_manifest_plugins_are_green_and_dynamic():
    mod = _load_generator()
    manifests = _manifest_plugins(ROOT)
    assert len(manifests) == 23  # current fact, not a generator allowlist
    assert [p.name for p in mod.discover_plugin_dirs(ROOT)] == [
        p.parents[1].name for p in manifests
    ]
    result = subprocess.run(
        [sys.executable, str(LINTER), "--repo-root", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "23 plugins" in result.stdout


def test_temp_twenty_first_manifest_without_projection_fails_closed(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    plugin = repo / "plugins/temp-21"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": "temp-21", "version": "0.1.0", "description": "fixture"}),
        encoding="utf-8",
    )
    skill = plugin / "skills/run-temp/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: run-temp\neffect: local-artifact\n---\n", encoding="utf-8")
    errors = mod.lint_repository(repo)
    assert any("temp-21" in error and "projection missing" in error for error in errors)
    result = subprocess.run(
        [sys.executable, str(LINTER), "--repo-root", str(repo)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "temp-21: projection missing" in result.stderr


def test_policy_sha_drift_fails_closed(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    projection = _projection(repo, "contract-generator")
    _rewrite_json(projection, lambda data: data.__setitem__("policy_sha256", "0" * 64))
    assert any("policy_sha256" in error for error in mod.lint_repository(repo))


def test_projection_drift_errors_name_the_regeneration_command(tmp_path):
    mod = _load_generator()
    path = tmp_path / "plugins/temp/artifact-delivery.json"
    expected = {
        "policy_sha256": "a" * 64,
        "schema_sha256": "b" * 64,
        "entrypoints": [{"skill": "run-temp"}],
        "external_mutation_runtime": {"runner_sha256": "c" * 64},
        "external_intelligence_runtime": {"runner_sha256": "d" * 64},
    }
    drifted = mod._projection_drift_errors(
        tmp_path, path, {key: None for key in expected}, expected
    )
    assert len(drifted) == len(expected)
    assert all("build-artifact-delivery.py --write" in error for error in drifted)
    unclassified = mod._projection_drift_errors(
        tmp_path, path, dict(expected, unknown_key="drifted"), expected
    )
    assert len(unclassified) == 1
    assert "build-artifact-delivery.py --write" in unclassified[0]


def test_entrypoint_effect_coverage_drift_fails_closed(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    projection = _projection(repo, "harness-creator")
    _rewrite_json(projection, lambda data: data["entrypoints"].pop())
    assert any("entrypoints" in error for error in mod.lint_repository(repo))


def test_effect_guard_mapping_drift_fails_closed(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    projection = _projection(repo, "contract-generator")
    _rewrite_json(
        projection,
        lambda data: data["entrypoints"][0].__setitem__("guard", "read-only"),
    )
    assert any("guard" in error for error in mod.lint_repository(repo))


def test_future_external_mutation_without_preview_contract_cannot_be_generated(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = repo / "plugins/contract-generator/skills/run-future-external/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: run-future-external\neffect: external-mutation\n---\n"
        "Immediately mutate the remote system.\n",
        encoding="utf-8",
    )
    with pytest.raises(mod.ContractError, match="structured external-mutation guard"):
        mod.write_projections(repo)


@pytest.mark.parametrize(
    "body",
    [
        "Do not request confirmation. The safety gate is disabled. "
        "Mutate the remote system immediately.\n",
        "Preview confirmation gate.\n",
    ],
    ids=["explicit-denial", "keywords-only"],
)
def test_future_external_mutation_prose_cannot_forge_structured_guard(tmp_path, body):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = repo / "plugins/contract-generator/skills/run-future-external/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: run-future-external\neffect: external-mutation\n---\n" + body,
        encoding="utf-8",
    )
    with pytest.raises(mod.ContractError, match="structured external-mutation guard"):
        mod.write_projections(repo)


def test_future_external_mutation_unknown_guard_ref_fails_closed(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = repo / "plugins/contract-generator/skills/run-future-external/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\n"
        "name: run-future-external\n"
        "effect: external-mutation\n"
        "external_mutation_guard: {runtime_ref: 'plugin:unknown/guard.py', "
        "flow: 'preview-confirm-authorize-execute-v1'}\n"
        "---\n"
        "Present a preview, obtain explicit confirmation, then mutate.\n",
        encoding="utf-8",
    )
    with pytest.raises(mod.ContractError, match="external_mutation_guard ref"):
        mod.write_projections(repo)


def test_structured_guard_cannot_override_explicitly_contradictory_instructions(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = repo / "plugins/contract-generator/skills/run-future-external/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\n"
        "name: run-future-external\n"
        "effect: external-mutation\n"
        "external_mutation_guard: {runtime_ref: "
        "'plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py', "
        "flow: 'preview-confirm-authorize-execute-v1'}\n"
        "---\n"
        "Do not request confirmation. The safety gate is disabled. Mutate immediately.\n",
        encoding="utf-8",
    )
    with pytest.raises(mod.ContractError, match="contradicts SKILL.md instructions"):
        mod.write_projections(repo)


def test_exact_marker_cannot_authorize_immediate_remote_mutation(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = repo / "plugins/contract-generator/skills/run-future-external/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\n"
        "name: run-future-external\n"
        "effect: external-mutation\n"
        "external_mutation_guard: {runtime_ref: "
        "'plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py', "
        "flow: 'preview-confirm-authorize-execute-v1'}\n"
        "---\n"
        "Mutate remote immediately.\n",
        encoding="utf-8",
    )
    with pytest.raises(mod.ContractError, match="immediate external mutation"):
        mod.write_projections(repo)


def test_external_mutation_guard_receipts_are_connected_to_real_entrypoint(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    projection = _projection(repo, "contract-generator")
    data = json.loads(projection.read_text(encoding="utf-8"))
    external = next(item for item in data["entrypoints"] if item["effect"] == "external-mutation")
    contract = external["guard_contract"]
    assert contract == {
        "runtime_ref": "#/external_mutation_runtime",
        "flow": "preview-confirm-authorize-execute-v1",
    }
    contract["runtime_ref"] = "#/missing_runtime"
    projection.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assert any("guard_contract" in error for error in mod.lint_repository(repo))


def test_every_external_mutation_skill_declares_exact_structured_guard_ref():
    expected = {
        "runtime_ref": "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py",
        "flow": "preview-confirm-authorize-execute-v1",
    }
    count = 0
    for manifest in _manifest_plugins(ROOT):
        plugin = manifest.parents[1]
        for skill in sorted((plugin / "skills").glob("*/SKILL.md")):
            text = skill.read_text(encoding="utf-8")
            frontmatter = yaml.safe_load(text.split("---", 2)[1]) or {}
            if frontmatter.get("effect") != "external-mutation":
                continue
            count += 1
            assert frontmatter.get("external_mutation_guard") == expected, skill
    assert count > 0


def test_every_external_mutation_skill_has_one_canonical_cli_wiring_block():
    mod = _load_generator()
    count = 0
    for manifest in _manifest_plugins(ROOT):
        plugin = manifest.parents[1]
        for skill in sorted((plugin / "skills").glob("*/SKILL.md")):
            text = skill.read_text(encoding="utf-8")
            frontmatter = yaml.safe_load(text.split("---", 2)[1]) or {}
            if frontmatter.get("effect") != "external-mutation":
                continue
            count += 1
            # SKILL.md の言語のマーカーがちょうど1組あり、もう一方の言語のマーカーは無い。
            language = mod._skill_language(text)
            for lang, (begin, end) in mod.EXTERNAL_GUARD_BLOCK_MARKERS.items():
                expected = 1 if lang == language else 0
                assert text.count(begin) == expected, (skill, lang)
                assert text.count(end) == expected, (skill, lang)
            assert (
                '--entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md"'
                in text
            ), skill
            for action in ("preview", "hook-confirm", "authorize", "execute"):
                assert action in text, (skill, action)
            assert text.count("build-external-mutation-guard.py") >= 3, skill
    assert count == 37


def test_structured_marker_without_canonical_cli_wiring_fails_closed(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = repo / "plugins/contract-generator/skills/run-future-external/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\n"
        "name: run-future-external\n"
        "effect: external-mutation\n"
        "external_mutation_guard: {runtime_ref: "
        "'plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py', "
        "flow: 'preview-confirm-authorize-execute-v1'}\n"
        "---\n"
        "Run python3 mutate_remote.py --really-write-remote.\n",
        encoding="utf-8",
    )
    with pytest.raises(mod.ContractError, match="canonical CLI wiring"):
        mod.write_projections(repo)


def test_external_skill_auto_approval_or_direct_mutation_example_fails_closed(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = next(
        path
        for path in (repo / "plugins").glob("*/skills/*/SKILL.md")
        if (yaml.safe_load(path.read_text().split("---", 2)[1]) or {}).get("effect")
        == "external-mutation"
    )
    text = skill.read_text(encoding="utf-8")
    skill.write_text(
        text
        + "\n```bash\npython3 mutate_remote.py --really-write-remote --auto-approve\n```\n",
        encoding="utf-8",
    )
    with pytest.raises(mod.ContractError, match="direct mutation|auto-approval"):
        mod.write_projections(repo)


@pytest.mark.parametrize(
    "command",
    [
        "python3 mutate_remote.py --apply",
        "python3 send-campaign.py --confirm-token forged",
        "python3 gh-bridge.py apply --plan sync.json",
        "python3 intake_publish_pipeline.py --intake intake.json --manifest manifest.json",
    ],
)
def test_canonical_block_cannot_authorize_direct_mutation_imperative(tmp_path, command):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = next(
        path
        for path in (repo / "plugins").glob("*/skills/*/SKILL.md")
        if (yaml.safe_load(path.read_text().split("---", 2)[1]) or {}).get("effect")
        == "external-mutation"
    )
    skill.write_text(
        skill.read_text(encoding="utf-8") + f"\n```bash\n{command}\n```\n",
        encoding="utf-8",
    )
    with pytest.raises(mod.ContractError, match="direct mutation CLI"):
        mod.write_projections(repo)


_EXTERNAL_GUARD_FRONTMATTER = (
    "---\n"
    "name: run-future-external\n"
    "effect: external-mutation\n"
    "external_mutation_guard: {runtime_ref: "
    "'plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py', "
    "flow: 'preview-confirm-authorize-execute-v1'}\n"
    "---\n"
)


def _external_skill_text(
    post_choice: str, *, runtime_root: str = "", blocks: tuple[str, ...] = ()
) -> str:
    """Post-choice 見出しだけで言語が決まる、外部変更のスキルの最小の SKILL.md。"""
    return (
        _EXTERNAL_GUARD_FRONTMATTER
        + "\n# run-future-external\n\n"
        + (runtime_root + "\n" if runtime_root else "")
        + "## 目的と出力契約\n\n外部の記録を1件更新する。\n\n"
        + f"{post_choice}\n\n以下の節は、「診断する」が記録されたときだけ実行する。\n\n"
        + "".join(block + "\n" for block in blocks)
        + "## 全体の流れ\n\n1. 記録を更新する。\n"
    )


def _add_external_skill(repo: pathlib.Path, text: str) -> pathlib.Path:
    skill = repo / "plugins/contract-generator/skills/run-future-external/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(text, encoding="utf-8")
    return skill


def _skill_snapshot(repo: pathlib.Path) -> dict[pathlib.Path, bytes]:
    return {path: path.read_bytes() for path in (repo / "plugins").glob("*/skills/*/SKILL.md")}


@pytest.mark.parametrize(
    "line,language",
    [
        ("## 選んだ深さでの改善の実行", "ja"),
        ("  ## 選んだ深さでの改善の実行  ", "ja"),
        ("## Post-choice selected improvement execution", "en"),
        ("## 選んだ深さでの改善の実行（補足）", "en"),
        ("本文で `## 選んだ深さでの改善の実行` に触れるだけ", "en"),
    ],
    ids=["exact", "surrounding-space", "english", "suffixed", "inline-mention"],
)
def test_skill_language_is_decided_by_whole_line_japanese_post_choice_heading(line, language):
    mod = _load_generator()
    assert mod._skill_language(f"# skill\n\n{line}\n\n本文。\n") == language


def test_japanese_guard_block_keeps_english_command_lines_byte_for_byte():
    mod = _load_generator()
    english = mod._canonical_external_guard_block()
    japanese = mod._canonical_external_guard_block("ja")
    assert english == mod._canonical_external_guard_block("en")
    assert english.startswith(mod.EXTERNAL_GUARD_BLOCK_BEGIN + "\n")
    assert english.endswith(mod.EXTERNAL_GUARD_BLOCK_END + "\n")
    assert japanese.startswith(mod.EXTERNAL_GUARD_BLOCK_BEGIN_JA + "\n")
    assert japanese.endswith(mod.EXTERNAL_GUARD_BLOCK_END_JA + "\n")
    assert mod.EXTERNAL_GUARD_BLOCK_BEGIN not in japanese
    assert mod.EXTERNAL_GUARD_BLOCK_BEGIN_JA not in english

    def commands(block: str) -> list[str]:
        return [line for line in block.splitlines() if line.startswith("python3 ")]

    assert len(commands(japanese)) == 4
    assert commands(japanese) == commands(english)
    with pytest.raises(mod.ContractError, match="unknown canonical guard block language"):
        mod._canonical_external_guard_block("fr")


@pytest.mark.parametrize("language,existing", [("en", None), ("ja", None), ("ja", "en"), ("en", "ja")])
def test_runtime_root_contract_migrates_locale_and_is_idempotent(tmp_path, language, existing):
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    text = _external_skill_text(mod.POST_CHOICE_HEADINGS[language], runtime_root=mod.RUNTIME_ROOT_CONTRACT_SECTIONS[existing] if existing else "")
    migrated = mod._ensure_runtime_root_contract(text, path)
    expected = mod._canonical_runtime_root_block(language, has_prompts=False)
    assert migrated.count(expected) == 1
    assert "`prompts/`" not in migrated
    body = migrated.split("---", 2)[2]
    assert body.index("## 目的と出力契約") < body.index(mod.RUNTIME_ROOT_BLOCK_BEGIN)
    assert mod._ensure_runtime_root_contract(migrated, path) == migrated


def test_japanese_post_choice_skill_migrates_to_japanese_block_and_runtime_root(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = _add_external_skill(repo, _external_skill_text(mod.POST_CHOICE_HEADING_JA))
    before = _skill_snapshot(repo)
    mod.migrate_external_guard_blocks(repo)

    text = skill.read_text(encoding="utf-8")
    front, body = text.split("---", 2)[1:]
    assert "runtime_root_policy: host-skill-path" in front
    assert body.count(mod._canonical_runtime_root_block("ja", has_prompts=(skill.parent / "prompts").is_dir())) == 1
    assert mod.RUNTIME_ROOT_CONTRACT_HEADING not in body
    assert body.count(mod._canonical_external_guard_block("ja")) == 1
    assert text.count(mod.EXTERNAL_GUARD_BLOCK_BEGIN_JA) == 1
    assert text.count(mod.EXTERNAL_GUARD_BLOCK_END_JA) == 1
    assert mod.EXTERNAL_GUARD_BLOCK_BEGIN not in text
    assert mod.EXTERNAL_GUARD_BLOCK_END not in text
    assert text.index(mod.POST_CHOICE_HEADING_JA) < text.index(mod.EXTERNAL_GUARD_BLOCK_BEGIN_JA)
    # 英語のスキルは 1 バイトも変わらない (日本語の正規形は 2 つ目の正規形として足しただけ)。
    changed = {path for path, data in before.items() if path.read_bytes() != data}
    assert skill in changed
    assert all("runtime-root-contract:v1" in path.read_text() for path in changed)


def test_japanese_skill_migration_passes_wiring_and_is_idempotent(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = _add_external_skill(repo, _external_skill_text(mod.POST_CHOICE_HEADING_JA))
    mod.migrate_external_guard_blocks(repo)

    mod._validate_external_guard_wiring(skill)
    # 禁止パターン (直接実行・ゲート無効化) が日本語の正規の文面を誤検出しないことも含めて通す。
    assert mod.write_projections(repo) == len(_manifest_plugins(repo))
    assert mod.lint_repository(repo) == []

    migrated = _skill_snapshot(repo)
    mod.migrate_external_guard_blocks(repo)
    assert _skill_snapshot(repo) == migrated


def test_japanese_skill_english_guard_block_is_replaced_by_migration(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = _add_external_skill(
        repo,
        _external_skill_text(
            mod.POST_CHOICE_HEADING_JA,
            runtime_root=mod.RUNTIME_ROOT_CONTRACT_SECTION_JA,
            blocks=(mod._canonical_external_guard_block(),),
        ),
    )
    mod.migrate_external_guard_blocks(repo)

    text = skill.read_text(encoding="utf-8")
    assert mod.EXTERNAL_GUARD_BLOCK_BEGIN not in text
    assert mod.EXTERNAL_GUARD_BLOCK_END not in text
    assert text.count(mod._canonical_external_guard_block("ja")) == 1
    assert text.count(mod.RUNTIME_ROOT_CONTRACT_HEADING_JA) == 1
    mod._validate_external_guard_wiring(skill)


@pytest.mark.parametrize(
    "post_choice_language,block_languages",
    [("ja", ("en",)), ("ja", ("ja", "en")), ("en", ("ja",)), ("en", ("en", "ja"))],
    ids=["ja-skill-en-block", "ja-skill-both-blocks", "en-skill-ja-block", "en-skill-both-blocks"],
)
def test_guard_block_language_mismatch_fails_closed(
    tmp_path, post_choice_language, block_languages
):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    _add_external_skill(
        repo,
        _external_skill_text(
            mod.POST_CHOICE_HEADINGS[post_choice_language],
            runtime_root=mod.RUNTIME_ROOT_CONTRACT_SECTIONS[post_choice_language],
            blocks=tuple(mod._canonical_external_guard_block(lang) for lang in block_languages),
        ),
    )
    with pytest.raises(mod.ContractError, match="canonical CLI wiring block language mismatch"):
        mod.write_projections(repo)


@pytest.mark.parametrize("language", ["en", "ja"])
def test_guard_block_markers_out_of_order_fail_closed(tmp_path, language):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    begin, end = mod.EXTERNAL_GUARD_BLOCK_MARKERS[language]
    skill = _add_external_skill(
        repo,
        _external_skill_text(
            mod.POST_CHOICE_HEADINGS[language],
            runtime_root=mod.RUNTIME_ROOT_CONTRACT_SECTIONS[language],
            blocks=(f"{end}\n{begin}\n",),
        ),
    )
    with pytest.raises(mod.ContractError, match="markers out of order"):
        mod._validate_external_guard_wiring(skill)


def test_external_entrypoint_requires_distributed_guard_dependency(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    manifest = repo / "plugins/contract-generator/.claude-plugin/plugin.json"
    _rewrite_json(manifest, lambda data: data.__setitem__("dependencies", []))
    with pytest.raises(mod.ContractError, match="requires skill-governance-adapters dependency"):
        mod.write_projections(repo)


def test_unknown_effect_is_rejected_before_projection_comparison(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    skill = next((repo / "plugins/contract-generator/skills").glob("*/SKILL.md"))
    text = skill.read_text(encoding="utf-8")
    text = text.replace("effect: external-mutation", "effect: time-travel", 1)
    skill.write_text(text, encoding="utf-8")
    assert any("unknown effect" in error for error in mod.lint_repository(repo))


def test_new_missing_effect_without_explicit_override_is_rejected(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    plugin = repo / "plugins/new-plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": "new-plugin", "version": "0.1.0", "description": "fixture"}),
        encoding="utf-8",
    )
    skill = plugin / "skills/run-new/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: run-new\n---\n", encoding="utf-8")
    errors = mod.lint_repository(repo)
    assert any("effect missing" in error for error in errors)


def test_external_intelligence_pointer_exact_keys_and_schema_hash(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    projection = json.loads(_projection(repo, "contract-generator").read_text(encoding="utf-8"))
    pointer = projection["external_intelligence_runtime"]
    assert set(pointer) == {
        "contract_id",
        "adapter_ref",
        "adapter_sha256",
        "engine_ref",
        "engine_sha256",
        "schema_ref",
        "contract_ref",
        "policy_sha256",
        "caller_ref",
        "caller_sha256",
        "caller_manifest_ref",
        "caller_event",
        "default_scope",
        "standalone_behavior",
    }
    assert pointer["contract_id"] == "external-intelligence-runtime-v1"
    assert pointer["default_scope"] == "project"
    assert pointer["standalone_behavior"] == "warning-continue"
    assert pointer["caller_event"] == "UserPromptSubmit"

    _rewrite_json(
        _projection(repo, "contract-generator"),
        lambda data: data["external_intelligence_runtime"].__setitem__(
            "policy_sha256", "f" * 64
        ),
    )
    assert any("external_intelligence_runtime" in error for error in mod.lint_repository(repo))


def test_external_intelligence_caller_must_be_manifest_registered_and_call_adapter(tmp_path):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    manifest = _hook_manifest(repo, "skill-governance-adapters")
    _rewrite_json(manifest, lambda data: data["hooks"].pop("UserPromptSubmit"))
    assert any("caller manifest registration" in error for error in mod.lint_repository(repo))

    repo = _copy_contract_repo(tmp_path / "second")
    caller = repo / "plugins/skill-governance-adapters/hooks/build-external-intelligence-context.py"
    caller.write_text("print('passive pointer only')\n", encoding="utf-8")
    assert any("caller does not invoke adapter" in error for error in mod.lint_repository(repo))


def test_external_mutation_runtime_missing_tampered_or_uninvoked_fails_closed(tmp_path):
    mod = _load_generator()
    runner_rel = pathlib.Path(
        "plugins/skill-governance-adapters/scripts/build-external-mutation-guard.py"
    )

    missing = _copy_contract_repo(tmp_path / "missing")
    (missing / runner_rel).unlink()
    assert any(
        "external mutation runtime runner_ref target missing" in error
        for error in mod.lint_repository(missing)
    )

    tampered = _copy_contract_repo(tmp_path / "tampered")
    runner = tampered / runner_rel
    runner.write_text(runner.read_text() + "\n# tampered fixture\n", encoding="utf-8")
    assert any(
        "external_mutation_runtime pointer/hook/hash drift" in error
        for error in mod.lint_repository(tampered)
    )

    uninvoked = _copy_contract_repo(tmp_path / "uninvoked")
    manifest = _hook_manifest(uninvoked, "skill-governance-adapters")
    _rewrite_json(manifest, lambda data: data["hooks"].pop("PreToolUse"))
    assert any(
        "consumer/enforcer hook is uninvoked" in error
        for error in mod.lint_repository(uninvoked)
    )

    no_confirmation = _copy_contract_repo(tmp_path / "no-confirmation")
    manifest = _hook_manifest(no_confirmation, "skill-governance-adapters")
    _rewrite_json(
        manifest,
        lambda data: data["hooks"]["UserPromptSubmit"][0]["hooks"].__setitem__(
            slice(None),
            [data["hooks"]["UserPromptSubmit"][0]["hooks"][0]],
        ),
    )
    assert any(
        "confirmation producer hook is uninvoked" in error
        for error in mod.lint_repository(no_confirmation)
    )


@pytest.mark.parametrize(
    "relative,effect",
    [
        ("plugins/dev-graph/skills/run-dev-graph-decompose/SKILL.md", "local-artifact"),
        ("plugins/dev-graph/skills/run-dev-graph-init/SKILL.md", "local-artifact"),
        ("plugins/dev-graph/skills/run-dev-graph-node/SKILL.md", "local-artifact"),
        ("plugins/dev-graph/skills/run-dev-graph-render/SKILL.md", "local-artifact"),
        ("plugins/dev-graph/skills/run-dev-graph-requirements/SKILL.md", "local-artifact"),
        ("plugins/dev-graph/skills/run-dev-graph-schedule/SKILL.md", "conversation-output"),
        ("plugins/dev-graph/skills/run-dev-graph-status/SKILL.md", "conversation-output"),
        ("plugins/dev-graph/skills/run-dev-graph-sync/SKILL.md", "external-mutation"),
        ("plugins/dev-graph/skills/run-dev-graph-system-spec/SKILL.md", "local-artifact"),
        ("plugins/guide-doc-generator/skills/assign-handout-readability-evaluator/SKILL.md", "conversation-output"),
        ("plugins/guide-doc-generator/skills/run-handout-build/SKILL.md", "local-artifact"),
        ("plugins/guide-doc-generator/skills/run-handout-extract/SKILL.md", "local-artifact"),
        ("plugins/system-dev-planner/skills/assign-system-dev-plan-evaluator/SKILL.md", "local-artifact"),
        ("plugins/system-dev-planner/skills/run-system-dev-plan/SKILL.md", "local-artifact"),
    ],
)
def test_legacy_missing_effects_have_explicit_projection_classification(relative, effect):
    plugin = pathlib.PurePosixPath(relative).parts[1]
    projection = json.loads((ROOT / "plugins" / plugin / "artifact-delivery.json").read_text())
    indexed = {item["path"]: item["effect"] for item in projection["entrypoints"]}
    package_relative = pathlib.PurePosixPath(*pathlib.PurePosixPath(relative).parts[2:]).as_posix()
    assert indexed[package_relative] == effect
    skill_text = (ROOT / relative).read_text(encoding="utf-8")
    assert f"effect: {effect}" in skill_text.split("---", 2)[1]


def test_canonical_guard_detects_prose_drift(tmp_path):
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    text = _external_skill_text(mod.POST_CHOICE_HEADING_JA, blocks=(mod._canonical_external_guard_block("ja"),))
    text = mod._ensure_runtime_root_contract(text, path)
    path.write_text(text, encoding="utf-8")
    mod._validate_external_guard_wiring(path)
    path.write_text(text.replace("解決のスクリプトが 0 以外で終わったら", "解決に失敗しても続けてよい"), encoding="utf-8")
    with pytest.raises(mod.ContractError, match="content drift"):
        mod._validate_external_guard_wiring(path)


def test_runtime_block_validates_locale_resources_and_content(tmp_path):
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    text = _external_skill_text(mod.POST_CHOICE_HEADING_JA)
    path.write_text(mod._ensure_runtime_root_contract(text, path), encoding="utf-8")
    mod._validate_runtime_root_wiring(path)
    (tmp_path / "prompts").mkdir()
    with pytest.raises(mod.ContractError, match="canonical block drift"):
        mod._validate_runtime_root_wiring(path)
    path.write_text(mod._ensure_runtime_root_contract(path.read_text(), path), encoding="utf-8")
    mod._validate_runtime_root_wiring(path)
    path.write_text(path.read_text().replace("host-skill-path", "cwd-guess"), encoding="utf-8")
    with pytest.raises(mod.ContractError, match="canonical block drift"):
        mod._validate_runtime_root_wiring(path)


@pytest.mark.parametrize("legacy_language", ["en", "ja"])
@pytest.mark.parametrize("with_bullets", [True, False], ids=["bullets+prose", "prose-only"])
def test_legacy_runtime_root_prose_is_moved_after_block_not_dropped(tmp_path, legacy_language, with_bullets):
    # 旧節の正規形の行は作り直すが、skill 固有の文 (引用・段落) は黙って消さずブロックの直後へ移す。
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    heading = mod.RUNTIME_ROOT_CONTRACT_SECTIONS[legacy_language].splitlines()[0]
    section = mod.RUNTIME_ROOT_CONTRACT_SECTIONS[legacy_language] if with_bullets else heading + "\n"
    custom = "> この skill の注記。パス解決は Runtime root contract に従う。\n\n独自の段落。\n続きの行。\n"
    text = _external_skill_text(mod.POST_CHOICE_HEADING_JA, runtime_root=section + "\n" + custom)
    migrated = mod._ensure_runtime_root_contract(text, path)
    block = mod._canonical_runtime_root_block("ja", has_prompts=False)
    assert migrated.count(block) == 1
    assert migrated.count(mod.RUNTIME_ROOT_CONTRACT_HEADING_JA) == 1
    assert mod.RUNTIME_ROOT_CONTRACT_HEADING not in migrated
    end = migrated.index(mod.RUNTIME_ROOT_BLOCK_END)
    for line in custom.strip("\n").splitlines():
        if line:
            assert migrated.count(line) == 1
            assert end < migrated.index(line) < migrated.index(mod.POST_CHOICE_HEADING_JA)
    assert mod._ensure_runtime_root_contract(migrated, path) == migrated
    path.write_text(migrated, encoding="utf-8")
    mod._validate_runtime_root_wiring(path)


def test_section_headings_skip_code_fences():
    # 節の境界は fence の外の "## " 行だけ。閉じは同じ文字・同じ長さ以上 (CommonMark)。
    mod = _load_generator()
    body = (
        "## A\n"
        "```\n## x\n```\n"
        "   ~~~~ text\n## y\n~~~\n```\n## まだ fence の中\n~~~~~\n"
        "## B\n"
        "``` `fence ではない`\n"
        "## C\n"
    )
    headings = mod._section_headings(body)
    assert [line for _, line in headings] == ["## A", "## B", "## C"]
    assert all(body[start:].startswith(line + "\n") for start, line in headings)


_FENCED_EXAMPLES = {
    "backtick": "```markdown\n## 例の見出し\n本文\n```\n",
    "tilde": "~~~markdown\n## 例の見出し\n```\n## まだ fence の中\n~~~\n",
    "longer-backtick": "````\n```\n## 例の見出し\n```\n````\n",
}


@pytest.mark.parametrize("fence", _FENCED_EXAMPLES.values(), ids=_FENCED_EXAMPLES.keys())
def test_runtime_root_block_is_not_inserted_inside_code_fence(tmp_path, fence):
    # 目的と出力契約の節に "## " を含む fence があっても、ブロックは fence の後ろ (節の終わり) へ入る。
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    text = _external_skill_text(mod.POST_CHOICE_HEADING_JA).replace(
        "外部の記録を1件更新する。\n", "外部の記録を1件更新する。\n\n" + fence
    )
    migrated = mod._ensure_runtime_root_contract(text, path)
    assert migrated.count(fence) == 1
    begin = migrated.index(mod.RUNTIME_ROOT_BLOCK_BEGIN)
    assert migrated.index(fence) + len(fence) <= begin < migrated.index(mod.POST_CHOICE_HEADING_JA)
    assert mod._ensure_runtime_root_contract(migrated, path) == migrated
    path.write_text(migrated, encoding="utf-8")
    mod._validate_runtime_root_wiring(path)


def test_legacy_runtime_root_section_moves_fenced_lines_together(tmp_path):
    # 旧節の中の fence に "## " があっても節はそこで切れない。fence は丸ごとブロックの直後へ移る。
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    fence = "~~~bash\n## shell の comment\necho ok\n~~~\n"
    section = mod.RUNTIME_ROOT_CONTRACT_SECTION + "\n" + fence
    text = _external_skill_text(mod.POST_CHOICE_HEADING_JA, runtime_root=section)
    migrated = mod._ensure_runtime_root_contract(text, path)
    assert mod.RUNTIME_ROOT_CONTRACT_HEADING not in migrated
    assert migrated.count(fence) == 1
    end = migrated.index(mod.RUNTIME_ROOT_BLOCK_END)
    assert end < migrated.index(fence) < migrated.index(mod.POST_CHOICE_HEADING_JA)
    assert mod._ensure_runtime_root_contract(migrated, path) == migrated
    path.write_text(migrated, encoding="utf-8")
    mod._validate_runtime_root_wiring(path)


def test_runtime_root_heading_inside_fence_is_not_a_legacy_section(tmp_path):
    # fence に例として書いた旧節は、本物の旧節ではないので消さない。
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    fence = "```markdown\n" + mod.RUNTIME_ROOT_CONTRACT_SECTION_JA + "```\n"
    text = _external_skill_text(mod.POST_CHOICE_HEADING_JA).replace(
        "外部の記録を1件更新する。\n", "外部の記録を1件更新する。\n\n" + fence
    )
    migrated = mod._ensure_runtime_root_contract(text, path)
    assert migrated.count(fence) == 1
    assert migrated.count(mod._canonical_runtime_root_block("ja", has_prompts=False)) == 1
    assert mod._ensure_runtime_root_contract(migrated, path) == migrated


@pytest.mark.parametrize(
    "relative",
    sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "plugins").glob("*/skills/*/SKILL.md")
        if "\neffect: external-mutation\n" in path.read_text(encoding="utf-8")
    ),
)
def test_runtime_root_migration_keeps_every_non_canonical_line_of_real_skills(relative):
    # 実 repo の外部変更 skill (run-extract-blueprint の引用・run-codex-plugin-install の段落を含む) で、
    # 移行が落としてよいのは正規形の行・旧見出し・runtime_root_policy の行だけ。書き込みはしない。
    from collections import Counter

    mod = _load_generator()
    path = ROOT / relative
    if mod._frontmatter(path).get("effect") != "external-mutation":
        pytest.skip("migration targets external-mutation skills only")
    original = path.read_text(encoding="utf-8")
    migrated = mod._ensure_runtime_root_contract(original, path)
    replaceable = {
        line.strip()
        for section in mod.RUNTIME_ROOT_CONTRACT_SECTIONS.values()
        for line in section.splitlines()
    } | {mod.RUNTIME_ROOT_BLOCK_BEGIN, mod.RUNTIME_ROOT_BLOCK_END}

    def countable(text: str) -> Counter:
        return Counter(
            line.strip()
            for line in text.splitlines()
            if line.strip() and line.strip() not in replaceable and not line.startswith("runtime_root_policy:")
        )

    assert countable(original) - countable(migrated) == Counter()
    assert mod._ensure_runtime_root_contract(migrated, path) == migrated


def test_frontmatter_is_closed_only_by_a_dash_only_line(tmp_path):
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    text = _external_skill_text(mod.POST_CHOICE_HEADING_JA).replace(
        "name: run-future-external\n", "name: run-future-external\ndescription: before---after\n"
    )
    path.write_text(text, encoding="utf-8")
    assert mod._frontmatter(path)["description"] == "before---after"
    migrated = mod._ensure_runtime_root_contract(text, path)
    path.write_text(migrated, encoding="utf-8")
    frontmatter = mod._frontmatter(path)
    assert frontmatter["description"] == "before---after"
    assert frontmatter["runtime_root_policy"] == mod.RUNTIME_ROOT_POLICY
    body = migrated.split("\n---\n", 1)[1]
    assert not any(line.startswith("runtime_root_policy:") for line in body.splitlines())
    unclosed = tmp_path / "unclosed.md"
    unclosed.write_text("---\nname: x\n# body\n", encoding="utf-8")
    assert mod._frontmatter(unclosed) == {}
    with pytest.raises(mod.ContractError, match="frontmatter missing"):
        mod._ensure_runtime_root_contract(unclosed.read_text(encoding="utf-8"), unclosed)


def test_post_choice_heading_is_matched_as_a_whole_line(tmp_path):
    # 本文中の言及や接尾辞付きの見出しを post-choice 節と取り違えない (移行の挿入位置と検査の両方)。
    mod = _load_generator()
    heading = mod.POST_CHOICE_HEADING
    mention = f"手順は `{heading}` に書く。"
    text = _external_skill_text(heading).replace("外部の記録を1件更新する。", "外部の記録を1件更新する。" + mention)
    repo = _copy_contract_repo(tmp_path)
    skill = _add_external_skill(repo, text)
    mod.migrate_external_guard_blocks(repo)
    migrated = skill.read_text(encoding="utf-8")
    real_heading = migrated.index("\n" + heading + "\n")
    assert real_heading < migrated.index(mod.EXTERNAL_GUARD_BLOCK_BEGIN)
    mod._validate_external_guard_wiring(skill)

    # 正しい見出しの前 (言及の後) にブロックを置いた文書は不合格。
    block = mod._canonical_external_guard_block()
    moved = migrated.replace(block + "\n", "").replace(mention, mention + "\n\n" + block)
    skill.write_text(moved, encoding="utf-8")
    with pytest.raises(mod.ContractError, match="post-choice execution"):
        mod._validate_external_guard_wiring(skill)

    suffixed = _external_skill_text(heading + "（旧）")
    assert mod._heading_span(suffixed, heading) is None
    skill.write_text(suffixed, encoding="utf-8")
    with pytest.raises(mod.ContractError, match="post-choice execution section missing"):
        mod.migrate_external_guard_blocks(repo)


@pytest.mark.parametrize("broken", ["non-utf8", "directory"])
@pytest.mark.parametrize("mode", ["--check", "--migrate-external-guard", "--write"])
def test_unreadable_skill_is_a_contract_error_not_a_traceback(tmp_path, broken, mode):
    repo = _copy_contract_repo(tmp_path)
    skill = repo / "plugins/contract-generator/skills/run-unreadable/SKILL.md"
    if broken == "non-utf8":
        skill.parent.mkdir(parents=True)
        skill.write_bytes(b"---\nname: run-unreadable\neffect: external-mutation\n---\n\xff\xfe\n")
    else:
        skill.mkdir(parents=True)
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--repo-root", str(repo), mode],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "ARTIFACT_DELIVERY_ERROR" in result.stderr
    assert "Traceback" not in result.stderr
    assert ("not UTF-8" if broken == "non-utf8" else "cannot read") in result.stderr


def test_unreadable_policy_is_a_contract_error(tmp_path):
    repo = _copy_contract_repo(tmp_path)
    (repo / "references" / POLICY.name).write_bytes(b"\xff{}")
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--repo-root", str(repo), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "not UTF-8" in result.stderr and "Traceback" not in result.stderr


def test_help_states_the_write_scope_of_every_mode():
    result = subprocess.run([sys.executable, str(GENERATOR), "--help"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    for needle in ("書き込み範囲", "artifact-delivery.json", "runtime_root_policy", "runtime root 節", "直接実行の例"):
        assert needle in result.stdout


@pytest.mark.parametrize("separator", ["&&", ";", "|", "||"])
def test_guard_name_does_not_hide_compound_direct_publication(separator):
    mod = _load_generator()
    line = f"""python3 "/guard/build-external-mutation-guard.py" execute --command-json '["python3", "worker.py"]' {separator} python3 guard-staged-publication.py --manifest plan.json"""
    assert mod._direct_external_mutation_instruction(line)


def test_canonical_guard_can_bind_quoted_mutation_argv():
    mod = _load_generator()
    line = """python3 "/guard/build-external-mutation-guard.py" execute --project-root "$PWD" --command-json '["python3", "guard-staged-publication.py", "--manifest", "plan.json"]'"""
    assert mod._direct_external_mutation_instruction(line) is None


@pytest.mark.parametrize("expression", ['$(python3 guard-staged-publication.py --manifest plan.json)', '`python3 guard-staged-publication.py --manifest plan.json`', '<(python3 guard-staged-publication.py --manifest plan.json)'])
def test_guard_substitution_is_rejected_before_execution(expression):
    mod = _load_generator()
    line = f"""python3 "/guard/build-external-mutation-guard.py" execute --project-root "{expression}" --command-json '["python3","worker.py"]'"""
    assert mod._direct_external_mutation_instruction(line)


def test_guard_json_literal_substitution_is_data():
    mod = _load_generator()
    line = """python3 "/guard/build-external-mutation-guard.py" execute --project-root "$PWD" --command-json '["python3","worker.py","literal $(value) and `data`"]'"""
    assert mod._direct_external_mutation_instruction(line) is None


# ---- 独立 review (79 点) の指摘の再現。各 test は review の再現手順をそのまま使う。 ----

_FIRST_EXTERNAL_SKILL = "plugins/contract-generator/skills/run-contract-finalize/SKILL.md"
_LAST_EXTERNAL_SKILL = "plugins/x-longpost-creator/skills/run-skill-feedback/SKILL.md"
PROJECTION_FILE = "artifact-delivery.json"


def _run_generator(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GENERATOR), "--repo-root", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _projection_snapshot(repo: pathlib.Path) -> dict[pathlib.Path, bytes]:
    return {path: path.read_bytes() for path in (repo / "plugins").glob(f"*/{PROJECTION_FILE}")}


def _copy_checkable_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """_copy_contract_repo に、実 repo の skill の prompts/ dir (有無だけ) を足した fixture。

    runtime root の管理ブロックは prompts/ の有無で正規形が変わる。prompts/ を持たない fixture では
    prompts/ を持つ skill がそれだけで drift になり、--check の rc 0 を前提にした再現ができない。
    """
    repo = _copy_contract_repo(tmp_path)
    for prompts in (ROOT / "plugins").glob("*/skills/*/prompts"):
        if prompts.is_dir() and (repo / prompts.relative_to(ROOT)).parent.is_dir():
            (repo / prompts.relative_to(ROOT)).mkdir()
    return repo


def test_write_on_clean_fixture_keeps_every_projection_byte_identical(tmp_path):
    # 正常経路の出力 (投影の byte) は修正の前後で変えない。
    repo = _copy_checkable_repo(tmp_path)
    before = _projection_snapshot(repo)
    result = _run_generator(repo, "--write")
    assert result.returncode == 0, result.stderr
    assert _projection_snapshot(repo) == before
    assert not list((repo / "plugins").glob("*/.*.tmp"))


def test_write_refuses_symlinked_projection_and_check_fails(tmp_path):
    # [中] 再現: 投影を repo の外の 3 byte の file への symlink にして --write → rc 0 で外の file が
    # 7583 byte に書き換わり、続く --check も rc 0 だった。
    repo = _copy_checkable_repo(tmp_path / "fixture")
    assert _run_generator(repo, "--check").returncode == 0
    projection = _projection(repo, "harness-creator")
    correct = projection.read_bytes()
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"{}\n")
    assert len(outside.read_bytes()) == 3
    projection.unlink()
    projection.symlink_to(outside)
    # 別の plugin の投影の書式を崩しておき、拒否した --write がそれも書き直さない (1 件も書かない) ことを見る。
    other = _projection(repo, "contract-generator")
    other.write_text(other.read_text(encoding="utf-8").replace("\n", "\n ", 1), encoding="utf-8")
    other_bytes = other.read_bytes()

    written = _run_generator(repo, "--write")
    assert written.returncode == 1, written.stdout + written.stderr
    assert "refusing to write through symlink: plugins/harness-creator/artifact-delivery.json" in written.stderr
    assert "Traceback" not in written.stderr
    assert outside.read_bytes() == b"{}\n"
    assert other.read_bytes() == other_bytes
    assert projection.is_symlink()

    checked = _run_generator(repo, "--check")
    assert checked.returncode == 1
    assert "plugins/harness-creator/artifact-delivery.json: projection must be a regular file" in checked.stderr

    # 辿った先の中身が正しくても、symlink の投影は不合格 (--write はそこへ書けない)。
    outside.write_bytes(correct)
    checked = _run_generator(repo, "--check")
    assert checked.returncode == 1
    assert "not reached through a symlink" in checked.stderr


def test_write_and_migration_refuse_files_behind_symlinked_directory(tmp_path):
    # [中] 途中の dir が symlink でも、書き込みは repo の外へ出る。
    repo = _copy_checkable_repo(tmp_path / "fixture")
    plugin = repo / "plugins" / "harness-creator"
    outside = tmp_path / "outside-plugin"
    shutil.move(str(plugin), str(outside))
    plugin.symlink_to(outside, target_is_directory=True)
    (outside / PROJECTION_FILE).write_bytes(b"{}\n")
    skills = _skill_snapshot(repo)
    assert any(outside in path.resolve().parents for path in skills)

    written = _run_generator(repo, "--write")
    assert written.returncode == 1
    assert "refusing to write through symlink: plugins/harness-creator" in written.stderr
    assert (outside / PROJECTION_FILE).read_bytes() == b"{}\n"

    migrated = _run_generator(repo, "--migrate-external-guard")
    assert migrated.returncode == 1
    assert "refusing to migrate a SKILL.md outside the repo root" in migrated.stderr
    assert _skill_snapshot(repo) == skills

    checked = _run_generator(repo, "--check")
    assert checked.returncode == 1
    assert "not reached through a symlink (plugins/harness-creator)" in checked.stderr


def test_english_skill_without_runtime_root_section_fails_check(tmp_path):
    # [中] 再現: 英語の run-contract-finalize から "## Runtime root contract" 節を丸ごと消しても
    # --check が rc 0 だった (日本語の skill にしか管理ブロックを求めていなかった)。
    mod = _load_generator()
    repo = _copy_checkable_repo(tmp_path)
    skill = repo / _FIRST_EXTERNAL_SKILL
    text = skill.read_text(encoding="utf-8")
    assert mod._skill_language(text) == "en"
    assert mod.RUNTIME_ROOT_BLOCK_BEGIN not in text
    assert _run_generator(repo, "--check").returncode == 0
    removed = re.sub(r"^## Runtime root contract\n.*?(?=^## )", "", text, count=1, flags=re.M | re.S)
    assert removed != text and mod.RUNTIME_ROOT_CONTRACT_HEADING not in removed
    skill.write_text(removed, encoding="utf-8")

    result = _run_generator(repo, "--check")
    assert result.returncode == 1
    assert (
        "run-contract-finalize/SKILL.md: runtime root contract requires a managed block or exactly one "
        "'## Runtime root contract' section (found 0)"
    ) in result.stderr


@pytest.mark.parametrize("case", ["missing", "duplicated", "policy-dropped", "fenced-only"])
def test_english_runtime_root_requires_block_or_one_legacy_section_with_policy(tmp_path, case):
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    section = mod.RUNTIME_ROOT_CONTRACT_SECTION
    runtime_root = {
        "missing": "",
        "duplicated": section + "\n" + section,
        "policy-dropped": section.replace("runtime_root_policy: host-skill-path", "runtime_root_policy: cwd-guess"),
        "fenced-only": "```markdown\n" + section + "```\n",
    }[case]
    message = {
        "missing": r"\(found 0\)",
        "duplicated": r"\(found 2\)",
        "policy-dropped": "does not state runtime_root_policy",
        "fenced-only": r"\(found 0\)",
    }[case]
    path.write_text(_external_skill_text(mod.POST_CHOICE_HEADING, runtime_root=runtime_root), encoding="utf-8")
    with pytest.raises(mod.ContractError, match=message):
        mod._validate_runtime_root_wiring(path)

    # 旧節 1 つ (policy あり) と、移行後の管理ブロックはどちらも通る。
    path.write_text(_external_skill_text(mod.POST_CHOICE_HEADING, runtime_root=section), encoding="utf-8")
    mod._validate_runtime_root_wiring(path)
    path.write_text(mod._ensure_runtime_root_contract(path.read_text(encoding="utf-8"), path), encoding="utf-8")
    mod._validate_runtime_root_wiring(path)


@pytest.mark.parametrize(
    "command",
    [
        "python3 \\\n  scripts/publish-notion-page.py --page-id X",
        "gh issue create --title x  # setup-send-log-db.py",
        "gh api repos/o/r/issues -f title=t",
        "gh release create v1",
        "git push origin main",
        # 同じ穴の別の綴り
        "python3 scripts/setup-send-log-db.py --apply",
        "gh api --method=POST repos/o/r/issues",
        "curl -d x=1 https://example.invalid/api",
        "curl --request=DELETE https://example.invalid/api/1",
        "git -C repo push origin main",
    ],
    ids=[
        "continued-python3", "comment-names-setup-send-log-db", "gh-api-implicit-post",
        "gh-release-create", "git-push", "setup-send-log-db-apply", "gh-api-method-equals",
        "curl-implicit-post", "curl-request-equals", "git-global-option-push",
    ],
)
def test_direct_execution_detection_covers_review_holes(command):
    # [低] 再現: review の 5 つの文字列は、どれも None (直接実行ではない) と判定されていた。
    mod = _load_generator()
    assert mod._direct_external_mutation_instruction(command)


@pytest.mark.parametrize(
    "command",
    [
        "python3 scripts/setup-send-log-db.py --check",
        "gh api repos/o/r/issues",
        "gh api -X GET repos/o/r/issues -f state=open",
        "curl -G -d q=1 https://example.invalid/search",
        "git -C repo status",
        "# python3 \\\nscripts/publish-notion-page.py",
    ],
    ids=["setup-send-log-db-read", "gh-api-get", "gh-api-explicit-get-query", "curl-get-query", "git-status", "comment-continuation"],
)
def test_read_only_commands_are_not_direct_execution(command):
    mod = _load_generator()
    assert mod._direct_external_mutation_instruction(command) is None


def test_migration_failure_rewrites_no_skill(tmp_path):
    # [低] 再現: 最後の外部 skill の post-choice 見出しを "## renamed heading" に変え、最初の skill の
    # runtime_root_policy 行を消して移行 → rc 1 なのに、最初の skill は書き換わっていた。
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    first, last = repo / _FIRST_EXTERNAL_SKILL, repo / _LAST_EXTERNAL_SKILL
    externals = [
        path
        for plugin in mod.discover_plugin_dirs(repo)
        for path in sorted((plugin / "skills").glob("*/SKILL.md"))
        if mod._frontmatter(path).get("effect") == "external-mutation"
    ]
    assert externals.index(first) < externals.index(last) == len(externals) - 1
    first_text = first.read_text(encoding="utf-8")
    first.write_text(re.sub(r"^runtime_root_policy:[^\n]*\n", "", first_text, count=1, flags=re.M), encoding="utf-8")
    assert first.read_text(encoding="utf-8") != first_text
    last_text = last.read_text(encoding="utf-8")
    heading = mod.POST_CHOICE_HEADINGS[mod._skill_language(last_text)]
    renamed = re.sub(rf"^{re.escape(heading)}[ \t]*$", "## renamed heading", last_text, count=1, flags=re.M)
    assert renamed != last_text
    last.write_text(renamed, encoding="utf-8")
    before = _skill_snapshot(repo)

    result = _run_generator(repo, "--migrate-external-guard")
    assert result.returncode == 1
    assert "run-skill-feedback/SKILL.md: canonical post-choice execution section missing" in result.stderr
    assert _skill_snapshot(repo) == before


@pytest.mark.parametrize("restore_fails", [False, True], ids=["restored", "restore-also-fails"])
def test_migration_write_error_restores_files_already_written(tmp_path, monkeypatch, restore_fails):
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path)
    before = _skill_snapshot(repo)
    real_replace = mod._replace_file
    calls: list[pathlib.Path] = []

    def flaky(path, text):
        calls.append(path)
        if len(calls) == 2 or (restore_fails and len(calls) == 3):
            raise PermissionError(13, "Permission denied", str(path))
        real_replace(path, text)

    monkeypatch.setattr(mod, "_replace_file", flaky)
    if restore_fails:
        with pytest.raises(mod.ContractError, match=r"restored 0 file\(s\); could not restore: plugins/"):
            mod.migrate_external_guard_blocks(repo)
        assert calls[2] == calls[0]  # 1 件目を戻そうとした
    else:
        with pytest.raises(mod.ContractError, match=r"migration write failed at .*restored 1 file\(s\)$"):
            mod.migrate_external_guard_blocks(repo)
        assert _skill_snapshot(repo) == before
    assert len(calls) == 3  # 1 件目の書き込み・失敗した 2 件目・1 件目の復元
    assert not list((repo / "plugins").glob("*/skills/*/.*.tmp"))


@pytest.mark.parametrize("hooks", ["../hooks/hooks.json", "hooks/../../hooks/hooks.json", "/hooks/hooks.json", "."])
def test_external_hooks_path_cannot_leave_plugin(tmp_path, hooks):
    # [低] 再現: lstrip("./") が "../hooks/hooks.json" を hooks/hooks.json と読み、".." の検査を抜けていた。
    mod = _load_generator()
    plugin = tmp_path / "plugin"
    manifest = plugin / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "plugin", "hooks": hooks}), encoding="utf-8")
    for place in (plugin / "hooks", tmp_path / "hooks"):
        place.mkdir(parents=True, exist_ok=True)
        (place / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": []}}), encoding="utf-8")
    with pytest.raises(mod.ContractError, match="external hooks path must stay inside plugin"):
        mod._hook_wiring(manifest)


def test_dot_prefixed_hooks_path_is_not_read_as_hooks_dir(tmp_path):
    # [低] 再現: ".hooks/hooks.json" も lstrip("./") で hooks/hooks.json と読まれていた。
    mod = _load_generator()
    plugin = tmp_path / "plugin"
    manifest = plugin / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    for directory, event in (("hooks", "Inside"), (".hooks", "Dotted")):
        (plugin / directory).mkdir()
        (plugin / directory / "hooks.json").write_text(json.dumps({"hooks": {event: []}}), encoding="utf-8")
    for declared, expected in (
        ("./hooks/hooks.json", {"Inside": []}),
        ("hooks/hooks.json", {"Inside": []}),
        (".hooks/hooks.json", {"Dotted": []}),
    ):
        manifest.write_text(json.dumps({"name": "plugin", "hooks": declared}), encoding="utf-8")
        assert mod._hook_wiring(manifest) == expected, declared


def test_skill_language_ignores_fenced_heading_and_frontmatter(tmp_path):
    # [低] 再現: fence に例として書いた日本語の post-choice 見出しで、言語を "ja" と取り違えていた。
    mod = _load_generator()
    fenced = "```markdown\n" + mod.POST_CHOICE_HEADING_JA + "\n```\n"
    assert mod._skill_language("# skill\n\n" + fenced) == "en"
    assert mod._skill_language("# skill\n\n" + mod.POST_CHOICE_HEADING_JA + "\n") == "ja"
    # frontmatter の block scalar の "  ```" を本文の fence の開きと読まない。
    front = "---\nname: x\ndescription: |\n  ```\n---\n"
    assert mod._skill_language(front + mod.POST_CHOICE_HEADING_JA + "\n") == "ja"


def test_fenced_other_language_runtime_root_section_is_not_a_mismatch(tmp_path):
    # [低] 再現: 言語の不一致の検査が fence の中の旧節 (例) まで数えていた。
    mod = _load_generator()
    path = tmp_path / "SKILL.md"
    english = _external_skill_text(mod.POST_CHOICE_HEADING, runtime_root=mod.RUNTIME_ROOT_CONTRACT_SECTION)
    anchor = "外部の記録を1件更新する。\n"
    example = "```markdown\n" + mod.RUNTIME_ROOT_CONTRACT_SECTION_JA + "```\n"
    path.write_text(english.replace(anchor, anchor + "\n" + example), encoding="utf-8")
    mod._validate_runtime_root_wiring(path)
    path.write_text(english.replace(anchor, anchor + "\n" + mod.RUNTIME_ROOT_CONTRACT_SECTION_JA), encoding="utf-8")
    with pytest.raises(mod.ContractError, match="runtime root contract language mismatch"):
        mod._validate_runtime_root_wiring(path)


def test_runtime_root_extra_text_keeps_fenced_lines_verbatim():
    # [低] 再現: 旧節の fence の中の正規形と同じ行を捨て、fence の中の空行も畳んでいた。
    mod = _load_generator()
    canonical_line = mod.RUNTIME_ROOT_CONTRACT_SECTION.splitlines()[2]
    fence = "```text\n" + canonical_line + "\n\n\n本文\n```"
    section = canonical_line + "\n\n\n\n" + fence + "\n\n\n独自の段落。\n"
    assert mod._runtime_root_extra_text(section) == fence + "\n\n独自の段落。"


@pytest.mark.parametrize(
    "args",
    [("--check", "--plugin", "no-such"), ("--write", "--skill", "no-such"), ("--plugin", "no-such"), ("--write", "--check")],
    ids=["check-plugin", "write-skill", "default-plugin", "two-modes"],
)
def test_selection_without_migration_and_combined_modes_are_usage_errors(tmp_path, args):
    # [低] 再現: --check --plugin no-such が "OK: 23 plugins" rc 0 だった (--check は絞らず全件を見る)。
    repo = _copy_contract_repo(tmp_path)
    before = _projection_snapshot(repo)
    result = _run_generator(repo, *args)
    assert result.returncode == 2
    assert "usage:" in result.stderr
    assert _projection_snapshot(repo) == before


@pytest.mark.parametrize(
    "selection,message",
    [
        (("--skill", "no-such"), "--skill selects no external-mutation SKILL.md: no-such"),
        (("--plugin", "no-such"), "--plugin selects no external-mutation SKILL.md: no-such"),
        (("--skill", "run-contract-finalize", "--skill", "no-such"), "--skill selects no external-mutation SKILL.md: no-such"),
    ],
    ids=["skill", "plugin", "one-of-two-skills"],
)
def test_migration_selection_that_matches_nothing_fails(tmp_path, selection, message):
    # [低] 再現: --migrate-external-guard --skill no-such が 0 skills の rc 0 だった。
    repo = _copy_contract_repo(tmp_path)
    before = _skill_snapshot(repo)
    result = _run_generator(repo, "--migrate-external-guard", *selection)
    assert result.returncode == 1
    assert message in result.stderr
    assert _skill_snapshot(repo) == before


def test_checker_guard_must_match_repo_root_guard_and_repo_code_is_not_run(tmp_path):
    # [低] 再現: shell 構文の判定に使う guard を __file__ 側から読み、--repo-root 側の guard と照合していなかった。
    # --repo-root は検査の対象なので、そこの Python は実行しない (実行すれば sentinel ができる)。
    mod = _load_generator()
    repo = _copy_contract_repo(tmp_path / "fixture")
    runner = repo / "plugins/skill-governance-adapters/scripts/build-external-mutation-guard.py"
    sentinel = tmp_path / "executed"
    runner.write_text(
        runner.read_text(encoding="utf-8") + f"\n__import__('pathlib').Path({str(sentinel)!r}).write_text('x')\n",
        encoding="utf-8",
    )
    before = _projection_snapshot(repo)

    assert any("canonical shell syntax checker drift" in error for error in mod.lint_repository(repo))
    with pytest.raises(mod.ContractError, match="canonical shell syntax checker drift"):
        mod.write_projections(repo)
    result = _run_generator(repo, "--check")
    assert result.returncode == 1
    assert "canonical shell syntax checker drift" in result.stderr
    assert not sentinel.exists()
    assert _projection_snapshot(repo) == before


def test_replace_file_keeps_mode_and_leaves_no_temporary_file(tmp_path, monkeypatch):
    mod = _load_generator()
    target = tmp_path / PROJECTION_FILE
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o640)
    mod._replace_file(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert [path.name for path in tmp_path.iterdir()] == [PROJECTION_FILE]

    mask = os.umask(0)
    os.umask(mask)
    fresh = tmp_path / "fresh.json"
    mod._replace_file(fresh, "fresh\n")
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o666 & ~mask
    fresh.unlink()

    # 置き換えの直前で落ちても、元の file は元のまま・一時ファイルも残らない。
    def no_space(source, destination):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(mod.os, "replace", no_space)
    with pytest.raises(OSError, match="No space left"):
        mod._replace_file(target, "partial\n")
    monkeypatch.undo()
    assert target.read_text(encoding="utf-8") == "new\n"
    assert [path.name for path in tmp_path.iterdir()] == [PROJECTION_FILE]

    # hard link の file はその場で書く (置き換えると、もう一方の名前が古い中身のまま切り離される)。
    alias = tmp_path / "alias.json"
    os.link(target, alias)
    mod._replace_file(target, "linked\n")
    assert alias.read_text(encoding="utf-8") == "linked\n"

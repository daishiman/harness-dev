#!/usr/bin/env python3
"""Build and verify thin artifact-delivery projections for every plugin."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import pathlib
import re
import shlex
import sys
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


POLICY_REL = pathlib.PurePosixPath("references/artifact-delivery-policy.json")
SCHEMA_REL = pathlib.PurePosixPath("references/artifact-delivery.schema.json")
PROJECTION_NAME = "artifact-delivery.json"
SCHEMA_ID = "https://harness.local/schemas/artifact-delivery.schema.json"
EXTERNAL_MUTATION_FLOW = "preview-confirm-authorize-execute-v1"
EXTERNAL_GUARD_BLOCK_BEGIN = "<!-- external-mutation-guard-cli:v1 -->"
EXTERNAL_GUARD_BLOCK_END = "<!-- /external-mutation-guard-cli:v1 -->"
# 日本語の正規形は 2 つ目の正規形で、英語の正規形は変えない。どちらを使うかは
# SKILL.md の Post-choice 見出しの言語で決まる (_skill_language)。
EXTERNAL_GUARD_BLOCK_BEGIN_JA = "<!-- external-mutation-guard-cli-ja:v1 -->"
EXTERNAL_GUARD_BLOCK_END_JA = "<!-- /external-mutation-guard-cli-ja:v1 -->"
EXTERNAL_GUARD_BLOCK_MARKERS = {
    "en": (EXTERNAL_GUARD_BLOCK_BEGIN, EXTERNAL_GUARD_BLOCK_END),
    "ja": (EXTERNAL_GUARD_BLOCK_BEGIN_JA, EXTERNAL_GUARD_BLOCK_END_JA),
}
POST_CHOICE_HEADING = "## Post-choice selected improvement execution"
POST_CHOICE_HEADING_JA = "## 選んだ深さでの改善の実行"
POST_CHOICE_HEADINGS = {"en": POST_CHOICE_HEADING, "ja": POST_CHOICE_HEADING_JA}
# guard CLI は skill-governance-adapters plugin にある。`<plugin root>/../skill-governance-adapters`
# は repo の plugins/ でしか兄弟に届かず、install 先 (<cache>/<marketplace>/<plugin>/<version>/)
# では同じ plugin の別 version 群を指す。そこで自 plugin に vendor した resolver
# (scripts/extract-plugin-root.py) で guard plugin の絶対 root を preview の前に 1 回だけ得て、
# 以後の guard 呼び出しはその値を埋めた単一コマンドにする。`$(...)` で埋め込むと
# PreToolUse enforcer の canonical 判定を通らず、pending 中は resolver 自体も遮断される。
# resolver の path は dual-root 形。Codex には CLAUDE_PLUGIN_ROOT が無いので、bare の
# ${CLAUDE_PLUGIN_ROOT} を撒くと Codex 側で空文字に展開され、別 path を叩きに行く。
EXTERNAL_GUARD_PLUGIN = "skill-governance-adapters"
EXTERNAL_GUARD_ROOT_RESOLVER = "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/extract-plugin-root.py"
EXTERNAL_GUARD_ROOT_PLACEHOLDER = "<GUARD_PLUGIN_ROOT>"
EXTERNAL_GUARD_SHELL_RUNNER = (
    f"{EXTERNAL_GUARD_ROOT_PLACEHOLDER}/scripts/build-external-mutation-guard.py"
)
RUNTIME_ROOT_POLICY = "host-skill-path"
RUNTIME_ROOT_BLOCK_BEGIN = "<!-- runtime-root-contract:v1 -->"
RUNTIME_ROOT_BLOCK_END = "<!-- /runtime-root-contract:v1 -->"
RUNTIME_ROOT_CONTRACT_HEADING = "## Runtime root contract"
RUNTIME_ROOT_CONTRACT_SECTION = f"""{RUNTIME_ROOT_CONTRACT_HEADING}

- `runtime_root_policy: {RUNTIME_ROOT_POLICY}` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。
"""
RUNTIME_ROOT_CONTRACT_HEADING_JA = "## 実行時のルートの決め方"
RUNTIME_ROOT_CONTRACT_SECTION_JA = f"""{RUNTIME_ROOT_CONTRACT_HEADING_JA}

- `runtime_root_policy: {RUNTIME_ROOT_POLICY}` を適用する。
- Claude Code では、プラグインのルートとして `CLAUDE_PLUGIN_ROOT` を使う。
- Codex では、ホストが示したこの `SKILL.md` の絶対パスから上の階層へたどり、プラグインの定義ファイル（`.codex-plugin/plugin.json` か `.claude-plugin/plugin.json`）を持つ最も近い祖先を、論理上の `PLUGIN_ROOT` とする。
- 作業ディレクトリ（`cwd`）からプラグインのルートを推測しない。置き換える前のプレースホルダをそのままシェルへ渡さない。シェルを呼ぶたびに、その中で解決済みの絶対パスを `PLUGIN_ROOT` に入れる。
- `prompts/` の下のファイルも、このスキルの決まりに従う。
"""
RUNTIME_ROOT_CONTRACT_SECTIONS = {
    "en": RUNTIME_ROOT_CONTRACT_SECTION,
    "ja": RUNTIME_ROOT_CONTRACT_SECTION_JA,
}
EXPECTED_EXTERNAL_MUTATION_RUNTIME = {
    "contract_id": "external-mutation-guard-v1",
    "runner_ref": "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py",
    "schema_ref": "plugin:skill-governance-adapters/schemas/external-mutation-guard.schema.json",
    "contract_ref": "plugin:skill-governance-adapters/references/external-mutation-guard-contract.md",
    "hook_manifest_ref": "plugin:skill-governance-adapters/.claude-plugin/plugin.json",
    "confirmation_event": "UserPromptSubmit",
    "enforcement_event": "PreToolUse",
    "enforcement_scope": "recognized-bash-remote-mutations-and-all-bash-during-pending-guard-context",
    "flow": EXTERNAL_MUTATION_FLOW,
}
EXPECTED_EXTERNAL_GUARD_POLICY = {
    "minimum_guard": "preview-and-explicit-confirmation",
    "preview_required": True,
    "runtime": EXPECTED_EXTERNAL_MUTATION_RUNTIME,
}
EXPECTED_FORBIDDEN = {
    "semantic-evaluation",
    "30-thinking-method-diagnosis",
    "multi-agent-review",
    "improvement-execution",
}
EXPECTED_CHOICES = ["accept-as-is", "light", "standard", "detailed"]
EXPECTED_POLICY_KEYS = {
    "schema_version",
    "schema_id",
    "schema_sha256",
    "policy_id",
    "effect_values_ref",
    "effect_values",
    "artifact_first",
    "draft_handoff",
    "before_user_choice",
    "user_choice",
    "auto_promotion",
    "minimum_safe_guard",
    "effect_guards",
    "external_intelligence_runtime",
    "effect_overrides",
}
EXPECTED_PROJECTION_KEYS = {
    "schema_version",
    "schema_id",
    "schema_sha256",
    "policy_id",
    "policy_sha256",
    "plugin",
    "manifest_ref",
    "artifact_first",
    "draft_handoff",
    "auto_promotion",
    "minimum_safe_guard",
    "entrypoints",
    "external_mutation_runtime",
    "external_intelligence_runtime",
}
EXPECTED_EXTERNAL_MUTATION_PROJECTION_KEYS = {
    "contract_id",
    "runner_ref",
    "runner_sha256",
    "schema_ref",
    "schema_sha256",
    "contract_ref",
    "hook_manifest_ref",
    "hook_manifest_sha256",
    "confirmation_event",
    "enforcement_event",
    "enforcement_scope",
    "flow",
    "preview_action",
    "confirmation_action",
    "authorize_action",
    "execute_action",
    "enforcer_action",
}
EXPECTED_RUNTIME_PROJECTION_KEYS = {
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
EXPECTED_EXTERNAL_RUNTIME = {
    "contract_id": "external-intelligence-runtime-v1",
    "adapter_ref": "plugin:skill-governance-adapters/scripts/build-external-intelligence-runtime.py",
    "engine_ref": "plugin:skill-governance-adapters/scripts/build-external-intelligence.py",
    "schema_ref": "plugin:skill-governance-adapters/schemas/external-intelligence-runtime.schema.json",
    "contract_ref": "plugin:skill-governance-adapters/references/external-intelligence-runtime-contract.md",
    "caller_ref": "plugin:skill-governance-adapters/hooks/build-external-intelligence-context.py",
    "caller_manifest_ref": "plugin:skill-governance-adapters/.claude-plugin/plugin.json",
    "caller_event": "UserPromptSubmit",
    "default_scope": "project",
    "standalone_behavior": "warning-continue",
}


class ContractError(ValueError):
    """A fail-closed artifact-delivery contract violation."""


def _repo_path(root: pathlib.Path, value: str | pathlib.PurePosixPath) -> pathlib.Path:
    return root / pathlib.PurePosixPath(value)


def _relative(root: pathlib.Path, path: pathlib.Path) -> str:
    return path.relative_to(root).as_posix()


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"required file missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"JSON root must be an object: {path}")
    return data


def _hook_wiring(manifest_path: pathlib.Path) -> dict[str, Any]:
    """plugin.json の hooks 宣言を、外出し形 (./hooks/hooks.json) も含めて読む。

    宣言の置き場が inline から参照形へ移っても、配線の実体は一つしかない。
    ここで正規化して、読む側が置き場の違いを知らずに済むようにする。

    manifest が `hooks` を一切書かない形もある: plugin loader が `hooks/hooks.json`
    を標準自動検出して1回だけ配布する現行契約で、manifest へ再掲すると二重読込に
    なるため意図的に空にしてある。この形を「宣言なし」と誤読すると guard の配線
    検査そのものが落ちるので、自動検出先を同じ正規化の中で解決する。
    """
    hooks = _load_json(manifest_path).get("hooks")
    if hooks is None:
        autoloaded = manifest_path.parent.parent / "hooks" / "hooks.json"
        if autoloaded.is_file():
            document = _load_json(autoloaded)
            hooks = document.get("hooks", document)
    if isinstance(hooks, str):
        rel = pathlib.PurePosixPath(hooks.lstrip("./"))
        if rel.is_absolute() or ".." in rel.parts:
            raise ContractError(f"external hooks path must stay inside plugin: {hooks}")
        external = _load_json(manifest_path.parent.parent / pathlib.Path(rel))
        hooks = external.get("hooks", external)
    if not isinstance(hooks, dict):
        raise ContractError(f"hook manifest hooks missing: {manifest_path}")
    return hooks


def _canonical_sha256(data: dict[str, Any]) -> str:
    encoded = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raw_sha256(path: pathlib.Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise ContractError(f"external intelligence reference missing: {path}") from exc


def _manifest_sha256(path: pathlib.Path) -> str:
    """plugin の hook 配線だけを固定する (manifest の他 field と version は除く)。

    生 hash を投影へ焼くと循環する。artifact-delivery.json は plugin の内容として
    build-plugin-release の fingerprint に数えられ、その fingerprint で version が
    上がり、version が動けば manifest の生 hash が変わって投影がまた drift する。
    不動点が存在しない。ここで固定したいのは「guard が宣言した hook がその manifest
    から外されていない」ことだけで、採番は無関係なので version を落として比較する。

    hash 対象は解決後の配線そのもの。manifest 本体を hash すると、宣言が
    `hooks/hooks.json` へ外出しされた瞬間に「hook が消えても sha が動かない」
    無害な定数になり、guard が守っているつもりで何も守らなくなる。
    """
    return _canonical_sha256(_hook_wiring(path))


def _plugin_ref_path(root: pathlib.Path, ref: str) -> pathlib.Path:
    prefix = "plugin:"
    if not isinstance(ref, str) or not ref.startswith(prefix):
        raise ContractError(f"external intelligence ref must start with {prefix!r}: {ref!r}")
    relative = pathlib.PurePosixPath(ref[len(prefix) :])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ContractError(f"unsafe external intelligence ref: {ref!r}")
    return root / "plugins" / relative


def discover_plugin_dirs(root: pathlib.Path) -> list[pathlib.Path]:
    """Return the on-disk manifest mother set; no plugin allowlist is used."""
    plugins_root = root / "plugins"
    return sorted(
        manifest.parents[1]
        for manifest in plugins_root.glob("*/.claude-plugin/plugin.json")
        if manifest.is_file()
    )


def _effect_values_from_source(root: pathlib.Path, ref: str) -> set[str]:
    if "#" not in ref:
        raise ContractError(f"effect_values_ref must name a symbol: {ref!r}")
    path_text, symbol = ref.rsplit("#", 1)
    path = _repo_path(root, path_text)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except FileNotFoundError as exc:
        raise ContractError(f"effect enum SSOT missing: {path}") from exc
    except SyntaxError as exc:
        raise ContractError(f"effect enum SSOT is invalid Python: {path}: {exc}") from exc
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == symbol for target in targets):
            continue
        try:
            raw = ast.literal_eval(node.value)
        except (ValueError, TypeError) as exc:
            raise ContractError(f"{ref} must be a literal collection") from exc
        if not isinstance(raw, (set, list, tuple)) or not all(
            isinstance(value, str) for value in raw
        ):
            raise ContractError(f"{ref} must contain string effect values")
        return set(raw)
    raise ContractError(f"effect enum symbol not found: {ref}")


def _frontmatter(path: pathlib.Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ContractError(f"entrypoint missing: {path}") from exc
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise ContractError(f"invalid SKILL.md frontmatter: {path}: {exc}") from exc
    if not isinstance(frontmatter, dict):
        raise ContractError(f"SKILL.md frontmatter must be an object: {path}")
    return frontmatter


def load_policy(root: pathlib.Path) -> dict[str, Any]:
    return _load_json(_repo_path(root, POLICY_REL))


def validate_document(
    schema: dict[str, Any],
    definition: str,
    document: dict[str, Any],
    label: str,
) -> None:
    """Validate a document against the selected central Draft 2020-12 $def."""
    try:
        Draft202012Validator.check_schema(schema)
        wrapper = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
        validator = Draft202012Validator(wrapper)
    except (SchemaError, KeyError, TypeError) as exc:
        raise ContractError(f"central schema contract drift: {exc}") from exc
    errors = sorted(
        validator.iter_errors(document),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ContractError(f"{label} Draft202012 validation failed at {location}: {error.message}")


def validate_schema_contract(schema: dict[str, Any]) -> None:
    """Prevent a valid-but-weakened schema from silently relaxing the gate."""
    try:
        definitions = schema["$defs"]
        policy = definitions["policy"]
        projection = definitions["projection"]
        entrypoint = definitions["entrypoint"]
        external_guard = definitions["externalMutationGuard"]
        external_mutation_runtime = definitions["externalMutationRuntimeProjection"]
        runtime_projection = definitions["externalRuntimeProjection"]
    except (KeyError, TypeError) as exc:
        raise ContractError(f"central schema contract drift: missing definition: {exc}") from exc
    external_branch = next(
        (
            branch
            for branch in entrypoint.get("allOf", [])
            if branch.get("if", {}).get("properties", {}).get("effect", {}).get("const")
            == "external-mutation"
        ),
        {},
    )
    checks = [
        (schema.get("$id") == SCHEMA_ID, "$id"),
        (set(policy.get("required", [])) == EXPECTED_POLICY_KEYS, "policy.required"),
        (set(projection.get("required", [])) == EXPECTED_PROJECTION_KEYS, "projection.required"),
        (set(entrypoint.get("required", [])) == {"path", "effect", "guard"}, "entrypoint.required"),
        (
            set(runtime_projection.get("required", [])) == EXPECTED_RUNTIME_PROJECTION_KEYS,
            "externalRuntimeProjection.required",
        ),
        (
            set(external_mutation_runtime.get("required", []))
            == EXPECTED_EXTERNAL_MUTATION_PROJECTION_KEYS,
            "externalMutationRuntimeProjection.required",
        ),
        (
            projection.get("properties", {}).get("manifest_ref", {}).get("const")
            == ".claude-plugin/plugin.json",
            "projection.manifest_ref.const",
        ),
        (
            projection.get("properties", {}).get("schema_id", {}).get("const") == SCHEMA_ID,
            "projection.schema_id.const",
        ),
        (
            entrypoint.get("properties", {}).get("path", {}).get("pattern")
            == r"^skills/[^/]+/SKILL\.md$",
            "entrypoint.path.pattern",
        ),
        (
            entrypoint.get("properties", {}).get("guard_contract", {}).get("$ref")
            == "#/$defs/externalMutationGuard",
            "entrypoint.guard_contract.$ref",
        ),
        (
            external_branch.get("then", {}).get("required") == ["guard_contract"],
            "entrypoint.external-mutation.guard_contract.required",
        ),
        (
            set(external_guard.get("required", []))
            == {"runtime_ref", "flow"},
            "externalMutationGuard.required",
        ),
        (
            external_guard.get("properties", {}).get("runtime_ref", {}).get("const")
            == "#/external_mutation_runtime"
            and external_guard.get("properties", {}).get("flow", {}).get("const")
            == EXTERNAL_MUTATION_FLOW,
            "externalMutationGuard.runtime connection",
        ),
        (
            policy.get("properties", {}).get("effect_overrides", {}).get("maxProperties") == 0
            and policy.get("properties", {}).get("effect_overrides", {}).get("const") == {},
            "policy.effect_overrides.maxProperties",
        ),
    ]
    failed = [name for passed, name in checks if not passed]
    if failed:
        raise ContractError(f"central schema contract drift: {', '.join(failed)}")


def validate_policy(root: pathlib.Path, policy: dict[str, Any]) -> None:
    schema = _load_json(_repo_path(root, SCHEMA_REL))
    validate_schema_contract(schema)
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict) or not {"policy", "projection"} <= set(definitions):
        raise ContractError(f"{SCHEMA_REL} must define policy and projection")
    if set(policy) != EXPECTED_POLICY_KEYS:
        raise ContractError(
            f"policy keys drift: expected={sorted(EXPECTED_POLICY_KEYS)!r} actual={sorted(policy)!r}"
        )
    if policy.get("schema_id") != SCHEMA_ID:
        raise ContractError("policy schema_id drift")
    if policy.get("schema_sha256") != _raw_sha256(_repo_path(root, SCHEMA_REL)):
        raise ContractError("policy schema_sha256 drift")
    validate_document(schema, "policy", policy, "artifact delivery policy")
    if policy.get("artifact_first") is not True:
        raise ContractError("artifact_first must be true")
    if policy.get("draft_handoff") != {
        "actual_artifact_required": True,
        "minimum_state": "usable-draft",
        "present_before_user_choice": True,
    }:
        raise ContractError("draft_handoff must present an actual usable draft before choice")
    before = policy.get("before_user_choice", {})
    if set(before.get("forbidden_operations", [])) != EXPECTED_FORBIDDEN:
        raise ContractError("before_user_choice forbidden operation set is incomplete")
    choice = policy.get("user_choice", {})
    if choice.get("improvement_levels") != EXPECTED_CHOICES:
        raise ContractError(
            "user_choice improvement levels must be accept-as-is/light/standard/detailed"
        )
    if choice.get("exhaustive_event") != "exhaustive":
        raise ContractError("exhaustive must be a separate user event")
    if choice.get("release_event") != "release":
        raise ContractError("release must be a separate explicit event")
    if choice.get("exhaustive_requires_separate_event") is not True:
        raise ContractError("exhaustive must require a separate explicit event")
    if policy.get("auto_promotion") != {"exhaustive": False, "release": False}:
        raise ContractError("release/exhaustive auto promotion must remain disabled")
    minimum = policy.get("minimum_safe_guard", {})
    if minimum.get("fail_closed_on_unknown_effect") is not True:
        raise ContractError("unknown effects must fail closed")
    if minimum.get("target_scope_required") is not True:
        raise ContractError("minimum safe guard must require target scope")

    declared_values = policy.get("effect_values")
    if not isinstance(declared_values, list) or not all(
        isinstance(value, str) for value in declared_values
    ):
        raise ContractError("effect_values must be a string array")
    ssot_values = _effect_values_from_source(root, policy.get("effect_values_ref", ""))
    if set(declared_values) != ssot_values or declared_values != sorted(ssot_values):
        raise ContractError("effect_values drift from validate-frontmatter.py#EFFECT_VALUES")
    schema_effect_values = definitions.get("effect", {}).get("enum")
    if schema_effect_values != sorted(ssot_values):
        raise ContractError("central artifact-delivery schema effect enum drift")
    guards = policy.get("effect_guards")
    if not isinstance(guards, dict) or set(guards) != ssot_values:
        raise ContractError("effect_guards must cover the exact effect enum")
    external = policy.get("external_intelligence_runtime")
    if external != EXPECTED_EXTERNAL_RUNTIME:
        raise ContractError("external_intelligence_runtime central pointer drift")
    if guards["external-mutation"] != EXPECTED_EXTERNAL_GUARD_POLICY:
        raise ContractError("external-mutation structured guard/receipt contract drift")

    if policy.get("effect_overrides") != {}:
        raise ContractError("effect_overrides must remain empty; declare effect in SKILL.md frontmatter")


def _external_mutation_runtime_projection(
    root: pathlib.Path, policy: dict[str, Any]
) -> dict[str, Any]:
    pointer = copy.deepcopy(policy["effect_guards"]["external-mutation"]["runtime"])
    if pointer != EXPECTED_EXTERNAL_MUTATION_RUNTIME:
        raise ContractError("external mutation runtime central pointer drift")
    paths = {
        key: _plugin_ref_path(root, pointer[key])
        for key in ("runner_ref", "schema_ref", "contract_ref", "hook_manifest_ref")
    }
    for key, path in paths.items():
        if not path.is_file():
            raise ContractError(f"external mutation runtime {key} target missing: {path}")

    runner_text = paths["runner_ref"].read_text(encoding="utf-8")
    try:
        runner_tree = ast.parse(runner_text, filename=str(paths["runner_ref"]))
    except SyntaxError as exc:
        raise ContractError(f"external mutation runner invalid Python: {exc}") from exc
    functions = {
        node.name
        for node in runner_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    required_functions = {"preview", "hook_confirm", "authorize", "execute", "pretool"}
    if not required_functions <= functions:
        raise ContractError(
            "external mutation runner lacks receipt producer/validator/consumer actions"
        )
    literals = {
        node.value
        for node in ast.walk(runner_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    actions = {"preview", "hook-confirm", "authorize", "execute", "pretool"}
    if not actions <= literals:
        raise ContractError("external mutation runner CLI actions are not connected")

    hooks = _hook_wiring(paths["hook_manifest_ref"])

    def registered(event: str, action: str, *, matcher: str | None = None) -> bool:
        groups = hooks.get(event)
        if not isinstance(groups, list):
            return False
        return any(
            isinstance(group, dict)
            and (matcher is None or group.get("matcher") == matcher)
            and any(
                isinstance(handler, dict)
                and isinstance(handler.get("command"), str)
                and paths["runner_ref"].name in handler["command"]
                and re.search(rf"\s{re.escape(action)}(?:\s|$)", handler["command"])
                for handler in group.get("hooks", [])
            )
            for group in groups
        )

    if not registered(pointer["confirmation_event"], "hook-confirm"):
        raise ContractError("external mutation confirmation producer hook is uninvoked")
    if not registered(pointer["enforcement_event"], "pretool", matcher="Bash"):
        raise ContractError("external mutation PreToolUse consumer/enforcer hook is uninvoked")

    return {
        **pointer,
        "runner_sha256": _raw_sha256(paths["runner_ref"]),
        "schema_sha256": _raw_sha256(paths["schema_ref"]),
        "hook_manifest_sha256": _manifest_sha256(paths["hook_manifest_ref"]),
        "preview_action": "preview",
        "confirmation_action": "hook-confirm",
        "authorize_action": "authorize",
        "execute_action": "execute",
        "enforcer_action": "pretool",
    }


def _external_runtime_projection(root: pathlib.Path, policy: dict[str, Any]) -> dict[str, Any]:
    pointer = copy.deepcopy(policy["external_intelligence_runtime"])
    for key in (
        "adapter_ref",
        "engine_ref",
        "schema_ref",
        "contract_ref",
        "caller_ref",
        "caller_manifest_ref",
    ):
        ref_path = _plugin_ref_path(root, pointer[key])
        if not ref_path.is_file():
            raise ContractError(f"external intelligence {key} target missing: {ref_path}")
    caller_path = _plugin_ref_path(root, pointer["caller_ref"])
    adapter_path = _plugin_ref_path(root, pointer["adapter_ref"])
    caller_text = caller_path.read_text(encoding="utf-8")
    try:
        caller_tree = ast.parse(caller_text, filename=str(caller_path))
    except SyntaxError as exc:
        raise ContractError(f"external intelligence caller invalid Python: {exc}") from exc
    calls_adapter = any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "runner")
            or (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and node.func.attr == "run"
            )
        )
        for node in ast.walk(caller_tree)
    )
    string_literals = {
        node.value
        for node in ast.walk(caller_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    if (
        not calls_adapter
        or not ({"--request", "--request-json"} & string_literals)
        or adapter_path.name not in caller_text
        or "ADAPTER_PATH" not in caller_text
    ):
        raise ContractError("external intelligence caller does not invoke adapter with a request argument")

    manifest_path = _plugin_ref_path(root, pointer["caller_manifest_ref"])
    event_groups = _hook_wiring(manifest_path).get(pointer["caller_event"], [])
    caller_suffix = "/".join(pathlib.PurePosixPath(pointer["caller_ref"].split(":", 1)[1]).parts[1:])
    registered = any(
        isinstance(group, dict)
        and any(
            isinstance(handler, dict)
            and isinstance(handler.get("command"), str)
            and caller_suffix in handler["command"]
            for handler in group.get("hooks", [])
        )
        for group in event_groups
    ) if isinstance(event_groups, list) else False
    if not registered:
        raise ContractError("external intelligence caller manifest registration missing")

    pointer["adapter_sha256"] = _raw_sha256(adapter_path)
    pointer["engine_sha256"] = _raw_sha256(_plugin_ref_path(root, pointer["engine_ref"]))
    pointer["policy_sha256"] = _raw_sha256(_plugin_ref_path(root, pointer["schema_ref"]))
    pointer["caller_sha256"] = _raw_sha256(caller_path)
    return pointer


def _external_guard_contradiction(path: pathlib.Path) -> str | None:
    """Reject explicit prose that contradicts the structured declaration."""
    text = path.read_text(encoding="utf-8").lower()
    immediate = (
        r"\bmutate\s+(?:the\s+)?remote\b.{0,40}\bimmediately\b",
        r"\bimmediately\s+mutate\s+(?:the\s+)?remote\b",
    )
    if any(re.search(pattern, text) for pattern in immediate):
        return "immediate external mutation bypasses the receipt consumer"
    patterns = (
        r"\bdo\s+not\s+(?:request|require|obtain|ask\s+for)\s+(?:explicit\s+)?confirmation\b",
        r"\b(?:the\s+)?(?:safety\s+)?gate\s+is\s+disabled\b",
        r"\b(?:skip|bypass|disable)\s+(?:the\s+)?(?:preview|confirmation|safety\s+)?gate\b",
        r"(?:\u30d7\u30ec\u30d3\u30e5\u30fc|\u78ba\u8a8d|\u5b89\u5168)\u30b2\u30fc\u30c8(?:\u306f|\u3092)?\u7121\u52b9",
    )
    if any(re.search(pattern, text) for pattern in patterns):
        return "structured external-mutation guard contradicts SKILL.md instructions"
    return None


def _skill_language(text: str) -> str:
    """SKILL.md の正規形の言語を Post-choice 見出しで決める。

    日本語の Post-choice 見出しが行全体で一致すれば (前後の空白は無視) "ja"、
    なければ従来どおり "en"。Runtime root 節の挿入・ガードブロックの移行・
    wiring の検査はすべてこの 1 つの判定に従う。
    """
    lines = (line.strip() for line in text.splitlines())
    return "ja" if POST_CHOICE_HEADING_JA in lines else "en"


def _canonical_external_guard_block(language: str = "en") -> str:
    if language not in EXTERNAL_GUARD_BLOCK_MARKERS:
        raise ContractError(f"unknown canonical guard block language: {language!r}")
    runner = EXTERNAL_GUARD_SHELL_RUNNER
    if language == "ja":
        # 散文だけを日本語にする。コマンド行は英語版とバイト単位で同じにし、
        # _validate_external_guard_wiring の必須コマンドの検査を両方の言語に効かせる。
        return f"""{EXTERNAL_GUARD_BLOCK_BEGIN_JA}
### 外部変更の受領書の手順（必須）

外部変更のコマンドを直接実行しない。山括弧のプレースホルダは、すべてこの実行で確かめた値に置き換える。
値が欠けていたり正しくなかったりすれば、中央の CLI が止める（fail-closed）。

`preview` の前に、ガードを持つプラグインのルートを1回だけ解決する。インストールされたプラグインからは、
隣のプラグインに `<プラグインのルート>/..` では届かないので、このパスを推測しない:

```bash
python3 "{EXTERNAL_GUARD_ROOT_RESOLVER}" {EXTERNAL_GUARD_PLUGIN}
```

表示された絶対パスを、`preview`・`authorize`・`execute` の `{EXTERNAL_GUARD_ROOT_PLACEHOLDER}` に使う
（確認を待つあいだはほかの Bash が止められるので、解決し直さない）。
解決のスクリプトが 0 以外で終わったら、外部変更をせずに止まり、`{EXTERNAL_GUARD_PLUGIN}` プラグインを入れるようユーザーに伝える。

```bash
python3 "{runner}" preview --project-root "$PWD" --entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" --target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" --side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json '<MUTATION_ARGV_JSON>'
```

この正規の `preview` の出力をユーザーに見せる。登録済みの `hook-confirm` を動かせるのは、`preview` が表示したとおりのユーザーの返答だけ。
そのあと、返ってきた2つの受領書のパスを使う:

```bash
python3 "{runner}" authorize --project-root "$PWD" --preview-receipt "<PREVIEW_RECEIPT_PATH>" --confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"
python3 "{runner}" execute --project-root "$PWD" --authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" --command-json '<MUTATION_ARGV_JSON>'
```

自動承認のフラグを使わない。この受領書の手順の外で外部変更のコマンドを実行しない。
{EXTERNAL_GUARD_BLOCK_END_JA}
"""
    return f"""{EXTERNAL_GUARD_BLOCK_BEGIN}
### Canonical external mutation receipt flow (mandatory)

Never execute the external mutation argv directly. Replace every angle-bracket placeholder
with the reviewed value from this run; the central CLI fails closed on missing/invalid values.

Resolve the guard plugin root once, before `preview`. An installed plugin cannot reach a sibling
plugin as `<plugin root>/..`, so never guess that path:

```bash
python3 "{EXTERNAL_GUARD_ROOT_RESOLVER}" {EXTERNAL_GUARD_PLUGIN}
```

Use the printed absolute path as `{EXTERNAL_GUARD_ROOT_PLACEHOLDER}` in `preview`, `authorize` and `execute`
(other Bash is blocked while the confirmation is pending, so do not resolve it again).
If the resolver exits non-zero, stop without any external mutation and tell the user to install
the `{EXTERNAL_GUARD_PLUGIN}` plugin.

```bash
python3 "{runner}" preview --project-root "$PWD" --entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" --target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" --side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json '<MUTATION_ARGV_JSON>'
```

Present that official preview output to the user. Only the exact user reply printed by `preview`
may trigger the registered `hook-confirm` producer. Then use the two returned receipt paths:

```bash
python3 "{runner}" authorize --project-root "$PWD" --preview-receipt "<PREVIEW_RECEIPT_PATH>" --confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"
python3 "{runner}" execute --project-root "$PWD" --authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" --command-json '<MUTATION_ARGV_JSON>'
```

Do not use an auto-approval flag or invoke the mutation command outside this receipt flow.
{EXTERNAL_GUARD_BLOCK_END}
"""


def _migrate_external_direct_examples(text: str) -> str:
    """Turn legacy executable mutation examples into inert argv inputs for the guard."""
    text = re.sub(
        r"(### 改善要望投入\n\n)```bash\n"
        r"python3 \$\{HARNESS_ROOT:-\.\}/scripts/notion-submit-improvement\.py \\\n"
        r".*?\n```",
        r"\1```text\n"
        "Construct <MUTATION_ARGV_JSON> as a JSON string array with the resolved python3 "
        "executable, the resolved notion-submit-improvement.py path, and these values: "
        "plugin, skill-name, title, type, desire, background, priority, importance, and pr-url.\n"
        "This is input to the canonical receipt flow above; never execute the submit script directly.\n"
        "```",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"# Notion PATCH 更新 \(同一ページ ID\)\n"
        r"python3 \$\{CLAUDE_PLUGIN_ROOT:-plugins/skill-intake\}/scripts/"
        r"intake_publish_pipeline\.py \\\n"
        r"\s+--intake\s+output/<hint>/intake\.json \\\n"
        r"\s+--manifest\s+output/<hint>/notion-manifest\.json \\\n"
        r"\s+--revise \\\n"
        r"\s+--page-id\s+<既存ページ ID>",
        "# Notion PATCH mutation: construct <MUTATION_ARGV_JSON> with the resolved "
        "intake_publish_pipeline.py path and --intake/--manifest/--revise/--page-id argv; "
        "pass it only to the canonical receipt flow above.",
        text,
    )
    text = re.sub(
        r"python3 \"\$PLUGIN_ROOT/scripts/intake_publish_pipeline\.py\" \\\n"
        r"\s+--intake\s+\"output/\$HINT/intake\.json\" \\\n"
        r"\s+--manifest\s+\"output/\$HINT/notion-manifest\.json\" \\\n"
        r"\s+\"\$\{MODE_ARGS\[@\]\}\" \\\n"
        r"\s+\"\$\{EXTRA_ARGS\[@\]\}\"",
        "# Construct <MUTATION_ARGV_JSON> from the resolved intake_publish_pipeline.py, "
        "--intake, --manifest, MODE_ARGS and EXTRA_ARGS; pass it only to the canonical "
        "receipt flow above.",
        text,
    )
    text = re.sub(
        r"\s*```bash\n\s*python3 \"\$CLAUDE_PLUGIN_ROOT/skills/"
        r"run-notion-gmail-sendlog-setup/scripts/setup-send-log-db\.py\" \\\n"
        r"\s*--db-id <送信ログDBのid> --apply[^\n]*\n\s*```",
        "```text\n"
        "Construct <MUTATION_ARGV_JSON> with the resolved setup-send-log-db.py path, "
        "--db-id and --apply. Pass it only to the canonical receipt flow above.\n"
        "```",
        text,
    )
    if "send-campaign.py" in text:
        # 禁止したいのは「skill が自動承認フラグを打つこと」であって、cron 用の
        # --auto-approve / --yes は send-campaign.py に実在し続ける。フラグ名を伏せ字
        # トークンへ潰すと _direct_external_mutation_instruction は緑になるが、本文には
        # 存在しないフラグを打てという嘘の手順が残る (しかも 2 フラグが同一文字列へ潰れて
        # 「`X` / `X`」と重複する)。検査を通すためではなく記述を真にするため、フラグ literal を
        # モード名へ寄せ、skill から打つ体裁の CLI 例そのものは落とす。
        text = re.sub(r"`?--auto-approve`?\s*/\s*`?--yes`?", "無人自動承認モード", text)
        text = re.sub(r"`?--auto-approve`?", "無人自動承認モード", text)
        text = re.sub(r"`?--yes`?(?=[`\s/),])", "無人自動承認モード", text)
        text = re.sub(
            r"^/run-notion-gmail-send 無人自動承認モード[^\n]*\n",
            "",
            text,
            flags=re.MULTILINE,
        )
        text = text.replace(
            '`python3 "$CLAUDE_PLUGIN_ROOT/skills/run-notion-gmail-send/scripts/send-campaign.py"`',
            "`<MUTATION_ARGV_JSON>` (the exact resolved send-campaign argv for the canonical receipt flow)",
        )
    return text


def _canonical_runtime_root_block(language: str, *, has_prompts: bool) -> str:
    """Render only resource contracts that actually exist for the owner skill."""
    section = RUNTIME_ROOT_CONTRACT_SECTIONS[language]
    if not has_prompts:
        section = "\n".join(line for line in section.splitlines() if "`prompts/`" not in line) + "\n"
    return RUNTIME_ROOT_BLOCK_BEGIN + "\n" + section + RUNTIME_ROOT_BLOCK_END + "\n"


def _ensure_runtime_root_contract(text: str, path: pathlib.Path) -> str:
    if not text.startswith("---"):
        raise ContractError(f"{path}: SKILL.md frontmatter missing")
    _, front, body = text.split("---", 2)
    if f"runtime_root_policy: {RUNTIME_ROOT_POLICY}" not in front:
        line = f"runtime_root_policy: {RUNTIME_ROOT_POLICY}"
        if re.search(r"^runtime_root_policy:", front, re.M):
            front = re.sub(r"^runtime_root_policy:[^\n]*", line, front, flags=re.M)
        else:
            front = front.rstrip("\n") + "\n" + line + "\n"
    language = _skill_language(text)
    block = _canonical_runtime_root_block(language, has_prompts=(path.parent / "prompts").is_dir())
    markers = (RUNTIME_ROOT_BLOCK_BEGIN, RUNTIME_ROOT_BLOCK_END)
    if any(marker in body for marker in markers):
        if any(body.count(marker) != 1 for marker in markers):
            raise ContractError(f"{path}: runtime root block missing/duplicated marker")
        start, end = body.index(markers[0]), body.index(markers[1])
        if end < start:
            raise ContractError(f"{path}: runtime root block markers out of order")
        body = body[:start] + body[end + len(markers[1]):].lstrip("\n")
    # Convert either legacy locale; relocate the managed block directly after purpose.
    headings = "|".join(re.escape(h) for h in (RUNTIME_ROOT_CONTRACT_HEADING, RUNTIME_ROOT_CONTRACT_HEADING_JA))
    body = re.sub(rf"^(?:{headings})[ \t]*\n.*?(?=^## |\Z)", "", body, flags=re.M | re.S)
    purpose = re.search(r"^## (?:Purpose & Output Contract|目的と出力契約)[ \t]*$", body, re.M)
    if purpose:
        following = re.search(r"^## ", body[purpose.end():], re.M)
        at = purpose.end() + following.start() if following else len(body)
    else:
        first = re.search(r"^## ", body, re.M)
        if first is None:
            raise ContractError(f"{path}: no section to anchor runtime root contract")
        at = first.start()
    body = body[:at].rstrip("\n") + "\n\n" + block + "\n" + body[at:].lstrip("\n")
    return "---" + front + "---" + body


def _validate_runtime_root_wiring(path: pathlib.Path) -> None:
    text = path.read_text(encoding="utf-8")
    language = _skill_language(text)
    other = "en" if language == "ja" else "ja"
    if re.search(rf"^{re.escape(RUNTIME_ROOT_CONTRACT_SECTIONS[other].splitlines()[0])}[ \t]*$", text, re.M):
        raise ContractError(f"{path}: runtime root contract language mismatch")
    begin, end = RUNTIME_ROOT_BLOCK_BEGIN, RUNTIME_ROOT_BLOCK_END
    if begin in text or end in text:
        if text.count(begin) != 1 or text.count(end) != 1 or text.index(end) < text.index(begin):
            raise ContractError(f"{path}: runtime root block markers invalid")
        actual = text[text.index(begin):text.index(end) + len(end)]
        expected = _canonical_runtime_root_block(language, has_prompts=(path.parent / "prompts").is_dir()).rstrip("\n")
        if actual != expected:
            raise ContractError(f"{path}: runtime root canonical block drift")
    elif language == "ja":
        raise ContractError(f"{path}: Japanese runtime root requires a managed block; run migration")


def migrate_external_guard_blocks(root: pathlib.Path, plugin_names: set[str] | None = None, skill_names: set[str] | None = None) -> int:
    """Mechanically place the canonical CLI contract in every external entrypoint."""
    logical_entrypoints = 0
    seen_inodes: set[tuple[int, int]] = set()
    # 既存のブロックは言語を問わず取り除き、ファイルの言語の正規形だけを入れ直す。
    block_pattern = re.compile(
        "|".join(
            rf"\n?{re.escape(begin)}.*?{re.escape(end)}\n?"
            for begin, end in EXTERNAL_GUARD_BLOCK_MARKERS.values()
        ),
        re.DOTALL,
    )
    for plugin_dir in discover_plugin_dirs(root):
        if plugin_names is not None and plugin_dir.name not in plugin_names:
            continue
        for path in sorted((plugin_dir / "skills").glob("*/SKILL.md")):
            if skill_names is not None and path.parent.name not in skill_names:
                continue
            if _frontmatter(path).get("effect") != "external-mutation":
                continue
            logical_entrypoints += 1
            identity = (path.stat().st_dev, path.stat().st_ino)
            if identity in seen_inodes:
                continue
            seen_inodes.add(identity)
            text = block_pattern.sub("\n", path.read_text(encoding="utf-8"))
            text = _migrate_external_direct_examples(text)
            text = _ensure_runtime_root_contract(text, path)
            language = _skill_language(text)
            heading = POST_CHOICE_HEADINGS[language]
            heading_at = text.find(heading)
            if heading_at < 0:
                raise ContractError(f"{path}: canonical post-choice execution section missing")
            paragraph_start = text.find("\n\n", heading_at + len(heading))
            paragraph_end = text.find("\n\n", paragraph_start + 2)
            if paragraph_start < 0 or paragraph_end < 0:
                raise ContractError(f"{path}: post-choice execution paragraph malformed")
            block = _canonical_external_guard_block(language)
            updated = (
                text[: paragraph_end + 2]
                + block
                + "\n\n"
                + text[paragraph_end + 2 :].lstrip("\n")
            )
            if updated != path.read_text(encoding="utf-8"):
                path.write_text(updated, encoding="utf-8")
    return logical_entrypoints


_SHELL_EXPANSION_CHECKER = None


def _guard_shell_expansion(command: str) -> bool:
    """Use the executable guard's parser as the single syntax contract."""
    global _SHELL_EXPANSION_CHECKER
    if _SHELL_EXPANSION_CHECKER is None:
        source = pathlib.Path(__file__).resolve().parents[1] / "plugins/skill-governance-adapters/scripts/build-external-mutation-guard.py"
        spec = importlib.util.spec_from_file_location("artifact_guard_shell_contract", source)
        if spec is None or spec.loader is None:
            raise ContractError("canonical shell syntax checker unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SHELL_EXPANSION_CHECKER = module.has_unsafe_shell_expansion
    return _SHELL_EXPANSION_CHECKER(command)


def _direct_external_mutation_instruction(text: str) -> str | None:
    if re.search(r"--(?:auto-approve|yes)(?:\s|`|\)|\]|$)", text):
        return "auto-approval bypass is forbidden for external mutation entrypoints"
    mutation_cli = re.compile(
        r"\bpython3\b[^\n]*(?:"
        r"send-campaign\.py|intake_publish_pipeline\.py|publish-notion-page\.py|"
        r"(?:mutat|publish|send|submit)[a-z0-9_-]*\.py|"
        r"gh-bridge\.py[^\n]*(?:\bapply\b|--apply)"
        r")",
        re.IGNORECASE,
    )
    direct_remote = re.compile(
        r"(?:\bcurl\b[^\n]*(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)\b|"
        r"\bgh\s+(?:issue|pr)\s+(?:create|edit|close|reopen|merge|comment)\b|"
        r"\bgh\s+api\b[^\n]*(?:-X|--method)\s*(?:POST|PUT|PATCH|DELETE)\b)",
        re.IGNORECASE,
    )
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "build-external-mutation-guard.py" in line:
            if _guard_shell_expansion(line):
                return f"shell expansion executes before canonical guard: {line[:160]}"
            try:
                tokens = list(shlex.shlex(line, posix=True, punctuation_chars=True))
            except ValueError:
                tokens = []
            canonical = (len(tokens) >= 3 and tokens[0] in {"python3", "/usr/bin/python3"}
                         and pathlib.PurePosixPath(tokens[1]).name == "build-external-mutation-guard.py"
                         and tokens[2] in {"preview", "authorize", "execute", "cancel"})
            operators = [token for token in tokens if token and set(token) <= set("&|;<>()")]
            if canonical and not operators:
                continue
            if operators:
                return f"compound guard command bypasses canonical execute: {line[:160]}"
        if line.startswith("MUTATION_ARGV_JSON="):
            continue
        if re.match(r"^(?:Construct|Set) <MUTATION_ARGV_JSON>", line):
            continue
        if "setup-send-log-db.py" in line:
            continue
        matched = mutation_cli.search(line)
        if matched and not (
            "notion-submit-improvement.py" in line and "--dry-run" in line
        ):
            return f"direct mutation CLI bypasses canonical execute: {line[:160]}"
        if direct_remote.search(line):
            return f"direct remote mutation bypasses canonical execute: {line[:160]}"
    return None


def _validate_external_guard_wiring(path: pathlib.Path) -> None:
    text = path.read_text(encoding="utf-8")
    language = _skill_language(text)
    # もう一方の言語のマーカーは 1 つでも残っていれば不合格 (言語の不一致・両言語の併存)。
    for other, markers in EXTERNAL_GUARD_BLOCK_MARKERS.items():
        if other != language and any(marker in text for marker in markers):
            raise ContractError(
                f"{path}: external-mutation canonical CLI wiring block language mismatch: "
                f"{other} block in {language} SKILL.md"
            )
    begin_marker, end_marker = EXTERNAL_GUARD_BLOCK_MARKERS[language]
    if text.count(begin_marker) != 1 or text.count(end_marker) != 1:
        raise ContractError(f"{path}: external-mutation canonical CLI wiring block missing/duplicated")
    start = text.index(begin_marker)
    # 終わりのマーカーが始まりより前にあると index は ValueError を投げる。契約違反として報告する。
    end = text.find(end_marker, start)
    if end < 0:
        raise ContractError(f"{path}: external-mutation canonical CLI wiring block markers out of order")
    block = text[start : end + len(end_marker)]
    post_choice = text.find(POST_CHOICE_HEADINGS[language])
    if post_choice < 0 or start < post_choice:
        raise ContractError(f"{path}: canonical CLI wiring must be in post-choice execution")
    runner = f'python3 "{EXTERNAL_GUARD_SHELL_RUNNER}"'
    required = (
        f'python3 "{EXTERNAL_GUARD_ROOT_RESOLVER}" {EXTERNAL_GUARD_PLUGIN}',
        f'{runner} preview --project-root "$PWD" '
        '--entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" '
        '--target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" '
        '--side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json \'<MUTATION_ARGV_JSON>\'',
        "hook-confirm",
        f'{runner} authorize --project-root "$PWD" '
        '--preview-receipt "<PREVIEW_RECEIPT_PATH>" '
        '--confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"',
        f'{runner} execute --project-root "$PWD" '
        '--authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" '
        '--command-json \'<MUTATION_ARGV_JSON>\'',
    )
    positions = [block.find(value) for value in required]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ContractError(f"{path}: canonical CLI wiring producer/consumer actions drift")
    direct = _direct_external_mutation_instruction(text)
    if direct is not None:
        raise ContractError(f"{path}: {direct}")
    if block != _canonical_external_guard_block(language).rstrip("\n"):
        raise ContractError(f"{path}: canonical CLI wiring block content drift")
    _validate_runtime_root_wiring(path)


def _external_guard_contract(
    path: pathlib.Path,
    frontmatter: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    declared = frontmatter.get("external_mutation_guard")
    if declared is None:
        raise ContractError(
            f"{path}: external-mutation requires a structured external-mutation guard"
        )
    runtime = policy["effect_guards"]["external-mutation"]["runtime"]
    expected = {"runtime_ref": runtime["runner_ref"], "flow": runtime["flow"]}
    if declared != expected:
        raise ContractError(
            f"{path}: external_mutation_guard ref/flow drift: {declared!r} != {expected!r}"
        )
    contradiction = _external_guard_contradiction(path)
    if contradiction is not None:
        raise ContractError(f"{path}: {contradiction}")
    _validate_external_guard_wiring(path)
    return {"runtime_ref": "#/external_mutation_runtime", "flow": runtime["flow"]}


def _entrypoints(
    root: pathlib.Path,
    plugin_dir: pathlib.Path,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    allowed = set(policy["effect_values"])
    guards = {
        effect: value["minimum_guard"]
        for effect, value in policy["effect_guards"].items()
    }
    result: list[dict[str, Any]] = []
    for path in sorted((plugin_dir / "skills").glob("*/SKILL.md")):
        repo_relative = _relative(root, path)
        package_relative = path.relative_to(plugin_dir).as_posix()
        frontmatter = _frontmatter(path)
        effect = frontmatter.get("effect")
        if effect is None:
            raise ContractError(f"effect missing in SKILL.md frontmatter: {repo_relative}")
        if effect not in allowed:
            raise ContractError(f"unknown effect in {repo_relative}: {effect!r}")
        guard = guards[effect]
        entrypoint: dict[str, Any] = {
            "path": package_relative,
            "effect": effect,
            "guard": guard,
        }
        if effect == "external-mutation":
            entrypoint["guard_contract"] = _external_guard_contract(
                path,
                frontmatter,
                policy,
            )
        result.append(entrypoint)
    return result


def build_projection(
    root: pathlib.Path,
    plugin_dir: pathlib.Path,
    policy: dict[str, Any],
    *,
    external_runtime: dict[str, Any] | None = None,
    external_mutation_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_path = plugin_dir / ".claude-plugin/plugin.json"
    manifest = _load_json(manifest_path)
    plugin_name = manifest.get("name")
    if plugin_name != plugin_dir.name:
        raise ContractError(
            f"manifest name mismatch: {manifest_path}: {plugin_name!r} != {plugin_dir.name!r}"
        )
    if external_runtime is None:
        external_runtime = _external_runtime_projection(root, policy)
    if external_mutation_runtime is None:
        external_mutation_runtime = _external_mutation_runtime_projection(root, policy)
    entrypoints = _entrypoints(root, plugin_dir, policy)
    if plugin_name != "skill-governance-adapters" and any(
        entrypoint["effect"] == "external-mutation" for entrypoint in entrypoints
    ):
        dependencies = manifest.get("dependencies")
        if not isinstance(dependencies, list) or "skill-governance-adapters" not in dependencies:
            raise ContractError(
                f"{manifest_path}: external-mutation entrypoint requires "
                "skill-governance-adapters dependency"
            )
    return {
        "schema_version": 1,
        "schema_id": policy["schema_id"],
        "schema_sha256": policy["schema_sha256"],
        "policy_id": policy["policy_id"],
        "policy_sha256": _canonical_sha256(policy),
        "plugin": plugin_name,
        "manifest_ref": ".claude-plugin/plugin.json",
        "artifact_first": policy["artifact_first"],
        "draft_handoff": copy.deepcopy(policy["draft_handoff"]),
        "auto_promotion": copy.deepcopy(policy["auto_promotion"]),
        "minimum_safe_guard": copy.deepcopy(policy["minimum_safe_guard"]),
        "entrypoints": entrypoints,
        "external_mutation_runtime": copy.deepcopy(external_mutation_runtime),
        "external_intelligence_runtime": copy.deepcopy(external_runtime),
    }


def render_projection(projection: dict[str, Any]) -> str:
    return json.dumps(projection, ensure_ascii=False, indent=2) + "\n"


def expected_projections(root: pathlib.Path) -> dict[pathlib.Path, dict[str, Any]]:
    policy = load_policy(root)
    validate_policy(root, policy)
    runtime = _external_runtime_projection(root, policy)
    mutation_runtime = _external_mutation_runtime_projection(root, policy)
    projections = {
        plugin_dir / PROJECTION_NAME: build_projection(
            root,
            plugin_dir,
            policy,
            external_runtime=runtime,
            external_mutation_runtime=mutation_runtime,
        )
        for plugin_dir in discover_plugin_dirs(root)
    }
    schema = _load_json(_repo_path(root, SCHEMA_REL))
    for path, projection in projections.items():
        validate_document(schema, "projection", projection, _relative(root, path))
    return projections


def write_projections(root: pathlib.Path) -> int:
    expected = expected_projections(root)
    for path, projection in expected.items():
        path.write_text(render_projection(projection), encoding="utf-8")
    return len(expected)


def _projection_drift_errors(
    root: pathlib.Path,
    path: pathlib.Path,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:
    relative = _relative(root, path)
    errors: list[str] = []
    if actual.get("policy_sha256") != expected["policy_sha256"]:
        errors.append(f"{relative}: policy_sha256 drift")
    if actual.get("schema_sha256") != expected["schema_sha256"]:
        errors.append(f"{relative}: schema_sha256 drift")
    if actual.get("entrypoints") != expected["entrypoints"]:
        errors.append(
            f"{relative}: entrypoints/effect/guard/guard_contract coverage drift"
        )
    if actual.get("external_mutation_runtime") != expected["external_mutation_runtime"]:
        errors.append(f"{relative}: external_mutation_runtime pointer/hook/hash drift")
    if actual.get("external_intelligence_runtime") != expected["external_intelligence_runtime"]:
        errors.append(f"{relative}: external_intelligence_runtime pointer/hash drift")
    if actual != expected and not errors:
        errors.append(f"{relative}: projection drift; regenerate with build-artifact-delivery.py --write")
    return errors


def lint_repository(root: pathlib.Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    try:
        policy = load_policy(root)
        validate_policy(root, policy)
        runtime = _external_runtime_projection(root, policy)
        mutation_runtime = _external_mutation_runtime_projection(root, policy)
        schema = _load_json(_repo_path(root, SCHEMA_REL))
    except ContractError as exc:
        return [str(exc)]

    plugin_dirs = discover_plugin_dirs(root)
    manifest_projection_paths = {plugin / PROJECTION_NAME for plugin in plugin_dirs}
    on_disk_projection_paths = set((root / "plugins").glob(f"*/{PROJECTION_NAME}"))
    for orphan in sorted(on_disk_projection_paths - manifest_projection_paths):
        errors.append(f"{_relative(root, orphan)}: projection has no plugin manifest")

    for plugin_dir in plugin_dirs:
        path = plugin_dir / PROJECTION_NAME
        if not path.is_file():
            errors.append(f"{plugin_dir.name}: projection missing: {_relative(root, path)}")
        try:
            expected = build_projection(
                root,
                plugin_dir,
                policy,
                external_runtime=runtime,
                external_mutation_runtime=mutation_runtime,
            )
        except ContractError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            continue
        try:
            actual = _load_json(path)
            validate_document(schema, "projection", actual, _relative(root, path))
        except ContractError as exc:
            errors.append(str(exc))
            continue
        errors.extend(_projection_drift_errors(root, path, actual, expected))
    return errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument("--skill", action="append", help="limit migration to named skill (repeatable)")
    parser.add_argument("--plugin", action="append", help="limit migration to named plugin (repeatable)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", help="write every projection")
    group.add_argument("--check", action="store_true", help="read-only parity check (default)")
    group.add_argument(
        "--migrate-external-guard",
        action="store_true",
        help="place/update the canonical CLI block in every external-mutation SKILL",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.migrate_external_guard:
        try:
            changed = migrate_external_guard_blocks(args.repo_root.resolve(), set(args.plugin) if args.plugin else None, set(args.skill) if args.skill else None)
        except ContractError as exc:
            print(f"ARTIFACT_DELIVERY_ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"EXTERNAL_MUTATION_GUARD_MIGRATED: {changed} skills")
        return 0
    root = args.repo_root.resolve()
    if args.write:
        try:
            count = write_projections(root)
        except ContractError as exc:
            print(f"ARTIFACT_DELIVERY_ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"ARTIFACT_DELIVERY_GENERATED: {count} plugins")
        return 0
    errors = lint_repository(root)
    if errors:
        for error in errors:
            print(f"ARTIFACT_DELIVERY_ERROR: {error}", file=sys.stderr)
        return 1
    print(f"ARTIFACT_DELIVERY_OK: {len(discover_plugin_dirs(root))} plugins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

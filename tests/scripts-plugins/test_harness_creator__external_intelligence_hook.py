from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "harness-creator"
RUNTIME_PLUGIN = ROOT / "plugins" / "skill-governance-adapters"
HOOK = RUNTIME_PLUGIN / "hooks" / "build-external-intelligence-context.py"
ADAPTER = RUNTIME_PLUGIN / "scripts" / "build-external-intelligence-runtime.py"
ENGINE = ADAPTER.with_name("build-external-intelligence.py")
HC_ADAPTER = (
    PLUGIN
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "build-external-intelligence-runtime.py"
)
HC_ENGINE = HC_ADAPTER.with_name("build-external-intelligence.py")
HC_CONTRACT = (
    PLUGIN
    / "skills"
    / "ref-knowledge-loop"
    / "references"
    / "external-intelligence-runtime-contract.md"
)


def _load_hook():
    spec = importlib.util.spec_from_file_location("external_intelligence_hook", HOOK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(project: Path, *, prompt: str = "repair the retry timeout") -> dict:
    return {
        "session_id": "session-123",
        "transcript_path": str(project / "transcript.jsonl"),
        "cwd": str(project),
        "permission_mode": "default",
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
    }


def _search_output(project: Path) -> dict:
    return {
        "schema_version": 1,
        "contract_id": "external-intelligence-runtime-v1",
        "operation": "search",
        "runtime": "claude-code",
        "status": "continue",
        "warnings": [],
        "policy": {
            "search_limit_max": 5,
            "score_threshold": 1.0,
            "summary_max_bytes": 512,
            "search_results_max_bytes": 4096,
            "detail_max_bytes": 4096,
            "details_total_max_bytes": 16384,
        },
        "memory": {
            "scope": "project",
            "user_scope_used": False,
            "status": "available",
            "engine": "central:skill-governance-adapters/build-external-intelligence.py",
        },
        "token_telemetry": {
            "status": "unavailable",
            "estimated": False,
            "input_tokens": None,
            "reused_input_tokens": None,
        },
        "state": {
            "schema_version": 1,
            "contract_id": "external-intelligence-runtime-v1",
            "run_id": "claude-session-123",
            "project_root": str(project.resolve()),
            "query": "repair the retry timeout",
            "candidate_ids": ["ei-0123456789ab"],
            "selected_ids": [],
            "phase": "searched",
            "memory_status": "available",
        },
        "candidates": [
            {
                "id": "ei-0123456789ab",
                "status": "candidate",
                "title": "Bound retries",
                "summary": "Cap retry loops and preserve the terminal error.",
                "score": 4.0,
                "resolution_status": "active",
                "observation_count": 2,
                "context_count": 2,
                "evidence_count": 2,
                "helpful_reuse_count": 1,
            }
        ],
        "details": [],
        "reuses": [],
        "capture": None,
    }


def _hook_wiring(plugin_dir: Path) -> dict:
    """hook 配線を、plugin.json inline / 参照形 / 標準自動検出のどれでも読む。

    宣言の置き場が変わっても配線の実体は一つ。検査側が置き場を知らずに済むよう正規化する。
    manifest が hooks を書かない形は「宣言なし」ではなく、loader が hooks/hooks.json を
    自動検出して1回だけ配布する現行契約。
    """
    manifest = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    wiring = manifest.get("hooks")
    if wiring is None:
        document = json.loads((plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        wiring = document.get("hooks", document)
    if isinstance(wiring, str):
        external = json.loads((plugin_dir / wiring.lstrip("./")).read_text(encoding="utf-8"))
        wiring = external.get("hooks", external)
    return wiring


def test_hook_is_registered_on_confirmed_claude_user_prompt_surface() -> None:
    groups = _hook_wiring(RUNTIME_PLUGIN)["UserPromptSubmit"]
    commands = [hook["command"] for group in groups for hook in group["hooks"]]
    assert any("hooks/build-external-intelligence-context.py" in item for item in commands)


def test_hook_builds_canonical_project_scoped_bounded_search_request(tmp_path: Path) -> None:
    module = _load_hook()
    project = tmp_path / "project"
    project.mkdir()
    seen = {}

    def runner(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        request = json.loads(command[command.index("--request-json") + 1])
        assert request == {
            "schema_version": 1,
            "contract_id": "external-intelligence-runtime-v1",
            "operation": "search",
            "runtime": "claude-code",
            "run_id": "claude-session-123",
            "project_root": str(project.resolve()),
            "context_id": "user-prompt:session-123",
            "query": "repair the retry timeout",
            "limit": 5,
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(_search_output(project)), "")

    output = module.execute_hook(_payload(project), adapter_path=ADAPTER, runner=runner)

    assert output is not None
    assert set(output) == {"continue", "suppressOutput", "hookSpecificOutput"}
    assert output["continue"] is True
    assert output["suppressOutput"] is True
    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "UserPromptSubmit"
    assert set(specific) == {"hookEventName", "additionalContext"}
    assert seen["kwargs"]["timeout"] <= 8
    assert seen["kwargs"]["shell"] is False


def test_hook_injects_thin_candidates_and_short_adopt_finish_instructions(tmp_path: Path) -> None:
    module = _load_hook()
    project = tmp_path / "project"
    project.mkdir()

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, json.dumps(_search_output(project)), "")

    output = module.execute_hook(_payload(project), adapter_path=ADAPTER, runner=runner)
    context = output["hookSpecificOutput"]["additionalContext"]

    assert "ei-0123456789ab" in context
    assert "Bound retries" in context
    assert "operation=adopt" in context
    assert "operation=finish" in context
    assert "selected candidate IDs only" in context
    assert "at most one" in context
    assert "details" not in context
    assert "rule" not in context
    assert len(context.encode("utf-8")) <= module.ADDITIONAL_CONTEXT_MAX_BYTES


def test_hook_caps_prompt_and_candidate_context_bytes(tmp_path: Path) -> None:
    module = _load_hook()
    project = tmp_path / "project"
    project.mkdir()
    output_doc = _search_output(project)
    output_doc["candidates"] *= 20
    output_doc["state"]["candidate_ids"] = ["ei-0123456789ab"]

    def runner(command, **kwargs):
        request = json.loads(command[command.index("--request-json") + 1])
        assert len(request["query"].encode("utf-8")) <= module.QUERY_MAX_BYTES
        return subprocess.CompletedProcess(command, 0, json.dumps(output_doc), "")

    output = module.execute_hook(_payload(project, prompt="再" * 10_000), adapter_path=ADAPTER, runner=runner)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert len(context.encode("utf-8")) <= module.ADDITIONAL_CONTEXT_MAX_BYTES
    assert context.count("ei-0123456789ab") <= 3


def test_memory_unavailable_or_bad_hook_input_is_fail_soft_and_silent(tmp_path: Path) -> None:
    module = _load_hook()
    project = tmp_path / "project"
    project.mkdir()
    unavailable = _search_output(project)
    unavailable["memory"]["status"] = "unavailable"
    unavailable["state"]["memory_status"] = "unavailable"
    unavailable["warnings"] = [{"code": "memory_absent", "message": "not initialized"}]
    unavailable["candidates"] = []

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, json.dumps(unavailable), "")

    assert module.execute_hook(_payload(project), adapter_path=ADAPTER, runner=runner) is None
    assert module.execute_hook({}, adapter_path=ADAPTER, runner=runner) is None
    assert module.execute_hook({**_payload(project), "hook_event_name": "Stop"}, adapter_path=ADAPTER, runner=runner) is None


def test_actual_user_prompt_hook_calls_actual_adapter_and_emits_additional_context(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed" / "skill-governance-adapters"
    shutil.copytree(RUNTIME_PLUGIN, installed)
    installed_engine = (
        installed / "scripts/build-external-intelligence.py"
    )
    installed_hook = installed / "hooks/build-external-intelligence-context.py"
    project = tmp_path / "project"
    project.mkdir()
    captured = subprocess.run(
        [
            "python3",
            str(installed_engine),
            "--scope",
            "project",
            "--project-root",
            str(project),
            "--agent",
            "claude",
            "capture",
            "--title",
            "Retry timeout safety",
            "--summary",
            "Bound retry timeouts and keep the terminal error.",
            "--rule",
            "Bound retry timeouts and preserve the terminal error.",
            "--context-id",
            "fixture/retry",
            "--evidence-ref",
            "fixture:retry",
            "--evidence-source",
            "fixture:hook-e2e",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert captured.returncode == 0, captured.stderr

    hook = subprocess.run(
        ["python3", str(installed_hook)],
        input=json.dumps(_payload(project)),
        text=True,
        capture_output=True,
        check=False,
    )

    assert hook.returncode == 0, hook.stderr
    output = json.loads(hook.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "Retry timeout safety" in context
    assert "operation=adopt" in context
    assert len(context.encode("utf-8")) <= 8_192


def test_every_standard_bundle_includes_runtime_provider() -> None:
    bundles = json.loads((ROOT / ".claude-plugin" / "bundles.json").read_text())
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    known_plugins = {item["name"] for item in marketplace["plugins"]}
    assert bundles["bundles"]
    for bundle in bundles["bundles"]:
        assert "skill-governance-adapters" in bundle["plugins"], bundle["name"]
        assert set(bundle["plugins"]) <= known_plugins, bundle["name"]


def test_every_installable_plugin_declares_native_runtime_provider_dependency() -> None:
    provider = "skill-governance-adapters"
    manifests = sorted((ROOT / "plugins").glob("*/.claude-plugin/plugin.json"))
    assert manifests
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["name"] == provider:
            assert provider not in manifest.get("dependencies", [])
            continue
        assert provider in manifest.get("dependencies", []), manifest["name"]

    for marketplace_path in (
        ROOT / ".claude-plugin/marketplace.json",
        ROOT / "marketplaces/local/.claude-plugin/marketplace.json",
    ):
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        for entry in marketplace["plugins"]:
            if entry["name"] == provider:
                continue
            source = (marketplace_path.parent.parent / entry["source"]).resolve()
            manifest = json.loads(
                (source / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
            )
            assert provider in manifest.get("dependencies", []), (
                marketplace["name"],
                entry["name"],
            )


@pytest.mark.skipif(shutil.which("claude") is None, reason="Claude Code CLI unavailable")
def test_isolated_individual_install_resolves_and_activates_runtime_provider(
    tmp_path: Path,
) -> None:
    marketplace_root = tmp_path / "marketplace"
    plugin_root = marketplace_root / "plugins"
    plugin_root.mkdir(parents=True)
    for name in ("skill-intake", "skill-governance-adapters"):
        shutil.copytree(ROOT / "plugins" / name, plugin_root / name)
    (marketplace_root / ".claude-plugin").mkdir()
    (marketplace_root / ".claude-plugin/marketplace.json").write_text(
        json.dumps(
            {
                "name": "isolated-runtime",
                "owner": {"name": "test"},
                "plugins": [
                    {"name": name, "source": f"./plugins/{name}"}
                    for name in ("skill-intake", "skill-governance-adapters")
                ],
            }
        ),
        encoding="utf-8",
    )
    config_dir = tmp_path / "claude-config"
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(config_dir), DISABLE_AUTOUPDATER="1")

    added = subprocess.run(
        ["claude", "plugin", "marketplace", "add", str(marketplace_root)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert added.returncode == 0, added.stdout + added.stderr
    installed = subprocess.run(
        ["claude", "plugin", "install", "skill-intake@isolated-runtime", "--scope", "user"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    listed = subprocess.run(
        ["claude", "plugin", "list", "--json"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert listed.returncode == 0, listed.stdout + listed.stderr
    rows = json.loads(listed.stdout)
    by_name = {row["id"].split("@", 1)[0]: row for row in rows}
    assert by_name["skill-intake"]["enabled"] is True
    assert by_name["skill-governance-adapters"]["enabled"] is True

    provider_cache = next(
        (config_dir / "plugins/cache/isolated-runtime/skill-governance-adapters").glob("*/")
    )
    assert "UserPromptSubmit" in _hook_wiring(provider_cache)
    assert (provider_cache / "hooks/build-external-intelligence-context.py").is_file()
    assert (
        provider_cache / "scripts/build-external-intelligence.py"
    ).is_file()


def test_only_distributable_plugin_contains_long_runtime_implementations() -> None:
    schema = RUNTIME_PLUGIN / "schemas/external-intelligence-runtime.schema.json"
    contract = RUNTIME_PLUGIN / "references/external-intelligence-runtime-contract.md"
    thresholds = {
        "build-external-intelligence-context.py": 5_000,
        "build-external-intelligence-runtime.py": 20_000,
        "build-external-intelligence.py": 30_000,
        "external-intelligence-runtime.schema.json": 8_000,
        "external-intelligence-runtime-contract.md": 3_000,
    }
    expected = {HOOK, ADAPTER, ENGINE, schema, contract}
    long_assets = {
        path
        for plugin in (PLUGIN, RUNTIME_PLUGIN)
        for name, minimum in thresholds.items()
        for path in plugin.rglob(name)
        if path.stat().st_size >= minimum
    }
    assert long_assets == expected

    assert HC_ENGINE.stat().st_size < 3_000
    assert HC_ADAPTER.stat().st_size < 3_000
    assert "skill-governance-adapters" in HC_ENGINE.read_text(encoding="utf-8")
    assert "skill-governance-adapters" in HC_ADAPTER.read_text(encoding="utf-8")
    assert HC_CONTRACT.stat().st_size < 1_500
    assert "plugin:skill-governance-adapters" in HC_CONTRACT.read_text(encoding="utf-8")
    assert not (PLUGIN / "hooks/build-external-intelligence-context.py").exists()
    assert not (
        PLUGIN / "skills/run-build-skill/schemas/external-intelligence-runtime.schema.json"
    ).exists()


def test_distributed_plugin_release_content_includes_runtime_caller_and_engine() -> None:
    spec = importlib.util.spec_from_file_location(
        "build_plugin_release", ROOT / "scripts/build-plugin-release.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    content = {
        path.relative_to(RUNTIME_PLUGIN).as_posix()
        for path in module.content_paths(RUNTIME_PLUGIN)
    }
    assert {
        "hooks/build-external-intelligence-context.py",
        "scripts/build-external-intelligence-runtime.py",
        "scripts/build-external-intelligence.py",
        "schemas/external-intelligence-runtime.schema.json",
    } <= content

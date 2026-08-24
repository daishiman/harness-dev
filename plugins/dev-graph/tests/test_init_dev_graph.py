from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path, PureWindowsPath

from jsonschema import Draft202012Validator


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "skills" / "run-dev-graph-init" / "scripts" / "build-dev-graph.py"
CONFIG_SCHEMA = PLUGIN / "schemas" / "repo-config.schema.json"
CONFIG_TEMPLATE = PLUGIN / "templates" / "repo-config.example.json"


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True)


def repository(tmp_path: Path) -> Path:
    root = tmp_path / "fixture"
    root.mkdir(parents=True)
    git("init", "-q", cwd=root)
    git("config", "user.email", "test@example.com", cwd=root)
    git("config", "user.name", "Test", cwd=root)
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    git("add", "README.md", cwd=root)
    git("commit", "-qm", "init", cwd=root)
    return root


def absolute_strings(value: object) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in absolute_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in absolute_strings(child)]
    if isinstance(value, str) and (Path(value).is_absolute() or PureWindowsPath(value).is_absolute()):
        return [value]
    return []


def invoke(
    root: Path,
    *extra: str,
    hook_source: str = "plugin",
    env_override: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if env_override:
        env.update(env_override)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(root), "--hook-source", hook_source, *extra],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def preview_config(root: Path) -> dict[str, object]:
    result = invoke(root, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["config_result"]["effective_config"]


def write_config(root: Path, config: dict[str, object]) -> None:
    path = root / ".dev-graph/config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_repo_config_template_conforms_to_the_canonical_schema() -> None:
    schema = json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8"))
    template = json.loads(CONFIG_TEMPLATE.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(template)) == []


def test_initializer_proves_full_readiness_and_second_run_is_zero_change(tmp_path: Path) -> None:
    root = repository(tmp_path)
    first = invoke(root)
    assert first.returncode == 0, first.stdout + first.stderr
    first_report = json.loads(first.stdout)
    assert first_report["owner"] == "C01/run-dev-graph-init"
    assert first_report["readiness"]["repo_config"]["valid"] is True
    assert first_report["readiness"]["graph"]["valid"] is True
    assert first_report["readiness"]["templates"] == {"valid": True, "missing": [], "count": 21}
    assert first_report["readiness"]["goal_seek"]["valid"] is True

    config = json.loads((root / ".dev-graph/config.json").read_text(encoding="utf-8"))
    schema = json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(config)) == []
    assert config["github"]["enabled"] is False
    assert config["content_roots"]["features"] == "features"
    assert all(not Path(value).is_absolute() for value in config["content_roots"].values())
    assert all(not Path(value).is_absolute() for value in config["local_state"].values())
    assert all((root / name).is_dir() for name in ("issues", "tasks", "specs", "architecture", "features", "docs", "system-spec"))

    receipt = json.loads((root / ".dev-graph/state/init-receipt.json").read_text(encoding="utf-8"))
    assert receipt["schema_result"]["graph"]["schema"] == "schemas/graph-node.schema.json"
    assert absolute_strings(receipt) == []

    goal = json.loads((root / "eval-log/run-dev-graph-init-goal-spec.json").read_text(encoding="utf-8"))
    progress = json.loads((root / "eval-log/run-dev-graph-init-progress.json").read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(goal["original_goal"].encode("utf-8")).hexdigest()
    assert progress["original_goal_hash"] == expected_hash
    assert (root / "eval-log/run-dev-graph-init-intermediate.jsonl").is_file()

    user_template = root / ".dev-graph/templates/task.md"
    user_template.write_text(user_template.read_text(encoding="utf-8") + "\nuser edit\n", encoding="utf-8")
    edited = user_template.read_bytes()
    intermediate_path = root / "eval-log/run-dev-graph-init-intermediate.jsonl"
    row = json.loads(intermediate_path.read_text(encoding="utf-8").splitlines()[0])
    row["merged_directive_for_next"] = "independent follow-up remains anchored"
    with intermediate_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    second = invoke(root)
    assert second.returncode == 0, second.stdout + second.stderr
    second_report = json.loads(second.stdout)
    assert second_report["planned_changes"] == []
    assert second_report["write_count"] == 0
    assert second_report["idempotent"] is True
    assert second_report["readiness"]["goal_seek"]["iterations"] == 2
    assert ".dev-graph/templates/task.md" in second_report["migration_preview"]
    assert user_template.read_bytes() == edited


def test_initializer_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = repository(tmp_path)
    before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    result = invoke(root, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "preview"
    assert report["write_count"] == 0
    assert ".dev-graph/config.json" in report["planned_changes"]
    assert report["config_result"]["source"] == "generated-default"
    assert report["policy_preview"]["routing"]["content_roots"] == report["config_result"]["effective_config"]["content_roots"]
    assert report["policy_preview"]["github"]["enabled"] is False
    assert report["policy_preview"]["worktrees"]["dirty_worktree_policy"] == "fail_closed"
    assert report["readiness_plan"]["repo_config"]["status"] == "validated"
    assert report["readiness_plan"]["graph"]["status"] == "validate-after-apply"
    assert "predicted_readiness" not in report
    assert sorted(path.relative_to(root).as_posix() for path in root.rglob("*")) == before


def test_existing_config_is_the_single_source_for_custom_roots_graph_receipt_and_readiness(tmp_path: Path) -> None:
    root = repository(tmp_path)
    config = preview_config(root)
    config["content_roots"]["specifications"] = "product/specifications"
    config["content_roots"]["documents"] = "knowledge/documents"
    config["local_state"] = {
        "graph": "runtime/state/custom-graph.json",
        "cache": "runtime/cache",
        "locks": "runtime/locks",
    }
    write_config(root, config)

    preview = invoke(root, "--dry-run")
    assert preview.returncode == 0, preview.stdout + preview.stderr
    preview_report = json.loads(preview.stdout)
    assert preview_report["config_result"]["source"] == "repository"
    assert preview_report["config_result"]["effective_config"] == config
    assert "product/specifications" in preview_report["planned_changes"]
    assert "runtime/state/custom-graph.json" in preview_report["planned_changes"]
    assert "runtime/state/init-receipt.json" in preview_report["planned_changes"]
    assert not (root / "product").exists()
    assert not (root / "runtime").exists()

    applied = invoke(root)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    report = json.loads(applied.stdout)
    assert report["readiness"]["graph"]["valid"] is True
    assert (root / "product/specifications").is_dir()
    assert (root / "knowledge/documents").is_dir()
    assert (root / "runtime/state/custom-graph.json").is_file()
    assert (root / "runtime/cache").is_dir()
    assert (root / "runtime/locks").is_dir()
    assert not (root / ".dev-graph/state/graph.json").exists()
    receipt_path = root / "runtime/state/init-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["content_roots"] == config["content_roots"]
    assert receipt["local_state"] == config["local_state"]
    assert receipt["config_result"]["effective_config"] == config
    assert receipt["schema_result"]["graph"]["valid"] is True
    assert absolute_strings(receipt) == []

    repeated = invoke(root)
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    repeated_report = json.loads(repeated.stdout)
    assert repeated_report["planned_changes"] == []
    assert repeated_report["write_count"] == 0
    assert repeated_report["idempotent"] is True


def test_two_repositories_share_the_initializer_but_not_config_content_or_state(tmp_path: Path) -> None:
    roots = [repository(tmp_path / name) for name in ("repo-a", "repo-b")]
    receipts: list[dict[str, object]] = []
    for label, root in zip(("a", "b"), roots, strict=True):
        config = preview_config(root)
        config["content_roots"]["documents"] = f"knowledge-{label}"
        config["local_state"] = {
            "graph": f"state-{label}/graph.json",
            "cache": f"cache-{label}",
            "locks": f"locks-{label}",
        }
        write_config(root, config)
        result = invoke(root)
        assert result.returncode == 0, result.stdout + result.stderr
        receipt = json.loads((root / f"state-{label}/init-receipt.json").read_text(encoding="utf-8"))
        assert receipt["content_roots"]["documents"] == f"knowledge-{label}"
        assert receipt["local_state"]["graph"] == f"state-{label}/graph.json"
        assert absolute_strings(receipt) == []
        receipts.append(receipt)

    assert (roots[0] / "knowledge-a").is_dir() and not (roots[0] / "knowledge-b").exists()
    assert (roots[1] / "knowledge-b").is_dir() and not (roots[1] / "knowledge-a").exists()
    assert not (roots[0] / "state-b").exists()
    assert not (roots[1] / "state-a").exists()
    assert receipts[0]["repository_id"] != receipts[1]["repository_id"]


def test_existing_config_unsafe_or_ambiguous_paths_fail_before_initializer_writes(tmp_path: Path) -> None:
    escaped = repository(tmp_path / "escaped")
    escaped_config = preview_config(escaped)
    outside = tmp_path / "outside-documents"
    outside.mkdir()
    (escaped / "linked-documents").symlink_to(outside, target_is_directory=True)
    escaped_config["content_roots"]["documents"] = "linked-documents"
    write_config(escaped, escaped_config)
    before_outside = sorted(path.relative_to(outside).as_posix() for path in outside.rglob("*"))

    rejected = invoke(escaped)
    assert rejected.returncode == 2
    assert "C24" in rejected.stdout and "escapes authority root" in rejected.stdout
    assert not (escaped / "issues").exists()
    assert not (escaped / ".dev-graph/state").exists()
    assert sorted(path.relative_to(outside).as_posix() for path in outside.rglob("*")) == before_outside

    ambiguous = repository(tmp_path / "ambiguous")
    ambiguous_config = preview_config(ambiguous)
    ambiguous_config["content_roots"]["documents"] = ambiguous_config["content_roots"]["specifications"]
    write_config(ambiguous, ambiguous_config)
    duplicated = invoke(ambiguous)
    assert duplicated.returncode == 2
    assert "content_roots must resolve to distinct" in duplicated.stdout
    assert not (ambiguous / "issues").exists()
    assert not (ambiguous / ".dev-graph/state").exists()


def test_initializer_fails_closed_on_existing_invalid_config(tmp_path: Path) -> None:
    root = repository(tmp_path)
    (root / ".dev-graph").mkdir()
    (root / ".dev-graph/config.json").write_text("{}\n", encoding="utf-8")
    before = (root / ".dev-graph/config.json").read_bytes()
    result = invoke(root)
    assert result.returncode == 2
    assert "existing repo config violates canonical schema" in result.stdout
    assert (root / ".dev-graph/config.json").read_bytes() == before
    assert not (root / ".dev-graph/state/init-receipt.json").exists()


def test_initializer_rejects_legacy_receipt_with_absolute_stored_path(tmp_path: Path) -> None:
    root = repository(tmp_path)
    first = invoke(root)
    assert first.returncode == 0, first.stdout + first.stderr
    receipt_path = root / ".dev-graph/state/init-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["schema_result"]["graph"]["schema"] = "/old/plugin/dev-graph/schemas/graph-node.schema.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    immutable = receipt_path.read_bytes()

    repeated = invoke(root)
    assert repeated.returncode == 2
    error = json.loads(repeated.stdout)
    assert "existing init receipt contains absolute stored paths" in error["error"]
    assert "$.schema_result.graph.schema" in error["error"]
    assert receipt_path.read_bytes() == immutable


def test_initializer_fails_closed_when_host_project_root_differs(tmp_path: Path) -> None:
    selected = repository(tmp_path / "selected")
    host = repository(tmp_path / "host")
    result = invoke(selected, "--dry-run", env_override={"CLAUDE_PROJECT_DIR": str(host)})
    assert result.returncode == 2
    assert "C24" in result.stdout and "CLAUDE_PROJECT_DIR" in result.stdout
    assert not (selected / ".dev-graph").exists()


def test_project_fallback_deep_merges_idempotently_and_rolls_back(tmp_path: Path) -> None:
    root = repository(tmp_path)
    settings_path = root / ".claude/settings.json"
    settings_path.parent.mkdir()
    original = {
        "theme": "dark",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Read", "hooks": [{"type": "command", "command": "python3 existing.py"}]}
            ]
        },
    }
    settings_path.write_text(json.dumps(original, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    before = settings_path.read_bytes()

    preview = invoke(root, "--dry-run", hook_source="project-fallback")
    assert preview.returncode == 0, preview.stdout + preview.stderr
    preview_report = json.loads(preview.stdout)
    assert preview_report["hook_preview"]["added_hook_count"] == 4
    assert preview_report["hook_preview"]["existing_value_digest_changes"] == 0
    assert settings_path.read_bytes() == before
    assert not (root / ".claude/dev-graph-plugin").exists()

    applied = invoke(root, hook_source="project-fallback")
    assert applied.returncode == 0, applied.stdout + applied.stderr
    report = json.loads(applied.stdout)
    assert report["readiness"]["claude_hooks"]["valid"] is True
    assert report["readiness"]["claude_hooks"]["duplicate_count"] == 0
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["theme"] == original["theme"]
    assert settings["hooks"]["PreToolUse"][0] == original["hooks"]["PreToolUse"][0]
    assert set(settings["hooks"]) == {"SessionStart", "PreToolUse", "PostToolUse", "TaskCompleted"}
    link = root / ".claude/dev-graph-plugin"
    assert link.is_symlink()
    assert not Path(os.readlink(link)).is_absolute()
    assert link.resolve(strict=True) == PLUGIN.resolve(strict=True)
    manifest = root / ".dev-graph/state/project-hook-rollback.json"
    assert manifest.is_file()
    config = json.loads((root / ".dev-graph/config.json").read_text(encoding="utf-8"))
    assert config["claude_hooks"]["source"] == "project"

    second = invoke(root, hook_source="project-fallback")
    assert second.returncode == 0, second.stdout + second.stderr
    second_report = json.loads(second.stdout)
    assert second_report["planned_changes"] == []
    assert second_report["write_count"] == 0
    assert second_report["idempotent"] is True

    rollback_preview = invoke(
        root, "--rollback-project-hooks", "--dry-run", hook_source="project-fallback",
    )
    assert rollback_preview.returncode == 0, rollback_preview.stdout + rollback_preview.stderr
    assert settings != original
    rollback = invoke(root, "--rollback-project-hooks", hook_source="project-fallback")
    assert rollback.returncode == 0, rollback.stdout + rollback.stderr
    assert json.loads(settings_path.read_text(encoding="utf-8")) == original
    assert not link.exists()
    assert not manifest.exists()


def test_project_fallback_rejects_effective_plugin_and_disabled_policy(tmp_path: Path) -> None:
    plugin_root = repository(tmp_path / "plugin-active")
    plugin_active = invoke(
        plugin_root,
        "--dry-run",
        hook_source="project-fallback",
        env_override={"CLAUDE_PLUGIN_ROOT": str(PLUGIN)},
    )
    assert plugin_active.returncode == 2
    assert "effective plugin hook detected" in plugin_active.stdout
    assert not (plugin_root / ".dev-graph").exists()

    disabled_root = repository(tmp_path / "disabled")
    local_settings = disabled_root / ".claude/settings.local.json"
    local_settings.parent.mkdir()
    local_settings.write_text('{"disableAllHooks": true}\n', encoding="utf-8")
    disabled = invoke(disabled_root, "--dry-run", hook_source="project-fallback")
    assert disabled.returncode == 2
    assert "disableAllHooks" in disabled.stdout
    assert not (disabled_root / ".dev-graph").exists()

    managed_root = repository(tmp_path / "managed")
    managed_settings = managed_root / ".claude/settings.json"
    managed_settings.parent.mkdir()
    managed_settings.write_text('{"allowManagedHooksOnly": true}\n', encoding="utf-8")
    managed = invoke(managed_root, "--dry-run", hook_source="project-fallback")
    assert managed.returncode == 2
    assert "allowManagedHooksOnly" in managed.stdout
    assert not (managed_root / ".dev-graph").exists()


def test_initializer_records_redacted_gh_cli_auth_state(tmp_path: Path) -> None:
    root = repository(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gh = fake_bin / "gh"
    fake_gh.write_text("#!/bin/sh\necho 'secret account and token' >&2\nexit 0\n", encoding="utf-8")
    fake_gh.chmod(0o755)
    result = invoke(root, env_override={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"})
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["gh_cli_auth"] == {
        "available": True,
        "authenticated": True,
        "status": "authenticated",
        "exit_code": 0,
    }
    assert "secret account" not in result.stdout
    receipt = json.loads((root / ".dev-graph/state/init-receipt.json").read_text(encoding="utf-8"))
    assert receipt["gh_cli_auth"] == report["gh_cli_auth"]

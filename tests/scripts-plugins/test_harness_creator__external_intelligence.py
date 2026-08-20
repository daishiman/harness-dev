"""harness-creator external intelligence store の利用者向け契約テスト。

プラグイン本体を runtime state で汚さず、Codex / Claude Code の観測を
同一ストアへ蓄積する。同一・類似知見は別 entry にせず観測へ集約し、
複数の独立証拠 + 別文脈での helpful reuse + owner approval なしでは昇格させない。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "harness-creator"
ENGINE = PLUGIN / "skills" / "run-build-skill" / "scripts" / "build-external-intelligence.py"
ADAPTER = PLUGIN / "skills" / "run-build-skill" / "scripts" / "auto-record-lesson.py"


def run_engine(state: Path, *args: str, env: dict[str, str] | None = None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(ENGINE), "--state-dir", str(state), *args],
        text=True,
        capture_output=True,
        env=merged_env,
        check=False,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc, payload


def capture(
    state: Path,
    *,
    agent: str,
    context: str,
    evidence: str,
    evidence_source: str | None = None,
    title: str = "Runtime state belongs outside plugin cache",
    summary: str = "Installed plugin copies can be replaced during upgrades.",
    rule: str = "Store runtime knowledge outside the installed plugin cache directory.",
):
    return run_engine(
        state,
        "--agent",
        agent,
        "capture",
        "--title",
        title,
        "--summary",
        summary,
        "--rule",
        rule,
        "--context-id",
        context,
        "--evidence-ref",
        evidence,
        "--evidence-source",
        evidence_source or evidence,
        "--tags",
        "plugin,state,portability",
    )


def test_codex_and_claude_share_one_entry_and_duplicate_observation_is_noop(tmp_path):
    state = tmp_path / "state"
    first, created = capture(
        state, agent="codex", context="repo-a/task-1", evidence="issue:a#1"
    )
    assert first.returncode == 0
    assert created["action"] == "created"
    entry_id = created["entry"]["id"]

    duplicate, unchanged = capture(
        state,
        agent="claude",
        context="repo-a/task-1",
        evidence="issue:a#1",
        title="Runtime  state belongs outside plugin cache!",
        rule="Store runtime knowledge outside the installed plugin cache directory!",
    )
    assert duplicate.returncode == 0
    assert unchanged["action"] == "duplicate_observation"
    assert unchanged["entry"]["id"] == entry_id
    assert unchanged["entry"]["observation_count"] == 1

    second, merged = capture(
        state,
        agent="claude",
        context="repo-b/task-8",
        evidence="pr:b#8",
        title="Runtime state belongs outside plugin caches",
        rule="Store runtime knowledge outside installed plugin cache directories.",
    )
    assert second.returncode == 0
    assert merged["action"] == "merged"
    assert merged["entry"]["id"] == entry_id
    assert merged["entry"]["status"] == "candidate"
    assert merged["entry"]["observation_count"] == 2
    assert merged["entry"]["context_count"] == 2
    assert merged["entry"]["evidence_count"] == 2
    assert {item["agent"] for item in merged["entry"]["observations"]} == {
        "codex",
        "claude",
    }


def test_ambiguous_similarity_requires_explicit_resolution(tmp_path):
    state = tmp_path / "state"
    _, created = capture(
        state,
        agent="codex",
        context="repo-a/a",
        evidence="case:a",
        title="Keep runtime state outside plugin cache",
        rule="Persist learned rules outside installed plugin files.",
    )

    possible, payload = capture(
        state,
        agent="claude",
        context="repo-b/b",
        evidence="case:b",
        title="Keep learned state away from plugin cache",
        rule="Do not persist runtime rules inside installed plugin files.",
    )
    assert possible.returncode == 3
    assert payload["status"] == "possible_duplicate"
    assert payload["candidates"][0]["id"] == created["entry"]["id"]

    resolved, merged = run_engine(
        state,
        "--agent",
        "claude",
        "capture",
        "--title",
        "Keep learned state away from plugin cache",
        "--summary",
        "Plugin upgrades replace package files.",
        "--rule",
        "Do not persist runtime rules inside installed plugin files.",
        "--context-id",
        "repo-b/b",
        "--evidence-ref",
        "case:b",
        "--evidence-source",
        "case:b",
        "--merge-with",
        created["entry"]["id"],
    )
    assert resolved.returncode == 0
    assert merged["action"] == "merged"
    assert merged["entry"]["id"] == created["entry"]["id"]


def test_promotion_requires_independent_observations_helpful_reuse_and_approval(tmp_path):
    state = tmp_path / "state"
    _, first = capture(state, agent="codex", context="repo-a/a", evidence="case:a")
    entry_id = first["entry"]["id"]

    early, blocked = run_engine(
        state,
        "promote",
        "--id",
        entry_id,
        "--target",
        "AGENTS.md",
        "--owner-approved",
        "--approved-by",
        "test-owner",
        "--approval-evidence-ref",
        "approval:test",
        "--falsifier",
        "The plugin data directory is guaranteed version-stable.",
        "--rollback",
        "Demote to candidate and remove the projected rule.",
    )
    assert early.returncode == 1
    assert blocked["status"] == "blocked"
    assert "status verified" in blocked["reason"]

    capture(state, agent="claude", context="repo-b/b", evidence="case:b")
    not_reused, blocked = run_engine(
        state,
        "promote",
        "--id",
        entry_id,
        "--target",
        "AGENTS.md",
        "--owner-approved",
        "--approved-by",
        "test-owner",
        "--approval-evidence-ref",
        "approval:test",
        "--falsifier",
        "The plugin data directory is guaranteed version-stable.",
        "--rollback",
        "Demote to candidate and remove the projected rule.",
    )
    assert not_reused.returncode == 1
    assert "status verified" in blocked["reason"]

    reused, verified = run_engine(
        state,
        "--agent",
        "codex",
        "reuse",
        "--id",
        entry_id,
        "--context-id",
        "repo-c/c",
        "--evidence-ref",
        "test:c",
        "--evidence-source",
        "test:c",
        "--outcome",
        "helpful",
    )
    assert reused.returncode == 0
    assert verified["entry"]["status"] == "verified"

    unproven_proc, unproven = run_engine(
        state,
        "promote",
        "--id",
        entry_id,
        "--target",
        "AGENTS.md",
        "--owner-approved",
        "--falsifier",
        "The plugin data directory is guaranteed version-stable.",
        "--rollback",
        "Demote to candidate and remove the projected rule.",
    )
    assert unproven_proc.returncode == 1
    assert "approved-by" in unproven["error"]

    promoted_proc, promoted = run_engine(
        state,
        "promote",
        "--id",
        entry_id,
        "--target",
        "AGENTS.md",
        "--owner-approved",
        "--approved-by",
        "test-owner",
        "--approval-evidence-ref",
        "approval:test",
        "--falsifier",
        "The plugin data directory is guaranteed version-stable.",
        "--rollback",
        "Demote to candidate and remove the projected rule.",
    )
    assert promoted_proc.returncode == 0
    assert promoted["entry"]["status"] == "promoted"
    assert promoted["entry"]["promotion"]["owner_approved"] is True
    assert promoted["entry"]["promotion"]["approved_by"] == "test-owner"
    original_promotion = promoted["entry"]["promotion"]

    repeated_proc, repeated = run_engine(
        state,
        "promote",
        "--id",
        entry_id,
        "--target",
        "different-target",
        "--owner-approved",
        "--approved-by",
        "different-owner",
        "--approval-evidence-ref",
        "approval:different",
        "--falsifier",
        "different falsifier",
        "--rollback",
        "different rollback",
    )
    assert repeated_proc.returncode == 0
    assert repeated["action"] == "already_promoted"
    assert repeated["entry"]["promotion"] == original_promotion


def test_project_scope_uses_git_common_dir_not_plugin_install(tmp_path):
    repo = tmp_path / "consumer"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    fake_plugin = repo / "plugin-cache" / "harness-creator"
    fake_plugin.mkdir(parents=True)

    proc = subprocess.run(
        [
            sys.executable,
            str(ENGINE),
            "--project-root",
            str(repo),
            "init",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert Path(payload["state_dir"]) == (
        repo / ".git" / "harness-creator" / "external-intelligence" / "v1"
    )
    assert not list(fake_plugin.rglob("events.jsonl"))


def test_user_scope_prefers_explicit_plugin_data_override(tmp_path):
    state = tmp_path / "plugin-data" / "external-intelligence" / "v1"
    env = os.environ.copy()
    env["HARNESS_INTELLIGENCE_HOME"] = str(state)
    proc = subprocess.run(
        [sys.executable, str(ENGINE), "--scope", "user", "init"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert Path(payload["state_dir"]) == state
    assert (state / "index.json").is_file()


def test_search_is_selective_and_event_chain_tampering_fails_closed(tmp_path):
    state = tmp_path / "state"
    _, created = capture(state, agent="codex", context="repo-a/a", evidence="case:a")
    capture(
        state,
        agent="claude",
        context="repo-z/z",
        evidence="case:z",
        title="Prefer stable prompt prefixes",
        summary="Stable instructions preserve prompt cache eligibility.",
        rule="Place stable instructions before variable task content.",
    )
    searched, result = run_engine(state, "search", "--query", "plugin cache runtime", "--limit", "1")
    assert searched.returncode == 0
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == created["entry"]["id"]
    assert "observations" not in result["results"][0]

    events = state / "events.jsonl"
    lines = events.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["entry"]["title"] = "tampered"
    lines[0] = json.dumps(first, ensure_ascii=False, sort_keys=True)
    events.write_text("\n".join(lines) + "\n", encoding="utf-8")

    verified, payload = run_engine(state, "verify")
    assert verified.returncode == 1
    assert payload["status"] == "corrupt"
    assert "hash" in payload["error"].lower()


def test_hook_adapter_records_same_failure_from_codex_and_claude_without_package_writes(tmp_path):
    state = tmp_path / "runtime-state"
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "session-a",
        "turn_id": "turn-a",
        "tool_use_id": "tool-a",
        "cwd": str(tmp_path),
        "tool_name": "Skill",
        "tool_input": {"skill": "run-build-skill"},
        "tool_response": {"content": "ERROR validator failed for generated capability"},
    }

    def invoke(agent: str, body: dict):
        env = os.environ.copy()
        env["HARNESS_INTELLIGENCE_HOME"] = str(state)
        env["HARNESS_AGENT"] = agent
        return subprocess.run(
            [sys.executable, str(ADAPTER)],
            input=json.dumps(body),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    first = invoke("codex", payload)
    duplicate = invoke("claude", payload)
    assert first.returncode == duplicate.returncode == 0

    second_payload = dict(payload)
    second_payload.update(session_id="session-b", turn_id="turn-b", tool_use_id="tool-b")
    second = invoke("claude", second_payload)
    assert second.returncode == 0

    searched, result = run_engine(state, "search", "--query", "validator failure")
    assert searched.returncode == 0
    assert len(result["results"]) == 1
    entry_id = result["results"][0]["id"]
    shown, detail = run_engine(state, "show", "--id", entry_id)
    assert shown.returncode == 0
    assert detail["entry"]["observation_count"] == 2
    assert {item["agent"] for item in detail["entry"]["observations"]} == {
        "codex",
        "claude",
    }
    assert not list(PLUGIN.rglob("runtime-state"))


def test_materialized_drift_can_be_repaired_but_chain_remains_authoritative(tmp_path):
    state = tmp_path / "state"
    capture(state, agent="codex", context="repo-a/a", evidence="case:a")
    (state / "index.json").write_text("{}\n", encoding="utf-8")

    drifted, drift = run_engine(state, "verify")
    assert drifted.returncode == 1
    assert drift["status"] == "drift"
    assert drift["drift"] == ["index.json"]

    repaired, result = run_engine(state, "verify", "--repair")
    assert repaired.returncode == 0
    assert result["status"] == "repaired"

    verified, result = run_engine(state, "verify")
    assert verified.returncode == 0
    assert result["status"] == "ok"
    assert result["event_count"] == 1


def test_force_new_requires_reason_and_records_explicit_distinction(tmp_path):
    state = tmp_path / "state"
    capture(
        state,
        agent="codex",
        context="repo-a/a",
        evidence="case:a",
        title="Keep runtime state outside plugin cache",
        rule="Persist learned rules outside installed plugin files.",
    )
    base = [
        "--agent",
        "claude",
        "capture",
        "--title",
        "Keep learned state away from plugin cache",
        "--summary",
        "User-scoped state has a different retention boundary.",
        "--rule",
        "Do not persist runtime rules inside installed plugin files.",
        "--context-id",
        "repo-b/b",
        "--evidence-ref",
        "case:b",
        "--evidence-source",
        "case:b",
        "--force-new",
    ]

    rejected, error = run_engine(state, *base)
    assert rejected.returncode == 1
    assert "distinct-reason" in error["error"]

    created, result = run_engine(
        state,
        *base,
        "--distinct-reason",
        "This entry is user-scoped while the prior entry is project-scoped.",
    )
    assert created.returncode == 0
    assert result["action"] == "created"
    assert "user-scoped" in result["entry"]["distinct_reason"]


def test_missing_ids_duplicate_reuse_and_limit_validation_fail_predictably(tmp_path):
    state = tmp_path / "state"
    _, created = capture(state, agent="codex", context="repo-a/a", evidence="case:a")
    entry_id = created["entry"]["id"]

    missing, result = run_engine(state, "show", "--id", "ei-aaaaaaaaaaaa")
    assert missing.returncode == 1
    assert result["status"] == "not_found"
    missing_suffix, result = run_engine(state, "show", "--id", "ei-aaaaaaaaaaaa-10")
    assert missing_suffix.returncode == 1
    assert result["status"] == "not_found"

    bad_limit, result = run_engine(state, "search", "--query", "runtime", "--limit", "0")
    assert bad_limit.returncode == 1
    assert "limit" in result["error"]

    missing_reuse, result = run_engine(
        state,
        "reuse",
        "--id",
        "ei-aaaaaaaaaaaa",
        "--context-id",
        "repo-b/b",
        "--evidence-ref",
        "case:b",
        "--evidence-source",
        "case:b",
        "--outcome",
        "neutral",
    )
    assert missing_reuse.returncode == 1
    assert "not found" in result["error"]

    first, result = run_engine(
        state,
        "reuse",
        "--id",
        entry_id,
        "--context-id",
        "repo-b/b",
        "--evidence-ref",
        "case:b",
        "--evidence-source",
        "case:b",
        "--outcome",
        "neutral",
    )
    assert first.returncode == 0
    duplicate, result = run_engine(
        state,
        "reuse",
        "--id",
        entry_id,
        "--context-id",
        "repo-b/b",
        "--evidence-ref",
        "case:b",
        "--evidence-source",
        "case:b",
        "--outcome",
        "helpful",
    )
    assert duplicate.returncode == 0
    assert result["action"] == "duplicate_reuse"
    assert result["entry"]["helpful_reuse_count"] == 0


def test_non_git_and_user_plugin_data_resolution_are_package_external(tmp_path):
    project = tmp_path / "plain-project"
    project.mkdir()
    env = os.environ.copy()
    env.pop("HARNESS_INTELLIGENCE_HOME", None)
    project_proc = subprocess.run(
        [sys.executable, str(ENGINE), "--project-root", str(project), "init"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    project_result = json.loads(project_proc.stdout)
    assert project_proc.returncode == 0
    assert Path(project_result["state_dir"]) == (
        project / ".harness" / "external-intelligence" / "v1"
    )

    plugin_data = tmp_path / "writable-plugin-data"
    env["PLUGIN_DATA"] = str(plugin_data)
    user_proc = subprocess.run(
        [sys.executable, str(ENGINE), "--scope", "user", "init"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    user_result = json.loads(user_proc.stdout)
    assert user_proc.returncode == 0
    assert Path(user_result["state_dir"]) == plugin_data / "external-intelligence" / "v1"


def test_superseded_entry_is_audited_and_removed_from_search(tmp_path):
    state = tmp_path / "state"
    _, created = capture(state, agent="codex", context="test-run", evidence="fixture:1")
    entry_id = created["entry"]["id"]

    superseded, result = run_engine(
        state,
        "--agent",
        "codex",
        "supersede",
        "--id",
        entry_id,
        "--reason",
        "Synthetic test observation, not production evidence.",
    )
    assert superseded.returncode == 0
    assert result["entry"]["status"] == "superseded"

    repeated, result = run_engine(
        state,
        "supersede",
        "--id",
        entry_id,
        "--reason",
        "Repeated cleanup is idempotent.",
    )
    assert repeated.returncode == 0
    assert result["action"] == "already_superseded"

    searched, result = run_engine(state, "search", "--query", "runtime plugin cache")
    assert searched.returncode == 0
    assert result["results"] == []
    events = (state / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(events[-1])["kind"] == "SUPERSEDED"


def test_evidence_independence_uses_stable_sources_not_volatile_refs(tmp_path):
    state = tmp_path / "state"
    _, created = capture(
        state,
        agent="codex",
        context="repo-a/a",
        evidence="run:1",
        evidence_source="ci:same-check",
    )
    entry_id = created["entry"]["id"]
    _, same_source = capture(
        state,
        agent="claude",
        context="repo-b/b",
        evidence="run:2",
        evidence_source="ci:same-check",
    )
    assert same_source["entry"]["context_count"] == 2
    assert same_source["entry"]["evidence_count"] == 1
    assert same_source["entry"]["status"] == "observation"

    _, candidate = capture(
        state,
        agent="claude",
        context="repo-c/c",
        evidence="review:1",
        evidence_source="review:maintainer",
    )
    assert candidate["entry"]["status"] == "candidate"

    _, still_candidate = run_engine(
        state,
        "reuse",
        "--id",
        entry_id,
        "--context-id",
        "repo-d/d",
        "--evidence-ref",
        "review:2",
        "--evidence-source",
        "review:maintainer",
        "--outcome",
        "helpful",
    )
    assert still_candidate["entry"]["status"] == "candidate"

    _, verified = run_engine(
        state,
        "reuse",
        "--id",
        entry_id,
        "--context-id",
        "repo-e/e",
        "--evidence-ref",
        "prod:1",
        "--evidence-source",
        "production:independent",
        "--outcome",
        "helpful",
    )
    assert verified["entry"]["status"] == "verified"


def test_ambiguous_automated_capture_is_durably_quarantined(tmp_path):
    state = tmp_path / "state"
    _, original = capture(
        state,
        agent="codex",
        context="repo-a/a",
        evidence="case:a",
        title="Keep runtime state outside plugin cache",
        rule="Persist learned rules outside installed plugin files.",
    )
    proc, quarantined = run_engine(
        state,
        "--agent",
        "claude",
        "capture",
        "--title",
        "Keep learned state away from plugin cache",
        "--summary",
        "Plugin upgrades replace package files.",
        "--rule",
        "Do not persist runtime rules inside installed plugin files.",
        "--context-id",
        "repo-b/b",
        "--evidence-ref",
        "case:b",
        "--evidence-source",
        "hook-failure:skill:abc123",
        "--ambiguous-action",
        "quarantine",
    )
    assert proc.returncode == 0
    assert quarantined["action"] == "created"
    assert quarantined["entry"]["status"] == "observation"
    assert quarantined["entry"]["resolution_status"] == "pending_duplicate"
    assert quarantined["entry"]["duplicate_candidates"][0]["id"] == original["entry"]["id"]
    assert len(quarantined["entry"]["duplicate_candidates"]) <= 3

    quarantined_id = quarantined["entry"]["id"]
    _, reuse = run_engine(
        state,
        "reuse",
        "--id",
        quarantined_id,
        "--context-id",
        "repo-c/c",
        "--evidence-ref",
        "case:c",
        "--evidence-source",
        "independent:prod",
        "--outcome",
        "helpful",
    )
    assert reuse["entry"]["status"] == "observation"
    searched, result = run_engine(state, "search", "--query", "learned state plugin cache")
    assert searched.returncode == 0
    pending = next(item for item in result["results"] if item["id"] == quarantined_id)
    assert pending["resolution_status"] == "pending_duplicate"


def test_entry_ids_are_validated_and_superseded_is_terminal(tmp_path):
    state = tmp_path / "state"
    _, created = capture(state, agent="codex", context="repo-a/a", evidence="case:a")
    entry_id = created["entry"]["id"]
    run_engine(state, "supersede", "--id", entry_id, "--reason", "obsolete")

    merged, error = run_engine(
        state,
        "capture",
        "--title",
        "Replacement",
        "--summary",
        "Replacement summary",
        "--rule",
        "Replacement rule",
        "--context-id",
        "repo-b/b",
        "--evidence-ref",
        "case:b",
        "--evidence-source",
        "case:b",
        "--merge-with",
        entry_id,
    )
    assert merged.returncode == 1
    assert "superseded" in error["error"]

    reused, error = run_engine(
        state,
        "reuse",
        "--id",
        entry_id,
        "--context-id",
        "repo-b/b",
        "--evidence-ref",
        "case:b",
        "--evidence-source",
        "case:b",
        "--outcome",
        "helpful",
    )
    assert reused.returncode == 1
    assert "superseded" in error["error"]

    for command in (
        ("show", "--id", "../../outside"),
        (
            "reuse",
            "--id",
            "../../outside",
            "--context-id",
            "x",
            "--evidence-ref",
            "x",
            "--evidence-source",
            "x",
            "--outcome",
            "neutral",
        ),
    ):
        rejected, payload = run_engine(state, *command)
        assert rejected.returncode == 1
        assert "invalid format" in payload["error"]
    assert not (tmp_path / "outside.json").exists()

    symlink_state = tmp_path / "symlink-state"
    outside_entries = tmp_path / "outside-entries"
    symlink_state.mkdir()
    outside_entries.mkdir()
    (symlink_state / "entries").symlink_to(outside_entries, target_is_directory=True)
    rejected, payload = run_engine(
        symlink_state, "show", "--id", "ei-aaaaaaaaaaaa"
    )
    assert rejected.returncode == 1
    assert "escapes the state root" in payload["error"]
    assert list(outside_entries.iterdir()) == []


def test_search_and_show_fail_closed_on_projection_drift(tmp_path):
    state = tmp_path / "state"
    _, created = capture(state, agent="codex", context="repo-a/a", evidence="case:a")
    entry_id = created["entry"]["id"]

    index_path = state / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["chain_head"] = "f" * 64
    index_path.write_text(json.dumps(index), encoding="utf-8")
    searched, error = run_engine(state, "search", "--query", "runtime")
    assert searched.returncode == 1
    assert "verify --repair" in error["error"]

    repaired, _ = run_engine(state, "verify", "--repair")
    assert repaired.returncode == 0
    detail_path = state / "entries" / f"{entry_id}.json"
    detail = json.loads(detail_path.read_text(encoding="utf-8"))
    detail["title"] = "tampered projection"
    detail_path.write_text(json.dumps(detail), encoding="utf-8")
    shown, error = run_engine(state, "show", "--id", entry_id)
    assert shown.returncode == 1
    assert "verify --repair" in error["error"]


def test_stale_lock_recovery_is_fail_closed_except_for_absent_pid(tmp_path):
    stale_state = tmp_path / "stale"
    run_engine(stale_state, "init")
    (stale_state / ".write.lock").write_text(
        json.dumps({"pid": 999_999_999, "acquired_at": "2026-08-20T00:00:00Z"}),
        encoding="utf-8",
    )
    recovered, result = run_engine(stale_state, "init")
    assert recovered.returncode == 0
    assert result["status"] == "ok"

    active_state = tmp_path / "active"
    run_engine(active_state, "init")
    (active_state / ".write.lock").write_text(
        json.dumps({"pid": os.getpid(), "acquired_at": "2026-08-20T00:00:00Z"}),
        encoding="utf-8",
    )
    active, result = run_engine(active_state, "init")
    assert active.returncode == 1
    assert "busy" in result["error"]

    malformed_state = tmp_path / "malformed"
    run_engine(malformed_state, "init")
    (malformed_state / ".write.lock").write_text("pid=unknown\n", encoding="utf-8")
    malformed, result = run_engine(malformed_state, "init")
    assert malformed.returncode == 1
    assert "busy" in result["error"]


def test_metrics_are_authoritative_read_only_kpis(tmp_path):
    state = tmp_path / "state"
    capture(state, agent="codex", context="repo-a/a", evidence="case:a")
    _, candidate = capture(state, agent="claude", context="repo-b/b", evidence="case:b")
    entry_id = candidate["entry"]["id"]
    run_engine(
        state,
        "reuse",
        "--id",
        entry_id,
        "--context-id",
        "repo-c/c",
        "--evidence-ref",
        "case:c",
        "--evidence-source",
        "case:c",
        "--outcome",
        "helpful",
    )
    run_engine(
        state,
        "promote",
        "--id",
        entry_id,
        "--target",
        "AGENTS.md",
        "--owner-approved",
        "--approved-by",
        "test-owner",
        "--approval-evidence-ref",
        "approval:test",
        "--falsifier",
        "a falsifier",
        "--rollback",
        "a rollback",
    )
    events_before = (state / "events.jsonl").read_bytes()
    index_before = (state / "index.json").read_bytes()
    proc, metrics = run_engine(state, "metrics")
    assert proc.returncode == 0
    assert metrics["event_count"] == 4
    assert metrics["entry_count"] == 1
    assert metrics["observation_count"] == 2
    assert metrics["merged_observation_ratio"] == 0.5
    assert metrics["helpful_reuse_count"] == 1
    assert metrics["promoted_count"] == metrics["promotion_event_count"] == 1
    assert metrics["events_bytes"] == len(events_before)
    assert (state / "events.jsonl").read_bytes() == events_before
    assert (state / "index.json").read_bytes() == index_before

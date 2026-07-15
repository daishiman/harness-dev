#!/usr/bin/env python3
# /// script
# name: test-aggregate-issue-diffs
# purpose: C11 の完全 commit pair 復元、digest、時系列集約、fail-closed 境界を検証する。
# inputs: scripts/aggregate-issue-diffs.py / tmp_path git repo
# outputs: pytest assertions and coverage evidence
# contexts: [E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest, git]
# ///
"""aggregate-issue-diffs.py の pytest。

一時 git repo を tempfile + subprocess で構築し、
  (a) 正常系 (entries 復元 + diff_sha256 安定/一致)
  (b) 曖昧照合 (同一 subject が複数) で exit2
  (c) digest mismatch で exit2
  (d) shallow repo で exit2
を検証する。stdlib only、network 不使用。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aggregate-issue-diffs.py"
_HEADING = "2026-07-13T02:32:50Z"
_SUBJECT = f"chore: update yaml-spec-cache ({_HEADING})"
_DIFF_FLAGS = ("-c", "color.ui=false", "diff", "--no-color", "--no-ext-diff", "--no-textconv")


def _git_env() -> dict:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "tester",
            "GIT_AUTHOR_EMAIL": "tester@example.com",
            "GIT_COMMITTER_NAME": "tester",
            "GIT_COMMITTER_EMAIL": "tester@example.com",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return env


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "cache.md").write_text("# YAML Spec Cache\nline1\n", encoding="utf-8")
    _git(repo, "add", "cache.md")
    _git(repo, "commit", "-q", "-m", "initial commit")


def _add_cache_commit(repo: Path, subject: str, body: str) -> None:
    (repo / "cache.md").write_text(body, encoding="utf-8")
    _git(repo, "add", "cache.md")
    _git(repo, "commit", "-q", "-m", subject)


def _write_events(path: Path, events: list[dict], issue: int = 42) -> None:
    path.write_text(json.dumps({"issue": issue, "events": events}), encoding="utf-8")


def _run_script(events: Path, repo: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--issue",
            "42",
            "--events",
            str(events),
            "--repo-root",
            str(repo),
            *extra,
        ],
        capture_output=True,
        text=True,
    )


def test_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"], capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert "--issue" in proc.stdout
    assert "--events" in proc.stdout


def test_happy_path_restores_entries_and_stable_digest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _add_cache_commit(repo, _SUBJECT, "# YAML Spec Cache\nline1\nline2 added\n")

    events = tmp_path / "events.json"
    _write_events(events, [{"event_at": _HEADING, "history_heading": _HEADING}])

    proc = _run_script(events, repo)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)

    assert len(payload["entries"]) == 1
    entry = payload["entries"][0]
    assert entry["history_heading"] == _HEADING
    assert entry["complete"] is True
    assert len(entry["diff_sha256"]) == 64
    assert entry["diff"], "diff text should be non-empty"

    # latest / untriaged / provenance
    assert payload["latest_entry"]["source_commit"] == entry["source_commit"]
    assert len(payload["untriaged_entries"]) == 1
    assert payload["source_provenance"]["issue"] == 42
    assert payload["source_provenance"]["network"] is False

    # diff_sha256 が実際の git diff の sha256 と一致すること (正しさ)
    diff = _git(repo, *_DIFF_FLAGS, entry["base_commit"], entry["source_commit"]).stdout
    assert entry["diff_sha256"] == hashlib.sha256(diff.encode("utf-8")).hexdigest()

    # 決定論: 同一入力 → 同一出力
    proc2 = _run_script(events, repo)
    assert proc2.returncode == 0
    assert proc2.stdout == proc.stdout


def test_since_filter_excludes_older_events(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _add_cache_commit(repo, _SUBJECT, "# YAML Spec Cache\nline1\nline2 added\n")

    events = tmp_path / "events.json"
    _write_events(events, [{"event_at": _HEADING, "history_heading": _HEADING}])

    proc = _run_script(events, repo, "--since", "2099-01-01T00:00:00Z")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["entries"] == []
    assert payload["latest_entry"] is None


def test_array_events_accept_naive_timestamp_and_triaged_entry(tmp_path: Path) -> None:
    """object wrapper 以外の array 入力、naive UTC、triaged 除外分岐を固定する。"""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _add_cache_commit(repo, _SUBJECT, "# YAML Spec Cache\nline1\nline2 added\n")
    events = tmp_path / "events.json"
    events.write_text(json.dumps([{
        "event_at": "2026-07-13T02:32:50",
        "history_heading": _HEADING,
        "triaged": True,
    }]), encoding="utf-8")

    proc = _run_script(events, repo)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert len(payload["entries"]) == 1
    assert payload["untriaged_entries"] == []


def test_ambiguous_match_exits_two(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    # 同一 subject を持つ 2 つの異なる commit を作る → 曖昧照合
    _add_cache_commit(repo, _SUBJECT, "# YAML Spec Cache\nvariant A\n")
    _add_cache_commit(repo, _SUBJECT, "# YAML Spec Cache\nvariant B\n")

    events = tmp_path / "events.json"
    _write_events(events, [{"event_at": _HEADING, "history_heading": _HEADING}])

    proc = _run_script(events, repo)
    assert proc.returncode == 2, proc.stdout
    assert "曖昧照合" in proc.stderr


def test_missing_commit_exits_two(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    # cache commit を作らない → 0 件照合 (fail-closed)
    events = tmp_path / "events.json"
    _write_events(events, [{"event_at": _HEADING, "history_heading": _HEADING}])

    proc = _run_script(events, repo)
    assert proc.returncode == 2, proc.stdout
    assert "曖昧照合" in proc.stderr


def test_digest_mismatch_exits_two(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _add_cache_commit(repo, _SUBJECT, "# YAML Spec Cache\nline1\nline2 added\n")

    events = tmp_path / "events.json"
    _write_events(
        events,
        [
            {
                "event_at": _HEADING,
                "history_heading": _HEADING,
                "expected_diff_sha256": "0" * 64,
            }
        ],
    )

    proc = _run_script(events, repo)
    assert proc.returncode == 2, proc.stdout
    assert "digest 不一致" in proc.stderr


def test_shallow_repo_exits_two(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    _init_repo(origin)
    _add_cache_commit(origin, _SUBJECT, "# YAML Spec Cache\nline1\nline2 added\n")

    shallow = tmp_path / "shallow"
    clone = subprocess.run(
        [
            "git",
            "clone",
            "--depth=1",
            f"file://{origin}",
            str(shallow),
        ],
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    assert clone.returncode == 0, clone.stderr

    is_shallow = subprocess.run(
        ["git", "-C", str(shallow), "rev-parse", "--is-shallow-repository"],
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    assert is_shallow.stdout.strip() == "true", "clone should be shallow"

    events = tmp_path / "events.json"
    _write_events(events, [{"event_at": _HEADING, "history_heading": _HEADING}])

    proc = _run_script(events, shallow)
    assert proc.returncode == 2, proc.stdout
    assert "shallow" in proc.stderr


def test_not_a_git_repo_exits_one(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    events = tmp_path / "events.json"
    _write_events(events, [{"event_at": _HEADING, "history_heading": _HEADING}])

    proc = _run_script(events, plain)
    assert proc.returncode == 1, proc.stdout


def test_malformed_events_exits_one(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    events = tmp_path / "events.json"
    events.write_text("{ not json", encoding="utf-8")

    proc = _run_script(events, repo)
    assert proc.returncode == 1, proc.stdout


def test_missing_required_arg_exits_one() -> None:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--events", "x.json"],
        capture_output=True,
        text=True,
    )
    # argparse 既定 exit2 を override して 一般エラー exit1 にしている
    assert proc.returncode == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

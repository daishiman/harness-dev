"""保存する内容・対象範囲・既存ファイルの競合を実ファイルで検証する。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from argparse import Namespace

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts/publish-staged-files.py"
spec = importlib.util.spec_from_file_location("ubm_publication", SCRIPT)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_plan(tmp_path):
    stage = tmp_path / "stage"
    official = tmp_path / "official"
    stage.mkdir()
    official.mkdir()
    draft = stage / "draft.md"
    draft.write_text("validated draft", encoding="utf-8")
    plan = {"schema_version": 1, "stage_root": str(stage), "roots": {"vault": str(official)},
            "entries": [{"root": "vault", "path": "one.md", "operation": "write",
                         "source": str(draft), "new_sha256": sha(draft), "old_sha256": None}]}
    manifest = stage / "manifest.json"
    return stage, official, draft, plan, manifest


def save(plan, manifest):
    manifest.write_text(json.dumps(plan), encoding="utf-8")
    return sha(manifest)


def test_exact_draft_is_saved_and_receipt_matches(tmp_path):
    _, official, draft, plan, manifest = fixture_plan(tmp_path)
    receipt = M.publish(manifest, save(plan, manifest))
    assert (official / "one.md").read_bytes() == draft.read_bytes()
    assert receipt["saved"][0]["sha256"] == sha(draft)
    assert receipt["batch_atomic"] is False


def test_manifest_and_draft_tamper_are_rejected_before_any_write(tmp_path):
    _, official, draft, plan, manifest = fixture_plan(tmp_path)
    approved = save(plan, manifest)
    manifest.write_text(manifest.read_text() + " ")
    with pytest.raises(ValueError, match="manifest changed"):
        M.publish(manifest, approved)
    approved = save(plan, manifest)
    draft.write_text("changed after approval")
    with pytest.raises(ValueError, match="draft changed"):
        M.publish(manifest, approved)
    assert list(official.iterdir()) == []


def test_late_existing_target_conflict_blocks_whole_batch(tmp_path):
    stage, official, _, plan, manifest = fixture_plan(tmp_path)
    second = stage / "second.md"
    second.write_text("second")
    plan["entries"].append({**plan["entries"][0], "path": "two.md", "source": str(second), "new_sha256": sha(second)})
    approved = save(plan, manifest)
    (official / "two.md").write_text("concurrent edit")
    with pytest.raises(ValueError, match="official file changed"):
        M.publish(manifest, approved)
    assert not (official / "one.md").exists()
    assert (official / "two.md").read_text() == "concurrent edit"


@pytest.mark.parametrize("relative", ["../escape.md", "/absolute.md", "dir/../../escape.md", "dir\\escape.md", "."])
def test_target_escape_is_rejected(tmp_path, relative):
    _, official, _, plan, manifest = fixture_plan(tmp_path)
    plan["entries"][0]["path"] = relative
    with pytest.raises(ValueError):
        M.publish(manifest, save(plan, manifest))
    assert list(official.iterdir()) == []


def test_symlink_parent_and_foreign_draft_are_rejected(tmp_path):
    _, official, _, plan, manifest = fixture_plan(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (official / "link").symlink_to(outside, target_is_directory=True)
    plan["entries"][0]["path"] = "link/escape.md"
    with pytest.raises(ValueError, match="symlink"):
        M.publish(manifest, save(plan, manifest))
    plan["entries"][0]["path"] = "one.md"
    foreign = outside / "draft.md"
    foreign.write_text("foreign")
    plan["entries"][0]["source"] = str(foreign)
    plan["entries"][0]["new_sha256"] = sha(foreign)
    with pytest.raises(ValueError, match="inside stage"):
        M.publish(manifest, save(plan, manifest))
    assert list(outside.iterdir()) == [foreign]


def test_archive_write_precedes_original_delete(tmp_path):
    stage, official, _, plan, manifest = fixture_plan(tmp_path)
    original = official / "old.md"
    original.write_text("historic content")
    backup = stage / "backup.md"
    backup.write_bytes(original.read_bytes())
    plan["entries"] = [{"root": "vault", "path": "old.md", "operation": "delete", "old_sha256": sha(original)},
                       {"root": "vault", "path": "archive/old.md", "operation": "write", "old_sha256": None,
                        "source": str(backup), "new_sha256": sha(backup)}]
    receipt = M.publish(manifest, save(plan, manifest))
    assert [e["operation"] for e in receipt["saved"]] == ["write", "delete"]
    assert not original.exists()
    assert (official / "archive/old.md").read_text() == "historic content"


def test_missing_old_hash_and_duplicate_target_fail_closed(tmp_path):
    _, official, _, plan, manifest = fixture_plan(tmp_path)
    del plan["entries"][0]["old_sha256"]
    with pytest.raises(ValueError, match="explicitly"):
        M.publish(manifest, save(plan, manifest))
    plan["entries"][0]["old_sha256"] = None
    plan["entries"].append(plan["entries"][0].copy())
    with pytest.raises(ValueError, match="duplicate"):
        M.publish(manifest, save(plan, manifest))
    assert list(official.iterdir()) == []


def test_cli_rejects_invalid_plan_without_traceback(tmp_path):
    _, official, _, plan, manifest = fixture_plan(tmp_path)
    plan["entries"] = [None]
    proc = subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(manifest), "--manifest-sha256", save(plan, manifest)], capture_output=True, text=True)
    assert proc.returncode == 2
    assert "Traceback" not in proc.stderr
    assert list(official.iterdir()) == []


def test_central_guard_binds_publication_argv_and_consumes_receipt(tmp_path):
    """実guardの受領書を一時root内で発行する。実ユーザー試行は主張しない。"""
    guard_path = PLUGIN.parent / "skill-governance-adapters/scripts/build-external-mutation-guard.py"
    guard_spec = importlib.util.spec_from_file_location("ubm_test_central_guard", guard_path)
    guard = importlib.util.module_from_spec(guard_spec)
    sys.modules[guard_spec.name] = guard
    guard_spec.loader.exec_module(guard)
    _, official, draft, plan, manifest = fixture_plan(tmp_path)
    command = [sys.executable, str(SCRIPT), "--manifest", str(manifest), "--manifest-sha256", save(plan, manifest)]
    command_json = json.dumps(command)
    preview = guard.preview(Namespace(project_root=str(tmp_path), entrypoint_ref="plugin:ubm-goal-setting/skills/run-ubm-journal/SKILL.md",
                                     target_scope=str(official), diff_summary="new one.md", side_effect_summary="one local file", command_json=command_json))
    assert preview["auto_grantable"] is False
    challenge = preview["challenge"]
    confirmation = guard._confirm_challenge(tmp_path.resolve(), "CONFIRM EXTERNAL MUTATION " + challenge, "fixture-session", challenge)
    authorization = guard.authorize(Namespace(project_root=str(tmp_path), preview_receipt=preview["receipt_path"], confirmation_receipt=confirmation["receipt_path"]))
    args = Namespace(project_root=str(tmp_path), authorization_receipt=authorization["receipt_path"], command_json=command_json)
    changed = [*command[:-1], "0" * 64]
    with pytest.raises(guard.GuardError, match="digest differs"):
        guard.execute(Namespace(**{**vars(args), "command_json": json.dumps(changed)}))
    assert not (official / "one.md").exists()
    assert guard.execute(args) == 0
    assert (official / "one.md").read_bytes() == draft.read_bytes()
    with pytest.raises(guard.GuardError, match="already consumed"):
        guard.execute(args)


def test_second_write_io_failure_reports_saved_paths_and_failed_target(tmp_path, monkeypatch, capsys):
    stage, official, _, plan, manifest = fixture_plan(tmp_path)
    second = stage / "second.md"
    second.write_text("second draft")
    plan["entries"].append({**plan["entries"][0], "path": "two.md", "source": str(second), "new_sha256": sha(second)})
    approved = save(plan, manifest)
    real_replace = M.os.replace

    def failing_replace(source, target):
        if Path(target).name == "two.md":
            raise OSError("fixture second-write failure")
        return real_replace(source, target)

    monkeypatch.setattr(M.os, "replace", failing_replace)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--manifest", str(manifest), "--manifest-sha256", approved])
    assert M.main() == 2
    failure = json.loads(capsys.readouterr().err)
    assert failure["saved"] == [{"path": str(official / "one.md"), "operation": "write", "sha256": plan["entries"][0]["new_sha256"]}]
    assert failure["failed_target"] == str(official / "two.md")
    assert failure["error"] == "fixture second-write failure"
    assert failure["batch_atomic"] is False
    assert (official / "one.md").read_text() == "validated draft"
    assert not (official / "two.md").exists()
    assert list(official.glob(".ubm-publish-*")) == []

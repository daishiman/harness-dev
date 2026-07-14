from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts" / "manage-system-plan-lock.py"
SPEC = importlib.util.spec_from_file_location("test_system_plan_lock_module", SCRIPT)
LOCK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOCK)  # type: ignore[union-attr]
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def make_repo(root: Path) -> str:
    c09 = LOCK._load_context()
    repository_id, _ = c09.derive_repository_id(root.resolve())
    config = json.loads((PLUGIN / "assets/default-project-config.json").read_text(encoding="utf-8"))
    config["repository_id"] = repository_id
    config.pop("repository_id_note", None)
    dump(root / ".dev-graph/config.json", config)
    for rel in config["content_roots"].values():
        (root / rel).mkdir(parents=True, exist_ok=True)
    for section in ("local_state", "plan_roots"):
        for rel in config[section].values():
            (root / rel).mkdir(parents=True, exist_ok=True)
    return repository_id


def args(root: Path, action: str, *, run: str = "run-a", owner: str = "session-a",
         feature: str = "FEATURE-1", digest: str = DIGEST_A, ttl: int = 120) -> list[str]:
    return [
        "--lock-action", action, "--repo-root", str(root), "--run-id", run,
        "--session-owner", owner, "--feature-id", feature,
        "--feature-digest", digest, "--ttl-seconds", str(ttl),
    ]


def invoke(argv: list[str], when: str) -> tuple[int, dict]:
    now = datetime.fromisoformat(when.replace("Z", "+00:00"))
    output = io.StringIO()
    root = argv[argv.index("--repo-root") + 1] if "--repo-root" in argv else None
    env = {**os.environ, **({"CLAUDE_PROJECT_DIR": root} if root else {})}
    with mock.patch.object(LOCK, "_utc_now", return_value=now), \
            mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
        code = LOCK.main(argv)
    return code, json.loads(output.getvalue())


class LockLifecycleTests(unittest.TestCase):
    def test_acquire_renew_release_preserves_owner_and_acquired_at(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            code, acquired = invoke(args(root, "acquire"), "2026-07-13T00:00:00Z")
            self.assertEqual(code, 0, acquired)
            lock_path = root / LOCK.LOCK_ROOT_REL / LOCK.LOCK_NAME
            state = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual(set(state), LOCK.LOCK_FIELDS)
            self.assertEqual(state["repository_id"], repository_id)
            self.assertEqual(state["acquired_at"], "2026-07-13T00:00:00Z")
            self.assertEqual(state["expires_at"], "2026-07-13T00:02:00Z")
            self.assertEqual(lock_path.stat().st_mode & 0o777, 0o600)

            code, renewed = invoke(args(root, "renew", ttl=180), "2026-07-13T00:01:00Z")
            self.assertEqual(code, 0, renewed)
            state = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual(state["acquired_at"], "2026-07-13T00:00:00Z")
            self.assertEqual(state["heartbeat_at"], "2026-07-13T00:01:00Z")
            self.assertEqual(state["expires_at"], "2026-07-13T00:04:00Z")

            code, released = invoke(args(root, "release"), "2026-07-13T00:02:00Z")
            self.assertEqual(code, 0, released)
            self.assertFalse(lock_path.exists())
            self.assertFalse(released["expired_cleanup"])

    def test_active_lock_and_owner_mismatch_are_domain_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); make_repo(root)
            self.assertEqual(invoke(args(root, "acquire"), "2026-07-13T00:00:00Z")[0], 0)
            code, blocked = invoke(args(root, "acquire", run="run-b"), "2026-07-13T00:00:01Z")
            self.assertEqual(code, 1); self.assertEqual(blocked["error_kind"], "domain")
            lock_path = root / LOCK.LOCK_ROOT_REL / LOCK.LOCK_NAME
            before = lock_path.read_bytes()
            for action, override in (("renew", {"owner": "other"}),
                                     ("release", {"digest": DIGEST_B})):
                with self.subTest(action=action):
                    code, result = invoke(args(root, action, **override), "2026-07-13T00:00:30Z")
                    self.assertEqual(code, 1); self.assertIn("mismatch", result["message"])
                    self.assertEqual(lock_path.read_bytes(), before)

            code, result = invoke(args(root, "renew"), "2026-07-12T23:59:59Z")
            self.assertEqual(code, 1); self.assertIn("clock regression", result["message"])
            self.assertEqual(lock_path.read_bytes(), before)

    def test_expired_acquire_writes_receipt_before_replacement(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); make_repo(root)
            self.assertEqual(invoke(args(root, "acquire", ttl=60), "2026-07-13T00:00:00Z")[0], 0)
            code, result = invoke(
                args(root, "acquire", run="run-b", owner="session-b", feature="FEATURE-2", digest=DIGEST_B),
                "2026-07-13T00:02:00Z",
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["lock"]["run_id"], "run-b")
            self.assertEqual(len(result["cleanup_receipts"]), 1)
            receipt = root / result["cleanup_receipts"][0]
            audit = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(audit["event"], "expired-lock-cleanup")
            self.assertEqual(audit["expired_lock"]["run_id"], "run-a")
            self.assertRegex(audit["expired_lock_sha256"], r"^sha256:[0-9a-f]{64}$")

    def test_expired_renew_cleans_and_blocks_but_expired_release_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); make_repo(root)
            self.assertEqual(invoke(args(root, "acquire", ttl=30), "2026-07-13T00:00:00Z")[0], 0)
            code, result = invoke(args(root, "renew"), "2026-07-13T00:01:00Z")
            self.assertEqual(code, 1); self.assertIn("expired", result["message"])
            self.assertFalse((root / LOCK.LOCK_ROOT_REL / LOCK.LOCK_NAME).exists())

            self.assertEqual(invoke(args(root, "acquire", ttl=30), "2026-07-13T00:02:00Z")[0], 0)
            code, result = invoke(args(root, "release"), "2026-07-13T00:03:00Z")
            self.assertEqual(code, 0, result); self.assertTrue(result["expired_cleanup"])
            self.assertTrue((root / result["cleanup_receipt"]).is_file())


class FailClosedTests(unittest.TestCase):
    def test_malformed_existing_lock_and_busy_guard_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); make_repo(root)
            locks = root / LOCK.LOCK_ROOT_REL
            lock_path = locks / LOCK.LOCK_NAME
            lock_path.write_text("{", encoding="utf-8")
            code, result = invoke(args(root, "acquire"), "2026-07-13T00:00:00Z")
            self.assertEqual(code, 1); self.assertIn("malformed", result["message"])
            lock_path.unlink()
            guard = locks / LOCK.GUARD_NAME
            with guard.open("r+") as stream:
                LOCK.fcntl.flock(stream.fileno(), LOCK.fcntl.LOCK_EX | LOCK.fcntl.LOCK_NB)
                code, result = invoke(args(root, "acquire"), "2026-07-13T00:00:00Z")
                self.assertEqual(code, 1); self.assertIn("in progress", result["message"])

    def test_symlink_lock_and_lock_root_are_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside_td:
            root = Path(td); make_repo(root)
            outside = Path(outside_td) / "outside.json"; outside.write_text("outside", encoding="utf-8")
            lock_path = root / LOCK.LOCK_ROOT_REL / LOCK.LOCK_NAME
            lock_path.symlink_to(outside)
            code, result = invoke(args(root, "acquire"), "2026-07-13T00:00:00Z")
            self.assertEqual(code, 1); self.assertIn("symlink", result["message"])
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td); make_repo(root)
            locks = root / LOCK.LOCK_ROOT_REL
            locks.rmdir()
            (root / "in-root-locks").mkdir()
            locks.symlink_to(root / "in-root-locks", target_is_directory=True)
            code, result = invoke(args(root, "acquire"), "2026-07-13T00:00:00Z")
            self.assertEqual(code, 2); self.assertIn("symlink", result["message"])

    def test_bad_cli_and_config_paths_are_contract_errors_with_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); make_repo(root)
            cases = [
                args(root, "acquire", run="../escape"),
                args(root, "acquire", digest="bad"),
                args(root, "acquire", ttl=0),
                [*args(root, "acquire")[:-1], "not-an-int"],
                args(root, "acquire") + ["--config", "../outside.json"],
                args(root, "acquire") + ["--config", "/tmp/outside.json"],
            ]
            for argv in cases:
                with self.subTest(argv=argv):
                    code, result = invoke(argv, "2026-07-13T00:00:00Z")
                    self.assertEqual(code, 2); self.assertEqual(result["error_kind"], "contract")

    def test_absent_lock_foreign_fixed_lock_and_receipt_symlink_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            code, result = invoke(args(root, "renew"), "2026-07-13T00:00:00Z")
            self.assertEqual(code, 1); self.assertIn("absent", result["message"])

            locks = root / LOCK.LOCK_ROOT_REL
            foreign = LOCK._lock_value("github:other/repo", type("A", (), {
                "run_id": "run-x", "session_owner": "s", "feature_id": "F",
                "feature_digest": DIGEST_A, "ttl_seconds": 60,
            })(), datetime(2026, 7, 13, tzinfo=timezone.utc))
            dump(locks / LOCK.LOCK_NAME, foreign)
            code, result = invoke(args(root, "acquire"), "2026-07-13T00:00:01Z")
            self.assertEqual(code, 1); self.assertIn("different repository", result["message"])
            (locks / LOCK.LOCK_NAME).unlink()

            expired = LOCK._lock_value(repository_id, type("A", (), {
                "run_id": "run-a", "session_owner": "session-a", "feature_id": "FEATURE-1",
                "feature_digest": DIGEST_A, "ttl_seconds": 1,
            })(), datetime(2026, 7, 13, tzinfo=timezone.utc))
            dump(locks / LOCK.LOCK_NAME, expired)
            target = root / "receipt-target"; target.mkdir()
            (locks / LOCK.RECEIPT_DIR_NAME).symlink_to(target, target_is_directory=True)
            code, result = invoke(args(root, "acquire"), "2026-07-13T00:01:00Z")
            self.assertEqual(code, 1); self.assertIn("receipt directory is a symlink", result["message"])


if __name__ == "__main__":
    unittest.main()

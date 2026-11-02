"""ランタイム確認と runtime-absent skip — algorithm 4 / AC-C21-3 / failure_modes。

generate-images-codex.js は codex 不在でも 3 回リトライして warn するだけなので、
そのまま走らせると『画像 0 枚だが exit 0』という最も紛らわしい状態になる。
だから **起動前に** 判定して skip を宣言する。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


class _Base(H.BridgeTestCase):
    def _run(self, tmp, *, node=True, codex=True, node_version=None, extra=()):
        tmp = Path(tmp)
        srg = H.make_srg(tmp)
        bin_dir = H.make_fake_bin(tmp, node=node, codex=codex)
        log = tmp / "log.jsonl"
        plan = H.write_plan(tmp / "plan.json", H.plan_payload())
        overrides = {}
        if node_version is not None:
            overrides[H.ENV_NODE_VERSION] = node_version
        proc = H.run(
            [
                "--image-plan",
                plan,
                "--assets-dir",
                H.make_assets_dir(tmp),
                "--srg-root",
                srg,
                *extra,
            ],
            env=H.clean_env(tmp, bin_dir=bin_dir, log=log, **overrides),
        )
        return proc, log


class NodeAbsentTest(_Base):
    """AC-C21-3: PATH から node を外すと runtime-absent skip。"""

    def test_exit_code_is_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node=False)
            self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_skip_reason_is_runtime_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node=False)
            data = H.stdout_json(self, proc)
            self.assertEqual("skipped", data["status"], H.describe(proc))
            self.assertEqual("runtime-absent", data["skip_reason"], H.describe(proc))

    def test_skip_detail_names_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node=False)
            detail = H.stdout_json(self, proc)["skip_detail"]
            self.assertIsInstance(detail, str, H.describe(proc))
            self.assertIn("node", detail, H.describe(proc))

    def test_runtime_node_is_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node=False)
            self.assertIsNone(H.stdout_json(self, proc)["runtime"]["node"], H.describe(proc))

    def test_srg_root_is_still_reported(self):
        """SRG は解決できている。skip の理由がランタイム側だと分かること。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node=False)
            self.assertIsNotNone(H.stdout_json(self, proc)["srg_root"], H.describe(proc))

    def test_nothing_is_launched(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, log = self._run(tmp, node=False)
            self.assertEqual([], H.node_log(log), "起動を試みている:\n" + H.describe(proc))

    def test_all_images_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node=False)
            statuses = {entry["status"] for entry in H.stdout_json(self, proc)["images"]}
            self.assertEqual({"skipped"}, statuses, H.describe(proc))


class NodeVersionTest(_Base):
    """algorithm 4: node の major 下限は 18。"""

    def test_old_node_is_runtime_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node_version="v16.20.2")
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual("runtime-absent", H.stdout_json(self, proc)["skip_reason"], H.describe(proc))

    def test_old_node_skip_detail_mentions_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node_version="v16.20.2")
            detail = H.stdout_json(self, proc)["skip_detail"] or ""
            self.assertTrue(
                "16" in detail or "version" in detail.lower() or "18" in detail,
                "版数不足であることが skip_detail から読めない: {!r}".format(detail),
            )

    def test_old_node_does_not_launch_vendor_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, log = self._run(tmp, node_version="v16.20.2")
            self.assertEqual([], H.invoked_scripts(log), "版数不足なのに委譲している:\n" + H.describe(proc))

    def test_supported_node_is_reported_in_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node_version="v20.11.0")
            reported = H.stdout_json(self, proc)["runtime"]["node"]
            self.assertIsNotNone(reported, H.describe(proc))
            self.assertIn("20", str(reported), H.describe(proc))

    def test_node_version_boundary_18_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, node_version="v18.0.0")
            self.assertNotEqual(
                "runtime-absent",
                H.stdout_json(self, proc).get("skip_reason"),
                "下限 18 を満たしているのに skip している:\n" + H.describe(proc),
            )


class CodexPresenceTest(_Base):
    """codex は本番実行のときだけ必要 (--dry-run では要らない)。"""

    def test_codex_absent_in_production_is_runtime_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, codex=False)
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual("runtime-absent", H.stdout_json(self, proc)["skip_reason"], H.describe(proc))

    def test_codex_absent_skip_detail_names_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, codex=False)
            self.assertIn("codex", H.stdout_json(self, proc)["skip_detail"] or "", H.describe(proc))

    def test_codex_absent_does_not_launch_the_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, log = self._run(tmp, codex=False)
            self.assertNotIn(
                "generate-images-codex.js", H.invoked_scripts(log), H.describe(proc)
            )

    def test_codex_absent_is_fine_in_dry_run(self):
        """--dry-run は codex exec を呼ばないので、codex 不在でも skip しない。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, codex=False, extra=["--dry-run"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual("dry-run", H.stdout_json(self, proc)["status"], H.describe(proc))

    def test_codex_path_is_reported_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp)
            self.assertIsNotNone(H.stdout_json(self, proc)["runtime"]["codex"], H.describe(proc))

    def test_codex_binary_is_never_executed_by_this_script(self):
        """codex を起動するのは委譲先であって本 script ではない (存在確認だけ)。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, log = self._run(tmp)
            tools = [entry.get("tool") for entry in H.node_log(log)]
            self.assertNotIn("codex", tools, "本 script が codex を直接起動している:\n" + H.describe(proc))


if __name__ == "__main__":
    unittest.main()

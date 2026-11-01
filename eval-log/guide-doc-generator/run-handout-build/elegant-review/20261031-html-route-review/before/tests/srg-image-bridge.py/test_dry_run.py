"""--dry-run — algorithm 11 / AC-C21-5。課金の発生する codex exec を呼ばない。

prompt / meta の機械展開 (無料・決定論) までは実行し、generate-images-codex.js へ
--dry-run を渡して組み立てコマンドを回収する。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


class DryRunTest(H.BridgeTestCase):
    def _run(self, tmp):
        tmp = Path(tmp)
        srg = H.make_srg(tmp)
        bin_dir = H.make_fake_bin(tmp)
        log = tmp / "log.jsonl"
        plan = H.write_plan(tmp / "plan.json", H.plan_payload())
        assets = H.make_assets_dir(tmp)
        proc = H.run(
            ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg, "--dry-run"],
            env=H.clean_env(tmp, bin_dir=bin_dir, log=log),
        )
        return proc, assets, log, srg

    def _generated(self, assets):
        return Path(assets) / "srg-work" / "assets" / "generated"

    def test_exit_code_is_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _, _ = self._run(tmp)
            self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_status_is_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _, _ = self._run(tmp)
            self.assertEqual("dry-run", H.stdout_json(self, proc)["status"], H.describe(proc))

    def test_all_images_are_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _, _ = self._run(tmp)
            statuses = {entry["status"] for entry in H.stdout_json(self, proc)["images"]}
            self.assertEqual({"dry-run"}, statuses, H.describe(proc))

    def test_deck_plan_is_written_to_the_work_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _, _ = self._run(tmp)
            self.assertTrue(
                (self._generated(assets) / "image-deck-plan.json").is_file(), H.describe(proc)
            )

    def test_prompt_and_meta_files_exist_for_every_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _, _ = self._run(tmp)
            generated = self._generated(assets)
            for entry in H.stdout_json(self, proc)["images"]:
                slug = entry["slug"]
                self.assertTrue((generated / (slug + ".prompt.txt")).is_file(), slug)
                self.assertTrue((generated / (slug + ".meta.json")).is_file(), slug)

    def test_no_png_is_produced(self):
        """課金ゼロ。素材ディレクトリに PNG が 1 件も現れない。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _, _ = self._run(tmp)
            self.assertEqual(
                [], sorted(Path(assets).glob("images/*.png")), "dry-run で PNG が作られた:\n" + H.describe(proc)
            )

    def test_delegated_commands_contain_a_codex_exec_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _, _ = self._run(tmp)
            commands = H.stdout_json(self, proc)["delegated_commands"]
            lines = [
                " ".join(str(part) for part in command)
                if isinstance(command, list)
                else str(command)
                for command in commands
            ]
            self.assertTrue(
                any("codex exec" in line for line in lines),
                "組み立てられた codex コマンドが回収されていない (node の argv だけでは足りない):\n"
                + H.describe(proc),
            )

    def test_dry_run_flag_is_passed_through_to_the_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, log, _ = self._run(tmp)
            calls = [e for e in H.node_log(log) if e.get("script") == "generate-images-codex.js"]
            self.assertTrue(calls, "generate-images-codex.js が起動されていない:\n" + H.describe(proc))
            self.assertIn("dry-run", calls[-1]["flags"], "--dry-run が渡っていない: {}".format(calls[-1]))

    def test_prompt_builder_is_launched_before_the_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, log, _ = self._run(tmp)
            scripts = H.invoked_scripts(log)
            self.assertIn("build-image-prompts.js", scripts, H.describe(proc))
            self.assertIn("generate-images-codex.js", scripts, H.describe(proc))
            self.assertLess(
                scripts.index("build-image-prompts.js"),
                scripts.index("generate-images-codex.js"),
                "起動順が逆: {}".format(scripts),
            )

    def test_codex_binary_is_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, log, _ = self._run(tmp)
            self.assertNotIn(
                "codex", [e.get("tool") for e in H.node_log(log)], H.describe(proc)
            )

    def test_genome_is_passed_explicitly(self):
        """algorithm 9: 既定解決に任せると project-local の有無で挙動が変わる。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, log, srg = self._run(tmp)
            calls = [e for e in H.node_log(log) if e.get("script") == "build-image-prompts.js"]
            self.assertTrue(calls, H.describe(proc))
            genome = calls[-1]["flags"].get("genome")
            self.assertIsInstance(genome, str, "--genome が渡っていない: {}".format(calls[-1]))
            self.assertEqual(
                str((Path(srg) / H.SRG_GENOME_RELPATH).resolve()),
                str(Path(genome).resolve()),
                "SRG 同梱 genome を明示していない",
            )

    def test_vendor_scripts_are_launched_from_their_original_location(self):
        """algorithm 4: ESM の解決が vendor/package.json に依存するため複製して動かさない。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, log, srg = self._run(tmp)
            for entry in H.node_log(log):
                path = entry.get("script_path")
                if not path:
                    continue
                self.assertTrue(Path(path).is_absolute(), "絶対パスで起動していない: {}".format(path))
                self.assertEqual(
                    str(Path(srg).resolve()),
                    str(Path(path).resolve().parents[2]),
                    "vendor 配下の元位置から起動していない: {}".format(path),
                )


if __name__ == "__main__":
    unittest.main()

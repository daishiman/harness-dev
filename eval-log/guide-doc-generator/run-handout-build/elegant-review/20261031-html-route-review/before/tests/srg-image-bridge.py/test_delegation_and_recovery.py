"""委譲の実行と PNG 回収 — algorithm 9/10/13/14/15、AC-C21-6 / 7、failure_modes。

要点は 2 つ。
1. **委譲先の exit code を成功判定に使わない。** generate-images-codex.js は slug 単位の
   失敗を warn して継続し exit 0 を返すので、回収側が実ファイルと PNG 署名を自分で検査する。
2. **fail-soft の対象は『委譲先が無いこと』であって『委譲が失敗したこと』ではない。**
   SRG が在るのに落ちたら exit 1 であって skip ではない。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


class _Base(H.BridgeTestCase):
    def _run(self, tmp, *, sections=None, prompts="all", pngs="all", extra=()):
        tmp = Path(tmp)
        srg = H.make_srg(tmp)
        bin_dir = H.make_fake_bin(tmp)
        log = tmp / "log.jsonl"
        sections = sections if sections is not None else [H.section("intro"), H.section("build")]
        plan = H.write_plan(tmp / "plan.json", H.plan_payload(sections=sections))
        assets = H.make_assets_dir(tmp)
        proc = H.run(
            ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg, *extra],
            env=H.clean_env(
                tmp, bin_dir=bin_dir, log=log, **{H.ENV_PROMPTS: prompts, H.ENV_PNGS: pngs}
            ),
        )
        return proc, assets, log


class HappyPathTest(_Base):
    def test_all_slugs_recovered_is_exit0_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual("generated", H.stdout_json(self, proc)["status"], H.describe(proc))

    def test_png_lands_in_assets_images(self):
        """write_scope: <assets-dir>/images/<slug>.png。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _ = self._run(tmp)
            for entry in H.stdout_json(self, proc)["images"]:
                self.assertTrue(
                    (Path(assets) / "images" / (entry["slug"] + ".png")).is_file(), entry["slug"]
                )

    def test_recovered_png_keeps_the_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _ = self._run(tmp)
            for path in sorted((Path(assets) / "images").glob("*.png")):
                self.assertTrue(
                    path.read_bytes().startswith(H.PNG_SIGNATURE), "PNG 署名が無い: {}".format(path)
                )

    def test_recovered_bytes_match_the_generated_file(self):
        """回収は copy2。バイト列を加工しない (data URI 化は C13 の責務)。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _ = self._run(tmp)
            generated = Path(assets) / "srg-work" / "assets" / "generated"
            for path in sorted((Path(assets) / "images").glob("*.png")):
                source = generated / path.name
                self.assertTrue(source.is_file(), "生成物が作業ディレクトリに無い: {}".format(source))
                self.assertEqual(source.read_bytes(), path.read_bytes(), path.name)

    def test_png_bytes_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _ = self._run(tmp)
            for entry in H.stdout_json(self, proc)["images"]:
                path = Path(assets) / "images" / (entry["slug"] + ".png")
                self.assertEqual(path.stat().st_size, entry["png_bytes"], entry["slug"])

    def test_delegated_commands_record_both_vendor_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            flat = " ".join(
                " ".join(str(part) for part in command)
                for command in H.stdout_json(self, proc)["delegated_commands"]
            )
            self.assertIn("build-image-prompts.js", flat, H.describe(proc))
            self.assertIn("generate-images-codex.js", flat, H.describe(proc))

    def test_delegated_commands_are_shell_free_argv_lists(self):
        """subprocess.run(shell=False, argv 配列)。1 要素へ連結された行を許さない。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            for command in H.stdout_json(self, proc)["delegated_commands"]:
                self.assertGreater(len(command), 1, "argv が分割されていない: {!r}".format(command))
                for part in command:
                    self.assertNotIn(" && ", str(part))
                    self.assertNotIn(" | ", str(part))

    def test_data_uri_is_not_produced_here(self):
        """C13 が data URI 化の owner。C21 は base64 化しない。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _ = self._run(tmp)
            self.assertNotIn("data:image", H.out_text(proc), H.describe(proc))
            for path in sorted(Path(assets).rglob("*")):
                if path.is_file() and path.suffix in (".json", ".txt"):
                    self.assertNotIn("data:image", path.read_text(encoding="utf-8", errors="replace"), str(path))


class PartialRecoveryTest(_Base):
    """AC-C21-6: 委譲先が exit 0 でも回収できなければ exit 1 / partial。"""

    def test_exit_code_is_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, pngs="first")
            self.assertEqual(1, proc.returncode, H.describe(proc))

    def test_status_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, pngs="first")
            self.assertEqual("partial", H.stdout_json(self, proc)["status"], H.describe(proc))

    def test_exactly_one_image_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, pngs="first")
            statuses = [entry["status"] for entry in H.stdout_json(self, proc)["images"]]
            self.assertEqual(1, statuses.count("failed"), H.describe(proc))
            self.assertEqual(1, statuses.count("generated"), H.describe(proc))

    def test_successful_slug_keeps_its_path(self):
        """成功分は回収したまま返し、C01 が部分素材で先へ進めるようにする。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _ = self._run(tmp, pngs="first")
            for entry in H.stdout_json(self, proc)["images"]:
                if entry["status"] == "generated":
                    self.assertTrue((Path(assets) / entry["path"]).is_file(), entry)

    def test_failed_slug_has_no_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, pngs="first")
            for entry in H.stdout_json(self, proc)["images"]:
                if entry["status"] == "failed":
                    self.assertIsNone(entry["path"], entry)

    def test_failure_reason_is_on_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, pngs="first")
            self.assertTrue(H.err_text(proc).strip(), "どの slug が落ちたかが stderr に無い")

    def test_no_recovery_at_all_is_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, pngs="none")
            self.assertEqual(1, proc.returncode, H.describe(proc))

    def test_no_recovery_is_not_reported_as_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, pngs="none")
            data = H.stdout_json(self, proc)
            self.assertNotEqual("skipped", data["status"], H.describe(proc))
            self.assertIsNone(data["skip_reason"], H.describe(proc))


class InvalidPngTest(_Base):
    """AC-C21-7: PNG 署名を持たないファイルは failed 扱いで、素材へコピーしない。"""

    def test_exit_code_is_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, pngs="invalid")
            self.assertEqual(1, proc.returncode, H.describe(proc))

    def test_all_slugs_are_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, pngs="invalid")
            statuses = {entry["status"] for entry in H.stdout_json(self, proc)["images"]}
            self.assertEqual({"failed"}, statuses, H.describe(proc))

    def test_nothing_is_copied_into_assets_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _ = self._run(tmp, pngs="invalid")
            self.assertEqual(
                [], sorted((Path(assets) / "images").glob("*")) if (Path(assets) / "images").exists() else [],
                "壊れた素材をコピーしている:\n" + H.describe(proc),
            )

    def test_signature_check_is_applied_to_a_single_bad_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            proc, assets, _ = self._run(tmp, pngs="invalid", sections=[H.section("intro")])
            self.assertEqual(1, proc.returncode, H.describe(proc))
            images = Path(assets) / "images"
            self.assertFalse(images.exists() and any(images.iterdir()), H.describe(proc))


class DelegateFailureTest(_Base):
    """failure_modes: build-image-prompts.js が非 0 なら exit 1 (skip にしない)。"""

    def test_prompt_builder_failure_is_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, prompts="fail")
            self.assertEqual(1, proc.returncode, H.describe(proc))

    def test_prompt_builder_failure_is_not_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, prompts="fail")
            data = H.stdout_json(self, proc)
            self.assertNotEqual("skipped", data["status"], H.describe(proc))
            self.assertIsNone(data["skip_reason"], H.describe(proc))

    def test_delegate_stderr_is_relayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, prompts="fail")
            self.assertIn("FAIL", H.err_text(proc), "委譲先の FAIL 行が転記されていない")

    def test_generator_is_not_launched_after_prompt_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, log = self._run(tmp, prompts="fail")
            self.assertNotIn("generate-images-codex.js", H.invoked_scripts(log), H.describe(proc))

    def test_zero_prompts_is_exit1(self):
        """algorithm 10: prompt が 1 件も生成されなければ exit 1。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, prompts="none")
            self.assertEqual(1, proc.returncode, H.describe(proc))

    def test_zero_prompts_does_not_launch_the_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, log = self._run(tmp, prompts="none")
            self.assertNotIn("generate-images-codex.js", H.invoked_scripts(log), H.describe(proc))


if __name__ == "__main__":
    unittest.main()

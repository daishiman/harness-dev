"""argv と exit code の契約 — brief argv / exit_codes / algorithm 1-2。

exit 2 は「呼び出し契約違反」であり、**skip (exit 0) へ畳んではならない**。
畳むと『画像が無い理由』が SRG 不在と区別できなくなる (algorithm 2 の理由文)。
"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class RequiredFlagTest(H.BridgeTestCase):
    def test_no_arguments_is_exit2(self):
        proc = H.run([])
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_image_plan_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = H.make_assets_dir(Path(tmp))
            proc = H.run(["--assets-dir", assets], env=H.clean_env(tmp))
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_assets_dir_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = H.write_plan(Path(tmp) / "plan.json", H.plan_payload())
            proc = H.run(["--image-plan", plan], env=H.clean_env(tmp))
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_unknown_flag_is_exit2(self):
        """argv に無い引数を受理しない (受理すると誤記が黙って無視される)。"""
        with tempfile.TemporaryDirectory() as tmp:
            plan = H.write_plan(Path(tmp) / "plan.json", H.plan_payload())
            assets = H.make_assets_dir(Path(tmp))
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--no-such-flag"],
                env=H.clean_env(tmp),
            )
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_force_flag_is_not_part_of_the_contract(self):
        """open_questions: --force 相当は今回入れない (argv 契約を変えない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            plan = H.write_plan(Path(tmp) / "plan.json", H.plan_payload())
            assets = H.make_assets_dir(Path(tmp))
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--force"],
                env=H.clean_env(tmp),
            )
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_dry_run_takes_no_value(self):
        """--dry-run は flag (type: flag)。値を要求しない。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            srg = H.make_srg(tmp)
            bin_dir = H.make_fake_bin(tmp)
            plan = H.write_plan(tmp / "plan.json", H.plan_payload())
            assets = H.make_assets_dir(tmp)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg, "--dry-run"],
                env=H.clean_env(tmp, bin_dir=bin_dir, log=tmp / "log.jsonl"),
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))


class AssetsDirContractTest(H.BridgeTestCase):
    def test_non_directory_assets_dir_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            plan = H.write_plan(tmp / "plan.json", H.plan_payload())
            not_a_dir = tmp / "file.txt"
            not_a_dir.write_text("これはディレクトリではない\n", encoding="utf-8")
            proc = H.run(["--image-plan", plan, "--assets-dir", not_a_dir], env=H.clean_env(tmp))
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_missing_assets_dir_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            plan = H.write_plan(tmp / "plan.json", H.plan_payload())
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", tmp / "nope"], env=H.clean_env(tmp)
            )
            self.assertEqual(2, proc.returncode, H.describe(proc))


class ImagePlanReadabilityTest(H.BridgeTestCase):
    def _run(self, tmp, payload_text):
        tmp = Path(tmp)
        plan = tmp / "plan.json"
        plan.write_text(payload_text, encoding="utf-8")
        assets = H.make_assets_dir(tmp)
        return H.run(["--image-plan", plan, "--assets-dir", assets], env=H.clean_env(tmp))

    def test_missing_plan_file_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            assets = H.make_assets_dir(tmp)
            proc = H.run(
                ["--image-plan", tmp / "nope.json", "--assets-dir", assets], env=H.clean_env(tmp)
            )
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_non_json_plan_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, "これは JSON ではない\n")
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_plan_that_is_a_list_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, json.dumps([H.section("intro")], ensure_ascii=False))
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_empty_sections_is_exit2(self):
        """algorithm 2: sections が空は契約違反 (skip ではない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, json.dumps(H.plan_payload(sections=[]), ensure_ascii=False))
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_missing_sections_key_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = H.plan_payload()
            payload.pop("sections")
            proc = self._run(tmp, json.dumps(payload, ensure_ascii=False))
            self.assertEqual(2, proc.returncode, H.describe(proc))


class RequiredSectionFieldTest(H.BridgeTestCase):
    """algorithm 2: section の必須キー欠落は exit 2。C05 が書く執筆値を捏造しない。"""

    REQUIRED = ("section_id", "heading", "subject", "diagram_structure", "overlay_text", "alt")

    def _exit_code_without(self, key):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            broken = H.section("intro")
            broken.pop(key)
            plan = H.write_plan(tmp / "plan.json", H.plan_payload(sections=[broken, H.section("build")]))
            assets = H.make_assets_dir(tmp)
            bin_dir = H.make_fake_bin(tmp)
            srg = H.make_srg(tmp)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg],
                env=H.clean_env(tmp, bin_dir=bin_dir, log=tmp / "log.jsonl"),
            )
            return proc

    def test_each_required_section_field_missing_is_exit2(self):
        for key in self.REQUIRED:
            with self.subTest(missing=key):
                proc = self._exit_code_without(key)
                self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_contract_violation_is_reported_on_stderr(self):
        proc = self._exit_code_without("subject")
        self.assertTrue(H.err_text(proc).strip(), "契約違反の理由が stderr に無い")

    def test_contract_violation_is_not_folded_into_skip(self):
        proc = self._exit_code_without("alt")
        text = H.out_text(proc)
        self.assertNotIn("srg-absent", text, "契約違反を skip へ畳んでいる")
        self.assertNotIn("runtime-absent", text, "契約違反を skip へ畳んでいる")


class StdinTest(H.BridgeTestCase):
    """brief stdin: 使用しない。読むと非対話経路で詰まる。"""

    def test_stdin_payload_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            plan = H.write_plan(tmp / "plan.json", H.plan_payload())
            assets = H.make_assets_dir(tmp)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets],
                env=H.clean_env(tmp),
                stdin_data='{"noise": true}\n',
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))


if __name__ == "__main__":
    unittest.main()

"""stdout 判定 JSON の形 — brief stdout / stderr。

「skip を成功と偽装しない」は stdout の形で担保される。skip 時も images を全件
列挙し、下流が『何が作られなかったか』を欠測として扱えることを固定する。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


def _sections():
    return [H.section("intro"), H.section("build"), H.section("wrap up")]


class _Base(H.BridgeTestCase):
    def _run(self, tmp, *, srg=True, extra=()):
        tmp = Path(tmp)
        bin_dir = H.make_fake_bin(tmp)
        log = tmp / "log.jsonl"
        srg_root = H.make_srg(tmp) if srg else tmp / "not-srg"
        if not srg:
            srg_root.mkdir(parents=True, exist_ok=True)
        plan = H.write_plan(tmp / "plan.json", H.plan_payload(sections=_sections()))
        assets = H.make_assets_dir(tmp)
        args = ["--image-plan", plan, "--assets-dir", assets]
        if srg:
            args += ["--srg-root", srg_root]
        proc = H.run(args + list(extra), env=H.clean_env(tmp, bin_dir=bin_dir, srg_root=(None if srg else srg_root), log=log))
        return proc, assets, log


class TopLevelShapeTest(_Base):
    def test_stdout_is_a_single_json_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            H.stdout_json(self, proc)

    def test_all_declared_keys_are_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            data = H.stdout_json(self, proc)
            for key in H.STDOUT_KEYS:
                self.assertIn(key, data, "stdout の宣言キー {} が無い".format(key))

    def test_status_is_from_the_declared_enum(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            data = H.stdout_json(self, proc)
            self.assertIn(data["status"], ("generated", "partial", "skipped", "dry-run"))

    def test_runtime_block_reports_node_and_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            runtime = H.stdout_json(self, proc)["runtime"]
            self.assertIsInstance(runtime, dict)
            self.assertIn("node", runtime)
            self.assertIn("codex", runtime)

    def test_images_entries_have_the_declared_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            for entry in H.stdout_json(self, proc)["images"]:
                for key in H.IMAGE_KEYS:
                    self.assertIn(key, entry, "images の宣言キー {} が無い".format(key))

    def test_images_lists_every_section_in_plan_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            images = H.stdout_json(self, proc)["images"]
            self.assertEqual(
                [s["section_id"] for s in _sections()],
                [entry["section_id"] for entry in images],
                H.describe(proc),
            )

    def test_delegated_commands_is_a_list_of_argv_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            commands = H.stdout_json(self, proc)["delegated_commands"]
            self.assertIsInstance(commands, list)
            for command in commands:
                self.assertIsInstance(command, list, "argv 列でない要素がある: {!r}".format(command))

    def test_recovered_path_is_relative_to_assets_dir(self):
        """brief stdout: path は assets-dir 相対 (絶対パスを焼くと成果物が移動できない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _ = self._run(tmp)
            for entry in H.stdout_json(self, proc)["images"]:
                if entry.get("path"):
                    self.assertFalse(
                        Path(entry["path"]).is_absolute(), "path が絶対パス: {}".format(entry["path"])
                    )
                    self.assertTrue((Path(assets) / entry["path"]).is_file(), entry["path"])

    def test_human_prose_goes_to_stderr_not_stdout(self):
        """brief stderr: 人間向けの文はここだけ。stdout は機械可読 1 個だけ。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            text = H.out_text(proc)
            self.assertTrue(text.lstrip().startswith("{"), H.describe(proc))
            self.assertTrue(text.rstrip().endswith("}"), H.describe(proc))


class SkipShapeTest(_Base):
    def test_skip_lists_all_sections_as_skipped(self):
        """brief stdout: skip 時も images を全件 skipped で列挙する。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, srg=False)
            data = H.stdout_json(self, proc)
            self.assertEqual("skipped", data["status"], H.describe(proc))
            self.assertEqual(
                ["skipped"] * len(_sections()),
                [entry["status"] for entry in data["images"]],
                H.describe(proc),
            )

    def test_skip_reason_is_from_the_declared_enum(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, srg=False)
            self.assertIn(H.stdout_json(self, proc)["skip_reason"], H.SKIP_REASONS)

    def test_skip_has_no_recovered_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, srg=False)
            for entry in H.stdout_json(self, proc)["images"]:
                self.assertIsNone(entry["path"], "skip なのに path がある: {}".format(entry))

    def test_skip_is_distinguishable_from_generated(self):
        """『skip を成功と偽装しない』— exit code が同じ 0 でも status が違う。"""
        with tempfile.TemporaryDirectory() as tmp:
            skipped, _, _ = self._run(tmp, srg=False)
        with tempfile.TemporaryDirectory() as tmp:
            generated, _, _ = self._run(tmp)
        self.assertEqual(0, skipped.returncode, H.describe(skipped))
        self.assertEqual(0, generated.returncode, H.describe(generated))
        self.assertNotEqual(
            H.stdout_json(self, skipped)["status"], H.stdout_json(self, generated)["status"]
        )

    def test_skip_reason_is_null_when_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            data = H.stdout_json(self, proc)
            self.assertIsNone(data["skip_reason"], H.describe(proc))
            self.assertIsNone(data["skip_detail"], H.describe(proc))

    def test_skip_reason_is_also_explained_on_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp, srg=False)
            self.assertTrue(H.err_text(proc).strip(), "skip 宣言の理由が stderr に無い")


class SlugContractTest(_Base):
    def test_slug_follows_sec_nn_kebab_rule(self):
        """algorithm 6: sec-NN-<section_id の kebab 化>、番号は出現順 1 始まり。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            images = H.stdout_json(self, proc)["images"]
            expected = [H.expected_slug(i, s["section_id"]) for i, s in enumerate(_sections(), 1)]
            self.assertEqual(expected, [entry["slug"] for entry in images], H.describe(proc))

    def test_slug_matches_srg_slug_pattern(self):
        """SRG の ^[a-z0-9]+(?:-[a-z0-9]+)*$ に適合させる。"""
        import re

        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _ = self._run(tmp)
            for entry in H.stdout_json(self, proc)["images"]:
                self.assertRegex(entry["slug"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


if __name__ == "__main__":
    unittest.main()

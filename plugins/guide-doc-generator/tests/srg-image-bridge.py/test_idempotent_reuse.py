"""既存 PNG の冪等スキップ — algorithm 12 / AC-C21-11 / P03 Y-01。

これは failure_modes ではなく**通常の正規ステップ**である。画像生成は非決定論
(gpt-image-2 に seed が無い) なので、既存素材の再生成は同一入力から別バイトの成果物を生む。
素材を確定させたうえで再現性の鎖を C11 側へ閉じるための再利用である。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


class _Base(H.BridgeTestCase):
    SECTIONS = ("intro", "build")

    def _sections(self):
        return [H.section(sid) for sid in self.SECTIONS]

    def _slugs(self):
        return [H.expected_slug(i, sid) for i, sid in enumerate(self.SECTIONS, 1)]

    def _run(self, tmp, *, preplace=(), pngs="all", extra=()):
        tmp = Path(tmp)
        srg = H.make_srg(tmp)
        bin_dir = H.make_fake_bin(tmp)
        log = tmp / "log.jsonl"
        plan = H.write_plan(tmp / "plan.json", H.plan_payload(sections=self._sections()))
        assets = H.make_assets_dir(tmp)
        placed = {}
        for slug, data in preplace:
            placed[slug] = H.place_existing_png(assets, slug, data).read_bytes()
        proc = H.run(
            ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg, *extra],
            env=H.clean_env(tmp, bin_dir=bin_dir, log=log, **{H.ENV_PNGS: pngs}),
        )
        return proc, assets, log, placed


class FullReuseTest(_Base):
    """AC-C21-11: 全 slug が既存で満たされたら委譲先を一切起動しない。"""

    def _preplace_all(self):
        return [(slug, b"\x89PNG\r\n\x1a\n" + b"existing-" + slug.encode()) for slug in self._slugs()]

    def test_exit_code_is_zero_and_status_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _, _ = self._run(tmp, preplace=self._preplace_all())
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual("generated", H.stdout_json(self, proc)["status"], H.describe(proc))

    def test_generator_is_not_launched(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, log, _ = self._run(tmp, preplace=self._preplace_all())
            self.assertNotIn(
                "generate-images-codex.js", H.invoked_scripts(log), "追加課金が起きる:\n" + H.describe(proc)
            )

    def test_delegated_commands_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _, _ = self._run(tmp, preplace=self._preplace_all())
            self.assertEqual([], H.stdout_json(self, proc)["delegated_commands"], H.describe(proc))

    def test_existing_bytes_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _, placed = self._run(tmp, preplace=self._preplace_all())
            for slug, before in placed.items():
                after = (Path(assets) / "images" / (slug + ".png")).read_bytes()
                self.assertEqual(before, after, "既存 PNG が書き換わった: {}".format(slug))

    def test_images_report_the_existing_files_as_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _, _ = self._run(tmp, preplace=self._preplace_all())
            for entry in H.stdout_json(self, proc)["images"]:
                self.assertEqual("generated", entry["status"], entry)
                self.assertTrue((Path(assets) / entry["path"]).is_file(), entry)


class PartialReuseTest(_Base):
    def _preplace_first(self):
        slug = self._slugs()[0]
        return [(slug, H.png_bytes("kept-" + slug))]

    def test_only_missing_slugs_are_delegated(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, log, _ = self._run(tmp, preplace=self._preplace_first())
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertIn("generate-images-codex.js", H.invoked_scripts(log), H.describe(proc))

    def test_existing_slug_is_not_regenerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, assets, _, placed = self._run(tmp, preplace=self._preplace_first())
            for slug, before in placed.items():
                after = (Path(assets) / "images" / (slug + ".png")).read_bytes()
                self.assertEqual(before, after, "既存 slug を再生成した: {}".format(slug))

    def test_all_slugs_end_up_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _, _, _ = self._run(tmp, preplace=self._preplace_first())
            statuses = {entry["status"] for entry in H.stdout_json(self, proc)["images"]}
            self.assertEqual({"generated"}, statuses, H.describe(proc))


class InvalidExistingPngTest(_Base):
    """署名を満たさない既存ファイルは『回収済み』とみなさない。"""

    def test_invalid_existing_file_triggers_delegation(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = [(slug, "壊れたファイル\n".encode("utf-8")) for slug in self._slugs()]
            proc, _, log, _ = self._run(tmp, preplace=broken)
            self.assertIn("generate-images-codex.js", H.invoked_scripts(log), H.describe(proc))

    def test_invalid_existing_file_is_replaced_by_a_valid_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = [(slug, "壊れたファイル\n".encode("utf-8")) for slug in self._slugs()]
            proc, assets, _, _ = self._run(tmp, preplace=broken)
            self.assertEqual(0, proc.returncode, H.describe(proc))
            for slug in self._slugs():
                data = (Path(assets) / "images" / (slug + ".png")).read_bytes()
                self.assertTrue(data.startswith(H.PNG_SIGNATURE), slug)


class DryRunDoesNotReuseTest(_Base):
    """--dry-run は生成しないので、既存 PNG があっても status は dry-run のまま。"""

    def test_status_stays_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            preplace = [(slug, H.png_bytes(slug)) for slug in self._slugs()]
            proc, _, _, _ = self._run(tmp, preplace=preplace, extra=["--dry-run"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual("dry-run", H.stdout_json(self, proc)["status"], H.describe(proc))

    def test_existing_bytes_are_unchanged_in_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            preplace = [(slug, H.png_bytes(slug)) for slug in self._slugs()]
            proc, assets, _, placed = self._run(tmp, preplace=preplace, extra=["--dry-run"])
            for slug, before in placed.items():
                self.assertEqual(
                    before, (Path(assets) / "images" / (slug + ".png")).read_bytes(), slug
                )


if __name__ == "__main__":
    unittest.main()

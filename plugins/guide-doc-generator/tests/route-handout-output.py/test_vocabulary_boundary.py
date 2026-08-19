"""種別語彙の単一正本 (C23) への境界 — AC-C19-08 / 09 / 10、algorithm 4、R20 / C42。"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


class VocabularyViolationTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_unknown_doc_type_is_exit1_with_one_stderr_line(self):
        """AC-C19-08: 語彙違反は exit 1 で stderr 1 行 (先頭に [route-handout-output])。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(
                Path(tmp) / "c.json",
                H.normalized_config(self, doc_type=H.unknown_doc_type(self)),
            )
            proc = H.run(["--config", cfg, "--out-dir", root])
            self.assertEqual(1, proc.returncode, H.describe(proc))
            lines = [l for l in H.err_text(proc).splitlines() if l.strip()]
            self.assertEqual(1, len(lines), "1 違反 1 行でない: {}".format(lines))
            self.assertTrue(lines[0].startswith(H.STDERR_PREFIX), lines[0])
            self.assertEqual([], list(root.iterdir()), "語彙違反でディレクトリを作った")

    def test_alias_is_not_accepted_as_doc_type(self):
        """algorithm 4: doc_type は slug で照合する (alias 解決は C23 の CLI 側の話)。

        alias をそのままディレクトリ名へ使えてしまうと <種別> の表現が 2 通りになる。
        """
        aliases = [
            a
            for entry in H.vocabulary_entries(self)
            for a in (entry.get("aliases") or [])
        ]
        if not aliases:
            self.skipTest("語彙正本に alias が無い")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(
                Path(tmp) / "c.json", H.normalized_config(self, doc_type=aliases[0])
            )
            proc = H.run(["--config", cfg, "--out-dir", root])
            self.assertIn(proc.returncode, (0, 1), H.describe(proc))
            if proc.returncode == 0:
                name = H.resolved_path(self, proc).name
                self.assertNotIn(
                    aliases[0],
                    name,
                    "alias がそのままディレクトリ名の <種別> になった: {}".format(name),
                )

    def test_purpose_field_is_not_matched_against_vocabulary(self):
        """AC-C19-08: purpose (自由記述) は語彙照合の対象にしない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(
                Path(tmp) / "c.json",
                H.normalized_config(self, purpose="語彙に無い自由記述をここへ書いてよい"),
            )
            proc = H.run(["--config", cfg, "--out-dir", root])
            self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_purpose_value_does_not_leak_into_directory_name(self):
        """<種別> は doc_type 由来の dir_token であって purpose ではない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(
                Path(tmp) / "c.json", H.normalized_config(self, purpose="秘密の目的テキスト")
            )
            proc = H.run(["--config", cfg, "--out-dir", root])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertNotIn("秘密の目的テキスト", H.resolved_path(self, proc).name)


class CatalogUnavailableTest(unittest.TestCase):
    """AC-C19-09 / failure_modes: C23 不在なら語彙を推測せず fail-closed。"""

    def setUp(self):
        H.require_script(self)

    def test_missing_c23_module_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out"
            target.mkdir()
            root = H.make_fixture_tree(self, Path(tmp), include_preset=False)
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(
                ["--config", cfg, "--out-dir", target], script=H.fixture_script(root)
            )
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertIn(H.STDERR_PREFIX, H.err_text(proc), H.describe(proc))
            self.assertEqual([], list(target.iterdir()), "C23 不在でディレクトリを作った")

    def test_broken_c23_module_is_exit2(self):
        """import できても呼び出しが失敗する場合も exit 2 (fail-closed)。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out"
            target.mkdir()
            root = H.make_fixture_tree(self, Path(tmp))
            (root / "scripts" / H.PRESET_SCRIPT.name).write_text(
                "raise RuntimeError('broken C23')\n", encoding="utf-8"
            )
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(
                ["--config", cfg, "--out-dir", target], script=H.fixture_script(root)
            )
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertEqual([], list(target.iterdir()))

    def test_missing_catalog_file_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out"
            target.mkdir()
            root = H.make_fixture_tree(self, Path(tmp))
            (root / H.CATALOG_RELPATH).unlink()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(
                ["--config", cfg, "--out-dir", target], script=H.fixture_script(root)
            )
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertEqual([], list(target.iterdir()))

    def test_catalog_change_changes_the_recorded_dir_token(self):
        """語彙は正本にしか無い: カタログ側の dir_token を変えると来歴も変わる。

        R25 でディレクトリ名から種別トークンが外れたため、カタログ由来である
        ことの観測点は命名ではなく来歴マーカー (.handout-route.json) になった。
        命名は変わらないこと自体も併せて固定する。
        """
        import json

        slug = H.any_doc_type(self)

        def mutate_catalog(root: Path):
            path = root / H.CATALOG_RELPATH
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry in data["vocabulary"]:
                if entry["slug"] == slug:
                    entry["dir_token"] = "retokened"
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out"
            target.mkdir()
            root = H.make_fixture_tree(self, Path(tmp))
            mutate_catalog(root)
            cfg = H.write_config(
                Path(tmp) / "c.json", H.normalized_config(self, doc_type=slug)
            )
            proc = H.run(
                ["--config", cfg, "--out-dir", target], script=H.fixture_script(root)
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))
            resolved = H.resolved_path(self, proc)
            marker = resolved / H.ROUTE_MARKER
            if not marker.is_file():
                self.fail("来歴マーカー {} が無い".format(marker))
            blob = "\n".join(H.flatten_strings(json.loads(marker.read_text("utf-8"))))
            self.assertIn(
                "retokened",
                blob,
                "カタログの dir_token が来歴へ反映されていない: {}".format(blob),
            )
            self.assertTrue(resolved.name.startswith(H.name_prefix(self)), resolved.name)
            self.assertNotIn("retokened", resolved.name, "命名に種別が漏れている")


class SingleAccessPathTest(unittest.TestCase):
    """AC-C19-10: C23 への到達は importlib 経由の 1 経路だけ (subprocess 0 件)。"""

    def setUp(self):
        H.require_script(self)

    def test_source_has_no_subprocess(self):
        source = H.read_source(self)
        self.assertNotIn("subprocess", source, "subprocess への参照がある")
        for token in ("os.system", "os.popen", "os.exec", "os.spawn"):
            self.assertNotIn(token, source, "プロセス起動 API {} がある".format(token))

    def test_source_reaches_c23_via_spec_from_file_location_once(self):
        source = H.read_source(self)
        self.assertIn("spec_from_file_location", source, "importlib 経路が無い")
        self.assertEqual(
            1,
            source.count("spec_from_file_location"),
            "C23 への到達経路が 1 つでない",
        )
        self.assertIn(H.PRESET_SCRIPT.name, source, "C23 の実体名への参照が無い")


if __name__ == "__main__":
    unittest.main()

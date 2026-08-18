"""モード契約 (argv / exit code / --list / --format) — AC-C23-01 / 10 と exit 2 系。"""

import json
import unittest

import _harness as H


class ListModeTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_list_text_emits_catalog_order_slugs(self):
        """AC-C23-01: --list --format text が catalog 記載順の slug を 1 行 1 件で出す。"""
        expected = H.slugs(self)
        proc = H.run(["--list", "--format", "text"])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        lines = H.out_text(proc).splitlines()
        self.assertEqual(expected, lines, H.describe(proc))

    def test_list_size_is_eight(self):
        """AC-C23-01: 用途語彙は 8 件 (語彙そのものは列挙せず件数だけを固定する)。"""
        proc = H.run(["--list", "--format", "text"])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertEqual(
            H.EXPECTED_VOCABULARY_SIZE, len(H.out_text(proc).splitlines()), H.describe(proc)
        )

    def test_list_json_entry_shape_and_order(self):
        """--list --format json は slug/label_ja/dir_token/aliases/preset_defined を記載順で返す。"""
        catalog = H.load_catalog(self)
        proc = H.run(["--list", "--format", "json"])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        payload = json.loads(H.out_text(proc))
        self.assertIsInstance(payload, list, H.describe(proc))
        self.assertEqual(H.slugs(self, catalog), [e["slug"] for e in payload])
        for entry in payload:
            self.assertEqual(
                {"slug", "label_ja", "dir_token", "aliases", "preset_defined"},
                set(entry.keys()),
                entry,
            )
            self.assertTrue(entry["preset_defined"], entry)

    def test_dir_tokens_and_aliases_are_globally_unique(self):
        """語彙正本の一意性契約 (手順 4c/4d/4e) が実データで成立している。"""
        entries = H.vocabulary_entries(self)
        for field in ("slug", "dir_token"):
            values = [e[field] for e in entries]
            self.assertEqual(len(values), len(set(values)), "{} が重複".format(field))
        aliases = [a for e in entries for a in e["aliases"]]
        self.assertEqual(len(aliases), len(set(aliases)), "aliases が slug 横断で重複")


class ModeArityTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_no_mode_is_exit_2(self):
        """AC-C23-10: モード 0 個は起動不正 (exit 2)。"""
        proc = H.run([])
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))

    def test_two_modes_is_exit_2(self):
        """AC-C23-10: モード 2 個同時指定も起動不正 (exit 2)。"""
        proc = H.run(["--list", "--purpose", H.LECTURE_SLUG])
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))

    def test_three_modes_is_exit_2(self):
        proc = H.run(["--list", "--audit-duplication", "--purpose", H.LECTURE_SLUG])
        self.assertEqual(2, proc.returncode, H.describe(proc))


class LaunchFailureTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_unknown_format_value_is_exit_2(self):
        """--format の enum 外は起動不正 (exit 2)。"""
        proc = H.run(["--list", "--format", "yaml"])
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))

    def test_missing_catalog_path_is_exit_2(self):
        """--catalog が読めないときは exit 2 (データ違反ではない)。"""
        proc = H.run(["--list", "--catalog", "/nonexistent/handout-purposes.json"])
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))

    def test_stdin_is_ignored(self):
        """非対話 script: stdin が接続されていても無視して通常どおり終わる。"""
        proc = H.run(["--list", "--format", "text"], stdin_data="lecture\nagenda\n")
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertEqual(H.slugs(self), H.out_text(proc).splitlines(), H.describe(proc))


if __name__ == "__main__":
    unittest.main()

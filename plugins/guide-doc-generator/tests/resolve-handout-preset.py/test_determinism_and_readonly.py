"""再現性と write_scope 空の実測 — AC-C23-11 / 12 と stdout の書式契約。"""

import json
import unittest

import _harness as H


class DeterminismTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_repeated_purpose_is_byte_identical(self):
        """AC-C23-11: 同一 catalog に対する 2 回実行の stdout がバイト一致。"""
        args = ["--purpose", H.LECTURE_SLUG]
        first = H.run(args)
        second = H.run(args)
        self.assertEqual(0, first.returncode, H.describe(first))
        self.assertEqual(0, second.returncode, H.describe(second))
        self.assertEqual(first.stdout, second.stdout)

    def test_repeated_list_is_byte_identical(self):
        first = H.run(["--list"])
        second = H.run(["--list"])
        self.assertEqual(0, first.returncode, H.describe(first))
        self.assertEqual(first.stdout, second.stdout)


class JsonFormattingTest(unittest.TestCase):
    """stdout 契約: ensure_ascii=false / indent=2 / sort_keys=true / 末尾改行 1 個 / LF 固定。"""

    def setUp(self):
        H.require_script(self)

    def _assert_canonical(self, proc):
        self.assertEqual(0, proc.returncode, H.describe(proc))
        raw = proc.stdout
        self.assertNotIn(b"\r", raw, "CRLF が混じっている")
        self.assertTrue(raw.endswith(b"\n"), "末尾改行が無い")
        self.assertFalse(raw.endswith(b"\n\n"), "末尾改行が 2 個以上")
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(H.canonical_json_bytes(payload), raw, "整形が契約と一致しない")

    def test_purpose_json_is_canonical(self):
        self._assert_canonical(H.run(["--purpose", H.LECTURE_SLUG]))

    def test_list_json_is_canonical(self):
        self._assert_canonical(H.run(["--list", "--format", "json"]))

    def test_non_ascii_is_not_escaped(self):
        """ensure_ascii=false: 日本語ラベルがそのまま出る。"""
        proc = H.run(["--list", "--format", "json"])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertNotIn("\\u", H.out_text(proc), "非 ASCII がエスケープされている")


class ReadOnlyTest(unittest.TestCase):
    """AC-C23-12: 実行後に catalog が無変更 (write_scope が空であることの実測)。"""

    def setUp(self):
        H.require_script(self)

    def test_catalog_untouched_after_all_modes(self):
        H.require_file(self, H.CATALOG, "C23")
        before_bytes = H.CATALOG.read_bytes()
        before_stat = H.CATALOG.stat()

        H.run(["--list"])
        H.run(["--purpose", H.LECTURE_SLUG])
        H.run(["--purpose", H.LECTURE_SLUG, "--presentation-order", "demo_first"])
        H.run(["--audit-duplication"])
        H.run(["--purpose", "zzz-not-a-purpose"])

        self.assertEqual(before_bytes, H.CATALOG.read_bytes(), "catalog の内容が変わった")
        self.assertEqual(before_stat.st_mtime_ns, H.CATALOG.stat().st_mtime_ns, "catalog の mtime が変わった")

    def test_config_dir_snapshot_unchanged(self):
        """config/ 配下のどのファイルにも書き戻さない。"""
        config_dir = H.PLUGIN_ROOT / "config"
        if not config_dir.is_dir():
            self.fail("config/ が未存在: {}".format(config_dir))
        snapshot = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(config_dir.rglob("*")) if p.is_file()}
        H.run(["--list"])
        H.run(["--purpose", H.LECTURE_SLUG])
        for path, (data, mtime) in snapshot.items():
            self.assertEqual(data, path.read_bytes(), path)
            self.assertEqual(mtime, path.stat().st_mtime_ns, path)


if __name__ == "__main__":
    unittest.main()

"""--audit-duplication (C42 のゲート実体) — AC-C23-08 / 09 と除外規則。"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class AuditOnRealTreeTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_clean_plugin_tree_has_no_violation(self):
        """AC-C23-08: 実 plugin ツリーで {"scanned":N,"violations":[]} / exit 0。"""
        proc = H.run(["--audit-duplication"])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        payload = json.loads(H.out_text(proc))
        self.assertEqual([], payload["violations"], H.describe(proc))
        self.assertGreater(payload["scanned"], 0, H.describe(proc))
        self.assertEqual({"scanned", "violations"}, set(payload.keys()), payload)


class AuditOnFixtureTreeTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = H.make_fixture_root(self, self.tmp)
        self.slugs = H.slugs(self)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, relpath, body):
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def test_fixture_tree_is_clean_baseline(self):
        proc = H.run_in_root(self.root, ["--audit-duplication"])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertEqual([], json.loads(H.out_text(proc))["violations"], H.describe(proc))

    def test_three_slugs_in_one_file_is_a_violation(self):
        """AC-C23-09: 語彙 3 種類が同一ファイルに現れると E-VOCAB-DUPLICATED / file:line / exit 1。"""
        self._write(
            "scripts/leaky.py",
            "PURPOSES = {}\n".format(json.dumps(self.slugs[:3])),
        )
        proc = H.run_in_root(self.root, ["--audit-duplication"])
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))
        stderr = H.err_text(proc).replace("\\", "/")
        self.assertIn("E-VOCAB-DUPLICATED", stderr, H.describe(proc))
        self.assertRegex(stderr, r"scripts/leaky\.py:\d+", H.describe(proc))

    def test_two_slugs_in_one_file_is_not_a_violation(self):
        """閾値は 3 種類。2 種類までは再定義とみなさない。"""
        self._write("scripts/borderline.py", "A = {}\n".format(json.dumps(self.slugs[:2])))
        proc = H.run_in_root(self.root, ["--audit-duplication"])
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_tests_directory_is_excluded(self):
        """failure_modes: tests/ 配下のフィクスチャは違反としない。"""
        self._write("tests/fixture_vocab.py", "ALL = {}\n".format(json.dumps(self.slugs)))
        proc = H.run_in_root(self.root, ["--audit-duplication"])
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_references_directory_is_excluded(self):
        """references/ の規範文書は語彙を説明として書いてよい。"""
        self._write("references/vocab.md", "\n".join("- " + s for s in self.slugs) + "\n")
        proc = H.run_in_root(self.root, ["--audit-duplication"])
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_catalog_itself_is_excluded(self):
        """語彙正本そのものは当然除外される (ベースラインが緑であることで担保)。"""
        proc = H.run_in_root(self.root, ["--audit-duplication"])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertGreater(json.loads(H.out_text(proc))["scanned"], 0, H.describe(proc))

    def test_allowlist_suppresses_violation(self):
        """config/vocabulary-audit-allowlist.json に列挙したパスは除外される。"""
        self._write("scripts/allowed.py", "A = {}\n".format(json.dumps(self.slugs[:3])))
        self._write(
            "config/vocabulary-audit-allowlist.json",
            json.dumps({"paths": ["scripts/allowed.py"]}, ensure_ascii=False, indent=2) + "\n",
        )
        proc = H.run_in_root(self.root, ["--audit-duplication"])
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_scan_targets_markdown_and_json(self):
        """走査対象は *.py / *.md / *.json / *.yaml。"""
        self._write("agents/leaky.md", "\n".join(self.slugs[:3]) + "\n")
        proc = H.run_in_root(self.root, ["--audit-duplication"])
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertIn("E-VOCAB-DUPLICATED", H.err_text(proc), H.describe(proc))

    def test_explicit_root_flag_is_honored(self):
        """--root で走査起点を差し替えられる。"""
        other = self.tmp / "other-tree"
        (other / "scripts").mkdir(parents=True, exist_ok=True)
        (other / "scripts" / "leaky.py").write_text(
            "A = {}\n".format(json.dumps(self.slugs[:3])), encoding="utf-8"
        )
        proc = H.run_in_root(self.root, ["--audit-duplication", "--root", str(other)])
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertIn("E-VOCAB-DUPLICATED", H.err_text(proc), H.describe(proc))


if __name__ == "__main__":
    unittest.main()

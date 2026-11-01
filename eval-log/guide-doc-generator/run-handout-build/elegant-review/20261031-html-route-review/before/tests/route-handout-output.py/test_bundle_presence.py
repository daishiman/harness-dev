"""同梱 4 点の存在検査と writer 注記 — AC-C19-13 / 14 / 19、algorithm 10。

同梱 4 点の固定名と writer の割り当ては _harness.BUNDLE_WRITERS に 1 箇所だけ置いてある
(正本は script-brief-C19.json bundle_writers / P03 Y-04)。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


def _create(tc, tmp):
    root = Path(tmp) / "out"
    root.mkdir(exist_ok=True)
    cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(tc))
    proc = H.run(["--config", cfg, "--out-dir", root, "--place-config"])
    tc.assertEqual(0, proc.returncode, H.describe(proc))
    return root, cfg, H.resolved_path(tc, proc)


def _fill_bundle(target: Path):
    """C11 / C01 が書く 2 点を、他 component の代役として置く。"""
    (target / "handout.html").write_text("<html></html>\n", encoding="utf-8")
    (target / "README.md").write_text("# 資料\n", encoding="utf-8")


class NormalRunPresenceTest(unittest.TestCase):
    """algorithm 10: mkdir 直後は handout.html / README.md が absent でも exit 0。"""

    def setUp(self):
        H.require_script(self)

    def test_fresh_run_is_exit0_even_though_two_items_are_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, target = _create(self, tmp)
            self.assertFalse((target / "handout.html").exists())
            self.assertFalse((target / "README.md").exists())

    def test_stdout_lists_all_four_items_with_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg, "--out-dir", root, "--place-config"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            for name in H.SELF_WRITTEN:
                H.assert_bundle_state(self, proc, name, "present")
            for name in ("handout.html", "README.md"):
                H.assert_bundle_state(self, proc, name, "absent")

    def test_stdout_annotates_the_writer_of_each_item(self):
        """algorithm 10: どの component が書いたものを検査しているかが読めること。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg, "--out-dir", root, "--place-config"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            lines = H.bundle_lines(self, proc)
            for name, writer in H.BUNDLE_WRITERS:
                self.assertIn(
                    writer,
                    lines[name],
                    "{} の行に writer {} の注記が無い: {!r}".format(name, writer, lines[name]),
                )

    def test_assets_without_place_config_is_absent_config(self):
        """--place-config 無しなら handout-config.json は absent (C19 が勝手に置かない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg, "--out-dir", root])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            H.assert_bundle_state(self, proc, "handout-config.json", "absent")
            H.assert_bundle_state(self, proc, "assets", "present")


class CheckOnlyTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_check_only_creates_nothing(self):
        """AC-C19-14: --check-only 実行後にディレクトリが新規作成されていない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            before = H.tree_snapshot(root)
            proc = H.run(["--config", cfg, "--out-dir", root, "--check-only"])
            self.assertIn(proc.returncode, (0, 1), H.describe(proc))
            self.assertEqual(before, H.tree_snapshot(root), "--check-only が書き込みを行った")

    def test_check_only_on_complete_bundle_is_exit0(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, cfg, target = _create(self, tmp)
            _fill_bundle(target)
            proc = H.run(["--config", cfg, "--out-dir", root, "--check-only"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            for name in H.BUNDLE_NAMES:
                H.assert_bundle_state(self, proc, name, "present")

    def test_check_only_lists_each_missing_item_on_stderr(self):
        """AC-C19-13: 欠落 1 点ごとに exit 1 で stderr へ列挙される。"""
        for missing, _writer in H.BUNDLE_WRITERS:
            with self.subTest(missing=missing):
                with tempfile.TemporaryDirectory() as tmp:
                    root, cfg, target = _create(self, tmp)
                    _fill_bundle(target)
                    victim = target / missing
                    if victim.is_dir():
                        victim.rmdir()
                    else:
                        victim.unlink()
                    proc = H.run(["--config", cfg, "--out-dir", root, "--check-only"])
                    self.assertEqual(1, proc.returncode, H.describe(proc))
                    err = H.err_text(proc)
                    self.assertIn(H.STDERR_PREFIX, err, H.describe(proc))
                    self.assertIn(missing, err, "欠落 {} が列挙されていない".format(missing))

    def test_check_only_reports_all_missing_items_at_once(self):
        """fail-closed の充足ゲートは最初の 1 件で止まらず列挙する。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, cfg, target = _create(self, tmp)
            proc = H.run(["--config", cfg, "--out-dir", root, "--check-only"])
            self.assertEqual(1, proc.returncode, H.describe(proc))
            err = H.err_text(proc)
            for missing in ("handout.html", "README.md"):
                self.assertIn(missing, err, "欠落 {} が列挙されていない".format(missing))

    def test_ordering_contradiction_is_not_created(self):
        """AC-C19-19: 同じディレクトリが通常実行では exit 0、--check-only では exit 1。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            created = H.run(["--config", cfg, "--out-dir", root, "--place-config"])
            self.assertEqual(0, created.returncode, H.describe(created))
            checked = H.run(["--config", cfg, "--out-dir", root, "--check-only"])
            self.assertEqual(1, checked.returncode, H.describe(checked))
            self.assertEqual(
                H.resolved_path(self, created),
                H.resolved_path(self, checked),
                "--check-only が別のディレクトリを見ている",
            )

    def test_check_only_does_not_delete_existing_files(self):
        """collision_rule (5): 既存ファイルの削除を行わない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, cfg, target = _create(self, tmp)
            extra = target / "user-note.txt"
            extra.write_text("利用者のメモ\n", encoding="utf-8")
            H.run(["--config", cfg, "--out-dir", root, "--check-only"])
            self.assertTrue(extra.is_file(), "--check-only が既存ファイルを消した")

    def test_check_only_ignores_unrelated_extra_files(self):
        """同梱 4 点以外の存在は充足判定に影響しない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, cfg, target = _create(self, tmp)
            _fill_bundle(target)
            (target / "notes.md").write_text("メモ\n", encoding="utf-8")
            proc = H.run(["--config", cfg, "--out-dir", root, "--check-only"])
            self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_check_only_rejects_a_file_where_assets_dir_is_expected(self):
        """assets/ はディレクトリであることが同梱物の条件。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, cfg, target = _create(self, tmp)
            _fill_bundle(target)
            (target / "assets").rmdir()
            (target / "assets").write_text("ディレクトリではない\n", encoding="utf-8")
            proc = H.run(["--config", cfg, "--out-dir", root, "--check-only"])
            self.assertEqual(1, proc.returncode, H.describe(proc))


class BundleNamesAreFixedTest(unittest.TestCase):
    """failure_modes: 本体名は index.html ではなく handout.html に固定 (hook 誤発火の回避)。"""

    def setUp(self):
        H.require_script(self)

    def test_index_html_does_not_satisfy_the_html_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, cfg, target = _create(self, tmp)
            (target / "index.html").write_text("<html></html>\n", encoding="utf-8")
            (target / "README.md").write_text("# 資料\n", encoding="utf-8")
            proc = H.run(["--config", cfg, "--out-dir", root, "--check-only"])
            self.assertEqual(1, proc.returncode, H.describe(proc))
            self.assertIn("handout.html", H.err_text(proc), H.describe(proc))

    def test_source_does_not_treat_index_html_as_the_body(self):
        source = H.read_source(self)
        self.assertNotIn("index.html", source, "本体名として index.html が現れている")


if __name__ == "__main__":
    unittest.main()

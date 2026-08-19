# -*- coding: utf-8 -*-
"""argv と exit code の契約 (script-brief-C20.json#argv / #exit_codes / algorithm A1)。

exit 2 は「起動側の不正」だけに割り当てられており、抽出の失敗 (exit 1) と
混ざらないことをここで固定する。AC-C20-11 / AC-C20-14 を含む。
"""

import os
import unittest

import _harness as H


class ArgvContract(H.C20TestCase):

    # ---- --html ----------------------------------------------------------

    def test_no_args_is_exit2(self):
        """--html 未指定は exit 2。"""
        self.assert_exit(self.run_cli(), 2)

    def test_out_without_html_is_exit2(self):
        """--out だけ与えても --html 必須は緩まない。"""
        html = self.write_html()
        self.assert_exit(self.run_cli("--out", self.out), 2)
        self.assertFalse(self.out.exists())
        self.assertTrue(html.exists())

    def test_missing_html_file_is_exit2(self):
        res = self.run_cli("--html", self.tmp / "no-such.html", "--out", self.out)
        self.assert_exit(res, 2)
        self.assert_not_written(self.out)

    def test_unreadable_html_is_exit2(self):
        path = self.write_html()
        os.chmod(path, 0o000)
        try:
            res = self.run_cli("--html", path, "--out", self.out)
        finally:
            os.chmod(path, 0o644)
        self.assert_exit(res, 2)

    def test_html_directory_is_exit2(self):
        d = self.tmp / "a-directory.html"
        d.mkdir()
        self.assert_exit(self.run_cli("--html", d, "--out", self.out), 2)

    def test_unknown_flag_is_exit2(self):
        path = self.write_html()
        self.assert_exit(self.run_cli("--html", path, "--no-such-flag"), 2)

    # ---- --out / --report の同一 realpath (AC-C20-11) ----------------------

    def test_out_same_path_as_html_is_exit2(self):
        """AC-C20-11: --out に --html と同じパスを与えたら exit 2、--html は無変更。"""
        path = self.write_html()
        before = path.read_bytes()
        res = self.run_cli("--html", path, "--out", path)
        self.assert_exit(res, 2)
        self.assertEqual(before, path.read_bytes(), "--html が書き換えられている")

    def test_out_same_realpath_via_symlink_is_exit2(self):
        """realpath 比較なので symlink 経由でも同一とみなす。"""
        path = self.write_html()
        link = self.tmp / "link.html"
        link.symlink_to(path)
        res = self.run_cli("--html", path, "--out", link)
        self.assert_exit(res, 2)

    def test_out_same_realpath_via_relative_path_is_exit2(self):
        path = self.write_html()
        weird = self.tmp / "sub" / ".." / "handout.html"
        (self.tmp / "sub").mkdir()
        res = self.run_cli("--html", path, "--out", weird)
        self.assert_exit(res, 2)

    def test_report_same_path_as_html_is_exit2(self):
        path = self.write_html()
        before = path.read_bytes()
        res = self.run_cli("--html", path, "--report", path)
        self.assert_exit(res, 2)
        self.assertEqual(before, path.read_bytes())

    # ---- 出力先の親ディレクトリ -------------------------------------------

    def test_out_parent_missing_is_exit2(self):
        path = self.write_html()
        res = self.run_cli("--html", path, "--out", self.tmp / "nope" / "out.json")
        self.assert_exit(res, 2)

    def test_report_parent_missing_is_exit2(self):
        path = self.write_html()
        res = self.run_cli("--html", path, "--report", self.tmp / "nope" / "report.json")
        self.assert_exit(res, 2)

    # ---- --compare --------------------------------------------------------

    def test_compare_unreadable_json_is_exit2(self):
        path = self.write_html()
        broken = self.write_json(None, name="broken.json", raw=b"{ not json")
        res = self.run_cli("--html", path, "--compare", broken)
        self.assert_exit(res, 2)

    def test_compare_missing_file_is_exit2(self):
        path = self.write_html()
        res = self.run_cli("--html", path, "--compare", self.tmp / "no-such.json")
        self.assert_exit(res, 2)

    # ---- 既定挙動 ---------------------------------------------------------

    def test_out_is_optional_and_check_only_run_writes_nothing(self):
        """--out 未指定時は書き出さず検査のみ行う。"""
        res, path = self.extract(out=False)
        self.assert_exit(res, 0)
        self.assertEqual([], [p.name for p in self.tmp.iterdir()
                              if p.name not in {"handout.html", "plugin-root"}],
                         "--out 未指定なのにファイルが作られている")

    def test_config_json_is_not_written_to_stdout(self):
        """構成データ JSON は stdout へ流さず常に --out へ書く。"""
        res, _ = self.extract()
        self.assert_exit(res, 0)
        self.assertNotIn('"sections"', res.stdout,
                         "構成データ JSON が stdout へ流れている: %r" % res.stdout)
        self.assertFalse(res.stdout.lstrip().startswith("{"))

    def test_stdout_summary_shape(self):
        """stdout の 1 行目は EXTRACTED から始まる 1 行サマリ。"""
        res, _ = self.extract()
        fields = self.summary(res)
        for key in ("sections", "parts", "exact", "heuristic", "unrecoverable"):
            self.assertIn(key, fields, "1 行サマリに %s= が無い: %r" % (key, res.stdout))
            self.assertTrue(fields[key].isdigit(), "%s= が数でない: %r" % (key, fields[key]))

    def test_roundtrip_field_absent_without_compare(self):
        """--compare 未指定のときサマリに roundtrip= を出さない (評価していない)。"""
        res, _ = self.extract()
        self.assertNotIn("roundtrip", self.summary(res))

    def test_stdin_is_not_read(self):
        """非対話 script。stdin を閉じても停止しない。"""
        res, _ = self.extract()
        self.assert_exit(res, 0)

    # ---- 入力の不可侵 (AC-C20-14) -----------------------------------------

    def test_html_is_never_modified(self):
        """AC-C20-14: 実行後も --html の内容と mtime が変わらない。"""
        path = self.write_html()
        before = path.read_bytes()
        before_mtime = path.stat().st_mtime_ns
        res, _ = self.extract(html=path, out=self.out)
        self.assert_exit(res, 0)
        self.assertEqual(before, path.read_bytes(), "--html の内容が変わった")
        self.assertEqual(before_mtime, path.stat().st_mtime_ns, "--html の mtime が変わった")

    def test_html_is_not_modified_on_failure_paths(self):
        """失敗経路 (malformed) でも --html は無変更。"""
        path = self.write_html("<html><body><section id=\"a\"></body></html>")
        before = path.read_bytes()
        res = self.run_cli("--html", path, "--out", self.out)
        self.assert_exit(res, 1)
        self.assertEqual(before, path.read_bytes())

    def test_write_scope_is_out_and_report_only(self):
        """write_scope: --out と --report の 2 ファイルだけ。plugin root を書かない。"""
        def listing():
            return sorted(p.relative_to(self.root).as_posix()
                          for p in self.root.rglob("*")
                          if p.is_file() and "__pycache__" not in p.parts)

        snapshot = listing()
        res, _ = self.extract(None, "--report", self.report)
        self.assert_exit(res, 0)
        self.assertTrue(self.out.exists() and self.report.exists(),
                        "--out / --report が書かれていない")
        after = listing()
        self.assertEqual(snapshot, after, "plugin root 配下へ書き込んでいる")


if __name__ == "__main__":
    unittest.main()

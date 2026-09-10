"""argv と exit code の契約 (script-brief-C14.json argv / exit_codes / AC-C14-7)。"""

import os
import tempfile
import unittest
from pathlib import Path

import _harness as H


class StdoutShapeTest(unittest.TestCase):
    """stdout: inline SVG 断片 1 個 (先頭 `<svg` 終端 `</svg>` + 末尾改行 1 個)。"""

    def _render(self, pattern):
        with tempfile.TemporaryDirectory() as td:
            return H.render(td, H.spec_for(pattern))

    def test_flow_exits_zero_and_starts_with_svg(self):
        res = self._render("flow")
        self.assertEqual(res.returncode, 0, res)
        self.assertTrue(res.stdout.startswith("<svg"), repr(res.stdout[:80]))

    def test_stdout_ends_with_exactly_one_trailing_newline(self):
        res = self._render("flow")
        self.assertEqual(res.returncode, 0, res)
        self.assertTrue(res.stdout.endswith("</svg>\n"), repr(res.stdout[-40:]))
        self.assertFalse(res.stdout.endswith("</svg>\n\n"), "末尾改行は 1 個")

    def test_stdout_has_no_xml_declaration_or_doctype(self):
        res = self._render("flow")
        self.assertEqual(res.returncode, 0, res)
        self.assertNotIn("<?xml", res.stdout)
        self.assertNotIn("<!DOCTYPE", res.stdout.upper().replace("<!doctype", "<!DOCTYPE"))

    def test_stdout_contains_exactly_one_root_svg(self):
        res = self._render("flow")
        self.assertEqual(res.returncode, 0, res)
        roots = [el for el in H.parse(res.stdout) if el.tag == "svg" and el.parent is None]
        self.assertEqual(len(roots), 1, "ルート <svg> は 1 個")

    def test_newlines_are_lf_only(self):
        res = self._render("flow")
        self.assertEqual(res.returncode, 0, res)
        self.assertNotIn(b"\r", res.stdout_bytes, "改行は \\n 固定 (手順 12)")

    def test_indentation_is_two_spaces(self):
        res = self._render("flow")
        self.assertEqual(res.returncode, 0, res)
        for i, line in enumerate(res.stdout.split("\n")):
            indent = len(line) - len(line.lstrip(" "))
            self.assertNotIn("\t", line, "行 %d にタブがある" % i)
            self.assertEqual(indent % 2, 0, "行 %d のインデントが 2 の倍数でない: %r" % (i, line))

    def test_success_writes_nothing_to_stderr(self):
        res = self._render("flow")
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stderr, "", "正常系の stderr は空")


class WidthArgvTest(unittest.TestCase):
    """--width: 既定 860 / viewBox 幅へ反映 / 正整数でなければ exit 2。"""

    def test_default_width_is_860(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        root = H.root_svg(res.stdout)
        self.assertIsNotNone(root, "ルート <svg> が無い")
        self.assertRegex(root.get("viewBox", ""), r"^0 0 %d \d+$" % H.DEFAULT_WIDTH)

    def test_explicit_width_is_reflected_in_viewbox(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(), width=640)
        self.assertEqual(res.returncode, 0, res)
        root = H.root_svg(res.stdout)
        self.assertIsNotNone(root, "ルート <svg> が無い")
        self.assertRegex(root.get("viewBox", ""), r"^0 0 640 \d+$")

    def test_viewbox_numbers_are_integers(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        root = H.root_svg(res.stdout)
        self.assertIsNotNone(root, "ルート <svg> が無い")
        self.assertRegex(root.get("viewBox", ""), r"^0 0 \d+ \d+$", "手順 7: 座標は整数へ丸める")

    def test_root_svg_has_no_width_or_height_attribute(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        root = H.root_svg(res.stdout)
        self.assertIsNotNone(root, "ルート <svg> が無い")
        self.assertNotIn("width", root.attrs, "手順 8: width/height 属性は出さない")
        self.assertNotIn("height", root.attrs, "手順 8: width/height 属性は出さない")

    def test_width_zero_is_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(), width=0)
        self.assertEqual(res.returncode, 2, res)

    def test_width_negative_is_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(), width=-100)
        self.assertEqual(res.returncode, 2, res)

    def test_width_non_numeric_is_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(), width="wide")
        self.assertEqual(res.returncode, 2, res)

    def test_width_float_is_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(), width="860.5")
        self.assertEqual(res.returncode, 2, "--width は正整数のみ: %r" % (res,))


class MissingArgvTest(unittest.TestCase):
    """argv 不正は exit 2 (呼び出し側への差し戻し)。"""

    def test_no_arguments_is_exit2(self):
        res = H.run_diagram([])
        self.assertEqual(res.returncode, 2, res)

    def test_missing_pattern_is_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            path = H.write_diagram(Path(td) / "d.json", H.flow_spec())
            res = H.run_diagram(["--diagram", path])
        self.assertEqual(res.returncode, 2, res)

    def test_missing_diagram_is_exit2(self):
        res = H.run_diagram(["--pattern", "flow"])
        self.assertEqual(res.returncode, 2, res)

    def test_unknown_flag_is_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            path = H.write_diagram(Path(td) / "d.json", H.flow_spec())
            res = H.run_diagram(["--diagram", path, "--pattern", "flow", "--colour", "red"])
        self.assertEqual(res.returncode, 2, res)

    def test_stdin_is_not_used(self):
        """stdin: 使わない。--diagram のパス指定のみ。"""
        with tempfile.TemporaryDirectory() as td:
            path = H.write_diagram(Path(td) / "d.json", H.flow_spec())
            res = H.run_diagram(["--pattern", "flow", "-"])
            # H-02: TemporaryDirectory の with ブロック内で読む
            # (外に出すと削除済みディレクトリを読んで FileNotFoundError になる)
            self.assertEqual(res.returncode, 2, res)
            self.assertEqual(path.read_text(encoding="utf-8")[:1], "{")


class UnreadableInputTest(unittest.TestCase):
    """AC-C14-7: 不在パス / 壊れた JSON は exit 2。"""

    def test_missing_file_is_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.run_diagram(
                ["--diagram", Path(td) / "nope.json", "--pattern", "flow"]
            )
        self.assertEqual(res.returncode, 2, res)
        self.assertNotEqual(res.stderr.strip(), "", "stderr へ OS エラーを出す")

    def test_broken_json_is_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "broken.json"
            path.write_text('{"title": "壊れた", ', encoding="utf-8")
            res = H.run_diagram(["--diagram", path, "--pattern", "flow"])
        self.assertEqual(res.returncode, 2, res)
        self.assertNotEqual(res.stderr.strip(), "", "stderr へ json の行桁を出す")

    def test_directory_as_diagram_is_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.run_diagram(["--diagram", td, "--pattern", "flow"])
        self.assertEqual(res.returncode, 2, res)

    def test_json_that_is_not_an_object_is_exit2_or_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "arr.json"
            path.write_text("[1, 2, 3]\n", encoding="utf-8")
            res = H.run_diagram(["--diagram", path, "--pattern", "flow"])
        self.assertIn(res.returncode, (1, 2), res)
        self.assertNotEqual(res.stderr.strip(), "")


class WriteScopeTest(unittest.TestCase):
    """write_scope=none: ファイルを一切作成・更新・削除しない。"""

    def _tree(self, root):
        return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*"))

    def test_no_files_are_created_in_cwd(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "work"
            work.mkdir()
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            path = H.write_diagram(spec_dir / "d.json", H.flow_spec())
            before = self._tree(work)
            res = H.run_diagram(["--diagram", path, "--pattern", "flow"], cwd=work)
            self.assertEqual(res.returncode, 0, res)
            self.assertEqual(self._tree(work), before, "cwd へファイルを作ってはならない")

    def test_input_file_is_not_modified(self):
        with tempfile.TemporaryDirectory() as td:
            path = H.write_diagram(Path(td) / "d.json", H.flow_spec())
            before = path.read_bytes()
            before_mtime = os.stat(path).st_mtime_ns
            res = H.run_diagram(["--diagram", path, "--pattern", "flow"])
            self.assertEqual(res.returncode, 0, res)
            self.assertEqual(path.read_bytes(), before, "入力 JSON を書き換えてはならない")
            self.assertEqual(os.stat(path).st_mtime_ns, before_mtime)


class ExitCodeSeparationTest(unittest.TestCase):
    """exit 1 (データ側へ差し戻し) と exit 2 (呼び出し側へ差し戻し) を混ぜない。"""

    def test_data_violation_is_never_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=[{"id": "a", "label": "1"}]))
        self.assertEqual(res.returncode, 1, "ノード数不足はデータ側の規約違反: %r" % (res,))

    def test_caller_error_is_never_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.run_diagram(
                ["--diagram", Path(td) / "absent.json", "--pattern", "flow"]
            )
        self.assertEqual(res.returncode, 2, "ファイル不在は呼び出し側の誤り: %r" % (res,))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

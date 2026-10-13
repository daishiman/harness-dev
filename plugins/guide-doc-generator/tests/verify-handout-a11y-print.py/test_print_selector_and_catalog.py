"""PRINT-02 のセレクタ照合と PRINT-03 の対象マーカーの出どころを赤で固定する。

正本: script-brief-C17.json の detection PRINT-02 / PRINT-03、
config/handout-parts.json の non_part_structure_markers。
coverage レビューの指摘:
  - PRINT-02 が `sel in ps` の部分文字列で照合し、`.bar-x` の print 規則で `.bar` を、
    `.pop-header` の print 規則で `header` を無効化したことにしていた。
  - PRINT-03 の対象マーカーを script 内の写しで持ち、カタログの改名に黙って遅れていた。
  - descendants() が先頭 pop と list 連結で O(n^2) だった (先行順は変えない)。
"""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

from hb_c17 import PLUGIN_ROOT, PRINT_CSS, SCRIPT, C17TestCase, Result, good_html, mutate

STICKY_PRINT_LINE = ".pop-header{position:static}\n"
CATALOG = PLUGIN_ROOT / "config" / "handout-parts.json"


def _load_script():
    spec = importlib.util.spec_from_file_location("hb_c17_a11y_print", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPrint02SelectorUnit(C17TestCase):

    def test_identifier_cut_in_the_middle_does_not_cover(self):
        cases = [(".bar-x", ".bar"), (".pop-header", "header"), ("#bar", "bar"),
                 (".barx", ".bar"), (".foo-bar", "bar")]
        for print_sel, sel in cases:
            with self.subTest(print_sel=print_sel, sel=sel):
                self.assertFalse(_load_script()._print_selector_covers(print_sel, sel))

    def test_exact_and_compound_print_selectors_cover(self):
        cases = [(".bar", ".bar"), ("header.pop-header", ".pop-header"),
                 ("main .pop-header", ".pop-header"), ("body header", "header"),
                 (".pop-header:not(.x)", ".pop-header")]
        for print_sel, sel in cases:
            with self.subTest(print_sel=print_sel, sel=sel):
                self.assertTrue(_load_script()._print_selector_covers(print_sel, sel))


class TestPrint02SelectorCli(C17TestCase):

    def test_longer_class_in_print_does_not_neutralize(self):
        """`.bar-x{position:static}` は `.bar` の sticky を無効化しない。"""
        html = good_html(css_extra=".bar{position:sticky;top:0}\n",
                         print_css=mutate(PRINT_CSS, STICKY_PRINT_LINE,
                                          STICKY_PRINT_LINE + ".bar-x{position:static}\n"))
        self.assertDetectionFails(self.check(html), "PRINT-02", count=1)

    def test_class_print_rule_does_not_neutralize_type_selector(self):
        """`.pop-header{position:static}` は `header{position:sticky}` を無効化しない。"""
        html = good_html(css_extra="header{position:sticky;top:0}\n")
        self.assertDetectionFails(self.check(html), "PRINT-02", count=1)

    def test_compound_print_selector_still_neutralizes(self):
        """brief の 1 段の緩和: `header.pop-header` は `.pop-header` を被覆する。"""
        html = good_html(print_css=mutate(PRINT_CSS, STICKY_PRINT_LINE,
                                          "header.pop-header{position:static}\n"))
        self.assertDetectionPasses(self.check(html), "PRINT-02")


class TestPrint03MarkersFromCatalog(C17TestCase):

    def _catalog_root(self, mutate_markers):
        root = self.tmp / "root-{}".format(mutate_markers.__name__)
        (root / "config").mkdir(parents=True)
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
        mutate_markers(data)
        (root / "config" / "handout-parts.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return root

    def _check_with_root(self, html_text, root):
        env = dict(os.environ, HB_ROOT=str(root))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--html", str(self.write_html(html_text))],
            capture_output=True, text=True, cwd=str(self.tmp), timeout=120, env=env,
        )
        return Result(proc.returncode, proc.stdout, proc.stderr)

    def test_marker_added_to_catalog_is_checked(self):
        """カタログに足したマーカーは、写しを直さなくても PRINT-03 の対象になる。"""
        def add_drawer(data):
            data["non_part_structure_markers"]["values"].append("drawer")
        root = self._catalog_root(add_drawer)
        html = good_html(body_extra='<div data-hb-part="drawer">メニュー</div>\n')
        self.assertDetectionFails(self._check_with_root(html, root), "PRINT-03", count=1)

    def test_broken_marker_list_is_exit_2(self):
        def drop(data):
            del data["non_part_structure_markers"]

        def section_only(data):
            data["non_part_structure_markers"]["values"] = ["section"]

        def not_strings(data):
            data["non_part_structure_markers"]["values"] = ["lightbox", 1]

        cases = [(drop, "non_part_structure_markers.values が文字列の配列でない"),
                 (not_strings, "non_part_structure_markers.values が文字列の配列でない"),
                 (section_only, "画面専用 UI の構造マーカーが無い")]
        for change, message in cases:
            with self.subTest(change.__name__):
                res = self._check_with_root(good_html(), self._catalog_root(change))
                self.assertEqual(2, res.rc, res)
                self.assertIn(message, res.err)

    def test_real_catalog_matches_previous_screen_only_set(self):
        """正本のカタログから引いた値は、以前の写しと同じ 4 値になる。"""
        markers = _load_script().load_screen_only_markers(PLUGIN_ROOT)
        self.assertEqual({"lightbox", "memo", "memo-global", "toolbar"}, set(markers))


class TestDescendantsOrder(unittest.TestCase):

    def test_preorder_is_kept(self):
        mod = _load_script()
        root = mod.Node("root", {}, 1, 1, None)

        def add(parent, tag):
            node = mod.Node(tag, {}, 1, 1, parent)
            parent.children.append(node)
            return node

        a = add(root, "a")
        add(a, "a1")
        a2 = add(a, "a2")
        add(a2, "a2x")
        add(root, "b")
        self.assertEqual(["a", "a1", "a2", "a2x", "b"], [n.tag for n in root.descendants()])

    def test_deep_and_wide_trees_finish(self):
        mod = _load_script()
        root = mod.Node("root", {}, 1, 1, None)
        node = root
        for i in range(5000):
            child = mod.Node("d{}".format(i), {}, 1, 1, node)
            node.children.append(child)
            node = child
        for i in range(20000):
            root.children.append(mod.Node("w{}".format(i), {}, 1, 1, root))
        self.assertEqual(25000, sum(1 for _ in root.descendants()))


if __name__ == "__main__":
    unittest.main()

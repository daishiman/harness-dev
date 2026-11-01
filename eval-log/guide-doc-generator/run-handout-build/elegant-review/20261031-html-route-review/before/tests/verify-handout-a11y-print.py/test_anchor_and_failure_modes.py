"""検査アンカー不在と failure_modes を赤で固定する。

正本: script-brief-C17.json の exit_codes(1) の後段、failure_modes 全 4 件、
AC-C17-03 (data-hb-part を 1 個も持たない HTML)。
いずれも「検査できないものを PASS へ畳まない」ことの回帰。
"""

import json
import unittest

from hb_c17 import C17TestCase, DETECTION_IDS, good_html

# data-hb-part を 1 個も持たない資料風 HTML
BODY_WITHOUT_PARTS = """<header class="pop-header">
<nav aria-label="目次"><a href="#s1">1. 導入</a></nav>
</header>
<main class="pop">
<section id="s1" class="pop-card"><h2>導入</h2><p>本日の狙いを確認します。</p></section>
</main>
"""

# 粗いトークナイザが解けない CSS (CSS ネスト構文 / ネストされた @supports)
NESTED_CSS = """@supports (display:grid){
@media print{
.pop-card{display:grid}
}
}
.pop-card{
& > h2{color:#111}
}
"""


class TestMissingAnchor(C17TestCase):
    """AC-C17-03: data-hb-part が 1 個も無い HTML。"""

    def setUp(self):
        super().setUp()
        self.res = self.check(good_html(body=BODY_WITHOUT_PARTS))

    def test_exit_one(self):
        self.assertEqual(1, self.res.rc,
                         "検査対象を同定できない HTML を PASS にしない (fail-closed)\n{}".format(self.res))

    def test_part_dependent_detections_are_fail_not_uncheckable(self):
        """NOT-STATICALLY-CHECKABLE へ逃がさず FAIL として計上する。"""
        for det in ("A11Y-01", "A11Y-02", "A11Y-05"):
            self.assertStatus(self.res, det, "FAIL",
                              "検査不能扱いで PASS / NOT-STATICALLY-CHECKABLE へ逃がさない")

    def test_result_line_is_fail(self):
        m = self.res.result_line()
        self.assertIsNotNone(m, self.res)
        self.assertEqual("FAIL", m.group("result"))

    def test_stderr_names_the_missing_attribute(self):
        self.assertIn("data-hb-part", self.res.err,
                      "必要な属性名を stderr に明示すること\n{}".format(self.res))

    def test_all_twelve_lines_still_printed(self):
        self.assertEqual(DETECTION_IDS, self.res.summary_order(), self.res)

    def test_table_with_scope_passes_even_without_parts(self):
        """A11Y-04 だけは data-hb-part 非依存なのでアンカー不在に巻き込まれない。"""
        html = good_html(body=BODY_WITHOUT_PARTS
                         + '<table><thead><tr><th scope="col">列</th></tr></thead>'
                           '<tbody><tr><td>値</td></tr></tbody></table>')
        self.assertDetectionPasses(self.check(html), "A11Y-04")

    def test_table_without_scope_fails_even_without_parts(self):
        html = good_html(body=BODY_WITHOUT_PARTS
                         + '<table><thead><tr><th>列</th></tr></thead>'
                           '<tbody><tr><td>値</td></tr></tbody></table>')
        self.assertDetectionFails(self.check(html), "A11Y-04", count=1)


class TestUnparsableCss(C17TestCase):
    """failure_modes: 解けない CSS ブロックは無視せず FAIL に倒す。"""

    def test_nested_css_is_exit_one(self):
        res = self.check(good_html(css_extra=NESTED_CSS))
        self.assertEqual(1, res.rc,
                         "未解析の CSS を見落として PASS にしない\n{}".format(res))

    def test_unparsed_blocks_are_listed_in_report(self):
        _, rep = self.report_for(good_html(css_extra=NESTED_CSS))
        self.assertIn("unparsed_css_blocks", rep)
        self.assertTrue(rep["unparsed_css_blocks"],
                        "解けなかったブロックを位置つきで列挙すること: {}".format(rep))

    def test_unparsed_block_entry_has_position(self):
        _, rep = self.report_for(good_html(css_extra=NESTED_CSS))
        for entry in rep["unparsed_css_blocks"]:
            self.assertIn("line", entry, entry)

    def test_parsable_css_leaves_the_list_empty(self):
        _, rep = self.report_for(good_html())
        self.assertEqual([], rep.get("unparsed_css_blocks", []),
                         "解ける CSS で未解析を報告してはいけない: {}".format(
                             json.dumps(rep.get("unparsed_css_blocks"), ensure_ascii=False)))

    def test_css_comment_is_not_treated_as_unparsable(self):
        html = good_html(css_extra="/* @media print { ここはコメント } */\n.x{color:#000}\n")
        _, rep = self.report_for(html)
        self.assertEqual([], rep.get("unparsed_css_blocks", []), rep)

    def test_commented_out_print_block_does_not_satisfy_print_01(self):
        """コメントは除去してから評価する (algorithm 3)。"""
        html = good_html(print_css="/* @media print{main{max-width:100%}} */\n")
        self.assertDetectionFails(self.check(html), "PRINT-01")


class TestNonHandoutDocument(C17TestCase):
    """failure_modes: 対象選別は呼び出し側の責務。届いた以上は資料 HTML として判定する。"""

    def test_document_without_style_and_parts_is_exit_one(self):
        res = self.check('<!DOCTYPE html><html lang="ja"><body><p>ただの HTML</p></body></html>')
        self.assertEqual(1, res.rc,
                         "構造要件を満たさない -> exit 1 (2 ではない)\n{}".format(res))

    def test_empty_document_is_exit_one(self):
        self.assertEqual(1, self.check("").rc)

    def test_malformed_html_does_not_crash_into_exit2(self):
        res = self.check(good_html(body_extra="<div><p>閉じていない"))
        self.assertIn(res.rc, (0, 1), "回復可能な崩れで exit 2 にしない\n{}".format(res))

    def test_unclosed_style_block_is_not_silently_passed(self):
        html = good_html().replace("</style>", "", 1)
        res = self.check(html)
        self.assertNotEqual(0, res.rc,
                            "<style> が閉じていない文書を PASS にしない\n{}".format(res))


if __name__ == "__main__":
    unittest.main()

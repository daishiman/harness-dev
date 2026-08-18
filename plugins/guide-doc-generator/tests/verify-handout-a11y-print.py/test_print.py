"""PRINT-01..04 (A4 印刷規則の宣言) を赤で固定する。

正本: script-brief-C17.json の detections PRINT-01 / 02 / 03 / 04、
AC-C17-07 (sticky に print 指定が無い) / AC-C17-08 (@media print が無い)、
failure_modes の「@media print が複数ブロックに分かれている」。
"""

import unittest

from hb_c17 import C17TestCase, PRINT_CSS, good_html, mutate

STICKY_PRINT_LINE = ".pop-header{position:static}\n"
HIDE_CLASS_LINE = ".lightbox,.memo-panel,.memo-global,.toolbar{display:none !important}\n"
HIDE_ATTR_LINE = ('[data-hb-part="lightbox"],[data-hb-part="memo"],'
                  '[data-hb-part="memo-global"],[data-hb-part="toolbar"]'
                  '{display:none !important}\n')
BREAK_LINE = ".pop-card{break-inside:avoid;page-break-inside:avoid}\n"
BREAK_AFTER_LINE = "h1,h2,h3{break-after:avoid}\n"


class TestPrint01MediaPrintExists(C17TestCase):

    def test_no_media_print_block(self):
        """AC-C17-08: @media print を持たない。"""
        res = self.check(good_html(print_css=""))
        self.assertDetectionFails(res, "PRINT-01")

    def test_print_02_to_04_also_counted_when_media_print_missing(self):
        """AC-C17-08: PRINT-02..04 も未充足として計上される (PASS へ畳まない)。"""
        res = self.check(good_html(print_css=""))
        for det in ("PRINT-02", "PRINT-03", "PRINT-04"):
            self.assertStatus(res, det, "FAIL", "@media print 不在時に PASS へ畳まない")

    def test_empty_media_print_block(self):
        html = good_html(print_css="@media print{}\n")
        self.assertDetectionFails(self.check(html), "PRINT-01")

    def test_at_page_without_a4_and_no_width_reset(self):
        html = good_html(page_css="@page{margin:14mm}\n",
                         print_css="@media print{\n" + STICKY_PRINT_LINE + HIDE_CLASS_LINE
                                   + HIDE_ATTR_LINE + BREAK_LINE + BREAK_AFTER_LINE
                                   + ".lightbox{position:static}\n}\n")
        self.assertDetectionFails(self.check(html), "PRINT-01")

    def test_width_reset_inside_print_substitutes_for_at_page(self):
        """@page が無くても print 内で版面幅を再指定していれば充足。"""
        html = good_html(page_css="")
        self.assertDetectionPasses(self.check(html), "PRINT-01")

    def test_at_page_size_a4_is_accepted(self):
        html = good_html(print_css=mutate(PRINT_CSS, "main.pop{max-width:100%}\n", ""))
        self.assertDetectionPasses(self.check(html), "PRINT-01")


class TestPrint02StickyNeutralized(C17TestCase):

    def test_sticky_selector_without_print_override(self):
        """AC-C17-07: .pop-header{position:sticky} があり print 側に指定が無い。"""
        html = good_html(print_css=mutate(PRINT_CSS, STICKY_PRINT_LINE, ""))
        self.assertDetectionFails(self.check(html), "PRINT-02", count=1)

    def test_fixed_selector_is_collected_too(self):
        html = good_html(css_extra=".pop-toc{position:fixed;left:0}\n")
        self.assertDetectionFails(self.check(html), "PRINT-02", count=1)

    def test_display_none_in_print_satisfies(self):
        html = good_html(css_extra=".pop-toc{position:fixed;left:0}\n",
                         print_css=mutate(PRINT_CSS, STICKY_PRINT_LINE,
                                          STICKY_PRINT_LINE + ".pop-toc{display:none}\n"))
        self.assertDetectionPasses(self.check(html), "PRINT-02")

    def test_position_relative_in_print_satisfies(self):
        html = good_html(print_css=mutate(PRINT_CSS, STICKY_PRINT_LINE,
                                          ".pop-header{position:relative}\n"))
        self.assertDetectionPasses(self.check(html), "PRINT-02")

    def test_print_side_still_sticky_is_violation(self):
        html = good_html(print_css=mutate(PRINT_CSS, STICKY_PRINT_LINE,
                                          ".pop-header{position:sticky}\n"))
        self.assertDetectionFails(self.check(html), "PRINT-02", count=1)

    def test_substring_selector_match_is_tolerated(self):
        """緩和: print 側が `header.pop-header` でも `.pop-header` と一致とみなす。"""
        html = good_html(print_css=mutate(PRINT_CSS, STICKY_PRINT_LINE,
                                          "header.pop-header{position:static}\n"))
        self.assertDetectionPasses(self.check(html), "PRINT-02")

    def test_each_uncovered_selector_counted_individually(self):
        html = good_html(css_extra=".pop-toc{position:fixed}\n.pop-fab{position:sticky;top:8px}\n")
        self.assertDetectionFails(self.check(html), "PRINT-02", count=2)

    def test_checked_counts_sticky_selectors(self):
        self.assertCheckedAtLeast(self.check_good(), "PRINT-02", 2,
                                  "土台 fixture は .pop-header (sticky) と .lightbox (fixed) を持つ")


class TestPrint03ScreenOnlyUiHidden(C17TestCase):

    def test_no_display_none_for_screen_only_ui(self):
        html = good_html(print_css=mutate(
            mutate(PRINT_CSS, HIDE_CLASS_LINE, ""), HIDE_ATTR_LINE, ""))
        res = self.check(html)
        self.assertDetectionFails(res, "PRINT-03")
        self.assertGreaterEqual(len(res.violations("PRINT-03")), 4,
                                "lightbox / memo / memo-global / toolbar を 1 件ずつ計上する\n{}".format(res))

    def test_attribute_selector_form_alone_is_enough(self):
        """推奨形 ([data-hb-part="…"]) だけで確実に一致する。"""
        html = good_html(print_css=mutate(PRINT_CSS, HIDE_CLASS_LINE, ""))
        self.assertDetectionPasses(self.check(html), "PRINT-03")

    def test_class_selector_form_alone_is_enough(self):
        html = good_html(print_css=mutate(PRINT_CSS, HIDE_ATTR_LINE, ""))
        self.assertDetectionPasses(self.check(html), "PRINT-03")

    def test_element_matched_by_class_only_is_in_scope(self):
        """class に memo を含む要素は data-hb-part が無くても対象。"""
        html = good_html(body_extra='<div class="memo-note"><p>走り書き</p></div>')
        self.assertDetectionFails(self.check(html), "PRINT-03", count=1)

    def test_display_none_outside_media_print_does_not_count(self):
        html = good_html(css_extra=".memo-note{display:none}\n",
                         body_extra='<div class="memo-note"><p>走り書き</p></div>')
        self.assertDetectionFails(self.check(html), "PRINT-03", count=1)

    def test_visibility_hidden_is_not_accepted(self):
        html = good_html(print_css=mutate(PRINT_CSS, HIDE_CLASS_LINE,
                                          ".lightbox,.memo-panel,.memo-global,.toolbar"
                                          "{visibility:hidden}\n"))
        html = mutate(html, HIDE_ATTR_LINE, "")
        self.assertDetectionFails(self.check(html), "PRINT-03")

    def test_checked_counts_screen_only_elements(self):
        self.assertCheckedAtLeast(self.check_good(), "PRINT-03", 4)


class TestPrint04PageBreaks(C17TestCase):

    def test_no_break_inside_declaration(self):
        html = good_html(print_css=mutate(PRINT_CSS, BREAK_LINE, ""))
        self.assertDetectionFails(self.check(html), "PRINT-04")

    def test_no_break_after_on_headings(self):
        html = good_html(print_css=mutate(PRINT_CSS, BREAK_AFTER_LINE, ""))
        self.assertDetectionFails(self.check(html), "PRINT-04")

    def test_legacy_page_break_inside_alone_is_accepted(self):
        html = good_html(print_css=mutate(PRINT_CSS, BREAK_LINE,
                                          ".pop-card{page-break-inside:avoid}\n"))
        self.assertDetectionPasses(self.check(html), "PRINT-04")

    def test_break_inside_auto_is_not_accepted(self):
        html = good_html(print_css=mutate(PRINT_CSS, BREAK_LINE,
                                          ".pop-card{break-inside:auto}\n"))
        self.assertDetectionFails(self.check(html), "PRINT-04")

    def test_break_declarations_outside_media_print_do_not_count(self):
        html = good_html(css_extra=".pop-card{break-inside:avoid}\nh2{break-after:avoid}\n",
                         print_css=mutate(mutate(PRINT_CSS, BREAK_LINE, ""), BREAK_AFTER_LINE, ""))
        self.assertDetectionFails(self.check(html), "PRINT-04")


class TestMultipleMediaPrintBlocks(C17TestCase):
    """failure_modes: 複数ブロックに分かれていても判定を変えない。"""

    SPLIT = ("@media print{\nmain.pop{max-width:100%}\n" + STICKY_PRINT_LINE
             + ".lightbox{position:static}\n}\n"
             + "@media print{\n" + HIDE_CLASS_LINE + HIDE_ATTR_LINE + "}\n"
             + "@media print{\n" + BREAK_LINE + BREAK_AFTER_LINE + "}\n")

    def test_split_blocks_are_merged_before_evaluation(self):
        res = self.check(good_html(print_css=self.SPLIT))
        for det in ("PRINT-01", "PRINT-02", "PRINT-03", "PRINT-04"):
            self.assertDetectionPasses(res, det)

    def test_split_blocks_give_same_verdict_as_single_block(self):
        single = self.check(good_html())
        split = self.check(good_html(print_css=self.SPLIT))
        self.assertEqual(single.rc, split.rc, (single, split))
        self.assertEqual({d: v["status"] for d, v in single.summary().items()},
                         {d: v["status"] for d, v in split.summary().items()})

    def test_style_split_across_two_elements_is_merged(self):
        """<style> が 2 つに分かれていても同じ (algorithm 2 の別途保持)。"""
        html = good_html(print_css="", head_extra="<style>\n" + PRINT_CSS + "</style>\n")
        res = self.check(html)
        for det in ("PRINT-01", "PRINT-02", "PRINT-03", "PRINT-04"):
            self.assertDetectionPasses(res, det)


if __name__ == "__main__":
    unittest.main()

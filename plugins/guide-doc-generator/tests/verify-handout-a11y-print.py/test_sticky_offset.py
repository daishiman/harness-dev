"""STICKY-01 (sticky ヘッダー分のアンカーオフセット補正) を赤で固定する。

正本: script-brief-C17.json の detection STICKY-01 (goal-spec C4)、AC-C17-09。
CSS 単独でも JS 単独でも違反 — 両系の存在を要求する。
"""

import unittest

from hb_c17 import BASE_CSS, C17TestCase, good_html, mutate

SCROLL_MARGIN = ".pop-card{scroll-margin-top:96px;padding:16px}"
JS_NO_RECT = """'use strict';
var header=document.querySelector('.pop-header');
var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
function jumpTo(y){window.scrollTo({top:y,behavior:reduce?'auto':'smooth'});}
"""
JS_NO_HEADER_LOOKUP = """'use strict';
var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
function jumpTo(y){var off=document.body.getBoundingClientRect().top;
window.scrollTo({top:y-off,behavior:reduce?'auto':'smooth'});}
"""


class TestSticky01AnchorOffset(C17TestCase):

    def test_css_only_without_js_measurement(self):
        """AC-C17-09: scroll-margin-top はあるが script に getBoundingClientRect が無い。"""
        res = self.check(good_html(script=JS_NO_RECT))
        self.assertDetectionFails(res, "STICKY-01", count=1)

    def test_js_only_without_css_declaration(self):
        html = good_html(base_css=mutate(BASE_CSS, SCROLL_MARGIN, ".pop-card{padding:16px}"))
        self.assertDetectionFails(self.check(html), "STICKY-01", count=1)

    def test_zero_scroll_margin_is_not_positive(self):
        html = good_html(base_css=mutate(BASE_CSS, SCROLL_MARGIN,
                                         ".pop-card{scroll-margin-top:0;padding:16px}"))
        self.assertDetectionFails(self.check(html), "STICKY-01")

    def test_negative_scroll_margin_is_not_positive(self):
        html = good_html(base_css=mutate(BASE_CSS, SCROLL_MARGIN,
                                         ".pop-card{scroll-margin-top:-8px;padding:16px}"))
        self.assertDetectionFails(self.check(html), "STICKY-01")

    def test_scroll_padding_top_is_accepted(self):
        html = good_html(base_css=mutate(BASE_CSS, SCROLL_MARGIN,
                                         ".pop-card{padding:16px}")
                         + "html{scroll-padding-top:96px}\n")
        self.assertDetectionPasses(self.check(html), "STICKY-01")

    def test_js_must_reference_the_sticky_element(self):
        """(b) sticky セレクタに対応する要素の取得と rect 計測が共起すること。"""
        self.assertDetectionFails(self.check(good_html(script=JS_NO_HEADER_LOOKUP)), "STICKY-01")

    def test_no_script_at_all(self):
        self.assertDetectionFails(self.check(good_html(script="")), "STICKY-01")

    def test_declaration_on_unrelated_selector_does_not_count(self):
        """(a) の対象セレクタは section 群へ到達しうるものに限る。"""
        html = good_html(base_css=mutate(BASE_CSS, SCROLL_MARGIN, ".pop-card{padding:16px}")
                         + ".footnote{scroll-margin-top:96px}\n")
        self.assertDetectionFails(self.check(html), "STICKY-01")

    def test_both_present_passes(self):
        self.assertDetectionPasses(self.check_good(), "STICKY-01")

    def test_violation_names_both_required_sides(self):
        res = self.check(good_html(script=JS_NO_RECT))
        blob = " ".join(r["missing"] for r in res.violations("STICKY-01"))
        self.assertIn("getBoundingClientRect", blob,
                      "欠落している側 (JS 実測) を violation に書くこと\n{}".format(res))

    def test_only_sticky_detection_fails_for_js_gap(self):
        self.assertOnlyThisDetectionFails(self.check(good_html(script=JS_NO_RECT)), "STICKY-01")


if __name__ == "__main__":
    unittest.main()

"""A11Y-06 (:focus-visible) / A11Y-07 (prefers-reduced-motion) を赤で固定する。

正本: script-brief-C17.json の detections A11Y-06 / A11Y-07、
AC-C17-05 (:focus-visible が無く outline:none だけ) / AC-C17-06 (animation だけ無効化)。
"""

import unittest

from hb_c17 import C17TestCase, good_html

# STICKY-01 を巻き込まずに A11Y-07 (c) だけを見るための script 土台
SCRIPT_WITH_OFFSET = """'use strict';
var header=document.querySelector('.pop-header');
function jumpTo(y){var off=header.getBoundingClientRect().height+12;SCROLL}
"""


def script_with(scroll):
    return SCRIPT_WITH_OFFSET.replace("SCROLL", scroll)


class TestA11y06FocusVisible(C17TestCase):

    def test_no_focus_visible_rule_with_outline_none(self):
        """AC-C17-05: :focus-visible 規則が無く outline:none だけがある。"""
        res = self.check(good_html(focus_css=""))
        self.assertDetectionFails(res, "A11Y-06")

    def test_focus_visible_declaring_outline_none_is_violation(self):
        html = good_html(focus_css="a:focus-visible{outline:none}\n")
        self.assertDetectionFails(self.check(html), "A11Y-06")

    def test_focus_visible_declaring_outline_zero_is_violation(self):
        html = good_html(focus_css=":focus-visible{outline:0}\n")
        self.assertDetectionFails(self.check(html), "A11Y-06")

    def test_focus_visible_with_box_shadow_is_accepted(self):
        html = good_html(
            focus_css=":focus-visible{box-shadow:0 0 0 3px #0b3d91}\n"
                      ".pop-chip:focus-visible{box-shadow:0 0 0 3px #0b3d91}\n")
        self.assertDetectionPasses(self.check(html), "A11Y-06")

    def test_box_shadow_none_is_not_accepted(self):
        html = good_html(
            focus_css=":focus-visible{box-shadow:none}\n"
                      ".pop-chip:focus-visible{box-shadow:none}\n")
        self.assertDetectionFails(self.check(html), "A11Y-06")

    def test_string_presence_in_comment_does_not_pass(self):
        html = good_html(focus_css="/* :focus-visible はテーマ側で定義する */\n")
        self.assertDetectionFails(self.check(html), "A11Y-06")

    def test_outline_none_selector_without_matching_focus_visible(self):
        """(c) outline:none を宣言した側に対応する :focus-visible が要る。"""
        html = good_html(css_extra=".copy-btn:focus{outline:none}\n")
        self.assertDetectionFails(self.check(html), "A11Y-06", count=1)

    def test_outline_none_selector_with_matching_focus_visible_passes(self):
        html = good_html(css_extra=".copy-btn:focus{outline:none}\n"
                                   ".copy-btn:focus-visible{outline:3px solid #0b3d91}\n")
        self.assertDetectionPasses(self.check(html), "A11Y-06")

    def test_universal_focus_visible_covers_outline_none(self):
        """(c) の対応は同一セレクタか `*` のどちらかでよい。"""
        html = good_html(focus_css="*:focus-visible{outline:3px solid #0b3d91}\n",
                         css_extra=".copy-btn:focus{outline:none}\n")
        self.assertDetectionPasses(self.check(html), "A11Y-06")

    def test_selector_list_is_split_before_matching(self):
        """`.x, .y:focus-visible` のカンマ区切りは個別に正規化して突合する。"""
        html = good_html(css_extra=".copy-btn:focus{outline:none}\n"
                                   ".x, .copy-btn:focus-visible{outline:3px solid #0b3d91}\n")
        self.assertDetectionPasses(self.check(html), "A11Y-06")

    def test_whitespace_variants_normalize_to_same_selector(self):
        html = good_html(css_extra=".copy-btn:focus{outline:none}\n"
                                   ".copy-btn:focus-visible   {outline:3px solid #0b3d91}\n")
        self.assertDetectionPasses(self.check(html), "A11Y-06")

    def test_outline_none_shorthand_zero_is_detected(self):
        html = good_html(css_extra=".copy-btn:focus{outline:0}\n")
        self.assertDetectionFails(self.check(html), "A11Y-06", count=1)


class TestA11y07ReducedMotion(C17TestCase):

    ONLY_ANIMATION = ("@media (prefers-reduced-motion: reduce){\n"
                      "*{animation:none}\n}\n")

    def test_animation_only_is_violation(self):
        """AC-C17-06: scroll-behavior と transition の欠落が違反として出る。"""
        res = self.check(good_html(rm_css=self.ONLY_ANIMATION))
        self.assertDetectionFails(res, "A11Y-07")

    def test_violation_message_names_the_missing_properties(self):
        res = self.check(good_html(rm_css=self.ONLY_ANIMATION))
        blob = " ".join(r["missing"] for r in res.violations("A11Y-07"))
        self.assertIn("scroll-behavior", blob, res)
        self.assertIn("transition", blob, res)

    def test_no_reduced_motion_block_at_all(self):
        self.assertDetectionFails(self.check(good_html(rm_css="")), "A11Y-07")

    def test_missing_transition_only(self):
        html = good_html(rm_css="@media (prefers-reduced-motion: reduce){\n"
                                "html{scroll-behavior:auto}\n*{animation-duration:0s}\n}\n")
        self.assertDetectionFails(self.check(html), "A11Y-07")

    def test_missing_scroll_behavior_only(self):
        html = good_html(rm_css="@media (prefers-reduced-motion: reduce){\n"
                                "*{animation-duration:0s;transition-duration:0s}\n}\n")
        self.assertDetectionFails(self.check(html), "A11Y-07")

    def test_scroll_behavior_smooth_inside_reduce_block_is_violation(self):
        html = good_html(rm_css="@media (prefers-reduced-motion: reduce){\n"
                                "html{scroll-behavior:smooth}\n"
                                "*{animation-duration:0s;transition-duration:0s}\n}\n")
        self.assertDetectionFails(self.check(html), "A11Y-07")

    def test_no_preference_prelude_does_not_satisfy(self):
        """prelude に prefers-reduced-motion と reduce の両方が要る。"""
        html = good_html(rm_css="@media (prefers-reduced-motion: no-preference){\n"
                                "html{scroll-behavior:auto}\n"
                                "*{animation-duration:0s;transition-duration:0s}\n}\n")
        self.assertDetectionFails(self.check(html), "A11Y-07")

    def test_animation_none_form_is_accepted(self):
        html = good_html(rm_css="@media (prefers-reduced-motion: reduce){\n"
                                "html{scroll-behavior:auto}\n"
                                "*{animation:none;transition:none}\n}\n")
        self.assertDetectionPasses(self.check(html), "A11Y-07")

    def test_smooth_scroll_in_script_without_matchmedia(self):
        """(c) JS のスムーススクロールが media query を無視している。"""
        html = good_html(script=script_with("window.scrollTo({top:y-off,behavior:'smooth'});"))
        self.assertDetectionFails(self.check(html), "A11Y-07", count=1)

    def test_double_quoted_smooth_is_detected(self):
        html = good_html(script=script_with('window.scrollTo({top:y-off,behavior: "smooth"});'))
        self.assertDetectionFails(self.check(html), "A11Y-07", count=1)

    def test_smooth_scroll_with_matchmedia_passes(self):
        html = good_html(script=script_with(
            "var r=matchMedia('(prefers-reduced-motion: reduce)').matches;"
            "window.scrollTo({top:y-off,behavior:r?'auto':'smooth'});"
            "if(!r){window.scrollTo({top:y-off,behavior:'smooth'});}"))
        self.assertDetectionPasses(self.check(html), "A11Y-07")

    def test_script_without_smooth_is_not_required_to_call_matchmedia(self):
        html = good_html(script=script_with("window.scrollTo({top:y-off});"))
        self.assertDetectionPasses(self.check(html), "A11Y-07")

    def test_matchmedia_without_the_query_string_is_not_enough(self):
        html = good_html(script=script_with(
            "var r=matchMedia('(max-width: 600px)').matches;"
            "window.scrollTo({top:y-off,behavior:'smooth'});"))
        self.assertDetectionFails(self.check(html), "A11Y-07")


if __name__ == "__main__":
    unittest.main()

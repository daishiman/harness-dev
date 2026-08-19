"""A11Y-01 (aria-pressed) / A11Y-02 (aria-selected) / A11Y-03 (アクセシブル名) を赤で固定する。

正本: script-brief-C17.json の detections A11Y-01 / A11Y-02 / A11Y-03、
AC-C17-02 (文字列の存在だけで PASS にしない) / AC-C17-04 (aria-selected=true が 2 個)。
"""

import unittest

from hb_c17 import C17TestCase, good_html, mutate

# _BODY 内の該当箇所 (mutate の差し替え元)
CC_BTN = ('<button class="map-item" aria-pressed="false" data-hb-title="Claude Code" '
          'data-hb-detail="端末で動く">Claude Code</button>')
CHIP_MID = '<button class="pop-chip" aria-pressed="false">中級</button>'
AUX_BTN = ('<button class="map-reset" data-hb-part-role="aux" '
           'aria-label="選択を解除する">解除</button>')
TAB_BUL = '<button role="tab" aria-selected="false" aria-controls="p-bul" id="t-bul">箇条書き</button>'
TAB_MD = '<button role="tab" aria-selected="true" aria-controls="p-md" id="t-md">Markdown</button>'
TABLIST_OPEN = '<div role="tablist" aria-label="記法">'
PANEL_BUL = '<div id="p-bul" role="tabpanel" aria-labelledby="t-bul" hidden>'
PANEL_MD = '<div id="p-md" role="tabpanel" aria-labelledby="t-md">'
COPY_BTN = ('<button class="copy-btn" aria-label="プロンプトをコピー">'
            '<svg data-hb-kind="icon" aria-hidden="true" viewBox="0 0 24 24">'
            '<path d="M8 8h10v10"/></svg></button>')
CHECKBOX = '<label for="ck1"><input id="ck1" type="checkbox"> 準備物を確認した</label>'
TOC_LINK = '<a href="#s1">1. 導入</a>'


class TestA11y01AriaPressed(C17TestCase):
    """トグル要素に aria-pressed が付いていること。"""

    def test_missing_aria_pressed_on_b08_button(self):
        html = mutate(good_html(), CC_BTN,
                      '<button class="map-item" data-hb-title="Claude Code" '
                      'data-hb-detail="端末で動く">Claude Code</button>')
        res = self.check(html)
        self.assertDetectionFails(res, "A11Y-01", count=1)

    def test_only_a11y01_fails_for_missing_aria_pressed(self):
        html = mutate(good_html(), CC_BTN,
                      '<button class="map-item" data-hb-title="Claude Code" '
                      'data-hb-detail="端末で動く">Claude Code</button>')
        self.assertOnlyThisDetectionFails(self.check(html), "A11Y-01")

    def test_invalid_aria_pressed_value(self):
        """値は "true"|"false" のいずれかに限る。"""
        html = mutate(good_html(), 'aria-pressed="false" data-hb-title="Claude Code"',
                      'aria-pressed="on" data-hb-title="Claude Code"')
        self.assertDetectionFails(self.check(html), "A11Y-01", count=1)

    def test_mixed_case_value_is_violation(self):
        html = mutate(good_html(), 'aria-pressed="false" data-hb-title="Claude Code"',
                      'aria-pressed="TRUE" data-hb-title="Claude Code"')
        self.assertDetectionFails(self.check(html), "A11Y-01")

    def test_empty_aria_pressed_value_is_violation(self):
        html = mutate(good_html(), 'aria-pressed="false" data-hb-title="Claude Code"',
                      'aria-pressed="" data-hb-title="Claude Code"')
        self.assertDetectionFails(self.check(html), "A11Y-01")

    def test_string_presence_elsewhere_does_not_pass(self):
        """AC-C17-02: 文書の隅にコメントとして aria-pressed があるだけでは PASS にしない。"""
        html = mutate(good_html(body_extra="<!-- aria-pressed -->"), CC_BTN,
                      '<button class="map-item" data-hb-title="Claude Code" '
                      'data-hb-detail="端末で動く">Claude Code</button>')
        res = self.check(html)
        self.assertDetectionFails(res, "A11Y-01", count=1)
        self.assertEqual(1, res.rc, res)

    def test_role_button_element_is_in_scope(self):
        """[role="button"] も対象 (<button> だけを見ない)。"""
        html = mutate(good_html(), CHIP_MID,
                      '<div role="button" tabindex="0" class="pop-chip">中級</div>')
        self.assertDetectionFails(self.check(html), "A11Y-01", count=1)

    def test_single_select_group_allows_at_most_one_true(self):
        """data-hb-single のチップ群で aria-pressed=true が 2 個。"""
        html = mutate(good_html(), CHIP_MID,
                      '<button class="pop-chip" aria-pressed="true">中級</button>')
        self.assertDetectionFails(self.check(html), "A11Y-01", count=1)

    def test_single_select_group_allows_zero_true(self):
        """高々 1 個 — 0 個は違反ではない。"""
        html = mutate(good_html(), '<button class="pop-chip" aria-pressed="true">初級</button>',
                      '<button class="pop-chip" aria-pressed="false">初級</button>')
        self.assertDetectionPasses(self.check(html), "A11Y-01")

    def test_aux_button_is_excluded(self):
        """data-hb-part-role="aux" は唯一の除外口 (aria-pressed 不要)。"""
        self.assertDetectionPasses(self.check_good(), "A11Y-01")

    def test_aux_marker_is_the_only_exclusion(self):
        """除外マーカーを外せば同じボタンが違反になる (除外口が効いていることの裏取り)。"""
        html = mutate(good_html(), AUX_BTN,
                      '<button class="map-reset" aria-label="選択を解除する">解除</button>')
        self.assertDetectionFails(self.check(html), "A11Y-01", count=1)

    def test_buttons_outside_toggle_parts_are_not_required_to_have_it(self):
        """B08 / B15 の外にある通常ボタンは対象外。"""
        html = good_html(body_extra='<p><button class="plain">送信する</button></p>')
        self.assertDetectionPasses(self.check(html), "A11Y-01")

    def test_multiple_missing_are_counted_individually(self):
        html = good_html()
        html = mutate(html, CC_BTN,
                      '<button class="map-item" data-hb-title="Claude Code" '
                      'data-hb-detail="端末で動く">Claude Code</button>')
        html = mutate(html, CHIP_MID, '<button class="pop-chip">中級</button>')
        self.assertDetectionFails(self.check(html), "A11Y-01", count=2)


class TestA11y02AriaSelected(C17TestCase):
    """タブの aria-selected / tablist / tabpanel の対応。"""

    def test_two_selected_tabs(self):
        """AC-C17-04: aria-selected="true" が 2 個。"""
        html = mutate(good_html(), TAB_BUL,
                      '<button role="tab" aria-selected="true" aria-controls="p-bul" '
                      'id="t-bul">箇条書き</button>')
        self.assertDetectionFails(self.check(html), "A11Y-02", count=1)

    def test_zero_selected_tabs(self):
        """ちょうど 1 個 — 0 個も違反。"""
        html = mutate(good_html(), TAB_MD,
                      '<button role="tab" aria-selected="false" aria-controls="p-md" '
                      'id="t-md">Markdown</button>')
        html = mutate(html, PANEL_BUL, '<div id="p-bul" role="tabpanel" aria-labelledby="t-bul">')
        self.assertDetectionFails(self.check(html), "A11Y-02")

    def test_missing_tablist_role(self):
        html = mutate(good_html(), TABLIST_OPEN, '<div class="tabs" aria-label="記法">')
        self.assertDetectionFails(self.check(html), "A11Y-02")

    def test_missing_aria_selected_on_tab(self):
        html = mutate(good_html(), TAB_BUL,
                      '<button role="tab" aria-controls="p-bul" id="t-bul">箇条書き</button>')
        self.assertDetectionFails(self.check(html), "A11Y-02")

    def test_invalid_aria_selected_value(self):
        html = mutate(good_html(), TAB_BUL,
                      '<button role="tab" aria-selected="yes" aria-controls="p-bul" '
                      'id="t-bul">箇条書き</button>')
        self.assertDetectionFails(self.check(html), "A11Y-02")

    def test_aria_controls_points_to_missing_id(self):
        html = mutate(good_html(), TAB_BUL,
                      '<button role="tab" aria-selected="false" aria-controls="p-none" '
                      'id="t-bul">箇条書き</button>')
        self.assertDetectionFails(self.check(html), "A11Y-02")

    def test_aria_controls_missing_entirely(self):
        html = mutate(good_html(), TAB_BUL,
                      '<button role="tab" aria-selected="false" id="t-bul">箇条書き</button>')
        self.assertDetectionFails(self.check(html), "A11Y-02")

    def test_aria_controls_target_is_not_a_tabpanel(self):
        html = mutate(good_html(), PANEL_BUL, '<div id="p-bul" aria-labelledby="t-bul" hidden>')
        self.assertDetectionFails(self.check(html), "A11Y-02")

    def test_unselected_panel_without_hidden(self):
        html = mutate(good_html(), PANEL_BUL, '<div id="p-bul" role="tabpanel" aria-labelledby="t-bul">')
        self.assertDetectionFails(self.check(html), "A11Y-02")

    def test_selected_panel_with_hidden(self):
        html = mutate(good_html(), PANEL_MD,
                      '<div id="p-md" role="tabpanel" aria-labelledby="t-md" hidden>')
        self.assertDetectionFails(self.check(html), "A11Y-02")

    def test_pass_fixture_reports_checked_tabs(self):
        self.assertCheckedAtLeast(self.check_good(), "A11Y-02", 1)


class TestA11y03AccessibleName(C17TestCase):
    """対話要素がアクセシブル名を持つこと。"""

    def test_icon_only_button_without_label(self):
        html = mutate(good_html(), COPY_BTN,
                      '<button class="copy-btn">'
                      '<svg data-hb-kind="icon" aria-hidden="true" viewBox="0 0 24 24">'
                      '<path d="M8 8h10v10"/></svg></button>')
        self.assertDetectionFails(self.check(html), "A11Y-03", count=1)

    def test_whitespace_only_aria_label_is_violation(self):
        html = mutate(good_html(), 'aria-label="プロンプトをコピー"', 'aria-label=" "')
        self.assertDetectionFails(self.check(html), "A11Y-03", count=1)

    def test_empty_aria_label_is_violation(self):
        html = mutate(good_html(), 'aria-label="プロンプトをコピー"', 'aria-label=""')
        self.assertDetectionFails(self.check(html), "A11Y-03")

    def test_anchor_without_text(self):
        html = mutate(good_html(), TOC_LINK, '<a href="#s1"></a>')
        self.assertDetectionFails(self.check(html), "A11Y-03", count=1)

    def test_anchor_with_only_whitespace_text(self):
        html = mutate(good_html(), TOC_LINK, '<a href="#s1">  </a>')
        self.assertDetectionFails(self.check(html), "A11Y-03")

    def test_summary_without_text(self):
        html = mutate(good_html(), '<summary>補足を開く</summary>', '<summary></summary>')
        self.assertDetectionFails(self.check(html), "A11Y-03")

    def test_checkbox_without_label(self):
        html = mutate(good_html(), CHECKBOX, '<input id="ck1" type="checkbox"> 準備物を確認した')
        self.assertDetectionFails(self.check(html), "A11Y-03", count=1)

    def test_checkbox_with_label_for_passes(self):
        html = mutate(good_html(), CHECKBOX,
                      '<input id="ck1" type="checkbox"><label for="ck1">準備物を確認した</label>')
        self.assertDetectionPasses(self.check(html), "A11Y-03")

    def test_aria_labelledby_is_accepted(self):
        html = mutate(good_html(), 'aria-label="プロンプトをコピー"',
                      'aria-labelledby="t-md"')
        self.assertDetectionPasses(self.check(html), "A11Y-03")

    def test_title_attribute_is_accepted(self):
        html = mutate(good_html(), 'aria-label="プロンプトをコピー"',
                      'title="プロンプトをコピー"')
        self.assertDetectionPasses(self.check(html), "A11Y-03")

    def test_text_bearing_button_needs_no_label(self):
        self.assertDetectionPasses(self.check_good(), "A11Y-03")

    def test_anchor_without_href_is_out_of_scope(self):
        """対象は <a href> — href の無いアンカーは対話要素ではない。"""
        html = good_html(body_extra='<p><a id="mark"></a>目印</p>')
        self.assertDetectionPasses(self.check(html), "A11Y-03")

    def test_hidden_lightbox_close_button_is_still_checked(self):
        """hidden な要素も DOM 上は操作対象になりうるので検査から外さない。"""
        html = mutate(good_html(), ' aria-label="拡大表示を閉じる"', '')
        self.assertDetectionFails(self.check(html), "A11Y-03")


if __name__ == "__main__":
    unittest.main()

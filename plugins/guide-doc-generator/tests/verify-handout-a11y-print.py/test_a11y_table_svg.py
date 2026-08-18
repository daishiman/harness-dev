"""A11Y-04 (th の scope) / A11Y-05 (装飾 SVG と意味を持つ SVG) を赤で固定する。

正本: script-brief-C17.json の detections A11Y-04 / A11Y-05。
"""

import unittest

from hb_c17 import C17TestCase, good_html, mutate

THEAD_ROW = '<thead><tr><th scope="col">観点</th><th scope="col">Chat</th></tr></thead>'
TBODY_ROW = '<tbody><tr><th scope="row">得意なこと</th><td>要約</td></tr></tbody>'
ICON_S1 = ('<svg data-hb-kind="icon" aria-hidden="true" viewBox="0 0 24 24">'
           '<path d="M4 12l5 5L20 6"/></svg>')
FIGURE_SVG = ('<svg data-hb-kind="figure" viewBox="0 0 400 240"><title>処理の流れ</title>'
              '<rect x="8" y="8" width="120" height="60"/></svg>')


class TestA11y04TableScope(C17TestCase):

    def test_missing_scope_on_header_cell(self):
        html = mutate(good_html(), THEAD_ROW,
                      '<thead><tr><th>観点</th><th scope="col">Chat</th></tr></thead>')
        self.assertDetectionFails(self.check(html), "A11Y-04", count=1)

    def test_only_a11y04_fails_for_missing_scope(self):
        html = mutate(good_html(), THEAD_ROW,
                      '<thead><tr><th>観点</th><th scope="col">Chat</th></tr></thead>')
        self.assertOnlyThisDetectionFails(self.check(html), "A11Y-04")

    def test_thead_cell_with_scope_row_is_violation(self):
        """<thead> 内の th は col であること (存在だけでは足りない)。"""
        html = mutate(good_html(), THEAD_ROW,
                      '<thead><tr><th scope="col">観点</th><th scope="row">Chat</th></tr></thead>')
        self.assertDetectionFails(self.check(html), "A11Y-04", count=1)

    def test_row_header_with_scope_col_is_violation(self):
        html = mutate(good_html(), TBODY_ROW,
                      '<tbody><tr><th scope="col">得意なこと</th><td>要約</td></tr></tbody>')
        self.assertDetectionFails(self.check(html), "A11Y-04", count=1)

    def test_invalid_scope_value(self):
        html = mutate(good_html(), '<th scope="col">観点</th>', '<th scope="colgroup">観点</th>')
        self.assertDetectionFails(self.check(html), "A11Y-04")

    def test_empty_scope_value(self):
        html = mutate(good_html(), '<th scope="col">観点</th>', '<th scope="">観点</th>')
        self.assertDetectionFails(self.check(html), "A11Y-04")

    def test_table_without_data_hb_part_is_still_checked(self):
        """A11Y-04 だけは data-hb-part 非依存 (表は宣言漏れでも要件が変わらない)。"""
        html = good_html(body_extra='<table><tr><th>列</th><td>値</td></tr></table>')
        self.assertDetectionFails(self.check(html), "A11Y-04", count=1)

    def test_each_bad_cell_counted_individually(self):
        html = mutate(good_html(), THEAD_ROW, '<thead><tr><th>観点</th><th>Chat</th></tr></thead>')
        self.assertDetectionFails(self.check(html), "A11Y-04", count=2)

    def test_checked_counts_all_header_cells(self):
        self.assertCheckedAtLeast(self.check_good(), "A11Y-04", 3, "土台 fixture の th は 3 個")


class TestA11y05Svg(C17TestCase):

    def test_icon_in_text_parent_without_aria_hidden(self):
        """(a) テキストを持つ親の子である icon/decor svg は aria-hidden 必須。"""
        html = mutate(good_html(), ICON_S1,
                      '<svg data-hb-kind="icon" viewBox="0 0 24 24"><path d="M4 12l5 5L20 6"/></svg>')
        self.assertDetectionFails(self.check(html), "A11Y-05", count=1)

    def test_decor_in_text_parent_without_aria_hidden(self):
        html = good_html(body_extra='<p><svg data-hb-kind="decor" viewBox="0 0 40 40">'
                                    '<path d="M0 0h40"/></svg> 区切り</p>')
        self.assertDetectionFails(self.check(html), "A11Y-05", count=1)

    def test_aria_hidden_svg_with_title_is_contradiction(self):
        """(b) aria-hidden="true" の svg が <title> を持つのは矛盾。"""
        html = mutate(good_html(), ICON_S1,
                      '<svg data-hb-kind="icon" aria-hidden="true" viewBox="0 0 24 24">'
                      '<title>チェック</title><path d="M4 12l5 5L20 6"/></svg>')
        self.assertDetectionFails(self.check(html), "A11Y-05", count=1)

    def test_name_bearing_svg_hidden_removes_the_name(self):
        """(c) アクセシブル名の供給源である svg が aria-hidden なら違反。"""
        html = good_html(body_extra='<p><button class="close-btn">'
                                    '<svg data-hb-kind="icon" role="img" aria-label="閉じる" '
                                    'aria-hidden="true" viewBox="0 0 24 24">'
                                    '<path d="M6 6l12 12"/></svg></button></p>')
        self.assertDetectionFails(self.check(html), "A11Y-05", count=1)

    def test_figure_svg_is_excluded_from_rule_a(self):
        """data-hb-kind="figure" は (a) の対象外 (概念図解は装飾ではない)。"""
        self.assertDetectionPasses(self.check_good(), "A11Y-05")

    def test_figure_svg_without_title_or_label_is_violation(self):
        """(a) の対象外にする代わりに <title> または aria-label を必須とする。"""
        html = mutate(good_html(), FIGURE_SVG,
                      '<svg data-hb-kind="figure" viewBox="0 0 400 240">'
                      '<rect x="8" y="8" width="120" height="60"/></svg>')
        self.assertDetectionFails(self.check(html), "A11Y-05", count=1)

    def test_figure_svg_with_aria_label_passes(self):
        html = mutate(good_html(), FIGURE_SVG,
                      '<svg data-hb-kind="figure" role="img" aria-label="処理の流れ" '
                      'viewBox="0 0 400 240"><rect x="8" y="8" width="120" height="60"/></svg>')
        self.assertDetectionPasses(self.check(html), "A11Y-05")

    def test_icon_with_aria_hidden_and_sibling_text_passes(self):
        html = good_html(body_extra='<p><svg data-hb-kind="icon" aria-hidden="true" '
                                    'viewBox="0 0 24 24"><path d="M4 4h16"/></svg> 補足</p>')
        self.assertDetectionPasses(self.check(html), "A11Y-05")

    def test_aria_hidden_false_is_not_accepted_as_hidden(self):
        html = mutate(good_html(), ICON_S1,
                      '<svg data-hb-kind="icon" aria-hidden="false" viewBox="0 0 24 24">'
                      '<path d="M4 12l5 5L20 6"/></svg>')
        self.assertDetectionFails(self.check(html), "A11Y-05")

    def test_checked_counts_svg_elements(self):
        self.assertCheckedAtLeast(self.check_good(), "A11Y-05", 3)


if __name__ == "__main__":
    unittest.main()

"""SC-06 (アイコン様式) / SC-07 (symbol と use の対応) / SC-08 (ナビ整合) を赤で固定する。

正本: script-brief-C16.json#detections、AC-C16-05 / 06 / 07。
"""

import json
import unittest

from hb_c16 import C16TestCase, good_html


def icon_svg(**over):
    attrs = {
        "data-hb-kind": "icon",
        "viewBox": "0 0 24 24",
        "fill": "none",
        "stroke": "currentColor",
        "stroke-width": "2.2",
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
    }
    for k, v in over.items():
        key = k.replace("__", "-").replace("_", "-")
        if v is None:
            attrs.pop(key, None)
        else:
            attrs[key] = v
    body = " ".join('{}="{}"'.format(k, v) for k, v in attrs.items())
    return '<svg {}><path d="M4 12l5 5L20 6"/></svg>'.format(body)


class TestSC06IconStyle(C16TestCase):

    def test_conforming_icon_passes(self):
        self.assertAllPass(self.check(good_html(extra=icon_svg())))

    def test_viewbox_mismatch(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(viewBox="0 0 20 20"))), "SC-06")

    def test_viewbox_whitespace_is_normalized(self):
        self.assertAllPass(self.check(good_html(extra=icon_svg(viewBox=" 0  0   24 24 "))),
                           msg="空白正規化後の完全一致で判定する")

    def test_fill_currentcolor_is_violation(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(fill="currentColor"))), "SC-06")

    def test_stroke_literal_color_is_violation(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(stroke="#333"))), "SC-06")

    def test_missing_fill_attribute(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(fill=None))), "SC-06")

    def test_missing_stroke_linecap(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(stroke__linecap=None))), "SC-06")

    def test_missing_stroke_linejoin(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(stroke__linejoin=None))), "SC-06")

    def test_stroke_linecap_wrong_value(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(stroke__linecap="butt"))), "SC-06")

    def test_stroke_width_lower_bound_inclusive(self):
        self.assertAllPass(self.check(good_html(extra=icon_svg(stroke__width="2.2"))))

    def test_stroke_width_upper_bound_inclusive(self):
        self.assertAllPass(self.check(good_html(extra=icon_svg(stroke__width="2.6"))))

    def test_stroke_width_mid_range(self):
        self.assertAllPass(self.check(good_html(extra=icon_svg(stroke__width="2.4"))))

    def test_stroke_width_below_range(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(stroke__width="2.1"))), "SC-06")

    def test_stroke_width_above_range(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(stroke__width="2.7"))), "SC-06")

    def test_stroke_width_non_numeric(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(stroke__width="thick"))), "SC-06")

    def test_stroke_width_missing(self):
        self.assertDetectionFails(self.check(good_html(extra=icon_svg(stroke__width=None))), "SC-06")

    def test_mascot_kind_is_out_of_scope(self):
        snippet = '<svg data-hb-kind="mascot" width="40" height="40" viewBox="0 0 40 40"><path d="M0 0L1 1"/></svg>'
        self.assertAllPass(self.check(good_html(extra=snippet)), msg="mascot は様式検査の対象外")

    def test_decor_kind_is_out_of_scope(self):
        snippet = '<svg data-hb-kind="decor" viewBox="0 0 100 8"><path d="M0 4L100 4"/></svg>'
        self.assertAllPass(self.check(good_html(extra=snippet)), msg="decor は様式検査の対象外")

    def test_icon_symbol_is_also_checked(self):
        bad_symbol = ('<symbol id="ic-bad" data-hb-kind="icon" viewBox="0 0 20 20">'
                      '<path d="M0 0L1 1"/></symbol>')
        res = self.check(good_html(symbols=bad_symbol, extra=icon_svg().replace(
            '<path d="M4 12l5 5L20 6"/>', '<use href="#ic-bad"/>')))
        self.assertDetectionFails(res, "SC-06", msg="symbol も様式検査の対象")


class TestSC06Unclassified(C16TestCase):
    """AC-C16-05: data-hb-kind を持たない svg は分類不能として違反 1 件。"""

    HTML = good_html(extra='<svg width="18" height="18" viewBox="0 0 24 24"><path d="M0 0L1 1"/></svg>')

    def test_exit_one(self):
        self.assertEqual(1, self.check(self.HTML).rc)

    def test_one_unclassified_violation(self):
        self.assertDetectionFails(self.check(self.HTML), "SC-06", count=1)

    def test_message_mentions_classification(self):
        rows = self.check(self.HTML).violations("SC-06")
        self.assertTrue(any("data-hb-kind" in r["message"] for r in rows),
                        "分類不能の理由 (data-hb-kind 欠落) を message に出す\n{}".format(rows))

    def test_unclassified_symbol_is_also_violation(self):
        html = good_html(symbols='<symbol id="ic-x" viewBox="0 0 24 24"><path d="M0 0L1 1"/></symbol>',
                         extra='<svg data-hb-kind="decor" viewBox="0 0 24 24"><use href="#ic-x"/></svg>')
        self.assertDetectionFails(self.check(html), "SC-06")

    def test_unclassified_is_not_folded_into_pass(self):
        self.assertNotEqual(0, self.check(self.HTML).rc, "分類不能を暗黙 pass へ畳まない")


class TestSC07SymbolUse(C16TestCase):

    def test_balanced_document_passes(self):
        self.assertAllPass(self.check(good_html()))

    def test_unused_symbol(self):
        html = good_html(symbols='<symbol id="ic-extra" data-hb-kind="icon" viewBox="0 0 24 24" '
                                 'fill="none" stroke="currentColor" stroke-width="2.2" '
                                 'stroke-linecap="round" stroke-linejoin="round"><path d="M0 0L1 1"/></symbol>')
        self.assertDetectionFails(self.check(html), "SC-07", count=1)

    def test_undefined_use_reference(self):
        snippet = '<svg data-hb-kind="decor" viewBox="0 0 24 24"><use href="#ic-missing"/></svg>'
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-07", count=1)

    def test_duplicate_symbol_id(self):
        dup = ('<symbol id="ic-check" data-hb-kind="icon" viewBox="0 0 24 24" fill="none" '
               'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
               'stroke-linejoin="round"><path d="M0 0L1 1"/></symbol>')
        self.assertDetectionFails(self.check(good_html(symbols=dup)), "SC-07")

    def test_xlink_href_reference_is_recognized(self):
        """xlink:href 形の参照も U に数える (未使用と誤判定しない)。"""
        self.assertDetectionPasses(self.check(good_html()), "SC-07")

    def test_external_use_href_is_not_sc07(self):
        """`#` を持たない use@href は SC-01/SC-03 の領分。"""
        snippet = '<svg data-hb-kind="decor" viewBox="0 0 24 24"><use href="./sprite.svg#ic"/></svg>'
        res = self.check(good_html(extra=snippet))
        self.assertDetectionPasses(res, "SC-07")
        self.assertEqual(1, res.rc)

    def test_each_unused_id_counted_separately(self):
        base = ('<symbol id="{sid}" data-hb-kind="icon" viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
                'stroke-linejoin="round"><path d="M0 0L1 1"/></symbol>')
        html = good_html(symbols=base.format(sid="ic-a") + base.format(sid="ic-b"))
        self.assertDetectionFails(self.check(html), "SC-07", count=2)


class TestAcC16_06(C16TestCase):
    """AC-C16-06: 未使用 symbol 1 個 + 未定義 use 1 個 = 違反 2 件。"""

    HTML = good_html(
        symbols=('<symbol id="ic-extra" data-hb-kind="icon" viewBox="0 0 24 24" fill="none" '
                 'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
                 'stroke-linejoin="round"><path d="M0 0L1 1"/></symbol>'),
        extra='<svg data-hb-kind="decor" viewBox="0 0 24 24"><use href="#ic-missing"/></svg>')

    def test_exit_one(self):
        self.assertEqual(1, self.check(self.HTML).rc)

    def test_two_violations(self):
        self.assertDetectionFails(self.check(self.HTML), "SC-07", count=2)


class TestSC08NavAnchors(C16TestCase):

    def test_seven_to_seven_passes(self):
        self.assertAllPass(self.check(good_html()))

    def test_unresolved_nav_reference(self):
        self.assertDetectionFails(self.check(good_html(nav='<a href="#s8">追加</a>')), "SC-08", count=1)

    def test_unlinked_section(self):
        extra = '</section><section id="s9"><h2>おまけ</h2><p>本文</p>'
        self.assertDetectionFails(self.check(good_html(extra=extra)), "SC-08")

    def test_duplicate_href_in_nav(self):
        self.assertDetectionFails(self.check(good_html(nav='<a href="#s1">再掲</a>')), "SC-08")

    def test_empty_fragment_href_is_violation(self):
        self.assertDetectionFails(self.check(good_html(nav='<a href="#">先頭</a>')), "SC-08")

    def test_duplicate_id_in_document(self):
        extra = '</section><section id="s7"><h2>重複</h2><p>本文</p>'
        self.assertDetectionFails(self.check(good_html(extra=extra)), "SC-08")

    def test_navbar_class_element_is_treated_as_nav(self):
        """<nav> でなくとも class に navbar を含む要素は N の収集対象。"""
        html = good_html().replace('<nav class="navbar">', '<div class="site navbar sticky">') \
                          .replace("</nav>", "</div>")
        self.assertAllPass(self.check(html))

    def test_anchor_outside_nav_is_not_counted(self):
        """本文中の #s1 リンクは N ではないので重複違反にしない。"""
        self.assertAllPass(self.check(good_html(extra='<p><a href="#s1">導入へ戻る</a></p>')))


class TestAcC16_07(C16TestCase):
    """AC-C16-07: nav に #s8 を足し section は 7 個のまま。"""

    HTML = good_html(nav='<a href="#s8">補足</a>')

    def test_exit_one(self):
        self.assertEqual(1, self.check(self.HTML).rc)

    def test_single_unresolved_reference(self):
        self.assertDetectionFails(self.check(self.HTML), "SC-08", count=1)

    def test_violation_names_the_missing_id(self):
        rows = self.check(self.HTML).violations("SC-08")
        self.assertTrue(any("s8" in r["message"] + r["evidence"] for r in rows), rows)


if __name__ == "__main__":
    unittest.main()

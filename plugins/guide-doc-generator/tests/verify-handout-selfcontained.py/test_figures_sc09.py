"""SC-09 (R21 goal-spec C55: 図表・グラフの欠落) を赤で固定する。

正本: script-brief-C16.json#detections SC-09、AC-C16-R21-55a / 55b / 55c、
RESOLUTION-R21.md の C55 行。
『参照が外を向いていない』と『中身がある』は別の述語である、が要点。
"""

import unittest

from hb_c16 import (BIG_DATA_URI, DATA_URI_63, DATA_URI_64, EXTERNAL_REF_DETECTIONS,
                    C16TestCase, good_html)


def diagram(inner, part="DIAGRAM"):
    return ('<figure data-hb-part="{}"><svg data-hb-kind="decor" viewBox="0 0 400 240">{}</svg>'
            '<figcaption>収支の流れ</figcaption></figure>'.format(part, inner))


def img_part(src, part="IMG"):
    return '<div data-hb-part="{}"><img src="{}" alt="管理画面"></div>'.format(part, src)


class TestSC09EmptyDiagram(C16TestCase):

    def test_svg_with_only_title_is_violation(self):
        self.assertDetectionFails(
            self.check(good_html(extra=diagram("<title>収支の流れ</title>"))), "SC-09", count=1)

    def test_svg_with_only_title_and_desc_is_violation(self):
        self.assertDetectionFails(
            self.check(good_html(extra=diagram("<title>x</title><desc>y</desc>"))), "SC-09", count=1)

    def test_svg_with_only_defs_and_g_is_violation(self):
        self.assertDetectionFails(
            self.check(good_html(extra=diagram('<defs><linearGradient id="g"/></defs><g></g>'))),
            "SC-09", count=1)

    def test_rect_counts_as_drawing_element(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<rect x="1" y="1" width="9" height="9"/>'))))

    def test_path_counts_as_drawing_element(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<path d="M0 0L9 9"/>'))))

    def test_circle_counts_as_drawing_element(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<circle cx="5" cy="5" r="4"/>'))))

    def test_ellipse_counts_as_drawing_element(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<ellipse cx="5" cy="5" rx="4" ry="2"/>'))))

    def test_line_counts_as_drawing_element(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<line x1="0" y1="0" x2="9" y2="9"/>'))))

    def test_polyline_counts_as_drawing_element(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<polyline points="0,0 9,9"/>'))))

    def test_polygon_counts_as_drawing_element(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<polygon points="0,0 9,0 9,9"/>'))))

    def test_text_counts_as_drawing_element(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<text x="1" y="9">収支</text>'))))

    def test_use_counts_as_drawing_element(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<use href="#ic-check"/>'))))

    def test_nested_drawing_element_inside_g_counts(self):
        self.assertAllPass(self.check(good_html(extra=diagram('<g><rect x="1" y="1" width="9" height="9"/></g>'))))


class TestSC09EmptyImage(C16TestCase):

    def test_empty_data_uri(self):
        self.assertDetectionFails(self.check(good_html(extra=img_part("data:,"))), "SC-09", count=1)

    def test_data_uri_below_threshold(self):
        self.assertDetectionFails(self.check(good_html(extra=img_part(DATA_URI_63))), "SC-09", count=1)

    def test_data_uri_at_threshold_passes(self):
        self.assertAllPass(self.check(good_html(extra=img_part(DATA_URI_64))),
                           msg="実体長 64 バイトちょうどは違反にしない")

    def test_real_image_passes(self):
        self.assertAllPass(self.check(good_html(extra=img_part(BIG_DATA_URI))))

    def test_img_without_src_is_violation(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<div data-hb-part="IMG"><img alt="管理画面"></div>')), "SC-09")


class TestSC09EmptyFrame(C16TestCase):

    def test_figure_without_img_or_svg(self):
        self.assertDetectionFails(
            self.check(good_html(extra="<figure><figcaption>収支</figcaption></figure>")), "SC-09", count=1)

    def test_diagram_part_without_svg(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<div data-hb-part="DIAGRAM"><p>ここに図</p></div>')), "SC-09")

    def test_img_part_without_img(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<div data-hb-part="IMG"></div>')), "SC-09")


class TestSC09Placeholders(C16TestCase):

    def _fails(self, text):
        self.assertDetectionFails(
            self.check(good_html(extra=diagram('<rect x="1" y="1" width="9" height="9"/>').replace(
                "<figcaption>収支の流れ</figcaption>", "<figcaption>{}</figcaption>".format(text)))),
            "SC-09", count=1)

    def test_mustache_placeholder(self):
        self._fails("{{chart_summary}}")

    def test_todo_placeholder(self):
        self._fails("TODO")

    def test_japanese_figure_placeholder(self):
        self._fails("図はここに入ります")

    def test_japanese_chart_placeholder(self):
        self._fails("グラフを挿入")

    def test_english_chart_placeholder(self):
        self._fails("chart placeholder")

    def test_prefix_match_is_enough(self):
        self._fails("図はここに入ります (差し替え予定)")

    def test_legitimate_caption_passes(self):
        self.assertAllPass(self.check(good_html(
            extra=diagram('<rect x="1" y="1" width="9" height="9"/>'))))


class TestAcC16_R21_55a(C16TestCase):
    """空 DIAGRAM 1 / 空 data URI IMG 1 / 枠だけの figure 1 = SC-09 違反 3 件。"""

    HTML = good_html(extra=(diagram("<title>収支の流れ</title><desc>説明</desc>") +
                            img_part("data:,") +
                            "<figure><figcaption>後で差し替え</figcaption></figure>"))

    def test_exit_one(self):
        self.assertEqual(1, self.check(self.HTML).rc)

    def test_three_violations(self):
        self.assertDetectionFails(self.check(self.HTML), "SC-09", count=3)

    def test_violations_have_line_numbers(self):
        for row in self.check(self.HTML).violations("SC-09"):
            self.assertGreater(int(row["pos"].split(":")[0]), 0, row)

    def test_external_reference_detections_all_pass(self):
        """同一実行の中で『外部参照ゼロ検査 (SC-01..SC-04 / SC-10) を通過する欠陥クラス』であることを示す。"""
        res = self.check(self.HTML)
        for det in EXTERNAL_REF_DETECTIONS:
            self.assertDetectionPasses(res, det,
                                       msg="SC-09 の欠陥は外部参照検査では捕まらない")


class TestAcC16_R21_55b(C16TestCase):
    """正常な図表だけの HTML。checked の対象範囲の回帰テスト。"""

    HTML = good_html(extra=img_part(BIG_DATA_URI) + '<svg data-hb-kind="decor" viewBox="0 0 40 8">'
                                                    '<path d="M0 4L40 4"/></svg>')

    def test_exit_zero(self):
        self.assertEqual(0, self.check(self.HTML).rc, self.check(self.HTML))

    def test_violations_zero(self):
        self.assertDetectionPasses(self.check(self.HTML), "SC-09")

    def test_checked_counts_only_figure_targets(self):
        """土台の figure[data-hb-part=DIAGRAM] 1 件 + IMG 1 件 = 2。

        figure と data-hb-part が同一要素に付く場合は 1 件として数える (要素単位の集合)。
        """
        self.assertEqual(2, self.check(self.HTML).summary()["SC-09"]["checked"],
                         self.check(self.HTML))

    def test_decorative_svg_is_not_counted(self):
        """data-hb-part を持たない装飾 SVG は checked に数えない。"""
        with_decor = self.check(self.HTML).summary()["SC-09"]["checked"]
        without = self.check(good_html(extra=img_part(BIG_DATA_URI))).summary()["SC-09"]["checked"]
        self.assertEqual(without, with_decor)


class TestAcC16_R21_55c(C16TestCase):
    """キャプションに『図はここに入ります』が残った HTML。"""

    HTML = good_html(extra=('<figure data-hb-part="DIAGRAM"><svg data-hb-kind="decor" viewBox="0 0 400 240">'
                            '<rect x="1" y="1" width="9" height="9"/></svg>'
                            '<figcaption>図はここに入ります</figcaption></figure>'))

    def test_exit_one(self):
        self.assertEqual(1, self.check(self.HTML).rc)

    def test_single_placeholder_violation(self):
        self.assertDetectionFails(self.check(self.HTML), "SC-09", count=1)

    def test_caught_by_this_gate_not_narrative_gate(self):
        res = self.check(self.HTML)
        self.assertTrue(res.violations("SC-09"),
                        "欠落は自己完結性の欠陥として本ゲートで落とす\n{}".format(res))


if __name__ == "__main__":
    unittest.main()

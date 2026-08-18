"""SC-05 / CR-EMOJI (絵文字判定の単一正本・二層規則) を赤で固定する。

最重要の境界: Unicode ブロック丸ごとの denylist を使わないこと。
★ U+2605 / ☆ U+2606 / ✔ U+2714 (VS16 なし) / ♪ U+266A / ■ U+25A0 / © U+00A9 (VS16 なし)
は絵文字ではなく pass する。
"""

import json
import unittest

from hb_c16 import BIG_DATA_URI, C16TestCase, good_html


def para(text):
    return "<p>{}</p>".format(text)


class TestSC05PassesJapaneseSymbols(C16TestCase):
    """層 2 のコードポイントを VS16 なしで書いたときと、日本語の記号・約物。"""

    def _assert_passes(self, text, note=""):
        res = self.check(good_html(extra=para(text)))
        self.assertDetectionPasses(res, "SC-05", msg=note)
        self.assertAllPass(res, msg=note)

    def test_black_star_u2605(self):
        self._assert_passes("\u2605 重要", "★ は絵文字ではない")

    def test_white_star_u2606(self):
        self._assert_passes("\u2606 補足", "☆ は絵文字ではない")

    def test_heavy_check_u2714_without_vs16(self):
        self._assert_passes("\u2714 完了", "✔ (VS16 なし) は絵文字ではない")

    def test_eighth_note_u266a(self):
        self._assert_passes("\u266a BGM あり", "♪ は絵文字ではない")

    def test_black_square_u25a0(self):
        self._assert_passes("\u25a0 前提", "■ は絵文字ではない")

    def test_copyright_u00a9_without_vs16(self):
        self._assert_passes("Copyright \u00a9 2026 例", "© (VS16 なし) は法的表記")

    def test_registered_u00ae_without_vs16(self):
        self._assert_passes("製品名\u00ae", "® (VS16 なし) は通す")

    def test_trademark_u2122_without_vs16(self):
        self._assert_passes("製品名\u2122", "™ (VS16 なし) は通す")

    def test_black_right_triangle_u25b6_without_vs16(self):
        self._assert_passes("\u25b6 再生", "▶ (VS16 なし) は通す")

    def test_gear_u2699_without_vs16(self):
        """false_positive_risk として明記された意図的 false negative。"""
        self._assert_passes("\u2699 設定", "⚙ (VS16 なし) は通す (層 2)")

    def test_japanese_punctuation_set(self):
        self._assert_passes("、。「」『』・〜々〆 の約物一式", "U+3000-U+303F は非検出")

    def test_dashes_and_ellipsis(self):
        self._assert_passes("— – … 所要 30 分", "U+2010-U+2027 は非検出")

    def test_permille_and_daggers(self):
        self._assert_passes("‰ † ‡", "U+2030-U+205E は非検出")

    def test_geometric_shapes_block(self):
        self._assert_passes("□ ▲ △ ● ○", "U+25A0-U+25FF は非検出")

    def test_fullwidth_forms(self):
        self._assert_passes("ＡＢＣ１２３！？", "U+FF01-U+FF60 は非検出")

    def test_halfwidth_kana(self):
        self._assert_passes("ﾊﾝｶｸ ｶﾅ", "U+FF61-U+FF9F は非検出")

    def test_codepoint_just_outside_layer1_range(self):
        self._assert_passes("\U0001F030 と \U0001F09F", "層 1 の列挙範囲外は通す")

    def test_lone_zwj_passes(self):
        res = self.check(good_html(extra=para("A\u200dB")))
        self.assertDetectionPasses(res, "SC-05", msg="孤立 ZWJ は絵文字ではない")

    def test_vs15_passes(self):
        res = self.check(good_html(extra=para("\u2714\ufe0e 完了")))
        self.assertDetectionPasses(res, "SC-05", msg="VS1-VS15 は字形指定であり絵文字ではない")

    def test_inline_svg_icon_is_not_emoji(self):
        snippet = ('<svg data-hb-kind="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                   'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
                   '<use href="#ic-check"/></svg>')
        self.assertAllPass(self.check(good_html(extra=snippet)))


class TestSC05Layer1Violations(C16TestCase):
    """層 1 = 単独で違反。"""

    def _assert_fails(self, text, expect_cp, count=1):
        res = self.check(good_html(extra=para(text)))
        self.assertDetectionFails(res, "SC-05", count=count)
        blob = "\n".join(r["message"] + r["evidence"] for r in res.violations("SC-05"))
        self.assertIn(expect_cp, blob,
                      "違反行に U+XXXX のコードポイント列を出すこと\n{}".format(res))

    def test_pointing_hand(self):
        self._assert_fails("まずはここから \U0001F449 触ってみる", "U+1F449")

    def test_white_heavy_check_mark(self):
        self._assert_fails("\u2705 完了", "U+2705")

    def test_grinning_face(self):
        self._assert_fails("\U0001F600 はじめまして", "U+1F600")

    def test_skin_tone_modifier(self):
        self._assert_fails("\U0001F44D\U0001F3FB", "U+1F3FB", count=2)

    def test_star_emoji_u2b50(self):
        self._assert_fails("\u2b50 おすすめ", "U+2B50")

    def test_cross_mark_u274c(self):
        self._assert_fails("\u274c 非対応", "U+274C")

    def test_double_exclamation_u203c(self):
        self._assert_fails("重要\u203c", "U+203C")

    def test_interrobang_u2049(self):
        self._assert_fails("なぜ\u2049", "U+2049")

    def test_layer1_range_lower_bound(self):
        self._assert_fails("\U0001F000", "U+1F000")

    def test_layer1_range_upper_bound(self):
        self._assert_fails("\U0001FAFF", "U+1FAFF")

    def test_regional_indicator_flag_counts_two(self):
        """国旗は 2 連でも 1 件ずつ計上する。"""
        res = self.check(good_html(extra="<li>\U0001F1EF\U0001F1F5 日本語版</li>"))
        self.assertDetectionFails(res, "SC-05", count=2)


class TestSC05Layer2Violations(C16TestCase):
    """層 2 = 直後に U+FE0F が続くときのみ違反。"""

    def _assert_fails(self, text, expect_cp):
        res = self.check(good_html(extra=para(text)))
        self.assertDetectionFails(res, "SC-05")
        blob = "\n".join(r["message"] + r["evidence"] for r in res.violations("SC-05"))
        self.assertIn(expect_cp, blob)

    def test_gear_with_vs16(self):
        self._assert_fails("\u2699\ufe0f 設定", "U+2699")

    def test_copyright_with_vs16(self):
        self._assert_fails("\u00a9\ufe0f 2026", "U+00A9")

    def test_check_mark_with_vs16(self):
        self._assert_fails("\u2714\ufe0f 完了", "U+2714")

    def test_heart_with_vs16(self):
        self._assert_fails("\u2764\ufe0f", "U+2764")

    def test_right_arrow_with_vs16(self):
        self._assert_fails("\u27a1\ufe0f 次へ", "U+27A1")

    def test_vs16_itself_is_layer1(self):
        """U+FE0F は絵文字表示指定そのものなので層 1。"""
        res = self.check(good_html(extra=para("A\ufe0f")))
        self.assertDetectionFails(res, "SC-05")


class TestSC05Sequences(C16TestCase):

    def test_keycap_sequence(self):
        res = self.check(good_html(extra=para("1\ufe0f\u20e3")))
        self.assertDetectionFails(res, "SC-05")
        blob = "\n".join(r["message"] + r["evidence"] for r in res.violations("SC-05"))
        self.assertIn("U+20E3", blob)

    def test_zwj_next_to_layer1_is_violation(self):
        res = self.check(good_html(extra=para("\U0001F468\u200d\U0001F4BB")))
        self.assertDetectionFails(res, "SC-05")
        blob = "\n".join(r["message"] + r["evidence"] for r in res.violations("SC-05"))
        self.assertIn("U+200D", blob, "絵文字連結シーケンスの ZWJ は違反")

    def test_tag_characters_are_layer1(self):
        res = self.check(good_html(extra=para("\U000E0067")))
        self.assertDetectionFails(res, "SC-05")


class TestSC05ScanScope(C16TestCase):
    """走査範囲: text node・全属性値・<style>・<script> 本文。"""

    def test_emoji_in_alt_attribute(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<img src="{}" alt="完了 \u2705">'.format(BIG_DATA_URI))), "SC-05")

    def test_emoji_in_style_body(self):
        self.assertDetectionFails(
            self.check(good_html(head='<style>.a::before{content:"\U0001F449"}</style>')), "SC-05")

    def test_emoji_in_script_body(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<script>var label="\U0001F680";</script>')), "SC-05")

    def test_numeric_character_reference_is_decoded(self):
        """convert_charrefs=True — 数値文字参照経由の混入も捕捉する。"""
        self.assertDetectionFails(self.check(good_html(extra=para("&#x1F449;"))), "SC-05")

    def test_decimal_character_reference_is_decoded(self):
        self.assertDetectionFails(self.check(good_html(extra=para("&#128073;"))), "SC-05")

    def test_base64_payload_is_excluded_from_scan(self):
        """base64 本体は ASCII 部分集合なので走査から除外しても検出漏れを生まない。"""
        self.assertAllPass(self.check(good_html(extra='<img src="{}" alt="図">'.format(BIG_DATA_URI))))

    def test_emoji_count_is_per_codepoint(self):
        res = self.check(good_html(extra=para("\U0001F449\U0001F449\u2705")))
        self.assertDetectionFails(res, "SC-05", count=3)


class TestAcC16_03(C16TestCase):
    """AC-C16-03: 日本語約物と記号だけの HTML は exit 0。"""

    HTML = good_html(extra=para("、。「」・…〜 \u2605 \u266a \u25a0 \u00a9 だけの本文"))

    def test_exit_zero(self):
        self.assertEqual(0, self.check(self.HTML).rc, self.check(self.HTML))

    def test_sc05_violations_zero(self):
        self.assertDetectionPasses(self.check(self.HTML), "SC-05")


class TestAcC16_04(C16TestCase):
    """AC-C16-04: 5 種の絵文字を 1 個ずつ含む HTML。"""

    HTML = good_html(extra=(para("\U0001F449") + para("\u2705") +
                            para("\U0001F1EF\U0001F1F5") + para("\u2699\ufe0f") +
                            para("1\ufe0f\u20e3")))

    def test_exit_one(self):
        self.assertEqual(1, self.check(self.HTML).rc)

    def test_at_least_five_violations(self):
        self.assertGreaterEqual(self.check(self.HTML).summary()["SC-05"]["violations"], 5)

    def test_every_violation_line_has_codepoints(self):
        for row in self.check(self.HTML).violations("SC-05"):
            self.assertRegex(row["message"] + row["evidence"], r"U\+[0-9A-F]{4,6}")

    def test_report_records_codepoints_field(self):
        _, rep = self.report_for(self.HTML)
        sc05 = [d for d in rep["detections"] if d["id"] == "SC-05"][0]
        self.assertTrue(sc05["violations"])
        for v in sc05["violations"]:
            self.assertIn("codepoints", v)


class TestSC05InfoRecords(C16TestCase):
    """判定は通すが人間レビューへ渡すもの (json-report の info)。"""

    def test_layer2_without_vs16_is_listed_as_info(self):
        _, rep = self.report_for(good_html(extra=para("\u2699 設定")))
        blob = json.dumps(rep, ensure_ascii=False)
        self.assertIn("U+2699", blob, "層 2 の VS16 なし出現は info として列挙する")

    def test_lone_zwj_is_listed_as_info(self):
        _, rep = self.report_for(good_html(extra=para("A\u200dB")))
        self.assertIn("U+200D", json.dumps(rep, ensure_ascii=False))

    def test_variation_selector_1_to_15_is_listed_as_info(self):
        _, rep = self.report_for(good_html(extra=para("\u2714\ufe0e")))
        self.assertIn("U+FE0E", json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()

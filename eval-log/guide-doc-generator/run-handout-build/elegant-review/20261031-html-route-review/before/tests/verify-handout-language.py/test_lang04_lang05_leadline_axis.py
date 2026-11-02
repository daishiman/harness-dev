# -*- coding: utf-8 -*-
"""LANG-04 (lead-line の存在) と LANG-05 (判断軸の一文の存在と形式)。

正本: script-brief-C18.json detections#LANG-04 / #LANG-05 と
failure_modes「HTML の section に data-hb-field が付いていない」。
"""

from __future__ import annotations

import unittest

from _support import SECTION_DEFS, LanguageGateTestCase, base_config, build_html


class TestLang04Presence(LanguageGateTestCase):
    def test_all_sections_have_exactly_one_lead_line(self):
        res = self.run_default()
        self.assert_detection_pass(res, "LANG-04")

    def test_checked_equals_section_count(self):
        res = self.run_default()
        self.assertEqual(
            len(SECTION_DEFS), self.checked(res, "LANG-04"), "checked は section の件数"
        )

    def test_missing_lead_line_is_a_violation(self):
        res = self.run_default(omit_lead_line={"s3"})
        self.assert_gate_fail(res, "LANG-04", count=1)

    def test_missing_lead_line_names_the_section(self):
        res = self.run_default(omit_lead_line={"s3"})
        joined = "\n".join("\t".join(r) for r in self.stderr_rows(res, "LANG-04"))
        self.assertIn("s3", joined, "違反行に section id が出る\n%s" % joined)

    def test_two_lead_lines_is_a_violation(self):
        """2 個以上は『どれが抽象 1 行か』が決まらないので違反。"""
        res = self.run_default(duplicate_lead_line={"s1"})
        self.assert_gate_fail(res, "LANG-04", count=1)

    def test_blank_lead_line_is_a_violation(self):
        res = self.run_default(blank_lead_line={"s4"})
        self.assert_gate_fail(res, "LANG-04", count=1)

    def test_multiple_sections_missing_lead_line(self):
        res = self.run_default(omit_lead_line={"s3", "s4"})
        self.assert_gate_fail(res, "LANG-04", count=2)

    def test_section_identified_by_id_only_is_still_checked(self):
        """data-hb-part="section" が無くても id を持つ <section> は対象。"""
        res = self.run_default(
            section_without_hb_part={"s3"}, omit_lead_line={"s3"}
        )
        self.assert_gate_fail(res, "LANG-04", count=1)

    def test_lead_line_outside_any_section_does_not_satisfy_a_section(self):
        cfg = base_config()
        html = build_html(cfg, omit_lead_line={"s3"})
        html = html.replace(
            "<footer", '<p data-hb-field="lead_line">外置きの抽象行。</p>\n<footer'
        )
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_gate_fail(res, "LANG-04", count=1)


class TestLang05Presence(LanguageGateTestCase):
    def test_all_sections_have_exactly_one_judgment_axis(self):
        res = self.run_default()
        self.assert_detection_pass(res, "LANG-05")

    def test_missing_judgment_axis_is_a_violation(self):
        res = self.run_default(omit_judgment_axis={"s4"})
        self.assert_gate_fail(res, "LANG-05", count=1)

    def test_empty_judgment_axis_is_a_violation(self):
        res = self.run_default(blank_judgment_axis={"s2"})
        self.assert_gate_fail(res, "LANG-05", count=1)

    def test_two_judgment_axes_is_a_violation(self):
        res = self.run_default(duplicate_judgment_axis={"s1"})
        self.assert_gate_fail(res, "LANG-05", count=1)

    def test_violation_row_names_the_section(self):
        res = self.run_default(omit_judgment_axis={"s4"})
        joined = "\n".join("\t".join(r) for r in self.stderr_rows(res, "LANG-05"))
        self.assertIn("s4", joined)


class TestLang05SentenceForm(LanguageGateTestCase):
    """形式条件: 句点 / ? / ？ で終わるか、80 文字以内であること。"""

    def test_sentence_ending_with_ideographic_full_stop_passes(self):
        res = self.run_default(judgment_axis_text={"s1": "迷ったら、やり直しが利くかで決める。"})
        self.assert_detection_pass(res, "LANG-05")

    def test_sentence_ending_with_fullwidth_question_mark_passes(self):
        res = self.run_default(judgment_axis_text={"s1": "誰が見て、次に何につながる？"})
        self.assert_detection_pass(res, "LANG-05")

    def test_sentence_ending_with_ascii_question_mark_passes(self):
        res = self.run_default(judgment_axis_text={"s1": "誰が見て、次に何につながる?"})
        self.assert_detection_pass(res, "LANG-05")

    def test_short_sentence_without_terminator_passes(self):
        """80 文字以内なら終止記号が無くても形式条件を満たす。"""
        res = self.run_default(judgment_axis_text={"s1": "迷ったら、やり直しが利くかで決める"})
        self.assert_detection_pass(res, "LANG-05")

    def test_long_text_without_terminator_is_a_violation(self):
        long_text = "この判断軸はとても長く、" * 12  # 80 文字超・終止記号なし
        self.assertGreater(len(long_text), 80)
        res = self.run_default(judgment_axis_text={"s1": long_text.rstrip("、")})
        self.assert_gate_fail(res, "LANG-05", count=1)

    def test_long_text_with_terminator_passes(self):
        long_text = "この判断軸はとても長く、" * 12 + "決める。"
        self.assertGreater(len(long_text), 80)
        res = self.run_default(judgment_axis_text={"s1": long_text})
        self.assert_detection_pass(res, "LANG-05")

    def test_exactly_80_characters_without_terminator_passes(self):
        res = self.run_default(judgment_axis_text={"s1": "あ" * 80})
        self.assert_detection_pass(res, "LANG-05")

    def test_81_characters_without_terminator_is_a_violation(self):
        res = self.run_default(judgment_axis_text={"s1": "あ" * 81})
        self.assert_gate_fail(res, "LANG-05", count=1)


class TestAnchorAbsence(LanguageGateTestCase):
    """failure_modes: data-hb-field が付いていない HTML を PASS へ畳まない。"""

    def _stripped(self):
        cfg = base_config()
        import re

        html = re.sub(r'\s*data-hb-field="[a-z_]+"', "", build_html(cfg))
        return self.write_html(html), self.write_config(cfg)

    def test_no_anchors_at_all_is_exit1_not_exit0(self):
        html, config = self._stripped()
        res = self.run_gate(html=html, config=config)
        self.assertEqual(
            1, res.returncode, "検査アンカー不在は PASS へ畳まず exit 1\nstdout=%s" % res.stdout
        )

    def test_no_anchors_fails_lang04(self):
        html, config = self._stripped()
        res = self.run_gate(html=html, config=config)
        self.assertEqual("FAIL", self.summary(res)["LANG-04"]["status"])

    def test_no_anchors_fails_lang05(self):
        html, config = self._stripped()
        res = self.run_gate(html=html, config=config)
        self.assertEqual("FAIL", self.summary(res)["LANG-05"]["status"])

    def test_no_anchors_fails_lang06(self):
        html, config = self._stripped()
        res = self.run_gate(html=html, config=config)
        self.assertEqual("FAIL", self.summary(res)["LANG-06"]["status"])

    def test_no_anchors_fails_date01(self):
        html, config = self._stripped()
        res = self.run_gate(html=html, config=config)
        self.assertEqual("FAIL", self.summary(res)["DATE-01"]["status"])

    def test_no_anchors_is_not_reported_as_checked_zero_pass(self):
        html, config = self._stripped()
        res = self.run_gate(html=html, config=config)
        for det in ("LANG-04", "LANG-05", "LANG-06"):
            self.assertNotEqual(
                "PASS", self.summary(res)[det]["status"], "%s を checked=0 PASS にしない" % det
            )


class TestSectionSetDisagreement(LanguageGateTestCase):
    """HTML の section が config より少ない場合も、描画された分は検査する。"""

    def test_html_missing_a_section_reduces_checked(self):
        res = self.run_default(omit_sections={"s4"})
        self.assertEqual(
            len(SECTION_DEFS) - 1,
            self.checked(res, "LANG-04"),
            "LANG-04 は描画された section を数える (集合一致の判定は C22 NAR-06 の責務)",
        )


if __name__ == "__main__":
    unittest.main()

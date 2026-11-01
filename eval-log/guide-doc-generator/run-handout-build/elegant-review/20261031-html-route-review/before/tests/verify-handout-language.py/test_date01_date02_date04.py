# -*- coding: utf-8 -*-
"""DATE-01 (書式) / DATE-02 (config との一致) / DATE-04 (文書内の一貫性)。

正本: script-brief-C18.json detections#DATE-01 / #DATE-02 / #DATE-04、
acceptance_checks AC-C18-07 / AC-C18-08、failure_modes「date-pill が 1 個も無い」。
R18 の表示正本は yyyy/mm/dd ただ一つ。script は書式変換を一切行わない。
"""

from __future__ import annotations

import json
import unittest

from _support import CONFIG_DATE, LanguageGateTestCase, base_config, build_html


class TestDate01Format(LanguageGateTestCase):
    def test_zero_padded_slash_form_passes(self):
        res = self.run_default()
        self.assert_detection_pass(res, "DATE-01")

    def test_ac07_missing_zero_padding_is_a_violation(self):
        res = self.run_default(date_pill_text="2026/8/17")
        self.assert_gate_fail(res, "DATE-01")

    def test_ac07_missing_zero_padding_in_day_is_a_violation(self):
        res = self.run_default(date_pill_text="2026/08/7")
        self.assert_gate_fail(res, "DATE-01")

    def test_hyphen_separator_is_a_violation(self):
        res = self.run_default(date_pill_text="2026-08-17")
        self.assert_gate_fail(res, "DATE-01")

    def test_dot_separator_is_a_violation(self):
        res = self.run_default(date_pill_text="2026.08.17")
        self.assert_gate_fail(res, "DATE-01")

    def test_weekday_suffix_is_a_violation(self):
        """完全一致。曜日併記は現案では一律違反 (open_questions 参照)。"""
        res = self.run_default(date_pill_text="2026/08/17 (月)")
        self.assert_gate_fail(res, "DATE-01")

    def test_japanese_era_is_a_violation(self):
        res = self.run_default(date_pill_text="令和8年8月17日")
        self.assert_gate_fail(res, "DATE-01")

    def test_surrounding_whitespace_is_trimmed_not_a_violation(self):
        cfg = base_config()
        html = build_html(cfg).replace(
            '>%s</span>' % CONFIG_DATE, '>\n  %s\n  </span>' % CONFIG_DATE
        )
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_detection_pass(res, "DATE-01")

    def test_ac08_nonexistent_calendar_date_is_a_violation(self):
        res = self.run_default(date_pill_text="2026/02/30")
        self.assert_gate_fail(res, "DATE-01")

    def test_ac08_nonexistent_date_reason_is_distinguishable(self):
        res = self.run_default(date_pill_text="2026/02/30")
        reason = "\t".join(self.stderr_rows(res, "DATE-01")[0][3:])
        self.assertTrue(
            "実在" in reason or "不存在" in reason or "暦" in reason,
            "『暦として実在しない日付』と読める理由を出す\nreason=%r" % reason,
        )

    def test_month_13_is_a_violation(self):
        res = self.run_default(date_pill_text="2026/13/01")
        self.assert_gate_fail(res, "DATE-01")

    def test_leap_day_of_a_leap_year_passes(self):
        cfg = base_config(date="2028/02/29")
        res = self.run_default(cfg, date_pill_text="2028/02/29")
        self.assert_detection_pass(res, "DATE-01")

    def test_leap_day_of_a_common_year_is_a_violation(self):
        res = self.run_default(date_pill_text="2026/02/29")
        self.assert_gate_fail(res, "DATE-01")


class TestDate01Position(LanguageGateTestCase):
    def test_date_in_header_passes(self):
        res = self.run_default(date_pill_position="header")
        self.assert_detection_pass(res, "DATE-01")

    def test_date_inside_hero_is_a_violation(self):
        """<header> 内でも hero より前でもない位置は違反。"""
        res = self.run_default(date_pill_position="hero")
        self.assert_gate_fail(res, "DATE-01")

    def test_date_after_hero_in_a_section_is_a_violation(self):
        res = self.run_default(date_pill_position="section")
        self.assert_gate_fail(res, "DATE-01")

    def test_missing_date_pill_is_a_violation(self):
        res = self.run_default(date_pill_position="none")
        self.assert_gate_fail(res, "DATE-01")

    def test_missing_date_pill_also_marks_date02_unsatisfied(self):
        """failure_modes: date-pill 不在は DATE-02 も未充足として計上する。"""
        res = self.run_default(date_pill_position="none")
        self.assertEqual(
            "FAIL",
            self.summary(res)["DATE-02"]["status"],
            "DATE-02 を checked=0 PASS へ畳まない\nstdout=%s" % res.stdout,
        )

    def test_missing_date_pill_is_exit1_not_exit2(self):
        res = self.run_default(date_pill_position="none")
        self.assertEqual(1, res.returncode, "R18 の不在は明確な FAIL (検査不成立ではない)")


class TestDate02Match(LanguageGateTestCase):
    def test_matching_value_passes(self):
        res = self.run_default()
        self.assert_detection_pass(res, "DATE-02")

    def test_off_by_one_day_is_a_violation(self):
        res = self.run_default(date_pill_text="2026/08/16")
        self.assert_gate_fail(res, "DATE-02")

    def test_violation_row_shows_both_values(self):
        res = self.run_default(date_pill_text="2026/08/16")
        joined = "\n".join("\t".join(r) for r in self.stderr_rows(res, "DATE-02"))
        self.assertIn("2026/08/16", joined)
        self.assertIn(CONFIG_DATE, joined, "config.date 側の値も出す")

    def test_no_format_conversion_is_performed(self):
        """script は書式変換を挟まない。ハイフン形は DATE-02 でも一致にしない。"""
        res = self.run_default(date_pill_text="2026-08-17")
        self.assertGreaterEqual(
            self.violations(res, "DATE-02"), 1, "変換して一致させてはならない"
        )

    def test_config_is_the_only_source_of_truth(self):
        """自前で今日の日付を取らない = 過去日でも未来日でも一致すれば PASS。"""
        cfg = base_config(date="1999/01/01")
        res = self.run_default(cfg, date_pill_text="1999/01/01")
        self.assert_detection_pass(res, "DATE-02")


class TestDate04Consistency(LanguageGateTestCase):
    def test_single_date_pill_passes(self):
        res = self.run_default()
        self.assert_detection_pass(res, "DATE-04")

    def test_two_identical_date_pills_pass(self):
        res = self.run_default(extra_date_pills=[CONFIG_DATE])
        self.assert_detection_pass(res, "DATE-04")

    def test_two_different_date_pills_are_a_violation(self):
        res = self.run_default(extra_date_pills=["2026/08/10"])
        self.assert_gate_fail(res, "DATE-04")

    def test_body_mentioning_another_date_is_not_a_violation(self):
        res = self.run_default(footer_texts=["提出期限は 2026/08/24 までです。"])
        self.assert_detection_pass(res, "DATE-04")
        self.assert_gate_pass(res)

    def test_body_date_is_listed_as_info_in_the_report(self):
        report = self.tmpdir / "report.json"
        self.run_default(
            json_report=report, footer_texts=["提出期限は 2026/08/24 までです。"]
        )
        text = json.dumps(self.read_report(report), ensure_ascii=False)
        self.assertIn("2026/08/24", text, "本文の別日付は info として json-report に列挙する")

    def test_non_zero_padded_body_date_is_also_collected_as_info(self):
        report = self.tmpdir / "report.json"
        self.run_default(json_report=report, footer_texts=["開催日は 2026/9/3 です。"])
        text = json.dumps(self.read_report(report), ensure_ascii=False)
        self.assertIn("2026/9/3", text, "本文日付の収集は \\d{4}/\\d{1,2}/\\d{1,2}")

    def test_body_date_equal_to_config_is_not_info(self):
        report = self.tmpdir / "report.json"
        res = self.run_default(
            json_report=report, footer_texts=["この資料の日付は %s です。" % CONFIG_DATE]
        )
        self.assert_gate_pass(res)
        self.assertEqual(0, self.violations(res, "DATE-04"))


if __name__ == "__main__":
    unittest.main()

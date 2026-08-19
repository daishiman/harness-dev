# -*- coding: utf-8 -*-
"""DATE-03: 出力ディレクトリ名の日付が構成データと一致すること (goal-spec C35)。

R17 のハイフン形 <YYYY-MM-DD> は命名専用の派生表現であり、R18 の表示正本
(yyyy/mm/dd) とは別概念。表示は DATE-01/02、命名は本項目。
種別語彙と slug の妥当性は C19 の責務なので判定しない。

正本: script-brief-C18.json detections#DATE-03、
acceptance_checks AC-C18-09 / AC-C18-10。
"""

from __future__ import annotations

import unittest

from _support import (
    CONFIG_DATE,
    LanguageGateTestCase,
    base_config,
    out_dir_name,
)


class TestDate03NotRequested(LanguageGateTestCase):
    """AC-C18-10: --out-dir 未指定は skip でも PASS でもなく NOT-REQUESTED。"""

    def test_status_is_not_requested(self):
        res = self.run_default()
        self.assertEqual("NOT-REQUESTED", self.summary(res)["DATE-03"]["status"])

    def test_status_is_not_pass(self):
        res = self.run_default()
        self.assertNotEqual(
            "PASS",
            self.summary(res)["DATE-03"]["status"],
            "評価していないものを PASS と表示しない",
        )

    def test_status_is_not_skip(self):
        res = self.run_default()
        self.assertNotEqual("SKIP", self.summary(res)["DATE-03"]["status"])

    def test_other_detections_still_pass_and_exit_zero(self):
        res = self.run_default()
        self.assert_gate_pass(res)

    def test_not_requested_produces_no_stderr_row(self):
        res = self.run_default()
        self.assertEqual([], self.stderr_rows(res, "DATE-03"))


class TestDate03Match(LanguageGateTestCase):
    def _run(self, dir_name, cfg=None):
        out_dir = self.make_out_dir(dir_name)
        return self.run_default(cfg, out_dir=out_dir)

    def test_matching_directory_name_passes(self):
        res = self._run(out_dir_name())
        self.assert_detection_pass(res, "DATE-03")

    def test_checked_is_one_when_requested(self):
        res = self._run(out_dir_name())
        self.assertEqual(1, self.checked(res, "DATE-03"))

    def test_ac09_date_mismatch_is_a_violation(self):
        res = self._run(out_dir_name(date="2026/08/16"))
        self.assert_gate_fail(res, "DATE-03", count=1)

    def test_ac09_violation_row_shows_both_values(self):
        res = self._run(out_dir_name(date="2026/08/16"))
        joined = "\n".join("\t".join(r) for r in self.stderr_rows(res, "DATE-03"))
        self.assertIn("2026-08-16", joined)
        self.assertIn(CONFIG_DATE.replace("/", "-"), joined, "純変換後の期待値も出す")

    def test_missing_zero_padding_is_a_violation(self):
        res = self._run(out_dir_name(date="2026/8/17"))
        self.assert_gate_fail(res, "DATE-03", count=1)

    def test_date_not_at_the_head_is_a_violation(self):
        res = self._run("lecture-2026-08-17-claude-intro")
        self.assert_gate_fail(res, "DATE-03", count=1)

    def test_slash_form_in_directory_name_is_a_violation(self):
        """命名側の派生表現はハイフン形のみ。表示正本をそのまま使うのは違反。"""
        res = self._run(out_dir_name(date="2026.08.17"))
        self.assert_gate_fail(res, "DATE-03", count=1)

    def test_missing_separator_after_the_date_is_a_violation(self):
        """11 文字目が dir_name_format の区切り文字であること。"""
        res = self._run("2026-08-17" + "lecture-claude-intro")
        self.assert_gate_fail(res, "DATE-03", count=1)

    def test_date_only_directory_name_is_a_violation(self):
        res = self._run("2026-08-17")
        self.assert_gate_fail(res, "DATE-03", count=1)

    def test_trailing_slash_does_not_change_the_basename(self):
        out_dir = self.make_out_dir(out_dir_name())
        html, config = self.write_pair()
        res = self.run_gate(html=html, config=config, out_dir=str(out_dir) + "/")
        self.assert_detection_pass(res, "DATE-03")

    def test_parent_directory_name_is_not_used(self):
        parent = self.make_out_dir("2026-08-16-wrong", with_file=False)
        target = parent / out_dir_name()
        target.mkdir()
        html, config = self.write_pair()
        res = self.run_gate(html=html, config=config, out_dir=target)
        self.assert_detection_pass(res, "DATE-03")


class TestDate03BoundaryWithC19(LanguageGateTestCase):
    """種別語彙と slug の妥当性は C19 の責務 = ここでは判定しない。"""

    def _run(self, dir_name):
        return self.run_default(out_dir=self.make_out_dir(dir_name))

    def test_unknown_doc_type_word_is_not_a_violation(self):
        res = self._run(out_dir_name(slug="まったく未知の種別-claude-intro"))
        self.assert_detection_pass(res, "DATE-03")

    def test_uppercase_slug_is_not_a_violation(self):
        res = self._run(out_dir_name(slug="lecture-CLAUDE_Intro"))
        self.assert_detection_pass(res, "DATE-03")

    def test_slug_mismatch_with_config_is_not_a_violation(self):
        res = self._run(out_dir_name(slug="lecture-something-else"))
        self.assert_detection_pass(res, "DATE-03")

    def test_doc_type_mismatch_with_config_is_not_a_violation(self):
        res = self._run(out_dir_name(slug="manual-claude-intro"))
        self.assert_detection_pass(res, "DATE-03")


class TestDate03PureConversion(LanguageGateTestCase):
    """比較値は config.date.replace('/', '-') の純変換 (C19 と同一)。"""

    def test_other_config_date_drives_the_expected_name(self):
        cfg = base_config(date="2027/01/05")
        out_dir = self.make_out_dir(out_dir_name(date="2027/01/05"))
        res = self.run_default(cfg, out_dir=out_dir, date_pill_text="2027/01/05")
        self.assert_detection_pass(res, "DATE-03")

    def test_stale_directory_name_is_caught_after_config_date_change(self):
        cfg = base_config(date="2027/01/05")
        out_dir = self.make_out_dir(out_dir_name())
        res = self.run_default(cfg, out_dir=out_dir, date_pill_text="2027/01/05")
        self.assert_gate_fail(res, "DATE-03", count=1)

    def test_date03_is_independent_of_date01_result(self):
        """date-pill が壊れていても DATE-03 は独立に評価される。"""
        out_dir = self.make_out_dir(out_dir_name())
        res = self.run_default(out_dir=out_dir, date_pill_text="2026/8/17")
        self.assertEqual("FAIL", self.summary(res)["DATE-01"]["status"])
        self.assert_detection_pass(res, "DATE-03")


if __name__ == "__main__":
    unittest.main()

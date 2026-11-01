# -*- coding: utf-8 -*-
"""検証面の分界 (AC-C22-11 / AC-C22-12) と再現性 (AC-C22-14)。

C22 は R19 専任であり、R11 (lead-line / 判断軸 / 用語の言い換え) と R18 (日付) は
C18 verify-handout-language.py の担当。一方が他方を代替しないことを回帰で固定する。
"""

from __future__ import annotations

import unittest

from _support import (
    DETECTION_ORDER,
    JUDGMENT_AXIS_TEXT,
    LEAD_LINE_TEXT,
    NarrativeGateTestCase,
    base_config,
    build_html,
)


class TestR11IsOutOfScope(NarrativeGateTestCase):
    """AC-C22-11: R11 の欠落を本ゲートは検出しない。"""

    def test_lead_line_and_axis_removed_still_passes(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, include_lead_line=False, include_judgment_axis=False))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_lead_line_only_removed_still_passes(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, include_lead_line=False))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_judgment_axis_only_removed_still_passes(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, include_judgment_axis=False))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_no_detection_row_mentions_lead_line_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, include_lead_line=False, include_judgment_axis=False))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertNotIn("lead_line", res.stderr)
        self.assertNotIn("judgment_axis", res.stderr)

    def test_glossary_absence_is_not_checked(self):
        # 専門用語の初出言い換え (R11) も本ゲートの担当外
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        self.assertNotIn("data-hb-glossary-term", html.read_text(encoding="utf-8"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_lead_line_text_alteration_is_not_checked(self):
        cfg = base_config()
        html = build_html(cfg).replace(LEAD_LINE_TEXT, "機能名から始まる書き出し。")
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_judgment_axis_text_alteration_is_not_checked(self):
        cfg = base_config()
        html = build_html(cfg).replace(JUDGMENT_AXIS_TEXT, "とくにありません。")
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)


class TestR18IsOutOfScope(NarrativeGateTestCase):
    """AC-C22-12: 日付は C18 の担当。"""

    def test_date_pill_removed_still_passes(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, include_date_pill=False))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_wrong_date_format_still_passes(self):
        cfg = base_config()
        html = build_html(cfg).replace(cfg["date"], "2026年8月17日")
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_date_mismatch_with_config_still_passes(self):
        cfg = base_config()
        html = build_html(cfg).replace(cfg["date"], "1999/01/01")
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)


class TestSelfContainedIsOutOfScope(NarrativeGateTestCase):
    """C16 の面 (外部参照・空画像) は本ゲートで判定しない。"""

    def test_external_stylesheet_link_is_not_a_narrative_violation(self):
        cfg = base_config()
        html = build_html(cfg).replace(
            "</head>", '<link rel="stylesheet" href="https://example.com/a.css"></head>', 1
        )
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_empty_svg_diagram_later_in_document_is_not_checked(self):
        cfg = base_config()
        html = build_html(cfg).replace(
            '    <div data-hb-part="B05"><p>本文の具体部品です。</p></div>\n',
            '    <figure data-hb-part="DIAGRAM"><svg data-hb-kind="figure"></svg></figure>\n',
        )
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)


class TestDeterminism(NarrativeGateTestCase):
    """AC-C22-14: 同一入力で 2 回実行しバイト一致。"""

    def test_stdout_byte_identical_on_pass(self):
        html, cfg = self.write_pair()
        a = self.run_gate(html, cfg)
        b = self.run_gate(html, cfg)
        self.assertEqual(a.stdout, b.stdout)

    def test_stdout_byte_identical_on_fail(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields={"goal"}, omit_section_goal={"s3"}))
        cfgp = self.write_config(cfg)
        a = self.run_gate(html, cfgp)
        b = self.run_gate(html, cfgp)
        self.assertEqual(a.stdout, b.stdout)

    def test_stderr_byte_identical_on_fail(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields={"goal"}, omit_section_goal={"s3"}))
        cfgp = self.write_config(cfg)
        a = self.run_gate(html, cfgp)
        b = self.run_gate(html, cfgp)
        self.assertEqual(a.stderr, b.stderr)

    def test_json_report_byte_identical(self):
        html, cfg = self.write_pair()
        r1 = self.tmpdir / "r1.json"
        r2 = self.tmpdir / "r2.json"
        self.run_gate(html, cfg, json_report=r1)
        self.run_gate(html, cfg, json_report=r2)
        self.assertEqual(r1.read_bytes(), r2.read_bytes(), "json-report がバイト一致すること")

    def test_exit_code_stable(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, first_item="diagram"))
        cfgp = self.write_config(cfg)
        self.assertEqual(
            self.run_gate(html, cfgp).returncode, self.run_gate(html, cfgp).returncode
        )

    def test_violation_rows_are_in_stable_order(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, omit_section_goal={"s2", "s5"}, nav_omit_attrs={"s3", "s6"})
        )
        cfgp = self.write_config(cfg)
        a = [tuple(r) for r in self.stderr_rows(self.run_gate(html, cfgp))]
        b = [tuple(r) for r in self.stderr_rows(self.run_gate(html, cfgp))]
        self.assertEqual(a, b)


class TestMultiViolationAccounting(NarrativeGateTestCase):
    """複数面が同時に壊れたとき、面ごとに独立して計上される。"""

    def test_all_detections_reported_even_when_first_fails(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields={"purpose", "background", "goal"}))
        res = self.run_gate(html, self.write_config(cfg))
        rows = self.summary(res)
        # 件数を直書きすると detection が増えた時 (R22 の NAR-09/NAR-10) に
        # 「後続を落としていない」ではなく「昔の本数と違う」を測る検査に化ける。
        self.assertEqual(
            len(DETECTION_ORDER), len(rows),
            "早期 return で後続 detection を落とさない\nstdout=%s" % res.stdout,
        )

    def test_independent_faces_counted_separately(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, omit_hero_fields={"goal"}, omit_section_goal={"s3"}, nav_omit_attrs={"s4"})
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assertEqual(1, self.violations(res, "NAR-01"))
        self.assertEqual(1, self.violations(res, "NAR-03"))
        self.assertEqual(1, self.violations(res, "NAR-05"))

    def test_stderr_row_count_matches_summary_total(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, omit_hero_fields={"goal"}, omit_section_goal={"s3"}, nav_omit_attrs={"s4"})
        )
        res = self.run_gate(html, self.write_config(cfg))
        total = sum(
            int(row["violations"]) for row in self.summary(res).values() if "violations" in row
        )
        self.assertEqual(total, len(self.stderr_rows(res)), "違反 1 件につき stderr 1 行")


if __name__ == "__main__":
    unittest.main()

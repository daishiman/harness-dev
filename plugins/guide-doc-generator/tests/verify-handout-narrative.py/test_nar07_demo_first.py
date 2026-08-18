# -*- coding: utf-8 -*-
"""NAR-07 / CR-DEMO1 (R21 C56)。C22 が単一正本の禁止規則。

demo_first のとき、読み手が最初に出会う提示物は実際の画面でなければならない。
概念図・フロー・特徴カード・120 文字超の説明段落を実画面より前に置くことを禁じる。

AC-C22-R21-56a / 56b / 56c。
"""

from __future__ import annotations

import unittest

from _support import NarrativeGateTestCase, base_config, build_html


def demo_first_config():
    cfg = base_config()
    cfg["presentation_order"] = "demo_first"
    return cfg


def explain_first_config():
    cfg = base_config()
    cfg["presentation_order"] = "explain_first"
    cfg["provenance"]["presentation_order_source"] = "explicit"
    return cfg


class TestNar07Prohibition(NarrativeGateTestCase):
    """禁止形であること: 実画面より前に抽象物を置いた時点で FAIL。"""

    def test_ac56a_diagram_first_is_violation(self):
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="diagram"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-07", count=1)

    def test_ac56a_message_states_diagram_before_real_screen(self):
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="diagram"))
        res = self.run_gate(html, self.write_config(cfg))
        blob = "\n".join("\t".join(r) for r in self.stderr_rows(res, "NAR-07"))
        self.assertIn("DIAGRAM", blob, "違反した部品が特定できること\nstderr=%r" % res.stderr)

    def test_ac56a_message_carries_line_number(self):
        cfg = demo_first_config()
        html_text = build_html(cfg, first_item="diagram")
        html = self.write_html(html_text)
        res = self.run_gate(html, self.write_config(cfg))
        rows = self.stderr_rows(res, "NAR-07")
        self.assertTrue(rows, "NAR-07 の違反行が無い")
        expected_line = next(
            i + 1 for i, ln in enumerate(html_text.splitlines()) if 'data-hb-part="DIAGRAM"' in ln
        )
        self.assertTrue(
            any(str(expected_line) in field for r in rows for field in r),
            "当該 DIAGRAM の行番号 (%d) が出ること\nstderr=%r" % (expected_line, res.stderr),
        )

    def test_flow_b14_first_is_violation(self):
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="flow"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-07", count=1)

    def test_feature_cards_b07_first_is_violation(self):
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="feature_cards"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-07", count=1)

    def test_long_explanatory_paragraph_first_is_violation(self):
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="long_paragraph"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-07", count=1)

    def test_figure_role_image_first_is_violation(self):
        # AC-C22-R21-56c 前半: screenshot 以外の画像は実画面と認めない
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="figure_img"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-07", count=1)

    def test_b17_without_live_demo_is_violation(self):
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="b17_no_live"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-07", count=1)

    def test_diagram_then_screenshot_is_violation(self):
        # 「実画面もどこかにある」では満たされない (推奨形にしない)
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="diagram_then_screenshot"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-07", count=1)


class TestNar07Allowed(NarrativeGateTestCase):
    def test_screenshot_first_passes(self):
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="screenshot"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)
        self.assertEqual("PASS", self.summary(res)["NAR-07"]["status"])

    def test_ac56b_screenshot_inserted_before_diagram_passes(self):
        # 概念図の存在自体は禁じていない
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="screenshot_then_diagram"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_b17_live_demo_first_passes(self):
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="b17_live"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_lead_line_before_screenshot_is_not_a_presentation_item(self):
        # lead_line (1 行の抽象) は R11 が要求する型なので提示物から除外
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="screenshot", include_lead_line=True))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_short_paragraph_before_screenshot_is_allowed(self):
        # 120 文字以下の段落は提示物に数えない
        cfg = demo_first_config()
        html = build_html(cfg, first_item="screenshot").replace(
            '    <div data-hb-part="IMG"',
            "    <p>短い前置きです。</p>\n    <div data-hb-part=\"IMG\"",
            1,
        )
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_hero_content_is_not_the_first_presentation_item(self):
        # 判定対象は hero より後・最初の role=main セクションから
        cfg = demo_first_config()
        html = build_html(cfg, first_item="screenshot").replace(
            "</div>\n  <section", '    <figure data-hb-part="DIAGRAM"></figure>\n</div>\n  <section', 1
        )
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assertEqual("PASS", self.summary(res)["NAR-07"]["status"])

    def test_diagram_in_second_section_is_allowed(self):
        cfg = demo_first_config()
        html = build_html(cfg, first_item="screenshot").replace(
            '    <div data-hb-part="B05"><p>本文の具体部品です。</p></div>\n',
            '    <figure data-hb-part="DIAGRAM"></figure>\n',
            1,
        )
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)


class TestNar07Skip(NarrativeGateTestCase):
    """AC-C22-R21-56c 後半: explain_first では PASS ではなく SKIP。"""

    def test_explain_first_exits_zero(self):
        cfg = explain_first_config()
        html = self.write_html(build_html(cfg, first_item="figure_img"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_explain_first_emits_skip_line(self):
        cfg = explain_first_config()
        html = self.write_html(build_html(cfg, first_item="figure_img"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertIn("NAR-07 SKIP order=explain_first", res.stdout)

    def test_explain_first_status_is_not_pass(self):
        cfg = explain_first_config()
        html = self.write_html(build_html(cfg, first_item="diagram"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertEqual(
            "SKIP", self.summary(res)["NAR-07"]["status"], "未評価が PASS に化けないこと"
        )

    def test_explain_first_diagram_first_is_allowed(self):
        cfg = explain_first_config()
        html = self.write_html(build_html(cfg, first_item="diagram"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_skip_line_has_no_violation_counter(self):
        cfg = explain_first_config()
        html = self.write_html(build_html(cfg, first_item="diagram"))
        res = self.run_gate(html, self.write_config(cfg))
        line = next(ln for ln in res.stdout.splitlines() if ln.startswith("NAR-07 "))
        self.assertNotIn("violations=", line, "SKIP 行に violations= を出さない")


class TestNar07SourceOfTruth(NarrativeGateTestCase):
    """判定に使う presentation_order の出所は config (HTML 属性ではない)。"""

    def test_config_demo_first_wins_over_html_attribute(self):
        cfg = demo_first_config()
        html = self.write_html(
            build_html(cfg, first_item="diagram", html_presentation_order="explain_first")
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-07", count=1)

    def test_config_explain_first_wins_over_html_attribute(self):
        cfg = explain_first_config()
        html = self.write_html(
            build_html(cfg, first_item="diagram", html_presentation_order="demo_first")
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assertEqual("SKIP", self.summary(res)["NAR-07"]["status"])

    def test_presentation_order_missing_from_config_is_exit2(self):
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="screenshot"))
        cfg.pop("presentation_order")
        res = self.run_gate(html, self.write_config(cfg))
        self.assertIn(res.returncode, (1, 2), "必須フィールド欠落を PASS にしない")
        self.assertNotEqual(0, res.returncode)

    def test_appendix_only_before_main_does_not_shift_target(self):
        # 判定は role=main の最初のセクションから始める
        cfg = demo_first_config()
        html = self.write_html(
            build_html(
                cfg,
                first_item="screenshot",
                section_order=["s7", "s1", "s2", "s3", "s4", "s5", "s6"],
            )
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assertEqual(
            "FAIL", self.summary(res)["NAR-08"]["status"], "appendix 先頭は NAR-08 の違反"
        )
        self.assertEqual(
            "PASS", self.summary(res)["NAR-07"]["status"], "NAR-07 は main の先頭を見る"
        )


if __name__ == "__main__":
    unittest.main()

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


class TestNar07ScopeIsOneItemDocumentWide(NarrativeGateTestCase):
    """NAR-07 が実際に見ている射程を固定する (P05-x-71 の測定面)。

    実装 (verify-handout-narrative.py の _first_presentation_item) は
    最初の role=main セクションの seq 以降を **文書全体にわたって** 走査し、
    最初に見つかった部品ノードか単一行上限超えの段落 1 つだけを判定する。
    セクション境界で打ち切らないため『最初の本編セクションの中だけを見る』
    のではなく『最初の 1 つを見たら以降は一切見ない』が正しい射程である。

    ここを固定しておかないと、射程を広げたときに何が変わるのかが
    report 上で PASS と見分けられない (未評価と合格の区別)。
    実装の是非は P05-x-71 の裁定に委ね、本クラスは事実のみを述べる。
    """

    def _strip_first_screenshot(self, html):
        import re

        stripped = re.sub(
            r'\n *<div data-hb-part="IMG".*?</div>', "", html, count=1, flags=re.S
        )
        self.assertNotEqual(html, stripped, "fixture から IMG 部品を落とせていない")
        return stripped

    def test_scope_crosses_section_boundary_when_first_section_has_no_item(self):
        # s1 から提示物を落とすと、判定対象は s1 の中で止まらず後続セクションへ移る。
        cfg = demo_first_config()
        html = self._strip_first_screenshot(build_html(cfg, first_item="screenshot"))
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-07", count=1)

    def test_only_one_item_is_ever_checked(self):
        # 対照 (合格) と違反の双方で checked=1。射程は常に 1 件で、
        # 後続セクションの提示順は評価対象に入らない。
        cfg = demo_first_config()
        good = build_html(cfg, first_item="screenshot")
        bad = self._strip_first_screenshot(good)
        for label, html in (("pass", good), ("fail", bad)):
            res = self.run_gate(self.write_html(html), self.write_config(cfg))
            self.assertEqual(
                1,
                int(self.summary(res)["NAR-07"]["checked"]),
                "%s 側で checked が 1 でない (射程が変わったなら P05-x-71 の裁定が要る)" % label,
            )


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
        # exit 2 は『検査が成立しなかった』の意 (script-brief-C22.json の exit_codes)。
        # 1 (品質 FAIL) を許すと、入力契約違反と品質違反が report 上で区別できない。
        self.assertEqual(2, res.returncode, "必須フィールド欠落は入力契約違反であって品質 FAIL ではない")

    def test_presentation_order_missing_emits_no_nar07_line(self):
        # 検査が成立していない以上、NAR-07 の判定結果を名乗ってはならない。
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="screenshot"))
        cfg.pop("presentation_order")
        res = self.run_gate(html, self.write_config(cfg))
        self.assertFalse(
            [ln for ln in res.stdout.splitlines() if ln.startswith("NAR-07 ")],
            "入力契約違反のときに NAR-07 の行を出さない",
        )


class TestNar07CannotBeDisabledByNulling(NarrativeGateTestCase):
    """presentation_order を null にするだけで C56 の検査を無効化できないこと。

    キー削除は必須フィールド検査 (verify-handout-narrative.py の
    REQUIRED_CONFIG_KEYS) が捕らえるが、その検査は `key not in config` であり
    null は素通りする。素通りした null は NAR-07 の判定で demo_first と
    一致せず SKIP へ落ちるため、値を null にするだけで違反のある HTML を
    exit 0 にできる。C22 は正規化済み構成データしか受け取らない契約なので
    (provenance を持つ = C12 の normalize を通っている)、null は
    『explain_first だった』ではなく『入力が正規化済みでない』を意味する。

    正本は script-brief-C22.json の exit_codes と NAR-07 の
    not_evaluated_when。C12 側の必須性の実行点は A5c。
    """

    def _null_order_pair(self):
        # HTML は demo_first のまま生成する。値を後から落とすことで
        # 『正規化後に値だけ消した構成データ』を再現する。
        cfg = demo_first_config()
        html = self.write_html(build_html(cfg, first_item="diagram"))
        cfg["presentation_order"] = None
        return html, self.write_config(cfg)

    def test_null_presentation_order_is_not_reported_as_skip(self):
        html, config = self._null_order_pair()
        res = self.run_gate(html, config)
        skip = [
            ln
            for ln in res.stdout.splitlines()
            if ln.startswith("NAR-07 ") and "SKIP" in ln
        ]
        self.assertFalse(
            skip,
            "null を SKIP へ倒すと、値を消すだけで C56 の検査を無効化できる: %r" % skip,
        )

    def test_null_presentation_order_does_not_exit_zero(self):
        # この HTML は demo_first なら NAR-07 違反 (実画面より前に DIAGRAM)。
        # null にした結果 exit 0 になるなら、違反が緑へ化けている。
        html, config = self._null_order_pair()
        res = self.run_gate(html, config)
        self.assertNotEqual(
            0, res.returncode, "違反のある HTML が presentation_order=null で緑になっている"
        )

    def test_null_presentation_order_is_exit2(self):
        html, config = self._null_order_pair()
        res = self.run_gate(html, config)
        self.assertEqual(
            2,
            res.returncode,
            "正規化済み構成データの null は入力契約違反 (キー削除と同じ扱い) であるべき",
        )

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

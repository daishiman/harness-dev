"""生成 HTML の骨格・CSS・JS 機構の契約 (algorithm 9〜22 / AC-C11-9,10,14)。"""

import re
import tempfile
import unittest

import _harness as H


def rich_config():
    return H.base_config(
        sections=[
            H.base_section(1, blocks=[
                H.BLOCK_FIXTURES["steps"],
                H.BLOCK_FIXTURES["image"],
                H.BLOCK_FIXTURES["checklist"],
                H.BLOCK_FIXTURES["prompt"],
                H.BLOCK_FIXTURES["download"],
                H.BLOCK_FIXTURES["tabs"],
            ]),
            H.base_section(2, id="s2", blocks=[H.BLOCK_FIXTURES["accordion"]]),
        ]
    )


class StructureTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        cls.config = rich_config()
        cls.result, cls.html, cls.out_path = H.render_html(cls._td.name, cls.config)
        if cls.result.returncode != 0:
            raise AssertionError("正常系 fixture の生成に失敗: %s" % cls.result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls._td.cleanup()


class HeroTest(StructureTestBase):
    def test_hero_renders_purpose_background_goal_as_three_elements(self):
        """algorithm 16 / checklist C37: 目的・背景・ゴールをそれぞれ独立の要素として出す。"""
        cfg = self.config
        for field in ("purpose", "background", "goal"):
            with self.subTest(field=field):
                els = H.field_elements(self.html, field)
                self.assertEqual(1, len(els), "%s は独立の要素 1 個" % field)
                self.assertEqual(cfg[field], els[0].text.strip())

    def test_hero_has_title_lead_and_goal_chips(self):
        hero = H.part_elements(self.html, "B02")
        self.assertEqual(1, len(hero))
        self.assertTrue(any(el.tag == "h1" for el in H.parse(self.html)))
        chips = [el for el in H.parse(self.html) if "goal-chip" in el.classes()]
        self.assertGreaterEqual(len(chips), len(self.config["goal_chips"]))


class SectionOrderTest(StructureTestBase):
    def test_section_children_follow_the_fixed_order(self):
        """algorithm 17: (a) 見出し → (b) ゴールチップ → (c) lead-line → (d) 部品 → (e) 判断軸 → (f) メモ。

        この順序は参照解析 §5 の『抽象 → 具体 → 判断軸』の構造化であり、
        構成データの並びでは変えられない。
        """
        section_html = self._first_section_html()
        positions = {
            "label": section_html.index('class="section-label'),
            "goal": section_html.index('data-hb-field="section_goal"'),
            "lead": section_html.index('data-hb-field="lead_line"'),
            "part": section_html.index('data-hb-part="B03"'),
            "axis": section_html.index('data-hb-field="judgment_axis"'),
            "memo": section_html.index('data-hb-part="memo"'),
        }
        ordered = ["label", "goal", "lead", "part", "axis", "memo"]
        actual = sorted(ordered, key=lambda k: positions[k])
        self.assertEqual(ordered, actual, "セクション内の固定順序が崩れている: %r" % positions)

    def test_section_order_is_not_overridable_by_block_order(self):
        """判断軸を先頭に置いた構成データでも、描画順は固定順序のまま。"""
        cfg = rich_config()
        cfg["sections"][0]["blocks"] = list(reversed(cfg["sections"][0]["blocks"]))
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, cfg)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertLess(
            html_text.index('data-hb-field="lead_line"'),
            html_text.index('data-hb-field="judgment_axis"'),
        )

    def _first_section_html(self):
        start = self.html.index("<section")
        end = self.html.index("</section>", start)
        return self.html[start:end]


class StickyNavAndOffsetTest(StructureTestBase):
    def test_header_is_sticky(self):
        """algorithm 14: header.pop-header は position:sticky; top:0。"""
        self.assertRegex(self.html, r"position\s*:\s*sticky")
        self.assertIn("pop-header", self.html)

    def test_offset_correction_is_doubled(self):
        """AC-C11-9 / checklist C4: CSS の scroll-margin-top と JS の実測補正の両方。"""
        self.assertRegex(self.html, r"scroll-margin-top\s*:\s*var\(--nav-h")
        self.assertIn("getBoundingClientRect", self.html)
        self.assertIn("scrollTo", self.html)


class StaggerTest(StructureTestBase):
    def test_stagger_is_css_only(self):
        """AC-C11-10 / checklist C14: @keyframes rise-in と inline --stagger。JS は関与しない。"""
        self.assertIn("@keyframes rise-in", self.html)
        self.assertRegex(self.html, r"animation-delay\s*:\s*var\(--stagger")
        inline = re.findall(r'style="--stagger:\s*(\d+)ms"', self.html)
        self.assertTrue(inline, "各セクション/カードへ inline の --stagger を付ける")
        for value in inline:
            self.assertLessEqual(int(value), 720, "min(index*120, 720) を超えている")
            self.assertEqual(0, int(value) % 120)

    def test_no_javascript_drives_the_stagger(self):
        script_body = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", self.html, re.S))
        self.assertNotIn("stagger", script_body, "スタガーに JS を関与させない")

    def test_reduced_motion_is_respected(self):
        self.assertIn("prefers-reduced-motion", self.html)


class PrintRuleTest(StructureTestBase):
    def test_a4_page_rule(self):
        """algorithm 21 / checklist C21: @page { size: A4; margin: 14mm }。"""
        self.assertRegex(self.html, r"@page\s*\{[^}]*size\s*:\s*A4")
        self.assertRegex(self.html, r"@page\s*\{[^}]*margin\s*:\s*14mm")

    def test_print_media_rules(self):
        block = self._print_block()
        self.assertRegex(block, r"position\s*:\s*static")
        self.assertRegex(block, r"break-inside\s*:\s*avoid")
        self.assertRegex(block, r"display\s*:\s*none")

    def test_memo_body_survives_printing(self):
        """メモ本文は印刷に残す (会議後に手元へ残る価値があるため)。"""
        block = self._print_block()
        self.assertNotRegex(
            block, r"\.memo-body[^{]*\{[^}]*display\s*:\s*none",
            "メモ本文を印刷から落としてはならない",
        )

    def _print_block(self):
        matches = re.findall(r"@media\s+print\s*\{(.*?)\n\s*\}\s*\n", self.html, re.S)
        self.assertTrue(matches, "@media print が無い")
        return "\n".join(matches)


class AccessibilityTest(StructureTestBase):
    def test_toggle_controls_expose_aria_pressed(self):
        self.assertIn("aria-pressed", self.html)

    def test_tabs_expose_tablist_semantics(self):
        self.assertIn('role="tablist"', self.html)
        self.assertIn("aria-selected", self.html)
        panels = [el for el in H.parse(self.html) if el.get("role") == "tabpanel"]
        self.assertTrue(panels)
        self.assertTrue(any("hidden" in el.attrs for el in panels[1:]) or len(panels) == 1)

    def test_lightbox_is_a_modal_dialog(self):
        lightbox = H.part_elements(self.html, "lightbox")
        self.assertEqual(1, len(lightbox))
        self.assertEqual("dialog", lightbox[0].get("role"))
        self.assertEqual("true", lightbox[0].get("aria-modal"))

    def test_decorative_icons_are_hidden_from_assistive_tech(self):
        for el in H.parse(self.html):
            if el.tag == "svg" and el.get("data-hb-kind") == "decor":
                self.assertEqual("true", el.get("aria-hidden"))

    def test_meaningful_svg_has_role_img(self):
        for el in H.parse(self.html):
            if el.tag == "svg" and el.get("data-hb-kind") == "figure":
                self.assertEqual("img", el.get("role"))

    def test_table_headers_have_scope(self):
        for el in H.parse(self.html):
            if el.tag == "th":
                self.assertIn(el.get("scope"), ("col", "row"))

    def test_focus_visible_outline_is_unified(self):
        self.assertIn(":focus-visible", self.html)


class SelfContainedTest(StructureTestBase):
    def test_no_external_reference_in_generated_html(self):
        """R01: 外部参照ゼロ (data URI と fragment 参照のみ)。"""
        for attr in ("src", "href", "srcset"):
            for value in re.findall(r'%s="([^"]*)"' % attr, self.html):
                self.assertFalse(
                    value.startswith(("http://", "https://", "//")),
                    "外部参照 %s=%s" % (attr, value),
                )
        self.assertNotIn("@import", self.html)
        for value in re.findall(r"url\(([^)]*)\)", self.html):
            self.assertNotIn("http", value)

    def test_single_mechanism_script_in_strict_mode(self):
        """algorithm 19: 機構スクリプトは 1 つの <script> に 'use strict' で出す。"""
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", self.html, re.S)
        self.assertEqual(1, len(scripts), "<script> は 1 つだけ")
        self.assertRegex(scripts[0].lstrip(), r"^['\"]use strict['\"];")

    def test_no_framework_or_cdn_reference(self):
        for token in ("cdn.", "unpkg", "jsdelivr", "react", "jquery", "vue"):
            self.assertNotIn(token, self.html.lower())

    def test_icon_sprite_is_emitted_once_and_referenced_by_fragment(self):
        """algorithm 9: symbols_svg は body 直後へ 1 度だけ。参照は <use href="#hbic-..."> のみ。"""
        uses = re.findall(r'<use[^>]*href="([^"]+)"', self.html)
        self.assertTrue(uses, "アイコン参照が無い")
        for href in uses:
            self.assertTrue(href.startswith("#hbic-"), "アイコン参照は #hbic- のみ: %s" % href)
        symbol_ids = set(re.findall(r'<symbol[^>]*id="([^"]+)"', self.html))
        self.assertEqual(
            set(), symbol_ids - {h[1:] for h in uses}, "未使用 symbol は 0 件"
        )


class MemoMechanismTest(StructureTestBase):
    def test_global_memo_is_always_present(self):
        self.assertEqual(1, len(H.part_elements(self.html, "memo-global")))

    def test_per_section_memo_is_present(self):
        self.assertEqual(
            len(self.config["sections"]), len(H.part_elements(self.html, "memo"))
        )

    def test_localstorage_key_uses_slug_not_generation_time(self):
        """algorithm 20: キーは handout:{slug}:{kind}:{id}。生成ごとに変わる値を混ぜない。"""
        script = re.findall(r"<script[^>]*>(.*?)</script>", self.html, re.S)[0]
        self.assertIn("localStorage", script)
        self.assertIn("handout:", script)
        self.assertIn(self.config["slug"], self.html)

    def test_memo_can_be_exported_and_cleared(self):
        script = re.findall(r"<script[^>]*>(.*?)</script>", self.html, re.S)[0]
        self.assertIn("DOMContentLoaded", script)
        for token in ("clipboard", "download", "clear"):
            self.assertIn(token, script.lower(), "メモの %s 機構が無い" % token)


class TypographyAndTokenTest(StructureTestBase):
    def test_palt_and_tabular_nums(self):
        """algorithm 12: body に palt、.num に tabular-nums。"""
        self.assertRegex(self.html, r'font-feature-settings\s*:\s*"palt"')
        self.assertRegex(self.html, r"font-variant-numeric\s*:\s*tabular-nums")
        self.assertRegex(self.html, r"letter-spacing\s*:\s*-0\.015em")

    def test_design_tokens_are_declared_as_css_variables_in_root(self):
        """algorithm 11: トークンは :root へ展開し、以降は var() 参照のみ。"""
        root = re.search(r":root\s*\{(.*?)\}", self.html, re.S)
        self.assertIsNotNone(root, ":root ブロックが無い")
        for var in ("--pop-primary", "--pop-bg", "--ink", "--line", "--card-radius", "--font-num"):
            self.assertIn(var, root.group(1), "%s が :root に無い" % var)
        after_root = self.html[root.end():]
        hex_colors = re.findall(r"#[0-9a-fA-F]{6}\b", after_root)
        self.assertEqual([], hex_colors, ":root の外に色の実値が現れている: %r" % hex_colors)


if __name__ == "__main__":
    unittest.main()

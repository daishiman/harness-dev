"""生成 SVG 自体の契約 (AC-C14-3 / 4 / 5 と 手順 9・10・12)。

- AC-C14-3 / goal-spec C60 (SC-10): 取得を発生させ得る参照は data: 以外を一律違反
- AC-C14-4: 絵文字レンジの検出 0 件
- AC-C14-5: var() のフォールバック以外に 16 進カラーリテラルを置かない (checklist C14)
- 手順 10: role="img" / <title> / 装飾要素の aria-hidden
- 手順 12: html.escape(quote=True) による全文字列のエスケープ
"""

import re
import tempfile
import unittest

import _harness as H


class ExternalReferenceTest(unittest.TestCase):
    """AC-C14-3 / SC-10: 外部参照ゼロ。"""

    def test_no_external_reference_for_every_pattern(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                self.assertEqual(H.external_reference_hits(res.stdout), [])

    def test_no_http_or_https_literal(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                self.assertNotIn("http://", res.stdout)
                self.assertNotIn("https://", res.stdout)

    def test_no_protocol_relative_reference(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        self.assertNotIn("//", res.stdout, "protocol-relative と xmlns URI の双方を出さない")

    def test_no_xlink_href(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                self.assertNotIn("xlink:href", res.stdout)

    def test_no_image_element_with_non_data_href(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        for el in H.parse(res.stdout):
            if el.tag != "image":
                continue
            self.assertTrue(el.get("href", "").startswith("data:"), el)

    def test_no_at_import_or_external_font(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        self.assertNotIn("@import", res.stdout)
        self.assertNotIn("@font-face", res.stdout)

    def test_no_script_element(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                self.assertNotIn("<script", res.stdout)

    def test_user_supplied_url_in_a_label_does_not_become_a_reference(self):
        """テキストノードの URL は違反ではないが、参照属性へ昇格させてもならない。"""
        steps = [
            {"id": "st1", "label": "案内 https://example.com を見る"},
            {"id": "st2", "label": "確認する"},
        ]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 0, res)
        for el in H.parse(res.stdout):
            for name, value in el.attrs.items():
                if name.lower() in H.FETCHING_ATTRS:
                    self.assertFalse(value.strip().startswith("http"), (el.tag, name, value))


class EmojiTest(unittest.TestCase):
    """AC-C14-4: 絵文字レンジの検出 0 件。"""

    def test_no_emoji_for_every_pattern(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                self.assertEqual(H.emoji_hits(res.stdout), [])

    def test_arrow_heads_are_drawn_not_typed_as_emoji(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(H.emoji_hits(res.stdout), [], "矢印は図形で描く")


class ColorTokenTest(unittest.TestCase):
    """AC-C14-5 / 手順 9: 色は var(--token, #fallback) の形でだけ書く。"""

    def test_no_raw_hex_literal_outside_var_fallback(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                self.assertEqual(H.raw_hex_literals(res.stdout), [])

    def test_fill_and_stroke_values_are_var_references(self):
        allowed_plain = {"none", "currentColor", "transparent", "inherit"}
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                for el in H.parse(res.stdout):
                    for attr in ("fill", "stroke"):
                        if attr not in el.attrs:
                            continue
                        value = el.attrs[attr].strip()
                        if value in allowed_plain:
                            continue
                        self.assertTrue(
                            value.startswith("var(--"),
                            "<%s %s=%r> が CSS 変数参照でない" % (el.tag, attr, value),
                        )

    def test_every_var_reference_carries_a_fallback(self):
        """単体で開いたときにも色が出る (手順 9)。"""
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        for m in re.finditer(r"var\(\s*--[A-Za-z0-9_-]+[^)]*\)", res.stdout):
            self.assertIn(",", m.group(0), "フォールバックが無い: %r" % m.group(0))

    def test_no_named_css_colors_in_fill_or_stroke(self):
        named = {"red", "blue", "green", "black", "white", "gray", "grey", "orange"}
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        for el in H.parse(res.stdout):
            for attr in ("fill", "stroke"):
                self.assertNotIn(el.attrs.get(attr, "").strip().lower(), named, el)

    def test_no_style_attribute_carrying_colors(self):
        """色は属性で書き、style 属性へ焼き込まない (差し替え箇所を 1 つに保つ)。"""
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        for el in H.parse(res.stdout):
            style = el.attrs.get("style", "")
            self.assertEqual(H.raw_hex_literals(style), [], el)


class AccessibilityTest(unittest.TestCase):
    """手順 10: role="img" / <title> / <desc> / 装飾の aria-hidden。"""

    def test_root_svg_has_role_img(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                root = H.root_svg(res.stdout)
                self.assertIsNotNone(root, "ルート <svg> が無い")
                self.assertEqual(root.get("role"), "img")

    def test_title_element_carries_the_diagram_title(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                spec = H.spec_for(pattern)
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, spec)
                self.assertEqual(res.returncode, 0, res)
                titles = [el.text.strip() for el in H.parse(res.stdout) if el.tag == "title"]
                self.assertIn(spec["title"], titles, titles)

    def test_title_is_the_first_child_of_root_svg(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        root = H.root_svg(res.stdout)
        self.assertIsNotNone(root, "ルート <svg> が無い")
        self.assertTrue(root.children, "子要素が無い")
        self.assertEqual(root.children[0].tag, "title")

    def test_description_is_emitted_as_desc_when_present(self):
        spec = H.flow_spec(description="申請から承認までを 3 段階で示す")
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, spec)
        self.assertEqual(res.returncode, 0, res)
        descs = [el.text.strip() for el in H.parse(res.stdout) if el.tag == "desc"]
        self.assertIn(spec["description"], descs, descs)

    def test_no_desc_when_description_is_absent(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.without(H.flow_spec(), "description"))
        self.assertEqual(res.returncode, 0, res)
        self.assertNotIn("<desc", res.stdout)

    def test_decorative_arrow_markers_are_aria_hidden(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        hidden = [el for el in H.parse(res.stdout) if el.attrs.get("aria-hidden") == "true"]
        self.assertGreater(len(hidden), 0, "装飾要素へ aria-hidden を付ける (手順 10)")

    def test_text_elements_are_not_aria_hidden(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        for el in H.parse(res.stdout):
            if el.tag == "text":
                self.assertNotEqual(el.attrs.get("aria-hidden"), "true", el)


class EscapingTest(unittest.TestCase):
    """手順 12: html.escape(quote=True) で全文字列をエスケープする。"""

    HOSTILE = '"><script>alert(1)</script> & <b>x</b>'

    def test_hostile_title_is_escaped(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(title=self.HOSTILE))
        self.assertEqual(res.returncode, 0, res)
        self.assertNotIn("<script>", res.stdout)
        self.assertIn("&lt;script&gt;", res.stdout)

    def test_hostile_label_is_escaped(self):
        steps = [{"id": "st1", "label": self.HOSTILE}, {"id": "st2", "label": "確認"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 0, res)
        self.assertNotIn("<script>", res.stdout)

    def test_ampersand_is_escaped_once(self):
        steps = [{"id": "st1", "label": "A & B"}, {"id": "st2", "label": "確認"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 0, res)
        self.assertIn("&amp;", res.stdout)
        self.assertNotIn("&amp;amp;", res.stdout, "二重エスケープしない")

    def test_double_quote_in_a_label_is_escaped(self):
        steps = [{"id": "st1", "label": 'いわゆる "本番" 環境'}, {"id": "st2", "label": "確認"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 0, res)
        self.assertIn("&quot;", res.stdout)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

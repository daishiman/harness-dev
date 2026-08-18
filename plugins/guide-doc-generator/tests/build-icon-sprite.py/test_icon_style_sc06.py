"""AC-C15-2 / C16 SC-06: アイコン様式の統一。

C11 は C15 が返した symbols_svg を **無加工で** 埋め込む契約
(script-brief-C11.json algorithm 9) なので、SC-06 が生成 HTML に課す条件は
そのまま C15 の出力へ課される。SC-06 のスコープは data-hb-kind="icon" であり、
mascot / decor は対象外。ただし「data-hb-kind を持たない svg/symbol」は
分類不能として違反に計上されるため、sprite の外枠 <svg> にも属性が要る。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H


class UnifiedStyleTest(unittest.TestCase):
    def _run(self, tmp, icons=None, names=("check", "cross", "clock"), strict=False):
        iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=list(names), icons=icons))
        cfg = H.write_config(
            Path(tmp),
            H.make_config(sections=[H.section("s{}".format(i), section_icon=n)
                                    for i, n in enumerate(names)]),
        )
        return H.run_sprite(self, cfg, iset, strict_style=strict)

    def test_all_symbols_carry_the_five_style_attributes(self):
        """AC-C15-2 / checklist C10。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = H.sprite_result(self, self._run(tmp))
            H.assert_sc06_style(self, result[H.OUT_SYMBOLS])

    def test_style_values_are_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = H.sprite_result(self, self._run(tmp))
            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            symbols = H.tags_named(collector, "symbol")
            self.assertTrue(symbols, "symbol が 1 件も無い")
            for _tag, attrs, _order in symbols:
                self.assertEqual(attrs.get("viewbox"), "0 0 24 24")
                self.assertEqual(attrs.get("fill"), "none")
                self.assertEqual(attrs.get("stroke"), "currentColor")
                self.assertEqual(attrs.get("stroke-linecap"), "round")
                self.assertEqual(attrs.get("stroke-linejoin"), "round")

    def test_style_is_not_taken_from_the_icon_set(self):
        """icon_set_source.schema: viewBox / fill / stroke は正本側に持たせない。

        正本が様式らしきフィールドを持っていても、出力は統一様式で上書きされる
        (様式のブレを構造的に起こせなくする)。
        """
        with tempfile.TemporaryDirectory() as tmp:
            icons = [
                {
                    "name": "check",
                    "paths": ["M4 12l5 5L20 6"],
                    "stroke_width": 2.2,
                    "viewBox": "0 0 20 20",
                    "fill": "currentColor",
                    "stroke": "#333",
                }
            ]
            result = H.sprite_result(self, self._run(tmp, icons=icons, names=("check",)))
            markup = result[H.OUT_SYMBOLS]
            self.assertNotIn("0 0 20 20", markup, "正本の様式フィールドが出力へ漏れている:\n" + markup)
            self.assertNotIn("#333", markup)
            H.assert_sc06_style(self, markup)

    def test_stroke_width_comes_from_the_icon_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            icons = [H.icon("check", stroke_width=2.5)]
            result = H.sprite_result(self, self._run(tmp, icons=icons, names=("check",)))
            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            widths = [a.get("stroke-width") for _t, a, _o in H.tags_named(collector, "symbol")]
            self.assertEqual([float(w) for w in widths], [2.5])


class KindAttributeTest(unittest.TestCase):
    """SC-06 の分類。data-hb-kind の語彙正本は C11 html_attribute_contract。"""

    def _result(self, tmp):
        iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=["check", "cross"]))
        cfg = H.write_config(
            Path(tmp),
            H.make_config(
                sections=[H.section("s1", section_icon="check"), H.section("s2", section_icon="cross")]
            ),
        )
        return H.sprite_result(self, H.run_sprite(self, cfg, iset))

    def test_every_symbol_is_classified_as_icon(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._result(tmp)
            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            symbols = H.tags_named(collector, "symbol")
            self.assertTrue(symbols, "symbol が 1 件も無い")
            for _tag, attrs, _order in symbols:
                self.assertEqual(
                    attrs.get(H.KIND_ATTR), "icon",
                    "SC-06 の様式検査対象になるよう {}=\"icon\" が要る: {}".format(H.KIND_ATTR, attrs),
                )

    def test_sprite_wrapper_svg_is_classified_too(self):
        """SC-06: data-hb-kind を持たない <svg> は分類不能として違反になる。

        外枠 <svg width="0" height="0"> はアイコンではないため、値は icon 以外の
        語彙 (mascot / decor / figure) でなければならない。icon にすると
        viewBox を持たない外枠自身が SC-06 の様式検査で落ちる。
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = self._result(tmp)
            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            wrappers = H.tags_named(collector, "svg")
            self.assertEqual(len(wrappers), 1, "外枠 <svg> は 1 個 (algorithm 9)")
            _tag, attrs, _order = wrappers[0]
            kind = attrs.get(H.KIND_ATTR)
            self.assertIsNotNone(kind, "外枠 <svg> に {} が無い (SC-06 分類不能)".format(H.KIND_ATTR))
            self.assertIn(kind, H.KIND_VALUES, "{} が語彙外: {!r}".format(H.KIND_ATTR, kind))
            self.assertNotEqual(
                kind, "icon",
                "外枠 <svg> は viewBox を持たないため icon 分類にすると SC-06 で落ちる",
            )

    def test_wrapper_shape_matches_algorithm_9(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._result(tmp)
            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            _tag, attrs, _order = H.tags_named(collector, "svg")[0]
            self.assertEqual(attrs.get("width"), "0")
            self.assertEqual(attrs.get("height"), "0")
            self.assertEqual(attrs.get("aria-hidden"), "true")
            self.assertIn("position:absolute", (attrs.get("style") or "").replace(" ", ""))
            self.assertEqual(
                len(H.tags_named(collector, "defs")), 1,
                "algorithm 9: <defs> で symbol を包む",
            )

    def test_symbol_attribute_order_is_fixed(self):
        """algorithm 9: 属性順は id / viewBox / fill / stroke / stroke-width / linecap / linejoin。

        data-hb-kind の挿入位置はブリーフに記述が無いため (README gaps G-02)、
        上記 7 属性が **この相対順で現れること** を部分列として固定する。
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = self._result(tmp)
            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            for _tag, _attrs, order in H.tags_named(collector, "symbol"):
                lowered = [k.lower() for k in order]
                want = [a.lower() for a in H.SYMBOL_ATTR_ORDER]
                positions = []
                for attr in want:
                    self.assertIn(attr, lowered, "symbol に {} が無い: {}".format(attr, order))
                    positions.append(lowered.index(attr))
                self.assertEqual(
                    positions, sorted(positions),
                    "algorithm 9 の属性順が守られていない: {}".format(order),
                )


class StrictStyleTest(unittest.TestCase):
    """failure_modes: stroke_width が範囲外のときの二段構え。"""

    def _fixture(self, tmp, width):
        iset = H.write_icon_set(
            Path(tmp), H.make_icon_set(icons=[H.icon("check", stroke_width=width)])
        )
        cfg = H.write_config(
            Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
        )
        return cfg, iset

    def test_out_of_range_is_exit1_under_strict_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp, 1.0)
            proc = H.run_sprite(self, cfg, iset, strict_style=True)
            H.expect_exit(self, proc, 1, "--strict-style 時の様式違反")

    def test_out_of_range_is_warning_without_strict_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp, 1.0)
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 0, "非 strict では warning で継続する契約")
            self.assertNotEqual(
                H.err_text(proc).strip(), "",
                "非 strict でも stderr へ warning を出す契約\n" + H.describe(proc),
            )

    def test_boundary_values_are_inclusive(self):
        """許容域は 2.2-2.6。両端はどちらのモードでも通る。"""
        with tempfile.TemporaryDirectory() as tmp:
            for width in (H.STROKE_WIDTH_MIN, H.STROKE_WIDTH_MAX):
                sub = Path(tmp) / str(width)
                sub.mkdir()
                cfg, iset = self._fixture(sub, width)
                proc = H.run_sprite(self, cfg, iset, strict_style=True)
                H.expect_exit(self, proc, 0, "stroke_width={} は許容域内".format(width))

    def test_just_outside_boundary_fails_under_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            for width in (2.1, 2.7):
                sub = Path(tmp) / str(width)
                sub.mkdir()
                cfg, iset = self._fixture(sub, width)
                proc = H.run_sprite(self, cfg, iset, strict_style=True)
                H.expect_exit(self, proc, 1, "stroke_width={} は許容域外".format(width))

    def test_strict_style_names_the_symbol_and_the_violation(self):
        """stderr 契約: 様式違反の symbol 名と違反項目。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp, 9.9)
            proc = H.run_sprite(self, cfg, iset, strict_style=True)
            H.expect_exit(self, proc, 1)
            err = H.err_text(proc)
            self.assertIn("check", err, "stderr に symbol 名が無い\n" + H.describe(proc))
            self.assertIn("stroke_width", err.replace("stroke-width", "stroke_width"),
                          "stderr に違反項目が無い\n" + H.describe(proc))


if __name__ == "__main__":
    unittest.main()

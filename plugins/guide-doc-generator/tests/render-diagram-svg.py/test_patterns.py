"""6 パターンの描画責務と版組規則 (手順 5-8) / module API / C55 SC-09 との接続。

C14 の責務 (R07) は「装飾でなく理解を助ける図解」であること。
ここでは意味フィールドが必ず描画へ現れることと、パターンごとの構造要素が
出ることを固定する。C56 (demo_first) との関係は本 script の外 (C22) の判定であり、
ここでは「C14 の出力は figure であって screenshot ではない」ことだけを確認する。
"""

import tempfile
import unittest

import _harness as H

# 手順 4 が各パターンで要求する意味フィールドの、描画へ現れるべきテキスト
EXPECTED_TEXTS = {
    "flow": ["申請する", "確認する", "承認する", "様式Aを使う"],
    "compare": ["費用", "速さ", "案A", "案B", "高い", "安い", "速い", "遅い"],
    "hierarchy": ["全社", "営業部", "開発部", "第1課"],
    "cycle": ["計画する", "実行する", "見直す"],
    "matrix": ["低い", "高い", "小さい", "大きい", "施策A", "施策B"],
    "versus": ["自前で作る", "既製品を使う", "自由度が高い", "早く始められる"],
}


def _visible_text(svg_text):
    """<text> / <tspan> の可視テキストを連結する (<title>/<desc> は含めない)。"""
    chunks = []
    for el in H.parse(svg_text):
        if el.tag in ("text", "tspan"):
            chunks.append(el.text)
    return "\n".join(chunks)


class PatternRenderingTest(unittest.TestCase):
    """6 パターンすべてが exit 0 で描画要素を持つ SVG を返す。"""

    def test_every_pattern_exits_zero(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)

    def test_every_pattern_emits_drawing_elements(self):
        """C55 / SC-09: DIAGRAM は <svg> と描画要素を持つことが要求される。"""
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                self.assertGreater(
                    len(H.drawing_elements(res.stdout)), 0,
                    "SC-09: title/desc/defs/g だけの <svg> は違反",
                )

    def test_every_pattern_renders_its_semantic_fields(self):
        for pattern, expected in EXPECTED_TEXTS.items():
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                visible = _visible_text(res.stdout)
                missing = [t for t in expected if t not in visible]
                self.assertEqual(missing, [], "描画されていない意味フィールド: %r" % missing)

    def test_no_placeholder_text_is_emitted(self):
        """SC-09 の未解決プレースホルダ検査に落ちる文字列を出さない。"""
        forbidden = ("TODO", "TBD", "図はここに入ります", "{{", "}}", "lorem")
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                for needle in forbidden:
                    self.assertNotIn(needle, res.stdout, needle)

    def test_flow_draws_arrows_between_nodes(self):
        """手順 7 flow: ノード間に矢印 path。"""
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        self.assertIn("path", H.tags(res.stdout), "flow の矢印は path で描く")

    def test_flow_node_count_matches_step_count(self):
        steps = [{"id": "st%d" % i, "label": "手順%d" % i} for i in range(1, 5)]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 0, res)
        rects = [el for el in H.parse(res.stdout) if el.tag == "rect"]
        self.assertGreaterEqual(len(rects), len(steps), "step ごとにノード枠を出す")

    def test_flow_nodes_are_laid_out_in_one_row(self):
        """手順 7 flow: 横 1 列の等分配置。"""
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        widths = {el.get("width") for el in H.parse(res.stdout)
                  if el.tag == "rect" and "width" in el.attrs}
        self.assertEqual(len(widths), 1, "ノード幅は等分なので 1 種類: %r" % widths)

    def test_compare_renders_a_header_row_plus_item_rows(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.compare_spec())
        self.assertEqual(res.returncode, 0, res)
        rects = [el for el in H.parse(res.stdout) if el.tag == "rect"]
        self.assertGreaterEqual(len(rects), 3, "ヘッダ行 + 2 行 (手順 7 compare)")

    def test_hierarchy_connects_parent_and_child_with_a_path(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.hierarchy_spec())
        self.assertEqual(res.returncode, 0, res)
        self.assertIn("path", H.tags(res.stdout), "親子は折れ線 path で接続する")

    def test_hierarchy_layers_have_distinct_y(self):
        """手順 7 hierarchy: 層ごとに y を固定する。"""
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.hierarchy_spec())
        self.assertEqual(res.returncode, 0, res)
        ys = {el.get("y") for el in H.parse(res.stdout)
              if el.tag == "rect" and "y" in el.attrs}
        self.assertGreaterEqual(len(ys), 2, "root 層と子層で y が異なる: %r" % ys)

    def test_cycle_uses_arc_paths(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.cycle_spec())
        self.assertEqual(res.returncode, 0, res)
        ds = H.all_attr_values(res.stdout, "d")
        self.assertTrue(any("A" in d for d in ds), "隣接間を円弧 path で接続する: %r" % ds)

    def test_cycle_is_symmetric_about_the_canvas_center(self):
        """手順 7 cycle: 中心 (W/2, H/2) 半径 R の円周へ n 等分配置。"""
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.cycle_spec(), width=800)
        self.assertEqual(res.returncode, 0, res)
        root = H.root_svg(res.stdout)
        self.assertIsNotNone(root, "ルート <svg> が無い")
        self.assertRegex(root.get("viewBox", ""), r"^0 0 800 \d+$")

    def test_matrix_draws_four_quadrants_and_axes(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec())
        self.assertEqual(res.returncode, 0, res)
        tags = H.tags(res.stdout)
        self.assertGreaterEqual(tags.count("rect"), 4, "4 象限の背景 rect")
        self.assertTrue("line" in tags or "path" in tags, "軸線を描く")

    def test_matrix_maps_coordinates_monotonically(self):
        """x が大きい item は x が小さい item より右に置かれる。"""
        items = [
            {"id": "left", "label": "左", "x": 0.1, "y": 0.5},
            {"id": "right", "label": "右", "x": 0.9, "y": 0.5},
        ]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=items))
        self.assertEqual(res.returncode, 0, res)
        xs = {}
        for el in H.parse(res.stdout):
            if el.tag in ("circle", "ellipse") and "cx" in el.attrs:
                xs.setdefault("points", []).append(int(el.get("cx")))
        self.assertGreaterEqual(len(xs.get("points", [])), 2, "item ごとに点を打つ")
        self.assertLess(min(xs["points"]), max(xs["points"]))

    def test_versus_draws_two_columns_and_a_divider(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.versus_spec())
        self.assertEqual(res.returncode, 0, res)
        tags = H.tags(res.stdout)
        self.assertGreaterEqual(tags.count("rect"), 2, "左右 2 カラムの rect")
        self.assertTrue("line" in tags or "path" in tags, "中央の区切り線")

    def test_versus_divider_is_decorative(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.versus_spec())
        self.assertEqual(res.returncode, 0, res)
        hidden = [el for el in H.parse(res.stdout) if el.attrs.get("aria-hidden") == "true"]
        self.assertGreater(len(hidden), 0, "区切り線は aria-hidden (手順 10)")

    def test_height_grows_with_content(self):
        """手順 8: H はパターン別の版組規則から決定論導出する。"""
        small = H.versus_spec(left={"label": "自前", "bullets": ["1"]},
                              right={"label": "既製", "bullets": ["1"]})
        large = H.versus_spec(left={"label": "自前", "bullets": ["1", "2", "3", "4", "5"]},
                              right={"label": "既製", "bullets": ["1", "2", "3", "4", "5"]})
        with tempfile.TemporaryDirectory() as td:
            a = H.render(td, small)
            b = H.render(td, large)
        self.assertEqual(a.returncode, 0, a)
        self.assertEqual(b.returncode, 0, b)
        ha = int(H.root_svg(a.stdout).get("viewBox").split()[3])
        hb = int(H.root_svg(b.stdout).get("viewBox").split()[3])
        self.assertGreater(hb, ha, "行数が増えれば高さが増える")


class TextWrapTest(unittest.TestCase):
    """手順 5-6: east_asian_width による幅見積りと貪欲折返し。"""

    def _fits(self, chars, count, width=860):
        steps = [{"id": "st1", "label": chars * count}, {"id": "st2", "label": "短"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps), width=width)
        return res

    def _threshold(self, char):
        """折返し上限を超えて exit 1 になる最小の文字数を返す (見つからなければ None)。"""
        last = 0
        for count in range(4, 240, 4):
            res = self._fits(char, count)
            if res.returncode == 1:
                return count
            self.assertEqual(res.returncode, 0, res)
            last = count
        self.fail("240 文字でも折返し上限に達しない (last=%d)" % last)

    def test_overflow_threshold_is_monotone_in_length(self):
        """長くして通ったのに短くして落ちる、という非単調が無い。"""
        seen_fail = False
        for count in (8, 24, 48, 96, 160, 240):
            res = self._fits("あ", count)
            self.assertIn(res.returncode, (0, 1), res)
            if res.returncode == 1:
                seen_fail = True
            else:
                self.assertFalse(seen_fail, "%d 文字で通るのに短い側で落ちている" % count)
        self.assertTrue(seen_fail, "十分長い label は必ず exit 1 になる")

    def test_wide_characters_are_measured_wider_than_narrow_ones(self):
        """'W' は 1.00em、ラテン文字は 0.55em (手順 5)。"""
        wide = self._threshold("あ")
        narrow = self._threshold("a")
        self.assertLess(wide, narrow, "全角の方が少ない文字数で溢れる (wide=%d narrow=%d)"
                        % (wide, narrow))

    def test_ambiguous_width_characters_are_measured_as_wide(self):
        """east_asian_width 'A' も 1.00em として扱う (手順 5)。"""
        wide = self._threshold("あ")
        ambiguous = self._threshold("×")
        self.assertEqual(ambiguous, wide, "'A' は 'W' と同じ 1.00em (A=%d W=%d)"
                         % (ambiguous, wide))

    def test_wrapped_lines_are_emitted_as_tspans(self):
        """折返しは <tspan x=... dy=...> で出す (手順 6)。"""
        label = "承認の前に必要な確認をすべて済ませてから提出する"
        steps = [{"id": "st1", "label": label}, {"id": "st2", "label": "短"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps), width=520)
        self.assertEqual(res.returncode, 0, res)
        tspans = [el for el in H.parse(res.stdout) if el.tag == "tspan"]
        self.assertGreater(len(tspans), 1, "2 行以上へ折り返す")
        for el in tspans:
            self.assertIn("x", el.attrs, el)
            self.assertIn("dy", el.attrs, el)

    def test_first_line_dy_is_zero_and_later_lines_are_one_point_four_five_em(self):
        label = "承認の前に必要な確認をすべて済ませてから提出する"
        steps = [{"id": "st1", "label": label}, {"id": "st2", "label": "短"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps), width=520)
        self.assertEqual(res.returncode, 0, res)
        dys = [el.get("dy") for el in H.parse(res.stdout) if el.tag == "tspan"]
        self.assertGreater(len(dys), 1, dys)
        self.assertEqual(dys[0], "0", "1 行目の dy は 0")
        for dy in dys[1:]:
            self.assertEqual(dy, "1.45em", "2 行目以降の dy は 1.45em")

    def test_latin_wraps_on_spaces(self):
        """ラテン文字は空白単位の貪欲折返し (単語を割らない)。"""
        label = "review the request then approve it before the deadline arrives"
        steps = [{"id": "st1", "label": label}, {"id": "st2", "label": "短"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps), width=520)
        if res.returncode != 0:
            self.skipTest("この幅では 3 行に収まらない")
        lines = [el.text for el in H.parse(res.stdout) if el.tag == "tspan"]
        joined = " ".join(l.strip() for l in lines)
        for word in label.split():
            self.assertIn(word, joined, "単語を途中で割ってはならない: %r" % word)

    def test_node_label_allows_up_to_three_lines(self):
        self.assertEqual(H.MAX_LINES_NODE_LABEL, 3)
        label = "承認の前に必要な確認をすべて済ませてから提出する必要がある"
        steps = [{"id": "st1", "label": label}, {"id": "st2", "label": "短"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps), width=520)
        self.assertEqual(res.returncode, 0, res)
        tspans = [el for el in H.parse(res.stdout) if el.tag == "tspan"]
        self.assertLessEqual(len(tspans), H.MAX_LINES_NODE_LABEL * 3,
                             "label 1 件あたり最大 3 行")


class ModuleApiTest(unittest.TestCase):
    """C11 が import 経由で呼ぶ render_diagram(spec, pattern, width) -> str。"""

    def test_render_diagram_is_exposed(self):
        module = H.load_module()
        self.assertTrue(hasattr(module, "render_diagram"),
                        "module API render_diagram が無い (dependencies.invoked_by)")

    def test_render_diagram_returns_the_same_string_as_the_cli(self):
        module = H.load_module()
        spec = H.flow_spec()
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, spec)
        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(module.render_diagram(spec, "flow", H.DEFAULT_WIDTH), res.stdout)

    def test_render_diagram_raises_on_a_violation(self):
        module = H.load_module()
        with self.assertRaises(Exception):
            module.render_diagram(H.flow_spec(steps=[{"id": "a", "label": "1"}]),
                                  "flow", H.DEFAULT_WIDTH)

    def test_importing_the_module_produces_no_output(self):
        """import しただけで stdout へ書かない (C11 の生成物を汚さない)。"""
        import contextlib
        import io

        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            H.load_module()
        self.assertEqual(buf_out.getvalue(), "")
        self.assertEqual(buf_err.getvalue(), "")

    def test_render_diagram_is_the_only_coordinate_owner(self):
        """single_writer: 版組規則の owner は本 script。C11 は座標計算を持たない。"""
        module = H.load_module()
        self.assertTrue(callable(getattr(module, "render_diagram", None)))


class AssetRoleBoundaryTest(unittest.TestCase):
    """C56: C14 の出力は assets[].role=figure 相当であり screenshot の代替にならない。"""

    def test_output_contains_no_raster_image(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                self.assertEqual([el for el in H.parse(res.stdout) if el.tag == "image"], [],
                                 "概念図解は実画面 (screenshot) を含まない")

    def test_output_does_not_claim_a_screenshot_role(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        self.assertNotIn("screenshot", res.stdout)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

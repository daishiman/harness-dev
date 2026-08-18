"""違反系入力で exit 1 になる系 (script-brief-C14.json 手順 3-6 / failure_modes / AC-C14-6)。

exit 1 は「入力データの規約違反」= 差し戻し先が構成データ側。
どの検査も stderr へ原因 (キーパス または node id) を出すことまでを契約とする。
"""

import tempfile
import unittest

import _harness as H


class PatternVocabularyTest(unittest.TestCase):
    """未知の pattern 名 / --pattern と diagram.pattern の不一致 (手順 1・3)。"""

    def test_unknown_pattern_word_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(pattern="timeline"), pattern="timeline")
        self.assertEqual(res.returncode, 1, res)

    def test_unknown_pattern_stderr_lists_the_six_accepted_words(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(pattern="timeline"), pattern="timeline")
        self.assertEqual(res.returncode, 1, res)
        missing = [p for p in H.PATTERNS if p not in res.stderr]
        self.assertEqual(missing, [], "stderr へ受理する 6 語を列挙する: %r" % res.stderr)

    def test_empty_pattern_is_exit1_or_exit2(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(), pattern="")
        self.assertIn(res.returncode, (1, 2), res)

    def test_pattern_is_case_sensitive(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(), pattern="FLOW")
        self.assertEqual(res.returncode, 1, "語彙は 6 語のリテラル: %r" % (res,))

    def test_pattern_mismatch_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(pattern="cycle"), pattern="flow")
        self.assertEqual(res.returncode, 1, res)

    def test_pattern_mismatch_stderr_shows_both_values(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(pattern="cycle"), pattern="flow")
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("flow", res.stderr, res.stderr)
        self.assertIn("cycle", res.stderr, res.stderr)

    def test_absent_diagram_pattern_field_is_accepted(self):
        """diagram.pattern は任意。無いときは --pattern が採用される (手順 3)。"""
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.without(H.flow_spec(), "pattern"), pattern="flow")
        self.assertEqual(res.returncode, 0, res)


class TitleRequiredTest(unittest.TestCase):
    """title (図解の主題 1 行) は全パターン必須 (手順 3)。"""

    def test_missing_title_is_exit1_for_every_pattern(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.without(H.spec_for(pattern), "title"))
                self.assertEqual(res.returncode, 1, res)
                self.assertIn("title", res.stderr, res.stderr)

    def test_empty_title_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(title=""))
        self.assertEqual(res.returncode, 1, res)


class FlowFieldTest(unittest.TestCase):
    """flow: steps[] 2-6、各 step に label 必須・note 任意 (手順 4)。"""

    def _steps(self, n):
        return [{"id": "st%d" % i, "label": "手順%d" % i} for i in range(1, n + 1)]

    def test_two_steps_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=self._steps(2)))
        self.assertEqual(res.returncode, 0, res)

    def test_six_steps_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=self._steps(6)))
        self.assertEqual(res.returncode, 0, res)

    def test_one_step_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=self._steps(1)))
        self.assertEqual(res.returncode, 1, res)

    def test_seven_steps_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=self._steps(7)))
        self.assertEqual(res.returncode, 1, res)

    def test_seven_steps_stderr_shows_actual_count_and_range(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=self._steps(7)))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("7", res.stderr, res.stderr)
        self.assertTrue(H.stderr_mentions(res, ["2", "6"]), res.stderr)

    def test_missing_steps_key_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.without(H.flow_spec(), "steps"))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("steps", res.stderr, res.stderr)

    def test_step_without_label_is_exit1_with_keypath(self):
        steps = self._steps(3)
        del steps[1]["label"]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("steps", res.stderr, res.stderr)
        self.assertTrue(H.stderr_mentions(res, ["label"]), res.stderr)

    def test_step_note_is_optional(self):
        steps = self._steps(3)
        steps[0]["note"] = "補足を添える"
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 0, res)


class CompareFieldTest(unittest.TestCase):
    """compare: axes[] 1-6 と items[] 2-4、cells は全マスが埋まっていること (手順 4)。"""

    def test_one_axis_and_two_items_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.compare_spec(axes=["費用"], items=["案A", "案B"],
                                              cells=[["高い"], ["安い"]]))
        self.assertEqual(res.returncode, 0, res)

    def test_seven_axes_is_exit1(self):
        axes = ["軸%d" % i for i in range(1, 8)]
        cells = [["値"] * 7, ["値"] * 7]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.compare_spec(axes=axes, cells=cells))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("axes", res.stderr, res.stderr)

    def test_zero_axes_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.compare_spec(axes=[], cells=[[], []]))
        self.assertEqual(res.returncode, 1, res)

    def test_one_item_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.compare_spec(items=["案A"], cells=[["高い", "速い"]]))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("items", res.stderr, res.stderr)

    def test_five_items_is_exit1(self):
        items = ["案%d" % i for i in range(1, 6)]
        cells = [["高い", "速い"] for _ in items]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.compare_spec(items=items, cells=cells))
        self.assertEqual(res.returncode, 1, res)

    def test_incomplete_cells_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.compare_spec(cells=[["高い", "速い"], ["安い"]]))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("cells", res.stderr, res.stderr)

    def test_missing_cells_key_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.without(H.compare_spec(), "cells"))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("cells", res.stderr, res.stderr)


class HierarchyFieldTest(unittest.TestCase):
    """hierarchy: root.label と children[] (深さ 2-3・各層 1-5) (手順 4)。"""

    def test_depth_three_is_accepted(self):
        spec = H.hierarchy_spec(children=[
            {"label": "営業部", "children": [{"label": "第1課"}]},
        ])
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, spec)
        self.assertEqual(res.returncode, 0, res)

    def test_missing_root_label_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.hierarchy_spec(root={}))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("root", res.stderr, res.stderr)

    def test_missing_root_key_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.without(H.hierarchy_spec(), "root"))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("root", res.stderr, res.stderr)

    def test_empty_children_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.hierarchy_spec(children=[]))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("children", res.stderr, res.stderr)

    def test_six_children_in_a_layer_is_exit1(self):
        children = [{"label": "部%d" % i} for i in range(1, 7)]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.hierarchy_spec(children=children))
        self.assertEqual(res.returncode, 1, res)

    def test_depth_four_is_exit1(self):
        spec = H.hierarchy_spec(children=[
            {"label": "第1層", "children": [
                {"label": "第2層", "children": [{"label": "第3層"}]},
            ]},
        ])
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, spec)
        self.assertEqual(res.returncode, 1, res)

    def test_child_without_label_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.hierarchy_spec(children=[{"children": []}]))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("label", res.stderr, res.stderr)


class CycleFieldTest(unittest.TestCase):
    """cycle: steps[] 3-6、各 step に label (手順 4)。"""

    def _steps(self, n):
        return [{"id": "cy%d" % i, "label": "段階%d" % i} for i in range(1, n + 1)]

    def test_three_steps_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.cycle_spec(steps=self._steps(3)))
        self.assertEqual(res.returncode, 0, res)

    def test_six_steps_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.cycle_spec(steps=self._steps(6)))
        self.assertEqual(res.returncode, 0, res)

    def test_two_steps_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.cycle_spec(steps=self._steps(2)))
        self.assertEqual(res.returncode, 1, "cycle の下限は flow (2) と異なり 3: %r" % (res,))

    def test_seven_steps_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.cycle_spec(steps=self._steps(7)))
        self.assertEqual(res.returncode, 1, res)

    def test_step_without_label_is_exit1(self):
        steps = self._steps(3)
        del steps[2]["label"]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.cycle_spec(steps=steps))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("label", res.stderr, res.stderr)


class MatrixFieldTest(unittest.TestCase):
    """matrix: x_axis/y_axis の low/high と items[] 1-8 (label と 0.0-1.0 の x,y)。"""

    def _items(self, n):
        return [
            {"id": "mx%d" % i, "label": "施策%d" % i, "x": 0.1 * i, "y": 0.1 * i}
            for i in range(1, n + 1)
        ]

    def test_one_item_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=self._items(1)))
        self.assertEqual(res.returncode, 0, res)

    def test_eight_items_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=self._items(8)))
        self.assertEqual(res.returncode, 0, res)

    def test_zero_items_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=[]))
        self.assertEqual(res.returncode, 1, res)

    def test_nine_items_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=self._items(9)))
        self.assertEqual(res.returncode, 1, res)

    def test_missing_x_axis_high_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(x_axis={"low": "低い"}))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("x_axis", res.stderr, res.stderr)
        self.assertIn("high", res.stderr, res.stderr)

    def test_missing_y_axis_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.without(H.matrix_spec(), "y_axis"))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("y_axis", res.stderr, res.stderr)

    def test_x_above_one_is_exit1_with_item_id_and_value(self):
        items = [{"id": "mx1", "label": "施策A", "x": 1.5, "y": 0.5}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=items))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("mx1", res.stderr, res.stderr)
        self.assertIn("1.5", res.stderr, res.stderr)

    def test_y_below_zero_is_exit1(self):
        items = [{"id": "mx1", "label": "施策A", "x": 0.5, "y": -0.2}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=items))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("mx1", res.stderr, res.stderr)

    def test_out_of_range_is_not_silently_clipped(self):
        items = [{"id": "mx1", "label": "施策A", "x": 2.0, "y": 0.5}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=items))
        self.assertEqual(res.returncode, 1, res)
        self.assertEqual(res.stdout, "", "クリップして描画してはならない")

    def test_boundary_values_zero_and_one_are_accepted(self):
        items = [
            {"id": "mx1", "label": "施策A", "x": 0.0, "y": 0.0},
            {"id": "mx2", "label": "施策B", "x": 1.0, "y": 1.0},
        ]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=items))
        self.assertEqual(res.returncode, 0, "0.0-1.0 は閉区間: %r" % (res,))

    def test_item_without_coordinates_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=[{"id": "mx1", "label": "施策A"}]))
        self.assertEqual(res.returncode, 1, res)

    def test_item_without_label_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=[{"id": "mx1", "x": 0.5, "y": 0.5}]))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("label", res.stderr, res.stderr)

    def test_non_numeric_coordinate_is_exit1(self):
        items = [{"id": "mx1", "label": "施策A", "x": "0.5", "y": 0.5}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.matrix_spec(items=items))
        self.assertEqual(res.returncode, 1, res)


class VersusFieldTest(unittest.TestCase):
    """versus: left/right の label と bullets[] (各 1-5) (手順 4)。"""

    def test_five_bullets_is_accepted(self):
        spec = H.versus_spec(left={"label": "自前", "bullets": ["b%d" % i for i in range(5)]})
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, spec)
        self.assertEqual(res.returncode, 0, res)

    def test_six_bullets_is_exit1(self):
        spec = H.versus_spec(left={"label": "自前", "bullets": ["b%d" % i for i in range(6)]})
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, spec)
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("bullets", res.stderr, res.stderr)

    def test_zero_bullets_is_exit1(self):
        spec = H.versus_spec(right={"label": "既製品", "bullets": []})
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, spec)
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("bullets", res.stderr, res.stderr)

    def test_missing_right_side_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.without(H.versus_spec(), "right"))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("right", res.stderr, res.stderr)

    def test_missing_side_label_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.versus_spec(left={"bullets": ["自由度が高い"]}))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("left", res.stderr, res.stderr)


class TextOverflowTest(unittest.TestCase):
    """折返し行数が上限を超えたら exit 1 (手順 6 / failure_modes)。自動短縮しない。"""

    LONG = "配布資料の読み手が迷わないように書き下した非常に長い説明文をここへ入れる" * 6

    def test_overflowing_node_label_is_exit1(self):
        steps = [{"id": "st1", "label": self.LONG}, {"id": "st2", "label": "短い"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 1, res)

    def test_overflow_stderr_reports_node_id(self):
        steps = [{"id": "st1", "label": self.LONG}, {"id": "st2", "label": "短い"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 1, res)
        self.assertIn("st1", res.stderr, "stderr へ該当 node id を出す: %r" % res.stderr)

    def test_overflow_stderr_reports_measured_and_allowed_width(self):
        steps = [{"id": "st1", "label": self.LONG}, {"id": "st2", "label": "短い"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.returncode, 1, res)
        numbers = [tok for tok in res.stderr.replace("\n", " ").split() if any(c.isdigit() for c in tok)]
        self.assertGreaterEqual(len(numbers), 2, "見積り幅と許容幅を出す: %r" % res.stderr)

    def test_overflow_is_not_truncated_with_ellipsis(self):
        steps = [{"id": "st1", "label": self.LONG}, {"id": "st2", "label": "短い"}]
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(steps=steps))
        self.assertEqual(res.stdout, "", "切り詰めた SVG を出してはならない")
        self.assertNotIn("…", res.stdout)

    def test_overflowing_bullets_is_exit1(self):
        spec = H.versus_spec(left={"label": "自前で作る", "bullets": [self.LONG]})
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, spec)
        self.assertEqual(res.returncode, 1, res)

    def test_overflowing_title_is_exit1(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(title=self.LONG))
        self.assertEqual(res.returncode, 1, res)

    def test_narrow_width_can_turn_a_fitting_label_into_exit1(self):
        """許容幅は --width から決定論導出される (固定閾値ではない)。"""
        steps = [{"id": "st1", "label": "確認して承認する"}, {"id": "st2", "label": "共有する"}]
        spec = H.flow_spec(steps=steps)
        with tempfile.TemporaryDirectory() as td:
            wide = H.render(td, spec, width=1600)
            narrow = H.render(td, spec, width=120)
        self.assertEqual(wide.returncode, 0, wide)
        self.assertEqual(narrow.returncode, 1, narrow)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

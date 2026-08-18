# -*- coding: utf-8 -*-
"""LANG-06: R11 の順序 (lead-line < 最初の具体部品 < 判断軸)。

『具体部品』の述語は config/handout-parts.json の section_scope=="in-section"。
部品 id の範囲を script へ焼き込まないこと (P03 Y-05) を CAT 系が固定する。

正本: script-brief-C18.json detections#LANG-06、
acceptance_checks AC-C18-05 / AC-C18-06 / AC-C18-LANG06-CAT。
"""

from __future__ import annotations

import json
import unittest

from _support import (
    DOCUMENT_PARTS,
    IN_SECTION_PARTS,
    NON_PART_MARKERS,
    PARTS_CATALOG,
    SCRIPT,
    LanguageGateTestCase,
    base_config,
    build_html,
)


class TestLang06Order(LanguageGateTestCase):
    def test_correct_order_passes(self):
        res = self.run_default()
        self.assert_detection_pass(res, "LANG-06")

    def test_ac05_axis_before_lead_line_is_a_violation(self):
        res = self.run_default(
            element_order={"s3": ["label", "goal", "axis", "lead", "parts", "extra"]}
        )
        self.assert_gate_fail(res, "LANG-06", count=1)

    def test_ac05_violation_row_names_the_section(self):
        res = self.run_default(
            element_order={"s3": ["label", "goal", "axis", "lead", "parts", "extra"]}
        )
        joined = "\n".join("\t".join(r) for r in self.stderr_rows(res, "LANG-06"))
        self.assertIn("s3", joined, "違反行に section id が出る\n%s" % joined)

    def test_part_before_lead_line_is_a_violation(self):
        res = self.run_default(
            element_order={"s3": ["label", "goal", "parts", "lead", "axis", "extra"]}
        )
        self.assert_gate_fail(res, "LANG-06", count=1)

    def test_axis_before_part_is_a_violation(self):
        res = self.run_default(
            element_order={"s3": ["label", "goal", "lead", "axis", "parts", "extra"]}
        )
        self.assert_gate_fail(res, "LANG-06", count=1)

    def test_section_goal_chip_before_lead_line_is_not_a_violation(self):
        """セクション冒頭のゴールチップ (C22 の担当) は順序条件に含めない。"""
        res = self.run_default()
        self.assert_detection_pass(res, "LANG-06")

    def test_section_goal_chip_after_axis_is_not_lang06_business(self):
        """goal-chip の位置は C22 NAR-03 の責務。C18 は一切触れない。"""
        res = self.run_default(
            element_order={"s3": ["label", "lead", "parts", "axis", "goal", "extra"]}
        )
        self.assert_detection_pass(res, "LANG-06")
        self.assert_gate_pass(res)

    def test_missing_section_goal_chip_is_not_lang06_business(self):
        res = self.run_default(omit_section_goal={"s3"})
        self.assert_gate_pass(res)

    def test_two_sections_out_of_order_produce_two_violations(self):
        order = ["label", "goal", "axis", "lead", "parts", "extra"]
        res = self.run_default(element_order={"s3": order, "s4": order})
        self.assert_gate_fail(res, "LANG-06", count=2)


class TestLang06ConcretePartPredicate(LanguageGateTestCase):
    def test_ac06_section_without_any_part_is_a_violation(self):
        res = self.run_default(no_parts={"s3"})
        self.assert_gate_fail(res, "LANG-06", count=1)

    def test_ac06_reason_mentions_missing_concrete_part(self):
        res = self.run_default(no_parts={"s3"})
        reason = "\t".join(self.stderr_rows(res, "LANG-06")[0][3:])
        self.assertIn("具体部品", reason, "『具体部品が無い』と読める理由を出す\nreason=%r" % reason)

    def test_document_scope_part_does_not_count_as_concrete(self):
        """section_scope=="document" の部品 (sticky ナビ・ヒーロー) は数えない。"""
        res = self.run_default(part_ids={"s3": DOCUMENT_PARTS})
        self.assert_gate_fail(res, "LANG-06", count=1)

    def test_structure_marker_does_not_count_as_concrete(self):
        """data-hb-part の構造・UI 枠の値 (memo / toolbar 等) は部品ではない。"""
        res = self.run_default(part_ids={"s3": NON_PART_MARKERS})
        self.assert_gate_fail(res, "LANG-06", count=1)

    def test_unknown_part_id_does_not_count_as_concrete(self):
        res = self.run_default(part_ids={"s3": ["B99"]})
        self.assert_gate_fail(res, "LANG-06", count=1)

    def test_every_in_section_part_id_is_accepted_alone(self):
        """カタログの in-section 部品はどれ 1 つでも『具体』として成立する。"""
        for pid in IN_SECTION_PARTS:
            with self.subTest(part=pid):
                res = self.run_default(part_ids={"s3": [pid]})
                self.assert_detection_pass(res, "LANG-06")

    def test_first_concrete_part_defines_the_boundary(self):
        """document 部品が先にあっても、境界は最初の in-section 部品で決まる。"""
        res = self.run_default(part_ids={"s3": ["B02", "B05"]})
        self.assert_detection_pass(res, "LANG-06")


class TestLang06CatalogDriven(LanguageGateTestCase):
    """AC-C18-LANG06-CAT: 部品 id が script へ焼き込まれていないこと。"""

    def test_part_added_after_the_original_range_is_recognized(self):
        """B16 / B17 は旧記述 (B03..B15) の外。カタログ駆動なら合格する。"""
        for pid in ("B16", "B17"):
            with self.subTest(part=pid):
                res = self.run_default(part_ids={"s3": [pid]})
                self.assert_detection_pass(res, "LANG-06")

    def test_non_b_prefixed_part_is_recognized(self):
        """IMG / DIAGRAM / TEXT は B\\d\\d 形ではない。id の形に依存していないこと。"""
        for pid in ("IMG", "DIAGRAM", "TEXT"):
            with self.subTest(part=pid):
                res = self.run_default(part_ids={"s3": [pid]})
                self.assert_detection_pass(res, "LANG-06")

    def test_script_reads_the_parts_catalog(self):
        self.require_script()
        self.assertIn(
            PARTS_CATALOG.name,
            SCRIPT.read_text(encoding="utf-8"),
            "LANG-06 は config/handout-parts.json を読んで述語を作る (id を列挙しない)",
        )

    def test_catalog_is_shipped_with_the_plugin(self):
        self.require_script()
        self.assertTrue(
            PARTS_CATALOG.exists(),
            "部品カタログ %s が無いと LANG-06 は成立しない (C11 が生成する)" % PARTS_CATALOG,
        )

    def test_catalog_declares_section_scope_for_every_part(self):
        if not PARTS_CATALOG.exists():
            self.fail("部品カタログ未生成: %s" % PARTS_CATALOG)
        catalog = json.loads(PARTS_CATALOG.read_text(encoding="utf-8"))
        for part in catalog["parts"]:
            self.assertIn("section_scope", part, "%s に section_scope が無い" % part.get("id"))


class TestLang06Nesting(LanguageGateTestCase):
    def test_descendant_part_counts_not_only_direct_child(self):
        """『子孫要素』が述語。入れ子でも具体部品として数える。"""
        cfg = base_config()
        html = build_html(cfg, no_parts={"s3"})
        html = html.replace(
            "    <p>ここには具体部品がありません。</p>\n",
            '    <div class="wrap"><div data-hb-part="B05"><p>入れ子の具体部品。</p></div></div>\n',
        )
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_detection_pass(res, "LANG-06")

    def test_part_in_another_section_does_not_satisfy_this_section(self):
        res = self.run_default(no_parts={"s3"}, part_ids={"s4": ["B05", "B07"]})
        self.assert_gate_fail(res, "LANG-06", count=1)


if __name__ == "__main__":
    unittest.main()

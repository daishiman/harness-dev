# -*- coding: utf-8 -*-
"""要点層と詳細層の切り分けの検査 (W-DETAIL-ABSENT / W-LAYER-ORDER / W-DETAIL-FLOWLESS)。

判定基準の出所は config/handout-visual-policy.json#layering である。層の印には
新しいフィールドを足さず、既存の順序つき enum である section.attainment_step を
使う。本テストはその再利用が保たれていること (層専用フィールドが生えていない
こと) と、層を分けていない資料を巻き込まないことを固定する。
"""

import json
import unittest

from _harness import section, text_part
from test_visual_density import VisualDensityTestBase, diagram, diagram_part, table_part

VISUAL_POLICY_RELPATH = "config/handout-visual-policy.json"

SUMMARY = "overview"
DETAIL = "operable"


def steps_part(part_id):
    """手順の並び (B03)。詳細層が持つべき『流れ』の部品。"""
    return {"part": "B03", "id": part_id, "data": {"rows": [
        {"key": "s1", "num": 1, "text": "受注を取り込む"},
        {"key": "s2", "num": 2, "text": "所要時間へ換算"},
    ]}}


class LayeringTestBase(VisualDensityTestBase):

    def patch_layering(self, **attrs):
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        policy.setdefault("layering", {}).update(attrs)
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    def layered_config(self, summary_parts=None, detail_parts=None, **over):
        """要点層 1 節 + 詳細層 1 節。警告が 1 件も出ない対照。"""
        cfg = self.visual_ok_config()
        cfg["sections"] = [
            section("intro", attainment_step=SUMMARY,
                    parts=summary_parts or [diagram_part("intro-d1"), text_part("intro-t1")]),
            section("practice", id="practice", attainment_step=DETAIL,
                    parts=detail_parts or [steps_part("practice-s1"), text_part("practice-t1")]),
        ]
        cfg.update(over)
        return cfg


class TestLayeringBaseline(LayeringTestBase):

    def test_layered_config_emits_no_layer_warning(self):
        res, _ = self.validate(self.layered_config())
        self.assert_exit(res, 0)
        for code in ("W-DETAIL-ABSENT", "W-LAYER-ORDER", "W-DETAIL-FLOWLESS"):
            self.assert_no_diag(res, code)

    def test_unlayered_config_is_out_of_scope(self):
        """全節が同じ段の資料には当てない。層を分けていない既存資料を落とさない。"""
        res, _ = self.validate(self.visual_ok_config())
        self.assert_exit(res, 0)
        for code in ("W-DETAIL-ABSENT", "W-LAYER-ORDER", "W-DETAIL-FLOWLESS"):
            self.assert_no_diag(res, code)


class TestDetailAbsent(LayeringTestBase):
    """要点だけの資料は、元の資料との差分が読み手に見えない。"""

    def test_summary_only_warns(self):
        cfg = self.layered_config()
        cfg["sections"][1]["attainment_step"] = SUMMARY
        cfg["attainment_level"] = SUMMARY
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-DETAIL-ABSENT", "/sections")

    def test_single_main_section_is_out_of_scope(self):
        """本編 1 節の資料に層の分離を求めても意味がない。"""
        cfg = self.layered_config()
        cfg["sections"] = [cfg["sections"][0]]
        cfg["attainment_level"] = SUMMARY
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-DETAIL-ABSENT")


class TestLayerOrder(LayeringTestBase):

    def test_summary_after_detail_warns(self):
        cfg = self.layered_config()
        cfg["sections"] = [cfg["sections"][1], cfg["sections"][0]]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-LAYER-ORDER", "/sections/1")

    def test_summary_before_detail_is_silent(self):
        res, _ = self.validate(self.layered_config())
        self.assert_no_diag(res, "W-LAYER-ORDER")


class TestDetailFlowless(LayeringTestBase):
    """詳細層を散文と表だけで書くと、要点層より読みにくい塊が後半に生まれる。"""

    def test_detail_without_flow_part_warns(self):
        cfg = self.layered_config(
            detail_parts=[table_part("practice-b1"), text_part("practice-t1")])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-DETAIL-FLOWLESS", "/sections/1/parts")

    def test_diagram_counts_as_flow(self):
        cfg = self.layered_config(
            detail_parts=[diagram_part("practice-d1"), text_part("practice-t1")])
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-DETAIL-FLOWLESS")

    def test_summary_layer_is_not_required_to_have_flow(self):
        """要点層は全体像だけを持てばよい。手順の形は求めない。"""
        cfg = self.layered_config(
            summary_parts=[table_part("intro-b1"), text_part("intro-t1")])
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-DETAIL-FLOWLESS")


class TestLayeringCanon(LayeringTestBase):
    """層の境目と詳細層の部品が script に埋まっていない。"""

    def test_detail_part_ids_come_from_canon(self):
        self.patch_layering(detail_parts={"ids": ["B14", "B17"]})
        res, _ = self.validate(self.layered_config())
        self.assert_diag(res, "W-DETAIL-FLOWLESS", "/sections/1/parts")

    def test_summary_step_comes_from_canon(self):
        """境目を operable へ動かすと、詳細層だった節が要点層になる。"""
        self.patch_layering(summary_step=DETAIL)
        cfg = self.layered_config()
        cfg["sections"][0]["attainment_step"] = DETAIL
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-DETAIL-ABSENT", "/sections")

    def test_missing_canon_falls_back(self):
        (self.root / VISUAL_POLICY_RELPATH).unlink()
        cfg = self.layered_config()
        cfg["sections"][1]["attainment_step"] = SUMMARY
        cfg["attainment_level"] = SUMMARY
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-DETAIL-ABSENT", "/sections")


if __name__ == "__main__":
    unittest.main()

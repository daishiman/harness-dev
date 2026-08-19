# -*- coding: utf-8 -*-
"""R21 C46 (冒頭の流れ) と C51 (成果 → 分解 → 用いる機能) の検査。

AC-C12-R21-46 / 51 が出所。閾値 max_items と属性 forbid_row_detail は
config/handout-sections.json 側にあり、script へ数値を書かないことを
データファイルの書き換えで回帰する。
"""

import unittest

import _harness as H


def b03(part_id, rows):
    return {"part": "B03", "id": part_id, "data": {"rows": rows}}


def row(num, text, time=None, sub=None):
    return {"num": num, "text": text, "sub": sub}


def flow_config(rows):
    cfg = H.valid_config()
    cfg["sections"] = [
        H.section("flow", section_kind="flow-overview", parts=[b03("flow-steps", rows)]),
        H.section("practice", id="practice"),
    ]
    return H.with_visual_floor(cfg)


def slot_part(part_id, slot):
    p = H.text_part(part_id)
    p["slot"] = slot
    return p


def capability_config(slots):
    cfg = H.valid_config()
    cfg["sections"] = [
        H.section(
            "cap",
            section_kind="capability-explainer",
            parts=[
                (slot_part("cap-p%d" % i, s) if s is not False else H.text_part("cap-p%d" % i))
                for i, s in enumerate(slots)
            ],
        ),
    ]
    # この section_kind は全部品に区画ラベルを課すので、下限を満たすために足す
    # 図解と画像にも slot が要る。末尾へ足すため最後の区画 (feature) を与える。
    return H.with_visual_floor(cfg, slot="feature")


class FlowOverviewMaxItems(H.C12TestCase):
    """C46: 大きな流れだけを列挙し、手順の詳細を冒頭に含めない。"""

    def test_within_max_items_passes(self):
        """既定 5 件までは通る。"""
        rows = [row(i + 1, "手順 %d" % (i + 1)) for i in range(5)]
        res, _ = self.validate(flow_config(rows))
        self.assert_exit(res, 0)

    def test_over_max_items_fails(self):
        """AC-C12-R21-46: 6 件は E-SECTIONKIND-MAXITEMS。"""
        rows = [row(i + 1, "手順 %d" % (i + 1)) for i in range(6)]
        res, _ = self.validate(flow_config(rows))
        self.assert_fails_with(res, "E-SECTIONKIND-MAXITEMS", "/sections/0")

    def test_threshold_comes_from_catalog_not_script(self):
        """AC-C12-R21-46 の回帰: max_items を 6 にすると同じ入力が通る (閾値が埋まっていない)。"""
        rows = [row(i + 1, "手順 %d" % (i + 1)) for i in range(6)]
        cfg = flow_config(rows)
        res_before, _ = self.validate(cfg)
        self.assert_fails_with(res_before, "E-SECTIONKIND-MAXITEMS")

        self.patch_sections_catalog("flow-overview", max_items=6)
        res_after, _ = self.validate(cfg)
        self.assert_no_diag(res_after, "E-SECTIONKIND-MAXITEMS")
        self.assert_exit(res_after, 0)

    def test_row_detail_is_forbidden(self):
        """AC-C12-R21-46: rows[].sub に詳細を書くと E-SECTIONKIND-ROWDETAIL。"""
        rows = [row(1, "全体像をつかむ", sub="メニューから設定 → 詳細 → 保存の順に押す")]
        res, _ = self.validate(flow_config(rows))
        self.assert_fails_with(res, "E-SECTIONKIND-ROWDETAIL", "/sections/0")

    def test_row_detail_null_is_fine(self):
        """sub が null なら通る。"""
        rows = [row(1, "全体像をつかむ"), row(2, "実際に動かす")]
        res, _ = self.validate(flow_config(rows))
        self.assert_exit(res, 0)

    def test_forbid_row_detail_is_catalog_driven(self):
        """forbid_row_detail を外すと sub を書けるようになる (規則の可変点はデータファイル)。"""
        rows = [row(1, "全体像をつかむ", sub="メニューから設定 → 詳細 → 保存の順に押す")]
        cfg = flow_config(rows)
        self.patch_sections_catalog("flow-overview", forbid_row_detail=None)
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "E-SECTIONKIND-ROWDETAIL")
        self.assert_exit(res, 0)

    def test_max_items_does_not_apply_to_other_kinds(self):
        """max_items 属性を持たない section_kind には件数制限がかからない。"""
        cfg = H.valid_config()
        cfg["sections"] = [
            H.section("steps", parts=[b03("s", [row(i + 1, "手順 %d" % (i + 1)) for i in range(8)])]),
        ]
        H.with_visual_floor(cfg)
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


class CapabilityExplainerSlots(H.C12TestCase):
    """C51: 機能名から始めず 成果 → 分解 → 用いる機能 の順。"""

    def test_correct_slot_order_passes(self):
        cfg = capability_config(["outcome", "breakdown", "feature"])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_multiple_parts_per_zone_pass(self):
        """各区画は 1 件以上であればよい (outcome+ → breakdown+ → feature+)。"""
        cfg = capability_config(["outcome", "outcome", "breakdown", "feature", "feature"])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_feature_before_outcome_fails(self):
        """AC-C12-R21-51: feature → outcome の並びは E-CAPABILITY-SLOT-ORDER。"""
        cfg = capability_config(["feature", "outcome", "breakdown"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-CAPABILITY-SLOT-ORDER", "/sections/0")

    def test_zone_regression_fails(self):
        """区画をまたぐ出戻り (feature の後の outcome) を落とす。"""
        cfg = capability_config(["outcome", "breakdown", "feature", "outcome"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-CAPABILITY-SLOT-ORDER", "/sections/0")

    def test_missing_zone_fails(self):
        """3 区画それぞれが 1 件以上必要。"""
        cfg = capability_config(["outcome", "feature"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-CAPABILITY-SLOT-ORDER", "/sections/0")

    def test_slot_missing_on_one_part(self):
        """AC-C12-R21-51: slot を 1 件だけ省くと E-CAPABILITY-SLOT-MISSING。"""
        cfg = capability_config(["outcome", False, "breakdown", "feature"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-CAPABILITY-SLOT-MISSING", "/sections/0/parts/1")

    def test_slot_null_counts_as_missing(self):
        """slot: null も未指定扱い (capability-explainer では全 part に必須)。"""
        cfg = capability_config(["outcome", None, "breakdown", "feature"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-CAPABILITY-SLOT-MISSING", "/sections/0/parts/1")

    def test_slot_enum(self):
        """slot は outcome | breakdown | feature | null。"""
        cfg = capability_config(["outcome", "detail", "feature"])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_slot_is_optional_in_other_kinds(self):
        """他の section_kind では slot は任意で、順序も要求しない。"""
        cfg = H.valid_config()
        cfg["sections"] = [
            H.section("std", parts=[slot_part("p0", "feature"), slot_part("p1", "outcome")]),
        ]
        H.with_visual_floor(cfg)
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-CAPABILITY-SLOT-ORDER")
        self.assert_no_diag(res, "E-CAPABILITY-SLOT-MISSING")


if __name__ == "__main__":
    unittest.main()

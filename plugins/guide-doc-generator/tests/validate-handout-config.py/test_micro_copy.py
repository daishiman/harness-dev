# -*- coding: utf-8 -*-
"""図解・カード内の 1 要素あたり文字数の検査 (W-COPY-LONG)。

判定基準の出所は config/handout-visual-policy.json#micro_copy (上限の正本) で、
その値は参考資料の実測 (analysis/guide-doc-generator/reference-analysis.md §12) に
由来する。本テストは上限値を固定値で書かず、正本を書き換えて挙動が追従することと、
免除対象 (原文貼り付け・本文・識別子) を巻き込まないことを固定する。
"""

import json
import unittest

from _harness import section, text_part, valid_config
from test_visual_density import VisualDensityTestBase, diagram, diagram_part

VISUAL_POLICY_RELPATH = "config/handout-visual-policy.json"

LONG = "この行は図解の補足として置くには長すぎる説明であり、要素そのものが段落になってしまっている状態を表す"
SHORT = "受注は前日までに確定する"


class MicroCopyTestBase(VisualDensityTestBase):

    def patch_micro_copy_role(self, role, **attrs):
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        for entry in policy["micro_copy"]["roles"]:
            if entry.get("role") == role:
                entry.update(attrs)
                break
        else:
            self.fail("micro_copy に役割 %s が無い" % role)
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    def card_part(self, part_id, **data):
        """カード 2 枚 (B04)。1 枚目へ役割別フィールドを差し込んで使う。"""
        card = {"label": "受注", "body": SHORT, "tone": "today"}
        card.update(data)
        other = {"label": "加工", "body": "当日の朝に確定する", "tone": "neutral"}
        return {"part": "B04", "id": part_id, "data": {"cards": [card, other]}}

    def map_part(self, part_id, **first):
        """選択肢の並び (B08)。要点 (title) と補足 (detail) を持つ部品。"""
        item = {"key": "a", "title": "受注を受ける", "detail": SHORT}
        item.update(first)
        return {"part": "B08", "id": part_id, "data": {"items": [
            item, {"key": "b", "title": "加工予定を立てる", "detail": "当日の朝に確定する"}]}}

    def config_with(self, part):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [diagram_part("intro-d1"), part]
        return cfg


class TestMicroCopyBaseline(MicroCopyTestBase):

    def test_short_elements_emit_no_warning(self):
        res, _ = self.validate(self.config_with(self.card_part("intro-c1")))
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "W-COPY-LONG")


class TestMicroCopyRoles(MicroCopyTestBase):
    """札・要点・補足の 3 役割それぞれに上限が当たる。"""

    def test_card_body_warns(self):
        """カードの本文は免除しない。利用者が長すぎると言うのはここである。"""
        cfg = self.config_with(self.card_part("intro-c1", body=LONG))
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-COPY-LONG", "/sections/0/parts/1/data/cards/0/body")

    def test_caption_field_warns(self):
        cfg = self.config_with(self.map_part("intro-m1", detail=LONG))
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-COPY-LONG", "/sections/0/parts/1/data/items/0/detail")

    def test_title_field_warns(self):
        cfg = self.config_with(self.map_part("intro-m1", title=LONG))
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-COPY-LONG", "/sections/0/parts/1/data/items/0/title")

    def test_title_limit_is_stricter_than_caption(self):
        """26 文字は補足 (40) には収まるが要点 (24) には収まらない。"""
        mid = "受注から加工予定を立てるまでの一連の流れを示す図です"
        cfg = self.config_with(self.map_part("intro-m1", title=mid, detail=mid))
        res, _ = self.validate(cfg)
        lines = self.assert_diag(res, "W-COPY-LONG")
        self.assertTrue(all("/title" in l for l in lines),
                        "要点だけが警告されていない: %r" % lines)

    def test_label_field_in_table_warns(self):
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"][1]["data"]["rows"][0]["header"] = "受注から加工予定までの流れ全体"
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-COPY-LONG", "/sections/1/parts/1/data/rows/0/header")

    def test_array_element_inherits_field_role(self):
        """cells[] のように名前が複数形の配列も、要素ごとに上限が当たる。"""
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"][1]["data"]["rows"][0]["cells"][1] = LONG
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-COPY-LONG", "/sections/1/parts/1/data/rows/0/cells/1")


class TestMicroCopyScope(MicroCopyTestBase):
    """当てる範囲が『部品と図解の data の中』に閉じている。"""

    def test_diagram_node_label_warns(self):
        cfg = self.visual_ok_config()
        cfg["diagrams"][0]["data"]["steps"][0]["label"] = LONG
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-COPY-LONG", "/diagrams/0/data/steps/0/label")

    def test_text_part_body_is_exempt(self):
        """TEXT の本文は detail_level の文字数予算が管轄であり、ここでは当てない。"""
        cfg = self.config_with(self.card_part("intro-c1"))
        cfg["sections"][1]["parts"] = [
            diagram_part("practice-d1", "overview"),
            text_part("practice-t1", body=LONG),
        ]
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-COPY-LONG")

    def test_identifier_fields_are_exempt(self):
        """id は読み手が読む文ではない。長くても警告しない。"""
        cfg = self.config_with(self.card_part("intro-" + "x" * 40))
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-COPY-LONG")

    def test_section_fields_are_not_touched(self):
        """セクション直下のフィールドは別の検査の管轄。ここでは当てない。"""
        cfg = self.config_with(self.card_part("intro-c1"))
        cfg["sections"][0]["heading"] = LONG
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-COPY-LONG")

    def test_exempt_part_ids_come_from_canon(self):
        """免除部品から TEXT を外すと、本文にも上限が当たるようになる。"""
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        policy["micro_copy"]["exempt_parts"]["ids"] = ["B10", "B11"]
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
        cfg = self.config_with(self.card_part("intro-c1"))
        cfg["sections"][1]["parts"] = [
            diagram_part("practice-d1", "overview"),
            text_part("practice-t1", body=LONG),
        ]
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-COPY-LONG", "/sections/1/parts/1/data/body")


class TestMicroCopyCanon(MicroCopyTestBase):
    """上限値が script に埋まっていない。"""

    def test_limit_comes_from_canon(self):
        cfg = self.config_with(self.card_part("intro-c1"))
        self.patch_micro_copy_role("caption", max_chars=5)
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-COPY-LONG", "/sections/0/parts/1/data/cards/0/body")

    def test_field_to_role_mapping_comes_from_canon(self):
        """detail を役割表から外すと、その項目には上限が当たらなくなる。"""
        cfg = self.config_with(self.map_part("intro-m1", detail=LONG))
        self.patch_micro_copy_role(
            "caption", fields=["text", "note", "expected", "alt", "cells", "sub", "body"])
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-COPY-LONG")

    def test_missing_canon_falls_back(self):
        (self.root / VISUAL_POLICY_RELPATH).unlink()
        cfg = self.config_with(self.card_part("intro-c1", body=LONG))
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-COPY-LONG", "/sections/0/parts/1/data/cards/0/body")


if __name__ == "__main__":
    unittest.main()

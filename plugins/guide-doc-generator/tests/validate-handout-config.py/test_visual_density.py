# -*- coding: utf-8 -*-
"""図解密度と散文量の検査 (W-VISUAL-ABSENT / W-DIAGRAM-FEW / W-TEXT-HEAVY / W-TEXT-RUN)。

判定基準の出所は config/handout-visual-policy.json (閾値の正本) である。
本テストは閾値そのものを固定値で書かず、正本を書き換えて挙動が追従することを
検査する。script 側へ閾値が埋め戻された場合、その回帰をここが捕まえる。

いずれも warning であり exit code は 0 のままであること (編集方針であって値域の
縛りではない) も併せて固定する。
"""

import json
import unittest

from _harness import C12TestCase, section, text_part, valid_config

VISUAL_POLICY_RELPATH = "config/handout-visual-policy.json"


def diagram(diagram_id="overview"):
    """concept 図解 1 枚 (C14 の flow パターン)。形の検査は C14 の担当。"""
    return {
        "id": diagram_id,
        "pattern": "flow",
        "title": "受注から加工予定までの流れ",
        "data": {"steps": [{"label": "受注"}, {"label": "加工予定"}]},
    }


def diagram_part(part_id, diagram_id="overview"):
    return {"part": "DIAGRAM", "id": part_id, "data": {"diagram_id": diagram_id}}


def table_part(part_id):
    """視覚部品として数えられる表 (B05 は列 2 件以上が必要)。"""
    return {
        "part": "B05",
        "id": part_id,
        "data": {
            "columns": ["項目", "内容"],
            "rows": [
                {"header": "受注", "cells": ["受注", "前日までに確定する"]},
                {"header": "加工", "cells": ["加工", "当日の朝に確定する"]},
            ],
        },
    }


class VisualDensityTestBase(C12TestCase):

    def visual_policy(self):
        path = self.root / VISUAL_POLICY_RELPATH
        self.assertTrue(path.exists(), "図解方針の正本が無い: %s" % path)
        return json.loads(path.read_text(encoding="utf-8"))

    def patch_visual_policy(self, **thresholds):
        """閾値正本を書き換える (script に閾値が埋まっていないことの回帰用)。

        キーは thresholds 直下の名前、値は差し込む value。
        """
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        for name, value in thresholds.items():
            policy.setdefault("thresholds", {}).setdefault(name, {})["value"] = value
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    def patch_visual_part_ids(self, ids):
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        policy["visual_parts"]["ids"] = ids
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    def visual_ok_config(self, **over):
        """図解密度の警告が 1 件も出ない構成データ。

        main 2 セクションに対し概念図解 2 枚 (floor=2)、各セクションは視覚部品を
        1 件以上持ち、部品 3 件のうち TEXT は 1 件 (上限比率 0.34 を超えない)。
        """
        cfg = valid_config(
            diagrams=[diagram(), diagram("detail")],
            sections=[
                section("intro", parts=[diagram_part("intro-d1"),
                                        table_part("intro-b1"),
                                        text_part("intro-t1")]),
                section("practice", id="practice",
                        parts=[diagram_part("practice-d1", "detail"),
                               table_part("practice-b1"),
                               text_part("practice-t1")]),
            ],
        )
        cfg.update(over)
        return cfg


class TestVisualDensityBaseline(VisualDensityTestBase):
    """警告が出ない状態を先に固定する (以降のテストの対照)。"""

    def test_visual_rich_config_emits_no_density_warning(self):
        res, _ = self.validate(self.visual_ok_config())
        self.assert_exit(res, 0)
        for code in ("W-VISUAL-ABSENT", "W-DIAGRAM-FEW", "W-TEXT-HEAVY", "W-TEXT-RUN"):
            self.assert_no_diag(res, code)


class TestVisualAbsent(VisualDensityTestBase):
    """W-VISUAL-ABSENT: 本文だけの main セクションを見つける。"""

    def test_text_only_main_section_warns(self):
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [text_part("practice-t1")]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-VISUAL-ABSENT", "/sections/1/parts")

    def test_appendix_section_is_exempt(self):
        """付録は読み飛ばされてよい節であり、図解の下限を当てない。"""
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [text_part("practice-t1")]
        cfg["sections"][1]["role"] = "appendix"
        cfg["sections"][1]["ties_to"] = []
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-VISUAL-ABSENT")

    def test_threshold_comes_from_canon_not_script(self):
        """下限を 3 件へ上げると、視覚部品 2 件のセクションが新たに警告される。"""
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_visual_parts_per_main_section=3)
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-VISUAL-ABSENT", "/sections/0/parts")

    def test_visual_part_ids_come_from_canon(self):
        """B05 を視覚部品の集合から外すと、表だけのセクションが警告される。"""
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [table_part("practice-b1"),
                                       table_part("practice-b2"),
                                       text_part("practice-t1")]
        self.patch_visual_part_ids(["DIAGRAM", "IMG"])
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-VISUAL-ABSENT", "/sections/1/parts")


class TestDiagramFew(VisualDensityTestBase):
    """W-DIAGRAM-FEW: 全体の関係を示す概念図解の枚数を見る。"""

    def test_zero_diagram_warns(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [table_part("intro-b1"),
                                       table_part("intro-b2"),
                                       text_part("intro-t1")]
        cfg["sections"][1]["parts"] = [table_part("practice-b1"),
                                       table_part("practice-b2"),
                                       text_part("practice-t1")]
        cfg.pop("diagrams", None)
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-DIAGRAM-FEW", "/diagrams")

    def test_floor_applies_to_small_documents(self):
        """main 2 個 × 比率 0.6 は切り上げて 2 枚。floor と一致するので 2 枚で足りる。"""
        res, _ = self.validate(self.visual_ok_config())
        self.assert_no_diag(res, "W-DIAGRAM-FEW")

    def test_ratio_comes_from_canon_not_script(self):
        """比率を 2.0 へ上げると main 2 個に対し 4 枚が必要になり、2 枚では足りない。"""
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_diagrams_per_main_sections=2.0)
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-DIAGRAM-FEW", "/diagrams")


class TestTextHeavy(VisualDensityTestBase):
    """W-TEXT-HEAVY: セクションが実質的に文章の塊になっていないか。"""

    def test_majority_text_warns(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            text_part("intro-t1"),
            table_part("intro-b1"),
            text_part("intro-t2"),
            text_part("intro-t3"),
        ]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-TEXT-HEAVY", "/sections/0/parts")

    def test_ratio_at_limit_is_allowed(self):
        """上限比率は『超えたら』警告であり、部品 3 件中 TEXT 1 件 (0.33) は許す。"""
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            table_part("intro-b1"),
            text_part("intro-t1"),
        ]
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-TEXT-HEAVY")

    def test_ratio_comes_from_canon_not_script(self):
        cfg = self.visual_ok_config()
        self.patch_visual_policy(max_text_parts_ratio_per_section=0.2)
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-TEXT-HEAVY", "/sections/0/parts")


class TestTextRun(VisualDensityTestBase):
    """W-TEXT-RUN: 画面上で 1 つの長文に見える TEXT の連続。"""

    def test_consecutive_text_warns(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            text_part("intro-t1"),
            text_part("intro-t2"),
            table_part("intro-b1"),
        ]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-TEXT-RUN", "/sections/0/parts/2")

    def test_reported_once_per_section(self):
        """同じ節の連続は直す箇所が同じなので、1 件だけ報告する。"""
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            text_part("intro-t1"),
            text_part("intro-t2"),
            text_part("intro-t3"),
            text_part("intro-t4"),
        ]
        res, _ = self.validate(cfg)
        lines = self.assert_diag(res, "W-TEXT-RUN")
        self.assertEqual(1, len(lines), "W-TEXT-RUN が節あたり 1 件に絞られていない: %r" % lines)

    def test_separated_text_is_allowed(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            text_part("intro-t1"),
            diagram_part("intro-d1"),
            text_part("intro-t2"),
        ]
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-TEXT-RUN")

    def test_limit_comes_from_canon_not_script(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            text_part("intro-t1"),
            text_part("intro-t2"),
            table_part("intro-b1"),
        ]
        self.patch_visual_policy(max_consecutive_text_parts=2)
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-TEXT-RUN")


class TestCanonAbsenceIsSoft(VisualDensityTestBase):
    """正本が読めなくても検査は落ちない (既定値へ退避する)。"""

    def test_missing_canon_falls_back(self):
        (self.root / VISUAL_POLICY_RELPATH).unlink()
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [text_part("practice-t1")]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-VISUAL-ABSENT", "/sections/1/parts")


if __name__ == "__main__":
    unittest.main()

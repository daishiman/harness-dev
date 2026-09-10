# -*- coding: utf-8 -*-
"""R21 C54 到達レベルの整合 (A9c)。

AC-C12-R21-54 が出所。順序つき enum (overview < operable < reproducible < skill-authoring)。
全 section.attainment_step が宣言以下 (E-ATTAINMENT-OVERRUN) かつ、少なくとも 1 件が
宣言と一致すること (E-ATTAINMENT-UNREACHED)。
"""

import unittest

import _harness as H

LEVELS = ["overview", "operable", "reproducible", "skill-authoring"]


def leveled_config(declared, steps):
    cfg = H.valid_config()
    cfg["attainment_level"] = declared
    cfg["sections"] = [
        H.section("s%d" % i, id="s%d" % i, attainment_step=step)
        for i, step in enumerate(steps)
    ]
    return H.with_visual_floor(cfg)


class AttainmentLevel(H.C12TestCase):

    def test_declared_level_enum(self):
        """列挙外の attainment_level は E-ATTAINMENT-LEVEL。"""
        cfg = H.valid_config()
        cfg["attainment_level"] = "expert"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-ATTAINMENT-LEVEL", "/attainment_level")

    def test_declared_level_required(self):
        """attainment_level は必須。"""
        cfg = H.valid_config()
        del cfg["attainment_level"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_step_enum(self):
        """section.attainment_step も同じ enum。"""
        cfg = H.valid_config()
        cfg["sections"][0]["attainment_step"] = "expert"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-ATTAINMENT-LEVEL", "/sections/0/attainment_step")

    def test_all_levels_are_accepted_as_declaration(self):
        """4 段いずれも宣言値として使える。"""
        for level in LEVELS:
            with self.subTest(level=level):
                res, _ = self.validate(leveled_config(level, [level, "overview"]))
                self.assert_exit(res, 0)

    def test_unreached_declaration(self):
        """AC-C12-R21-54: skill-authoring 宣言で全 step が operable 以下なら E-ATTAINMENT-UNREACHED。"""
        cfg = leveled_config("skill-authoring", ["overview", "operable"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-ATTAINMENT-UNREACHED", "/attainment_level")

    def test_overrun_step(self):
        """AC-C12-R21-54: 宣言 operable に対し skill-authoring の section は E-ATTAINMENT-OVERRUN。"""
        cfg = leveled_config("operable", ["operable", "skill-authoring"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-ATTAINMENT-OVERRUN", "/sections/1/attainment_step")

    def test_reproducible_overruns_operable(self):
        """順序つき enum であること (reproducible > operable)。"""
        cfg = leveled_config("operable", ["operable", "reproducible"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-ATTAINMENT-OVERRUN", "/sections/1/attainment_step")

    def test_lower_steps_are_allowed(self):
        """宣言未満の step は許される (上限検査であって一致要求ではない)。"""
        cfg = leveled_config("reproducible", ["overview", "operable", "reproducible"])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_null_step_is_out_of_scope_for_overrun(self):
        """null のセクションは上限検査の対象外。"""
        cfg = leveled_config("operable", ["operable", None])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_null_step_does_not_count_as_reached(self):
        """null は到達判定にも寄与しない。"""
        cfg = leveled_config("reproducible", [None, "operable"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-ATTAINMENT-UNREACHED")

    def test_exact_match_satisfies_reached(self):
        """1 件でも宣言と一致すれば到達と見なす。"""
        cfg = leveled_config("skill-authoring", ["overview", "skill-authoring"])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-ATTAINMENT-UNREACHED")


if __name__ == "__main__":
    unittest.main()

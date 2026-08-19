# -*- coding: utf-8 -*-
"""R21 C48 / C58 の紐づけと付録隔離 (A9b)。

AC-C12-R21-48 / 58 が出所。role=main のセクションは
(a) goal または focus_theme:* を 1 件以上、(b) target_task:* を 1 件以上 含むこと。
運営連絡 (section_kind=logistics) は required_role=appendix により本編へ置けない。
"""

import unittest

import _harness as H


def appendix_section(section_id="notice", **over):
    s = H.section(section_id, role="appendix", ties_to=[], section_kind="logistics",
                  attainment_step=None)
    s.update(over)
    return s


class TiesTo(H.C12TestCase):

    def test_main_section_without_ties_to(self):
        """AC-C12-R21-48: role=main から ties_to を削ると E-SECTION-UNTIED-GOAL。"""
        cfg = H.valid_config()
        del cfg["sections"][0]["ties_to"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTION-UNTIED-GOAL", "/sections/0")

    def test_main_section_with_empty_ties_to(self):
        """空配列も同じ (role=main では 1 件以上)。"""
        cfg = H.valid_config()
        cfg["sections"][0]["ties_to"] = []
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTION-UNTIED-GOAL", "/sections/0")

    def test_dangling_focus_theme_reference(self):
        """AC-C12-R21-48: 実在しない focus_theme:5 は E-TIES-DANGLING。"""
        cfg = H.valid_config()
        cfg["sections"][0]["ties_to"] = ["focus_theme:5", "target_task:vehicle-pl"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-TIES-DANGLING", "/sections/0/ties_to/0")

    def test_dangling_target_task_reference(self):
        """実在しない target_task:<id> も E-TIES-DANGLING。"""
        cfg = H.valid_config()
        cfg["sections"][0]["ties_to"] = ["goal", "target_task:nope"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-TIES-DANGLING", "/sections/0/ties_to/1")

    def test_unknown_ties_to_form(self):
        """3 形式 (goal / focus_theme:<idx> / target_task:<id>) 以外は受け付けない。"""
        cfg = H.valid_config()
        cfg["sections"][0]["ties_to"] = ["section:practice", "target_task:vehicle-pl"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_focus_theme_index_zero_based_and_valid(self):
        """focus_theme:0 は 0-based の実在参照として通る。"""
        cfg = H.valid_config()
        cfg["sections"][0]["ties_to"] = ["focus_theme:0", "target_task:vehicle-pl"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_goal_tie_alone_is_not_enough(self):
        """AC-C12-R21-58: goal だけに紐づく本編は E-SECTION-UNTIED-TASK で落ちる。"""
        cfg = H.valid_config()
        for sec in cfg["sections"]:
            sec["ties_to"] = ["goal"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTION-UNTIED-TASK", "/sections/0")

    def test_task_tie_alone_is_not_enough(self):
        """逆に target_task だけでも C48 側 (goal / focus_theme) が欠ける。"""
        cfg = H.valid_config()
        for sec in cfg["sections"]:
            sec["ties_to"] = ["target_task:vehicle-pl"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTION-UNTIED-GOAL", "/sections/0")

    def test_focus_theme_tie_satisfies_c48(self):
        """C48 は goal でも focus_theme でも満たせる。"""
        cfg = H.valid_config()
        for sec in cfg["sections"]:
            sec["ties_to"] = ["focus_theme:0", "target_task:vehicle-pl"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_appendix_section_may_have_empty_ties_to(self):
        """role=appendix では ties_to が空配列でよい。"""
        cfg = H.valid_config()
        cfg["sections"].append(appendix_section())
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


class RoleAndAppendix(H.C12TestCase):

    def test_logistics_cannot_be_main(self):
        """AC-C12-R21-48: section_kind=logistics を role=main で置くと E-SECTION-ROLE-CONFLICT。"""
        cfg = H.valid_config()
        cfg["sections"].append(
            H.section("notice", section_kind="logistics", role="main",
                      ties_to=["goal", "target_task:vehicle-pl"], attainment_step=None)
        )
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTION-ROLE-CONFLICT", "/sections/2")

    def test_required_role_comes_from_catalog(self):
        """required_role の出所は config/handout-sections.json (script に書かない)。

        logistics の required_role を外すと role=main で通るようになる。
        """
        self.patch_sections_catalog("logistics", required_role=None)
        cfg = H.valid_config()
        cfg["sections"].append(
            H.section("notice", section_kind="logistics", role="main",
                      ties_to=["goal", "target_task:vehicle-pl"], attainment_step=None)
        )
        H.with_visual_floor(cfg)
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "E-SECTION-ROLE-CONFLICT")
        self.assert_exit(res, 0)

    def test_appendix_before_main_is_rejected(self):
        """AC-C12-R21-48: appendix は全ての main より後ろ。前に置くと E-APPENDIX-ORDER。"""
        cfg = H.valid_config()
        cfg["sections"] = [appendix_section()] + cfg["sections"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-APPENDIX-ORDER", "/sections/0")

    def test_appendix_after_main_is_accepted(self):
        """末尾の appendix は通る (隔離の成立)。"""
        cfg = H.valid_config()
        cfg["sections"] = cfg["sections"] + [appendix_section()]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_role_enum(self):
        """role は main | appendix のみ。"""
        cfg = H.valid_config()
        cfg["sections"][0]["role"] = "extra"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_untied_topic_has_no_place_in_main(self):
        """紐づけを持てない伝達事項は appendix + logistics へ隔離する以外に置き場が無い。"""
        untied = H.section("notice", ties_to=[], attainment_step=None)
        cfg = H.valid_config()
        cfg["sections"].append(untied)
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTION-UNTIED-GOAL", "/sections/2")

        cfg2 = H.valid_config()
        cfg2["sections"].append(appendix_section())
        res2, _ = self.validate(cfg2)
        self.assert_exit(res2, 0)


if __name__ == "__main__":
    unittest.main()

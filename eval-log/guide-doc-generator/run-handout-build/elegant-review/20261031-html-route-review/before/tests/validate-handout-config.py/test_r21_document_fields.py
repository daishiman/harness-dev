# -*- coding: utf-8 -*-
"""R21 の document 追加検査 (A5b)。C47 focus_theme / C57 覚えることの対 / C58 target_tasks。

出所: script-brief-C12.json の document_level_fields と acceptance_checks
AC-C12-R21-47 / 57 / 58、RESOLUTION-R21.md の該当行。
"""

import unittest

import _harness as H


class FocusTheme(H.C12TestCase):
    """C47: 冒頭の主題枠を 1〜2 件に絞り、空にできない。"""

    def test_focus_theme_missing(self):
        """AC-C12-R21-47: focus_theme の欠落は exit 1。"""
        cfg = H.valid_config()
        del cfg["focus_theme"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)
        codes = {l.split(" ")[0] for l in res.stderr.splitlines() if l.strip()}
        self.assertTrue(
            {"E-FOCUS-THEME", "E-FIELD-MISSING"} & codes,
            "focus_theme 欠落が E-FOCUS-THEME / E-FIELD-MISSING のどちらでも報告されない: %r" % res.stderr,
        )

    def test_focus_theme_empty_array(self):
        """AC-C12-R21-47: 0 件は E-FOCUS-THEME。"""
        cfg = H.valid_config()
        cfg["focus_theme"] = []
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FOCUS-THEME", "/focus_theme")

    def test_focus_theme_three_items(self):
        """AC-C12-R21-47: 3 件以上は E-FOCUS-THEME (冒頭の情報過多へ戻さない)。"""
        cfg = H.valid_config()
        cfg["focus_theme"] = [
            "自分の集計業務を生成 AI へ任せる勘所をつかむ",
            "指示文の型を覚えて自分の言葉で書き換えられる",
            "出力の誤りを見つけて直す手順を身につける",
        ]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FOCUS-THEME", "/focus_theme")

    def test_focus_theme_two_items_pass(self):
        """上限は 2 件なのでちょうど 2 件は通る。"""
        cfg = H.valid_config()
        cfg["focus_theme"] = [
            "自分の集計業務を生成 AI へ任せる勘所をつかむ",
            "指示文の型を覚えて自分の言葉で書き換えられる",
        ]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_focus_theme_blank_element(self):
        """AC-C12-R21-47: 空文字の混入は E-FOCUS-THEME。"""
        cfg = H.valid_config()
        cfg["focus_theme"] = ["   "]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FOCUS-THEME", "/focus_theme/0")

    def test_focus_theme_element_too_short(self):
        """各要素は 10..60 文字。"""
        cfg = H.valid_config()
        cfg["focus_theme"] = ["短い"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FOCUS-THEME", "/focus_theme/0")

    def test_focus_theme_element_too_long(self):
        cfg = H.valid_config()
        cfg["focus_theme"] = ["あ" * 61]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FOCUS-THEME", "/focus_theme/0")

    def test_focus_theme_is_not_replaced_by_goal(self):
        """focus_theme は document.goal と別フィールドで、goal があっても代替されない。"""
        cfg = H.valid_config()
        cfg["focus_theme"] = []
        self.assertTrue(cfg["goal"])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-FOCUS-THEME")


class RememberPair(H.C12TestCase):
    """C57: must_remember と no_need_to_remember は対で必須。"""

    def test_only_must_remember(self):
        """AC-C12-R21-57: no_need_to_remember が空なら E-REMEMBER-PAIR。"""
        cfg = H.valid_config()
        cfg["must_remember"] = ["指示文は目的から書く", "出力は必ず自分で確かめる"]
        cfg["no_need_to_remember"] = []
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-REMEMBER-PAIR")

    def test_only_no_need_to_remember(self):
        """AC-C12-R21-57: 逆向きも同じ診断 (対称な検査)。"""
        cfg = H.valid_config()
        cfg["must_remember"] = []
        cfg["no_need_to_remember"] = ["個々のモデル名とオプションの綴り"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-REMEMBER-PAIR")

    def test_both_missing_is_also_pair_violation(self):
        """両方欠落も対の不成立として落ちる。"""
        cfg = H.valid_config()
        del cfg["must_remember"]
        del cfg["no_need_to_remember"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)
        codes = {l.split(" ")[0] for l in res.stderr.splitlines() if l.strip()}
        self.assertTrue({"E-REMEMBER-PAIR", "E-FIELD-MISSING"} & codes, res.stderr)

    def test_must_remember_over_default_max(self):
        """AC-C12-R21-57: 既定上限 2 を超える 3 件は E-REMEMBER-MAX。"""
        cfg = H.valid_config()
        cfg["must_remember"] = ["指示文は目的から書く", "出力は必ず自分で確かめる", "元データの範囲を先に決める"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-REMEMBER-MAX", "/must_remember")

    def test_must_remember_max_can_be_raised(self):
        """must_remember_max を上げれば 3 件が通る (上限だけが可変)。"""
        cfg = H.valid_config()
        cfg["must_remember_max"] = 3
        cfg["must_remember"] = ["指示文は目的から書く", "出力は必ず自分で確かめる", "元データの範囲を先に決める"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_must_remember_max_out_of_range(self):
        """must_remember_max は 1..5。"""
        for value in (0, 6):
            with self.subTest(value=value):
                cfg = H.valid_config()
                cfg["must_remember_max"] = value
                res, _ = self.validate(cfg)
                self.assert_exit(res, 1)

    def test_must_remember_lower_bound_is_not_configurable(self):
        """下限 1 件は不変 (must_remember_max を上げても 0 件は通らない)。"""
        cfg = H.valid_config()
        cfg["must_remember_max"] = 5
        cfg["must_remember"] = []
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-REMEMBER-PAIR")

    def test_remember_element_length(self):
        """must_remember の各要素は 5..60 文字、no_need_to_remember は 5..80 文字。"""
        cfg = H.valid_config()
        cfg["must_remember"] = ["短い"]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

        cfg2 = H.valid_config()
        cfg2["no_need_to_remember"] = ["あ" * 81]
        res2, _ = self.validate(cfg2)
        self.assert_exit(res2, 1)


class TargetTasks(H.C12TestCase):
    """C58: 達成したい具体業務。"""

    def test_target_tasks_empty(self):
        """AC-C12-R21-58: 0 件は E-TARGET-TASKS-EMPTY。"""
        cfg = H.valid_config()
        cfg["target_tasks"] = []
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-TARGET-TASKS-EMPTY", "/target_tasks")

    def test_target_tasks_missing(self):
        """ヒアリング漏れは target_tasks の欠落として確実に落ちる。"""
        cfg = H.valid_config()
        del cfg["target_tasks"]
        cfg["sections"] = [H.section("intro", ties_to=["goal"])]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_target_task_id_must_be_unique(self):
        """id は一意 (ties_to の参照先が一意に決まるため)。"""
        cfg = H.valid_config()
        cfg["target_tasks"] = [
            {"id": "vehicle-pl", "label": "車両収支レポートの月次集計を自動化する"},
            {"id": "vehicle-pl", "label": "車両収支レポートの確認手順を短縮する"},
        ]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_target_task_id_format(self):
        cfg = H.valid_config()
        cfg["target_tasks"] = [{"id": "Vehicle_PL", "label": "車両収支レポートの月次集計を自動化する"}]
        cfg["sections"] = [H.section("intro", ties_to=["goal", "target_task:Vehicle_PL"])]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_target_task_label_length(self):
        """label は 10..80 文字。"""
        cfg = H.valid_config()
        cfg["target_tasks"] = [{"id": "vehicle-pl", "label": "集計"}]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_reader_attributes_do_not_substitute_target_tasks(self):
        """reader / prior_knowledge_level / essential_problem は属性であって達成目標を代替しない。"""
        cfg = H.valid_config()
        cfg["target_tasks"] = []
        for key in ("reader", "prior_knowledge_level", "essential_problem"):
            self.assertTrue(cfg[key])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-TARGET-TASKS-EMPTY")


if __name__ == "__main__":
    unittest.main()

"""C01 run-handout-build の受入テスト (実装前は赤で固定する)。

対象: plugins/guide-doc-generator/skills/run-handout-build/

skill component は実行そのものを機械検査できないため、SKILL.md の宣言的契約
(frontmatter / 必須セクション / 参照スクリプトの実在 / ヒアリング必須項目 /
呼び出す component の宣言) を検査する。判定器は contract_lib.check_skill で、
その判定力は test_contract_checker.py が受入例・非受入例で固定している。

契約 id と出典の対応表は同ディレクトリの README.md を参照。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

SKILL_DIR = contract_lib.build_target_dir()


class HandoutBuildSkillContractTest(unittest.TestCase):
    """契約 id ごとに 1 メソッド。実装が無い間は全件が AC-C01-1 で赤になる。"""

    @classmethod
    def setUpClass(cls):
        cls.violations = contract_lib.check_skill(SKILL_DIR)
        cls.ids = contract_lib.violation_ids(cls.violations)

    def assertContract(self, contract_id):
        # 実装が無い状態を「違反 0 件」と読ませない。SKILL.md が無い間は
        # 全契約が未達であり、各契約テストは赤でなければならない。
        if not (SKILL_DIR / "SKILL.md").is_file():
            self.fail(f"{contract_id} 未達: SKILL.md が未実装 ({SKILL_DIR / 'SKILL.md'})")
        hits = [x for x in self.violations if x.contract_id == contract_id]
        if hits:
            self.fail(
                f"{contract_id} 違反 ({SKILL_DIR}):\n"
                + "\n".join(f"  - {x.message}" for x in hits)
            )

    # --- 存在と identity -------------------------------------------------
    def test_AC_C01_1_build_target_skill_md_exists(self):
        """build_target に SKILL.md が実在する (task-spec acceptance_criterion)。"""
        self.assertTrue(
            (SKILL_DIR / "SKILL.md").is_file(),
            f"SKILL.md が未実装: {SKILL_DIR / 'SKILL.md'}",
        )

    def test_AC_C01_2_frontmatter_identity(self):
        """name / prefix / kind / hierarchy が brief と一致する。"""
        self.assertContract("AC-C01-2")

    def test_AC_C01_3_description_declares_trigger(self):
        """description が trigger_conditions から発見可能な語彙を持つ。"""
        self.assertContract("AC-C01-3")

    # --- 責務 ------------------------------------------------------------
    def test_AC_C01_4_responsibilities_exact_five(self):
        """responsibilities は R1-elicit / R2-design / R3-render / R4-verify / R5-refine の 5 件ちょうど。"""
        self.assertContract("AC-C01-4")

    def test_AC_C01_5_responsibility_prompt_files_exist(self):
        """各責務の prompts/<R-id>.md が宣言され実在する。"""
        self.assertContract("AC-C01-5")

    # --- combinator / feedback contract ----------------------------------
    def test_AC_C01_6_goal_seek_contract(self):
        """combinators と goal_seek (inline / subagent / max_loops 5) が inventory と一致する。"""
        self.assertContract("AC-C01-6")

    def test_AC_C01_7_feedback_contract_criteria(self):
        """IN1 (inner/script) / OUT1 (outer/test) / OUT2 (outer/test) が揃う。"""
        self.assertContract("AC-C01-7")

    # --- 本文骨格 ---------------------------------------------------------
    def test_AC_C01_8_required_sections(self):
        """run 系 skill の必須セクションとゴールシークのサブセクションが揃う。"""
        self.assertContract("AC-C01-8")

    def test_AC_C01_9_criteria_acceptance_covers_all_criteria(self):
        """## Criteria acceptance が全 criteria id に言及する。"""
        self.assertContract("AC-C01-9")

    # --- 参照スクリプト ---------------------------------------------------
    def test_AC_C01_10_deterministic_check_scripts_referenced_and_exist(self):
        """deterministic_checks の 7 script が script_refs にあり、参照パスが実在する。"""
        self.assertContract("AC-C01-10")

    # --- R21 ヒアリング必須項目 (C58 owner) --------------------------------
    def test_AC_C01_11_hearing_required_items_declared(self):
        """R21 必須 5 項目が過不足なく宣言され、required と question_ja を持つ。"""
        self.assertContract("AC-C01-11")

    def test_AC_C01_12_target_tasks_min_one(self):
        """target_tasks は 1 件以上必須で、C12 E-TARGET-TASKS-EMPTY に紐づく (R21 C58)。"""
        self.assertContract("AC-C01-12")

    def test_AC_C01_13_remember_pair_required(self):
        """must_remember と no_need_to_remember が対で必須、上限 2 件 (R21 C57)。"""
        self.assertContract("AC-C01-13")

    def test_AC_C01_14_presentation_order_is_not_a_hearing_item(self):
        """提示順は質問せず C12 CR-PRESENTATION-ORDER が導出する。"""
        self.assertContract("AC-C01-14")

    # --- 責務境界 ---------------------------------------------------------
    def test_AC_C01_15_gate_aggregation_delegated_to_c09(self):
        """ゲート 4 状態集約は C09 CR-GATE-AGG が正本で、自前集約しない (P03 Y-07)。"""
        self.assertContract("AC-C01-15")

    def test_AC_C01_16_bundle_placement_delegated_to_c19(self):
        """handout-config.json と assets/ の配置は C19 (--place-config / --assets-src) (P03 Y-04)。"""
        self.assertContract("AC-C01-16")

    def test_AC_C01_17_readme_writer_and_five_sections(self):
        """README.md の writer は C01 で、5 節を宣言する。"""
        self.assertContract("AC-C01-17")

    def test_AC_C01_18_readability_review_delegated_to_c03(self):
        """depends_on に C03 を持ち、読みやすさ判定を C03 へ委譲する (P03 Y-09)。"""
        self.assertContract("AC-C01-18")

    def test_AC_C01_19_non_interactive_path_open(self):
        """検証済み構成データを直接受け取る非対話経路を塞がない。"""
        self.assertContract("AC-C01-19")

    def test_AC_C01_20_html_assembly_delegated_to_scripts(self):
        """HTML の組み立ては決定論 script へ委譲し LLM で書かない。"""
        self.assertContract("AC-C01-20")

    # --- 出力契約とメタ ---------------------------------------------------
    def test_AC_C01_21_output_contract_declared(self):
        """同梱 4 点と生成レポート 4 要素が Purpose & Output Contract に宣言される。"""
        self.assertContract("AC-C01-21")

    def test_AC_C01_22_allowed_tools(self):
        """allowed-tools が Read / Write / Bash を含む。"""
        self.assertContract("AC-C01-22")

    def test_AC_C01_23_output_language_ja(self):
        """output_language が ja である。"""
        self.assertContract("AC-C01-23")

    def test_AC_C01_24_source_traceability(self):
        """source が component-inventory.json#C01 を指す。"""
        self.assertContract("AC-C01-24")

    # --- 総合 -------------------------------------------------------------
    def test_no_contract_violation_remains(self):
        """契約違反が 1 件も残っていない。"""
        self.assertEqual(
            [],
            [(x.contract_id, x.message) for x in self.violations],
        )


class BuildTargetLayoutTest(unittest.TestCase):
    """build_target のディレクトリ構造そのもの。"""

    def test_skill_directory_exists(self):
        self.assertTrue(SKILL_DIR.is_dir(), f"build_target が未作成: {SKILL_DIR}")

    def test_prompts_directory_exists(self):
        self.assertTrue(
            (SKILL_DIR / "prompts").is_dir(),
            "goal_seek engine=inline は責務ごとの prompts/<R-id>.md を要求する",
        )


if __name__ == "__main__":
    unittest.main()

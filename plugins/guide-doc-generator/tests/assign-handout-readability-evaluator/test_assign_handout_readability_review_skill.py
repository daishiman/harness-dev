"""C03 assign-handout-readability-evaluator の受入テスト (実装前は赤で固定する)。

対象: plugins/guide-doc-generator/skills/assign-handout-readability-evaluator/

skill component は実行そのものを機械検査できないため、SKILL.md の宣言的契約
(frontmatter / 必須セクション / 委譲先 agent と script の実在 / 委譲の入出力契約 /
責務境界) を検査する。判定器は contract_lib.check_skill で、その判定力は
test_contract_checker.py が受入例・非受入例で固定している。

C03 は「初心者に伝わるか」を自分で判定しない skill である。したがってここで赤に
固定するのは「よいレビューをするか」ではなく、次の 3 点である。
  1. 独立 context の handout-readability-reviewer (C06) へ委譲する配線があるか
  2. 委譲の入力 (html_path / config_path / gate_reports / reader_profile / scope) と
     出力 (verdict 7 項目 / findings 6 項目) が欠落なく契約されているか
  3. 判定基準とループ制御を C03 が吸収していないか (proposer≠approver の保持)

契約 id と出典の対応表は同ディレクトリの README.md を参照。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

SKILL_DIR = contract_lib.build_target_dir()


class AssignHandoutReadabilityReviewContractTest(unittest.TestCase):
    """契約 id ごとに 1 メソッド。実装が無い間は全件が AC-C03-1 で赤になる。"""

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
    def test_AC_C03_1_build_target_skill_md_exists(self):
        """build_target に SKILL.md が実在する (task-spec acceptance_criterion)。"""
        self.assertTrue(
            (SKILL_DIR / "SKILL.md").is_file(),
            f"SKILL.md が未実装: {SKILL_DIR / 'SKILL.md'}",
        )

    def test_AC_C03_2_frontmatter_identity(self):
        """name / prefix / kind / hierarchy と user-invocable: false が brief と一致する。"""
        self.assertContract("AC-C03-2")

    def test_AC_C03_3_description_declares_trigger(self):
        """description が trigger_conditions (読みやすさ / レビュー / 資料) から発見できる。"""
        self.assertContract("AC-C03-3")

    # --- 委譲の配線 --------------------------------------------------------
    def test_AC_C03_4_delegates_to_independent_reviewer_agent(self):
        """context: fork で handout-readability-reviewer (C06) へ委譲し、その実体が存在する。"""
        self.assertContract("AC-C03-4")

    # --- 責務 --------------------------------------------------------------
    def test_AC_C03_5_responsibilities_exact_one_assign(self):
        """responsibilities は R1-assign 1 件ちょうど (自分で判定する責務を持たない)。"""
        self.assertContract("AC-C03-5")

    def test_AC_C03_6_responsibility_prompt_exists(self):
        """prompts/R-review-readability.md が宣言され実在する (C06 prompt_ref)。"""
        self.assertContract("AC-C03-6")

    def test_AC_C03_7_depends_on_matches_inventory(self):
        """depends_on は C04 / C18 (component-inventory.json #C03)。"""
        self.assertContract("AC-C03-7")

    def test_AC_C03_8_deterministic_check_script_referenced_and_exists(self):
        """deterministic_checks の verify-handout-language.py が宣言され実在する。"""
        self.assertContract("AC-C03-8")

    def test_AC_C03_9_required_sections(self):
        """assign 系 skill の必須セクションが揃う。"""
        self.assertContract("AC-C03-9")

    # --- 責務境界 -----------------------------------------------------------
    def test_AC_C03_10_read_only_boundary(self):
        """書き込み系ツールを持たず、資料の書き換えは C01 の責務であると宣言する。"""
        self.assertContract("AC-C03-10")

    def test_AC_C03_11_holds_no_judgement_criteria(self):
        """判定基準を持たず verdict を再判定しない (判定するのは C06)。"""
        self.assertContract("AC-C03-11")

    # --- 委譲の入出力契約 ---------------------------------------------------
    def test_AC_C03_12_delegation_inputs_assembled(self):
        """html_path / config_path / gate_reports / reader_profile を渡し scope は任意。"""
        self.assertContract("AC-C03-12")

    def test_AC_C03_13_gate_exit0_is_precondition(self):
        """C16/C17/C18/C22 の全 exit0 が前提で、FAIL 残存時は blocked を差し戻す。"""
        self.assertContract("AC-C03-13")

    def test_AC_C03_14_verdict_fields_collected_without_loss(self):
        """verdict 7 項目と findings 6 項目 (根拠と改善提案を含む) を欠落なく回収する。"""
        self.assertContract("AC-C03-14")

    def test_AC_C03_15_parent_context_not_leaked(self):
        """設計意図・ヒアリング生ログ・参照 HTML・loop 回数・過去 findings を渡さない。"""
        self.assertContract("AC-C03-15")

    def test_AC_C03_16_no_loop_control(self):
        """combinators / goal_seek を持たず、再レビュー回数の上限も持たない。"""
        self.assertContract("AC-C03-16")

    # --- メタ ---------------------------------------------------------------
    def test_AC_C03_17_rubric_refs(self):
        """rubric_refs が ref-handout-design-system を指す。"""
        self.assertContract("AC-C03-17")

    def test_AC_C03_18_output_language_ja(self):
        """output_language が ja である。"""
        self.assertContract("AC-C03-18")

    def test_AC_C03_19_source_traceability(self):
        """source が component-inventory.json#C03 を指す。"""
        self.assertContract("AC-C03-19")

    def test_AC_C03_20_proposer_is_not_approver(self):
        """生成した本人が採点しない構造 (独立 context) を本文が宣言する。"""
        self.assertContract("AC-C03-20")

    # --- 総合 ---------------------------------------------------------------
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
            "R1-assign は prompt_required: true なので prompts/ が要る",
        )

    def test_reviewer_agent_exists(self):
        """委譲先 C06 の実体 (別 leaf の build_target) が無ければ委譲は成立しない。"""
        agent = contract_lib.repo_root() / "plugins/guide-doc-generator/agents/handout-readability-reviewer.md"
        self.assertTrue(agent.is_file(), f"委譲先 agent が未実装: {agent}")


if __name__ == "__main__":
    unittest.main()

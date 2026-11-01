"""C02 run-handout-extract の受入テスト (実装前は赤で固定する)。

対象: plugins/guide-doc-generator/skills/run-handout-extract/

skill component は実行そのものを機械検査できないため、SKILL.md の宣言的契約
(frontmatter / 必須セクション / 参照スクリプトの実在 / 逆抽出の入出力契約 /
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


class HandoutExtractSkillContractTest(unittest.TestCase):
    """契約 id ごとに 1 メソッド。実装が無い間は全件が AC-C02-1 で赤になる。"""

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
    def test_AC_C02_1_build_target_skill_md_exists(self):
        """build_target に SKILL.md が実在する (task-spec acceptance_criterion)。"""
        self.assertTrue(
            (SKILL_DIR / "SKILL.md").is_file(),
            f"SKILL.md が未実装: {SKILL_DIR / 'SKILL.md'}",
        )

    def test_AC_C02_2_frontmatter_identity(self):
        """name / prefix / kind / hierarchy が brief と一致する。"""
        self.assertContract("AC-C02-2")

    def test_AC_C02_3_description_declares_trigger(self):
        """description が trigger_conditions の語彙 (逆抽出 / HTML / 構成データ) を持つ。"""
        self.assertContract("AC-C02-3")

    # --- 責務 ------------------------------------------------------------
    def test_AC_C02_4_responsibilities_exact_three(self):
        """responsibilities は R1-scan / R2-complete / R3-roundtrip の 3 件ちょうど。"""
        self.assertContract("AC-C02-4")

    def test_AC_C02_5_responsibility_prompt_files_exist(self):
        """各責務の prompts/<R-id>.md が宣言され実在する。"""
        self.assertContract("AC-C02-5")

    # --- combinator / feedback contract ----------------------------------
    def test_AC_C02_6_goal_seek_contract(self):
        """combinators と goal_seek (inline / subagent / max_loops 5) が inventory と一致する。"""
        self.assertContract("AC-C02-6")

    def test_AC_C02_7_feedback_contract_criteria(self):
        """IN1 (inner/script) / OUT1 (outer/test) が過不足なく揃う。"""
        self.assertContract("AC-C02-7")

    # --- 本文骨格 ---------------------------------------------------------
    def test_AC_C02_8_required_sections(self):
        """run 系 skill の必須セクションとゴールシークのサブセクションが揃う。"""
        self.assertContract("AC-C02-8")

    def test_AC_C02_9_criteria_acceptance_covers_all_criteria(self):
        """## Criteria acceptance が IN1 / OUT1 に言及する。"""
        self.assertContract("AC-C02-9")

    # --- 参照スクリプト ---------------------------------------------------
    def test_AC_C02_10_deterministic_check_scripts_referenced_and_exist(self):
        """deterministic_checks の 4 script が script_refs にあり、参照パスが実在する。"""
        self.assertContract("AC-C02-10")

    # --- 逆抽出の入出力契約 (R1-scan) ---------------------------------------
    def test_AC_C02_11_html_parsing_delegated_to_c20(self):
        """HTML の走査は C20 が唯一の実装で、skill は自前で parse しない。"""
        self.assertContract("AC-C02-11")

    def test_AC_C02_25_extract_invocation_flags_declared(self):
        """extract-handout-config.py を --html / --out / --report で起動する宣言がある。"""
        self.assertContract("AC-C02-25")

    # --- 逆抽出の入出力契約 (R2-complete) -----------------------------------
    def test_AC_C02_13_semantic_fields_are_never_guessed(self):
        """マーカーが無い意味情報 7 種を推測せず null で残す (C20 never_guessed)。"""
        self.assertContract("AC-C02-13")

    def test_AC_C02_14_unrecoverable_reported_as_triplet(self):
        """復元不能箇所を キーパス / 理由 / 補完方針 の 3 点セットで列挙し、黙って落とさない。"""
        self.assertContract("AC-C02-14")

    def test_AC_C02_15_guessed_and_read_values_are_distinguished(self):
        """推測値と実読み取り値を fidelity (exact / heuristic) で区別する。"""
        self.assertContract("AC-C02-15")

    def test_AC_C02_19_validation_failure_is_not_papered_over(self):
        """C12 FAIL 時に値を捏造せず、欠落キーパスを示し、空の構成データを成功にしない。"""
        self.assertContract("AC-C02-19")

    # --- 逆抽出の入出力契約 (R3-roundtrip) ----------------------------------
    def test_AC_C02_12_roundtrip_granularity_is_config_equivalence(self):
        """round-trip は正規化後の構成データ等価 (provenance 除外) で判定し、バイト一致を課さない。"""
        self.assertContract("AC-C02-12")

    def test_AC_C02_26_rerender_path_declared(self):
        """再レンダリング (C11) と自己完結性検査 (C16) を経て等価判定する。"""
        self.assertContract("AC-C02-26")

    def test_AC_C02_20_roundtrip_diff_is_not_summarized_as_equivalent(self):
        """差分は E-ROUNDTRIP-DIFF / JSON Pointer / expected / actual で全件示す。"""
        self.assertContract("AC-C02-20")

    # --- 責務境界 ---------------------------------------------------------
    def test_AC_C02_17_no_content_rewrite_or_improvement(self):
        """資料内容の書き換え・改善提案をしない (brief boundary)。"""
        self.assertContract("AC-C02-17")

    def test_AC_C02_18_stops_at_config_and_hands_off_to_c07(self):
        """生成へ踏み込まず構成データで止まり /handout-build を案内する。"""
        self.assertContract("AC-C02-18")

    def test_AC_C02_21_depends_on_declared(self):
        """depends_on が C11 / C12 / C16 / C20 を含む。"""
        self.assertContract("AC-C02-21")

    # --- 出力契約とメタ ---------------------------------------------------
    def test_AC_C02_16_output_contract_declared(self):
        """構成データ JSON と逆抽出レポート 3 要素が Purpose & Output Contract に宣言される。"""
        self.assertContract("AC-C02-16")

    def test_AC_C02_22_allowed_tools(self):
        """allowed-tools が Read / Write / Bash を含む。"""
        self.assertContract("AC-C02-22")

    def test_AC_C02_23_output_language_ja(self):
        """output_language が ja である。"""
        self.assertContract("AC-C02-23")

    def test_AC_C02_24_source_traceability(self):
        """source が component-inventory.json#C02 を指す。"""
        self.assertContract("AC-C02-24")

    def test_AC_C02_27_checklist_covers_brief(self):
        """完了チェックリストが brief checklist の 4 項目を覆う。"""
        self.assertContract("AC-C02-27")

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

    def test_extractor_script_exists(self):
        """C20 extract-handout-config.py の実体 (逆抽出の唯一の実装) が要る。"""
        script = contract_lib.repo_root() / "plugins/guide-doc-generator/scripts/extract-handout-config.py"
        self.assertTrue(script.is_file(), f"C20 の実体が未実装: {script}")


if __name__ == "__main__":
    unittest.main()

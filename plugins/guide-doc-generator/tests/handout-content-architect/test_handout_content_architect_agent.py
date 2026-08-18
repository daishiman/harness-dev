"""C05 handout-content-architect の受入テスト (実装前は赤で固定する)。

対象: plugins/guide-doc-generator/agents/handout-content-architect.md

sub-agent component は実行そのものを機械検査できないため、agent 定義 Markdown の
宣言的契約 (frontmatter の name / description / tools / 必須セクション /
責務境界の明記 / 入出力スキーマの宣言) を検査する。判定器は
contract_lib.check_agent で、その判定力は test_contract_checker.py が
受入例・非受入例で固定している。

契約 id と出典の対応表は同ディレクトリの README.md を参照。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

AGENT_MD = contract_lib.build_target()


class HandoutContentArchitectContractTest(unittest.TestCase):
    """契約 id ごとに 1 メソッド。実装が無い間は全件が赤になる。"""

    def setUp(self):
        # setUpClass で例外を投げると errors になり「テストが無い」のと区別できない。
        # 実装が無い状態でも violations は算出でき、各契約は failure として落ちる。
        self.violations = contract_lib.check_agent(AGENT_MD)

    def assertContract(self, contract_id):
        if not AGENT_MD.is_file():
            self.fail(f"{contract_id} 未達: agent 定義が未実装 ({AGENT_MD})")
        hits = [x for x in self.violations if x.contract_id == contract_id]
        if hits:
            self.fail(
                f"{contract_id} 違反 ({AGENT_MD}):\n"
                + "\n".join(f"  - {x.message}" for x in hits)
            )

    # --- 存在と identity -------------------------------------------------
    def test_AC_C05_1_build_target_exists(self):
        """build_target の agent 定義が実在する (task-spec acceptance_criterion)。"""
        self.assertTrue(
            AGENT_MD.is_file(),
            f"agent 定義が未実装: {AGENT_MD}",
        )

    def test_AC_C05_2_frontmatter_identity(self):
        """name / kind / isolation / owner_skill / prompt_layer と必須キーが揃う (AC1)。"""
        self.assertContract("AC-C05-2")

    def test_AC_C05_3_tools_are_read_and_write_only(self):
        """tools は Read, Write ちょうど。Bash / Edit を持たない (AC1 / inventory)。"""
        self.assertContract("AC-C05-3")

    def test_AC_C05_4_description_matches_canonical(self):
        """description が brief / inventory の正本文言と一致する (AC1)。"""
        self.assertContract("AC-C05-4")

    def test_AC_C05_5_prompt_ref_points_to_responsibility_prompt(self):
        """prompt_ref が責務 prompt (prompts/R*-design-config.md) を指す (AC1)。"""
        self.assertContract("AC-C05-5")

    # --- 本文骨格 --------------------------------------------------------
    def test_AC_C05_6_required_sections_and_anchor(self):
        """brief の body_sections 8 件と ANCHOR_RE 互換の責務アンカーがある。"""
        self.assertContract("AC-C05-6")

    def test_AC_C05_7_agent_prompt_section_lint_compatible(self):
        """Prompt Templates / Self-Evaluation が lint の要求を満たす (AC2)。"""
        self.assertContract("AC-C05-7")

    # --- 責務境界 --------------------------------------------------------
    def test_AC_C05_8_no_html_css_svg_output(self):
        """HTML/CSS/SVG を書かず、出力が構成データ JSON 1 個に限定される (AC3)。"""
        self.assertContract("AC-C05-8")

    def test_AC_C05_9_must_not_assume_declared(self):
        """must_not_assume の 5 項目が禁止として明記されている (AC4)。"""
        self.assertContract("AC-C05-9")

    def test_AC_C05_10_no_parent_context_leak(self):
        """親会話の前提 (参照 HTML の文面・開発計画の文脈) が本文へ混入していない。"""
        self.assertContract("AC-C05-10")

    def test_AC_C05_11_lead_line_and_goal_are_distinct(self):
        """lead_line と section goal が別フィールドで両方必須 (AC5 / C40)。"""
        self.assertContract("AC-C05-11")

    def test_AC_C05_12_date_single_writer(self):
        """date が入力に無いとき出力せず、既定充填を C12 --normalize へ委ねる (AC7)。"""
        self.assertContract("AC-C05-12")

    # --- R21 の型制約 ----------------------------------------------------
    def test_AC_C05_13_presentation_order_not_derived_here(self):
        """presentation_order を自分で導出せず、導出表も複製しない (R21 C49)。"""
        self.assertContract("AC-C05-13")

    def test_AC_C05_14_focus_theme_ties_to_and_logistics(self):
        """focus_theme 1-2 件 / ties_to / logistics の appendix 隔離 (R21 C47 C48)。"""
        self.assertContract("AC-C05-14")

    def test_AC_C05_15_flow_overview_constraints(self):
        """冒頭 flow-overview は手順詳細を書かず、上限は sections config に従う (C46)。"""
        self.assertContract("AC-C05-15")

    def test_AC_C05_16_capability_explainer_slot_order(self):
        """outcome → breakdown → feature の順と、機能名から始めない指示 (C51)。"""
        self.assertContract("AC-C05-16")

    def test_AC_C05_17_attainment_dialogue_handson_duration(self):
        """attainment_level の範囲 / dialogue / handson (B17) / anticipated-qa / duration。"""
        self.assertContract("AC-C05-17")

    def test_AC_C05_18_remember_pair_is_blocking(self):
        """must_remember と no_need_to_remember の対、片方だけは blocked (C57)。"""
        self.assertContract("AC-C05-18")

    # --- 入出力契約 ------------------------------------------------------
    def test_AC_C05_19_input_fields_and_blocked_handback(self):
        """hearing_result 14 項目の宣言と、質問を返さず blocked で差し戻す旨。"""
        self.assertContract("AC-C05-19")

    def test_AC_C05_20_output_contract_keys(self):
        """戻り値 11 キーと、書き出しが 1 ファイルだけである宣言。"""
        self.assertContract("AC-C05-20")

    def test_AC_C05_21_proposer_is_not_approver(self):
        """検証器・出力先解決を自分で実行しない (Bash 非保持) 旨の明記。"""
        self.assertContract("AC-C05-21")

    # --- SSOT と下流責務 --------------------------------------------------
    def test_AC_C05_22_vocabulary_ssot(self):
        """部品 id / 用途語彙 / schema を正本ファイルから引き、散文へ列挙しない (Y-05 Y-06)。"""
        self.assertContract("AC-C05-22")

    def test_AC_C05_23_downstream_boundaries(self):
        """SVG 座標 = C14 / symbol 抽出 = C15 / data URI 化 = C13 の委譲明記。"""
        self.assertContract("AC-C05-23")

    def test_AC_C05_24_no_emoji(self):
        """本文に絵文字が無く、構成データへ絵文字を書かない旨がある (C10)。"""
        self.assertContract("AC-C05-24")

    def test_AC_C05_25_glossary_declaration_and_body_pairing(self):
        """glossary {term, plain} の宣言と、本文初出の括弧書き併記 (C16)。"""
        self.assertContract("AC-C05-25")

    def test_AC_C05_26_no_preset_composition(self):
        """プリセットを合成せず、セクション追加の判断を decision_log へ残す。"""
        self.assertContract("AC-C05-26")


if __name__ == "__main__":
    unittest.main()

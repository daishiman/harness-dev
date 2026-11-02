"""C04 ref-handout-design-system の受入テスト (実装前は赤で固定する)。

対象 build_target: plugins/guide-doc-generator/skills/ref-handout-design-system/

skill component は実行そのものを機械検査できないため、SKILL.md の宣言的契約
(frontmatter / 4 面の見出し / 規範文言 / 語彙を複製していないこと / vendoring
実体の実在) を検査する。判定器は contract_lib.check_skill で、その判定力は
test_contract_checker.py が受入例・非受入例で固定している。

契約 id と出典の対応表は同ディレクトリの README.md を参照。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

SKILL_DIR = contract_lib.build_target_dir()
SKILL_MD = SKILL_DIR / "SKILL.md"


class RefHandoutDesignSystemContractTest(unittest.TestCase):
    """契約 id ごとに 1 メソッド。実装が無い間は全件が赤になる。"""

    @classmethod
    def setUpClass(cls):
        # 実装が未存在でも例外を投げない。check_skill は SKILL.md 不在を
        # Violation("AC-C04-1") として返すので、全メソッドが failure で落ちる。
        cls.violations = contract_lib.check_skill(SKILL_DIR)

    def assertContract(self, contract_id):
        if not SKILL_MD.is_file():
            self.fail(f"{contract_id} 未達: SKILL.md が未実装 ({SKILL_MD})")
        hits = [x for x in self.violations if x.contract_id == contract_id]
        if hits:
            self.fail(
                f"{contract_id} 違反 ({SKILL_DIR}):\n"
                + "\n".join(f"  - {x.message}" for x in hits)
            )

    # --- 存在と identity ---------------------------------------------------
    def test_AC_C04_1_build_target_skill_md_exists(self):
        """build_target に SKILL.md が実在する (task-spec acceptance_criterion)。"""
        self.assertTrue(SKILL_MD.is_file(), f"SKILL.md が未実装: {SKILL_MD}")

    def test_AC_C04_2_frontmatter_identity(self):
        """name / prefix=ref / kind=ref / hierarchy_level=L1 が brief と一致する。"""
        self.assertContract("AC-C04-2")

    def test_AC_C04_3_description_declares_trigger(self):
        """description が trigger_conditions 3 件の語彙で発見可能である。"""
        self.assertContract("AC-C04-3")

    def test_AC_C04_4_output_language_ja(self):
        """output_language が ja である。"""
        self.assertContract("AC-C04-4")

    def test_AC_C04_5_source_traceability(self):
        """source が component-inventory.json#C04 を指す。"""
        self.assertContract("AC-C04-5")

    # --- ref kind の権限と非宣言 -------------------------------------------
    def test_AC_C04_6_allowed_tools_read_only(self):
        """参照回答しかしないので allowed-tools は Read のみ。"""
        self.assertContract("AC-C04-6")

    def test_AC_C04_7_no_execution_or_loop_declarations(self):
        """cli_tools / mcp_tools / deterministic_checks / combinators / goal_seek を持たない。"""
        self.assertContract("AC-C04-7")

    # --- output_contract の 4 面 -------------------------------------------
    def test_AC_C04_8_purpose_section(self):
        """`## Purpose & Output Contract` がある。"""
        self.assertContract("AC-C04-8")

    def test_AC_C04_8a_parts_catalog_face(self):
        """面 1: 部品カタログの構成データ表現。"""
        self.assertContract("AC-C04-8a")

    def test_AC_C04_8b_css_token_face(self):
        """面 2: CSS 変数トークン一覧。"""
        self.assertContract("AC-C04-8b")

    def test_AC_C04_8c_icon_face(self):
        """面 3: アイコン規約。"""
        self.assertContract("AC-C04-8c")

    def test_AC_C04_8d_writing_face(self):
        """面 4: 文章設計の型。"""
        self.assertContract("AC-C04-8d")

    # --- 責務境界 -----------------------------------------------------------
    def test_AC_C04_9_no_html_generation_or_verification(self):
        """HTML の生成・検証をせず C11 / C16-C18 へ委譲すると明記する。"""
        self.assertContract("AC-C04-9")

    # --- 語彙の単一正本 (P03 Y-05 / Y-06 / Y-08) ----------------------------
    def test_AC_C04_10_part_ids_not_duplicated(self):
        """部品 id を本文へ列挙せず config/handout-parts.json (C11) を読んで答える。"""
        self.assertContract("AC-C04-10")

    def test_AC_C04_11_purpose_vocab_pointer(self):
        """用途語彙を列挙せず config/handout-purposes.json (C23) を指す。"""
        self.assertContract("AC-C04-11")

    def test_AC_C04_12_section_kind_pointer(self):
        """section_kind 値を列挙せず config/handout-sections.json (writer C12) を指す。"""
        self.assertContract("AC-C04-12")

    # --- デザイントークン (R10 / R21 C52) ------------------------------------
    def test_AC_C04_13_accent_one_color_four_steps(self):
        """アクセント 1 色 + 明度 4 段階の CSS 変数語彙が C11 と一致する。"""
        self.assertContract("AC-C04-13")

    def test_AC_C04_14_css_variable_driven(self):
        """実値は :root だけに置き、以降は var() 参照にする規範を持つ。"""
        self.assertContract("AC-C04-14")

    def test_AC_C04_15_theme_values_live_in_token_file(self):
        """値の正本は assets/tokens/<theme>.json。散文に実値 (hex) を焼かない。"""
        self.assertContract("AC-C04-15")

    def test_AC_C04_16_text_limits_owned_elsewhere(self):
        """text_limits.block_body_max_chars (既定 400) のスキーマ owner は C11、折り畳みは C12 CR-TEXT-FOLD。"""
        self.assertContract("AC-C04-16")

    def test_AC_C04_17_typography_palt_and_tabular_nums(self):
        """font-feature-settings:"palt" と数値の tabular-nums。"""
        self.assertContract("AC-C04-17")

    def test_AC_C04_18_rise_in_stagger_without_js(self):
        """rise-in スタガー入場を --stagger インライン変数で JS 非依存に成立させる。"""
        self.assertContract("AC-C04-18")

    # --- アイコン規約 (R08) ---------------------------------------------------
    def test_AC_C04_19_icon_style_four_rules(self):
        """viewBox="0 0 24 24" / stroke="currentColor" / fill="none" / stroke-linecap="round"。"""
        self.assertContract("AC-C04-19")

    def test_AC_C04_20_symbol_use_and_sprite_owner(self):
        """<symbol> 定義 + <use> 参照・未使用 0 件・sprite 生成は C15。"""
        self.assertContract("AC-C04-20")

    def test_AC_C04_21_no_emoji(self):
        """絵文字を使わない規範を持ち、SKILL.md 自身も絵文字を含まない。"""
        self.assertContract("AC-C04-21")

    # --- 自己完結と vendoring (R10) ------------------------------------------
    def test_AC_C04_22_no_user_global_or_absolute_paths(self):
        """~/.claude などユーザーグローバル資産と絶対パスへの参照が 0 件。"""
        self.assertContract("AC-C04-22")

    def test_AC_C04_23_design_language_vendored(self):
        """jp-web-design モードB「Pop・親しみ」を skill 配下へ vendoring し参照する。"""
        self.assertContract("AC-C04-23")

    # --- 総合 -----------------------------------------------------------------
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

    def test_vendored_asset_directory_exists(self):
        """R10 の自己完結は plugin 内に実体があって初めて成立する。"""
        self.assertTrue(
            any((SKILL_DIR / d).is_dir() for d in contract_lib.VENDOR_DIRS),
            f"vendoring 先 ({' / '.join(contract_lib.VENDOR_DIRS)}) が {SKILL_DIR} に無い",
        )


if __name__ == "__main__":
    unittest.main()

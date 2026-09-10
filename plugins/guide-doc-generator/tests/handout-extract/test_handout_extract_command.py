"""C08 handout-extract の受入テスト (実装前は赤で固定する)。

対象 build_target: plugins/guide-doc-generator/commands/handout-extract.md

slash-command component は実行そのものを機械検査できないため、command 定義の
宣言的契約 (frontmatter / 委譲先 skill の宣言と実在 / 引数の既定値と上書き規則 /
委譲先不在時の縮退 / round-trip の粒度の開示 / 入口が自前でパースロジックを
持たないこと) を検査する。判定器は contract_lib.check_command で、その判定力は
test_contract_checker.py が受入例・非受入例で固定している。

契約 id と出典の対応表は同ディレクトリの README.md を参照。
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

PLUGIN_ROOT = contract_lib.plugin_root()
PLAN_ROOT = contract_lib.plan_root()
COMMAND_MD = contract_lib.build_target()


class HandoutExtractCommandContractTest(unittest.TestCase):
    """契約 id ごとに 1 メソッド。実装が無い間は全件が赤になる。"""

    @classmethod
    def setUpClass(cls):
        cls.violations = contract_lib.check_command(PLUGIN_ROOT)
        cls.ids = contract_lib.violation_ids(cls.violations)

    def assertContract(self, contract_id):
        # 実装が無い状態を「違反 0 件」と読ませない。
        if not COMMAND_MD.is_file():
            self.fail(f"{contract_id} 未達: command 定義が未実装 ({COMMAND_MD})")
        hits = [x for x in self.violations if x.contract_id == contract_id]
        if hits:
            self.fail(
                f"{contract_id} 違反 ({COMMAND_MD}):\n"
                + "\n".join(f"  - {x.message}" for x in hits)
            )

    # --- 存在と frontmatter ----------------------------------------------
    def test_AC_C08_0_build_target_exists(self):
        """build_target に command 定義が実在する (task-spec acceptance_criterion)。"""
        self.assertTrue(COMMAND_MD.is_file(), f"未実装: {COMMAND_MD}")

    def test_AC_C08_1_frontmatter_matches_inventory(self):
        """name / description / argument-hint / allowed-tools / disable-model-invocation。

        allowed-tools は inventory #C08 の 4 件ちょうど (過不足を許さない)。
        """
        self.assertContract("AC-C08-1")

    # --- 委譲 -------------------------------------------------------------
    def test_AC_C08_2_delegates_to_run_handout_extract(self):
        """delegation_form の宣言と、委譲先 skill / 委譲チェーン script の実在。"""
        self.assertContract("AC-C08-2")

    # --- round-trip の粒度 -------------------------------------------------
    def test_AC_C08_3_roundtrip_granularity_disclosed(self):
        """正規化後の構成データ等価で判定し HTML バイト一致は課さない旨と、
        復元される範囲 / されない範囲の区別が具体名つきで宣言されている。"""
        self.assertContract("AC-C08-3")

    # --- 境界 -------------------------------------------------------------
    def test_AC_C08_4_no_overlap_with_build_and_verify(self):
        """生成 (C07) と検証 (C09) を兼ねず、案内は /handout-build に留まる。"""
        self.assertContract("AC-C08-4")

    def test_AC_C08_PARSE_entry_has_no_parsing_logic(self):
        """入口が自前で HTML を解釈せず、走査と補完を C02 skill へ渡す (R14)。"""
        self.assertContract("AC-C08-PARSE")

    # --- 引数 -------------------------------------------------------------
    def test_AC_C08_ARGS_defaults_and_overrides(self):
        """引数の既定値と上書きの解決結果 (13 通り) が正解表と一致する。"""
        self.assertContract("AC-C08-ARGS")

    # --- 縮退 -------------------------------------------------------------
    def test_AC_C08_DEGRADE_missing_delegate_is_not_success(self):
        """委譲先 skill / script が不在なら停止し、解決を試みたパスを示す。"""
        self.assertContract("AC-C08-DEGRADE")

    # --- failure_modes ----------------------------------------------------
    def test_AC_C08_FM_1_entry_stop_without_delegation(self):
        """html-path 未指定 / 不在 / ディレクトリは委譲先を起動せず停止する。"""
        self.assertContract("AC-C08-FM-1")

    def test_AC_C08_FM_2_no_silent_overwrite(self):
        """--out の既存ファイルを黙って上書きしない。"""
        self.assertContract("AC-C08-FM-2")

    def test_AC_C08_FM_3_partial_success_stays_partial(self):
        """部品構造を同定できない場合、空の構成データを成功として返さない。"""
        self.assertContract("AC-C08-FM-3")

    def test_AC_C08_FM_4_unrestorable_info_is_reported(self):
        """復元不能箇所をキーパス / 理由 / 補完方針の 3 点セットで列挙し、推測値を区別する。"""
        self.assertContract("AC-C08-FM-4")

    def test_AC_C08_FM_5_roundtrip_diff_is_fail(self):
        """round-trip 差分ありは FAIL であり等価扱いにしない。"""
        self.assertContract("AC-C08-FM-5")

    def test_AC_C08_FM_6_validate_fail_is_not_fabricated_away(self):
        """validate FAIL は事実として提示し、値を捏造して通さない。"""
        self.assertContract("AC-C08-FM-6")

    # --- 総合 -------------------------------------------------------------
    def test_no_contract_violation_remains(self):
        """契約違反が 1 件も残っていない。"""
        self.assertEqual([], [(x.contract_id, x.message) for x in self.violations])


class BuildTargetLayoutTest(unittest.TestCase):
    """build_target の配置と委譲先の実在。"""

    def test_commands_directory_exists(self):
        self.assertTrue(
            (PLUGIN_ROOT / "commands").is_dir(),
            f"commands/ が未作成: {PLUGIN_ROOT / 'commands'}",
        )

    def test_delegate_skill_exists(self):
        skill_md = PLUGIN_ROOT / "skills" / contract_lib.DELEGATE_SKILL / "SKILL.md"
        self.assertTrue(
            skill_md.is_file(),
            f"委譲先 C02 skill が未実装 (委譲先不在は成功ではない): {skill_md}",
        )

    def test_delegated_scripts_exist(self):
        missing = [
            name
            for name in contract_lib.DELEGATED_SCRIPTS
            if not (PLUGIN_ROOT / "scripts" / name).is_file()
        ]
        self.assertEqual(
            [],
            missing,
            "C02 の deterministic_checks が未実装 (round-trip 判定が成立しない)",
        )


class PlanContractTest(unittest.TestCase):
    """plan 側の事実 (AC-C08-2 / AC-C08-4 の後半) — 実装に依存しないので緑。

    実装がこの前提を書き換えた場合に赤へ転じる形で固定する。
    """

    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(
            (PLAN_ROOT / "component-inventory.json").read_text(encoding="utf-8")
        )
        cls.c02 = json.loads(
            (PLAN_ROOT / "briefs" / "skill-brief-C02.json").read_text(encoding="utf-8")
        )
        cls.c08 = json.loads(
            (PLAN_ROOT / "briefs" / "command-brief-C08.json").read_text(encoding="utf-8")
        )

    def _component(self, cid):
        for comp in self.inventory["components"]:
            if comp["id"] == cid:
                return comp
        self.fail(f"component {cid} が inventory に無い")

    def test_AC_C08_2_delegate_exists_as_skill(self):
        c02 = self._component("C02")
        self.assertEqual("skill", c02["component_kind"])
        self.assertEqual(contract_lib.DELEGATE_SKILL, c02["name"])

    def test_AC_C08_2_delegation_chain_includes_c20(self):
        """委譲チェーンに extract-handout-config.py (C20) が含まれる。"""
        self.assertIn("extract-handout-config.py", self.c02["deterministic_checks"])
        c20 = self._component("C20")
        self.assertEqual("extract-handout-config.py", c20["name"])

    def test_AC_C08_2_checker_constants_match_brief(self):
        """チェッカが持つ委譲チェーンの定数が C02 brief と一致している。"""
        self.assertEqual(
            list(contract_lib.DELEGATED_SCRIPTS),
            list(self.c02["deterministic_checks"]),
        )
        self.assertEqual(
            list(contract_lib.DELEGATED_RESPONSIBILITIES),
            [r["id"] for r in self.c02["responsibilities"]],
        )

    def test_AC_C08_1_checker_constants_match_inventory(self):
        c08 = self._component("C08")
        self.assertEqual(contract_lib.COMMAND_NAME, c08["name"])
        self.assertEqual(contract_lib.ARGUMENT_HINT, c08["argument-hint"])
        self.assertEqual(list(contract_lib.REQUIRED_TOOLS), list(c08["allowed-tools"]))
        self.assertIs(False, c08["disable-model-invocation"])
        self.assertEqual(contract_lib.BUILD_TARGET, c08["build_target"])

    def test_AC_C08_4_generation_belongs_to_c07(self):
        """生成の責務は C07 にあり、C08 は案内に留まる (brief boundary)。"""
        c07 = self._component("C07")
        self.assertEqual("handout-build", c07["name"])
        self.assertIn("/handout-build", self.c08["behavior"][7])
        self.assertIn("C07 の責務", self.c08["behavior"][7])

    def test_AC_C08_4_verification_belongs_to_c09(self):
        c09 = self._component("C09")
        self.assertEqual("handout-verify", c09["name"])
        self.assertNotIn("C09", self.c08["boundary"])


if __name__ == "__main__":
    unittest.main()

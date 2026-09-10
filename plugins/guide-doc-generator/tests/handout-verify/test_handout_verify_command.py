"""C09 handout-verify の受入テスト (実装前は赤で固定する)。

対象 build_target: plugins/guide-doc-generator/commands/handout-verify.md

slash-command component は実行そのものを機械検査できないため、command 定義の
宣言的契約 (frontmatter / 参照 script の実在と argv / 集約規則の宣言 /
引数の既定値と上書き規則 / 縮退時の挙動 / 報告の形) を検査する。判定器は
contract_lib.check_command で、その判定力は test_contract_checker.py が
受入例・非受入例で固定している。

契約 id と出典の対応表は同ディレクトリの README.md を参照。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aggregation_spec as spec  # noqa: E402
import contract_lib  # noqa: E402

PLUGIN_ROOT = contract_lib.plugin_root()
COMMAND_MD = contract_lib.build_target()


class HandoutVerifyCommandContractTest(unittest.TestCase):
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
    def test_AC_C09_0_build_target_exists(self):
        """build_target に command 定義が実在する (task-spec acceptance_criterion)。"""
        self.assertTrue(COMMAND_MD.is_file(), f"未実装: {COMMAND_MD}")

    def test_AC_C09_1_frontmatter_matches_inventory(self):
        """name / description / argument-hint / allowed-tools / disable-model-invocation。

        allowed-tools に Skill と Write が含まれないことを含む (AC-C09-1)。
        """
        self.assertContract("AC-C09-1")

    # --- 委譲先 script ----------------------------------------------------
    def test_AC_C09_2_delegated_scripts_exist_with_matching_argv(self):
        """C16 / C17 / C18 / C22 の script 4 本が実在し argv の形が一致する。"""
        self.assertContract("AC-C09-2")

    # --- 縮退 -------------------------------------------------------------
    def test_AC_C09_3_config_missing_degrades_to_not_run(self):
        """--config 未指定 / 未正規化で language・narrative が not-run、全体 incomplete。"""
        self.assertContract("AC-C09-3")

    def test_AC_C09_4_no_fail_fast(self):
        """1 ゲートが落ちても後続を止めず、全ゲートを走らせて全体 fail にする。"""
        self.assertContract("AC-C09-4")

    def test_AC_C09_5_only_run_is_partial(self):
        """--only は成功時でも partial。除外は not-run (excluded-by-only)。未知 gate_id は停止。"""
        self.assertContract("AC-C09-5")

    def test_AC_C09_7_entry_stop_is_not_pass(self):
        """html-path 不在 / ディレクトリ指定で 1 ゲートも実行せず停止し、pass を返さない。"""
        self.assertContract("AC-C09-7")

    def test_AC_C09_9_script_absent_is_not_run(self):
        """script 不在は not-run (script-absent) で、解決を試みたパスを提示する。"""
        self.assertContract("AC-C09-9")

    # --- 引数 -------------------------------------------------------------
    def test_AC_C09_11_argument_defaults_and_overrides(self):
        """引数 5 件の既定値と上書き規則が宣言されている。"""
        self.assertContract("AC-C09-11")

    # --- 境界 -------------------------------------------------------------
    def test_AC_C09_6_read_only_boundary(self):
        """生成 (C07) / 逆抽出 (C08) / 正規化 (C12) を行わない read-only 集約入口。"""
        self.assertContract("AC-C09-6")

    # --- 報告 -------------------------------------------------------------
    def test_AC_C09_10_reports_all_four_gates(self):
        """4 ゲート全部を行として出し、not-run を表から省かない。集約サマリを出す。"""
        self.assertContract("AC-C09-10")

    # --- 集約規則 (CR-GATE-AGG) -------------------------------------------
    def test_AC_C09_AGG_1_single_source_of_truth(self):
        """集約規則の単一正本がこの command であり、C01 経路と同一 verdict になる。"""
        self.assertContract("AC-C09-AGG-1")

    def test_AC_C09_AGG_2_machine_readable_verdict_table(self):
        """CR-GATE-AGG ブロックが 512 通りすべてで正解表と一致する。"""
        self.assertContract("AC-C09-AGG-2")

    def test_AC_C09_AGG_3_states_reasons_and_exit_codes_declared(self):
        """4 状態 / 4 verdict / 4 つの not-run 理由 / exit 0-1-2 の写像が宣言される。"""
        self.assertContract("AC-C09-AGG-3")

    def test_AC_C09_AGG_4_not_run_is_never_folded_into_pass(self):
        """not-run を pass 側へ畳む記述が無く、畳まない旨が明示される。"""
        self.assertContract("AC-C09-AGG-4")

    # --- 総合 -------------------------------------------------------------
    def test_no_contract_violation_remains(self):
        """契約違反が 1 件も残っていない。"""
        self.assertEqual([], [(x.contract_id, x.message) for x in self.violations])


class BuildTargetLayoutTest(unittest.TestCase):
    """build_target の配置と委譲先 script の実在。"""

    def test_commands_directory_exists(self):
        self.assertTrue(
            (PLUGIN_ROOT / "commands").is_dir(),
            f"commands/ が未作成: {PLUGIN_ROOT / 'commands'}",
        )

    def test_all_four_gate_scripts_exist(self):
        missing = [
            name
            for name in spec.GATE_SCRIPTS.values()
            if not (PLUGIN_ROOT / "scripts" / name).is_file()
        ]
        self.assertEqual(
            [],
            missing,
            "C09 が起動する 4 ゲートの script が未実装 (script 不在は not-run であり pass ではない)",
        )

    def test_config_validator_script_exists(self):
        """未正規化 config の検出に使う validate-handout-config.py (C12) が実在する。"""
        self.assertTrue(
            (PLUGIN_ROOT / "scripts" / "validate-handout-config.py").is_file(),
            "validate-handout-config.py が無いと config-not-normalized を判定できない",
        )


class ConsumerParityTest(unittest.TestCase):
    """AC-C09-AGG-1: C01 R4-verify が自前集約していないこと (invariant の相手側)。"""

    SKILL_MD = PLUGIN_ROOT / "skills" / "run-handout-build" / "SKILL.md"

    def test_c01_delegates_aggregation_to_c09(self):
        if not self.SKILL_MD.is_file():
            self.fail(f"AC-C09-AGG-1 未達: C01 SKILL.md が未実装 ({self.SKILL_MD})")
        body = self.SKILL_MD.read_text(encoding="utf-8")
        self.assertIn(
            "/handout-verify",
            body,
            "C01 R4-verify は C09 を起動してその集約結果を受け取る (P03 Y-07)",
        )
        self.assertIn(
            contract_lib.CANONICAL_ID,
            body,
            "C01 側に集約規則の正本 CR-GATE-AGG への参照が無い",
        )


if __name__ == "__main__":
    unittest.main()

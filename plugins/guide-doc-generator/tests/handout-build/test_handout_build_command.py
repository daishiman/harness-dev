"""C07 handout-build の受入テスト (実装前は赤で固定する)。

対象 build_target: plugins/guide-doc-generator/commands/handout-build.md

slash-command component は実行そのものを機械検査できないため、command 定義の
宣言的契約 (frontmatter / 引数表の既定値と上書き規則 / 経路判定 / 委譲先の宣言 /
矛盾停止条件 / 縮退時の挙動 / 報告の形 / 薄い入口であることの宣言) を検査する。
判定器は contract_lib.check_command で、その判定力は test_contract_checker.py が
受入例・非受入例で固定している。

契約 id と出典の対応表は同ディレクトリの README.md を参照。
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

PLUGIN_ROOT = contract_lib.plugin_root()
COMMAND_MD = contract_lib.build_target()
REPO_ROOT = PLUGIN_ROOT.parents[1]
PLAN_DIR = REPO_ROOT / "plugin-plans" / "guide-doc-generator"
BRIEF = PLAN_DIR / "briefs" / "command-brief-C07.json"
INVENTORY = PLAN_DIR / "component-inventory.json"


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _inventory_component(cid):
    data = _load_json(INVENTORY)
    components = data["components"] if isinstance(data, dict) else data
    for item in components:
        if item.get("id") == cid:
            return item
    return None


class HandoutBuildCommandContractTest(unittest.TestCase):
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
    def test_AC_C07_0_build_target_exists(self):
        """build_target に command 定義が実在する (task-spec acceptance_criterion)。"""
        self.assertTrue(COMMAND_MD.is_file(), f"未実装: {COMMAND_MD}")

    def test_AC_C07_1_frontmatter_matches_inventory(self):
        """name / description / argument-hint / allowed-tools / disable-model-invocation。

        allowed-tools は Read / Write / Bash / Skill と過不足なく一致する
        (allowed_tools_rationale: これ以上は不要、これ未満では非対話経路が成立しない)。
        """
        self.assertContract("AC-C07-1")

    # --- 引数 -------------------------------------------------------------
    def test_AC_C07_ARGS_defaults_and_overrides(self):
        """6 引数それぞれの既定値と上書き規則が機械可読な形で宣言されている。"""
        self.assertContract("AC-C07-ARGS")

    def test_AC_C07_2_doc_type_vocabulary_not_hardcoded(self):
        """用途種別の語彙が command 定義に列挙されていない (語彙正本は C23 のみ)。"""
        self.assertContract("AC-C07-2")

    def test_AC_C07_3_theme_three_points(self):
        """--theme の 3 点: 構成データ未指定時のみ有効 / 書き戻し / 再現の単位。"""
        self.assertContract("AC-C07-3")

    def test_AC_C07_DATE_normalization_is_delegated(self):
        """--date は正規化への入力に留まり、command は書式判定も現在日取得もしない。"""
        self.assertContract("AC-C07-DATE")

    def test_AC_C07_OUTDIR_parent_only(self):
        """--out-dir は親ディレクトリだけを上書きし、命名規則は C19 が導出する。"""
        self.assertContract("AC-C07-OUTDIR")

    def test_AC_C07_CONFIG_is_stronger_than_cli(self):
        """--config は存在と JSON 可読性だけを確認し、構成データが CLI より強い正本。"""
        self.assertContract("AC-C07-CONFIG")

    # --- 委譲 -------------------------------------------------------------
    def test_AC_C07_4_delegates_to_run_handout_build(self):
        """brief delegation_form どおりに C01 skill へ委譲し、委譲先が実在する。"""
        self.assertContract("AC-C07-4")

    # --- 経路 -------------------------------------------------------------
    def test_AC_C07_5_non_interactive_route_exists(self):
        """--config のみの起動でヒアリングが始まらない非対話経路が明示されている。"""
        self.assertContract("AC-C07-5")

    # --- 境界 -------------------------------------------------------------
    def test_AC_C07_6_thin_entry_boundary(self):
        """command 自身がロジックを持たない (判断も加工もしない薄い入口)。"""
        self.assertContract("AC-C07-6")

    # --- behavior の停止条件 ----------------------------------------------
    def test_AC_C07_B1_unknown_flag_stops(self):
        """未知フラグを推測解釈せず停止する。"""
        self.assertContract("AC-C07-B1")

    def test_AC_C07_B2_topic_and_config_conflict(self):
        """題材と --config の同時指定は矛盾として停止する。"""
        self.assertContract("AC-C07-B2")

    # --- failure_modes ----------------------------------------------------
    def test_AC_C07_FM_1_no_args_starts_elicitation(self):
        """題材も --config も無い起動はエラーにせずヒアリングを開始する。"""
        self.assertContract("AC-C07-FM-1")

    def test_AC_C07_FM_2_missing_config_stops_before_delegation(self):
        """--config が読めないとき委譲先を起動せず停止し、解決したパスを示す。"""
        self.assertContract("AC-C07-FM-2")

    def test_AC_C07_FM_3_unknown_doc_type_stops(self):
        """語彙外 --doc-type は C23 の exit≠0 を受けて停止し候補提示を案内する。"""
        self.assertContract("AC-C07-FM-3")

    def test_AC_C07_FM_4_conflict_is_never_silent(self):
        """構成データとの衝突はキーパスと両方の値を示して停止する (黙って処理しない)。"""
        self.assertContract("AC-C07-FM-4")

    def test_AC_C07_FM_5_gate_fail_is_not_success(self):
        """ゲート FAIL 時に成功と読める要約を書かない。"""
        self.assertContract("AC-C07-FM-5")

    def test_AC_C07_FM_6_optional_dependency_absence_is_fail_soft(self):
        """slide-report-generator 不在は skip 理由つき報告で他ステップを完走させる。"""
        self.assertContract("AC-C07-FM-6")

    # --- 報告 -------------------------------------------------------------
    def test_AC_C07_REPORT_five_elements(self):
        """生成レポートの 5 要素を加工せずそのまま提示する。"""
        self.assertContract("AC-C07-REPORT")

    def test_AC_C07_THEME_NOTICE_writeback_is_announced(self):
        """--theme 採用時に再指定不要である旨を伝える。"""
        self.assertContract("AC-C07-THEME-NOTICE")

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
        """AC-C07-4: 委譲先 run-handout-build (C01) が build_target に実在する。"""
        skill_md = PLUGIN_ROOT / "skills" / "run-handout-build" / "SKILL.md"
        self.assertTrue(skill_md.is_file(), f"委譲先 skill が未実装: {skill_md}")

    def test_referenced_scripts_exist(self):
        """command 本文が名指しする単一正本 script が実在する。"""
        missing = [
            name
            for name in (
                contract_lib.PRESET_RESOLVER,
                contract_lib.CONFIG_VALIDATOR,
                contract_lib.OUTPUT_ROUTER,
                contract_lib.THEME_WRITEBACK_WRITER,
            )
            if not (PLUGIN_ROOT / "scripts" / name).is_file()
        ]
        self.assertEqual([], missing, "command が名指しする正本 script が未実装")


class ConsumerParityTest(unittest.TestCase):
    """AC-C07-5 の相手側: C01 が非対話経路を塞いでいないこと。"""

    SKILL_MD = PLUGIN_ROOT / "skills" / "run-handout-build" / "SKILL.md"

    def test_c01_accepts_non_interactive_entry(self):
        if not self.SKILL_MD.is_file():
            self.fail(f"AC-C07-5 未達: C01 SKILL.md が未実装 ({self.SKILL_MD})")
        body = self.SKILL_MD.read_text(encoding="utf-8")
        self.assertIn(
            "非対話",
            body,
            "C01 側にも非対話経路の記述が要る (対話は既定経路であって唯一経路ではない)",
        )


class SourceOfTruthTest(unittest.TestCase):
    """チェッカの定数が brief / inventory 由来であることを固定する。

    P05 の実装側が contract_lib の期待値を書き換えて判定を緩められないよう、
    定数の出所をここで照合する。plan 側の成果物は既に存在するのでこのクラスは
    実装前でも緑になる。
    """

    def test_description_comes_from_inventory(self):
        self.assertEqual(_inventory_component("C07")["description"], contract_lib.DESCRIPTION)

    def test_allowed_tools_come_from_inventory(self):
        self.assertEqual(
            _inventory_component("C07")["allowed-tools"], list(contract_lib.REQUIRED_TOOLS)
        )

    def test_build_target_comes_from_inventory(self):
        self.assertEqual(_inventory_component("C07")["build_target"], contract_lib.BUILD_TARGET)

    def test_argument_names_come_from_brief(self):
        brief = _load_json(BRIEF)
        self.assertEqual(
            [a["name"] for a in brief["arguments"]], list(contract_lib.ARGUMENT_NAMES)
        )

    def test_argument_hint_tokens_come_from_brief(self):
        hint = _load_json(BRIEF)["argument_hint"]
        for token in contract_lib.ARGUMENT_HINT_TOKENS:
            self.assertIn(token, hint)

    def test_delegation_form_comes_from_brief(self):
        self.assertEqual(_load_json(BRIEF)["delegation_form"], contract_lib.DELEGATION_FORM)

    def test_delegate_build_target_comes_from_inventory(self):
        """AC-C07-4 前半: run-handout-build が skill として実在し build_target が一致。"""
        c01 = _inventory_component("C01")
        self.assertEqual("skill", c01["component_kind"])
        self.assertEqual("run-handout-build", c01["name"])
        self.assertEqual(contract_lib.DELEGATE_BUILD_TARGET, c01["build_target"])

    def test_doc_type_vocabulary_comes_from_c23(self):
        purpose = _inventory_component("C23")["purpose"]
        for slug in contract_lib.DOC_TYPE_VOCABULARY:
            self.assertIn(slug, purpose)

    def test_failure_mode_count_matches_brief(self):
        """failure_modes を 1 つでも落として実装しないよう件数を固定する。"""
        self.assertEqual(6, len(_load_json(BRIEF)["failure_modes"]))


if __name__ == "__main__":
    unittest.main()

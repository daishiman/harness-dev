"""C09 集約規則 CR-GATE-AGG の受入テスト。

2 層で構成する。

  1. TestOracle* — 正解表 (aggregation_spec.aggregate) 自身の性質を固定する。
     実装に依存しないので実装前でも緑。ここが「答え」であり、P05 の実装が
     これを都合よく書き換えられないよう先に確定させる。
  2. TestDeclared* — 実装 (commands/handout-verify.md) が宣言する verdict_table を
     4^4 x 2 = 512 通りの入力すべてで正解表と突き合わせる。実装が無い間は赤。

契約 id と出典の対応表は同ディレクトリの README.md を参照。
"""

import sys
import unittest
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aggregation_spec as spec  # noqa: E402
import contract_lib  # noqa: E402

PLUGIN_ROOT = contract_lib.plugin_root()
COMMAND_MD = contract_lib.build_target()


# ==========================================================================
# 1. 正解表そのものの性質 (実装非依存 / 実装前も緑)
# ==========================================================================


class TestOracleShape(unittest.TestCase):
    """集約対象と語彙が brief と一致すること。"""

    def test_gate_faces_are_exactly_four(self):
        """集約対象は C16 / C17 / C18 / C22 の 4 面ちょうど (P03 Y-07)。"""
        self.assertEqual(
            {"C16", "C17", "C18", "C22"},
            set(spec.GATE_FACES.values()),
        )
        self.assertEqual(4, len(spec.GATE_IDS))

    def test_four_gate_states(self):
        self.assertEqual(("pass", "fail", "error", "not-run"), spec.GATE_STATES)

    def test_four_verdicts(self):
        self.assertEqual(("pass", "fail", "incomplete", "partial"), spec.VERDICTS)

    def test_not_run_reasons_are_exactly_four(self):
        self.assertEqual(
            {"config-missing", "config-not-normalized", "excluded-by-only", "script-absent"},
            set(spec.NOT_RUN_REASONS),
        )

    def test_exit_code_mapping(self):
        self.assertEqual({0: "pass", 1: "fail", 2: "error"}, spec.EXIT_CODE_TO_STATE)


class TestOracleAggregation(unittest.TestCase):
    """正解表の網羅的な性質。not-run が pass へ畳まれないことが要点。"""

    def test_all_pass_is_pass(self):
        states = {g: "pass" for g in spec.GATE_IDS}
        self.assertEqual("pass", spec.aggregate(states, only_used=False))

    def test_all_pass_with_only_is_partial(self):
        states = {g: "pass" for g in spec.GATE_IDS}
        self.assertEqual("partial", spec.aggregate(states, only_used=True))

    def test_any_fail_makes_overall_fail(self):
        for combo in product(spec.GATE_STATES, repeat=4):
            if "fail" not in combo:
                continue
            states = dict(zip(spec.GATE_IDS, combo))
            for only_used in (False, True):
                self.assertEqual("fail", spec.aggregate(states, only_used), combo)

    def test_any_error_makes_overall_fail(self):
        for combo in product(spec.GATE_STATES, repeat=4):
            if "error" not in combo or "fail" in combo:
                continue
            states = dict(zip(spec.GATE_IDS, combo))
            for only_used in (False, True):
                self.assertEqual("fail", spec.aggregate(states, only_used), combo)

    def test_not_run_never_becomes_pass(self):
        """not-run を 1 つでも含む組み合わせが pass になる経路は存在しない。"""
        for states, only_used in spec.all_combinations():
            if "not-run" not in states.values():
                continue
            self.assertNotEqual(
                "pass",
                spec.aggregate(states, only_used),
                f"not-run を含むのに pass になった: {states} only={only_used}",
            )

    def test_not_run_without_failure_is_incomplete(self):
        """fail も error も無く not-run がある全実行は incomplete。"""
        for combo in product(("pass", "not-run"), repeat=4):
            if "not-run" not in combo:
                continue
            states = dict(zip(spec.GATE_IDS, combo))
            self.assertEqual("incomplete", spec.aggregate(states, only_used=False), combo)

    def test_only_run_is_partial_when_nothing_failed(self):
        for combo in product(("pass", "not-run"), repeat=4):
            states = dict(zip(spec.GATE_IDS, combo))
            self.assertEqual("partial", spec.aggregate(states, only_used=True), combo)

    def test_pass_requires_all_four_faces_passing(self):
        """pass になる組み合わせは (全 pass, --only 未使用) のちょうど 1 通り。"""
        passing = [
            (states, only_used)
            for states, only_used in spec.all_combinations()
            if spec.aggregate(states, only_used) == "pass"
        ]
        self.assertEqual(1, len(passing), passing)
        states, only_used = passing[0]
        self.assertFalse(only_used)
        self.assertEqual({"pass"}, set(states.values()))

    def test_every_combination_has_a_verdict(self):
        count = 0
        for states, only_used in spec.all_combinations():
            self.assertIn(spec.aggregate(states, only_used), spec.VERDICTS)
            count += 1
        self.assertEqual(512, count)

    def test_rejects_wrong_gate_set(self):
        with self.assertRaises(ValueError):
            spec.aggregate({"selfcontained": "pass"}, only_used=False)

    def test_rejects_unknown_state(self):
        states = {g: "pass" for g in spec.GATE_IDS}
        states["language"] = "skipped"
        with self.assertRaises(ValueError):
            spec.aggregate(states, only_used=False)


class TestReferenceTable(unittest.TestCase):
    """参考 verdict_table が正解表と 512 通りで一致すること (評価器の健全性)。"""

    def test_reference_table_matches_oracle(self):
        for states, only_used in spec.all_combinations():
            self.assertEqual(
                spec.aggregate(states, only_used),
                spec.resolve(spec.REFERENCE_VERDICT_TABLE, states, only_used),
                f"{states} only={only_used}",
            )

    def test_resolver_rejects_unknown_verdict(self):
        with self.assertRaises(spec.TableError):
            spec.resolve(
                [{"when": {}, "verdict": "blocked"}],
                {g: "pass" for g in spec.GATE_IDS},
                False,
            )

    def test_resolver_rejects_incomplete_table(self):
        with self.assertRaises(spec.TableError):
            spec.resolve(
                [{"when": {"any_state": ["fail"]}, "verdict": "fail"}],
                {g: "pass" for g in spec.GATE_IDS},
                False,
            )


# ==========================================================================
# 2. 実装が宣言する verdict_table (実装前は赤)
# ==========================================================================


def _declared_table():
    """実装が宣言する verdict_table を返す。取得できなければ理由文字列を返す。"""
    if not COMMAND_MD.is_file():
        return None, f"command 定義が未実装: {COMMAND_MD}"
    text = COMMAND_MD.read_text(encoding="utf-8")
    _, body = contract_lib.split_frontmatter(text)
    block, errors = contract_lib.extract_aggregation_block(body)
    if block is None:
        return None, f'id="{contract_lib.CANONICAL_ID}" の集約規則ブロックが無い ({"; ".join(errors) or "fenced json 未宣言"})'
    table = block.get("verdict_table")
    if table is None:
        return None, "宣言ブロックに verdict_table が無い"
    return table, None


class DeclaredAggregationTest(unittest.TestCase):
    """AC-C09-AGG-2: 実装の集約規則が 512 通りすべてで正解表と一致する。"""

    def table(self):
        table, reason = _declared_table()
        if table is None:
            self.fail(f"AC-C09-AGG-2 未達: {reason}")
        return table

    def assertVerdict(self, states, only_used, expected):
        got = spec.resolve(self.table(), states, only_used)
        self.assertEqual(expected, got, f"{states} only={only_used}")

    # --- 状態ごとの網羅 ---------------------------------------------------

    def test_all_pass_is_pass(self):
        """4 面すべて pass かつ全実行のときだけ pass。"""
        self.assertVerdict({g: "pass" for g in spec.GATE_IDS}, False, "pass")

    def test_every_combination_containing_fail_is_fail(self):
        """fail を含む 175 通り x 2 がすべて全体 fail。"""
        table = self.table()
        for combo in product(spec.GATE_STATES, repeat=4):
            if "fail" not in combo:
                continue
            states = dict(zip(spec.GATE_IDS, combo))
            for only_used in (False, True):
                self.assertEqual(
                    "fail", spec.resolve(table, states, only_used), f"{states} only={only_used}"
                )

    def test_every_combination_containing_error_is_fail(self):
        """error (exit 2 = 検査器の異常) は fail 側へ倒す (fail-closed)。"""
        table = self.table()
        for combo in product(spec.GATE_STATES, repeat=4):
            if "error" not in combo:
                continue
            states = dict(zip(spec.GATE_IDS, combo))
            for only_used in (False, True):
                self.assertEqual(
                    "fail", spec.resolve(table, states, only_used), f"{states} only={only_used}"
                )

    def test_not_run_is_never_folded_into_pass(self):
        """not-run を含むどの組み合わせも pass にならない (CR-GATE-AGG の要点)。"""
        table = self.table()
        for states, only_used in spec.all_combinations():
            if "not-run" not in states.values():
                continue
            self.assertNotEqual(
                "pass",
                spec.resolve(table, states, only_used),
                f"未実行を通ったことにしている: {states} only={only_used}",
            )

    def test_not_run_without_failure_is_incomplete(self):
        """fail も error も無く not-run がある全実行は incomplete。"""
        table = self.table()
        for combo in product(("pass", "not-run"), repeat=4):
            if "not-run" not in combo:
                continue
            states = dict(zip(spec.GATE_IDS, combo))
            self.assertEqual(
                "incomplete", spec.resolve(table, states, False), f"{states}"
            )

    def test_all_four_not_run_is_not_pass(self):
        """1 ゲートも走らなかった実行を pass として返さない。"""
        states = {g: "not-run" for g in spec.GATE_IDS}
        self.assertVerdict(states, False, "incomplete")

    def test_only_run_success_is_partial(self):
        """--only を使った実行は成功時でも pass ではなく partial。"""
        table = self.table()
        for combo in product(("pass", "not-run"), repeat=4):
            states = dict(zip(spec.GATE_IDS, combo))
            self.assertEqual("partial", spec.resolve(table, states, True), f"{states}")

    def test_exhaustive_512_combinations_match_oracle(self):
        """4^4 x 2 = 512 通りを 1 件も残さず正解表と突き合わせる。"""
        table = self.table()
        mismatches = []
        for states, only_used in spec.all_combinations():
            want = spec.aggregate(states, only_used)
            got = spec.resolve(table, states, only_used)
            if got != want:
                mismatches.append((dict(states), only_used, want, got))
        self.assertEqual([], mismatches[:10], f"食い違い {len(mismatches)} 件")

    # --- brief の受入検査に対応するシナリオ --------------------------------

    def test_AC_C09_3_config_missing_scenario(self):
        """--config 未指定: language / narrative が not-run、全体 incomplete。"""
        self.assertVerdict(
            {
                "selfcontained": "pass",
                "a11y-print": "pass",
                "language": "not-run",
                "narrative": "not-run",
            },
            False,
            "incomplete",
        )

    def test_AC_C09_4_one_gate_fail_scenario(self):
        """1 ゲートだけ fail、残り 3 面は実行済み pass でも全体 fail。"""
        self.assertVerdict(
            {
                "selfcontained": "pass",
                "a11y-print": "fail",
                "language": "pass",
                "narrative": "pass",
            },
            False,
            "fail",
        )

    def test_AC_C09_5_only_selfcontained_scenario(self):
        """--only selfcontained: 成功しても partial、残り 3 面は not-run。"""
        self.assertVerdict(
            {
                "selfcontained": "pass",
                "a11y-print": "not-run",
                "language": "not-run",
                "narrative": "not-run",
            },
            True,
            "partial",
        )

    def test_script_absent_scenario_is_not_pass(self):
        """script 不在による not-run を含む実行は pass にならない。"""
        self.assertVerdict(
            {
                "selfcontained": "not-run",
                "a11y-print": "pass",
                "language": "pass",
                "narrative": "pass",
            },
            False,
            "incomplete",
        )

    def test_error_plus_not_run_is_fail(self):
        """error と not-run が同居する場合は fail が優先する。"""
        self.assertVerdict(
            {
                "selfcontained": "error",
                "a11y-print": "pass",
                "language": "not-run",
                "narrative": "not-run",
            },
            False,
            "fail",
        )


if __name__ == "__main__":
    unittest.main()

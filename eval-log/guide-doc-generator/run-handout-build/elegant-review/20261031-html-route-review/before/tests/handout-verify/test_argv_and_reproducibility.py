"""C09 /handout-verify の 2 面 — 実 script の argv 契約と再現性。

既存の test_handout_verify_command.py / test_contract_checker.py /
test_aggregation_rule.py は「違反系入力で落ちる」面と「argv と exit code の宣言」
面を担っていたが、次の 2 点はどのファイルも担っていなかったため本ファイルで足す。

面 A の補強: argv 契約の突合先
  従来の AC-C09-2 は「command 定義の本文に GATE_ARGV のフラグが現れるか」を見て
  いたが、GATE_ARGV 自体がテスト側の表であったため、表と本文が揃っていれば実
  script が受け取らないフラグでも緑になった。本ファイルは同じフラグを実 script
  の argparse と突合し、「宣言はあるが受け口が無い」型の欠陥を落とす。
  (GATE_ARGV は本 cycle で command-brief-C09.json#gates[] からの実測へ移したため、
   突合は brief ↔ 実 script の 2 者間になる。)

面 B: 再現性
  build_target が Markdown である本 component_kind では、実行の再現性ではなく
  次の 2 つが対応物になる。
    B-1 判定器 (contract_lib.check_command) と集約オラクル (aggregation_spec) が
        同じ入力に対し何度実行しても同一の結果を返すこと。判定器が非決定論だと
        赤緑がその日の運で決まる。
    B-2 実装が宣言する verdict_table が、全組み合わせ (4 状態 ^ 4 ゲート × --only
        の有無) に対してオラクルと一致し、かつ評価順に依存しないこと。
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aggregation_spec as spec  # noqa: E402
import contract_lib  # noqa: E402

PLUGIN_ROOT = contract_lib.plugin_root()
COMMAND_MD = contract_lib.build_target()
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
TESTS_DIR = Path(__file__).resolve().parent

_ADD_ARGUMENT = re.compile(r"add_argument\(\s*[\"'](--[a-z][a-z0-9-]*)[\"']")


def _argparse_options(script_path: Path):
    return set(_ADD_ARGUMENT.findall(script_path.read_text(encoding="utf-8")))


class GateArgvMatchesRealScriptsTest(unittest.TestCase):
    """面 A: 宣言された argv が実 script の argparse に実在する。"""

    def test_every_declared_flag_exists_in_the_gate_script(self):
        for gate_id in spec.GATE_IDS:
            script = SCRIPTS_DIR / spec.GATE_SCRIPTS[gate_id]
            with self.subTest(gate=gate_id):
                self.assertTrue(script.is_file(), f"ゲート script が実在しない: {script}")
                options = _argparse_options(script)
                for flag in spec.GATE_ARGV[gate_id]:
                    self.assertIn(
                        flag,
                        options,
                        f"{gate_id} へ渡す {flag} が {script.name} の argparse に無い "
                        f"(実在するのは {sorted(options)})",
                    )

    def test_json_report_is_accepted_by_every_gate_script(self):
        """集約は --json-report の回収が前提なので、全ゲートが受け口を持つこと。"""
        for gate_id in spec.GATE_IDS:
            script = SCRIPTS_DIR / spec.GATE_SCRIPTS[gate_id]
            with self.subTest(gate=gate_id):
                self.assertIn(
                    "--json-report",
                    _argparse_options(script),
                    f"{script.name} が --json-report を受け取れない (集約の入力が取れない)",
                )

    def test_config_requirement_matches_the_script_that_needs_it(self):
        """config 必須ゲートだけが --config を持つ (縮退規則の前提が実装と揃っている)。"""
        for gate_id in spec.GATE_IDS:
            options = _argparse_options(SCRIPTS_DIR / spec.GATE_SCRIPTS[gate_id])
            with self.subTest(gate=gate_id):
                self.assertEqual(
                    gate_id in spec.GATES_REQUIRING_CONFIG,
                    "--config" in options,
                    f"{gate_id}: config 必須の宣言と実 script の --config 受け口が食い違う",
                )


class CheckerReproducibilityTest(unittest.TestCase):
    """面 B-1: 判定器の再現性。"""

    def test_check_command_returns_identical_violations_on_repeated_runs(self):
        first = contract_lib.check_command(PLUGIN_ROOT)
        second = contract_lib.check_command(PLUGIN_ROOT)
        self.assertEqual(
            list(first), list(second), "同一入力に対する判定が 2 回の実行で一致しない"
        )

    def test_check_command_is_reproducible_in_a_fresh_interpreter(self):
        code = (
            "import sys, json;"
            f"sys.path.insert(0, {str(TESTS_DIR)!r});"
            "import contract_lib as c;"
            "print(json.dumps([list(v) for v in c.check_command(c.plugin_root())], ensure_ascii=False))"
        )
        runs = []
        for _ in range(2):
            proc = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True, check=False
            )
            self.assertEqual(0, proc.returncode, f"判定器の起動に失敗した: {proc.stderr}")
            runs.append(proc.stdout)
        self.assertEqual(runs[0], runs[1], "別プロセス 2 回の判定結果が一致しない")


class AggregationReproducibilityTest(unittest.TestCase):
    """面 B-2: 集約結果の再現性と順序非依存性。"""

    def test_oracle_is_deterministic_over_all_combinations(self):
        first = [spec.aggregate(s, o) for s, o in spec.all_combinations()]
        second = [spec.aggregate(s, o) for s, o in spec.all_combinations()]
        self.assertEqual(first, second, "オラクルが同じ入力に対し異なる verdict を返した")
        self.assertEqual(
            len(spec.GATE_STATES) ** len(spec.GATE_IDS) * 2,
            len(first),
            "全組み合わせの列挙件数が状態数 ^ ゲート数 × --only の 2 値と合わない",
        )

    def test_aggregate_does_not_depend_on_gate_ordering(self):
        """states の dict 順を変えても verdict が変わらない (辞書順への依存を落とす)。"""
        for states, only_used in spec.all_combinations():
            reversed_states = {g: states[g] for g in reversed(spec.GATE_IDS)}
            with self.subTest(states=tuple(states.items()), only=only_used):
                self.assertEqual(
                    spec.aggregate(states, only_used),
                    spec.aggregate(reversed_states, only_used),
                    "ゲートの並び順で verdict が変わる",
                )

    def _declared_table(self):
        if not COMMAND_MD.is_file():
            self.fail(f"未達: command 定義が未実装 ({COMMAND_MD})")
        _, body = contract_lib.split_frontmatter(COMMAND_MD.read_text(encoding="utf-8"))
        block, errors = contract_lib.extract_aggregation_block(body)
        if block is None:
            self.fail(
                f'id="{contract_lib.CANONICAL_ID}" の集約規則ブロックが取れない: {errors}'
            )
        table = block.get("verdict_table")
        self.assertIsNotNone(table, "宣言ブロックに verdict_table が無い")
        return table

    def test_declared_table_extraction_is_reproducible(self):
        """同じファイルを 2 回読んで同じ表が取れ、評価結果もオラクルと一致する。

        抽出が本文の並びや正規表現の貪欲さに依存すると、無関係な文言の追加で表が
        変わり、集約検査が黙って別のものを測り始める。
        """
        first = self._declared_table()
        second = self._declared_table()
        self.assertEqual(first, second, "同じ本文から 2 回取り出した verdict_table が一致しない")
        for states, only_used in spec.all_combinations():
            with self.subTest(states=tuple(states.items()), only=only_used):
                self.assertEqual(
                    spec.aggregate(states, only_used),
                    spec.resolve(first, states, only_used),
                )


class UnimplementedBuildTargetSurrogateTest(unittest.TestCase):
    """実装を消さずに「未実装なら赤」を測る代理検査。

    acceptance_criterion の後半 (build_target が未実装の時点で失敗する) は実装が
    既に存在するため現物では再現できない。実装の削除は禁止されているので、空の
    ディレクトリを plugin root と見立てて判定器の挙動だけを固定する。これは代理
    であって現物での再現ではない。
    """

    def test_empty_plugin_root_yields_the_existence_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            violations = contract_lib.check_command(Path(tmp))
        self.assertEqual(
            ["AC-C09-1"],
            sorted({v.contract_id for v in violations}),
            "command 定義が無い plugin root を判定器が存在契約 1 件で落としていない",
        )


class NoLiteralCopyOfCanonTest(unittest.TestCase):
    """値域・件数のリテラルをテスト側へ写していないこと。"""

    def test_gate_roster_is_derived_from_the_brief(self):
        gates = spec.BRIEF["gates"]
        self.assertEqual([g["gate_id"] for g in gates], list(spec.GATE_IDS))
        self.assertEqual({g["gate_id"]: g["script"] for g in gates}, spec.GATE_SCRIPTS)
        self.assertEqual({g["gate_id"]: g["component"] for g in gates}, spec.GATE_FACES)

    def test_expectations_scale_with_the_gate_roster(self):
        """検査側の期待値がゲート本数の literal ではなく名簿から導かれていること。

        面が 1 つ増えたときに黙って古くならないことを、名簿由来の派生値
        (argv / config 必須面 / 全組み合わせ件数) が名簿と連動することで固定する。
        散文中の「4 面」という記述は説明であり期待値ではないため対象外。
        """
        self.assertEqual(set(spec.GATE_ARGV), set(spec.GATE_IDS))
        self.assertEqual(set(spec.GATE_SCRIPTS), set(spec.GATE_IDS))
        self.assertTrue(set(spec.GATES_REQUIRING_CONFIG) <= set(spec.GATE_IDS))
        self.assertEqual(
            len(spec.GATE_STATES) ** len(spec.GATE_IDS) * 2,
            sum(1 for _ in spec.all_combinations()),
        )
        self.assertEqual(
            str(len(spec.GATE_IDS)),
            contract_lib.ARGUMENT_DEFAULTS["--only"],
            "--only 未指定時の全実行本数がゲート名簿と連動していない",
        )


if __name__ == "__main__":
    unittest.main()

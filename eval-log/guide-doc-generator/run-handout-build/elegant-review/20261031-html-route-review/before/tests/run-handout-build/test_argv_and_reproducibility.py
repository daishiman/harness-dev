"""C01 run-handout-build の 2 面 — 委譲 argv / exit code 契約と再現性。

既存の test_run_handout_build_skill.py・test_contract_checker.py・
test_predicate_scope.py は「違反系入力で落ちる」面を担っていたが、以下の 2 面は
どのファイルも担っていなかったため本ファイルで足す。

面 A: 委譲 argv と exit code 契約
  build_target が Markdown (skill) であるため、script のように自身が argv を
  受けて exit code を返すわけではない。この component_kind における対応物を
  次のとおり定義して測る。
    A-1 SKILL.md が決定論 script の名前の隣に書いたフラグは、その script の
        argparse に実在しなければならない (存在しないフラグを指示する
        「宣言はあるが受け口が無い」型の欠陥を落とす)。
    A-2 exit code の意味づけ (0/1/2 → pass/fail/error) の正本は C09
        handout-verify の CR-GATE-AGG である。C01 はそれを自分で再定義しない。
    A-3 ゲート起動は /handout-verify への委譲宣言として存在する。

面 B: 再現性
  B-1 判定器 (contract_lib.check_skill) が同じ入力に対し何度実行しても同一の
      違反列を返す。判定器が非決定論だと、赤緑がその日の運で決まる。
  B-2 契約としての再現性 = OUT2 (同梱構成データからの 2 回生成でバイト一致)。
      R5-refine が生成済み HTML の直接編集を禁じ、決定論経路での作り直しを
      宣言していることが、OUT2 を壊さないための唯一の宣言点である。

面 C (退行ガード): 値域・件数リテラルの写し込み禁止
  C-1 goal_seek の max_loops など、正本がデータファイル側にある数値を
      テスト側へ焼き直していないこと (F-C06-04 で正本を C01 goal_seek 1 つに
      畳んだ経緯があるため、写すと正本が再び 2 つになる)。
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

SKILL_DIR = contract_lib.build_target_dir()
SKILL_MD = SKILL_DIR / "SKILL.md"
SCRIPTS_DIR = contract_lib.repo_root() / "plugins" / "guide-doc-generator" / "scripts"
TESTS_DIR = Path(__file__).resolve().parent

_FLAG = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")
_ADD_ARGUMENT = re.compile(r"add_argument\(\s*[\"'](--[a-z][a-z0-9-]*)[\"']")


def _skill_body():
    if not SKILL_MD.is_file():
        return None
    return SKILL_MD.read_text(encoding="utf-8")


def _argparse_options(script_path: Path):
    text = script_path.read_text(encoding="utf-8")
    return set(_ADD_ARGUMENT.findall(text))


class DelegationArgvContractTest(unittest.TestCase):
    """面 A: 委譲先 script の argv と exit code の契約。"""

    def setUp(self):
        body = _skill_body()
        if body is None:
            self.fail(f"未達: SKILL.md が未実装 ({SKILL_MD})")
        self.body = body
        self.lines = body.splitlines()

    def test_flags_written_next_to_a_script_exist_in_its_argparse(self):
        """SKILL.md が script 名の隣に書いたフラグは実 script の argparse に実在する。"""
        checked = 0
        for lineno, line in enumerate(self.lines, 1):
            for script in contract_lib.REQUIRED_SCRIPTS:
                if script not in line:
                    continue
                path = SCRIPTS_DIR / script
                if not path.is_file():
                    self.fail(f"SKILL.md:{lineno} が参照する {script} が実在しない: {path}")
                options = _argparse_options(path)
                for flag in sorted(set(_FLAG.findall(line))):
                    checked += 1
                    self.assertIn(
                        flag,
                        options,
                        f"SKILL.md:{lineno} が {script} に {flag} を渡しているが "
                        f"当該 script の argparse に無い (実在するのは {sorted(options)})",
                    )
        self.assertGreater(
            checked,
            0,
            "SKILL.md に script 名とフラグを同じ行で書いた箇所が 1 つも無い。"
            "委譲 argv が本文から読み取れない状態であり、本検査が空振りしている",
        )

    def test_exit_code_semantics_are_not_redefined_here(self):
        """exit code → 状態 の対応づけを C01 が自前で定義していない (正本は C09)。

        C09 handout-verify の CR-GATE-AGG が 0=pass / 1=fail / 2=error の唯一の
        正本。C01 が同じ対応表を持つと、片方だけ変わったときに検出できない。
        """
        offenders = []
        for lineno, line in enumerate(self.lines, 1):
            if not re.search(r"exit\s*[12]\b", line):
                continue
            if re.search(r"(fail|error|失敗|エラー|警告)", line):
                offenders.append(f"SKILL.md:{lineno}: {line.strip()}")
        self.assertEqual(
            [],
            offenders,
            "exit code の意味づけは C09 CR-GATE-AGG が正本であり C01 で再定義しない:\n"
            + "\n".join(offenders),
        )

    def test_gate_invocation_is_delegated_to_handout_verify(self):
        """ゲート起動が /handout-verify への委譲として宣言されている。"""
        self.assertIn(
            "/handout-verify",
            self.body,
            "検証ゲートの起動が /handout-verify (C09) への委譲として宣言されていない",
        )


class CheckerReproducibilityTest(unittest.TestCase):
    """面 B-1: 判定器そのものの再現性。"""

    def _targets(self):
        targets = [("build_target", SKILL_DIR)]
        accept = TESTS_DIR / "fixtures" / "accept" / "skills" / "run-handout-build"
        if accept.is_dir():
            targets.append(("accept fixture", accept))
        return targets

    def test_check_skill_returns_identical_violations_on_repeated_runs(self):
        for label, target in self._targets():
            with self.subTest(target=label):
                first = contract_lib.check_skill(target)
                second = contract_lib.check_skill(target)
                self.assertEqual(
                    list(first),
                    list(second),
                    f"{label} に対する判定が 2 回の実行で一致しない (順序も含めて同一であること)",
                )

    def test_check_skill_is_reproducible_in_a_fresh_interpreter(self):
        """別プロセスで読み直しても同じ違反列になる (import 順や辞書順への依存を落とす)。"""
        code = (
            "import sys, json;"
            f"sys.path.insert(0, {str(TESTS_DIR)!r});"
            "import contract_lib as c;"
            f"print(json.dumps([list(v) for v in c.check_skill(c.build_target_dir())], ensure_ascii=False))"
        )
        runs = []
        for _ in range(2):
            proc = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True, check=False
            )
            self.assertEqual(0, proc.returncode, f"判定器の起動に失敗した: {proc.stderr}")
            runs.append(proc.stdout)
        self.assertEqual(runs[0], runs[1], "別プロセス 2 回の判定結果が一致しない")


class Out2RegenerationInvariantTest(unittest.TestCase):
    """面 B-2: OUT2 (バイト一致再生成) を壊さないための宣言が本文にあること。"""

    def setUp(self):
        body = _skill_body()
        if body is None:
            self.fail(f"未達: SKILL.md が未実装 ({SKILL_MD})")
        self.body = body

    def test_out2_is_declared_as_an_outer_test_criterion(self):
        scope, verify_by = contract_lib.REQUIRED_CRITERIA["OUT2"]
        self.assertEqual(("outer", "test"), (scope, verify_by))
        self.assertIn("OUT2", self.body, "feedback_contract に OUT2 の宣言が無い")

    def test_refine_forbids_hand_editing_generated_html(self):
        """R5-refine が生成済み HTML の直接編集を禁じ、決定論経路での作り直しを宣言する。

        手編集を許すと同梱構成データから再生成した HTML と現物が食い違い、
        OUT2 のバイト一致が構造的に成立しなくなる。
        """
        self.assertIn("R5-refine", self.body, "R5-refine の宣言が SKILL.md に無い")
        hits = [
            line
            for line in self.body.splitlines()
            if re.search(r"直接編集せず|編集しない", line)
            and "決定論" in line
            and "作り直" in line
        ]
        self.assertTrue(
            hits,
            "生成済み HTML を直接編集せず決定論経路で作り直す、という宣言が本文に無い。"
            "手編集を許すと同梱構成データからの再生成と現物が食い違い OUT2 (バイト一致) "
            "が構造的に成立しなくなる",
        )
        self.assertTrue(
            any("OUT2" in line or "再現" in line for line in hits),
            "直接編集禁止の宣言が OUT2 (再現一致) を理由として結び付けていない。"
            "理由が切れていると、後から『少しだけ手で直す』例外が入ったときに"
            "何が壊れるのか読み取れない",
        )


class UnimplementedBuildTargetSurrogateTest(unittest.TestCase):
    """実装を消さずに「未実装なら赤」を測る代理検査。

    acceptance_criterion の後半 (build_target 未実装時に失敗する) は実装が既に
    存在するため現物では再現できない。実装を削除して測るのは禁止されているので、
    空のディレクトリを build_target と見立てて判定器の挙動だけを固定する。
    これは代理であって、現物での再現ではない。
    """

    def test_empty_build_target_yields_the_existence_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            violations = contract_lib.check_skill(Path(tmp))
        ids = contract_lib.violation_ids(violations)
        self.assertIn(
            "AC-C01-1",
            ids,
            "SKILL.md が無い build_target を判定器が違反として落としていない",
        )

    def test_existence_check_short_circuits_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            violations = contract_lib.check_skill(Path(tmp))
        self.assertEqual(
            ["AC-C01-1"],
            sorted({v.contract_id for v in violations}),
            "SKILL.md 不在時は存在契約 1 件で停止すること (後続検査が例外や偽陽性を出さない)",
        )


class NoLiteralCopyOfCanonTest(unittest.TestCase):
    """面 C: 正本がデータファイルにある値をテスト側へ焼き直していないこと。"""

    def _test_sources(self):
        return sorted(p for p in TESTS_DIR.glob("*.py"))

    def test_max_loops_numeric_literal_is_not_copied_into_tests(self):
        pattern = re.compile(r"max_loops[\"']?\s*[:=]\s*\d")
        offenders = []
        for path in self._test_sources():
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    offenders.append(f"{path.name}:{lineno}: {line.strip()}")
        self.assertEqual(
            [],
            offenders,
            "max_loops の数値は component-inventory.json #C01 goal_seek が唯一の正本 "
            "(F-C06-04)。テスト側へ写すと正本が 2 つになる:\n" + "\n".join(offenders),
        )

    def test_derived_constants_match_the_canonical_data_files(self):
        """導出した定数が正本と一致する (導出経路が空振りしていないことの確認)。"""
        self.assertEqual(
            contract_lib.REQUIRED_GOAL_SEEK,
            dict(contract_lib._INVENTORY_C01["goal_seek"]),
        )
        self.assertEqual(
            list(contract_lib.REQUIRED_SCRIPTS),
            list(contract_lib._BRIEF["deterministic_checks"]),
        )
        self.assertEqual(
            list(contract_lib.REQUIRED_RESPONSIBILITIES),
            [r["id"] for r in contract_lib._BRIEF["responsibilities"]],
        )
        for name in ("REQUIRED_HEARING_FIELDS", "README_SECTIONS", "REPORT_ELEMENTS"):
            self.assertTrue(
                getattr(contract_lib, name),
                f"{name} が空。正本からの導出が空振りしている",
            )


if __name__ == "__main__":
    unittest.main()

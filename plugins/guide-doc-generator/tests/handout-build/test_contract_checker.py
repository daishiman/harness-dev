"""チェッカ自身の検査 — 受入例を通し、非受入例を落とすことを固定する。

このモジュールは実装 (plugins/guide-doc-generator/commands/handout-build.md) に
依存しない。実装前でも緑になるのが正しい。目的は
「test_handout_build_command.py が使う判定器が、何も検出しない空ゲートでは
ないこと」を先に固定することにある。
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402
from reject_cases import REJECT_CASES  # noqa: E402

ACCEPT_ROOT = Path(__file__).resolve().parent / "fixtures" / "accept"


class TestAcceptFixture(unittest.TestCase):
    """受入例: 契約を満たす command 定義は違反 0 件になる。"""

    def test_accept_fixture_exists(self):
        self.assertTrue((ACCEPT_ROOT / "commands" / "handout-build.md").is_file())

    def test_accept_fixture_has_no_violation(self):
        violations = contract_lib.check_command(ACCEPT_ROOT)
        self.assertEqual(
            [],
            [(x.contract_id, x.message) for x in violations],
            "受入例が落ちる場合はチェッカ側の誤りである",
        )


class TestRejectFixtures(unittest.TestCase):
    """非受入例: 契約違反を 1 箇所注入すると、対応する契約 id で落ちる。"""

    def _materialize(self, old, new):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c07-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        md = tmp / "accept" / "commands" / "handout-build.md"
        text = md.read_text(encoding="utf-8")
        self.assertEqual(
            1,
            text.count(old),
            f"reject case の置換前文字列が受入例に一意に存在しない: {old[:60]!r}",
        )
        md.write_text(text.replace(old, new), encoding="utf-8")
        return tmp / "accept"

    def test_reject_cases_are_detected(self):
        for name, old, new, expected_id in REJECT_CASES:
            with self.subTest(case=name):
                root = self._materialize(old, new)
                ids = contract_lib.violation_ids(contract_lib.check_command(root))
                self.assertIn(
                    expected_id,
                    ids,
                    f"非受入例 {name} が {expected_id} で落ちていない (検出: {ids})",
                )

    def test_every_contract_id_has_a_reject_case(self):
        """契約 id が「注入しても落ちない飾り」になっていないことを固定する。"""
        covered = {case[3] for case in REJECT_CASES}
        expected = {
            "AC-C07-1",
            "AC-C07-ARGS",
            "AC-C07-2",
            "AC-C07-3",
            "AC-C07-DATE",
            "AC-C07-OUTDIR",
            "AC-C07-CONFIG",
            "AC-C07-4",
            "AC-C07-5",
            "AC-C07-6",
            "AC-C07-B1",
            "AC-C07-B2",
            "AC-C07-FM-1",
            "AC-C07-FM-2",
            "AC-C07-FM-3",
            "AC-C07-FM-4",
            "AC-C07-FM-5",
            "AC-C07-FM-6",
            "AC-C07-FM-7",
            "AC-C07-REPORT",
            "AC-C07-THEME-NOTICE",
        }
        self.assertEqual(set(), expected - covered)

    def test_missing_command_file_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c07-empty-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ids = contract_lib.violation_ids(contract_lib.check_command(tmp))
        self.assertEqual(["AC-C07-1"], ids)

    def test_missing_delegate_skill_is_rejected(self):
        """委譲先 skill が実在しない場合は AC-C07-4 で落ちる。"""
        tmp = Path(tempfile.mkdtemp(prefix="hb-c07-skill-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        (tmp / "accept" / "skills" / "run-handout-build" / "SKILL.md").unlink()
        ids = contract_lib.violation_ids(contract_lib.check_command(tmp / "accept"))
        self.assertIn("AC-C07-4", ids)

    def test_missing_frontmatter_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c07-fm-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        md = tmp / "accept" / "commands" / "handout-build.md"
        md.write_text("# handout-build\n\n本文だけ\n", encoding="utf-8")
        ids = contract_lib.violation_ids(contract_lib.check_command(tmp / "accept"))
        self.assertEqual(["AC-C07-1"], ids)


class TestFrontmatterParser(unittest.TestCase):
    """契約検査が依存する YAML 部分集合パーサの最低限の挙動。"""

    def test_parses_inline_list_and_bool(self):
        fm, body = contract_lib.split_frontmatter(
            "---\n"
            "name: handout-build\n"
            "allowed-tools: [Read, Write, Bash, Skill]\n"
            "disable-model-invocation: false\n"
            "---\n"
            "body text\n"
        )
        self.assertEqual("handout-build", fm["name"])
        self.assertEqual(["Read", "Write", "Bash", "Skill"], fm["allowed-tools"])
        self.assertIs(False, fm["disable-model-invocation"])
        self.assertIn("body text", body)


class TestArgsBlockExtraction(unittest.TestCase):
    """本文からの CR-HB-ARGS ブロック取り出し。"""

    def test_extracts_block_by_id(self):
        body = '文\n\n```json\n{"id": "OTHER"}\n```\n\n```json\n{"id": "CR-HB-ARGS", "x": 1}\n```\n'
        block, errors = contract_lib.extract_args_block(body)
        self.assertEqual([], errors)
        self.assertEqual(1, block["x"])

    def test_reports_broken_json(self):
        body = "```json\n{not json}\n```\n"
        block, errors = contract_lib.extract_args_block(body)
        self.assertIsNone(block)
        self.assertEqual(1, len(errors))


if __name__ == "__main__":
    unittest.main()

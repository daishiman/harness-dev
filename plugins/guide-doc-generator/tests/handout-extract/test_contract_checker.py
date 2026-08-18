"""チェッカ自身の検査 — 受入例を通し、非受入例を落とすことを固定する。

このモジュールは実装 (plugins/guide-doc-generator/commands/handout-extract.md) に
依存しない。実装前でも緑になるのが正しい。目的は
「test_handout_extract_command.py が使う判定器が、何も検出しない空ゲートでは
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
        self.assertTrue((ACCEPT_ROOT / "commands" / "handout-extract.md").is_file())

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
        tmp = Path(tempfile.mkdtemp(prefix="hb-c08-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        md = tmp / "accept" / "commands" / "handout-extract.md"
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
        """契約 id ごとに少なくとも 1 件の非受入例がある (空ゲートの契約を作らない)。"""
        covered = {case[3] for case in REJECT_CASES}
        expected = {
            "AC-C08-1", "AC-C08-2", "AC-C08-3", "AC-C08-4",
            "AC-C08-ARGS", "AC-C08-DEGRADE",
            "AC-C08-FM-1", "AC-C08-FM-3", "AC-C08-FM-4",
            "AC-C08-FM-5", "AC-C08-FM-6", "AC-C08-PARSE",
        }
        self.assertEqual(set(), expected - covered)

    def test_missing_command_file_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c08-empty-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ids = contract_lib.violation_ids(contract_lib.check_command(tmp))
        self.assertEqual(["AC-C08-1"], ids)

    def test_missing_delegated_skill_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c08-skill-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        shutil.rmtree(tmp / "accept" / "skills" / "run-handout-extract")
        ids = contract_lib.violation_ids(contract_lib.check_command(tmp / "accept"))
        self.assertIn("AC-C08-2", ids)

    def test_missing_referenced_script_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c08-script-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        (tmp / "accept" / "scripts" / "extract-handout-config.py").unlink()
        ids = contract_lib.violation_ids(contract_lib.check_command(tmp / "accept"))
        self.assertIn("AC-C08-2", ids)

    def test_broken_args_block_is_rejected(self):
        root = self._materialize('"id": "CR-EXTRACT-ARGS",', '"id": "CR-OTHER",')
        ids = contract_lib.violation_ids(contract_lib.check_command(root))
        self.assertIn("AC-C08-ARGS", ids)


class TestFrontmatterParser(unittest.TestCase):
    """契約検査が依存する YAML 部分集合パーサの最低限の挙動。"""

    def test_parses_inline_list_and_bool(self):
        fm, body = contract_lib.split_frontmatter(
            "---\n"
            "name: handout-extract\n"
            "allowed-tools: [Read, Write, Bash, Skill]\n"
            "disable-model-invocation: false\n"
            "---\n"
            "body text\n"
        )
        self.assertEqual("handout-extract", fm["name"])
        self.assertEqual(["Read", "Write", "Bash", "Skill"], fm["allowed-tools"])
        self.assertIs(False, fm["disable-model-invocation"])
        self.assertIn("body text", body)


class TestArgsBlockExtraction(unittest.TestCase):
    """本文からの CR-EXTRACT-ARGS ブロック取り出し。"""

    def test_extracts_block_by_id(self):
        body = '文\n\n```json\n{"id": "OTHER"}\n```\n\n```json\n{"id": "CR-EXTRACT-ARGS", "x": 1}\n```\n'
        block, errors = contract_lib.extract_args_block(body)
        self.assertEqual([], errors)
        self.assertEqual(1, block["x"])

    def test_reports_broken_json(self):
        body = "```json\n{not json}\n```\n"
        block, errors = contract_lib.extract_args_block(body)
        self.assertIsNone(block)
        self.assertEqual(1, len(errors))

    def test_strip_fences_removes_declaration_from_prose(self):
        body = "散文\n```json\n{\"id\": \"CR-EXTRACT-ARGS\"}\n```\n続き\n"
        self.assertNotIn("CR-EXTRACT-ARGS", contract_lib.strip_fences(body))


if __name__ == "__main__":
    unittest.main()

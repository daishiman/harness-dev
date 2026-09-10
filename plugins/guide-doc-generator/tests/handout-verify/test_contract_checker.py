"""チェッカ自身の検査 — 受入例を通し、非受入例を落とすことを固定する。

このモジュールは実装 (plugins/guide-doc-generator/commands/handout-verify.md) に
依存しない。実装前でも緑になるのが正しい。目的は
「test_handout_verify_command.py が使う判定器が、何も検出しない空ゲートでは
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
        self.assertTrue((ACCEPT_ROOT / "commands" / "handout-verify.md").is_file())

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
        tmp = Path(tempfile.mkdtemp(prefix="hb-c09-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        md = tmp / "accept" / "commands" / "handout-verify.md"
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

    def test_missing_command_file_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c09-empty-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ids = contract_lib.violation_ids(contract_lib.check_command(tmp))
        self.assertEqual(["AC-C09-1"], ids)

    def test_missing_referenced_script_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c09-script-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        (tmp / "accept" / "scripts" / "verify-handout-a11y-print.py").unlink()
        ids = contract_lib.violation_ids(contract_lib.check_command(tmp / "accept"))
        self.assertIn("AC-C09-2", ids)


class TestFrontmatterParser(unittest.TestCase):
    """契約検査が依存する YAML 部分集合パーサの最低限の挙動。"""

    def test_parses_inline_list_and_bool(self):
        fm, body = contract_lib.split_frontmatter(
            "---\n"
            "name: handout-verify\n"
            "allowed-tools: [Read, Bash]\n"
            "disable-model-invocation: false\n"
            "---\n"
            "body text\n"
        )
        self.assertEqual("handout-verify", fm["name"])
        self.assertEqual(["Read", "Bash"], fm["allowed-tools"])
        self.assertIs(False, fm["disable-model-invocation"])
        self.assertIn("body text", body)


class TestAggregationBlockExtraction(unittest.TestCase):
    """本文からの CR-GATE-AGG ブロック取り出し。"""

    def test_extracts_block_by_id(self):
        body = '文\n\n```json\n{"id": "OTHER"}\n```\n\n```json\n{"id": "CR-GATE-AGG", "x": 1}\n```\n'
        block, errors = contract_lib.extract_aggregation_block(body)
        self.assertEqual([], errors)
        self.assertEqual(1, block["x"])

    def test_reports_broken_json(self):
        body = "```json\n{not json}\n```\n"
        block, errors = contract_lib.extract_aggregation_block(body)
        self.assertIsNone(block)
        self.assertEqual(1, len(errors))


if __name__ == "__main__":
    unittest.main()

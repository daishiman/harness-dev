"""チェッカ自身の検査 — 受入例を通し、非受入例を落とすことを固定する。

このモジュールは実装 (plugins/guide-doc-generator/agents/handout-content-architect.md)
に依存しない。実装前でも緑になるのが正しい。目的は
「test_handout_content_architect_agent.py が使う判定器が、何も検出しない
空ゲートではないこと」を先に固定することにある。
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402
from reject_cases import REJECT_CASES  # noqa: E402

ACCEPT_MD = (
    Path(__file__).resolve().parent
    / "fixtures" / "accept" / "agents" / "handout-content-architect.md"
)


class TestAcceptFixture(unittest.TestCase):
    """受入例: 契約を満たす agent 定義は違反 0 件になる。"""

    def test_accept_fixture_exists(self):
        self.assertTrue(ACCEPT_MD.is_file(), f"受入例が無い: {ACCEPT_MD}")

    def test_accept_fixture_has_no_violation(self):
        violations = contract_lib.check_agent(ACCEPT_MD)
        self.assertEqual(
            [],
            [(x.contract_id, x.message) for x in violations],
            "受入例が落ちる場合はチェッカ側の誤りである",
        )


class TestRejectFixtures(unittest.TestCase):
    """非受入例: 契約違反を 1 箇所注入すると、対応する契約 id で落ちる。"""

    def _materialize(self, old, new):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c05-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        target = tmp / "handout-content-architect.md"
        shutil.copyfile(ACCEPT_MD, target)
        text = target.read_text(encoding="utf-8")
        self.assertEqual(
            1,
            text.count(old),
            f"reject case の置換前文字列が受入例に一意に存在しない: {old[:60]!r}",
        )
        target.write_text(text.replace(old, new), encoding="utf-8")
        return target

    def test_reject_cases_are_detected(self):
        for name, old, new, expected_id in REJECT_CASES:
            with self.subTest(case=name):
                agent_md = self._materialize(old, new)
                ids = contract_lib.violation_ids(contract_lib.check_agent(agent_md))
                self.assertIn(
                    expected_id,
                    ids,
                    f"reject case {name} が {expected_id} で落ちない (検出: {ids})",
                )

    def test_every_contract_id_has_a_reject_case(self):
        """AC-C05-2 以降の全契約 id に、それを落とす非受入例が 1 件以上ある。"""
        covered = {case[3] for case in REJECT_CASES}
        # AC-C05-1 (ファイル不在) は reject fixture ではなく実体の不在で落ちる。
        missing = [
            f"AC-C05-{i}" for i in range(2, 27) if f"AC-C05-{i}" not in covered
        ]
        self.assertEqual([], missing, f"非受入例が無い契約 id: {missing}")

    def test_missing_file_is_detected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c05-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ids = contract_lib.violation_ids(contract_lib.check_agent(tmp / "absent.md"))
        self.assertEqual(["AC-C05-1"], ids)


if __name__ == "__main__":
    unittest.main()

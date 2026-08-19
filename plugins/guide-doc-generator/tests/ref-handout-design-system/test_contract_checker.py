"""判定器 (contract_lib.check_skill) の判定力を固定する。

実装が無い段階で `test_ref_handout_design_system.py` が赤であることには、
判定器が本当に契約を見ているという裏付けが要る。何も検出しない空ゲートでも
「SKILL.md が無い」だけで赤にはできてしまうためである。ここでは受入例が通り、
非受入例が **期待した契約 id で** 落ちることを固定する。

このファイルは実装の有無に依存しないので常に緑でよい。
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402
import fixtures_lib  # noqa: E402
import reject_cases  # noqa: E402


class AcceptFixtureTest(unittest.TestCase):
    def test_accept_fixture_has_no_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = fixtures_lib.write_accept(tmp)
            violations = contract_lib.check_skill(skill_dir)
        self.assertEqual(
            [],
            [(x.contract_id, x.message) for x in violations],
            "受入例が落ちる = 判定器が契約より厳しい (過検出)",
        )


class RejectFixtureTest(unittest.TestCase):
    def test_missing_skill_md_is_ac1(self):
        with tempfile.TemporaryDirectory() as tmp:
            violations = contract_lib.check_skill(Path(tmp) / "skills" / "absent")
        self.assertEqual({"AC-C04-1"}, contract_lib.violation_ids(violations))

    def test_no_frontmatter_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "ref-handout-design-system"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# 見出しだけ\n", encoding="utf-8")
            violations = contract_lib.check_skill(skill_dir)
        self.assertIn("AC-C04-2", contract_lib.violation_ids(violations))

    def test_each_reject_case_hits_its_contract(self):
        for case in reject_cases.CASES:
            with self.subTest(case=case.name):
                with tempfile.TemporaryDirectory() as tmp:
                    skill_dir = reject_cases.materialize(case, tmp)
                    ids = contract_lib.violation_ids(contract_lib.check_skill(skill_dir))
                self.assertIn(
                    case.expected_id,
                    ids,
                    f"非受入例 {case.name} が {case.expected_id} で落ちない (検出漏れ)。実際: {sorted(ids)}",
                )

    def test_reject_cases_cover_every_contract_id(self):
        """AC-C04-1 / 2 以外の全契約に、落とす非受入例が 1 件以上ある。"""
        covered = {c.expected_id for c in reject_cases.CASES} | {"AC-C04-1", "AC-C04-2"}
        # AC-C04-8 (Purpose 見出し) は 8a-8d と同じ検査関数で、8c/8d の非受入例が
        # 判定関数の到達を保証しているため、個別の非受入例を持たない。
        expected = set(contract_lib.ALL_CONTRACT_IDS) - {"AC-C04-8", "AC-C04-8a", "AC-C04-8b"}
        self.assertEqual(set(), expected - covered, "非受入例の無い契約が残っている")


class EmojiRuleTest(unittest.TestCase):
    """CR-EMOJI (C16 canonical_rules.emoji_rule) の層 1 部分集合であることの確認。"""

    def test_japanese_symbols_are_not_emoji(self):
        # CR-EMOJI が明示的に「通す」と書いた記号
        self.assertEqual([], contract_lib.find_emoji("★☆✔♪■© 、。「」・…〜"))

    def test_emoji_are_detected(self):
        hits = contract_lib.find_emoji("\U0001F449✅\U0001F1EF\U0001F1F5⚙️")
        self.assertGreaterEqual(len(hits), 5)


if __name__ == "__main__":
    unittest.main()

"""チェッカ自身の検査 — 受入例を通し、非受入例を落とすことを固定する。

このモジュールは実装 (plugins/guide-doc-generator/skills/run-handout-build/) に
依存しない。実装前でも緑になるのが正しい。目的は
「test_run_handout_build_skill.py が使う判定器が、何も検出しない空ゲートでは
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
ACCEPT_SKILL_DIR = ACCEPT_ROOT / "skills" / "run-handout-build"


class TestAcceptFixture(unittest.TestCase):
    """受入例: 契約を満たす SKILL.md は違反 0 件になる。"""

    def test_accept_fixture_exists(self):
        self.assertTrue((ACCEPT_SKILL_DIR / "SKILL.md").is_file())

    def test_accept_fixture_has_no_violation(self):
        violations = contract_lib.check_skill(ACCEPT_SKILL_DIR)
        self.assertEqual(
            [],
            [(x.contract_id, x.message) for x in violations],
            "受入例が落ちる場合はチェッカ側の誤りである",
        )


class TestRejectFixtures(unittest.TestCase):
    """非受入例: 契約違反を 1 箇所注入すると、対応する契約 id で落ちる。"""

    def _materialize(self, old, new):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c01-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        skill_md = tmp / "accept" / "skills" / "run-handout-build" / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        self.assertEqual(
            1,
            text.count(old),
            f"reject case の置換前文字列が受入例に一意に存在しない: {old[:60]!r}",
        )
        skill_md.write_text(text.replace(old, new), encoding="utf-8")
        return skill_md.parent

    def test_reject_cases_are_detected(self):
        for name, old, new, expected_id in REJECT_CASES:
            with self.subTest(case=name):
                skill_dir = self._materialize(old, new)
                ids = contract_lib.violation_ids(contract_lib.check_skill(skill_dir))
                self.assertIn(
                    expected_id,
                    ids,
                    f"非受入例 {name} が {expected_id} で落ちていない (検出: {ids})",
                )

    def test_missing_skill_md_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c01-empty-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ids = contract_lib.violation_ids(contract_lib.check_skill(tmp))
        self.assertEqual(["AC-C01-1"], ids)

    def test_missing_prompt_file_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c01-prompt-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        (tmp / "accept" / "skills" / "run-handout-build" / "prompts" / "R1-elicit.md").unlink()
        ids = contract_lib.violation_ids(
            contract_lib.check_skill(tmp / "accept" / "skills" / "run-handout-build")
        )
        self.assertIn("AC-C01-5", ids)

    def test_missing_referenced_script_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c01-script-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        (tmp / "accept" / "scripts" / "route-handout-output.py").unlink()
        ids = contract_lib.violation_ids(
            contract_lib.check_skill(tmp / "accept" / "skills" / "run-handout-build")
        )
        self.assertIn("AC-C01-10", ids)


class TestFrontmatterParser(unittest.TestCase):
    """契約検査が依存する YAML 部分集合パーサの最低限の挙動。"""

    def test_parses_nested_list_of_mappings(self):
        fm, body = contract_lib.split_frontmatter(
            "---\n"
            "name: x\n"
            "tools: [Read, Bash]\n"
            "items:\n"
            "  - id: A\n"
            "    n: 1\n"
            "    ok: true\n"
            "  - id: B\n"
            "nested:\n"
            "  inner:\n"
            "    - a\n"
            "    - b\n"
            "---\n"
            "body text\n"
        )
        self.assertEqual("x", fm["name"])
        self.assertEqual(["Read", "Bash"], fm["tools"])
        self.assertEqual([{"id": "A", "n": 1, "ok": True}, {"id": "B"}], fm["items"])
        self.assertEqual(["a", "b"], fm["nested"]["inner"])
        self.assertIn("body text", body)


if __name__ == "__main__":
    unittest.main()

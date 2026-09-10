"""チェッカ自身の検査 — 受入例を通し、非受入例を落とすことを固定する。

このモジュールは実装 (plugins/guide-doc-generator/skills/run-handout-extract/) に
依存しない。実装前でも緑になるのが正しい。目的は
「test_run_handout_extract_skill.py が使う判定器が、何も検出しない空ゲートでは
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
ACCEPT_SKILL_DIR = ACCEPT_ROOT / "skills" / "run-handout-extract"


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
        tmp = Path(tempfile.mkdtemp(prefix="hb-c02-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        skill_md = tmp / "accept" / "skills" / "run-handout-extract" / "SKILL.md"
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

    def test_every_contract_id_has_a_reject_case(self):
        """契約 id ごとに、それを落とす非受入例が最低 1 件ある。

        AC-C02-1 (SKILL.md 欠落) だけは置換注入で作れないため個別テストで担保する。
        """
        covered = {case[3] for case in REJECT_CASES} | {"AC-C02-1"}
        expected = {f"AC-C02-{i}" for i in range(1, 28)}
        self.assertEqual(
            set(),
            expected - covered,
            "非受入例が存在しない契約 id がある (空ゲートになりうる)",
        )

    def test_missing_skill_md_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c02-empty-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ids = contract_lib.violation_ids(contract_lib.check_skill(tmp))
        self.assertEqual(["AC-C02-1"], ids)

    def test_missing_prompt_file_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c02-prompt-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        (tmp / "accept" / "skills" / "run-handout-extract" / "prompts" / "R1-scan.md").unlink()
        ids = contract_lib.violation_ids(
            contract_lib.check_skill(tmp / "accept" / "skills" / "run-handout-extract")
        )
        self.assertIn("AC-C02-5", ids)

    def test_missing_referenced_script_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="hb-c02-script-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(ACCEPT_ROOT, tmp / "accept")
        (tmp / "accept" / "scripts" / "extract-handout-config.py").unlink()
        ids = contract_lib.violation_ids(
            contract_lib.check_skill(tmp / "accept" / "skills" / "run-handout-extract")
        )
        self.assertIn("AC-C02-10", ids)


class TestContractsAreDerivedFromBriefs(unittest.TestCase):
    """契約の定数がブリーフの正本と一致していること (推測で発明していないこと)。

    テスト側が勝手な契約値を持つと、実装が正本に従っても赤のままになる。
    ここで plan 側の正本と突き合わせておく。
    """

    @classmethod
    def setUpClass(cls):
        import json

        plan = contract_lib.repo_root() / "plugin-plans" / "guide-doc-generator"
        cls.brief = json.loads((plan / "briefs" / "skill-brief-C02.json").read_text("utf-8"))
        inventory = json.loads((plan / "component-inventory.json").read_text("utf-8"))
        cls.c02 = next(c for c in inventory["components"] if c["id"] == "C02")

    def test_responsibilities_match_brief(self):
        self.assertEqual(
            [r["id"] for r in self.brief["responsibilities"]],
            list(contract_lib.REQUIRED_RESPONSIBILITIES),
        )

    def test_deterministic_checks_match_brief(self):
        self.assertEqual(
            self.brief["deterministic_checks"],
            list(contract_lib.REQUIRED_SCRIPTS),
        )

    def test_checklist_matches_brief(self):
        self.assertEqual(self.brief["checklist"], list(contract_lib.REQUIRED_CHECKLIST))

    def test_goal_seek_matches_inventory(self):
        self.assertEqual(contract_lib.REQUIRED_GOAL_SEEK, self.c02["goal_seek"])

    def test_criteria_match_inventory(self):
        actual = {
            c["id"]: (c["loop_scope"], c["verify_by"])
            for c in self.c02["feedback_contract"]["criteria"]
        }
        self.assertEqual(contract_lib.REQUIRED_CRITERIA, actual)

    def test_depends_on_matches_inventory(self):
        self.assertEqual(list(contract_lib.REQUIRED_DEPENDS_ON), self.c02["depends_on"])

    def test_build_target_matches_inventory(self):
        self.assertEqual(contract_lib.BUILD_TARGET, self.c02["build_target"])


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

"""AC1: frontmatter の契約 (agent-brief-C06.json#acceptance_checks[AC1] / frontmatter_fields)。"""

from __future__ import annotations

import re

import hb_c06 as H


class TestFrontmatterPresence(H.AgentContractTestCase):
    def test_build_target_exists(self):
        # 赤の起点。setUp が先に落ちるので、ここは実装後の回帰用。
        self.assertTrue(H.AGENT.exists(), "build_target が存在しない")

    def test_frontmatter_block_is_closed(self):
        raw, _ = H.split_frontmatter(self.text)
        self.assertTrue(raw.strip(), "frontmatter が空")

    def test_all_declared_fields_present(self):
        fm = H.frontmatter(self.text)
        for field in H.BRIEF["frontmatter_fields"]["fields"]:
            key = field.split(":")[0].strip()
            with self.subTest(field=key):
                self.assertIn(
                    key, fm, "frontmatter_fields で宣言された '{}' が無い".format(key)
                )

    def test_no_empty_field_values(self):
        fm = H.frontmatter(self.text)
        for field in H.BRIEF["frontmatter_fields"]["fields"]:
            key = field.split(":")[0].strip()
            with self.subTest(field=key):
                self.assertTrue(
                    fm.get(key, "").strip(), "'{}' の値が空".format(key)
                )


class TestFrontmatterValues(H.AgentContractTestCase):
    def setUp(self):
        super().setUp()
        self.fm = H.frontmatter(self.text)

    def test_name_matches_brief(self):
        self.assertEqual(H.BRIEF["name"], self.fm.get("name"))

    def test_name_matches_filename(self):
        self.assertEqual(H.AGENT.stem, self.fm.get("name"))

    def test_description_matches_brief(self):
        # 末尾の句点はブリーフ側が持たない (lint-skill-description R5 は '使う。' を要求する)。
        # 句点の有無だけを吸収して突合する。詳細は README の gaps を参照。
        expected = H.BRIEF["description"].rstrip("。")
        actual = (self.fm.get("description") or "").rstrip("。")
        self.assertEqual(expected, actual, "description がブリーフと一致しない")

    def test_description_passes_lint_skill_description(self):
        issues = H.description_issues(
            self.fm.get("name", ""), self.fm.get("description", "")
        )
        self.assertEqual([], issues, "lint-skill-description の R1-R5 違反")

    def test_kind_is_agent(self):
        self.assertEqual("agent", self.fm.get("kind"))

    def test_isolation_is_fork(self):
        self.assertEqual(
            "fork", self.fm.get("isolation"), "独立 context は fork で宣言する"
        )

    def test_owner_skill_is_c03(self):
        self.assertEqual("assign-handout-readability-evaluator", self.fm.get("owner_skill"))

    def test_prompt_layer_is_7layer(self):
        self.assertEqual("7layer", self.fm.get("prompt_layer"))

    def test_prompt_ref_points_at_responsibility_prompt(self):
        ref = self.fm.get("prompt_ref", "")
        self.assertTrue(
            ref.endswith("prompts/R-review-readability.md"),
            "prompt_ref が責務 prompt を指していない: {}".format(ref),
        )

    def test_prompt_ref_lives_under_owner_skill(self):
        ref = self.fm.get("prompt_ref", "")
        self.assertIn(
            "skills/assign-handout-readability-evaluator/",
            ref,
            "prompt_ref が owner skill 配下でない: {}".format(ref),
        )

    def test_version_is_semver(self):
        self.assertRegex(self.fm.get("version", ""), r"^\d+\.\d+\.\d+$")

    def test_owner_is_non_empty(self):
        self.assertTrue((self.fm.get("owner") or "").strip())

    def test_model_is_declared(self):
        # 値 (sonnet 固定 / inherit) は open_questions で未確定。宣言の有無だけを固定する。
        self.assertTrue((self.fm.get("model") or "").strip(), "model が未宣言")

    def test_since_is_iso_date(self):
        self.assertRegex(self.fm.get("since", ""), r"^\d{4}-\d{2}-\d{2}$")

    def test_last_audited_is_iso_date(self):
        self.assertRegex(self.fm.get("last-audited", ""), r"^\d{4}-\d{2}-\d{2}$")


class TestToolGrant(H.AgentContractTestCase):
    """AC1 / AC4: 付与 tool は Read と Bash のみ。Write を持たせない (proposer != approver)。"""

    def setUp(self):
        super().setUp()
        self.tools = H.tools_set(H.frontmatter(self.text))

    def test_tools_equal_brief(self):
        self.assertEqual(set(H.BRIEF["tools"]), self.tools)

    def test_tools_equal_inventory_read_bash(self):
        self.assertEqual({"Read", "Bash"}, self.tools)

    def test_write_is_not_granted(self):
        self.assertNotIn("Write", self.tools, "Write を持つと proposer=approver になる")

    def test_no_mutating_tool_is_granted(self):
        for banned in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Task"):
            with self.subTest(tool=banned):
                self.assertNotIn(banned, self.tools)

    def test_read_is_granted(self):
        self.assertIn("Read", self.tools)

    def test_bash_is_granted(self):
        self.assertIn("Bash", self.tools)


class TestResponsibilityAnchor(H.AgentContractTestCase):
    """body_sections が要求する責務アンカー。形 (R1 か R-review-readability か) は
    open_questions[0] で未確定のため、ここでは『アンカーが存在すること』だけを固定する。"""

    ANCHOR_ANY = re.compile(r"<!--\s*responsibility:\s*([^\s>-]+(?:-[^\s>]+)*)\s*-->")

    def test_anchor_exists(self):
        self.assertRegex(H.body(self.text), self.ANCHOR_ANY)

    def test_exactly_one_anchor(self):
        found = self.ANCHOR_ANY.findall(H.body(self.text))
        self.assertEqual(1, len(found), "責務アンカーは 1 個: {}".format(found))

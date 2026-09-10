"""AC1 / AC2: quality_gates.p0_lint の 3 本が exit0 になること。

規則そのもの (必須見出し・Self-Evaluation の観点語) はテスト側へ複製せず、
script を実行した結果を正解として使う。ただし『どの見出しが要るか』は
ブリーフの body_sections が独立に宣言しているので、そちらとの一致も見る。
"""

from __future__ import annotations

import hb_c06 as H


class TestP0Lint(H.AgentContractTestCase):
    def test_validate_frontmatter_exits_zero(self):
        self.assertTrue(
            H.VALIDATE_FRONTMATTER.exists(), "{} が無い".format(H.VALIDATE_FRONTMATTER)
        )
        proc = H.run_lint(H.VALIDATE_FRONTMATTER, str(H.AGENT))
        self.assertEqual(
            0, proc.returncode, "validate-frontmatter 失敗:\n{}".format(proc.stderr)
        )

    def test_lint_agent_prompt_section_exits_zero(self):
        self.assertTrue(
            H.LINT_AGENT_PROMPT_SECTION.exists(),
            "{} が無い".format(H.LINT_AGENT_PROMPT_SECTION),
        )
        proc = H.run_lint(H.LINT_AGENT_PROMPT_SECTION, str(H.AGENT))
        self.assertEqual(
            0,
            proc.returncode,
            "lint-agent-prompt-section 失敗:\n{}{}".format(proc.stdout, proc.stderr),
        )

    def test_lint_skill_description_reports_no_violation(self):
        fm = H.frontmatter(self.text)
        self.assertEqual(
            [], H.description_issues(fm.get("name", ""), fm.get("description", ""))
        )


class TestPromptSectionShape(H.AgentContractTestCase):
    """AC2 の内訳を lint 実行と独立に固定する (lint が緩んでも契約が残るように)。"""

    def test_prompt_templates_section_exists(self):
        self.assertIsNotNone(
            H.section("## Prompt Templates", self.text), "'## Prompt Templates' が無い"
        )

    def test_self_evaluation_section_exists(self):
        self.assertIsNotNone(
            H.section("## Self-Evaluation", self.text), "'## Self-Evaluation' が無い"
        )

    def test_self_evaluation_references_a_dimension(self):
        eval_body = H.section("## Self-Evaluation", self.text) or ""
        dimensions = ("完全性", "一貫性", "深度", "検証可能性", "簡潔性")
        self.assertTrue(
            any(d in eval_body for d in dimensions),
            "Self-Evaluation が {} のいずれにも言及しない".format("/".join(dimensions)),
        )

    def test_prompt_templates_has_quote_or_round(self):
        prompt_body = H.section("## Prompt Templates", self.text) or ""
        has_quote = any(
            line.lstrip().startswith(">") for line in prompt_body.splitlines()
        )
        has_round = any(line.startswith("### ") for line in prompt_body.splitlines())
        has_marker = "(対話なし: 自動実行 agent)" in prompt_body
        self.assertTrue(
            has_quote or has_round or has_marker,
            "Prompt Templates に '> ' 引用 / '### ' 小見出し / 自動実行マーカー のいずれも無い",
        )

"""## Purpose: question_solved が本文へ落ちていること。

C06 が答える問いは「機械ゲートが全て exit0 になった資料について、その知見を
持たない読者が読んだとき意味の水準でどこが伝わらないか」である。
Purpose がこれを言っていないと、実装は『読みやすさ全般』の agent に膨らむ。
"""

from __future__ import annotations

import hb_c06 as H

PURPOSE = "## Purpose"


class TestPurpose(H.AgentContractTestCase):
    def test_purpose_section_exists(self):
        self.assertIsNotNone(H.section(PURPOSE, self.text))

    def test_purpose_states_post_gate_scope(self):
        self.assert_mentions_any(
            ("決定論ゲート", "機械ゲート", "exit0"),
            "機械判定の後に残る面だけを見ることが Purpose に無い",
        )

    def test_purpose_states_semantic_level(self):
        self.assert_mentions_any(
            ("意味の水準", "意味水準", "意味の側"),
            "意味の水準の判定であることが Purpose に無い",
        )

    def test_purpose_states_uninformed_reader(self):
        self.assert_mentions_any(
            ("知見を持たない読者", "その知見を持たない", "初心者"),
            "知見を持たない読者の立場で読むことが Purpose に無い",
        )

    def test_purpose_matches_brief_description_intent(self):
        for token in ("専門用語", "抽象", "具体"):
            with self.subTest(token=token):
                self.assert_mentions(token, "description の判定観点が本文に無い")


class TestRequirementTraceability(H.AgentContractTestCase):
    """requirements_covered / checklist_covered の追跡可能性。"""

    def test_brief_covers_r11(self):
        self.assertIn("R11", H.BRIEF["requirements_covered"])

    def test_checklist_coverage_note_declares_machine_split(self):
        note = H.BRIEF["checklist_coverage_note"]
        self.assertIn("機械ゲート", note)

    def test_verdict_does_not_replace_checklist(self):
        self.assert_mentions_any(
            ("checklist の合否を置き換え", "置き換えることはない", "機械ゲート"),
            "C06 の verdict が機械ゲートの合否を置き換えないことの明示",
        )

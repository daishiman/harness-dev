"""body_sections: agent-brief-C06.json#body_sections が宣言する骨格。"""

from __future__ import annotations

import re

import hb_c06 as H


class TestBodySections(H.AgentContractTestCase):
    def test_every_declared_section_present(self):
        src = H.body(self.text)
        for heading in H.BRIEF["body_sections"]:
            if heading.startswith("<!--"):
                continue
            with self.subTest(heading=heading):
                self.assertIn(heading, src, "宣言された見出し '{}' が無い".format(heading))

    def test_sections_appear_in_declared_order(self):
        src = H.body(self.text)
        declared = [h for h in H.BRIEF["body_sections"] if h.startswith("#")]
        positions = []
        for heading in declared:
            idx = src.find(heading)
            if idx < 0:
                self.fail("見出し '{}' が無いため順序を検査できない".format(heading))
            positions.append((heading, idx))
        self.assertEqual(
            [h for h, _ in positions],
            [h for h, _ in sorted(positions, key=lambda p: p[1])],
            "見出しの順序が body_sections の宣言と違う",
        )

    def test_single_h1_title(self):
        h1s = re.findall(r"^# .+$", H.body(self.text), re.MULTILINE)
        self.assertEqual(1, len(h1s), "H1 は 1 つ: {}".format(h1s))

    def test_h1_is_the_agent_name(self):
        self.assertRegex(
            H.body(self.text),
            re.compile(r"^#\s+handout-readability-reviewer\s*$", re.MULTILINE),
        )

    def test_no_placeholder_left(self):
        for token in ("TODO", "TBD", "FIXME", "<<", "XXX"):
            with self.subTest(token=token):
                self.assertNotIn(token, H.body(self.text))

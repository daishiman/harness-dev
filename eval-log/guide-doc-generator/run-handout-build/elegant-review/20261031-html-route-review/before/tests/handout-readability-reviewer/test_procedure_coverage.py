"""procedure: ## Goal-Seeking Execution が判定手順を順序どおり持つこと。

手順は「何を見るか」ではなく「どの順で見るか」に意味がある。
とくに最終ステップ (除外リストとの突合) が最後に来ていないと、
機械面の指摘が findings に残ったまま返る。
"""

from __future__ import annotations

import hb_c06 as H

EXEC = "## Goal-Seeking Execution"

# procedure の各ステップを 1 語で代表させたもの (ブリーフの並び順と同じ)
STEP_MARKERS = [
    ("gate_reports の確認", ("gate_reports",)),
    ("読者の確定", ("reader_profile",)),
    ("規範の読み込み", ("文章設計の型", "references")),
    ("HTML の通読", ("通読",)),
    ("冒頭の並び順", ("opening-order", "goal_chips")),
    ("nav と目次", ("nav", "目次")),
    ("ナビの拾いやすさ", ("nav-scannability", "流し読み")),
    ("lead-line 判定", ("lead-line",)),
    ("具体部品の判定", ("concreteness", "具体部品")),
    ("図解と本文の噛み合い", ("visual-fit", "図解")),
    ("カードの粒度", ("card-granularity", "1 話題")),
    ("判断軸の判定", ("decision-line", "判断軸")),
    ("初出用語の判定", ("glossary", "初出")),
    ("セクション間の移り", ("goal-chain", "セクション間")),
    ("文の連なり", ("sentence-flow", "指示語")),
    ("severity 付与", ("severity",)),
    ("除外リストとの突合", ("除外リスト", "突合", "突き合わせ")),
    ("strengths の抽出", ("strengths",)),
]


class TestProcedureSteps(H.AgentContractTestCase):
    def test_execution_section_exists(self):
        self.assertIsNotNone(H.section(EXEC, self.text), "{} が無い".format(EXEC))

    def test_every_step_is_represented(self):
        for label, markers in STEP_MARKERS:
            with self.subTest(step=label):
                self.assert_mentions_any(markers, "手順 '{}' が本文に無い".format(label))

    def test_step_count_matches_brief(self):
        self.assertEqual(
            len(H.BRIEF["procedure"]),
            len(STEP_MARKERS),
            "ブリーフの procedure 件数とテストの代表語の件数がずれている "
            "(ブリーフが変わったらこのテストを直す)",
        )


class TestProcedureOrder(H.AgentContractTestCase):
    """順序が意味を持つ 3 点だけを固定する。"""

    def _pos(self, needles):
        norm = H.normalize(H.body(self.text))
        found = [norm.find(H.normalize(n)) for n in needles]
        found = [p for p in found if p >= 0]
        if not found:
            self.fail("いずれの記述も無い: {}".format(list(needles)))
        return min(found)

    def test_gate_check_comes_before_semantic_review(self):
        self.assertLess(
            self._pos(("gate_reports",)),
            self._pos(("lead-line",)),
            "gate_reports の確認が意味レビューより前に来ていない",
        )

    def test_reader_is_fixed_before_judging(self):
        self.assertLess(
            self._pos(("reader_profile",)),
            self._pos(("severity",)),
            "読者の確定が judgement より前に来ていない",
        )

    def test_overlap_removal_is_the_last_gate(self):
        self.assertLess(
            self._pos(("severity",)),
            self._pos(("除外リスト", "突合", "突き合わせ")),
            "除外リストとの突合が severity 付与より後に来ていない",
        )


class TestVisualPixelReview(H.AgentContractTestCase):
    """visual-fit が alt 文だけの机上判定へ退化しないこと。"""

    def test_every_illustration_is_opened_as_pixels(self):
        for token in ("実画素", "1 枚ずつ開いて", "alt"):
            self.assert_mentions(token, "画像を実際に開く契約 {} が無い".format(token))

    def test_visual_fit_checks_scene_and_style(self):
        for token in (
            "人物または役割主体",
            "行為",
            "場所",
            "主役の具体物",
            "配色",
            "俯瞰角度",
            "小物密度",
        ):
            self.assert_mentions(token, "visual-fit の判定軸 {} が無い".format(token))

    def test_generic_icon_only_image_is_rejected(self):
        for token in ("抽象アイコン", "UI カード", "羅列"):
            self.assert_mentions(token, "汎用図への退化を拒否する語 {} が無い".format(token))

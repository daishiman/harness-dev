"""AC3: 責務境界。機械判定できる面は C16/C17/C18/C22 の責務であり C06 は見ない。

チーム lead が名指しした「機械判定後に残る意味的な読みやすさだけを見る」を、
除外リスト側 (何を見ないか) と意味側 (同じ対象の何を見るか) の 1 対 1 対比として固定する。
片側だけだと、実装が『機械面も見てよい』と読める余地が残る。
"""

from __future__ import annotations

import hb_c06 as H

CONSTRAINTS = "## Constraints"


class TestExcludedGatesAreNamed(H.AgentContractTestCase):
    def test_each_machine_gate_is_named_as_excluded(self):
        for gate in H.MACHINE_GATES:
            with self.subTest(gate=gate):
                self.assert_mentions(gate, "除外リストに {} が無い".format(gate))

    def test_exclusion_is_stated_as_prohibition(self):
        self.assert_mentions_any(
            ("findings に挙げてはならない", "指摘してはならない", "対象外"),
            "機械ゲート担当面を findings に挙げない禁止の明示",
        )


class TestExcludedSurfaces(H.AgentContractTestCase):
    """boundary が列挙する『見ない』面。5 つとも本文に無ければ実装が拾ってしまう。"""

    def test_emoji_excluded(self):
        self.assert_mentions("絵文字", "C16 が見る面 (絵文字) の除外明示")

    def test_aria_excluded(self):
        self.assert_mentions("aria", "C17 が見る面 (aria 属性) の除外明示")

    def test_print_layout_excluded(self):
        self.assert_mentions_any(("印刷版面", "印刷"), "C17 が見る面 (印刷版面) の除外明示")

    def test_date_format_excluded(self):
        self.assert_mentions_any(
            ("日付書式", "yyyy/mm/dd"), "C18 が見る面 (日付書式) の除外明示"
        )

    def test_sentence_length_limit_excluded(self):
        self.assert_mentions_any(
            ("一文の字数上限", "字数上限", "字数"), "C18 が見る面 (字数) の除外明示"
        )

    def test_existence_checks_excluded(self):
        self.assert_mentions_any(
            ("存在検査", "『存在』", "存在するか"), "存在検査が機械側であることの明示"
        )

    def test_external_reference_excluded(self):
        self.assert_mentions_any(
            ("外部参照", "未使用 symbol"), "C16 が見る面 (自己完結性) の除外明示"
        )

    def test_glossary_coverage_declaration_excluded(self):
        self.assert_mentions_any(
            ("glossary 宣言の被覆", "宣言の被覆", "宣言の有無"),
            "C18 が見る面 (言い換え宣言の被覆) の除外明示",
        )


class TestSemanticCounterparts(H.AgentContractTestCase):
    """同じ対象の『意味の側』だけを見ることの 1 対 1 対比。"""

    def test_contrast_is_written_explicitly(self):
        self.assert_mentions_any(
            ("ではなく",), "『存在するかではなく〜か』の対比表現"
        )

    def test_lead_line_semantic_side(self):
        self.assert_mentions_any(
            ("抽象を 1 行で", "抽象が言い切れて", "1 行で言い切"),
            "lead-line: 存在ではなく抽象を 1 行で言い切れているか",
        )

    def test_decision_line_semantic_side(self):
        self.assert_mentions_any(
            ("次の選択を助ける", "意思決定を助ける", "その場で選択できる問い"),
            "decision-line: 存在ではなく読者の次の選択を助けるか",
        )

    def test_glossary_semantic_side(self):
        self.assert_mentions_any(
            ("初心者に通じる", "別の専門用語で言い換え"),
            "glossary: 宣言ではなく言い換えが初心者に通じるか",
        )

    def test_goal_chain_semantic_side(self):
        self.assert_mentions_any(
            ("goal への連なり", "連なりが読者に辿れる", "全体ゴールから"),
            "goal-chain: 描画ではなくゴールの連なりが辿れるか",
        )

    def test_sentence_flow_semantic_side(self):
        self.assert_mentions_any(
            ("読み進められる", "文の連なり"),
            "sentence-flow: 字数ではなく文の連なりとして読み進められるか",
        )

    def test_concreteness_semantic_side(self):
        self.assert_mentions_any(
            ("抽象の実例", "具体が 1 例", "型が見えない"),
            "concreteness: 抽象と具体の往復が成立しているか",
        )


class TestComponentBoundaries(H.AgentContractTestCase):
    """C01 / C03 との分界。C06 は判定だけを持ち、運搬とループ制御と修正を持たない。"""

    def test_c03_owns_transport(self):
        self.assert_mentions_any(
            ("assign-handout-readability-evaluator", "C03"),
            "呼び出し側 skill (C03) との分界の明示",
        )

    def test_c06_has_no_loop_control(self):
        self.assert_mentions_any(
            ("loop 制御", "ループ制御", "再修正の起動"),
            "C06 が loop 制御を持たないことの明示",
        )

    def test_c06_does_not_hand_over_verdict(self):
        self.assert_mentions_any(
            ("verdict の受け渡し", "受け渡しは C03"),
            "verdict の受け渡しが C03 側であることの明示",
        )

    def test_fix_belongs_to_c01(self):
        self.assert_mentions_any(
            ("修正は C01", "C01 の責務"), "修正が C01 の責務であることの明示"
        )

    def test_suggestion_is_not_an_apply_instruction(self):
        self.assert_mentions_any(
            ("提案であって適用指示ではない", "適用はしない", "適用しない"),
            "suggestion が提案であって適用指示でないことの明示",
        )


class TestOverlapSelfCheck(H.AgentContractTestCase):
    """boundary 突合を手順の最終ステップに固定する (failure_modes: 機械面の重複指摘)。"""

    def test_overlap_findings_are_forbidden(self):
        self.assert_mentions_any(
            ("machine_gate_overlap=true", "machine_gate_overlap が true"),
            "machine_gate_overlap=true の finding を出してはならないことの明示",
        )

    def test_self_check_removes_overlap(self):
        self.assert_mentions_any(
            ("自己検査で除去", "除外リストと突き合わせ", "突合"),
            "除外リストとの突合による自己除去手順",
        )

    def test_removed_items_go_to_not_reviewed(self):
        self.assert_mentions_any(
            ("not_reviewed へ", "not_reviewed に"),
            "除去したものを理由付きで not_reviewed に残すこと",
        )

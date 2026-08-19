"""failure_modes: ブリーフが列挙した 7 つの壊れ方それぞれに、本文の防止策が対応すること。

失敗モードは「起きうる」ではなく「起きたときに何が本文に無かったか」で書かれている。
対応する防止策が本文に無ければ、実装は必ずそのモードへ落ちる。
"""

from __future__ import annotations

import hb_c06 as H


class TestFailureModeMitigations(H.AgentContractTestCase):
    def test_brief_declares_seven_failure_modes(self):
        self.assertEqual(
            7, len(H.BRIEF["failure_modes"]),
            "ブリーフの failure_modes 件数が変わった (テストの対応表を直す)",
        )

    def test_1_machine_overlap_mitigated(self):
        self.assert_mentions_any(
            ("除外リスト", "突合", "machine_gate_overlap"),
            "機械面の重複指摘: 最終ステップでの突合が無い",
        )

    def test_2_design_intent_filling_mitigated(self):
        self.assert_mentions_any(
            ("逐語引用", "quote"),
            "設計意図での穴埋め: location.quote 必須が無い",
        )

    def test_3_indiscriminate_fail_mitigated(self):
        self.assert_mentions_any(
            ("読み返せば分かる", "より良くできる"),
            "全部 FAIL の無差別指摘: severity の定義が本文に無い",
        )

    def test_4_applying_the_fix_mitigated(self):
        self.assert_mentions_any(
            ("Bash 経由の書き込み", "書き換えない", "適用はしない"),
            "改善案の適用: 書き込み禁止の明記が無い",
        )

    def test_5_failed_beginner_acting_mitigated(self):
        self.assert_mentions_any(
            ("1 文で確定", "一文で確定", "立場を明示"),
            "初心者演技の失敗: 読者を 1 文で確定させる手順が無い",
        )

    def test_6_goodhart_mitigated(self):
        self.assert_mentions_any(
            ("過去に出した findings", "毎回", "通読"),
            "Goodhart 化: 毎回通読させる指示が無い",
        )

    def test_7_swallowing_blocked_mitigated(self):
        self.assert_mentions_any(
            ("意味レビューへ進まず", "意味レビューを始めない", "status=blocked"),
            "blocked の握りつぶし: ゲート FAIL 時の差し戻しが無い",
        )

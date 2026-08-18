"""AC7: 決定論ゲートが FAIL の状態で起動されたときの差し戻し経路。"""

from __future__ import annotations

import hb_c06 as H


class TestBlockedPath(H.AgentContractTestCase):
    def test_blocked_status_is_declared(self):
        self.assert_mentions_any(
            ("status=blocked", "status: blocked", '"blocked"'),
            "ゲート FAIL 時に status=blocked を返すこと",
        )

    def test_blocked_reason_is_required_when_blocked(self):
        self.assert_mentions_any(
            ("blocked_reason", "差し戻し理由"),
            "blocked のときだけ blocked_reason が非空であること",
        )

    def test_semantic_review_is_not_started(self):
        self.assert_mentions_any(
            ("意味レビューへ進まず", "意味レビューを始めない", "レビューへ進まない"),
            "ゲート FAIL のまま意味レビューへ進まないこと",
        )

    def test_reason_for_not_reviewing_is_stated(self):
        self.assert_mentions_any(
            ("形式問題に埋もれる", "形式起因"),
            "形式起因の読みにくさを意味の問題として報告しない理由の明示",
        )

    def test_gate_reports_can_be_reverified_by_bash(self):
        self.assert_mentions_any(
            ("再実行", "自ら再実行"),
            "必要なら Bash で該当検査を再実行して確認すること",
        )

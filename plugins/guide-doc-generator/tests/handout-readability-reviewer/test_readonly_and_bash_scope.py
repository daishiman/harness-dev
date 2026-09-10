"""AC4: read-only レビュアーであること。Bash の用途が限定されていること。

tools から Write を外すだけでは Bash 経由の書き込みが塞がらない。
構造 (tool 付与) と宣言 (本文) の両方で塞ぐ、という tools_rationale の意図を固定する。
"""

from __future__ import annotations

import hb_c06 as H


class TestReadOnlyDeclaration(H.AgentContractTestCase):
    def test_does_not_rewrite_handout_or_config(self):
        self.assert_mentions_any(
            ("資料も構成データも書き換えない", "書き換えない", "read-only"),
            "資料・構成データを書き換えないことの明示",
        )

    def test_write_tool_is_not_granted(self):
        self.assertNotIn("Write", H.tools_set(H.frontmatter(self.text)))

    def test_bash_write_is_forbidden(self):
        self.assert_mentions_any(
            ("Bash 経由の書き込みも禁止", "Bash 経由の書き込み", "Bash での書き込みを行わない"),
            "Bash 経由の書き込み禁止の明示 (failure_modes: 改善案の適用)",
        )

    def test_no_fix_is_applied(self):
        self.assert_mentions_any(
            ("修正は行わない", "直さない", "適用はしない"),
            "自ら修正しないことの明示",
        )


class TestBashScope(H.AgentContractTestCase):
    """Bash の用途は検査 script の読み取り実行に限る。"""

    def test_each_allowed_script_is_named(self):
        for script in H.ALLOWED_BASH_SCRIPTS:
            with self.subTest(script=script):
                self.assert_mentions(
                    script, "Bash で再実行してよい script の列挙"
                )

    def test_bash_usage_is_limited(self):
        self.assert_mentions_any(
            ("限定", "に限る"), "Bash 用途が限定されていることの明示"
        )

    def test_json_report_is_the_only_write(self):
        self.assert_mentions_any(
            ("--json-report", "json-report の一時パス"),
            "書き込みは --json-report の一時パスのみ",
        )

    def test_rerun_purpose_is_deduplication(self):
        self.assert_mentions_any(
            ("既に判定済み", "重複指摘", "自分の指摘対象から除外"),
            "再実行の目的が機械判定済み面の除外であることの明示",
        )

"""AC5: 返却物の形式検査 (agent-brief-C06.json#output_contract)。

task-spec P04-C06-01 の acceptance_criterion が名指しした 2 本のうちの 1 本。
axis / severity の語彙はテスト側で列挙せず、ブリーフの returns 宣言から取り出す。
"""

from __future__ import annotations

import hb_c06 as H

OUTPUTS = "## Outputs"


class TestTopLevelShape(H.AgentContractTestCase):
    """戻り値のトップレベル 7 キー。"""

    def test_status(self):
        self.assert_mentions("status", "status キーの宣言", where=OUTPUTS)

    def test_status_enum(self):
        for value in ("ok", "blocked"):
            with self.subTest(value=value):
                self.assert_mentions(value, "status の値域", where=OUTPUTS)

    def test_verdict(self):
        self.assert_mentions("verdict", "verdict キーの宣言", where=OUTPUTS)

    def test_verdict_enum(self):
        for value in ("PASS", "FAIL"):
            with self.subTest(value=value):
                self.assert_mentions(value, "verdict の値域", where=OUTPUTS)

    def test_reviewed_as(self):
        self.assert_mentions("reviewed_as", "読者としての立場の写し", where=OUTPUTS)

    def test_findings(self):
        self.assert_mentions("findings", "findings 配列", where=OUTPUTS)

    def test_strengths(self):
        self.assert_mentions("strengths", "保護対象を返す strengths", where=OUTPUTS)

    def test_not_reviewed(self):
        self.assert_mentions("not_reviewed", "見なかった軸と理由", where=OUTPUTS)

    def test_blocked_reason(self):
        self.assert_mentions("blocked_reason", "blocked 理由", where=OUTPUTS)


class TestFindingShape(H.AgentContractTestCase):
    """finding 1 件が持つべきフィールド。根拠 (逐語引用) と改善案を必須にする。"""

    def test_id(self):
        self.assert_mentions("id", "finding の id", where=OUTPUTS)

    def test_severity(self):
        self.assert_mentions("severity", "finding の severity", where=OUTPUTS)

    def test_axis(self):
        self.assert_mentions("axis", "finding の axis", where=OUTPUTS)

    def test_location(self):
        self.assert_mentions("location", "finding の location", where=OUTPUTS)

    def test_location_section_id(self):
        self.assert_mentions("section_id", "location の section_id", where=OUTPUTS)

    def test_location_element(self):
        self.assert_mentions("element", "location の element", where=OUTPUTS)

    def test_location_quote(self):
        self.assert_mentions("quote", "location の逐語引用", where=OUTPUTS)

    def test_quote_is_verbatim_and_required(self):
        self.assert_mentions_any(
            ("逐語引用", "そのまま引用"),
            "判定根拠を HTML の逐語引用に限る (failure_modes: 設計意図での穴埋め)",
        )

    def test_why_not_understood(self):
        self.assert_mentions(
            "why_not_understood", "知見のない読者として何が分からなかったか", where=OUTPUTS
        )

    def test_suggestion(self):
        self.assert_mentions("suggestion", "改善案", where=OUTPUTS)

    def test_machine_gate_overlap(self):
        self.assert_mentions(
            "machine_gate_overlap", "機械ゲートとの重複フラグ", where=OUTPUTS
        )


class TestAxisVocabulary(H.AgentContractTestCase):
    """axis 語彙 6 件。ブリーフの returns 宣言が正本。"""

    def test_all_axes_declared(self):
        for axis in H.brief_axes():
            with self.subTest(axis=axis):
                self.assert_mentions(axis, "axis 語彙 '{}' の宣言".format(axis))

    def test_axis_count_is_six(self):
        self.assertEqual(6, len(H.brief_axes()), "brief 側の axis 語彙が 6 件でない")


class TestSeverityVocabulary(H.AgentContractTestCase):
    def test_all_severities_declared(self):
        for sev in H.brief_severities():
            with self.subTest(severity=sev):
                self.assert_mentions(sev, "severity 語彙 '{}' の宣言".format(sev))

    def test_high_definition(self):
        self.assert_mentions_any(
            ("読み進めるのをやめる", "誤って理解"),
            "high の定義 (読者が読み進めるのをやめる/誤って理解する)",
        )

    def test_medium_definition(self):
        self.assert_mentions_any(
            ("読み返せば分かる", "負荷が高い"), "medium の定義"
        )

    def test_low_definition(self):
        self.assert_mentions_any(("より良くできる",), "low の定義")


class TestVerdictRule(H.AgentContractTestCase):
    """verdict の決め方が本文に固定されていること (無差別 FAIL を防ぐ)。"""

    def test_high_one_means_fail(self):
        self.assert_mentions_any(
            ("high が 1 件でもあれば FAIL", "highが1件でもあればFAIL", "high 1 件で FAIL"),
            "severity=high が 1 件でもあれば verdict=FAIL",
        )

    def test_otherwise_pass(self):
        self.assert_mentions_any(
            ("それ以外は PASS", "それ以外はPASS"), "high が無ければ PASS"
        )


class TestNoFileWrites(H.AgentContractTestCase):
    """output_contract.writes_files は空。findings は戻り値で返す。"""

    def test_findings_are_returned_not_written(self):
        self.assert_mentions_any(
            ("戻り値", "ファイルを介さない", "ファイルは書かない"),
            "findings を戻り値で返しファイルを書かない",
        )

    def test_writes_files_if_declared_is_empty(self):
        norm = H.normalize(H.body(self.text))
        if "writes_files" in norm:
            self.assertIn(
                "writes_files:[]",
                norm,
                "writes_files を書くなら空配列でなければならない (read-only レビュアー)",
            )

    def test_brief_declares_no_writes(self):
        self.assertEqual([], H.BRIEF["output_contract"]["writes_files"])

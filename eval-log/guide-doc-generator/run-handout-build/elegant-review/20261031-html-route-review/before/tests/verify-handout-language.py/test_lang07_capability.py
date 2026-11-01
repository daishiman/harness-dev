# -*- coding: utf-8 -*-
"""LANG-07 (R21 / goal-spec C51): できること起点の解説が機能名から始まらないこと。

正本: script-brief-C18.json detections#LANG-07 と
acceptance_checks AC-C18-R21-51a / 51b、RESOLUTION-R21.md の C51 行
(判定の正本は C12 の slot 順序検査、C18 は描画テキスト面の副検査)。
"""

from __future__ import annotations

import unittest

from _support import (
    CAPABILITY_LEAD_LINE_NG,
    CAPABILITY_LEAD_LINE_OK,
    FEATURE_HEADING,
    LanguageGateTestCase,
    base_config,
)


def _cfg_with_lead(lead_line, section_kind="capability-explainer", sid="s2"):
    cfg = base_config()
    for sec in cfg["sections"]:
        if sec["id"] == sid:
            sec["lead_line"] = lead_line
            sec["section_kind"] = section_kind
    return cfg


class TestLang07Scope(LanguageGateTestCase):
    """対象は section_kind=="capability-explainer" の section だけ。"""

    def test_default_capability_section_passes(self):
        res = self.run_default()
        self.assert_detection_pass(res, "LANG-07")

    def test_checked_counts_only_capability_sections(self):
        res = self.run_default()
        self.assertEqual(
            1, self.checked(res, "LANG-07"), "capability-explainer は fixture に 1 件"
        )

    def test_ac51b_no_capability_section_is_checked_zero_pass(self):
        cfg = _cfg_with_lead(CAPABILITY_LEAD_LINE_NG, section_kind="standard")
        res = self.run_default(
            cfg,
            section_kind_attr={"s2": "standard"},
            lead_line_text={"s2": CAPABILITY_LEAD_LINE_NG},
        )
        self.assert_detection_pass(res, "LANG-07")
        self.assertEqual(0, self.checked(res, "LANG-07"))

    def test_ac51b_same_lead_line_passes_when_kind_is_standard(self):
        cfg = _cfg_with_lead(CAPABILITY_LEAD_LINE_NG, section_kind="standard")
        res = self.run_default(
            cfg,
            section_kind_attr={"s2": "standard"},
            lead_line_text={"s2": CAPABILITY_LEAD_LINE_NG},
            plain_parts_only={"s2"},
        )
        self.assert_gate_pass(res)

    def test_feature_heading_in_a_standard_section_is_ignored(self):
        cfg = _cfg_with_lead("Projects の話をします。", section_kind="standard", sid="s3")
        res = self.run_default(cfg, lead_line_text={"s3": "Projects の話をします。"})
        self.assert_detection_pass(res, "LANG-07")


class TestLang07PrefixMatch(LanguageGateTestCase):
    """lead_line の先頭が feature 見出しと前方一致していれば違反。"""

    def test_ac51a_lead_line_starts_with_feature_heading(self):
        cfg = _cfg_with_lead(CAPABILITY_LEAD_LINE_NG)
        res = self.run_default(cfg, lead_line_text={"s2": CAPABILITY_LEAD_LINE_NG})
        self.assert_gate_fail(res, "LANG-07", count=1)

    def test_ac51a_violation_row_names_the_section(self):
        cfg = _cfg_with_lead(CAPABILITY_LEAD_LINE_NG)
        res = self.run_default(cfg, lead_line_text={"s2": CAPABILITY_LEAD_LINE_NG})
        joined = "\n".join("\t".join(r) for r in self.stderr_rows(res, "LANG-07"))
        self.assertIn("s2", joined, "違反行に section id が出る\n%s" % joined)

    def test_ac51a_evidence_shows_the_matched_feature_heading(self):
        cfg = _cfg_with_lead(CAPABILITY_LEAD_LINE_NG)
        res = self.run_default(cfg, lead_line_text={"s2": CAPABILITY_LEAD_LINE_NG})
        joined = "\n".join("\t".join(r) for r in self.stderr_rows(res, "LANG-07"))
        self.assertIn(FEATURE_HEADING, joined, "一致した feature 見出しを evidence に出す")

    def test_ac51b_outcome_first_lead_line_passes(self):
        cfg = _cfg_with_lead(CAPABILITY_LEAD_LINE_OK)
        res = self.run_default(cfg, lead_line_text={"s2": CAPABILITY_LEAD_LINE_OK})
        self.assert_gate_pass(res)

    def test_match_ignores_spaces_and_symbols(self):
        """比較は NFKC + 空白除去 + 記号 (・/ ： : - —) 除去の上で行う。"""
        cfg = _cfg_with_lead("プロ ジェクト：を使うと便利です。")
        res = self.run_default(
            cfg,
            lead_line_text={"s2": "プロ ジェクト：を使うと便利です。"},
            feature_headings={"s2": ["プロジェクト"]},
        )
        self.assert_gate_fail(res, "LANG-07", count=1)

    def test_match_is_nfkc_insensitive(self):
        cfg = _cfg_with_lead("Ｐｒｏｊｅｃｔｓ を使うと便利です。")
        res = self.run_default(
            cfg,
            lead_line_text={"s2": "Ｐｒｏｊｅｃｔｓ を使うと便利です。"},
            feature_headings={"s2": ["Projects"]},
        )
        self.assert_gate_fail(res, "LANG-07", count=1)

    def test_feature_heading_in_the_middle_is_not_a_violation(self):
        """前方一致限定。文中に機能名が出るだけでは落とさない。"""
        cfg = _cfg_with_lead("報告書づくりが Projects で 10 分に縮む。")
        res = self.run_default(
            cfg, lead_line_text={"s2": "報告書づくりが Projects で 10 分に縮む。"}
        )
        self.assert_detection_pass(res, "LANG-07")

    def test_short_feature_heading_is_excluded(self):
        """2 文字以下の feature 見出しは誤検出回避のため対象外。"""
        cfg = _cfg_with_lead("AI が下書きを作る。")
        res = self.run_default(
            cfg,
            lead_line_text={"s2": "AI が下書きを作る。"},
            feature_headings={"s2": ["AI"]},
        )
        self.assert_detection_pass(res, "LANG-07")

    def test_three_character_feature_heading_is_in_scope(self):
        cfg = _cfg_with_lead("検索窓が下書きを作る。")
        res = self.run_default(
            cfg,
            lead_line_text={"s2": "検索窓が下書きを作る。"},
            feature_headings={"s2": ["検索窓"]},
        )
        self.assert_gate_fail(res, "LANG-07", count=1)

    def test_any_of_multiple_feature_headings_triggers(self):
        cfg = _cfg_with_lead("Artifacts を使うと便利です。")
        res = self.run_default(
            cfg,
            lead_line_text={"s2": "Artifacts を使うと便利です。"},
            feature_headings={"s2": ["Projects", "Artifacts"]},
        )
        self.assert_gate_fail(res, "LANG-07", count=1)

    def test_one_section_yields_at_most_one_violation(self):
        cfg = _cfg_with_lead("Projects を使うと便利です。")
        res = self.run_default(
            cfg,
            lead_line_text={"s2": "Projects を使うと便利です。"},
            feature_headings={"s2": ["Projects", "Projects の設定"]},
        )
        self.assert_gate_fail(res, "LANG-07", count=1)


class TestLang07NounPhraseRule(LanguageGateTestCase):
    """『〜機能』『〜モード』『〜ツール』で終わる名詞句 + 助詞 (は/を/の) も違反。"""

    def _run(self, lead):
        cfg = _cfg_with_lead(lead)
        return self.run_default(
            cfg, lead_line_text={"s2": lead}, feature_headings={"s2": ["まったく別の見出し"]}
        )

    def test_kinou_wo_is_a_violation(self):
        self.assert_gate_fail(self._run("検索機能を使うと速くなります。"), "LANG-07", count=1)

    def test_kinou_wa_is_a_violation(self):
        self.assert_gate_fail(self._run("検索機能は速いです。"), "LANG-07", count=1)

    def test_kinou_no_is_a_violation(self):
        self.assert_gate_fail(self._run("検索機能の使い方を説明します。"), "LANG-07", count=1)

    def test_mode_is_a_violation(self):
        self.assert_gate_fail(self._run("集中モードを使うと速くなります。"), "LANG-07", count=1)

    def test_tool_is_a_violation(self):
        self.assert_gate_fail(self._run("変換ツールを使うと速くなります。"), "LANG-07", count=1)

    def test_outcome_sentence_without_the_pattern_passes(self):
        res = self._run("毎週の報告書づくりが 10 分で終わる。")
        self.assert_detection_pass(res, "LANG-07")

    def test_noun_phrase_later_in_the_sentence_is_not_a_violation(self):
        res = self._run("報告書づくりが速くなる。検索機能を使います。")
        self.assert_detection_pass(res, "LANG-07")


class TestLang07Boundary(LanguageGateTestCase):
    """C12 (構造) との分界: slot の順序そのものは C18 の責務ではない。"""

    def test_slot_order_violation_alone_does_not_fail_lang07(self):
        cfg = _cfg_with_lead(CAPABILITY_LEAD_LINE_OK)
        res = self.run_default(
            cfg,
            lead_line_text={"s2": CAPABILITY_LEAD_LINE_OK},
            plain_parts_only={"s2"},  # slot 属性を持たない部品だけの capability section
        )
        self.assert_detection_pass(res, "LANG-07")
        self.assert_gate_pass(res)

    def test_capability_section_without_feature_slot_still_checks_noun_phrase(self):
        cfg = _cfg_with_lead("検索機能を使うと速くなります。")
        res = self.run_default(
            cfg,
            lead_line_text={"s2": "検索機能を使うと速くなります。"},
            plain_parts_only={"s2"},
        )
        self.assert_gate_fail(res, "LANG-07", count=1)

    def test_capability_section_without_lead_line_is_lang04_not_lang07(self):
        cfg = _cfg_with_lead(CAPABILITY_LEAD_LINE_OK)
        res = self.run_default(cfg, omit_lead_line={"s2"})
        self.assert_gate_fail(res, "LANG-04", count=1)
        self.assertEqual(
            0, self.violations(res, "LANG-07"), "lead_line 不在は LANG-04 の面 (二重計上しない)"
        )


if __name__ == "__main__":
    unittest.main()

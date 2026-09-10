# -*- coding: utf-8 -*-
"""LANG-01: 宣言された専門用語が初出時に括弧書きの言い換えを伴うこと。

正本: script-brief-C18.json detections#LANG-01 と
acceptance_checks AC-C18-02 / AC-C18-03 / AC-C18-04、
failure_modes「config.glossary[] が空配列」。
"""

from __future__ import annotations

import json
import unittest

from _support import GLOSSARY, LanguageGateTestCase, base_config, to_fullwidth


class TestLang01PassForms(LanguageGateTestCase):
    """合格形。括弧の種類・空白の有無・NFKC 差は吸収する。"""

    def test_all_three_terms_paraphrased_at_first_occurrence(self):
        res = self.run_default()
        self.assert_detection_pass(res, "LANG-01")

    def test_checked_equals_glossary_size(self):
        res = self.run_default()
        self.assertEqual(
            len(GLOSSARY), self.checked(res, "LANG-01"), "checked は glossary の件数"
        )

    def test_halfwidth_parenthesis_is_accepted(self):
        res = self.run_default(glossary_modes={"コネクタ": "first_paren_halfwidth"})
        self.assert_detection_pass(res, "LANG-01")

    def test_ideographic_space_before_parenthesis_is_accepted(self):
        res = self.run_default(glossary_modes={"コネクタ": "first_paren_ideographic_space"})
        self.assert_detection_pass(res, "LANG-01")

    def test_ascii_space_before_parenthesis_is_accepted(self):
        res = self.run_default(glossary_modes={"プロンプト": "first_paren_ascii_space"})
        self.assert_detection_pass(res, "LANG-01")

    def test_nfkc_difference_in_plain_is_accepted(self):
        """plain の全角/半角差は NFKC 正規化で吸収する。"""
        res = self.run_default(glossary_modes={"プロンプト": "first_paren_fullwidth_plain"})
        self.assert_detection_pass(res, "LANG-01")

    def test_repeated_parenthesis_is_not_a_violation(self):
        """2 回目以降の括弧書きの重複は違反にしない (冗長さは本ゲートの責務ではない)。"""
        res = self.run_default(glossary_modes={"MCP": "first_paren_repeated"})
        self.assert_detection_pass(res, "LANG-01")

    def test_second_occurrence_without_parenthesis_is_not_a_violation(self):
        res = self.run_default()
        self.assert_gate_pass(res)

    def test_alnum_term_inside_longer_word_is_not_the_first_occurrence(self):
        """英数 term は単語境界を課す。MCPX の中の MCP は初出ではない。"""
        res = self.run_default(glossary_modes={"MCP": "prefixed_longer_word"})
        self.assert_detection_pass(res, "LANG-01")

    def test_empty_glossary_is_checked_zero_pass(self):
        cfg = base_config(glossary=[])
        res = self.run_default(cfg, omit_glossary_body=True)
        self.assert_detection_pass(res, "LANG-01")
        self.assertEqual(0, self.checked(res, "LANG-01"))


class TestLang01Violations(LanguageGateTestCase):
    def test_ac02_paraphrase_only_at_second_occurrence(self):
        res = self.run_default(glossary_modes={"コネクタ": "second_paren"})
        self.assert_gate_fail(res, "LANG-01", count=1)

    def test_ac02_evidence_shows_surrounding_text(self):
        """初出位置の前後 40 文字を evidence に付ける。"""
        res = self.run_default(glossary_modes={"コネクタ": "second_paren"})
        joined = "\n".join("\t".join(row) for row in self.stderr_rows(res, "LANG-01"))
        self.assertIn("を用意します", joined, "初出周辺の本文が evidence に出ていない\n%s" % joined)

    def test_ac02_violation_row_names_the_term(self):
        res = self.run_default(glossary_modes={"コネクタ": "second_paren"})
        joined = "\n".join("\t".join(row) for row in self.stderr_rows(res, "LANG-01"))
        self.assertIn("コネクタ", joined)

    def test_ac02_violation_row_carries_line_and_column(self):
        res = self.run_default(glossary_modes={"コネクタ": "second_paren"})
        rows = self.stderr_rows(res, "LANG-01")
        self.assertTrue(
            any(":" in row[2] for row in rows),
            "用語違反の位置は line:col 形式\nrows=%r" % (rows,),
        )

    def test_ac03_declared_but_absent_term_is_a_violation(self):
        res = self.run_default(glossary_modes={"MCP": "absent"})
        self.assert_gate_fail(res, "LANG-01", count=1)

    def test_ac03_absent_term_reason_differs_from_missing_paraphrase(self):
        res = self.run_default(glossary_modes={"MCP": "absent"})
        rows = self.stderr_rows(res, "LANG-01")
        reason = "\t".join(rows[0][3:])
        self.assertTrue(
            "出現" in reason or "未出現" in reason,
            "『宣言されたが本文に出現しない』と読める理由を出す\nreason=%r" % reason,
        )

    def test_bare_term_without_any_paraphrase_is_a_violation(self):
        res = self.run_default(glossary_modes={"プロンプト": "bare_no_paren"})
        self.assert_gate_fail(res, "LANG-01", count=1)

    def test_equals_form_is_a_violation(self):
        """『用語 ＝ 言い換え』形は意図的に不合格 (goal-spec C16 は括弧書きと明記)。"""
        res = self.run_default(glossary_modes={"コネクタ": "equals_form"})
        self.assert_gate_fail(res, "LANG-01", count=1)

    def test_wrong_paraphrase_content_is_a_violation(self):
        res = self.run_default(glossary_modes={"コネクタ": "wrong_plain"})
        self.assert_gate_fail(res, "LANG-01", count=1)

    def test_parenthesis_not_adjacent_to_term_is_a_violation(self):
        res = self.run_default(glossary_modes={"コネクタ": "paren_not_adjacent"})
        self.assert_gate_fail(res, "LANG-01", count=1)

    def test_paraphrase_only_in_attribute_is_a_violation(self):
        """T は text node の連結。属性値の言い換えは本文と見なさない。"""
        res = self.run_default(glossary_modes={"プロンプト": "in_attribute_only"})
        self.assert_gate_fail(res, "LANG-01", count=1)

    def test_paraphrase_only_in_script_is_a_violation(self):
        """<script> の内容は本文から除外する。"""
        res = self.run_default(glossary_modes={"MCP": "in_script_only"})
        self.assert_gate_fail(res, "LANG-01", count=1)

    def test_multiple_terms_produce_multiple_violations(self):
        res = self.run_default(
            glossary_modes={"コネクタ": "second_paren", "MCP": "absent", "プロンプト": "bare_no_paren"}
        )
        self.assert_gate_fail(res, "LANG-01", count=3)

    def test_japanese_term_has_no_word_boundary_relief(self):
        """日本語 term は境界条件を課さない = 部分文字列でも初出として拾う。"""
        res = self.run_default(glossary_modes={"コネクタ": "japanese_substring_first"})
        self.assert_gate_fail(res, "LANG-01", count=1)


class TestLang01LongestTermFirst(LanguageGateTestCase):
    """部分文字列関係のある用語は長い方を先に照合する。"""

    def _cfg(self):
        return base_config(
            glossary=[
                {"term": "スキル", "plain": "決まった手順のまとまり"},
                {"term": "スキルセット", "plain": "手順のまとまりの組み合わせ"},
            ]
        )

    def test_both_terms_paraphrased_passes(self):
        cfg = self._cfg()
        res = self.run_default(cfg, glossary_source=cfg["glossary"])
        self.assert_detection_pass(res, "LANG-01")
        self.assertEqual(2, self.checked(res, "LANG-01"))

    def test_longer_term_occurrence_does_not_satisfy_shorter_term(self):
        cfg = self._cfg()
        res = self.run_default(
            cfg,
            glossary_source=cfg["glossary"],
            glossary_modes={"スキル": "bare_no_paren"},
        )
        self.assert_gate_fail(res, "LANG-01", count=1)


class TestLang01EmptyGlossaryDisclosure(LanguageGateTestCase):
    """宣言 0 件を黙って PASS にすると抜け道になる。可視化を必須にする。"""

    def _run(self):
        cfg = base_config(glossary=[])
        report = self.tmpdir / "report.json"
        res = self.run_default(cfg, json_report=report, omit_glossary_body=True)
        return res, report

    def test_stdout_carries_a_note_about_zero_declarations(self):
        res, _ = self._run()
        notes = [
            ln
            for ln in res.stdout.splitlines()
            if "宣言" in ln and not ln.startswith("LANG-01 ")
        ]
        self.assertTrue(
            notes, "用語宣言 0 件の注記を stdout へ必ず出す\nstdout=%r" % res.stdout
        )

    def test_json_report_carries_the_same_note(self):
        res, report = self._run()
        text = json.dumps(self.read_report(report), ensure_ascii=False)
        self.assertIn("宣言", text, "json-report にも 0 件の注記を残す")

    def test_zero_declaration_still_exits_zero(self):
        res, _ = self._run()
        self.assertEqual(0, res.returncode, "宣言 0 件そのものは違反ではない")


class TestLang01Boundary(LanguageGateTestCase):
    def test_term_appearing_in_title_only_is_not_body_occurrence(self):
        """title は <head> 内であり本文テキスト T に含めない。"""
        cfg = base_config(
            title="MCP ではじめる一歩",
            glossary=[{"term": "MCP", "plain": "道具をつなぐ共通の決まり"}],
        )
        res = self.run_default(
            cfg,
            h1_text="はじめての一歩",
            glossary_source=cfg["glossary"],
            glossary_modes={"MCP": "first_paren"},
        )
        self.assert_detection_pass(res, "LANG-01")

    def test_fullwidth_plain_declared_and_halfwidth_rendered(self):
        cfg = base_config(
            glossary=[{"term": "プロンプト", "plain": to_fullwidth("AI") + " への指示文"}]
        )
        res = self.run_default(
            cfg,
            glossary_source=[{"term": "プロンプト", "plain": "AI への指示文"}],
        )
        self.assert_detection_pass(res, "LANG-01")


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""責務境界の回帰と再現性。

C18 は「機械判定できる文章構造」だけを持つ。意味的な読みやすさは C06
(handout-readability-reviewer)、構成データのスキーマは C12、外部参照は C16、
a11y と印刷は C17、R19 の筋道は C22、ディレクトリ命名の語彙は C19 の責務。

正本: script-brief-C18.json (requirements_covered / detections の
false_positive_risk)、agent-brief-C06.json の boundary、
RESOLUTION-R21.md (C51 / C52 の owner)、
acceptance_checks AC-C18-12 / AC-C18-13。
"""

from __future__ import annotations

import unittest

from _support import (
    LanguageGateTestCase,
    SCRIPT,
    base_config,
    build_html,
)


class TestSemanticJudgementIsOutOfScope(LanguageGateTestCase):
    """C06 の面 (意味の妥当性) を C18 が拾わないこと。"""

    def test_meaningless_lead_line_still_passes(self):
        """『その 1 行で抽象が言い切れているか』は C06 の面。"""
        res = self.run_default(lead_line_text={"s3": "あああああああああああ。"})
        self.assert_gate_pass(res)

    def test_meaningless_judgment_axis_still_passes(self):
        """『その一文が読者の次の選択を助けるか』は C06 の面。"""
        res = self.run_default(judgment_axis_text={"s3": "いいいいいいいいいい。"})
        self.assert_gate_pass(res)

    def test_paraphrase_written_in_another_jargon_still_passes(self):
        """『言い換えが初心者に通じるか』は C06 の面。宣言どおりなら PASS。"""
        cfg = base_config(
            glossary=[{"term": "コネクタ", "plain": "MCP トランスポートのアダプタ実装"}]
        )
        res = self.run_default(cfg, glossary_source=cfg["glossary"])
        self.assert_gate_pass(res)

    def test_lead_line_that_is_not_abstract_still_passes(self):
        res = self.run_default(
            lead_line_text={"s3": "手順 3 の画面で右上のボタンを押してください。"}
        )
        self.assert_gate_pass(res)

    def test_judgment_axis_that_is_not_a_judgment_still_passes(self):
        res = self.run_default(judgment_axis_text={"s3": "以上です。"})
        self.assert_gate_pass(res)

    def test_out_of_scope_block_is_not_empty_even_on_a_clean_pass(self):
        res = self.run_default()
        block = self.out_of_scope_block(res)
        self.assertIsNotNone(block, "全 PASS でも OUT-OF-SCOPE 節を省略しない")
        self.assertGreaterEqual(
            len(block.splitlines()), 2, "OUT-OF-SCOPE は見出しだけの空節にしない\n%s" % block
        )


class TestOtherGatesAreOutOfScope(LanguageGateTestCase):
    def test_external_reference_is_not_c18_business(self):
        """外部参照の有無は C16 SC-01..04。"""
        cfg = base_config()
        html = build_html(cfg).replace(
            "</body>", '<img src="https://example.com/x.png" alt="外部画像">\n</body>'
        )
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_missing_alt_is_not_c18_business(self):
        """alt 欠落は C17 の a11y 面。"""
        cfg = base_config()
        html = build_html(cfg).replace("</body>", '<img src="data:,">\n</body>')
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_missing_hero_purpose_is_not_c18_business(self):
        """目的・背景・ゴールの描画は C22 NAR-01。"""
        cfg = base_config()
        html = build_html(cfg).replace(
            '  <p data-hb-field="purpose">%s</p>\n' % cfg["purpose"], ""
        )
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_missing_nav_is_not_c18_business(self):
        cfg = base_config()
        res = self.run_gate(
            html=self.write_html(build_html(cfg)), config=self.write_config(cfg)
        )
        self.assert_gate_pass(res)

    def test_section_goal_absence_is_not_c18_business(self):
        """セクションゴールの存在と位置は C22 NAR-03/04。"""
        res = self.run_default(omit_section_goal={"s1", "s2", "s3", "s4"})
        self.assert_gate_pass(res)


class TestR21NonOwnedItemsAreOutOfScope(LanguageGateTestCase):
    """RESOLUTION-R21.md で C18 が owner でない項目を検査に含めない。"""

    def test_c52_block_body_length_is_not_checked(self):
        """C52 の文字数上限とアコーディオン畳み込みの owner は C12 (--normalize)。"""
        cfg = base_config()
        long_body = "とても長い本文です。" * 60  # 400 文字を大きく超える
        html = build_html(cfg).replace(
            "<p>本文の具体部品です。</p>", "<p>%s</p>" % long_body, 1
        )
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_c51_slot_order_is_not_checked(self):
        """C51 の判定正本は C12 の parts[].slot 順序検査。C18 は文言面のみ。"""
        cfg = base_config()
        html = build_html(cfg)
        # capability セクション内の slot 順序を feature → outcome へ入れ替える
        start = html.index('<section id="s2"')
        end = html.index("</section>", start)
        lines = html[start:end].splitlines(keepends=True)
        feature = next(i for i, ln in enumerate(lines) if 'data-hb-slot="feature"' in ln)
        lead = next(i for i, ln in enumerate(lines) if 'data-hb-field="lead_line"' in ln)
        lines.insert(lead + 1, lines.pop(feature))  # feature を outcome より前へ
        html = html[:start] + "".join(lines) + html[end:]
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assertEqual(
            0,
            self.violations(res, "LANG-07"),
            "slot の並び自体は C12 の面。LANG-07 は lead_line の書き出しだけを見る",
        )

    def test_c46_flow_overview_item_count_is_not_checked(self):
        """C46 の項目数上限の owner は C12。"""
        cfg = base_config()
        rows = "".join("<li>手順 %d</li>" % i for i in range(1, 12))
        html = build_html(cfg).replace(
            "<p>本文の具体部品です。</p>", "<ol>%s</ol>" % rows, 1
        )
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_gate_pass(res)


class TestSingleDateSource(LanguageGateTestCase):
    """AC-C18-12: 日付の単一ソース原則を実装レベルで固定する。"""

    def _source(self):
        self.require_script()
        return SCRIPT.read_text(encoding="utf-8")

    def test_source_does_not_call_date_today(self):
        self.assertNotIn("date.today", self._source())

    def test_source_does_not_call_datetime_now(self):
        self.assertNotIn("datetime.now", self._source())

    def test_source_does_not_call_today_at_all(self):
        self.assertNotIn("today(", self._source())

    def test_source_does_not_call_time_time(self):
        self.assertNotIn("time.time(", self._source())

    def test_source_does_not_call_utcnow(self):
        self.assertNotIn("utcnow", self._source())


class TestDeterminism(LanguageGateTestCase):
    """AC-C18-13: 同一入力で 2 回実行し stdout / json-report がバイト一致。"""

    def test_stdout_is_byte_identical_on_pass(self):
        html, config = self.write_pair()
        out_dir = self.make_out_dir()
        a = self.run_gate(html=html, config=config, out_dir=out_dir)
        b = self.run_gate(html=html, config=config, out_dir=out_dir)
        self.assertEqual(a.stdout, b.stdout)

    def test_stdout_is_byte_identical_on_fail(self):
        html, config = self.write_pair(
            omit_lead_line={"s3"}, glossary_modes={"コネクタ": "second_paren"}
        )
        a = self.run_gate(html=html, config=config)
        b = self.run_gate(html=html, config=config)
        self.assertEqual(a.stdout, b.stdout)

    def test_stderr_is_byte_identical_on_fail(self):
        html, config = self.write_pair(
            omit_lead_line={"s3"}, omit_judgment_axis={"s4"}
        )
        a = self.run_gate(html=html, config=config)
        b = self.run_gate(html=html, config=config)
        self.assertEqual(a.stderr, b.stderr)

    def test_json_report_is_byte_identical(self):
        html, config = self.write_pair()
        out_dir = self.make_out_dir()
        r1 = self.tmpdir / "r1.json"
        r2 = self.tmpdir / "r2.json"
        self.run_gate(html=html, config=config, out_dir=out_dir, json_report=r1)
        self.run_gate(html=html, config=config, out_dir=out_dir, json_report=r2)
        self.assertEqual(r1.read_bytes(), r2.read_bytes())

    def test_exit_code_is_stable(self):
        html, config = self.write_pair(glossary_modes={"MCP": "absent"})
        a = self.run_gate(html=html, config=config)
        b = self.run_gate(html=html, config=config)
        self.assertEqual(a.returncode, b.returncode)

    def test_json_report_is_overwritten_not_appended(self):
        html, config = self.write_pair()
        report = self.tmpdir / "r.json"
        report.write_text("x" * 10000, encoding="utf-8")
        self.run_gate(html=html, config=config, json_report=report)
        self.read_report(report)

    def test_result_does_not_depend_on_cwd(self):
        import subprocess
        import sys

        from _support import REPO_ROOT

        html, config = self.write_pair()
        self.require_script()
        outs = []
        for cwd in (REPO_ROOT, self.tmpdir):
            outs.append(
                subprocess.run(
                    [sys.executable, str(SCRIPT), "--html", str(html), "--config", str(config)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    cwd=str(cwd),
                ).stdout
            )
        self.assertEqual(outs[0], outs[1], "cwd に依存せず同じ判定を返す")


class TestFormattingInsensitivity(LanguageGateTestCase):
    """整形差 (改行・インデント) で判定を変えない。"""

    def test_extra_newlines_do_not_change_the_verdict(self):
        cfg = base_config()
        html = build_html(cfg).replace("\n", "\n\n")
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_minified_html_does_not_change_the_verdict(self):
        cfg = base_config()
        html = "".join(ln.strip() for ln in build_html(cfg).splitlines())
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_crlf_line_endings_do_not_change_the_verdict(self):
        cfg = base_config()
        html = build_html(cfg).replace("\n", "\r\n")
        res = self.run_gate(html=self.write_html(html), config=self.write_config(cfg))
        self.assert_gate_pass(res)


class TestMismatchedPair(LanguageGateTestCase):
    """failure_modes: --config と --html が別資料でも整合性の証明はしない。"""

    def test_unrelated_pair_fails_with_violations_not_error(self):
        cfg_a = base_config()
        cfg_b = base_config(
            date="2020/01/01",
            glossary=[{"term": "全く別の語", "plain": "別の言い換え"}],
        )
        html = self.write_html(build_html(cfg_a))
        res = self.run_gate(html=html, config=self.write_config(cfg_b))
        self.assertEqual(1, res.returncode, "突合結果を返す述語に徹する (exit 2 にしない)")

    def test_unrelated_pair_reports_both_lang01_and_date02(self):
        cfg_a = base_config()
        cfg_b = base_config(
            date="2020/01/01",
            glossary=[{"term": "全く別の語", "plain": "別の言い換え"}],
        )
        html = self.write_html(build_html(cfg_a))
        res = self.run_gate(html=html, config=self.write_config(cfg_b))
        self.assertGreaterEqual(self.violations(res, "LANG-01"), 1)
        self.assertGreaterEqual(self.violations(res, "DATE-02"), 1)


if __name__ == "__main__":
    unittest.main()

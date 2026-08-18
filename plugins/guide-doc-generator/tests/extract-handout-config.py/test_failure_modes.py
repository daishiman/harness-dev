# -*- coding: utf-8 -*-
"""異常系 (failure_modes / AC-C20-10 / fail_semantics)。

「正しい失敗の仕方」を固定する。壊れた入力から一見正しい構成データが生まれない
こと、1 箇所の破損で全体を捨てないこと、書いてはいけない場面で --out を書かない
ことの 3 点が主眼。
"""

import unittest

import _harness as H


class MalformedHtml(H.C20TestCase):

    UNCLOSED = ('<!DOCTYPE html>\n<html data-hb-doc-type="lecture">\n<body>\n'
                '<section id="intro">\n  <p data-hb-part="TEXT" data-hb-part-id="t1">本文\n'
                '</body>\n</html>\n')

    def test_unclosed_tag_is_exit1(self):
        """AC-C20-10: 終了タグが閉じておらず親子が確定できない。"""
        res, _ = self.extract(self.UNCLOSED)
        self.assert_exit(res, 1)

    def test_unclosed_tag_reports_malformed_with_line_number(self):
        res, _ = self.extract(self.UNCLOSED)
        lines = self.assert_diag(res, H.E_HTML_MALFORMED)
        self.assertTrue(any(any(t.isdigit() for t in l.split()) for l in lines),
                        "E-HTML-MALFORMED に行番号が無い: %r" % lines)

    def test_out_is_not_written_on_malformed(self):
        res, _ = self.extract(self.UNCLOSED)
        self.assert_exit(res, 1)
        self.assert_not_written(self.out)

    def test_stray_end_tag_breaks_the_stack(self):
        html = ('<!DOCTYPE html>\n<html>\n<body>\n<section id="a"><p>x</p></div>\n'
                '</section>\n</body>\n</html>\n')
        res, _ = self.extract(html)
        self.assert_exit(res, 1)
        self.assert_diag(res, H.E_HTML_MALFORMED)

    def test_void_elements_do_not_break_the_stack(self):
        """void 要素はスタックへ積まない (br / img / meta / hr / link / input / source)。"""
        part = ('  <p data-hb-part="TEXT" data-hb-part-id="t1"'
                ' data-hb-body="1 行目 2 行目">1 行目<br>2 行目</p>\n'
                '  <hr>\n')
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro", parts=part)]))
        self.assert_exit(res, 0)

    def test_comments_and_doctype_are_ignored(self):
        part = ('  <!-- 注記 -->\n'
                '  <p data-hb-part="TEXT" data-hb-part-id="t1" data-hb-body="本文">本文</p>\n')
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro", parts=part)]))
        self.assert_exit(res, 0)
        self.assertNotIn("注記", self.out_text())


class DuplicateSectionId(H.C20TestCase):

    def _html(self):
        return H.full_html(sections=[
            H.section_html("intro", parts=H.part_text("t1")),
            H.section_html("intro", parts=H.part_text("t2")),
        ])

    def test_duplicate_section_id_is_exit1(self):
        res, _ = self.extract(self._html())
        self.assert_exit(res, 1)

    def test_duplicate_section_id_is_unrecoverable_not_silently_resolved(self):
        res, _ = self.extract(self._html())
        self.assert_diag(res, H.E_UNRECOVERABLE, "intro")


class BrokenDiagramData(H.C20TestCase):
    """1 箇所の破損で全体の抽出を捨てない。"""

    def _html(self):
        # data-hb-media-record はこの要素が diagrams[] の実体を持つ印。
        # これが無いとレジストリを組みに行かないので破損も検出されない。
        broken = ('  <div data-hb-part="DIAGRAM" data-hb-part-id="d1" data-hb-diagram-id="f1"'
                  ' data-hb-media-record="f1" data-hb-diagram-title="壊れた図"'
                  ' data-hb-diagram-pattern="linear-flow"'
                  ' data-hb-diagram-data="{not json"><svg></svg></div>\n')
        return H.full_html(sections=[
            H.section_html("intro", parts=broken + H.part_text("t1")),
            H.section_html("practice", heading="演習", parts=H.part_b03("p-steps")),
        ])

    def test_broken_diagram_is_exit1(self):
        res, _ = self.extract(self._html())
        self.assert_exit(res, 1)

    def test_broken_diagram_is_reported_as_unrecoverable(self):
        res, _ = self.extract(self._html())
        self.assert_diag(res, H.E_UNRECOVERABLE)

    def test_other_sections_are_still_extracted(self):
        res, _ = self.extract(self._html())
        cfg = self.read_out()
        self.assertEqual(["intro", "practice"], [s["id"] for s in cfg["sections"]])
        self.assertEqual(["B03"], [p["part"] for p in cfg["sections"][1]["parts"]])

    def test_partial_output_is_written_for_unrecoverable(self):
        res, _ = self.extract(self._html())
        self.assertTrue(self.out.exists(),
                        "E-EXTRACT-UNRECOVERABLE では穴つき成果物を残す")


class EmptyAndEdgeInputs(H.C20TestCase):

    def test_empty_file_does_not_crash(self):
        res, _ = self.extract("")
        self.assertIn(res.returncode, (1, 2),
                      "空 HTML の扱いが 1/2 のいずれでもない (exit=%d)" % res.returncode)

    def test_empty_file_emits_a_diagnostic_code(self):
        res, _ = self.extract("")
        codes = {l.split(" ")[0] for l in res.stderr.splitlines() if l.strip()}
        self.assertTrue(codes, "空 HTML に対して診断が 1 件も出ていない")
        self.assertTrue(all(c.startswith("E-") or c.startswith("W-") for c in codes),
                        "先頭が診断コードでない行がある: %r" % codes)

    def test_html_without_sections_is_not_a_crash(self):
        html = H._html_open_tag() + "<body>" + H.doc_fields() + "</body></html>"
        res, _ = self.extract("<!DOCTYPE html>\n" + html)
        self.assertIn(res.returncode, (0, 1))

    def test_non_utf8_html_is_rejected_cleanly(self):
        path = self.tmp / "sjis.html"
        path.write_bytes("<html><body>日本語</body></html>".encode("shift_jis"))
        res = self.run_cli("--html", path, "--out", self.out)
        self.assertIn(res.returncode, (1, 2), "UTF-8 でない入力で異常終了していない")
        self.assert_not_written(self.out)


if __name__ == "__main__":
    unittest.main()

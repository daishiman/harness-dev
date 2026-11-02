# -*- coding: utf-8 -*-
"""heuristic 経路と復元不能の扱い (heuristic_fallback / fail_semantics / AC-C20-08)。

R14 の主用途は手書き HTML のテンプレート化なので、マーカーが無い入力でも部品は
復元する。一方で意味情報を推測しないこと (never_guessed) と、穴つき成果物を
--out へ残しつつ exit 1 にすること (fail_semantics の非対称) をここで固定する。
"""

import unittest

import _harness as H

NEVER_GUESSED_DOCUMENT = ("reader", "prior_knowledge_level", "essential_problem", "doc_type")
NEVER_GUESSED_SECTION = ("lead_line", "judgment_axis", "goal")


class LegacyHandwrittenHtml(H.C20TestCase):
    """AC-C20-08: マーカーを持たない参照 v1 相当の HTML。"""

    def setUp(self):
        super().setUp()
        self.res, self.html = self.extract(H.LEGACY_HTML)

    def test_exit1_because_required_fields_are_unrecoverable(self):
        self.assert_exit(self.res, 1)

    def test_partial_config_is_still_written(self):
        """fail_semantics: E-EXTRACT-UNRECOVERABLE のときだけ穴つき成果物を書く。"""
        self.assertTrue(self.out.exists(), "穴つき構成データが --out へ書かれていない")

    def test_parts_are_recovered_by_class_map(self):
        parts = self.read_out()["sections"][0]["parts"]
        self.assertEqual(["B03", "B11", "TEXT", "B15"], [p["part"] for p in parts])

    def test_heuristic_warning_is_emitted_for_each_guessed_part(self):
        lines = self.assert_diag(self.res, H.W_HEURISTIC)
        self.assertEqual(4, len(lines), "heuristic 部品の件数と警告件数が合わない: %r" % lines)

    def test_heuristic_warning_carries_the_evidence_class_name(self):
        lines = self.assert_diag(self.res, H.W_HEURISTIC)
        joined = "\n".join(lines)
        for cls in ("step-row", "prompt-box", "pop-chips"):
            self.assertIn(cls, joined, "根拠クラス名 %s が警告に無い" % cls)

    def test_never_guessed_document_fields_are_null(self):
        cfg = self.read_out()
        for key in NEVER_GUESSED_DOCUMENT:
            self.assertIsNone(cfg.get(key), "%s を推測している" % key)

    def test_never_guessed_section_fields_are_null(self):
        section = self.read_out()["sections"][0]
        for key in NEVER_GUESSED_SECTION:
            self.assertIsNone(section.get(key), "section.%s を推測している" % key)

    def test_unrecoverable_is_reported_with_json_pointer(self):
        for key in NEVER_GUESSED_DOCUMENT:
            self.assert_diag(self.res, H.E_UNRECOVERABLE, "/" + key)

    def test_unrecoverable_section_pointer_is_indexed(self):
        self.assert_diag(self.res, H.E_UNRECOVERABLE, "/sections/0/lead_line")

    def test_holes_are_not_written_as_extra_keys(self):
        """no_extra_keys: 穴の一覧を構成データへ書き込まない (C12 の未知キー検査対策)。"""
        cfg = self.read_out()
        for key in ("unrecoverable", "fidelity", "_holes", "extraction_report"):
            self.assertNotIn(key, cfg, "穴の一覧が構成データへ混入している: %s" % key)

    def test_summary_reports_heuristic_and_unrecoverable_counts(self):
        fields = self.summary(self.res)
        self.assertNotEqual("0", fields["heuristic"])
        self.assertNotEqual("0", fields["unrecoverable"])

    def test_plain_paragraph_becomes_text_part(self):
        """A8: どの class_map にも当たらない本文は TEXT にする。"""
        parts = self.read_out()["sections"][0]["parts"]
        text_parts = [p for p in parts if p["part"] == "TEXT"]
        self.assertEqual(1, len(text_parts))
        self.assertIn("地の文", text_parts[0]["data"]["body"])


class StrictFidelity(H.C20TestCase):
    """--strict-fidelity は「任意フィールドの復元不能も 0 件」を要求する。"""

    def _html_without_optional_markers(self):
        """必須は揃うが assets の原本パス (任意) が復元できない HTML。"""
        part = ('  <figure data-hb-part="IMG" data-hb-part-id="i1"'
                ' data-hb-media-record="shot-1" data-hb-asset-id="shot-1"'
                ' data-hb-asset-alt="集計画面">'
                '<img src="%s"></figure>\n' % H.PNG_DATA_URI)
        return H.full_html(sections=[H.section_html("intro", parts=part)])

    def test_optional_gap_is_exit0_without_flag(self):
        res, _ = self.extract(self._html_without_optional_markers())
        self.assert_exit(res, 0)

    def test_optional_gap_is_exit1_with_flag(self):
        res, _ = self.extract(self._html_without_optional_markers(), "--strict-fidelity")
        self.assert_exit(res, 1)

    def test_heuristic_part_is_exit1_with_flag(self):
        """reporting: heuristic で同定した部品も --strict-fidelity 下では不合格。"""
        html = H.full_html(sections=[H.section_html(
            "intro", parts='  <div class="step-row"><div>元データを集める</div></div>\n')])
        res, _ = self.extract(html, "--strict-fidelity")
        self.assert_exit(res, 1)
        self.assert_diag(res, H.W_HEURISTIC)

    def test_fully_marked_html_passes_strict_fidelity(self):
        res, _ = self.extract(H.full_html(), "--strict-fidelity")
        self.assert_exit(res, 0)


class DocumentMetaMarkers(H.C20TestCase):
    """preserved_only_with_markers: マーカーが無ければ復元せず穴にする。"""

    def _drop_attribute(self, attr):
        html = H.full_html()
        start = html.index("<html")
        end = html.index(">", start)
        head = html[start:end]
        for token in head.split(" "):
            if token.startswith(attr + "="):
                return html.replace(" " + token, "", 1)
        self.fail("fixture に属性 %s が無い" % attr)

    def test_missing_meta_reader_is_unrecoverable(self):
        res, _ = self.extract(self._drop_attribute("data-hb-meta-reader"))
        self.assert_exit(res, 1)
        self.assert_diag(res, H.E_UNRECOVERABLE, "/reader")
        self.assertIsNone(self.read_out().get("reader"))

    def test_missing_doc_type_is_unrecoverable(self):
        res, _ = self.extract(self._drop_attribute("data-hb-doc-type"))
        self.assert_exit(res, 1)
        self.assert_diag(res, H.E_UNRECOVERABLE, "/doc_type")

    def test_missing_theme_is_not_invented(self):
        """落とすのは著者が書いた値を運ぶ data-hb-config-theme の方。

        data-hb-theme は既定値の解決を経た実効テーマなので、著者が theme 欄を
        書かなかった資料でも必ず値が入る。そちらを落としても「書いていない」の
        再現にはならない。
        """
        res, _ = self.extract(self._drop_attribute("data-hb-config-theme"))
        self.assertIsNone(self.read_out().get("theme"), "theme を推測している")

    def test_missing_diagram_data_marker_is_unrecoverable(self):
        """diagrams[].data は data-hb-diagram-data が無いと戻せない。"""
        part = ('  <div data-hb-part="DIAGRAM" data-hb-part-id="d1" data-hb-diagram-id="flow-1"'
                ' data-hb-media-record="flow-1" data-hb-diagram-title="集計の流れ"'
                ' data-hb-diagram-pattern="linear-flow"><svg></svg></div>\n')
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro", parts=part)]))
        self.assert_exit(res, 1)
        self.assert_diag(res, H.E_UNRECOVERABLE)


if __name__ == "__main__":
    unittest.main()

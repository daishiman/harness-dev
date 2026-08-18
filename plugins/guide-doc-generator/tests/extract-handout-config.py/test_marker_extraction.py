# -*- coding: utf-8 -*-
"""マーカー経路の逆抽出 (algorithm A4-A10 / renderer_marker_requirements)。

AC-C20-05 (全部品が exact) / AC-C20-06 (data URI 添付と画像) /
AC-C20-13 (<pre> の原文保持) を含む。値の出所は data-hb-* マーカーだけであり、
クラス名や本文の位置から推測した値がここへ混ざらないことも併せて固定する。
"""

import json
import unittest

import _harness as H


class DocumentLevelExtraction(H.C20TestCase):

    def setUp(self):
        super().setUp()
        self.res, self.html = self.extract()

    def test_exit0_on_fully_marked_html(self):
        self.assert_exit(self.res, 0)

    def test_no_unrecoverable_on_fully_marked_html(self):
        self.assert_exit(self.res, 0)
        self.assert_no_diag(self.res, H.E_UNRECOVERABLE)

    def test_no_heuristic_on_fully_marked_html(self):
        """マーカーがある要素は heuristic 経路へ落ちない。"""
        self.assert_exit(self.res, 0)
        self.assert_no_diag(self.res, H.W_HEURISTIC)

    def test_document_fields_are_restored(self):
        cfg = self.read_out()
        for key, value in H.expected_document_fields().items():
            self.assertEqual(value, cfg.get(key), "%s が復元されていない" % key)

    def test_schema_version_is_taken_from_html_attribute(self):
        cfg = self.read_out()
        self.assertEqual(H.DOC_META["schema_version"], cfg.get("schema_version"))

    def test_document_glossary_is_restored_with_scope(self):
        cfg = self.read_out()
        self.assertEqual([{"term": "プロンプト", "plain": "AI へ渡す指示文"}],
                         cfg.get("glossary"))

    def test_notes_enabled_is_not_silently_dropped(self):
        """preserved_exact に notes_enabled があるため、値か穴のどちらかで必ず残る。"""
        cfg = self.read_out()
        self.assertIn("notes_enabled", cfg)

    def test_sections_are_in_document_order(self):
        cfg = self.read_out()
        self.assertEqual(["intro", "practice"], [s["id"] for s in cfg["sections"]])

    def test_section_fields_are_restored(self):
        section = self.read_out()["sections"][0]
        self.assertEqual("導入", section["heading"])
        self.assertEqual("この節を読み終えると、着手点を自分で決められるようになる", section["goal"])
        self.assertEqual("指示は目的から書くと崩れない", section["lead_line"])
        self.assertEqual("迷ったら、受け取る人が何を判断できるかで決める", section["judgment_axis"])
        self.assertEqual("20分", section["duration"])

    def test_section_kind_is_taken_from_marker(self):
        section = self.read_out()["sections"][0]
        self.assertEqual("standard", section["section_kind"])

    def test_non_default_section_kind_is_restored(self):
        res, _ = self.extract(H.full_html(sections=[
            H.section_html("agenda", kind="agenda-timebox", parts=H.part_b03("agenda-steps")),
        ]))
        self.assert_exit(res, 0)
        self.assertEqual("agenda-timebox", self.read_out()["sections"][0]["section_kind"])

    def test_summary_counts_match_extracted_content(self):
        fields = self.summary(self.res)
        cfg = self.read_out()
        self.assertEqual(len(cfg["sections"]), int(fields["sections"]))
        self.assertEqual(sum(len(s["parts"]) for s in cfg["sections"]), int(fields["parts"]))
        self.assertEqual("0", fields["heuristic"])
        self.assertEqual("0", fields["unrecoverable"])

    def test_out_uses_c12_serialization_conventions(self):
        """A12: ensure_ascii=false / indent=2 / sort_keys=true / LF / 末尾改行 1 個。"""
        text = self.out_text()
        self.assertTrue(text.endswith("\n"), "末尾改行が無い")
        self.assertFalse(text.endswith("\n\n"), "末尾改行が 2 個以上ある")
        self.assertNotIn("\r", text, "CRLF が混ざっている")
        self.assertNotIn("\\u", text, "ensure_ascii=True で書かれている")
        cfg = json.loads(text)
        self.assertEqual(json.dumps(cfg, ensure_ascii=False, indent=2, sort_keys=True) + "\n", text)


class PartExtraction(H.C20TestCase):

    def _extract_parts(self, parts_html):
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro", parts=parts_html)]))
        parts = self.read_out()["sections"][0]["parts"]
        self.assertTrue(parts, "部品が 1 件も復元されていない")
        return res, parts

    def test_part_type_and_id_come_from_markers(self):
        res, parts = self._extract_parts(H.part_b03())
        self.assert_exit(res, 0)
        self.assertEqual([("B03", "intro-steps")], [(p["part"], p["id"]) for p in parts])

    def test_parts_are_in_dom_order(self):
        res, parts = self._extract_parts(H.part_b03() + H.part_text() + H.part_b15())
        self.assert_exit(res, 0)
        self.assertEqual(["B03", "TEXT", "B15"], [p["part"] for p in parts])

    def test_b03_rows_keep_key_and_raw_time(self):
        """data-hb-key / data-hb-time の素値を優先し、装飾つき表示から切り出さない。"""
        res, parts = self._extract_parts(H.part_b03())
        self.assert_exit(res, 0)
        rows = parts[0]["data"]["rows"]
        self.assertEqual(["collect", "ask"], [r["key"] for r in rows])
        self.assertEqual(["10分", "10分"], [r["time"] for r in rows])

    def test_b09_rows_keep_key(self):
        res, parts = self._extract_parts(H.part_b09())
        self.assert_exit(res, 0)
        self.assertEqual("has-data", parts[0]["data"]["rows"][0]["key"])

    def test_b15_chips_keep_key(self):
        res, parts = self._extract_parts(H.part_b15())
        self.assert_exit(res, 0)
        self.assertEqual("daily", parts[0]["data"]["chips"][0]["key"])

    def test_b16_owner_and_due_come_from_attributes(self):
        res, parts = self._extract_parts(H.part_b16())
        self.assert_exit(res, 0)
        row = parts[0]["data"]["rows"][0]
        self.assertEqual("佐藤", row["owner"])
        self.assertEqual("2026年8月24日", row["due"])

    def test_b11_pre_body_keeps_newlines_and_indent(self):
        """AC-C20-13: <pre> 配下は空白も改行も畳まない。"""
        res, parts = self._extract_parts(H.part_b11())
        self.assert_exit(res, 0)
        values = [v for v in parts[0]["data"].values() if isinstance(v, str)]
        self.assertIn(H.PROMPT_BODY, values,
                      "<pre> の本文が原文のまま復元されていない: %r" % (parts[0]["data"],))

    def test_normal_text_whitespace_is_collapsed(self):
        """<pre> 以外は連続空白を 1 個へ畳んで trim する。

        印つき部品の body は data-hb-body が運ぶため、表示テキストの正規化が
        値になるのは印を持たない手書き HTML (heuristic 経路) だけである。
        測る対象をその経路へ寄せる。
        """
        html = H.full_html(sections=[H.section_html(
            "intro", parts='  <p>\n'
                           '     指示は   目的から\n   書く\n  </p>\n')])
        res, _ = self.extract(html)
        self.assert_exit(res, 0)
        part = self.read_out()["sections"][0]["parts"][0]
        self.assertEqual("指示は 目的から 書く", part["data"]["body"])

    def test_character_references_are_resolved(self):
        """convert_charrefs=True。実体参照は文字へ戻る。"""
        html = H.full_html(sections=[H.section_html(
            "intro", parts='  <p>A &amp; B &lt;C&gt;</p>\n')])
        res, _ = self.extract(html)
        self.assert_exit(res, 0)
        self.assertEqual("A & B <C>",
                         self.read_out()["sections"][0]["parts"][0]["data"]["body"])

    def test_all_catalog_in_section_parts_can_be_restored_exactly(self):
        """AC-C20-05: 部品を 1 つずつ含む HTML で unrecoverable=0 / heuristic=0。"""
        parts = (H.part_b03() + H.part_b09() + H.part_b11() + H.part_b12()
                 + H.part_b15() + H.part_b16() + H.part_text() + H.part_img()
                 + H.part_diagram())
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro", parts=parts)]))
        self.assert_exit(res, 0)
        fields = self.summary(res)
        self.assertEqual("0", fields["unrecoverable"])
        self.assertEqual("0", fields["heuristic"])
        self.assertEqual("9", fields["parts"])
        self.assertEqual(str(int(fields["parts"])), fields["exact"])


class MediaExtraction(H.C20TestCase):

    def test_image_asset_is_restored_with_data_uri(self):
        """AC-C20-06: alt / caption / 原本パス / data URI 本体。"""
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro", parts=H.part_img())]))
        self.assert_exit(res, 0)
        cfg = self.read_out()
        assets = cfg.get("assets") or []
        self.assertEqual(1, len(assets), "assets が復元されていない: %r" % cfg.keys())
        asset = assets[0]
        self.assertEqual("shot-1", asset["id"])
        self.assertEqual("集計画面", asset["alt"])
        self.assertEqual("実際の集計画面", asset["caption"])
        self.assertEqual("assets/shot-1.png", asset["src"])
        self.assertIn(H.PNG_DATA_URI, [v for v in asset.values() if isinstance(v, str)],
                      "data URI 本体が assets へ保持されていない: %r" % asset)

    def test_attachment_is_restored_with_data_uri(self):
        """AC-C20-06: filename / mime / fallback_hint と data URI 本体。"""
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro", parts=H.part_b12())]))
        self.assert_exit(res, 0)
        attachments = self.read_out().get("attachments") or []
        self.assertEqual(1, len(attachments))
        att = attachments[0]
        self.assertEqual("template.xlsx", att["filename"])
        self.assertEqual(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", att["mime"])
        self.assertEqual("開けない場合は共有ドライブの同名ファイルを使う", att["fallback_hint"])
        self.assertIn(H.XLSX_DATA_URI, [v for v in att.values() if isinstance(v, str)],
                      "data URI 本体が attachments へ保持されていない: %r" % att)

    def test_large_data_uri_is_kept_verbatim(self):
        """巨大 data URI は上限を設けず文字列としてそのまま保持する。"""
        big = "data:image/png;base64," + "A" * 400000
        html = H.full_html(sections=[H.section_html(
            "intro",
            parts='  <figure data-hb-part="IMG" data-hb-part-id="big"'
                  ' data-hb-media-record="big" data-hb-asset-id="big"'
                  ' data-hb-asset-alt="大きな画像"><img src="%s"></figure>\n'
                  % big)])
        res, _ = self.extract(html)
        self.assert_exit(res, 0)
        asset = self.read_out()["assets"][0]
        self.assertIn(big, [v for v in asset.values() if isinstance(v, str)],
                      "巨大 data URI が切り詰められている")

    def test_diagram_structure_comes_from_data_attribute(self):
        """生成 SVG からではなく data-hb-diagram-data から構造データを戻す。"""
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro",
                                                                   parts=H.part_diagram())]))
        self.assert_exit(res, 0)
        diagrams = self.read_out().get("diagrams") or []
        self.assertEqual(1, len(diagrams))
        self.assertEqual("flow-1", diagrams[0]["id"])
        self.assertEqual("linear-flow", diagrams[0]["pattern"])
        self.assertEqual(H.DIAGRAM_DATA, diagrams[0]["data"])

    def test_svg_geometry_is_not_reverse_engineered(self):
        """SVG の座標が構成データへ混ざらない (data 属性だけが復元路)。"""
        res, _ = self.extract(H.full_html(sections=[H.section_html("intro",
                                                                   parts=H.part_diagram())]))
        self.assert_exit(res, 0)
        text = self.out_text()
        self.assertNotIn("viewBox", text)
        self.assertNotIn("<rect", text)

    def test_script_and_style_bodies_are_discarded(self):
        """<script> / <style> の中身は構成データの一部ではない。"""
        res, _ = self.extract()
        self.assert_exit(res, 0)
        text = self.out_text()
        self.assertNotIn("console.log", text)
        self.assertNotIn("pop-header{", text)


if __name__ == "__main__":
    unittest.main()

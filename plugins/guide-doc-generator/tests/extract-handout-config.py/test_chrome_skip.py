# -*- coding: utf-8 -*-
"""生成 chrome の読み飛ばし (algorithm A3 / AC-C20-07 / failure_modes)。

data-hb-generated="true" の部分木を丸ごと切り落とすこと、マーカーが無い場合も
クラス名で二重防御が効くことを固定する。ここが崩れると round-trip は必ず落ちるが、
diff からは「何が構成データか」の定義の問題だと追いにくいため、独立して固定する。
"""

import unittest

import _harness as H


class GeneratedChromeIsSkipped(H.C20TestCase):

    def setUp(self):
        super().setUp()
        self.res, self.html = self.extract(H.full_html(chrome=True))
        self.assertTrue(self.out.exists(), "--out が書かれていないので chrome の混入を検査できない")
        self.cfg = self.read_out()

    def test_exit0_with_chrome_present(self):
        self.assert_exit(self.res, 0)

    def test_structural_parts_never_appear(self):
        """AC-C20-07: B01 / B02 が復元結果に現れない。"""
        ids = [p["part"] for s in self.cfg.get("sections", []) for p in s.get("parts", [])]
        self.assertNotIn("B01", ids)
        self.assertNotIn("B02", ids)

    def test_document_scope_catalog_parts_never_appear(self):
        """カタログの section_scope=document の部品は逆抽出対象外 (id 直書きしない)。"""
        document_scope = {p["id"] for p in self.parts_catalog()["parts"]
                          if p.get("section_scope") == "document"}
        self.assertTrue(document_scope, "カタログに document スコープ部品が無い")
        ids = {p["part"] for s in self.cfg.get("sections", []) for p in s.get("parts", [])}
        self.assertEqual(set(), ids & document_scope)

    def test_chrome_text_does_not_leak_into_config(self):
        text = self.out_text()
        for token in ("生成フッタ", "ヒーロー枠", "ナビ", "i-check"):
            self.assertNotIn(token, text, "chrome 由来のテキストが混入している: %s" % token)

    def test_chrome_lead_line_does_not_override_section_lead_line(self):
        """hero 内のダミー data-hb-field を拾わない (部分木ごと読み飛ばすため)。"""
        self.assertNotEqual("生成されたヒーロー内のダミー", self.cfg.get("lead_line"))
        for section in self.cfg.get("sections", []):
            self.assertNotEqual("生成されたヒーロー内のダミー", section.get("lead_line"))

    def test_memo_keys_do_not_become_parts(self):
        text = self.out_text()
        self.assertNotIn("memo-1", text)

    def test_lightbox_image_does_not_become_an_asset(self):
        """chrome 内の <img> は assets へ入らない。"""
        assets = self.cfg.get("assets") or []
        self.assertEqual([], assets, "chrome の画像が assets に混入している: %r" % assets)

    def test_part_count_equals_marked_parts_only(self):
        fields = self.summary(self.res)
        self.assertEqual("6", fields["parts"],
                         "chrome を数えている疑い (期待 6 = B03/TEXT/B11/B09/B15/B16)")


class UnmarkedChromeIsSkippedByClassName(H.C20TestCase):
    """A3 の二重防御: data-hb-generated が無くてもクラス名で切り落とす。"""

    def setUp(self):
        super().setUp()
        self.res, self.html = self.extract(H.full_html(chrome=False, unmarked_chrome=True))
        self.assertTrue(self.out.exists(), "--out が書かれていないので chrome の混入を検査できない")
        self.cfg = self.read_out()

    def test_pop_header_is_skipped(self):
        self.assertNotIn("導入</a>", self.out_text())

    def test_pop_bottom_is_skipped(self):
        self.assertNotIn("生成フッタ", self.out_text())

    def test_memo_ui_is_skipped(self):
        text = self.out_text()
        self.assertNotIn("memo-area", text)
        self.assertNotIn("memo-pane", text)

    def test_unmarked_chrome_is_not_reported_as_heuristic_part(self):
        """読み飛ばした chrome を TEXT 部品として拾わない。"""
        ids = [p["id"] for s in self.cfg.get("sections", []) for p in s.get("parts", [])]
        self.assertEqual(len(set(ids)), len(ids), "部品 id が重複している: %r" % ids)
        self.assertEqual(6, len(ids), "chrome を部品として拾っている: %r" % ids)


if __name__ == "__main__":
    unittest.main()

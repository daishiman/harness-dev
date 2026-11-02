# -*- coding: utf-8 -*-
"""C20 が前提コネクタを id だけで復元することの受入テスト (R25/REQ-9)。

schemas/ROUNDTRIP-CONTRACT.md の /prerequisite_connectors 裁定が定める形は
`[{"connector": <data-hb-key>, "note": <but 書き>}]` であり、**表示ラベルを
読み戻さない**。読み戻すと表示ラベルが構成データ側にも生まれ、
config/handout-vocabulary.json と 2 つの出所ができる。語彙を直したときに
構成データ側の古い表記が残る状態は、まさにその 2 出所が作る事故である。

ここで固定するのは 3 点:
  1. 印を持つ項目から id が復元される。
  2. 可視テキスト (ラベル) はどのキーにも入らない。
  3. but 書きは語彙に無い著者記述なので本文から復元される。
"""

import unittest

import _harness as H


def connector_list(items):
    """C11 build_hero が出す形の HTML 断片。印は li 側にある。"""
    out = ['<ul class="meta-list prerequisite-connectors" aria-label="前提となる外部接続">']
    for cid, label, note in items:
        note_html = ('<span class="connector-note" '
                     'data-hb-field="prerequisite_connector_note">%s</span>' % note) if note else ""
        out.append('<li class="connector" data-hb-field="prerequisite_connector" '
                   'data-hb-key="%s"><span class="connector-label">%s</span>%s</li>'
                   % (cid, label, note_html))
    out.append("</ul>\n")
    return "".join(out)


THREE = [("google-drive", "Google Drive", None),
         ("onedrive", "OneDrive", None),
         ("kintone", "kintone", "レコード読み取りのみ")]


class ConnectorRestore(H.C20TestCase):

    def setUp(self):
        super().setUp()
        self.res, _ = self.extract(H.full_html(extra_body=connector_list(THREE)))

    def test_exit0(self):
        self.assert_exit(self.res, 0)

    def test_ids_are_restored_in_document_order(self):
        cfg = self.read_out()
        self.assertEqual(["google-drive", "onedrive", "kintone"],
                         [e["connector"] for e in cfg["prerequisite_connectors"]])

    def test_display_label_is_not_read_back(self):
        cfg = self.read_out()
        for entry in cfg["prerequisite_connectors"]:
            self.assertLessEqual(set(entry), {"connector", "note"},
                                 "connector / note 以外のキーが復元されている: %r" % entry)
            for value in entry.values():
                self.assertNotIn("Google Drive", value)
                self.assertNotIn("OneDrive", value)

    def test_note_is_restored_from_text(self):
        cfg = self.read_out()
        entries = cfg["prerequisite_connectors"]
        self.assertNotIn("note", entries[0], "but 書きの無い項目に note を捏造している")
        self.assertEqual("レコード読み取りのみ", entries[2]["note"])

    def test_note_does_not_bleed_across_entries(self):
        """but 書きは項目の内側からだけ引く。文書全体を走査すると隣の項目を拾う。"""
        cfg = self.read_out()
        self.assertNotIn("note", cfg["prerequisite_connectors"][1])


class ConnectorAbsence(H.C20TestCase):

    def test_absent_list_does_not_produce_a_null_key(self):
        """任意配列。書いていない資料へ null を置くと round-trip が差分になる。"""
        res, _ = self.extract()
        self.assert_exit(res, 0)
        cfg = self.read_out()
        self.assertNotIn("prerequisite_connectors", cfg)

    def test_entry_without_key_is_reported_as_a_gap(self):
        html = H.full_html(extra_body=(
            '<ul class="prerequisite-connectors">'
            '<li data-hb-field="prerequisite_connector">Google Drive</li></ul>\n'))
        res, _ = self.extract(html)
        cfg = self.read_out()
        self.assertEqual([], cfg.get("prerequisite_connectors"),
                         "id を運ぶ印が無い項目を、本文から id を推測して復元している")


if __name__ == "__main__":
    unittest.main()

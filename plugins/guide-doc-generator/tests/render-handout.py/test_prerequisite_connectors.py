"""C11 が前提コネクタ (R25/REQ-9) を冒頭カードへ描くことの受入テスト。

契約の要点は「表示ラベルの出所を 1 つに保つ」ことにある。構成データが持つのは
id だけで、読者に見える表記は config/handout-vocabulary.json#connectors にしか
無い。したがって:

  - 描くのは語彙のラベルであって id ではない (id を描いて取り繕わない)。
  - 語彙に引けない id は描画で握り潰さず異常終了させる。C12 が
    E-CONNECTOR-UNKNOWN で先に止めるので、ここへ到達するのは正本と構成データが
    食い違った状態であり、黙って何かを描くと食い違いが見えなくなる。
  - 印 (data-hb-key) は id を運ぶ。C20 はこれだけを読み戻す
    (schemas/ROUNDTRIP-CONTRACT.md /prerequisite_connectors)。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


FIELD = "prerequisite_connector"
NOTE_FIELD = "prerequisite_connector_note"

THREE = [{"connector": "google-drive"}, {"connector": "onedrive"}, {"connector": "kintone"}]


class TestConnectorCard(unittest.TestCase):

    def render(self, connectors):
        cfg = H.base_config()
        if connectors is not None:
            cfg["prerequisite_connectors"] = connectors
        with tempfile.TemporaryDirectory() as tmp:
            res, html_text, _ = H.render_html(tmp, cfg)
        return res, html_text

    def test_three_user_specified_connectors_are_rendered(self):
        res, html_text = self.render(THREE)
        self.assertEqual(0, res.returncode, res.stderr)
        els = H.elements_with(html_text, "data-hb-field", FIELD)
        self.assertEqual(3, len(els), "前提コネクタが 3 件描かれていない")
        self.assertEqual(["google-drive", "onedrive", "kintone"],
                         [el.attrs.get("data-hb-key") for el in els])

    def test_display_label_comes_from_vocabulary_not_the_id(self):
        res, html_text = self.render(THREE)
        self.assertEqual(0, res.returncode, res.stderr)
        texts = [el.text.strip() for el in H.elements_with(html_text, "data-hb-field", FIELD)]
        self.assertEqual(["Google Drive", "OneDrive", "kintone"], texts)
        # id をそのまま可視テキストへ落としていないこと
        self.assertNotIn("google-drive", " ".join(texts))

    def test_absent_field_renders_no_list(self):
        res, html_text = self.render(None)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertEqual([], H.elements_with(html_text, "data-hb-field", FIELD))
        # CSS 規則は常に出る (テーマは構成データに依らない)。見るのは本文側の要素。
        lists = [el for el in H.parse(html_text)
                 if "prerequisite-connectors" in (el.attrs.get("class") or "")]
        self.assertEqual([], lists)

    def test_note_is_rendered_as_its_own_field(self):
        res, html_text = self.render([{"connector": "kintone", "note": "読み取りのみ"}])
        self.assertEqual(0, res.returncode, res.stderr)
        notes = [el.text.strip()
                 for el in H.elements_with(html_text, "data-hb-field", NOTE_FIELD)]
        self.assertEqual(["読み取りのみ"], notes)

    def test_unknown_id_is_not_papered_over(self):
        res, _ = self.render([{"connector": "dropbox"}])
        self.assertNotEqual(0, res.returncode,
                            "語彙に無い id で正常終了した (id を描いて取り繕っている疑い)")
        self.assertIn("dropbox", res.stderr)

    def test_label_does_not_leak_into_a_second_canon(self):
        """script 側に表示ラベルを焼いていないこと (語彙正本と 2 つの出所を作らない)。"""
        src = H.source_text()
        for label in ("Google Drive", "OneDrive", "kintone"):
            self.assertNotIn(label, src,
                             "render-handout.py に表示ラベル %r が焼かれている" % label)


class TestConnectorListIsAChipRow(unittest.TestCase):
    """R11/R9: 前提は「読む文」でなく「並ぶ札」。行頭記号付きの長い箇条書きに
    しないことを、生成 CSS の宣言として固定する。数値そのものは検査しない
    (見た目の調整で動く) が、list-style を外して横に並べる意図は固定する。
    """

    def test_connector_list_is_flex_without_bullets(self):
        cfg = H.base_config()
        cfg["prerequisite_connectors"] = THREE
        with tempfile.TemporaryDirectory() as tmp:
            res, html_text, _ = H.render_html(tmp, cfg)
        self.assertEqual(0, res.returncode, res.stderr)
        head, _, tail = html_text.partition(".prerequisite-connectors {")
        self.assertTrue(tail, "前提コネクタ用の CSS 規則が無い")
        block = tail.split("}")[0]
        self.assertIn("list-style: none", block)
        self.assertIn("display: flex", block)
        self.assertIn("flex-wrap: wrap", block)


if __name__ == "__main__":
    unittest.main()

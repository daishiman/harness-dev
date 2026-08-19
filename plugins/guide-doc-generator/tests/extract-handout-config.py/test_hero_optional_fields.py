"""冒頭の任意項目 lead / goal_chips の読み戻し (P05-x-56 / 利用者要求 R9)。

この 2 項目は「冒頭の散文を伸ばす代わりに置く受け皿」であり、著者が書いた内容
そのものである。よって round-trip の対象になる。ここで固定するのは 3 つ。

1. マーカーが刻まれていれば値が (配列は文書順のまま) 戻ること。
2. 書かれていない資料では、キーを作らず・警告も出さないこと。
   任意項目の不在は欠落ではないので、gap として数えると「完全に復元できた」
   資料が毎回警告を吐き、警告が見なくてよいものへ退化する。
3. 裁定表 (schemas/ROUNDTRIP-CONTRACT.md) にこの 2 項目の裁定が載っていること。
   表にもテストにも載っていない項目は、免除を宣言しないまま黙って対象外になる。
"""

import json
import re
import unittest

import _harness as H

LEAD = "この資料は、月次の締め作業を 1 人で回せる状態を目指す"
CHIPS = ("自力で実施できる", "詰まった箇所を言語化できる", "次の担当へ引き継げる")

CONTRACT = H.SRC_PLUGIN_ROOT / "schemas" / "ROUNDTRIP-CONTRACT.md"


def hero_markup():
    """C11 が build_hero で出す形と同じ刻み方の fixture。"""
    return ('<p data-hb-field="lead">%s</p>\n' % LEAD) + "".join(
        '<span data-hb-field="goal_chips">%s</span>\n' % chip for chip in CHIPS)


def with_hero(html):
    """文書スコープ (最初の section より前) へ冒頭の 2 項目を差し込む。"""
    anchor = '<p data-hb-field="purpose">'
    assert anchor in html, "fixture の形が変わっている"
    return html.replace(anchor, hero_markup() + anchor, 1)


class HeroOptionalFieldsRoundTrip(H.C20TestCase):

    def extracted(self, html):
        res, _ = self.extract(html)
        self.assert_exit(res, 0)
        return json.loads(self.out_text())

    def test_lead_is_restored_from_its_marker(self):
        config = self.extracted(with_hero(H.full_html()))
        self.assertEqual(LEAD, config["lead"])

    def test_goal_chips_are_restored_in_document_order(self):
        config = self.extracted(with_hero(H.full_html()))
        self.assertEqual(list(CHIPS), config["goal_chips"])

    def test_reordering_the_chips_changes_the_restored_order(self):
        """順序が本当に文書から来ていること (たまたま一致していないこと) の対照。"""
        html = with_hero(H.full_html())
        first, last = CHIPS[0], CHIPS[-1]
        swapped = html.replace(first, "\x00").replace(last, first).replace("\x00", last)
        self.assertEqual([last, *CHIPS[1:-1], first],
                         self.extracted(swapped)["goal_chips"])

    def test_an_absent_optional_field_does_not_become_a_null(self):
        """書いていない項目に null を置くと『null と書いた』になる。

        置いた場合、読み戻した構成データは schema の型検査 (string / array) で
        落ち、round-trip が成立しなくなる。
        """
        config = self.extracted(H.full_html())
        for field in ("lead", "goal_chips"):
            self.assertNotIn(field, config, "不在の任意項目にキーが作られている")

    def test_an_absent_optional_field_is_not_reported_as_a_gap(self):
        res, _ = self.extract(H.full_html())
        self.assert_exit(res, 0)
        for field in ("lead", "goal_chips"):
            self.assertNotIn("/" + field, res.stderr,
                             "任意項目の不在が欠落として報告されている")


class TheAdjudicationIsDeclared(H.C20TestCase):
    """裁定表に載せる。載せずに読めるようにすると、契約の外で挙動だけが増える。"""

    def adjudications(self):
        text = CONTRACT.read_text(encoding="utf-8")
        block = re.search(r"```json\n(.*?\"adjudications\".*?)\n```", text, re.S)
        self.assertIsNotNone(block, "裁定表の fenced JSON が見つからない")
        return json.loads(block.group(1))["adjudications"]

    def test_both_fields_are_adjudicated_as_marker(self):
        by_pointer = {a["pointer"]: a for a in self.adjudications()}
        for pointer in ("/lead", "/goal_chips"):
            self.assertIn(pointer, by_pointer, "裁定表に載っていない")
            self.assertEqual("marker", by_pointer[pointer]["decision"])


if __name__ == "__main__":
    unittest.main()

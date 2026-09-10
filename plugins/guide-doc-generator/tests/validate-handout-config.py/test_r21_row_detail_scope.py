# -*- coding: utf-8 -*-
"""R21 C46 の適用範囲 — forbid_row_detail が見ていない 2 つの穴 (意図的に赤)。

**本ファイルは現行実装に対して赤で固定される。P05-x-64 の受け皿であり、
緑にするには validate-handout-config.py の修正が要る (本ノードの write_scope 外)。**

criterion (config/handout-sections.json の当該 section_kind の説明文):
「大きな流れだけを列挙し、個々の手順・操作の詳細は書かない (R21 C46)」

出荷実装 (validate-handout-config.py:1081-1087) はこれを 2 重に狭めている:

1. 走査する器が rows だけ。直上 :1075 の max_items 検査は ("rows", "cards") の
   両方を走査するのに、forbid_row_detail 検査は :1082 で rows 部品だけを引く。
   同一 section_kind に掛かる隣り合う 2 検査で走査対象が非対称であり、冒頭概観
   をカード部品で組むと検査が 1 件も走らない。
2. 見るフィールドが row.sub だけ (:1087 の `row.get("sub") is not None`)。
   行本文そのものへ操作手順を書けば素通りする。criterion が禁じているのは
   「詳細を書くこと」であって「sub というフィールドを使うこと」ではない。

section_kind の slug も件数もここへ書かない。対象は
config/handout-sections.json から forbid_row_detail 属性で引き当てる。
"""

import unittest

import _harness as H

# 操作手順そのもの (criterion が冒頭に置くことを禁じている文)。
PROCEDURE = "画面右上のメニューから設定を開き、詳細タブへ移動して保存ボタンを押す"
OVERVIEW = "全体像をつかむ"


class RowDetailScopeTestCase(H.C12TestCase):

    def forbidding_kind(self):
        """forbid_row_detail=true を持つ section_kind の slug を正本から引く。"""
        kinds = [
            k for k in self.sections_catalog().get("section_kinds", [])
            if k.get("forbid_row_detail")
        ]
        self.assertTrue(kinds, "forbid_row_detail を持つ section_kind が正本に無い")
        return kinds[0]["slug"]

    def rows_config(self, rows):
        cfg = H.valid_config()
        cfg["sections"] = [
            H.section("flow", section_kind=self.forbidding_kind(),
                      parts=[{"part": "B03", "id": "flow-steps", "data": {"rows": rows}}]),
            H.section("practice", id="practice"),
        ]
        return H.with_visual_floor(cfg)

    def cards_config(self, bodies):
        cfg = H.valid_config()
        cards = [{"label": "手順 %d" % (i + 1), "body": body, "tone": "neutral"}
                 for i, body in enumerate(bodies)]
        cfg["sections"] = [
            H.section("flow", section_kind=self.forbidding_kind(),
                      parts=[{"part": "B04", "id": "flow-cards", "data": {"cards": cards}}]),
            H.section("practice", id="practice"),
        ]
        return H.with_visual_floor(cfg)


class RowDetailIsNotOnlyTheSubField(RowDetailScopeTestCase):
    """穴 2: 行本文へ手順を書いても素通りする。"""

    def test_procedure_in_row_text_is_rejected(self):
        rows = [{"num": 1, "text": PROCEDURE, "sub": None},
                {"num": 2, "text": OVERVIEW, "sub": None}]
        res, _ = self.validate(self.rows_config(rows))
        self.assert_fails_with(res, "E-SECTIONKIND-ROWDETAIL", "/sections/0")

    def test_overview_only_rows_still_pass(self):
        """穴を塞いだあとも、大きな流れだけの行は通る (過剰検出の回帰)。"""
        rows = [{"num": 1, "text": OVERVIEW, "sub": None},
                {"num": 2, "text": "実際に動かす", "sub": None}]
        res, _ = self.validate(self.rows_config(rows))
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-SECTIONKIND-ROWDETAIL")


class RowDetailScopeCoversCards(RowDetailScopeTestCase):
    """穴 1: 器をカード部品に替えると検査が 1 件も走らない。"""

    def test_procedure_in_card_body_is_rejected(self):
        res, _ = self.validate(self.cards_config([PROCEDURE, OVERVIEW]))
        self.assert_fails_with(res, "E-SECTIONKIND-ROWDETAIL", "/sections/0")

    def test_overview_only_cards_still_pass(self):
        res, _ = self.validate(self.cards_config([OVERVIEW, "実際に動かす"]))
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-SECTIONKIND-ROWDETAIL")

    def test_scope_is_symmetric_with_max_items(self):
        """同一 section_kind に掛かる 2 検査が同じ器の集合を見ること。

        max_items 側は rows と cards の両方を走査する。片方だけを見る検査が
        隣にあると、器を替えるだけで規則が消える。
        """
        res, _ = self.validate(self.cards_config([PROCEDURE, OVERVIEW]))
        self.assert_exit(res, 1)


class ForbidRowDetailStaysCatalogDriven(RowDetailScopeTestCase):
    """属性を外せば規則も消える (規則の可変点はデータファイル側)。"""

    def test_removing_the_attribute_allows_detail(self):
        slug = self.forbidding_kind()
        rows = [{"num": 1, "text": PROCEDURE, "sub": None},
                {"num": 2, "text": OVERVIEW, "sub": None}]
        cfg = self.rows_config(rows)
        self.patch_sections_catalog(slug, forbid_row_detail=None)
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "E-SECTIONKIND-ROWDETAIL")


if __name__ == "__main__":
    unittest.main()

"""カタログ部品のうちレンダリング検査が無かった 4 部品を固定する (P04-x-09)。

`schemas/handout-config.schema.json` の `$defs.part_data` はカタログ全部品の
data 形を定義するが、そのうち B04 トリオカード / B06 二択グリッド /
B07 特徴カード / B14 フローは `tests/render-handout.py/` 配下のどのテストにも
出現せず、「描画結果が正しいか」を見るテストが 1 件も無かった。
test_parts_catalog.py の動的テストは data-hb-part ルートの有無しか見ないため、
中身を落とした実装でも緑のまま通過してしまう。ここでその穴を塞ぐ。

期待値の出所 (発明しない):
- 部品 id と block.type の対応: config/handout-parts.json の parts[]
- 各 block の data 形: plugin-plans/guide-doc-generator/briefs/script-brief-C11.json
  の block_to_component_map と schemas/handout-config.schema.json $defs.part_data
- 属性語彙: script-brief-C11.json html_attribute_contract

件数・id 集合はすべて schema / catalog / fixture から導出し、テスト本文へ
リテラルで焼かない (焼くと正本が動いてもテストが気づかない)。
"""

import json
import re
import tempfile
import unittest

import _harness as H

SCHEMA_PATH = H.PLUGIN_ROOT / "schemas" / "handout-config.schema.json"


# --------------------------------------------------------------------------
# 正本からの導出ヘルパ
# --------------------------------------------------------------------------


def require_schema():
    if not SCHEMA_PATH.is_file():
        raise AssertionError("構成データ schema が未実装: %s (owner=C12)" % SCHEMA_PATH)


def schema_part_ids():
    """$defs.part_data のキーのうち部品定義であるものの id 集合。

    件数リテラルを書かず、「x_placement を持つ dict である」という
    schema 側の形から導出する (description のような散文キーを除く)。
    """
    require_schema()
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        schema = json.load(fh)
    part_data = schema["$defs"]["part_data"]
    return {
        key for key, value in part_data.items()
        if isinstance(value, dict) and "x_placement" in value
    }


def part_id_for_block(block_type):
    """block.type からカタログ経由で部品 id を引く (id を第 2 の名簿にしない)。"""
    hits = [p["id"] for p in H.catalog_parts() if p["data_block_type"] == block_type]
    if len(hits) != 1:
        raise AssertionError(
            "block.type=%r に対応する部品がカタログで一意でない: %r" % (block_type, hits)
        )
    return hits[0]


def descendants(element):
    out = []
    stack = list(element.children)
    while stack:
        el = stack.pop()
        out.append(el)
        stack.extend(el.children)
    return out


def attr_values(element):
    return [v for v in element.attrs.values() if isinstance(v, str)]


class BlockRenderCase(unittest.TestCase):
    """1 block だけを持つ構成データを描画し、その部品ルートを取り出す土台。"""

    BLOCK_TYPE = None

    @classmethod
    def setUpClass(cls):
        if cls.BLOCK_TYPE is None:
            raise unittest.SkipTest("土台クラス")
        cls.block = H.BLOCK_FIXTURES[cls.BLOCK_TYPE]
        cls.part_id = part_id_for_block(cls.BLOCK_TYPE)
        cls._td = tempfile.TemporaryDirectory()
        cls.result, cls.html, _ = H.render_html(cls._td.name, H.config_with_block(cls.block))

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_td", None) is not None:
            cls._td.cleanup()

    def setUp(self):
        self.assertEqual(
            0, self.result.returncode,
            "block.type=%s の描画に失敗: %s" % (self.BLOCK_TYPE, self.result.stderr),
        )

    def root(self):
        roots = H.part_elements(self.html, self.part_id)
        self.assertEqual(
            1, len(roots),
            "data-hb-part=%s のルート要素がちょうど 1 つ出ていない (%d 件)"
            % (self.part_id, len(roots)),
        )
        return roots[0]

    def assert_repeat_keys(self, keys):
        """html_attribute_contract: 反復要素は data-hb-key を持つ。"""
        rendered = {
            el.get("data-hb-key")
            for el in descendants(self.root())
            if "data-hb-key" in el.attrs
        }
        missing = [k for k in keys if k not in rendered]
        self.assertEqual(
            [], missing,
            "%s の反復要素へ data-hb-key が出ていない: %r (出ているのは %r)"
            % (self.part_id, missing, sorted(rendered)),
        )


# --------------------------------------------------------------------------
# B04 トリオカード (block.type=trio)
# --------------------------------------------------------------------------


class TrioCardRenderingTest(BlockRenderCase):
    """block_to_component_map: cards[2-3].{tone:"today"|"rest", title, body, icon?} / 「tone でトーン差」。"""

    BLOCK_TYPE = "trio"

    def test_root_uses_the_catalog_part_id(self):
        """B04: 部品ルートの data-hb-part はカタログ id (block.type からの導出と一致)。"""
        self.assertEqual(self.part_id, self.root().get("data-hb-part"))
        self.assertTrue(self.root().get("data-hb-part-id"), "セクション内一意の部品 id が無い")

    def test_every_card_text_is_rendered(self):
        """B04: 全カードの title と body が本文へ落ちる (1 枚でも欠けたら赤)。"""
        for card in self.block["cards"]:
            self.assertIn(card["title"], self.html, "カード見出しが描画されていない")
            self.assertIn(card["body"], self.html, "カード本文が描画されていない")

    def test_cards_carry_repeat_keys(self):
        """B04: 各カードは data-hb-key を持つ反復要素として出る。"""
        self.assert_repeat_keys([c["key"] for c in self.block["cards"]])

    def test_card_count_matches_the_input(self):
        """B04: 描画されるカード数は入力 cards 件数と一致する (件数はリテラルにしない)。"""
        keyed = [el for el in descendants(self.root()) if "data-hb-key" in el.attrs]
        self.assertEqual(len(self.block["cards"]), len(keyed))

    def test_tone_is_visible_in_the_markup(self):
        """B04: 「tone でトーン差」を機械可読に追える (class か data 属性へ tone 値が出る)。

        属性名は C11 契約が固定していないため、カード要素の属性値のどこかに
        tone 値が現れることだけを見る (符号化先の名前は実装の自由)。
        """
        keyed = {
            el.get("data-hb-key"): el
            for el in descendants(self.root())
            if "data-hb-key" in el.attrs
        }
        for card in self.block["cards"]:
            el = keyed.get(card["key"])
            self.assertIsNotNone(el, "カード %s の要素が無い" % card["key"])
            self.assertTrue(
                any(card["tone"] in value for value in attr_values(el)),
                "カード %s の tone=%s がマークアップから読めない: %r"
                % (card["key"], card["tone"], el.attrs),
            )


# --------------------------------------------------------------------------
# B06 二択グリッド (block.type=versus)
# --------------------------------------------------------------------------


class VersusGridRenderingTest(BlockRenderCase):
    """block_to_component_map: left/right.{label, tone, bullets[]} / 『A ならこっち / B ならこっち』の型。"""

    BLOCK_TYPE = "versus"

    def sides(self):
        return [self.block["left"], self.block["right"]]

    def test_root_uses_the_catalog_part_id(self):
        """B06: 部品ルートの data-hb-part はカタログ id。"""
        self.assertEqual(self.part_id, self.root().get("data-hb-part"))

    def test_both_sides_render_label_and_bullets(self):
        """B06: 左右のラベルと全 bullet が描画される (片側だけ出す経路を許さない)。"""
        for side in self.sides():
            self.assertIn(side["label"], self.html, "側のラベルが描画されていない")
            for bullet in side["bullets"]:
                self.assertIn(bullet, self.html, "bullet が描画されていない")

    def test_both_sides_carry_repeat_keys(self):
        """B06: 左右は data-hb-key を持つ反復要素として出る。"""
        self.assert_repeat_keys([side["key"] for side in self.sides()])

    def test_left_is_rendered_before_right(self):
        """B06: 二択の並びは入力順 (left → right) で決定論的。"""
        left_at = self.html.index(self.block["left"]["label"])
        right_at = self.html.index(self.block["right"]["label"])
        self.assertLess(left_at, right_at, "left が right より後に出ている")


# --------------------------------------------------------------------------
# B07 特徴カード (block.type=features)
# --------------------------------------------------------------------------


class FeatureCardRenderingTest(BlockRenderCase):
    """block_to_component_map: cards[2-3].{title, body, icon?, footnote?} / footnote は出典枠でリンクにしない。"""

    BLOCK_TYPE = "features"

    def test_root_uses_the_catalog_part_id(self):
        """B07: 部品ルートの data-hb-part はカタログ id。"""
        self.assertEqual(self.part_id, self.root().get("data-hb-part"))

    def test_every_card_text_is_rendered(self):
        """B07: 全カードの title / body が描画される。"""
        for card in self.block["cards"]:
            self.assertIn(card["title"], self.html)
            self.assertIn(card["body"], self.html)

    def test_footnote_is_rendered_as_text(self):
        """B07: footnote (出典・参考の表記枠) を落とさない。"""
        for card in self.block["cards"]:
            if card.get("footnote"):
                self.assertIn(card["footnote"], self.html, "footnote が描画されていない")

    def test_footnote_is_not_turned_into_a_link(self):
        """B07: 自己完結性の制約により部品内へリンクを作らない (出所はテキスト表記に留める)。"""
        anchors = [el for el in descendants(self.root()) if el.tag == "a"]
        self.assertEqual([], [el.attrs for el in anchors], "B07 の内側に <a> が出ている")

    def test_cards_carry_repeat_keys(self):
        """B07: 各カードは data-hb-key を持つ反復要素として出る。"""
        self.assert_repeat_keys([c["key"] for c in self.block["cards"]])


# --------------------------------------------------------------------------
# B14 フロー (block.type=flow)
# --------------------------------------------------------------------------


class FlowRenderingTest(BlockRenderCase):
    """block_to_component_map: 「C14 の pattern=flow へ委譲。フロー表現をレンダラ側で二重に持たない」。"""

    BLOCK_TYPE = "flow"

    def test_root_uses_the_catalog_part_id(self):
        """B14: 部品ルートの data-hb-part はカタログ id。"""
        self.assertEqual(self.part_id, self.root().get("data-hb-part"))

    def test_every_step_label_is_rendered(self):
        """B14: 全ステップのラベルが描画される。"""
        for step in self.block["steps"]:
            self.assertIn(step["label"], self.html, "フローのステップが描画されていない")

    def test_flow_is_delegated_to_inline_svg(self):
        """B14: 図解は inline SVG として部品内へ埋め込まれる (C14 委譲)。"""
        svgs = [el for el in descendants(self.root()) if el.tag == "svg"]
        self.assertTrue(svgs, "B14 の内側に inline SVG が無い (C14 pattern=flow への委譲が落ちている)")

    def test_inline_svg_is_classified(self):
        """B14: html_attribute_contract 「全 svg/symbol に data-hb-kind」。"""
        for el in descendants(self.root()):
            if el.tag in ("svg", "symbol"):
                self.assertIn(
                    el.get("data-hb-kind"), ("icon", "mascot", "decor", "figure"),
                    "data-hb-kind が無い/語彙外: %r" % (el.attrs,),
                )

    def test_diagram_pattern_is_exposed(self):
        """B14: 図解ラッパへ data-hb-diagram-pattern が block.pattern の素値で出る。"""
        patterns = {
            el.get("data-hb-diagram-pattern")
            for el in [self.root()] + descendants(self.root())
            if "data-hb-diagram-pattern" in el.attrs
        }
        self.assertIn(
            self.block["pattern"], patterns,
            "B14 の図解 pattern が生成物から読めない (出ているのは %r)" % sorted(patterns),
        )


# --------------------------------------------------------------------------
# 網羅のメタ検査
# --------------------------------------------------------------------------


class SchemaPartCoverageTest(unittest.TestCase):
    """「カタログ部品ごとのレンダリングテストが存在する」を機械的に固定する。"""

    def test_schema_and_catalog_declare_the_same_part_ids(self):
        """$defs.part_data のキー集合とカタログ id 集合の一致 (二重名簿の乖離を検出)。"""
        self.assertEqual(
            {p["id"] for p in H.catalog_parts()}, schema_part_ids(),
            "schema $defs.part_data とカタログで部品 id 集合が食い違っている",
        )

    def test_every_schema_part_id_appears_in_the_test_suite(self):
        """全 part id がテスト本文へ出現する (未検査の部品を残さない)。"""
        uncovered = {}
        for part_id in sorted(schema_part_ids()):
            pattern = re.compile(r"\b%s\b" % re.escape(part_id))
            files = [
                path.name
                for path in sorted(H.TESTS_DIR.glob("*.py"))
                if pattern.search(path.read_text(encoding="utf-8"))
            ]
            if not files:
                uncovered[part_id] = files
        self.assertEqual(
            {}, uncovered,
            "レンダリングテストが 1 件も無い部品: %r" % sorted(uncovered),
        )


if __name__ == "__main__":
    unittest.main()

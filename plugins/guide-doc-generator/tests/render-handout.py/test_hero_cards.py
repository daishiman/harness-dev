"""C11 が冒頭をカードとして描くことの受入テスト (P05-x-40 / 利用者要求 R3・R9)。

固定するのは 4 点。

1. **ゴールが最初**: 冒頭の並び順の正本は
   config/handout-visual-policy.json#opening.hero_card_fields.order であり、
   その先頭が goal である。描画順も検査 (C22 NAR-01) もこの 1 か所から引く。
2. **散文でなくカード**: 旧描画は p.hero-purpose 等の 3 行で、ラベルが行頭の
   inline span だったため 1 つの段落の塊に見えた。.hero-card-grid > .hero-card
   に置き換え、ラベルをカードの見出しへ格上げする。
3. **印は本文側**: data-hb-field はカードの外枠でなく本文の要素に付く。外枠へ
   付けると見出し語 (「目的」等) がマーカーの可視テキストへ混ざり、NAR-02 の
   『可視テキスト == 構成データ』と C20 の読み戻しが同時に壊れる。
4. **日本語を script へ焼かない**: 見出し語の出所は
   config/handout-vocabulary.json だけ。順序の正本と表記の正本を分けてあるので、
   片方を直したつもりでもう片方が動くことがない。
"""

import json
import tempfile
import unittest

import _harness as H

VISUAL_POLICY = H.PLUGIN_ROOT / "config" / "handout-visual-policy.json"
VOCABULARY = H.PLUGIN_ROOT / "config" / "handout-vocabulary.json"


def canon_order():
    policy = json.loads(VISUAL_POLICY.read_text(encoding="utf-8"))
    return list(policy["opening"]["hero_card_fields"]["order"])


def vocabulary_group(group):
    doc = json.loads(VOCABULARY.read_text(encoding="utf-8"))
    return {e["field"]: e["label"] for e in doc[group]["entries"]}


def render(**over):
    cfg = H.base_config(**over)
    with tempfile.TemporaryDirectory() as tmp:
        res, html_text, _ = H.render_html(tmp, cfg)
    return res, html_text, cfg


def cards(html_text):
    return [el for el in H.parse(html_text)
            if "hero-card" == (el.attrs.get("class") or "")]


class GoalComesFirst(unittest.TestCase):

    def test_the_canon_puts_goal_first(self):
        """利用者要求 R3。正本そのものを固定する。"""
        self.assertEqual("goal", canon_order()[0])

    def test_cards_are_rendered_in_canon_order(self):
        res, html_text, _ = render()
        self.assertEqual(0, res.returncode, res.stderr)
        rendered = [el.attrs.get("data-hb-card-field") for el in cards(html_text)]
        self.assertEqual(canon_order(), rendered)

    def test_the_goal_appears_before_purpose_in_document_order(self):
        res, html_text, _ = render()
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertLess(html_text.index('data-hb-field="goal"'),
                        html_text.index('data-hb-field="purpose"'))

    def test_order_is_not_baked_into_the_script(self):
        """script が順序の第 2 の出所になっていないこと。

        走査するのは「今の正本の並び」を綴った literal だけにする。旧順序の
        3 語は必須キーの集合 (順序を持たない) にも現れるので、その出現まで
        禁じると集合と順列を取り違えた検査になる。
        """
        source = H.source_text()
        baked = ", ".join('"%s"' % name for name in canon_order())
        self.assertNotIn(baked, source, "並び順が script へ焼かれている")
        self.assertIn("hero_card_order", source)


class CardsInsteadOfProse(unittest.TestCase):

    def test_the_old_prose_paragraphs_are_gone(self):
        res, html_text, _ = render()
        self.assertEqual(0, res.returncode, res.stderr)
        for klass in ("hero-purpose", "hero-background", "hero-goal", "hero-label"):
            self.assertNotIn(klass, html_text, "旧い散文の器が残っている: " + klass)

    def test_each_field_gets_its_own_card_with_a_heading(self):
        res, html_text, _ = render()
        self.assertEqual(0, res.returncode, res.stderr)
        labels = vocabulary_group("hero_card_labels")
        found = cards(html_text)
        self.assertEqual(len(canon_order()), len(found))
        for el in found:
            field = el.attrs.get("data-hb-card-field")
            self.assertIn(labels[field], el.text)

    def test_the_grid_wraps_the_cards(self):
        res, html_text, _ = render()
        self.assertEqual(0, res.returncode, res.stderr)
        grids = [el for el in H.parse(html_text)
                 if "hero-card-grid" == (el.attrs.get("class") or "")]
        self.assertEqual(1, len(grids))

    def test_the_grid_flows_in_one_column(self):
        """冒頭は 1 列で流す (2026-08-25 利用者要求)。

        横並びにすると 1 列が 220px まで細り、1 行 10 字前後で折り返して語の
        途中が切れる。読みにくさの出所は文の長さでなく列の細さだったので、
        列数を幅へ追従させるのではなく 1 列に固定する。狭い画面で崩れないことは
        カード 1 枚が縦積み (札が本文の 1 段上) であることが担う。
        """
        res, html_text, _ = render()
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertIn(".hero-card-grid {\n  display: flex;\n"
                      "  flex-direction: column;", html_text)
        self.assertNotIn("repeat(auto-fit", html_text.split(".hero-card {")[0]
                         .split(".hero-card-grid {")[-1])

    def test_the_label_sits_above_the_body(self):
        """札は本文の左でなく 1 段上 (2026-08-26 利用者要求)。

        冒頭には見出し付きの塊が 2 種類ある (hero-card と hero-list)。札を左へ
        置いていたのはカード側だけで、本文の左端がカードごとに違って見えていた。
        列を作る宣言がカード側に残っていないことで、2 種類の入れ物が同じ形に
        なっていることを測る。
        """
        res, html_text, _ = render()
        self.assertEqual(0, res.returncode, res.stderr)
        card_css = html_text.split(".hero-card {")[-1].split("}")[0]
        self.assertNotIn("grid-template-columns", card_css)
        self.assertNotIn("display: grid", card_css)


class MarkersStayOnTheBody(unittest.TestCase):
    """見出し語がマーカーの可視テキストへ混ざらないこと。"""

    def test_field_text_equals_the_config_value(self):
        res, html_text, cfg = render()
        self.assertEqual(0, res.returncode, res.stderr)
        for field in canon_order():
            self.assertEqual([cfg[field]], H.field_texts(html_text, field))

    def test_the_heading_word_is_not_inside_the_marker(self):
        res, html_text, _ = render()
        labels = vocabulary_group("hero_card_labels")
        for field in canon_order():
            for el in H.field_elements(html_text, field):
                self.assertNotIn(labels[field], el.text)


class ListsCarryHeadings(unittest.TestCase):
    """見出しの無い ul を冒頭へ積まない (利用者要求 R9)。"""

    def test_each_hero_list_is_named(self):
        res, html_text, _ = render(
            focus_theme=["最初の 1 回"],
            must_remember=["保存先を決める"],
            no_need_to_remember=["内部の仕組み"])
        self.assertEqual(0, res.returncode, res.stderr)
        headings = vocabulary_group("hero_list_headings")
        named = {el.attrs.get("data-hb-list-field") for el in H.parse(html_text)
                 if "hero-list" == (el.attrs.get("class") or "")}
        for field in ("focus_theme", "must_remember", "no_need_to_remember"):
            self.assertIn(field, named)
            self.assertIn(headings[field], html_text)

    def test_headings_are_not_baked_into_the_script(self):
        source = H.source_text()
        for label in vocabulary_group("hero_list_headings").values():
            self.assertNotIn(label, source, "見出し語が script へ焼かれている")

    def test_both_label_groups_are_read_from_the_vocabulary(self):
        """見出し語の出所が語彙正本の 2 群であること。

        カードの見出し語 (目的・背景) は 2 字の一般語で、注釈や CSS の
        コメントにも当然現れる。素の部分一致で「焼かれていない」を主張すると
        注釈を書いた瞬間に赤くなる検査になるので、ここは配線の側を見る。
        描画された文字列が語彙正本と一致することは
        CardsInsteadOfProse.test_each_field_gets_its_own_card_with_a_heading
        が押さえている。
        """
        source = H.source_text()
        for group in ("hero_card_labels", "hero_list_headings"):
            self.assertIn('vocabulary_labels("%s"' % group, source)


if __name__ == "__main__":
    unittest.main()

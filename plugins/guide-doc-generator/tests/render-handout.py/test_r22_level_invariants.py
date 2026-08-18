"""R22 C65 — detail_level を変えても C44 の共有の型が保持される。

goal-spec C65: 同一の構成データから detail_level だけを変えて生成したとき、
sticky 目次 / 日付表記 / 目的・背景・ゴール / 抽象↔具体の往復 / アイコン規約 /
単一ファイル自己完結 が全水準で保持され、差分は各ブロックの記述量と
任意詳細部の展開・畳み込みに限定される。

C11 は本文を切り詰めない (記述量を動かすのは C12 --normalize) ため、
同一の正規化済み構成データからの 3 生成物は、粒度属性と open 属性を除いて
バイト一致でなければならない。これが「差分が限定される」の最も強い形。
"""

import copy
import re
import tempfile
import unittest

import _harness as H

DETAIL_LEVELS = ("overview", "standard", "detailed")

DATE_PATTERN = re.compile(r"^\d{4}/\d{2}/\d{2}$")

# 生成物間で変わってよい属性 (これ以外の差分は C44 の共有の型を壊す)
# data-hb-open は open と同じ「展開状態」の事実を逆抽出用に運ぶ印なので、
# 素の open 属性だけ落として data-hb-open を残すと、同じ 1 つの差分を
# 2 か所で数えることになる。
VARIABLE_ATTR_PATTERN = re.compile(
    r'\s*data-hb-(?:detail-level|evidence-depth|text-limit|open)="[^"]*"'
)
OPEN_ATTR_PATTERN = re.compile(r"(<details\b[^>]*?)\s+open(?=[\s/>])")


def level_config(detail_level, open_flag=None):
    """detail_level だけが異なる正規化済み構成データ。

    open_flag を与えると、C12 が水準に応じて立てる B10 の open を模す。
    """
    tail = copy.deepcopy(H.BLOCK_FIXTURES["accordion"])
    tail["id"] = "blk-text-cont"
    tail["items"] = [
        {
            "key": "ac1",
            "summary": "詳しい説明 (続き)",
            "body": "折り畳まれた残余の本文をここに置く。",
            "open": bool(open_flag) if open_flag is not None else False,
        }
    ]
    sections = [
        H.base_section(1, blocks=[copy.deepcopy(H.BLOCK_FIXTURES["text"]), tail]),
        H.base_section(2, blocks=[copy.deepcopy(H.BLOCK_FIXTURES["steps"])]),
    ]
    cfg = H.base_config(sections=sections)
    cfg["detail_level"] = detail_level
    cfg["evidence_depth"] = "cited"
    cfg["provenance"] = dict(cfg.get("provenance") or {})
    cfg["provenance"]["detail_level_source"] = "explicit"
    cfg["provenance"]["evidence_depth_source"] = "preset-default"
    return cfg


def render(tc, cfg):
    with tempfile.TemporaryDirectory() as td:
        res, html_text, _ = H.render_html(td, cfg)
    tc.assertEqual(0, res.returncode, res.stderr)
    return html_text


def canonical(html_text):
    """粒度属性と open 属性を落とした比較用の正規形。"""
    stripped = VARIABLE_ATTR_PATTERN.sub("", html_text)
    return OPEN_ATTR_PATTERN.sub(r"\1", stripped)


class SharedTypeAcrossLevelsTest(unittest.TestCase):
    """C44 の共有の型が全水準で保持されること。"""

    def _html(self, level):
        return render(self, level_config(level))

    def test_sticky_nav_anchors_match_sections_at_every_level(self):
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                html_text = self._html(level)
                navs = H.part_elements(html_text, "B01")
                self.assertTrue(navs, "sticky 目次 (B01) が無い")
                hrefs = [
                    el.get("href")
                    for el in H.parse(html_text)
                    if el.tag == "a" and (el.get("href") or "").startswith("#")
                ]
                section_ids = [
                    el.get("id") for el in H.parse(html_text) if el.tag == "section"
                ]
                self.assertTrue(section_ids, "section が 1 件も無い")
                for sid in section_ids:
                    self.assertIn("#" + sid, hrefs, "nav に %s へのアンカーが無い" % sid)

    def test_date_is_rendered_in_yyyy_mm_dd_at_every_level(self):
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                texts = H.field_texts(self._html(level), "date")
                self.assertTrue(texts, "日付が描画されていない")
                for text in texts:
                    self.assertRegex(text, DATE_PATTERN)

    def test_purpose_background_goal_are_rendered_at_every_level(self):
        for level in DETAIL_LEVELS:
            html_text = self._html(level)
            for field in ("purpose", "background", "goal"):
                with self.subTest(detail_level=level, field=field):
                    self.assertTrue(
                        H.field_elements(html_text, field),
                        "%s が描画されていない" % field,
                    )

    def test_abstract_to_concrete_round_trip_at_every_level(self):
        """抽象 1 行 (lead_line) → 具体部品 → 判断軸 1 行 (judgment_axis) の反復。"""
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                html_text = self._html(level)
                sections = [el for el in H.parse(html_text) if el.tag == "section"]
                self.assertTrue(sections)
                self.assertEqual(
                    len(sections), len(H.field_elements(html_text, "lead_line"))
                )
                self.assertEqual(
                    len(sections), len(H.field_elements(html_text, "judgment_axis"))
                )

    def test_icon_convention_at_every_level(self):
        """全 svg / symbol に data-hb-kind が付き、絵文字を持たない。"""
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                html_text = self._html(level)
                svgs = [el for el in H.parse(html_text) if el.tag in ("svg", "symbol")]
                self.assertTrue(svgs, "アイコンが 1 つも無い")
                for el in svgs:
                    self.assertIn("data-hb-kind", el.attrs)

    def test_single_file_self_contained_at_every_level(self):
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                html_text = self._html(level)
                self.assertNotIn("http://", html_text)
                self.assertNotIn("https://", html_text)
                for el in H.parse(html_text):
                    src = el.get("src")
                    if src is not None:
                        self.assertTrue(
                            src.startswith("data:"),
                            "外部参照が残っている: %r" % src,
                        )


class LevelDiffIsBoundedTest(unittest.TestCase):
    """差分が粒度属性と任意詳細部の展開状態に限定されること。"""

    def test_identical_config_differs_only_in_granularity_attributes(self):
        htmls = {level: render(self, level_config(level)) for level in DETAIL_LEVELS}
        base = canonical(htmls["standard"])
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                self.assertEqual(base, canonical(htmls[level]))

    def test_open_state_is_the_only_other_difference(self):
        """C12 が水準に応じて立てた open を含めても、差分はそこに限られる。"""
        htmls = {
            "overview": render(self, level_config("overview", open_flag=False)),
            "standard": render(self, level_config("standard", open_flag=False)),
            "detailed": render(self, level_config("detailed", open_flag=True)),
        }
        base = canonical(htmls["standard"])
        for level, html_text in htmls.items():
            with self.subTest(detail_level=level):
                self.assertEqual(base, canonical(html_text))

    def test_the_granularity_attributes_actually_differ(self):
        """比較の正規化が差分を消しているだけではないことの見張り。"""
        htmls = {level: render(self, level_config(level)) for level in DETAIL_LEVELS}
        values = {
            level: [
                el.get("data-hb-detail-level")
                for el in H.parse(html_text)
                if el.tag == "html"
            ]
            for level, html_text in htmls.items()
        }
        self.assertEqual({"overview": ["overview"], "standard": ["standard"],
                          "detailed": ["detailed"]}, values)

    def test_section_and_part_structure_is_identical_across_levels(self):
        shapes = {}
        for level in DETAIL_LEVELS:
            html_text = render(self, level_config(level))
            shapes[level] = [
                (el.get("data-hb-part"), el.get("data-hb-part-id"))
                for el in H.parse(html_text)
                if "data-hb-part" in el.attrs
            ]
        self.assertEqual(shapes["overview"], shapes["standard"])
        self.assertEqual(shapes["overview"], shapes["detailed"])

    def test_body_text_is_not_modulated_by_the_renderer(self):
        """記述量を動かすのは C12。C11 は水準で本文を増減しない。"""
        body = H.BLOCK_FIXTURES["text"]["body"]
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                self.assertIn(body, render(self, level_config(level)))


if __name__ == "__main__":
    unittest.main()

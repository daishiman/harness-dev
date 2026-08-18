"""部品カタログ駆動のレンダリング検査 (AC-C11-5 / AC-C11-19 / P03 Y-05)。

テストメソッドは config/handout-parts.json から動的生成する。
テスト側にも part id を列挙しないので、カタログに部品を足すと
「fixture が無い」「レンダリングされない」として自動的に赤になる。
"""

import tempfile
import unittest

import _harness as H

# 部品ごとの追加検査 (block_to_component_map の notes 由来)。
# 網羅の判定はカタログ側が行うので、この表はカタログの部分集合でよい。
EXTRA_ASSERTIONS = {
    "B01": lambda t, html, el: t.assertTrue(H.elements_with(html, "data-hb-nav-goal")),
    "B02": lambda t, html, el: t.assertTrue(H.field_elements(html, "purpose")),
    "B03": lambda t, html, el: (
        t.assertTrue(H.elements_with(html, "data-hb-time")),
        t.assertTrue([e for e in H.parse(html) if "step-num" in e.classes()]),
    ),
    "B05": lambda t, html, el: (
        t.assertTrue([e for e in H.parse(html) if "table-wrap" in e.classes()]),
        t.assertTrue([e for e in H.parse(html) if "hl-cell" in e.classes()]),
    ),
    "B08": lambda t, html, el: t.assertTrue(H.elements_with(html, "data-hb-detail")),
    "B09": lambda t, html, el: t.assertIn('type="checkbox"', html),
    "B10": lambda t, html, el: t.assertTrue([e for e in H.parse(html) if e.tag == "details"]),
    "B11": lambda t, html, el: t.assertTrue([e for e in H.parse(html) if e.tag == "pre"]),
    "B12": lambda t, html, el: (
        t.assertTrue(H.elements_with(html, "data-hb-filename")),
        t.assertTrue([e for e in H.parse(html) if "dl-hint" in e.classes()]),
    ),
    "B13": lambda t, html, el: t.assertIn('role="tablist"', html),
    "B15": lambda t, html, el: t.assertEqual("true", el.get("data-hb-single")),
    "B16": lambda t, html, el: (
        t.assertTrue(H.elements_with(html, "data-hb-owner")),
        t.assertTrue(H.elements_with(html, "data-hb-due")),
    ),
    "B17": lambda t, html, el: [
        t.assertIn(text, html)
        for text in ("画面右上のボタンを押す", "一覧が表示される", "権限設定を見直す")
    ],
    "IMG": lambda t, html, el: (
        t.assertTrue(H.elements_with(html, "data-hb-asset-id")),
        t.assertTrue(H.part_elements(html, "lightbox")),
    ),
    "DIAGRAM": lambda t, html, el: t.assertTrue(H.elements_with(html, "data-hb-diagram-pattern")),
    "TEXT": lambda t, html, el: t.assertIn("地の文", html),
}


class PartRenderingTest(unittest.TestCase):
    """カタログの全部品に 1 メソッドずつ対応する (メソッドは末尾で動的に注入)。"""

    def _render_part(self, part):
        block_type = part["data_block_type"]
        if block_type is None:
            config = H.base_config()
        else:
            fixture = H.BLOCK_FIXTURES.get(block_type)
            self.assertIsNotNone(
                fixture,
                "カタログの部品 %s (block.type=%s) に対応する fixture がテストに無い"
                % (part["id"], block_type),
            )
            config = H.config_with_block(fixture)
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, config)
        self.assertEqual(0, res.returncode, "部品 %s の生成に失敗: %s" % (part["id"], res.stderr))
        roots = H.part_elements(html_text, part["id"])
        self.assertTrue(roots, "data-hb-part=%s のルート要素が出ていない" % part["id"])
        extra = EXTRA_ASSERTIONS.get(part["id"])
        if extra is not None:
            extra(self, html_text, roots[0])


class CatalogCoverageTest(unittest.TestCase):
    def test_every_catalog_part_has_a_dedicated_test_method(self):
        """AC-C11-5: カタログに部品を足したのにテストが無い状態は網羅検査で FAIL する。"""
        expected = {"test_part_%s" % p["id"] for p in H.catalog_parts()}
        actual = {name for name in dir(PartRenderingTest) if name.startswith("test_part_")}
        self.assertEqual(set(), expected - actual, "テストの無い部品: %r" % (expected - actual))

    def test_every_content_part_has_a_block_fixture(self):
        missing = [
            p["id"] for p in H.catalog_parts()
            if p["data_block_type"] and p["data_block_type"] not in H.BLOCK_FIXTURES
        ]
        self.assertEqual([], missing, "fixture の無い部品: %r" % missing)

    def test_catalog_is_sorted_and_well_formed(self):
        """schema: id 昇順に並べる (決定論)。各エントリは 6 フィールドを持つ。"""
        parts = H.catalog_parts()
        ids = [p["id"] for p in parts]
        self.assertEqual(sorted(ids), ids, "カタログは id 昇順で並べる")
        self.assertEqual(len(ids), len(set(ids)))
        for part in parts:
            for field in ("id", "name_ja", "kind", "section_scope", "data_block_type", "since", "source"):
                self.assertIn(field, part)
            self.assertIn(part["kind"], ("structural", "content", "media"))
            self.assertIn(part["section_scope"], ("in-section", "document"))
            self.assertIn(part["since"], ("v1", "plan"))


class CatalogModuleApiTest(unittest.TestCase):
    """consumer_contract: C12 / C18 / C23 が使う module API を C11 が公開する。"""

    def _load_module(self):
        import importlib.util

        H.require_script()
        spec = importlib.util.spec_from_file_location("hb_parts", str(H.SCRIPT))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_load_parts_catalog_returns_catalog_entries(self):
        module = self._load_module()
        loaded = module.load_parts_catalog()
        self.assertEqual(
            [p["id"] for p in H.catalog_parts()],
            [p["id"] for p in loaded["parts"]],
        )

    def test_is_known_part_uses_the_catalog(self):
        module = self._load_module()
        for part in H.catalog_parts():
            self.assertTrue(module.is_known_part(part["id"]))
        self.assertFalse(module.is_known_part("B99"))

    def test_in_section_parts_uses_section_scope_predicate(self):
        """C18 LANG-06 の『具体部品』述語は section_scope=in-section で決まる。"""
        module = self._load_module()
        expected = [p["id"] for p in H.catalog_parts() if p["section_scope"] == "in-section"]
        self.assertEqual(expected, [p["id"] if isinstance(p, dict) else p for p in module.in_section_parts()])


class SingleVocabularyTest(unittest.TestCase):
    def test_part_ids_are_not_enumerated_outside_the_catalog(self):
        """AC-C11-19 / Y-05: catalog 以外に part id のリテラル列挙が 0 件。

        走査対象は H.scannable_sources() が決める (実行されるコードと、指示として
        読み込まれるテキスト)。散文の注釈は語彙になり得ないので対象外。

        走査範囲そのものが正しいか (scripts/*.json が抜け道になっていないか) は
        test_scan_scope.py が反例注入で別途固定する。
        """
        H.require_script()
        offenders = H.enumerated_part_id_offenders()
        self.assertEqual([], offenders, "部品 id のリテラル列挙:\n%s" % "\n".join(offenders))


def _attach_part_tests():
    try:
        parts = H.catalog_parts()
    except AssertionError as exc:
        message = str(exc)

        def missing_catalog(self):
            self.fail(message)

        setattr(PartRenderingTest, "test_part_catalog_is_present", missing_catalog)
        return

    for part in parts:
        def make(part=part):
            def test(self):
                self._render_part(part)

            test.__doc__ = "AC-C11-5: %s %s のレンダリング" % (part["id"], part["name_ja"])
            return test

        setattr(PartRenderingTest, "test_part_%s" % part["id"], make())


_attach_part_tests()


if __name__ == "__main__":
    unittest.main()

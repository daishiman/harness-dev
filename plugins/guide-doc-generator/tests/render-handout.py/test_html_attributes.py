"""機械可読属性の契約 (script-brief-C11.json html_attribute_contract / algorithm 22b)。

この語彙は C16 / C17 / C18 / C20 / C22 の検査アンカーであり、欠落は下流ゲートの全項目 FAIL を招く。
"""

import re
import tempfile
import unittest

import _harness as H

FULL_CONFIG_BLOCKS = [
    H.BLOCK_FIXTURES["steps"],
    H.BLOCK_FIXTURES["image"],
    H.BLOCK_FIXTURES["diagram"],
    H.BLOCK_FIXTURES["download"],
    H.BLOCK_FIXTURES["map"],
    H.BLOCK_FIXTURES["chips"],
    H.BLOCK_FIXTURES["action-items"],
    H.BLOCK_FIXTURES["table"],
]


def full_config():
    return H.base_config(
        sections=[H.base_section(1, blocks=FULL_CONFIG_BLOCKS)],
        attachments=[H.BLOCK_FIXTURES["download"]["attachments"][0]],
    )


class AttributeContractTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        cls.result, cls.html, cls.out_path = H.render_html(cls._td.name, full_config())
        if cls.result.returncode != 0:
            raise AssertionError("正常系 fixture の生成に失敗: %s" % cls.result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls._td.cleanup()

    def html_element(self):
        for el in H.parse(self.html):
            if el.tag == "html":
                return el
        raise AssertionError("<html> 要素が無い")


class DocumentLevelAttributeTest(AttributeContractTestBase):
    def test_html_element_carries_document_metadata(self):
        """<html> の文書メタ (schema-version / doc-type / subject-slug / theme)。"""
        cfg = full_config()
        el = self.html_element()
        self.assertEqual(cfg["schema_version"], el.get("data-hb-schema-version"))
        self.assertEqual(cfg["doc_type"], el.get("data-hb-doc-type"))
        self.assertEqual(cfg["subject_slug"], el.get("data-hb-subject-slug"))
        self.assertTrue(el.get("data-hb-theme"))

    def test_non_rendered_required_meta_is_exposed_as_attributes(self):
        """本文へ描画されない必須メタは <html> の属性で運ぶ。"""
        cfg = full_config()
        el = self.html_element()
        self.assertEqual(cfg["reader"], el.get("data-hb-meta-reader"))
        self.assertEqual(cfg["prior_knowledge_level"], el.get("data-hb-meta-knowledge"))
        self.assertEqual(cfg["essential_problem"], el.get("data-hb-meta-problem"))


class PartAttributeTest(AttributeContractTestBase):
    def test_every_part_root_has_part_and_part_id(self):
        """全部品ルートに data-hb-part と セクション内一意の data-hb-part-id。"""
        roots = [el for el in H.parse(self.html) if "data-hb-part" in el.attrs]
        self.assertTrue(roots)
        structural = set(H.load_parts_catalog()["non_part_structure_markers"]["values"])
        part_ids = []
        for el in roots:
            if el.get("data-hb-part") in structural:
                continue
            self.assertTrue(el.get("data-hb-part-id"), "部品ルートに data-hb-part-id が無い: %r" % el)
            part_ids.append(el.get("data-hb-part-id"))
        self.assertEqual(len(part_ids), len(set(part_ids)), "data-hb-part-id はセクション内一意")

    def test_part_values_come_from_catalog_or_structure_markers(self):
        """data-hb-part の値はカタログ id か non_part_structure_markers のいずれか。"""
        catalog = H.load_parts_catalog()
        allowed = {p["id"] for p in catalog["parts"]}
        allowed |= set(catalog["non_part_structure_markers"]["values"])
        seen = {el.get("data-hb-part") for el in H.elements_with(self.html, "data-hb-part")}
        self.assertEqual(set(), seen - allowed, "契約外の data-hb-part 値: %r" % (seen - allowed))

    def test_all_svg_and_symbol_have_kind(self):
        """全 svg / symbol に data-hb-kind (未分類は C16 SC-06 が違反に計上する)。"""
        for el in H.parse(self.html):
            if el.tag in ("svg", "symbol"):
                self.assertIn(el.get("data-hb-kind"), ("icon", "mascot", "decor", "figure"),
                              "data-hb-kind が無い/語彙外: %r" % el)

    def test_generated_chrome_is_marked(self):
        """nav / hero / sprite / footer / メモ UI / lightbox に data-hb-generated=true。"""
        generated = H.elements_with(self.html, "data-hb-generated")
        self.assertTrue(generated)
        for el in generated:
            self.assertEqual("true", el.get("data-hb-generated"))
        marked_parts = {el.get("data-hb-part") for el in generated}
        for expected in ("B01", "B02", "lightbox", "memo-global"):
            self.assertIn(expected, marked_parts)


class AttributeNamespaceTest(AttributeContractTestBase):
    def test_no_data_attribute_outside_hb_namespace(self):
        """AC-C11-18 / X-03: data- で始まり data-hb- で始まらない属性が 0 件。"""
        offenders = set()
        for el in H.parse(self.html):
            for name in el.attrs:
                if name.startswith("data-") and not name.startswith("data-hb-"):
                    offenders.add((el.tag, name))
        self.assertEqual(set(), offenders, "prefix なしの独自 data 属性: %r" % offenders)

    def test_retired_attribute_names_are_absent(self):
        """統合前の旧語彙 (data-part / data-role / data-goal 等) は出力しない。"""
        for retired in ("data-part=", "data-role=", "data-kind=", "data-title=",
                        "data-detail=", "data-single=", "data-goal="):
            self.assertNotIn(retired, self.html, "旧語彙 %s が残っている" % retired)


class FieldAttributeTest(AttributeContractTestBase):
    def test_document_fields_are_rendered_with_field_attribute(self):
        """data-hb-field の値は C12 config_schema のキー名に一致する。"""
        cfg = full_config()
        for field in ("title", "date", "purpose", "background", "goal", "duration"):
            with self.subTest(field=field):
                texts = H.field_texts(self.html, field)
                self.assertTrue(texts, "data-hb-field=%s が描画されていない" % field)

    def test_document_goal_and_section_goal_use_distinct_field_names(self):
        """資料全体ゴールは goal、セクションゴールは section_goal (取り違え防止)。"""
        self.assertTrue(H.field_elements(self.html, "goal"))
        self.assertTrue(H.field_elements(self.html, "section_goal"))
        self.assertNotEqual(
            H.field_elements(self.html, "goal")[0], H.field_elements(self.html, "section_goal")[0]
        )

    def test_section_fields_are_rendered(self):
        for field in ("section_goal", "section_duration", "lead_line", "judgment_axis"):
            with self.subTest(field=field):
                self.assertTrue(H.field_elements(self.html, field), "data-hb-field=%s が無い" % field)


class DatePillTest(AttributeContractTestBase):
    def test_date_pill_matches_normalized_date_verbatim(self):
        """AC-C11-6 / checklist C33,C34: date-pill は構成データの date と同値・無変換。"""
        pills = H.field_elements(self.html, "date")
        self.assertEqual(1, len(pills), "date-pill は 1 個だけ")
        text = pills[0].text.strip()
        self.assertRegex(text, r"^\d{4}/\d{2}/\d{2}$")
        self.assertEqual(H.DEFAULT_DATE, text)
        self.assertIn("date-pill", " ".join(pills[0].classes()))

    def test_date_is_not_reformatted(self):
        """ゼロ埋め補正も書式変換も行わない (正本は C12)。"""
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, H.base_config(date="2026/12/31"))
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertEqual(["2026/12/31"], H.field_texts(html_text, "date"))


class NavGoalReferenceTest(AttributeContractTestBase):
    def test_nav_links_carry_goal_in_attributes_not_in_label(self):
        """block_to_component_map B01 / algorithm 14: nav 本体は簡潔・ゴールは補助属性。"""
        cfg = full_config()
        links = [el for el in H.elements_with(self.html, "data-hb-nav-goal")]
        self.assertEqual(len(cfg["sections"]), len(links))
        for link, section in zip(links, cfg["sections"]):
            self.assertEqual("a", link.tag)
            self.assertEqual("#" + section["id"], link.get("href"))
            self.assertEqual(section["goal"], link.get("data-hb-nav-goal"))
            self.assertEqual(section["goal"], link.get("title"), "title 属性へも同値を出す")
            self.assertEqual("goal-%s" % section["id"], link.get("aria-describedby"))
            self.assertNotIn(section["goal"], link.text, "nav ラベルへゴール全文を複製しない")

    def test_aria_describedby_target_is_the_section_goal_chip(self):
        """参照先 id=goal-s{n} はセクション冒頭のゴールチップそのもの (文言を複製しない)。"""
        cfg = full_config()
        by_id = {el.get("id"): el for el in H.parse(self.html) if el.get("id")}
        for section in cfg["sections"]:
            target = by_id.get("goal-%s" % section["id"])
            self.assertIsNotNone(target, "id=goal-%s の要素が無い" % section["id"])
            self.assertEqual("section_goal", target.get("data-hb-field"))
            self.assertEqual(section["goal"], target.text.strip())


class SectionAttributeTest(AttributeContractTestBase):
    def test_section_elements_carry_kind_and_role_and_ties(self):
        cfg = full_config()
        sections = [el for el in H.parse(self.html) if el.tag == "section"]
        self.assertEqual(len(cfg["sections"]), len(sections))
        for el, src in zip(sections, cfg["sections"]):
            self.assertEqual(src["section_kind"], el.get("data-hb-section-kind"))
            self.assertEqual(src["role"], el.get("data-hb-section-role"))
            self.assertEqual(src["ties_to"], el.get("data-hb-ties-to"))
            self.assertEqual("section", el.get("data-hb-part"))


class RepeatingElementAttributeTest(AttributeContractTestBase):
    def test_repeating_elements_carry_key(self):
        """行・カード・チップ・タブ等の反復要素に data-hb-key。"""
        keys = [el.get("data-hb-key") for el in H.elements_with(self.html, "data-hb-key")]
        self.assertTrue(keys)
        for key in keys:
            self.assertTrue(key.strip())

    def test_action_item_rows_carry_owner_and_due(self):
        rows = H.elements_with(self.html, "data-hb-owner")
        self.assertTrue(rows, "B16 の各行に data-hb-owner が無い")
        for el in rows:
            self.assertTrue(el.get("data-hb-due"))

    def test_step_rows_carry_time(self):
        self.assertTrue(H.elements_with(self.html, "data-hb-time"), "B03 の行に data-hb-time が無い")

    def test_map_items_carry_title_and_detail(self):
        items = H.elements_with(self.html, "data-hb-title")
        self.assertTrue(items)
        for el in items:
            self.assertIn("data-hb-detail", el.attrs)

    def test_chips_single_flag(self):
        chips = H.part_elements(self.html, "B15")
        self.assertTrue(chips)
        self.assertEqual("true", chips[0].get("data-hb-single"))


class AssetAttributeTest(AttributeContractTestBase):
    def test_image_carries_asset_attributes(self):
        imgs = H.elements_with(self.html, "data-hb-asset-id")
        self.assertTrue(imgs)
        for el in imgs:
            self.assertTrue(el.get("data-hb-asset-alt"))
            self.assertIn("data-hb-asset-caption", el.attrs)
            self.assertIn("data-hb-src", el.attrs)

    def test_attachment_link_carries_download_attributes(self):
        links = H.elements_with(self.html, "data-hb-attachment-id")
        self.assertTrue(links, "<a download> に data-hb-attachment-id が無い")
        for el in links:
            self.assertTrue(el.get("data-hb-filename"))
            self.assertTrue(el.get("data-hb-mime"))
            self.assertIn("data-hb-fallback-hint", el.attrs)

    def test_diagram_wrapper_carries_diagram_attributes(self):
        wrappers = H.elements_with(self.html, "data-hb-diagram-id")
        self.assertTrue(wrappers)
        for el in wrappers:
            self.assertTrue(el.get("data-hb-diagram-pattern"))
            self.assertTrue(el.get("data-hb-diagram-data"))

    def test_aux_buttons_are_marked_for_a11y_exclusion(self):
        """data-hb-part-role=aux は C17 A11Y-01 の唯一の除外口。"""
        for el in H.elements_with(self.html, "data-hb-part-role"):
            self.assertEqual("aux", el.get("data-hb-part-role"))


class AttributeContractCoverageTest(AttributeContractTestBase):
    def test_every_attribute_in_the_contract_appears_in_the_script(self):
        """契約に列挙された属性名が 1 つも実装から漏れていない (語彙の写し漏れ検出)。

        ソース文字列だけを見るのでは足りない。部品 data の項目名から属性名を
        導出する経路 (data-hb-<field>) では、属性名そのものは script のどこにも
        literal として現れないため、grep では「実装から消えた」と「導出で出して
        いる」を区別できない。生成物側の語彙も併せて見る — こちらは
        「文字列はあるが出力されない」偽の緑も同時に潰す。
        """
        src = H.source_text()
        names = set()
        for entry in re.findall(r"data-hb-[a-z-]+", src):
            names.add(entry)
        for entry in re.findall(r"data-hb-[a-z-]+", self.html):
            names.add(entry)
        for required in (
            "data-hb-schema-version", "data-hb-doc-type", "data-hb-subject-slug", "data-hb-theme",
            "data-hb-meta-reader", "data-hb-meta-knowledge", "data-hb-meta-problem",
            "data-hb-field", "data-hb-part", "data-hb-part-id", "data-hb-part-role",
            "data-hb-kind", "data-hb-nav-goal", "data-hb-section-kind", "data-hb-key",
            "data-hb-owner", "data-hb-due", "data-hb-time", "data-hb-title", "data-hb-detail",
            "data-hb-single", "data-hb-glossary-term", "data-hb-glossary-plain",
            "data-hb-glossary-scope", "data-hb-asset-id", "data-hb-asset-alt",
            "data-hb-asset-caption", "data-hb-src", "data-hb-attachment-id", "data-hb-filename",
            "data-hb-mime", "data-hb-fallback-hint", "data-hb-diagram-id",
            "data-hb-diagram-pattern", "data-hb-diagram-data", "data-hb-presentation-order",
            "data-hb-presentation-order-source", "data-hb-section-role", "data-hb-ties-to",
            "data-hb-slot", "data-hb-asset-role", "data-hb-attainment-step",
            "data-hb-text-limit", "data-hb-generated",
        ):
            with self.subTest(attribute=required):
                self.assertIn(required, names)


if __name__ == "__main__":
    unittest.main()

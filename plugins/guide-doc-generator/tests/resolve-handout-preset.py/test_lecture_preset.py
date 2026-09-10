"""R21 C53 / C57 — lecture プリセットの必須セクションと必須 document フィールド。

AC-C23-R21-53 / 57。section_kind と part id は C12 / C11 の正本データと突き合わせてから
lecture の preset に対して要求する (この test が section_kind 語彙を再定義しないため)。
"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H

# C53 / C59 が lecture へ必須化した section_kind。値の実在は handout-sections.json で照合する。
LECTURE_REQUIRED_SECTION_KINDS = (
    "flow-overview",
    "capability-explainer",
    "handson",
    "anticipated-qa",
    "dialogue",
)
HANDSON_REQUIRED_PART = "B17"
ANTICIPATED_QA_PART = "B10"
LECTURE_REQUIRED_DOCUMENT_FIELDS = ("must_remember", "no_need_to_remember")


class LectureSectionKindTest(unittest.TestCase):
    """AC-C23-R21-53。"""

    def setUp(self):
        H.require_script(self)

    def _lecture_payload(self):
        proc = H.run(["--purpose", H.LECTURE_SLUG])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        return json.loads(H.out_text(proc))

    def test_required_section_kinds_exist_in_sections_catalog(self):
        """要求する section_kind が C12 の中立データファイルに実在する (語彙の再定義をしない)。"""
        sections = json.loads(H.require_file(self, H.SECTIONS_FILE, "C12").read_text(encoding="utf-8"))
        known = {k["slug"] for k in sections["section_kinds"]}
        for kind in LECTURE_REQUIRED_SECTION_KINDS:
            self.assertIn(kind, known, "section_kind 正本に無い値をテストが要求している")

    def test_lecture_contains_all_required_kinds(self):
        """5 種別が 1 件以上ずつ含まれる。catalog から 1 件でも削れば落ちる。"""
        payload = self._lecture_payload()
        kinds = [s["section_kind"] for s in payload["section_order"]]
        for kind in LECTURE_REQUIRED_SECTION_KINDS:
            with self.subTest(kind=kind):
                self.assertIn(kind, kinds, kinds)

    def test_handson_section_recommends_b17(self):
        """ハンズオン枠の推奨部品に B17 が入る (R21 C53)。"""
        payload = self._lecture_payload()
        handson = [s for s in payload["section_order"] if s["section_kind"] == "handson"]
        self.assertTrue(handson, "handson セクションが無い")
        for section in handson:
            self.assertIn(HANDSON_REQUIRED_PART, section["recommended_parts"], section)

    def test_anticipated_qa_uses_existing_accordion_part(self):
        """先回り Q&A は新部品を作らず既存 B10 を器にする (R21 C53)。"""
        payload = self._lecture_payload()
        qa = [s for s in payload["section_order"] if s["section_kind"] == "anticipated-qa"]
        self.assertTrue(qa, "anticipated-qa セクションが無い")
        for section in qa:
            self.assertIn(ANTICIPATED_QA_PART, section["recommended_parts"], section)

    def test_required_kind_sections_are_required_true(self):
        """必須化した 5 種別のセクションは required=true である (任意枠に退化しない)。"""
        payload = self._lecture_payload()
        for section in payload["section_order"]:
            if section["section_kind"] in LECTURE_REQUIRED_SECTION_KINDS:
                with self.subTest(section=section["id"]):
                    self.assertTrue(section["required"], section)


class LectureRequiredDocumentFieldsTest(unittest.TestCase):
    """AC-C23-R21-57。C23 は必須宣言を渡すだけで、対の強制は C12 が正本。"""

    def setUp(self):
        H.require_script(self)

    def test_lecture_declares_remember_pair(self):
        proc = H.run(["--purpose", H.LECTURE_SLUG])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        fields = json.loads(H.out_text(proc)).get("required_document_fields")
        self.assertIsNotNone(fields, "lecture に required_document_fields が無い")
        for name in LECTURE_REQUIRED_DOCUMENT_FIELDS:
            self.assertIn(name, fields, fields)

    def test_declared_fields_exist_in_config_schema(self):
        """手順 4i: required_document_fields は C12 の document レベルフィールドとして実在する。"""
        schema = json.loads(H.require_file(self, H.SCHEMA_FILE, "C12").read_text(encoding="utf-8"))
        known = set(schema.get("properties", {}).keys())
        for preset in H.presets(self).values():
            for name in preset.get("required_document_fields", []):
                with self.subTest(field=name):
                    self.assertIn(name, known, "schema の properties に無いフィールドを宣言している")

    def test_single_field_of_the_pair_is_not_rejected_by_c23(self):
        """対の強制は C12 の正本。片方だけでも C23 は E-PRESET-REQFIELD-UNKNOWN を出さない。"""
        with tempfile.TemporaryDirectory() as tmp:
            def mutate(catalog):
                catalog["presets"][H.LECTURE_SLUG]["required_document_fields"] = [
                    LECTURE_REQUIRED_DOCUMENT_FIELDS[0]
                ]

            root = H.make_fixture_root(self, Path(tmp), mutate)
            proc = H.run_in_root(root, ["--purpose", H.LECTURE_SLUG])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertNotIn("E-PRESET-REQFIELD-UNKNOWN", H.err_text(proc), H.describe(proc))


class RequiredDocumentFieldsValidationTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_unknown_document_field_is_rejected(self):
        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["required_document_fields"] = ["not_a_document_field"]

        proc = H.run_in_root(H.make_fixture_root(self, self.tmp, mutate), ["--purpose", H.LECTURE_SLUG])
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))
        self.assertIn("E-PRESET-REQFIELD-UNKNOWN", H.err_text(proc), H.describe(proc))

    def test_duplicated_document_field_is_rejected(self):
        def mutate(catalog):
            name = LECTURE_REQUIRED_DOCUMENT_FIELDS[0]
            catalog["presets"][H.LECTURE_SLUG]["required_document_fields"] = [name, name]

        proc = H.run_in_root(H.make_fixture_root(self, self.tmp, mutate), ["--purpose", H.LECTURE_SLUG])
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))


if __name__ == "__main__":
    unittest.main()

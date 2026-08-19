"""--purpose の解決契約 — AC-C23-02 / 05 / 06 / 07。"""

import json
import unittest

import _harness as H


class PurposeCoverageTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_every_vocabulary_slug_resolves(self):
        """AC-C23-02: 全語彙が exit 0 で section_order 1 件以上を返す (C41 / C43)。"""
        for slug in H.slugs(self):
            with self.subTest(slug=slug):
                proc = H.run(["--purpose", slug])
                self.assertEqual(0, proc.returncode, H.describe(proc))
                payload = json.loads(H.out_text(proc))
                self.assertEqual(slug, payload["purpose"], H.describe(proc))
                self.assertGreaterEqual(len(payload["section_order"]), 1, H.describe(proc))

    def test_purpose_output_keys(self):
        """--purpose の出力キー契約 (stdout 契約 + 手順 7)。"""
        slug = H.slugs(self)[0]
        proc = H.run(["--purpose", slug])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        payload = json.loads(H.out_text(proc))
        required = {
            "purpose",
            "label_ja",
            "dir_token",
            "section_order",
            "recommended_parts",
            "notes",
            "catalog_sha256",
            "presentation_order",
            "applied_variant",
        }
        self.assertTrue(required.issubset(set(payload.keys())), sorted(payload.keys()))

    def test_output_matches_catalog_entry(self):
        """出力は catalog の vocabulary エントリ + presets[slug] の合成であり改変しない。"""
        catalog = H.load_catalog(self)
        entry = H.vocabulary_entries(self, catalog)[0]
        preset = H.presets(self, catalog)[entry["slug"]]
        proc = H.run(["--purpose", entry["slug"]])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        payload = json.loads(H.out_text(proc))
        self.assertEqual(entry["label_ja"], payload["label_ja"])
        self.assertEqual(entry["dir_token"], payload["dir_token"])
        self.assertEqual(preset["section_order"], payload["section_order"])
        self.assertEqual(preset["recommended_parts"], payload["recommended_parts"])

    def test_catalog_sha256_matches_file_bytes(self):
        """catalog_sha256 は catalog ファイルのバイト列の sha256 (provenance)。"""
        import hashlib

        expected = hashlib.sha256(H.CATALOG.read_bytes()).hexdigest()
        proc = H.run(["--purpose", H.slugs(self)[0]])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertEqual(expected, json.loads(H.out_text(proc))["catalog_sha256"])


class PurposeTokenNormalizationTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_alias_exact_match_resolves(self):
        """AC-C23-06: alias の完全一致が当該 slug を返す。"""
        entries = [e for e in H.vocabulary_entries(self) if e["aliases"]]
        self.assertTrue(entries, "alias を持つ語彙が 1 件も無い")
        for entry in entries:
            with self.subTest(slug=entry["slug"]):
                proc = H.run(["--purpose", entry["aliases"][0]])
                self.assertEqual(0, proc.returncode, H.describe(proc))
                self.assertEqual(entry["slug"], json.loads(H.out_text(proc))["purpose"])

    def test_case_and_surrounding_space_are_normalized(self):
        """手順 6: NFKC 正規化 → 前後空白除去 → 小文字化。"""
        slug = H.slugs(self)[0]
        proc = H.run(["--purpose", "  " + slug.upper() + "  "])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertEqual(slug, json.loads(H.out_text(proc))["purpose"])

    def test_prefix_match_is_rejected(self):
        """AC-C23-07: 前方一致では解決しない (E-VOCAB-UNKNOWN / exit 1 / stdout 空)。"""
        slug = H.slugs(self)[0]
        proc = H.run(["--purpose", slug[:3]])
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))
        self.assertIn("E-VOCAB-UNKNOWN", H.err_text(proc), H.describe(proc))

    def test_unknown_token_lists_all_vocabulary_on_stderr(self):
        """E-VOCAB-UNKNOWN は全語彙一覧を stderr へ添える。"""
        proc = H.run(["--purpose", "zzz-not-a-purpose"])
        self.assertEqual(1, proc.returncode, H.describe(proc))
        stderr = H.err_text(proc)
        self.assertIn("E-VOCAB-UNKNOWN", stderr, H.describe(proc))
        for slug in H.slugs(self):
            self.assertIn(slug, stderr, H.describe(proc))


class CompositePurposeTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_composite_tokens_are_rejected(self):
        """AC-C23-05: ',' '+' '/' 内部空白のいずれかを含むと E-VOCAB-COMPOSITE / exit 1。"""
        a, b = H.slugs(self)[0], H.slugs(self)[1]
        for token in ("{},{}".format(a, b), "{}+{}".format(a, b), "{}/{}".format(a, b), "{} {}".format(a, b)):
            with self.subTest(token=token):
                proc = H.run(["--purpose", token])
                self.assertEqual(1, proc.returncode, H.describe(proc))
                self.assertEqual("", H.out_text(proc), H.describe(proc))
                self.assertIn("E-VOCAB-COMPOSITE", H.err_text(proc), H.describe(proc))


if __name__ == "__main__":
    unittest.main()

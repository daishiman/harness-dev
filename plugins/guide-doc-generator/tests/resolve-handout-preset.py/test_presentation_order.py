"""R21 C50 — presentation_order_variants は自身の section_order の順列に限る。

AC-C23-R21-50a / 50b / 50c。並べ替えの導出は C12 の CR-PRESENTATION-ORDER が唯一の実行点で、
本 script は確定値を受け取るだけ (導出しないことも 50c で固定する)。
"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class VariantShapeTest(unittest.TestCase):
    """catalog 側の形 (script 実装より前に成立していなければならない契約)。"""

    def test_variants_keys_are_exactly_two(self):
        for slug, preset in H.presets(self).items():
            variants = preset.get("presentation_order_variants")
            if variants is None:
                continue
            with self.subTest(slug=slug):
                self.assertEqual(H.PRESENTATION_ORDER_KEYS, set(variants.keys()))

    def test_variants_are_permutations_of_section_order(self):
        for slug, preset in H.presets(self).items():
            variants = preset.get("presentation_order_variants")
            if variants is None:
                continue
            ids = [s["id"] for s in preset["section_order"]]
            for mode, order in variants.items():
                with self.subTest(slug=slug, mode=mode):
                    self.assertEqual(sorted(ids), sorted(order), "順列でない (増減がある)")
                    self.assertEqual(len(order), len(set(order)), "順列でない (重複がある)")


class PresentationOrderCliTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_two_modes_differ_only_in_order(self):
        """AC-C23-R21-50a: section の multiset が一致し順序だけが入れ替わる。共有の型は不変。"""
        outs = {}
        for mode in sorted(H.PRESENTATION_ORDER_KEYS):
            proc = H.run(["--purpose", H.LECTURE_SLUG, "--presentation-order", mode])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            outs[mode] = json.loads(H.out_text(proc))
            self.assertEqual(mode, outs[mode]["presentation_order"], H.describe(proc))
            self.assertEqual(mode, outs[mode]["applied_variant"], H.describe(proc))

        demo, explain = outs["demo_first"], outs["explain_first"]
        key = lambda sections: sorted(json.dumps(s, sort_keys=True) for s in sections)
        self.assertEqual(key(demo["section_order"]), key(explain["section_order"]))
        self.assertNotEqual(
            [s["id"] for s in demo["section_order"]],
            [s["id"] for s in explain["section_order"]],
            "2 モードで順序が変わっていない",
        )
        for field in ("recommended_parts", "notes", "required_document_fields", "label_ja", "dir_token"):
            self.assertEqual(demo.get(field), explain.get(field), field)

    def test_applied_order_matches_catalog_variant(self):
        """並べ替え結果は catalog の variant 定義そのものであり script が導出しない。"""
        variants = H.presets(self)[H.LECTURE_SLUG]["presentation_order_variants"]
        for mode, expected_ids in variants.items():
            with self.subTest(mode=mode):
                proc = H.run(["--purpose", H.LECTURE_SLUG, "--presentation-order", mode])
                self.assertEqual(0, proc.returncode, H.describe(proc))
                payload = json.loads(H.out_text(proc))
                self.assertEqual(expected_ids, [s["id"] for s in payload["section_order"]])

    def test_preset_without_variants_is_unchanged(self):
        """AC-C23-R21-50c 前半: variants を持たない preset は並べ替えず applied_variant=null。"""
        slug = H.slug_without_variants(self)
        expected = [s["id"] for s in H.presets(self)[slug]["section_order"]]
        proc = H.run(["--purpose", slug, "--presentation-order", "demo_first"])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        payload = json.loads(H.out_text(proc))
        self.assertEqual(expected, [s["id"] for s in payload["section_order"]])
        self.assertIsNone(payload["applied_variant"], H.describe(proc))

    def test_presentation_order_alone_is_exit_2(self):
        """AC-C23-R21-50c 後半: --purpose なしの単独指定は起動不正 (exit 2)。"""
        proc = H.run(["--presentation-order", "demo_first"])
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))

    def test_unknown_presentation_order_value_is_exit_2(self):
        """enum 外の値は exit 2。"""
        proc = H.run(["--purpose", H.LECTURE_SLUG, "--presentation-order", "video_first"])
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))

    def test_no_presentation_order_flag_keeps_catalog_order(self):
        """--presentation-order 未指定なら section_order を catalog 記載順のまま返す (導出しない)。"""
        expected = [s["id"] for s in H.presets(self)[H.LECTURE_SLUG]["section_order"]]
        proc = H.run(["--purpose", H.LECTURE_SLUG])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        payload = json.loads(H.out_text(proc))
        self.assertEqual(expected, [s["id"] for s in payload["section_order"]])
        self.assertIsNone(payload["applied_variant"], H.describe(proc))


class VariantValidationTest(unittest.TestCase):
    """AC-C23-R21-50b: 順列でない variant は手順 4i が落とす。"""

    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _run_with_mutation(self, mutate):
        root = H.make_fixture_root(self, self.tmp, mutate)
        return H.run_in_root(root, ["--purpose", H.LECTURE_SLUG])

    def test_missing_section_in_variant(self):
        def mutate(catalog):
            variants = catalog["presets"][H.LECTURE_SLUG]["presentation_order_variants"]
            variants["demo_first"] = variants["demo_first"][:-1]

        proc = self._run_with_mutation(mutate)
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))
        self.assertIn("E-PRESET-ORDER-NOT-PERMUTATION", H.err_text(proc), H.describe(proc))

    def test_unknown_section_in_variant(self):
        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["presentation_order_variants"]["demo_first"].append("foo")

        proc = self._run_with_mutation(mutate)
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertIn("E-PRESET-ORDER-NOT-PERMUTATION", H.err_text(proc), H.describe(proc))

    def test_duplicated_section_in_variant(self):
        def mutate(catalog):
            variants = catalog["presets"][H.LECTURE_SLUG]["presentation_order_variants"]
            variants["explain_first"] = variants["explain_first"][:-1] + [variants["explain_first"][0]]

        proc = self._run_with_mutation(mutate)
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertIn("E-PRESET-ORDER-NOT-PERMUTATION", H.err_text(proc), H.describe(proc))

    def test_variant_key_set_violation(self):
        """キー集合が厳密に {demo_first, explain_first} でなければ E-PRESET-ORDER-KEYS。"""
        def mutate(catalog):
            variants = catalog["presets"][H.LECTURE_SLUG]["presentation_order_variants"]
            variants["hybrid"] = list(variants["demo_first"])

        proc = self._run_with_mutation(mutate)
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertIn("E-PRESET-ORDER-KEYS", H.err_text(proc), H.describe(proc))

    def test_variant_missing_one_key(self):
        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["presentation_order_variants"].pop("explain_first")

        proc = self._run_with_mutation(mutate)
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertIn("E-PRESET-ORDER-KEYS", H.err_text(proc), H.describe(proc))


class VariantCoverageTest(unittest.TestCase):
    """VariantShapeTest が空振りしていないことを固定する。

    VariantShapeTest の 2 本は `variants is None` の preset を continue で飛ばす。
    variants を持つ preset は測定時点で 8 件中 1 件しかないため、その 1 件から
    variants が消えると 2 本とも「0 件を検査して緑」になる。検出コードが実在する
    ことと、その検出が実際に何かを見ていることは別である
    (C59 の share 検査が対象節 0 件のとき素通りしていたのと同じ形)。

    どの preset が variants を持つべきかの正本は brief の preset_definitions で、
    出荷 catalog はその写しである。ここでは件数のリテラルを書かず、
    正本から実測して突き合わせる。
    """

    C23_BRIEF = H.REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs" / "script-brief-C23.json"

    def canon_carriers(self):
        if not self.C23_BRIEF.is_file():
            self.fail("正本が読めない: {}".format(self.C23_BRIEF))
        data = json.loads(self.C23_BRIEF.read_text(encoding="utf-8"))
        presets = data.get("preset_definitions")
        if not isinstance(presets, list) or not presets:
            self.fail("script-brief-C23.json に preset_definitions が無い")
        return {
            entry.get("purpose") for entry in presets
            if isinstance(entry.get("presentation_order_variants"), dict)
        }

    def shipped_carriers(self):
        return {
            slug for slug, preset in H.presets(self).items()
            if isinstance(preset.get("presentation_order_variants"), dict)
        }

    def test_shape_checks_are_not_vacuous(self):
        """variants を持つ preset が 1 件以上あること (0 件なら shape 検査は無検査)。"""
        self.assertTrue(
            self.shipped_carriers(),
            "presentation_order_variants を持つ preset が 0 件。"
            "VariantShapeTest の 2 本が 1 件も検査せずに緑になる状態である",
        )

    def test_carriers_match_the_canon(self):
        """どの preset が variants を持つかが正本と一致すること。

        C50 の『2 モードで順序が入れ替わる』要求が及ぶ範囲そのものであり、
        出荷側で黙って増減すると shape 検査の射程が変わる。
        """
        self.assertEqual(self.canon_carriers(), self.shipped_carriers())


if __name__ == "__main__":
    unittest.main()

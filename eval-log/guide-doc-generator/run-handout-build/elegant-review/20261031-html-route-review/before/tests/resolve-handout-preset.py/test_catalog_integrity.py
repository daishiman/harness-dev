"""catalog 自己整合検査 (手順 4) — AC-C23-03 / 04 と failure_modes。

全て HB_ROOT へ差し替えた一時 root に対して実行する。実 plugin ツリーは一切変更しない。
"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class CatalogIntegrityTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _root(self, mutate=None) -> Path:
        return H.make_fixture_root(self, self.tmp, mutate)

    def assert_data_violation(self, proc, code):
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))
        self.assertIn(code, H.err_text(proc), H.describe(proc))

    def test_untouched_fixture_root_passes(self):
        """複製した clean な root では全モード前段の自己整合検査を通過する (対照)。"""
        proc = H.run_in_root(self._root(), ["--list", "--format", "text"])
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_preset_uncovered_fails_even_in_list_mode(self):
        """AC-C23-03: presets から 1 キー削ると --list でも E-PRESET-UNCOVERED / exit 1。"""
        dropped = {}

        def mutate(catalog):
            slug = catalog["vocabulary"][0]["slug"]
            dropped["slug"] = slug
            catalog["presets"].pop(slug)

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, "E-PRESET-UNCOVERED")
        self.assertIn(dropped["slug"], H.err_text(proc), H.describe(proc))

    def test_preset_uncovered_blocks_other_resolvable_purpose(self):
        """failure_modes: 別の解決可能な語彙を --purpose しても止まる (片側更新をその場で落とす)。"""
        def mutate(catalog):
            catalog["presets"].pop(catalog["vocabulary"][-1]["slug"])

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.slugs(self)[0]])
        self.assert_data_violation(proc, "E-PRESET-UNCOVERED")

    def test_preset_orphan(self):
        """vocabulary に無い preset キーは E-PRESET-ORPHAN / exit 1。"""
        def mutate(catalog):
            catalog["presets"]["ghost-purpose"] = {
                "section_order": [],
                "recommended_parts": [],
                "notes": "",
                # 4(j) の必須キーは満たしておき、4(f) の orphan 判定だけを切り出す
                "granularity_defaults": {"detail_level": "standard", "evidence_depth": "none"},
            }

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, "E-PRESET-ORPHAN")

    def test_preset_forbidden_key(self):
        """AC-C23-04: allowlist 外のキーを preset へ足すと E-PRESET-FORBIDDEN-KEY / exit 1 (C44)。"""
        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["sticky_nav"] = False

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.LECTURE_SLUG])
        self.assert_data_violation(proc, "E-PRESET-FORBIDDEN-KEY")

    def test_preset_forbidden_order_key(self):
        """AC-C23-R21-50d: 順序系の別キー (order_override) も許可キー外として落ちる。"""
        def mutate(catalog):
            preset = catalog["presets"][H.LECTURE_SLUG]
            preset["order_override"] = [s["id"] for s in preset["section_order"]]

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.LECTURE_SLUG])
        self.assert_data_violation(proc, "E-PRESET-FORBIDDEN-KEY")

    def test_duplicate_alias_across_slugs(self):
        """failure_modes: alias が 2 slug に重複すると E-CATALOG-MALFORMED / exit 1。"""
        def mutate(catalog):
            first = catalog["vocabulary"][0]
            catalog["vocabulary"][1]["aliases"] = list(catalog["vocabulary"][1]["aliases"]) + [
                first["aliases"][0]
            ]

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, "E-CATALOG-MALFORMED")

    def test_duplicate_dir_token(self):
        """dir_token の全体一意 (手順 4d) が破れると exit 1。"""
        def mutate(catalog):
            catalog["vocabulary"][1]["dir_token"] = catalog["vocabulary"][0]["dir_token"]

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, "E-CATALOG-MALFORMED")

    def test_slug_pattern_violation(self):
        """slug は ^[a-z][a-z0-9-]*$ (手順 4c)。"""
        def mutate(catalog):
            bad = "Lecture_X"
            old = catalog["vocabulary"][0]["slug"]
            catalog["vocabulary"][0]["slug"] = bad
            catalog["presets"][bad] = catalog["presets"].pop(old)

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, "E-CATALOG-MALFORMED")

    def test_unknown_section_kind(self):
        """手順 4h: section_kind が config/handout-sections.json に無い値なら exit 1。"""
        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["section_order"][0]["section_kind"] = "not-a-kind"

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.LECTURE_SLUG])
        self.assert_data_violation(proc, "E-CATALOG-MALFORMED")

    def test_unknown_recommended_part(self):
        """failure_modes: section_order に未知の part id があると exit 1。"""
        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["section_order"][0]["recommended_parts"] = ["B99"]

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.LECTURE_SLUG])
        self.assert_data_violation(proc, "E-CATALOG-MALFORMED")

    def test_document_scope_part_is_rejected_in_section(self):
        """手順 4h: section の recommended_parts は section_scope=in-section の id に限る。"""
        parts = json.loads(H.require_file(self, H.PARTS_FILE, "C11").read_text(encoding="utf-8"))
        doc_ids = [p["id"] for p in parts["parts"] if p.get("section_scope") == "document"]
        self.assertTrue(doc_ids, "section_scope=document の部品が正本に無い")

        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["section_order"][0]["recommended_parts"] = [doc_ids[0]]

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.LECTURE_SLUG])
        self.assert_data_violation(proc, "E-CATALOG-MALFORMED")

    def test_duplicate_section_id_within_preset(self):
        """手順 4h: section id は preset 内で一意。"""
        def mutate(catalog):
            order = catalog["presets"][H.LECTURE_SLUG]["section_order"]
            order[1]["id"] = order[0]["id"]

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.LECTURE_SLUG])
        self.assert_data_violation(proc, "E-CATALOG-MALFORMED")

    def test_unknown_schema_version(self):
        """手順 4a: schema_version が既知でなければ exit 1。"""
        def mutate(catalog):
            catalog["schema_version"] = 99999

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, "E-CATALOG-MALFORMED")

    def test_malformed_json_is_exit_2(self):
        """手順 3: JSON として parse できない catalog は exit 2 (起動系)。"""
        root = self._root()
        (root / H.CATALOG_RELPATH).write_text("{ not json", encoding="utf-8")
        proc = H.run_in_root(root, ["--list"])
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))

    def test_missing_catalog_lists_candidate_paths(self):
        """failure_modes: catalog が無いとき exit 2 で探索候補を stderr へ列挙する。"""
        root = self._root()
        (root / H.CATALOG_RELPATH).unlink()
        proc = H.run_in_root(root, ["--list"])
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertIn(str(root), H.err_text(proc), H.describe(proc))


if __name__ == "__main__":
    unittest.main()

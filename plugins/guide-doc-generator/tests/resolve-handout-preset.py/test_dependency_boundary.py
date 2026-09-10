"""依存の向きと stdlib 限定 — AC-C23-14 と P03 Y-08 の循環解消。

C23 は section_kind 正本を「データファイルとして読む」だけで C12 を import しない。
この向きを実装ソースに対して固定する。
"""

import ast
import re
import sys
import unittest

import _harness as H

STDLIB = set(getattr(sys, "stdlib_module_names", ()))


class StdlibOnlyTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self.source = H.SCRIPT.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def _imported_roots(self):
        roots = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    roots.add(node.module.split(".")[0])
        return roots

    def test_only_stdlib_imports(self):
        """AC-C23-14 / C27: 外部パッケージの import が 0 件。"""
        self.assertTrue(STDLIB, "sys.stdlib_module_names が使えない Python (3.10+ が前提)")
        external = sorted(r for r in self._imported_roots() if r not in STDLIB)
        self.assertEqual([], external, "標準ライブラリ以外を import している: {}".format(external))

    def test_no_yaml_import(self):
        self.assertNotIn("yaml", self._imported_roots())


class NoCycleTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self.source = H.SCRIPT.read_text(encoding="utf-8")

    def test_does_not_load_c12_module(self):
        """C12 validate-handout-config.py を import / spec_from_file_location しない。"""
        self.assertNotIn("validate-handout-config", self.source)
        self.assertNotIn("validate_handout_config", self.source)

    def test_does_not_load_sibling_scripts(self):
        """他 script をモジュールとして読み込まない (invokes は空)。"""
        for name in re.findall(r"spec_from_file_location\(\s*[\"']([^\"']+)", self.source):
            self.assertNotIn("validate", name)

    def test_reads_section_kind_data_file(self):
        """section_kind の照合は中立データファイル経由で行う。"""
        self.assertIn("handout-sections.json", self.source)

    def test_reads_parts_data_file(self):
        self.assertIn("handout-parts.json", self.source)

    def test_no_subprocess_invocation(self):
        """invokes: [] — 他 script を subprocess でも起動しない。"""
        self.assertNotIn("subprocess", self.source)


class NoWriteTest(unittest.TestCase):
    """write_scope: [] — 書き込み系の呼び出しをソース上に持たない。"""

    def setUp(self):
        H.require_script(self)
        self.source = H.SCRIPT.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_no_write_text_or_bytes(self):
        for forbidden in ("write_text(", "write_bytes(", "os.remove(", "shutil.copy", "os.rename("):
            with self.subTest(call=forbidden):
                self.assertNotIn(forbidden, self.source)

    def test_open_calls_are_read_only(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
                modes = [a.value for a in node.args[1:2] if isinstance(a, ast.Constant)]
                modes += [
                    kw.value.value
                    for kw in node.keywords
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant)
                ]
                for mode in modes:
                    with self.subTest(mode=mode):
                        self.assertNotRegex(str(mode), r"[wax+]", "書き込みモードで open している")


class VocabularyNotEnumeratedTest(unittest.TestCase):
    """語彙リテラルを script 本体へ列挙しない (正本はカタログ 1 本)。"""

    def setUp(self):
        H.require_script(self)
        self.source = H.SCRIPT.read_text(encoding="utf-8")

    def test_script_does_not_enumerate_vocabulary(self):
        hits = [s for s in H.slugs(self) if re.search(r"[\"']{}[\"']".format(re.escape(s)), self.source)]
        self.assertLess(
            len(hits), 3, "script 本体が用途語彙を列挙している (--audit-duplication の閾値と同じ 3 種): {}".format(hits)
        )

    def test_script_does_not_enumerate_section_kinds(self):
        import json

        sections = json.loads(H.require_file(self, H.SECTIONS_FILE, "C12").read_text(encoding="utf-8"))
        kinds = [k["slug"] for k in sections["section_kinds"]]
        hits = [k for k in kinds if re.search(r"[\"']{}[\"']".format(re.escape(k)), self.source)]
        self.assertLess(len(hits), 3, "section_kind の enum を script へ写している: {}".format(hits))


if __name__ == "__main__":
    unittest.main()

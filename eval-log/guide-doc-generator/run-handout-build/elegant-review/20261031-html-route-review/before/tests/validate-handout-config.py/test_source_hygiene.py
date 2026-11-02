# -*- coding: utf-8 -*-
"""実装本体のソースに対する構造検査 (AC-C12-14 / AC-C12-23 / SSOT 規律)。

語彙リテラルや閾値を script が自前に持たないことは C42 / C46 / C59 の前提であり、
挙動テストだけでは「たまたま同じ値を書いた」状態を落とせないため、ソース側でも固定する。
"""

import ast
import json
import re
import unittest

import _harness as H

ALLOWED_IMPORT_ROOTS = {
    "json", "sys", "argparse", "pathlib", "re", "datetime",
    "unicodedata", "hashlib", "importlib", "os", "tempfile", "math",
}


class SourceHygiene(H.C12TestCase):

    def setUp(self):
        super().setUp()
        self.source = self.script_source()
        self.tree = ast.parse(self.source)

    def _string_literals(self):
        return [n.value for n in ast.walk(self.tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]

    def _numeric_literals(self):
        return [n.value for n in ast.walk(self.tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)]

    def test_stdlib_only_imports(self):
        """AC-C12-23: 許可された標準ライブラリのみ。yaml と外部パッケージは 0 件 (C27)。"""
        roots = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
        self.assertEqual(set(), roots - ALLOWED_IMPORT_ROOTS,
                         "許可外の import がある: %r" % sorted(roots - ALLOWED_IMPORT_ROOTS))

    def test_no_yaml(self):
        """yaml は使わない。"""
        self.assertNotIn("yaml", self.source)

    def test_no_purpose_vocabulary_literals(self):
        """AC-C12-14: 用途語彙 slug が文字列リテラルとして 1 つも現れない (C42)。"""
        catalog_path = self.root / H.PURPOSES_CATALOG_RELPATH
        self.assertTrue(catalog_path.exists(), "用途語彙正本が無い: %s" % catalog_path)
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        vocab = set()
        # 語彙配列のキーは "vocabulary" (owner: C23)。"entries" ではない。
        for entry in catalog["vocabulary"]:
            vocab.add(entry["slug"])
            vocab.update(entry.get("aliases", []))
        found = sorted(vocab & set(self._string_literals()))
        self.assertEqual([], found, "語彙リテラルが script に埋まっている: %r" % found)

    def test_no_part_id_enumeration(self):
        """part id の名簿を自前に持たない (id 語彙の正本は C11 の config/handout-parts.json)。

        data の形の定義表としてキーに現れるのは許すが、
        カタログ全件の列挙 (B01..B17 が一様に並ぶ配列リテラル) は持たせない。
        """
        parts_path = self.root / H.PARTS_CATALOG_RELPATH
        self.assertTrue(parts_path.exists(), "部品カタログ正本が無い: %s" % parts_path)
        catalog = json.loads(parts_path.read_text(encoding="utf-8"))
        document_scope = {p["id"] for p in catalog["parts"] if p.get("section_scope") == "document"}
        found = sorted(document_scope & set(self._string_literals()))
        self.assertEqual([], found,
                         "generated-chrome 部品の id を script が列挙している (section_scope で判定すべき): %r" % found)

    def test_no_section_kind_threshold_literals(self):
        """C46: 閾値をデータファイル側から読み、script へ書かない。"""
        catalog = self.sections_catalog()
        thresholds = set()
        for kind in catalog["section_kinds"]:
            for key in ("max_items",):
                if key in kind:
                    thresholds.add(kind[key])
        self.assertTrue(thresholds, "閾値属性が正本に 1 件も無い")
        found = sorted(str(v) for v in thresholds & set(self._numeric_literals()))
        self.assertEqual([], found, "閾値が script に埋まっている: %r" % found)

    def test_section_kind_default_is_not_hardcoded(self):
        """N7 の既定値 'standard' も catalog の default から読む。"""
        default = self.sections_catalog()["default"]
        self.assertNotIn(default, self._string_literals(),
                         "section_kind の既定値 %r が script に埋まっている" % default)

    def test_does_not_import_c23_by_file_path_literal_only(self):
        """C23 はモジュールとして importlib 経由で読み込む (語彙を自前に持たない)。"""
        self.assertIn("importlib", self.source)
        self.assertIn("resolve-handout-preset.py", self.source)

    def test_config_is_opened_read_only(self):
        """N13: --config を書き込みモードで開く経路が無い。"""
        writes = re.findall(r"open\([^)]*['\"][wa]\+?b?['\"]", self.source)
        self.assertEqual([], writes, "書き込みモードの open がある: %r" % writes)

    def test_single_date_resolution_point(self):
        """date_single_source_guarantee: 現在日付の取得は 1 箇所だけ。"""
        occurrences = re.findall(r"date\.today\(\)|datetime\.now\(\)|time\.time\(\)", self.source)
        self.assertLessEqual(len(occurrences), 1,
                             "現在日付の取得点が複数ある: %r" % occurrences)

    def test_no_network_access(self):
        """network: false。"""
        for token in ("urllib.request", "socket", "http.client", "requests"):
            self.assertNotIn(token, self.source, "ネットワーク経路がある: %s" % token)


if __name__ == "__main__":
    unittest.main()

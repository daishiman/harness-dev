# -*- coding: utf-8 -*-
"""実装本体のソース構造 (AC-C20-15 / C27 / parsing_strategy / write_scope)。

挙動テストだけでは「たまたま今は通る書き方」を落とせない項目をここで固定する。
とくに正規表現による DOM 解析の禁止と、C12 の正規化を再実装しないことは、
どちらも壊れ方が静かなので構造側で止める。
"""

import ast
import re
import unittest

import _harness as H

# acceptance_checks AC-C20-15 が列挙する import
ALLOWED_IMPORT_ROOTS = {
    "html", "json", "sys", "argparse", "pathlib", "re",
    "unicodedata", "importlib", "os", "tempfile",
}

FORBIDDEN_HTML_LIBS = ("bs4", "BeautifulSoup", "lxml", "html5lib", "selectolax", "yaml")


class SourceHygiene(H.C20TestCase):

    def setUp(self):
        super().setUp()
        self.source = self.script_source()
        try:
            self.tree = ast.parse(self.source)
        except SyntaxError as exc:
            self.fail("実装が Python として解析できない: %r" % exc)

    def _import_roots(self):
        roots = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
        return roots

    def test_stdlib_only_imports(self):
        """AC-C20-15: 許可された標準ライブラリのみ。"""
        extra = self._import_roots() - ALLOWED_IMPORT_ROOTS
        self.assertEqual(set(), extra, "許可外の import がある: %r" % sorted(extra))

    def test_html_parser_is_used(self):
        self.assertIn("html.parser", self.source, "html.parser を使っていない")
        self.assertIn("HTMLParser", self.source)

    def test_convert_charrefs_is_enabled(self):
        """parsing_strategy: convert_charrefs=True で実体参照を解決する。"""
        self.assertNotRegex(self.source, r"convert_charrefs\s*=\s*False",
                            "convert_charrefs を無効化している")

    def test_no_third_party_html_library(self):
        """AC-C20-15: BeautifulSoup 等の HTML ライブラリと yaml が 0 件 (C27)。"""
        for token in FORBIDDEN_HTML_LIBS:
            self.assertNotIn(token, self.source, "外部 HTML ライブラリ/yaml がある: %s" % token)

    def test_no_regex_dom_parsing(self):
        """正規表現でタグを掴む経路を持たない (属性順や空白の差で壊れるため)。"""
        suspicious = re.findall(r"re\.(?:findall|search|match|finditer|sub)\(\s*r?['\"][^'\"]*<",
                                self.source)
        self.assertEqual([], suspicious, "正規表現で DOM を解析している: %r" % suspicious)

    def test_no_network_access(self):
        """network: false。"""
        for token in ("urllib", "socket", "http.client", "requests", "ssl"):
            self.assertNotIn(token, self.source, "ネットワーク経路がある: %s" % token)

    def test_html_is_opened_read_only(self):
        """--html は常に読み取り専用 (write_scope は out-file 系のみ)。"""
        writes = re.findall(r"open\([^)]*['\"][wax]\+?b?['\"]", self.source)
        self.assertLessEqual(len(writes), 2,
                             "書き込みモードの open が多すぎる (--out / --report 以外がある): %r" % writes)

    def test_normalization_is_imported_from_c12(self):
        """invokes: C12 を importlib で読み込み、正規化を再実装しない。"""
        self.assertIn("importlib", self.source)
        self.assertIn("validate-handout-config.py", self.source,
                      "C12 をモジュールとして読み込んでいない (正規化の基準が 2 つになる)")

    def test_no_reimplemented_date_normalization(self):
        """日付書式の正規化を自前に持たない (C12 の正規化を通す)。"""
        self.assertNotIn("strftime", self.source)
        self.assertNotIn("%Y年%m月%d日", self.source)

    def test_nfc_normalization_is_applied(self):
        """text_handling: 最後に NFC 正規化する。"""
        self.assertIn("NFC", self.source)

    def test_no_sorting_of_sections_or_parts(self):
        """ordering: sections は文書順、parts は DOM 順。ソートしない。"""
        sorts = re.findall(r"\.sort\(|sorted\(\s*(?:sections|parts)\b", self.source)
        self.assertEqual([], sorts, "sections / parts をソートしている: %r" % sorts)

    def test_atomic_replace_is_used(self):
        """A12: 一時ファイル + os.replace で差し替える。"""
        self.assertIn("os.replace", self.source)

    def test_no_config_blob_extraction(self):
        """構成データ blob (<script type=application/json>) を前提にしない。"""
        self.assertNotIn("application/json", self.source,
                         "埋め込み blob を読む経路がある (手書き HTML を逆抽出できなくなる)")


if __name__ == "__main__":
    unittest.main()

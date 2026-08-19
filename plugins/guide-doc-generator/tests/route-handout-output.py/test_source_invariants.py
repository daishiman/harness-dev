"""script ソースに対する不変条件 — AC-C19-02 / 03 / 04 / 07 / 10、C27 / C42。

いずれも「実装がどう書かれていても満たすべき」不変条件であり、ソースを静的に読んで判定する。
語彙リテラルの検査は語彙正本から生成した集合で行い、テスト側に語彙を焼き付けない。
"""

import re
import sys
import unittest

import _harness as H


def _code_without_comments(source: str) -> str:
    """行コメントを落とした本文 (docstring は残す — brief が docstring 列挙も禁じている)。"""
    return "\n".join(re.sub(r"#.*$", "", line) for line in source.splitlines())


class NoEnvironmentSpecificPathTest(unittest.TestCase):
    """AC-C19-02: 環境固有の絶対パスを持たない (既定値は config 側にしかない)。"""

    def setUp(self):
        self.source = H.read_source(self)

    def test_no_obsidianmemo_literal(self):
        self.assertNotIn("ObsidianMemo", self.source)

    def test_no_user_home_literal(self):
        self.assertNotIn("/Users/", self.source)
        self.assertNotIn("/home/", self.source)

    def test_no_default_out_dir_literal_in_source(self):
        """既定出力先の値は config/handout-output.json にのみ存在する。"""
        code = _code_without_comments(self.source)
        self.assertNotIn("資料作成", code, "既定出力先らしき日本語パス片がソースにある")


class NoVocabularyLiteralTest(unittest.TestCase):
    """AC-C19-03: 用途種別の語彙リテラルが 0 件 (C42 の単一正本)。"""

    def setUp(self):
        self.source = H.read_source(self)

    def test_no_catalog_slug_or_dir_token_appears_in_source(self):
        code = _code_without_comments(self.source)
        offenders = []
        for entry in H.vocabulary_entries(self):
            for value in {entry["slug"], entry.get("dir_token", entry["slug"])}:
                if re.search(r"['\"]{}['\"]".format(re.escape(value)), code):
                    offenders.append(value)
        self.assertEqual([], sorted(offenders), "語彙リテラルがソースに現れている")

    def test_no_catalog_alias_appears_in_source(self):
        code = _code_without_comments(self.source)
        offenders = [
            alias
            for entry in H.vocabulary_entries(self)
            for alias in (entry.get("aliases") or [])
            if alias in code
        ]
        self.assertEqual([], sorted(offenders), "alias がソースに現れている")


class NoClockAccessTest(unittest.TestCase):
    """AC-C19-04: 現在時刻取得が 0 件 (日付の正本は構成データの date だけ)。"""

    def setUp(self):
        self.source = H.read_source(self)

    def test_no_current_time_api(self):
        code = _code_without_comments(self.source)
        for token in (
            "date.today",
            "datetime.now",
            "datetime.today",
            "datetime.utcnow",
            "time.time",
            "time.localtime",
        ):
            self.assertNotIn(token, code, "現在時刻取得 {} がある".format(token))

    def test_no_datetime_or_time_import(self):
        """algorithm 3: stdlib の日付 API をこの script が触らないこと自体が不変条件。"""
        code = _code_without_comments(self.source)
        for pattern in (r"^\s*import\s+datetime", r"^\s*from\s+datetime\s+import", r"^\s*import\s+time\b"):
            self.assertIsNone(
                re.search(pattern, code, re.MULTILINE),
                "日付 / 時刻モジュールを import している ({})".format(pattern),
            )


class DateFormatInvariantTest(unittest.TestCase):
    """AC-C19-07: ^\\d{4}-\\d{2}-\\d{2}$ で date を検証する記述が 0 件。"""

    def setUp(self):
        self.source = H.read_source(self)

    def test_no_hyphen_date_validation_regex(self):
        code = _code_without_comments(self.source)
        offenders = re.findall(r"\\d\{4\}\s*-\s*\\d\{2\}\s*-\s*\\d\{2\}", code)
        self.assertEqual([], offenders, "yyyy-mm-dd を受理する検証正規表現がある")

    def test_slash_date_validation_regex_exists(self):
        code = _code_without_comments(self.source)
        self.assertTrue(
            re.search(r"\\d\{4\}\s*/\s*\\d\{2\}\s*/\s*\\d\{2\}", code),
            "yyyy/mm/dd の検証正規表現が無い (受理書式は 1 つだけ)",
        )


class StdlibOnlyTest(unittest.TestCase):
    """C27: 標準ライブラリのみ。外部パッケージ import が 0 件。"""

    def setUp(self):
        self.source = H.read_source(self)

    def test_all_imports_are_stdlib(self):
        modules = set()
        for line in self.source.splitlines():
            m = re.match(r"\s*import\s+([A-Za-z_][\w.]*)", line)
            if m:
                modules.add(m.group(1).split(".")[0])
            m = re.match(r"\s*from\s+([A-Za-z_][\w.]*)\s+import", line)
            if m:
                modules.add(m.group(1).split(".")[0])
        allowed = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
        self.assertEqual(
            set(), modules - allowed, "標準ライブラリ以外を import している"
        )

    def test_no_network_access(self):
        code = _code_without_comments(self.source)
        for token in ("urllib.request", "http.client", "socket.", "requests"):
            self.assertNotIn(token, code, "ネットワーク API {} がある".format(token))


if __name__ == "__main__":
    unittest.main()

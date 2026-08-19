"""AC-C15-9 / AC-C15-10 / single_writer: 実装の境界を静的に固定する。

- AC-C15-9  標準ライブラリのみ。yaml import 0 件 (checklist C27)
- AC-C15-10 アイコン語彙 41 語のハードコードが 0 件 (語彙の正本は icon-set.json)
- single_writer  symbol 生成と id 採番の owner は C15 だけ。C11 は埋め込むだけ
"""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

import _harness as H


def _imported_roots(tree: ast.AST) -> set[str]:
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


class StdlibOnlyTest(unittest.TestCase):
    """AC-C15-9 / checklist C27。"""

    def _tree(self):
        source = H.script_source(self)
        try:
            return ast.parse(source), source
        except SyntaxError as exc:
            self.fail("実装が構文エラー: {}".format(exc))

    def test_all_imports_are_stdlib(self):
        tree, _source = self._tree()
        for root in sorted(_imported_roots(tree)):
            self.assertIn(
                root, sys.stdlib_module_names,
                "標準ライブラリ外の import: {}".format(root),
            )

    def test_no_forbidden_third_party_imports(self):
        tree, _source = self._tree()
        found = _imported_roots(tree) & H.FORBIDDEN_IMPORTS
        self.assertEqual(found, set(), "禁止された import: {}".format(sorted(found)))

    def test_yaml_appears_nowhere(self):
        _tree, source = self._tree()
        self.assertNotIn("yaml", source.lower(), "yaml への言及が 0 件でない (checklist C27)")

    def test_imports_stay_within_the_declared_set(self):
        """AC-C15-9 が名指しする集合 (json/sys/os/argparse/html/re/difflib/pathlib 「など」)。

        「など」なので上位集合を許すが、宣言外はすべて標準ライブラリであることを
        上のテストが担保する。ここでは宣言集合の主要 4 つが実際に使われることを見る。
        """
        tree, _source = self._tree()
        roots = _imported_roots(tree)
        for required in ("json", "sys", "argparse", "difflib"):
            self.assertIn(
                required, roots,
                "AC-C15-9 が挙げる {} が使われていない (契約どおりの実装になっていない疑い)".format(required),
            )

    def test_no_network_or_subprocess(self):
        """network=false / invokes=[]。通信も子プロセス起動もしない。"""
        tree, _source = self._tree()
        for banned in ("subprocess", "socket", "http", "urllib", "ftplib", "asyncio"):
            self.assertNotIn(banned, _imported_roots(tree), "{} を import している".format(banned))

    def test_no_nondeterministic_modules(self):
        """checklist C29。時刻・乱数・ファイル列挙順に依存させない。"""
        tree, _source = self._tree()
        for banned in ("random", "time", "datetime", "uuid", "glob", "tempfile", "secrets"):
            self.assertNotIn(
                banned, _imported_roots(tree),
                "決定論を壊しうる {} を import している".format(banned),
            )


class NoHardcodedVocabularyTest(unittest.TestCase):
    """AC-C15-10: script 本文をアイコン語彙 41 語で grep して 0 件。"""

    def test_no_icon_name_literal_in_source(self):
        source = H.script_source(self)
        hits = []
        for name in H.VOCABULARY:
            for quote in ('"', "'"):
                if quote + name + quote in source:
                    hits.append(name)
                    break
        self.assertEqual(
            hits, [],
            "アイコン名が実装へハードコードされている (語彙の正本は icon-set.json): {}".format(hits),
        )

    def test_vocabulary_lives_in_the_icon_set_only(self):
        """語彙を足しても script 無改修で認識される (単一正本の原則)。"""
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(
                Path(tmp), H.make_icon_set(names=["brand-new-icon"])
            )
            cfg = H.write_config(
                Path(tmp),
                H.make_config(sections=[H.section("s1", section_icon="brand-new-icon")]),
            )
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            self.assertEqual([e["name"] for e in result[H.OUT_USED]], ["brand-new-icon"])
            self.assertIn("hbic-brand-new-icon", result[H.OUT_SYMBOLS])

    def test_removing_an_icon_from_the_set_makes_it_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=["cross"]))
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 1, "語彙が正本以外にも生きている疑い")


class ModuleApiTest(unittest.TestCase):
    """dependencies.invoked_by: C11 は module import で build_sprite(config, icon_set) を呼ぶ。

    CLI と module で同一の判定を通す形 (純関数 + main() の二層) を固定する。
    """

    def test_build_sprite_is_defined(self):
        source = H.script_source(self)
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            self.fail("実装が構文エラー: {}".format(exc))
        names = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn(
            "build_sprite", names,
            "C11 が import する build_sprite(config, icon_set) が無い: {}".format(sorted(names)),
        )
        self.assertIn("main", names, "CLI 経路の main() が無い (CLI としても独立に検証できる契約)")

    def test_build_sprite_takes_config_and_icon_set(self):
        source = H.script_source(self)
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            self.fail("実装が構文エラー: {}".format(exc))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "build_sprite":
                args = [a.arg for a in node.args.args]
                self.assertEqual(
                    args[:2], ["config", "icon_set"],
                    "build_sprite(config, icon_set) の引数名が契約と違う: {}".format(args),
                )
                return
        self.fail("build_sprite が見つからない")

    def test_module_import_does_not_run_main(self):
        """import 副作用で CLI が走らないこと (C11 は import して関数だけを呼ぶ)。"""
        source = H.script_source(self)
        self.assertIn(
            '__name__ == "__main__"', source.replace("'", '"'),
            "__main__ ガードが無い (module import で CLI が走る)",
        )


class ResponsibilityBoundaryTest(unittest.TestCase):
    """C15 が越えてはならない境界 (single_writer / write_scope)。"""

    def test_no_html_document_scaffolding(self):
        """C15 が出すのは sprite 断片だけ。HTML 文書は C11 の責務。"""
        source = H.script_source(self)
        for token in ("<!DOCTYPE", "<html", "<body", "<head"):
            self.assertNotIn(token, source, "HTML 文書の生成に踏み込んでいる: {}".format(token))

    def test_no_use_element_generation(self):
        """参照側の <use> を書くのは C11。C15 は use_href を返すだけ (algorithm 10)。"""
        source = H.script_source(self)
        self.assertNotIn("<use", source, "<use> を C15 が生成している (C11 の責務)")

    def test_no_file_write_api(self):
        source = H.script_source(self)
        for token in ("open(", "write_text", "write_bytes", "mkdir", "shutil"):
            if token == "open(":
                # 読み込みの open は必要。書きモードだけを禁じる。
                for mode in ('"w"', "'w'", '"a"', "'a'", '"wb"', "'wb'", '"w+"', "'w+'"):
                    self.assertNotIn(
                        mode, source, "書き込みモードの open がある (write_scope=none): {}".format(mode)
                    )
                continue
            if token in ("write_text", "write_bytes", "mkdir", "shutil"):
                self.assertNotIn(token, source, "ファイル書き込み API がある: {}".format(token))


if __name__ == "__main__":
    unittest.main()

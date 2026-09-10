"""AC-C13-6 / C27 と責務境界 (P03 Y-04) を script 本体の静的検査で固定する。

「data URI を作る側だけを担う」という purpose は実行結果だけでは示せない。
外部依存ゼロと、配置・HTML 焼き込みへ手を出していないことをソースの走査で押さえる。
"""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

import _harness as H

# AC-C13-6 が名指しする、C13 に許される import。__future__ は依存ではないので除外しない。
ALLOWED_IMPORTS = {"argparse", "base64", "json", "os", "pathlib", "sys", "__future__"}

# C27 違反として 0 件でなければならない外部パッケージ。
FORBIDDEN_PACKAGES = {"PIL", "Pillow", "yaml", "requests", "numpy", "lxml", "bs4", "magic"}

# 決定論を壊す / 責務境界を越える標準ライブラリ。
FORBIDDEN_STDLIB = {
    "mimetypes",  # algorithm 5: OS 依存の MIME 解決を使わない
    "subprocess",  # AC-C13-6: 子プロセス起動 0 件
    "shutil",  # P03 Y-04: 原本の複製は C19 の責務
    "random",
    "datetime",
    "time",
    "uuid",
    "socket",
    "urllib",
    "http",
}


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


class StdlibOnlyTest(unittest.TestCase):
    def setUp(self):
        self.source = H.script_source(self)
        self.imports = _imported_modules(self.source)

    def test_no_third_party_imports(self):
        """AC-C13-6: import が標準ライブラリのみ。"""
        non_stdlib = {m for m in self.imports if m not in sys.stdlib_module_names}
        self.assertEqual(set(), non_stdlib, "標準ライブラリ外の import: {}".format(sorted(non_stdlib)))

    def test_forbidden_packages_absent(self):
        hits = sorted(p for p in FORBIDDEN_PACKAGES if p in self.imports)
        self.assertEqual([], hits, "C27 違反の import: {}".format(hits))

    def test_forbidden_stdlib_absent(self):
        hits = sorted(m for m in FORBIDDEN_STDLIB if m in self.imports)
        self.assertEqual([], hits, "使ってはならない標準ライブラリ: {}".format(hits))

    def test_imports_stay_within_declared_set(self):
        """AC-C13-6 が列挙する 6 モジュールの範囲に収まる。"""
        extra = sorted(self.imports - ALLOWED_IMPORTS)
        self.assertEqual([], extra, "AC-C13-6 の宣言外 import: {}".format(extra))

    def test_no_subprocess_launch(self):
        for token in ("subprocess", "os.system", "os.exec", "os.spawn", "popen"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.source)

    def test_base64_encodebytes_is_not_used(self):
        """algorithm 8: 76 文字ごとに改行が入るため使わない。"""
        self.assertNotIn("encodebytes", self.source)
        self.assertNotIn("encodestring", self.source)

    def test_b64encode_is_used(self):
        self.assertIn("b64encode", self.source)


class ResponsibilityBoundaryTest(unittest.TestCase):
    """P03 Y-04: 配置は C19、HTML 焼き込みは C11。C13 はどちらもしない。"""

    def setUp(self):
        self.source = H.script_source(self)

    def test_no_file_copy_api(self):
        for token in ("copyfile", "copytree", "copy2(", "shutil"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.source)

    def test_no_html_emission(self):
        for token in ("<img", "<a href", "lightbox", "dl-hint", "Blob(", "</html>"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.source)

    def test_no_handout_config_placement(self):
        """handout-config.json の配置は C19 (--place-config)。"""
        self.assertNotIn("handout-config.json", self.source)
        self.assertNotIn("place-config", self.source)

    def test_no_assets_dir_argument_for_output(self):
        """出力先 assets/ への複製引数 (--assets-src) は C19 の argv。C13 は持たない。"""
        self.assertNotIn("assets-src", self.source)

    def test_no_image_reencoding(self):
        for token in ("zlib", "compress(", "resize", "thumbnail"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.source)


class WriteScopeTest(unittest.TestCase):
    """write_scope: --out で指定された 1 ファイルのみ。"""

    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.assets_dir, self.work = H.make_workspace(self, self.tmp)
        H.write_asset(self.assets_dir, "hero.png", H.png_bytes())
        H.write_asset(self.assets_dir, "sheet.xlsx", H.xlsx_bytes())
        config = H.make_config(
            assets=[H.image_asset("hero", "hero.png")],
            attachments=[H.attachment("sheet", "sheet.xlsx", H.MIME_XLSX, "sheet.xlsx")],
        )
        self.config_path = H.write_config(self.work, config)

    def tearDown(self):
        self._tmp.cleanup()

    def test_stdout_run_writes_nothing_to_disk(self):
        before = H.tree_snapshot(self.tmp)
        proc = H.run_embed(self, self.config_path, self.assets_dir)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertEqual(before, H.tree_snapshot(self.tmp), "--out 省略時に書き込みが発生した")

    def test_out_run_writes_exactly_one_file(self):
        before = set(H.tree_snapshot(self.tmp).keys())
        out = self.work / "embedded.json"
        proc = H.run_embed(self, self.config_path, self.assets_dir, out=out)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        after = set(H.tree_snapshot(self.tmp).keys())
        self.assertEqual(
            {str(out.relative_to(self.tmp))},
            after - before,
            "--out 以外のファイルが作られた: {}".format(sorted(after - before)),
        )

    def test_no_assets_subdirectory_is_created(self):
        """C19 の責務である出力先 assets/ を C13 が作らない。"""
        H.run_embed(self, self.config_path, self.assets_dir, out=self.work / "embedded.json")
        self.assertFalse((self.work / "assets").exists(), "C13 が assets/ を作っている")

    def test_input_config_is_not_modified(self):
        before = self.config_path.read_bytes()
        H.run_embed(self, self.config_path, self.assets_dir, out=self.work / "embedded.json")
        self.assertEqual(before, self.config_path.read_bytes(), "--config を書き換えている")


if __name__ == "__main__":
    unittest.main()

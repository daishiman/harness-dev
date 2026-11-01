"""同一入力の再現性と決定論 (AC-C11-1 / AC-C11-11 / AC-C11-17 / algorithm 24)。"""

import difflib
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import _harness as H

# 標準ライブラリのみ (stdlib_only: true / checklist C27)。
STDLIB_ALLOWED = set(
    """argparse base64 collections contextlib copy dataclasses datetime enum functools
    hashlib html importlib io itertools json math os pathlib re shutil string subprocess
    sys textwrap types typing unicodedata urllib uuid xml zlib""".split()
)


class ByteReproducibilityTest(unittest.TestCase):
    def test_two_runs_are_byte_identical(self):
        """AC-C11-1 / checklist C29: 同一構成データから 2 回生成して sha256 が一致する。"""
        config = H.base_config(
            sections=[
                H.base_section(1, blocks=[H.BLOCK_FIXTURES["steps"], H.BLOCK_FIXTURES["table"]]),
                H.base_section(2, id="s2", blocks=[H.BLOCK_FIXTURES["checklist"]]),
            ]
        )
        digests = []
        for i in range(2):
            with tempfile.TemporaryDirectory() as td:
                res, html_text, out = H.render_html(td, config)
                self.assertEqual(0, res.returncode, res.stderr)
                digests.append(hashlib.sha256(out.read_bytes()).hexdigest())
        self.assertEqual(digests[0], digests[1], "2 回生成のバイト一致が壊れている")

    def test_output_path_does_not_leak_into_html(self):
        """出力先パスやプロセス由来の値が本文へ混ざらない (再現性の単位は構成データ 1 点)。"""
        config = H.base_config()
        bodies = []
        for name in ("a", "b"):
            with tempfile.TemporaryDirectory() as td:
                cfg = H.write_config(Path(td) / "config.json", config)
                out = Path(td) / ("%s.html" % name)
                res = H.run_render(["--config", cfg, "--out", out])
                self.assertEqual(0, res.returncode, res.stderr)
                bodies.append(out.read_text(encoding="utf-8"))
        self.assertEqual(bodies[0], bodies[1])

    def test_input_key_order_is_preserved(self):
        """algorithm 2/24: dict は入力順のまま扱う (object_pairs_hook)。並べ替えて出力しない。"""
        block_a = dict(H.BLOCK_FIXTURES["steps"])
        block_b = dict(H.BLOCK_FIXTURES["checklist"])
        cfg1 = H.base_config(sections=[H.base_section(1, blocks=[block_a, block_b])])
        cfg2 = H.base_config(sections=[H.base_section(1, blocks=[block_b, block_a])])
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            r1, h1, _ = H.render_html(td1, cfg1)
            r2, h2, _ = H.render_html(td2, cfg2)
        self.assertEqual(0, r1.returncode, r1.stderr)
        self.assertEqual(0, r2.returncode, r2.stderr)
        self.assertLess(h1.index('data-hb-part="B03"'), h1.index('data-hb-part="B09"'))
        self.assertLess(h2.index('data-hb-part="B09"'), h2.index('data-hb-part="B03"'))


class TokenIndirectionTest(unittest.TestCase):
    """AC-C11-11 / checklist C14: アクセント色の実値は :root にしか現れない。"""

    def _clone_plugin_root(self, dest):
        shutil.copytree(H.PLUGIN_ROOT, dest, symlinks=True)
        return Path(dest)

    def test_accent_token_change_only_diffs_root_block(self):
        config = H.base_config()
        with tempfile.TemporaryDirectory() as td:
            clone = self._clone_plugin_root(Path(td) / "plugin")
            tokens = clone / "assets" / "tokens" / "pop.json"
            if not tokens.is_file():
                raise AssertionError("テーマトークン正本が未実装: %s" % tokens)
            data = json.loads(tokens.read_text(encoding="utf-8"))
            before_out = Path(td) / "before.html"
            cfg = H.write_config(Path(td) / "config.json", config)
            r1 = H.run_render(["--config", cfg, "--out", before_out], env_extra={"HB_ROOT": str(clone)})
            self.assertEqual(0, r1.returncode, r1.stderr)

            key = self._accent_key(data)
            self._set_accent(data, key, "#123456")
            tokens.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            after_out = Path(td) / "after.html"
            r2 = H.run_render(["--config", cfg, "--out", after_out], env_extra={"HB_ROOT": str(clone)})
            self.assertEqual(0, r2.returncode, r2.stderr)

            diff = [
                ln for ln in difflib.unified_diff(
                    before_out.read_text(encoding="utf-8").splitlines(),
                    after_out.read_text(encoding="utf-8").splitlines(),
                    lineterm="", n=0,
                )
                if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))
            ]
        self.assertTrue(diff, "トークンを変えたのに出力が変わらないのはトークン未参照")
        for line in diff:
            self.assertIn("--pop-primary", line, "差分は :root のアクセント定義行のみであること: %r" % line)

    @staticmethod
    def _accent_key(data):
        for key in data:
            if "pop-primary" in key or key in ("pop_primary", "primary"):
                return key
        raise AssertionError("テーマトークンにアクセント色 (--pop-primary 相当) が無い: %r" % list(data))

    @staticmethod
    def _set_accent(data, key, value):
        if isinstance(data[key], dict):
            first = next(iter(data[key]))
            data[key][first] = value
        else:
            data[key] = value


class StdlibOnlyTest(unittest.TestCase):
    def test_no_third_party_imports(self):
        """AC-C11-17 / checklist C27: 標準ライブラリのみ。yaml import は 0 件。"""
        modules = H.imported_modules()
        self.assertNotIn("yaml", modules)
        unexpected = sorted(m for m in modules if m not in STDLIB_ALLOWED and not m.startswith("_"))
        self.assertEqual([], unexpected, "標準ライブラリ以外の import: %r" % unexpected)

    def test_no_randomness_or_process_identity(self):
        """algorithm 24: 乱数・プロセス id・mtime を一切使わない。"""
        src = H.source_text()
        for forbidden in ("random.", "uuid4", "os.getpid", "st_mtime", "getmtime"):
            self.assertNotIn(forbidden, src, "%s は決定論を壊す" % forbidden)

    def test_escaping_is_unified(self):
        """algorithm 24: エスケープは html.escape(quote=True) に統一する。"""
        src = H.source_text()
        self.assertIn("html.escape", src)
        self.assertNotIn("quote=False", src)

    def test_config_text_is_escaped_in_output(self):
        """エスケープ統一の実挙動: 構成データ中の < > " が生タグとして出ない。"""
        config = H.base_config(title='見出し <script>"x"</script>')
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, config)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertNotIn("見出し <script>", html_text)
        self.assertIn("&lt;script&gt;", html_text)


if __name__ == "__main__":
    unittest.main()

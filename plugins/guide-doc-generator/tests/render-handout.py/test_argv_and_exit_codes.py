"""argv と exit code の契約 (script-brief-C11.json argv / exit_codes / algorithm 1,25)。

exit 0 = 出力できた / exit 1 = 入力データの規約違反 / exit 2 = 実行不能。
"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class ArgvContractTest(unittest.TestCase):
    def test_config_is_required(self):
        """--config は required=true。省略起動は実行不能なので exit 2。"""
        res = H.run_render([])
        self.assertEqual(2, res.returncode, res.stderr)

    def test_missing_config_file_is_exit2(self):
        """--config のファイル不在は実行不能 (algorithm 2)。"""
        with tempfile.TemporaryDirectory() as td:
            res = H.run_render(["--config", Path(td) / "no-such.json"])
        self.assertEqual(2, res.returncode, res.stderr)

    def test_broken_json_is_exit2(self):
        """JSON 構文エラーは exit 2 (差し戻し先は呼び出し側)。"""
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "config.json"
            bad.write_text("{ not json", encoding="utf-8")
            res = H.run_render(["--config", bad])
        self.assertEqual(2, res.returncode, res.stderr)

    def test_out_parent_directory_absent_is_exit2(self):
        """--out の親ディレクトリを掘るのは C19 の責務。レンダラは exit 2 で止まる。"""
        with tempfile.TemporaryDirectory() as td:
            cfg = H.write_config(Path(td) / "config.json", H.base_config())
            out = Path(td) / "not-created" / "handout.html"
            res = H.run_render(["--config", cfg, "--out", out])
            self.assertEqual(2, res.returncode, res.stderr)
            self.assertFalse(out.parent.exists(), "レンダラがディレクトリを掘ってはならない")

    def test_stdout_is_html_when_out_absent(self):
        """--out 未指定時の stdout は単一 HTML 全文 (stdout 契約)。"""
        with tempfile.TemporaryDirectory() as td:
            cfg = H.write_config(Path(td) / "config.json", H.base_config())
            res = H.run_render(["--config", cfg])
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertTrue(res.stdout.lstrip().startswith("<!"), res.stdout[:80])
        self.assertIn("</html>", res.stdout)

    def test_stdout_is_result_json_when_out_given(self):
        """--out 指定時の stdout は結果 JSON 1 オブジェクト 1 行 (stdout 契約の全キー)。"""
        with tempfile.TemporaryDirectory() as td:
            res, html_text, out = H.render_html(td, H.base_config())
            self.assertEqual(0, res.returncode, res.stderr)
            payload = res.json_line()
            for key in (
                "html_path", "bytes", "sections", "blocks_by_type", "icons_used",
                "diagrams", "embedded_bytes", "theme", "config_written", "warnings",
            ):
                self.assertIn(key, payload)
            self.assertEqual(str(out), payload["html_path"])
            self.assertEqual(out.stat().st_size, payload["bytes"])
            self.assertEqual(2, payload["sections"])
            self.assertIsNone(payload["config_written"])
            self.assertIsInstance(payload["warnings"], list)

    def test_output_encoding_and_trailing_newline(self):
        """UTF-8 (BOM なし) / 改行 LF / 末尾改行 1 個 (algorithm 24)。"""
        with tempfile.TemporaryDirectory() as td:
            res, html_text, out = H.render_html(td, H.base_config())
            self.assertEqual(0, res.returncode, res.stderr)
            raw = out.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "BOM を付けてはならない")
        self.assertNotIn(b"\r\n", raw, "改行は \\n 固定")
        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.endswith(b"\n\n"), "末尾改行は 1 個")

    def test_stdin_is_not_used(self):
        """stdin は使わない。閉じた stdin でも正常に動く。"""
        with tempfile.TemporaryDirectory() as td:
            cfg = H.write_config(Path(td) / "config.json", H.base_config())
            res = H.run_render(["--config", cfg])
        self.assertEqual(0, res.returncode, res.stderr)

    def test_plugin_root_resolution_falls_through_to_file_relative(self):
        """plugin_root_resolution: HB_ROOT が実在しなければ後続段へ落ち、最初に実在した root を採る。

        script は plugins/guide-doc-generator/scripts/ に置かれるので 4 段目 (__file__ の親の親)
        が必ず成立する。よって不在の HB_ROOT を渡しても exit 0 で生成できなければならない
        (絶対パスの直書きや HB_ROOT 必須化を禁じる担保)。
        """
        with tempfile.TemporaryDirectory() as td:
            cfg = H.write_config(Path(td) / "config.json", H.base_config())
            res = H.run_render(
                ["--config", cfg],
                env_extra={
                    "HB_ROOT": str(Path(td) / "nowhere"),
                    "CLAUDE_PLUGIN_ROOT": str(Path(td) / "nowhere2"),
                },
            )
        self.assertEqual(0, res.returncode, res.stderr)


class ThemeArgvContractTest(unittest.TestCase):
    def test_theme_without_config_out_is_exit2(self):
        """AC-C11-12 後半 / algorithm 1: --theme 単独指定は起動方法の誤りで exit 2。"""
        with tempfile.TemporaryDirectory() as td:
            cfg = H.write_config(Path(td) / "config.json", H.base_config())
            res = H.run_render(["--config", cfg, "--theme", "pop", "--out", Path(td) / "o.html"])
        self.assertEqual(2, res.returncode, res.stderr)

    def test_theme_specified_twice_is_exit1(self):
        """AC-C11-12 前半 / algorithm 4: theme 欄を持つ構成データへ --theme を重ねたら exit 1。"""
        with tempfile.TemporaryDirectory() as td:
            cfg = H.write_config(Path(td) / "config.json", H.base_config(theme="pop"))
            res = H.run_render([
                "--config", cfg,
                "--theme", "pop",
                "--out", Path(td) / "o.html",
                "--config-out", Path(td) / "work.json",
            ])
        self.assertEqual(1, res.returncode, res.stderr)

    def test_theme_writeback_only_touches_theme_field(self):
        """AC-C11-13: --config-out へテーマ 1 欄だけ追記し、他フィールドは非改変。"""
        with tempfile.TemporaryDirectory() as td:
            source = H.base_config()
            cfg = H.write_config(Path(td) / "config.json", source)
            out = Path(td) / "out" / "handout.html"
            out.parent.mkdir(parents=True)
            written = Path(td) / "work" / "config.json"
            written.parent.mkdir(parents=True)
            res = H.run_render([
                "--config", cfg, "--theme", "pop", "--out", out, "--config-out", written,
            ])
            self.assertEqual(0, res.returncode, res.stderr)
            self.assertTrue(written.is_file(), "--config-out が指すパスへ書くこと")
            got = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual("pop", got.get("theme"))
            got.pop("theme")
            self.assertEqual(source, got, "theme 以外のフィールドを書き換えてはならない")
            self.assertEqual(str(written), res.json_line()["config_written"])
            # 同梱物 handout-config.json の writer は C19 だけ (P03 Y-04)
            self.assertFalse((out.parent / "handout-config.json").exists())
            self.assertEqual(
                {"handout.html"}, {p.name for p in out.parent.iterdir()},
                "出力ディレクトリへ書いてよいのは handout.html 1 点のみ",
            )

    def test_default_theme_is_pop_when_nothing_specified(self):
        """algorithm 4: theme 欄も --theme も無ければ既定テーマ pop。"""
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, H.base_config())
            self.assertEqual(0, res.returncode, res.stderr)
            self.assertEqual("pop", res.json_line()["theme"])
        self.assertEqual(["pop"], [el.get("data-hb-theme") for el in H.parse(html_text) if el.tag == "html"])


if __name__ == "__main__":
    unittest.main()

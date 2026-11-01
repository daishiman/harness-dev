"""argv 契約と exit code 契約 (script-brief-C15.json argv / exit_codes / algorithm 1)。

exit 1 (入力データの規約違反 = 差し戻し先は構成データ / アイコンセット正本) と
exit 2 (実行不能 = 差し戻し先は呼び出し側) を混同させないことが本ファイルの主眼。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class ArgvContractTest(unittest.TestCase):
    def test_config_is_required(self):
        """--config は required=true。欠落は実行不能なので exit 2。"""
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            proc = H.run_sprite(self, config_path=None, icon_set=iset)
            H.expect_exit(self, proc, 2, "--config 欠落")

    def test_unknown_flag_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(Path(tmp), H.make_config())
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            proc = H.run_sprite(self, cfg, iset, extra_args=["--nope"])
            H.expect_exit(self, proc, 2, "未知の flag")

    def test_positional_argument_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(Path(tmp), H.make_config())
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            proc = H.run_sprite(self, cfg, iset, extra_args=["extra.json"])
            H.expect_exit(self, proc, 2, "位置引数は契約に無い")

    def test_format_enum_is_closed(self):
        """algorithm 1: --format が 3 語のいずれでもなければ exit 2。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(Path(tmp), H.make_config())
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            for bad in ("Both", "json", "svg", "", "both,manifest"):
                proc = H.run_sprite(self, cfg, iset, fmt=bad)
                H.expect_exit(self, proc, 2, "--format={!r}".format(bad))

    def test_format_values_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            for fmt in H.FORMATS:
                proc = H.run_sprite(self, cfg, iset, fmt=fmt)
                H.expect_exit(self, proc, 0, "--format={}".format(fmt))

    def test_default_format_is_both(self):
        """--format 未指定は both と同一の stdout になる (argv default)。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            default = H.run_sprite(self, cfg, iset)
            explicit = H.run_sprite(self, cfg, iset, fmt=H.DEFAULT_FORMAT)
            H.expect_exit(self, default, 0)
            self.assertEqual(
                default.stdout, explicit.stdout,
                "--format 未指定の既定は both のはず\n" + H.describe(default),
            )

    def test_stdin_is_not_read(self):
        """stdin 契約: 使わない。stdin にゴミを流しても挙動が変わらない。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            clean = H.run_sprite(self, cfg, iset)
            noisy = H.run_sprite(self, cfg, iset, stdin_data="{not json at all")
            self.assertEqual(clean.stdout, noisy.stdout, "stdin を読んでいる疑い\n" + H.describe(noisy))
            self.assertEqual(clean.returncode, noisy.returncode)


class FormatOutputShapeTest(unittest.TestCase):
    def _fixture(self, tmp):
        cfg = H.write_config(
            Path(tmp),
            H.make_config(sections=[H.section("s1", section_icon="check")]),
        )
        iset = H.write_icon_set(Path(tmp), H.make_icon_set())
        return cfg, iset

    def test_symbols_format_is_raw_svg_not_json(self):
        """--format=symbols は symbols_svg の中身のみを raw で出す (stdout 契約)。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp)
            proc = H.run_sprite(self, cfg, iset, fmt="symbols")
            H.expect_exit(self, proc, 0)
            text = H.out_text(proc)
            self.assertIn("<symbol", text, "symbols が SVG を出していない\n" + H.describe(proc))
            try:
                json.loads(text)
            except json.JSONDecodeError:
                pass
            else:
                self.fail("--format=symbols が JSON を出している (raw SVG の契約)\n" + H.describe(proc))

    def test_manifest_format_has_used_only(self):
        """--format=manifest は used 配列を持つ JSON のみ (symbols_svg を含めない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp)
            proc = H.run_sprite(self, cfg, iset, fmt="manifest")
            H.expect_exit(self, proc, 0)
            data = H.parse_stdout_json(self, proc)
            self.assertIsInstance(data, dict, "manifest は JSON オブジェクト\n" + H.describe(proc))
            self.assertIn(H.OUT_USED, data, "manifest に used が無い: {}".format(sorted(data)))
            self.assertNotIn(
                H.OUT_SYMBOLS, data,
                "--format=manifest は参照表のみ。symbols_svg を含めない契約",
            )

    def test_both_format_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp)
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset, fmt="both"))
            self.assertEqual(result[H.OUT_SET_VERSION], "1", "set_version を正本から転記する契約")


class UnrunnableExit2Test(unittest.TestCase):
    """exit_codes 2: --config / --icon-set の不在・JSON 構文エラー。"""

    def test_missing_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            proc = H.run_sprite(self, Path(tmp) / "nope.json", iset)
            H.expect_exit(self, proc, 2, "--config のファイル不在")

    def test_missing_icon_set_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(Path(tmp), H.make_config())
            proc = H.run_sprite(self, cfg, Path(tmp) / "nope.json")
            H.expect_exit(self, proc, 2, "--icon-set のファイル不在")

    def test_config_is_a_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            (Path(tmp) / "dir").mkdir()
            proc = H.run_sprite(self, Path(tmp) / "dir", iset)
            H.expect_exit(self, proc, 2, "--config がディレクトリ")

    def test_broken_json_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(Path(tmp), "{\"sections\": [")
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 2, "構成データの JSON 構文エラー")

    def test_broken_json_icon_set(self):
        """algorithm 3: 正本の構文エラーは exit 2 (規約違反 exit 1 ではない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(Path(tmp), H.make_config())
            iset = H.write_icon_set(Path(tmp), "{icons: }")
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 2, "正本の JSON 構文エラー")

    def test_exit2_diagnostics_go_to_stderr_not_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            proc = H.run_sprite(self, Path(tmp) / "nope.json", iset)
            self.assertNotEqual(H.err_text(proc).strip(), "", "exit 2 で stderr が空\n" + H.describe(proc))
            self.assertEqual(
                H.out_text(proc).strip(), "",
                "診断は stderr のみ。stdout を汚さない契約\n" + H.describe(proc),
            )


class EmptySpriteTest(unittest.TestCase):
    """AC-C15-6 / algorithm 12 / failure_modes: アイコン参照 0 件。"""

    def test_zero_icons_is_exit0_with_empty_sprite(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp),
                H.make_config(sections=[H.section("s1", blocks=[H.block("text")])]),
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            self.assertEqual(result[H.OUT_SYMBOLS], "", "使用 0 件なら symbols_svg は空文字列")
            self.assertEqual(result[H.OUT_USED], [], "使用 0 件なら used は空配列")

    def test_zero_icons_emits_no_empty_defs(self):
        """algorithm 12: 空の <defs> すら出さない (C16 の未使用 symbol 検査へノイズを載せない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(Path(tmp), H.make_config(sections=[H.section("s1")]))
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            proc = H.run_sprite(self, cfg, iset, fmt="symbols")
            H.expect_exit(self, proc, 0)
            self.assertEqual(
                H.out_text(proc).strip(), "",
                "使用 0 件で <defs> や <svg> を出している\n" + H.describe(proc),
            )

    def test_zero_icons_still_reports_unused_in_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(Path(tmp), H.make_config(sections=[H.section("s1")]))
            iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=["check", "cross"]))
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            self.assertEqual(
                result[H.OUT_UNUSED], ["check", "cross"],
                "unused_in_set は正本定義順の未使用名 (診断情報)",
            )


if __name__ == "__main__":
    unittest.main()

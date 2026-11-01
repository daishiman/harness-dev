"""argv と exit code の呼び出し契約 (script-brief-C13.json argv / exit_codes / algorithm 1)。

exit2 = 呼び出し契約違反。exit1 = 入力データ由来の失敗。この 2 つを混ぜないことを固定する。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H


class ArgvContractTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.assets_dir, self.work = H.make_workspace(self, self.tmp)
        H.write_asset(self.assets_dir, "hero.png", H.png_bytes())
        self.config = H.write_config(
            self.work, H.make_config(assets=[H.image_asset("a1", "hero.png")])
        )

    def tearDown(self):
        self._tmp.cleanup()

    # --- 必須 flag ---------------------------------------------------------

    def test_config_missing_is_exit2(self):
        proc = H.run(["--assets-dir", self.assets_dir])
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_assets_dir_missing_is_exit2(self):
        proc = H.run(["--config", self.config])
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_no_args_is_exit2(self):
        proc = H.run([])
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_unknown_flag_is_exit2(self):
        proc = H.run(
            ["--config", self.config, "--assets-dir", self.assets_dir, "--embed-all"]
        )
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_positional_argument_is_exit2(self):
        proc = H.run(["--config", self.config, "--assets-dir", self.assets_dir, "extra"])
        self.assertEqual(2, proc.returncode, H.describe(proc))

    # --- --max-bytes は 1 以上の整数のみ ------------------------------------

    def test_max_bytes_zero_is_exit2(self):
        """AC-C13-5: --max-bytes 0 は exit2。"""
        proc = H.run_embed(self, self.config, self.assets_dir, max_bytes=0)
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_max_bytes_negative_is_exit2(self):
        proc = H.run_embed(self, self.config, self.assets_dir, max_bytes=-1)
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_max_bytes_non_integer_is_exit2(self):
        for value in ("abc", "1.5", "1e6", "", " 12"):
            with self.subTest(value=value):
                proc = H.run_embed(self, self.config, self.assets_dir, max_bytes=value)
                self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_max_bytes_one_is_accepted_as_calling_contract(self):
        """1 は契約上有効。素材が上限を超えるので exit0 + skip になる (契約違反ではない)。"""
        proc = H.run_embed(self, self.config, self.assets_dir, max_bytes=1)
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_default_max_bytes_is_reported_in_summary(self):
        """既定値 5242880 (argv default)。サマリの max_bytes に事実として出る。"""
        proc = H.run_embed(self, self.config, self.assets_dir)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        summary = H.summary_of(self, H.parse_stdout_json(self, proc))
        self.assertEqual(H.DEFAULT_MAX_BYTES, summary.get("max_bytes"), H.describe(proc))

    # --- --assets-dir の実体 ------------------------------------------------

    def test_assets_dir_not_a_directory_is_exit2(self):
        not_dir = self.work / "not-a-dir.txt"
        not_dir.write_text("x", encoding="utf-8")
        proc = H.run_embed(self, self.config, not_dir)
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_assets_dir_absent_is_exit2(self):
        proc = H.run_embed(self, self.config, self.tmp / "no-such-dir")
        self.assertEqual(2, proc.returncode, H.describe(proc))

    # --- --config の実体 ----------------------------------------------------

    def test_config_absent_is_exit1(self):
        """入力データ由来の失敗 (JSON として読めない) は exit1。"""
        proc = H.run_embed(self, self.tmp / "no-such-config.json", self.assets_dir)
        self.assertEqual(1, proc.returncode, H.describe(proc))

    def test_config_broken_json_is_exit1(self):
        broken = self.work / "broken.json"
        broken.write_text("{ this is not json", encoding="utf-8")
        proc = H.run_embed(self, broken, self.assets_dir)
        self.assertEqual(1, proc.returncode, H.describe(proc))

    def test_asset_reference_wrong_type_is_exit1(self):
        """素材参照キーの型が不正 (exit_codes 1)。"""
        bad = H.make_config(assets=[H.image_asset("a1", "hero.png")])
        bad["assets"][0]["src"] = 12345
        proc = H.run_embed(self, H.write_config(self.work, bad, "bad.json"), self.assets_dir)
        self.assertEqual(1, proc.returncode, H.describe(proc))

    # --- stdout / --out の二面出力の禁止 -------------------------------------

    def test_stdout_carries_config_when_out_omitted(self):
        proc = H.run_embed(self, self.config, self.assets_dir)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        payload = H.parse_stdout_json(self, proc)
        self.assertEqual("研修ハンドアウト", payload.get("title"), H.describe(proc))

    def test_stdout_is_empty_when_out_given(self):
        out = self.work / "embedded.json"
        proc = H.run_embed(self, self.config, self.assets_dir, out=out)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))
        self.assertTrue(out.is_file(), "--out が書かれていない: {}".format(out))

    def test_out_file_content_equals_stdout_of_equivalent_run(self):
        out = self.work / "embedded.json"
        proc_file = H.run_embed(self, self.config, self.assets_dir, out=out)
        proc_stdout = H.run_embed(self, self.config, self.assets_dir)
        self.assertEqual(0, proc_file.returncode, H.describe(proc_file))
        self.assertEqual(0, proc_stdout.returncode, H.describe(proc_stdout))
        self.assertEqual(
            out.read_bytes(),
            proc_stdout.stdout,
            "--out のバイト列と stdout のバイト列が一致しない",
        )

    def test_out_into_missing_directory_is_exit1(self):
        """--out への書き込み失敗は入力由来の失敗 (exit1)。"""
        proc = H.run_embed(
            self, self.config, self.assets_dir, out=self.tmp / "no-such-dir" / "o.json"
        )
        self.assertEqual(1, proc.returncode, H.describe(proc))

    # --- stdin ---------------------------------------------------------------

    def test_stdin_is_ignored(self):
        """stdin は使用しない。与えられても読まない (stdin 契約)。"""
        proc_with = H.run_embed(
            self, self.config, self.assets_dir, stdin_data='{"title":"侵入"}'
        )
        proc_without = H.run_embed(self, self.config, self.assets_dir)
        self.assertEqual(0, proc_with.returncode, H.describe(proc_with))
        self.assertEqual(proc_without.stdout, proc_with.stdout, "stdin が出力へ影響している")


if __name__ == "__main__":
    unittest.main()

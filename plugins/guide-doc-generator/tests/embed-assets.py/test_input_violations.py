"""AC-C13-5: 違反系入力の exit code と、失敗時に出力を残さないこと。

exit1 (入力データ由来) と exit2 (呼び出し契約違反) の切り分けは algorithm 4 の判断に従う:
  - 宣言された素材が無い    -> exit1 (構成データの誤り。黙って続けると素材の無い資料を出荷する)
  - 絶対パス / assets-dir 脱出 -> exit2 (呼び出し契約違反)
どちらでも出力は書かない (部分書き込みを残さない)。
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import _harness as H

SENTINEL = '{"pre-existing": true}\n'


class InputViolationTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.assets_dir, self.work = H.make_workspace(self, self.tmp)
        H.write_asset(self.assets_dir, "ok.png", H.png_bytes())
        self.outside = self.tmp / "outside"
        self.outside.mkdir(parents=True, exist_ok=True)
        (self.outside / "secret.png").write_bytes(H.png_bytes())

    def tearDown(self):
        self._tmp.cleanup()

    def _config_with_src(self, src, name="c.json"):
        config = H.make_config(
            assets=[H.image_asset("ok", "ok.png"), H.image_asset("bad", src)]
        )
        return H.write_config(self.work, config, name)

    def _run_src(self, src, out=None, name="c.json"):
        return H.run_embed(self, self._config_with_src(src, name), self.assets_dir, out=out)

    # --- exit1: 宣言された素材が無い ----------------------------------------

    def test_missing_asset_file_is_exit1(self):
        proc = self._run_src("no-such-image.png")
        self.assertEqual(1, proc.returncode, H.describe(proc))

    def test_missing_asset_is_not_downgraded_to_warning(self):
        """failure_modes: 上限超過と同じ warning 扱いにしない。"""
        proc = self._run_src("no-such-image.png")
        self.assertEqual("", H.out_text(proc), "失敗したのに構成データを出している")

    def test_directory_as_asset_is_exit1(self):
        (self.assets_dir / "adir").mkdir()
        proc = self._run_src("adir")
        self.assertEqual(1, proc.returncode, H.describe(proc))

    @unittest.skipIf(os.geteuid() == 0, "root では権限エラーを再現できない")
    def test_unreadable_asset_is_exit1(self):
        path = H.write_asset(self.assets_dir, "locked.png", H.png_bytes())
        path.chmod(0o000)
        try:
            proc = self._run_src("locked.png")
            self.assertEqual(1, proc.returncode, H.describe(proc))
        finally:
            path.chmod(0o644)

    # --- exit2: パス脱出 -----------------------------------------------------

    def test_absolute_path_reference_is_exit2(self):
        proc = self._run_src(str(self.outside / "secret.png"))
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_parent_escape_reference_is_exit2(self):
        proc = self._run_src("../outside/secret.png")
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_nested_parent_escape_reference_is_exit2(self):
        """normpath 後に外へ出るなら、途中で潜っていても違反 (algorithm 4)。"""
        H.write_asset(self.assets_dir, "sub/keep.png", H.png_bytes())
        proc = self._run_src("sub/../../outside/secret.png")
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_symlink_pointing_outside_is_exit2(self):
        link = self.assets_dir / "link.png"
        try:
            link.symlink_to(self.outside / "secret.png")
        except OSError as exc:  # pragma: no cover - 環境依存
            self.skipTest("symlink を作成できない: {}".format(exc))
        proc = self._run_src("link.png")
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_symlinked_directory_escape_is_exit2(self):
        link_dir = self.assets_dir / "outlink"
        try:
            link_dir.symlink_to(self.outside, target_is_directory=True)
        except OSError as exc:  # pragma: no cover - 環境依存
            self.skipTest("symlink を作成できない: {}".format(exc))
        proc = self._run_src("outlink/secret.png")
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_inside_relative_path_is_accepted(self):
        """脱出検査が正常な相対参照まで巻き込まないこと (偽陽性の固定)。"""
        H.write_asset(self.assets_dir, "sub/deep/inner.png", H.png_bytes())
        proc = self._run_src("sub/deep/../deep/inner.png")
        self.assertEqual(0, proc.returncode, H.describe(proc))

    # --- 失敗時に出力を残さない ------------------------------------------------

    def test_out_file_not_created_on_exit1(self):
        out = self.work / "never.json"
        proc = self._run_src("no-such-image.png", out=out)
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertFalse(out.exists(), "失敗したのに --out が作られている")

    def test_out_file_not_created_on_exit2(self):
        out = self.work / "never2.json"
        proc = self._run_src("../outside/secret.png", out=out)
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertFalse(out.exists(), "失敗したのに --out が作られている")

    def test_existing_out_file_is_untouched_on_failure(self):
        """AC-C13-5: 既存ファイルが書き換わらない (原子的差し替え)。"""
        out = self.work / "existing.json"
        out.write_text(SENTINEL, encoding="utf-8")
        for src, expected in (("no-such-image.png", 1), ("../outside/secret.png", 2)):
            with self.subTest(src=src):
                proc = self._run_src(src, out=out, name="c-{}.json".format(expected))
                self.assertEqual(expected, proc.returncode, H.describe(proc))
                self.assertEqual(SENTINEL, out.read_text(encoding="utf-8"))

    def test_no_temporary_files_left_behind_on_failure(self):
        out = self.work / "atomic.json"
        proc = self._run_src("no-such-image.png", out=out)
        self.assertEqual(1, proc.returncode, H.describe(proc))
        leftovers = [p.name for p in self.work.iterdir() if p.name.startswith("atomic.json")]
        self.assertEqual([], leftovers, "テンポラリが残っている: {}".format(leftovers))

    # --- assets-dir は read-only ---------------------------------------------

    def test_assets_dir_is_never_modified(self):
        """argv --assets-dir: read-only であり本 script は 1 バイトも書かない。"""
        before = H.tree_snapshot(self.assets_dir)
        H.run_embed(
            self,
            self._config_with_src("ok.png", "same.json"),
            self.assets_dir,
            out=self.work / "o.json",
        )
        self._run_src("no-such-image.png", name="fail.json")
        self.assertEqual(before, H.tree_snapshot(self.assets_dir), "assets-dir が変更された")


if __name__ == "__main__":
    unittest.main()

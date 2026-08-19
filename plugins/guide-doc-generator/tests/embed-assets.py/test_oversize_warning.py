"""AC-C13-3 / C30: 上限超過は生成を止めず warning。exit0 のまま該当素材だけ skip する。

「大きいことは事実であって作者の誤りではない」という failure_modes の判断を、
exit code と出力フィールドと stderr 行形式の 3 面で固定する。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H

SMALL_NAME = "small.png"
BIG_NAME = "big.pdf"


class OversizeSkipTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.assets_dir, self.work = H.make_workspace(self, self.tmp)

        self.small = H.png_bytes()
        self.big = H.pdf_bytes(payload_size=4096)
        H.write_asset(self.assets_dir, SMALL_NAME, self.small)
        H.write_asset(self.assets_dir, BIG_NAME, self.big)
        # small < limit < big になる閾値を素材の実サイズから決める。
        self.limit = len(self.small) + 1
        self.assertLess(self.limit, len(self.big), "fixture の前提が壊れている")

        config = H.make_config(
            assets=[H.image_asset("shot", SMALL_NAME)],
            attachments=[H.attachment("manual", BIG_NAME, H.MIME_PDF, BIG_NAME)],
        )
        self.config_path = H.write_config(self.work, config)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, max_bytes=None, out=None):
        proc = H.run_embed(
            self,
            self.config_path,
            self.assets_dir,
            max_bytes=self.limit if max_bytes is None else max_bytes,
            out=out,
        )
        if out is not None:
            return proc, H.load_json_file(self, out)
        return proc, H.parse_stdout_json(self, proc)

    def test_exit_code_is_zero_despite_skip(self):
        """AC-C13-3 / exit_codes 0: skip が 1 件以上あっても 0。"""
        proc, _out = self._run()
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_oversize_entry_has_no_data_uri(self):
        _proc, out = self._run()
        entry = H.find_entry(self, out, "attachments", "manual")
        self.assertIsNone(entry.get("data_uri"), "上限超過素材に data_uri が付いている")

    def test_oversize_entry_records_status_reason_and_bytes(self):
        _proc, out = self._run()
        entry = H.find_entry(self, out, "attachments", "manual")
        self.assertEqual(H.STATUS_SKIPPED, entry.get("embed_status"))
        self.assertTrue(entry.get("embed_skip_reason"), "embed_skip_reason が空")
        self.assertEqual(len(self.big), entry.get("source_bytes"))

    def test_oversize_entry_records_assets_dir_relative_path(self):
        """algorithm 7: 素材の assets-dir 相対パスを素材オブジェクトへ書く (代替手段の材料)。"""
        _proc, out = self._run()
        entry = H.find_entry(self, out, "attachments", "manual")
        serialized = repr(entry)
        self.assertIn(BIG_NAME, serialized, "相対パスが素材オブジェクトへ残っていない: {}".format(serialized))
        self.assertNotIn(
            str(self.assets_dir), serialized, "絶対パスを書いている (機械依存の値を出力へ混ぜない)"
        )

    def test_other_asset_in_same_run_is_still_embedded(self):
        """AC-C13-3: 同じ実行内の他素材は埋め込まれている (生成を止めない)。"""
        _proc, out = self._run()
        entry = H.find_entry(self, out, "assets", "shot")
        self.assertEqual(H.STATUS_EMBEDDED, entry.get("embed_status"))
        self.assertTrue(H.data_uri_of(self, entry).startswith("data:{};base64,".format(H.MIME_PNG)))

    def test_stderr_has_one_warn_line_with_hint(self):
        """stderr 契約: `WARN <asset_id>: <reason>; 代替手段: <hint>` を 1 素材 1 行。"""
        proc, _out = self._run()
        warns = H.warn_lines(proc)
        self.assertEqual(1, len(warns), H.describe(proc))
        line = warns[0]
        self.assertTrue(
            line.startswith(H.WARN_PREFIX + "manual: "),
            "WARN 行が `WARN <asset_id>: ` 形式でない: {}".format(line),
        )
        self.assertIn(H.WARN_HINT_SEP, line, "代替手段が示されていない: {}".format(line))
        self.assertTrue(line.split(H.WARN_HINT_SEP, 1)[1].strip(), "代替手段が空: {}".format(line))

    def test_warn_goes_to_stderr_not_stdout(self):
        proc, _out = self._run()
        self.assertNotIn(H.WARN_PREFIX, H.out_text(proc), "WARN が stdout を汚している")

    def test_summary_counts_split_embedded_and_skipped(self):
        _proc, out = self._run()
        summary = H.summary_of(self, out)
        self.assertEqual(self.limit, summary.get("max_bytes"))
        self.assertEqual(1, summary.get("embedded_count"))
        self.assertEqual(1, summary.get("skipped_count"))
        self.assertEqual(
            len(self.small) + len(self.big),
            summary.get("total_source_bytes"),
            "合計原本バイト数は skip 分も含む事実の記録",
        )

    def test_summary_warning_entry_matches_stderr(self):
        proc, out = self._run()
        warnings = H.summary_of(self, out).get("warnings")
        self.assertIsInstance(warnings, list, H.describe(proc))
        self.assertEqual(1, len(warnings), H.describe(proc))
        self.assertEqual("manual", warnings[0].get("asset_id"))
        self.assertTrue(warnings[0].get("hint"), "サマリ側の hint が空")

    def test_cumulative_total_is_not_a_threshold(self):
        """argv --max-bytes: 累積合計に対する閾値は持たない。

        1 件あたりは上限内だが合計が上限を超える構成で、全件が埋め込まれること。
        """
        limit = max(len(self.small), len(self.big)) + 1
        self.assertLess(limit, len(self.small) + len(self.big), "fixture の前提が壊れている")
        proc, out = self._run(max_bytes=limit)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        summary = H.summary_of(self, out)
        self.assertEqual(0, summary.get("skipped_count"), H.describe(proc))
        self.assertEqual(2, summary.get("embedded_count"), H.describe(proc))

    def test_boundary_equal_to_limit_is_embedded(self):
        """algorithm 7: 「超える」素材を skip する。上限ちょうどは埋め込む。"""
        proc, out = self._run(max_bytes=len(self.big))
        self.assertEqual(0, proc.returncode, H.describe(proc))
        entry = H.find_entry(self, out, "attachments", "manual")
        self.assertEqual(H.STATUS_EMBEDDED, entry.get("embed_status"), H.describe(proc))

    def test_boundary_one_below_limit_is_skipped(self):
        proc, out = self._run(max_bytes=len(self.big) - 1)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        entry = H.find_entry(self, out, "attachments", "manual")
        self.assertEqual(H.STATUS_SKIPPED, entry.get("embed_status"), H.describe(proc))

    def test_skip_still_writes_out_file(self):
        """skip は失敗ではない。--out は正常に書かれる。"""
        out_path = self.work / "embedded.json"
        proc, _out = self._run(out=out_path)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        self.assertTrue(out_path.is_file())


if __name__ == "__main__":
    unittest.main()

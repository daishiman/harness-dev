"""AC-C13-1: ローカル画像が base64 data URI として構成データへ実体埋め込みされること (C5)。

利用者要件の根幹はここ。リンク参照ではなく HTML 内へ実体を持たせるため、
C13 の出力段階で data_uri が入っており、元のローカルパスが data_uri 側へ残らないことを固定する。
"""

from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

import _harness as H


class ImageEmbeddingTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.assets_dir, self.work = H.make_workspace(self, self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def _run_single_png(self, relpath="img/hero.png"):
        self.png = H.png_bytes()
        H.write_asset(self.assets_dir, relpath, self.png)
        config = H.make_config(assets=[H.image_asset("hero", relpath)])
        proc = H.run_embed(
            self, H.write_config(self.work, config), self.assets_dir
        )
        self.assertEqual(0, proc.returncode, H.describe(proc))
        out = H.parse_stdout_json(self, proc)
        return proc, out, H.find_entry(self, out, "assets", "hero")

    def test_png_gets_png_data_uri(self):
        """AC-C13-1: data:image/png;base64, で始まる data_uri が入る。"""
        proc, _out, entry = self._run_single_png()
        uri = H.data_uri_of(self, entry)
        self.assertTrue(
            uri.startswith("data:{};base64,".format(H.MIME_PNG)),
            "data_uri が data:image/png;base64, で始まらない: {}\n{}".format(uri[:80], H.describe(proc)),
        )

    def test_payload_round_trips_to_original_bytes(self):
        """埋め込みは無加工。再エンコード・リサイズ・圧縮を行わない (algorithm 8)。"""
        _proc, _out, entry = self._run_single_png()
        payload = H.data_uri_payload(self, H.data_uri_of(self, entry))
        self.assertEqual(self.png, base64.b64decode(payload), "原本バイトを復元できない")

    def test_embed_status_is_embedded(self):
        _proc, _out, entry = self._run_single_png()
        self.assertEqual(H.STATUS_EMBEDDED, entry.get("embed_status"))

    def test_source_path_does_not_leak_into_data_uri(self):
        """AC-C13-1: 元のローカルパス文字列が data_uri 側に残らない。"""
        relpath = "img/hero.png"
        _proc, _out, entry = self._run_single_png(relpath)
        uri = H.data_uri_of(self, entry)
        self.assertNotIn(relpath, uri)
        self.assertNotIn("hero.png", uri)
        self.assertNotIn(str(self.assets_dir), uri)

    def test_source_bytes_and_encoded_chars_are_recorded(self):
        """algorithm 8: source_bytes / encoded_chars を併記する。"""
        _proc, _out, entry = self._run_single_png()
        uri = H.data_uri_of(self, entry)
        self.assertEqual(len(self.png), entry.get("source_bytes"))
        self.assertEqual(
            len(H.data_uri_payload(self, uri)),
            entry.get("encoded_chars"),
            "encoded_chars が base64 payload の文字数と一致しない",
        )

    def test_skip_reason_absent_when_embedded(self):
        _proc, _out, entry = self._run_single_png()
        self.assertIsNone(entry.get("embed_skip_reason"))

    def test_original_asset_fields_are_preserved(self):
        """C13 は畳み込むだけで、C12 が確定した既存フィールドを壊さない。"""
        _proc, _out, entry = self._run_single_png()
        for key, expected in (
            ("id", "hero"),
            ("kind", "image"),
            ("alt", "画面の説明"),
            ("role", "screenshot"),
        ):
            with self.subTest(key=key):
                self.assertEqual(expected, entry.get(key))

    def test_src_is_not_rewritten_to_data_uri(self):
        """data URI は data_uri フィールドへ入る。src を破壊すると C20 の逆抽出が原本参照を失う。"""
        relpath = "img/hero.png"
        _proc, _out, entry = self._run_single_png(relpath)
        self.assertEqual(relpath, entry.get("src"))

    def test_multiple_images_all_embedded_in_document_order(self):
        for name, data in (
            ("a.png", H.png_bytes()),
            ("b.jpg", H.jpeg_bytes()),
            ("c.gif", H.gif_bytes()),
            ("d.webp", H.webp_bytes()),
            ("e.svg", H.svg_bytes()),
        ):
            H.write_asset(self.assets_dir, name, data)
        ids = ["a", "b", "c", "d", "e"]
        config = H.make_config(
            assets=[
                H.image_asset(i, n)
                for i, n in zip(ids, ["a.png", "b.jpg", "c.gif", "d.webp", "e.svg"])
            ]
        )
        proc = H.run_embed(self, H.write_config(self.work, config), self.assets_dir)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        out = H.parse_stdout_json(self, proc)
        self.assertEqual(ids, [a.get("id") for a in out["assets"]], "assets の出現順が変わっている")
        for asset_id in ids:
            with self.subTest(asset_id=asset_id):
                entry = H.find_entry(self, out, "assets", asset_id)
                self.assertEqual(H.STATUS_EMBEDDED, entry.get("embed_status"))
                self.assertTrue(H.data_uri_of(self, entry).startswith("data:image/"))

    def test_summary_counts_embedded_assets(self):
        """algorithm 9: 資料単位サマリ asset_embedding。"""
        _proc, out, _entry = self._run_single_png()
        summary = H.summary_of(self, out)
        for field in H.SUMMARY_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, summary)
        self.assertEqual(1, summary.get("embedded_count"))
        self.assertEqual(0, summary.get("skipped_count"))
        self.assertEqual(len(self.png), summary.get("total_source_bytes"))

    def test_no_warning_for_clean_png(self):
        proc, _out, _entry = self._run_single_png()
        self.assertEqual([], H.warn_lines(proc), H.describe(proc))

    def test_stderr_summary_is_present_on_success(self):
        """stderr 契約: 人間向けサマリは exit0 でも出る。"""
        proc, _out, _entry = self._run_single_png()
        self.assertNotEqual("", H.err_text(proc).strip(), "stderr サマリが出ていない")


if __name__ == "__main__":
    unittest.main()

"""AC-C13-2 と algorithm 5 / 6: 自前 MIME 対応表とバイトシグネチャ優先。

mimetypes (OS 依存) を使わないことは test_stdlib_boundary.py 側で固定する。
ここでは「同一入力から出る MIME 値」そのものを契約として固定する。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H


class AttachmentMimeTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.assets_dir, self.work = H.make_workspace(self, self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, config):
        proc = H.run_embed(self, H.write_config(self.work, config), self.assets_dir)
        return proc, H.parse_stdout_json(self, proc)

    def test_xlsx_zip_pdf_use_own_table_values(self):
        """AC-C13-2: 3 件とも data_uri を持ち MIME が自前対応表の値と一致する。"""
        H.write_asset(self.assets_dir, "book.xlsx", H.xlsx_bytes())
        H.write_asset(self.assets_dir, "bundle.zip", H.zip_bytes())
        H.write_asset(self.assets_dir, "manual.pdf", H.pdf_bytes())
        config = H.make_config(
            attachments=[
                H.attachment("x", "book.xlsx", H.MIME_XLSX, "book.xlsx"),
                H.attachment("z", "bundle.zip", H.MIME_ZIP, "bundle.zip"),
                H.attachment("p", "manual.pdf", H.MIME_PDF, "manual.pdf"),
            ]
        )
        proc, out = self._run(config)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        for att_id, expected in (("x", H.MIME_XLSX), ("z", H.MIME_ZIP), ("p", H.MIME_PDF)):
            with self.subTest(att_id=att_id):
                entry = H.find_entry(self, out, "attachments", att_id)
                uri = H.data_uri_of(self, entry)
                self.assertEqual(expected, H.data_uri_mime(self, uri), H.describe(proc))
                self.assertEqual(H.STATUS_EMBEDDED, entry.get("embed_status"))

    def test_extension_lookup_is_case_insensitive(self):
        """algorithm 5: 表は小文字化した拡張子で引く。"""
        H.write_asset(self.assets_dir, "MANUAL.PDF", H.pdf_bytes())
        config = H.make_config(
            attachments=[H.attachment("p", "MANUAL.PDF", H.MIME_PDF, "MANUAL.PDF")]
        )
        proc, out = self._run(config)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        entry = H.find_entry(self, out, "attachments", "p")
        self.assertEqual(H.MIME_PDF, H.data_uri_mime(self, H.data_uri_of(self, entry)))

    def test_unknown_extension_falls_back_to_octet_stream_with_warning(self):
        """failure_modes: 未知拡張子は application/octet-stream で埋め込み継続 (exit0) + warning 1 行。"""
        H.write_asset(self.assets_dir, "data.qqq", H.bin_bytes())
        config = H.make_config(
            attachments=[H.attachment("u", "data.qqq", H.MIME_OCTET, "data.qqq")]
        )
        proc, out = self._run(config)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        entry = H.find_entry(self, out, "attachments", "u")
        self.assertEqual(H.MIME_OCTET, H.data_uri_mime(self, H.data_uri_of(self, entry)))
        self.assertEqual(H.STATUS_EMBEDDED, entry.get("embed_status"))
        warns = H.warn_lines(proc)
        self.assertEqual(1, len(warns), "未知拡張子の warning は 1 行: {}".format(H.describe(proc)))
        self.assertIn("u", warns[0])

    def test_image_signature_wins_over_extension(self):
        """algorithm 6: 拡張子とシグネチャが食い違う画像はシグネチャ由来の MIME を採用し warning。"""
        H.write_asset(self.assets_dir, "shot.png", H.jpeg_bytes())
        config = H.make_config(assets=[H.image_asset("s", "shot.png")])
        proc, out = self._run(config)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        entry = H.find_entry(self, out, "assets", "s")
        self.assertEqual(
            "image/jpeg",
            H.data_uri_mime(self, H.data_uri_of(self, entry)),
            "実バイト (JPEG) ではなく拡張子 (.png) を採用している: {}".format(H.describe(proc)),
        )
        self.assertEqual(1, len(H.warn_lines(proc)), H.describe(proc))

    def test_matching_signature_produces_no_warning(self):
        for name, data, mime in (
            ("a.png", H.png_bytes(), "image/png"),
            ("b.jpg", H.jpeg_bytes(), "image/jpeg"),
            ("c.gif", H.gif_bytes(), "image/gif"),
            ("d.webp", H.webp_bytes(), "image/webp"),
            ("e.svg", H.svg_bytes(), "image/svg+xml"),
        ):
            with self.subTest(name=name):
                assets_dir, work = H.make_workspace(self, self.tmp / name)
                H.write_asset(assets_dir, name, data)
                config = H.make_config(assets=[H.image_asset("i", name)])
                proc = H.run_embed(self, H.write_config(work, config), assets_dir)
                self.assertEqual(0, proc.returncode, H.describe(proc))
                out = H.parse_stdout_json(self, proc)
                entry = H.find_entry(self, out, "assets", "i")
                self.assertEqual(mime, H.data_uri_mime(self, H.data_uri_of(self, entry)))
                self.assertEqual([], H.warn_lines(proc), H.describe(proc))

    def test_svg_leading_whitespace_is_tolerated(self):
        """algorithm 6: SVG は先頭非空白が '<' であることで判定する。"""
        H.write_asset(self.assets_dir, "fig.svg", b"\n  \t" + H.svg_bytes())
        config = H.make_config(assets=[H.image_asset("f", "fig.svg")])
        proc, out = self._run(config)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        entry = H.find_entry(self, out, "assets", "f")
        self.assertEqual("image/svg+xml", H.data_uri_mime(self, H.data_uri_of(self, entry)))
        self.assertEqual([], H.warn_lines(proc), H.describe(proc))

    def test_non_image_attachment_is_not_signature_checked(self):
        """algorithm 6 は画像に限る。pdf の中身が zip でも MIME は表どおり application/pdf。"""
        H.write_asset(self.assets_dir, "weird.pdf", H.zip_bytes())
        config = H.make_config(
            attachments=[H.attachment("w", "weird.pdf", H.MIME_PDF, "weird.pdf")]
        )
        proc, out = self._run(config)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        entry = H.find_entry(self, out, "attachments", "w")
        self.assertEqual(H.MIME_PDF, H.data_uri_mime(self, H.data_uri_of(self, entry)))

    def test_warning_is_recorded_in_summary_warnings(self):
        """algorithm 9: サマリの warnings に {asset_id, reason, hint} が入る。"""
        H.write_asset(self.assets_dir, "data.qqq", H.bin_bytes())
        config = H.make_config(
            attachments=[H.attachment("u", "data.qqq", H.MIME_OCTET, "data.qqq")]
        )
        proc, out = self._run(config)
        warnings = H.summary_of(self, out).get("warnings")
        self.assertIsInstance(warnings, list, H.describe(proc))
        self.assertEqual(1, len(warnings), H.describe(proc))
        self.assertEqual({"asset_id", "reason", "hint"}, set(warnings[0].keys()))
        self.assertEqual("u", warnings[0]["asset_id"])


if __name__ == "__main__":
    unittest.main()

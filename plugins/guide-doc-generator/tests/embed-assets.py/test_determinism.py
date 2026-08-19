"""AC-C13-4 / C29: 同一入力から同一バイト列。

決定論を壊す既知の 4 経路を個別に固定する:
  (a) base64.encodebytes による 76 文字ごとの改行混入 (algorithm 8)
  (b) 辞書のハッシュ順に依存した走査順 (algorithm 3)
  (c) OS 依存の MIME 解決 (algorithm 5) — 値の同一性としてここで、実装面は境界テストで
  (d) json.dump のシリアライズ形式のぶれ (algorithm 10)
"""

from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class DeterminismTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.assets_dir, self.work = H.make_workspace(self, self.tmp)

        H.write_asset(self.assets_dir, "hero.png", H.png_bytes(payload_size=2048))
        H.write_asset(self.assets_dir, "sheet.xlsx", H.xlsx_bytes(extra=512))
        H.write_asset(self.assets_dir, "manual.pdf", H.pdf_bytes(payload_size=1024))
        config = H.make_config(
            assets=[H.image_asset("hero", "hero.png", alt="日本語の代替テキスト")],
            attachments=[
                H.attachment("sheet", "sheet.xlsx", H.MIME_XLSX, "sheet.xlsx", "配布した素材フォルダを参照"),
                H.attachment("manual", "manual.pdf", H.MIME_PDF, "manual.pdf"),
            ],
        )
        self.config_path = H.write_config(self.work, config)
        self.input_keys = list(config.keys())

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, **kwargs):
        proc = H.run_embed(self, self.config_path, self.assets_dir, **kwargs)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        return proc

    def test_two_runs_are_byte_identical(self):
        """AC-C13-4: 2 回実行の出力バイト列が完全一致する。"""
        first = self._run()
        second = self._run()
        self.assertEqual(first.stdout, second.stdout, "stdout のバイト列が 2 回で異なる")

    def test_out_file_is_byte_identical_across_runs(self):
        out = self.work / "embedded.json"
        self._run(out=out)
        first = out.read_bytes()
        self._run(out=out)
        self.assertEqual(first, out.read_bytes(), "--out のバイト列が 2 回で異なる")

    def test_hash_randomization_does_not_change_output(self):
        """algorithm 3: 走査順は構成データ上の出現順。辞書のハッシュ順に依存しない。"""
        outputs = set()
        for seed in ("0", "1", "12345"):
            proc = H.run(
                [
                    "--config",
                    self.config_path,
                    "--assets-dir",
                    self.assets_dir,
                ],
                env=H.clean_env(PYTHONHASHSEED=seed),
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))
            outputs.add(proc.stdout)
        self.assertEqual(1, len(outputs), "PYTHONHASHSEED によって出力が変わる")

    def test_base64_payload_has_no_newline(self):
        """algorithm 8: base64.encodebytes は使わない (76 文字ごとの改行を挟むため)。"""
        out = H.parse_stdout_json(self, self._run())
        for collection, entry_id in (("assets", "hero"), ("attachments", "sheet")):
            with self.subTest(entry_id=entry_id):
                uri = H.data_uri_of(self, H.find_entry(self, out, collection, entry_id))
                payload = H.data_uri_payload(self, uri)
                self.assertNotIn("\n", payload)
                self.assertNotIn("\r", payload)
                self.assertNotIn(" ", payload)

    def test_base64_payload_is_standard_alphabet(self):
        out = H.parse_stdout_json(self, self._run())
        uri = H.data_uri_of(self, H.find_entry(self, out, "assets", "hero"))
        payload = H.data_uri_payload(self, uri)
        try:
            base64.b64decode(payload, validate=True)
        except Exception as exc:  # pragma: no cover - 赤の診断用
            self.fail("標準 base64 として復号できない ({}): {}".format(exc, payload[:60]))

    def test_output_uses_ensure_ascii_false(self):
        """stdout 契約: UTF-8 / ensure_ascii=false。"""
        text = H.out_text(self._run())
        self.assertIn("日本語の代替テキスト", text, "非 ASCII が \\uXXXX へ退避されている")
        self.assertNotIn("\\u", text)

    def test_output_uses_indent_two_and_single_trailing_newline(self):
        """algorithm 10: indent=2 / 末尾改行 1 個。"""
        raw = self._run().stdout
        text = raw.decode("utf-8")
        self.assertTrue(text.endswith("}\n"), "末尾が `}` + 改行 1 個でない")
        self.assertFalse(text.endswith("\n\n"), "末尾改行が 2 個以上ある")
        self.assertIn('\n  "title"', text, "indent=2 になっていない")
        self.assertNotIn("\r\n", text, "改行が CRLF になっている")

    def test_input_key_order_is_preserved(self):
        """stdout 契約: キー順は入力の順序を保存する (sort_keys しない)。"""
        text = H.out_text(self._run())
        positions = []
        for key in self.input_keys:
            index = text.find('"{}"'.format(key))
            self.assertNotEqual(-1, index, "入力キー {} が出力から消えている".format(key))
            positions.append(index)
        self.assertEqual(sorted(positions), positions, "入力のキー順が保存されていない")

    def test_reordered_input_keys_change_output_order_only(self):
        """キー順保存は「入力に従う」であって「固定順へ正規化する」ではない。"""
        original = json.loads(self.config_path.read_text(encoding="utf-8"))
        reordered = {k: original[k] for k in reversed(list(original.keys()))}
        other = H.write_config(self.work, reordered, "reordered.json")
        proc = H.run_embed(self, other, self.assets_dir)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        text = H.out_text(proc)
        self.assertLess(
            text.find('"sections"'),
            text.find('"schema_version"'),
            "入力のキー順に追随していない",
        )

    def test_duplicate_reference_yields_identical_data_uri(self):
        """failure_modes: 同一素材が複数箇所から参照されても同じ data URI 文字列になる。"""
        config = H.make_config(
            assets=[
                H.image_asset("a", "hero.png"),
                H.image_asset("b", "hero.png"),
                H.image_asset("c", "./hero.png"),
            ]
        )
        proc = H.run_embed(self, H.write_config(self.work, config, "dup.json"), self.assets_dir)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        out = H.parse_stdout_json(self, proc)
        uris = {
            H.data_uri_of(self, H.find_entry(self, out, "assets", i)) for i in ("a", "b", "c")
        }
        self.assertEqual(1, len(uris), "同一素材から異なる data URI が出ている")

    def test_output_does_not_leak_absolute_paths(self):
        """機械依存の絶対パスが出力へ混ざると別マシンでバイト一致しない。"""
        text = H.out_text(self._run())
        self.assertNotIn(str(self.assets_dir), text)
        self.assertNotIn(str(self.tmp), text)

    def test_output_has_no_timestamp_like_field(self):
        """時刻を書くと 2 回実行のバイト一致が壊れる。サマリは件数とバイト数だけ。"""
        summary = H.summary_of(self, H.parse_stdout_json(self, self._run()))
        for key in summary.keys():
            with self.subTest(key=key):
                self.assertNotIn("time", key.lower())
                self.assertNotIn("date", key.lower())
                self.assertNotIn("generated", key.lower())


if __name__ == "__main__":
    unittest.main()

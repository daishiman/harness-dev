"""納品フォルダだけを移しても図解選定の証跡を使えること。"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


def receipt_for(config):
    digest = hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
    return {"config_sha256": digest, "decision_log": []}


class SelectionReceiptPlacement(unittest.TestCase):
    def test_receipt_is_copied_with_the_unchanged_delivery_config(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = H.normalized_config(self)
            source = H.write_config(root / "source.json", config)
            receipt = Path(str(source) + ".visual-selection.json")
            receipt.write_text(json.dumps(receipt_for(config), ensure_ascii=False), encoding="utf-8")
            result = H.run(["--config", source, "--out-dir", root / "out", "--place-config"])
            self.assertEqual(0, result.returncode, H.describe(result))
            dest = H.resolved_path(self, result)
            self.assertEqual(source.read_bytes(), (dest / "handout-config.json").read_bytes())
            self.assertEqual(receipt.read_bytes(), (dest / "handout-config.json.visual-selection.json").read_bytes())

    def test_stale_receipt_is_rejected_before_placement(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = H.normalized_config(self)
            source = H.write_config(root / "source.json", config)
            receipt = receipt_for(config)
            receipt["config_sha256"] = "0" * 64
            Path(str(source) + ".visual-selection.json").write_text(json.dumps(receipt), encoding="utf-8")
            result = H.run(["--config", source, "--out-dir", root / "out", "--place-config"])
            self.assertEqual(1, result.returncode, H.describe(result))
            self.assertFalse((root / "out").exists())

    def test_existing_config_without_receipt_remains_supported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = H.write_config(root / "source.json", H.normalized_config(self))
            result = H.run(["--config", source, "--out-dir", root / "out", "--place-config"])
            self.assertEqual(0, result.returncode, H.describe(result))
            self.assertFalse((H.resolved_path(self, result) / "handout-config.json.visual-selection.json").exists())

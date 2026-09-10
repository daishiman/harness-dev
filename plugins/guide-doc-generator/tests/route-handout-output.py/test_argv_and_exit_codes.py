"""argv と exit code の契約 — brief argv / exit_codes / algorithm 1-3 / AC-C19-18。"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class ArgvContractTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_config_is_required(self):
        """--config 必須 (argv 契約)。省略は検査を実行できない契約違反 = exit 2。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc = H.run(["--out-dir", tmp])
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertIn(H.STDERR_PREFIX, H.err_text(proc), H.describe(proc))

    def test_no_arguments_is_exit2(self):
        proc = H.run([])
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_unknown_option_is_exit2(self):
        """argv に無い引数を受理しない (受理すると誤記が黙って無視される)。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg, "--out-dir", tmp, "--no-such-flag"])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_missing_config_file_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = H.run(["--config", Path(tmp) / "nope.json", "--out-dir", tmp])
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertIn(H.STDERR_PREFIX, H.err_text(proc), H.describe(proc))

    def test_non_json_config_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.json"
            cfg.write_text("これは JSON ではない\n", encoding="utf-8")
            proc = H.run(["--config", cfg, "--out-dir", tmp])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_place_config_with_check_only_is_exit2(self):
        """AC-C19-18: 検査モードで書き込みを起こさない (argv --place-config の併用禁止)。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            before = H.tree_snapshot(root)
            proc = H.run(
                ["--config", cfg, "--out-dir", root, "--check-only", "--place-config"]
            )
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertEqual(before, H.tree_snapshot(root), "併用時に書き込みが起きた")

    def test_stdin_is_not_read(self):
        """brief stdin: 使用しない。stdin を読むと非対話経路で詰まる。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(
                ["--config", cfg, "--out-dir", root], stdin_data="{\"noise\": true}\n"
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))


class NormalizationGateTest(unittest.TestCase):
    """algorithm 2: 正規化マーカーが無ければ exit 2 (未正規化の素通しは C35 を壊す)。"""

    def setUp(self):
        H.require_script(self)

    def _run_with(self, tmp, payload):
        root = Path(tmp) / "out"
        root.mkdir(exist_ok=True)
        cfg = H.write_config(Path(tmp) / "c.json", payload)
        return root, H.run(["--config", cfg, "--out-dir", root])

    def test_unnormalized_config_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = H.normalized_config(self, provenance=H.OMIT)
            root, proc = self._run_with(tmp, payload)
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertIn(H.STDERR_PREFIX, H.err_text(proc), H.describe(proc))
            self.assertEqual([], list(root.iterdir()), "未正規化入力でディレクトリを作った")

    def test_unnormalized_marker_absent_in_provenance_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = H.normalized_config(self, provenance={"date_source": "config"})
            _, proc = self._run_with(tmp, payload)
            self.assertEqual(2, proc.returncode, H.describe(proc))


class RequiredFieldsTest(unittest.TestCase):
    """exit_codes 2: date または doc_type フィールド欠落。algorithm 3 の書式検査。"""

    def setUp(self):
        H.require_script(self)

    def _exit_for(self, **overrides):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(
                Path(tmp) / "c.json", H.normalized_config(self, **overrides)
            )
            proc = H.run(["--config", cfg, "--out-dir", root])
            created = list(root.iterdir())
            return proc, created

    def test_missing_date_is_exit2(self):
        proc, created = self._exit_for(date=H.OMIT)
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertEqual([], created)

    def test_missing_doc_type_is_exit2(self):
        proc, created = self._exit_for(doc_type=H.OMIT)
        self.assertEqual(2, proc.returncode, H.describe(proc))
        self.assertEqual([], created)

    def test_hyphenated_date_is_rejected(self):
        """受理する入力書式は yyyy/mm/dd ひとつだけ (AC-C19-07 の実行時の裏返し)。"""
        proc, _ = self._exit_for(date=H.FIXTURE_DATE_DIR)
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_unpadded_date_is_rejected(self):
        proc, _ = self._exit_for(date="2026/8/17")
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_non_string_date_is_rejected(self):
        proc, _ = self._exit_for(date=20260817)
        self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_empty_date_is_rejected(self):
        proc, _ = self._exit_for(date="")
        self.assertEqual(2, proc.returncode, H.describe(proc))


class JsonReportTest(unittest.TestCase):
    """--json-report は write_scope の例外的な単一ファイル (argv / algorithm 11)。"""

    def setUp(self):
        H.require_script(self)

    def test_report_is_machine_readable_and_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            report_dir = Path(tmp) / "report"
            report_dir.mkdir()
            report = report_dir / "r.json"
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(
                ["--config", cfg, "--out-dir", root, "--json-report", report]
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))
            payload = H.load_report(self, report)
            self.assertEqual(
                ["r.json"],
                sorted(p.name for p in report_dir.iterdir()),
                "--json-report で指定した 1 ファイル以外が書かれた",
            )
            blob = "\n".join(H.flatten_strings(payload))
            self.assertIn(str(H.resolved_path(self, proc)), blob)

    def test_report_contains_bundle_presence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            report = Path(tmp) / "r.json"
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(
                ["--config", cfg, "--out-dir", root, "--json-report", report]
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))
            blob = "\n".join(H.flatten_strings(H.load_report(self, report)))
            for name in H.BUNDLE_NAMES:
                self.assertIn(name, blob, "レポートに同梱物 {} が無い".format(name))

    def test_report_is_written_in_check_only_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            report = Path(tmp) / "r.json"
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(
                ["--config", cfg, "--out-dir", root, "--check-only", "--json-report", report]
            )
            self.assertEqual(1, proc.returncode, H.describe(proc))
            H.load_report(self, report)


if __name__ == "__main__":
    unittest.main()

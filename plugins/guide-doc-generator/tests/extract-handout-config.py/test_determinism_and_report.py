# -*- coding: utf-8 -*-
"""再現性と抽出レポート (AC-C20-12 / report_shape / algorithm A12・A14)。

同一入力からは常に同一バイト列が出ること (抽出も決定論であること) と、
レポートが C02 skill の素材として機械可読であることを固定する。
"""

import json
import unittest

import _harness as H


class Determinism(H.C20TestCase):

    def test_two_runs_produce_identical_bytes(self):
        """AC-C20-12: 同一 HTML から --out を 2 回生成して cmp。"""
        res1, html = self.extract()
        first = self.out_bytes()
        second_path = self.tmp / "out2.json"
        res2 = self.run_cli("--html", html, "--out", second_path)
        self.assert_exit(res2, 0)
        self.assertEqual(first, self.out_bytes(second_path), "2 回の抽出結果がバイト一致しない")

    def test_two_runs_produce_identical_stdout(self):
        res1, html = self.extract()
        res2 = self.run_cli("--html", html, "--out", self.tmp / "out2.json")
        self.assert_exit(res2, 0)
        self.assertEqual(res1.stdout, res2.stdout)

    def test_two_runs_produce_identical_stderr_on_failure(self):
        res1, html = self.extract(H.LEGACY_HTML)
        res2 = self.run_cli("--html", html, "--out", self.tmp / "out2.json")
        self.assert_exit(res2, 1)
        self.assertEqual(sorted(res1.stderr.splitlines()), sorted(res2.stderr.splitlines()))

    def test_report_is_deterministic(self):
        res1, html = self.extract(None, "--report", self.report)
        first = self.report.read_bytes() if self.report.exists() else None
        self.assertIsNotNone(first, "--report が書かれていない")
        second = self.tmp / "report2.json"
        self.run_cli("--html", html, "--out", self.tmp / "out2.json", "--report", second)
        self.assertTrue(second.exists(), "--report が 2 回目で書かれていない")
        self.assertEqual(first, second.read_bytes())

    def test_output_path_is_not_recorded_in_config(self):
        """出力先パスが構成データへ入ると実行環境で結果が変わる。"""
        res, _ = self.extract()
        self.assertNotIn(str(self.tmp), self.out_text())

    def test_out_is_replaced_atomically(self):
        """A12: 一時ファイルへ書いて os.replace。中間ファイルを残さない。"""
        res, _ = self.extract()
        self.assert_exit(res, 0)
        self.assertTrue(self.out.exists(), "--out が書かれていない")
        leftovers = [p.name for p in self.tmp.iterdir()
                     if p.name.startswith("out.json") and p.name != "out.json"]
        self.assertEqual([], leftovers, "一時ファイルが残っている: %r" % leftovers)


class ReportShape(H.C20TestCase):

    def setUp(self):
        super().setUp()
        self.res, self.html = self.extract(None, "--report", self.report)

    def _report(self):
        self.assertTrue(self.report.exists(), "--report が書かれていない")
        return json.loads(self.report.read_text(encoding="utf-8"))

    def test_report_has_source_html(self):
        self.assertIn("source_html", self._report())

    def test_report_lists_sections_and_parts_with_fidelity(self):
        rep = self._report()
        self.assertEqual(["intro", "practice"], [s["id"] for s in rep["sections"]])
        for section in rep["sections"]:
            for part in section["parts"]:
                self.assertIn(part["fidelity"], ("exact", "heuristic"))
                self.assertIn("part", part)
                self.assertIn("id", part)

    def test_report_has_fidelity_summary(self):
        summary = self._report()["fidelity_summary"]
        for key in ("exact", "heuristic", "unrecoverable"):
            self.assertIsInstance(summary[key], int)

    def test_report_summary_matches_stdout_summary(self):
        rep = self._report()
        fields = self.summary(self.res)
        self.assertEqual(int(fields["exact"]), rep["fidelity_summary"]["exact"])
        self.assertEqual(int(fields["heuristic"]), rep["fidelity_summary"]["heuristic"])
        self.assertEqual(int(fields["unrecoverable"]), rep["fidelity_summary"]["unrecoverable"])

    def test_report_unrecoverable_entries_have_pointer_and_reason(self):
        report = self.tmp / "legacy-report.json"
        res, html = self.extract(H.LEGACY_HTML, "--report", report)
        self.assertTrue(report.exists(), "--report が書かれていない")
        rep = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(rep["unrecoverable"], "復元不能一覧が空")
        for entry in rep["unrecoverable"]:
            self.assertIn("pointer", entry)
            self.assertIn("reason", entry)

    def test_report_roundtrip_block_says_not_compared(self):
        rep = self._report()
        self.assertFalse(rep["roundtrip"]["compared"])

    def test_report_roundtrip_block_records_diffs(self):
        res, html = self.extract()
        cfg = self.read_out()
        cfg["title"] = "書き換えたタイトル"
        compare = self.write_json(cfg, name="modified.json")
        report = self.tmp / "diff-report.json"
        self.run_cli("--html", html, "--compare", compare, "--report", report)
        self.assertTrue(report.exists(), "--report が書かれていない")
        rep = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(rep["roundtrip"]["compared"])
        self.assertFalse(rep["roundtrip"]["equivalent"])
        self.assertTrue(rep["roundtrip"]["diffs"])
        for diff in rep["roundtrip"]["diffs"]:
            self.assertIn("pointer", diff)
            self.assertIn("expected", diff)
            self.assertIn("actual", diff)

    def test_report_is_written_even_when_extraction_fails(self):
        """レポートは C02 skill の作業台。exit 1 でも素材は残す。"""
        report = self.tmp / "legacy2-report.json"
        res, _ = self.extract(H.LEGACY_HTML, "--report", report)
        self.assert_exit(res, 1)
        self.assertTrue(report.exists())


if __name__ == "__main__":
    unittest.main()

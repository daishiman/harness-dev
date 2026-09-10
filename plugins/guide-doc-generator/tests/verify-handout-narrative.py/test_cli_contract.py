# -*- coding: utf-8 -*-
"""argv / exit code / stdout 書式の契約 (AC-C22-01 / AC-C22-13 / failure_modes)。"""

from __future__ import annotations

import json
import os
import stat
import unittest

from _support import (
    DETECTION_ORDER,
    NarrativeGateTestCase,
    base_config,
    build_html,
)


class TestHappyPathContract(NarrativeGateTestCase):
    """AC-C22-01: 正しい HTML と config で exit 0。"""

    def test_ac01_exit_zero(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assert_gate_pass(res)

    def test_ac01_stderr_empty(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("", res.stderr)

    def test_ac01_all_detection_lines_present(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        rows = self.summary(res)
        self.assertEqual(
            set(DETECTION_ORDER), set(rows),
            "detections 配列の全 detection の行が出ること (%s)" % ", ".join(DETECTION_ORDER),
        )

    def test_ac01_detection_line_count_matches_detections(self):
        """AC-C22-01: 行数は detections の件数と一致する (数値リテラルで固定しない)。"""
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual(
            len(DETECTION_ORDER), len(self.detection_ids(res)),
            "detection 行数が detections 配列の件数と一致しない\nstdout=%r" % res.stdout,
        )

    def test_ac01_detection_lines_in_fixed_order(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        seen = [ln.split()[0] for ln in res.stdout.splitlines() if ln.split() and ln.split()[0] in DETECTION_ORDER]
        self.assertEqual(DETECTION_ORDER, seen, "detection 行は detections 配列の定義順")

    def test_ac15_detection_id_column_matches_detections_exactly(self):
        """AC-C22-15: stdout の id 列が detections の id 列と順序込みで完全一致。

        `summary()` の絞り込みを通さないため、未知 id の混入と欠落も検出する。
        """
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual(
            DETECTION_ORDER, self.detection_ids(res),
            "stdout の detection id 列が detections 配列と一致しない\nstdout=%r" % res.stdout,
        )

    def test_ac01_result_line_carries_html_path(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("RESULT: PASS %s" % html, res.stdout.splitlines()[0])

    def test_ac01_every_detection_line_has_checked_and_violations(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        for det, row in self.summary(res).items():
            if row["status"] == "SKIP":
                continue
            self.assertIn("checked", row, "%s に checked= が無い" % det)
            self.assertIn("violations", row, "%s に violations= が無い" % det)

    def test_ac01_all_violation_counts_zero(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        for det, row in self.summary(res).items():
            if row["status"] == "SKIP":
                continue
            self.assertEqual("0", row["violations"], "%s の violations は 0" % det)

    def test_ac01_demo_first_fixture_reports_nar07_pass_not_skip(self):
        # base fixture は presentation_order=demo_first + 先頭 screenshot
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("PASS", self.summary(res)["NAR-07"]["status"])


class TestOutOfScopeDisclosure(NarrativeGateTestCase):
    """stdout 末尾の OUT-OF-SCOPE 節 (毎回出す)。"""

    def test_out_of_scope_section_present_on_pass(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertIn("OUT-OF-SCOPE:", res.stdout)

    def test_out_of_scope_section_present_on_fail(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields={"goal"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertIn("OUT-OF-SCOPE:", res.stdout)

    def test_out_of_scope_declares_semantic_goal_not_judged(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        tail = res.stdout.split("OUT-OF-SCOPE:", 1)[1]
        self.assertIn("C06", tail, "ゴールの意味的妥当性を判定していないこと (C06 の責務) を明示する")

    def test_out_of_scope_declares_r11_r18_belong_to_c18(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        tail = res.stdout.split("OUT-OF-SCOPE:", 1)[1]
        self.assertIn("R11", tail)
        self.assertIn("R18", tail)
        self.assertIn("C18", tail)

    def test_out_of_scope_declares_css_cascade_limitation(self):
        # NAR-04 の (e) は近似であることを開示する (brief open_questions)
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        tail = res.stdout.split("OUT-OF-SCOPE:", 1)[1]
        self.assertIn("NAR-04", tail)

    def test_out_of_scope_is_last_section(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        idx = res.stdout.index("OUT-OF-SCOPE:")
        for det in DETECTION_ORDER:
            self.assertLess(res.stdout.index(det + " "), idx, "%s 行は OUT-OF-SCOPE より前" % det)


class TestArgvAndExit2(NarrativeGateTestCase):
    """AC-C22-13 と入力不正系。いずれも exit 2 + ERROR 1 行。"""

    def test_missing_html_arg(self):
        _, cfg = self.write_pair()
        self.assert_gate_error(self.run_gate(config=cfg))

    def test_missing_config_arg(self):
        html, _ = self.write_pair()
        self.assert_gate_error(self.run_gate(html=html))

    def test_no_args_at_all(self):
        self.assert_gate_error(self.run_gate())

    def test_html_file_absent(self):
        _, cfg = self.write_pair()
        self.assert_gate_error(self.run_gate(self.tmpdir / "nope.html", cfg))

    def test_config_file_absent(self):
        html, _ = self.write_pair()
        self.assert_gate_error(self.run_gate(html, self.tmpdir / "nope.json"))

    def test_config_is_not_json(self):
        html, _ = self.write_pair()
        bad = self.tmpdir / "bad.json"
        bad.write_text("{これは JSON ではない", encoding="utf-8")
        self.assert_gate_error(self.run_gate(html, bad))

    def test_config_not_normalized(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg.pop("provenance")
        self.assert_gate_error(self.run_gate(html, self.write_config(cfg)))

    def test_config_normalized_by_wrong_writer(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg["provenance"]["normalized_by"] = "handmade"
        self.assert_gate_error(self.run_gate(html, self.write_config(cfg)))

    def test_config_missing_purpose(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg.pop("purpose")
        self.assert_gate_error(self.run_gate(html, self.write_config(cfg)))

    def test_config_missing_background(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg.pop("background")
        self.assert_gate_error(self.run_gate(html, self.write_config(cfg)))

    def test_config_missing_goal(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg.pop("goal")
        self.assert_gate_error(self.run_gate(html, self.write_config(cfg)))

    def test_config_missing_sections(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg.pop("sections")
        self.assert_gate_error(self.run_gate(html, self.write_config(cfg)))

    def test_config_sections_empty_is_exit2(self):
        # failure_modes: sections 0 件は検査の失敗ではなく入力の不正
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg["sections"] = []
        self.assert_gate_error(self.run_gate(html, self.write_config(cfg)))

    def test_html_undecodable(self):
        _, cfg = self.write_pair()
        bad = self.tmpdir / "bad.html"
        bad.write_bytes(b"\xff\xfe\x00\x00<html>")
        self.assert_gate_error(self.run_gate(bad, cfg))

    def test_json_report_unwritable_directory(self):
        html, cfg = self.write_pair()
        locked = self.tmpdir / "locked"
        locked.mkdir()
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, locked, stat.S_IRWXU)
        self.assert_gate_error(self.run_gate(html, cfg, json_report=locked / "r.json"))

    def test_json_report_parent_missing(self):
        html, cfg = self.write_pair()
        self.assert_gate_error(self.run_gate(html, cfg, json_report=self.tmpdir / "no" / "r.json"))

    def test_unknown_flag(self):
        html, cfg = self.write_pair()
        self.assert_gate_error(self.run_gate(html, cfg, extra_argv=["--strict"]))

    def test_stdin_is_not_used(self):
        # brief: stdin は使用しない。config を stdin で渡す経路が生えていないこと
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assert_gate_pass(res)


class TestJsonReport(NarrativeGateTestCase):
    def test_report_written_when_requested(self):
        html, cfg = self.write_pair()
        report = self.tmpdir / "report.json"
        self.run_gate(html, cfg, json_report=report)
        self.assertTrue(report.exists(), "--json-report のパスへ書き出すこと")

    def test_report_is_valid_json(self):
        html, cfg = self.write_pair()
        report = self.tmpdir / "report.json"
        self.run_gate(html, cfg, json_report=report)
        json.loads(report.read_text(encoding="utf-8"))

    def test_report_lists_all_detections(self):
        html, cfg = self.write_pair()
        report = self.tmpdir / "report.json"
        self.run_gate(html, cfg, json_report=report)
        blob = report.read_text(encoding="utf-8")
        for det in DETECTION_ORDER:
            self.assertIn(det, blob, "json-report に %s の結果が無い" % det)

    def test_report_not_written_when_not_requested(self):
        html, cfg = self.write_pair()
        before = set(p.name for p in self.tmpdir.iterdir())
        self.run_gate(html, cfg)
        self.assertEqual(before, set(p.name for p in self.tmpdir.iterdir()))


class TestWriteScope(NarrativeGateTestCase):
    """single_writer: --json-report 以外へ書かない。"""

    def test_html_untouched(self):
        html, cfg = self.write_pair()
        before = html.read_bytes()
        self.run_gate(html, cfg, json_report=self.tmpdir / "r.json")
        self.assertEqual(before, html.read_bytes())

    def test_config_untouched(self):
        html, cfg = self.write_pair()
        before = cfg.read_bytes()
        self.run_gate(html, cfg, json_report=self.tmpdir / "r.json")
        self.assertEqual(before, cfg.read_bytes())

    def test_no_stray_files_created(self):
        html, cfg = self.write_pair()
        report = self.tmpdir / "r.json"
        self.run_gate(html, cfg, json_report=report)
        self.assertEqual(
            {html.name, cfg.name, report.name}, set(p.name for p in self.tmpdir.iterdir())
        )


if __name__ == "__main__":
    unittest.main()

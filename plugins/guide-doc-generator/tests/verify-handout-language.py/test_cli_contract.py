# -*- coding: utf-8 -*-
"""C18 の argv / exit code / stdout 書式 / OUT-OF-SCOPE / json-report / write_scope。

正本: script-brief-C18.json の argv, stdout, stderr, exit_codes, write_scope,
single_writer, acceptance_checks AC-C18-01 / AC-C18-04 / AC-C18-11。
"""

from __future__ import annotations

import json
import os
import stat
import unittest

from _support import (
    DETECTION_ORDER,
    LanguageGateTestCase,
    OUT_DIR_NAME,
    base_config,
    build_html,
)


class TestHappyPathContract(LanguageGateTestCase):
    """AC-C18-01: 全 detection が通る入力での出力契約。"""

    def test_ac01_exit_zero(self):
        res = self.run_default()
        self.assert_gate_pass(res)

    def test_ac01_stderr_is_empty(self):
        res = self.run_default()
        self.assertEqual("", res.stderr, "PASS 時の stderr は 1 バイトも出さない")

    def test_ac01_first_line_is_result_with_html_path(self):
        html, config = self.write_pair()
        res = self.run_gate(html=html, config=config)
        self.require_script()
        self.assertEqual("RESULT: PASS %s" % html, res.stdout.splitlines()[0])

    def test_ac01_all_detection_rows_present(self):
        res = self.run_default(out_dir=self.make_out_dir())
        rows = self.summary(res)
        for det in DETECTION_ORDER:
            self.assertIn(det, rows, "%s のサマリ行が無い\nstdout=%r" % (det, res.stdout))

    def test_ac01_detection_rows_are_in_fixed_order(self):
        res = self.run_default(out_dir=self.make_out_dir())
        self.assertEqual(
            DETECTION_ORDER,
            self.summary_order(res),
            "stdout の detection 行は LANG-01, LANG-04..07, DATE-01..04 の固定順",
        )

    def test_ac01_lang02_and_lang03_do_not_exist(self):
        res = self.run_default()
        self.assertNotIn("LANG-02", res.stdout, "LANG-02 は契約に存在しない")
        self.assertNotIn("LANG-03", res.stdout, "LANG-03 は契約に存在しない")

    def test_ac01_every_row_has_checked_and_violations(self):
        res = self.run_default(out_dir=self.make_out_dir())
        for det, row in self.summary(res).items():
            self.assertIn("checked", row, "%s に checked= が無い" % det)
            self.assertIn("violations", row, "%s に violations= が無い" % det)

    def test_ac01_all_statuses_are_pass_when_out_dir_given(self):
        res = self.run_default(out_dir=self.make_out_dir())
        for det in DETECTION_ORDER:
            self.assert_detection_pass(res, det)


class TestOutOfScopeDisclosure(LanguageGateTestCase):
    """AC-C18-04: 検出できない事実を PASS の内容として偽装しない。"""

    UNDECLARED = (
        "本文にはトークン上限やレートリミット、エンベディング、"
        "ファインチューニング、コンテキストウィンドウ、"
        "リトリーバル拡張生成といった未宣言の専門用語を多数含みます。"
    )

    def _run_with_undeclared_terms(self):
        cfg = base_config()
        return self.run_default(cfg, footer_texts=[self.UNDECLARED])

    def test_out_of_scope_section_exists_on_pass(self):
        res = self.run_default()
        self.assertIsNotNone(
            self.out_of_scope_block(res), "OUT-OF-SCOPE 節が無い\nstdout=%r" % res.stdout
        )

    def test_out_of_scope_section_exists_on_fail(self):
        res = self.run_default(omit_lead_line={"s3"})
        self.assertIsNotNone(
            self.out_of_scope_block(res), "FAIL 時にも OUT-OF-SCOPE 節を出す\nstdout=%r" % res.stdout
        )

    def test_out_of_scope_is_last(self):
        res = self.run_default()
        block = self.out_of_scope_block(res)
        self.assertNotIn(
            "RESULT:", block, "OUT-OF-SCOPE 節は stdout の末尾 (以降にサマリを出さない)"
        )
        for det in DETECTION_ORDER:
            self.assertNotIn(
                "\n%s " % det, block, "%s のサマリ行が OUT-OF-SCOPE より後にある" % det
            )

    def test_out_of_scope_states_undeclared_terms_are_undetectable(self):
        res = self._run_with_undeclared_terms()
        self.assertIn("未宣言", self.out_of_scope_block(res))

    def test_out_of_scope_states_plainness_is_not_judged(self):
        res = self._run_with_undeclared_terms()
        block = self.out_of_scope_block(res)
        self.assertTrue(
            "平易" in block or "文体" in block,
            "『文体の平易さは判定していない』を毎回明示する\nblock=%r" % block,
        )

    def test_ac04_undeclared_terms_do_not_fail_the_gate(self):
        res = self._run_with_undeclared_terms()
        self.assert_gate_pass(res)


class TestArgvAndExit2(LanguageGateTestCase):
    """exit_codes 2: 検査が成立しない入力。"""

    def test_missing_html_is_exit2(self):
        _, config = self.write_pair()
        self.assert_gate_error(self.run_gate(config=config))

    def test_missing_config_is_exit2(self):
        html, _ = self.write_pair()
        self.assert_gate_error(self.run_gate(html=html))

    def test_no_argv_at_all_is_exit2(self):
        self.assert_gate_error(self.run_gate())

    def test_unknown_option_is_exit2(self):
        html, config = self.write_pair()
        self.assert_gate_error(
            self.run_gate(html=html, config=config, extra_argv=["--strict"])
        )

    def test_html_path_missing_is_exit2(self):
        _, config = self.write_pair()
        self.assert_gate_error(
            self.run_gate(html=self.tmpdir / "no-such.html", config=config)
        )

    def test_config_path_missing_is_exit2(self):
        html, _ = self.write_pair()
        self.assert_gate_error(
            self.run_gate(html=html, config=self.tmpdir / "no-such.json")
        )

    def test_config_is_not_json_is_exit2(self):
        html, _ = self.write_pair()
        bad = self.tmpdir / "bad.json"
        bad.write_text("{ これは JSON ではない", encoding="utf-8")
        self.assert_gate_error(self.run_gate(html=html, config=bad))

    def test_html_is_not_utf8_is_exit2(self):
        _, config = self.write_pair()
        bad = self.tmpdir / "sjis.html"
        bad.write_bytes("<html><body>日本語</body></html>".encode("cp932"))
        self.assert_gate_error(self.run_gate(html=bad, config=config))

    def test_html_unreadable_is_exit2(self):
        html, config = self.write_pair()
        os.chmod(html, 0o000)
        self.addCleanup(os.chmod, html, stat.S_IRUSR | stat.S_IWUSR)
        if os.access(html, os.R_OK):
            self.skipTest("root 実行のため読み取り不可を作れない")
        self.assert_gate_error(self.run_gate(html=html, config=config))

    def test_config_without_normalized_marker_is_exit2(self):
        cfg = base_config()
        cfg.pop("provenance")
        html = self.write_html(build_html(cfg))
        self.assert_gate_error(self.run_gate(html=html, config=self.write_config(cfg)))

    def test_config_normalized_by_wrong_value_is_exit2(self):
        cfg = base_config()
        cfg["provenance"]["normalized_by"] = "handmade"
        html = self.write_html(build_html(cfg))
        self.assert_gate_error(self.run_gate(html=html, config=self.write_config(cfg)))

    def test_ac11_config_date_missing_is_exit2(self):
        """AC-C18-11: 未正規化 (date 未充填) は exit 2。script が日付を補完しない。"""
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg.pop("date")
        self.assert_gate_error(self.run_gate(html=html, config=self.write_config(cfg)))

    def test_ac11_config_date_empty_is_exit2(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg["date"] = ""
        self.assert_gate_error(self.run_gate(html=html, config=self.write_config(cfg)))

    def test_config_glossary_missing_is_exit2(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg.pop("glossary")
        self.assert_gate_error(self.run_gate(html=html, config=self.write_config(cfg)))

    def test_config_sections_missing_is_exit2(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg.pop("sections")
        self.assert_gate_error(self.run_gate(html=html, config=self.write_config(cfg)))

    def test_config_sections_empty_is_exit2(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg["sections"] = []
        self.assert_gate_error(self.run_gate(html=html, config=self.write_config(cfg)))

    def test_json_report_unwritable_is_exit2(self):
        html, config = self.write_pair()
        target = self.tmpdir / "no-such-dir" / "report.json"
        self.assert_gate_error(
            self.run_gate(html=html, config=config, json_report=target)
        )

    def test_exit2_does_not_print_result_pass(self):
        _, config = self.write_pair()
        res = self.run_gate(config=config)
        self.assertNotIn("RESULT: PASS", res.stdout, "検査不成立を PASS と表示しない")


class TestJsonReport(LanguageGateTestCase):
    """--json-report の最低限の契約 (キー名スキーマはブリーフ未記載 = gap)。"""

    def test_report_file_is_created(self):
        report = self.tmpdir / "report.json"
        self.run_default(json_report=report)
        self.read_report(report)

    def test_report_is_valid_json_object(self):
        report = self.tmpdir / "report.json"
        self.run_default(json_report=report)
        self.assertIsInstance(self.read_report(report), dict)

    def test_report_mentions_every_detection_id(self):
        report = self.tmpdir / "report.json"
        self.run_default(out_dir=self.make_out_dir(), json_report=report)
        text = json.dumps(self.read_report(report), ensure_ascii=False)
        for det in DETECTION_ORDER:
            self.assertIn(det, text, "json-report に %s が現れない" % det)

    def test_report_written_on_failure_too(self):
        report = self.tmpdir / "report.json"
        res = self.run_default(json_report=report, omit_lead_line={"s3"})
        self.assertEqual(1, res.returncode)
        self.read_report(report)

    def test_report_records_out_dir_not_requested(self):
        report = self.tmpdir / "report.json"
        self.run_default(json_report=report)
        text = json.dumps(self.read_report(report), ensure_ascii=False)
        self.assertIn("NOT-REQUESTED", text, "DATE-03 の未要求状態を json-report にも残す")


class TestWriteScope(LanguageGateTestCase):
    """single_writer: --json-report のパス 1 点以外へ書かない。"""

    def _snapshot(self, root):
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    def test_no_file_created_without_json_report(self):
        html, config = self.write_pair()
        before = self._snapshot(self.tmpdir)
        self.run_gate(html=html, config=config)
        self.assertEqual(before, self._snapshot(self.tmpdir), "--json-report 無しで書き込みが発生した")

    def test_html_and_config_are_not_modified(self):
        html, config = self.write_pair()
        before = (html.read_bytes(), config.read_bytes())
        self.run_gate(html=html, config=config, json_report=self.tmpdir / "r.json")
        self.assertEqual(before, (html.read_bytes(), config.read_bytes()))

    def test_out_dir_contents_are_not_touched(self):
        out_dir = self.make_out_dir()
        before = self._snapshot(out_dir)
        html, config = self.write_pair()
        self.run_gate(html=html, config=config, out_dir=out_dir)
        self.assertEqual(before, self._snapshot(out_dir), "--out-dir 配下へ書き込んだ")

    def test_only_report_file_is_added(self):
        html, config = self.write_pair()
        before = set(self._snapshot(self.tmpdir))
        report = self.tmpdir / "report.json"
        self.run_gate(html=html, config=config, json_report=report)
        added = set(self._snapshot(self.tmpdir)) - before
        self.assertEqual({"report.json"}, added, "追加されたファイルは json-report 1 点のみ")

    def test_repo_root_is_not_polluted(self):
        html, config = self.write_pair()
        self.run_gate(html=html, config=config)
        from _support import REPO_ROOT

        self.assertFalse(
            (REPO_ROOT / "report.json").exists(), "cwd へ既定名のレポートを書いてはならない"
        )


class TestStderrFormat(LanguageGateTestCase):
    """stderr の行書式: FAIL<TAB><detection_id><TAB><位置><TAB><対象><TAB><理由>。"""

    def test_violation_rows_are_tab_separated_with_five_fields(self):
        res = self.run_default(omit_lead_line={"s3"})
        for row in self.stderr_rows(res):
            self.assertGreaterEqual(
                len(row), 5, "違反行は 5 フィールド以上のタブ区切り\nrow=%r" % (row,)
            )

    def test_violation_row_carries_detection_id(self):
        res = self.run_default(omit_lead_line={"s3"})
        rows = self.stderr_rows(res, "LANG-04")
        self.assertTrue(rows, "LANG-04 の違反行が stderr に無い\nstderr=%r" % res.stderr)

    def test_violation_row_locator_names_the_section(self):
        res = self.run_default(omit_lead_line={"s3"})
        rows = self.stderr_rows(res, "LANG-04")
        self.assertTrue(
            any("s3" in "\t".join(row[2:]) for row in rows),
            "位置フィールドに section id が出る\nrows=%r" % (rows,),
        )

    def test_stderr_row_count_matches_summary_total(self):
        res = self.run_default(omit_lead_line={"s3"}, omit_judgment_axis={"s4"})
        total = sum(
            self.violations(res, det)
            for det in DETECTION_ORDER
            if self.summary(res)[det]["status"] != "NOT-REQUESTED"
        )
        self.assertEqual(
            total, len(self.stderr_rows(res)), "違反 1 件につき stderr 1 行\nstderr=%r" % res.stderr
        )

    def test_no_error_row_when_only_violations(self):
        res = self.run_default(omit_lead_line={"s3"})
        self.assertEqual(
            [], [ln for ln in res.stderr.splitlines() if ln.startswith("ERROR\t")],
            "違反 (exit 1) を ERROR 行で表現しない",
        )

    def test_all_detections_reported_even_when_first_fails(self):
        """早期 return で後続 detection を落とさない。"""
        res = self.run_default(
            omit_lead_line={"s3"}, date_pill_text="2026/8/17", out_dir=self.make_out_dir()
        )
        for det in DETECTION_ORDER:
            self.assertIn(det, self.summary(res), "%s のサマリ行が消えた" % det)
        self.assertGreaterEqual(self.violations(res, "LANG-04"), 1)
        self.assertGreaterEqual(self.violations(res, "DATE-01"), 1)


class TestCliMisc(LanguageGateTestCase):
    def test_stdin_is_not_used(self):
        """stdin: 使用しない。閉じた stdin でも正常に判定できる。"""
        import subprocess
        import sys

        html, config = self.write_pair()
        self.require_script()
        from _support import REPO_ROOT, SCRIPT

        res = subprocess.run(
            [sys.executable, str(SCRIPT), "--html", str(html), "--config", str(config)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(0, res.returncode, "stdin を読もうとして詰まってはならない")

    def test_absolute_paths_work_from_repo_root(self):
        html, config = self.write_pair()
        res = self.run_gate(html=html.resolve(), config=config.resolve())
        self.assertEqual(0, res.returncode, "絶対パスで実行できる\nstderr=%s" % res.stderr)

    def test_pass_summary_does_not_claim_an_unchecked_date_source(self):
        """日付の真値は config 1 点。stdout に別日付を持ち出さない。"""
        res = self.run_default()
        self.assert_gate_pass(res)
        self.assertNotIn("today", res.stdout.lower())

    def test_out_dir_argument_is_optional(self):
        res = self.run_default()
        self.assertEqual(
            "NOT-REQUESTED",
            self.summary(res)["DATE-03"]["status"],
            "--out-dir は任意引数であり、未指定でも exit 0 に到達する",
        )

    def test_out_dir_that_does_not_exist_is_still_name_checked(self):
        """DATE-03 は basename だけを見る (配下のファイルを読まない)。"""
        html, config = self.write_pair()
        res = self.run_gate(html=html, config=config, out_dir=self.tmpdir / OUT_DIR_NAME)
        self.assertEqual(
            0, res.returncode, "存在しないディレクトリでも名前が正しければ通る\nstderr=%s" % res.stderr
        )


if __name__ == "__main__":
    unittest.main()

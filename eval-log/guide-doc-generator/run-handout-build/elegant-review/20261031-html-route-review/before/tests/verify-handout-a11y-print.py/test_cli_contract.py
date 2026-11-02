"""CLI 契約 (argv / exit code / stdout / stderr / write_scope / 冪等性) を赤で固定する。

正本: script-brief-C17.json の argv / stdin / stdout / stderr / exit_codes /
write_scope / single_writer、AC-C17-01 / 10 / 11 / 12。
"""

import os
import stat
import subprocess
import sys
import unittest

import hb_c17
from hb_c17 import (C17TestCase, DETECTION_IDS, OUT_OF_SCOPE_HEADER,
                    OUT_OF_SCOPE_TOPICS, good_html)


class TestBuildTarget(C17TestCase):

    def test_script_exists_at_build_target(self):
        """build_target のパスに実体があること。"""
        self.assertTrue(hb_c17.SCRIPT.exists(),
                        "build_target 未実装: {}".format(hb_c17.SCRIPT))

    def test_script_is_stdlib_only_no_network(self):
        """stdlib_only かつ network:false — 取得系 module を import しない。"""
        hb_c17.require_script()
        src = hb_c17.SCRIPT.read_text(encoding="utf-8")
        for banned in ("import urllib", "from urllib", "import socket",
                       "import requests", "http.client", "urlopen"):
            self.assertNotIn(banned, src,
                             "ネットワークアクセス経路を持ってはいけない: {}".format(banned))

    def test_script_does_not_depend_on_third_party_parser(self):
        """CSS/HTML とも標準ライブラリだけで扱う (algorithm 2-3)。"""
        hb_c17.require_script()
        src = hb_c17.SCRIPT.read_text(encoding="utf-8")
        for banned in ("bs4", "BeautifulSoup", "lxml", "tinycss", "cssutils"):
            self.assertNotIn(banned, src,
                             "外部パーサに依存してはいけない: {}".format(banned))


class TestPassPath(C17TestCase):
    """AC-C17-01: a11y 属性と print 規則を完備した HTML。"""

    def setUp(self):
        super().setUp()
        self.res = self.check_good()

    def test_exit_zero(self):
        self.assertEqual(0, self.res.rc, self.res)

    def test_result_line_is_pass(self):
        m = self.res.result_line()
        self.assertIsNotNone(
            m, "1 行目が `RESULT: PASS|FAIL <html_path>` でない\n{}".format(self.res))
        self.assertEqual("PASS", m.group("result"))

    def test_result_line_carries_html_path(self):
        m = self.res.result_line()
        self.assertIsNotNone(m, self.res)
        self.assertIn("handout.html", m.group("path"))

    def test_twelve_summary_lines_in_fixed_order(self):
        self.assertEqual(DETECTION_IDS, self.res.summary_order(),
                         "A11Y-01..07 / PRINT-01..04 / STICKY-01 を固定順で 1 行ずつ出すこと"
                         "\n{}".format(self.res))

    def test_stderr_empty_on_pass(self):
        self.assertEqual("", self.res.err, self.res)

    def test_all_detections_report_pass(self):
        for det in DETECTION_IDS:
            self.assertDetectionPasses(self.res, det)

    def test_a11y_detections_actually_checked_something(self):
        """PASS fixture は各 A11Y 検査のアンカーを含むので checked は 0 でない。"""
        for det in ("A11Y-01", "A11Y-02", "A11Y-03", "A11Y-04", "A11Y-05"):
            self.assertCheckedAtLeast(
                self.res, det, 1,
                "検査対象 0 件の PASS は『検査していない』と区別が付かない")


class TestOutOfScopeSection(C17TestCase):
    """AC-C17-10: 静的に検査していない事項を毎回明示する。"""

    def setUp(self):
        super().setUp()
        self.res = self.check_good()

    def test_out_of_scope_section_exists(self):
        self.assertIsNotNone(self.res.out_of_scope_block(),
                             "stdout 末尾に OUT-OF-SCOPE: 節が無い\n{}".format(self.res))

    def test_out_of_scope_is_the_last_section(self):
        block = self.res.out_of_scope_block()
        self.assertIsNotNone(block, self.res)
        self.assertTrue(self.res.out.rstrip().endswith(block.rstrip()),
                        "OUT-OF-SCOPE 節は stdout の末尾に置くこと\n{}".format(self.res))

    def test_out_of_scope_lists_all_required_topics(self):
        block = self.res.out_of_scope_block() or ""
        for topic, needles in OUT_OF_SCOPE_TOPICS.items():
            for needle in needles:
                self.assertIn(needle, block,
                              "OUT-OF-SCOPE に {} の記載が無い ({})\n{}".format(topic, needle, self.res))

    def test_out_of_scope_printed_on_fail_too(self):
        """FAIL でも節を落とさない (範囲外の明示は判定結果に依存しない)。"""
        res = self.check(good_html(print_css=""))
        self.assertEqual(1, res.rc, res)
        self.assertIsNotNone(res.out_of_scope_block(),
                             "FAIL 時にも OUT-OF-SCOPE 節を出すこと\n{}".format(res))

    def test_summary_lines_precede_out_of_scope(self):
        lines = self.res.out.splitlines()
        header_idx = [i for i, l in enumerate(lines)
                      if l.strip().startswith(OUT_OF_SCOPE_HEADER)]
        self.assertTrue(header_idx, self.res)
        tail = "\n".join(lines[header_idx[0]:])
        for det in DETECTION_IDS:
            self.assertNotIn(det + " PASS", tail,
                             "detection 行は OUT-OF-SCOPE より前に出すこと\n{}".format(self.res))


class TestFailPathStreams(C17TestCase):

    BAD = good_html(print_css="")

    def test_exit_one_on_violation(self):
        self.assertEqual(1, self.check(self.BAD).rc)

    def test_result_line_is_fail(self):
        m = self.check(self.BAD).result_line()
        self.assertIsNotNone(m)
        self.assertEqual("FAIL", m.group("result"))

    def test_same_twelve_lines_on_fail(self):
        """PASS/FAIL いずれでも同じ行構成 (差分比較のため)。"""
        self.assertEqual(DETECTION_IDS, self.check(self.BAD).summary_order())

    def test_stderr_line_has_five_tab_fields(self):
        res = self.check(self.BAD)
        raw = [l for l in res.err.splitlines() if l.startswith("FAIL\t")]
        self.assertTrue(raw, "違反 1 件につき 1 行の FAIL 行が要る\n{}".format(res))
        for line in raw:
            self.assertEqual(
                5, len(line.split("\t")),
                "FAIL<TAB>id<TAB>line:col<TAB>対象<TAB>欠落内容 の 5 列\n{}".format(line))

    def test_stderr_position_is_line_colon_col(self):
        for row in self.check(self.BAD).violations():
            line, _, col = row["pos"].partition(":")
            self.assertTrue(line.isdigit() and col.isdigit(),
                            "位置は line:col 形式: {}".format(row["pos"]))

    def test_stderr_violation_names_target_and_missing(self):
        for row in self.check(self.BAD).violations():
            self.assertTrue(row["target"].strip(), "対象要素/セレクタ列が空: {}".format(row))
            self.assertTrue(row["missing"].strip(), "欠落内容の列が空: {}".format(row))

    def test_stdout_and_stderr_are_not_mixed(self):
        res = self.check(self.BAD)
        self.assertNotIn("FAIL\t", res.out, "個別違反は stderr のみ\n{}".format(res))
        self.assertNotIn("RESULT:", res.err, "判定サマリは stdout のみ\n{}".format(res))

    def test_violation_count_matches_stderr_rows(self):
        res = self.check(self.BAD)
        for det, row in res.summary().items():
            self.assertEqual(row["violations"], len(res.violations(det)),
                             "{} のサマリ件数と stderr 行数が食い違う\n{}".format(det, res))


class TestUsageErrors(C17TestCase):
    """AC-C17-11: exit 2 は検査が成立しない場合のみ。品質 FAIL (1) と混ざらない。"""

    def _assert_error_exit(self, res):
        self.assertEqual(2, res.rc,
                         "検査不能は exit 2 (品質 FAIL の 1 と混同しない)\n{}".format(res))
        self.assertEqual(1, len(res.errors()),
                         "ERROR<TAB><reason> の 1 行だけを出すこと\n{}".format(res))

    def test_missing_html_option(self):
        self._assert_error_exit(self.run_cli())

    def test_nonexistent_html_path(self):
        self._assert_error_exit(self.run_cli("--html", self.tmp / "no-such.html"))

    def test_unknown_option(self):
        self._assert_error_exit(
            self.run_cli("--html", self.write_html(good_html()), "--bogus"))

    def test_directory_instead_of_file(self):
        d = self.tmp / "outdir"
        d.mkdir()
        self._assert_error_exit(self.run_cli("--html", d))

    def test_positional_html_not_accepted(self):
        """--html はオプション必須 (位置引数の別経路を作らない)。"""
        self._assert_error_exit(self.run_cli(self.write_html(good_html())))

    def test_undecodable_utf8(self):
        p = self.tmp / "broken.html"
        p.write_bytes(b"<html><body>\xff\xfe not utf-8 </body></html>")
        self._assert_error_exit(self.run_cli("--html", p))

    def test_unreadable_html(self):
        if os.geteuid() == 0:
            self.skipTest("root では権限テストが成立しない")
        p = self.write_html(good_html())
        p.chmod(0)
        self.addCleanup(p.chmod, stat.S_IRUSR | stat.S_IWUSR)
        self._assert_error_exit(self.run_cli("--html", p))

    def test_json_report_parent_dir_missing_is_exit2(self):
        target = self.tmp / "nodir" / "report.json"
        res = self.run_cli("--html", self.write_html(good_html()), "--json-report", target)
        self._assert_error_exit(res)
        self.assertFalse(target.parent.exists(),
                         "ディレクトリ作成は C19 の責務であり本 script は作らない")

    def test_json_report_unwritable_is_exit2(self):
        if os.geteuid() == 0:
            self.skipTest("root では権限テストが成立しない")
        d = self.tmp / "ro"
        d.mkdir()
        d.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(d.chmod, 0o700)
        self._assert_error_exit(
            self.run_cli("--html", self.write_html(good_html()), "--json-report", d / "r.json"))

    def test_stdin_html_not_supported(self):
        """stdin は使用しない (script-brief-C17.json#stdin)。"""
        hb_c17.require_script()
        proc = subprocess.run([sys.executable, str(hb_c17.SCRIPT)],
                              input=good_html(), capture_output=True, text=True, timeout=120)
        self.assertEqual(2, proc.returncode, proc)

    def test_error_exit_does_not_print_result_line(self):
        res = self.run_cli("--html", self.tmp / "no-such.html")
        self.assertIsNone(res.result_line(),
                          "検査不能時に RESULT 行を出すと FAIL と読み違える\n{}".format(res))


class TestWriteScope(C17TestCase):
    """single_writer: --json-report の 1 点以外へ書かない。"""

    BAD = good_html(print_css="")

    def _snapshot(self):
        return {str(p.relative_to(self.tmp)): (p.stat().st_mtime_ns, p.read_bytes())
                for p in sorted(self.tmp.rglob("*")) if p.is_file()}

    def test_no_json_report_means_no_file_written(self):
        p = self.write_html(self.BAD)
        before = self._snapshot()
        self.run_cli("--html", p)
        self.assertEqual(before, self._snapshot(), "未指定時は一切ファイルを書かない")

    def test_target_html_untouched_on_fail(self):
        p = self.write_html(self.BAD)
        before = (p.stat().st_mtime_ns, p.read_bytes())
        self.run_cli("--html", p, "--json-report", self.tmp / "r.json")
        self.assertEqual(before, (p.stat().st_mtime_ns, p.read_bytes()),
                         "検査器は検査対象 HTML / CSS を書き換えない")

    def test_only_the_report_file_is_created(self):
        p = self.write_html(self.BAD)
        self.run_cli("--html", p, "--json-report", self.tmp / "r.json")
        written = {str(f.relative_to(self.tmp)) for f in self.tmp.rglob("*") if f.is_file()}
        self.assertEqual({"handout.html", "r.json"}, written)


class TestJsonReport(C17TestCase):

    def test_report_top_level_keys(self):
        _, rep = self.report_for(good_html())
        for key in ("html", "result", "detections", "summary", "out_of_scope"):
            self.assertIn(key, rep)

    def test_report_lists_twelve_detections(self):
        _, rep = self.report_for(good_html())
        self.assertEqual(DETECTION_IDS, [d["id"] for d in rep["detections"]])

    def test_report_detection_shape(self):
        _, rep = self.report_for(good_html())
        for det in rep["detections"]:
            for key in ("id", "status", "checked", "violations"):
                self.assertIn(key, det)
            self.assertIsInstance(det["violations"], list)

    def test_report_violation_shape(self):
        _, rep = self.report_for(good_html(print_css=""))
        rows = [v for d in rep["detections"] for v in d["violations"]]
        self.assertTrue(rows, "FAIL 時は violations に要素が入る")
        for v in rows:
            for key in ("line", "col", "target", "missing"):
                self.assertIn(key, v)

    def test_report_result_matches_exit_code(self):
        res, rep = self.report_for(good_html())
        self.assertEqual("PASS", rep["result"])
        self.assertEqual(0, res.rc)

    def test_report_records_cooccurrence_only_notice_for_a11y07(self):
        """A11Y-07 (c) が共起検査に留まる旨を json-report に残す (false_positive_risk)。"""
        _, rep = self.report_for(good_html())
        det = [d for d in rep["detections"] if d["id"] == "A11Y-07"][0]
        blob = repr(det) + repr(rep.get("out_of_scope"))
        self.assertIn("共起", blob,
                      "A11Y-07 の (c) は共起検査であることを機械可読側にも残すこと: {}".format(det))


class TestDeterminism(C17TestCase):
    """AC-C17-12: 同一入力の再現性 (stdout / --json-report がバイト一致)。"""

    SAMPLE = good_html(print_css="", focus_css="", script="'use strict';var a=1;")

    def test_stdout_is_byte_identical_across_runs(self):
        p = self.write_html(self.SAMPLE)
        self.assertEqual(self.run_cli("--html", p).out, self.run_cli("--html", p).out)

    def test_stderr_is_byte_identical_across_runs(self):
        p = self.write_html(self.SAMPLE)
        self.assertEqual(self.run_cli("--html", p).err, self.run_cli("--html", p).err)

    def test_json_report_is_byte_identical_across_runs(self):
        p = self.write_html(self.SAMPLE)
        a, b = self.tmp / "a.json", self.tmp / "b.json"
        ra = self.run_cli("--html", p, "--json-report", a)
        rb = self.run_cli("--html", p, "--json-report", b)
        self.assertTrue(a.exists() and b.exists(),
                        "--json-report が書かれていない\n{}\n{}".format(ra, rb))
        self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_exit_code_stable_across_runs(self):
        p = self.write_html(self.SAMPLE)
        self.assertEqual(self.run_cli("--html", p).rc, self.run_cli("--html", p).rc)

    def test_violations_sorted_by_detection_then_position(self):
        res = self.run_cli("--html", self.write_html(self.SAMPLE))
        order = {d: i for i, d in enumerate(DETECTION_IDS)}
        keys = [(order.get(r["detection_id"], 99),
                 int(r["pos"].split(":")[0]), int(r["pos"].split(":")[1]))
                for r in res.violations()]
        self.assertEqual(sorted(keys), keys,
                         "detection の固定順・出現位置の昇順で並べる\n{}".format(res))

    def test_report_independent_of_input_path(self):
        """入力パス以外は同一入力なら同一結果 (パス由来の揺れを持ち込まない)。"""
        a = self.write_html(self.SAMPLE, "a.html")
        b = self.write_html(self.SAMPLE, "b.html")
        ra, rb = self.run_cli("--html", a), self.run_cli("--html", b)
        self.assertEqual(ra.summary(), rb.summary(), (ra, rb))


if __name__ == "__main__":
    unittest.main()

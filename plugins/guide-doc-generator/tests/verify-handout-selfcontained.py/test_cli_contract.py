"""CLI 契約 (argv / exit code / stdout / stderr / 冪等性 / write_scope) を赤で固定する。

正本: script-brief-C16.json の argv / stdout / stderr / exit_codes / write_scope /
single_writer / failure_modes、AC-C16-01 / 08 / 09 / 10。
"""

import json
import os
import stat
import unittest

import hb_c16
from hb_c16 import C16TestCase, DETECTION_IDS, good_html


class TestBuildTarget(C16TestCase):

    def test_script_exists_at_build_target(self):
        """build_target のパスに実体があること。"""
        self.assertTrue(hb_c16.SCRIPT.exists(),
                        "build_target 未実装: {}".format(hb_c16.SCRIPT))

    def test_script_is_stdlib_only_no_network(self):
        """stdlib_only かつ network:false — 取得系 module を import しない。"""
        hb_c16.require_script()
        src = hb_c16.SCRIPT.read_text(encoding="utf-8")
        for banned in ("import urllib", "from urllib", "import socket",
                       "import requests", "http.client", "urlopen"):
            self.assertNotIn(banned, src,
                             "ネットワークアクセス経路を持ってはいけない: {}".format(banned))


class TestPassPath(C16TestCase):
    """AC-C16-01: 参照 v2 相当の自己完結 HTML。"""

    def setUp(self):
        super().setUp()
        self.res = self.check_good()

    def test_exit_zero(self):
        self.assertEqual(0, self.res.rc, self.res)

    def test_result_line_is_pass(self):
        m = self.res.result_line()
        self.assertIsNotNone(m, "1 行目が `RESULT: PASS|FAIL <html_path>` でない\n{}".format(self.res))
        self.assertEqual("PASS", m.group("result"))

    def test_result_line_carries_html_path(self):
        m = self.res.result_line()
        self.assertIsNotNone(m, self.res)
        self.assertIn("handout.html", m.group("path"))

    def test_all_summary_lines_in_fixed_order(self):
        self.assertEqual(DETECTION_IDS, self.res.summary_order(),
                         "SC-01..SC-10 を固定順で 1 行ずつ出すこと\n{}".format(self.res))

    def test_stderr_empty_on_pass(self):
        self.assertEqual("", self.res.err, self.res)

    def test_all_detections_report_pass(self):
        for det in DETECTION_IDS:
            self.assertDetectionPasses(self.res, det)

    def test_sc09_actually_evaluated_on_pass_fixture(self):
        """fixture には図表を 1 件含めるので SC-09 の checked は 0 でない (AC-C16-01)。"""
        self.assertGreaterEqual(self.res.summary()["SC-09"]["checked"], 1, self.res)


class TestFailPath(C16TestCase):

    BAD = good_html(extra='<p><a href="https://example.com/doc">外部資料</a></p>')

    def test_exit_one_on_violation(self):
        self.assertEqual(1, self.check(self.BAD).rc)

    def test_result_line_is_fail(self):
        m = self.check(self.BAD).result_line()
        self.assertIsNotNone(m)
        self.assertEqual("FAIL", m.group("result"))

    def test_same_summary_lines_on_fail(self):
        """PASS/FAIL いずれでも同じ行構成 (差分比較のため)。"""
        self.assertEqual(DETECTION_IDS, self.check(self.BAD).summary_order())

    def test_stderr_line_has_five_tab_fields(self):
        res = self.check(self.BAD)
        raw = [l for l in res.err.splitlines() if l.startswith("FAIL\t")]
        self.assertTrue(raw, "違反 1 件につき 1 行の FAIL 行が要る\n{}".format(res))
        for line in raw:
            self.assertEqual(5, len(line.split("\t")),
                             "FAIL<TAB>id<TAB>line:col<TAB>message<TAB>evidence の 5 列\n{}".format(line))

    def test_stderr_position_is_line_colon_col(self):
        for row in self.check(self.BAD).violations():
            line, _, col = row["pos"].partition(":")
            self.assertTrue(line.isdigit() and col.isdigit(),
                            "位置は line:col 形式: {}".format(row["pos"]))

    def test_stderr_evidence_truncated_to_120(self):
        long_url = "https://example.com/" + "x" * 400
        res = self.check(good_html(extra='<p><a href="{}">長い</a></p>'.format(long_url)))
        for row in res.violations():
            self.assertLessEqual(len(row["evidence"]), 120, row)

    def test_stdout_and_stderr_are_not_mixed(self):
        res = self.check(self.BAD)
        self.assertNotIn("FAIL\t", res.out, "個別違反は stderr のみ\n{}".format(res))
        self.assertNotIn("RESULT:", res.err, "判定サマリは stdout のみ\n{}".format(res))

    def test_violation_line_numbers_point_into_document(self):
        res = self.check(self.BAD)
        total_lines = len(self.BAD.splitlines())
        for row in res.violations():
            self.assertLessEqual(int(row["pos"].split(":")[0]), total_lines, row)


class TestUsageErrors(C16TestCase):
    """exit 2: 検査そのものが成立しない場合 (AC-C16-08)。"""

    def _assert_error_exit(self, res):
        self.assertEqual(2, res.rc, "検査不能は exit 2 (品質 FAIL の 1 と混同しない)\n{}".format(res))
        self.assertEqual(1, len(res.errors()),
                         "ERROR<TAB><reason> の 1 行だけを出すこと\n{}".format(res))

    def test_missing_html_option(self):
        self._assert_error_exit(self.run_cli())

    def test_nonexistent_html_path(self):
        self._assert_error_exit(self.run_cli("--html", self.tmp / "no-such.html"))

    def test_unknown_option(self):
        self._assert_error_exit(self.run_cli("--html", self.write_html(good_html()), "--bogus"))

    def test_directory_instead_of_file(self):
        """ディレクトリ指定は受け付けない。"""
        d = self.tmp / "outdir"
        d.mkdir()
        self._assert_error_exit(self.run_cli("--html", d))

    def test_glob_argument_not_accepted(self):
        self.write_html(good_html(), "a.html")
        self._assert_error_exit(self.run_cli("--html", self.tmp / "*.html"))

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
        """failure_modes: 親ディレクトリを作らず exit 2。"""
        target = self.tmp / "nodir" / "report.json"
        res = self.run_cli("--html", self.write_html(good_html()), "--json-report", target)
        self._assert_error_exit(res)
        self.assertFalse(target.parent.exists(), "ディレクトリ作成は C19 の責務であり本 script は作らない")

    def test_json_report_unwritable_is_exit2(self):
        if os.geteuid() == 0:
            self.skipTest("root では権限テストが成立しない")
        d = self.tmp / "ro"
        d.mkdir()
        d.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(d.chmod, 0o700)
        self._assert_error_exit(
            self.run_cli("--html", self.write_html(good_html()), "--json-report", d / "r.json"))

    def test_stdin_html_path_not_supported(self):
        """stdin から HTML を読む経路は設けない (--html 必須)。"""
        hb_c16.require_script()
        import subprocess
        import sys
        proc = subprocess.run([sys.executable, str(hb_c16.SCRIPT)],
                              input=good_html(), capture_output=True, text=True, timeout=120)
        self.assertEqual(2, proc.returncode, proc)


class TestWriteScope(C16TestCase):
    """single_writer: --json-report の 1 点以外へ書かない (AC-C16-09)。"""

    BAD = good_html(extra='<img src="./assets/x.png" alt="図">')

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
                         "検査器は検査対象 HTML を書き換えない")

    def test_only_the_report_file_is_created(self):
        p = self.write_html(self.BAD)
        self.run_cli("--html", p, "--json-report", self.tmp / "r.json")
        written = {str(f.relative_to(self.tmp)) for f in self.tmp.rglob("*") if f.is_file()}
        self.assertEqual({"handout.html", "r.json"}, written)


class TestJsonReport(C16TestCase):

    def test_report_top_level_keys(self):
        _, rep = self.report_for(good_html())
        for key in ("html", "result", "detections", "summary"):
            self.assertIn(key, rep)

    def test_report_lists_all_detections(self):
        _, rep = self.report_for(good_html())
        self.assertEqual(DETECTION_IDS, [d["id"] for d in rep["detections"]])

    def test_report_detection_shape(self):
        _, rep = self.report_for(good_html())
        for det in rep["detections"]:
            for key in ("id", "status", "checked", "violations"):
                self.assertIn(key, det)
            self.assertIsInstance(det["violations"], list)

    def test_report_violation_shape(self):
        _, rep = self.report_for(good_html(extra='<a href="https://example.com/">x</a>'))
        rows = [v for d in rep["detections"] for v in d["violations"]]
        self.assertTrue(rows, "FAIL 時は violations に要素が入る")
        for v in rows:
            for key in ("line", "col", "message", "evidence"):
                self.assertIn(key, v)

    def test_report_result_matches_exit_code(self):
        res, rep = self.report_for(good_html())
        self.assertEqual("PASS", rep["result"])
        self.assertEqual(0, res.rc)


class TestDeterminism(C16TestCase):
    """AC-C16-10: 同一入力の再現性。"""

    SAMPLE = good_html(extra='<p><a href="https://a.example/1">a</a>'
                             '<a href="https://b.example/2">b</a>'
                             '<img src="./x.png" alt="x"></p>')

    def test_stdout_is_byte_identical_across_runs(self):
        p = self.write_html(self.SAMPLE)
        self.assertEqual(self.run_cli("--html", p).out, self.run_cli("--html", p).out)

    def test_stderr_is_byte_identical_across_runs(self):
        p = self.write_html(self.SAMPLE)
        self.assertEqual(self.run_cli("--html", p).err, self.run_cli("--html", p).err)

    def test_json_report_is_byte_identical_across_runs(self):
        p = self.write_html(self.SAMPLE)
        a, b = self.tmp / "a.json", self.tmp / "b.json"
        self.run_cli("--html", p, "--json-report", a)
        self.run_cli("--html", p, "--json-report", b)
        self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_violations_sorted_by_detection_then_position(self):
        res = self.run_cli("--html", self.write_html(self.SAMPLE))
        keys = [(r["detection_id"], int(r["pos"].split(":")[0]), int(r["pos"].split(":")[1]))
                for r in res.violations()]
        self.assertEqual(sorted(keys), keys, "detection_id・出現位置の昇順で並べる\n{}".format(res))

    def test_exit_code_stable_across_runs(self):
        p = self.write_html(self.SAMPLE)
        self.assertEqual(self.run_cli("--html", p).rc, self.run_cli("--html", p).rc)


class TestStructuralFailureModes(C16TestCase):

    def test_document_without_nav_and_section_is_exit1(self):
        """failure_modes: nav も section も無ければ PASS へ畳まず exit 1。"""
        res = self.check("<!DOCTYPE html><html lang=\"ja\"><body><p>ただの HTML</p></body></html>")
        self.assertEqual(1, res.rc, "資料 HTML の構造要件を満たさない -> exit 1 (2 ではない)\n{}".format(res))

    def test_malformed_html_does_not_crash_into_exit2(self):
        """未閉じタグは寛容モードで続行する (例外中断のみ exit 2)。"""
        res = self.check(good_html(extra="<div><p>閉じていない"))
        self.assertIn(res.rc, (0, 1), "回復可能な崩れで exit 2 にしない\n{}".format(res))

    def test_malformed_html_is_recorded_in_report(self):
        _, rep = self.report_for(good_html(extra="<div><p>閉じていない"))
        blob = json.dumps(rep, ensure_ascii=False)
        self.assertIn("SC-00", blob, "パーサ警告は SC-00 相当として json-report に残す")


if __name__ == "__main__":
    unittest.main()

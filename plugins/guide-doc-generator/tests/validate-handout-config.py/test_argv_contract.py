# -*- coding: utf-8 -*-
"""argv と exit code の契約 (script-brief-C12.json: argv / exit_codes / A1 / A2)。

exit 2 は「起動側の不正」、exit 1 は「構成データ側の違反」。この 2 つを混ぜないことが
呼び出し側 (C01 / hook) が差し戻し先を判別できる根拠なので、境界を 1 件ずつ固定する。
"""

import json
import unittest

import _harness as H


class ArgvContract(H.C12TestCase):

    # --- exit 2: 起動側の不正 --------------------------------------------

    def test_config_missing_flag_is_exit2(self):
        """--config 未指定は exit 2 (exit_codes.2)。"""
        res = self.run_cli()
        self.assert_exit(res, 2)

    def test_config_path_not_found_is_exit2(self):
        """--config が存在しないパスなら exit 2 (内容の問題ではないため 1 にしない)。"""
        res = self.run_cli("--config", self.tmp / "no-such-file.json")
        self.assert_exit(res, 2)

    def test_normalize_without_out_is_exit2(self):
        """AC-C12-10: --normalize の単独指定は exit 2。"""
        path = self.write_config(H.valid_config())
        res = self.run_cli("--config", path, "--normalize")
        self.assert_exit(res, 2)

    def test_out_same_realpath_as_config_is_exit2(self):
        """AC-C12-09: --out が --config と同一 realpath なら exit 2 (in-place 書き換えの禁止)。"""
        path = self.write_config(H.valid_config())
        before = path.read_bytes()
        res = self.run_cli("--config", path, "--normalize", "--out", path)
        self.assert_exit(res, 2)
        self.assertEqual(before, path.read_bytes(), "--config が書き換えられている")

    def test_out_same_realpath_via_symlink_is_exit2(self):
        """realpath 比較であること (別名リンク経由でも in-place を許さない)。"""
        path = self.write_config(H.valid_config())
        link = self.tmp / "alias.json"
        link.symlink_to(path)
        res = self.run_cli("--config", path, "--normalize", "--out", link)
        self.assert_exit(res, 2)

    def test_out_parent_directory_missing_is_exit2(self):
        """--out の親ディレクトリが存在しなければ exit 2。"""
        path = self.write_config(H.valid_config())
        res = self.run_cli("--config", path, "--normalize", "--out", self.tmp / "nodir" / "out.json")
        self.assert_exit(res, 2)

    def test_today_bad_format_is_exit2(self):
        """--today が YYYY-MM-DD でなければ exit 2 (起動引数の書式)。"""
        path = self.write_config(H.valid_config())
        res = self.run_cli("--config", path, "--today", "2026/08/17")
        self.assert_exit(res, 2)

    def test_today_wellformed_is_accepted(self):
        """--today が書式どおりなら受理される (試験用の縫い目が働くこと)。"""
        path = self.write_config(H.valid_config())
        res = self.run_cli("--config", path, "--today", "2026-08-17")
        self.assert_exit(res, 0)

    def test_schema_path_unresolvable_is_exit2(self):
        """--schema が解決できなければ exit 2。"""
        path = self.write_config(H.valid_config())
        res = self.run_cli("--config", path, "--schema", self.tmp / "no-schema.json")
        self.assert_exit(res, 2)

    def test_catalog_path_unresolvable_is_exit2(self):
        """--catalog が解決できなければ exit 2 (C23 の resolve_catalog_path へ委譲)。"""
        path = self.write_config(H.valid_config())
        res = self.run_cli("--config", path, "--catalog", self.tmp / "no-catalog.json")
        self.assert_exit(res, 2)

    def test_broken_json_is_exit1_not_exit2(self):
        """JSON として parse できない入力は内容の問題なので exit 1 (failure_modes)。"""
        path = self.write_config(None, raw="{\"title\": ".encode("utf-8"))
        res = self.run_cli("--config", path)
        self.assert_exit(res, 1)

    def test_broken_json_reports_line_and_column(self):
        """parse 失敗時は行番号と桁を添える (failure_modes)。"""
        path = self.write_config(None, raw="{\n  \"title\": ,\n}\n".encode("utf-8"))
        res = self.run_cli("--config", path)
        self.assert_exit(res, 1)
        self.assertRegex(res.stderr, r"(line|行)\s*\d+", "行番号が stderr に無い: %r" % res.stderr)
        self.assertRegex(res.stderr, r"(column|col|桁)\s*\d+", "桁が stderr に無い: %r" % res.stderr)

    # --- exit 0 の姿 ------------------------------------------------------

    def test_valid_config_exit0_with_summary_and_empty_stderr(self):
        """AC-C12-01: 全必須フィールドを満たす入力は stdout に OK サマリ 1 行、stderr 空、exit 0。"""
        res, _ = self.validate(H.valid_config())
        self.assert_exit(res, 0)
        self.assertEqual("", res.stderr, "stderr が空でない: %r" % res.stderr)
        lines = [l for l in res.stdout.splitlines() if l.strip()]
        self.assertTrue(lines, "stdout に OK サマリが無い")
        self.assertTrue(lines[0].startswith("OK"), "サマリ行が OK で始まらない: %r" % lines[0])

    def test_summary_reports_counts(self):
        """サマリは内訳 (sections / doc_type / date / warnings) を含む。"""
        res, _ = self.validate(H.valid_config())
        self.assert_exit(res, 0)
        for token in ("sections=", "doc_type=", "date=", "warnings="):
            self.assertIn(token, res.stdout, "サマリに %s が無い: %r" % (token, res.stdout))

    def test_stdout_is_not_json(self):
        """構成データ JSON を stdout へ流さない (JSON の行き先は --out 一箇所)。"""
        res, _, _ = self.normalize(H.valid_config())
        self.assert_exit(res, 0)
        with self.assertRaises(ValueError, msg="stdout が JSON になっている: %r" % res.stdout):
            json.loads(res.stdout)

    def test_stdin_is_ignored(self):
        """stdin は読まない非対話 script。接続されていても結果が変わらない。"""
        path = self.write_config(H.valid_config())
        res = self.run_cli("--config", path, stdin_data="このゴミは無視されるべき\n")
        self.assert_exit(res, 0)

    def test_config_is_never_modified(self):
        """N13: --config は 'r' モードでしか開かない (内容が無変更)。"""
        cfg = H.valid_config()
        del cfg["date"]
        path = self.write_config(cfg)
        before = path.read_bytes()
        res = self.run_cli("--config", path, "--normalize", "--out", self.out, "--today", "2026-08-17")
        self.assert_exit(res, 0)
        self.assertEqual(before, path.read_bytes(), "--config が書き換えられている")

    def test_hb_root_env_resolves_plugin_root(self):
        """A2: 実体解決 4 段の 1 段目 HB_ROOT が効くこと (試験がこの縫い目に依存する)。"""
        path = self.write_config(H.valid_config())
        res = self.run_cli("--config", path, env_root=True)
        self.assert_exit(res, 0)

    def test_diagnostic_line_shape(self):
        """stderr は 1 行 1 件で '<コード> <JSON Pointer> <説明>' の形 (stderr 契約)。"""
        cfg = H.valid_config()
        cfg["sections"][1]["goal"] = ""
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)
        for line in [l for l in res.stderr.splitlines() if l.strip()]:
            parts = line.split(" ", 2)
            self.assertTrue(parts[0].startswith(("E-", "W-")), "先頭が診断コードでない: %r" % line)
            self.assertTrue(len(parts) >= 3, "キーパスと説明が無い: %r" % line)
            self.assertTrue(parts[1].startswith("/"), "第 2 要素が JSON Pointer でない: %r" % line)

    def test_all_violations_are_listed_not_just_first(self):
        """failure_modes: 必須欠落が複数あるとき、最初の 1 件で止めず全件を列挙する。"""
        cfg = H.valid_config()
        del cfg["purpose"]
        del cfg["reader"]
        cfg["sections"][0].pop("goal")
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)
        self.assert_diag(res, "E-FIELD-MISSING", "/purpose")
        self.assert_diag(res, "E-FIELD-MISSING", "/reader")
        self.assert_diag(res, "E-FIELD-MISSING", "/sections/0/goal")


if __name__ == "__main__":
    unittest.main()

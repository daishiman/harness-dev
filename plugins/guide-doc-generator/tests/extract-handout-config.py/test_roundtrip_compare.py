# -*- coding: utf-8 -*-
"""--compare の round-trip 等価判定 (roundtrip_granularity / AC-C20-01 / AC-C20-03)。

合格条件はバイト一致ではなく「正規化済み構成データの comparable projection 上での
深い等価」である。provenance を比較へ含めないこと、配列は順序込みで比べること、
不一致は JSON Pointer + expected + actual で全件出すことを固定する。

比較の基準を 2 つにしないため、正規化は C12 のモジュール API を通す
(C12 も P05 未実装なので、本ファイルは C20 単体では緑にならない)。
"""

import json
import unittest

import _harness as H


class CompareUsesExtractedConfig(H.C20TestCase):
    """--out へ書いた復元結果をそのまま --compare へ与えれば必ず等価になる。

    この不変条件は C11 が無くても成立し、比較関数が「常に不一致」でも
    「常に一致」でもないことを固定する土台になる。
    """

    def setUp(self):
        super().setUp()
        self.res, self.html = self.extract()
        self.baseline = self.out if self.out.exists() else None

    def test_self_compare_is_equivalent(self):
        self.assertIsNotNone(self.baseline, "--out が無いので比較できない")
        res = self.run_cli("--html", self.html, "--compare", self.baseline)
        self.assert_exit(res, 0)
        self.assertEqual("EQUIVALENT", self.summary(res).get("roundtrip"))

    def test_self_compare_emits_no_diff(self):
        self.assertIsNotNone(self.baseline)
        res = self.run_cli("--html", self.html, "--compare", self.baseline)
        self.assert_no_diag(res, H.E_ROUNDTRIP_DIFF)

    def test_provenance_only_in_compare_is_not_a_diff(self):
        """comparable_projection: provenance ブロックは比較対象から外す。"""
        self.assertIsNotNone(self.baseline)
        cfg = json.loads(self.baseline.read_text(encoding="utf-8"))
        cfg["provenance"] = {"normalized_by": "C12", "schema_version": "1.0",
                             "catalog_sha256": "0" * 64, "date_source": "explicit"}
        with_prov = self.write_json(cfg, name="with-provenance.json")
        res = self.run_cli("--html", self.html, "--compare", with_prov)
        self.assert_exit(res, 0)

    def test_field_change_is_reported_as_diff(self):
        """AC-C20-03: judgment_axis を書き換えたら pointer + expected + actual で落ちる。"""
        self.assertIsNotNone(self.baseline)
        cfg = json.loads(self.baseline.read_text(encoding="utf-8"))
        cfg["sections"][1]["judgment_axis"] = "書き換えた判断軸"
        modified = self.write_json(cfg, name="modified.json")
        res = self.run_cli("--html", self.html, "--compare", modified)
        self.assert_exit(res, 1)
        lines = self.assert_diag(res, H.E_ROUNDTRIP_DIFF, "/sections/1/judgment_axis")
        joined = "\n".join(lines)
        self.assertIn("expected=", joined)
        self.assertIn("actual=", joined)

    def test_all_diffs_are_reported_not_just_the_first(self):
        """compare_procedure 5: 不一致は全件出す。"""
        self.assertIsNotNone(self.baseline)
        cfg = json.loads(self.baseline.read_text(encoding="utf-8"))
        cfg["sections"][0]["judgment_axis"] = "書き換え 1"
        cfg["sections"][1]["lead_line"] = "書き換え 2"
        cfg["title"] = "書き換え 3"
        modified = self.write_json(cfg, name="modified2.json")
        res = self.run_cli("--html", self.html, "--compare", modified)
        self.assert_exit(res, 1)
        lines = self.assert_diag(res, H.E_ROUNDTRIP_DIFF)
        self.assertGreaterEqual(len(lines), 3, "不一致が全件出ていない: %r" % lines)

    def test_section_order_change_is_a_diff(self):
        """配列は順序込みで比較する (順序が意味を持つため)。"""
        self.assertIsNotNone(self.baseline)
        cfg = json.loads(self.baseline.read_text(encoding="utf-8"))
        cfg["sections"].reverse()
        modified = self.write_json(cfg, name="reordered.json")
        res = self.run_cli("--html", self.html, "--compare", modified)
        self.assert_exit(res, 1)
        self.assert_diag(res, H.E_ROUNDTRIP_DIFF)

    def test_summary_reports_roundtrip_state_on_failure(self):
        self.assertIsNotNone(self.baseline)
        cfg = json.loads(self.baseline.read_text(encoding="utf-8"))
        cfg["title"] = "別のタイトル"
        modified = self.write_json(cfg, name="modified3.json")
        res = self.run_cli("--html", self.html, "--compare", modified)
        self.assertNotEqual("EQUIVALENT", self.summary(res).get("roundtrip"))

    def test_out_is_not_written_when_roundtrip_differs(self):
        """fail_semantics: E-ROUNDTRIP-DIFF のときは --out を書かない。"""
        self.assertIsNotNone(self.baseline)
        cfg = json.loads(self.baseline.read_text(encoding="utf-8"))
        cfg["title"] = "別のタイトル"
        modified = self.write_json(cfg, name="modified4.json")
        fresh = self.tmp / "fresh-out.json"
        res = self.run_cli("--html", self.html, "--compare", modified, "--out", fresh)
        self.assert_exit(res, 1)
        self.assert_not_written(fresh)


class CompareNormalizesBothSides(H.C20TestCase):
    """未正規化の --compare も C12 の正規化を通してから比べる。"""

    def test_unnormalized_date_is_not_a_diff(self):
        res, html = self.extract()
        base = self.read_out()
        base["date"] = "2026-08-17"      # 正規化前の書式 (意味は同じ)
        compare = self.write_json(base, name="unnormalized.json")
        res2 = self.run_cli("--html", html, "--compare", compare)
        self.assert_exit(res2, 0)

    def test_key_order_is_not_a_diff(self):
        res, html = self.extract()
        base = self.read_out()
        reversed_cfg = {k: base[k] for k in reversed(list(base.keys()))}
        compare = self.write_json(reversed_cfg, name="reordered-keys.json")
        res2 = self.run_cli("--html", html, "--compare", compare)
        self.assert_exit(res2, 0)


if __name__ == "__main__":
    unittest.main()

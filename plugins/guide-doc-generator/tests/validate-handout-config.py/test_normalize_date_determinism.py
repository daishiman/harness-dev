# -*- coding: utf-8 -*-
"""--normalize の確定規則と再現性 (normalize_algorithm N1-N13 / encoding_rules)。

AC-C12-05/06/07/08/11/21/22 と date_single_source_guarantee が出所。
日付の既定充填は plugin 全体でこの script の N4 だけが行う、という単一 writer の性質を
--today の縫い目で凍結して検査する。
"""

import json
import unittest

import _harness as H


class DateResolution(H.C12TestCase):

    def test_missing_date_is_filled_from_today_seam(self):
        """AC-C12-05: date 未指定 + --today で既定充填され date_source が default-today (C33)。"""
        cfg = H.valid_config()
        del cfg["date"]
        res, _, out = self.normalize(cfg, "--today", "2026-08-17")
        self.assert_exit(res, 0)
        data = self.read_out(out)
        self.assertEqual("2026/08/17", data["date"])
        self.assertEqual("default-today", data["provenance"]["date_source"])

    def test_null_date_is_filled_from_today_seam(self):
        """date が null でも既定充填の経路に入る (N4)。"""
        cfg = H.valid_config()
        cfg["date"] = None
        res, _, out = self.normalize(cfg, "--today", "2026-08-17")
        self.assert_exit(res, 0)
        data = self.read_out(out)
        self.assertEqual("2026/08/17", data["date"])
        self.assertEqual("default-today", data["provenance"]["date_source"])

    def test_explicit_date_records_config_source(self):
        """利用者指定の date は上書きされず date_source=config。"""
        res, _, out = self.normalize(H.valid_config(), "--today", "2026-01-01")
        self.assert_exit(res, 0)
        data = self.read_out(out)
        self.assertEqual("2026/08/17", data["date"])
        self.assertEqual("config", data["provenance"]["date_source"])

    def test_date_variants_are_reshaped(self):
        """AC-C12-06: 4 書式を受理して yyyy/mm/dd (ゼロ埋め・スラッシュ) へ整形する (C34)。"""
        for given in ("2026-8-17", "2026/8/17", "2026-08-17", "2026/08/17"):
            with self.subTest(given=given):
                cfg = H.valid_config()
                cfg["date"] = given
                out = self.tmp / ("out-%s.json" % given.replace("/", "_"))
                res, _, out = self.normalize(cfg, out=out)
                self.assert_exit(res, 0)
                self.assertEqual("2026/08/17", self.read_out(out)["date"])

    def test_nonexistent_calendar_date(self):
        """AC-C12-07: 書式が合っていても暦に無い日付は E-DATE-INVALID。"""
        cfg = H.valid_config()
        cfg["date"] = "2026/02/30"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-DATE-INVALID", "/date")

    def test_unparseable_date_format(self):
        """受理書式以外の日付表記は違反。"""
        cfg = H.valid_config()
        cfg["date"] = "2026年8月17日"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_no_second_date_field_is_produced(self):
        """date_single_source_guarantee: 派生形 (YYYY-MM-DD) をフィールドとして保存しない。"""
        cfg = H.valid_config()
        del cfg["date"]
        res, _, out = self.normalize(cfg, "--today", "2026-08-17")
        self.assert_exit(res, 0)
        data = self.read_out(out)
        date_like = [k for k in data if "date" in k.lower() and k != "date"]
        self.assertEqual([], date_like, "date 以外の日付フィールドが生えている: %r" % date_like)
        self.assertNotIn("2026-08-17", json.dumps(data, ensure_ascii=False),
                         "ディレクトリ名用のハイフン形が構成データへ保存されている")


class NormalizeDefaults(H.C12TestCase):

    def test_schema_version_is_filled(self):
        """N3: schema_version が無ければ現行版を充填する。"""
        cfg = H.valid_config()
        del cfg["schema_version"]
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual("1.0", self.read_out(out)["schema_version"])

    def test_section_kind_default_comes_from_catalog(self):
        """N7: section_kind 未指定は catalog の default を充填する (script に既定値を書かない)。"""
        default = self.sections_catalog()["default"]
        cfg = H.valid_config()
        del cfg["sections"][0]["section_kind"]
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual(default, self.read_out(out)["sections"][0]["section_kind"])

    def test_notes_enabled_default(self):
        """N7: notes_enabled 未指定は true。"""
        cfg = H.valid_config()
        del cfg["notes_enabled"]
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertIs(True, self.read_out(out)["notes_enabled"])

    def test_role_default_main(self):
        """N7b: section.role 未指定は main。"""
        cfg = H.valid_config()
        del cfg["sections"][0]["role"]
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual("main", self.read_out(out)["sections"][0]["role"])

    def test_must_remember_max_default(self):
        """N7b: must_remember_max 未指定は 2。"""
        res, _, out = self.normalize(H.valid_config())
        self.assert_exit(res, 0)
        self.assertEqual(2, self.read_out(out)["must_remember_max"])

    def test_attainment_step_is_not_guessed(self):
        """N7b: attainment_step は推測で埋めない (null のまま保持)。"""
        cfg = H.valid_config()
        cfg["sections"][1]["attainment_step"] = None
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertIsNone(self.read_out(out)["sections"][1]["attainment_step"])

    def test_theme_is_preserved_untouched(self):
        """AC-C12-22: theme は C12 が触らない (書き戻しの writer は C11 のみ)。"""
        tokens_dir = self.root / H.TOKENS_RELDIR
        self.assertTrue(tokens_dir.exists(), "テーマトークン置き場が無い: %s" % tokens_dir)
        theme = sorted(p.stem for p in tokens_dir.glob("*.json"))[0]
        cfg = H.valid_config()
        cfg["theme"] = theme
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual(theme, self.read_out(out)["theme"])

    def test_provenance_shape(self):
        """N11: provenance に規定の 8 キーが揃う。

        R22 (C61-C66) で detail_level / evidence_depth を導入した際に、その決定根拠を
        残す detail_level_source / evidence_depth_source が provenance へ加わった。
        本テストは 6 キーのまま据え置かれていた (R22 の追随漏れ)。
        """
        res, _, out = self.normalize(H.valid_config())
        self.assert_exit(res, 0)
        prov = self.read_out(out)["provenance"]
        self.assertEqual(
            {"normalized_by", "schema_version", "catalog_sha256", "date_source",
             "presentation_order_source", "detail_level_source", "evidence_depth_source",
             "text_fold_count"},
            set(prov),
        )
        self.assertEqual("validate-handout-config.py", prov["normalized_by"])
        self.assertIsInstance(prov["text_fold_count"], int)
        # 追加した 2 キーは「どこから決まったか」の記録なので空では意味を持たない。
        for key in ("detail_level_source", "evidence_depth_source"):
            self.assertTrue(isinstance(prov[key], str) and prov[key].strip(),
                            "%s が空: %r" % (key, prov[key]))


class SubjectSlug(H.C12TestCase):

    def test_slug_is_derived_from_ascii_title(self):
        """N5: 未指定なら title から決定論導出する。"""
        cfg = H.valid_config()
        del cfg["subject_slug"]
        cfg["title"] = "AI Guide Doc  Generator / Workshop!"
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual("ai-guide-doc-generator-workshop", self.read_out(out)["subject_slug"])

    def test_slug_is_truncated_to_40_chars(self):
        """N5: 40 文字で切る。"""
        cfg = H.valid_config()
        del cfg["subject_slug"]
        cfg["title"] = "a" * 60
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual("a" * 40, self.read_out(out)["subject_slug"])

    def test_japanese_only_title_is_not_auto_slugged(self):
        """AC-C12-21: 日本語のみの title からは導出せず E-SLUG-UNDERIVABLE (無意味な自動生成をしない)。"""
        cfg = H.valid_config()
        del cfg["subject_slug"]
        cfg["title"] = "生成エーアイ活用勉強会"
        res, _, out = self.normalize(cfg)
        self.assert_fails_with(res, "E-SLUG-UNDERIVABLE", "/subject_slug")
        self.assertFalse(out.exists(), "違反時に --out が作られている")
        self.assertIn("subject_slug", res.stderr)


class FailClosed(H.C12TestCase):

    def test_no_out_file_on_violation(self):
        """AC-C12-11: 違反がある入力へ --normalize しても --out を作らない (N1 fail-closed)。"""
        cfg = H.valid_config()
        cfg["sections"][0]["goal"] = ""
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 1)
        self.assertFalse(out.exists(), "fail-closed でないため部分成果物が残っている")

    def test_existing_out_file_is_left_intact_on_violation(self):
        """既存の --out を違反実行が壊さない (原子的差し替えの前提)。"""
        self.out.write_text("previous", encoding="utf-8")
        cfg = H.valid_config()
        del cfg["purpose"]
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 1)
        self.assertEqual("previous", out.read_text(encoding="utf-8"))

    def test_no_temp_file_left_behind(self):
        """N12: 一時ファイルを --out と同じディレクトリへ残さない。

        判定は「本実行が増やしたか」で行う。harness は self.root = tmp/"plugin-root" を
        self.out = tmp/"out.json" と同じ親へ作るため、iterdir() の全件を leftover と
        みなすと script が何も残さなくても赤になる (harness 自身の固定物を数える誤検出)。
        除外名を書き下すと harness の内部構造の第 2 の名簿になるので、名前ではなく
        実行前後の差分で判定する。
        """
        before = {p.name for p in self.out.parent.iterdir()}
        res, _, out = self.normalize(H.valid_config())
        self.assert_exit(res, 0)
        leftovers = sorted(p.name for p in out.parent.iterdir()
                           if p.name not in before and p != out and p.suffix != ".json")
        self.assertEqual([], leftovers, "一時ファイルが残っている: %r" % leftovers)


class EncodingAndDeterminism(H.C12TestCase):

    def test_two_runs_are_byte_identical(self):
        """AC-C12-08: 同一入力に対する 2 回の --normalize がバイト一致する (C29 の前提)。"""
        cfg = H.valid_config()
        out1 = self.tmp / "out1.json"
        out2 = self.tmp / "out2.json"
        r1, path, _ = self.normalize(cfg, "--today", "2026-08-17", out=out1)
        r2 = self.run_cli("--config", path, "--normalize", "--out", out2, "--today", "2026-08-17")
        self.assert_exit(r1, 0)
        self.assert_exit(r2, 0)
        self.assertEqual(out1.read_bytes(), out2.read_bytes(), "2 回の出力がバイト一致しない")

    def test_key_order_is_independent_of_input_order(self):
        """encoding_rules: sort_keys によりキー順が入力に依らず一意になる。"""
        cfg = H.valid_config()
        shuffled = dict(reversed(list(cfg.items())))
        out1 = self.tmp / "a.json"
        out2 = self.tmp / "b.json"
        r1, _, _ = self.normalize(cfg, out=out1)
        r2, _, _ = self.normalize(shuffled, out=out2)
        self.assert_exit(r1, 0)
        self.assert_exit(r2, 0)
        self.assertEqual(out1.read_bytes(), out2.read_bytes())

    def test_output_byte_shape(self):
        """encoding_rules: indent=2 / ensure_ascii=False / 末尾改行 1 個 / LF 固定。"""
        res, _, out = self.normalize(H.valid_config())
        self.assert_exit(res, 0)
        raw = out.read_bytes()
        self.assertTrue(raw.endswith(b"\n"), "末尾改行が無い")
        self.assertFalse(raw.endswith(b"\n\n"), "末尾改行が 2 個以上ある")
        self.assertNotIn(b"\r", raw, "CR が混入している")
        self.assertNotIn(b"\\u", raw, "非 ASCII がエスケープされている (ensure_ascii=False でない)")
        self.assertIn(b'\n  "', raw, "indent=2 になっていない")

    def test_array_order_is_preserved(self):
        """encoding_rules: 配列は意味を持つので再ソートしない。"""
        cfg = H.valid_config()
        cfg["sections"] = [H.section("zulu"), H.section("alpha", id="alpha")]
        H.with_visual_floor(cfg)
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual(["zulu", "alpha"], [s["id"] for s in self.read_out(out)["sections"]])

    def test_bom_is_stripped(self):
        """N2: BOM は許容して剥がす。"""
        raw = ("﻿" + json.dumps(H.valid_config(), ensure_ascii=False)).encode("utf-8")
        path = self.write_config(None, raw=raw)
        res = self.run_cli("--config", path, "--normalize", "--out", self.out)
        self.assert_exit(res, 0)
        self.assertFalse(self.out.read_bytes().startswith(b"\xef\xbb\xbf"), "出力に BOM が残っている")

    def test_crlf_input_is_normalized(self):
        """N2: CRLF は LF へ正規化する。"""
        raw = json.dumps(H.valid_config(), ensure_ascii=False, indent=2).replace("\n", "\r\n").encode("utf-8")
        path = self.write_config(None, raw=raw)
        res = self.run_cli("--config", path, "--normalize", "--out", self.out)
        self.assert_exit(res, 0)
        self.assertNotIn(b"\r", self.out.read_bytes())

    def test_strings_are_nfc_normalized(self):
        """encoding_rules: 全ての文字列を NFC 正規化する。"""
        import unicodedata
        cfg = H.valid_config()
        cfg["glossary"] = [{"term": unicodedata.normalize("NFD", "ガイド"), "plain": "手引き"}]
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        term = self.read_out(out)["glossary"][0]["term"]
        self.assertEqual(unicodedata.normalize("NFC", "ガイド"), term)

    def test_trailing_whitespace_is_trimmed_and_newlines_kept(self):
        """encoding_rules: 行末空白は除去、文字列内の改行は保持。"""
        cfg = H.valid_config()
        cfg["sections"][0]["parts"] = [H.text_part("t1", "1 行目です。   \n2 行目です。  ")]
        H.with_visual_floor(cfg)
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        body = self.read_out(out)["sections"][0]["parts"][0]["data"]["body"]
        self.assertEqual("1 行目です。\n2 行目です。", body)


if __name__ == "__main__":
    unittest.main()

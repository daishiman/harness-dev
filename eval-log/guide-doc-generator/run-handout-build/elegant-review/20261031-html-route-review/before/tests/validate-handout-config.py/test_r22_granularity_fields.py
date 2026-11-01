# -*- coding: utf-8 -*-
"""R22 C61 / C62 — detail_level と evidence_depth の 2 軸 (CR-GRANULARITY-*)。

出所は briefs/RESOLUTION-R22.md と script-brief-C12.json の
r22_granularity_constraints (granularity_orthogonality / preset_default_only) および
config_schema.document_level_fields の detail_level / evidence_depth。

- C61: detail_level は enum (overview / standard / detailed)。--normalize が
  doc_type の既定値 (C23 granularity_defaults) を充填し
  provenance.detail_level_source へ 'preset-default' / 'explicit' を記録する。
- C62: evidence_depth は enum (none / cited / sourced) の独立軸。
  3x3=9 通り全てが valid で、禁止の対を 1 つも設けない。

既定値の対応表はこの script が持ってはならない (C23 と二重正本になる) ため、
期待値は C23 のブリーフから読み、テストソースへ書かない。
"""

import json
import unittest
from pathlib import Path

import _harness as H

# RESOLUTION-R22.md 設計判断 1 の値域 (数値ではなく語彙なので直に置く)
DETAIL_LEVELS = ("overview", "standard", "detailed")
EVIDENCE_DEPTHS = ("none", "cited", "sourced")

BRIEFS_DIR = H.REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs"
C23_BRIEF = BRIEFS_DIR / "script-brief-C23.json"


def preset_granularity_defaults(tc):
    """doc_type -> {detail_level, evidence_depth} の既定値 (正本は C23)。"""
    if not C23_BRIEF.is_file():
        tc.fail("既定値の正本が読めない: %s" % C23_BRIEF)
    data = json.loads(C23_BRIEF.read_text(encoding="utf-8"))
    defaults = (data.get("granularity_defaults") or {}).get("defaults")
    if not isinstance(defaults, dict) or not defaults:
        tc.fail("script-brief-C23.json に granularity_defaults.defaults が無い")
    return {
        doc_type: {
            "detail_level": entry.get("detail_level"),
            "evidence_depth": entry.get("evidence_depth"),
        }
        for doc_type, entry in defaults.items()
    }


class R22ConfigTestCase(H.C12TestCase):
    """R22 追補で共有する assert (既存 assert の意味は変えない)。"""

    def assert_rejected_field(self, res, pointer):
        """列挙外の値は exit 1 で、キーパスを名指しした診断行が出ること。

        診断コードそのものは C12 のブリーフが R22 分を定義していないため
        (R22-AMENDMENT.md の gap 参照)、ここではキーパスだけを固定する。
        """
        self.assert_exit(res, 1)
        lines = [l for l in res.stderr.splitlines() if pointer in l]
        self.assertTrue(
            lines,
            "%s を名指しする診断行が stderr に無い\nstderr=%r" % (pointer, res.stderr),
        )
        return lines


class DetailLevelPresetDefault(R22ConfigTestCase):
    """C61: 用途プリセットは既定値を与えるだけ (CR-GRANULARITY-PRESET-DEFAULT-ONLY)。"""

    def test_normalize_fills_default_per_doc_type(self):
        for doc_type, expected in preset_granularity_defaults(self).items():
            with self.subTest(doc_type=doc_type):
                cfg = H.valid_config(doc_type=doc_type)
                cfg.pop("detail_level", None)
                out = self.tmp / ("dl-%s.json" % doc_type)
                res, _, out = self.normalize(cfg, out=out)
                self.assert_exit(res, 0)
                data = self.read_out(out)
                self.assertEqual(expected["detail_level"], data.get("detail_level"))
                self.assertEqual(
                    "preset-default", data["provenance"].get("detail_level_source")
                )

    def test_explicit_value_overrides_the_preset_default(self):
        """既定と異なる値を明示しても拒まない (プリセットは値を固定しない)。"""
        defaults = preset_granularity_defaults(self)
        doc_type, expected = sorted(defaults.items())[0]
        other = [lv for lv in DETAIL_LEVELS if lv != expected["detail_level"]][0]
        cfg = H.valid_config(doc_type=doc_type, detail_level=other)
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        data = self.read_out(out)
        self.assertEqual(other, data["detail_level"])
        self.assertEqual("explicit", data["provenance"]["detail_level_source"])

    def test_explicit_value_equal_to_default_is_still_explicit(self):
        """既定と同値の明示指定でも由来が判別できること。"""
        defaults = preset_granularity_defaults(self)
        doc_type, expected = sorted(defaults.items())[0]
        cfg = H.valid_config(doc_type=doc_type, detail_level=expected["detail_level"])
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual("explicit", self.read_out(out)["provenance"]["detail_level_source"])

    def test_null_is_treated_as_absent(self):
        cfg = H.valid_config(detail_level=None)
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        data = self.read_out(out)
        self.assertIn(data.get("detail_level"), DETAIL_LEVELS)
        self.assertEqual("preset-default", data["provenance"]["detail_level_source"])

    def test_every_level_is_accepted_for_every_doc_type(self):
        """『勉強会だから必ず粗い』を型にしない — どの用途でも 3 水準が通る。"""
        for doc_type in sorted(preset_granularity_defaults(self)):
            for level in DETAIL_LEVELS:
                with self.subTest(doc_type=doc_type, detail_level=level):
                    cfg = H.valid_config(doc_type=doc_type, detail_level=level)
                    res, _ = self.validate(cfg)
                    self.assert_exit(res, 0)


class DetailLevelEnum(R22ConfigTestCase):
    """C61: 値域の検査。"""

    def test_each_enum_value_passes_validation(self):
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                res, _ = self.validate(H.valid_config(detail_level=level))
                self.assert_exit(res, 0)

    def test_unknown_value_is_rejected(self):
        res, _ = self.validate(H.valid_config(detail_level="verbose"))
        self.assert_rejected_field(res, "/detail_level")

    def test_hyphenated_variant_is_rejected(self):
        res, _ = self.validate(H.valid_config(detail_level="over-view"))
        self.assert_rejected_field(res, "/detail_level")

    def test_non_string_is_rejected(self):
        res, _ = self.validate(H.valid_config(detail_level=3))
        self.assert_rejected_field(res, "/detail_level")

    def test_absent_field_is_not_a_validation_error(self):
        """required は『normalize が充填』なので、検証専用実行では欠落を咎めない。"""
        cfg = H.valid_config()
        cfg.pop("detail_level", None)
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_normalized_output_always_carries_the_field(self):
        cfg = H.valid_config()
        cfg.pop("detail_level", None)
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertIn(self.read_out(out).get("detail_level"), DETAIL_LEVELS)


class EvidenceDepthEnum(R22ConfigTestCase):
    """C62: evidence_depth も同格の必須フィールド。"""

    def test_each_enum_value_passes_validation(self):
        for depth in EVIDENCE_DEPTHS:
            with self.subTest(evidence_depth=depth):
                res, _ = self.validate(H.valid_config(evidence_depth=depth))
                self.assert_exit(res, 0)

    def test_unknown_value_is_rejected(self):
        res, _ = self.validate(H.valid_config(evidence_depth="citation"))
        self.assert_rejected_field(res, "/evidence_depth")

    def test_non_string_is_rejected(self):
        res, _ = self.validate(H.valid_config(evidence_depth=True))
        self.assert_rejected_field(res, "/evidence_depth")

    def test_normalize_fills_default_per_doc_type(self):
        for doc_type, expected in preset_granularity_defaults(self).items():
            with self.subTest(doc_type=doc_type):
                cfg = H.valid_config(doc_type=doc_type)
                cfg.pop("evidence_depth", None)
                out = self.tmp / ("ed-%s.json" % doc_type)
                res, _, out = self.normalize(cfg, out=out)
                self.assert_exit(res, 0)
                data = self.read_out(out)
                self.assertEqual(expected["evidence_depth"], data.get("evidence_depth"))
                self.assertEqual(
                    "preset-default", data["provenance"].get("evidence_depth_source")
                )

    def test_explicit_value_is_recorded_as_explicit(self):
        cfg = H.valid_config(evidence_depth="sourced")
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        data = self.read_out(out)
        self.assertEqual("sourced", data["evidence_depth"])
        self.assertEqual("explicit", data["provenance"]["evidence_depth_source"])


class GranularityOrthogonality(R22ConfigTestCase):
    """C62: CR-GRANULARITY-ORTHOGONAL — 9 通り全てが valid で禁止の対が無い。"""

    def test_all_nine_combinations_validate(self):
        for level in DETAIL_LEVELS:
            for depth in EVIDENCE_DEPTHS:
                with self.subTest(detail_level=level, evidence_depth=depth):
                    cfg = H.valid_config(detail_level=level, evidence_depth=depth)
                    res, _ = self.validate(cfg)
                    self.assert_exit(res, 0)

    def test_all_nine_combinations_normalize_without_mutation(self):
        """正規化しても片方の値から他方を書き換えない。"""
        for level in DETAIL_LEVELS:
            for depth in EVIDENCE_DEPTHS:
                with self.subTest(detail_level=level, evidence_depth=depth):
                    cfg = H.valid_config(detail_level=level, evidence_depth=depth)
                    out = self.tmp / ("cmb-%s-%s.json" % (level, depth))
                    res, _, out = self.normalize(cfg, out=out)
                    self.assert_exit(res, 0)
                    data = self.read_out(out)
                    self.assertEqual(level, data["detail_level"])
                    self.assertEqual(depth, data["evidence_depth"])

    def test_changing_one_axis_does_not_move_the_other(self):
        """『どちらか一方だけを変えた 2 つの構成データが両方とも受理される』。"""
        base_depth = EVIDENCE_DEPTHS[0]
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                cfg = H.valid_config(detail_level=level, evidence_depth=base_depth)
                out = self.tmp / ("ax1-%s.json" % level)
                res, _, out = self.normalize(cfg, out=out)
                self.assert_exit(res, 0)
                self.assertEqual(base_depth, self.read_out(out)["evidence_depth"])

        base_level = DETAIL_LEVELS[0]
        for depth in EVIDENCE_DEPTHS:
            with self.subTest(evidence_depth=depth):
                cfg = H.valid_config(detail_level=base_level, evidence_depth=depth)
                out = self.tmp / ("ax2-%s.json" % depth)
                res, _, out = self.normalize(cfg, out=out)
                self.assert_exit(res, 0)
                self.assertEqual(base_level, self.read_out(out)["detail_level"])

    def test_detailed_without_evidence_is_valid(self):
        """利用者の標本に無い組み合わせ (詳しいが根拠は不要) が表現できること。"""
        res, _ = self.validate(H.valid_config(detail_level="detailed", evidence_depth="none"))
        self.assert_exit(res, 0)

    def test_overview_with_sources_is_valid(self):
        """粗いが根拠は示す (経営向けの要約) が表現できること。"""
        res, _ = self.validate(H.valid_config(detail_level="overview", evidence_depth="sourced"))
        self.assert_exit(res, 0)

    def test_no_forbidden_pair_diagnostic_exists_in_the_script(self):
        """禁止の対を 1 つも設けない — 組み合わせを咎める診断語彙を持たない。"""
        src = self.script_source()
        for fragment in (
            "E-GRANULARITY-COMBINATION",
            "E-DETAIL-EVIDENCE",
            "FORBIDDEN_GRANULARITY",
        ):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, src)


class DefaultsAreNotDuplicatedHere(R22ConfigTestCase):
    """C61: 既定値の対応表を C12 が持たない (正本は C23 のみ)。"""

    def test_script_does_not_hardcode_doc_type_vocabulary(self):
        src = self.script_source()
        for doc_type in sorted(preset_granularity_defaults(self)):
            with self.subTest(doc_type=doc_type):
                self.assertNotIn(
                    '"%s"' % doc_type,
                    src,
                    "既定値の対応表が C12 側へ複製されている (正本は C23)",
                )

    def test_script_resolves_defaults_through_c23(self):
        src = self.script_source()
        self.assertIn(
            "resolve-handout-preset",
            src,
            "既定値を C23 のモジュール API から引いていない",
        )


if __name__ == "__main__":
    unittest.main()

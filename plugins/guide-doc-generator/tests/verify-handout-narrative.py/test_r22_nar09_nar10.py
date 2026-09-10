# -*- coding: utf-8 -*-
"""R22 C66 — NAR-09 / NAR-10 (宣言した粒度と実態の突合)。

出所は script-brief-C22.json の detections NAR-09 / NAR-10 と
canonical_rules.granularity_declared_vs_actual、および briefs/RESOLUTION-R22.md。

- NAR-09: root の data-hb-detail-level を読み、role=='main' の全 section の
  可視本文量を section 数で割った 1 セクション平均を実測値とする。
  実測平均が宣言した水準の予算帯 (min/max) から外れていれば違反で、上振れ
  (宣言より詳しく書いた) も下振れ (宣言より薄い) も同じ扱い。3 水準すべてが
  自分の帯で検査される — standard を素通りさせると、既定値を宣言するだけで
  文章量の検査を外せてしまう (利用者指定 2026-08-19 の調整軸)。
- NAR-10: root の data-hb-evidence-depth が cited 以上なら role=='main' の
  各 claim ブロックが根拠参照を 1 つ以上内包すること。sourced ではさらに
  各根拠参照が非空の出典表記を持つこと。none は根拠の有無を問わない。

水準の境界値はテーマトークンから読み、テストソースへ数値を書かない。
"""

from __future__ import annotations

import json
import re
import unittest

from _support import NarrativeGateTestCase, REPO_ROOT, SCRIPT, base_config, build_html

DETAIL_LEVELS = ("overview", "standard", "detailed")
EVIDENCE_DEPTHS = ("none", "cited", "sourced")

R22_DETECTIONS = ("NAR-09", "NAR-10")

MAIN_IDS = ["s1", "s2", "s3", "s4", "s5", "s6"]
APPENDIX_ID = "s7"

PLUGIN_ROOT = REPO_ROOT / "plugins" / "guide-doc-generator"
TOKENS_DIR = PLUGIN_ROOT / "assets" / "tokens"
BY_DETAIL_KEY = "section_body_chars_by_detail_level"
C11_BRIEF = REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs" / "script-brief-C11.json"


def level_limits(tc):
    """水準別の節あたり予算 (min/max)。テーマトークンだけを正本とする。

    C11 ブリーフへの代替経路は持たない。ブリーフが持つのは 1 ブロックの上限で
    単位が違い、そこへ落ちると『通ったが別の値で検査した』状態になる。
    """
    if TOKENS_DIR.is_dir():
        for path in sorted(TOKENS_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            limits = (data.get("text_limits") or {}).get(BY_DETAIL_KEY)
            if isinstance(limits, dict) and all(
                isinstance(limits.get(lv), dict)
                and isinstance(limits[lv].get("min"), int)
                and isinstance(limits[lv].get("max"), int)
                for lv in DETAIL_LEVELS
            ):
                return {lv: dict(limits[lv]) for lv in DETAIL_LEVELS}
    tc.fail("テーマトークンに %s (min/max) が無い: %s" % (BY_DETAIL_KEY, TOKENS_DIR))


def in_band_chars(limits, level, baseline):
    """その水準の帯の真ん中へ収まる filler 字数。

    見出し・lead-line など HTML の定型文 (baseline) は filler と別に数えられる。
    帯の狭い overview では baseline だけで上限へ届くため、テスト側で引いておく
    (数値の正本はトークン、baseline は実測。どちらもテストに直書きしない)。
    """
    band = limits[level]
    return max(0, (band["min"] + band["max"]) // 2 - baseline)


def filler(chars):
    return "    <p>%s</p>\n" % ("あ" * chars) if chars > 0 else ""


def claim_block(index, evidence=True, source="社内検証レポート 2026-08"):
    """主張ブロック 1 件。evidence=False なら根拠を内包しない。"""
    body = '    <div data-hb-part="B05" data-hb-block-role="claim">\n'
    body += "      <p>主張 %d: この手順を採ると手戻りが減ります。</p>\n" % index
    if evidence:
        attrs = 'data-hb-evidence="ev%d"' % index
        if source is not None:
            attrs += ' data-hb-evidence-source="%s"' % source
        body += "      <p %s>根拠となる観測をここに書く。</p>\n" % attrs
    body += "    </div>\n"
    return body


def _inject(html, section_id, extra):
    if not extra:
        return html
    marker = '<section id="%s"' % section_id
    start = html.index(marker)
    end = html.index("  </section>\n", start)
    return html[:end] + extra + html[end:]


def granular_html(
    cfg,
    detail_level,
    evidence_depth,
    main_body_chars=0,
    appendix_body_chars=0,
    claims_per_main=0,
    claim_options=None,
    appendix_claims=0,
    **opts,
):
    """粒度を宣言し、主張ブロックと本文量を制御した HTML を組み立てる。"""
    html = build_html(cfg, **opts)
    html = html.replace(
        '<html lang="ja"',
        '<html lang="ja" data-hb-detail-level="%s" data-hb-evidence-depth="%s"'
        % (detail_level, evidence_depth),
        1,
    )
    claim_options = claim_options or {}
    counter = 0
    for sec in cfg["sections"]:
        sid = sec["id"]
        if sec["role"] == "main":
            extra = filler(main_body_chars)
            for _ in range(claims_per_main):
                counter += 1
                extra += claim_block(counter, **claim_options.get(counter, {}))
            html = _inject(html, sid, extra)
        else:
            extra = filler(appendix_body_chars)
            for _ in range(appendix_claims):
                counter += 1
                extra += claim_block(counter, evidence=False)
            html = _inject(html, sid, extra)
    return html


def granular_config(detail_level, evidence_depth, **overrides):
    cfg = base_config(**overrides)
    cfg["detail_level"] = detail_level
    cfg["evidence_depth"] = evidence_depth
    cfg["provenance"] = dict(cfg["provenance"])
    cfg["provenance"]["detail_level_source"] = "explicit"
    cfg["provenance"]["evidence_depth_source"] = "explicit"
    return cfg


class R22GateTestCase(NarrativeGateTestCase):
    """NAR-09 / NAR-10 の行を読むための追加ヘルパ。

    P04-x-05 の裁定 B により _support.DETECTION_ORDER は NAR-01..NAR-10 の
    10 件 (detections 配列の定義順) へ追従済みで、summary() も R22 の行を読む。
    本ヘルパは R22 の 2 件だけを取り出すための絞り込みとして残す
    (経緯は R22-AMENDMENT.md と RESOLUTION-P04-x-05.md の裁定 B)。
    """

    def r22_summary(self, res):
        rows = {}
        for line in res.stdout.splitlines():
            fields = line.split()
            if not fields or fields[0] not in R22_DETECTIONS:
                continue
            row = {"status": fields[1] if len(fields) > 1 else ""}
            for f in fields[2:]:
                if "=" in f:
                    k, v = f.split("=", 1)
                    row[k] = v
            rows[fields[0]] = row
        return rows

    def assert_detection_pass(self, res, detection_id):
        row = self.r22_summary(res).get(detection_id)
        self.assertIsNotNone(
            row, "stdout に %s のサマリ行が無い\nstdout=%r" % (detection_id, res.stdout)
        )
        self.assertEqual(
            "PASS", row["status"], "%s は PASS のはず\nstderr=%r" % (detection_id, res.stderr)
        )

    def assert_detection_fail(self, res, detection_id, count=None):
        self.assertEqual(
            1, res.returncode, "違反検出は exit 1\nstdout=%s\nstderr=%s" % (res.stdout, res.stderr)
        )
        row = self.r22_summary(res).get(detection_id)
        self.assertIsNotNone(
            row, "stdout に %s のサマリ行が無い\nstdout=%r" % (detection_id, res.stdout)
        )
        self.assertEqual("FAIL", row["status"], "%s は FAIL のはず" % detection_id)
        n = int(row.get("violations", "0"))
        if count is None:
            self.assertGreaterEqual(n, 1, "%s の violations は 1 以上" % detection_id)
        else:
            self.assertEqual(count, n, "%s の violations 件数" % detection_id)
        self.assertGreaterEqual(
            len(self.stderr_rows(res, detection_id)),
            1,
            "%s の違反行が stderr に無い\nstderr=%r" % (detection_id, res.stderr),
        )

    def baseline_chars(self):
        """filler 0 のときの 1 セクション平均。detailed 宣言の違反行から実測する。"""
        res = self.run_granular("detailed", "none", main_body_chars=0)
        rows = self.stderr_rows(res, "NAR-09")
        for row in rows:
            found = re.search(r"measured_avg_chars=(\d+)", "\t".join(row))
            if found:
                return int(found.group(1))
        self.fail("baseline を実測できない (stderr=%r)" % res.stderr)

    def run_granular(self, detail_level, evidence_depth, **kwargs):
        cfg = granular_config(detail_level, evidence_depth)
        html = granular_html(cfg, detail_level, evidence_depth, **kwargs)
        return self.run_gate(self.write_html(html), self.write_config(cfg))


class DetectionSurfaceTest(R22GateTestCase):
    """C66: 2 検出が stdout の集計面に現れること。"""

    def test_both_detections_are_reported(self):
        res = self.run_granular("standard", "none")
        rows = self.r22_summary(res)
        for detection_id in R22_DETECTIONS:
            with self.subTest(detection=detection_id):
                self.assertIn(detection_id, rows, "stdout=%r" % res.stdout)

    def test_rows_carry_checked_and_violations(self):
        res = self.run_granular("standard", "none")
        rows = self.r22_summary(res)
        for detection_id in R22_DETECTIONS:
            with self.subTest(detection=detection_id):
                row = rows.get(detection_id, {})
                self.assertIn("checked", row)
                self.assertIn("violations", row)

    def test_detection_order_places_r22_after_r21(self):
        res = self.run_granular("standard", "none")
        seen = [
            line.split()[0]
            for line in res.stdout.splitlines()
            if line.split() and line.split()[0].startswith("NAR-")
        ]
        self.assertEqual(
            sorted(seen), seen, "detection 行は id の昇順で固定\nstdout=%r" % res.stdout
        )


class Nar09DeclaredDetailLevelTest(R22GateTestCase):
    """NAR-09: 宣言した detail_level が実態と一致すること。"""

    def test_detailed_declared_with_overview_sized_body_is_violation(self):
        res = self.run_granular("detailed", "none", main_body_chars=0)
        self.assert_detection_fail(res, "NAR-09")

    def test_detailed_declared_with_detailed_sized_body_passes(self):
        limits = level_limits(self)
        res = self.run_granular(
            "detailed", "none", main_body_chars=in_band_chars(limits, "detailed", self.baseline_chars()))
        self.assert_detection_pass(res, "NAR-09")

    def test_overview_declared_with_detailed_sized_body_is_violation(self):
        limits = level_limits(self)
        res = self.run_granular("overview", "none", main_body_chars=limits["detailed"]["max"] * 2)
        self.assert_detection_fail(res, "NAR-09")

    def test_overview_declared_with_small_body_passes(self):
        res = self.run_granular("overview", "none", main_body_chars=0)
        self.assert_detection_pass(res, "NAR-09")

    def test_standard_is_checked_on_both_sides(self):
        """既定値の宣言で検査を外せない (両側とも自分の帯で見る)。"""
        limits = level_limits(self)
        for chars in (0, limits["detailed"]["max"] * 2):
            with self.subTest(main_body_chars=chars):
                res = self.run_granular("standard", "none", main_body_chars=chars)
                self.assert_detection_fail(res, "NAR-09")

    def test_standard_declared_with_standard_sized_body_passes(self):
        limits = level_limits(self)
        res = self.run_granular(
            "standard", "none", main_body_chars=in_band_chars(limits, "standard", self.baseline_chars()))
        self.assert_detection_pass(res, "NAR-09")

    def test_average_not_total(self):
        """セクション数が多いだけで detailed 判定にならない。"""
        res = self.run_granular("detailed", "none", main_body_chars=0)
        self.assert_detection_fail(res, "NAR-09")
        row = self.r22_summary(res)["NAR-09"]
        self.assertEqual(str(len(MAIN_IDS)), row.get("checked"))

    def test_appendix_body_does_not_rescue_the_declaration(self):
        """実測は role=='main' の平均。付録を膨らませても detailed にならない。"""
        limits = level_limits(self)
        res = self.run_granular(
            "detailed", "none", main_body_chars=0, appendix_body_chars=limits["detailed"]["max"] * 10
        )
        self.assert_detection_fail(res, "NAR-09")

    def test_stderr_names_the_declared_and_measured_values(self):
        res = self.run_granular("detailed", "none", main_body_chars=0)
        rows = self.stderr_rows(res, "NAR-09")
        self.assertTrue(rows, "stderr=%r" % res.stderr)
        joined = "\n".join("\t".join(r) for r in rows)
        self.assertIn("detailed", joined, "宣言値が違反行に無い")

    def test_missing_declaration_attribute_is_an_error(self):
        """検査に必要な属性が無い場合は PASS でも FAIL でもなく検査不成立。"""
        cfg = granular_config("detailed", "none")
        html = granular_html(cfg, "detailed", "none")
        html = re.sub(r'\s*data-hb-detail-level="[^"]*"', "", html, count=1)
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assertIn(
            res.returncode, (1, 2), "宣言が読めない資料を通してはならない\nstdout=%r" % res.stdout
        )


class Nar09NumbersLiveInTheThemeTokenTest(R22GateTestCase):
    """NAR-09: 水準の境界値は C11 のテーマトークンから引き、本 script に持たない。"""

    def test_script_has_no_numeric_literal_of_the_boundaries(self):
        self.require_script()
        src = SCRIPT.read_text(encoding="utf-8")
        limits = level_limits(self)
        for level in ("overview", "detailed"):
            with self.subTest(level=level):
                self.assertIsNone(
                    re.search(r"(?<![\w.])%d(?![\w.])" % limits[level]["max"], src),
                    "水準の境界値 %s が script へ埋め込まれている" % level,
                )

    def test_script_reads_the_theme_token_key(self):
        self.require_script()
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(BY_DETAIL_KEY, src, "テーマトークンのキーを参照していない")


class Nar10EvidenceDepthTest(R22GateTestCase):
    """NAR-10: 宣言した evidence_depth が実態と一致すること。"""

    def test_cited_passes_when_every_claim_has_evidence(self):
        res = self.run_granular("standard", "cited", claims_per_main=1)
        self.assert_detection_pass(res, "NAR-10")

    def test_cited_fails_when_one_claim_lacks_evidence(self):
        options = {1: {"evidence": False}}
        res = self.run_granular(
            "standard", "cited", claims_per_main=1, claim_options=options
        )
        self.assert_detection_fail(res, "NAR-10", count=1)

    def test_cited_does_not_require_a_source_label(self):
        options = {i: {"source": None} for i in range(1, len(MAIN_IDS) + 1)}
        res = self.run_granular(
            "standard", "cited", claims_per_main=1, claim_options=options
        )
        self.assert_detection_pass(res, "NAR-10")

    def test_sourced_requires_a_non_empty_source_label(self):
        options = {i: {"source": None} for i in range(1, len(MAIN_IDS) + 1)}
        res = self.run_granular(
            "standard", "sourced", claims_per_main=1, claim_options=options
        )
        self.assert_detection_fail(res, "NAR-10")

    def test_sourced_rejects_an_empty_source_label(self):
        options = {i: {"source": ""} for i in range(1, len(MAIN_IDS) + 1)}
        res = self.run_granular(
            "standard", "sourced", claims_per_main=1, claim_options=options
        )
        self.assert_detection_fail(res, "NAR-10")

    def test_sourced_passes_when_every_evidence_has_a_source(self):
        res = self.run_granular("standard", "sourced", claims_per_main=1)
        self.assert_detection_pass(res, "NAR-10")

    def test_none_is_permissive(self):
        """none は『根拠を書いてはならない』ではない。"""
        options = {i: {"evidence": False} for i in range(1, len(MAIN_IDS) + 1)}
        res = self.run_granular("standard", "none", claims_per_main=1, claim_options=options)
        self.assert_detection_pass(res, "NAR-10")

    def test_none_also_passes_when_evidence_is_present(self):
        res = self.run_granular("standard", "none", claims_per_main=1)
        self.assert_detection_pass(res, "NAR-10")

    def test_judgement_is_per_claim_not_per_document(self):
        """1 箇所だけ根拠がある資料が sourced を名乗れない。"""
        options = {i: {"evidence": False} for i in range(2, len(MAIN_IDS) + 1)}
        res = self.run_granular(
            "standard", "sourced", claims_per_main=1, claim_options=options
        )
        self.assert_detection_fail(res, "NAR-10", count=len(MAIN_IDS) - 1)

    def test_vacuous_pass_without_claim_blocks(self):
        res = self.run_granular("standard", "sourced", claims_per_main=0)
        self.assert_detection_pass(res, "NAR-10")
        self.assertEqual("0", self.r22_summary(res)["NAR-10"].get("checked"))

    def test_appendix_claims_are_out_of_scope(self):
        res = self.run_granular(
            "standard", "sourced", claims_per_main=1, appendix_claims=1
        )
        self.assert_detection_pass(res, "NAR-10")

    def test_stderr_names_the_offending_claim(self):
        options = {1: {"evidence": False}}
        res = self.run_granular(
            "standard", "cited", claims_per_main=1, claim_options=options
        )
        rows = self.stderr_rows(res, "NAR-10")
        self.assertTrue(rows, "stderr=%r" % res.stderr)
        self.assertTrue(
            any("s1" in "\t".join(r) for r in rows),
            "違反した claim のセクションが特定できない: %r" % res.stderr,
        )


class GranularityAxesAreIndependentAtTheGateTest(R22GateTestCase):
    """C62 の直交性がゲート側でも保たれること (片方の違反が他方を巻き込まない)。"""

    def test_nar09_violation_does_not_fail_nar10(self):
        res = self.run_granular("detailed", "cited", main_body_chars=0, claims_per_main=1)
        self.assert_detection_fail(res, "NAR-09")
        self.assert_detection_pass(res, "NAR-10")

    def test_nar10_violation_does_not_fail_nar09(self):
        limits = level_limits(self)
        options = {1: {"evidence": False}}
        res = self.run_granular(
            "detailed",
            "cited",
            main_body_chars=in_band_chars(limits, "detailed", self.baseline_chars()),
            claims_per_main=1,
            claim_options=options,
        )
        self.assert_detection_pass(res, "NAR-09")
        self.assert_detection_fail(res, "NAR-10")

    def test_all_nine_declarations_are_accepted_by_the_gate(self):
        """9 通りの宣言そのものを不正扱いしない (禁止の対は無い)。"""
        limits = level_limits(self)
        baseline = self.baseline_chars()
        for level in DETAIL_LEVELS:
            chars = in_band_chars(limits, level, baseline)
            for depth in EVIDENCE_DEPTHS:
                with self.subTest(detail_level=level, evidence_depth=depth):
                    res = self.run_granular(
                        level, depth, main_body_chars=chars, claims_per_main=1
                    )
                    self.assertNotEqual(
                        2, res.returncode, "宣言の組み合わせを検査不成立にしてはならない"
                    )
                    self.assert_detection_pass(res, "NAR-09")
                    self.assert_detection_pass(res, "NAR-10")


if __name__ == "__main__":
    unittest.main()

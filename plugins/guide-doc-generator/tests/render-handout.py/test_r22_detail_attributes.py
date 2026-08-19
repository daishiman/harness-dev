"""R22 C63 (数値の正本とレンダリング側) — テーマトークンと粒度属性の焼き込み。

契約の出所は script-brief-C11.json の
- theme_token_schema_ownership.added_block_r22 / added_block_r22_values
  (text_limits.block_body_max_chars_by_detail_level。値の正本はテーマトークン)
- html_attribute_contract の data-hb-detail-level / data-hb-evidence-depth

C11 は上限を適用しない (折り畳みは C12 --normalize)。C11 の責務は
「採用した上限をそのまま焼く」ことと「open 属性をデータどおりに描く」こと。
上限の数値はテーマトークン (無ければ C11 のブリーフ) から読み、テストソースへ
書かない。
"""

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _harness as H

DETAIL_LEVELS = ("overview", "standard", "detailed")
EVIDENCE_DEPTHS = ("none", "cited", "sourced")

BY_DETAIL_KEY = "block_body_max_chars_by_detail_level"
TOKENS_DIR = H.PLUGIN_ROOT / "assets" / "tokens"
C11_BRIEF = H.REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs" / "script-brief-C11.json"


def brief_limits(tc):
    """水準別上限の確定値 (script-brief-C11.json added_block_r22_values)。"""
    if not C11_BRIEF.is_file():
        tc.fail("水準別上限の値が読める正本が無い: %s" % C11_BRIEF)
    data = json.loads(C11_BRIEF.read_text(encoding="utf-8"))
    values = (data.get("theme_token_schema_ownership") or {}).get("added_block_r22_values")
    if not isinstance(values, dict):
        tc.fail("script-brief-C11.json に added_block_r22_values が無い")
    limits = {}
    for level in DETAIL_LEVELS:
        value = values.get(level)
        if not isinstance(value, int):
            tc.fail("added_block_r22_values.%s が整数でない: %r" % (level, value))
        limits[level] = value
    return limits


def token_files(tc):
    if not TOKENS_DIR.is_dir():
        tc.fail("テーマトークン置き場が未実装: %s (owner=C11)" % TOKENS_DIR)
    paths = sorted(TOKENS_DIR.glob("*.json"))
    if not paths:
        tc.fail("テーマトークンが 1 件も無い: %s" % TOKENS_DIR)
    return paths


def token_limits(tc, path):
    data = json.loads(path.read_text(encoding="utf-8"))
    limits = (data.get("text_limits") or {}).get(BY_DETAIL_KEY)
    if not isinstance(limits, dict):
        tc.fail("text_limits.%s が無い: %s" % (BY_DETAIL_KEY, path))
    return limits


def granular_config(detail_level, evidence_depth, **over):
    cfg = H.base_config(**over)
    cfg["detail_level"] = detail_level
    cfg["evidence_depth"] = evidence_depth
    cfg.setdefault("provenance", {})
    cfg["provenance"] = dict(cfg["provenance"])
    cfg["provenance"]["detail_level_source"] = "preset-default"
    cfg["provenance"]["evidence_depth_source"] = "preset-default"
    return cfg


def html_root(tc, html_text):
    for el in H.parse(html_text):
        if el.tag == "html":
            return el
    tc.fail("<html> 要素が無い")


class ThemeTokenLevelLimitsTest(unittest.TestCase):
    """added_block_r22: 水準別の上限はテーマトークンが持つ。"""

    def test_every_theme_declares_the_three_levels(self):
        for path in token_files(self):
            limits = token_limits(self, path)
            for level in DETAIL_LEVELS:
                with self.subTest(theme=path.stem, level=level):
                    self.assertIsInstance(limits.get(level), int)

    def test_values_match_the_decided_numbers(self):
        expected = brief_limits(self)
        for path in token_files(self):
            with self.subTest(theme=path.stem):
                self.assertEqual(expected, {k: token_limits(self, path).get(k) for k in expected})

    def test_standard_equals_the_r21_default_key(self):
        """既存の block_body_max_chars は standard の値として残る。"""
        for path in token_files(self):
            data = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(theme=path.stem):
                self.assertEqual(
                    data["text_limits"].get("block_body_max_chars"),
                    token_limits(self, path).get("standard"),
                )

    def test_renderer_has_no_numeric_literal_of_the_limits(self):
        """数値の正本はテーマトークン 1 箇所 — script 側へ書かない。"""
        src = H.source_text()
        for level, value in brief_limits(self).items():
            with self.subTest(level=level):
                # 直後の % を除外するのは CSS の長さ指定 (width: 100%) を上限の
                # 焼き込みと読み違えないため。上限は文字数なので単位を伴わない。
                # この除外を入れないと、上限値が 100 のように CSS で頻出する数へ
                # 決まった瞬間に本検査が偽陽性で赤くなり、直し方が「CSS を壊す」
                # しか無くなる (実際 R25/REQ-7 で standard=100 になり発生した)。
                self.assertIsNone(
                    re.search(r"(?<![\w.])%d(?![\w.%%])" % value, src),
                    "上限 %s (%d) が script へ数値リテラルとして埋め込まれている" % (level, value),
                )


class GranularityAttributeTest(unittest.TestCase):
    """html_attribute_contract: data-hb-detail-level / data-hb-evidence-depth。"""

    def _render(self, detail_level, evidence_depth):
        cfg = granular_config(detail_level, evidence_depth)
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, cfg)
        self.assertEqual(0, res.returncode, res.stderr)
        return html_text

    def test_both_attributes_are_emitted_verbatim(self):
        for level in DETAIL_LEVELS:
            for depth in EVIDENCE_DEPTHS:
                with self.subTest(detail_level=level, evidence_depth=depth):
                    root = html_root(self, self._render(level, depth))
                    self.assertEqual(level, root.get("data-hb-detail-level"))
                    self.assertEqual(depth, root.get("data-hb-evidence-depth"))

    def test_attributes_are_two_not_one(self):
        """1 属性へ連結しない (C22 が分解を要さないため)。"""
        html_text = self._render("detailed", "sourced")
        self.assertEqual(1, len(H.elements_with(html_text, "data-hb-detail-level")))
        self.assertEqual(1, len(H.elements_with(html_text, "data-hb-evidence-depth")))

    def test_renderer_does_not_derive_the_values(self):
        """導出点は C12 のみ。doc_type から引き直さない。"""
        cfg = granular_config("overview", "none", doc_type="report")
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, cfg)
        self.assertEqual(0, res.returncode, res.stderr)
        root = html_root(self, html_text)
        self.assertEqual("overview", root.get("data-hb-detail-level"))
        self.assertEqual("none", root.get("data-hb-evidence-depth"))


class TextLimitBakingTest(unittest.TestCase):
    """data-hb-text-limit は採用水準の上限を焼く (C52 の 1 値を R22 で水準別に引く)。"""

    def test_baked_limit_follows_the_detail_level(self):
        limits = brief_limits(self)
        for level in DETAIL_LEVELS:
            with self.subTest(detail_level=level):
                cfg = granular_config(level, "none")
                with tempfile.TemporaryDirectory() as td:
                    res, html_text, _ = H.render_html(td, cfg)
                self.assertEqual(0, res.returncode, res.stderr)
                self.assertEqual(
                    str(limits[level]), html_root(self, html_text).get("data-hb-text-limit")
                )

    def test_falls_back_to_block_body_max_chars_when_key_absent(self):
        """キーを持たないテーマでも壊れない (fail-soft)。複製した写しで検証する。"""
        H.require_script()
        limits = brief_limits(self)
        cfg = granular_config("detailed", "none")
        with tempfile.TemporaryDirectory() as td:
            clone = Path(td) / "plugin"
            shutil.copytree(H.PLUGIN_ROOT, clone, symlinks=True)
            tokens_dir = clone / "assets" / "tokens"
            if not tokens_dir.is_dir():
                self.fail("テーマトークン置き場が未実装: %s" % (H.PLUGIN_ROOT / "assets" / "tokens"))
            fallback = None
            for path in sorted(tokens_dir.glob("*.json")):
                data = json.loads(path.read_text(encoding="utf-8"))
                text_limits = data.setdefault("text_limits", {})
                text_limits.pop(BY_DETAIL_KEY, None)
                text_limits["block_body_max_chars"] = limits["overview"]
                fallback = limits["overview"]
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            if fallback is None:
                self.fail("テーマトークンが 1 件も無い: %s" % tokens_dir)
            cfg_path = H.write_config(Path(td) / "config.json", cfg)
            out = Path(td) / "handout.html"
            proc = subprocess.run(
                [sys.executable, str(clone / "scripts" / "render-handout.py"),
                 "--config", str(cfg_path), "--out", str(out)],
                capture_output=True, text=True,
                env={**os.environ, "HB_ROOT": str(clone)},
            )
            html_text = out.read_text(encoding="utf-8") if out.is_file() else ""
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(str(fallback), html_root(self, html_text).get("data-hb-text-limit"))


class AccordionOpenStateTest(unittest.TestCase):
    """fold_behavior_at_detailed: 構造は全水準で同一、open 属性だけが変わる。"""

    def _accordion_config(self, detail_level, open_flag):
        block = copy.deepcopy(H.BLOCK_FIXTURES["accordion"])
        block["id"] = "blk-text-cont"
        block["items"] = [
            {"key": "ac1", "summary": "詳しい説明 (続き)", "body": "折り畳まれた残余の本文",
             "open": open_flag}
        ]
        cfg = granular_config(detail_level, "none")
        cfg["sections"] = [H.base_section(1, blocks=[H.BLOCK_FIXTURES["text"], block])]
        cfg["nav"] = [{"href": "#" + s["id"], "label": s["heading"]} for s in cfg["sections"]]
        return cfg

    def _details_elements(self, cfg):
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, cfg)
        self.assertEqual(0, res.returncode, res.stderr)
        roots = H.part_elements(html_text, "B10")
        self.assertTrue(roots, "B10 が描画されていない")
        details = [el for el in H.parse(html_text) if el.tag == "details"]
        self.assertTrue(details, "<details> が描画されていない")
        return details

    def test_open_true_renders_the_open_attribute(self):
        """detailed が生成する B10 は open=true として描かれる。"""
        for el in self._details_elements(self._accordion_config("detailed", True)):
            self.assertIn("open", el.attrs, "open=true の項目が畳まれている")

    def test_open_false_renders_without_the_attribute(self):
        for level in ("overview", "standard"):
            with self.subTest(detail_level=level):
                for el in self._details_elements(self._accordion_config(level, False)):
                    self.assertNotIn("open", el.attrs, "open=false の項目が開いている")

    def test_renderer_does_not_decide_the_open_state_by_itself(self):
        """open の決定者は C12 (--normalize)。C11 は水準から推測しない。"""
        for el in self._details_elements(self._accordion_config("detailed", False)):
            self.assertNotIn(
                "open", el.attrs, "detail_level から open を推測してはならない"
            )

    def test_structure_is_identical_regardless_of_open_state(self):
        opened = self._details_elements(self._accordion_config("detailed", True))
        closed = self._details_elements(self._accordion_config("overview", False))
        self.assertEqual(len(opened), len(closed))


if __name__ == "__main__":
    unittest.main()

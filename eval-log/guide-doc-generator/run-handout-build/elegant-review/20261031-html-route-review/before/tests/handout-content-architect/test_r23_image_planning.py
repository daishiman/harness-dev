"""C05 agent 側の RESOLUTION-R23 契約 (AC8 / AC9 / AC10) を赤で固定する。

対象: plugins/guide-doc-generator/agents/handout-content-architect.md (producer: P05-C05-01)

このファイルは `contract_lib.py` を変更せず、R23 で追加された宣言だけを独立に検査する。
判定は宣言的 (agent 定義 Markdown の記述) に限り、agent の実行結果は見ない
(AC10 の実行検査は C21 側の tests/srg-image-bridge.py/ が事前検査として持つ)。

正本の二重化を避けるための約束:
- 焼き込みの上限値は書かない。C21 brief の `baked_text_discipline` から読んで
  「その数値が agent 本文に現れない」ことだけを見る。
- motif 名 / 密度語彙 / layoutTemplate 名は genome ファイルから読む。
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

REPO_ROOT = contract_lib.repo_root()
AGENT_MD = contract_lib.build_target()
C21_BRIEF = REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs" / "script-brief-C21.json"


def _brief() -> dict:
    return json.loads(C21_BRIEF.read_text(encoding="utf-8"))


def _genome_paths() -> list[Path]:
    """brief の family → genome テンプレートを repo 実体へ解決する。"""
    families = _brief()["image_style_families"]["families"]
    paths = []
    for spec in families.values():
        template = str(spec["genome"])
        resolved = template.replace(
            "<SRG_ROOT>", str(REPO_ROOT / "plugins" / "slide-report-generator")
        ).replace("<HB_ROOT>", str(REPO_ROOT / "plugins" / "guide-doc-generator"))
        paths.append(Path(resolved))
    return paths


def _find_key(node, key):
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            found = _find_key(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_key(value, key)
            if found is not None:
                return found
    return None


class _AgentTextTest(unittest.TestCase):
    """agent 定義が未実装なら fail (skip しない)。"""

    def setUp(self):
        if not AGENT_MD.is_file():
            self.fail("agent 定義が未実装: {} (owner: P05-C05-01)".format(AGENT_MD))
        self.text = AGENT_MD.read_text(encoding="utf-8")

    def assertOrdered(self, markers, message):
        positions = []
        for marker in markers:
            index = self.text.find(marker)
            self.assertNotEqual(-1, index, "{}: 記述が無い ({})".format(message, marker))
            positions.append(index)
        self.assertEqual(sorted(positions), positions, "{}: 順序が違う ({})".format(message, markers))


class AdaptationProcedureTest(_AgentTextTest):
    """AC8: セクション別内容適応の 4 段が順番付きで required。"""

    def test_the_four_stages_appear_in_order(self):
        self.assertOrdered(
            ["adaptation_trace", "semanticMapping", "layoutSelectionByStructure", "props"],
            "内容適応 4 段 (概念抽出 → 具体物写像 → 図解型と密度 → 3 役 motifs)",
        )

    def test_the_stages_are_declared_required(self):
        self.assertTrue(
            re.search(r"(required|必ず|必須)", self.text),
            "4 段が required として書かれていない",
        )

    def test_novelty_fallback_is_declared(self):
        for token in ("noveltyRule", "densityPreservation", "densityLevels"):
            self.assertIn(token, self.text, "{} への参照が無い".format(token))

    def test_copying_the_reference_deck_is_forbidden(self):
        self.assertTrue(
            re.search(r"丸写し", self.text), "『参照デッキの構図を丸写ししない』の禁止が無い"
        )

    def test_writing_genome_vocabulary_from_memory_is_forbidden(self):
        self.assertTrue(
            re.search(r"記憶", self.text), "『genome の語彙を記憶で書かない』の禁止が無い"
        )


class NoDuplicatedSourceOfTruthTest(_AgentTextTest):
    """AC9: 上限値 / genome 語彙を agent 本文へ写さない。"""

    def test_no_baked_text_limit_numbers(self):
        discipline = _brief()["baked_text_discipline"]
        limits = [
            int(discipline["blocks_per_image_max"]),
            int(discipline["chars_per_block_max"]),
        ]
        offenders = []
        for line in self.text.splitlines():
            if not re.search(r"(baked|焼き込み|ブロック|字数)", line):
                continue
            for number in limits:
                if re.search(r"(?<![0-9]){}(?![0-9])".format(number), line):
                    offenders.append(line.strip())
        self.assertEqual(
            [], offenders, "焼き込み上限の数値を持っている (正本は C21 の baked_text_discipline)"
        )

    def test_the_limits_are_delegated_to_c21_in_words(self):
        self.assertTrue(
            re.search(r"C21", self.text), "上限の正本が C21 であることが書かれていない"
        )

    def test_no_motif_name_is_enumerated(self):
        offenders = []
        for path in _genome_paths():
            if not path.is_file():
                self.fail("genome が未存在: {} (owner: P05-x-04)".format(path))
            data = json.loads(path.read_text(encoding="utf-8"))
            for motif in _find_key(data, "motifs") or []:
                name = motif.get("name") if isinstance(motif, dict) else motif
                if isinstance(name, str) and name and name in self.text:
                    offenders.append(name)
        self.assertEqual([], offenders, "genome の motif 名を写している (正本は genome ファイル)")

    def test_no_density_word_is_enumerated(self):
        offenders = []
        for path in _genome_paths():
            if not path.is_file():
                self.fail("genome が未存在: {} (owner: P05-x-04)".format(path))
            levels = _find_key(json.loads(path.read_text(encoding="utf-8")), "densityLevels") or {}
            for level in levels:
                if re.search(r"""["'`]{}["'`]""".format(re.escape(level)), self.text):
                    offenders.append(level)
        self.assertEqual([], offenders, "密度語彙を写している (正本は genome ファイル)")

    def test_no_layout_template_name_is_enumerated(self):
        offenders = []
        for path in _genome_paths():
            if not path.is_file():
                self.fail("genome が未存在: {} (owner: P05-x-04)".format(path))
            table = _find_key(json.loads(path.read_text(encoding="utf-8")), "layoutSelectionByStructure")
            for value in (table or {}).values():
                if isinstance(value, str) and re.search(
                    r"""["'`]{}["'`]""".format(re.escape(value)), self.text
                ):
                    offenders.append(value)
        self.assertEqual([], offenders, "layoutTemplate 名を写している (正本は genome ファイル)")

    def test_no_prompt_template_body(self):
        """C17: プロンプト本文のテンプレートを持たない (組み立ては委譲先の責務)。"""
        for token in ("promptSuffix", "negativePrompt", "consistencyAnchors"):
            self.assertNotIn(token, self.text, "プロンプト構成物 {} を持っている".format(token))


class OutputFieldContractTest(_AgentTextTest):
    """AC10 の前提: 出力フィールドが宣言されている (実行検査は C21 側)。"""

    def test_required_image_fields_are_declared(self):
        for field in (
            "overlay_text",
            "baked_text",
            "motifs",
            "platform",
            "primary",
            "props",
            "density_level",
            "adaptation_trace",
            "style_family",
            "diagram_pattern",
        ):
            self.assertIn(field, self.text, "画像計画フィールド {} の宣言が無い".format(field))

    def test_default_text_policy_is_baked_with_overlay(self):
        self.assertIn(
            "baked-with-overlay", self.text, "既定の text_policy (R23 (a)) が書かれていない"
        )

    def test_overlay_only_is_paired_with_a_reason(self):
        self.assertIn("text_policy_reason", self.text, "overlay-only の対指定が書かれていない")

    def test_overlay_text_is_always_non_empty(self):
        self.assertTrue(
            re.search(r"overlay_text[^\n]*(非空|必ず)", self.text),
            "overlay_text が常に非空である旨が書かれていない",
        )

    def test_the_three_baked_forms_are_closed(self):
        forms = tuple(_brief()["baked_text_discipline"]["forms"].keys())
        for form in forms:
            self.assertIn(form, self.text, "焼き込み形式 {} の宣言が無い".format(form))
        self.assertTrue(
            re.search(r"(句点|完全文)", self.text), "完全文を焼かない旨が書かれていない"
        )

    def test_both_style_families_are_named(self):
        for family in _brief()["image_style_families"]["families"]:
            self.assertIn(family, self.text, "style family {} の宣言が無い".format(family))

    def test_uniform_composition_self_check_is_declared(self):
        self.assertTrue(
            re.search(r"diagram_pattern[^\n]*motifs\.primary|motifs\.primary[^\n]*diagram_pattern", self.text),
            "(図解型, motifs.primary) の全件同一を自己確認する旨が書かれていない (R23 (e))",
        )

    def test_isometric_comic_scene_is_the_handout_default(self):
        self.assertTrue(
            re.search(r"配布ガイド[\s\S]{0,120}既定[\s\S]{0,120}isometric-diorama", self.text),
            "配布ガイドの illustration が漫画調ジオラマを既定にしていない",
        )

    def test_subject_contract_requires_a_concrete_scene(self):
        for token in ("人物または役割主体", "行為", "場所", "主役の具体物", "読み順"):
            self.assertIn(token, self.text, "subject / diagram_structure の場面要件 {} が無い".format(token))

    def test_generic_icon_grid_is_forbidden(self):
        for token in ("抽象アイコン", "UI カード", "主役にしない"):
            self.assertIn(token, self.text, "汎用インフォグラフィック退化の禁止 {} が無い".format(token))

    def test_style_reference_is_forwarded_by_the_parent(self):
        self.assertIn("style_reference_paths", self.text)
        self.assertTrue(
            re.search(r"ファイルパス[^\n]*構成データへ焼き込まない", self.text),
            "参照画像のパスを portability を壊す形で構成データへ書く余地がある",
        )


if __name__ == "__main__":
    unittest.main()

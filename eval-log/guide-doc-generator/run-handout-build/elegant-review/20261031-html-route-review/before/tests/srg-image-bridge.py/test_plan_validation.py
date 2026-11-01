"""SRG 受け入れ規約に対する事前検査 — algorithm 8 / AC-C21-8。

違反は exit 2 で止める。build-image-prompts.js 側も同じ検査で exit 1 になるが、
こちらで止めれば差し戻し先が handout の計画側だと分かる。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H
import _r23_support as R


class _Base(H.BridgeTestCase):
    def _run(self, tmp, sections, *, motifs=None, extra=(), plan_extra=None):
        tmp = Path(tmp)
        srg = H.make_srg(tmp, motifs=motifs)
        bin_dir = H.make_fake_bin(tmp)
        log = tmp / "log.jsonl"
        payload = H.plan_payload(sections=sections, **(plan_extra or {}))
        plan = H.write_plan(tmp / "plan.json", payload)
        proc = H.run(
            ["--image-plan", plan, "--assets-dir", H.make_assets_dir(tmp), "--srg-root", srg, *extra],
            env=H.clean_env(tmp, bin_dir=bin_dir, log=log),
        )
        return proc, log


class MotifVocabularyTest(_Base):
    """AC-C21-8: motifs[] は genome の motifs[].name の部分集合であること。"""

    def test_unknown_motif_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro", motifs=["no-such-motif"])])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_unknown_motif_is_not_folded_into_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro", motifs=["no-such-motif"])])
            self.assertNotIn("skipped", H.out_text(proc), "契約違反を skip へ畳んでいる")

    def test_unknown_motif_stops_before_delegating(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, log = self._run(tmp, [H.section("intro", motifs=["no-such-motif"])])
            self.assertEqual([], H.invoked_scripts(log), H.describe(proc))

    def test_known_motifs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            motifs = ["alpha-motif", "beta-motif"]
            proc, _ = self._run(tmp, [H.section("intro", motifs=motifs)], motifs=motifs)
            self.assertNotEqual(2, proc.returncode, H.describe(proc))

    def test_motif_vocabulary_comes_from_the_genome_file_not_from_the_script(self):
        """genome を差し替えれば通る motif が変わる (語彙を script へ焼かない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(
                tmp, [H.section("intro", motifs=["only-in-this-genome"])], motifs=["only-in-this-genome"]
            )
            self.assertNotEqual(2, proc.returncode, H.describe(proc))

    def test_one_bad_motif_among_good_ones_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            motifs = ["alpha-motif"]
            sections = [H.section("intro", motifs=motifs), H.section("build", motifs=["ghost"])]
            proc, _ = self._run(tmp, sections, motifs=motifs)
            self.assertEqual(2, proc.returncode, H.describe(proc))


class TextLengthTest(_Base):
    """algorithm 8 の下限: subject / diagramStructure 40 字、purpose / audienceTakeaway 12 字。"""

    def test_short_subject_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro", subject="A small diagram")])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_short_diagram_structure_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro", diagram_structure="Two boxes")])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_subject_of_exactly_40_chars_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro", subject="A" * 40)])
            self.assertNotEqual(2, proc.returncode, H.describe(proc))

    def test_short_goal_is_exit2(self):
        """purpose ← goal の写像 (12 字下限)。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro", goal="短い")])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_short_lead_line_is_exit2(self):
        """audienceTakeaway ← lead_line の写像 (12 字下限)。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro", lead_line="短い")])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_empty_overlay_text_entry_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro", overlay_text=[""])])
            self.assertEqual(2, proc.returncode, H.describe(proc))


class AmbiguousWordTest(_Base):
    """algorithm 8: 曖昧語を含む記述は受け付けない。"""

    def test_ambiguous_english_word_in_subject_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            subject = (
                "A beautiful high quality illustration of the build workflow that "
                "spans the whole width of the page"
            )
            proc, _ = self._run(tmp, [H.section("intro", subject=subject)])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_ambiguous_japanese_word_in_alt_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro", alt="おしゃれな図")])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_concrete_description_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run(tmp, [H.section("intro")])
            self.assertNotEqual(2, proc.returncode, H.describe(proc))


class NoFabricationTest(_Base):
    """algorithm 7: 日本語見出しから英文を捏造しない (C05 が書く値をそのまま使う)。"""

    def test_subject_is_carried_through_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            subject = (
                "A hand drawn panel showing a printer emitting a stapled handout while "
                "a reviewer marks the margin"
            )
            proc, _ = self._run(tmp, [H.section("intro", subject=subject)], extra=["--dry-run"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            deck = (Path(tmp) / "assets" / "srg-work" / "assets" / "generated" / "image-deck-plan.json")
            self.assertTrue(deck.is_file(), "image-deck-plan.json が無い:\n" + H.describe(proc))
            self.assertIn(subject, deck.read_text(encoding="utf-8"), "subject が写像されていない")

    def test_missing_subject_is_not_synthesised_from_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = H.section("intro")
            broken.pop("subject")
            proc, _ = self._run(tmp, [broken])
            self.assertEqual(2, proc.returncode, "見出しから subject を捏造している:\n" + H.describe(proc))


class DeckPlanShapeTest(_Base):
    """algorithm 6-7: 生成した image-deck-plan.json の形。"""

    def _deck(self, tmp):
        proc, _ = self._run(tmp, [H.section("intro"), H.section("build")], extra=["--dry-run"])
        deck_path = Path(tmp) / "assets" / "srg-work" / "assets" / "generated" / "image-deck-plan.json"
        if not deck_path.is_file():
            self.fail("image-deck-plan.json が無い:\n" + H.describe(proc))
        import json

        return json.loads(deck_path.read_text(encoding="utf-8")), proc

    def test_top_level_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, proc = self._deck(tmp)
            for key in ("styleGenome", "deck", "slides"):
                self.assertIn(key, deck, H.describe(proc))

    def test_one_section_becomes_one_slide(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, proc = self._deck(tmp)
            self.assertEqual(2, len(deck["slides"]), H.describe(proc))
            self.assertEqual(2, deck["deck"].get("totalSlides"), H.describe(proc))

    def test_pattern_and_text_policy_are_fixed(self):
        """pattern は image-only 固定。textPolicy の既定は RESOLUTION-R23 (a) が正本
        (`overlay-only` 固定は撤回され `baked-with-overlay` 既定になった)。"""
        with tempfile.TemporaryDirectory() as tmp:
            deck, proc = self._deck(tmp)
            for slide in deck["slides"]:
                self.assertEqual("image-only", slide.get("pattern"), H.describe(proc))
                self.assertEqual(R.DEFAULT_TEXT_POLICY, slide.get("textPolicy"), H.describe(proc))
                self.assertEqual("none", slide.get("backgroundSource"), H.describe(proc))

    def test_generation_block_is_fixed(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, proc = self._deck(tmp)
            for slide in deck["slides"]:
                generation = slide.get("generation") or {}
                self.assertEqual("high", generation.get("quality"), H.describe(proc))
                self.assertEqual("2560x1440", generation.get("size"), H.describe(proc))

    def test_slide_numbers_follow_section_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck, proc = self._deck(tmp)
            self.assertEqual(
                [H.expected_slug(1, "intro"), H.expected_slug(2, "build")],
                [slide.get("slug") for slide in deck["slides"]],
                H.describe(proc),
            )


if __name__ == "__main__":
    unittest.main()

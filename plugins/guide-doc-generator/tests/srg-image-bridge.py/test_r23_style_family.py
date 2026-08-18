"""RESOLUTION-R23 (c) — style family 2 系統と図解型からの全域写像。

固定する性質:
- 6 語の図解型に対する写像は全域であり、fallback を持たない。
- 図解型を持たないセクションは style_family の明示が必須 (既定へ落とさない)。
- 明示上書きが勝つ。allowlist は 2 語で閉じている。
- 2 family が混在する資料は family ごとに `--genome` を分けて委譲する
  (1 回の起動が受け取れる --genome は 1 つ)。
- handout 側 genome (`P05-x-04` の産出物) の欠落は skip ではなく exit2。

genome の**内容**はここに写さない。family → genome パスの対応は brief の
`image_style_families.families[].genome` から、motif 語彙は genome ファイルから読む。
"""

import os
import unittest
from pathlib import Path

import _harness as H
import _r23_support as R


def _flat_section(tc, section_id, pattern, *, index=0, **extra):
    """flat family のセクション。motif 名は handout 側 genome から引く (未存在なら fail)。"""
    genome = H.require_file(tc, H.handout_genome_path(), "P05-x-04")
    names = R.genome_motif_names(genome)
    if len(names) < 2:
        tc.fail("handout 側 genome の motifs[] が足りない: {}".format(genome))
    roles = {
        "platform": names[0],
        "primary": names[(index + 1) % len(names)],
        "props": [names[-1]],
    }
    return H.section(
        section_id,
        motifs=roles,
        diagram_pattern=pattern,
        adaptation_trace=[{"concept": "比較", "motif": roles["primary"]}],
        **extra,
    )


class HandoutGenomePresenceTest(H.BridgeTestCase):
    """handout 側 genome は plugin 同梱物である (producer: P05-x-04)。未存在なら赤。"""

    def test_handout_hosted_genome_file_exists(self):
        H.require_file(self, H.handout_genome_path(), "P05-x-04")

    def test_handout_genome_is_json_with_a_motif_vocabulary(self):
        genome = H.require_file(self, H.handout_genome_path(), "P05-x-04")
        names = R.genome_motif_names(genome)
        self.assertTrue(names, "genome に motifs[].name が無い: {}".format(genome))
        self.assertTrue(all(isinstance(n, str) and n for n in names), names)

    def test_handout_genome_declares_the_density_vocabulary(self):
        import json

        genome = H.require_file(self, H.handout_genome_path(), "P05-x-04")
        data = json.loads(genome.read_text(encoding="utf-8"))
        self.assertTrue(
            H.genome_density_levels(data),
            "genome に densityPreservation.densityLevels が無い: {}".format(genome),
        )

    def test_handout_genome_shares_the_schema_version_line_with_the_srg_genome(self):
        import json

        genome = H.require_file(self, H.handout_genome_path(), "P05-x-04")
        data = json.loads(genome.read_text(encoding="utf-8"))
        expected = str(H.real_genome_data().get("schemaVersion", "")).split(".")[:2]
        self.assertEqual(
            expected, str(data.get("schemaVersion", "")).split(".")[:2],
            "build-image-prompts.js が食える schemaVersion 系列でない",
        )

    def test_the_two_families_are_a_closed_allowlist(self):
        self.assertEqual(2, len(H.image_style_families()["families"]))

    def test_the_selection_map_is_total_over_the_patterns(self):
        """全域性は「定義域の要素数」ではなく「fallback を持たず値が全て埋まっている」で見る
        (図解型の本数は導出値であって契約ではない)。"""
        mapping = H.style_family_map()
        self.assertTrue(mapping, "写像が空")
        self.assertEqual(
            [], [k for k, v in mapping.items() if not v], "値の無い図解型がある"
        )
        self.assertEqual(
            [], [k for k in mapping if k.lower() in ("default", "fallback", "*", "_")],
            "写像が fallback を持っている (全域なら不要)",
        )
        self.assertEqual(
            set(H.image_style_families()["families"]), set(mapping.values()),
            "写像の値域が 2 family に閉じていない",
        )


class DeterministicSelectionTest(R.R23TestCase):
    """図解型 → family の写像どおりに genome が振り分けられる (AC-C21-15)。"""

    def _genome_names_of(self, ctx):
        return {Path(deck.get("styleGenome", "")).name for deck in self.decks(ctx)}

    def test_each_pattern_selects_the_mapped_family_genome(self):
        for pattern, family in sorted(H.style_family_map().items()):
            with self.subTest(pattern=pattern):
                with self.temp() as tmp:
                    if family == R.flat_family():
                        section = _flat_section(self, "sec", pattern)
                    else:
                        section = H.section("sec", diagram_pattern=pattern)
                    ctx = self.dry_run_plan(
                        tmp, [section], with_handout_genome=(family == R.flat_family())
                    )
                    expected = H.resolve_family_genome(
                        family, srg_root=ctx["srg"], hb_root=ctx["hb_root"]
                    )
                    self.assertEqual(
                        {expected.name}, self._genome_names_of(ctx),
                        "図解型 {} が {} の genome へ振られていない:\n{}".format(
                            pattern, family, H.describe(ctx["proc"])
                        ),
                    )

    def test_resolved_genome_is_passed_through_the_genome_flag(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, [H.section("intro")])
            expected = H.resolve_family_genome(
                R.iso_family(), srg_root=ctx["srg"], hb_root=ctx["hb_root"]
            )
            passed = [
                entry.get("flags", {}).get("genome")
                for entry in H.node_log(ctx["log"])
                if entry.get("script") == "build-image-prompts.js"
            ]
            self.assertTrue(passed, "build-image-prompts.js が起動していない:\n" + H.describe(ctx["proc"]))
            for value in passed:
                self.assertIsNotNone(value, "--genome が渡っていない")
                self.assertEqual(
                    os.path.realpath(str(expected)), os.path.realpath(str(value)),
                    "解決した genome と別のファイルを渡している",
                )

    def test_explicit_style_family_overrides_the_mapping(self):
        pattern = R.iso_patterns()[0]
        with self.temp() as tmp:
            section = _flat_section(self, "sec", pattern, style_family=R.flat_family())
            ctx = self.dry_run_plan(tmp, [section], with_handout_genome=True)
            expected = H.resolve_family_genome(
                R.flat_family(), srg_root=ctx["srg"], hb_root=ctx["hb_root"]
            )
            self.assertEqual({expected.name}, self._genome_names_of(ctx), H.describe(ctx["proc"]))

    def test_unknown_style_family_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", style_family="no-such-family")])
            self.assertExit2(ctx, "allowlist 外の style_family が通っている")

    def test_section_without_pattern_and_without_family_is_exit2(self):
        """E-IMG-FAMILY-MISSING: 既定へ落とさない。"""
        with self.temp() as tmp:
            section = H.section("intro")
            section.pop("diagram_pattern")
            ctx = self.run_plan(tmp, [section])
            self.assertExit2(ctx, "図解型も family も無いセクションが既定へ落ちている")

    def test_family_missing_stops_before_delegating(self):
        with self.temp() as tmp:
            section = H.section("intro")
            section.pop("diagram_pattern")
            ctx = self.run_plan(tmp, [section])
            self.assertStoppedBeforeDelegating(ctx)

    def test_section_without_pattern_but_with_explicit_family_is_accepted(self):
        with self.temp() as tmp:
            section = H.section("intro", style_family=R.iso_family())
            section.pop("diagram_pattern")
            ctx = self.dry_run_plan(tmp, [section])
            self.assertNotExit2(ctx, "family を明示したセクションが拒否されている")

    def test_unknown_diagram_pattern_is_exit2(self):
        """写像が全域なのは 6 語に対してであり、7 語目は入力として存在しない。"""
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", diagram_pattern="no-such-pattern")])
            self.assertExit2(ctx, "定義域外の図解型が通っている")


class MixedFamilyDelegationTest(R.R23TestCase):
    """2 family 混在は family ごとに build-image-prompts.js を起動する。"""

    def _sections(self):
        return [
            H.section("intro", diagram_pattern=R.iso_patterns()[0]),
            _flat_section(self, "compare", R.flat_patterns()[0], index=1),
        ]

    def test_prompt_builder_runs_once_per_family(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, self._sections(), with_handout_genome=True)
            builds = [s for s in H.invoked_scripts(ctx["log"]) if s == "build-image-prompts.js"]
            self.assertEqual(2, len(builds), "family ごとの起動になっていない:\n" + H.describe(ctx["proc"]))

    def test_each_invocation_uses_its_own_genome(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, self._sections(), with_handout_genome=True)
            passed = {
                os.path.realpath(str(entry.get("flags", {}).get("genome")))
                for entry in H.node_log(ctx["log"])
                if entry.get("script") == "build-image-prompts.js"
            }
            expected = {
                os.path.realpath(
                    str(H.resolve_family_genome(f, srg_root=ctx["srg"], hb_root=ctx["hb_root"]))
                )
                for f in (R.iso_family(), R.flat_family())
            }
            self.assertEqual(expected, passed, H.describe(ctx["proc"]))

    def test_slugs_are_unchanged_by_the_family_split(self):
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, self._sections(), with_handout_genome=True)
            slugs = sorted(slide.get("slug") for _, slide in self.slides(ctx))
            self.assertEqual(
                sorted([H.expected_slug(1, "intro"), H.expected_slug(2, "compare")]), slugs,
                H.describe(ctx["proc"]),
            )


class HandoutGenomeIsFailClosedTest(R.R23TestCase):
    """algorithm 3b: 同梱すべき genome の欠落は skip ではなく exit2。"""

    def test_flat_section_without_the_bundled_genome_is_exit2(self):
        with self.temp() as tmp:
            section = H.section("only", diagram_pattern=R.flat_patterns()[0])
            ctx = self.run_plan(tmp, [section], with_handout_genome=False)
            self.assertExit2(ctx, "handout 側 genome 欠落が exit2 になっていない")

    def test_missing_bundled_genome_is_not_reported_as_skip(self):
        with self.temp() as tmp:
            section = H.section("only", diagram_pattern=R.flat_patterns()[0])
            ctx = self.run_plan(tmp, [section], with_handout_genome=False)
            self.assertNotIn(
                "srg-absent", H.out_text(ctx["proc"]),
                "同梱漏れを環境不在の skip へ畳んでいる:\n" + H.describe(ctx["proc"]),
            )

    def test_iso_only_plan_does_not_require_the_flat_genome(self):
        """使わない family の genome 不在は阻害要因にならない (解決は使うときだけ)。"""
        with self.temp() as tmp:
            ctx = self.dry_run_plan(
                tmp,
                [H.section("intro", diagram_pattern=R.iso_patterns()[0])],
                with_handout_genome=False,
            )
            self.assertNotExit2(ctx, "使っていない family の genome 不在で落ちている")


if __name__ == "__main__":
    unittest.main()

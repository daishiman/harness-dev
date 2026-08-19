"""RESOLUTION-R23 (d)(e) — 平坦化退化の代理指標とセクション別適応の機械化。

(d) 採用した代理指標は 4 件だけで、画素判定を持ち込まない。
    1. density_level 必須 (値域の正本は genome の densityLevels)
    2. motifs は {platform, primary, props[]} の 3 役構造体 (空の平坦図を書けなくする)
    3. adaptation_trace 必須 (根拠なき motif 選定を落とす)
    4. 回収後の meta 照合 (exit code は変えず、開示する)
(e) セクションが 2 件以上で (図解型, motifs.primary) が全件同一なら exit2。閾値は置かない。

退けた検査 (画素解析 / diagramPrimitives 非空) を後から足し戻していないことも固定する。
"""

import re
import unittest
from pathlib import Path

import _harness as H
import _r23_support as R


class MotifRoleStructureTest(R.R23TestCase):
    """(d) 2: 平坦な配列は受け付けない。3 役が揃い props が 1 件以上。"""

    def test_flat_motif_array_is_exit2(self):
        with self.temp() as tmp:
            section = H.section("intro")
            section["motifs"] = list(H.default_motifs())
            ctx = self.run_plan(tmp, [section])
            self.assertExit2(ctx, "平坦な motifs 配列が通っている (3 役構造体が要件)")

    def test_missing_platform_is_exit2(self):
        with self.temp() as tmp:
            section = H.section("intro")
            section["motifs"] = {k: v for k, v in section["motifs"].items() if k != "platform"}
            ctx = self.run_plan(tmp, [section])
            self.assertExit2(ctx, "platform 欠落が通っている")

    def test_missing_primary_is_exit2(self):
        with self.temp() as tmp:
            section = H.section("intro")
            section["motifs"] = {k: v for k, v in section["motifs"].items() if k != "primary"}
            ctx = self.run_plan(tmp, [section])
            self.assertExit2(ctx, "primary 欠落が通っている")

    def test_empty_props_is_exit2(self):
        """richnessFloor: 小物 1 点以上。空の角丸枠 + テキストだけを書けなくする。"""
        with self.temp() as tmp:
            section = H.section("intro")
            section["motifs"] = dict(section["motifs"], props=[])
            ctx = self.run_plan(tmp, [section])
            self.assertExit2(ctx, "props 空が通っている")

    def test_props_must_be_a_list(self):
        with self.temp() as tmp:
            section = H.section("intro")
            section["motifs"] = dict(section["motifs"], props=H.default_motifs()[0])
            ctx = self.run_plan(tmp, [section])
            self.assertExit2(ctx, "props が単一名でも通っている")

    def test_unknown_name_in_any_role_is_exit2(self):
        for role in ("platform", "primary", "props"):
            with self.subTest(role=role):
                with self.temp() as tmp:
                    section = H.section("intro")
                    roles = dict(section["motifs"])
                    roles[role] = ["no-such-motif"] if role == "props" else "no-such-motif"
                    section["motifs"] = roles
                    ctx = self.run_plan(tmp, [section])
                    self.assertExit2(ctx, "{} が genome 語彙外でも通っている".format(role))

    def test_roles_are_concatenated_for_the_delegate(self):
        """委譲先の入力契約は文字列配列のまま (platform → primary → props の順)。"""
        with self.temp() as tmp:
            section = H.section("intro")
            ctx = self.dry_run_plan(tmp, [section, H.section("build")])
            expected = None
            for _, slide in self.slides(ctx):
                if slide.get("slug") == H.expected_slug(1, "intro"):
                    expected = slide.get("motifs")
            plan_roles = H.plan_payload(sections=[section, H.section("build")])["sections"][0]["motifs"]
            self.assertEqual(
                [plan_roles["platform"], plan_roles["primary"], *plan_roles["props"]], expected,
                "3 役の連結順が違う:\n" + H.describe(ctx["proc"]),
            )


class DensityLevelTest(R.R23TestCase):
    """(d) 1: 値域の正本は genome。script が 3 語を自前で列挙しない。"""

    def test_missing_density_level_is_exit2(self):
        with self.temp() as tmp:
            section = H.section("intro")
            section.pop("density_level")
            ctx = self.run_plan(tmp, [section])
            self.assertExit2(ctx, "density_level 欠落が通っている")

    def test_out_of_vocabulary_density_level_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", density_level="ultra")])
            self.assertExit2(ctx, "値域外の density_level が通っている")

    def test_every_level_declared_by_the_genome_is_accepted(self):
        for level in H.genome_density_levels():
            with self.subTest(level=level):
                with self.temp() as tmp:
                    ctx = self.dry_run_plan(tmp, [H.section("intro", density_level=level)])
                    self.assertNotExit2(ctx, "genome が宣言する密度 {} が拒否されている".format(level))

    def test_density_level_reaches_the_delegate(self):
        level = H.genome_density_levels()[-1]
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, [H.section("intro", density_level=level)])
            for _, slide in self.slides(ctx):
                self.assertEqual(level, slide.get("densityLevel"), H.describe(ctx["proc"]))


class AdaptationTraceTest(R.R23TestCase):
    """(d) 3: 主題語 → 選択 motif の対応を必須にする。"""

    def test_missing_adaptation_trace_is_exit2(self):
        with self.temp() as tmp:
            section = H.section("intro")
            section.pop("adaptation_trace")
            ctx = self.run_plan(tmp, [section])
            self.assertExit2(ctx, "adaptation_trace 欠落が通っている")

    def test_empty_adaptation_trace_is_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [H.section("intro", adaptation_trace=[])])
            self.assertExit2(ctx, "空の adaptation_trace が通っている")

    def test_trace_motif_outside_the_three_roles_is_exit2(self):
        """根拠なき motif 選定 = 3 役のどれとも一致しない対応。"""
        with self.temp() as tmp:
            other = H.default_motifs()[1]
            section = H.section(
                "intro",
                motifs={"platform": H.default_motifs()[0], "primary": H.default_motifs()[0],
                        "props": [H.default_motifs()[0]]},
                adaptation_trace=[{"concept": "流れ", "motif": other}],
            )
            ctx = self.run_plan(tmp, [section])
            self.assertExit2(ctx, "3 役に無い motif を指す trace が通っている")


class UniformCompositionTest(R.R23TestCase):
    """(e) セクション 2 件以上で (図解型, motifs.primary) が全件同一なら exit2。"""

    def _same(self, section_id):
        names = H.default_motifs()
        roles = {"platform": names[0], "primary": names[-1], "props": [names[0]]}
        return H.section(
            section_id,
            motifs=roles,
            diagram_pattern=R.iso_patterns()[0],
            adaptation_trace=[{"concept": "流れ", "motif": roles["primary"]}],
        )

    def test_two_identical_sections_are_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [self._same("intro"), self._same("build")])
            self.assertExit2(ctx, "全セクション同一構図が通っている")

    def test_three_identical_sections_are_exit2(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [self._same("a"), self._same("b"), self._same("c")])
            self.assertExit2(ctx, "全セクション同一構図が通っている")

    def test_uniform_composition_stops_before_delegating(self):
        with self.temp() as tmp:
            ctx = self.run_plan(tmp, [self._same("intro"), self._same("build")])
            self.assertStoppedBeforeDelegating(ctx)

    def test_single_section_document_is_not_uniform(self):
        """1 件しかない資料に『全件同一』は適用しない。"""
        with self.temp() as tmp:
            ctx = self.dry_run_plan(tmp, [self._same("only")])
            self.assertNotExit2(ctx, "単一セクションが退化として落ちている")

    def test_differing_primary_alone_is_enough(self):
        with self.temp() as tmp:
            second = self._same("build")
            roles = dict(second["motifs"], primary=H.default_motifs()[0])
            second["motifs"] = roles
            second["adaptation_trace"] = [{"concept": "流れ", "motif": roles["primary"]}]
            ctx = self.dry_run_plan(tmp, [self._same("intro"), second])
            self.assertNotExit2(ctx, "primary が違うのに退化と判定されている")

    def test_differing_pattern_alone_is_enough(self):
        with self.temp() as tmp:
            second = self._same("build")
            second["diagram_pattern"] = R.iso_patterns()[1]
            ctx = self.dry_run_plan(tmp, [self._same("intro"), second])
            self.assertNotExit2(ctx, "図解型が違うのに退化と判定されている")

    def test_shared_props_are_allowed(self):
        """props の重複は許す (小物は一貫性のために再利用される)。"""
        with self.temp() as tmp:
            first = self._same("intro")
            second = self._same("build")
            roles = dict(second["motifs"], primary=H.default_motifs()[0])
            second["motifs"] = roles
            second["adaptation_trace"] = [{"concept": "流れ", "motif": roles["primary"]}]
            self.assertEqual(first["motifs"]["props"], second["motifs"]["props"])
            ctx = self.dry_run_plan(tmp, [first, second])
            self.assertNotExit2(ctx, "props の重複だけで退化と判定されている")


class MetaDriftDisclosureTest(R.R23TestCase):
    """(d) 4: 回収後の meta 照合は exit code を変えず、必ず開示する。"""

    def _run_real(self, tmp, meta_mode):
        return self.run_plan(
            tmp, [H.section("intro"), H.section("build")], env_extra={H.ENV_META: meta_mode}
        )

    def test_faithful_meta_is_exit0_without_drift(self):
        with self.temp() as tmp:
            ctx = self._run_real(tmp, "faithful")
            self.assertEqual(0, ctx["proc"].returncode, H.describe(ctx["proc"]))
            for entry in H.stdout_json(self, ctx["proc"])["images"]:
                self.assertFalse(entry.get("meta_drift"), entry)

    def test_drifted_meta_is_disclosed_per_image(self):
        with self.temp() as tmp:
            ctx = self._run_real(tmp, "drift")
            drifted = [
                entry for entry in H.stdout_json(self, ctx["proc"])["images"]
                if entry.get("meta_drift")
            ]
            self.assertTrue(drifted, "meta の不一致が開示されていない:\n" + H.describe(ctx["proc"]))

    def test_drifted_meta_does_not_change_the_exit_code(self):
        with self.temp() as tmp:
            ctx = self._run_real(tmp, "drift")
            self.assertEqual(0, ctx["proc"].returncode, "meta 不一致で出荷を止めている")

    def test_drifted_meta_warns_on_stderr(self):
        with self.temp() as tmp:
            ctx = self._run_real(tmp, "drift")
            self.assertTrue(H.err_text(ctx["proc"]).strip(), "meta 不一致について黙っている")

    def test_dropped_meta_fields_are_disclosed_too(self):
        """委譲先が値を落とした状態 = プロンプトに密度指示が乗っていない証拠。"""
        with self.temp() as tmp:
            ctx = self._run_real(tmp, "drop")
            drifted = [
                entry for entry in H.stdout_json(self, ctx["proc"])["images"]
                if entry.get("meta_drift")
            ]
            self.assertTrue(drifted, "meta の欠落が開示されていない:\n" + H.describe(ctx["proc"]))


class RejectedChecksStayRejectedTest(H.BridgeTestCase):
    """裁定が退けた検査を後から足し戻していないこと (AC-C21-17)。"""

    def setUp(self):
        super().setUp()
        self.source = H.read_source(self)

    def test_no_pixel_analysis_library(self):
        for token in ("PIL", "Pillow", "numpy", "cv2", "Image.open", "imghdr"):
            self.assertNotIn(token, self.source, "画素解析へ踏み込んでいる: {}".format(token))

    def test_no_diagram_primitives_requirement(self):
        self.assertNotIn(
            "diagramPrimitives", self.source,
            "実在しないフィールドの検査を持ち込んでいる (why_not_diagram_primitives)",
        )

    def test_density_vocabulary_is_not_hard_coded(self):
        """AC-C21-17: 密度語彙は genome から読む。script が自前で列挙しない。"""
        for level in H.genome_density_levels():
            self.assertIsNone(
                re.search(r"""["']{}["']""".format(re.escape(level)), self.source),
                "密度語彙 {} をハードコードしている".format(level),
            )

    def test_motif_names_are_not_hard_coded(self):
        for name in H.real_genome_motifs():
            self.assertNotIn(name, self.source, "motif 名 {} をハードコードしている".format(name))

    def test_layout_template_names_are_not_hard_coded(self):
        layout = H.find_key(H.real_genome_data(), "layoutSelectionByStructure") or {}
        self.assertTrue(layout, "実 genome に layoutSelectionByStructure が無い")
        for key in layout:
            self.assertIsNone(
                re.search(r"""["']{}["']""".format(re.escape(key)), self.source),
                "layoutTemplate 名 {} をハードコードしている".format(key),
            )

    def test_no_threshold_for_composition_diversity(self):
        """(e) は割合の閾値を持たない。閾値は Goodhart 化する。"""
        checks = H.brief()["degradation_proxy_checks"]["uniform_composition_ban"]
        self.assertIn("why_no_threshold", checks)
        self.assertNotIn("threshold", str(checks["rule"]).lower())


class GenomeIsNotCopiedIntoTestsTest(unittest.TestCase):
    """テスト側が genome の内容を写していないこと (正本の二重化防止)。"""

    def test_tests_do_not_embed_genome_motif_names(self):
        names = set(H.real_genome_motifs())
        for path in sorted(Path(H.TESTS_DIR).glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for name in names:
                self.assertNotIn(
                    name, text, "{} が genome の motif 名 {} を写している".format(path.name, name)
                )

    def test_tests_do_not_embed_density_vocabulary(self):
        """密度語彙は一般名詞と衝突する (画像生成 quality にも同じ語がある) ため、
        密度を主題にしている R23 側のファイルに限って写しを禁じる。"""
        for path in sorted(Path(H.TESTS_DIR).glob("*r23*.py")):
            text = path.read_text(encoding="utf-8")
            for level in H.genome_density_levels():
                self.assertIsNone(
                    re.search(r"""["']{}["']""".format(re.escape(level)), text),
                    "{} が密度語彙 {} を写している".format(path.name, level),
                )


if __name__ == "__main__":
    unittest.main()

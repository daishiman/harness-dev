"""R20 の不変条件 — プリセット間の差分はセクションの並びと推奨部品に限られる (C44)。

共有の型 (sticky 目次 / 日付表記 / 目的・背景・ゴール / 抽象↔具体の往復 / アイコン規約 /
単一ファイル自己完結) は preset から触れる経路を持たない。これを「文言で確かめる」のではなく
「preset に到達できるキーが閉じた allowlist に限られる」というデータ形で固定する。

P04-x-05 裁定 A: 保証の内容は allowlist が閉じていることであって鍵面の個数ではない。
個数は allowlist からの導出値なので、期待値も _harness.ALLOWED_PRESET_KEYS から導き
数値リテラルで固定しない (導出値を写すと、無害なキー追加が保証違反に見える)。
"""

import json
import unittest

import _harness as H

# preset から触れてはならない不変項を示唆するキー断片 (C44)。
INVARIANT_KEY_FRAGMENTS = (
    "nav",
    "sticky",
    "date",
    "icon",
    "emoji",
    "theme",
    "font",
    "css",
    "template",
    "self_contained",
    "selfcontained",
    "print",
    "memo",
    "localstorage",
    "a11y",
    "goal_block",
)


class PresetKeySurfaceTest(unittest.TestCase):
    """catalog 実データに対する検査 (script より前段の契約)。"""

    def test_preset_keys_are_within_the_allowlist(self):
        """許可キー集合が閉じていること (裁定 A。個数は導出値なので数えない)。"""
        for slug, preset in H.presets(self).items():
            with self.subTest(slug=slug):
                extra = set(preset.keys()) - H.ALLOWED_PRESET_KEYS
                self.assertEqual(
                    set(), extra,
                    "allowlist 外のキーがある: {} (allowlist={})".format(
                        sorted(extra), sorted(H.ALLOWED_PRESET_KEYS)
                    ),
                )

    def test_every_preset_has_the_required_keys(self):
        """必須キーの欠落も allowlist と同じ検査面で落とす (裁定 C: fallback を置かない)。"""
        for slug, preset in H.presets(self).items():
            with self.subTest(slug=slug):
                missing = H.REQUIRED_PRESET_KEYS - set(preset.keys())
                self.assertEqual(
                    set(), missing, "必須キーが欠けている: {}".format(sorted(missing))
                )

    def test_no_preset_key_touches_invariants(self):
        for slug, preset in H.presets(self).items():
            for key in preset.keys():
                lowered = key.lower()
                for fragment in INVARIANT_KEY_FRAGMENTS:
                    with self.subTest(slug=slug, key=key, fragment=fragment):
                        self.assertNotIn(fragment, lowered, "不変項へ到達しうるキー名")

    def test_section_entry_keys_are_fixed(self):
        """section の形も固定。

        image_role は利用者要求 R8 (図解と画像を毎回セクションごとに必ず)
        で加わった 6 番目のキーで、『どの役の画像を置く節か』を骨格の時点で
        宣言させる。ここは形の固定 (増えても減ってもいない) だけを見る。値域と
        宣言漏れの扱いは test_image_role.py が持つ。
        """
        expected = {"id", "heading", "section_kind", "recommended_parts", "required",
                    "image_role"}
        for slug, preset in H.presets(self).items():
            for section in preset["section_order"]:
                with self.subTest(slug=slug, section=section.get("id")):
                    self.assertEqual(expected, set(section.keys()))

    def test_every_preset_has_section_order_and_parts(self):
        for slug, preset in H.presets(self).items():
            with self.subTest(slug=slug):
                self.assertGreaterEqual(len(preset["section_order"]), 1)
                self.assertIsInstance(preset["recommended_parts"], list)


class PresetCliSurfaceTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_cli_output_exposes_only_variant_fields_per_preset(self):
        """用途間で異なりうるのは section_order / recommended_parts / notes /
        required_document_fields / presentation_order と語彙属性だけ。"""
        allowed_top_level = {
            "purpose",
            "label_ja",
            "dir_token",
            "section_order",
            "recommended_parts",
            "notes",
            "required_document_fields",
            "presentation_order",
            "granularity_defaults",  # 裁定 A・C: --purpose 出力へ常に含まれる
            "applied_variant",
            "catalog_sha256",
        }
        for slug in H.slugs(self):
            with self.subTest(slug=slug):
                proc = H.run(["--purpose", slug])
                self.assertEqual(0, proc.returncode, H.describe(proc))
                payload = json.loads(H.out_text(proc))
                extra = set(payload.keys()) - allowed_top_level
                self.assertEqual(set(), extra, "用途固有の出力キーが増えている: {}".format(sorted(extra)))

    def test_section_kinds_are_all_known_to_c12_catalog(self):
        """全プリセットの section_kind が中立データファイルの語彙に収まる。"""
        sections = json.loads(H.require_file(self, H.SECTIONS_FILE, "C12").read_text(encoding="utf-8"))
        known = {k["slug"] for k in sections["section_kinds"]}
        for slug in H.slugs(self):
            proc = H.run(["--purpose", slug])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            for section in json.loads(H.out_text(proc))["section_order"]:
                with self.subTest(slug=slug, section=section["id"]):
                    self.assertIn(section["section_kind"], known)

    def test_recommended_parts_are_in_section_scope(self):
        """推奨部品は必ず section_scope=in-section の id (値域の正本は C11 の部品カタログ)。"""
        parts = json.loads(H.require_file(self, H.PARTS_FILE, "C11").read_text(encoding="utf-8"))
        in_section = {p["id"] for p in parts["parts"] if p.get("section_scope") == "in-section"}
        for slug in H.slugs(self):
            proc = H.run(["--purpose", slug])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            payload = json.loads(H.out_text(proc))
            for section in payload["section_order"]:
                for part_id in section["recommended_parts"]:
                    with self.subTest(slug=slug, part=part_id):
                        self.assertIn(part_id, in_section)


if __name__ == "__main__":
    unittest.main()

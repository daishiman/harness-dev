"""IMG の役の宣言と値域 (P05-x-36 / 利用者要求 R8)。

「図解と画像を毎回セクションごとに必ず追加する」を成り立たせる部品は 2 つある。
C12 側の per-section ゲート (W-DIAGRAM-FEW / E-IMAGE-ABSENT) が『無い』を落とし、
preset 側の image_role が『どちらの役の画像を置く節か』を骨格の時点で宣言する。
後者は診断コードが定義されているだけで受入テストが 1 本も無かったため、ここで固定する。

役の値域の正本は
config/handout-visual-policy.json#thresholds.min_images_per_main_section.role_split.roles
であり、本 script はその写しを持たない (控えは正本を読めない経路のためだけにあり、
出荷中の正本とずれたまま出荷できないことを最後のクラスが押さえる)。
"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


def canon_roles():
    policy = json.loads(H.VISUAL_POLICY_FILE.read_text(encoding="utf-8"))
    split = policy["thresholds"]["min_images_per_main_section"]["role_split"]
    return [entry["role"] for entry in split["roles"]]


class ImageRoleTestBase(unittest.TestCase):
    def setUp(self):
        H.require_script(self)
        H.require_file(self, H.VISUAL_POLICY_FILE, "C12 (視覚方針正本)")
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _root(self, mutate=None, **opts) -> Path:
        return H.make_fixture_root(self, self.tmp, mutate, **opts)

    def assert_data_violation(self, proc, code):
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertIn(code, H.err_text(proc), H.describe(proc))

    @staticmethod
    def first_section(catalog):
        slug = catalog["vocabulary"][0]["slug"]
        return catalog["presets"][slug]["section_order"][0]


class ShippedPresetsDeclareTheRole(ImageRoleTestBase):
    """出荷中の骨格が、どの節にどの役の画像を置くかを宣言し切っていること。"""

    def test_clean_root_passes(self):
        proc = H.run_in_root(self._root(), ["--list", "--format", "text"])
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_every_section_of_every_preset_declares_an_image_role(self):
        catalog = H.load_catalog(self)
        allowed = set(canon_roles())
        for slug, preset in catalog["presets"].items():
            for index, section in enumerate(preset["section_order"]):
                self.assertIn(
                    "image_role", section,
                    "%s/section_order[%d] が image_role を宣言していない" % (slug, index))
                self.assertIn(
                    section["image_role"], allowed,
                    "%s/section_order[%d] の image_role が正本の値域外" % (slug, index))


class MissingRoleIsRejected(ImageRoleTestBase):
    """宣言漏れは『キー面が違う』へ混ぜず、直せる 1 事実として名指しする。"""

    def test_dropping_the_role_fails(self):
        def mutate(catalog):
            self.first_section(catalog).pop("image_role")

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, "E-PRESET-IMAGE-ROLE-MISSING")

    def test_the_generic_shape_error_is_not_used_for_a_missing_role(self):
        """欠落 1 件を preset 全体の形の崩れと同じ診断にしない。"""
        def mutate(catalog):
            self.first_section(catalog).pop("image_role")

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assertNotIn("E-CATALOG-MALFORMED", H.err_text(proc), H.describe(proc))

    def test_the_diagnostic_names_the_allowed_roles(self):
        def mutate(catalog):
            self.first_section(catalog).pop("image_role")

        proc = H.run_in_root(self._root(mutate), ["--list"])
        for role in canon_roles():
            self.assertIn(role, H.err_text(proc), H.describe(proc))

    def test_a_missing_role_stops_a_resolvable_purpose_too(self):
        """骨格が壊れている間は、別の解決可能な用途も通さない。"""
        def mutate(catalog):
            self.first_section(catalog).pop("image_role")

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.slugs(self)[-1]])
        self.assert_data_violation(proc, "E-PRESET-IMAGE-ROLE-MISSING")


class UnknownRoleIsRejected(ImageRoleTestBase):

    def test_a_role_outside_the_canon_fails(self):
        def mutate(catalog):
            self.first_section(catalog)["image_role"] = "diagram"

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, "E-PRESET-IMAGE-ROLE-UNKNOWN")

    def test_the_diagnostic_shows_the_offending_value(self):
        def mutate(catalog):
            self.first_section(catalog)["image_role"] = "diagram"

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assertIn("diagram", H.err_text(proc), H.describe(proc))

    def test_an_empty_role_is_not_treated_as_a_declaration(self):
        def mutate(catalog):
            self.first_section(catalog)["image_role"] = ""

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, "E-PRESET-IMAGE-ROLE-UNKNOWN")


class TheValueDomainComesFromTheCanon(ImageRoleTestBase):
    """値域の出所が正本であって script の定数でないこと。"""

    def test_a_role_added_to_the_canon_becomes_acceptable(self):
        """正本へ役を足せば、script を触らずに preset がその役を使える。"""
        def mutate_policy(policy):
            (policy["thresholds"]["min_images_per_main_section"]["role_split"]["roles"]
             .append({"role": "diagram", "use": "対照用", "source": "対照用"}))

        def mutate(catalog):
            self.first_section(catalog)["image_role"] = "diagram"

        root = self._root(mutate, mutate_policy=mutate_policy)
        proc = H.run_in_root(root, ["--list"])
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_a_role_removed_from_the_canon_stops_being_acceptable(self):
        """逆向きの対照。正本から外した役は、出荷中の骨格が使っていても落ちる。"""
        dropped = canon_roles()[-1]

        def mutate_policy(policy):
            split = policy["thresholds"]["min_images_per_main_section"]["role_split"]
            split["roles"] = [e for e in split["roles"] if e["role"] != dropped]

        def mutate(catalog):
            self.first_section(catalog)["image_role"] = dropped

        root = self._root(mutate, mutate_policy=mutate_policy)
        proc = H.run_in_root(root, ["--list"])
        self.assert_data_violation(proc, "E-PRESET-IMAGE-ROLE-UNKNOWN")

    def test_the_script_does_not_carry_the_canon_as_its_own_domain(self):
        """控えが実質の正本になっていないこと (名前で用途を分ける)。"""
        source = H.SCRIPT.read_text(encoding="utf-8")
        self.assertIn("FALLBACK_IMAGE_ROLES", source)
        self.assertNotIn("IMAGE_ROLE_VALUES", source)


class FallbackMirrorsTheShippedCanon(ImageRoleTestBase):
    """正本が読めない経路でも検査が消えず、控えがずれたまま出荷できないこと。"""

    def test_the_check_survives_a_missing_canon(self):
        def mutate(catalog):
            self.first_section(catalog)["image_role"] = "diagram"

        root = self._root(mutate, omit_policy=True)
        proc = H.run_in_root(root, ["--list"])
        self.assert_data_violation(proc, "E-PRESET-IMAGE-ROLE-UNKNOWN")

    def test_a_broken_canon_does_not_crash_the_resolver(self):
        def mutate_policy(policy):
            policy["thresholds"]["min_images_per_main_section"]["role_split"] = "壊れた形"

        root = self._root(mutate_policy=mutate_policy)
        proc = H.run_in_root(root, ["--list", "--format", "text"])
        self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_the_fallback_equals_the_shipped_canon(self):
        source = H.SCRIPT.read_text(encoding="utf-8")
        line = next(l for l in source.splitlines() if l.startswith("FALLBACK_IMAGE_ROLES"))
        for role in canon_roles():
            self.assertIn(role, line, "控えが出荷中の正本とずれている")
        self.assertEqual(2 * len(canon_roles()), line.count('"'), "控えの件数が正本と違う")


if __name__ == "__main__":
    unittest.main()

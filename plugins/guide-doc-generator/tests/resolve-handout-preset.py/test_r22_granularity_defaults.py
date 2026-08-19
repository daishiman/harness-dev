"""R22 C61 (既定値側) — C23 granularity_defaults。

出所は script-brief-C23.json granularity_defaults と briefs/RESOLUTION-R22.md。
C23 は doc_type ごとの既定値の単一正本であり、直交性と上書き規則
(CR-GRANULARITY-ORTHOGONAL / CR-GRANULARITY-PRESET-DEFAULT-ONLY) の正本は C12 側。
したがってここで検査するのは「既定値が doc_type から引けること」と
「既定値が制約になっていないこと」の 2 点だけ。

P04-x-05 裁定 A・C により格納形が確定した:
- `granularity_defaults` は preset オブジェクトの 6 番目の許可キーであり、
  **全 preset の必須キー**。値のキー集合は厳密に {detail_level, evidence_depth}。
- 中央表を preset の外側へ別置きしない (ブリーフの `granularity_defaults.defaults` は
  説明用の写しであって第 2 の格納先ではない)。
- 実行時の fallback 既定は置かない。欠落は catalog 検査 (手順 4(j)) で
  `E-PRESET-GRANULARITY-MISSING` として落ちる。手順 4(f) の presets↔vocabulary
  完全一致と合わせ、全 8 語彙の被覆が構造から出る。
- 到達経路はモジュール API `granularity_defaults(catalog, purpose)` で、
  `None` を返す経路も fallback も持たない (未定義語彙のみ UnknownPurposeError)。
経緯は R22-AMENDMENT.md と briefs/RESOLUTION-P04-x-05.md の裁定 A / C を参照。
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import _harness as H

# RESOLUTION-R22.md 設計判断 1 の値域
DETAIL_LEVELS = ("overview", "standard", "detailed")
EVIDENCE_DEPTHS = ("none", "cited", "sourced")

# 値のキー集合の正本は _harness (裁定 A・C / algorithm 4(j))。ここで二重に列挙しない。
GRANULARITY_KEYS = tuple(sorted(H.GRANULARITY_DEFAULT_KEYS))

# 手順 4(j) の診断コード (script-brief-C23.json stderr)
E_MISSING = "E-PRESET-GRANULARITY-MISSING"
E_KEYS = "E-PRESET-GRANULARITY-KEYS"
E_VALUE = "E-PRESET-GRANULARITY-VALUE"

C23_BRIEF = H.REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs" / "script-brief-C23.json"


def brief_defaults(tc):
    """doc_type -> {detail_level, evidence_depth} (期待値の正本)。"""
    if not C23_BRIEF.is_file():
        tc.fail("既定値の正本が読めない: {}".format(C23_BRIEF))
    data = json.loads(C23_BRIEF.read_text(encoding="utf-8"))
    presets = data.get("preset_definitions")
    if not isinstance(presets, list) or not presets:
        tc.fail("script-brief-C23.json に preset_definitions が無い")
    out = {}
    for entry in presets:
        slug = entry.get("purpose")
        gd = entry.get("granularity_defaults")
        if not isinstance(gd, dict):
            tc.fail(
                "preset_definitions[{}] に granularity_defaults が無い "
                "(裁定 C: 全 preset の必須キー)".format(slug)
            )
        out[slug] = {k: gd.get(k) for k in GRANULARITY_KEYS}
    return out


def brief_defaults_table(tc):
    """granularity_defaults.defaults (説明用の写し) を読む。

    裁定 C により実データの正本は preset_definitions[].granularity_defaults 1 箇所で、
    この表はその写しである。写しが正本とずれていないことを別に固定する
    (ずれを許すと、写しの側が第 2 の正本として振る舞い始める)。
    """
    if not C23_BRIEF.is_file():
        tc.fail("既定値の正本が読めない: {}".format(C23_BRIEF))
    data = json.loads(C23_BRIEF.read_text(encoding="utf-8"))
    defaults = (data.get("granularity_defaults") or {}).get("defaults")
    if not isinstance(defaults, dict) or not defaults:
        tc.fail("script-brief-C23.json に granularity_defaults.defaults が無い")
    return {
        slug: {k: entry.get(k) for k in GRANULARITY_KEYS}
        for slug, entry in defaults.items()
    }


def load_module(tc):
    H.require_script(tc)
    spec = importlib.util.spec_from_file_location("hb_preset", H.SCRIPT)
    if spec is None or spec.loader is None:
        tc.fail("importlib でモジュールとして読み込めない: {}".format(H.SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GranularityDefaultsApiTest(unittest.TestCase):
    """C61: C12 --normalize が doc_type から既定値を引く経路。"""

    def setUp(self):
        self.module = load_module(self)
        self.catalog = self.module.load_catalog()

    def _defaults(self, slug):
        fn = getattr(self.module, "granularity_defaults", None)
        if not callable(fn):
            self.fail(
                "公開 API に granularity_defaults(catalog, purpose) が無い "
                "(C12 は既定値の対応表を持てないため、この経路以外に到達手段が無い)"
            )
        return fn(self.catalog, slug)

    def test_public_symbol_exists(self):
        self.assertTrue(
            callable(getattr(self.module, "granularity_defaults", None)),
            "granularity_defaults が公開 API に無い",
        )

    def test_defaults_match_the_brief_for_every_declared_doc_type(self):
        for slug, expected in brief_defaults(self).items():
            with self.subTest(purpose=slug):
                self.assertEqual(expected, dict(self._defaults(slug)))

    def test_every_vocabulary_slug_has_defaults(self):
        """語彙 8 件すべてに既定値がある (片側更新で未被覆を作らない)。"""
        for slug in H.slugs(self):
            with self.subTest(purpose=slug):
                got = self._defaults(slug)
                self.assertIsInstance(got, dict, "既定値が dict でない: {!r}".format(got))
                self.assertEqual(set(GRANULARITY_KEYS), set(got.keys()))

    def test_values_are_within_the_enums(self):
        for slug in H.slugs(self):
            got = self._defaults(slug)
            with self.subTest(purpose=slug):
                self.assertIn(got.get("detail_level"), DETAIL_LEVELS)
                self.assertIn(got.get("evidence_depth"), EVIDENCE_DEPTHS)

    def test_alias_resolves_to_the_same_defaults(self):
        entry = next(e for e in H.vocabulary_entries(self) if e["aliases"])
        resolved = self.module.resolve(self.catalog, entry["aliases"][0])["slug"]
        self.assertEqual(self._defaults(entry["slug"]), self._defaults(resolved))

    def test_unknown_purpose_raises(self):
        fn = getattr(self.module, "granularity_defaults", None)
        if not callable(fn):
            self.fail("公開 API に granularity_defaults が無い")
        with self.assertRaises(self.module.UnknownPurposeError):
            fn(self.catalog, "zzz-not-a-purpose")


class GranularityDefaultsAreNotConstraintsTest(unittest.TestCase):
    """C61: 既定値は『多くの場合これでよい』の表明であって禁止ではない。"""

    def setUp(self):
        self.module = load_module(self)
        self.catalog = self.module.load_catalog()

    def test_catalog_has_no_restriction_vocabulary(self):
        raw = json.dumps(self.catalog, ensure_ascii=False)
        for fragment in (
            "allowed_detail_level",
            "forbidden_detail_level",
            "allowed_evidence_depth",
            "forbidden_evidence_depth",
            "detail_level_locked",
        ):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, raw, "既定値が制約として書かれている")

    def test_script_has_no_rejection_path_for_granularity(self):
        src = H.require_script(self).read_text(encoding="utf-8")
        for fragment in ("E-GRANULARITY", "E-DETAIL-LEVEL", "E-EVIDENCE-DEPTH"):
            with self.subTest(fragment=fragment):
                self.assertNotIn(
                    fragment, src, "粒度の可否判定は C23 の責務ではない (C12 が持つ)"
                )

    def test_two_axes_move_independently_across_presets(self):
        """既定値の集合そのものが 2 軸の独立を示す (片方から他方が決まらない)。"""
        defaults = brief_defaults(self)
        by_detail = {}
        for pair in defaults.values():
            by_detail.setdefault(pair["detail_level"], set()).add(pair["evidence_depth"])
        self.assertTrue(
            any(len(depths) > 1 for depths in by_detail.values()),
            "同じ detail_level に複数の evidence_depth が現れない = 1 軸に畳めてしまう",
        )

    def test_user_named_patterns_are_distinct_points(self):
        """『勉強会のように大まかに』と『レポートのように詳細に』が別の点であること。"""
        defaults = brief_defaults(self)
        for slug in ("study-notes", "report"):
            if slug not in defaults:
                self.fail("利用者が挙げたパターンに対応する doc_type {} の既定値が無い".format(slug))
        self.assertNotEqual(defaults["study-notes"], defaults["report"])


class GranularityDefaultsCoverageTest(unittest.TestCase):
    """裁定 C: 全語彙が既定を持つ。被覆漏れを 2 つの独立した列挙へ分けない。"""

    def test_brief_presets_cover_every_vocabulary_slug(self):
        """AC-C23-R22-61a: 期待 slug 集合は vocabulary から導く (テストへ列挙しない)。"""
        expected = set(H.slugs(self))
        self.assertEqual(
            expected, set(brief_defaults(self)),
            "preset_definitions の granularity_defaults が全語彙を覆っていない",
        )

    def test_vocabulary_size_matches_the_contract(self):
        """語彙は 8 件 (AC-C23-01)。裁定 C の『全 8 語彙被覆』の前提を明示する。"""
        self.assertEqual(H.EXPECTED_VOCABULARY_SIZE, len(H.slugs(self)))

    def test_the_defaults_table_is_a_faithful_copy(self):
        """説明用の写しが正本とずれていないこと (ずれると第 2 の正本になる)。"""
        self.assertEqual(brief_defaults(self), brief_defaults_table(self))

    def test_every_catalog_preset_declares_granularity_defaults(self):
        """catalog 実データ側でも必須キーであること (格納先は preset の内側 1 箇所)。"""
        for slug, preset in H.presets(self).items():
            with self.subTest(purpose=slug):
                got = preset.get("granularity_defaults")
                self.assertIsInstance(
                    got, dict, "{} に granularity_defaults が無い".format(slug)
                )
                self.assertEqual(
                    H.GRANULARITY_DEFAULT_KEYS, set(got.keys()),
                    "キー集合は厳密に {} (裁定 A)".format(sorted(H.GRANULARITY_DEFAULT_KEYS)),
                )
                self.assertIn(got.get("detail_level"), DETAIL_LEVELS)
                self.assertIn(got.get("evidence_depth"), EVIDENCE_DEPTHS)

    def test_proposal_default_is_standard_and_sourced(self):
        """裁定 C が明示的に決めた唯一の新規値。ここだけは値を書いて固定する。"""
        defaults = brief_defaults(self)
        self.assertIn("proposal", defaults, "proposal の既定値が無い (被覆漏れの再発)")
        self.assertEqual(
            {"detail_level": "standard", "evidence_depth": "sourced"},
            defaults["proposal"],
        )


class GranularityCatalogGateTest(unittest.TestCase):
    """手順 4(j): 欠落・キー面・値域を catalog 検査で落とす (実行時 fallback を置かない)。"""

    def setUp(self):
        H.require_script(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _root(self, mutate=None) -> Path:
        return H.make_fixture_root(self, self.tmp, mutate)

    def assert_data_violation(self, proc, code):
        self.assertEqual(1, proc.returncode, H.describe(proc))
        self.assertEqual("", H.out_text(proc), H.describe(proc))
        self.assertIn(code, H.err_text(proc), H.describe(proc))

    def test_missing_key_is_exit1(self):
        """AC-C23-R22-61b: 1 preset から削ると exit 1 (fallback へ落ちない)。"""
        target = {}

        def mutate(catalog):
            slug = sorted(catalog["presets"])[0]
            target["slug"] = slug
            catalog["presets"][slug].pop("granularity_defaults", None)

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, E_MISSING)
        self.assertIn(target["slug"], H.err_text(proc), H.describe(proc))

    def test_missing_key_also_blocks_purpose_mode(self):
        """欠落した preset 以外を --purpose しても止まる (片側更新をその場で落とす)。"""
        def mutate(catalog):
            catalog["presets"][sorted(catalog["presets"])[-1]].pop("granularity_defaults", None)

        proc = H.run_in_root(self._root(mutate), ["--purpose", sorted(H.presets(self))[0]])
        self.assert_data_violation(proc, E_MISSING)

    def test_extra_inner_key_is_exit1(self):
        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["granularity_defaults"]["why"] = "説明"

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.LECTURE_SLUG])
        self.assert_data_violation(proc, E_KEYS)

    def test_missing_inner_key_is_exit1(self):
        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["granularity_defaults"].pop("evidence_depth")

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.LECTURE_SLUG])
        self.assert_data_violation(proc, E_KEYS)

    def test_out_of_range_value_is_exit1(self):
        def mutate(catalog):
            catalog["presets"][H.LECTURE_SLUG]["granularity_defaults"]["detail_level"] = "verbose"

        proc = H.run_in_root(self._root(mutate), ["--purpose", H.LECTURE_SLUG])
        self.assert_data_violation(proc, E_VALUE)

    def test_new_vocabulary_without_defaults_is_exit1(self):
        """AC-C23-R22-61c: 語彙追加が既定値の決定を必ず伴うことを構造で強制する。"""
        def mutate(catalog):
            template = catalog["presets"][H.LECTURE_SLUG]
            catalog["vocabulary"].append({
                "slug": "zzz-new-purpose",
                "label_ja": "新しい用途",
                "dir_token": "zzz-new",
                "aliases": [],
            })
            preset = json.loads(json.dumps(template))
            preset.pop("granularity_defaults", None)
            catalog["presets"]["zzz-new-purpose"] = preset

        proc = H.run_in_root(self._root(mutate), ["--list"])
        self.assert_data_violation(proc, E_MISSING)


class NoRuntimeFallbackTest(unittest.TestCase):
    """裁定 C: 実行時の fallback 既定を持たない (退避経路は第 2 の正本になる)。"""

    def test_script_has_no_default_value_literals(self):
        """AC-C23-R22-61d: 値域も既定値も script 本文へ書かない。"""
        src = H.require_script(self).read_text(encoding="utf-8")
        for value in DETAIL_LEVELS + EVIDENCE_DEPTHS:
            for quote in ('"', "'"):
                with self.subTest(value=value, quote=quote):
                    self.assertNotIn(
                        quote + value + quote, src,
                        "既定値/enum のリテラルが script にある: {} "
                        "(値域の正本は C12、既定値の正本は catalog)".format(value),
                    )

    def test_api_never_returns_none(self):
        """未定義語彙は例外であって None ではない (None は黙って通る fallback になる)。"""
        module = load_module(self)
        catalog = module.load_catalog()
        for slug in H.slugs(self):
            with self.subTest(purpose=slug):
                self.assertIsNotNone(module.granularity_defaults(catalog, slug))

    def test_purpose_output_always_carries_granularity_defaults(self):
        """algorithm 7: 常に非空で出るため呼び出し側が有無を分岐しない。"""
        for slug in H.slugs(self):
            with self.subTest(purpose=slug):
                proc = H.run(["--purpose", slug])
                self.assertEqual(0, proc.returncode, H.describe(proc))
                payload = json.loads(H.out_text(proc))
                self.assertIn("granularity_defaults", payload, H.describe(proc))
                self.assertEqual(
                    H.GRANULARITY_DEFAULT_KEYS,
                    set(payload["granularity_defaults"].keys()),
                    H.describe(proc),
                )


if __name__ == "__main__":
    unittest.main()

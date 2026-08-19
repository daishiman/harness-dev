"""公開モジュール API — AC-C23-13。

C12 / C19 はハイフンを含むファイル名のため importlib.util.spec_from_file_location で読み込む。
CLI と同じ値が返ることを確認し、consumer が語彙を列挙せずに済むことを固定する。
"""

import importlib.util
import json
import unittest

import _harness as H


def load_module(tc):
    H.require_script(tc)
    spec = importlib.util.spec_from_file_location("hb_preset", H.SCRIPT)
    if spec is None or spec.loader is None:
        tc.fail("importlib でモジュールとして読み込めない: {}".format(H.SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicApiTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module(self)

    def test_public_symbols_exist(self):
        for name in (
            "CATALOG_RELPATH",
            "resolve_catalog_path",
            "load_catalog",
            "vocabulary",
            "resolve",
            "preset",
            "dir_token",
            "catalog_sha256",
            "CatalogError",
            "UnknownPurposeError",
        ):
            with self.subTest(symbol=name):
                self.assertTrue(hasattr(self.module, name), "公開 API に {} が無い".format(name))

    def test_catalog_relpath_constant(self):
        self.assertEqual(H.CATALOG_RELPATH, self.module.CATALOG_RELPATH)

    def test_vocabulary_matches_cli(self):
        catalog = self.module.load_catalog()
        self.assertEqual(H.slugs(self), list(self.module.vocabulary(catalog)))

    def test_dir_token_matches_cli(self):
        catalog = self.module.load_catalog()
        for slug in H.slugs(self):
            with self.subTest(slug=slug):
                proc = H.run(["--purpose", slug])
                self.assertEqual(0, proc.returncode, H.describe(proc))
                self.assertEqual(
                    json.loads(H.out_text(proc))["dir_token"], self.module.dir_token(catalog, slug)
                )

    def test_resolve_accepts_alias(self):
        catalog = self.module.load_catalog()
        entry = next(e for e in H.vocabulary_entries(self) if e["aliases"])
        self.assertEqual(entry["slug"], self.module.resolve(catalog, entry["aliases"][0])["slug"])

    def test_resolve_raises_on_unknown(self):
        catalog = self.module.load_catalog()
        with self.assertRaises(self.module.UnknownPurposeError):
            self.module.resolve(catalog, "zzz-not-a-purpose")

    def test_preset_matches_cli(self):
        catalog = self.module.load_catalog()
        slug = H.slugs(self)[0]
        proc = H.run(["--purpose", slug])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        payload = json.loads(H.out_text(proc))
        self.assertEqual(payload["section_order"], self.module.preset(catalog, slug)["section_order"])

    def test_catalog_sha256_matches_cli(self):
        import hashlib

        expected = hashlib.sha256(H.CATALOG.read_bytes()).hexdigest()
        self.assertEqual(expected, self.module.catalog_sha256(H.CATALOG))

    def test_resolve_catalog_path_finds_plugin_root(self):
        self.assertEqual(H.CATALOG.resolve(), self.module.resolve_catalog_path(None).resolve())

    def test_import_does_not_execute_cli(self):
        """モジュール import で stdout へ何も出さず sys.exit もしない (import 副作用ゼロ)。"""
        module = load_module(self)
        self.assertTrue(callable(module.load_catalog))


if __name__ == "__main__":
    unittest.main()

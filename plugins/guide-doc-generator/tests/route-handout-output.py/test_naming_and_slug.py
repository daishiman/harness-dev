"""ディレクトリ命名規則 — AC-C19-06 / 11、algorithm 3 / 5 / 7。

書式そのものは config/handout-output.json#dir_name_format が正本 (R25 以降は
{date}_{slug})。本ファイルはその書式をテストへ焼かず _harness 経由で引く。
"""

import tempfile
import unicodedata
import unittest
from pathlib import Path

import _harness as H


def _dirname(tc, tmp, **overrides):
    root = Path(tmp) / "out"
    root.mkdir(exist_ok=True)
    cfg = H.write_config(
        Path(tmp) / "c.json", H.normalized_config(tc, **overrides)
    )
    proc = H.run(["--config", cfg, "--out-dir", root])
    tc.assertEqual(0, proc.returncode, H.describe(proc))
    return root, proc, H.resolved_path(tc, proc).name


class DatePrefixTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_directory_date_is_pure_transform_of_config_date(self):
        """AC-C19-06: ディレクトリ名の先頭が date の純変換 (replace('/','-'))。"""
        with tempfile.TemporaryDirectory() as tmp:
            _, _, name = _dirname(self, tmp)
            self.assertTrue(
                name.startswith(H.FIXTURE_DATE.replace("/", "-")),
                "ディレクトリ名 {!r} が date の純変換で始まっていない".format(name),
            )
            self.assertTrue(name.startswith(H.name_prefix(self)), name)

    def test_directory_date_follows_a_different_config_date(self):
        """現在日ではなく構成データの日付に追従する (algorithm 3: 現在時刻を取らない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            _, _, name = _dirname(self, tmp, date="1999/01/02")
            self.assertTrue(name.startswith("1999-01-02"), name)
            self.assertNotIn(H.FIXTURE_DATE_DIR, name, "fixture の日付が残っている")

    def test_derived_date_is_not_persisted_as_a_field(self):
        """algorithm 3: 派生値をフィールドとして保存しない (来歴には date が入る)。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, _, name = _dirname(self, tmp)
            marker = root / name / H.ROUTE_MARKER
            if not marker.is_file():
                self.fail("来歴マーカー {} が無い (algorithm 9)".format(marker))
            import json

            payload = json.loads(marker.read_text(encoding="utf-8"))
            self.assertIn(
                H.FIXTURE_DATE,
                H.flatten_strings(payload),
                "来歴に構成データの日付 (yyyy/mm/dd) が残っていない",
            )


class PurposeTokenTest(unittest.TestCase):
    """種別トークンの居場所 (R25): ディレクトリ名ではなく来歴マーカー。

    dir_name_format が {date}_{slug} になった結果、日本語 slug の直前に英字
    トークンが挟まらない。種別そのものは捨てず marker.json へ残す。
    """

    def setUp(self):
        H.require_script(self)

    def test_dir_token_is_not_a_segment_of_the_directory_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            slug = H.any_doc_type(self)
            token = H.dir_token_of(self, slug)
            _, _, name = _dirname(self, tmp, doc_type=slug)
            self.assertNotIn(
                "-{}-".format(token),
                name,
                "命名に種別トークンが挟まっている: {!r}".format(name),
            )

    def test_directory_name_follows_the_canonical_format(self):
        """algorithm 4: 命名は config/handout-output.json の書式そのもの。"""
        with tempfile.TemporaryDirectory() as tmp:
            slug = H.any_doc_type(self)
            _, _, name = _dirname(self, tmp, doc_type=slug)
            expected = H.dir_name_format(self).format(
                date=H.FIXTURE_DATE_DIR, slug=H.slug_part(self, name)
            )
            self.assertEqual(expected, name)

    def test_every_catalog_slug_produces_the_same_shape(self):
        """語彙全件で命名が成立する (語彙を列挙せず正本から回す)。"""
        with tempfile.TemporaryDirectory() as tmp:
            prefix = H.name_prefix(self)
            for entry in H.vocabulary_entries(self):
                slug = entry["slug"]
                _, _, name = _dirname(self, tmp, doc_type=slug)
                self.assertTrue(
                    name.startswith(prefix), "{} の命名: {}".format(slug, name)
                )

    def test_dir_token_still_lives_in_the_route_marker(self):
        """命名から外しても種別は失われない (来歴に残る)。"""
        import json

        with tempfile.TemporaryDirectory() as tmp:
            slug = H.any_doc_type(self)
            root, _, name = _dirname(self, tmp, doc_type=slug)
            marker = root / name / H.ROUTE_MARKER
            if not marker.is_file():
                self.fail("来歴マーカー {} が無い".format(marker))
            blob = "\n".join(H.flatten_strings(json.loads(marker.read_text("utf-8"))))
            self.assertIn(H.dir_token_of(self, slug), blob)


class SlugTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_explicit_subject_slug_is_used_verbatim(self):
        """slug_rule (a): 明示 subject_slug は検証だけして採用する。"""
        with tempfile.TemporaryDirectory() as tmp:
            _, _, name = _dirname(self, tmp, subject_slug="explicit-slug")
            self.assertEqual("explicit-slug", H.slug_part(self, name), name)

    def test_japanese_only_title_yields_non_empty_slug(self):
        """AC-C19-11: 日本語のみの title でも slug が空にならない。"""
        with tempfile.TemporaryDirectory() as tmp:
            _, _, name = _dirname(
                self, tmp, subject_slug=H.OMIT, title="生成AIの業務活用入門"
            )
            self.assertTrue(H.slug_part(self, name), "slug 部が空: {!r}".format(name))

    def test_same_title_yields_same_slug(self):
        """AC-C19-11: 同じ title からは常に同じ slug が出る (別ルートでも一致)。"""
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            _, _, first = _dirname(
                self, tmp_a, subject_slug=H.OMIT, title="生成AIの業務活用入門"
            )
            _, _, second = _dirname(
                self, tmp_b, subject_slug=H.OMIT, title="生成AIの業務活用入門"
            )
            self.assertEqual(first, second)

    def test_derived_slug_has_no_forbidden_characters(self):
        """slug_rule (b): 空白 / パス区切り / OS 禁止文字 / 制御文字を残さない。"""
        with tempfile.TemporaryDirectory() as tmp:
            _, _, name = _dirname(
                self,
                tmp,
                subject_slug=H.OMIT,
                title=' A/B\\C:D*E?F"G<H>I|J K\tL ',
            )
            slug = H.slug_part(self, name)
            for char in '/\\:*?"<>| \t':
                self.assertNotIn(char, slug, "禁止文字 {!r} が slug に残った: {!r}".format(char, slug))
            self.assertFalse(slug.startswith("-") or slug.endswith("-"), slug)
            self.assertFalse(slug.startswith(".") or slug.endswith("."), slug)
            self.assertNotIn("--", slug, "連続ハイフンが畳まれていない: {!r}".format(slug))

    def test_derived_slug_is_truncated_to_40_chars(self):
        """slug_rule (b): 先頭 40 文字で切る。"""
        with tempfile.TemporaryDirectory() as tmp:
            _, _, name = _dirname(
                self, tmp, subject_slug=H.OMIT, title="あ" * 120
            )
            slug = H.slug_part(self, name)
            self.assertLessEqual(len(slug), 40, "slug が 40 文字を超えた: {!r}".format(slug))
            self.assertGreater(len(slug), 0)

    def test_derived_slug_is_nfkc_normalized_and_lowercased(self):
        """slug_rule (b): NFKC 正規化 → ASCII 大文字を小文字化。"""
        with tempfile.TemporaryDirectory() as tmp:
            _, _, name = _dirname(self, tmp, subject_slug=H.OMIT, title="ＡＢＣ")
            slug = H.slug_part(self, name)
            self.assertEqual(unicodedata.normalize("NFKC", slug), slug)
            self.assertEqual(slug.lower(), slug, "ASCII 大文字が残った: {!r}".format(slug))

    def test_untitled_fallback_is_topic_hash8(self):
        """slug_rule (c): 導出結果が空のときだけ topic-<hash8>。"""
        import hashlib

        title = "///"
        expected = "topic-{}".format(
            hashlib.sha256(unicodedata.normalize("NFKC", title).encode("utf-8"))
            .hexdigest()[:8]
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, _, name = _dirname(self, tmp, subject_slug=H.OMIT, title=title)
            self.assertEqual(expected, H.slug_part(self, name), name)


class DirectoryStructureTest(unittest.TestCase):
    """ディレクトリ内の構造 (algorithm 9): assets/ と来歴マーカー。"""

    def setUp(self):
        H.require_script(self)

    def test_assets_directory_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _, name = _dirname(self, tmp)
            self.assertTrue((root / name / "assets").is_dir(), "assets/ が作られていない")

    def test_route_marker_records_resolution_provenance(self):
        """algorithm 9: date / purpose / slug / config の sha256 / 解決段。"""
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg, "--out-dir", root])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            marker = H.resolved_path(self, proc) / H.ROUTE_MARKER
            if not marker.is_file():
                self.fail("来歴マーカー {} が無い".format(marker))
            blob = "\n".join(H.flatten_strings(json.loads(marker.read_text("utf-8"))))
            self.assertIn(H.config_sha256(cfg), blob, "config の sha256 が来歴に無い")
            self.assertIn(H.dir_token_of(self, H.any_doc_type(self)), blob)
            H.assert_stage_recorded(self, blob, "argv")

    def test_nothing_is_written_outside_the_resolved_directory(self):
        """write_scope: ルート直下に解決ディレクトリ 1 つだけを作る。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, _, name = _dirname(self, tmp)
            self.assertEqual([name], sorted(p.name for p in root.iterdir()))


if __name__ == "__main__":
    unittest.main()

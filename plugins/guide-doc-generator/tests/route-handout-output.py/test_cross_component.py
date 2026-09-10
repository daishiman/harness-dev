"""他 component との境界 — AC-C19-03 (後半) / 06 (後半) / 20、P03 Y-04 / Y-09。

これらは C19 単体では緑にできない (他 component の成果物に依存する)。
単一 writer と単一正本という性質上、意図した結合である。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H

# 出力先ディレクトリへ書く実装が現れてはいけない component (bundle_writers の裏返し)。
NON_PLACING_COMPONENTS = (
    (H.EMBED_SCRIPT, "C13"),   # data URI 化のみ。配置には一切関与しない
    (H.RENDER_SCRIPT, "C11"),  # handout.html 1 ファイルだけを書く
    (H.BUILD_SKILL, "C01"),    # README.md だけを書く
)


class BundleWriterUniquenessTest(unittest.TestCase):
    """AC-C19-20: handout-config.json と assets/ 配下へ書く実装が C19 にしか無い。"""

    def test_c13_does_not_place_files(self):
        source = H.require_file(self, H.EMBED_SCRIPT, "C13").read_text(encoding="utf-8")
        for token in ("handout-config.json", "shutil.copy", "copytree"):
            self.assertNotIn(token, source, "C13 に配置の実装がある: {}".format(token))

    def test_c11_does_not_write_handout_config_json(self):
        source = H.require_file(self, H.RENDER_SCRIPT, "C11").read_text(encoding="utf-8")
        self.assertNotIn(
            "handout-config.json",
            source,
            "C11 が出力先へ構成データを書いている (writer は C19)",
        )

    def test_c01_delegates_placement_to_c19(self):
        text = H.require_file(self, H.BUILD_SKILL, "C01").read_text(encoding="utf-8")
        self.assertIn("--place-config", text, "C01 が --place-config を C19 へ渡していない")
        self.assertIn("--assets-src", text, "C01 が --assets-src を C19 へ渡していない")

    def test_only_c19_builds_the_directory_name(self):
        """single_writer: 命名規則を自前で組み立てる実装が 2 箇所に生まれない。"""
        for path, owner in NON_PLACING_COMPONENTS:
            with self.subTest(owner=owner):
                text = H.require_file(self, path, owner).read_text(encoding="utf-8")
                self.assertNotIn(
                    'replace("/", "-")',
                    text,
                    "{} がディレクトリ名の日付派生を自前で持っている".format(owner),
                )


class VocabularyDuplicationGateTest(unittest.TestCase):
    """AC-C19-03 後半: C23 の --audit-duplication が重複 0 件で exit 0。"""

    def test_audit_duplication_passes_on_the_real_tree(self):
        H.require_script(self)
        H.require_file(self, H.PRESET_SCRIPT, "C23")
        proc = H.run(["--audit-duplication"], script=H.PRESET_SCRIPT)
        self.assertEqual(0, proc.returncode, H.describe(proc))


class DateConsistencyWithC18Test(unittest.TestCase):
    """AC-C19-06 後半: C19 が作ったディレクトリ名を C18 が exit 0 と判定する。"""

    def test_c18_accepts_the_directory_created_by_c19(self):
        H.require_script(self)
        H.require_file(self, H.VERIFY_LANGUAGE_SCRIPT, "C18")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            created = H.run(["--config", cfg, "--out-dir", root, "--place-config"])
            self.assertEqual(0, created.returncode, H.describe(created))
            target = H.resolved_path(self, created)
            (target / "handout.html").write_text(
                "<html lang=\"ja\"><body></body></html>\n", encoding="utf-8"
            )
            checked = H.run(
                ["--config", cfg, "--out-dir", target],
                script=H.VERIFY_LANGUAGE_SCRIPT,
            )
            self.assertNotIn(
                "date",
                H.err_text(checked).lower(),
                "C18 が日付整合違反を報告した: {}".format(H.describe(checked)),
            )


if __name__ == "__main__":
    unittest.main()

"""AC-C15-5 / algorithm 4・6 / failure_modes: 入力データの規約違反は exit 1 で fail-closed。

「黙って既定アイコンへ落とす」経路が 1 つも無いことと、
差し戻し先が判る診断 (名前・キーパス・近似候補) が出ることを固定する。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H


class UndefinedIconNameTest(unittest.TestCase):
    """AC-C15-5: 正本に無い名前を参照する → exit 1 / 名前・キーパス・近似候補。"""

    def _run(self, tmp, config):
        iset = H.write_icon_set(Path(tmp), H.make_icon_set())
        cfg = H.write_config(Path(tmp), config)
        return H.run_sprite(self, cfg, iset)

    def test_unknown_name_is_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, H.make_config(sections=[H.section("s1", section_icon="rocket")]))
            H.expect_exit(self, proc, 1, "語彙外は fail-closed")

    def test_stderr_names_the_icon_and_key_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(
                tmp,
                H.make_config(
                    sections=[H.section("s1", blocks=[H.block("list", items=["rocket"])])]
                ),
            )
            H.expect_exit(self, proc, 1)
            err = H.err_text(proc)
            self.assertIn("rocket", err, "stderr に未定義アイコン名が無い\n" + H.describe(proc))
            self.assertIn(
                "sections[0].blocks[0].items[0].icon", err,
                "stderr に参照キーパスが無い\n" + H.describe(proc),
            )

    def test_stderr_offers_close_matches(self):
        """algorithm 6: difflib.get_close_matches の上位 3 件。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, H.make_config(sections=[H.section("s1", section_icon="checkk")]))
            H.expect_exit(self, proc, 1)
            self.assertIn(
                "check", H.err_text(proc),
                "近似候補 (checkk -> check) が出ていない\n" + H.describe(proc),
            )

    def test_no_silent_fallback_icon(self):
        """未定義名を既定アイコンへ落とす経路が無い (意味の違うアイコンを出さない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, H.make_config(sections=[H.section("s1", section_icon="rocket")]))
            self.assertNotEqual(proc.returncode, 0, "未定義名で成功している (既定へ落とした疑い)")
            self.assertEqual(
                H.out_text(proc).strip(), "",
                "exit 1 なのに sprite を出している\n" + H.describe(proc),
            )

    def test_all_unknown_names_are_reported_not_just_the_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(
                tmp,
                H.make_config(
                    sections=[
                        H.section("s1", section_icon="rocket"),
                        H.section("s2", section_icon="unicorn"),
                    ]
                ),
            )
            H.expect_exit(self, proc, 1)
            err = H.err_text(proc)
            self.assertIn("rocket", err)
            self.assertIn("unicorn", err, "2 件目の未定義名が報告されていない\n" + H.describe(proc))


class IconSetIntegrityTest(unittest.TestCase):
    """algorithm 4: 正本そのものの検査。"""

    def _run(self, tmp, icons, used="check"):
        iset = H.write_icon_set(Path(tmp), H.make_icon_set(icons=icons))
        cfg = H.write_config(
            Path(tmp), H.make_config(sections=[H.section("s1", section_icon=used)])
        )
        return H.run_sprite(self, cfg, iset)

    def test_name_must_match_the_character_class(self):
        """name が [a-z0-9-]+ に一致しなければ exit 1。"""
        with tempfile.TemporaryDirectory() as tmp:
            for i, bad in enumerate(["Check", "check_mark", "チェック", "check mark", "check.svg", ""]):
                sub = Path(tmp) / str(i)
                sub.mkdir()
                proc = self._run(sub, [H.icon(bad)], used=bad or "check")
                H.expect_exit(self, proc, 1, "name={!r} は字種違反".format(bad))

    def test_valid_names_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, ok in enumerate(["check", "arrow-right", "step-1", "a", "x9"]):
                sub = Path(tmp) / str(i)
                sub.mkdir()
                proc = self._run(sub, [H.icon(ok)], used=ok)
                H.expect_exit(self, proc, 0, "name={!r} は許容される".format(ok))

    def test_empty_paths_is_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, [H.icon("check", paths=[])])
            H.expect_exit(self, proc, 1, "paths が空配列")

    def test_integrity_is_checked_before_scanning(self):
        """algorithm 4 は 5 より前。未使用アイコンの規約違反も落とす。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, [H.icon("check"), H.icon("BAD")])
            H.expect_exit(self, proc, 1, "未使用でも正本の字種違反は落とす")

    def test_missing_icons_key_is_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), {H.SET_VERSION_KEY: "1"})
            cfg = H.write_config(Path(tmp), H.make_config())
            proc = H.run_sprite(self, cfg, iset)
            self.assertIn(
                proc.returncode, (1, 2),
                "icons を持たない正本で成功している\n" + H.describe(proc),
            )

    def test_stderr_reports_the_icon_set_resolution_path(self):
        """stderr 契約: アイコンセット正本の読み込み経路 (実体解決でどこを採ったか)。"""
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=["check"]))
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 0)
            self.assertIn(
                "icon-set.json", H.err_text(proc),
                "stderr に正本の読み込み経路が出ていない\n" + H.describe(proc),
            )


class ConfigShapeTest(unittest.TestCase):
    """走査対象の型が壊れているときの扱い。"""

    def test_non_string_icon_value_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon=42)])
            )
            proc = H.run_sprite(self, cfg, iset)
            self.assertNotEqual(
                proc.returncode, 0,
                "icon の型不正を黙って読み飛ばしている\n" + H.describe(proc),
            )

    def test_top_level_array_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            cfg = H.write_config(Path(tmp), [1, 2, 3])
            proc = H.run_sprite(self, cfg, iset)
            self.assertNotEqual(proc.returncode, 0, "構成データがオブジェクトでないのに成功している")


class NoSideEffectTest(unittest.TestCase):
    """write_scope=none。成功でも失敗でもファイルを 1 バイトも書かない。"""

    def test_success_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            H.write_icon_set(root, H.make_icon_set())
            H.write_config(root, H.make_config(sections=[H.section("s1", section_icon="check")]))
            before = H.tree_snapshot(root)
            proc = H.run_sprite(self, root / "handout-config.json", root / "icon-set.json")
            H.expect_exit(self, proc, 0)
            self.assertEqual(before, H.tree_snapshot(root), "write_scope=none に反して書き込みがある")

    def test_failure_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            H.write_icon_set(root, H.make_icon_set())
            H.write_config(root, H.make_config(sections=[H.section("s1", section_icon="rocket")]))
            before = H.tree_snapshot(root)
            proc = H.run_sprite(self, root / "handout-config.json", root / "icon-set.json")
            H.expect_exit(self, proc, 1)
            self.assertEqual(before, H.tree_snapshot(root), "失敗時にファイルを書いている")

    def test_icon_set_is_never_written_back(self):
        """icon_set_source: 正本は read-only。本 script は決して書き戻さない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            iset = H.write_icon_set(root, H.make_icon_set())
            before = iset.read_bytes()
            cfg = H.write_config(
                root, H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            H.run_sprite(self, cfg, iset)
            self.assertEqual(before, iset.read_bytes(), "アイコンセット正本が書き換えられている")


if __name__ == "__main__":
    unittest.main()

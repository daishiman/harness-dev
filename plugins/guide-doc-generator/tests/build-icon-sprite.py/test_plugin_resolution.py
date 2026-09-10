"""AC-C15-7 / algorithm 2: --icon-set 未指定時の plugin 実体解決 4 段。

解決順は index.md の実行時可搬性方針 (C09/C10/C11/C12/C15/C21/C23 で共通):
  1. HB_ROOT
  2. ${HB_ROOT:-$CLAUDE_PLUGIN_ROOT}
  3. 候補直下の .claude-plugin/plugin.json を読み name=="guide-doc-generator" を照合
  4. __file__ の親の親 (scripts/ の親)
いずれも解決できなければ exit 2 で試した経路を stderr へ列挙する。
絶対パスを実装へ直書きしない。

検査は tempdir に複製した plugin ツリーに対して行い、実 plugin ツリーへは書かない。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H


class SelfResolutionTest(unittest.TestCase):
    def _tree(self, tmp, **kwargs):
        root = Path(tmp) / "plugin-root"
        script = H.make_plugin_tree(self, root, **kwargs)
        cfg = H.write_config(
            Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
        )
        return root, script, cfg

    def test_file_relative_resolution_without_env(self):
        """AC-C15-7: HB_ROOT も CLAUDE_PLUGIN_ROOT も未設定で __file__ 相対に落ちて exit 0。"""
        with tempfile.TemporaryDirectory() as tmp:
            _root, script, cfg = self._tree(tmp)
            proc = H.run_sprite(self, cfg, icon_set=None, script=script, env=H.clean_env())
            H.expect_exit(self, proc, 0, "__file__ 相対の自己解決に失敗している")
            result = H.sprite_result(self, proc)
            self.assertEqual([e["name"] for e in result[H.OUT_USED]], ["check"])

    def test_hb_root_takes_precedence(self):
        """1 段目 HB_ROOT。ここにだけ違う正本を置いて採られた側を判別する。"""
        with tempfile.TemporaryDirectory() as tmp:
            _root, script, cfg = self._tree(tmp)
            other = Path(tmp) / "other-root"
            H.make_plugin_tree(
                self, other,
                icon_set_data=H.make_icon_set(
                    icons=[H.icon("check", title="HB_ROOT 側")], set_version="hb-root"
                ),
                with_script=False,
            )
            proc = H.run_sprite(
                self, cfg, icon_set=None, script=script, env=H.clean_env(HB_ROOT=other)
            )
            result = H.sprite_result(self, proc)
            self.assertEqual(
                result[H.OUT_SET_VERSION], "hb-root",
                "HB_ROOT が 1 段目として採られていない\n" + H.describe(proc),
            )

    def test_claude_plugin_root_is_used_when_hb_root_is_absent(self):
        """2 段目 ${HB_ROOT:-$CLAUDE_PLUGIN_ROOT}。"""
        with tempfile.TemporaryDirectory() as tmp:
            _root, script, cfg = self._tree(tmp)
            other = Path(tmp) / "cpr-root"
            H.make_plugin_tree(
                self, other,
                icon_set_data=H.make_icon_set(
                    icons=[H.icon("check")], set_version="cpr-root"
                ),
                with_script=False,
            )
            proc = H.run_sprite(
                self, cfg, icon_set=None, script=script,
                env=H.clean_env(CLAUDE_PLUGIN_ROOT=other),
            )
            result = H.sprite_result(self, proc)
            self.assertEqual(
                result[H.OUT_SET_VERSION], "cpr-root",
                "CLAUDE_PLUGIN_ROOT が 2 段目として採られていない\n" + H.describe(proc),
            )

    def test_explicit_icon_set_overrides_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            _root, script, cfg = self._tree(tmp)
            explicit = H.write_icon_set(
                Path(tmp) / "explicit",
                H.make_icon_set(icons=[H.icon("check")], set_version="explicit"),
            )
            proc = H.run_sprite(self, cfg, icon_set=explicit, script=script, env=H.clean_env())
            result = H.sprite_result(self, proc)
            self.assertEqual(result[H.OUT_SET_VERSION], "explicit")


class ResolutionFailureTest(unittest.TestCase):
    """algorithm 2 / failure_modes: 4 段すべて外れたら exit 2 + 試行経路の列挙。"""

    def _unresolvable(self, tmp):
        """scripts/ だけを持ち assets/icons/ を持たない root へ script を複製する。"""
        root = Path(tmp) / "bare"
        script = H.make_plugin_tree(
            self, root, with_manifest=False, with_icon_set=False
        )
        cfg = H.write_config(
            Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
        )
        return script, cfg

    def test_unresolvable_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            script, cfg = self._unresolvable(tmp)
            proc = H.run_sprite(self, cfg, icon_set=None, script=script, env=H.clean_env())
            H.expect_exit(self, proc, 2, "実体解決の失敗は exit 2 (規約違反 exit 1 と分ける)")

    def test_failure_lists_the_attempted_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            script, cfg = self._unresolvable(tmp)
            proc = H.run_sprite(self, cfg, icon_set=None, script=script, env=H.clean_env())
            H.expect_exit(self, proc, 2)
            err = H.err_text(proc)
            for token in ("HB_ROOT", "CLAUDE_PLUGIN_ROOT", "plugin.json", "__file__"):
                self.assertIn(
                    token, err,
                    "stderr の試行経路に {} が無い (HB_ROOT 未設定の切り分けができない)\n{}".format(
                        token, H.describe(proc)
                    ),
                )

    def test_nonexistent_hb_root_falls_through(self):
        """4 段は「順に試し最初に実在した root を採る」。1 段目が不在でも打ち切らない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plugin-root"
            script = H.make_plugin_tree(self, root)
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            proc = H.run_sprite(
                self, cfg, icon_set=None, script=script,
                env=H.clean_env(HB_ROOT=Path(tmp) / "does-not-exist"),
            )
            H.expect_exit(self, proc, 0, "1 段目が不在なだけで解決を打ち切っている")


class NoHardcodedPathTest(unittest.TestCase):
    """algorithm 2: 絶対パスを実装へ直書きしない。"""

    def test_source_has_no_absolute_path_literal(self):
        source = H.script_source(self)
        for bad in ('"/Users', "'/Users", '"/home', "'/home", '"/opt', "'/opt", "C:\\\\"):
            self.assertNotIn(bad, source, "絶対パスの直書きがある: {}".format(bad))

    def test_source_mentions_all_four_resolution_stages(self):
        source = H.script_source(self)
        for token in ("HB_ROOT", "CLAUDE_PLUGIN_ROOT", "plugin.json", "guide-doc-generator"):
            self.assertIn(token, source, "実体解決 4 段のうち {} が実装に無い".format(token))


if __name__ == "__main__":
    unittest.main()

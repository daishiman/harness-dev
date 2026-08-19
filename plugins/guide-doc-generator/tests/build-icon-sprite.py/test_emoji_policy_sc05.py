"""AC-C15-3 / C16 SC-05 (CR-EMOJI): 絵文字ゼロを二層規則で判定する。

判定規則の単一正本は script-brief-C16.json の canonical_rules.emoji_rule
(RESOLUTION-P03.md Y-03 で確定)。**Unicode ブロック丸ごとの denylist は用いない**。
★ U+2605 / ☆ U+2606 / ✔ U+2714 (VS16 なし) / ♪ U+266A / ■ U+25A0 / © U+00A9
(VS16 なし) は絵文字ではなく通す。

C15 は R08「絵文字を使わない」の入口を正本の検査で塞ぐ側なので、
(a) 出力に絵文字が 1 件も出ないこと と
(b) 正本に絵文字が混入していたら exit 1 で落とすこと
の両方を固定する。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H


class OutputHasNoEmojiTest(unittest.TestCase):
    """AC-C15-3: 出力全体を走査して検出 0 件。"""

    def test_stdout_and_stderr_are_emoji_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = ["check", "cross", "warning", "star", "sparkle"]
            iset = H.write_icon_set(
                Path(tmp),
                H.make_icon_set(icons=[H.icon(n, title="見出し " + n) for n in names]),
            )
            cfg = H.write_config(
                Path(tmp),
                H.make_config(sections=[H.section("s{}".format(i), section_icon=n)
                                        for i, n in enumerate(names)]),
            )
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 0)
            H.assert_no_emoji(self, H.out_text(proc), "stdout")
            H.assert_no_emoji(self, H.err_text(proc), "stderr")

    def test_symbols_svg_uses_path_not_glyph(self):
        """絵文字の代替は <path> であって文字ではない (R08)。"""
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=["check"]))
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            self.assertTrue(H.tags_named(collector, "path"), "path が無い")
            H.assert_no_emoji(self, result[H.OUT_SYMBOLS], "symbols_svg")

    def test_error_diagnostics_are_emoji_free(self):
        """exit 1 の診断も出力の一部。ここへ絵文字を混ぜない。"""
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=["check"]))
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="rocket")])
            )
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 1)
            H.assert_no_emoji(self, H.err_text(proc), "stderr")


class IconSetEmojiRejectionTest(unittest.TestCase):
    """failure_modes: アイコン名や title に絵文字が混入 → exit 1 / コードポイント併記。"""

    def _run(self, tmp, title):
        iset = H.write_icon_set(
            Path(tmp), H.make_icon_set(icons=[H.icon("check", title=title)])
        )
        cfg = H.write_config(
            Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
        )
        return H.run_sprite(self, cfg, iset)

    def test_layer1_emoji_in_title_is_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            for glyph in ("\U0001F449", "✅", "\U0001F1EF\U0001F1F5", "✨"):
                sub = Path(tmp) / "{:X}".format(ord(glyph[0]))
                sub.mkdir()
                proc = self._run(sub, "完了 " + glyph)
                H.expect_exit(self, proc, 1, "層 1 絵文字 {}".format(H.format_codepoints(glyph)))

    def test_layer2_with_vs16_is_exit1(self):
        """AC-C15-3c: U+2699 U+FE0F (歯車 + VS16) は層 2 + VS16 なので違反。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, "設定 ⚙️")
            H.expect_exit(self, proc, 1, "層 2 + VS16")

    def test_layer2_violation_reports_sc05_and_codepoints(self):
        """AC-C15-3c: stderr へ detection_id=SC-05 と codepoints をそのまま転記する。

        P04-x-05 G-03: 判定文言を C15 側で言い換えないこと (言い換えは規則の複製の第一歩)。
        """
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, "設定 ⚙️")
            H.expect_exit(self, proc, 1)
            err = H.err_text(proc).upper()
            self.assertIn("SC-05", err, "stderr に detection_id=SC-05 が無い\n" + H.describe(proc))
            self.assertIn("2699", err, "stderr に該当コードポイントが無い\n" + H.describe(proc))
            self.assertIn("FE0F", err, "stderr に VS16 のコードポイントが無い\n" + H.describe(proc))

    def test_keycap_sequence_is_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, "手順 1️⃣")
            H.expect_exit(self, proc, 1, "キーキャップ列")

    def test_violation_reports_codepoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, "次へ \U0001F449")
            H.expect_exit(self, proc, 1)
            err = H.err_text(proc)
            self.assertIn(
                "1F449", err.upper(),
                "stderr に該当文字のコードポイントが無い\n" + H.describe(proc),
            )


class NonEmojiSymbolsPassTest(unittest.TestCase):
    """CR-EMOJI の回帰: 日本語文書で常用する記号を殺さない。

    ブロック丸ごとの denylist を実装すると、ここが落ちる。
    """

    def _run(self, tmp, title):
        iset = H.write_icon_set(
            Path(tmp), H.make_icon_set(icons=[H.icon("check", title=title)])
        )
        cfg = H.write_config(
            Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
        )
        return H.run_sprite(self, cfg, iset)

    def test_star_and_check_mark_pass(self):
        """AC-C15-3b: ★ U+2605 / ✔ U+2714 (VS16 なし)。U+2714 は旧 denylist の U+2600-27BF に入る。"""
        with tempfile.TemporaryDirectory() as tmp:
            for i, title in enumerate(("★ 重要", "✔ 完了", "☆ 補足")):
                sub = Path(tmp) / str(i)
                sub.mkdir()
                proc = self._run(sub, title)
                H.expect_exit(
                    self, proc, 0,
                    "CR-EMOJI は {} を絵文字としない ({})".format(title, H.format_codepoints(title[0])),
                )

    def test_copyright_and_music_and_geometric_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, title in enumerate(("© 2026 例", "♪ BGM", "■ 前提", "▶ 再生")):
                sub = Path(tmp) / str(i)
                sub.mkdir()
                proc = self._run(sub, title)
                H.expect_exit(self, proc, 0, "CR-EMOJI 非検出のはず: {}".format(title))

    def test_japanese_punctuation_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, "「まとめ」・所要〜30 分…、そして。")
            H.expect_exit(self, proc, 0, "日本語約物を絵文字と誤検出している")

    def test_arrow_without_vs16_passes(self):
        """U+2192 → は旧 denylist の U+2190-21FF に入るが CR-EMOJI では非検出。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp, "入力 → 出力")
            H.expect_exit(self, proc, 0, "→ (U+2192) を絵文字と誤検出している")


class EmojiDelegationTest(unittest.TestCase):
    """P04-x-05 G-03: 絵文字判定の正本は C16 の CR-EMOJI 1 箇所であり C15 は委譲する。

    「同じ規則を書く」ではなく「同じ実装を呼ぶ」であることを静的・動的の両面で固定する。
    """

    def test_source_has_no_emoji_codepoint_enumeration(self):
        """AC-C15-11: 絵文字判定に関するコードポイント列挙が script 本文に 0 件。"""
        source = H.script_source(self).upper()
        hits = [t for t in H.EMOJI_CODEPOINT_TOKENS if t in source]
        self.assertEqual(
            hits, [],
            "絵文字のコードポイントが C15 へ書かれている (語彙の正本は C16 の CR-EMOJI 1 箇所): "
            "{}".format(hits),
        )

    def test_source_has_no_unicode_plus_notation(self):
        """U+XXXX 表記での独自レンジ定義も第 2 の正本になる。"""
        source = H.script_source(self)
        self.assertNotIn(
            "U+", source.upper(),
            "script 本文に U+XXXX 表記がある (絵文字の語彙を C15 が持ってはならない)",
        )

    def test_source_delegates_to_c16_scan_emoji(self):
        """委譲先が C16 の scan_emoji であること (module import・ファイル名にハイフン)。"""
        source = H.script_source(self)
        self.assertIn(
            H.C16_SCRIPT.name, source,
            "C16 {} への委譲が実装に無い".format(H.C16_SCRIPT.name),
        )
        self.assertIn(
            H.C16_MODULE_FUNCTION, source,
            "C16 の {}(text) を呼んでいない".format(H.C16_MODULE_FUNCTION),
        )
        self.assertIn(
            "spec_from_file_location", source,
            "ハイフンを含むファイル名を importlib で読み込む作法になっていない",
        )

    def test_missing_c16_is_exit2_fail_closed(self):
        """C16 を解決できないときは独自判定へ退避せず exit 2 (退避経路は第 2 の正本になる)。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "no-c16"
            script = H.make_plugin_tree(self, root, with_c16=False)
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            proc = H.run_sprite(self, cfg, icon_set=None, script=script, env=H.clean_env())
            H.expect_exit(
                self, proc, 2,
                "C16 未解決時は fail-closed。独自判定で exit 0/1 を返してはならない",
            )
            self.assertIn(
                H.C16_SCRIPT.name, H.err_text(proc),
                "stderr に解決できなかった C16 の script 名が無い\n" + H.describe(proc),
            )


class EscapingTest(unittest.TestCase):
    """algorithm 13: 文字列は html.escape(quote=True) でエスケープする。"""

    def test_title_is_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(
                Path(tmp), H.make_icon_set(icons=[H.icon("check", title='A & B <x> "q"')])
            )
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            markup = result[H.OUT_SYMBOLS]
            self.assertIn("&amp;", markup, "& がエスケープされていない:\n" + markup)
            self.assertNotIn("<x>", markup, "生の < > が出ている:\n" + markup)
            self.assertIn("&quot;", markup, "quote=True でエスケープされていない:\n" + markup)


if __name__ == "__main__":
    unittest.main()

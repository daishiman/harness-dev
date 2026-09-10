"""C16 SC-07 / AC-C15-8 の C15 側: <symbol> と <use> の 1:1 対応。

C15 の出力そのものには <use> は含まれない (参照側の <use> は C11 が use_href から
書く。script-brief-C11.json algorithm 9)。したがって C15 が構造で保証すべきは

  定義された symbol 集合 == 参照表 (used) の symbol_id 集合

であり、これが崩れなければ C11 が use_href をそのまま使う限り SC-07 は成立する。
「未使用の symbol」「未定義の use」「重複」の 3 種の違反が C15 側の出力からは
発生し得ないことをここで固定する。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H


class PairingTest(unittest.TestCase):
    def _run(self, tmp, used_names, set_names):
        iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=list(set_names)))
        cfg = H.write_config(
            Path(tmp),
            H.make_config(
                sections=[H.section("s{}".format(i), section_icon=n)
                          for i, n in enumerate(used_names)]
            ),
        )
        return H.sprite_result(self, H.run_sprite(self, cfg, iset))

    def test_definitions_and_manifest_are_one_to_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp, ["check", "clock", "target"], H.VOCABULARY)
            H.assert_sc07_pairing(self, result)

    def test_no_unused_symbol_can_be_emitted(self):
        """SC-07 (a) 未使用 symbol。定義側は参照表と同一集合でしか出ない。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp, ["check"], ["check", "cross", "clock", "star"])
            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            self.assertEqual(H.symbol_ids(collector), ["hbic-check"])
            self.assertEqual([e["name"] for e in result[H.OUT_USED]], ["check"])

    def test_no_undefined_reference_can_be_emitted(self):
        """SC-07 (b) 未定義参照。参照表の全 use_href が定義済み id を指す。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp, ["check", "clock"], H.VOCABULARY)
            defined = set(H.symbol_ids(H.parse_svg(self, result[H.OUT_SYMBOLS])))
            for entry in result[H.OUT_USED]:
                self.assertEqual(
                    entry["use_href"], "#" + entry["symbol_id"],
                    "use_href の形が #symbol_id でない: {}".format(entry),
                )
                self.assertIn(
                    entry["symbol_id"], defined,
                    "参照表が未定義 symbol を指している: {}".format(entry),
                )

    def test_repeated_references_do_not_duplicate_symbols(self):
        """SC-07 (c) 重複。同名を何度参照しても symbol は 1 件。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp),
                H.make_config(
                    nav_icon="check",
                    goal_chips=["check"],
                    sections=[
                        H.section("s1", section_icon="check",
                                  blocks=[H.block("list", items=["check", "check"])]),
                        H.section("s2", section_icon="check"),
                    ],
                ),
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            ids = H.symbol_ids(H.parse_svg(self, result[H.OUT_SYMBOLS]))
            self.assertEqual(ids, ["hbic-check"], "重複定義が出ている: {}".format(ids))
            # nav.icon / hero.goal_chips[0].icon / sections[0].icon / items×2 / sections[1].icon
            self.assertEqual(result[H.OUT_USED][0]["ref_count"], 6)
            H.assert_sc07_pairing(self, result)


class SymbolIdSchemeTest(unittest.TestCase):
    """algorithm 8: id = "hbic-" + name。連番やハッシュを使わない (C20 の逆抽出のため)。"""

    def test_id_is_name_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = ["arrow-right", "step-1", "step-2"]
            iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=names))
            cfg = H.write_config(
                Path(tmp),
                H.make_config(sections=[H.section("s{}".format(i), section_icon=n)
                                        for i, n in enumerate(names)]),
            )
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            ids = H.symbol_ids(H.parse_svg(self, result[H.OUT_SYMBOLS]))
            self.assertEqual(ids, ["hbic-arrow-right", "hbic-step-1", "hbic-step-2"])

    def test_id_has_no_sequence_or_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = ["check", "cross", "clock"]
            iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=names))
            cfg = H.write_config(
                Path(tmp),
                H.make_config(sections=[H.section("s{}".format(i), section_icon=n)
                                        for i, n in enumerate(names)]),
            )
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            for sid in H.symbol_ids(H.parse_svg(self, result[H.OUT_SYMBOLS])):
                suffix = sid[len(H.SYMBOL_ID_PREFIX):]
                self.assertIn(
                    suffix, names,
                    "id 接尾辞 {!r} が語彙そのものでない (連番/ハッシュの疑い)".format(suffix),
                )


class DuplicateNameInSetTest(unittest.TestCase):
    """failure_modes: 正本内で symbol name が重複 → exit 1。

    id 採番が name 由来のため、重複は HTML 内の id 重複 = SC-07 (c) になる。
    """

    def test_duplicate_name_is_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(
                Path(tmp), H.make_icon_set(icons=[H.icon("check"), H.icon("cross"), H.icon("check")])
            )
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 1, "正本の name 重複")

    def test_duplicate_name_reports_name_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(
                Path(tmp), H.make_icon_set(icons=[H.icon("check"), H.icon("cross"), H.icon("check")])
            )
            cfg = H.write_config(Path(tmp), H.make_config())
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 1)
            err = H.err_text(proc)
            self.assertIn("check", err, "stderr に重複名が無い\n" + H.describe(proc))
            self.assertIn("2", err, "stderr に配列 index が無い\n" + H.describe(proc))

    def test_duplicate_is_detected_even_when_unused(self):
        """検査は正本全体に掛かる (algorithm 4 は走査より前)。"""
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(
                Path(tmp), H.make_icon_set(icons=[H.icon("clock"), H.icon("clock")])
            )
            cfg = H.write_config(Path(tmp), H.make_config())
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 1, "未使用でも正本の重複は落とす")


if __name__ == "__main__":
    unittest.main()

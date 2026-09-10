"""AC-C15-8: C16 verify-handout-selfcontained.py との producer↔consumer 契約。

C16 の実装有無に依存させないため、SC-05 / SC-06 / SC-07 の判定は
script-brief-C16.json の detections 本文から `_harness` 側へ写して掛ける
(C16 の実装が出来上がった後は AC-C16-* 側が同じ入力で二重に確認する)。

組み立て方は C11 の契約に従う:
  - symbols_svg を <body> 直後へ 1 度だけ置く (algorithm 9)
  - 参照は <use href="#hbic-{name}"> のみを使う
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H


def build_html(result: dict) -> str:
    """C11 が行う埋め込みを最小構成で再現する (symbols_svg は無加工)。"""
    uses = "\n".join(
        '  <svg {}="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        ' stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'
        ' aria-hidden="true"><use href="{}"></use></svg>'.format(H.KIND_ATTR, e["use_href"])
        for e in result[H.OUT_USED]
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"ja\">\n<body>\n"
        + result[H.OUT_SYMBOLS]
        + "\n"
        + uses
        + "\n</body>\n</html>\n"
    )


class SelfContainedContractTest(unittest.TestCase):
    def _result(self, tmp, names=("check", "clock", "target")):
        iset = H.write_icon_set(Path(tmp), H.make_icon_set())
        cfg = H.write_config(
            Path(tmp),
            H.make_config(
                sections=[H.section("s{}".format(i), section_icon=n) for i, n in enumerate(names)]
            ),
        )
        return H.sprite_result(self, H.run_sprite(self, cfg, iset, strict_style=True))

    def test_sc06_passes_on_the_embedded_sprite(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._result(tmp)
            H.assert_sc06_style(self, build_html(result))

    def test_sc07_one_to_one_in_the_assembled_html(self):
        """SC-07: D (symbol id 集合) と U (use 参照集合) が過不足なく一致する。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._result(tmp)
            collector = H.parse_svg(self, build_html(result))
            defined = H.symbol_ids(collector)
            referenced = [ref.lstrip("#") for ref in H.use_refs(collector)]
            self.assertEqual(
                sorted(defined), sorted(referenced),
                "SC-07 違反。定義 {} / 参照 {}".format(defined, referenced),
            )
            self.assertEqual(len(defined), len(set(defined)), "id 重複 (SC-07 c)")
            self.assertEqual(
                set(defined) - set(referenced), set(), "未使用 symbol (SC-07 a)"
            )
            self.assertEqual(
                set(referenced) - set(defined), set(), "未定義参照 (SC-07 b)"
            )

    def test_sc05_zero_emoji_in_the_assembled_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._result(tmp)
            H.assert_no_emoji(self, build_html(result), "組み立て HTML")

    def test_no_external_reference_in_the_sprite(self):
        """SC-01/SC-03 (CR-EXT): sprite は取得を発生させる参照を持たない。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._result(tmp)
            markup = result[H.OUT_SYMBOLS]
            for scheme in ("http://", "https://", "//cdn", "ftp://"):
                self.assertNotIn(scheme, markup, "sprite に外部参照 {} がある".format(scheme))

    def test_use_href_is_a_fragment_reference(self):
        """SC-07 は id 参照形だけを扱う。外部ファイル参照形の use_href を出さない。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._result(tmp)
            for entry in result[H.OUT_USED]:
                self.assertTrue(
                    entry["use_href"].startswith("#"),
                    "use_href が fragment でない: {}".format(entry["use_href"]),
                )
                self.assertNotIn(
                    ".svg", entry["use_href"],
                    "外部ファイル参照形の use_href は SC-01/SC-03 で落ちる: {}".format(entry),
                )

    def test_empty_sprite_still_satisfies_sc07(self):
        """AC-C15-6 の状態でも C16 の検査を通る (定義 0 / 参照 0)。"""
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            cfg = H.write_config(Path(tmp), H.make_config(sections=[H.section("s1")]))
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset, strict_style=True))
            html = build_html(result)
            collector = H.parse_svg(self, html)
            self.assertEqual(H.symbol_ids(collector), [])
            self.assertEqual(H.use_refs(collector), [])
            H.assert_no_emoji(self, html, "空 sprite の HTML")


class StrictStyleCallPathTest(unittest.TestCase):
    """argv: C01 の build 経路と C16 の検査経路は常に --strict-style を付けて呼ぶ。"""

    def test_strict_style_does_not_change_valid_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            plain = H.run_sprite(self, cfg, iset)
            strict = H.run_sprite(self, cfg, iset, strict_style=True)
            H.expect_exit(self, plain, 0)
            self.assertEqual(
                plain.stdout, strict.stdout,
                "様式が正しい入力では --strict-style で stdout が変わらない契約",
            )


if __name__ == "__main__":
    unittest.main()

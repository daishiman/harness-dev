"""AC-C15-4 / algorithm 7・13 / checklist C29: 同一入力から常にバイト一致。

決定論を壊す既知の経路を個別に固定する:
  (a) 使用アイコンの並びを参照出現順にする (algorithm 7 が禁じる)
  (b) 辞書のハッシュ順に依存した走査
  (c) json.dumps の形式ぶれ (ensure_ascii / indent / sort_keys)
  (d) 時刻・パス・環境値の出力への混入
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class SectionReorderTest(unittest.TestCase):
    """AC-C15-4: セクション順だけ入れ替えても symbols_svg の sha256 が一致する。"""

    def _config(self, order):
        return H.make_config(
            sections=[
                H.section("s-" + name, section_icon=name) for name in order
            ]
        )

    def test_sha256_matches_across_section_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            a = H.write_config(Path(tmp), self._config(["check", "clock", "target"]), "a.json")
            b = H.write_config(Path(tmp), self._config(["target", "check", "clock"]), "b.json")
            ra = H.sprite_result(self, H.run_sprite(self, a, iset))
            rb = H.sprite_result(self, H.run_sprite(self, b, iset))
            self.assertEqual(
                H.sha256_text(ra[H.OUT_SYMBOLS]),
                H.sha256_text(rb[H.OUT_SYMBOLS]),
                "並び替えで sprite のバイト列が変わっている (algorithm 7 の射影が無い)\n"
                "A:\n{}\nB:\n{}".format(ra[H.OUT_SYMBOLS], rb[H.OUT_SYMBOLS]),
            )

    def test_order_follows_the_icon_set_definition_order(self):
        """algorithm 7: 並び順は『正本 icons 配列の定義順』に射影する。"""
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(
                Path(tmp), H.make_icon_set(names=["zeta", "alpha", "mid"])
            )
            cfg = H.write_config(Path(tmp), self._config(["mid", "zeta", "alpha"]))
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            ids = H.symbol_ids(H.parse_svg(self, result[H.OUT_SYMBOLS]))
            self.assertEqual(
                ids, ["hbic-zeta", "hbic-alpha", "hbic-mid"],
                "正本定義順への射影になっていない (参照順や辞書順の疑い): {}".format(ids),
            )

    def test_manifest_order_matches_symbol_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=["zeta", "alpha", "mid"]))
            cfg = H.write_config(Path(tmp), self._config(["mid", "alpha", "zeta"]))
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            ids = H.symbol_ids(H.parse_svg(self, result[H.OUT_SYMBOLS]))
            self.assertEqual(ids, [e["symbol_id"] for e in result[H.OUT_USED]])


class RepeatRunTest(unittest.TestCase):
    def _fixture(self, tmp):
        iset = H.write_icon_set(Path(tmp), H.make_icon_set())
        cfg = H.write_config(
            Path(tmp),
            H.make_config(
                nav_icon="list",
                goal_chips=["star"],
                sections=[
                    H.section("s1", section_icon="check",
                              blocks=[H.block("list", items=["clock", "target"])]),
                    H.section("s2", blocks=[H.block("cards", cards=["folder"])]),
                ],
            ),
        )
        return cfg, iset

    def test_two_runs_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp)
            first = H.run_sprite(self, cfg, iset)
            second = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, first, 0)
            self.assertEqual(first.stdout, second.stdout, "2 回実行で stdout が変わる")
            self.assertEqual(first.stderr, second.stderr, "2 回実行で stderr が変わる")

    def test_hash_seed_does_not_change_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp)
            a = H.run_sprite(self, cfg, iset, env=H.clean_env(PYTHONHASHSEED="0"))
            b = H.run_sprite(self, cfg, iset, env=H.clean_env(PYTHONHASHSEED="12345"))
            H.expect_exit(self, a, 0)
            self.assertEqual(a.stdout, b.stdout, "走査が辞書のハッシュ順に依存している")

    def test_cwd_does_not_change_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp)
            a = H.run_sprite(self, cfg, iset)
            b = H.run_sprite(self, cfg, iset, cwd=tmp)
            H.expect_exit(self, a, 0)
            self.assertEqual(a.stdout, b.stdout, "cwd が出力へ漏れている")

    def test_each_format_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, iset = self._fixture(tmp)
            for fmt in H.FORMATS:
                a = H.run_sprite(self, cfg, iset, fmt=fmt)
                b = H.run_sprite(self, cfg, iset, fmt=fmt)
                self.assertEqual(a.stdout, b.stdout, "--format={} が非決定".format(fmt))


class SerializationFormatTest(unittest.TestCase):
    """algorithm 13: json.dumps(ensure_ascii=False, indent=2, sort_keys=False)。"""

    def _run(self, tmp):
        iset = H.write_icon_set(
            Path(tmp), H.make_icon_set(icons=[H.icon("check", title="完了")])
        )
        cfg = H.write_config(
            Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
        )
        return H.run_sprite(self, cfg, iset)

    def test_ensure_ascii_is_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp)
            H.expect_exit(self, proc, 0)
            text = H.out_text(proc)
            self.assertNotIn("\\u", text, "ensure_ascii=True で出力している\n" + text[:1000])

    def test_indent_is_two_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp)
            H.expect_exit(self, proc, 0)
            text = H.out_text(proc)
            data = json.loads(text)
            want = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
            self.assertEqual(
                text.rstrip("\n"), want,
                "json.dumps(ensure_ascii=False, indent=2, sort_keys=False) と一致しない",
            )

    def test_keys_are_not_sorted(self):
        """sort_keys=False。結果 JSON のキーは stdout 契約の宣言順で出る。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp)
            H.expect_exit(self, proc, 0)
            keys = list(json.loads(H.out_text(proc)).keys())
            self.assertEqual(
                keys[:4], [H.OUT_SYMBOLS, H.OUT_USED, H.OUT_UNUSED, H.OUT_SET_VERSION],
                "結果 JSON のキー順が stdout 契約と違う: {}".format(keys),
            )

    def test_newlines_are_lf_only(self):
        """algorithm 13: 改行 \\n 固定。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc = self._run(tmp)
            H.expect_exit(self, proc, 0)
            self.assertNotIn(b"\r", proc.stdout, "CRLF が混じっている")

    def test_symbols_svg_is_indented_by_two_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = H.sprite_result(self, self._run(tmp))
            lines = [ln for ln in result[H.OUT_SYMBOLS].split("\n") if ln.strip()]
            self.assertGreater(len(lines), 1, "symbols_svg が 1 行に潰れている")
            for line in lines:
                indent = len(line) - len(line.lstrip(" "))
                self.assertEqual(indent % 2, 0, "インデントが 2 スペース単位でない: {!r}".format(line))
                self.assertNotIn("\t", line, "タブインデントが混じっている: {!r}".format(line))


class NoEnvironmentLeakTest(unittest.TestCase):
    def test_no_absolute_paths_in_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            proc = H.run_sprite(self, cfg, iset)
            H.expect_exit(self, proc, 0)
            self.assertNotIn(tmp, H.out_text(proc), "stdout に絶対パスが漏れている")

    def test_no_timestamp_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            for key in result:
                self.assertNotIn(
                    key.lower(), ("generated_at", "timestamp", "date", "mtime"),
                    "時刻系フィールドは決定論を壊す: {}".format(key),
                )


if __name__ == "__main__":
    unittest.main()

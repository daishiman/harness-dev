"""AC-C15-1 / algorithm 5・7・10・11: 使用アイコンだけを抽出する。

checklist C11 (未使用 symbol 0 件) を「生成後に検査する」のではなく
「生成時に構造で満たす」ことを固定する。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _harness as H


class OnlyUsedIconsTest(unittest.TestCase):
    def test_three_referenced_icons_yield_exactly_three_symbols(self):
        """AC-C15-1: symbol 3 件ちょうど。正本の他 38 語は 1 件も含まれない。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp),
                H.make_config(
                    sections=[
                        H.section("s1", section_icon="check"),
                        H.section("s2", blocks=[H.block("list", items=["clock"])]),
                        H.section("s3", blocks=[H.block("cards", cards=["target"])]),
                    ]
                ),
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())  # 41 語すべて
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))

            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            ids = H.symbol_ids(collector)
            self.assertEqual(
                len(ids), 3,
                "使用 3 件に対し symbol {} 件: {}".format(len(ids), ids),
            )
            self.assertEqual(
                set(ids), {"hbic-check", "hbic-clock", "hbic-target"},
                "採番規則 hbic-<name> と使用集合が一致しない: {}".format(ids),
            )
            for name in H.VOCABULARY:
                if name in ("check", "clock", "target"):
                    continue
                self.assertNotIn(
                    "hbic-" + name, ids,
                    "未使用アイコン {} が sprite に混入 (checklist C11)".format(name),
                )

    def test_unused_in_set_lists_the_remaining_vocabulary(self):
        """algorithm 11: unused_in_set は診断情報で、SVG には一切含めない。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set(names=["check", "cross", "clock"]))
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            self.assertEqual(result[H.OUT_UNUSED], ["cross", "clock"])
            self.assertNotIn("cross", result[H.OUT_SYMBOLS])
            self.assertNotIn("clock", result[H.OUT_SYMBOLS])


class ScanScopeTest(unittest.TestCase):
    """algorithm 5: 走査対象は schema 上でアイコン名を取りうる全キーに限る。"""

    def test_all_declared_icon_keys_are_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp),
                H.make_config(
                    nav_icon="list",
                    goal_chips=["star"],
                    sections=[
                        H.section(
                            "s1",
                            section_icon="check",
                            blocks=[
                                H.block("text", block_icon="info"),
                                H.block("list", items=["clock"]),
                                H.block("cards", cards=["target"]),
                                H.block("tabs", tabs=["folder"]),
                            ],
                        )
                    ],
                ),
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            names = {e["name"] for e in result[H.OUT_USED]}
            self.assertEqual(
                names,
                {"list", "star", "check", "info", "clock", "target", "folder"},
                "algorithm 5 の走査キーに漏れがある: {}".format(sorted(names)),
            )

    def test_no_full_text_heuristic_search(self):
        """algorithm 5: ヒューリスティックな全文検索は行わない。

        本文中に語彙と同じ単語 (check / star) が現れても、それは icon キーでは
        ないのでアイコン参照として拾ってはならない。
        """
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.make_config(
                sections=[
                    H.section(
                        "s1",
                        blocks=[
                            {
                                "type": "text",
                                "body": "check の star を list する手順です",
                                "label": "check",
                                "name": "star",
                                "icon_hint": "clock",
                            }
                        ],
                    )
                ]
            )
            path = H.write_config(Path(tmp), cfg)
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            result = H.sprite_result(self, H.run_sprite(self, path, iset))
            self.assertEqual(
                result[H.OUT_USED], [],
                "icon キー以外の文字列をアイコン参照として拾っている: {}".format(result[H.OUT_USED]),
            )
            self.assertEqual(result[H.OUT_SYMBOLS], "")


class ManifestTest(unittest.TestCase):
    """algorithm 10: 参照表の各フィールド。"""

    def test_ref_count_and_ref_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp),
                H.make_config(
                    sections=[
                        H.section(
                            "s1",
                            blocks=[
                                H.block("list", items=["check", "check"]),
                                H.block("cards", cards=["check"]),
                            ],
                        )
                    ]
                ),
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            self.assertEqual(len(result[H.OUT_USED]), 1, "同名は一意化される (algorithm 7)")
            entry = result[H.OUT_USED][0]
            self.assertEqual(entry["ref_count"], 3, "ref_count が参照回数と一致しない: {}".format(entry))
            self.assertEqual(
                len(entry["ref_paths"]), 3,
                "ref_paths は参照ごとに 1 件 (走査順): {}".format(entry["ref_paths"]),
            )

    def test_ref_paths_are_key_paths_not_values(self):
        """algorithm 5: キーパス文字列 (例 sections[0].blocks[2].items[1].icon) を記録する。"""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp),
                H.make_config(
                    sections=[H.section("s1", blocks=[H.block("list", items=["check"])])]
                ),
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            path = result[H.OUT_USED][0]["ref_paths"][0]
            self.assertEqual(
                path, "sections[0].blocks[0].items[0].icon",
                "ref_paths がキーパス形式でない: {!r}".format(path),
            )

    def test_ref_paths_follow_document_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = H.write_config(
                Path(tmp),
                H.make_config(
                    sections=[
                        H.section("s1", blocks=[H.block("list", items=["check"])]),
                        H.section("s2", section_icon="check"),
                    ]
                ),
            )
            iset = H.write_icon_set(Path(tmp), H.make_icon_set())
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            paths = result[H.OUT_USED][0]["ref_paths"]
            self.assertEqual(
                paths,
                ["sections[0].blocks[0].items[0].icon", "sections[1].icon"],
                "ref_paths が入力順の深さ優先になっていない: {}".format(paths),
            )


class SymbolBodyTest(unittest.TestCase):
    """algorithm 9: symbol の中身 (path の並びと title)。"""

    def test_all_paths_are_emitted_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = ["M4 12l5 5L20 6", "M2 2h4", "M20 20l-3-3"]
            iset = H.write_icon_set(
                Path(tmp), H.make_icon_set(icons=[H.icon("check", paths=paths)])
            )
            cfg = H.write_config(
                Path(tmp), H.make_config(sections=[H.section("s1", section_icon="check")])
            )
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            collector = H.parse_svg(self, result[H.OUT_SYMBOLS])
            emitted = [attrs.get("d") for _t, attrs, _o in H.tags_named(collector, "path")]
            self.assertEqual(emitted, paths, "paths の順序が保存されていない: {}".format(emitted))

    def test_title_is_emitted_only_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            iset = H.write_icon_set(
                Path(tmp),
                H.make_icon_set(icons=[H.icon("check", title="完了"), H.icon("cross")]),
            )
            cfg = H.write_config(
                Path(tmp),
                H.make_config(
                    sections=[H.section("s1", section_icon="check"), H.section("s2", section_icon="cross")]
                ),
            )
            result = H.sprite_result(self, H.run_sprite(self, cfg, iset))
            markup = result[H.OUT_SYMBOLS]
            collector = H.parse_svg(self, markup)
            self.assertEqual(
                len(H.tags_named(collector, "title")), 1,
                "title を持つのは 1 件だけのはず:\n" + markup,
            )
            self.assertIn("完了", markup)


if __name__ == "__main__":
    unittest.main()

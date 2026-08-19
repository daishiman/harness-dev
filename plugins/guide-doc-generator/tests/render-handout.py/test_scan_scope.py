"""AC-C11-19 の走査範囲そのものを反例注入で固定する (P05-x-29)。

test_parts_catalog.py の SingleVocabularyTest は「リポジトリの現状に違反が無い」
ことしか言わない。走査範囲が狭すぎて**到達していない**だけの緑と、本当に違反が
無い緑は、そこからは区別できない。ここでは使い捨ての root へ両方向の反例を注入
して、鳴るべきものが鳴り・鳴るべきでないものが鳴らないことを実測する。

判断基準は P05-x-23 が確立した 1 本を変えない: 「そのテキストを何かが読むか
(実行される / 指示として読み込まれる)」。除外してよいのは次の 2 種類だけ。

  1. Python のコメントと docstring (実行されない)
  2. scripts/ 配下で何にも読み込まれない非実行ファイル (leaf の作業記録 .md)

`.json` は 1 にも 2 にも当たらない (プログラムが読む) ので走査対象である。

リポジトリ上の正本は一切触らない。scannable_sources(plugin_root=...) へ使い捨て
の root を渡すだけなので、モジュールグローバルの書き換えも復元手順も無い。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


def _sample_part_ids(count=3):
    """カタログから部品 id を借りる (テスト側に id を書かない)。"""
    ids = [p["id"] for p in H.catalog_parts() if H.PART_ID_PATTERN.fullmatch(p["id"])]
    if len(ids) < count:
        raise AssertionError(
            "カタログに B?? 形式の部品 id が %d 個未満で反例を作れない: %r" % (count, ids))
    return ids[:count]


class _ScratchRoot:
    """使い捨ての plugin root。`with` を抜けると丸ごと消えるので復元手順が要らない。"""

    def __init__(self):
        self._td = tempfile.TemporaryDirectory()
        self.path = Path(self._td.name)

    def __enter__(self):
        (self.path / "scripts").mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        self._td.cleanup()
        return False

    def write(self, relpath, text):
        target = self.path / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def offenders(self):
        return H.enumerated_part_id_offenders(self.path)


class ScanScopeCounterExampleTest(unittest.TestCase):
    """反例ごとに「期待」と「実測」を 1 対 1 で対応させる。"""

    # ------------------------------------------------------------------
    # RED を期待する方向: 何かが読むテキストへ部品 id の名簿を置いた場合
    # ------------------------------------------------------------------

    def test_part_id_roster_in_scripts_json_is_detected(self):
        """scripts/*.json の名簿は検出される (P05-x-29 が塞いだ抜け道)。"""
        a, b, c = _sample_part_ids()
        body = '{\n  "part_class_map": {\n    "%s": "a",\n    "%s": "b",\n    "%s": "c"\n  }\n}\n' % (a, b, c)
        with _ScratchRoot() as root:
            root.write("scripts/part-map.json", body)
            offenders = root.offenders()
        self.assertTrue(offenders, "scripts/part-map.json の部品 id 名簿が検出されていない")
        self.assertTrue(
            all("part-map.json" in o for o in offenders),
            "検出行が part-map.json 以外を指している: %r" % offenders,
        )

    def test_part_id_roster_in_unknown_scripts_suffix_is_detected(self):
        """未知の拡張子は既定で走査対象側へ倒す (allowlist だと素通りしていた)。"""
        a, b, _ = _sample_part_ids()
        with _ScratchRoot() as root:
            root.write("scripts/part-map.yaml", "map:\n  %s: a\n  %s: b\n" % (a, b))
            root.write("scripts/part-map.txt", "%s,%s\n" % (a, b))
            offenders = root.offenders()
        self.assertEqual(
            {"part-map.yaml", "part-map.txt"},
            {Path(o.split(":", 1)[0]).name for o in offenders},
            "未知拡張子のデータファイルが走査から漏れている: %r" % offenders,
        )

    def test_part_id_roster_in_executable_python_is_detected(self):
        """.py の実コード上の名簿は従来どおり検出される (回帰確認)。"""
        a, b, _ = _sample_part_ids()
        with _ScratchRoot() as root:
            root.write("scripts/gen.py", 'PART_CLASS_MAP = {"%s": "a", "%s": "b"}\n' % (a, b))
            offenders = root.offenders()
        self.assertTrue(offenders, ".py の実コード上の名簿が検出されていない")

    def test_part_id_roster_in_instruction_markdown_outside_scripts_is_detected(self):
        """skills/ 等の .md は指示として読み込まれるので拡張子に関係なく対象。"""
        a, b, _ = _sample_part_ids()
        with _ScratchRoot() as root:
            root.write("skills/run-x/SKILL.md", "使える部品は %s と %s。\n" % (a, b))
            offenders = root.offenders()
        self.assertTrue(offenders, "skills/ 配下の .md が走査から漏れている")

    # ------------------------------------------------------------------
    # GREEN を期待する方向: 何にも読み込まれない散文
    # ------------------------------------------------------------------

    def test_prose_in_scripts_markdown_is_not_detected(self):
        """scripts/*.md は leaf の作業記録で誰にも読み込まれない。"""
        a, b, _ = _sample_part_ids()
        with _ScratchRoot() as root:
            root.write(
                "scripts/RESOLUTION-P05-x-99.md",
                "# 記録\n\n%s の描画で %s と同じ経路を通ることを確認した。\n" % (a, b),
            )
            offenders = root.offenders()
        self.assertEqual([], offenders, "scripts/*.md の散文が誤検出された: %r" % offenders)

    def test_prose_in_python_docstring_and_comment_is_not_detected(self):
        """.py の docstring とコメントは実行されないので語彙になり得ない。"""
        a, b, _ = _sample_part_ids()
        source = (
            '"""%s の説明。\n\n%s とは別の経路を通る。\n"""\n\n'
            "# %s は %s の後に描画する\n"
            "VALUE = 1\n" % (a, b, a, b)
        )
        with _ScratchRoot() as root:
            root.write("scripts/render.py", source)
            offenders = root.offenders()
        self.assertEqual([], offenders, "docstring / コメントの散文が誤検出された: %r" % offenders)

    def test_referenced_scripts_markdown_is_detected(self):
        """同じ .md でも、走査対象が名前で参照していれば読まれる側なので対象。

        除外条件は拡張子ではなく「何にも読み込まれない」ことなので、参照が付いた
        瞬間に走査へ戻る必要がある。戻らないと「参照付きの .md へ名簿を置く」が
        次の抜け道になる。
        """
        a, b, _ = _sample_part_ids()
        with _ScratchRoot() as root:
            root.write("scripts/part-roster.md", "| %s | a |\n| %s | b |\n" % (a, b))
            root.write("scripts/loader.py", 'ROSTER = open("scripts/part-roster.md").read()\n')
            offenders = root.offenders()
        self.assertEqual(
            {"part-roster.md"},
            {Path(o.split(":", 1)[0]).name for o in offenders},
            "参照されている scripts/*.md が走査から漏れている: %r" % offenders,
        )

    def test_reference_from_python_prose_does_not_pull_markdown_in(self):
        """コメントで名前に触れただけは「読んでいる」に数えない (判定材料はマスク後)。"""
        a, b, _ = _sample_part_ids()
        with _ScratchRoot() as root:
            root.write("scripts/part-roster.md", "| %s | a |\n| %s | b |\n" % (a, b))
            root.write("scripts/loader.py", "# 詳細は part-roster.md を見よ\nV = 1\n")
            offenders = root.offenders()
        self.assertEqual([], offenders, "散文の言及で .md が引き込まれた: %r" % offenders)

    def test_generated_artifacts_are_not_scanned(self):
        """__pycache__ と .pyc は生成物。正本を直せば追随するので走査しない。"""
        a, b, _ = _sample_part_ids()
        with _ScratchRoot() as root:
            root.write("scripts/__pycache__/gen.cpython-311.pyc", '{"%s": "a"}\n' % a)
            root.write("scripts/__pycache__/stale.py", 'M = {"%s": "b"}\n' % b)
            offenders = root.offenders()
        self.assertEqual([], offenders, "生成物が走査されている: %r" % offenders)

    # ------------------------------------------------------------------
    # 両方向を同時に置いても互いを打ち消さないこと
    # ------------------------------------------------------------------

    def test_both_directions_coexist(self):
        """散文があっても名簿の検出は消えず、名簿があっても散文は誤検出されない。"""
        a, b, _ = _sample_part_ids()
        with _ScratchRoot() as root:
            root.write("scripts/part-map.json", '{"%s": "a", "%s": "b"}\n' % (a, b))
            root.write("scripts/NOTES.md", "%s と %s の話。\n" % (a, b))
            root.write("scripts/render.py", '"""%s の説明。"""\n\n# %s も同様\nV = 1\n' % (a, b))
            offenders = root.offenders()
        self.assertEqual(
            {"part-map.json"},
            {Path(o.split(":", 1)[0]).name for o in offenders},
            "両方向を同時に置くと結果が変わる: %r" % offenders,
        )


class ScanScopePolicyTest(unittest.TestCase):
    def test_scripts_exclusion_is_a_denylist_of_unread_suffixes(self):
        """除外は「読まれないと特定できるもの」だけ。allowlist へ戻したら赤にする。

        allowlist に戻すと未知の拡張子が既定で素通りするため、この不変条件を
        名前で固定しておく。
        """
        self.assertEqual((".md",), H.SCRIPT_UNREAD_SUFFIXES)
        self.assertFalse(
            hasattr(H, "SCRIPT_EXECUTABLE_SUFFIXES"),
            "走査対象の allowlist が復活している (denylist へ統一したはず)",
        )

    def test_scannable_sources_does_not_mutate_module_state(self):
        """使い捨て root を渡しても既定の走査対象は変わらない (復元手順が不要)。"""
        before = [p for p, _ in H.scannable_sources()]
        with _ScratchRoot() as root:
            root.write("scripts/part-map.json", '{"x": 1}\n')
            H.scannable_sources(root.path)
        self.assertEqual(before, [p for p, _ in H.scannable_sources()])


if __name__ == "__main__":
    unittest.main()

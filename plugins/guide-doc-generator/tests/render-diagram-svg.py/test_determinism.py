"""同一入力の再現性と標準ライブラリのみ (AC-C14-1 / AC-C14-2 / AC-C14-8 / checklist C9・C27・C29)。"""

import hashlib
import re
import tempfile
import unittest
from pathlib import Path

import _harness as H

# AC-C14-8 が許す標準ライブラリ (algorithm が名指ししているもの + 一般的な stdlib)
ALLOWED_IMPORTS = {
    "json", "sys", "os", "argparse", "html", "unicodedata", "collections",
    "math", "pathlib", "typing", "dataclasses", "re", "io", "textwrap",
    "functools", "itertools", "__future__",
}

FORBIDDEN_IMPORTS = {"yaml", "lxml", "jinja2", "requests", "numpy", "svgwrite", "cairosvg"}

# 手順 11: 乱数・時刻・オブジェクト id を一切使わない
NON_DETERMINISTIC_PATTERNS = (
    r"\brandom\.",
    r"\buuid\b",
    r"\btime\.(time|monotonic|perf_counter)\b",
    r"\bdatetime\.(now|today|utcnow)\b",
    r"(?<![A-Za-z0-9_])id\(",
    r"\bos\.urandom\b",
    r"\bsecrets\.",
)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ByteReproducibilityTest(unittest.TestCase):
    """AC-C14-2: 同一 fixture を 2 回実行して stdout の sha256 が一致する。"""

    def test_two_runs_are_byte_identical_for_every_pattern(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                spec = H.spec_for(pattern)
                with tempfile.TemporaryDirectory() as td:
                    first = H.render(td, spec)
                    second = H.render(td, spec)
                self.assertEqual(first.returncode, 0, first)
                self.assertEqual(second.returncode, 0, second)
                self.assertEqual(_sha(first.stdout), _sha(second.stdout))

    def test_hash_seed_does_not_change_output(self):
        """辞書順依存が無いこと (PYTHONHASHSEED を変えても同一)。"""
        spec = H.compare_spec()
        with tempfile.TemporaryDirectory() as td:
            path = H.write_diagram(Path(td) / "d.json", spec)
            args = ["--diagram", path, "--pattern", "compare"]
            a = H.run_diagram(args, env_extra={"PYTHONHASHSEED": "1"})
            b = H.run_diagram(args, env_extra={"PYTHONHASHSEED": "12345"})
        self.assertEqual(a.returncode, 0, a)
        self.assertEqual(b.returncode, 0, b)
        self.assertEqual(a.stdout_bytes, b.stdout_bytes)

    def test_timezone_does_not_change_output(self):
        spec = H.flow_spec()
        with tempfile.TemporaryDirectory() as td:
            path = H.write_diagram(Path(td) / "d.json", spec)
            args = ["--diagram", path, "--pattern", "flow"]
            a = H.run_diagram(args, env_extra={"TZ": "UTC"})
            b = H.run_diagram(args, env_extra={"TZ": "Asia/Tokyo"})
        self.assertEqual(a.returncode, 0, a)
        self.assertEqual(a.stdout_bytes, b.stdout_bytes)

    def test_cwd_does_not_change_output(self):
        spec = H.flow_spec()
        with tempfile.TemporaryDirectory() as td:
            path = H.write_diagram(Path(td) / "d.json", spec)
            other = Path(td) / "elsewhere"
            other.mkdir()
            args = ["--diagram", path, "--pattern", "flow"]
            a = H.run_diagram(args, cwd=H.REPO_ROOT)
            b = H.run_diagram(args, cwd=other)
        self.assertEqual(a.returncode, 0, a)
        self.assertEqual(a.stdout_bytes, b.stdout_bytes)

    def test_key_order_in_input_does_not_change_output(self):
        """object_pairs_hook で入力順を保持しても、意味が同じなら出力は同じ。"""
        spec = H.flow_spec()
        reordered = {k: spec[k] for k in reversed(list(spec.keys()))}
        with tempfile.TemporaryDirectory() as td:
            a = H.render(td, spec)
            b = H.render(td, reordered)
        self.assertEqual(a.returncode, 0, a)
        self.assertEqual(b.returncode, 0, b)
        self.assertEqual(a.stdout_bytes, b.stdout_bytes)

    def test_output_is_valid_utf8(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        res.stdout_bytes.decode("utf-8")


class GoldenSvgTest(unittest.TestCase):
    """AC-C14-1: 9 パターンの最小 fixture が golden とバイト一致する。

    golden は実装後に `python3 record_goldens.py` で一度だけ記録する。
    記録前は「golden 未記録」として赤のままにする — 実装が golden を後から
    自分の出力へ合わせて書き換えても、本ファイル群の構造検査は独立に効く。
    """

    def test_golden_directory_exists(self):
        self.assertTrue(
            H.GOLDEN_DIR.is_dir(),
            "golden 未記録: %s (実装後に record_goldens.py で記録する)" % H.GOLDEN_DIR,
        )

    def test_golden_matches_for_every_pattern(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                golden = H.GOLDEN_DIR / ("%s.svg" % pattern)
                self.assertTrue(golden.is_file(), "golden 未記録: %s" % golden)
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                self.assertEqual(res.stdout_bytes, golden.read_bytes())


class StdlibOnlyTest(unittest.TestCase):
    """AC-C14-8 / checklist C27: 標準ライブラリのみ。"""

    def test_no_third_party_imports(self):
        extra = sorted(H.imported_modules() - ALLOWED_IMPORTS)
        self.assertEqual(extra, [], "標準ライブラリ以外を import している: %r" % extra)

    def test_no_yaml_import(self):
        self.assertNotIn("yaml", H.imported_modules())

    def test_no_known_forbidden_imports(self):
        hit = sorted(H.imported_modules() & FORBIDDEN_IMPORTS)
        self.assertEqual(hit, [])

    def test_imports_are_parseable_as_python(self):
        import ast

        ast.parse(H.source_text())


class NonDeterminismSourceTest(unittest.TestCase):
    """手順 11: 乱数・時刻・オブジェクト id をソースへ持ち込まない。"""

    def test_source_has_no_nondeterministic_calls(self):
        src = H.source_text()
        hits = [p for p in NON_DETERMINISTIC_PATTERNS if re.search(p, src)]
        self.assertEqual(hits, [], "非決定の源: %r" % hits)

    def test_internal_ids_follow_the_hbdg_scheme(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec())
        self.assertEqual(res.returncode, 0, res)
        for value in H.all_ids(res.stdout):
            self.assertRegex(value, r"^hbdg-[A-Za-z0-9_-]+$", "手順 11 の採番規則")

    def test_diagram_id_is_used_as_the_id_prefix_when_given(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.flow_spec(id="alpha"))
        self.assertEqual(res.returncode, 0, res)
        ids = H.all_ids(res.stdout)
        for value in ids:
            self.assertTrue(value.startswith("hbdg-alpha-"), "id=%r" % value)

    def test_id_prefix_falls_back_to_the_pattern_name(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.without(H.flow_spec(), "id"))
        self.assertEqual(res.returncode, 0, res)
        for value in H.all_ids(res.stdout):
            self.assertTrue(value.startswith("hbdg-flow-"), "id=%r" % value)

    def test_ids_are_unique_within_one_fragment(self):
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.cycle_spec())
        self.assertEqual(res.returncode, 0, res)
        ids = H.all_ids(res.stdout)
        self.assertEqual(len(ids), len(set(ids)), "id が重複している: %r" % ids)

    def test_two_diagrams_with_different_ids_do_not_collide(self):
        with tempfile.TemporaryDirectory() as td:
            a = H.render(td, H.flow_spec(id="alpha"))
            b = H.render(td, H.flow_spec(id="beta"))
        self.assertEqual(a.returncode, 0, a)
        self.assertEqual(b.returncode, 0, b)
        self.assertEqual(set(H.all_ids(a.stdout)) & set(H.all_ids(b.stdout)), set())


class CoordinateRoundingTest(unittest.TestCase):
    """手順 7: すべての座標を整数 px へ丸める (浮動小数の表記揺れを排する)。"""

    COORD_ATTRS = ("x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
                   "width", "height")

    def test_no_floating_point_coordinates(self):
        for pattern in H.PATTERNS:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as td:
                    res = H.render(td, H.spec_for(pattern))
                self.assertEqual(res.returncode, 0, res)
                for el in H.parse(res.stdout):
                    if el.tag == "svg":
                        continue
                    for attr in self.COORD_ATTRS:
                        if attr not in el.attrs:
                            continue
                        value = el.attrs[attr]
                        if value.endswith("em") or value.endswith("%"):
                            continue
                        self.assertRegex(
                            value, r"^-?\d+$",
                            "<%s %s=%r> が整数でない" % (el.tag, attr, value),
                        )

    def test_path_data_has_no_long_float_tails(self):
        """円弧座標も小数第 3 位までで丸める (手順 7 cycle)。"""
        with tempfile.TemporaryDirectory() as td:
            res = H.render(td, H.cycle_spec())
        self.assertEqual(res.returncode, 0, res)
        for d in H.all_attr_values(res.stdout, "d"):
            for m in re.finditer(r"-?\d+\.(\d+)", d):
                self.assertLessEqual(len(m.group(1)), 3, "小数第 4 位以降がある: %r" % d)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

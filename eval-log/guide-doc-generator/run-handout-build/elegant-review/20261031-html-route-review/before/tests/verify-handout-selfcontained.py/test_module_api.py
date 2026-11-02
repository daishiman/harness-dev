"""module_api / 単一正本の不変条件を赤で固定する。

- module_api: scan_external_references / scan_emoji の公開点 (RESOLUTION-P03 X-01/X-02)
- AC-C16-11: C10 hook と C16 が同一入力に同一判定を返すこと (canonical_rules.invariant)
- AC-C16-12: C10 / C11 のソースに規則本文の複製が無いこと
"""

import json
import re
import subprocess
import sys
import unittest

import hb_c16
from hb_c16 import EXTERNAL_REF_DETECTIONS, HOOK_C10, RENDER_C11, C16TestCase, load_hb


def field(violation, name):
    """Violation は dict でも属性オブジェクトでもよい。"""
    if isinstance(violation, dict):
        if name not in violation:
            raise AssertionError("Violation に {} が無い: {!r}".format(name, violation))
        return violation[name]
    if not hasattr(violation, name):
        raise AssertionError("Violation に {} が無い: {!r}".format(name, violation))
    return getattr(violation, name)


class TestModuleLoading(unittest.TestCase):

    def test_loadable_by_spec_from_file_location(self):
        mod = load_hb()
        self.assertIsNotNone(mod)

    def test_exports_scan_external_references(self):
        self.assertTrue(callable(getattr(load_hb(), "scan_external_references", None)),
                        "module_api.exports に scan_external_references(html_text) が要る")

    def test_exports_scan_emoji(self):
        self.assertTrue(callable(getattr(load_hb(), "scan_emoji", None)),
                        "module_api.exports に scan_emoji(text) が要る")

    def test_import_does_not_execute_cli(self):
        """module として読み込んだだけで検査や終了をしない。"""
        mod = load_hb()
        self.assertTrue(hasattr(mod, "scan_emoji"))


class TestScanExternalReferences(unittest.TestCase):

    def setUp(self):
        self.scan = load_hb().scan_external_references

    def test_text_node_url_returns_no_violation(self):
        self.assertEqual([], list(self.scan("<p>https://portal.example.com を参照</p>")),
                         "取得を発生させない text node の URL は返さない (CR-EXT)")

    def test_href_url_returns_violation(self):
        rows = list(self.scan('<a href="https://example.com/x">x</a>'))
        self.assertEqual(1, len(rows), rows)

    def test_violation_detection_id_is_in_sc01_to_sc04(self):
        rows = list(self.scan('<a href="https://example.com/x">x</a>'))
        self.assertIn(field(rows[0], "detection_id"), EXTERNAL_REF_DETECTIONS)

    def test_violation_has_position_and_evidence(self):
        rows = list(self.scan('<a href="https://example.com/x">x</a>'))
        self.assertIsInstance(field(rows[0], "line"), int)
        self.assertIsInstance(field(rows[0], "col"), int)
        self.assertTrue(field(rows[0], "evidence"))

    def test_data_uri_returns_no_violation(self):
        self.assertEqual([], list(self.scan('<img src="data:image/png;base64,AAAA" alt="a">')))

    def test_svg_namespace_returns_no_violation(self):
        self.assertEqual([], list(self.scan('<svg xmlns="http://www.w3.org/2000/svg"></svg>')))

    def test_style_url_returns_violation(self):
        self.assertTrue(list(self.scan("<style>.a{background:url(https://x.example/a.png)}</style>")))

    def test_at_import_returns_violation(self):
        self.assertTrue(list(self.scan("<style>@import url(data:text/css,);</style>")))


class TestScanEmoji(unittest.TestCase):

    def setUp(self):
        self.scan = load_hb().scan_emoji

    def test_plain_text_input_is_supported(self):
        """HTML 以外の素のテキスト (handout-config.json の値など) にも掛けられる。"""
        self.assertEqual([], list(self.scan("研修資料 2026 年度版")))

    def test_star_is_not_emoji(self):
        self.assertEqual([], list(self.scan("\u2605 \u2606 \u2714 \u266a \u25a0 \u00a9")))

    def test_pointing_hand_is_emoji(self):
        rows = list(self.scan("\U0001F449"))
        self.assertEqual(1, len(rows), rows)

    def test_codepoints_field_is_populated(self):
        rows = list(self.scan("\U0001F449"))
        self.assertIn("U+1F449", str(field(rows[0], "codepoints")))

    def test_layer2_requires_vs16(self):
        self.assertEqual([], list(self.scan("\u2699")))
        self.assertTrue(list(self.scan("\u2699\ufe0f")))

    def test_detection_id_is_sc05(self):
        rows = list(self.scan("\U0001F449"))
        self.assertEqual("SC-05", field(rows[0], "detection_id"))

    def test_no_block_denylist_in_source(self):
        """CR-EMOJI: ブロック丸ごとの denylist (U+2600-U+27BF 等) を持たない。"""
        src = hb_c16.SCRIPT.read_text(encoding="utf-8") if hb_c16.SCRIPT.exists() else ""
        hb_c16.require_script()
        for banned in ("0x2600, 0x27BF", "0x2600,0x27bf", "(0x2600, 0x27bf)", "(0x2b00, 0x2bff)"):
            self.assertNotIn(banned.lower(), src.lower(),
                             "ブロック丸ごとの denylist を使わない: {}".format(banned))


class TestCliAndModuleShareTheSameJudgement(C16TestCase):
    """constraint: CLI 側にだけ存在する判定分岐を作らない。"""

    CASES = [
        '<p>https://portal.example.com を参照</p>',
        '<a href="https://example.com/x">x</a>',
        "<p>\u2605 \u2714 \u00a9</p>",
        '<p>\U0001F449</p>',
    ]

    def test_module_and_cli_agree_on_external_refs(self):
        mod = load_hb()
        for case in self.CASES:
            html = hb_c16.good_html(extra=case)
            res = self.check(html)
            cli_has = any(res.summary()[d]["violations"] for d in EXTERNAL_REF_DETECTIONS)
            self.assertEqual(bool(list(mod.scan_external_references(html))), cli_has,
                             "CLI と module_api の判定が食い違う: {!r}".format(case))

    def test_module_and_cli_agree_on_emoji(self):
        mod = load_hb()
        for case in self.CASES:
            html = hb_c16.good_html(extra=case)
            res = self.check(html)
            self.assertEqual(bool(list(mod.scan_emoji(html))),
                             bool(res.summary()["SC-05"]["violations"]),
                             "CLI と module_api の判定が食い違う: {!r}".format(case))


# --------------------------------------------------------------------------
# AC-C16-11: C10 hook との判定一致
# --------------------------------------------------------------------------

PARITY_FIXTURES = [
    ("text-node-url", '<p>配布元は https://portal.example.com です</p>', False),
    ("href-url", '<p><a href="https://portal.example.com">ポータル</a></p>', True),
    ("cdn-script", '<script src="https://cdn.example/a.js"></script>', True),
    ("data-uri-img", '<img src="data:image/png;base64,AAAA" alt="a">', False),
    ("relative-script-src", '<script src="./app.js"></script>', True),
    ("inline-script", "<script>var a = 1;</script>", False),
    ("iframe", '<iframe src="./inner.html"></iframe>', True),
    ("star-u2605", "<p>\u2605 重要</p>", False),
    ("check-u2714-plain", "<p>\u2714 完了</p>", False),
    ("copyright-plain", "<p>\u00a9 2026</p>", False),
    ("copyright-vs16", "<p>\u00a9\ufe0f 2026</p>", True),
    ("gear-plain", "<p>\u2699 設定</p>", False),
    ("gear-vs16", "<p>\u2699\ufe0f 設定</p>", True),
    ("pointing-hand", "<p>\U0001F449 ここ</p>", True),
    ("flag-jp", "<p>\U0001F1EF\U0001F1F5</p>", True),
]


class TestC10ParityBase(C16TestCase):
    """C10 hook を PostToolUse 契約どおりに起動して判定を突き合わせる。"""

    def run_hook(self, html_text):
        if not HOOK_C10.exists():
            raise AssertionError("未実装: {} (C10)".format(HOOK_C10))
        outdir = self.tmp / "2026-08-17-lecture-自己完結性の検査"
        outdir.mkdir(exist_ok=True)
        (outdir / "handout-config.json").write_text("{}", encoding="utf-8")
        target = outdir / "handout.html"
        target.write_text(html_text, encoding="utf-8")
        payload = {"tool_name": "Write", "hook_event_name": "PostToolUse",
                   "tool_input": {"file_path": str(target)}, "cwd": str(self.tmp)}
        proc = subprocess.run([sys.executable, str(HOOK_C10)], input=json.dumps(payload),
                              capture_output=True, text=True, timeout=120)
        return proc

    def c16_violates(self, html_text):
        mod = load_hb()
        return bool(list(mod.scan_external_references(html_text))) or bool(list(mod.scan_emoji(html_text)))

    def c16_codepoints(self, html_text):
        mod = load_hb()
        cps = set()
        for v in mod.scan_emoji(html_text):
            for cp in re.findall(r"U\+[0-9A-Fa-f]{4,6}", str(field(v, "codepoints"))):
                cps.add(cp.upper())
        return cps


def _make_parity_test(name, snippet, expect_violation):
    def test(self):
        html = hb_c16.good_html(extra=snippet)
        c16 = self.c16_violates(html)
        self.assertEqual(expect_violation, c16,
                         "C16 の判定が仕様と違う ({}) ".format(name))
        proc = self.run_hook(html)
        hook_blocked = proc.returncode == 2
        self.assertEqual(c16, hook_blocked,
                         "C10 と C16 の判定が一致しない ({}): hook rc={} stderr={!r}".format(
                             name, proc.returncode, proc.stderr))
    test.__name__ = "test_parity_" + name.replace("-", "_")
    test.__doc__ = "AC-C16-11: {} で C10 と C16 の違反有無が一致する".format(name)
    return test


def _make_codepoint_parity_test(name, snippet):
    def test(self):
        html = hb_c16.good_html(extra=snippet)
        expected = self.c16_codepoints(html)
        self.assertTrue(expected, "この fixture は絵文字違反を持つ前提 ({})".format(name))
        proc = self.run_hook(html)
        reported = {cp.upper() for cp in re.findall(r"U\+[0-9A-Fa-f]{4,6}", proc.stderr)}
        self.assertEqual(expected, reported,
                         "C10 が報告する違反コードポイントが C16 と一致しない ({})".format(name))
    test.__name__ = "test_codepoint_parity_" + name.replace("-", "_")
    test.__doc__ = "AC-C16-11: {} で違反コードポイントが完全一致する".format(name)
    return test


class TestAcC16_11(TestC10ParityBase):
    pass


for _name, _snippet, _expect in PARITY_FIXTURES:
    _t = _make_parity_test(_name, _snippet, _expect)
    setattr(TestAcC16_11, _t.__name__, _t)

for _name, _snippet in [("copyright-vs16", "<p>\u00a9\ufe0f 2026</p>"),
                        ("gear-vs16", "<p>\u2699\ufe0f 設定</p>"),
                        ("pointing-hand", "<p>\U0001F449 ここ</p>"),
                        ("flag-jp", "<p>\U0001F1EF\U0001F1F5</p>")]:
    _t = _make_codepoint_parity_test(_name, _snippet)
    setattr(TestAcC16_11, _t.__name__, _t)


class TestAcC16_12(unittest.TestCase):
    """C10 / C11 のソースに規則本文の複製が無いこと。"""

    SCHEME_LITERALS = ['"http://"', "'http://'", '"https://"', "'https://'",
                       '"ftp://"', '"wss://"']
    CODEPOINT_LITERALS = [r"0x1F600", r"0x1f600", r"0x2705", r"0x1F449", r"\U0001F600"]

    def _source(self, path, label):
        if not path.exists():
            raise AssertionError("未実装: {} ({})".format(path, label))
        return path.read_text(encoding="utf-8")

    def test_c10_has_no_scheme_enumeration(self):
        src = self._source(HOOK_C10, "C10")
        for lit in self.SCHEME_LITERALS:
            self.assertNotIn(lit, src, "C10 に外部スキームの列挙を置かない: {}".format(lit))

    def test_c10_has_no_codepoint_enumeration(self):
        src = self._source(HOOK_C10, "C10")
        for lit in self.CODEPOINT_LITERALS:
            self.assertNotIn(lit, src, "C10 に絵文字コードポイントの列挙を置かない: {}".format(lit))

    def test_c10_calls_the_canonical_functions(self):
        src = self._source(HOOK_C10, "C10")
        self.assertIn("scan_external_references", src)
        self.assertIn("scan_emoji", src)

    def test_c10_loads_c16_as_module(self):
        src = self._source(HOOK_C10, "C10")
        self.assertIn("spec_from_file_location", src)
        self.assertIn("verify-handout-selfcontained.py", src)

    def test_c11_has_no_scheme_enumeration(self):
        src = self._source(RENDER_C11, "C11")
        for lit in self.SCHEME_LITERALS:
            self.assertNotIn(lit, src, "C11 に外部スキームの列挙を置かない: {}".format(lit))

    def test_c11_has_no_codepoint_enumeration(self):
        src = self._source(RENDER_C11, "C11")
        for lit in self.CODEPOINT_LITERALS:
            self.assertNotIn(lit, src, "C11 に絵文字コードポイントの列挙を置かない: {}".format(lit))

    def test_c11_calls_the_canonical_functions(self):
        src = self._source(RENDER_C11, "C11")
        self.assertIn("scan_external_references", src)


if __name__ == "__main__":
    unittest.main()

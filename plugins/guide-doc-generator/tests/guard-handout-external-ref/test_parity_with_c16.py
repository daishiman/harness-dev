"""C10 と C16 の判定一致 (rule_delegation.invariant / AC-C16-11 と対をなす)。

正本:
  - hook-brief-C10.json#rule_delegation.invariant
  - script-brief-C16.json#canonical_rules.invariant / #acceptance_checks[AC-C16-11]

固定する不変条件:
  同一入力に対し、C10 の block 有無と C16 の scan_* の違反有無が全件一致し、
  絵文字違反のコードポイント集合も完全一致する。

期待値をこのテストへ直書きしないのが要点である。期待値は C16 module_api の
戻り値そのものとし、C10 をそれと突き合わせる。こうしておけば規則が将来
CR-EXT / CR-EMOJI 側で変わっても、このテストは規則の複製として腐らない。
"""

import re

from hb_c10 import C10TestCase, D1, D2, clean_html, load_c16

#: 境界事例 fixture (AC-C16-11 の PARITY_FIXTURES と同じ集合)
PARITY_FIXTURES = [
    ("text-node-url", '<p>配布元は https://portal.example.com です</p>'),
    ("href-url", '<p><a href="https://portal.example.com">ポータル</a></p>'),
    ("cdn-script", '<script src="https://cdn.example/a.js"></script>'),
    ("data-uri-img", '<img src="data:image/png;base64,AAAA" alt="a">'),
    ("page-anchor", '<a href="#s1">1. 導入</a>'),
    ("svg-namespace", '<svg xmlns="http://www.w3.org/2000/svg"></svg>'),
    ("star-u2605", "<p>★ 重要</p>"),
    ("white-star-u2606", "<p>☆ 参考</p>"),
    ("check-u2714-plain", "<p>✔ 完了</p>"),
    ("copyright-plain", "<p>© 2026</p>"),
    ("copyright-vs16", "<p>©️ 2026</p>"),
    ("gear-plain", "<p>⚙ 設定</p>"),
    ("gear-vs16", "<p>⚙️ 設定</p>"),
    ("note-u266a", "<p>♪ BGM あり</p>"),
    ("square-u25a0", "<p>■ 前提</p>"),
    ("pointing-hand", "<p>\U0001F449 ここ</p>"),
    ("white-check-u2705", "<p>✅ 完了</p>"),
    ("flag-jp", "<p>\U0001F1EF\U0001F1F5</p>"),
    ("keycap-one", "<p>1️⃣</p>"),
    ("both-d1-and-d2", '<p><a href="https://x.example">\U0001F680</a></p>'),
]

CODEPOINT_RE = re.compile(r"U\+[0-9A-Fa-f]{4,6}")


def _field(violation, name):
    if isinstance(violation, dict):
        if name not in violation:
            raise AssertionError("Violation に {} が無い: {!r}".format(name, violation))
        return violation[name]
    if not hasattr(violation, name):
        raise AssertionError("Violation に {} が無い: {!r}".format(name, violation))
    return getattr(violation, name)


class ParityBase(C10TestCase):

    def c16_external(self, html_text):
        return list(load_c16().scan_external_references(html_text))

    def c16_emoji(self, html_text):
        return list(load_c16().scan_emoji(html_text))

    def c16_codepoints(self, html_text):
        cps = set()
        for v in self.c16_emoji(html_text):
            for cp in CODEPOINT_RE.findall(str(_field(v, "codepoints"))):
                cps.add(cp.upper())
        return cps


def _make_verdict_test(name, snippet):
    def test(self):
        html = clean_html(extra=snippet)
        c16_violates = bool(self.c16_external(html)) or bool(self.c16_emoji(html))
        res = self.run_on(html)
        self.assertIn(res.rc, (0, 2),
                      "契約上の exit code は 0 か 2 のみ ({})\n{}".format(name, res))
        self.assertEqual(c16_violates, res.rc == 2,
                         "C10 と C16 の判定が一致しない ({})\n{}".format(name, res))
    test.__name__ = "test_verdict_" + name.replace("-", "_")
    test.__doc__ = "AC-C16-11: {} で違反有無が一致する".format(name)
    return test


def _make_detection_test(name, snippet):
    def test(self):
        html = clean_html(extra=snippet)
        if self.c16_external(html):
            res = self.run_on(html)
            self.assertTrue(res.mentions(D1),
                            "C16 が外部参照違反を返すのに C10 が {} を出さない ({})\n{}".format(
                                D1, name, res))
        if self.c16_emoji(html):
            res = self.run_on(html)
            self.assertTrue(res.mentions(D2),
                            "C16 が絵文字違反を返すのに C10 が {} を出さない ({})\n{}".format(
                                D2, name, res))
    test.__name__ = "test_detection_id_" + name.replace("-", "_")
    test.__doc__ = "AC-C16-11: {} で報告する detection の種類が一致する".format(name)
    return test


def _make_codepoint_test(name, snippet):
    def test(self):
        html = clean_html(extra=snippet)
        expected = self.c16_codepoints(html)
        if not expected:
            self.skipTest("この fixture は絵文字違反を持たない")
        res = self.run_on(html)
        reported = {cp.upper() for cp in CODEPOINT_RE.findall(res.err)}
        self.assertEqual(expected, reported,
                         "C10 が報告する違反コードポイントが C16 と一致しない ({})\n{}".format(
                             name, res))
    test.__name__ = "test_codepoints_" + name.replace("-", "_")
    test.__doc__ = "AC-C16-11: {} で違反コードポイントが完全一致する".format(name)
    return test


class TestVerdictParity(ParityBase):
    """違反の有無が全件一致する。"""


class TestDetectionIdParity(ParityBase):
    """どちらの規則で落ちたかが一致する。"""


class TestCodepointParity(ParityBase):
    """絵文字違反のコードポイントが完全一致する。"""


for _name, _snippet in PARITY_FIXTURES:
    _t = _make_verdict_test(_name, _snippet)
    setattr(TestVerdictParity, _t.__name__, _t)
    _t = _make_detection_test(_name, _snippet)
    setattr(TestDetectionIdParity, _t.__name__, _t)
    _t = _make_codepoint_test(_name, _snippet)
    setattr(TestCodepointParity, _t.__name__, _t)


class TestNoOneSidedFailure(ParityBase):
    """片方だけが FAIL/PASS になる状態は設計上存在しない (invariant の言い換え)。"""

    def test_c16_clean_implies_c10_pass(self):
        html = clean_html(extra="<p>★ 重要 / ✔ 完了 / © 2026 / https://example.com</p>")
        self.assertEqual([], self.c16_external(html), "この fixture は C16 で clean な前提")
        self.assertEqual([], self.c16_emoji(html), "この fixture は C16 で clean な前提")
        self.assertPassSilently(self.run_on(html), "C16 が clean なら C10 も素通し")

    def test_c16_dirty_implies_c10_block(self):
        html = clean_html(extra='<link rel="stylesheet" href="https://x.example/a.css">')
        self.assertTrue(self.c16_external(html), "この fixture は C16 で違反な前提")
        res = self.run_on(html)
        self.assertEqual(2, res.rc, "C16 が違反なら C10 も block\n{}".format(res))

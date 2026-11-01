"""目次を左の柱へ置くことの受入テスト (利用者要求 R26 / 2026-08-19)。

要求は 3 つ。「ヘッダーにある目次をサイドバーへ」「スクロールしても常に見える」
「今の内容のまま左揃え」。これを 1 つの資料の HTML でなく **プラグインの側**で
固定するため、次の 4 点を検査する。

1. **置き場所は正本から来る**: `config/handout-visual-policy.json#nav.layout` /
   `nav.sidebar_width_px` / `nav.collapse_below_px` が単一正本であり、描画側に
   既定値を持たない (欠けたら生成が落ちる)。数値をスクリプトへ焼くと、次に
   作る資料へ同じ見た目が伝わらない。
2. **常に見える**: 柱は sticky のまま。スクロール量に依らず消えない。
3. **左揃え**: 札は柱の幅いっぱいに伸び、行頭が縦一線に揃う。
4. **中身は変えない**: 札の数・順序・ラベル・連番は帯だったときと同じ。
   見た目の移動が目次の内容を書き換えてはならない。
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _harness as H

VISUAL_POLICY = H.PLUGIN_ROOT / "config" / "handout-visual-policy.json"


def canon_nav():
    return json.loads(VISUAL_POLICY.read_text(encoding="utf-8"))["nav"]


def render():
    cfg = H.base_config()
    with tempfile.TemporaryDirectory() as tmp:
        res, html_text, _ = H.render_html(tmp, cfg)
    return res, html_text, cfg


def header_of(html_text):
    for el in H.parse(html_text):
        classes = el.attrs.get("class") or ""
        if el.tag == "header" and "pop-header" in classes.split():
            return el
    return None


class CanonOwnsTheLayout(unittest.TestCase):

    def test_canon_declares_the_sidebar(self):
        nav = canon_nav()
        self.assertEqual("sidebar", nav["layout"])
        self.assertIsInstance(nav["sidebar_width_px"], int)
        self.assertIsInstance(nav["collapse_below_px"], int)

    def test_rendered_css_uses_the_canon_numbers(self):
        nav = canon_nav()
        res, html_text, _ = render()
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertIn("--side-nav-w: {}px".format(nav["sidebar_width_px"]), html_text)
        self.assertIn("min-width: {}px".format(nav["collapse_below_px"]), html_text)

    def test_missing_canon_key_stops_the_render(self):
        """既定値へ落ちない。正本を欠いた状態で「それらしい幅」で描かない。"""
        H.require_script()
        with tempfile.TemporaryDirectory() as td:
            clone = Path(td) / "plugin"
            shutil.copytree(H.PLUGIN_ROOT, clone, symlinks=True)
            policy_path = clone / "config" / "handout-visual-policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            del policy["nav"]["sidebar_width_px"]
            policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
            cfg_path = H.write_config(Path(td) / "config.json", H.base_config())
            out = Path(td) / "handout.html"
            proc = subprocess.run(
                [sys.executable, str(clone / "scripts" / "render-handout.py"),
                 "--config", str(cfg_path), "--out", str(out)],
                capture_output=True, text=True,
                env={**os.environ, "HB_ROOT": str(clone)},
            )
        self.assertNotEqual(0, proc.returncode,
                            "正本が欠けても生成できてしまうと、既定値が第 2 の正本になる")
        self.assertIn("sidebar_width_px", proc.stderr)


class SidebarIsAlwaysVisible(unittest.TestCase):

    def test_header_declares_the_sidebar_layout(self):
        res, html_text, _ = render()
        self.assertEqual(0, res.returncode, res.stderr)
        header = header_of(html_text)
        self.assertIsNotNone(header, "目次を包む header が無い")
        self.assertIn("pop-header--sidebar", (header.attrs.get("class") or "").split())
        self.assertEqual("sidebar", header.attrs.get("data-hb-nav-layout"))

    def test_sidebar_stays_sticky(self):
        """要求『スクロールしても常に表示』。柱の高さは画面の高さに張る。"""
        _, html_text, _ = render()
        self.assertRegex(html_text, r"\.pop-header\s*\{[^}]*position\s*:\s*sticky")
        self.assertRegex(html_text, r"\.pop-header\s*\{[^}]*top\s*:\s*0")
        self.assertRegex(html_text, r"\.pop-header--sidebar\s*\{[^}]*height\s*:\s*100vh")

    def test_page_shell_puts_the_nav_beside_the_body(self):
        """柱と本文は横に並ぶ。DOM 順は 目次 → 本文 のまま変えない。"""
        _, html_text, _ = render()
        self.assertRegex(html_text, r"\.page-shell\s*\{[^}]*grid-template-columns\s*:\s*var\(--side-nav-w\)")
        shell = html_text.index('<div class="page-shell">')
        header = html_text.index("<header ")
        self.assertLess(shell, header, "器は目次より前に開く")
        self.assertLess(header, html_text.index('<main class="wrap"'),
                        "DOM 順は 目次 → 本文")

    def test_body_is_not_pushed_down_by_the_nav(self):
        """柱は本文の上に被らない。被り量 (--nav-h) は 0 で、帯へ戻す幅でだけ復活する。"""
        _, html_text, _ = render()
        self.assertRegex(html_text, r"--nav-h:\s*0px")
        narrow = re.search(
            r"@media \(max-width: {}px\)\s*\{{(.*?)\n\}}".format(
                canon_nav()["collapse_below_px"] - 1),
            html_text, re.S)
        self.assertIsNotNone(narrow, "帯へ戻す幅の分岐が無い")
        self.assertRegex(narrow.group(1), r":root\s*\{\s*--nav-h:\s*\d+px")


class IndexIsLeftAligned(unittest.TestCase):

    def test_chips_fill_the_column_and_start_at_the_same_line(self):
        _, html_text, _ = render()
        rule = re.search(r"\.pop-header--sidebar \.nav-chip \{([^}]*)\}", html_text)
        self.assertIsNotNone(rule, "柱の中の札に対する規則が無い")
        body = rule.group(1)
        self.assertRegex(body, r"width\s*:\s*100%")
        self.assertRegex(body, r"justify-content\s*:\s*flex-start")
        self.assertRegex(body, r"text-align\s*:\s*left")

    def test_title_is_left_aligned_too(self):
        _, html_text, _ = render()
        rule = re.search(r"\.pop-header--sidebar \.doc-title-bar \{([^}]*)\}", html_text)
        self.assertIsNotNone(rule)
        self.assertRegex(rule.group(1), r"text-align\s*:\s*left")

    def test_column_stacks_the_chips(self):
        _, html_text, _ = render()
        rule = re.search(r"\.pop-header--sidebar \.navbar \{([^}]*)\}", html_text)
        self.assertIsNotNone(rule)
        self.assertRegex(rule.group(1), r"flex-direction\s*:\s*column")


class IndexContentIsUnchanged(unittest.TestCase):
    """置き場所を変えただけで、目次の中身は帯だったときと同一。"""

    def test_one_chip_per_section_in_order(self):
        res, html_text, cfg = render()
        self.assertEqual(0, res.returncode, res.stderr)
        chips = [el for el in H.parse(html_text)
                 if "nav-chip" == (el.attrs.get("class") or "")]
        self.assertEqual(len(cfg["sections"]), len(chips))
        for index, (chip, section) in enumerate(zip(chips, cfg["sections"]), start=1):
            self.assertEqual("#" + section["id"], chip.attrs.get("href"))
            self.assertEqual(str(index), chip.attrs.get("data-hb-nav-index"))
            self.assertEqual(section["goal"], chip.attrs.get("data-hb-nav-goal"))

    def test_labels_are_not_truncated_in_the_dom(self):
        """省略は CSS だけで行う (読み上げとページ内検索は全文を得る)。"""
        _, html_text, cfg = render()
        for section in cfg["sections"]:
            self.assertIn(section["heading"], html_text)


class SidebarDoesNotBlockOperation(unittest.TestCase):
    """柱を置いたことで「押せない・辿り着けない」を作らない (UI/UX 側の受入)。"""

    def test_bottom_toolbar_starts_after_the_column(self):
        """下の帯は本文への操作。画面いっぱいに敷くと 100vh の柱の足元
        (最後の札) が帯の下へ隠れて押せなくなる。柱の幅だけ右へ寄せる。"""
        _, html_text, _ = render()
        wide = re.search(
            r"@media \(min-width: {}px\)\s*\{{(.*?)\n\}}".format(
                canon_nav()["collapse_below_px"]),
            html_text, re.S)
        self.assertIsNotNone(wide, "柱を立てる幅の分岐が無い")
        self.assertRegex(wide.group(1),
                         r"\.toolbar\s*\{[^}]*left\s*:\s*var\(--side-nav-w\)")

    def test_keyboard_can_skip_the_index(self):
        """柱は DOM 上つねに本文より前。最初の Tab で本文へ抜ける出口を置く。"""
        _, html_text, _ = render()
        anchors = [el for el in H.parse(html_text)
                   if el.tag == "a" and "skip-to-main" in (el.attrs.get("class") or "").split()]
        self.assertEqual(1, len(anchors), "本文へ跳ぶリンクは 1 本だけ置く")
        target = anchors[0].attrs.get("href")
        self.assertTrue(target.startswith("#"), target)
        self.assertIn('id="{}"'.format(target[1:]), html_text,
                      "跳び先の id が本文側に無い")
        self.assertLess(html_text.index("skip-to-main"), html_text.index("nav-chip"),
                        "出口は札より前に無いと最初の Tab で拾えない")

    def test_skip_link_is_hidden_until_focused(self):
        """マウスで読む人の紙面は変えない。ただし display:none にはしない
        (焦点が当たらなくなり、置いた意味が消える)。"""
        _, html_text, _ = render()
        rule = re.search(r"\.skip-to-main \{([^}]*)\}", html_text)
        self.assertIsNotNone(rule)
        self.assertNotRegex(rule.group(1), r"display\s*:\s*none")
        self.assertRegex(rule.group(1), r"width\s*:\s*1px")
        self.assertRegex(html_text, r"\.skip-to-main:focus \{[^}]*width\s*:\s*auto")


class SidebarFallsBackOnPaper(unittest.TestCase):

    def test_print_unstacks_the_column(self):
        """紙に 100vh の柱は成立しない。段組みを解いて帯へ戻す。"""
        _, html_text, _ = render()
        block = "\n".join(re.findall(r"@media\s+print\s*\{(.*?)\n\s*\}\s*\n",
                                     html_text, re.S))
        self.assertIn(".page-shell { display: block; }", block)
        self.assertRegex(block, r"\.pop-header--sidebar\s*\{[^}]*height\s*:\s*auto")


if __name__ == "__main__":
    unittest.main()

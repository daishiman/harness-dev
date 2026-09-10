"""C17 verify-handout-a11y-print.py 受入テストの共通ハーネス。

このモジュール自体はテストを持たない (discover の pattern test_*.py に一致しない)。
契約の正本は plugin-plans/guide-doc-generator/briefs/script-brief-C17.json であり、
ここには「契約をどう観測するか」だけを置く。判定規則の複製は置かない。

実装が未着手のあいだ、require_script() は AssertionError を投げる。
これにより各テストは error ではなく failure (赤) として記録される。
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parents[1]          # plugins/guide-doc-generator
REPO_ROOT = TESTS_DIR.parents[3]            # repo root

SCRIPT = PLUGIN_ROOT / "scripts" / "verify-handout-a11y-print.py"

# stdout の固定順 (script-brief-C17.json#stdout)
DETECTION_IDS = ["A11Y-01", "A11Y-02", "A11Y-03", "A11Y-04", "A11Y-05",
                 "A11Y-06", "A11Y-07",
                 "PRINT-01", "PRINT-02", "PRINT-03", "PRINT-04",
                 "STICKY-01"]

SUMMARY_RE = re.compile(
    r"^(?P<id>(?:A11Y|PRINT|STICKY)-\d{2})\s+"
    r"(?P<status>PASS|FAIL|NOT-STATICALLY-CHECKABLE)\s+"
    r"checked=(?P<checked>\d+)\s+violations=(?P<violations>\d+)\s*$"
)
RESULT_RE = re.compile(r"^RESULT:\s+(?P<result>PASS|FAIL)\s+(?P<path>\S.*)$")

# stdout 末尾に必ず出る節 (AC-C17-10)
OUT_OF_SCOPE_HEADER = "OUT-OF-SCOPE:"
# 範囲外として毎回明示することが要求されている 5 事項 (AC-C17-10 / algorithm 3)
OUT_OF_SCOPE_TOPICS = {
    "a4_fit": ["A4", "版面"],
    "page_break": ["改ページ"],
    "focus_ring": ["フォーカス"],
    "post_js_dom": ["JS", "DOM"],
    "cascade": ["カスケード"],
}


def require_script():
    """実装が存在しなければ赤で落とす。"""
    if not SCRIPT.exists():
        raise AssertionError(
            "未実装: {} が存在しない。P05 でこの build_target を実装すること "
            "(script-brief-C17.json#build_target)".format(SCRIPT)
        )


class Result:
    __slots__ = ("rc", "out", "err")

    def __init__(self, rc, out, err):
        self.rc = rc
        self.out = out
        self.err = err

    def __repr__(self):  # 失敗時の可読性のため
        return "Result(rc={!r}, out={!r}, err={!r})".format(self.rc, self.out, self.err)

    # --- stdout ---
    def result_line(self):
        first = self.out.splitlines()[0] if self.out.splitlines() else ""
        return RESULT_RE.match(first)

    def summary(self):
        """detection_id -> {'status','checked','violations'}"""
        table = {}
        for line in self.out.splitlines():
            m = SUMMARY_RE.match(line)
            if m:
                table[m.group("id")] = {
                    "status": m.group("status"),
                    "checked": int(m.group("checked")),
                    "violations": int(m.group("violations")),
                }
        return table

    def summary_order(self):
        return [m.group("id") for m in
                (SUMMARY_RE.match(l) for l in self.out.splitlines()) if m]

    def out_of_scope_block(self):
        """OUT-OF-SCOPE: 以降の本文を返す。節が無ければ None。"""
        lines = self.out.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith(OUT_OF_SCOPE_HEADER):
                return "\n".join(lines[i:])
        return None

    # --- stderr ---
    def violations(self, detection_id=None):
        rows = []
        for line in self.err.splitlines():
            parts = line.split("\t")
            if not parts or parts[0] != "FAIL":
                continue
            row = {
                "detection_id": parts[1] if len(parts) > 1 else "",
                "pos": parts[2] if len(parts) > 2 else "",
                "target": parts[3] if len(parts) > 3 else "",
                "missing": parts[4] if len(parts) > 4 else "",
            }
            if detection_id is None or row["detection_id"] == detection_id:
                rows.append(row)
        return rows

    def errors(self):
        return [l for l in self.err.splitlines() if l.startswith("ERROR\t")]


# --------------------------------------------------------------------------
# fixture — 12 detection を全て PASS する HTML を土台にし、
#           検査対象の規則だけを 1 つ壊して切り分ける
# --------------------------------------------------------------------------

PNG_DATA_URI = ("data:image/png;base64,"
                + base64.b64encode(b"\x89PNG\r\n\x1a\n" + bytes(range(64))).decode("ascii"))

BASE_CSS = """:root{--pop-primary-deep:#0b3d91}
html{scroll-behavior:smooth}
body{font-family:system-ui,"Hiragino Sans",sans-serif;margin:0}
.pop-header{position:sticky;top:0;background:#fff;z-index:10}
.pop-card{scroll-margin-top:96px;padding:16px}
.pop-chip:focus{outline:none}
main.pop{max-width:960px;margin:0 auto}
.lightbox{position:fixed;inset:0;background:rgba(0,0,0,.7)}
"""

FOCUS_CSS = """:focus-visible{outline:3px solid var(--pop-primary-deep);outline-offset:2px}
.pop-chip:focus-visible{outline:3px solid var(--pop-primary-deep)}
"""

REDUCED_MOTION_CSS = """@media (prefers-reduced-motion: reduce){
html{scroll-behavior:auto}
*,*::before,*::after{animation-duration:0s !important;transition-duration:0s !important}
}
"""

PAGE_CSS = "@page{size:A4;margin:14mm}\n"

PRINT_CSS = """@media print{
main.pop{max-width:100%}
.pop-header{position:static}
.lightbox{position:static}
.lightbox,.memo-panel,.memo-global,.toolbar{display:none !important}
[data-hb-part="lightbox"],[data-hb-part="memo"],[data-hb-part="memo-global"],[data-hb-part="toolbar"]{display:none !important}
.pop-card{break-inside:avoid;page-break-inside:avoid}
h1,h2,h3{break-after:avoid}
}
"""

# nav オフセット補正 (STICKY-01 b) とスムーススクロールの抑制 (A11Y-07 c) を含む
SCRIPT_JS = """'use strict';
var header=document.querySelector('.pop-header');
var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
function jumpTo(y){
  var off=header.getBoundingClientRect().height+12;
  if(reduce){window.scrollTo({top:y-off});}
  else{window.scrollTo({top:y-off,behavior:'smooth'});}
}
"""

_BODY = """<header class="pop-header" data-hb-part="B01">
<nav aria-label="目次"><a href="#s1">1. 導入</a><a href="#s2">2. 選ぶ</a></nav>
</header>
<main class="pop">
<section id="s1" class="pop-card" data-hb-part="section">
<h2>導入</h2>
<p><svg data-hb-kind="icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M4 12l5 5L20 6"/></svg> 本日の狙いを確認します。</p>
<div data-hb-part="B05">
<table>
<thead><tr><th scope="col">観点</th><th scope="col">Chat</th></tr></thead>
<tbody><tr><th scope="row">得意なこと</th><td>要約</td></tr></tbody>
</table>
</div>
<figure data-hb-part="DIAGRAM"><svg data-hb-kind="figure" viewBox="0 0 400 240"><title>処理の流れ</title><rect x="8" y="8" width="120" height="60"/></svg><figcaption>処理の流れ</figcaption></figure>
<figure data-hb-part="IMG"><img src="PNG_DATA_URI" alt="操作画面"></figure>
</section>
<section id="s2" class="pop-card" data-hb-part="section">
<h2>選ぶ</h2>
<div data-hb-part="B08" class="map">
<button class="map-item" aria-pressed="false" data-hb-title="Claude Code" data-hb-detail="端末で動く">Claude Code</button>
<button class="map-item" aria-pressed="true" data-hb-title="Chat" data-hb-detail="対話で使う">Chat</button>
<button class="map-reset" data-hb-part-role="aux" aria-label="選択を解除する">解除</button>
</div>
<div data-hb-part="B15" data-hb-single class="chips">
<button class="pop-chip" aria-pressed="true">初級</button>
<button class="pop-chip" aria-pressed="false">中級</button>
</div>
<div data-hb-part="B13">
<div role="tablist" aria-label="記法">
<button role="tab" aria-selected="true" aria-controls="p-md" id="t-md">Markdown</button>
<button role="tab" aria-selected="false" aria-controls="p-bul" id="t-bul">箇条書き</button>
</div>
<div id="p-md" role="tabpanel" aria-labelledby="t-md"><p>見出しは # で書きます。</p></div>
<div id="p-bul" role="tabpanel" aria-labelledby="t-bul" hidden><p>行頭に - を置きます。</p></div>
</div>
<div data-hb-part="B10"><details><summary>補足を開く</summary><p>詳細はこちら。</p></details></div>
<div data-hb-part="B11" class="prompt-box"><pre>要約してください</pre>
<button class="copy-btn" aria-label="プロンプトをコピー"><svg data-hb-kind="icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M8 8h10v10"/></svg></button>
</div>
<div data-hb-part="B09"><label for="ck1"><input id="ck1" type="checkbox"> 準備物を確認した</label></div>
BODY_EXTRA
</section>
</main>
<div data-hb-part="toolbar" class="toolbar"><button class="print-btn" aria-label="印刷する">印刷</button></div>
<div data-hb-part="memo" class="memo-panel"><label for="m1">このセクションのメモ</label><input id="m1" type="text" aria-label="このセクションのメモ"></div>
<div data-hb-part="memo-global" class="memo-global"><label for="m0">全体メモ</label><input id="m0" type="text" aria-label="全体メモ"></div>
<div data-hb-part="lightbox" class="lightbox" role="dialog" aria-modal="true" aria-label="画像の拡大表示" hidden>
<button class="lightbox-close" aria-label="拡大表示を閉じる"><svg data-hb-kind="icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M6 6l12 12"/></svg></button>
</div>
"""

_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>配布資料</title>
<style>
CSS_BLOCK</style>
HEAD_EXTRA</head>
<body>
BODY_BLOCK<script>
SCRIPT_BLOCK</script>
</body>
</html>
"""


def good_html(body_extra="", css_extra="", head_extra="",
              base_css=None, focus_css=None, rm_css=None,
              page_css=None, print_css=None, script=None, body=None):
    """12 detection を全て PASS する HTML を組み立てる。

    各引数へ空文字や差し替え文字列を渡すことで、規則を 1 つだけ壊した
    境界事例 fixture を作る。
    """
    css = "".join([
        BASE_CSS if base_css is None else base_css,
        FOCUS_CSS if focus_css is None else focus_css,
        REDUCED_MOTION_CSS if rm_css is None else rm_css,
        PAGE_CSS if page_css is None else page_css,
        PRINT_CSS if print_css is None else print_css,
        css_extra,
    ])
    body_block = (_BODY if body is None else body).replace("BODY_EXTRA", body_extra)
    body_block = body_block.replace("PNG_DATA_URI", PNG_DATA_URI)
    return (_TEMPLATE
            .replace("CSS_BLOCK", css)
            .replace("HEAD_EXTRA", head_extra)
            .replace("BODY_BLOCK", body_block)
            .replace("SCRIPT_BLOCK", SCRIPT_JS if script is None else script))


def mutate(html, old, new):
    """土台 fixture の 1 箇所だけを壊す。差し替え先が見つからなければ即座に落とす。

    fixture の文言を後から変えたときに、壊したつもりの箇所が壊れていない
    (=検査が空振りしている) 状態を防ぐ。
    """
    if old not in html:
        raise AssertionError("fixture が変わっている: 差し替え対象が見つからない\n{!r}".format(old))
    return html.replace(old, new, 1)


class C17TestCase(unittest.TestCase):
    """CLI を実行して契約を観測するテストの土台。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hb-c17-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    # --- 入力 ---
    def write_html(self, text, name="handout.html"):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8")
        return p

    # --- 実行 ---
    def run_cli(self, *args):
        require_script()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *[str(a) for a in args]],
            capture_output=True, text=True, cwd=str(self.tmp), timeout=120,
        )
        return Result(proc.returncode, proc.stdout, proc.stderr)

    def check(self, html_text, *extra_args, name="handout.html"):
        return self.run_cli("--html", self.write_html(html_text, name), *extra_args)

    def check_good(self, **kw):
        return self.check(good_html(**kw))

    def report_for(self, html_text):
        """--json-report を付けて実行し (Result, report_dict) を返す。"""
        rp = self.tmp / "report.json"
        res = self.check(html_text, "--json-report", rp)
        self.assertTrue(rp.exists(),
                        "--json-report のパスへ JSON が書かれていない: {}".format(res))
        return res, json.loads(rp.read_text(encoding="utf-8"))

    # --- 断言ヘルパ ---
    def assertDetectionFails(self, res, detection_id, count=None, msg=""):
        table = res.summary()
        self.assertIn(detection_id, table,
                      "stdout に {} のサマリ行が無い {}\n{}".format(detection_id, msg, res))
        self.assertEqual("FAIL", table[detection_id]["status"],
                         "{} が FAIL になっていない {}\n{}".format(detection_id, msg, res))
        self.assertEqual(1, res.rc, "品質 FAIL は exit 1 {}\n{}".format(msg, res))
        if count is not None:
            self.assertEqual(count, table[detection_id]["violations"],
                             "{} の violations 件数が違う {}\n{}".format(detection_id, msg, res))
        self.assertTrue(res.violations(detection_id),
                        "stderr に {} の違反行が無い {}\n{}".format(detection_id, msg, res))

    def assertDetectionPasses(self, res, detection_id, msg=""):
        table = res.summary()
        self.assertIn(detection_id, table,
                      "stdout に {} のサマリ行が無い {}\n{}".format(detection_id, msg, res))
        self.assertEqual("PASS", table[detection_id]["status"],
                         "{} が PASS でない {}\n{}".format(detection_id, msg, res))
        self.assertEqual(0, table[detection_id]["violations"],
                         "{} の violations が 0 でない {}\n{}".format(detection_id, msg, res))

    def assertStatus(self, res, detection_id, status, msg=""):
        table = res.summary()
        self.assertIn(detection_id, table,
                      "stdout に {} のサマリ行が無い {}\n{}".format(detection_id, msg, res))
        self.assertEqual(status, table[detection_id]["status"],
                         "{} の status が {} でない {}\n{}".format(detection_id, status, msg, res))

    def assertCheckedAtLeast(self, res, detection_id, minimum, msg=""):
        """checked=0 の PASS は『検査していない』と区別が付かないので下限を固定する。"""
        table = res.summary()
        self.assertIn(detection_id, table,
                      "stdout に {} のサマリ行が無い {}\n{}".format(detection_id, msg, res))
        self.assertGreaterEqual(table[detection_id]["checked"], minimum,
                                "{} の checked が {} 未満 {}\n{}".format(
                                    detection_id, minimum, msg, res))

    def assertOnlyThisDetectionFails(self, res, detection_id, msg=""):
        """狙った detection だけが落ちること (fixture の切り分け精度を固定する)。"""
        table = res.summary()
        others = [d for d, v in table.items()
                  if d != detection_id and v["status"] != "PASS"]
        self.assertEqual([], others,
                         "{} 以外も落ちている: {} {}\n{}".format(detection_id, others, msg, res))

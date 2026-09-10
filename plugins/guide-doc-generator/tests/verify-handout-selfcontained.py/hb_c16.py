"""C16 verify-handout-selfcontained.py 受入テストの共通ハーネス。

このモジュール自体はテストを持たない (discover の pattern test_*.py に一致しない)。
契約の正本は plugin-plans/guide-doc-generator/briefs/script-brief-C16.json であり、
ここには「契約をどう観測するか」だけを置く。判定規則の複製は置かない。

実装が未着手のあいだ、require_script() は AssertionError を投げる。
これにより各テストは error ではなく failure (赤) として記録される。
"""

from __future__ import annotations

import base64
import importlib.util
import json
import os
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

SCRIPT = PLUGIN_ROOT / "scripts" / "verify-handout-selfcontained.py"
HOOK_C10 = PLUGIN_ROOT / "hooks" / "guard-handout-external-ref.py"
RENDER_C11 = PLUGIN_ROOT / "scripts" / "render-handout.py"

# stdout の固定順 (script-brief-C16.json#stdout)。
# SC-10 は利用者要件の明確化で追加された同梱閉包の包括規則 (ブリーフ未反映 / README gaps 参照)。
# 新設 detection は固定順の末尾に付き、サマリ行数は 10 になる。
DETECTION_IDS = ["SC-01", "SC-02", "SC-03", "SC-04", "SC-05",
                 "SC-06", "SC-07", "SC-08", "SC-09", "SC-10"]

# CR-EXT (取得を発生させる参照) を実装する detection 群
EXTERNAL_REF_DETECTIONS = ["SC-01", "SC-02", "SC-03", "SC-04", "SC-10"]

SUMMARY_RE = re.compile(
    r"^(?P<id>SC-\d{2})\s+(?P<status>PASS|FAIL)\s+checked=(?P<checked>\d+)\s+violations=(?P<violations>\d+)\s*$"
)
RESULT_RE = re.compile(r"^RESULT:\s+(?P<result>PASS|FAIL)\s+(?P<path>\S.*)$")


def require_script():
    """実装が存在しなければ赤で落とす。"""
    if not SCRIPT.exists():
        raise AssertionError(
            "未実装: {} が存在しない。P05 でこの build_target を実装すること "
            "(script-brief-C16.json#build_target)".format(SCRIPT)
        )


def load_hb():
    """module_api の読み込み作法 (importlib.util.spec_from_file_location) をそのまま使う。"""
    require_script()
    spec = importlib.util.spec_from_file_location("hb_selfcontained", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("module として読み込めない: {}".format(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
                "message": parts[3] if len(parts) > 3 else "",
                "evidence": parts[4] if len(parts) > 4 else "",
            }
            if detection_id is None or row["detection_id"] == detection_id:
                rows.append(row)
        return rows

    def errors(self):
        return [l for l in self.err.splitlines() if l.startswith("ERROR\t")]


# --------------------------------------------------------------------------
# fixture
# --------------------------------------------------------------------------

# 実体長 64 バイト以上の data URI (SC-09 (a) の閾値を余裕で超える)
BIG_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"IHDR" + bytes(range(256))
BIG_DATA_URI = "data:image/png;base64," + base64.b64encode(BIG_PNG_BYTES).decode("ascii")
# 実体長ちょうど 64 バイト / 63 バイト (境界)
DATA_URI_64 = "data:image/png;base64," + base64.b64encode(b"a" * 64).decode("ascii")
DATA_URI_63 = "data:image/png;base64," + base64.b64encode(b"a" * 63).decode("ascii")

ICON_ATTRS = ('viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"')

_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>配布資料</title>
<style>:root{--fg:#111}body{font-family:system-ui,"Hiragino Sans",sans-serif}</style>
<!--HEAD-->
</head>
<body>
<svg data-hb-kind="mascot" width="0" height="0" aria-hidden="true"><defs>
<symbol id="ic-check" data-hb-kind="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12l5 5L20 6"/></symbol>
<symbol id="ic-warn" data-hb-kind="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v9"/></symbol>
<!--SYMBOLS-->
</defs></svg>
<nav class="navbar">
<a href="#s1">導入</a><a href="#s2">前提</a><a href="#s3">手順</a><a href="#s4">注意</a><a href="#s5">演習</a><a href="#s6">質問</a><a href="#s7">まとめ</a>
<!--NAV-->
</nav>
<section id="s1"><h2>導入</h2><p>本日の狙いを 3 点で確認します。</p></section>
<section id="s2"><h2>前提</h2><p><svg data-hb-kind="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><use href="#ic-check"/></svg> 準備物の確認</p></section>
<section id="s3"><h2>手順</h2><p><svg data-hb-kind="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><use xlink:href="#ic-warn"/></svg> 順番に進めます。</p></section>
<section id="s4"><h2>注意</h2><p>操作は元に戻せます。</p></section>
<section id="s5"><h2>演習</h2><p>手元で試します。</p></section>
<section id="s6"><h2>質問</h2><p>よくある質問をまとめました。</p></section>
<section id="s7"><h2>まとめ</h2>
<figure data-hb-part="DIAGRAM"><svg data-hb-kind="decor" viewBox="0 0 400 240"><rect x="8" y="8" width="120" height="60"/><path d="M8 8L128 68"/><text x="12" y="90">収支</text></svg><figcaption>収支の流れ</figcaption></figure>
<!--EXTRA-->
</section>
</body>
</html>
"""


def good_html(extra="", head="", nav="", symbols=""):
    """AC-C16-01 が要求する『参照 v2 相当の自己完結 HTML』。

    検出ごとの fixture はこの土台へ snippet を差し込んで作る。
    最小 snippet 単体では SC-08 (nav/section 不在 -> failure_modes により exit 1) に
    巻き込まれ、目的の detection を切り分けられないため。
    """
    return (_TEMPLATE
            .replace("<!--EXTRA-->", extra)
            .replace("<!--HEAD-->", head)
            .replace("<!--NAV-->", nav)
            .replace("<!--SYMBOLS-->", symbols))


class C16TestCase(unittest.TestCase):
    """CLI を実行して契約を観測するテストの土台。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hb-c16-"))
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
        self.assertTrue(rp.exists(), "--json-report のパスへ JSON が書かれていない: {}".format(res))
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

    def assertAnyDetectionFails(self, res, detection_ids, msg=""):
        """どの detection が報告するかがブリーフ上未確定な違反のための断言。

        「どれか 1 つは必ず捕える」ことだけを固定し、担当 detection の
        取り合いは実装 (とブリーフ改訂) に委ねる。
        """
        self.assertEqual(1, res.rc, "品質 FAIL は exit 1 {}\n{}".format(msg, res))
        table = res.summary()
        hit = [d for d in detection_ids if table.get(d, {}).get("status") == "FAIL"]
        self.assertTrue(hit, "{} のいずれかが FAIL になること {}\n{}".format(
            detection_ids, msg, res))
        self.assertTrue(any(res.violations(d) for d in hit),
                        "stderr に違反行が無い {}\n{}".format(msg, res))

    def assertDetectionPasses(self, res, detection_id, msg=""):
        table = res.summary()
        self.assertIn(detection_id, table,
                      "stdout に {} のサマリ行が無い {}\n{}".format(detection_id, msg, res))
        self.assertEqual("PASS", table[detection_id]["status"],
                         "{} が PASS でない {}\n{}".format(detection_id, msg, res))
        self.assertEqual(0, table[detection_id]["violations"],
                         "{} の violations が 0 でない {}\n{}".format(detection_id, msg, res))

    def assertAllPass(self, res, msg=""):
        self.assertEqual(0, res.rc, "exit 0 を期待した {}\n{}".format(msg, res))
        self.assertEqual("", res.err.strip(), "stderr は空を期待した {}\n{}".format(msg, res))

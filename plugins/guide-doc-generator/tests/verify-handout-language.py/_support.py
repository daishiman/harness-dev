# -*- coding: utf-8 -*-
"""C18 verify-handout-language.py の受入テスト用の共通支援。

契約の正本は plugin-plans/guide-doc-generator/briefs/script-brief-C18.json。
本モジュールは fixture 生成と実行ヘルパのみを持ち、判定基準そのものは
各 test_*.py の assert に置く (支援側へ隠さない)。

実装 (plugins/guide-doc-generator/scripts/verify-handout-language.py) は未存在。
未実装は import 例外ではなく `self.fail()` で表明し、
discover 時に errors ではなく failures として赤になるようにしてある。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

# tests/verify-handout-language.py/_support.py から repo ルートまで 4 階層
REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "plugins" / "guide-doc-generator" / "scripts" / "verify-handout-language.py"
PARTS_CATALOG = REPO_ROOT / "plugins" / "guide-doc-generator" / "config" / "handout-parts.json"

# stdout の固定順 (script-brief-C18.json stdout)。LANG-02 / LANG-03 は存在しない。
DETECTION_ORDER = [
    "LANG-01",
    "LANG-04",
    "LANG-05",
    "LANG-06",
    "LANG-07",
    "DATE-01",
    "DATE-02",
    "DATE-03",
    "DATE-04",
]

NORMALIZED_BY = "validate-handout-config.py"  # C12 provenance.normalized_by
CONFIG_DATE = "2026/08/17"

# 出力ディレクトリ名の書式は C19 と C18 DATE-03 が同じ 1 本の正本
# (config/handout-output.json#dir_name_format) を読む。fixture 側でも同じ正本から
# 組み立て、R25 のように書式が変わったとき test 側だけ旧形で固まらないようにする。
OUTPUT_CONFIG = REPO_ROOT / "plugins" / "guide-doc-generator" / "config" / "handout-output.json"
DIR_NAME_FORMAT = json.loads(OUTPUT_CONFIG.read_text(encoding="utf-8"))["dir_name_format"]
DIR_SEPARATOR = DIR_NAME_FORMAT.split("{date}", 1)[1].split("{slug}", 1)[0]
DEFAULT_SLUG = "lecture-claude-intro"


def out_dir_name(date=CONFIG_DATE, slug=DEFAULT_SLUG):
    """命名用ディレクトリ名。日付は表示正本の純変換 (replace('/','-'))。"""
    return DIR_NAME_FORMAT.format(date=date.replace("/", "-"), slug=slug)


OUT_DIR_NAME = out_dir_name()

# 部品カタログ (config/handout-parts.json, owner C11) の section_scope 別代表値。
# id をここへ列挙しているのはテスト fixture の都合であり、
# 「script が id を焼き込んでいないこと」は test_lang06 の CAT 系が別途固定する。
IN_SECTION_PARTS = ["B03", "B05", "B07", "B10", "B16", "B17", "IMG", "DIAGRAM", "TEXT"]
# 「見出しの直後の絵」= LANG-06 の順序判定で起点に数えない部品。
# id を並べず data_block_type からカタログ経由で引く (script 側と同じ導出)。
VISUAL_PARTS = frozenset(
    part["id"]
    for part in json.loads(PARTS_CATALOG.read_text(encoding="utf-8"))["parts"]
    if part.get("section_scope") == "in-section"
    and part.get("data_block_type") in ("image", "diagram")
)


def parts_for(part_id):
    """その部品 1 種だけで『具体部品あり』を成立させる最小の並び。

    絵は節の先頭 1 枚だけ順序の起点から外れる (利用者指定 2026-08-19) ので、
    絵の id は 2 枚置いて「2 枚目は具体として数える」ことまで含めて確かめる。
    """
    return [part_id, part_id] if part_id in VISUAL_PARTS else [part_id]
DOCUMENT_PARTS = ["B01", "B02"]
NON_PART_MARKERS = ["section", "lightbox", "memo", "memo-global", "toolbar"]

TITLE = "はじめての一歩"
PURPOSE_TEXT = "この資料は、はじめて触る人が最初の一回を終えるためのものです。"
BACKGROUND_TEXT = "導入は決まったが、社内に触ったことがある人がいない。"
GOAL_TEXT = "読み終えたら、自分の仕事で一つ試せる状態になる。"

DEFAULT_LEAD_LINE = "出力の形は、読む人と次の使い道で決まる。"
DEFAULT_JUDGMENT_AXIS = "迷ったら『誰が見て、次に何につながる？』で決める。"
DEFAULT_SECTION_GOAL = "読み終えたら、次の一手が自分で選べる。"

# glossary。term は title / hero / 見出しに現れない語だけを選び、
# 「本文での初出」が section 本文の中で一意に決まるようにしてある。
GLOSSARY = [
    {"term": "コネクタ", "plain": "外とつながる仕組み"},
    {"term": "プロンプト", "plain": "AI への指示文"},
    {"term": "MCP", "plain": "道具をつなぐ共通の決まり"},
]

CAPABILITY_LEAD_LINE_OK = "毎週の報告書づくりが 10 分で終わる。"
CAPABILITY_LEAD_LINE_NG = "Projects 機能を使うと、報告書づくりが楽になります。"
FEATURE_HEADING = "Projects"

SECTION_DEFS = [
    {"id": "s1", "heading": "1. まずは全体像", "kind": "standard"},
    {"id": "s2", "heading": "2. できること", "kind": "capability-explainer"},
    {"id": "s3", "heading": "3. 出力形式", "kind": "standard"},
    {"id": "s4", "heading": "4. 次にやること", "kind": "action-items"},
]

GLOSSARY_SECTION_ID = "s1"  # glossary の本文出現を担う section


def to_fullwidth(text):
    """ASCII 英数と空白を全角へ寄せる (NFKC で元へ戻る形を作るため)。"""
    out = []
    for ch in text:
        code = ord(ch)
        if 0x21 <= code <= 0x7E:
            out.append(chr(code + 0xFEE0))
        elif ch == " ":
            out.append("　")
        else:
            out.append(ch)
    return "".join(out)


def nfkc_squash(text):
    return "".join(unicodedata.normalize("NFKC", text).split())


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def base_config(**overrides):
    """AC-C18-01 の PASS 系構成データ (C12 --normalize 済みの形)。"""
    cfg = {
        "schema_version": "1.0",
        "doc_type": "lecture",
        "subject_slug": "claude-intro",
        "title": TITLE,
        "date": CONFIG_DATE,
        "purpose": PURPOSE_TEXT,
        "background": BACKGROUND_TEXT,
        "goal": GOAL_TEXT,
        "reader": "はじめて触る社内メンバー",
        "prior_knowledge_level": "none",
        "essential_problem": "何ができるのかの像が無いまま説明を聞いて離脱する。",
        "presentation_order": "demo_first",
        "attainment_level": "operable",
        "glossary": [dict(g) for g in GLOSSARY],
        "sections": [
            {
                "id": s["id"],
                "heading": s["heading"],
                "goal": DEFAULT_SECTION_GOAL,
                "lead_line": (
                    CAPABILITY_LEAD_LINE_OK
                    if s["kind"] == "capability-explainer"
                    else DEFAULT_LEAD_LINE
                ),
                "judgment_axis": DEFAULT_JUDGMENT_AXIS,
                "section_kind": s["kind"],
                "role": "main",
            }
            for s in SECTION_DEFS
        ],
        "provenance": {
            "normalized_by": NORMALIZED_BY,
            "schema_version": "1.0",
            "date_source": "config",
            "presentation_order_source": "derived-from-prior-knowledge",
            "text_fold_count": 0,
        },
    }
    cfg.update(overrides)
    return cfg


# ---------------------------------------------------------------------------
# glossary の本文レンダリング
# ---------------------------------------------------------------------------


def glossary_paragraph(term, plain, mode):
    """glossary 1 件分の本文段落を mode に従って生成する。

    mode の意味は test 側の docstring と README の対応表に書いてある。
    """
    if mode == "absent":
        return ""
    if mode == "first_paren":
        return "<p>まず%s（%s）を用意します。以降、%sは同じ意味で使います。</p>\n" % (term, plain, term)
    if mode == "first_paren_halfwidth":
        return "<p>まず%s(%s)を用意します。</p>\n" % (term, plain)
    if mode == "first_paren_ideographic_space":
        return "<p>まず%s　（%s）を用意します。</p>\n" % (term, plain)
    if mode == "first_paren_ascii_space":
        return "<p>まず%s （%s）を用意します。</p>\n" % (term, plain)
    if mode == "first_paren_fullwidth_plain":
        return "<p>まず%s（%s）を用意します。</p>\n" % (term, to_fullwidth(plain))
    if mode == "first_paren_repeated":
        return "<p>まず%s（%s）を用意します。次に%s（%s）を確認します。</p>\n" % (
            term,
            plain,
            term,
            plain,
        )
    if mode == "second_paren":
        return "<p>まず%sを用意します。あとで%s（%s）について詳しく述べます。</p>\n" % (
            term,
            term,
            plain,
        )
    if mode == "equals_form":
        return "<p>%s ＝ %s として扱います。</p>\n" % (term, plain)
    if mode == "wrong_plain":
        return "<p>まず%s（詳しくは後ろの節を見てください）を用意します。</p>\n" % term
    if mode == "paren_not_adjacent":
        return "<p>まず%sを、手順に沿って（%s）を用意します。</p>\n" % (term, plain)
    if mode == "bare_no_paren":
        return "<p>まず%sを用意します。</p>\n" % term
    if mode == "in_attribute_only":
        # 属性値にだけ言い換えを置く。本文テキスト T には現れない。
        return '<p title="%s（%s）">まず%sを用意します。</p>\n' % (term, plain, term)
    if mode == "in_script_only":
        return "<script>var s = \"%s（%s）\";</script>\n<p>まず%sを用意します。</p>\n" % (
            term,
            plain,
            term,
        )
    if mode == "prefixed_longer_word":
        # 英数 term の単語境界条件用。term が別語の一部として先に現れる。
        return "<p>%sX という別名を先に説明し、その後%s（%s）を用意します。</p>\n" % (
            term,
            term,
            plain,
        )
    if mode == "japanese_substring_first":
        # 日本語 term は境界条件を課さないので、これは初出として拾われる想定。
        return "<p>%s設計の話から始めます。次に%s（%s）を用意します。</p>\n" % (term, term, plain)
    raise ValueError("unknown glossary mode: %r" % (mode,))


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


def _part_html(part_id, body, slot=None, heading=None, part_seq=0):
    attrs = ['data-hb-part="%s"' % part_id, 'data-hb-part-id="p%d"' % part_seq]
    if slot:
        attrs.append('data-hb-slot="%s"' % slot)
    inner = ""
    if heading is not None:
        inner += "<h3>%s</h3>" % heading
    inner += body
    return "    <div %s>%s</div>\n" % (" ".join(attrs), inner)


def _date_pill(value):
    return '<span class="date-pill" data-hb-field="date">%s</span>' % value


def _section_html(sec, opts):
    sid = sec["id"]
    kind = opts.get("section_kind_attr", {}).get(sid, sec["section_kind"])
    pieces = {}

    pieces["label"] = '    <div class="section-label">%s</div>\n' % sec["heading"]

    goal = opts.get("section_goal_text", {}).get(sid, sec["goal"])
    pieces["goal"] = (
        ""
        if sid in opts.get("omit_section_goal", set())
        else '    <p class="goal-chip" data-hb-field="section_goal">%s</p>\n' % goal
    )

    lead_text = opts.get("lead_line_text", {}).get(sid, sec["lead_line"])
    if sid in opts.get("omit_lead_line", set()):
        lead = ""
    elif sid in opts.get("blank_lead_line", set()):
        lead = '    <p data-hb-field="lead_line">   </p>\n'
    else:
        lead = '    <p data-hb-field="lead_line">%s</p>\n' % lead_text
    if sid in opts.get("duplicate_lead_line", set()):
        lead = lead + lead
    pieces["lead"] = lead

    axis_text = opts.get("judgment_axis_text", {}).get(sid, sec["judgment_axis"])
    if sid in opts.get("omit_judgment_axis", set()):
        axis = ""
    elif sid in opts.get("blank_judgment_axis", set()):
        axis = '    <p data-hb-field="judgment_axis">　</p>\n'
    else:
        axis = '    <p data-hb-field="judgment_axis">%s</p>\n' % axis_text
    if sid in opts.get("duplicate_judgment_axis", set()):
        axis = axis + axis
    pieces["axis"] = axis

    # 具体部品
    body_parts = []
    if kind == "capability-explainer" and sid not in opts.get("plain_parts_only", set()):
        headings = opts.get("feature_headings", {}).get(sid, [FEATURE_HEADING])
        body_parts.append(
            _part_html("B07", "<p>報告書づくりの成果です。</p>", slot="outcome", part_seq=1)
        )
        body_parts.append(
            _part_html("B03", "<ol><li>集める</li><li>まとめる</li></ol>", slot="breakdown", part_seq=2)
        )
        for i, h in enumerate(headings):
            body_parts.append(
                _part_html("B07", "<p>使う道具です。</p>", slot="feature", heading=h, part_seq=3 + i)
            )
    else:
        part_ids = opts.get("part_ids", {}).get(sid, ["B05"])
        for i, pid in enumerate(part_ids):
            body_parts.append(_part_html(pid, "<p>本文の具体部品です。</p>", part_seq=1 + i))
    part_less = sid in opts.get("no_parts", set())
    if part_less:
        body_parts = ["    <p>ここには具体部品がありません。</p>\n"]
    if sid == GLOSSARY_SECTION_ID and not opts.get("omit_glossary_body"):
        modes = opts.get("glossary_modes", {})
        extra = []
        for g in opts.get("glossary_source", GLOSSARY):
            m = modes.get(g["term"], "first_paren")
            extra.append(glossary_paragraph(g["term"], g["plain"], m))
        joined = "".join(extra)
        if part_less:
            # 具体部品を持たせない指定のときは部品でない器へ入れる
            body_parts.append('    <div class="prose">%s</div>\n' % joined)
        else:
            body_parts.append(
                '    <div data-hb-part="TEXT" data-hb-part-id="pg">%s</div>\n' % joined
            )
    pieces["parts"] = "".join(body_parts)

    extra_html = opts.get("extra_section_html", {}).get(sid, "")
    pieces["extra"] = extra_html

    order = opts.get("element_order", {}).get(sid, ["label", "goal", "lead", "parts", "axis", "extra"])
    attrs = ['id="%s"' % sid, 'data-hb-part="section"', 'data-hb-section-kind="%s"' % kind]
    if sid in opts.get("section_without_hb_part", set()):
        attrs = ['id="%s"' % sid, 'data-hb-section-kind="%s"' % kind]
    out = ["  <section %s>\n" % " ".join(attrs)]
    for key in order:
        out.append(pieces.get(key, ""))
    out.append("  </section>\n")
    return "".join(out)


def build_html(cfg, **opts):
    """構成データと整合する PASS 系 HTML を既定で組み立て、opts で 1 点だけ壊す。"""
    date_value = opts.get("date_pill_text", cfg["date"])
    date_position = opts.get("date_pill_position", "header")  # header|hero|section|none
    sections = [s for s in cfg["sections"] if s["id"] not in opts.get("omit_sections", set())]

    out = []
    out.append("<!DOCTYPE html>\n")
    out.append(
        '<html lang="ja" data-hb-schema-version="%s" data-hb-doc-type="%s" '
        'data-hb-subject-slug="%s" data-hb-presentation-order="%s">\n'
        % (cfg["schema_version"], cfg["doc_type"], cfg["subject_slug"], cfg["presentation_order"])
    )
    out.append('<head><meta charset="utf-8"><title>%s</title>\n' % cfg["title"])
    out.append("<style>.date-pill{display:inline-flex}</style>\n</head>\n")
    out.append("<body>\n")

    out.append('<header class="pop-header" data-hb-generated="true">\n')
    out.append('  <div class="head-top"><h1>%s</h1>' % opts.get("h1_text", cfg["title"]))
    if date_position == "header":
        out.append(_date_pill(date_value))
    out.append("</div>\n</header>\n")

    out.append('<div class="pop-hero" data-hb-part="B02" data-hb-generated="true">\n')
    if date_position == "hero":
        out.append("  %s\n" % _date_pill(date_value))
    out.append('  <p data-hb-field="purpose">%s</p>\n' % cfg["purpose"])
    out.append('  <p data-hb-field="background">%s</p>\n' % cfg["background"])
    out.append('  <p data-hb-field="goal">%s</p>\n' % cfg["goal"])
    out.append("</div>\n")

    for sec in sections:
        html = _section_html(sec, opts)
        if date_position == "section" and sec is sections[0]:
            html = html.replace("  </section>\n", "    %s\n  </section>\n" % _date_pill(date_value))
        out.append(html)

    for extra in opts.get("extra_sections_html", []):
        out.append(extra)

    out.append('<footer data-hb-generated="true">\n')
    for value in opts.get("extra_date_pills", []):
        out.append("  %s\n" % _date_pill(value))
    for text in opts.get("footer_texts", []):
        out.append("  <p>%s</p>\n" % text)
    out.append("</footer>\n")

    out.append("</body>\n</html>\n")
    return "".join(out)


# ---------------------------------------------------------------------------
# TestCase 基底
# ---------------------------------------------------------------------------


class LanguageGateTestCase(unittest.TestCase):
    """実行ヘルパと共通 assert。"""

    maxDiff = None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmpdir = Path(self._tmp.name)

    # -- 実行 ---------------------------------------------------------------

    def require_script(self):
        if not SCRIPT.exists():
            self.fail(
                "未実装: %s が存在しない。P05 が script-brief-C18.json の contract で"
                " 実装するまで本テストは赤で固定される" % SCRIPT
            )

    def write_config(self, cfg, name="handout-config.json"):
        path = self.tmpdir / name
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_html(self, html, name="handout.html"):
        path = self.tmpdir / name
        path.write_text(html, encoding="utf-8")
        return path

    def write_pair(self, cfg=None, **opts):
        cfg = cfg if cfg is not None else base_config()
        return self.write_html(build_html(cfg, **opts)), self.write_config(cfg)

    def make_out_dir(self, name=OUT_DIR_NAME, with_file=True):
        path = self.tmpdir / name
        path.mkdir(parents=True, exist_ok=True)
        if with_file:
            (path / "index.html").write_text("既存の成果物", encoding="utf-8")
        return path

    def run_gate(self, html=None, config=None, out_dir=None, json_report=None, extra_argv=None):
        self.require_script()
        argv = [sys.executable, str(SCRIPT)]
        if html is not None:
            argv += ["--html", str(html)]
        if config is not None:
            argv += ["--config", str(config)]
        if out_dir is not None:
            argv += ["--out-dir", str(out_dir)]
        if json_report is not None:
            argv += ["--json-report", str(json_report)]
        if extra_argv:
            argv += list(extra_argv)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            argv, capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(REPO_ROOT)
        )

    def run_default(self, cfg=None, out_dir=None, json_report=None, **opts):
        html, config = self.write_pair(cfg, **opts)
        return self.run_gate(html=html, config=config, out_dir=out_dir, json_report=json_report)

    # -- stdout の解析 -------------------------------------------------------

    def summary(self, res):
        """`<detection_id> <STATUS> checked=<n> violations=<n>` を辞書へ。"""
        rows = {}
        for line in res.stdout.splitlines():
            fields = line.split()
            if not fields or fields[0] not in DETECTION_ORDER:
                continue
            row = {"status": fields[1] if len(fields) > 1 else ""}
            for f in fields[2:]:
                if "=" in f:
                    k, v = f.split("=", 1)
                    row[k] = v
            rows[fields[0]] = row
        return rows

    def summary_order(self, res):
        order = []
        for line in res.stdout.splitlines():
            fields = line.split()
            if fields and fields[0] in DETECTION_ORDER:
                order.append(fields[0])
        return order

    def stderr_rows(self, res, detection_id=None):
        rows = []
        for line in res.stderr.splitlines():
            fields = line.split("\t")
            if fields and fields[0] == "FAIL":
                if detection_id is None or (len(fields) > 1 and fields[1] == detection_id):
                    rows.append(fields)
        return rows

    def violations(self, res, detection_id):
        row = self.summary(res).get(detection_id)
        self.assertIsNotNone(
            row, "stdout に %s のサマリ行が無い\nstdout=%r" % (detection_id, res.stdout)
        )
        self.assertIn("violations", row, "%s のサマリ行に violations= が無い" % detection_id)
        return int(row["violations"])

    def checked(self, res, detection_id):
        row = self.summary(res).get(detection_id)
        self.assertIsNotNone(
            row, "stdout に %s のサマリ行が無い\nstdout=%r" % (detection_id, res.stdout)
        )
        self.assertIn("checked", row, "%s のサマリ行に checked= が無い" % detection_id)
        return int(row["checked"])

    def out_of_scope_block(self, res):
        lines = res.stdout.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("OUT-OF-SCOPE:"):
                return "\n".join(lines[i:])
        return None

    def read_report(self, path):
        self.assertTrue(Path(path).exists(), "--json-report のファイルが作られていない: %s" % path)
        return json.loads(Path(path).read_text(encoding="utf-8"))

    # -- 共通 assert ---------------------------------------------------------

    def assert_gate_pass(self, res):
        self.assertEqual(
            0, res.returncode, "exit 0 を期待\nstdout=%s\nstderr=%s" % (res.stdout, res.stderr)
        )
        self.assertEqual("", res.stderr.strip(), "PASS 時の stderr は空であること")
        self.assertTrue(
            res.stdout.splitlines()[0].startswith("RESULT: PASS "),
            "1 行目は `RESULT: PASS <html_path>`\nstdout=%r" % res.stdout,
        )

    def assert_gate_fail(self, res, detection_id, count=None):
        self.assertEqual(
            1, res.returncode, "違反検出は exit 1\nstdout=%s\nstderr=%s" % (res.stdout, res.stderr)
        )
        self.assertTrue(
            res.stdout.splitlines()[0].startswith("RESULT: FAIL "),
            "1 行目は `RESULT: FAIL <html_path>`\nstdout=%r" % res.stdout,
        )
        row = self.summary(res).get(detection_id)
        self.assertIsNotNone(row, "%s のサマリ行が無い\nstdout=%r" % (detection_id, res.stdout))
        self.assertEqual("FAIL", row["status"], "%s は FAIL であること" % detection_id)
        n = int(row["violations"])
        if count is None:
            self.assertGreaterEqual(n, 1, "%s の violations は 1 以上" % detection_id)
        else:
            self.assertEqual(count, n, "%s の violations 件数" % detection_id)
        self.assertGreaterEqual(
            len(self.stderr_rows(res, detection_id)),
            1,
            "%s の違反行が stderr に無い\nstderr=%r" % (detection_id, res.stderr),
        )

    def assert_detection_pass(self, res, detection_id):
        row = self.summary(res).get(detection_id)
        self.assertIsNotNone(row, "%s のサマリ行が無い\nstdout=%r" % (detection_id, res.stdout))
        self.assertEqual(
            "PASS",
            row["status"],
            "%s は PASS であること\nstdout=%s\nstderr=%s" % (detection_id, res.stdout, res.stderr),
        )
        self.assertEqual(0, int(row["violations"]), "%s の violations は 0" % detection_id)

    def assert_gate_error(self, res):
        self.assertEqual(
            2, res.returncode, "検査不成立は exit 2\nstdout=%s\nstderr=%s" % (res.stdout, res.stderr)
        )
        err_lines = [ln for ln in res.stderr.splitlines() if ln.startswith("ERROR\t")]
        self.assertEqual(
            1, len(err_lines), "ERROR<TAB><reason> をちょうど 1 行\nstderr=%r" % res.stderr
        )

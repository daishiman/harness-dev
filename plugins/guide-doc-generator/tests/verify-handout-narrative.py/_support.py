# -*- coding: utf-8 -*-
"""C22 verify-handout-narrative.py の受入テスト用の共通支援。

正本は plugin-plans/guide-doc-generator/briefs/script-brief-C22.json。
本モジュールは fixture 生成と実行ヘルパのみを持ち、判定基準そのものは
各 test_*.py の assert に置く (支援側へ隠さない)。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# tests/verify-handout-narrative.py/_support.py から repo ルートまで 4 階層
REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "plugins" / "guide-doc-generator" / "scripts" / "verify-handout-narrative.py"

# stdout の固定順。
# 正本は script-brief-C22.json の detections 配列の定義順であり
# (canonical_rules.detection_order_contract / P04-x-05 裁定 B)、本定数はその写しである。
# 件数は導出値なので数値リテラルとして別に持たない (len(DETECTION_ORDER) を使う)。
DETECTION_ORDER = [
    "NAR-01",
    "NAR-02",
    "NAR-03",
    "NAR-04",
    "NAR-05",
    "NAR-06",
    "NAR-07",
    "NAR-08",
    "NAR-09",  # R22 C66: 宣言した detail_level と実態の突合
    "NAR-10",  # R22 C66: 宣言した evidence_depth と実態の突合
]

# stdout の detection 行の頭 (`NAR-xx <STATUS> ...`)。
DETECTION_LINE_RE = re.compile(r"^(NAR-\S+)\b")

NORMALIZED_BY = "validate-handout-config.py"  # C12 provenance.normalized_by

# 冒頭 3 要素の並び順の正本。fixture も検査も同じ 1 か所から引く。
VISUAL_POLICY_PATH = (
    REPO_ROOT / "plugins" / "guide-doc-generator" / "config" /
    "handout-visual-policy.json")


def canonical_hero_field_order():
    policy = json.loads(VISUAL_POLICY_PATH.read_text(encoding="utf-8"))
    return list(policy["opening"]["hero_card_fields"]["order"])

SECTION_DEFS = [
    ("s1", "はじめての 1 回", "読み終えたら、今日やることが分かる。", "main", "standard"),
    ("s2", "できること", "読み終えたら、依頼の書き方が 1 つ選べる。", "main", "capability-explainer"),
    ("s3", "手を動かす", "読み終えたら、自分の手元で 1 度動かせる。", "main", "handson"),
    ("s4", "つまずきどころ", "読み終えたら、詰まったときの戻り方が分かる。", "main", "anticipated-qa"),
    ("s5", "判断のしかた", "読み終えたら、任せる範囲を自分で決められる。", "main", "decisions"),
    ("s6", "次にやること", "読み終えたら、明日の 1 手が決まっている。", "main", "action-items"),
    ("s7", "運営連絡", "読み終えたら、当日の集合と連絡先が分かる。", "appendix", "logistics"),
]

PURPOSE_TEXT = "この資料は Claude をはじめて触る人が最初の 1 回を終えるためのものです。"
BACKGROUND_TEXT = "導入は決まったが、社内に触ったことがある人がいない。"
GOAL_TEXT = "読み終えたら、自分の業務で 1 つ試せる状態になる。"

LEAD_LINE_TEXT = "まずは 1 度、実際の画面を見てから話を進めます。"
JUDGMENT_AXIS_TEXT = "迷ったら、やり直しが利くかどうかで決めてください。"

LONG_PARAGRAPH = "これは概説の段落です。" * 20  # 120 文字を確実に超える
SHORT_PARAGRAPH = "短い補足です。"

PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBASOkA9AAAAAASUVORK5CYII="
)


def base_config(**overrides):
    """AC-C22-01 の PASS 系構成データ (7 section)。"""
    cfg = {
        "schema_version": "1.0",
        "doc_type": "lecture",
        "subject_slug": "claude-first-step",
        "title": "Claude ではじめる最初の 1 回",
        "date": "2026/08/17",
        "purpose": PURPOSE_TEXT,
        "background": BACKGROUND_TEXT,
        "goal": GOAL_TEXT,
        "presentation_order": "demo_first",
        "sections": [
            {
                "id": sid,
                "title": title,
                "goal": goal,
                "role": role,
                "section_kind": kind,
                "ties_to": "goal",
            }
            for sid, title, goal, role, kind in SECTION_DEFS
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


def section_goal_of(cfg, section_id):
    for sec in cfg["sections"]:
        if sec["id"] == section_id:
            return sec["goal"]
    raise KeyError(section_id)


def _hero_field(field, text, present=True):
    if not present:
        return ""
    return '    <p data-hb-field="%s">%s</p>\n' % (field, text)


def _nav_anchor(cfg, sec, opts):
    sid = sec["id"]
    goal = sec["goal"]
    label = "%s" % sec["title"]
    if sid in opts.get("nav_omit_attrs", set()):
        return '  <a href="#%s">%s</a>\n' % (sid, label)
    if sid in opts.get("nav_only_title", set()):
        return '  <a href="#%s" title="%s">%s</a>\n' % (sid, goal, label)
    mismatch = opts.get("nav_mismatch", {}).get(sid)
    if mismatch:
        nav_goal = mismatch.get("data-hb-nav-goal", goal)
        title = mismatch.get("title", goal)
        return '  <a href="#%s" data-hb-nav-goal="%s" title="%s">%s</a>\n' % (
            sid,
            nav_goal,
            title,
            label,
        )
    return '  <a href="#%s" data-hb-nav-goal="%s" title="%s">%s</a>\n' % (sid, goal, goal, label)


def _presentation_item(kind):
    """demo_first 判定 (NAR-07) の対象になる最初の提示物。"""
    if kind == "screenshot":
        return (
            '    <div data-hb-part="IMG" data-hb-asset-role="screenshot">'
            '<img data-hb-asset-role="screenshot" src="%s" alt="Claude の入力欄"></div>\n' % PNG_DATA_URI
        )
    if kind == "figure_img":
        return (
            '    <div data-hb-part="IMG" data-hb-asset-role="figure">'
            '<img data-hb-asset-role="figure" src="%s" alt="全体像の図"></div>\n' % PNG_DATA_URI
        )
    if kind == "diagram":
        return (
            '    <figure data-hb-part="DIAGRAM" data-hb-diagram-id="d1">'
            '<svg data-hb-kind="figure" viewBox="0 0 10 10"></svg></figure>\n'
        )
    if kind == "flow":
        return '    <div data-hb-part="B14"><ol><li>手順の流れ</li></ol></div>\n'
    if kind == "feature_cards":
        return '    <div data-hb-part="B07"><div class="card">特徴 1</div></div>\n'
    if kind == "long_paragraph":
        return "    <p>%s</p>\n" % LONG_PARAGRAPH
    if kind == "short_paragraph":
        return "    <p>%s</p>\n" % SHORT_PARAGRAPH
    if kind == "b17_live":
        return (
            '    <div data-hb-part="B17" data-hb-live-demo="true">'
            "<ol><li>画面を開いて一緒に操作します</li></ol></div>\n"
        )
    if kind == "b17_no_live":
        return '    <div data-hb-part="B17"><ol><li>あとで各自で試してください</li></ol></div>\n'
    if kind == "screenshot_then_diagram":
        return _presentation_item("screenshot") + _presentation_item("diagram")
    if kind == "diagram_then_screenshot":
        return _presentation_item("diagram") + _presentation_item("screenshot")
    raise ValueError(kind)


def _section_html(cfg, sec, opts, is_first_main):
    sid = sec["id"]
    goal = sec["goal"]
    role_attr = opts.get("section_role_attr", {}).get(sid, sec["role"])
    parts = []
    parts.append(
        '  <section id="%s" data-hb-part="section" data-hb-section-role="%s" '
        'data-hb-section-kind="%s" data-hb-ties-to="%s">\n'
        % (sid, role_attr, sec["section_kind"], sec.get("ties_to", "goal"))
    )
    parts.append('    <div class="section-label">%s</div>\n' % sec["title"])

    goal_html = '    <p class="goal-chip" data-hb-field="section_goal">%s</p>\n' % goal
    if sid in opts.get("section_goal_in_details", set()):
        goal_html = (
            "    <details><summary>ゴール</summary>"
            '<p class="goal-chip" data-hb-field="section_goal">%s</p></details>\n' % goal
        )
    if sid in opts.get("section_goal_hidden_attr", set()):
        goal_html = '    <p class="goal-chip" data-hb-field="section_goal" hidden>%s</p>\n' % goal
    if sid in opts.get("section_goal_aria_hidden", set()):
        goal_html = (
            '    <p class="goal-chip" data-hb-field="section_goal" aria-hidden="true">%s</p>\n' % goal
        )
    if sid in opts.get("section_goal_inline_none", set()):
        goal_html = (
            '    <p class="goal-chip" data-hb-field="section_goal" style="display:none">%s</p>\n' % goal
        )
    if sid in opts.get("section_goal_duplicated", set()):
        goal_html = goal_html + goal_html
    if sid in opts.get("omit_section_goal", set()):
        goal_html = ""

    at_end = sid in opts.get("section_goal_at_end", set())
    if not at_end:
        parts.append(goal_html)

    if opts.get("include_lead_line", True):
        parts.append('    <p data-hb-field="lead_line">%s</p>\n' % LEAD_LINE_TEXT)

    if is_first_main:
        parts.append(_presentation_item(opts.get("first_item", "screenshot")))
    else:
        parts.append('    <div data-hb-part="B05"><p>本文の具体部品です。</p></div>\n')

    if opts.get("include_judgment_axis", True):
        parts.append('    <p data-hb-field="judgment_axis">%s</p>\n' % JUDGMENT_AXIS_TEXT)

    if at_end:
        parts.append(goal_html)

    parts.append("  </section>\n")
    return "".join(parts)


def build_html(cfg, **opts):
    """構成データと一致する PASS 系 HTML を既定で組み立て、opts で 1 点だけ壊す。"""
    order = opts.get("section_order") or [s["id"] for s in cfg["sections"]]
    rendered_ids = [sid for sid in order if sid not in opts.get("omit_sections", set())]
    by_id = {s["id"]: s for s in cfg["sections"]}
    for extra in opts.get("extra_html_sections", []):
        by_id.setdefault(
            extra["id"],
            {
                "id": extra["id"],
                "title": extra.get("title", extra["id"]),
                "goal": extra.get("goal", "余分なセクションのゴール。"),
                "role": extra.get("role", "main"),
                "section_kind": extra.get("section_kind", "standard"),
                "ties_to": "goal",
            },
        )
        rendered_ids.append(extra["id"])

    first_main = None
    for sid in rendered_ids:
        sec = by_id[sid]
        role_attr = opts.get("section_role_attr", {}).get(sid, sec["role"])
        if role_attr == "main":
            first_main = sid
            break

    css = [".goal-chip{display:inline-flex}"]
    if opts.get("css_hidden_goal_chip"):
        css.append(".goal-chip{display:none}")
    if opts.get("css_print_hidden_goal_chip"):
        css.append("@media print{.goal-chip{display:none}}")
    if opts.get("extra_css"):
        css.append(opts["extra_css"])

    out = []
    out.append("<!DOCTYPE html>\n")
    out.append(
        '<html lang="ja" data-hb-schema-version="1.0" data-hb-doc-type="%s" '
        'data-hb-subject-slug="%s" data-hb-presentation-order="%s" '
        'data-hb-presentation-order-source="%s">\n'
        % (
            cfg["doc_type"],
            cfg["subject_slug"],
            opts.get("html_presentation_order", cfg["presentation_order"]),
            cfg["provenance"]["presentation_order_source"],
        )
    )
    out.append('<head><meta charset="utf-8"><title>%s</title>\n' % cfg["title"])
    out.append("<style>%s</style>\n</head>\n" % "".join(css))
    out.append("<body>\n")

    if not opts.get("omit_nav"):
        out.append('<nav class="navbar" data-hb-part="B01" data-hb-generated="true">\n')
        nav_ids = opts.get("nav_order") or rendered_ids
        for sid in nav_ids:
            if sid in by_id:
                out.append(_nav_anchor(cfg, by_id[sid], opts))
        out.append("</nav>\n")

    omit_hero = opts.get("omit_hero_fields", set())
    texts = {
        "purpose": cfg["purpose"],
        "background": cfg["background"],
        "goal": cfg["goal"],
    }
    texts.update(opts.get("hero_text_override", {}))
    # 既定の並びは正本から引く。ここに順序を literal で書くと、正本を変えたとき
    # 「実装は追従したのに fixture だけ旧順序」で全件が赤くなる (P05-x-40)。
    hero_order = opts.get("hero_field_order", canonical_hero_field_order())

    out.append('<div class="pop-hero" data-hb-part="B02" data-hb-generated="true">\n')
    out.append("    <h1>%s</h1>\n" % cfg["title"])
    if opts.get("include_date_pill", True):
        out.append('    <span class="date-pill" data-hb-field="date">%s</span>\n' % cfg["date"])
    for field in hero_order:
        out.append(_hero_field(field, texts[field], field not in omit_hero))
        if field in opts.get("duplicate_hero_field", set()):
            out.append(_hero_field(field, texts[field], True))
    out.append("</div>\n")

    for sid in rendered_ids:
        sec = by_id[sid]
        html = _section_html(cfg, sec, opts, sid == first_main)
        if sid == rendered_ids[0]:
            for field in opts.get("hero_field_after_first_section", []):
                html = html.replace(
                    "  </section>\n",
                    _hero_field(field, texts[field], True) + "  </section>\n",
                )
        out.append(html)

    out.append("</body>\n</html>\n")
    html = "".join(out)
    if opts.get("strip_all_hb_fields"):
        import re

        html = re.sub(r'\s*data-hb-field="[a-z_]+"', "", html)
    return html


class NarrativeGateTestCase(unittest.TestCase):
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
                "未実装: %s が存在しない。P05 が script-brief-C22.json の contract で"
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
        html = build_html(cfg, **opts)
        return self.write_html(html), self.write_config(cfg)

    def run_gate(self, html=None, config=None, json_report=None, extra_argv=None):
        self.require_script()
        argv = [sys.executable, str(SCRIPT)]
        if html is not None:
            argv += ["--html", str(html)]
        if config is not None:
            argv += ["--config", str(config)]
        if json_report is not None:
            argv += ["--json-report", str(json_report)]
        if extra_argv:
            argv += list(extra_argv)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            argv, capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(REPO_ROOT)
        )

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

    def detection_ids(self, res):
        """stdout の detection 行の id 列を出現順で返す (AC-C22-15)。

        `summary()` と違い DETECTION_ORDER で絞り込まないため、
        未知の id や余分な行・欠落もそのまま差分に出る。
        """
        return [
            m.group(1)
            for m in (DETECTION_LINE_RE.match(ln) for ln in res.stdout.splitlines())
            if m
        ]

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

    def assert_gate_error(self, res):
        self.assertEqual(
            2, res.returncode, "検査不成立は exit 2\nstdout=%s\nstderr=%s" % (res.stdout, res.stderr)
        )
        err_lines = [ln for ln in res.stderr.splitlines() if ln.startswith("ERROR\t")]
        self.assertEqual(
            1, len(err_lines), "ERROR<TAB><reason> をちょうど 1 行\nstderr=%r" % res.stderr
        )

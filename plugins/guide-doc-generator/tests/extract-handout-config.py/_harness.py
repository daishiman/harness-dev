# -*- coding: utf-8 -*-
"""C20 extract-handout-config.py の受入テスト共通ハーネス。

判定基準の出所は plugin-plans/guide-doc-generator/briefs/script-brief-C20.json
(argv / exit_codes / algorithm / parsing_strategy / roundtrip_granularity /
renderer_marker_requirements / heuristic_fallback / fail_semantics /
acceptance_checks) と briefs/RESOLUTION-P03.md の Y-05。
ここには契約を書かず、契約を叩くための足場だけを置く。

実装 (plugins/guide-doc-generator/scripts/extract-handout-config.py) は P05 の担当で
本テスト作成時点では存在しない。存在しない場合 run() は returncode=127 の合成結果を
返すため、各テストは「期待する exit code / 診断コードが出ない」という形で赤になる。
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

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_PLUGIN_ROOT = REPO_ROOT / "plugins" / "guide-doc-generator"
SCRIPT_RELPATH = Path("scripts") / "extract-handout-config.py"
SRC_SCRIPT = SRC_PLUGIN_ROOT / SCRIPT_RELPATH

# ブリーフ dependencies.reads が挙げる、id 語彙の単一正本 (owner: C11 / P03 Y-05)
PARTS_CATALOG_RELPATH = Path("config") / "handout-parts.json"
# 実装前でも「カタログが正本」であることを検査できるよう、plan 側の正本を参照先に持つ
PLAN_PARTS_CATALOG = (REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs"
                      / "config" / "handout-parts.json")
# C12 は正規化関数の共有先 (importlib 経由)。id 語彙の出所として参照してはならない
C12_SCRIPT_RELPATH = Path("scripts") / "validate-handout-config.py"

NOT_IMPLEMENTED_MARKER = "HB-TEST-SCRIPT-NOT-FOUND"

PART_ID_RE = re.compile(r"^(B\d{2}|IMG|DIAGRAM|TEXT)$")

# 診断コード (script-brief-C20.json#stderr)
E_UNRECOVERABLE = "E-EXTRACT-UNRECOVERABLE"
W_HEURISTIC = "W-EXTRACT-HEURISTIC"
E_ROUNDTRIP_DIFF = "E-ROUNDTRIP-DIFF"
E_HTML_MALFORMED = "E-HTML-MALFORMED"

# roundtrip_granularity.comparable_projection が比較から外すブロック
PROVENANCE_KEYS = ("normalized_by", "schema_version", "catalog_sha256", "date_source")


def _synthetic_missing(script_path):
    return subprocess.CompletedProcess(
        args=[str(script_path)],
        returncode=127,
        stdout="",
        stderr="%s %s (P05 未実装)\n" % (NOT_IMPLEMENTED_MARKER, script_path),
    )


def run(args, root, cwd=None, env_root=True):
    """コピーした plugin root 配下の script を argv 付きで起動する。"""
    script = Path(root) / SCRIPT_RELPATH
    if not script.exists():
        return _synthetic_missing(script)
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if env_root:
        env["HB_ROOT"] = str(root)
    else:
        env.pop("HB_ROOT", None)
    return subprocess.run(
        [sys.executable, str(script)] + [str(a) for a in args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd else str(REPO_ROOT),
    )


# --------------------------------------------------------------------------
# HTML fixture
#
# renderer_marker_requirements.required_markers に列挙されたマーカーだけを使って
# 「C11 が出したはずの HTML」を組む。ここで使うマーカー以外は使わない
# (使ってしまうと C20 のテストが C11 の未確定な装飾に依存する)。
# --------------------------------------------------------------------------

DOC_META = {
    "schema_version": "1.0",
    "doc_type": "lecture",
    "subject_slug": "ai-handout-workshop",
    "theme": "aurora",
    "reader": "月次集計を担当する管理部門の担当者",
    "prior_knowledge_level": "basic",
    "essential_problem": "手順は分かっていても、どこから自動化に着手すればよいかを決められない",
    "title": "生成 AI で月次集計を組み立てる",
    # 日付は紙面に出さず root 属性 data-hb-date で運ぶ (C11 build_doc_head)。
    # 値は構成データの date をそのまま刻むので、ここも正規化後の書式にする。
    "date": "2026/08/17",
    "purpose": "生成 AI を日々の集計業務へ組み込む手順を、その場で再現できる形で共有する",
    "background": "現場では月次の車両収支集計を手作業で行っており、締め日前の残業が慢性化している",
    "goal": "受講者が自分の集計業務を 1 つ選び、生成 AI へ渡す指示文を自力で書けるようになる",
    # R21 / R22 の型フィールド。C11 は文書レベル属性として出しており、
    # 逆抽出はこれらを既定値で埋めずに読む (埋めると著者の選択が化ける)。
    "presentation_order": "demo_first",
    "detail_level": "standard",
    "evidence_depth": "cited",
    "must_remember_max": "2",
    "notes_enabled": "true",
    "attainment_level": "operable",
}

# 同じ data-hb-field が複数回現れる配列項目 (R21)。
FOCUS_THEME = ["自分の集計業務を 1 つ選んで指示文に落とす力"]
MUST_REMEMBER = ["指示文は目的から書く", "元データの範囲を必ず明示する"]
NO_NEED_TO_REMEMBER = ["モデル名ごとの細かい上限値 (本資料を見返せば足りる)"]
TARGET_TASKS = [
    {"id": "monthly-close", "label": "月次の車両収支を締めまでにまとめる"},
]

PROMPT_BODY = "目的:\n  月次の車両収支をまとめる\n\n手順:\n  1. 元データを貼る\n  2. 集計軸を伝える"

PNG_DATA_URI = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
                "AAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
XLSX_DATA_URI = ("data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;"
                 "base64,UEsDBBQAAAAIAA==")

DIAGRAM_DATA = {"nodes": [{"id": "n1", "label": "元データ"}, {"id": "n2", "label": "集計"}],
                "edges": [{"from": "n1", "to": "n2"}]}


def _html_open_tag():
    return (
        '<html lang="ja"'
        ' data-hb-schema-version="%(schema_version)s"'
        ' data-hb-doc-type="%(doc_type)s"'
        ' data-hb-subject-slug="%(subject_slug)s"'
        ' data-hb-theme="%(theme)s"'
        # data-hb-theme は既定値解決を経た実効テーマなので、著者が theme を
        # 書いたかどうかは別の印で運ぶ (C11 と同じ二本立て)。
        ' data-hb-config-theme="%(theme)s"'
        ' data-hb-meta-reader="%(reader)s"'
        ' data-hb-meta-knowledge="%(prior_knowledge_level)s"'
        ' data-hb-meta-problem="%(essential_problem)s"'
        ' data-hb-presentation-order="%(presentation_order)s"'
        ' data-hb-detail-level="%(detail_level)s"'
        ' data-hb-evidence-depth="%(evidence_depth)s"'
        ' data-hb-must-remember-max="%(must_remember_max)s"'
        ' data-hb-notes-enabled="%(notes_enabled)s"'
        # 日付は可視要素をやめ root 属性で運ぶ (利用者指定 2026-08-19 / C11)。
        ' data-hb-date="%(date)s">' % DOC_META
    )


GENERATED_CHROME = """
<nav class="pop-header" data-hb-generated="true">
  <a href="#intro">導入</a><a href="#practice">演習</a>
  <div data-hb-part="B01" data-hb-part-id="nav">ナビ</div>
</nav>
<div class="hero" data-hb-generated="true">
  <div data-hb-part="B02" data-hb-part-id="hero">ヒーロー枠</div>
  <p data-hb-field="lead_line">生成されたヒーロー内のダミー</p>
</div>
<svg class="sprite" data-hb-generated="true"><symbol id="i-check"></symbol></svg>
<div class="memo-global" data-hb-generated="true">
  <textarea class="memo-area" data-hb-key="memo-1"></textarea>
</div>
<footer class="pop-bottom" data-hb-generated="true">生成フッタ</footer>
"""

# マーカーを持たない chrome (二重防御の検査用)
UNMARKED_CHROME = """
<nav class="pop-header"><a href="#intro">導入</a></nav>
<div class="memo-pane"><textarea class="memo-area"></textarea></div>
<footer class="pop-bottom">生成フッタ</footer>
"""


def doc_head():
    return (
        "<!DOCTYPE html>\n" + _html_open_tag() + "\n<head><meta charset=\"utf-8\">"
        "<title>%(title)s</title>"
        "<style>.pop-header{color:#000}</style>"
        "</head>\n<body>\n" % DOC_META
    )


def doc_fields():
    return (
        '<h1 data-hb-field="title">%(title)s</h1>\n'
        '<p data-hb-field="purpose">%(purpose)s</p>\n'
        '<p data-hb-field="background">%(background)s</p>\n'
        '<p data-hb-field="goal">%(goal)s</p>\n'
        '<p data-hb-field="attainment_level">%(attainment_level)s</p>\n' % DOC_META
        # 配列項目は同じ印を持つ要素が文書順に並ぶ。target_task だけは id を
        # 本文でなく data-hb-key が運ぶ (label と id の 2 値を持つため)。
        + "".join('<li data-hb-field="focus_theme">%s</li>\n' % t for t in FOCUS_THEME)
        + "".join('<li data-hb-field="must_remember">%s</li>\n' % t for t in MUST_REMEMBER)
        + "".join('<li data-hb-field="no_need_to_remember">%s</li>\n' % t
                  for t in NO_NEED_TO_REMEMBER)
        + "".join('<li data-hb-field="target_task" data-hb-key="%s">%s</li>\n'
                  % (t["id"], t["label"]) for t in TARGET_TASKS)
    )


def section_html(section_id="intro", kind="standard", parts="", heading="導入",
                 goal="この節を読み終えると、着手点を自分で決められるようになる",
                 lead_line="指示は目的から書くと崩れない",
                 judgment_axis="迷ったら、受け取る人が何を判断できるかで決める",
                 role="main", ties_to=("monthly-close",),
                 attainment_step="operable"):
    # R21 C48/C54/C58: 本編か付録か・どの業務に紐づくか・どこまで到達するか。
    # 既定値で埋めると appendix が本編扱いになるため C11 は属性で明示する。
    # 開きタグだけ先に組むのは、% 書式の適用範囲を連結で壊さないため。
    open_tag = (
        '<section id="%s" data-hb-section-kind="%s" data-hb-section-role="%s"'
        ' data-hb-ties-to="%s" data-hb-attainment-step="%s">\n'
        % (section_id, kind, role, " ".join(ties_to), attainment_step)
    )
    return open_tag + (
        '  <h2 data-hb-field="heading">%s</h2>\n'
        '  <p data-hb-field="section_goal">%s</p>\n'
        '  <p data-hb-field="lead_line">%s</p>\n'
        '  <p data-hb-field="judgment_axis">%s</p>\n'
        '%s'
        '</section>\n' % (heading, goal, lead_line, judgment_axis, parts)
    )


def part_b03(part_id="intro-steps"):
    return (
        # 反復要素は data-hb-entries が「どの配列か」を、行の
        # data-hb-<field> が各値を運ぶ (表示テキストからは切り出さない)。
        '  <ol data-hb-part="B03" data-hb-part-id="%s" data-hb-entries="rows">\n'
        '    <li class="step-row" data-hb-key="collect" data-hb-text="元データを集める"'
        '><span>元データを集める</span></li>\n'
        '    <li class="step-row" data-hb-key="ask" data-hb-text="指示文を書く"'
        '><span>指示文を書く</span></li>\n'
        '  </ol>\n' % part_id
    )


def part_b09(part_id="intro-check"):
    return (
        '  <ul data-hb-part="B09" data-hb-part-id="%s" data-hb-entries="rows">\n'
        '    <li class="pop-row" data-hb-key="has-data" data-hb-text="元データが揃っている">'
        '<label><input type="checkbox">元データが揃っている</label></li>\n'
        '  </ul>\n' % part_id
    )


def part_b11(part_id="intro-prompt"):
    return (
        # body の実体は data-hb-body。<pre> は表示側の写しで、属性の方が
        # 改行もインデントもそのまま運べる (表示要素は装飾を挟みうる)。
        '  <div class="prompt-box" data-hb-part="B11" data-hb-part-id="%s"'
        ' data-hb-body="%s">\n'
        '    <pre>%s</pre>\n'
        '  </div>\n' % (part_id, PROMPT_BODY, PROMPT_BODY)
    )


def part_b15(part_id="intro-chips"):
    return (
        # B15 は chips 群の鍵 (data-hb-key) が必須項目。反復要素側の鍵とは別物で、
        # 「どの選択肢群か」を表す部品自身の値である。
        '  <div class="pop-chips" data-hb-part="B15" data-hb-part-id="%s"'
        ' data-hb-key="cadence" data-hb-entries="chips">\n'
        '    <button data-hb-key="daily" data-hb-label="日次">日次</button>\n'
        '  </div>\n' % part_id
    )


def part_b16(part_id="intro-actions"):
    return (
        '  <ul data-hb-part="B16" data-hb-part-id="%s" data-hb-entries="rows">\n'
        '    <li data-hb-key="a1" data-hb-text="集計軸を確定する" data-hb-owner="佐藤"'
        ' data-hb-due="2026年8月24日">集計軸を確定する</li>\n'
        '  </ul>\n' % part_id
    )


def part_text(part_id="intro-text", body="指示は目的から書くと崩れない。"):
    return ('  <p data-hb-part="TEXT" data-hb-part-id="%s" data-hb-body="%s">%s</p>\n'
            % (part_id, body, body))


def part_img(part_id="intro-img"):
    return (
        # data-hb-media-record は「この要素が assets[] の実体を持つ」印。
        # 素材を参照するだけの部品と区別が付かないと、逆抽出が付随情報を
        # 持たない側を素材の出所に選んでしまう。
        '  <figure data-hb-part="IMG" data-hb-part-id="%s" data-hb-media-record="shot-1"'
        ' data-hb-asset-id="shot-1" data-hb-asset-alt="集計画面"'
        ' data-hb-asset-caption="実際の集計画面" data-hb-src="assets/shot-1.png">\n'
        '    <img src="%s">\n'
        '  </figure>\n' % (part_id, PNG_DATA_URI)
    )


def part_b12(part_id="intro-dl"):
    return (
        '  <a class="dl-btn" download="template.xlsx" href="%s" data-hb-part="B12"'
        ' data-hb-part-id="%s" data-hb-attachment-id="tpl"'
        # label は部品 data の必須項目 (表示文言とは別に印で運ぶ)。
        ' data-hb-label="テンプレートをダウンロード"'
        # attachments[] の実体を持つのはこのリンク (参照だけの部品と区別する)。
        ' data-hb-media-record="tpl"'
        ' data-hb-filename="template.xlsx"'
        ' data-hb-mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"'
        ' data-hb-fallback-hint="開けない場合は共有ドライブの同名ファイルを使う">'
        'テンプレートをダウンロード</a>\n' % (XLSX_DATA_URI, part_id)
    )


def part_diagram(part_id="intro-diagram", data=None):
    payload = json.dumps(DIAGRAM_DATA if data is None else data, ensure_ascii=False)
    payload = payload.replace('"', "&quot;")
    return (
        '  <div data-hb-part="DIAGRAM" data-hb-part-id="%s" data-hb-diagram-id="flow-1"'
        # diagrams[] の実体を持つ部品。data は平坦化後の姿からは切り出せない
        # ため、レジストリ実体の写しを data-hb-diagram-record-data で運ぶ。
        ' data-hb-media-record="flow-1" data-hb-diagram-title="集計の流れ"'
        ' data-hb-diagram-record-data="%s"'
        ' data-hb-diagram-pattern="linear-flow" data-hb-diagram-data="%s">\n'
        '    <svg viewBox="0 0 10 10"><rect x="0" y="0" width="4" height="2"></rect></svg>\n'
        '  </div>\n' % (part_id, payload, payload)
    )


def glossary_html():
    return (
        '<p data-hb-glossary-term="プロンプト" data-hb-glossary-plain="AI へ渡す指示文"'
        ' data-hb-glossary-scope="document">プロンプト</p>\n'
    )


def full_html(sections=None, chrome=True, extra_body="", unmarked_chrome=False):
    """マーカーを備えた生成 HTML 相当の fixture。"""
    if sections is None:
        sections = [
            section_html("intro", parts=part_b03() + part_text() + part_b11()),
            section_html("practice", heading="演習", parts=part_b09() + part_b15() + part_b16()),
        ]
    body = doc_fields() + glossary_html()
    if chrome:
        body = GENERATED_CHROME + body
    if unmarked_chrome:
        body = UNMARKED_CHROME + body
    body += "".join(sections) + extra_body
    if chrome:
        body += '<div class="lightbox" data-hb-generated="true"><img src="%s"></div>\n' % PNG_DATA_URI
    return doc_head() + body + "<script>console.log(1)</script>\n</body>\n</html>\n"


# 参照 v1 相当のマーカーなし手書き HTML (AC-C20-08)
LEGACY_HTML = """<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>手書き資料</title></head>
<body>
<h1>手書き資料</h1>
<section id="intro">
  <h2>導入</h2>
  <div class="step-row"><div>元データを集める</div></div>
  <div class="prompt-box"><pre>目的:\n  集計する</pre></div>
  <p>この段落はどの型にも当てはまらない地の文である。</p>
  <div class="pop-chips"><button>日次</button></div>
</section>
</body>
</html>
"""


# --------------------------------------------------------------------------
# 期待される構成データ (逆抽出結果)
# --------------------------------------------------------------------------

def expected_document_fields():
    """preserved_exact のうち文書レベルのもの + preserved_only_with_markers のメタ。"""
    return {
        "title": DOC_META["title"],
        "date": DOC_META["date"],
        "doc_type": DOC_META["doc_type"],
        "subject_slug": DOC_META["subject_slug"],
        "theme": DOC_META["theme"],
        "purpose": DOC_META["purpose"],
        "background": DOC_META["background"],
        "goal": DOC_META["goal"],
        "reader": DOC_META["reader"],
        "prior_knowledge_level": DOC_META["prior_knowledge_level"],
        "essential_problem": DOC_META["essential_problem"],
        # R21 / R22。属性 1 本で運ぶ型フィールドは型ごと復元される
        # (must_remember_max は整数・notes_enabled は真偽値)。
        "presentation_order": DOC_META["presentation_order"],
        "detail_level": DOC_META["detail_level"],
        "evidence_depth": DOC_META["evidence_depth"],
        "must_remember_max": int(DOC_META["must_remember_max"]),
        "notes_enabled": DOC_META["notes_enabled"] == "true",
        "attainment_level": DOC_META["attainment_level"],
        "focus_theme": list(FOCUS_THEME),
        "must_remember": list(MUST_REMEMBER),
        "no_need_to_remember": list(NO_NEED_TO_REMEMBER),
        "target_tasks": [dict(t) for t in TARGET_TASKS],
    }


def comparable_projection(config):
    """roundtrip_granularity.comparable_projection: provenance ブロック全体を除く。"""
    out = {k: v for k, v in config.items() if k != "provenance"}
    for key in PROVENANCE_KEYS:
        out.pop(key, None)
    return out


class C20TestCase(unittest.TestCase):
    """plugin root を temp へ複製し、そこの script を叩く基底クラス。

    部品カタログ (config/handout-parts.json) を書き換えても挙動が追従することを
    検査するため、毎テスト独立したコピーを使う。
    """

    maxDiff = None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "plugin-root"
        if SRC_PLUGIN_ROOT.exists():
            shutil.copytree(SRC_PLUGIN_ROOT, self.root,
                            ignore=shutil.ignore_patterns("tests", "__pycache__"))
        else:
            self.root.mkdir(parents=True)
        self.out = self.tmp / "out.json"
        self.report = self.tmp / "report.json"

    def tearDown(self):
        self._tmp.cleanup()

    # ---- 入力ファイル ----------------------------------------------------

    def write_html(self, html=None, name="handout.html", encoding="utf-8"):
        path = self.tmp / name
        path.write_text(full_html() if html is None else html, encoding=encoding)
        return path

    def write_json(self, obj, name="compare.json", raw=None):
        path = self.tmp / name
        if raw is not None:
            path.write_bytes(raw)
        else:
            path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    # ---- 実行 ------------------------------------------------------------

    def run_cli(self, *args, **kwargs):
        return run(list(args), self.root, **kwargs)

    def extract(self, html=None, *extra, out=None, **kwargs):
        """--html を書いてから起動する。out=False なら --out を付けない。"""
        path = html if isinstance(html, Path) else self.write_html(html)
        args = ["--html", path]
        if out is not False:
            args += ["--out", out or self.out]
        args += list(extra)
        return self.run_cli(*args, **kwargs), path

    # ---- assert ----------------------------------------------------------

    def assert_exit(self, res, expected):
        self.assertEqual(
            expected,
            res.returncode,
            "exit code が %d でない (実際 %d)\nstdout=%r\nstderr=%r"
            % (expected, res.returncode, res.stdout, res.stderr),
        )

    def assert_diag(self, res, code, contains=None):
        """stderr に '<診断コード> ...' の行があること (1 行 1 件・先頭が診断コード)。"""
        lines = [l for l in res.stderr.splitlines() if l.split(" ")[0] == code]
        self.assertTrue(
            lines,
            "stderr に診断コード %s の行が無い\nstderr=%r\nexit=%d"
            % (code, res.stderr, res.returncode),
        )
        if contains is not None:
            self.assertTrue(
                any(contains in l for l in lines),
                "%s の行に %r が含まれない: %r" % (code, contains, lines),
            )
        return lines

    def assert_no_diag(self, res, code):
        lines = [l for l in res.stderr.splitlines() if l.split(" ")[0] == code]
        self.assertFalse(lines, "出るべきでない診断 %s が出ている: %r" % (code, lines))

    def assert_not_written(self, path):
        self.assertFalse(Path(path).exists(),
                         "書かれてはならない出力が存在する: %s" % path)

    def out_bytes(self, out=None):
        out = Path(out or self.out)
        self.assertTrue(out.exists(), "--out が書き出されていない: %s" % out)
        return out.read_bytes()

    def out_text(self, out=None):
        return self.out_bytes(out).decode("utf-8")

    def read_out(self, out=None):
        return json.loads(self.out_text(out))

    def summary(self, res):
        """stdout の 1 行サマリを key=value の dict へ分解する。"""
        first = (res.stdout.splitlines() or [""])[0]
        self.assertTrue(
            first.startswith("EXTRACTED "),
            "stdout の 1 行目が 1 行サマリ (EXTRACTED ...) でない: %r" % res.stdout,
        )
        fields = {}
        for token in first.split()[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key] = value
        return fields

    # ---- 参照データ ------------------------------------------------------

    def parts_catalog_path(self):
        return self.root / PARTS_CATALOG_RELPATH

    def parts_catalog(self):
        """id 語彙の単一正本 (P03 Y-05)。実装前は plan 側の正本へ退避する。"""
        path = self.parts_catalog_path()
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(
            PLAN_PARTS_CATALOG.exists(),
            "部品カタログ正本が plan 側にも無い: %s" % PLAN_PARTS_CATALOG,
        )
        return json.loads(PLAN_PARTS_CATALOG.read_text(encoding="utf-8"))

    def catalog_ids(self):
        return {p["id"] for p in self.parts_catalog()["parts"]}

    def write_parts_catalog(self, catalog):
        path = self.parts_catalog_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def script_path(self):
        return self.root / SCRIPT_RELPATH

    def script_source(self):
        script = self.script_path()
        self.assertTrue(
            script.exists(),
            "実装 %s が存在しない (build_target: plugins/guide-doc-generator/scripts/"
            "extract-handout-config.py)" % script,
        )
        return script.read_text(encoding="utf-8")

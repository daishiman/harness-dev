#!/usr/bin/env python3
# /// script
# name: validate-report-visual
# purpose: output_mode=report の report.html を静的解析し report 特有の視覚崩れ (section 構造欠落 / 1項目1ビジュアル逸脱 / 段落過密 / 未解決プレースホルダ / 印刷letterbox兆候) を fail-closed 検出する plugin-root glue。slide の verify-slides.js/validate-print.js に対応する report 版の決定論視覚ゲート。CLI と import (pytest) 両対応・Python 標準ライブラリのみ。
# inputs:
#   - CLI: <report.html> [--structure <report-structure.json>] [--require-structure] [--strict] [--json]
# outputs:
#   - stdout: JSON (呼び出し側が食える検証結果 findings[])
#   - exit: 0=崩れ無し (PASS) / 1=崩れ検出 (fail-closed) / 2=usage・ファイル不在。
#           --require-structure では --structure 欠落を usage error (2) にする。
#           --strict では warn 兆候も 1 に昇格する。
# contexts: [glue]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""report.html の決定論視覚ゲート (fail-closed)。

C7 で vendor/ は byte 不可侵のため、report.html 用の視覚崩れ検出を plugin-root
scripts/ に Python 標準ライブラリのみ (html.parser + re) で新設する。slide が持つ
verify-slides.js (16:9比率) / validate-print.js (letterbox) に対応する report 版。

検査項目 (report gate は --require-structure + --structure が必須。互換用の HTML 単体診断は可):
  C1 section-structure  : h1 (report-title) 起点と report-section/h2 見出し階層の存在。
                          --structure 指定時は sections[].id/heading の欠落を fail 検出。
  C2 one-visual         : 1セクション1ビジュアル原則。過剰重複を閾値超過で warn/fail。
                          render フォールバック図 (描画失敗の兆候) も検出。
  C3 paragraph-density  : 極端に長い連続段落・段落数過密 (オーバーフロー兆候)。
  C4 placeholder        : 未解決プレースホルダ ({{...}}) 残存・空セクションを fail 検出。
  C5 print-letterbox    : @media print 内の cover/16:9 letterbox 兆候 (slide 用印刷指定の
                          report 混入)・@page landscape を warn 検出 (任意)。
  C6 structuring(1.1.0) : 下限=羅列 / 上限=過剰構造化・強調過多 の双方向 warn (body[]/narrative/強調密度)。
  C7 structuring(1.2.0) : through-line(文書アーク/節間接続)・色覚非依存の強調(非色第2チャネル)・
                          reportType 横断要素 role・多様性<適合性(羅列の床)・render 忠実度
                          (structure が新block/throughLine/placement を宣言→html 反映) を検査。
                          render 忠実度の不一致は fail、密度/流れ系は warn (strict 昇格)。
  C8 essence-visual(1.3.0): 論理構造を展開する実質節(分析/主張/課題/解決/所見/背景/影響/本文)が
                          内容を一目化する本質図解(非 none visual)を持つか。表・テキストのみで関係構造を
                          説明する『なんとなく表』(図解不在)を warn (strict 昇格)。要約/結論/次アクション等は
                          text-first 許容で対象外 (結論への図解強制=逆退化を避ける・意味判定は reviewer)。

exit code 規約:
  - 0: 崩れ無し (PASS)。--strict 時は warn も無い。
  - 1: 崩れ検出 (fail-closed)。--strict では warn 兆候も 1 に昇格。
  - 2: usage / report.html or --structure ファイル不在 /
       --require-structure 時の --structure 欠落 (fail-closed)。

pytest からは analyze_report() / check_report() を import して使う。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# 検査閾値の SSOT。ここが唯一の値域定義 (テストは thresholds= で上書き可)。
DEFAULT_THRESHOLDS = {
    "max_visuals_per_section": 1,   # 1項目1ビジュアル。これを超えると warn。
    "visuals_fail_bound": 3,        # ビジュアルがこの数以上で fail (過剰重複)。
    "para_len_warn": 2000,          # 単一段落の文字数がこれ以上で warn。
    "para_len_fail": 3800,          # 単一段落の文字数がこれ以上で fail (schema max 4000 近傍)。
    "section_para_warn": 15,        # 1セクションの段落数がこれ以上で warn (過密)。
    # -- 1.1.0 構造化ゲート (羅列←→過剰構造化 の双方向) --
    "max_highlights_per_section": 6,  # 1セクションの ==highlight== (mark) がこれ超で warn (強調過多)。
    "max_keypoints_per_section": 2,   # 1セクションの key-point ボックスがこれ超で warn (強調過多)。
    # -- 1.2.0 構造化ゲート (through-line / 色覚非依存 / reportType 横断 / 多様性<適合性) --
    "doc_highlight_budget": 24,       # 文書全体の ==highlight== 総数上限 (per-section cap に加えた doc-level 予算)。
    "monotone_block_floor": 6,        # 1セクションの body[] が同一 block 型のみでこの数以上 → 羅列 warn (床)。
    "throughline_min_sections": 4,    # section 数がこれ以上の文書で meta.throughLine 未宣言 → warn (文書アーク欠落)。
    "transition_min_sections": 3,     # section 数がこれ以上で transition が皆無 → warn (節が飛び石・流れが切れる)。
    "parts_suggest_sections": 12,     # length=deep でこれ以上の節数なら throughLineParts(part 単位 sub-arc) 未宣言を warn (大規模文書の道標)。
}

# narrative(節内論理展開) を必要とする role。report-narrative-logic.md §6.1 の role→narrative 表 (SSOT正本) と
# 1:1 で対応させる: 「期待」群=REQUIRED / 「不要」群+「文脈依存(learning系)」群=OPTIONAL。
# schema の section.role enum(全22値) を過不足なく二分類し fall-through を無くす。
# 文脈依存(concept/question/conclusion/diagram-understanding/example-application/caution) は「節が主張を
# 持てば narrative 期待」という意味判定であり機械では測れないため、機械ゲートは安全側(OPTIONAL=warn しない)へ
# 倒し、主張を持つのに narrative 欠落という意味的欠陥は report-quality-reviewer(C24) が判定する(二層分離)。
_NARRATIVE_REQUIRED_ROLES = {
    "analysis", "argument", "problem", "solution", "finding", "background", "impact", "body",
}
_NARRATIVE_OPTIONAL_ROLES = {
    "reference", "procedure", "summary", "overview", "prerequisite", "step", "cta", "next-action",
    "concept", "question", "conclusion", "diagram-understanding", "example-application", "caution",
}
# 二分類は Mutually Exclusive を import 時に自己検査する (将来 enum 追加時に片方へ二重登録した desync を早期検出)。
# Collectively Exhaustive (両集合 == schema role enum) は schema を要するため tests の
# test_120_role_classification_covers_all_schema_roles が担保する。
assert _NARRATIVE_REQUIRED_ROLES.isdisjoint(_NARRATIVE_OPTIONAL_ROLES), (
    "role narrative 分類が重複: " + str(sorted(_NARRATIVE_REQUIRED_ROLES & _NARRATIVE_OPTIONAL_ROLES))
)

# 1.3.0 本質図解 (essence-visual) を必須とする role。narrative 必須 role のうち、
# 明確に *関係構造* を持つ分析系に限定する。汎用の body / 叙述寄りの background は
# 図解を機械強制しない (過剰強制=『なんとなく図』の逆退化を避け、guidance/reviewer に委ねる)。
_ESSENCE_REQUIRED_ROLES = _NARRATIVE_REQUIRED_ROLES - {"body", "background"}

# reportType → 本質的に含むべき横断要素の role 群 (report-narrative-logic.md 正本の抜粋・機械検査可能な subset)。
# 意味の充足 (要約が本当に要約か) は report-quality-reviewer に委ね、ここでは role の存在のみ決定論検査する。
_REPORTTYPE_REQUIRED_ROLES = {
    "internal-analysis": {"summary", "next-action"},
    "client-proposal": {"solution", "cta"},
    "tech-doc": {"prerequisite", "reference"},
    "learning": {"question", "conclusion"},
}

# 未解決プレースホルダ ({{...}} / {{}})。pre/code/svg 内は走査対象外にして
# mermaid の hexagon 記法 A{{...}} 等の誤検出を避ける。
_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]*\}\}")

# インライン脚注参照 [^id] (render-report.js の inlineMd と同じ id 文法)。
_FOOTNOTE_REF_RE = re.compile(r"\[\^([a-z0-9][a-z0-9-]*)\]", re.IGNORECASE)

# 走査から外す (プレースホルダ誤検出源) タグ。style/script は data 自体を捨てる。
_SUPPRESS_TAGS = {"pre", "code", "svg"}


class _ReportParser(HTMLParser):
    """report.html を1パスで走査し、検査に必要な事実だけを収集する。

    収集物:
      - h1_texts[]            : report-title 起点の h1 テキスト。
      - sections[]            : {id, heading, p_count, max_p_len, text_len,
                                 figure_count, img_count, table_count, has_fallback}
      - style_text            : <style> 内容 (連結)。@media print 解析用。
      - placeholder_text      : pre/code/svg/script/style を除いた可視テキスト。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1_texts: list[str] = []
        self.sections: list[dict] = []
        self._section_stack: list[dict] = []
        self._figure_depth = 0
        self._suppress_depth = 0
        self._in_style = False
        self._in_script = False
        self._style_buf: list[str] = []
        self._placeholder_buf: list[str] = []
        self.toc_sidebar_count = 0
        self._capture: str | None = None
        self._capture_buf: list[str] = []

    # -- 収集アクセサ --------------------------------------------------------
    @property
    def style_text(self) -> str:
        return "".join(self._style_buf)

    @property
    def placeholder_text(self) -> str:
        return "".join(self._placeholder_buf)

    def _cur_section(self):
        return self._section_stack[-1] if self._section_stack else None

    # -- start (通常/自己終了 両方) ------------------------------------------
    def handle_starttag(self, tag, attrs):
        self._on_start(tag, dict(attrs), self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._on_start(tag, dict(attrs), self_closing=True)

    def _on_start(self, tag, attrd, self_closing):
        cls = attrd.get("class", "") or ""
        class_tokens = set(cls.split())

        if tag == "style":
            self._in_style = True
            return
        if tag == "script":
            self._in_script = True
            return

        # TOC の有無は CSS セレクタでなく、実際の nav DOM だけを事実とする。
        # buildReportCss() は TOC が無い report にも .report-toc--sidebar 規則を
        # 常時出力するため、CSS token 判定は scrollspy 欠落の偽陽性になる。
        if tag == "nav" and "report-toc--sidebar" in class_tokens:
            self.toc_sidebar_count += 1

        if tag in _SUPPRESS_TAGS and not self_closing:
            self._suppress_depth += 1

        if tag == "section" and "report-section" in cls:
            self._section_stack.append(
                {
                    "id": attrd.get("id", ""),
                    "heading": "",
                    "p_count": 0,
                    "max_p_len": 0,
                    "text_len": 0,
                    "figure_count": 0,
                    "img_count": 0,
                    "table_count": 0,
                    "content_count": 0,  # 段落以外の構造化本文ブロック (リスト/定義リスト/タスク/強調/引用等) の存在量。空セクション誤判定を防ぐ。
                    "has_fallback": False,
                }
            )
            return

        sec = self._cur_section()

        # 段落以外の構造化本文ブロックも「本文あり」として計上 (body block は <p> を出さないものが多い)。
        if sec is not None:
            if tag in ("li", "dt", "dd"):
                sec["content_count"] += 1
            elif any(
                marker in cls
                for marker in (
                    "report-keypoint", "report-stat", "report-quote", "report-callout",
                    "report-subheading", "report-deflist", "report-tasklist", "report-footnotes",
                    "report-list", "report-narrative", "report-code",
                )
            ):
                sec["content_count"] += 1

        if tag == "h1":
            self._start_capture("h1")
        elif tag == "h2" and sec is not None:
            self._start_capture("h2")
        elif tag == "p" and sec is not None:
            sec["p_count"] += 1
            self._start_capture("p")
        elif tag == "figure":
            if sec is not None and "report-visual" in cls:
                sec["figure_count"] += 1
                if "report-visual--fallback" in cls:
                    sec["has_fallback"] = True
            if not self_closing:
                self._figure_depth += 1
        elif tag == "img":
            # figure 直下の img は figure 側でビジュアル計上済み。単独 img のみ数える。
            if sec is not None and self._figure_depth == 0:
                sec["img_count"] += 1
        elif tag == "table":
            if sec is not None:
                sec["table_count"] += 1

    # -- end -----------------------------------------------------------------
    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False
            return
        if tag == "script":
            self._in_script = False
            return
        if tag in _SUPPRESS_TAGS and self._suppress_depth > 0:
            self._suppress_depth -= 1
        if tag == "figure" and self._figure_depth > 0:
            self._figure_depth -= 1
        if self._capture and tag == self._capture:
            self._finish_capture()
        if tag == "section" and self._section_stack:
            self.sections.append(self._section_stack.pop())

    # -- data ----------------------------------------------------------------
    def handle_data(self, data):
        if self._in_style:
            self._style_buf.append(data)
            return
        if self._in_script:
            return
        if self._capture:
            self._capture_buf.append(data)
        # プレースホルダ走査対象は pre/code/svg を除く可視テキストのみ。
        if self._suppress_depth == 0:
            self._placeholder_buf.append(data)

    # -- capture helpers -----------------------------------------------------
    def _start_capture(self, tag):
        if self._capture:  # 入れ子開始は無視 (見出し/段落は入れ子にならない)。
            return
        self._capture = tag
        self._capture_buf = []

    def _finish_capture(self):
        text = "".join(self._capture_buf).strip()
        if self._capture == "h1":
            self.h1_texts.append(text)
        elif self._capture == "h2":
            sec = self._cur_section()
            if sec is not None and not sec["heading"]:
                sec["heading"] = text
        elif self._capture == "p":
            sec = self._cur_section()
            if sec is not None:
                length = len(text)
                sec["text_len"] += length
                if length > sec["max_p_len"]:
                    sec["max_p_len"] = length
        self._capture = None
        self._capture_buf = []


def analyze_report(html: str) -> dict:
    """report.html を静的解析して検査用の事実 dict を返す (副作用なし)。

    返り値: {"h1_texts": [...], "sections": [ {..} ], "style_text": str,
             "placeholders": [str], "print_css": str, "toc_sidebar_count": int}
    """
    parser = _ReportParser()
    parser.feed(html)
    parser.close()
    # section を閉じ忘れた malformed HTML でも残りを回収する。
    while parser._section_stack:
        parser.sections.append(parser._section_stack.pop())

    placeholders = sorted(set(_PLACEHOLDER_RE.findall(parser.placeholder_text)))
    return {
        "h1_texts": parser.h1_texts,
        "sections": parser.sections,
        "style_text": parser.style_text,
        "placeholders": placeholders,
        "print_css": _extract_print_css(parser.style_text),
        "toc_sidebar_count": parser.toc_sidebar_count,
    }


def _extract_print_css(style_text: str) -> str:
    """<style> 内の @media print { ... } ブロックを (簡易・決定論) 抽出して連結する。"""
    blocks: list[str] = []
    idx = 0
    needle = "@media print"
    lowered = style_text.lower()
    while True:
        pos = lowered.find(needle, idx)
        if pos == -1:
            break
        brace = style_text.find("{", pos)
        if brace == -1:
            break
        depth = 0
        end = brace
        for i in range(brace, len(style_text)):
            ch = style_text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        blocks.append(style_text[brace + 1 : end])
        idx = end + 1
    return "\n".join(blocks)


def _visual_count(sec: dict) -> int:
    """1セクションの hero ビジュアル数 (figure.report-visual + 単独 img)。

    1.1.0+ 設計で表(table)は body ブロック=構造化本文であり hero visual ではないため
    『1項目1ビジュアル』のカウントには含めない (図解+補助表を持つ正当な節の誤爆を防ぐ)。
    """
    return sec["figure_count"] + sec["img_count"]


def _has_content(sec: dict) -> bool:
    """セクションが実質的な本文/ビジュアルを持つか (空セクション誤判定を防ぐ)。

    段落テキスト・hero ビジュアル・表・段落以外の構造化ブロック(リスト/定義/タスク/強調等)の
    いずれかがあれば非空とみなす。
    """
    return (
        sec["text_len"] > 0
        or _visual_count(sec) > 0
        or sec["table_count"] > 0
        or sec["content_count"] > 0
    )


def _check_essence_visual(structure, add) -> None:
    """1.3.0 本質図解カバレッジ (essence-visual)。

    明確な関係構造を持つ論理節 (_ESSENCE_REQUIRED_ROLES = 分析/主張/課題/解決/所見/影響)
    は、その節の論理構造を『パッと見て』掴ませる非 none ビジュアルを 1 枚持つべき。表・テキスト
    のみで関係構造を説明する『なんとなく表』(＝図解の不在) を塞ぐ。

    - 対象 role は narrative 必須 role と同一 SSOT (argue/analyze する節)。summary/next-action/
      conclusion/concept/example-application 等 (_NARRATIVE_OPTIONAL_ROLES) は text-first を許容し咎めない
      (結論・要約に図解を強制すると『なんとなく図』の逆退化を招くため、機械ゲートは論理節に限定する)。
    - 図解が本質を突くか/内容と 1:1 か等の意味判定は report-quality-reviewer に委ねる (二層分離)。
    - severity は C6/C7 のカバレッジ系と同じ warn 通常 / --strict で fail 昇格。
    """
    struct = structure if isinstance(structure, dict) else None
    if struct is None:
        return
    for s in struct.get("sections") or []:
        if not isinstance(s, dict):
            continue
        role = s.get("role") or "body"
        if role not in _ESSENCE_REQUIRED_ROLES:
            continue
        visual = s.get("visual") if isinstance(s.get("visual"), dict) else {}
        kind = visual.get("kind")
        if kind in (None, "none"):
            add(
                "essence-visual",
                "warn",
                f"section '{s.get('id') or '?'}'(role={role}): 本質図解が無い "
                f"(論理構造を持つ節は内容を一目化する図解を1枚持つ・表/テキストのみは『なんとなく表』の兆候)",
                s.get("id"),
            )


def _check_structuring_1_1_0(html, structure, html_sections, th, add) -> None:
    """1.1.0 構造化ゲート (report-narrative-logic.md)。

    下限=『羅列でも破綻ゼロなら PASS』を塞ぐ / 上限=『構造過剰・強調過多でも多様性ありなら PASS』を塞ぐ
    双方向の warn を出す。block 型は structure(権威源) を、要点強調密度は html を主に使う。
    意味の正否 (論理が本質を突くか等) は report-quality-reviewer の意味判定に委ねる (二層分離)。
    """
    struct = structure if isinstance(structure, dict) else None
    if struct is not None:
        meta = struct.get("meta") or {}
        sv = meta.get("schemaVersion", "1.0.0")
        length = meta.get("length")
        secs = [s for s in (struct.get("sections") or []) if isinstance(s, dict)]
        # 構造化を要求する条件: 1.1.0/1.2.0 を宣言 or length=deep(腰を据えて読む長尺) or 実際に body/narrative 使用。
        # 1.2.0 を宣言しつつ body/narrative を一切使わない『opt-in したのに退化』を穴にしない (ダブル・ループ)。
        is_110 = sv in ("1.1.0", "1.2.0") or length == "deep" or any(s.get("body") or s.get("narrative") for s in secs)
        if is_110:
            any_body = False
            for s in secs:
                sid = s.get("id")
                body = s.get("body") if isinstance(s.get("body"), list) else []
                paras = s.get("paragraphs") if isinstance(s.get("paragraphs"), list) else []
                if body:
                    any_body = True
                if body and paras:
                    add("structuring", "warn",
                        f"section '{sid or '?'}': body[] と paragraphs[] を二重充填 (body[] 優先ゆえ paragraphs[] は描画されない・どちらかに寄せる)", sid)
                # 1.2.0: role-aware。reference/procedure/summary 等は narrative 不要 (弧の強制は category error)。
                role = (s.get("role") or "body")
                if body and not s.get("narrative") and role not in _NARRATIVE_OPTIONAL_ROLES:
                    add("structuring", "warn",
                        f"section '{sid or '?'}'(role={role}): narrative(本質課題→解決→活用) が無い (節内論理展開を宣言すると羅列を防げる)", sid)
                kp = sum(1 for b in body if isinstance(b, dict) and b.get("type") == "key-point")
                if kp > th["max_keypoints_per_section"]:
                    add("emphasis-overuse", "warn",
                        f"section '{sid or '?'}': key-point が {kp}個 (強調過多・節あたり0〜{th['max_keypoints_per_section']}個に絞る)", sid)
            if secs and not any_body:
                trigger = "1.2.0" if sv == "1.2.0" else ("1.1.0" if sv == "1.1.0" else "length=deep")
                add("structuring", "warn",
                    f"構造化({trigger})が要求されるが body[](構造化ブロック) を一切使っていない (全節 paragraphs[] のみ・表/コード/リスト/強調ボックスが無く『情報の羅列』の兆候)")

    # html 駆動 (section chunk 単位の強調密度)。structure が key-point を検査済みなら html 側は highlight のみ。
    chunks = re.split(r"<section\b", html)[1:]
    for i, chunk in enumerate(chunks):
        hl = len(re.findall(r'<mark class="report-hl"', chunk))
        if hl > th["max_highlights_per_section"]:
            add("emphasis-overuse", "warn",
                f"section #{i + 1}: 要点ハイライト(==…==) が {hl}箇所 (強調過多・要点に絞る)")
        if struct is None:
            kp = len(re.findall(r'class="report-keypoint', chunk))
            if kp > th["max_keypoints_per_section"]:
                add("emphasis-overuse", "warn",
                    f"section #{i + 1}: key-point ボックスが {kp}個 (強調過多・節あたり0〜{th['max_keypoints_per_section']}個)")


def _check_structuring_1_2_0(html, structure, facts, th, add) -> None:
    """1.2.0 構造化ゲート (report-narrative-logic.md L4)。

    through-line(文書アーク/節間接続)・色覚非依存の強調・reportType 横断要素・
    多様性<適合性(羅列の床のみ叩く)・render 忠実度(structure 宣言→html 反映) を検査する。
    意味の正否は report-quality-reviewer に委ねる (二層分離)。
    """
    struct = structure if isinstance(structure, dict) else None
    meta = (struct.get("meta") or {}) if struct else {}
    sv = meta.get("schemaVersion", "1.0.0")
    secs = [s for s in (struct.get("sections") or []) if isinstance(s, dict)] if struct else []
    is_120 = sv == "1.2.0" or bool(meta.get("throughLine")) or any(
        s.get("transition") or (s.get("role") == "argument") for s in secs
    ) or any(
        isinstance(b, dict) and b.get("type") in {"definition-list", "footnote", "task-list"}
        for s in secs for b in (s.get("body") or [])
    )

    # -- structure 駆動: through-line/横断要素/多様性 は 1.2.0 文書にのみ適用 (旧 doc への誤発火を防ぐ) --
    if struct is not None and secs and is_120:
        # (1) 文書アーク throughLine: 節数が多い/1.2.0 宣言なのに未宣言 → warn。
        #     ただし length=brief は §6.3 マトリクスで throughLine を opt-out 許容 (短報にアークを強制しない)。
        if meta.get("length") != "brief" and (sv == "1.2.0" or len(secs) >= th["throughline_min_sections"] or meta.get("length") == "deep") and not (meta.get("throughLine") or "").strip():
            add("through-line", "warn",
                f"文書アーク(meta.throughLine)が未宣言 (section {len(secs)}節・冒頭=本質課題→本論=解決→結=活用の通し筋を宣言すると飛び石を防げる)")
        # 大規模文書(多節・deep)は throughLine を part 単位へ階層化すると道標になる。
        if meta.get("length") == "deep" and len(secs) >= th["parts_suggest_sections"] and not (meta.get("throughLineParts") if isinstance(meta.get("throughLineParts"), list) else None):
            add("through-line", "warn",
                f"大規模文書({len(secs)}節・deep)だが throughLineParts(part 単位 sub-arc)が未宣言 (単一 throughLine に収まらない弧を部へ分解すると読者の道標になる)")
        # (2) 節間接続 transition: 節が多いのに1つも transition が無い → warn。
        if len(secs) >= th["transition_min_sections"]:
            n_trans = sum(1 for s in secs if (s.get("transition") or "").strip())
            if n_trans == 0:
                add("through-line", "warn",
                    f"節間接続(section.transition)が皆無 ({len(secs)}節・節末の橋渡し1文で流れを繋ぐ)")
        # (3) reportType 横断要素: 型別に本質的に含むべき role の存在を決定論検査 (意味は quality-reviewer)。
        rt = meta.get("reportType")
        required = _REPORTTYPE_REQUIRED_ROLES.get(rt)
        if required:
            present = {s.get("role") for s in secs if s.get("role")}
            missing = required - present
            if missing:
                add("cross-cutting", "warn",
                    f"reportType='{rt}' の横断要素 role が不足: {sorted(missing)} (report-narrative-logic.md の型別必須要素)")
        # (4) 多様性<適合性: 羅列の床のみ叩く (同一 block 型のみ N 個以上=段落の羅列)。多様性それ自体は加点しない。
        for s in secs:
            body = s.get("body") if isinstance(s.get("body"), list) else []
            if len(body) >= th["monotone_block_floor"]:
                types = {b.get("type") for b in body if isinstance(b, dict)}
                if len(types) == 1 and "paragraph" in types:
                    add("structuring", "warn",
                        f"section '{s.get('id') or '?'}': body[] が全て paragraph ({len(body)}個・段落の羅列。表/リスト/定義リスト/強調で内容に適合する構造化を検討)", s.get("id"))

    # -- render 忠実度/placement live: feature 宣言時のみ発火するので version gate 不要 (self-gating) --
    if struct is not None and secs:
        # (5) render 忠実度: structure が新 block/throughLine を宣言したのに html に反映が無い → fail。
        declared_blocks = {b.get("type") for s in secs for b in (s.get("body") or []) if isinstance(b, dict)}
        block_class = {
            "definition-list": "report-deflist",
            "footnote": "report-footnotes",
            "task-list": "report-tasklist",
        }
        for btype, cls in block_class.items():
            if btype in declared_blocks and cls not in html:
                add("render-fidelity", "fail",
                    f"structure が block type='{btype}' を宣言したが report.html に .{cls} が無い (render-report.js 未反映)")
        if (meta.get("throughLine") or "").strip() and "report-throughline" not in html:
            add("render-fidelity", "fail",
                "meta.throughLine を宣言したが report.html に .report-throughline が無い (render 未反映)")
        if any((s.get("transition") or "").strip() for s in secs) and "report-transition" not in html:
            add("render-fidelity", "fail",
                "section.transition を宣言したが report.html に .report-transition が無い (render 未反映)")
        # (6) placement live 反映: emphasisZone/emphasis を宣言したのに data-emphasis が html に無い → fail。
        wants_emph = any(
            ((s.get("visual") or {}).get("layout") or {}).get("emphasisZone", "normal") not in ("normal", None)
            or ((s.get("visual") or {}).get("layout") or {}).get("emphasis", "normal") not in ("normal", None)
            for s in secs
        )
        if wants_emph and "data-emphasis" not in html:
            add("render-fidelity", "fail",
                "placement.emphasisZone/emphasis を宣言したが report.html に data-emphasis が無い (placement 未 live 反映)")
        # focalPoint も placement live 反映の対象 (readingOrder/emphasisZone と対称・dead field 化を防ぐ)。
        wants_focal = any(
            isinstance(((s.get("visual") or {}).get("layout") or {}).get("focalPoint"), dict)
            or isinstance(s.get("focalPoint"), dict)
            for s in secs
        )
        if wants_focal and "data-focal" not in html:
            add("render-fidelity", "fail",
                "placement.focalPoint/section.focalPoint を宣言したが report.html に data-focal が無い (focalPoint 未 live 反映)")
        # readingOrder も placement live 反映の対象 (emphasisZone/focalPoint と対称に被覆し回帰を捕捉)。
        # readingOrder は視線方向ヒント属性で視覚再配置はしないが、data-reading-order 出力の退行は検出する。
        wants_order = any(
            (s.get("readingOrder") or ((s.get("visual") or {}).get("layout") or {}).get("readingOrder"))
            for s in secs
        )
        if wants_order and "data-reading-order" not in html:
            add("render-fidelity", "fail",
                "section.readingOrder/placement.readingOrder を宣言したが report.html に data-reading-order が無い (readingOrder 未 live 反映)")
        # narrative の essence系(essence/approach/leverage)と logic[] を併載すると render は essence系を優先し
        # logic[] を黙って描画しない (schema は両形を許容するが render は排他)。併載を warn で顕在化する。
        for s in secs:
            nar = s.get("narrative")
            if isinstance(nar, dict) and any(nar.get(k) for k in ("essence", "approach", "leverage")) and nar.get("logic"):
                add("structuring", "warn",
                    f"section '{s.get('id') or '?'}': narrative に essence系と logic[] を併載 (render は essence系を優先し logic[] を描画しない・一方へ寄せる)", s.get("id"))

        # footnote インライン参照 [^id] の係り先健全性: 参照 id に対応する footnote(id) が無ければ warn (dangling ref / id typo)。
        fn_ids: set = set()
        ref_ids: set = set()
        for s in secs:
            for para in (s.get("paragraphs") or []):
                if isinstance(para, str):
                    ref_ids.update(m.lower() for m in _FOOTNOTE_REF_RE.findall(para))
            for b in (s.get("body") or []):
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "footnote":
                    for fn in (b.get("footnotes") or []):
                        if isinstance(fn, dict) and fn.get("id"):
                            fn_ids.add(str(fn["id"]).lower())
                if isinstance(b.get("text"), str):
                    ref_ids.update(m.lower() for m in _FOOTNOTE_REF_RE.findall(b["text"]))
                for item in (b.get("items") or []):
                    if isinstance(item, str):
                        ref_ids.update(m.lower() for m in _FOOTNOTE_REF_RE.findall(item))
        dangling = ref_ids - fn_ids
        if dangling:
            add("footnote-ref", "warn",
                f"インライン脚注参照 [^id] に対応する footnote(id) が無い: {sorted(dangling)} (dangling ref / id typo・同一文書内に id 付き footnote を置く)")

    # -- html 駆動 (render 品質・色覚非依存 / doc-level 予算) ---------------------
    # (7) 色覚非依存の第2チャネル: mark.report-hl を使うのに CSS block が非色属性 (font-weight/underline) を持たない → warn。
    if '<mark class="report-hl"' in html:
        m = re.search(r"mark\.report-hl\s*\{([^}]*)\}", facts["style_text"])
        css = (m.group(1) if m else "")
        has_second_channel = bool(re.search(r"font-weight\s*:\s*[6-9]\d\d", css)) or ("underline" in css) or ("text-decoration" in css)
        if not has_second_channel:
            add("colorblind-safe", "warn",
                "要点強調(mark.report-hl)が色単一チャネル (font-weight/underline 等の非色第2チャネルを併存させ色覚非依存にする)")
    # (8) doc-level highlight 予算: 文書全体の ==highlight== 総数上限 (per-section cap に加えた総量)。
    total_hl = len(re.findall(r'<mark class="report-hl"', html))
    if total_hl > th["doc_highlight_budget"]:
        add("emphasis-overuse", "warn",
            f"文書全体の要点ハイライトが {total_hl}箇所 (doc 予算 {th['doc_highlight_budget']} 超・強調の希釈。真の要点に絞る)")


def _check_uiux_shape(html, facts, add) -> None:
    """第3次 UI/UX レイアウトの shape 検査 (render-report.js が emit する接合トークンの回帰保護)。

    render 側 CSS/JS が screen/print/狭画面の挙動を出力しても、それを守る決定論ゲートが無ければ
    トークンが消えても緑のまま退行する (窮屈/print破壊/degrade崩れ)。ここは CSS・DOM 構造の『存在』
    検査に限り、意味適合 (読みやすいか等) は report-quality-reviewer(C24) へ委ねる (二層分離)。
    essence-visual (図解の要否) は _check_essence_visual が担う。
    """
    css = facts["style_text"]
    css_l = css.lower()
    # 完全な report render (render-report.js buildReportCss 出力) のみ対象。
    # buildReportCss は必ず --report-width を emit するため、これを full-render の marker とする。
    # 最小 fixture / 部分 HTML (他ロジックの単体検査) は対象外にし誤爆を防ぐ。
    if "--report-width" not in css_l:
        return
    print_css = facts["print_css"].lower()
    html_l = html.lower()
    # CSS 規則は TOC の非存在証明にならない。実 DOM に sidebar nav がある時だけ
    # scrollspy 契約を要求する (TOC なし report への偽陽性を防ぐ)。
    has_toc = facts["toc_sidebar_count"] > 0

    # screen 読書レイアウトの接合トークン (消えると『空白>本文』の窮屈へ退行)
    screen_tokens = [
        (".report-layout", "screen 2カラム grid (.report-layout)"),
        ("--report-measure", "本文可読幅トークン (--report-measure)"),
        ("--report-page-max", "実効利用幅トークン (--report-page-max)"),
    ]
    for token, label in screen_tokens:
        if token not in css_l:
            add("uiux-shape", "warn", f"screen レイアウトの接合トークン欠落: {label} (render 側で消えると窮屈/退行の回帰)")
    # sticky TOC + scrollspy (TOC を持つ report のみ要求)
    if has_toc:
        if "is-active" not in css_l:
            add("uiux-shape", "warn", "scrollspy ハイライト (a.is-active) の CSS が無い")
        if "aria-current" not in html_l:
            add("uiux-shape", "warn", "aria-current 同期が無い (現在位置が支援技術/色非依存で辿れない)")
        if "beforeprint" in html_l and "afterprint" not in html_l:
            add("uiux-shape", "warn", "afterprint が無い (印刷後に scrollspy が復帰しない)")
    # print 非退行: @media print 存在 + .report 幅規則 (190mm/A4)
    if not print_css:
        add("uiux-shape", "warn", "@media print ブロックが無い (print/A4 読了体験の非退行を検査できない)")
    elif "190mm" not in print_css and "--report-width" not in print_css and ".report" not in print_css:
        add("uiux-shape", "warn", "@media print 内に .report 幅規則 (190mm/A4) が無い")
    # 狭画面 breakpoint (インライン TOC への graceful degrade)
    if not re.search(r"@media[^{]*max-width", css_l):
        add("uiux-shape", "warn", "狭画面 breakpoint (@media max-width) が無い (インライン TOC への degrade を検査できない)")
    # card 最小幅 (狭幅で潰れない grid)
    if "minmax(" not in css_l:
        add("uiux-shape", "warn", "grid の minmax( による card 最小幅指定が無い (狭幅で潰れる回帰)")
    # タイポ目標レンジ (rem→px @16px base): 本文 16-18px / title:body <=2.2 (過大見出しの窮屈を塞ぐ)
    def _rem_px(name):
        m = re.search(re.escape(name) + r"\s*:\s*([0-9.]+)rem", css)
        return float(m.group(1)) * 16 if m else None
    body_px = _rem_px("--fs-body")
    title_px = _rem_px("--fs-title")
    if body_px is not None and not (15.5 <= body_px <= 18.5):
        add("uiux-shape", "warn", f"本文サイズ --fs-body≈{body_px:.1f}px が 16-18px 読書レンジ外")
    if body_px and title_px and title_px / body_px > 2.3:
        add("uiux-shape", "warn", f"title/body 比 {title_px / body_px:.2f} が 2.2 超 (見出し過大で窮屈)")


def check_report(html, structure=None, strict=False, thresholds=None) -> dict:
    """report.html の視覚崩れを検査し findings[] を返す (fail-closed 判定は passed で表現)。

    返り値:
      {"passed": bool, "strict": bool, "findings": [ {check, severity, section, message} ],
       "summary": {"h1": int, "sections": int, "fail": int, "warn": int}}
      - severity="fail": 崩れ (常に passed=False)。
      - severity="warn": 兆候 (strict のときだけ passed=False へ寄与)。
    """
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update(thresholds)

    facts = analyze_report(html)
    sections = facts["sections"]
    findings: list[dict] = []

    def add(check, severity, message, section=None):
        findings.append(
            {"check": check, "severity": severity, "section": section, "message": message}
        )

    # -- C1: section 構造 ----------------------------------------------------
    if not facts["h1_texts"]:
        add("section-structure", "fail", "h1 (report-title) が無い: 見出し階層の起点欠落")
    if not sections:
        add("section-structure", "fail", "report-section が1つも無い: section 構造欠落")
    for sec in sections:
        if not sec["heading"]:
            add(
                "section-structure",
                "fail",
                f"section '{sec['id'] or '?'}' に h2 見出しが無い",
                sec["id"],
            )

    if structure is not None:
        struct_sections = structure.get("sections", []) if isinstance(structure, dict) else []
        html_ids = {s["id"] for s in sections if s["id"]}
        html_by_id = {s["id"]: s for s in sections if s["id"]}
        for ss in struct_sections:
            sid = ss.get("id") if isinstance(ss, dict) else None
            if sid and sid not in html_ids:
                add(
                    "section-structure",
                    "fail",
                    f"structure の section '{sid}' が report.html に無い (欠落)",
                    sid,
                )
            elif sid:
                want = (ss.get("heading") or "").strip()
                got = (html_by_id[sid]["heading"] or "").strip()
                if want and got and want != got:
                    add(
                        "section-structure",
                        "warn",
                        f"section '{sid}' の見出し不一致: structure='{want}' / html='{got}'",
                        sid,
                    )
        if struct_sections and len(sections) > len(struct_sections):
            add(
                "section-structure",
                "warn",
                f"report.html の section 数 ({len(sections)}) が structure ({len(struct_sections)}) を超過",
            )

    # -- C2: 1項目1ビジュアル / render フォールバック -------------------------
    max_v = th["max_visuals_per_section"]
    fail_bound = th["visuals_fail_bound"]
    for sec in sections:
        vc = _visual_count(sec)
        if vc >= fail_bound:
            add(
                "one-visual",
                "fail",
                f"section '{sec['id'] or '?'}': ビジュアル {vc}個 (過剰重複・1項目1ビジュアル違反)",
                sec["id"],
            )
        elif vc > max_v:
            add(
                "one-visual",
                "warn",
                f"section '{sec['id'] or '?'}': ビジュアル {vc}個 (1項目1ビジュアル逸脱)",
                sec["id"],
            )
        if sec["has_fallback"]:
            add(
                "one-visual",
                "warn",
                f"section '{sec['id'] or '?'}': ビジュアル描画フォールバック (render 失敗の兆候)",
                sec["id"],
            )

    # -- C3: 段落過密 / オーバーフロー兆候 -----------------------------------
    for sec in sections:
        if sec["max_p_len"] >= th["para_len_fail"]:
            add(
                "paragraph-density",
                "fail",
                f"section '{sec['id'] or '?'}': 段落が極端に長い ({sec['max_p_len']}字・オーバーフロー兆候)",
                sec["id"],
            )
        elif sec["max_p_len"] >= th["para_len_warn"]:
            add(
                "paragraph-density",
                "warn",
                f"section '{sec['id'] or '?'}': 段落が長い ({sec['max_p_len']}字)",
                sec["id"],
            )
        if sec["p_count"] >= th["section_para_warn"]:
            add(
                "paragraph-density",
                "warn",
                f"section '{sec['id'] or '?'}': 段落数過密 ({sec['p_count']}段落)",
                sec["id"],
            )

    # -- C4: 未解決プレースホルダ / 空セクション -----------------------------
    for ph in facts["placeholders"]:
        add("placeholder", "fail", f"未解決プレースホルダ残存: {ph}")
    for sec in sections:
        if not _has_content(sec):
            add(
                "placeholder",
                "fail",
                f"section '{sec['id'] or '?'}': 本文もビジュアルも無い (空セクション)",
                sec["id"],
            )

    # -- C5: 印刷 letterbox / cover 兆候 (任意・warn) --------------------------
    print_css = facts["print_css"].lower()
    if re.search(r"object-fit\s*:\s*cover", print_css):
        add("print-letterbox", "warn", "@media print に object-fit:cover (印刷端切れ兆候)")
    if re.search(r"background-size\s*:\s*cover", print_css):
        add("print-letterbox", "warn", "@media print に background-size:cover (印刷端切れ兆候)")
    if re.search(r"aspect-ratio\s*:\s*16\s*/\s*9", print_css):
        add("print-letterbox", "warn", "@media print に 16:9 letterbox 指定 (slide 用印刷指定の report 混入)")
    if re.search(r"@page[^{]*\{[^}]*landscape", facts["style_text"].lower()):
        add("print-letterbox", "warn", "@page が landscape: report は A4 portrait 想定")

    # -- C6: 1.1.0 構造化ゲート (下限=羅列を塞ぐ / 上限=過剰構造化・強調過多を塞ぐ) --------
    _check_structuring_1_1_0(html, structure, sections, th, add)

    # -- C8: 1.3.0 本質図解カバレッジ (論理節の図解不在=『なんとなく表』を塞ぐ) ----------
    _check_essence_visual(structure, add)

    # -- C7: 1.2.0 構造化ゲート (through-line / 色覚非依存 / reportType横断 / render忠実度) --------
    _check_structuring_1_2_0(html, structure, facts, th, add)

    # -- C9: 第3次 UI/UX shape (screen接合トークン/print非退行/狭画面degrade/aria-current/タイポレンジ) --
    _check_uiux_shape(html, facts, add)

    n_fail = sum(1 for f in findings if f["severity"] == "fail")
    n_warn = sum(1 for f in findings if f["severity"] == "warn")
    passed = n_fail == 0 and (not strict or n_warn == 0)

    return {
        "passed": passed,
        "strict": strict,
        "findings": findings,
        "summary": {
            "h1": len(facts["h1_texts"]),
            "sections": len(sections),
            "fail": n_fail,
            "warn": n_warn,
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate-report-visual",
        description="report.html の決定論視覚ゲート (fail-closed): section構造/1項目1ビジュアル/段落過密/プレースホルダ/印刷letterbox",
    )
    p.add_argument("report", help="検査対象 report.html")
    p.add_argument(
        "--structure",
        dest="structure",
        default=None,
        help="report-structure.json (指定時は sections[].id/heading の欠落も照合)",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="warn 兆候も崩れ (exit 1) に昇格させる",
    )
    p.add_argument("--json", action="store_true", help="(既定で JSON 出力・互換用フラグ)")
    p.add_argument(
        "--require-structure",
        action="store_true",
        help="report gate モード: --structure 欠落を fail-open とせず exit 2 で塞ぐ",
    )
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    report_path = Path(args.report)
    if not report_path.is_file():
        sys.stderr.write(f"error: report.html not found: {report_path}\n")
        return 2

    if args.require_structure and not args.structure:
        sys.stderr.write("error: --require-structure 指定時は --structure が必須 (report gate の fail-open 封鎖)\n")
        return 2

    structure = None
    if args.structure:
        struct_path = Path(args.structure)
        if not struct_path.is_file():
            sys.stderr.write(f"error: --structure not found: {struct_path}\n")
            return 2
        try:
            structure = json.loads(struct_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            sys.stderr.write(f"error: --structure not readable JSON: {e}\n")
            return 2

    html = report_path.read_text(encoding="utf-8", errors="replace")
    result = check_report(html, structure=structure, strict=args.strict)

    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

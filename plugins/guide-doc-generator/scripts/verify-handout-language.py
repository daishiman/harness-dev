#!/usr/bin/env python3
# /// script
# name: verify-handout-language
# version: 0.1.0
# purpose: C18 初心者向け言語規約 (用語の初出言い換え・一文の長さ) と日付表記を検査する fail-closed ゲート
# inputs:
#   - argv: --html <path> --config <path> [--out-dir <dir>] [--json-report <path>]
# outputs:
#   - stdout: 違反一覧
#   - file: --json-report の検査結果
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out / --json-report / --config-out で明示された path のみ
# ///
# -*- coding: utf-8 -*-
"""C18 verify-handout-language.py — 初心者向け言語規約 (R11) と日付表記 (R18) の fail-closed ゲート。

契約の正本は plugin-plans/guide-doc-generator/briefs/script-brief-C18.json。
受入判定の正本は plugins/guide-doc-generator/tests/verify-handout-language.py/。

検査する面 (detection):
  LANG-01  宣言用語 (config.glossary[]) が本文の初出で括弧書きの言い換えを伴うか
  LANG-04  各セクションが lead-line をちょうど 1 個持つか
  LANG-05  各セクションが判断軸の一文をちょうど 1 個持つか (存在と形式のみ)
  LANG-06  lead-line < 最初の具体部品 < 判断軸 の順序 (R11 の型)
  LANG-07  できること起点セクションの lead_line が機能名から始まっていないか (R21 C51 の描画テキスト面)
  DATE-01  冒頭の日付表記が yyyy/mm/dd (ゼロ埋め) で暦として実在するか
  DATE-02  日付表記が正規化済み構成データの date と無変換で一致するか
  DATE-03  出力ディレクトリ名の先頭が date の純変換 (replace('/','-')) と一致するか
  DATE-04  文書内の日付表記が一貫しているか (本文中の別日付は info 止まり)

語彙と閾値は本ソースへ列挙せず、次の中立データから読む (読めなければ exit 2):
  config/handout-parts.json      部品 id 語彙 (LANG-06 の『具体部品』述語 = section_scope=="in-section")
  config/handout-sections.json   section_kind 語彙 (LANG-07 の対象種別)
  schemas/handout-config.schema.json
                                 date の書式パターン / 正規化マーカーの値 / 1 行フィールドの長さ上限

日付の単一ソース原則: 本 script は現在日を一切取得しない。真値は --config の date のみ。
"""

from __future__ import annotations

import argparse
import bisect
import datetime
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

# --------------------------------------------------------------------------
# 出力契約 (script-brief-C18.json stdout / stderr)
# --------------------------------------------------------------------------

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

OUT_OF_SCOPE_LINES = [
    "  - 未宣言の専門用語は検出できない。用語の同定は構成データの宣言駆動であり、"
    "宣言されていない語は本ゲートの検査対象にならない",
    "  - 文体の平易さ、および lead-line / 判断軸が意味として妥当かは判定していない "
    "(C06 handout-readability-reviewer の面)",
    "  - 出力ディレクトリ名の種別語彙と主題 slug は判定していない (C19 route-handout-output.py の面)",
]

# 中立データの所在 (cwd 非依存)
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PARTS_CATALOG_PATH = PLUGIN_ROOT / "config" / "handout-parts.json"
SECTIONS_CATALOG_PATH = PLUGIN_ROOT / "config" / "handout-sections.json"
CONFIG_SCHEMA_PATH = PLUGIN_ROOT / "schemas" / "handout-config.schema.json"

# LANG-07 の対象種別 slug。値そのものは config/handout-sections.json が正本であり、
# 本 script は「その語彙に実在すること」を起動時に確認したうえで参照する (不在なら exit 2)。
CAPABILITY_KIND_SLUG = "capability-explainer"

# LANG-07 の比較で落とす記号 (brief detections#LANG-07)。
LANG07_STRIP_SYMBOLS = "・/：:-—"
# LANG-07 の名詞句規則 (brief detections#LANG-07)。
LANG07_NOUN_SUFFIXES = ("機能", "モード", "ツール")
LANG07_PARTICLES = ("は", "を", "の")
# feature 見出しが短すぎるときの誤検出回避 (brief: 2 文字以下は対象外)。
LANG07_MIN_HEADING_LEN = 3

# stderr の evidence に付ける初出位置の前後文字数 (brief stderr)。
EVIDENCE_RADIUS = 40

# 本文中の日付様文字列 (brief detections#DATE-04)。
BODY_DATE_RE = re.compile(r"\d{4}/\d{1,2}/\d{1,2}")

# HTML の void 要素 (閉じタグを持たない) と、本文テキスト T へ含めない要素。
VOID_TAGS = frozenset(
    [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]
)
NON_BODY_TAGS = frozenset(["script", "style", "template", "head"])

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")


# --------------------------------------------------------------------------
# fail-closed
# --------------------------------------------------------------------------


def fail_closed(reason):
    """検査不成立 (exit 2)。ERROR<TAB><reason> をちょうど 1 行だけ出す。"""
    sys.stderr.write("ERROR\t%s\n" % reason)
    raise SystemExit(2)


class _Parser(argparse.ArgumentParser):
    """argparse の usage 出力を出さず、契約どおりの ERROR 行 1 本で落とす。"""

    def error(self, message):  # noqa: D401
        fail_closed("引数が不正: %s" % message)

    def exit(self, status=0, message=None):
        if status:
            fail_closed("引数が不正")
        raise SystemExit(status)


# --------------------------------------------------------------------------
# HTML 収集
# --------------------------------------------------------------------------


class Node(object):
    __slots__ = ("tag", "attrs", "order", "line", "col", "parent", "children", "t_start", "t_end")

    def __init__(self, tag, attrs, order, line, col, parent):
        self.tag = tag
        self.attrs = attrs
        self.order = order
        self.line = line
        self.col = col
        self.parent = parent
        self.children = []
        self.t_start = 0
        self.t_end = 0

    def has_ancestor_tag(self, tag):
        node = self.parent
        while node is not None:
            if node.tag == tag:
                return True
            node = node.parent
        return False

    def descendants(self):
        stack = list(reversed(self.children))
        while stack:
            node = stack.pop()
            yield node
            for child in reversed(node.children):
                stack.append(child)


class Collector(HTMLParser):
    """文書順の要素ツリーと本文テキスト T を同時に作る。

    T は text node の文書順連結。<script> / <style> / <template> / <head> の
    内容と属性値は含めない (『初出』= 読者の目に触れる最初の位置 という定義のため)。
    """

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = Node("#document", {}, 0, 1, 0, None)
        self.stack = [self.root]
        self.counter = 0
        self._text = []
        self._len = 0
        self._chunk_offsets = []
        self._chunks = []

    # -- 収集 ---------------------------------------------------------------

    def _new_node(self, tag, attrs):
        self.counter += 1
        line, col = self.getpos()
        table = {}
        for key, value in attrs:
            key = key.lower()
            if key not in table:
                table[key] = value if value is not None else ""
        parent = self.stack[-1]
        node = Node(tag, table, self.counter, line, col, parent)
        node.t_start = self._len
        node.t_end = self._len
        parent.children.append(node)
        return node

    def handle_starttag(self, tag, attrs):
        node = self._new_node(tag.lower(), attrs)
        if node.tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self._new_node(tag.lower(), attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                while len(self.stack) > index:
                    self.stack.pop().t_end = self._len
                return

    def _in_non_body(self):
        for node in self.stack:
            if node.tag in NON_BODY_TAGS:
                return True
        return False

    def handle_data(self, data):
        if not data or self._in_non_body():
            return
        line, col = self.getpos()
        self._chunk_offsets.append(self._len)
        self._chunks.append((line, col, data))
        self._text.append(data)
        self._len += len(data)

    # -- 結果 ---------------------------------------------------------------

    def finish(self):
        while len(self.stack) > 1:
            self.stack.pop().t_end = self._len
        self.root.t_end = self._len
        return "".join(self._text)

    def locate(self, offset):
        """本文テキスト T のオフセットを元 HTML の line:col へ戻す。"""
        if not self._chunks:
            return (1, 1)
        index = bisect.bisect_right(self._chunk_offsets, offset) - 1
        if index < 0:
            index = 0
        base = self._chunk_offsets[index]
        line, col, text = self._chunks[index]
        for char in text[: max(0, offset - base)]:
            if char == "\n":
                line += 1
                col = 0
            else:
                col += 1
        return (line, col + 1)


# --------------------------------------------------------------------------
# 文字列の正規化
# --------------------------------------------------------------------------


def squash(text):
    """NFKC 正規化 + 空白除去 (LANG-01 の言い換え一致判定)。"""
    return "".join(unicodedata.normalize("NFKC", text).split())


def fold(text):
    """長さを保つ NFKC 寄せ。1 文字が 1 文字へ写る場合だけ置換する。

    T のオフセットを壊さずに全角/半角差 (括弧・空白・英数) を吸収するために使う。
    """
    out = []
    for char in text:
        normalized = unicodedata.normalize("NFKC", char)
        out.append(normalized if len(normalized) == 1 else char)
    return "".join(out)


def lang07_norm(text):
    """LANG-07 の比較用: NFKC + 空白除去 + 記号除去。"""
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(
        char
        for char in normalized
        if not char.isspace() and char not in LANG07_STRIP_SYMBOLS
    )


def one_line(text):
    """stderr の 1 行へ収めるため空白類を 1 個の空白へ畳む (タブと改行を出さない)。"""
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# 中立データの読み込み
# --------------------------------------------------------------------------


def load_json_file(path, label):
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail_closed("%s が見つからない: %s" % (label, path))
    except UnicodeDecodeError:
        fail_closed("%s を UTF-8 として読めない: %s" % (label, path))
    except OSError as exc:
        fail_closed("%s を読み取れない: %s (%s)" % (label, path, exc.strerror))
    try:
        return json.loads(raw)
    except ValueError as exc:
        fail_closed("%s が JSON として不正: %s (%s)" % (label, path, exc))


class Vocabulary(object):
    """script へ焼き込まない語彙と閾値の束。"""

    def __init__(self):
        catalog = load_json_file(PARTS_CATALOG_PATH, "部品カタログ (handout-parts.json)")
        parts = catalog.get("parts") if isinstance(catalog, dict) else None
        if not isinstance(parts, list) or not parts:
            fail_closed("部品カタログに parts が無い: %s" % PARTS_CATALOG_PATH)
        self.in_section_part_ids = set()
        self.document_part_ids = set()
        for part in parts:
            if not isinstance(part, dict) or "id" not in part or "section_scope" not in part:
                fail_closed(
                    "部品カタログの要素に id / section_scope が無い: %s" % PARTS_CATALOG_PATH
                )
            if part["section_scope"] == "in-section":
                self.in_section_part_ids.add(part["id"])
            elif part["section_scope"] == "document":
                self.document_part_ids.add(part["id"])
        if not self.in_section_part_ids:
            fail_closed(
                "部品カタログに section_scope==\"in-section\" の部品が 1 件も無い: %s"
                % PARTS_CATALOG_PATH
            )

        sections = load_json_file(
            SECTIONS_CATALOG_PATH, "セクション種別カタログ (handout-sections.json)"
        )
        kinds = sections.get("section_kinds") if isinstance(sections, dict) else None
        slugs = {k.get("slug") for k in kinds} if isinstance(kinds, list) else set()
        if CAPABILITY_KIND_SLUG not in slugs:
            fail_closed(
                "セクション種別カタログに %s が無い: %s"
                % (CAPABILITY_KIND_SLUG, SECTIONS_CATALOG_PATH)
            )
        self.capability_kind = CAPABILITY_KIND_SLUG

        schema = load_json_file(CONFIG_SCHEMA_PATH, "構成データスキーマ")
        try:
            self.date_pattern_text = schema["properties"]["date"]["pattern"]
            provenance = schema["$defs"]["provenance"]["properties"]
            self.normalized_by_value = provenance["normalized_by"]["const"]
            self.single_line_max_chars = schema["$defs"]["section"]["properties"]["lead_line"][
                "maxLength"
            ]
        except (KeyError, TypeError):
            fail_closed("構成データスキーマから日付書式・正規化マーカー・長さ上限を読めない")
        if not isinstance(self.single_line_max_chars, int) or self.single_line_max_chars <= 0:
            fail_closed("構成データスキーマの 1 行フィールド長さ上限が数値でない")
        try:
            self.date_re = re.compile(self.date_pattern_text)
            # 命名側の派生表現は表示正本の純変換 (C19 と同一の replace('/','-'))。
            self.dir_date_re = re.compile(self.date_pattern_text.replace("/", "-"))
        except re.error:
            fail_closed("構成データスキーマの日付書式パターンが正規表現として不正")
        self.dir_date_len = 10
        self.dir_separator = "-"


# --------------------------------------------------------------------------
# 検査結果の器
# --------------------------------------------------------------------------


class Violation(object):
    __slots__ = ("detection", "locator", "target", "reason", "evidence")

    def __init__(self, detection, locator, target, reason, evidence=""):
        self.detection = detection
        self.locator = locator
        self.target = target
        self.reason = reason
        self.evidence = evidence

    def row(self):
        return "FAIL\t%s\t%s\t%s\t%s\t%s" % (
            self.detection,
            one_line(self.locator) or "-",
            one_line(self.target) or "-",
            one_line(self.reason) or "-",
            one_line(self.evidence) or "-",
        )

    def as_dict(self):
        return {
            "detection": self.detection,
            "locator": self.locator,
            "target": self.target,
            "reason": self.reason,
            "evidence": self.evidence,
        }


class Detection(object):
    __slots__ = ("id", "status", "checked", "violations", "notes")

    def __init__(self, detection_id, checked=0, status=None):
        self.id = detection_id
        self.checked = checked
        self.violations = []
        self.notes = []
        self.status = status

    def add(self, locator, target, reason, evidence=""):
        self.violations.append(Violation(self.id, locator, target, reason, evidence))

    def resolved_status(self):
        if self.status is not None:
            return self.status
        return "FAIL" if self.violations else "PASS"


# --------------------------------------------------------------------------
# LANG-01
# --------------------------------------------------------------------------


def _is_alnum_term(term):
    return re.fullmatch(r"[A-Za-z0-9]+", term) is not None


def _boundary_ok(folded_text, start, end):
    before = folded_text[start - 1] if start > 0 else ""
    after = folded_text[end] if end < len(folded_text) else ""
    boundary = re.compile(r"[A-Za-z0-9_-]")
    if before and boundary.match(before):
        return False
    if after and boundary.match(after):
        return False
    return True


def _find_first_occurrence(folded_text, folded_term, consumed, alnum):
    if not folded_term:
        return -1
    start = 0
    while True:
        pos = folded_text.find(folded_term, start)
        if pos < 0:
            return -1
        end = pos + len(folded_term)
        overlapped = any(not (end <= lo or pos >= hi) for lo, hi in consumed)
        if not overlapped and (not alnum or _boundary_ok(folded_text, pos, end)):
            return pos
        start = pos + 1


def _paraphrase_follows(folded_text, end, plain):
    """term の直後に括弧書きの言い換えが続くか。"""
    index = end
    while index < len(folded_text) and folded_text[index].isspace():
        index += 1
    if index >= len(folded_text) or folded_text[index] != "(":
        return (False, None)
    close = folded_text.find(")", index + 1)
    if close < 0:
        return (False, None)
    content = folded_text[index + 1 : close]
    return (squash(content) == squash(plain), content)


def analyse_lang01(text, folded_text, collector, glossary):
    detection = Detection("LANG-01", checked=len(glossary))
    if not glossary:
        detection.notes.append(
            "用語宣言が 0 件のため言い換え検査は実質無効 (LANG-01 checked=0)"
        )
        return detection

    entries = []
    for entry in glossary:
        if not isinstance(entry, dict):
            entries.append(("", ""))
            continue
        entries.append((str(entry.get("term", "")), str(entry.get("plain", ""))))

    # 部分文字列関係のある用語は長い方から照合し、その占有位置を短い term の初出から外す。
    consumed = []
    positions = {}
    for index in sorted(range(len(entries)), key=lambda i: (-len(entries[i][0]), i)):
        term = entries[index][0]
        folded_term = fold(term)
        pos = _find_first_occurrence(
            folded_text, folded_term, consumed, _is_alnum_term(term)
        )
        positions[index] = pos
        if pos >= 0:
            consumed.append((pos, pos + len(folded_term)))

    for index, (term, plain) in enumerate(entries):
        if not term:
            detection.add("-", "(空の term)", "glossary の term が空である")
            continue
        pos = positions[index]
        if pos < 0:
            detection.add(
                "-",
                term,
                "宣言されたが本文に一度も出現しない (宣言の腐敗)",
            )
            continue
        end = pos + len(term)
        line, col = collector.locate(pos)
        locator = "%d:%d" % (line, col)
        evidence = one_line(
            text[max(0, pos - EVIDENCE_RADIUS) : min(len(text), end + EVIDENCE_RADIUS)]
        )
        ok, content = _paraphrase_follows(folded_text, end, plain)
        if ok:
            continue
        if content is None:
            reason = "初出の直後に括弧書きの言い換えが無い (期待: %s)" % one_line(plain)
        else:
            reason = "初出の括弧書きが宣言された言い換えと一致しない (期待: %s / 実際: %s)" % (
                one_line(plain),
                one_line(content),
            )
        detection.add(locator, term, reason, evidence)
    return detection


# --------------------------------------------------------------------------
# セクション面 (LANG-04 / LANG-05 / LANG-06 / LANG-07)
# --------------------------------------------------------------------------


def collect_sections(root):
    """検査対象セクション: <section> のうち id を持つか data-hb-part="section" のもの。"""
    found = []
    for node in root.descendants():
        if node.tag != "section":
            continue
        if node.attrs.get("id") or node.attrs.get("data-hb-part") == "section":
            found.append(node)
    return found


def _field_nodes(section, field):
    return [n for n in section.descendants() if n.attrs.get("data-hb-field") == field]


def _node_text(text, node):
    return text[node.t_start : node.t_end]


def _section_label(section):
    return section.attrs.get("id") or "(id 無しの section)"


def _locator(node):
    return "%d:%d" % (node.line, node.col + 1)


def analyse_sections(text, sections, vocab):
    lang04 = Detection("LANG-04", checked=len(sections))
    lang05 = Detection("LANG-05", checked=len(sections))
    lang06 = Detection("LANG-06", checked=len(sections))

    for section in sections:
        sid = _section_label(section)
        loc = _locator(section)
        leads = _field_nodes(section, "lead_line")
        axes = _field_nodes(section, "judgment_axis")
        parts = [
            n
            for n in section.descendants()
            if n.attrs.get("data-hb-part") in vocab.in_section_part_ids
        ]

        # -- LANG-04
        if not leads:
            lang04.add(loc, sid, "lead-line (data-hb-field=\"lead_line\") が存在しない")
        elif len(leads) > 1:
            lang04.add(
                loc, sid, "lead-line が %d 個ある (抽象 1 行が一意に決まらない)" % len(leads)
            )
        elif not _node_text(text, leads[0]).strip():
            lang04.add(_locator(leads[0]), sid, "lead-line が空白のみで非空でない")

        # -- LANG-05
        if not axes:
            lang05.add(loc, sid, "判断軸 (data-hb-field=\"judgment_axis\") が存在しない")
        elif len(axes) > 1:
            lang05.add(loc, sid, "判断軸が %d 個ある (一文が一意に決まらない)" % len(axes))
        else:
            axis_text = _node_text(text, axes[0]).strip()
            if not axis_text:
                lang05.add(_locator(axes[0]), sid, "判断軸が空白のみで非空でない")
            elif not axis_text.endswith(("。", "?", "？")) and (
                len(axis_text) > vocab.single_line_max_chars
            ):
                lang05.add(
                    _locator(axes[0]),
                    sid,
                    "判断軸が一文の形式を満たさない (句点 / ? / ？ で終わらず %d 文字を超える: %d 文字)"
                    % (vocab.single_line_max_chars, len(axis_text)),
                )

        # -- LANG-06
        if len(leads) != 1 or len(axes) != 1:
            lang06.add(
                loc,
                sid,
                "順序を判定するアンカー (lead-line / 判断軸) が一意でないため R11 の型を検査できない",
            )
        elif not parts:
            lang06.add(
                loc,
                sid,
                "具体部品 (部品カタログで section_scope==\"in-section\" の data-hb-part) が 0 個で、"
                "抽象と判断軸だけになっている",
            )
        else:
            lead_order = leads[0].order
            axis_order = axes[0].order
            first_part = min(part.order for part in parts)
            if not (lead_order < first_part < axis_order):
                lang06.add(
                    loc,
                    sid,
                    "R11 の順序が崩れている (期待: lead-line < 最初の具体部品 < 判断軸 / "
                    "実際の文書順: lead-line=%d, 最初の具体部品=%d, 判断軸=%d)"
                    % (lead_order, first_part, axis_order),
                )
    return lang04, lang05, lang06


def _feature_headings(text, section):
    headings = []
    for node in section.descendants():
        if node.attrs.get("data-hb-slot") != "feature":
            continue
        for child in node.descendants():
            if child.tag in HEADING_TAGS:
                heading = _node_text(text, child).strip()
                if heading:
                    headings.append(heading)
                break
    return headings


def _noun_phrase_match(normalized_lead):
    pattern = re.compile(
        r"^[^。．.!！?？、,]{0,30}?(%s)(%s)"
        % ("|".join(LANG07_NOUN_SUFFIXES), "|".join(LANG07_PARTICLES))
    )
    return pattern.match(normalized_lead)


def analyse_lang07(text, sections, vocab):
    targets = [
        s for s in sections if s.attrs.get("data-hb-section-kind") == vocab.capability_kind
    ]
    detection = Detection("LANG-07", checked=len(targets))
    for section in targets:
        sid = _section_label(section)
        leads = _field_nodes(section, "lead_line")
        if len(leads) != 1:
            # lead_line の不在・重複は LANG-04 の面。ここで二重計上しない。
            continue
        lead_text = _node_text(text, leads[0]).strip()
        if not lead_text:
            continue
        normalized_lead = lang07_norm(lead_text)
        hit = None
        for heading in _feature_headings(text, section):
            normalized_heading = lang07_norm(heading)
            if len(normalized_heading) < LANG07_MIN_HEADING_LEN:
                continue
            if normalized_lead.startswith(normalized_heading):
                hit = (
                    "lead_line が同セクションの機能見出しから始まっている (見出し: %s)"
                    % one_line(heading),
                    heading,
                )
                break
        if hit is None:
            match = _noun_phrase_match(normalized_lead)
            if match:
                hit = (
                    "lead_line が機能名の名詞句 + 助詞で始まっている (成果から書き出すこと)",
                    match.group(0),
                )
        if hit is not None:
            detection.add(_locator(leads[0]), sid, hit[0], one_line(lead_text) + " / " + one_line(hit[1]))
    return detection


# --------------------------------------------------------------------------
# 日付面 (DATE-01 / DATE-02 / DATE-03 / DATE-04)
# --------------------------------------------------------------------------


def _calendar_exists(value):
    try:
        year, month, day = (int(part) for part in value.split("/"))
        datetime.date(year, month, day)
    except (ValueError, TypeError):
        return False
    return True


def analyse_dates(text, root, sections, vocab, config_date, out_dir_arg):
    date_nodes = [n for n in root.descendants() if n.attrs.get("data-hb-field") == "date"]

    # 冒頭判定の基準点: <header> の内側、または文書スコープ部品 (ヒーロー / sticky ナビ) より前。
    anchor_order = None
    for node in root.descendants():
        if node.attrs.get("data-hb-part") in vocab.document_part_ids:
            anchor_order = node.order
            break

    def in_lead_position(node):
        if node.has_ancestor_tag("header"):
            return True
        return anchor_order is not None and node.order < anchor_order

    date01 = Detection("DATE-01", checked=len(date_nodes))
    date02 = Detection("DATE-02", checked=1)
    date04 = Detection("DATE-04", checked=len(date_nodes))

    values = [(_node_text(text, node).strip(), node) for node in date_nodes]

    if not date_nodes:
        date01.add(
            "-",
            "(data-hb-field=\"date\")",
            "冒頭の日付表記が 1 個も存在しない (R18 は日付表記の存在を必須とする)",
        )
        date02.add(
            "-",
            config_date,
            "日付表記が無く、正規化済み構成データの date と突合できない",
        )
    else:
        for value, node in values:
            if not vocab.date_re.fullmatch(value):
                date01.add(
                    _locator(node),
                    value or "(空)",
                    "日付表記が yyyy/mm/dd (ゼロ埋め・スラッシュ区切り) に完全一致しない",
                )
            elif not _calendar_exists(value):
                date01.add(
                    _locator(node),
                    value,
                    "暦として実在しない日付である",
                )
        if not any(in_lead_position(node) for _, node in values):
            first = values[0][1]
            date01.add(
                _locator(first),
                values[0][0] or "(空)",
                "日付表記が冒頭 (<header> 内、またはヒーローより文書順で前) に無い",
            )

        primary_value, primary_node = next(
            ((v, n) for v, n in values if in_lead_position(n)), values[0]
        )
        if primary_value != config_date:
            date02.add(
                _locator(primary_node),
                primary_value or "(空)",
                "日付表記が正規化済み構成データの date と一致しない (構成データ: %s / 表示: %s)"
                % (config_date, primary_value or "(空)"),
            )
        for value, node in values:
            if node is primary_node:
                continue
            if value != primary_value:
                date04.add(
                    _locator(node),
                    value or "(空)",
                    "文書内の日付表記が一貫していない (冒頭: %s / この位置: %s)"
                    % (primary_value or "(空)", value or "(空)"),
                )

    body_dates = sorted(
        {match for match in BODY_DATE_RE.findall(text) if match != config_date}
    )

    date03 = Detection("DATE-03")
    if out_dir_arg is None:
        date03.status = "NOT-REQUESTED"
        date03.checked = 0
        date03.notes.append(
            "--out-dir が未指定のため DATE-03 は評価していない (PASS ではない)"
        )
    else:
        date03.checked = 1
        raw = str(out_dir_arg).rstrip("/")
        basename = raw.rsplit("/", 1)[-1]
        expected = config_date.replace("/", "-")
        head = basename[: vocab.dir_date_len]
        if not vocab.dir_date_re.fullmatch(head):
            date03.add(
                basename,
                head or "(空)",
                "ディレクトリ名の先頭 %d 文字が命名用の日付表現でない (期待: %s)"
                % (vocab.dir_date_len, expected),
            )
        elif head != expected:
            date03.add(
                basename,
                head,
                "ディレクトリ名の日付が構成データの date の純変換と一致しない (期待: %s / 実際: %s)"
                % (expected, head),
            )
        elif len(basename) <= vocab.dir_date_len or basename[vocab.dir_date_len] != vocab.dir_separator:
            date03.add(
                basename,
                basename[: vocab.dir_date_len + 1],
                "日付の直後が区切り文字 %s でない (<YYYY-MM-DD>-<種別>-<主題slug>)"
                % vocab.dir_separator,
            )

    return date01, date02, date03, date04, body_dates


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def _read_text_file(path_arg, label):
    path = Path(path_arg)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail_closed("%s が見つからない: %s" % (label, path_arg))
    except IsADirectoryError:
        fail_closed("%s がファイルでない: %s" % (label, path_arg))
    except UnicodeDecodeError:
        fail_closed("%s を UTF-8 として読めない: %s" % (label, path_arg))
    except OSError as exc:
        fail_closed("%s を読み取れない: %s (%s)" % (label, path_arg, exc.strerror))


def load_normalized_config(path_arg, vocab):
    raw = _read_text_file(path_arg, "構成データ")
    try:
        config = json.loads(raw)
    except ValueError as exc:
        fail_closed("構成データが JSON として不正: %s (%s)" % (path_arg, exc))
    if not isinstance(config, dict):
        fail_closed("構成データが JSON オブジェクトでない: %s" % path_arg)

    provenance = config.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("normalized_by") != vocab.normalized_by_value:
        fail_closed(
            "構成データが正規化済みでない (provenance.normalized_by が正規化マーカーと一致しない)"
        )

    value = config.get("date")
    if not isinstance(value, str) or not value.strip():
        fail_closed("正規化済み構成データの必須フィールドが未充填: date")
    if "glossary" not in config or not isinstance(config["glossary"], list):
        fail_closed("正規化済み構成データの必須フィールドが欠落: glossary")
    sections = config.get("sections")
    if not isinstance(sections, list) or not sections:
        fail_closed("正規化済み構成データの必須フィールドが欠落: sections")
    return config


def build_report(html_arg, config_arg, out_dir_arg, result, detections, body_dates):
    return {
        "component": "C18",
        "script": "verify-handout-language.py",
        "result": result,
        "html": str(html_arg),
        "config": str(config_arg),
        "out_dir": None if out_dir_arg is None else str(out_dir_arg),
        "detections": [
            {
                "id": det.id,
                "status": det.resolved_status(),
                "checked": det.checked,
                "violation_count": len(det.violations),
                "violations": [v.as_dict() for v in det.violations],
                "notes": list(det.notes),
            }
            for det in detections
        ],
        "notes": [note for det in detections for note in det.notes],
        "info": {
            "body_dates_other_than_config_date": list(body_dates),
            "body_dates_note": "本文中の別日付は資料の内容表現として正当なので違反にしない (info)",
        },
        "out_of_scope": [line.strip("- ").strip() for line in OUT_OF_SCOPE_LINES],
    }


def main(argv):
    parser = _Parser(add_help=False, prog="verify-handout-language.py")
    parser.add_argument("--html")
    parser.add_argument("--config")
    parser.add_argument("--out-dir", dest="out_dir")
    parser.add_argument("--json-report", dest="json_report")
    args = parser.parse_args(argv)

    if args.html is None:
        fail_closed("必須引数 --html が指定されていない")
    if args.config is None:
        fail_closed("必須引数 --config が指定されていない")

    report_path = None
    if args.json_report is not None:
        report_path = Path(args.json_report)
        parent = report_path.parent if str(report_path.parent) else Path(".")
        if not parent.is_dir():
            fail_closed("--json-report の書き出し先ディレクトリが存在しない: %s" % parent)

    vocab = Vocabulary()
    html_text = _read_text_file(args.html, "生成 HTML")
    config = load_normalized_config(args.config, vocab)
    config_date = config["date"].strip()

    collector = Collector()
    try:
        collector.feed(html_text)
        collector.close()
    except Exception as exc:  # noqa: BLE001 - 解析不能は検査不成立
        fail_closed("生成 HTML を解析できない: %s" % exc)
    text = collector.finish()
    folded_text = fold(text)

    sections = collect_sections(collector.root)

    lang01 = analyse_lang01(text, folded_text, collector, config["glossary"])
    lang04, lang05, lang06 = analyse_sections(text, sections, vocab)
    lang07 = analyse_lang07(text, sections, vocab)
    date01, date02, date03, date04, body_dates = analyse_dates(
        text, collector.root, sections, vocab, config_date, args.out_dir
    )

    by_id = {
        "LANG-01": lang01,
        "LANG-04": lang04,
        "LANG-05": lang05,
        "LANG-06": lang06,
        "LANG-07": lang07,
        "DATE-01": date01,
        "DATE-02": date02,
        "DATE-03": date03,
        "DATE-04": date04,
    }
    detections = [by_id[detection_id] for detection_id in DETECTION_ORDER]

    violations = [v for det in detections for v in det.violations]
    result = "FAIL" if violations else "PASS"

    out_lines = ["RESULT: %s %s" % (result, args.html)]
    for det in detections:
        out_lines.append(
            "%s %s checked=%d violations=%d"
            % (det.id, det.resolved_status(), det.checked, len(det.violations))
        )
    for det in detections:
        for note in det.notes:
            out_lines.append("注記: %s" % note)
    out_lines.append("OUT-OF-SCOPE:")
    out_lines.extend(OUT_OF_SCOPE_LINES)

    if report_path is not None:
        payload = build_report(args.html, args.config, args.out_dir, result, detections, body_dates)
        try:
            report_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            fail_closed("--json-report を書き出せない: %s (%s)" % (report_path, exc.strerror))

    sys.stdout.write("\n".join(out_lines) + "\n")
    if violations:
        sys.stderr.write("".join(v.row() + "\n" for v in violations))
    return 1 if violations else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except BrokenPipeError:
        sys.exit(2)

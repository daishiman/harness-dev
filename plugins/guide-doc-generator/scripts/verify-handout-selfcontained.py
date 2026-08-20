#!/usr/bin/env python3
# /// script
# name: verify-handout-selfcontained
# version: 0.1.0
# purpose: C16 生成 HTML の自己完結性 (取得を発生させる参照の不在)・絵文字ゼロ・アイコン様式・symbol 整合・アンカー整合の単一正本となる fail-closed ゲート
# inputs:
#   - argv: --html <path> [--json-report <path>]
# outputs:
#   - stdout: 違反一覧 (CR-EXT ほか)
#   - file: --json-report の検査結果
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out / --json-report / --config-out で明示された path のみ
# ///
"""C16 verify-handout-selfcontained.py — 生成 HTML の自己完結性ゲート。

契約の正本は plugin-plans/guide-doc-generator/briefs/script-brief-C16.json。
本 script は次の 2 つの規則の **単一正本 (owner)** である。

- CR-EXT  : 取得 (fetch) を発生させる参照は data: 以外を一律違反とする (SC-01..04 / SC-10)
- CR-EMOJI: 絵文字判定の二層規則 (SC-05)。ブロック丸ごとの denylist は用いない

C10 hook / C11 レンダラ / C15 build-icon-sprite.py は独自判定を持たず、
module_api の scan_external_references(html_text) / scan_emoji(text) を呼ぶ
(P04-x-05 裁定 G-03)。

Python 3.10+ 標準ライブラリのみ。ネットワークアクセスは行わない。
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 定数 (出力契約)
# ---------------------------------------------------------------------------

DETECTION_IDS = ("SC-01", "SC-02", "SC-03", "SC-04", "SC-05",
                 "SC-06", "SC-07", "SC-08", "SC-09", "SC-10")

PARSER_WARNING_ID = "SC-00"

EXIT_OK = 0
EXIT_QUALITY_FAIL = 1
EXIT_UNUSABLE = 2

EVIDENCE_MAX = 120

# ---------------------------------------------------------------------------
# 語彙の外部化 (script へリテラル列挙しない)
# ---------------------------------------------------------------------------

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PARTS_CATALOG_RELPATH = ("config", "handout-parts.json")
ICON_SET_RELPATH = ("assets", "icons", "icon-set.json")

# handout-parts.json#field_semantics の値。部品 id そのものは列挙しない。
PART_KIND_MEDIA = "media"
PART_BLOCK_TYPE_PLAIN_TEXT = "text"

# C11 html_attribute_contract が正本の属性名 / 分類値 (SC-06)。
KIND_ATTR = "data-hb-kind"
KIND_ICON = "icon"
PART_ATTR = "data-hb-part"
NAV_EXCLUDE_ATTR = "data-hb-nav"
NAV_EXCLUDE_VALUE = "exclude"


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class InspectionError(Exception):
    """検査そのものが成立しない (exit 2)。"""


# ---------------------------------------------------------------------------
# Violation
# ---------------------------------------------------------------------------


def _sanitize(text, limit=None):
    if text is None:
        return ""
    out = str(text).replace("\t", " ").replace("\r", " ").replace("\n", " ")
    out = re.sub(r"\s+", " ", out).strip()
    if limit is not None and len(out) > limit:
        out = out[:limit]
    return out


class Violation:
    """module_api の Violation = {detection_id, line, col, message, evidence, codepoints}."""

    __slots__ = ("detection_id", "line", "col", "message", "evidence", "codepoints")

    def __init__(self, detection_id, line, col, message, evidence="", codepoints=None):
        self.detection_id = detection_id
        self.line = int(line)
        self.col = int(col)
        self.message = _sanitize(message)
        self.evidence = _sanitize(evidence, EVIDENCE_MAX)
        self.codepoints = codepoints

    def sort_key(self):
        return (self.detection_id, self.line, self.col)

    def to_dict(self):
        return {
            "detection_id": self.detection_id,
            "line": self.line,
            "col": self.col,
            "message": self.message,
            "evidence": self.evidence,
            "codepoints": self.codepoints,
        }

    def __repr__(self):
        return "Violation({}, {}:{}, {!r})".format(
            self.detection_id, self.line, self.col, self.message)


class InfoRecord:
    """判定は通すが人間レビュー (C06) へ渡す記録。"""

    __slots__ = ("detection_id", "line", "col", "message", "codepoints")

    def __init__(self, detection_id, line, col, message, codepoints=None):
        self.detection_id = detection_id
        self.line = int(line)
        self.col = int(col)
        self.message = _sanitize(message)
        self.codepoints = codepoints

    def to_dict(self):
        return {
            "detection_id": self.detection_id,
            "line": self.line,
            "col": self.col,
            "message": self.message,
            "codepoints": self.codepoints,
        }


# ---------------------------------------------------------------------------
# CR-EMOJI (SC-05) — 絵文字判定の単一正本
# ---------------------------------------------------------------------------

# 層 1 = 単独で違反。面 1 の絵文字ブロック群と、BMP では絵文字表示が既定の
# コードポイントだけを置く。日本語の記号・約物を巻き込むブロック denylist は用いない。
_L1_RANGES = (
    (0x1F000, 0x1F02F), (0x1F0A0, 0x1F0FF), (0x1F100, 0x1F1FF),
    (0x1F200, 0x1F2FF), (0x1F300, 0x1F5FF), (0x1F600, 0x1F64F),
    (0x1F680, 0x1F6FF), (0x1F700, 0x1F8FF), (0x1F900, 0x1F9FF),
    (0x1FA00, 0x1FAFF), (0xE0020, 0xE007F),
    (0x2648, 0x2653), (0x2753, 0x2755), (0x2795, 0x2797), (0x2B05, 0x2B07),
)

_L1_SINGLES = frozenset((
    0xFE0F, 0x20E3, 0x203C, 0x2049, 0x2614, 0x2615, 0x267F, 0x2693,
    0x26A1, 0x26AA, 0x26AB, 0x26BD, 0x26BE, 0x26C4, 0x26C5, 0x26CE,
    0x26D4, 0x26EA, 0x26F2, 0x26F3, 0x26F5, 0x26FA, 0x26FD, 0x2705,
    0x270A, 0x270B, 0x2728, 0x274C, 0x274E, 0x2757, 0x27B0, 0x27BF,
    0x2934, 0x2935, 0x2B1B, 0x2B1C, 0x2B50, 0x2B55,
))

# 層 2 = 直後に U+FE0F (VS16) が続くときだけ違反。
# VS16 を伴わない © ® ™ ★ ▶ ♪ ♂ ✔ ⚙ 等は通す。
_L2_RANGES = (
    (0x2194, 0x21AA), (0x23E9, 0x23FA), (0x25FB, 0x25FE),
    (0x2600, 0x2604), (0x2638, 0x263A), (0x2694, 0x2699),
    (0x26F7, 0x26F9),
)

_L2_SINGLES = frozenset((
    0x00A9, 0x00AE, 0x2122, 0x2139, 0x231A, 0x231B, 0x2328, 0x23CF,
    0x24C2, 0x25AA, 0x25AB, 0x25B6, 0x25C0, 0x260E, 0x2611, 0x2618,
    0x261D, 0x2620, 0x2622, 0x2623, 0x2626, 0x262A, 0x262E, 0x262F,
    0x2640, 0x2642, 0x265F, 0x2660, 0x2663, 0x2665, 0x2666, 0x2668,
    0x267B, 0x267E, 0x2692, 0x269B, 0x269C, 0x26A0, 0x26A7, 0x26B0,
    0x26B1, 0x26C8, 0x26CF, 0x26D1, 0x26D3, 0x26E9, 0x26F0, 0x26F1,
    0x26F4, 0x2702, 0x2708, 0x2709, 0x270C, 0x270D, 0x270F, 0x2712,
    0x2714, 0x2716, 0x271D, 0x2721, 0x2733, 0x2734, 0x2744, 0x2747,
    0x2763, 0x2764, 0x27A1, 0x3030, 0x303D, 0x3297, 0x3299,
))

_VS16 = 0xFE0F
_ZWJ = 0x200D
_VS1 = 0xFE00
_VS15 = 0xFE0E


def _in_ranges(cp, ranges):
    for low, high in ranges:
        if low <= cp <= high:
            return True
    return False


def is_layer1_codepoint(cp: int) -> bool:
    """層 1 (単独で絵文字扱い) か。"""
    return cp in _L1_SINGLES or _in_ranges(cp, _L1_RANGES)


def is_layer2_codepoint(cp: int) -> bool:
    """層 2 (VS16 を伴うときだけ絵文字扱い) か。"""
    return cp in _L2_SINGLES or _in_ranges(cp, _L2_RANGES)


def format_codepoints(text: str) -> str:
    return " ".join("U+{:04X}".format(ord(ch)) for ch in text)


_ICON_NAME_CACHE = None


def _icon_name_candidates():
    """代替アイコン名の候補を assets の正本から読む (語彙を script へ持たない)。"""
    global _ICON_NAME_CACHE
    if _ICON_NAME_CACHE is None:
        names = []
        try:
            raw = PLUGIN_ROOT.joinpath(*ICON_SET_RELPATH).read_text(encoding="utf-8")
            data = json.loads(raw)
            for entry in data.get("icons", []):
                name = entry.get("name")
                if isinstance(name, str):
                    names.append(name)
        except (OSError, ValueError, AttributeError):
            names = []
        _ICON_NAME_CACHE = tuple(names[:3])
    return _ICON_NAME_CACHE


def _emoji_suggestion():
    names = _icon_name_candidates()
    if not names:
        return "inline SVG アイコンへ置き換えること"
    return "inline SVG アイコンへ置き換えること (候補: {})".format(", ".join(names))


def _emoji_hits(text):
    """CR-EMOJI を 1 度だけ適用する内部実装。

    返り値は (index, matched_text, kind, reason) の列。
    kind は "violation" (SC-05 違反) か "info" (json-report へ残す記録)。
    層 2 のコードポイントと直後の VS16 は 1 件の違反へまとめる
    (規則としては「層 2 + VS16 で 1 つの絵文字」であり、
    C15 が codepoints をそのまま転記できるようにするため)。
    """
    hits = []
    length = len(text)
    i = 0
    while i < length:
        cp = ord(text[i])
        nxt = ord(text[i + 1]) if i + 1 < length else None
        if is_layer2_codepoint(cp) and nxt == _VS16:
            hits.append((i, text[i:i + 2], "violation", "層 2 のコードポイントに VS16 が付き絵文字化している"))
            i += 2
            continue
        if cp == _ZWJ:
            prev_cp = ord(text[i - 1]) if i > 0 else None
            if (prev_cp is not None and is_layer1_codepoint(prev_cp)) or \
               (nxt is not None and is_layer1_codepoint(nxt)):
                hits.append((i, text[i], "violation", "絵文字連結シーケンスの ZWJ"))
            else:
                hits.append((i, text[i], "info", "孤立 ZWJ は絵文字ではないので通す"))
            i += 1
            continue
        if is_layer1_codepoint(cp):
            hits.append((i, text[i], "violation", "絵文字表示が既定のコードポイント (層 1)"))
            i += 1
            continue
        if is_layer2_codepoint(cp):
            hits.append((i, text[i], "info",
                         "層 2 のコードポイントが VS16 なしで出現 (通すが機種により絵文字表示になり得る)"))
            i += 1
            continue
        if _VS1 <= cp <= _VS15:
            hits.append((i, text[i], "info", "異体字セレクタ VS1-VS15 は字形指定であり絵文字ではない"))
            i += 1
            continue
        i += 1
    return hits


def _emoji_records(text, base_line=1, base_col=1):
    violations = []
    infos = []
    for index, matched, kind, reason in _emoji_hits(text):
        line, col = _offset_pos(base_line, base_col, text, index)
        cps = format_codepoints(matched)
        if kind == "violation":
            violations.append(Violation(
                "SC-05", line, col,
                "絵文字を検出: {} — {}。{}".format(cps, reason, _emoji_suggestion()),
                cps, cps))
        else:
            infos.append(InfoRecord("SC-05", line, col,
                                    "{}: {}".format(reason, cps), cps))
    return violations, infos


def scan_emoji(text):
    """CR-EMOJI (SC-05 の二層規則) を適用する。

    入力は素の文字列でよい (HTML でなくてもよい)。C15 は icons[].name /
    icons[].title をここへ直接渡す。返り値は Violation の list。
    """
    if not isinstance(text, str) or not text:
        return []
    violations, _infos = _emoji_records(text)
    return violations


# ---------------------------------------------------------------------------
# 位置計算
# ---------------------------------------------------------------------------


def _offset_pos(base_line, base_col, text, index):
    """base (1 始まり line / col) から text[:index] を消費した位置を返す。"""
    if index <= 0:
        return base_line, base_col
    seg = text[:index]
    newlines = seg.count("\n")
    if newlines:
        return base_line + newlines, len(seg) - seg.rfind("\n")
    return base_line, base_col + index


# ---------------------------------------------------------------------------
# HTML 収集
# ---------------------------------------------------------------------------

from html.parser import HTMLParser  # noqa: E402  (定数定義の後に置く)

VOID_TAGS = frozenset((
    "area", "base", "br", "col", "embed", "frame", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
))

RAW_TEXT_TAGS = frozenset(("script", "style"))

# CR-EXT: URL を取り得る属性 (SC-01 / SC-10 の詳細診断用の列挙)
URL_ATTRS = ("href", "src", "srcset", "poster", "data", "action",
             "formaction", "cite", "background", "xlink:href")

EXTERNAL_SCHEME_PREFIXES = ("http://", "https://", "//", "ftp://", "ws://", "wss://")

NAMESPACE_URI_WHITELIST = frozenset((
    "http://www.w3.org/2000/svg",
    "http://www.w3.org/1999/xlink",
    "http://www.w3.org/XML/1998/namespace",
))

SC03_ASSET_ATTRS = {
    "img": ("src",),
    "source": ("srcset",),
    "video": ("poster",),
    "object": ("data",),
    "embed": ("src",),
}

SC04_FETCHING_RELS = frozenset((
    "stylesheet", "preconnect", "dns-prefetch", "preload", "prefetch",
    "modulepreload",
))

SC10_FRAME_TAGS = frozenset(("iframe", "frame", "portal"))

SVG_DRAWING_TAGS = frozenset((
    "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "image", "use",
))

ICON_STYLE_EXPECTED = (
    ("viewbox", "0 0 24 24"),
    ("fill", "none"),
    ("stroke", "currentColor"),
    ("stroke-linecap", "round"),
    ("stroke-linejoin", "round"),
)

STROKE_WIDTH_MIN = 2.2
STROKE_WIDTH_MAX = 2.6

PLACEHOLDER_PREFIXES = ("{{", "TODO", "図はここに入ります", "グラフを挿入",
                        "chart placeholder")

_DATA_URI_SCAN_HEAD = 64


class Node:
    __slots__ = ("tag", "attrs", "attr_list", "line", "col", "raw",
                 "children", "parent", "texts")

    def __init__(self, tag, attr_list, line, col, raw, parent=None):
        self.tag = tag
        self.attr_list = attr_list
        self.attrs = {}
        for name, value in attr_list:
            key = name.lower()
            if key not in self.attrs:
                self.attrs[key] = value
        self.line = line
        self.col = col
        self.raw = raw or ""
        self.children = []
        self.parent = parent
        self.texts = []

    def get(self, name, default=None):
        value = self.attrs.get(name)
        return default if value is None else value

    def has(self, name):
        return name in self.attrs

    def attr_pos(self, name):
        if not self.raw:
            return self.line, self.col
        match = re.search(r"(?<![\w:.-])" + re.escape(name) + r"\s*=", self.raw,
                          re.IGNORECASE)
        index = match.start() if match else 0
        return _offset_pos(self.line, self.col, self.raw, index)

    def descendants(self):
        for child in self.children:
            yield child
            for deeper in child.descendants():
                yield deeper

    def visible_text(self):
        parts = []
        if self.tag not in RAW_TEXT_TAGS:
            parts.extend(self.texts)
            for child in self.children:
                parts.append(child.visible_text())
        return "".join(parts)


class _Collector(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", [], 1, 1, "")
        self.stack = [self.root]
        self.elements = []
        self.text_regions = []
        self.attr_regions = []
        self.css_blocks = []
        self.js_blocks = []
        self.warnings = []

    # --- helpers ---
    def _pos(self):
        line, offset = self.getpos()
        return line, offset + 1

    def _register(self, tag, attrs):
        line, col = self._pos()
        node = Node(tag, attrs, line, col, self.get_starttag_text(), self.stack[-1])
        self.stack[-1].children.append(node)
        self.elements.append(node)
        for name, value in attrs:
            if not isinstance(value, str) or not value:
                continue
            vline, vcol = node.attr_pos(name)
            scan_value = value
            if scan_value.lstrip().lower().startswith("data:"):
                scan_value = scan_value[:_DATA_URI_SCAN_HEAD]
            self.attr_regions.append((scan_value, vline, vcol))
        return node

    # --- HTMLParser hooks ---
    def handle_starttag(self, tag, attrs):
        node = self._register(tag, attrs)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self._register(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                for forced in self.stack[index + 1:]:
                    self.warnings.append(
                        "未閉じの <{}> を <{}> の終了で強制的に閉じた (line {})".format(
                            forced.tag, tag, forced.line))
                del self.stack[index:]
                return
        line, _col = self._pos()
        self.warnings.append(
            "対応する開始タグの無い終了タグ </{}> (line {})".format(tag, line))

    def handle_data(self, data):
        if not data:
            return
        line, col = self._pos()
        current = self.stack[-1]
        if current.tag == "style":
            self.css_blocks.append((data, line, col))
        elif current.tag == "script":
            self.js_blocks.append((data, line, col))
        else:
            current.texts.append(data)
        self.text_regions.append((data, line, col))

    def close(self):
        super().close()
        for pending in self.stack[1:]:
            self.warnings.append(
                "閉じられていない <{}> (line {})".format(pending.tag, pending.line))
        del self.stack[1:]


class Document:
    """収集済みの 1 パス走査結果。"""

    def __init__(self, html_text):
        self.text = html_text
        collector = _Collector()
        try:
            collector.feed(html_text)
            collector.close()
        except Exception as exc:  # noqa: BLE001 - パーサの回復不能例外は exit 2
            raise InspectionError("HTML パーサが回復不能な例外を出した ({}: {})".format(
                type(exc).__name__, exc))
        self.elements = collector.elements
        self.root = collector.root
        self.text_regions = collector.text_regions
        self.attr_regions = collector.attr_regions
        self.css_blocks = collector.css_blocks
        self.js_blocks = collector.js_blocks
        self.warnings = collector.warnings

    def by_tag(self, *tags):
        wanted = set(tags)
        return [node for node in self.elements if node.tag in wanted]


# ---------------------------------------------------------------------------
# 共通述語
# ---------------------------------------------------------------------------


def _is_data_uri(value):
    return value.strip().lower().startswith("data:")


def _is_fragment(value):
    return value.strip().startswith("#")


def _has_external_scheme(value):
    lowered = value.strip().lower()
    return any(lowered.startswith(prefix) for prefix in EXTERNAL_SCHEME_PREFIXES)


def _srcset_candidates(value):
    """srcset をカンマ区切りで分ける。data URI 内のカンマでは分けない。"""
    parts = re.split(r",(?=\s)", value)
    out = []
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        out.append(stripped.split()[0])
    return out


def _attr_url_values(node, name, value):
    if name == "srcset":
        return _srcset_candidates(value)
    return [value]


_URL_FUNC_RE = re.compile(
    r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^)'\"]*))\s*\)", re.IGNORECASE)
_FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*\}", re.IGNORECASE)
_AT_IMPORT_RE = re.compile(r"@import\b", re.IGNORECASE)
_LOCAL_FUNC_RE = re.compile(r"\blocal\s*\(", re.IGNORECASE)


def _url_matches(css_text):
    for match in _URL_FUNC_RE.finditer(css_text):
        value = match.group(1)
        if value is None:
            value = match.group(2)
        if value is None:
            value = match.group(3)
        yield match.start(), (value or "").strip()


# ---------------------------------------------------------------------------
# SC-01 .. SC-04, SC-10 (CR-EXT)
# ---------------------------------------------------------------------------


def _detect_sc01(doc):
    violations = []
    checked = 0
    for node in doc.elements:
        for name, value in node.attr_list:
            key = name.lower()
            if not isinstance(value, str):
                continue
            candidate = False
            if key in URL_ATTRS:
                candidate = True
            elif key == "xmlns" or key.startswith("xmlns:"):
                if value.strip() in NAMESPACE_URI_WHITELIST:
                    continue
                candidate = True
            elif key == "xml:base":
                candidate = True
            if not candidate:
                continue
            for part in _attr_url_values(node, key, value):
                checked += 1
                if _has_external_scheme(part):
                    line, col = node.attr_pos(name)
                    violations.append(Violation(
                        "SC-01", line, col,
                        "外部スキームを持つ参照属性 {}@{} は自己完結性を破る".format(node.tag, key),
                        part))
    return checked, violations


def _detect_sc02(doc):
    violations = []
    checked = 0
    for label, blocks in (("script", doc.js_blocks), ("style", doc.css_blocks)):
        for text, line, col in blocks:
            checked += 1
            lowered = text.lower()
            for scheme in ("http://", "https://"):
                start = 0
                while True:
                    index = lowered.find(scheme, start)
                    if index < 0:
                        break
                    vline, vcol = _offset_pos(line, col, text, index)
                    violations.append(Violation(
                        "SC-02", vline, vcol,
                        "<{}> 本文の http(s) リテラルはコメントであっても削除すること".format(label),
                        text[index:index + EVIDENCE_MAX]))
                    start = index + len(scheme)
    return checked, violations


def _detect_sc03(doc):
    violations = []
    checked = 0
    for node in doc.elements:
        for attr in SC03_ASSET_ATTRS.get(node.tag, ()):
            value = node.attrs.get(attr)
            if not isinstance(value, str):
                continue
            for part in _attr_url_values(node, attr, value):
                checked += 1
                if _is_data_uri(part):
                    continue
                if _has_external_scheme(part):
                    continue  # 外部スキームは SC-01 が報告する (同一違反を 2 度数えない)
                line, col = node.attr_pos(attr)
                violations.append(Violation(
                    "SC-03", line, col,
                    "{}@{} が data: で始まらない。素材は data URI として同梱すること".format(
                        node.tag, attr),
                    part))
        if node.tag == "a" and isinstance(node.attrs.get("href"), str):
            value = node.attrs["href"]
            checked += 1
            stripped = value.strip()
            if _has_external_scheme(stripped):
                continue  # 外部スキームは SC-01 が報告する (同一違反を 2 度数えない)
            lowered = stripped.lower()
            allowed = (stripped.startswith("#") or lowered.startswith("data:")
                       or lowered.startswith("mailto:") or lowered.startswith("tel:"))
            if not allowed:
                line, col = node.attr_pos("href")
                violations.append(Violation(
                    "SC-03", line, col,
                    "a@href は # / data: / mailto: / tel: のいずれかで始まること",
                    stripped or "(空文字)"))
    return checked, violations


def _detect_sc04(doc):
    violations = []
    checked = 0
    for node in doc.by_tag("link"):
        checked += 1
        rel = node.get("rel", "")
        tokens = {token.lower() for token in re.split(r"\s+", rel) if token}
        hit = sorted(tokens & SC04_FETCHING_RELS)
        if hit:
            line, col = node.attr_pos("rel")
            violations.append(Violation(
                "SC-04", line, col,
                "link@rel={} は href の値によらず外部取得を前提とする指示である".format(
                    "/".join(hit)),
                node.raw))
    for text, line, col in doc.css_blocks:
        checked += 1
        for match in _AT_IMPORT_RE.finditer(text):
            vline, vcol = _offset_pos(line, col, text, match.start())
            violations.append(Violation(
                "SC-04", vline, vcol,
                "@import は値によらず違反 (スタイルは HTML 内へ同梱すること)",
                text[match.start():match.start() + EVIDENCE_MAX]))
        for block in _FONT_FACE_RE.finditer(text):
            body = block.group(0)
            for offset, value in _url_matches(body):
                if _is_data_uri(value):
                    continue
                vline, vcol = _offset_pos(line, col, text, block.start() + offset)
                violations.append(Violation(
                    "SC-04", vline, vcol,
                    "@font-face の src url() が data: で始まらない",
                    value))
            for local_match in _LOCAL_FUNC_RE.finditer(body):
                vline, vcol = _offset_pos(line, col, text,
                                          block.start() + local_match.start())
                violations.append(Violation(
                    "SC-04", vline, vcol,
                    "@font-face の local() は端末フォント依存となるため違反",
                    body[local_match.start():local_match.start() + EVIDENCE_MAX]))
    return checked, violations


def _detect_sc10(doc):
    """C60: 取得を発生させ得る参照は data: でなければ一律違反 (allowlist)。"""
    violations = []
    checked = 0

    for node in doc.elements:
        if node.tag in SC10_FRAME_TAGS:
            checked += 1
            violations.append(Violation(
                "SC-10", node.line, node.col,
                "<{}> は入れ子閲覧文脈を持ち込むため要素の存在自体が違反".format(node.tag),
                node.raw))
            continue
        if node.tag == "script":
            checked += 1
            if node.has("src"):
                line, col = node.attr_pos("src")
                violations.append(Violation(
                    "SC-10", line, col,
                    "script@src は値によらず違反。JS はインライン本文として同梱すること",
                    node.get("src", "")))
            continue
        if node.tag == "link":
            checked += 1
            href = node.attrs.get("href")
            if not isinstance(href, str):
                line, col = node.line, node.col
                violations.append(Violation(
                    "SC-10", line, col,
                    "link@href が無い。取得を発生させ得る指示は data: 実体のみ許可する",
                    node.raw))
            elif not _is_data_uri(href):
                line, col = node.attr_pos("href")
                violations.append(Violation(
                    "SC-10", line, col,
                    "link@href が data: で始まらない (rel によらず違反)", href))
            continue
        for name, value in node.attr_list:
            key = name.lower()
            if key not in URL_ATTRS or not isinstance(value, str):
                continue
            if node.tag == "a" and key == "href":
                # a@href の閉包判定は SC-03 が担当する (同一違反を 2 度数えない)
                continue
            for part in _attr_url_values(node, key, value):
                checked += 1
                if _is_data_uri(part) or _is_fragment(part):
                    continue
                line, col = node.attr_pos(name)
                violations.append(Violation(
                    "SC-10", line, col,
                    "{}@{} が data: でも文書内フラグメントでもない (同梱閉包の違反)".format(
                        node.tag, key),
                    part))

    for text, line, col in doc.css_blocks:
        spans = [(m.start(), m.end()) for m in _FONT_FACE_RE.finditer(text)]
        for offset, value in _url_matches(text):
            if any(start <= offset < end for start, end in spans):
                continue  # @font-face の src は SC-04 が報告する
            checked += 1
            if _is_data_uri(value):
                continue
            vline, vcol = _offset_pos(line, col, text, offset)
            violations.append(Violation(
                "SC-10", vline, vcol,
                "CSS の url() が data: で始まらない (同梱閉包の違反)", value))

    for node in doc.elements:
        style_value = node.attrs.get("style")
        if not isinstance(style_value, str):
            continue
        for offset, value in _url_matches(style_value):
            checked += 1
            if _is_data_uri(value):
                continue
            line, col = node.attr_pos("style")
            violations.append(Violation(
                "SC-10", line, col,
                "style 属性の url() が data: で始まらない (同梱閉包の違反)", value))

    return checked, violations


def scan_external_references(html_text):
    """CR-EXT を適用し SC-01..SC-04 および SC-10 の違反を返す。

    取得を発生させない text node の URL は返さない。
    """
    if not isinstance(html_text, str) or not html_text:
        return []
    doc = Document(html_text)
    rows = []
    for detector in (_detect_sc01, _detect_sc02, _detect_sc03, _detect_sc04,
                     _detect_sc10):
        _checked, violations = detector(doc)
        rows.extend(violations)
    rows.sort(key=Violation.sort_key)
    return rows


# ---------------------------------------------------------------------------
# SC-05 (CLI 側の走査範囲)
# ---------------------------------------------------------------------------


def _detect_sc05(doc):
    violations = []
    infos = []
    checked = 0
    regions = list(doc.text_regions) + list(doc.attr_regions)
    for text, line, col in regions:
        checked += 1
        found, info = _emoji_records(text, line, col)
        violations.extend(found)
        infos.extend(info)
    violations.sort(key=Violation.sort_key)
    infos.sort(key=lambda rec: (rec.line, rec.col))
    return checked, violations, infos


# ---------------------------------------------------------------------------
# SC-06 / SC-07
# ---------------------------------------------------------------------------


def _detect_sc06(doc):
    violations = []
    nodes = doc.by_tag("svg", "symbol")
    for node in nodes:
        if not node.has(KIND_ATTR):
            violations.append(Violation(
                "SC-06", node.line, node.col,
                "<{}> に {} 属性が無く様式検査の対象を分類できない (未分類を pass へ畳まない)".format(
                    node.tag, KIND_ATTR),
                node.raw))
            continue
        if node.get(KIND_ATTR, "").strip().lower() != KIND_ICON:
            continue
        reasons = []
        for attr, expected in ICON_STYLE_EXPECTED:
            actual = node.attrs.get(attr)
            if actual is None:
                reasons.append("{} が無い".format(attr))
                continue
            normalized = re.sub(r"\s+", " ", actual).strip()
            if normalized != expected:
                reasons.append("{}={!r} (期待 {!r})".format(attr, normalized, expected))
        width = node.attrs.get("stroke-width")
        if width is None:
            reasons.append("stroke-width が無い")
        else:
            try:
                value = float(str(width).strip())
            except ValueError:
                reasons.append("stroke-width={!r} が数値でない".format(width))
            else:
                if not (STROKE_WIDTH_MIN <= value <= STROKE_WIDTH_MAX):
                    reasons.append("stroke-width={} が {}..{} の外".format(
                        value, STROKE_WIDTH_MIN, STROKE_WIDTH_MAX))
        if reasons:
            violations.append(Violation(
                "SC-06", node.line, node.col,
                "アイコン様式に適合しない <{}>: {}".format(node.tag, " / ".join(reasons)),
                node.raw))
    violations.sort(key=Violation.sort_key)
    return len(nodes), violations


def _use_reference(node):
    for attr in ("href", "xlink:href"):
        value = node.attrs.get(attr)
        if isinstance(value, str):
            return attr, value
    return None, None


def _detect_sc07(doc):
    violations = []
    symbols = [node for node in doc.by_tag("symbol") if isinstance(node.attrs.get("id"), str)]
    uses = doc.by_tag("use")

    referenced = []
    for node in uses:
        attr, value = _use_reference(node)
        if value is None:
            continue
        stripped = value.strip()
        if not stripped.startswith("#"):
            continue  # 外部ファイル参照は SC-01 / SC-03 / SC-10 の領分
        referenced.append((stripped[1:], node, attr))

    defined_ids = [node.attrs["id"] for node in symbols]
    referenced_ids = {ref for ref, _node, _attr in referenced}

    seen = {}
    for node in symbols:
        sid = node.attrs["id"]
        if sid in seen:
            violations.append(Violation(
                "SC-07", node.line, node.col,
                "symbol id が重複している: {}".format(sid), node.raw))
        else:
            seen[sid] = node

    for node in symbols:
        sid = node.attrs["id"]
        if sid not in referenced_ids and seen.get(sid) is node:
            violations.append(Violation(
                "SC-07", node.line, node.col,
                "未使用の symbol 定義: {} (use から 1 度も参照されていない)".format(sid),
                node.raw))

    for ref, node, _attr in referenced:
        if ref not in seen:
            violations.append(Violation(
                "SC-07", node.line, node.col,
                "未定義の use 参照: #{} に対応する symbol が無い".format(ref), node.raw))

    violations.sort(key=Violation.sort_key)
    return len(defined_ids) + len(referenced), violations


# ---------------------------------------------------------------------------
# SC-08
# ---------------------------------------------------------------------------


def _class_tokens(node):
    value = node.attrs.get("class")
    if not isinstance(value, str):
        return frozenset()
    return frozenset(token for token in re.split(r"\s+", value) if token)


def _detect_sc08(doc):
    violations = []
    info = []
    nav_nodes = [node for node in doc.elements
                 if node.tag == "nav" or "navbar" in _class_tokens(node)]
    sections = [node for node in doc.by_tag("section")
                if isinstance(node.attrs.get("id"), str)]

    if not nav_nodes and not sections:
        violations.append(Violation(
            "SC-08", 1, 1,
            "sticky ナビも section も存在せず、資料 HTML の構造要件を満たさない",
            ""))
        return 0, violations, info

    nav_links = []
    for nav in nav_nodes:
        for node in nav.descendants():
            if node.tag != "a":
                continue
            href = node.attrs.get("href")
            if isinstance(href, str) and href.strip().startswith("#"):
                nav_links.append((href.strip(), node))

    section_ids = []
    excluded = []
    for node in sections:
        sid = node.attrs["id"]
        if node.get(NAV_EXCLUDE_ATTR, "").strip().lower() == NAV_EXCLUDE_VALUE:
            excluded.append(sid)
            info.append(InfoRecord(
                "SC-08", node.line, node.col,
                "{}=\"{}\" により nav 未掲載を許容した section: {}".format(
                    NAV_EXCLUDE_ATTR, NAV_EXCLUDE_VALUE, sid)))
            continue
        section_ids.append(sid)

    known_section_ids = {node.attrs["id"] for node in sections}
    seen_hrefs = set()
    referenced = set()
    for href, node in nav_links:
        target = href[1:]
        if not target:
            line, col = node.attr_pos("href")
            violations.append(Violation(
                "SC-08", line, col,
                "空フラグメント href=\"#\" は解決先を持たない", node.raw))
            continue
        if href in seen_hrefs:
            line, col = node.attr_pos("href")
            violations.append(Violation(
                "SC-08", line, col,
                "nav 内で同一 href が重複している: {}".format(href), node.raw))
        seen_hrefs.add(href)
        referenced.add(target)
        if target not in known_section_ids:
            line, col = node.attr_pos("href")
            violations.append(Violation(
                "SC-08", line, col,
                "未解決のナビ参照: {} に対応する section id が存在しない".format(href),
                node.raw))

    for node in sections:
        sid = node.attrs["id"]
        if sid in excluded:
            continue
        if sid not in referenced:
            violations.append(Violation(
                "SC-08", node.line, node.col,
                "nav から参照されていない section: id={}".format(sid), node.raw))

    id_positions = {}
    for node in doc.elements:
        value = node.attrs.get("id")
        if not isinstance(value, str) or not value:
            continue
        if value in id_positions:
            violations.append(Violation(
                "SC-08", node.line, node.col,
                "文書内で id が重複している: {}".format(value), node.raw))
        else:
            id_positions[value] = node

    violations.sort(key=Violation.sort_key)
    return len(nav_links) + len(sections), violations, info


# ---------------------------------------------------------------------------
# SC-09 (R21 C55)
# ---------------------------------------------------------------------------

_FIGURE_PART_IDS_CACHE = None


def figure_part_ids():
    """図表・グラフの部品 id を config の単一正本から読む。

    handout-parts.json 以外へ部品 id を列挙しない (config の rule)。
    media 部品のうち素テキストの受け皿 (data_block_type=text) を除いたものが
    「枠が空でないこと」を要求される対象である。
    """
    global _FIGURE_PART_IDS_CACHE
    if _FIGURE_PART_IDS_CACHE is not None:
        return _FIGURE_PART_IDS_CACHE
    path = PLUGIN_ROOT.joinpath(*PARTS_CATALOG_RELPATH)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InspectionError(
            "部品 id の正本を読めない: {} ({})".format(path, exc))
    ids = []
    for part in data.get("parts", []):
        if not isinstance(part, dict):
            continue
        if part.get("kind") != PART_KIND_MEDIA:
            continue
        if part.get("data_block_type") == PART_BLOCK_TYPE_PLAIN_TEXT:
            continue
        part_id = part.get("id")
        if isinstance(part_id, str):
            ids.append(part_id)
    if not ids:
        raise InspectionError(
            "部品 id の正本に図表部品が 1 件も無い: {}".format(path))
    _FIGURE_PART_IDS_CACHE = frozenset(ids)
    return _FIGURE_PART_IDS_CACHE


def _data_uri_payload_length(value):
    body = value.strip()[len("data:"):]
    meta, sep, payload = body.partition(",")
    if not sep:
        return 0
    if "base64" in meta.lower():
        try:
            return len(base64.b64decode(payload, validate=False))
        except Exception:  # noqa: BLE001 - 壊れた base64 は実体無しとみなす
            return 0
    return len(payload.encode("utf-8"))


def _detect_sc09(doc):
    violations = []
    part_ids = figure_part_ids()
    targets = []
    for node in doc.elements:
        part = node.attrs.get(PART_ATTR)
        is_part_target = isinstance(part, str) and part.strip() in part_ids
        if is_part_target or node.tag == "figure":
            targets.append(node)

    for node in targets:
        imgs = [child for child in node.descendants() if child.tag == "img"]
        svgs = [child for child in node.descendants() if child.tag == "svg"]

        if not imgs and not svgs:
            violations.append(Violation(
                "SC-09", node.line, node.col,
                "図表の枠だけが残り <img> も <svg> も持たない", node.raw))
        else:
            satisfied = False
            reasons = []
            for img in imgs:
                src = img.attrs.get("src")
                if not isinstance(src, str) or not src.strip():
                    reasons.append("<img> に src が無い")
                    continue
                if not _is_data_uri(src):
                    reasons.append("<img src> が data: ではない")
                    continue
                size = _data_uri_payload_length(src)
                if size < 64:
                    reasons.append("<img src> の実体長 {} バイトが 64 バイト未満".format(size))
                    continue
                satisfied = True
            for svg in svgs:
                drawing = [child for child in svg.descendants()
                           if child.tag in SVG_DRAWING_TAGS]
                if drawing:
                    satisfied = True
                else:
                    reasons.append("<svg> が描画要素を 1 つも持たない")
            if not satisfied:
                violations.append(Violation(
                    "SC-09", node.line, node.col,
                    "図表の中身が空である: {}".format(" / ".join(reasons) or "実体無し"),
                    node.raw))

        text = re.sub(r"\s+", " ", node.visible_text()).strip()
        if text:
            for prefix in PLACEHOLDER_PREFIXES:
                if text.startswith(prefix):
                    violations.append(Violation(
                        "SC-09", node.line, node.col,
                        "未解決のプレースホルダが残っている: {!r}".format(prefix), text))
                    break

    violations.sort(key=Violation.sort_key)
    return len(targets), violations


# ---------------------------------------------------------------------------
# 検査全体
# ---------------------------------------------------------------------------


class DetectionResult:
    __slots__ = ("id", "checked", "violations", "info")

    def __init__(self, detection_id, checked, violations, info=None):
        self.id = detection_id
        self.checked = checked
        self.violations = violations
        self.info = info or []

    @property
    def status(self):
        return "FAIL" if self.violations else "PASS"

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "checked": self.checked,
            "violations": [v.to_dict() for v in self.violations],
            "info": [i.to_dict() for i in self.info],
        }


def inspect_html(html_text):
    """全 detection を評価して DetectionResult の固定順 list を返す。"""
    doc = Document(html_text)
    results = {}

    for detection_id, detector in (("SC-01", _detect_sc01), ("SC-02", _detect_sc02),
                                   ("SC-03", _detect_sc03), ("SC-04", _detect_sc04),
                                   ("SC-10", _detect_sc10)):
        checked, violations = detector(doc)
        violations.sort(key=Violation.sort_key)
        results[detection_id] = DetectionResult(detection_id, checked, violations)

    checked, violations, infos = _detect_sc05(doc)
    results["SC-05"] = DetectionResult("SC-05", checked, violations, infos)

    checked, violations = _detect_sc06(doc)
    results["SC-06"] = DetectionResult("SC-06", checked, violations)

    checked, violations = _detect_sc07(doc)
    results["SC-07"] = DetectionResult("SC-07", checked, violations)

    checked, violations, infos = _detect_sc08(doc)
    results["SC-08"] = DetectionResult("SC-08", checked, violations, infos)

    checked, violations = _detect_sc09(doc)
    results["SC-09"] = DetectionResult("SC-09", checked, violations)

    ordered = [results[detection_id] for detection_id in DETECTION_IDS]
    warnings = [{"id": PARSER_WARNING_ID, "message": _sanitize(text)}
                for text in doc.warnings]
    return ordered, warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):

    def error(self, message):
        raise InspectionError("引数が不正: {}".format(message))

    def exit(self, status=0, message=None):
        if status:
            raise InspectionError("引数が不正: {}".format(message or "usage error"))
        raise SystemExit(status)


def _build_parser():
    parser = _Parser(
        prog="verify-handout-selfcontained.py",
        description="生成 HTML の自己完結性を検査する fail-closed ゲート",
        add_help=True,
    )
    parser.add_argument("--html", required=True,
                        help="検査対象の生成 HTML (1 実行 1 ファイル)")
    parser.add_argument("--json-report", default=None,
                        help="機械可読の検査結果 JSON の書き出し先 (任意)")
    return parser


def _read_html(path_text):
    path = Path(path_text)
    if not path.exists():
        raise InspectionError("--html のパスが存在しない: {}".format(path))
    if not path.is_file():
        raise InspectionError(
            "--html はファイルを 1 点だけ指定する (ディレクトリ・グロブは受け付けない): {}".format(path))
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InspectionError("--html を読み取れない: {} ({})".format(path, exc))
    try:
        return path, raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise InspectionError("--html が UTF-8 としてデコードできない: {} ({})".format(path, exc))


def _build_report(html_path, results, warnings):
    total_violations = sum(len(r.violations) for r in results)
    result = "FAIL" if total_violations else "PASS"
    return {
        "html": str(html_path),
        "result": result,
        "detections": [r.to_dict() for r in results],
        "summary": {
            "result": result,
            "total_checked": sum(r.checked for r in results),
            "total_violations": total_violations,
            "exit_code": EXIT_QUALITY_FAIL if total_violations else EXIT_OK,
            "failed_detections": [r.id for r in results if r.violations],
        },
        "warnings": warnings,
    }


def _write_report(path_text, report):
    path = Path(path_text)
    parent = path.parent if str(path.parent) else Path(".")
    if not parent.exists():
        raise InspectionError(
            "--json-report の親ディレクトリが存在しない (ディレクトリ作成は本 script の責務ではない): {}".format(
                parent))
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    try:
        path.write_text(payload, encoding="utf-8")
    except OSError as exc:
        raise InspectionError("--json-report を書き込めない: {} ({})".format(path, exc))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = _build_parser().parse_args(argv)
        html_path, html_text = _read_html(args.html)
        results, warnings = inspect_html(html_text)
        report = _build_report(args.html, results, warnings)
        if args.json_report is not None:
            _write_report(args.json_report, report)
    except InspectionError as exc:
        sys.stderr.write("ERROR\t{}\n".format(_sanitize(exc)))
        return EXIT_UNUSABLE
    except SystemExit as exc:  # argparse の --help
        return int(exc.code or 0)

    total_violations = sum(len(r.violations) for r in results)
    verdict = "FAIL" if total_violations else "PASS"

    out = ["RESULT: {} {}".format(verdict, args.html)]
    for result in results:
        out.append("{} {} checked={} violations={}".format(
            result.id, result.status, result.checked, len(result.violations)))
    sys.stdout.write("\n".join(out) + "\n")

    if total_violations:
        rows = []
        for result in results:
            for violation in result.violations:
                rows.append(violation)
        rows.sort(key=Violation.sort_key)
        sys.stderr.write("".join(
            "FAIL\t{}\t{}:{}\t{}\t{}\n".format(
                v.detection_id, v.line, v.col, v.message, v.evidence)
            for v in rows))
        return EXIT_QUALITY_FAIL
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

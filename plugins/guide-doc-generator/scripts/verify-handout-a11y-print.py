#!/usr/bin/env python3
# /// script
# name: verify-handout-a11y-print
# version: 0.1.0
# purpose: C17 生成 HTML の a11y 属性の適用先と A4 印刷用 @media print 規則の宣言を検査する fail-closed ゲート
# inputs:
#   - argv: --html <path> [--json-report <path>]
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
"""verify-handout-a11y-print.py (C17)

生成された単一 HTML について
  (a) a11y 属性が「正しい要素へ」付いているかを部品宣言 (data-hb-part) を基準に検査し
  (b) A4 印刷用の @media print 規則が sticky ヘッダー・lightbox・メモ UI に対して
      実際に宣言されているかを検査し
  (c) sticky ヘッダー分のアンカーオフセット補正が CSS と JS の両方に存在するか
を検査する fail-closed ゲート。

契約の正本: plugin-plans/guide-doc-generator/briefs/script-brief-C17.json
検出規則 ID: A11Y-01..A11Y-07 / PRINT-01..PRINT-04 / STICKY-01 (12 個。増減させない)

read-only。書き込むのは --json-report で明示指定された 1 ファイルのみ。
Python 3.10+ の標準ライブラリのみを使う (HTML パースは html.parser)。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# --------------------------------------------------------------------------
# 定数
# --------------------------------------------------------------------------

DETECTION_IDS = [
    "A11Y-01", "A11Y-02", "A11Y-03", "A11Y-04", "A11Y-05", "A11Y-06", "A11Y-07",
    "PRINT-01", "PRINT-02", "PRINT-03", "PRINT-04",
    "STICKY-01",
]

OUT_OF_SCOPE = [
    "A4 実版面への収まり (テキストのはみ出し・図版の分断) は静的に検査していない",
    "改ページの実位置は静的に検査していない (宣言の有無のみを見る)",
    "実フォーカスリングの描画結果は静的に検査していない",
    "JS 実行後の DOM は静的に検査していない (静的な HTML 文字列のみを読む)",
    "CSS カスケード・詳細度・変数展開・calc の実効性は静的に検査していない "
    "(セレクタ突合は文字列一致)",
    "A11Y-07 (c) と STICKY-01 (b) は script 本文の共起検査に留まる "
    "(実際の分岐利用は検査していない)",
]

A11Y07_NOTE = "(c) は script 本文の文字列共起検査に留まる (実際の分岐利用は未検査)"

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}

# 部品 id の literal はこの script に持たない (P03 Y-05 / AC-C11-19)。
# 検査対象の器は config/handout-parts.json の data_block_type 述語で実行時に引く。
#   A11Y-01 (aria-pressed) の対象 = トグル UI を持つ 2 部品 (選択マップ / 選択チップ)
#   A11Y-02 (aria-selected) の対象 = タブ部品
TOGGLE_BLOCK_TYPES = ("map", "chips")
TAB_BLOCK_TYPE = "tabs"

ROOT_ENV_VARS = ("HB_ROOT", "CLAUDE_PLUGIN_ROOT")
PARTS_RELPATH = Path("config") / "handout-parts.json"

SCREEN_ONLY_PARTS = {"lightbox", "memo", "memo-global", "toolbar"}
SCREEN_ONLY_CLASS_NEEDLES = ("lightbox", "memo")


# --------------------------------------------------------------------------
# HTML 軽量ツリー
# --------------------------------------------------------------------------


class Node:
    __slots__ = ("tag", "attrs", "line", "col", "parent", "children", "texts")

    def __init__(self, tag, attrs, line, col, parent):
        self.tag = tag
        self.attrs = attrs
        self.line = line
        self.col = col
        self.parent = parent
        self.children = []
        self.texts = []

    # --- 便宜 ---
    def classes(self):
        raw = self.attrs.get("class") or ""
        return [c.lower() for c in raw.split() if c]

    def descendants(self):
        stack = list(self.children)
        while stack:
            n = stack.pop(0)
            yield n
            stack = list(n.children) + stack

    def subtree_text(self):
        buf = list(self.texts)
        for c in self.children:
            buf.append(c.subtree_text())
        return "".join(buf)

    def own_and_child_text(self):
        """自分の直下テキスト + svg 以外の子孫テキスト。"""
        buf = list(self.texts)
        for c in self.children:
            if c.tag == "svg":
                continue
            buf.append(c.subtree_text())
        return "".join(buf)

    def ancestors(self):
        p = self.parent
        while p is not None:
            yield p
            p = p.parent

    def repr_short(self):
        bits = [self.tag]
        for a in ("data-hb-part", "data-hb-kind", "id", "class", "role"):
            v = self.attrs.get(a)
            if v:
                bits.append('{}="{}"'.format(a, v))
        return "<" + " ".join(bits) + ">"


class StyleBlob:
    __slots__ = ("text", "line", "col")

    def __init__(self, text, line, col):
        self.text = text
        self.line = line
        self.col = col


class DocParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, 1, 0, None)
        self.stack = [self.root]
        self.all = []
        self.styles = []
        self.scripts = []
        self._pending = None  # ("style"|"script", line, col)

    # --- 内部 ---
    def _open(self, tag, attrs, line, col):
        d = {}
        for k, v in attrs:
            if k not in d:
                d[k] = v if v is not None else ""
        node = Node(tag, d, line, col, self.stack[-1])
        self.stack[-1].children.append(node)
        self.all.append(node)
        return node

    # --- HTMLParser hooks ---
    def handle_starttag(self, tag, attrs):
        line, col = self.getpos()
        node = self._open(tag, attrs, line, col)
        if tag in VOID_TAGS:
            return
        self.stack.append(node)
        if tag in ("style", "script"):
            self._pending = (tag, line, col)

    def handle_startendtag(self, tag, attrs):
        line, col = self.getpos()
        self._open(tag, attrs, line, col)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break
        if tag in ("style", "script"):
            self._pending = None

    def handle_data(self, data):
        line, col = self.getpos()
        cur = self.stack[-1]
        if cur.tag == "style":
            self.styles.append(StyleBlob(data, line, col))
        elif cur.tag == "script":
            self.scripts.append(StyleBlob(data, line, col))
        else:
            cur.texts.append(data)


# --------------------------------------------------------------------------
# CSS 粗トークナイザ
# --------------------------------------------------------------------------


class CssRule:
    __slots__ = ("prelude", "selectors", "decls", "line", "col", "context")

    def __init__(self, prelude, decls, line, col, context):
        self.prelude = prelude
        self.selectors = split_selectors(prelude)
        self.decls = decls
        self.line = line
        self.col = col
        self.context = context


class AtBlock:
    __slots__ = ("name", "prelude", "rules", "decls", "line", "col")

    def __init__(self, name, prelude, line, col):
        self.name = name
        self.prelude = prelude
        self.rules = []
        self.decls = []
        self.line = line
        self.col = col

    def decl_count(self):
        return len(self.decls) + sum(len(r.decls) for r in self.rules)


def norm_sel(text):
    return re.sub(r"\s+", " ", text.strip()).lower()


def split_selectors(prelude):
    out = []
    depth = 0
    buf = []
    for ch in prelude:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append(norm_sel("".join(buf)))
            buf = []
        else:
            buf.append(ch)
    tail = norm_sel("".join(buf))
    if tail:
        out.append(tail)
    return [s for s in out if s]


def strip_css_comments(text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for ch in text[i:j]:
                out.append("\n" if ch == "\n" else " ")
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def parse_declarations(body):
    decls = []
    for chunk in body.split(";"):
        if ":" not in chunk:
            continue
        prop, _, value = chunk.partition(":")
        prop = prop.strip().lower()
        value = value.strip()
        value = re.sub(r"!\s*important\s*$", "", value, flags=re.I).strip()
        value = re.sub(r"\s+", " ", value).lower()
        if prop and re.fullmatch(r"-?[a-z][a-z0-9-]*", prop):
            decls.append((prop, value))
    return decls


def _match_block(text, open_idx):
    """open_idx は '{'。対応する '}' の index を返す。見つからなければ None。"""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


class CssModel:
    def __init__(self):
        self.top_rules = []
        self.at_blocks = []
        self.unparsed = []

    def all_rules(self):
        for r in self.top_rules:
            yield r
        for b in self.at_blocks:
            for r in b.rules:
                yield r


def parse_css_blob(blob, model):
    text = strip_css_comments(blob.text)

    def pos(offset):
        head = text[:offset]
        nl = head.count("\n")
        if nl:
            return blob.line + nl, offset - (head.rfind("\n") + 1)
        return blob.line, blob.col + offset

    i = 0
    n = len(text)
    while i < n:
        while i < n and (text[i].isspace() or text[i] == ";"):
            i += 1
        if i >= n:
            break
        start = i
        j = i
        while j < n and text[j] not in "{}":
            j += 1
        if j >= n:
            rest = text[start:].strip()
            if rest:
                line, col = pos(start)
                model.unparsed.append({
                    "line": line, "col": col,
                    "reason": "ブロックが閉じていない、または宣言ブロックを伴わない断片",
                    "snippet": rest[:60],
                })
            break
        if text[j] == "}":
            frag = text[start:j + 1].strip()
            if frag:
                line, col = pos(start)
                model.unparsed.append({
                    "line": line, "col": col,
                    "reason": "対応する開き括弧の無い '}'",
                    "snippet": frag[:60],
                })
            i = j + 1
            continue

        prelude = text[start:j].strip()
        close = _match_block(text, j)
        if close is None:
            line, col = pos(start)
            model.unparsed.append({
                "line": line, "col": col,
                "reason": "ブロックが閉じていない",
                "snippet": text[start:start + 60].strip(),
            })
            break
        body = text[j + 1:close]
        line, col = pos(start)
        _consume_block(prelude, body, j + 1, line, col, pos, model)
        i = close + 1


def _consume_block(prelude, body, body_offset, line, col, pos, model):
    if prelude.startswith("@"):
        name = re.split(r"[\s({]", prelude[1:], 1)[0].strip().lower()
        block = AtBlock(name, norm_sel(prelude), line, col)
        if "{" in body:
            ok = _parse_nested_rules(body, body_offset, pos, block, model, prelude, line, col)
            if not ok:
                return
        else:
            block.decls = parse_declarations(body)
        model.at_blocks.append(block)
        return

    if "{" in body:
        model.unparsed.append({
            "line": line, "col": col,
            "reason": "宣言ブロック内の入れ子 (CSS ネスト構文) は本 script の粗トークナイザで解けない",
            "snippet": (prelude + "{")[:60],
        })
        return
    model.top_rules.append(CssRule(prelude, parse_declarations(body), line, col, None))


def _parse_nested_rules(body, body_offset, pos, block, model, prelude, line, col):
    i = 0
    n = len(body)
    while i < n:
        while i < n and (body[i].isspace() or body[i] == ";"):
            i += 1
        if i >= n:
            break
        start = i
        j = i
        while j < n and body[j] not in "{}":
            j += 1
        if j >= n or body[j] == "}":
            frag = body[start:j].strip()
            if frag:
                l2, c2 = pos(body_offset + start)
                model.unparsed.append({
                    "line": l2, "col": c2,
                    "reason": "at-rule 内で宣言ブロックを伴わない断片",
                    "snippet": frag[:60],
                })
                return False
            i = j + 1
            continue
        inner_prelude = body[start:j].strip()
        close = _match_block(body, j)
        if close is None:
            l2, c2 = pos(body_offset + start)
            model.unparsed.append({
                "line": l2, "col": c2,
                "reason": "at-rule 内のブロックが閉じていない",
                "snippet": inner_prelude[:60],
            })
            return False
        inner_body = body[j + 1:close]
        l2, c2 = pos(body_offset + start)
        if inner_prelude.startswith("@"):
            model.unparsed.append({
                "line": l2, "col": c2,
                "reason": "入れ子になった at-rule は本 script の粗トークナイザで解けない",
                "snippet": (prelude + " > " + inner_prelude)[:60],
            })
            return False
        if "{" in inner_body:
            model.unparsed.append({
                "line": l2, "col": c2,
                "reason": "at-rule 内の宣言ブロックにさらに入れ子がある (CSS ネスト構文)",
                "snippet": (prelude + " > " + inner_prelude)[:60],
            })
            return False
        block.rules.append(
            CssRule(inner_prelude, parse_declarations(inner_body), l2, c2, block.prelude))
        i = close + 1
    return True


# --------------------------------------------------------------------------
# セレクタ <-> 要素の粗マッチ
# --------------------------------------------------------------------------

_ATTR_PART_RE = re.compile(r'^\[data-hb-part\s*=\s*(.+?)\]$')
_TAG_RE = re.compile(r"^[a-z][a-z0-9]*$")
_TAG_CLASS_RE = re.compile(r"^([a-z][a-z0-9]*)\.([a-z0-9_-]+)$")
_CLASS_RE = re.compile(r"^\.([a-z0-9_-]+)$")
_ID_RE = re.compile(r"^#([a-z0-9_-]+)$")


def selector_matches_element(sel, el):
    """タグ / class / id / [data-hb-part] レベルの文字列一致だけを見る粗マッチ。"""
    s = sel.strip()
    if not s:
        return False
    if s == "*":
        return True
    m = _ATTR_PART_RE.match(s)
    if m:
        want = m.group(1).strip().strip("\"'")
        return (el.attrs.get("data-hb-part") or "").lower() == want
    m = _CLASS_RE.match(s)
    if m:
        return m.group(1) in el.classes()
    m = _ID_RE.match(s)
    if m:
        return (el.attrs.get("id") or "").lower() == m.group(1)
    if _TAG_RE.match(s):
        return el.tag == s
    m = _TAG_CLASS_RE.match(s)
    if m:
        return el.tag == m.group(1) and m.group(2) in el.classes()
    return False


def selector_tokens(sel):
    """セレクタから JS 側で参照されうる識別子 (class / id / tag) を取り出す。"""
    return [t for t in re.findall(r"[.#]?[a-z][a-z0-9_-]*", sel) if t]


# --------------------------------------------------------------------------
# 検査コンテキスト
# --------------------------------------------------------------------------


class CatalogError(Exception):
    """部品カタログ正本を解決できない (fail-closed / exit 2)。"""


def resolve_root():
    for name in ROOT_ENV_VARS:
        value = os.environ.get(name)
        if value:
            return Path(value)
    return Path(__file__).resolve().parent.parent


def load_part_ids_by_block_type(root=None):
    """data_block_type -> 部品 id の対応をカタログ正本から引く。

    この script は部品 id の名簿も literal も持たない (P03 Y-05)。
    カタログが引けないときは黙って素通しせず fail-closed で落とす。
    """
    path = (Path(root) if root is not None else resolve_root()) / PARTS_RELPATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CatalogError("部品カタログ正本を読めない: {} ({})".format(path, exc))
    table = {}
    parts = data.get("parts") if isinstance(data, dict) else None
    for part in parts or []:
        if not isinstance(part, dict):
            continue
        block = part.get("data_block_type")
        part_id = part.get("id")
        if isinstance(block, str) and isinstance(part_id, str):
            if block in table:
                raise CatalogError(
                    "部品カタログの data_block_type が一意でない: {}".format(block))
            table[block] = part_id
    missing = [b for b in (*TOGGLE_BLOCK_TYPES, TAB_BLOCK_TYPE) if b not in table]
    if missing:
        raise CatalogError(
            "部品カタログに検査対象の block.type が無い: {}".format(", ".join(missing)))
    return table


class Ctx:
    def __init__(self, doc, css, part_ids):
        self.part_ids = part_ids
        self.toggle_parts = {part_ids[b] for b in TOGGLE_BLOCK_TYPES}
        self.tab_part = part_ids[TAB_BLOCK_TYPE]
        self.doc = doc
        self.css = css
        self.elements = doc.all
        self.by_id = {}
        for el in doc.all:
            eid = el.attrs.get("id")
            if eid and eid not in self.by_id:
                self.by_id[eid] = el
        self.parts = [el for el in doc.all if "data-hb-part" in el.attrs]
        self.script_text = "\n".join(s.text for s in doc.scripts)
        self.scripts = doc.scripts

        self.print_blocks = [
            b for b in css.at_blocks
            if b.name == "media" and re.search(r"\bprint\b", b.prelude)
        ]
        self.print_rules = [r for b in self.print_blocks for r in b.rules]
        self.non_print_rules = list(css.top_rules)
        for b in css.at_blocks:
            if b not in self.print_blocks:
                self.non_print_rules.extend(b.rules)
        self.sections = [
            el for el in doc.all
            if el.tag == "section" or (el.attrs.get("data-hb-part") == "section")
        ]


def V(line, col, target, missing):
    return {"line": int(line), "col": int(col), "target": target, "missing": missing}


# --------------------------------------------------------------------------
# A11Y-01 aria-pressed
# --------------------------------------------------------------------------


def detect_a11y01(ctx):
    checked = 0
    vio = []
    for part in ctx.parts:
        if part.attrs.get("data-hb-part") not in ctx.toggle_parts:
            continue
        toggles = []
        for el in part.descendants():
            if el.attrs.get("data-hb-part-role") == "aux":
                continue
            if el.tag == "button" or (el.attrs.get("role") or "").lower() == "button":
                toggles.append(el)
        checked += len(toggles)
        for el in toggles:
            val = el.attrs.get("aria-pressed")
            if val not in ("true", "false"):
                vio.append(V(el.line, el.col, el.repr_short(),
                             'aria-pressed が "true"|"false" で付いていない '
                             "(現在値: {})".format("欠落" if val is None else repr(val))))
        if "data-hb-single" in part.attrs:
            trues = [el for el in toggles if el.attrs.get("aria-pressed") == "true"]
            if len(trues) > 1:
                vio.append(V(part.line, part.col, part.repr_short(),
                             'data-hb-single の単一選択で aria-pressed="true" が '
                             "{} 個ある (高々 1 個)".format(len(trues))))
    return checked, vio


# --------------------------------------------------------------------------
# A11Y-02 aria-selected
# --------------------------------------------------------------------------


def detect_a11y02(ctx):
    checked = 0
    vio = []
    for part in ctx.parts:
        if part.attrs.get("data-hb-part") != ctx.tab_part:
            continue
        nodes = [part] + list(part.descendants())
        if not any((n.attrs.get("role") or "").lower() == "tablist" for n in nodes):
            vio.append(V(part.line, part.col, part.repr_short(),
                         'role="tablist" が部品 root にもその子孫にも無い'))
        tabs = [n for n in nodes if (n.attrs.get("role") or "").lower() == "tab"]
        checked += len(tabs)

        bad_value = False
        for t in tabs:
            val = t.attrs.get("aria-selected")
            if val not in ("true", "false"):
                bad_value = True
                vio.append(V(t.line, t.col, t.repr_short(),
                             'aria-selected が "true"|"false" で付いていない '
                             "(現在値: {})".format("欠落" if val is None else repr(val))))

        selected_ok = False
        if not bad_value and tabs:
            trues = [t for t in tabs if t.attrs.get("aria-selected") == "true"]
            if len(trues) != 1:
                vio.append(V(part.line, part.col, part.repr_short(),
                             'aria-selected="true" がちょうど 1 個でない '
                             "({} 個)".format(len(trues))))
            else:
                selected_ok = True

        panels = {}
        controls_ok = True
        for t in tabs:
            ref = t.attrs.get("aria-controls")
            if not ref:
                controls_ok = False
                vio.append(V(t.line, t.col, t.repr_short(),
                             "aria-controls が無く対応する tabpanel を同定できない"))
                continue
            target = ctx.by_id.get(ref)
            if target is None:
                controls_ok = False
                vio.append(V(t.line, t.col, t.repr_short(),
                             'aria-controls="{}" が実在する id を指していない'.format(ref)))
                continue
            if (target.attrs.get("role") or "").lower() != "tabpanel":
                controls_ok = False
                vio.append(V(t.line, t.col, t.repr_short(),
                             'aria-controls="{}" の参照先が role="tabpanel" でない'.format(ref)))
                continue
            panels[t] = target

        if selected_ok and controls_ok:
            for t in tabs:
                panel = panels.get(t)
                if panel is None:
                    continue
                is_selected = t.attrs.get("aria-selected") == "true"
                has_hidden = "hidden" in panel.attrs
                if is_selected and has_hidden:
                    vio.append(V(panel.line, panel.col, panel.repr_short(),
                                 "選択中の tab に対応する tabpanel に hidden が付いている"))
                elif (not is_selected) and (not has_hidden):
                    vio.append(V(panel.line, panel.col, panel.repr_short(),
                                 "非選択の tab に対応する tabpanel に hidden が無い"))
    return checked, vio


# --------------------------------------------------------------------------
# A11Y-03 アクセシブル名
# --------------------------------------------------------------------------


def _has_attr_name(el):
    for a in ("aria-label", "aria-labelledby", "title"):
        v = el.attrs.get(a)
        if v is not None and v.strip():
            return True
    return False


def detect_a11y03(ctx):
    checked = 0
    vio = []
    labels_for = set()
    for el in ctx.elements:
        if el.tag == "label":
            v = el.attrs.get("for")
            if v:
                labels_for.add(v)

    for el in ctx.elements:
        interactive = (
            el.tag in ("button", "summary")
            or (el.tag == "a" and "href" in el.attrs)
            or el.tag == "input"
        )
        if not interactive:
            continue
        checked += 1
        if _has_attr_name(el):
            continue
        if el.tag == "input":
            eid = el.attrs.get("id")
            if eid and eid in labels_for:
                continue
            if any(a.tag == "label" for a in el.ancestors()):
                continue
            vio.append(V(el.line, el.col, el.repr_short(),
                         "アクセシブル名が無い (label[for] / 祖先 label / aria-label / "
                         "aria-labelledby / title のいずれも無い)"))
            continue
        if el.subtree_text().strip():
            continue
        vio.append(V(el.line, el.col, el.repr_short(),
                     "アクセシブル名が無い (非空テキスト / aria-label / aria-labelledby / "
                     "title のいずれも無い)"))
    return checked, vio


# --------------------------------------------------------------------------
# A11Y-04 表の見出しセル
# --------------------------------------------------------------------------


def detect_a11y04(ctx):
    checked = 0
    vio = []
    for table in [el for el in ctx.elements if el.tag == "table"]:
        for th in [n for n in table.descendants() if n.tag == "th"]:
            checked += 1
            scope = th.attrs.get("scope")
            in_thead = False
            for a in th.ancestors():
                if a is table:
                    break
                if a.tag == "thead":
                    in_thead = True
                    break
            if scope not in ("col", "row"):
                vio.append(V(th.line, th.col, th.repr_short(),
                             'scope="col"|"row" が無い (現在値: {})'.format(
                                 "欠落" if scope is None else repr(scope))))
                continue
            if in_thead and scope != "col":
                vio.append(V(th.line, th.col, th.repr_short(),
                             '<thead> 内の th は scope="col" であること (現在値: '
                             '"{}")'.format(scope)))
            elif (not in_thead) and scope != "row":
                vio.append(V(th.line, th.col, th.repr_short(),
                             '行頭の th は scope="row" であること (現在値: '
                             '"{}")'.format(scope)))
    return checked, vio


# --------------------------------------------------------------------------
# A11Y-05 装飾 SVG と意味を持つ SVG
# --------------------------------------------------------------------------


def detect_a11y05(ctx):
    checked = 0
    vio = []
    for svg in [el for el in ctx.elements if el.tag == "svg"]:
        kind = (svg.attrs.get("data-hb-kind") or "").lower()
        if not kind:
            continue
        checked += 1
        hidden = svg.attrs.get("aria-hidden") == "true"
        has_title = any(c.tag == "title" for c in svg.descendants())
        svg_label = svg.attrs.get("aria-label")
        svg_names = bool(has_title or (svg_label and svg_label.strip()))
        parent = svg.parent
        parent_text = parent.own_and_child_text().strip() if parent is not None else ""
        parent_label = ""
        if parent is not None:
            parent_label = (parent.attrs.get("aria-label") or "").strip()

        if kind == "figure":
            if not svg_names:
                vio.append(V(svg.line, svg.col, svg.repr_short(),
                             'data-hb-kind="figure" の svg は <title> または aria-label が必須'))
        elif kind in ("icon", "decor", "mascot"):
            if parent_text and not hidden:
                vio.append(V(svg.line, svg.col, svg.repr_short(),
                             'テキストを持つ親要素の中の data-hb-kind="{}" には '
                             'aria-hidden="true" が必須'.format(kind)))

        if hidden and has_title:
            vio.append(V(svg.line, svg.col, svg.repr_short(),
                         'aria-hidden="true" の svg が <title> を持つのは矛盾 '
                         "(どちらかを外すこと)"))
        if hidden and svg_names and not has_title and not parent_text and not parent_label:
            vio.append(V(svg.line, svg.col, svg.repr_short(),
                         "アクセシブル名の供給源である svg が "
                         'aria-hidden="true" で名前が消える'))
    return checked, vio


# --------------------------------------------------------------------------
# A11Y-06 :focus-visible
# --------------------------------------------------------------------------

_OUTLINE_OFF = {"none", "0"}


def _fv_base(sel):
    return norm_sel(sel.replace(":focus-visible", ""))


def _focus_base(sel):
    s = sel.replace(":focus-visible", "")
    s = s.replace(":focus-within", "").replace(":focus", "")
    return norm_sel(s)


def detect_a11y06(ctx):
    checked = 0
    vio = []
    fv_rules = []
    fv_bases = set()
    effective = False
    for rule in ctx.css.all_rules():
        fv_sels = [s for s in rule.selectors if ":focus-visible" in s]
        if not fv_sels:
            continue
        fv_rules.append(rule)
        for s in fv_sels:
            fv_bases.add(_fv_base(s))
        for prop, value in rule.decls:
            if prop == "outline" and value and value not in _OUTLINE_OFF:
                effective = True
            elif prop == "outline-style" and value not in ("none", ""):
                effective = True
            elif prop == "box-shadow" and value and value != "none":
                effective = True
    checked += len(fv_rules)

    if not fv_rules:
        vio.append(V(1, 0, "<style>",
                     ":focus-visible を含むセレクタの規則が 1 つも無い "
                     "(文字列の存在だけでは充足しない)"))
    elif not effective:
        first = fv_rules[0]
        vio.append(V(first.line, first.col, first.prelude.strip() or ":focus-visible",
                     ":focus-visible 規則に有効な outline (none/0 以外) または "
                     "box-shadow (none 以外) が無い"))

    universal = "*" in fv_bases
    for rule in ctx.css.all_rules():
        off = False
        for prop, value in rule.decls:
            if prop == "outline" and value in _OUTLINE_OFF:
                off = True
        if not off:
            continue
        for sel in rule.selectors:
            if ":focus-visible" in sel:
                continue
            checked += 1
            base = _focus_base(sel)
            if universal or base in fv_bases:
                continue
            vio.append(V(rule.line, rule.col, sel,
                         "outline を無効化しているが、対応する "
                         "{}:focus-visible 規則が無い".format(base or sel)))
    return checked, vio


# --------------------------------------------------------------------------
# A11Y-07 prefers-reduced-motion
# --------------------------------------------------------------------------

_ZERO_VALUES = {"none", "0", "0s", "0ms", "0s !important"}
_SMOOTH_RE = re.compile(r"""behavior\s*:\s*['"]smooth['"]""")


def _is_off(value):
    v = value.strip()
    return v in _ZERO_VALUES or re.fullmatch(r"0(s|ms)?", v) is not None or v == "none"


def detect_a11y07(ctx):
    checked = 0
    vio = []
    blocks = [b for b in ctx.css.at_blocks
              if b.name == "media"
              and "prefers-reduced-motion" in b.prelude
              and re.search(r"\breduce\b", b.prelude)]
    checked += 1
    if not blocks:
        vio.append(V(1, 0, "@media (prefers-reduced-motion: reduce)",
                     "prefers-reduced-motion と reduce の双方を含む @media ブロックが無い "
                     "(scroll-behavior / animation / transition の抑制が宣言されていない)"))
    else:
        scroll_ok = False
        scroll_bad = False
        anim_ok = False
        trans_ok = False
        for b in blocks:
            for decls in [b.decls] + [r.decls for r in b.rules]:
                for prop, value in decls:
                    if prop == "scroll-behavior":
                        if value == "auto":
                            scroll_ok = True
                        else:
                            scroll_bad = True
                    elif prop in ("animation", "animation-duration") and _is_off(value):
                        anim_ok = True
                    elif prop in ("transition", "transition-duration") and _is_off(value):
                        trans_ok = True
        missing = []
        if not scroll_ok:
            missing.append("scroll-behavior:auto")
        if scroll_bad:
            missing.append("scroll-behavior が auto 以外に指定されている")
        if not anim_ok:
            missing.append("animation / animation-duration の none|0s 化")
        if not trans_ok:
            missing.append("transition / transition-duration の none|0s 化")
        if missing:
            b = blocks[0]
            vio.append(V(b.line, b.col, b.prelude,
                         "reduce ブロックに次が足りない: " + " / ".join(missing)))

    for blob in ctx.scripts:
        checked += 1
        if not _SMOOTH_RE.search(blob.text):
            continue
        if "matchMedia" in blob.text and "prefers-reduced-motion" in blob.text:
            continue
        vio.append(V(blob.line, blob.col, "<script>",
                     "script が behavior:'smooth' を指定しているが、同じ script 内に "
                     "matchMedia と prefers-reduced-motion の参照が無い (共起検査)"))
    return checked, vio


# --------------------------------------------------------------------------
# PRINT-01 @media print / @page
# --------------------------------------------------------------------------


def detect_print01(ctx):
    checked = 1
    vio = []
    if not ctx.print_blocks:
        vio.append(V(1, 0, "@media print",
                     "@media print ブロックが 1 つも無い"))
        return checked, vio
    total = sum(b.decl_count() for b in ctx.print_blocks)
    if total == 0:
        b = ctx.print_blocks[0]
        vio.append(V(b.line, b.col, b.prelude,
                     "@media print ブロックに宣言が 1 つも無い (空ブロック)"))
        return checked, vio

    a4 = False
    for b in ctx.css.at_blocks:
        if b.name != "page":
            continue
        for prop, value in b.decls:
            if prop == "size" and "a4" in value:
                a4 = True
    if not a4:
        for r in ctx.print_rules:
            for prop, value in r.decls:
                if prop == "max-width" and (value.endswith("mm") or value == "100%"):
                    a4 = True
    if not a4:
        b = ctx.print_blocks[0]
        vio.append(V(b.line, b.col, b.prelude,
                     "@page{size:...A4...} も @media print 内での版面幅の再指定 "
                     "(max-width が mm 単位 または 100%) も無い"))
    return checked, vio


# --------------------------------------------------------------------------
# PRINT-02 sticky/fixed の印刷時無効化
# --------------------------------------------------------------------------


def _collect_positioned(ctx, values):
    found = []
    seen = set()
    for rule in ctx.non_print_rules:
        hit = False
        for prop, value in rule.decls:
            if prop == "position" and value in values:
                hit = True
        if not hit:
            continue
        for sel in rule.selectors:
            if sel in seen:
                continue
            seen.add(sel)
            found.append((sel, rule))
    return found


def detect_print02(ctx):
    targets = _collect_positioned(ctx, {"sticky", "fixed"})
    checked = len(targets)
    vio = []
    for sel, rule in targets:
        covered = False
        for pr in ctx.print_rules:
            if not any(ps == sel or sel in ps for ps in pr.selectors):
                continue
            for prop, value in pr.decls:
                if prop == "position" and value in ("static", "relative"):
                    covered = True
                elif prop == "display" and value == "none":
                    covered = True
        if not covered:
            vio.append(V(rule.line, rule.col, sel,
                         "@media print 内で position:static / position:relative / "
                         "display:none のいずれも宣言されていない"))
    return checked, vio


# --------------------------------------------------------------------------
# PRINT-03 画面専用 UI の印刷時非表示
# --------------------------------------------------------------------------


def _is_screen_only(el):
    part = el.attrs.get("data-hb-part")
    if part in SCREEN_ONLY_PARTS:
        return True
    raw = (el.attrs.get("class") or "").lower()
    return any(needle in raw for needle in SCREEN_ONLY_CLASS_NEEDLES)


def detect_print03(ctx):
    candidates = [el for el in ctx.elements if _is_screen_only(el)]
    cand_set = set(id(e) for e in candidates)
    targets = [el for el in candidates
               if not any(id(a) in cand_set for a in el.ancestors())]
    checked = len(targets)
    vio = []
    hide_rules = []
    for pr in ctx.print_rules:
        if any(prop == "display" and value == "none" for prop, value in pr.decls):
            hide_rules.append(pr)
    for el in targets:
        covered = False
        for pr in hide_rules:
            if any(selector_matches_element(s, el) for s in pr.selectors):
                covered = True
                break
        if not covered:
            vio.append(V(el.line, el.col, el.repr_short(),
                         "@media print 内でこの要素へ到達するセレクタの display:none が無い"))
    return checked, vio


# --------------------------------------------------------------------------
# PRINT-04 改ページの意図
# --------------------------------------------------------------------------

_HEADING_RE = re.compile(r"\bh[1-6]\b")


def detect_print04(ctx):
    checked = 1
    vio = []
    break_inside = False
    break_after = False
    for r in ctx.print_rules:
        for prop, value in r.decls:
            if prop in ("break-inside", "page-break-inside") and value == "avoid":
                break_inside = True
            if prop in ("break-after", "page-break-after") and value == "avoid":
                if any(_HEADING_RE.search(s) for s in r.selectors):
                    break_after = True
    ref = ctx.print_blocks[0] if ctx.print_blocks else None
    line = ref.line if ref else 1
    col = ref.col if ref else 0
    if not break_inside:
        vio.append(V(line, col, "@media print",
                     "セクションカードに対する break-inside / page-break-inside: avoid "
                     "の宣言が無い"))
    if not break_after:
        vio.append(V(line, col, "@media print",
                     "見出し要素 (h1..h6) に対する break-after: avoid 相当の宣言が無い"))
    return checked, vio


# --------------------------------------------------------------------------
# STICKY-01 アンカーオフセット補正
# --------------------------------------------------------------------------

_LEN_RE = re.compile(r"^(-?\d+(?:\.\d+)?)")
_SCROLL_CONTAINER_SELECTORS = {"html", ":root", "body", "*"}


def _positive_length(value):
    m = _LEN_RE.match(value.strip())
    if not m:
        return False
    try:
        return float(m.group(1)) > 0
    except ValueError:
        return False


def detect_sticky01(ctx):
    checked = 2
    vio = []

    css_ok = False
    for rule in ctx.non_print_rules:
        for prop, value in rule.decls:
            if prop not in ("scroll-margin-top", "scroll-padding-top"):
                continue
            if not _positive_length(value):
                continue
            for sel in rule.selectors:
                if any(selector_matches_element(sel, sec) for sec in ctx.sections):
                    css_ok = True
                elif prop == "scroll-padding-top" and sel in _SCROLL_CONTAINER_SELECTORS:
                    css_ok = True
    if not css_ok:
        vio.append(V(1, 0, "<style>",
                     "section 群へ到達するセレクタに対する正の "
                     "scroll-margin-top / scroll-padding-top の宣言が無い"))

    sticky_sels = [sel for sel, _ in _collect_positioned(ctx, {"sticky"})]
    tokens = []
    for sel in sticky_sels:
        for t in selector_tokens(sel):
            tokens.append(t.lstrip(".#"))
    js_ok = False
    for blob in ctx.scripts:
        if "getBoundingClientRect" not in blob.text:
            continue
        if not tokens:
            js_ok = True
            break
        if any(t and t in blob.text for t in tokens):
            js_ok = True
            break
    if not js_ok:
        vio.append(V(1, 0, "<script>",
                     "script に getBoundingClientRect による sticky 要素の実測 "
                     "(該当 class/tag の取得との共起) が無い"))
    return checked, vio


# --------------------------------------------------------------------------
# 実行
# --------------------------------------------------------------------------

DETECTORS = {
    "A11Y-01": detect_a11y01,
    "A11Y-02": detect_a11y02,
    "A11Y-03": detect_a11y03,
    "A11Y-04": detect_a11y04,
    "A11Y-05": detect_a11y05,
    "A11Y-06": detect_a11y06,
    "A11Y-07": detect_a11y07,
    "PRINT-01": detect_print01,
    "PRINT-02": detect_print02,
    "PRINT-03": detect_print03,
    "PRINT-04": detect_print04,
    "STICKY-01": detect_sticky01,
}

# data-hb-part を検査アンカーとする detection (アンカー不在なら FAIL に倒す)
ANCHOR_DEPENDENT = ("A11Y-01", "A11Y-02", "A11Y-05")

ANCHOR_MISSING_MSG = (
    "data-hb-part 属性が 1 個も存在せず検査アンカーを同定できない "
    "(C11 render-handout.py の html_attribute_contract に従い data-hb-part を付与すること)"
)


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)

    def exit(self, status=0, message=None):
        if status:
            raise UsageError(message or "引数の解析に失敗した")
        raise SystemExit(status)


def build_parser():
    p = _Parser(prog="verify-handout-a11y-print.py", add_help=True)
    p.add_argument("--html", required=True, help="検査対象の生成 HTML")
    p.add_argument("--json-report", dest="json_report", default=None,
                   help="機械可読の検査結果 JSON の書き出し先")
    return p


def run(html_path, html_text):
    doc = DocParser()
    doc.feed(html_text)
    doc.close()

    css = CssModel()
    for blob in doc.styles:
        parse_css_blob(blob, css)

    ctx = Ctx(doc, css, load_part_ids_by_block_type())
    anchor_missing = not ctx.parts

    results = []
    for det_id in DETECTION_IDS:
        checked, vio = DETECTORS[det_id](ctx)
        if anchor_missing and det_id in ANCHOR_DEPENDENT:
            vio = [V(1, 0, "<document>", ANCHOR_MISSING_MSG)] + list(vio)
            checked = 0
        vio = sorted(vio, key=lambda v: (v["line"], v["col"]))
        results.append({
            "id": det_id,
            "status": "FAIL" if vio else "PASS",
            "checked": checked,
            "violations": vio,
        })

    unparsed = sorted(css.unparsed, key=lambda u: (u["line"], u["col"]))
    total = sum(len(r["violations"]) for r in results)
    failed = [r["id"] for r in results if r["status"] == "FAIL"]
    ok = (total == 0 and not unparsed)

    report = {
        "html": str(html_path),
        "result": "PASS" if ok else "FAIL",
        "detections": results,
        "summary": {
            "total_violations": total,
            "failed_detections": failed,
            "unparsed_css_blocks": len(unparsed),
            "anchor_missing": anchor_missing,
        },
        "unparsed_css_blocks": unparsed,
        "notes": {"A11Y-07": A11Y07_NOTE},
        "out_of_scope": list(OUT_OF_SCOPE),
    }
    for r in results:
        if r["id"] == "A11Y-07":
            r["note"] = A11Y07_NOTE
    return report


def render_stdout(report):
    lines = ["RESULT: {} {}".format(report["result"], report["html"])]
    for det in report["detections"]:
        lines.append("{} {} checked={} violations={}".format(
            det["id"], det["status"], det["checked"], len(det["violations"])))
    lines.append("OUT-OF-SCOPE:")
    for item in OUT_OF_SCOPE:
        lines.append("  - " + item)
    return "\n".join(lines) + "\n"


def render_stderr(report):
    lines = []
    for det in report["detections"]:
        for v in det["violations"]:
            lines.append("FAIL\t{}\t{}:{}\t{}\t{}".format(
                det["id"], v["line"], v["col"], v["target"], v["missing"]))
    for u in report["unparsed_css_blocks"]:
        lines.append("FAIL\tCSS-PARSE\t{}:{}\t{}\t{}".format(
            u["line"], u["col"], u.get("snippet") or "<style>", u["reason"]))
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def main(argv):
    try:
        args = build_parser().parse_args(argv)
    except UsageError as exc:
        reason = " ".join(str(exc).split())
        sys.stderr.write("ERROR\t引数が不正: {}\n".format(reason))
        return 2

    html_path = Path(args.html)
    if not html_path.exists():
        sys.stderr.write("ERROR\t--html のファイルが存在しない: {}\n".format(html_path))
        return 2
    if not html_path.is_file():
        sys.stderr.write("ERROR\t--html がファイルではない: {}\n".format(html_path))
        return 2
    try:
        html_text = html_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        sys.stderr.write("ERROR\t--html を UTF-8 としてデコードできない: {}\n".format(html_path))
        return 2
    except OSError as exc:
        sys.stderr.write("ERROR\t--html を読み取れない: {} ({})\n".format(html_path, exc.strerror))
        return 2

    try:
        report = run(html_path, html_text)
    except CatalogError as exc:
        sys.stderr.write("ERROR\t{}\n".format(exc))
        return 2
    except Exception as exc:  # HTML/CSS パーサの回復不能例外
        sys.stderr.write("ERROR\t検査中に回復不能な例外: {}: {}\n".format(
            type(exc).__name__, exc))
        return 2

    if args.json_report is not None:
        target = Path(args.json_report)
        if not target.parent.exists():
            sys.stderr.write(
                "ERROR\t--json-report の親ディレクトリが存在しない: {}\n".format(target.parent))
            return 2
        try:
            payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False)
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(payload + "\n")
        except OSError as exc:
            sys.stderr.write("ERROR\t--json-report を書き込めない: {} ({})\n".format(
                target, exc.strerror))
            return 2

    sys.stdout.write(render_stdout(report))
    sys.stderr.write(render_stderr(report))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

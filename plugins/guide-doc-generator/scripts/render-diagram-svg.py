#!/usr/bin/env python3
# /// script
# name: render-diagram-svg
# version: 0.1.0
# purpose: C14 図解 1 個分の宣言データから flow / compare / hierarchy / cycle / matrix / versus の 6 パターンを inline SVG 断片として決定論生成する
# inputs:
#   - argv: --diagram <path> [--pattern <name>] [--width <px>]
# outputs:
#   - stdout: inline SVG 断片
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: stdout のみ
# ///
"""C14 render-diagram-svg.py

構造データ (図解 1 個分の宣言 JSON) から
flow / compare / hierarchy / cycle / matrix / versus の 6 パターンの概念図解を
inline SVG 断片として決定論生成する。

契約の正本: plugin-plans/guide-doc-generator/briefs/script-brief-C14.json

- write_scope=none: ファイルを一切作成・更新・削除しない。出力は stdout のみ。
- 標準ライブラリのみ。乱数・時刻・オブジェクト参照値を一切使わない。
- 色はすべて CSS 変数参照 + フォールバックの形で書く (テーマ追従)。
- 外部参照 (取得を発生させる参照) を一切出さない。
"""

import argparse
import html
import json
import math
import re
import sys
import unicodedata
from collections import OrderedDict

# --------------------------------------------------------------------------
# 定数 (brief argv / algorithm 手順 5-9)
# --------------------------------------------------------------------------

PATTERNS = ("flow", "compare", "hierarchy", "cycle", "matrix", "versus")

DEFAULT_WIDTH = 860

MARGIN = 16
GAP = 24
PAD = 12

FS_TITLE = 15
FS_LABEL = 15
FS_NOTE = 12.5
FS_AXIS = 12.5

MAX_LINES_TITLE = 2
MAX_LINES_LABEL = 3
MAX_LINES_NOTE = 2
MAX_LINES_BULLET = 2
MAX_LINES_CELL = 3

LINE_RATIO = 1.45

# 手順 9: 色は var(--token, #fallback) の形でだけ書く
INK = "var(--ink, #16191d)"
MUTED = "var(--ink-muted, #5b6470)"
PRIMARY = "var(--pop-primary, #43a4f5)"
PRIMARY_SOFT = "var(--pop-primary-soft, #d9edfe)"
ACCENT = "var(--pop-accent, #f2994a)"
ACCENT_SOFT = "var(--pop-accent-soft, #fdeadb)"
SURFACE = "var(--surface, #ffffff)"
RULE = "var(--rule, #d5dae1)"

ID_SAFE = re.compile(r"[^A-Za-z0-9_-]")


class DiagramError(Exception):
    """入力データの規約違反 (exit 1) / 実行不能 (exit 2)。"""

    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# 数値と文字列 (手順 5・7・12)
# --------------------------------------------------------------------------

def ifloor(value):
    """明示丸め (round-half-even を避ける)。"""
    return int(math.floor(float(value) + 0.5))


def line_height(font_size):
    return ifloor(float(font_size) * LINE_RATIO)


def fmt_size(value):
    number = float(value)
    if number.is_integer():
        return "%d" % int(number)
    return "%.1f" % number


def esc(value):
    return html.escape(str(value), quote=True)


def is_wide(char):
    return unicodedata.east_asian_width(char) in ("W", "F", "A")


def text_em(text):
    total = 0.0
    for char in text:
        total += 1.00 if is_wide(char) else 0.55
    return total


def text_width(text, font_size):
    return text_em(text) * float(font_size)


def _tokenize(text):
    tokens = []
    buf = ""
    for char in text:
        if char in (" ", "\t", "\n", "　"):
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(" ")
        elif is_wide(char):
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(char)
        else:
            buf += char
    if buf:
        tokens.append(buf)
    return tokens


def wrap_text(text, font_size, max_width):
    """日本語は文字単位・ラテン文字は空白単位の貪欲折返し (手順 6)。"""
    limit = float(max(1, int(max_width)))
    lines = []
    current = ""
    for token in _tokenize(text):
        if token == " " and current == "":
            continue
        candidate = current + token
        if current and text_width(candidate, font_size) > limit:
            lines.append(current.rstrip())
            current = ""
            if token == " ":
                continue
            candidate = token
        if current == "" and text_width(candidate, font_size) > limit:
            piece = ""
            for char in candidate:
                if piece and text_width(piece + char, font_size) > limit:
                    lines.append(piece)
                    piece = char
                else:
                    piece += char
            current = piece
        else:
            current = candidate
    if current.rstrip():
        lines.append(current.rstrip())
    if not lines:
        lines = [""]
    return lines


def fit(text, font_size, max_width, max_lines, where):
    lines = wrap_text(text, font_size, max_width)
    if len(lines) > max_lines:
        raise DiagramError(
            "%s: テキストが枠に収まりません "
            "(見積り幅 %d px / 許容幅 %d px / 折返し後 %d 行 / 上限 %d 行)。"
            "自動短縮はしないので構成データ側で文言を詰めてください"
            % (where, ifloor(text_width(text, font_size)),
               int(max_width), len(lines), max_lines)
        )
    return lines


# --------------------------------------------------------------------------
# SVG 組み立て (手順 12: 属性順を固定・2 スペース・LF)
# --------------------------------------------------------------------------

class Out:
    def __init__(self):
        self.lines = []

    def add(self, indent, text):
        self.lines.append(("  " * indent) + text)


def attrs_str(pairs):
    out = ""
    for name, value in pairs:
        out += ' %s="%s"' % (name, esc(value))
    return out


def rect(out, indent, x, y, width, height, fill, stroke=None, radius=8):
    pairs = [("x", int(x)), ("y", int(y)),
             ("width", int(width)), ("height", int(height))]
    if radius:
        pairs.append(("rx", int(radius)))
    pairs.append(("fill", fill))
    if stroke:
        pairs.append(("stroke", stroke))
        pairs.append(("stroke-width", "1"))
    out.add(indent, "<rect%s />" % attrs_str(pairs))


def line(out, indent, x1, y1, x2, y2, stroke, width="1"):
    pairs = [("x1", int(x1)), ("y1", int(y1)), ("x2", int(x2)), ("y2", int(y2)),
             ("stroke", stroke), ("stroke-width", width), ("aria-hidden", "true")]
    out.add(indent, "<line%s />" % attrs_str(pairs))


def path(out, indent, data, fill="none", stroke=None, width="2"):
    pairs = [("d", data), ("fill", fill)]
    if stroke:
        pairs.append(("stroke", stroke))
        pairs.append(("stroke-width", width))
    pairs.append(("aria-hidden", "true"))
    out.add(indent, "<path%s />" % attrs_str(pairs))


def circle(out, indent, cx, cy, radius, fill, stroke=None, decorative=False):
    pairs = [("cx", int(cx)), ("cy", int(cy)), ("r", int(radius)), ("fill", fill)]
    if stroke:
        pairs.append(("stroke", stroke))
        pairs.append(("stroke-width", "2"))
    if decorative:
        pairs.append(("aria-hidden", "true"))
    out.add(indent, "<circle%s />" % attrs_str(pairs))


def text_block(out, indent, lines, x, y, font_size, fill,
               anchor="middle", weight=None):
    pairs = [("x", int(x)), ("y", int(y)), ("fill", fill),
             ("font-size", fmt_size(font_size)), ("text-anchor", anchor)]
    if weight:
        pairs.append(("font-weight", weight))
    if len(lines) == 1:
        out.add(indent, "<text%s>%s</text>" % (attrs_str(pairs), esc(lines[0])))
        return
    out.add(indent, "<text%s>" % attrs_str(pairs))
    for index, content in enumerate(lines):
        dy = "0" if index == 0 else "1.45em"
        out.add(indent + 1, '<tspan x="%d" dy="%s">%s</tspan>'
                % (int(x), dy, esc(content)))
    out.add(indent, "</text>")


def arrow_head(out, indent, tip_x, tip_y, dir_x, dir_y, fill, size=9, half=5):
    """矢頭を三角形 path で描く (装飾なので aria-hidden)。"""
    norm = math.hypot(dir_x, dir_y)
    if norm == 0.0:
        return
    ux, uy = dir_x / norm, dir_y / norm
    nx, ny = -uy, ux
    bx, by = tip_x - ux * size, tip_y - uy * size
    data = "M %d %d L %d %d L %d %d Z" % (
        ifloor(tip_x), ifloor(tip_y),
        ifloor(bx + nx * half), ifloor(by + ny * half),
        ifloor(bx - nx * half), ifloor(by - ny * half),
    )
    path(out, indent, data, fill=fill)


# --------------------------------------------------------------------------
# 共通の検査 (手順 3-4)
# --------------------------------------------------------------------------

def need_text(container, key, where):
    value = container.get(key) if isinstance(container, dict) else None
    if not isinstance(value, str) or value.strip() == "":
        raise DiagramError("%s: 必須フィールドが欠落しています (空でない文字列が要ります)" % where)
    return value


def need_list(spec, key, low, high):
    value = spec.get(key)
    if value is None:
        raise DiagramError("%s: 必須フィールドが欠落しています" % key)
    if not isinstance(value, list):
        raise DiagramError("%s: 配列である必要があります" % key)
    if not (low <= len(value) <= high):
        raise DiagramError(
            "%s: 件数 %d は許容範囲 %d-%d の外です" % (key, len(value), low, high))
    return value


def need_dict(spec, key):
    value = spec.get(key)
    if not isinstance(value, dict):
        raise DiagramError("%s: 必須フィールドが欠落しています (オブジェクトが要ります)" % key)
    return value


def node_key(node, fallback):
    value = node.get("id") if isinstance(node, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


# --------------------------------------------------------------------------
# パターン: flow
# --------------------------------------------------------------------------

def build_flow(spec, width, body_y, out):
    steps = need_list(spec, "steps", 2, 6)
    count = len(steps)
    avail = width - 2 * MARGIN
    node_w = ifloor((avail - GAP * (count - 1)) / float(count))
    node_w = max(node_w, 2 * PAD + 2)
    inner = max(1, node_w - 2 * PAD)

    label_lines = []
    note_lines = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise DiagramError("steps[%d]: オブジェクトである必要があります" % index)
        where = "steps[%d] (%s)" % (index, node_key(step, "steps[%d]" % index))
        label = need_text(step, "label", where + ".label")
        label_lines.append(fit(label, FS_LABEL, inner, MAX_LINES_LABEL, where + ".label"))
        note = step.get("note")
        if note is None or note == "":
            note_lines.append([])
        elif not isinstance(note, str):
            raise DiagramError("%s.note: 文字列である必要があります" % where)
        else:
            note_lines.append(fit(note, FS_NOTE, inner, MAX_LINES_NOTE, where + ".note"))

    label_lh = line_height(FS_LABEL)
    note_lh = line_height(FS_NOTE)
    max_label = max(len(item) for item in label_lines)
    max_note = max(len(item) for item in note_lines)
    node_h = PAD + max_label * label_lh + PAD
    if max_note:
        node_h += 6 + max_note * note_lh

    for index in range(count):
        x = MARGIN + index * (node_w + GAP)
        rect(out, 1, x, body_y, node_w, node_h, PRIMARY_SOFT, PRIMARY)
        center = x + node_w // 2
        text_block(out, 1, label_lines[index], center,
                   body_y + PAD + FS_LABEL, FS_LABEL, INK, "middle", "600")
        if note_lines[index]:
            text_block(out, 1, note_lines[index], center,
                       body_y + PAD + max_label * label_lh + 6 + ifloor(FS_NOTE),
                       FS_NOTE, MUTED, "middle")

    mid_y = body_y + node_h // 2
    for index in range(count - 1):
        start = MARGIN + index * (node_w + GAP) + node_w
        end = start + GAP
        path(out, 1, "M %d %d L %d %d" % (start + 2, mid_y, end - 9, mid_y),
             fill="none", stroke=PRIMARY)
        arrow_head(out, 1, end - 1, mid_y, 1.0, 0.0, PRIMARY)

    return body_y + node_h + MARGIN


# --------------------------------------------------------------------------
# パターン: compare
# --------------------------------------------------------------------------

def build_compare(spec, width, body_y, out):
    axes = need_list(spec, "axes", 1, 6)
    for index, axis in enumerate(axes):
        if not isinstance(axis, str) or axis.strip() == "":
            raise DiagramError("axes[%d]: 空でない文字列が要ります" % index)
    items = need_list(spec, "items", 2, 4)
    for index, item in enumerate(items):
        if not isinstance(item, str) or item.strip() == "":
            raise DiagramError("items[%d]: 空でない文字列が要ります" % index)

    cells = spec.get("cells")
    if cells is None:
        raise DiagramError("cells: 必須フィールドが欠落しています")
    if not isinstance(cells, list) or len(cells) != len(items):
        actual = len(cells) if isinstance(cells, list) else -1
        raise DiagramError(
            "cells: 行数 %d が items の件数 %d と一致しません (全マスを埋めてください)"
            % (actual, len(items)))
    for row_index, row in enumerate(cells):
        if not isinstance(row, list) or len(row) != len(axes):
            actual = len(row) if isinstance(row, list) else -1
            raise DiagramError(
                "cells[%d]: 列数 %d が axes の件数 %d と一致しません (全マスを埋めてください)"
                % (row_index, actual, len(axes)))
        for col_index, value in enumerate(row):
            if not isinstance(value, str) or value.strip() == "":
                raise DiagramError(
                    "cells[%d][%d]: 空でない文字列が要ります" % (row_index, col_index))

    table_w = width - 2 * MARGIN
    col_w = max(2 * PAD + 2, ifloor((table_w - ifloor(table_w * 0.26)) / float(len(axes))))
    name_w = table_w - col_w * len(axes)
    if name_w < 2 * PAD + 2:
        name_w = 2 * PAD + 2
    name_inner = max(1, name_w - 2 * PAD)
    cell_inner = max(1, col_w - 2 * PAD)

    axis_lines = []
    for index, axis in enumerate(axes):
        axis_lines.append(
            fit(axis, FS_AXIS, cell_inner, MAX_LINES_CELL, "axes[%d]" % index))
    item_lines = []
    value_lines = []
    for index, item in enumerate(items):
        item_lines.append(
            fit(item, FS_LABEL, name_inner, MAX_LINES_CELL, "items[%d]" % index))
        row = []
        for col_index, value in enumerate(cells[index]):
            row.append(fit(value, FS_NOTE, cell_inner, MAX_LINES_CELL,
                           "cells[%d][%d]" % (index, col_index)))
        value_lines.append(row)

    label_lh = line_height(FS_LABEL)
    note_lh = line_height(FS_NOTE)
    axis_lh = line_height(FS_AXIS)

    head_h = PAD + max(len(item) for item in axis_lines) * axis_lh + PAD
    row_heights = []
    for index in range(len(items)):
        tallest = max(
            [len(item_lines[index]) * label_lh]
            + [len(cell) * note_lh for cell in value_lines[index]]
        )
        row_heights.append(PAD + tallest + PAD)

    y = body_y
    rect(out, 1, MARGIN, y, table_w, head_h, PRIMARY_SOFT, PRIMARY)
    for index in range(len(axes)):
        center = MARGIN + name_w + index * col_w + col_w // 2
        text_block(out, 1, axis_lines[index], center, y + PAD + ifloor(FS_AXIS),
                   FS_AXIS, INK, "middle", "600")
    y += head_h

    for index in range(len(items)):
        height = row_heights[index]
        rect(out, 1, MARGIN, y, table_w, height, SURFACE, RULE)
        text_block(out, 1, item_lines[index], MARGIN + PAD, y + PAD + FS_LABEL,
                   FS_LABEL, INK, "start", "600")
        for col_index in range(len(axes)):
            center = MARGIN + name_w + col_index * col_w + col_w // 2
            text_block(out, 1, value_lines[index][col_index], center,
                       y + PAD + ifloor(FS_NOTE), FS_NOTE, MUTED, "middle")
        for col_index in range(len(axes)):
            sep = MARGIN + name_w + col_index * col_w
            line(out, 1, sep, y, sep, y + height, RULE)
        y += height

    return y + MARGIN


# --------------------------------------------------------------------------
# パターン: hierarchy
# --------------------------------------------------------------------------

def _walk_hierarchy(nodes, depth, keypath):
    if depth > 3:
        raise DiagramError(
            "%s: 階層の深さ %d は許容範囲 2-3 の外です (root を第 1 層と数えます)"
            % (keypath, depth))
    for index, node in enumerate(nodes):
        where = "%s[%d]" % (keypath, index)
        if not isinstance(node, dict):
            raise DiagramError("%s: オブジェクトである必要があります" % where)
        need_text(node, "label", where + ".label")
        sub = node.get("children")
        if sub is None:
            continue
        if not isinstance(sub, list):
            raise DiagramError("%s.children: 配列である必要があります" % where)
        if len(sub) > 5:
            raise DiagramError(
                "%s.children: 件数 %d は許容範囲 1-5 の外です" % (where, len(sub)))
        if sub:
            _walk_hierarchy(sub, depth + 1, where + ".children")


def build_hierarchy(spec, width, body_y, out):
    root = need_dict(spec, "root")
    root_label = need_text(root, "label", "root.label")
    children = need_list(spec, "children", 1, 5)
    _walk_hierarchy(children, 2, "children")

    layers = [[{"label": root_label}]]
    parents = [[-1]]
    current = [(child, 0) for child in children]
    while current:
        layers.append([node for node, _ in current])
        parents.append([owner for _, owner in current])
        following = []
        for index, (node, _) in enumerate(current):
            for sub in (node.get("children") or []):
                following.append((sub, index))
        current = following

    avail = width - 2 * MARGIN
    label_lh = line_height(FS_LABEL)
    layer_gap = 32

    boxes = []
    y = body_y
    for depth, layer in enumerate(layers):
        count = len(layer)
        node_w = min(240, ifloor((avail - GAP * (count - 1)) / float(count)))
        node_w = max(node_w, 2 * PAD + 2)
        inner = max(1, node_w - 2 * PAD)
        lines = []
        for index, node in enumerate(layer):
            where = "root" if depth == 0 else "children (層 %d)[%d]" % (depth + 1, index)
            lines.append(fit(node["label"], FS_LABEL, inner, MAX_LINES_LABEL, where))
        layer_h = PAD + max(len(item) for item in lines) * label_lh + PAD
        total_w = count * node_w + GAP * (count - 1)
        start_x = MARGIN + ifloor((avail - total_w) / 2.0)
        row = []
        for index in range(count):
            x = start_x + index * (node_w + GAP)
            row.append((x, y, node_w, layer_h, lines[index]))
        boxes.append(row)
        y += layer_h + layer_gap

    for depth, row in enumerate(boxes):
        if depth == 0:
            continue
        for index, box in enumerate(row):
            owner = parents[depth][index]
            px, py, pw, ph, _ = boxes[depth - 1][owner]
            parent_x = px + pw // 2
            parent_y = py + ph
            child_x = box[0] + box[2] // 2
            child_y = box[1]
            mid = (parent_y + child_y) // 2
            path(out, 1, "M %d %d L %d %d L %d %d L %d %d"
                 % (parent_x, parent_y, parent_x, mid, child_x, mid, child_x, child_y),
                 fill="none", stroke=RULE)

    for depth, row in enumerate(boxes):
        fill = PRIMARY_SOFT if depth == 0 else SURFACE
        stroke = PRIMARY if depth == 0 else RULE
        for box in row:
            x, top, node_w, layer_h, lines = box
            rect(out, 1, x, top, node_w, layer_h, fill, stroke)
            text_block(out, 1, lines, x + node_w // 2, top + PAD + FS_LABEL,
                       FS_LABEL, INK, "middle", "600" if depth == 0 else None)

    last = boxes[-1][0]
    return last[1] + last[3] + MARGIN


# --------------------------------------------------------------------------
# パターン: cycle
# --------------------------------------------------------------------------

def build_cycle(spec, width, body_y, out):
    steps = need_list(spec, "steps", 3, 6)
    count = len(steps)
    avail = width - 2 * MARGIN
    node_w = min(190, ifloor((avail - 2 * GAP) / 3.0))
    node_w = max(node_w, 2 * PAD + 2)
    inner = max(1, node_w - 2 * PAD)

    label_lines = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise DiagramError("steps[%d]: オブジェクトである必要があります" % index)
        where = "steps[%d] (%s)" % (index, node_key(step, "steps[%d]" % index))
        label = need_text(step, "label", where + ".label")
        label_lines.append(fit(label, FS_LABEL, inner, MAX_LINES_LABEL, where + ".label"))

    label_lh = line_height(FS_LABEL)
    node_h = PAD + max(len(item) for item in label_lines) * label_lh + PAD

    radius = ifloor((width - node_w - 2 * MARGIN) / 2.0)
    radius = max(70, min(170, radius))
    center_x = width // 2
    center_y = body_y + radius + node_h // 2

    step_deg = round(360.0 / count, 3)
    inset = round(step_deg * 0.34, 3)

    def point(angle_deg, distance):
        rad = math.radians(angle_deg)
        return (center_x + distance * math.cos(rad),
                center_y + distance * math.sin(rad))

    for index in range(count):
        begin = round(-90.0 + step_deg * index + inset, 3)
        finish = round(-90.0 + step_deg * (index + 1) - inset, 3)
        sx, sy = point(begin, radius)
        ex, ey = point(finish, radius)
        path(out, 1, "M %d %d A %d %d 0 0 1 %d %d"
             % (ifloor(sx), ifloor(sy), radius, radius, ifloor(ex), ifloor(ey)),
             fill="none", stroke=PRIMARY)
        rad = math.radians(finish)
        arrow_head(out, 1, ex, ey, -math.sin(rad), math.cos(rad), PRIMARY)

    for index in range(count):
        angle = round(-90.0 + step_deg * index, 3)
        nx, ny = point(angle, radius)
        x = ifloor(nx) - node_w // 2
        y = ifloor(ny) - node_h // 2
        rect(out, 1, x, y, node_w, node_h, PRIMARY_SOFT, PRIMARY)
        text_block(out, 1, label_lines[index], x + node_w // 2,
                   y + PAD + FS_LABEL, FS_LABEL, INK, "middle", "600")

    return body_y + 2 * radius + node_h + MARGIN


# --------------------------------------------------------------------------
# パターン: matrix
# --------------------------------------------------------------------------

def build_matrix(spec, width, body_y, out):
    axis_text = {}
    for axis_key in ("x_axis", "y_axis"):
        axis = need_dict(spec, axis_key)
        for edge in ("low", "high"):
            axis_text[(axis_key, edge)] = need_text(
                axis, edge, "%s.%s" % (axis_key, edge))

    items = need_list(spec, "items", 1, 8)
    prepared = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise DiagramError("items[%d]: オブジェクトである必要があります" % index)
        key = node_key(item, "items[%d]" % index)
        where = "items[%d] (%s)" % (index, key)
        label = need_text(item, "label", where + ".label")
        coords = {}
        for axis in ("x", "y"):
            value = item.get(axis)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DiagramError(
                    "%s.%s: 0.0-1.0 の実数が要ります (値=%r)" % (where, axis, value))
            if not (0.0 <= float(value) <= 1.0):
                raise DiagramError(
                    "%s.%s: 値 %s は 0.0-1.0 の範囲外です (クリップせず差し戻します)"
                    % (where, axis, value))
            coords[axis] = float(value)
        prepared.append((label, coords["x"], coords["y"], where))

    gutter = 64
    plot_x = MARGIN + gutter
    plot_w = max(40, width - 2 * MARGIN - gutter)
    plot_h = max(40, ifloor(plot_w * 0.58))
    plot_y = body_y + 8
    half_w = plot_w // 2
    half_h = plot_h // 2

    rect(out, 1, plot_x, plot_y, half_w, half_h, SURFACE, RULE, 0)
    rect(out, 1, plot_x + half_w, plot_y, plot_w - half_w, half_h,
         PRIMARY_SOFT, RULE, 0)
    rect(out, 1, plot_x, plot_y + half_h, half_w, plot_h - half_h,
         SURFACE, RULE, 0)
    rect(out, 1, plot_x + half_w, plot_y + half_h, plot_w - half_w,
         plot_h - half_h, ACCENT_SOFT, RULE, 0)

    line(out, 1, plot_x + half_w, plot_y, plot_x + half_w, plot_y + plot_h, RULE, "2")
    line(out, 1, plot_x, plot_y + half_h, plot_x + plot_w, plot_y + half_h, RULE, "2")

    axis_inner = max(1, gutter - 8)
    side_inner = max(1, plot_w // 3)
    high_y = fit(axis_text[("y_axis", "high")], FS_AXIS, axis_inner,
                 MAX_LINES_NOTE, "y_axis.high")
    low_y = fit(axis_text[("y_axis", "low")], FS_AXIS, axis_inner,
                MAX_LINES_NOTE, "y_axis.low")
    low_x = fit(axis_text[("x_axis", "low")], FS_AXIS, side_inner,
                MAX_LINES_NOTE, "x_axis.low")
    high_x = fit(axis_text[("x_axis", "high")], FS_AXIS, side_inner,
                 MAX_LINES_NOTE, "x_axis.high")

    text_block(out, 1, high_y, MARGIN, plot_y + ifloor(FS_AXIS), FS_AXIS, MUTED, "start")
    text_block(out, 1, low_y, MARGIN, plot_y + plot_h, FS_AXIS, MUTED, "start")
    text_block(out, 1, low_x, plot_x, plot_y + plot_h + 22, FS_AXIS, MUTED, "start")
    text_block(out, 1, high_x, plot_x + plot_w, plot_y + plot_h + 22,
               FS_AXIS, MUTED, "end")

    for label, px, py, where in prepared:
        cx = plot_x + ifloor(px * plot_w)
        cy = plot_y + plot_h - ifloor(py * plot_h)
        circle(out, 1, cx, cy, 7, PRIMARY, SURFACE)
        lines = fit(label, FS_NOTE, side_inner, MAX_LINES_NOTE, where + ".label")
        text_block(out, 1, lines, cx, cy + 22, FS_NOTE, INK, "middle")

    return plot_y + plot_h + 44


# --------------------------------------------------------------------------
# パターン: versus
# --------------------------------------------------------------------------

def build_versus(spec, width, body_y, out):
    col_w = ifloor((width - 2 * MARGIN - GAP) / 2.0)
    col_w = max(col_w, 2 * PAD + 2)
    inner = max(1, col_w - 2 * PAD)
    bullet_inner = max(1, inner - 18)

    label_lh = line_height(FS_LABEL)
    note_lh = line_height(FS_NOTE)

    columns = []
    for side in ("left", "right"):
        block = need_dict(spec, side)
        label = need_text(block, "label", "%s.label" % side)
        head = fit(label, FS_LABEL, inner, MAX_LINES_LABEL, "%s.label" % side)
        bullets = block.get("bullets")
        if bullets is None:
            raise DiagramError("%s.bullets: 必須フィールドが欠落しています" % side)
        if not isinstance(bullets, list):
            raise DiagramError("%s.bullets: 配列である必要があります" % side)
        if not (1 <= len(bullets) <= 5):
            raise DiagramError(
                "%s.bullets: 件数 %d は許容範囲 1-5 の外です" % (side, len(bullets)))
        rendered = []
        for index, bullet in enumerate(bullets):
            where = "%s.bullets[%d]" % (side, index)
            if not isinstance(bullet, str) or bullet.strip() == "":
                raise DiagramError("%s: 空でない文字列が要ります" % where)
            rendered.append(fit(bullet, FS_NOTE, bullet_inner, MAX_LINES_BULLET, where))
        height = PAD + len(head) * label_lh + 10
        for item in rendered:
            height += len(item) * note_lh + 8
        height += PAD
        columns.append((head, rendered, height))

    col_h = max(columns[0][2], columns[1][2])

    for index, (head, rendered, _) in enumerate(columns):
        x = MARGIN + index * (col_w + GAP)
        fill = PRIMARY_SOFT if index == 0 else ACCENT_SOFT
        stroke = PRIMARY if index == 0 else ACCENT
        rect(out, 1, x, body_y, col_w, col_h, fill, stroke)
        text_block(out, 1, head, x + col_w // 2, body_y + PAD + FS_LABEL,
                   FS_LABEL, INK, "middle", "600")
        y = body_y + PAD + len(head) * label_lh + 10
        for item in rendered:
            circle(out, 1, x + PAD + 4, y + 5, 3, stroke, None, True)
            text_block(out, 1, item, x + PAD + 18, y + ifloor(FS_NOTE),
                       FS_NOTE, INK, "start")
            y += len(item) * note_lh + 8

    divider = MARGIN + col_w + GAP // 2
    line(out, 1, divider, body_y, divider, body_y + col_h, RULE, "2")

    return body_y + col_h + MARGIN


BUILDERS = OrderedDict((
    ("flow", build_flow),
    ("compare", build_compare),
    ("hierarchy", build_hierarchy),
    ("cycle", build_cycle),
    ("matrix", build_matrix),
    ("versus", build_versus),
))


# --------------------------------------------------------------------------
# module API (C11 が import 経由で呼ぶ)
# --------------------------------------------------------------------------

def render_diagram(spec, pattern, width=DEFAULT_WIDTH):
    """図解 1 個分の宣言 JSON から inline SVG 断片 (末尾改行 1 個) を返す。"""
    if not isinstance(spec, dict):
        raise DiagramError("--diagram: オブジェクト (JSON object) が要ります", 2)
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        raise DiagramError("--width: 正整数が要ります (受領=%r)" % (width,), 2)

    if pattern not in PATTERNS:
        raise DiagramError(
            "--pattern が未知の語です: %r / 受理する 6 語: %s"
            % (pattern, " ".join(PATTERNS)))

    declared = spec.get("pattern")
    if declared is not None and declared != pattern:
        raise DiagramError(
            "pattern の取り違え: --pattern=%s / diagram.pattern=%s "
            "(どちらかを直してください)" % (pattern, declared))

    title = need_text(spec, "title", "title")

    raw_key = spec.get("id")
    if isinstance(raw_key, str) and raw_key.strip():
        base = ID_SAFE.sub("-", raw_key.strip())
    else:
        base = pattern
    if not base:
        base = pattern

    out = Out()

    title_inner = max(1, width - 2 * MARGIN)
    title_lines = fit(title, FS_TITLE, title_inner, MAX_LINES_TITLE, "title")
    text_block(out, 1, title_lines, MARGIN, MARGIN + FS_TITLE,
               FS_TITLE, INK, "start", "700")
    body_y = MARGIN + len(title_lines) * line_height(FS_TITLE) + 16

    height = BUILDERS[pattern](spec, width, body_y, out)
    height = max(int(height), body_y)

    parts = ['<svg id="hbdg-%s-1" role="img" viewBox="0 0 %d %d">'
             % (esc(base), int(width), int(height))]
    parts.append("  <title>%s</title>" % esc(title))
    description = spec.get("description")
    if isinstance(description, str) and description.strip():
        parts.append("  <desc>%s</desc>" % esc(description))
    parts.extend(out.lines)
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="render-diagram-svg.py",
        description="構造データから概念図解の inline SVG 断片を決定論生成する",
    )
    parser.add_argument("--diagram", required=True,
                        help="図解 1 個分の宣言 JSON のパス")
    parser.add_argument("--pattern", required=True,
                        help="flow | compare | hierarchy | cycle | matrix | versus")
    parser.add_argument("--width", default=str(DEFAULT_WIDTH),
                        help="SVG の viewBox 幅 (正整数・既定 %d)" % DEFAULT_WIDTH)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    raw_width = str(args.width)
    if not re.match(r"^[0-9]+$", raw_width) or int(raw_width) <= 0:
        sys.stderr.write("--width は正整数のみ受け付けます: %s\n" % raw_width)
        return 2
    width = int(raw_width)

    try:
        with open(args.diagram, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as exc:
        sys.stderr.write("--diagram を読めません: %s\n" % exc)
        return 2

    try:
        spec = json.loads(raw, object_pairs_hook=OrderedDict)
    except ValueError as exc:
        sys.stderr.write("--diagram の JSON 構文エラー: %s\n" % exc)
        return 2

    if not isinstance(spec, dict):
        sys.stderr.write("--diagram: JSON object が要ります (受領=%s)\n"
                         % type(spec).__name__)
        return 2

    try:
        svg = render_diagram(spec, args.pattern, width)
    except DiagramError as exc:
        sys.stderr.write("%s\n" % exc)
        return exc.code

    sys.stdout.buffer.write(svg.encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

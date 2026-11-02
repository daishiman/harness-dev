#!/usr/bin/env python3
# /// script
# name: verify-handout-narrative
# version: 0.1.0
# purpose: C22 資料の筋道 (目的・背景・ゴールの充足、セクションゴールの常時表示、提示順の型) を検査する fail-closed ゲート。検出定義の正本はブリーフ側に持つ
# inputs:
#   - argv: --html <path> --config <path> [--json-report <path>]
# outputs:
#   - stdout: 違反一覧 (NAR-01..NAR-10)
#   - file: --json-report の検査結果
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out / --json-report / --config-out で明示された path のみ
# ///
# -*- coding: utf-8 -*-
"""C22 verify-handout-narrative.py — 資料の筋道 (R19) を検査する fail-closed ゲート。

正本は plugin-plans/guide-doc-generator/briefs/script-brief-C22.json。
検出は同ブリーフの detections 配列 (NAR-01..NAR-10) が唯一の正本で、
本 script は件数も閾値も語彙も自前に持たず、次の同梱データから read-only で引く。

  - schemas/handout-config.schema.json  … detail_level / evidence_depth /
      presentation_order / role の値域、単一行フィールドの最大長
  - config/handout-parts.json           … data-hb-part の部品語彙と section_scope
  - config/handout-sections.json        … section_kind の語彙と required_role
  - assets/tokens/<theme>.json          … text_limits.section_body_chars_by_detail_level

いずれかが読めない場合は検査を成立させず exit 2 (fail-closed)。

R11 (lead-line / 判断軸 / 用語の言い換え) と R18 (日付) は C18 の担当であり、
本 script は判定しない。両者は別の検証面で、一方が他方を代替しない。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent

SCHEMA_PATH = PLUGIN_ROOT / "schemas" / "handout-config.schema.json"
PARTS_PATH = PLUGIN_ROOT / "config" / "handout-parts.json"
SECTIONS_PATH = PLUGIN_ROOT / "config" / "handout-sections.json"
VISUAL_POLICY_PATH = PLUGIN_ROOT / "config" / "handout-visual-policy.json"
TOKENS_DIR = PLUGIN_ROOT / "assets" / "tokens"

# テーマトークンが持つ水準別上限のキー。値 (数値) は本 script に持たない。
# 節あたりの文章量予算 (min/max)。1 ブロックの上限 (block_body_max_chars_by_detail_level)
# とは単位が違う — NAR-09 が測るのは「節にどれだけ載っているか」であり、
# 単位の違う block 上限と節の実測平均を比べていた旧実装では両端の水準しか発火しなかった。
BY_DETAIL_KEY = "section_body_chars_by_detail_level"

NORMALIZED_BY = "validate-handout-config.py"

# HTML 側の検査アンカー。語彙の正本は C11 の html_attribute_contract。
FIELD_PURPOSE = "purpose"
FIELD_BACKGROUND = "background"
FIELD_GOAL = "goal"
FIELD_SECTION_GOAL = "section_goal"
FIELD_LEAD_LINE = "lead_line"

# 部品 id の literal は本 script に持たない (P03 Y-05 / AC-C11-19)。
# 検査アンカーになる部品は config/handout-parts.json の述語で実行時に引く。
#   hero        = section_scope=document の骨格部品 (カタログ順の 2 件目。C11
#                 render-handout.py の document_part_ids() と同じ規約)
#   handson/IMG = data_block_type から引く
SECTION_SCOPE_DOCUMENT = "document"
SECTION_SCOPE_IN_SECTION = "in-section"
BLOCK_HANDSON = "handson"
BLOCK_IMAGE = "image"

REQUIRED_CONFIG_KEYS = ("purpose", "background", "goal", "sections", "presentation_order")

VOID_TAGS = frozenset(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]
)

OUT_OF_SCOPE_NOTES = (
    "セクションゴールが全体ゴールに資するかの意味的妥当性は判定していない (C06 の責務)",
    "R11 (lead-line / 判断軸 / 用語の言い換え) と R18 (日付) は本ゲートの担当外で C18 が判定する",
    "NAR-04 の常時表示判定は CSS カスケードを解決しない近似であり、祖先条件付きの非表示"
    "・詳細度による打ち消しは検出できない (メディアクエリ内の規則は対象外)",
    "外部参照・空画像などの自己完結性 (C16) と印刷面 (C17) は本ゲートの担当外",
)


class GateError(Exception):
    """検査が成立しない (exit 2)。"""


# --------------------------------------------------------------------------
# テキスト正規化
# --------------------------------------------------------------------------

_WS_RE = re.compile(r"[\s　]+")


def normalize_text(value):
    """NFKC → 連続空白の圧縮 → 前後トリム。これ以上の変形は行わない。"""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return _WS_RE.sub(" ", text).strip()


# --------------------------------------------------------------------------
# HTML 収集器
# --------------------------------------------------------------------------


class Node(object):
    __slots__ = ("tag", "attrs", "line", "col", "parent", "seq", "content", "children")

    def __init__(self, tag, attrs, line, col, parent, seq):
        self.tag = tag
        self.attrs = attrs
        self.line = line
        self.col = col
        self.parent = parent
        self.seq = seq
        self.content = []
        self.children = []

    # -- 属性 --------------------------------------------------------------

    def attr(self, name):
        return self.attrs.get(name)

    def has_attr(self, name):
        return name in self.attrs

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def position(self):
        return "%d:%d" % (self.line, self.col)

    # -- 親子 --------------------------------------------------------------

    def ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def descendants(self):
        for child in self.children:
            yield child
            for sub in child.descendants():
                yield sub

    def text_fragments(self):
        if self.tag in ("script", "style", "template"):
            return []
        out = []
        for item in self.content:
            if isinstance(item, str):
                piece = normalize_text(item)
                if piece:
                    out.append(piece)
            else:
                out.extend(item.text_fragments())
        return out

    def text(self):
        return normalize_text(" ".join(self.text_fragments()))

    def text_length(self):
        return sum(len(piece) for piece in self.text_fragments())


class Collector(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = Node("#document", {}, 0, 0, None, 0)
        self.stack = [self.root]
        self.nodes = []
        self.style_text = []
        self._seq = 0

    def _make(self, tag, attrs):
        self._seq += 1
        line, col = self.getpos()
        parent = self.stack[-1]
        node = Node(
            tag,
            dict((k, v if v is not None else "") for k, v in attrs),
            line,
            col,
            parent,
            self._seq,
        )
        parent.content.append(node)
        parent.children.append(node)
        self.nodes.append(node)
        return node

    def handle_starttag(self, tag, attrs):
        node = self._make(tag, attrs)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self._make(tag, attrs)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        current = self.stack[-1]
        if current.tag == "style":
            self.style_text.append(data)
        current.content.append(data)


def parse_html(text):
    collector = Collector()
    collector.feed(text)
    collector.close()
    return collector


# --------------------------------------------------------------------------
# 同梱データ (閾値・語彙の正本) の読み込み
# --------------------------------------------------------------------------


def _load_json(path, label):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise GateError("%s を読めない: %s (%s)" % (label, path, exc.__class__.__name__))
    except UnicodeDecodeError:
        raise GateError("%s をデコードできない: %s" % (label, path))
    except ValueError:
        raise GateError("%s が JSON として不正: %s" % (label, path))


def _collect_single_line_max(schema):
    """x_single_line なフィールドの maxLength 最大値 (『1 行の抽象』の上限)。"""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("x_single_line") is True and isinstance(node.get("maxLength"), int):
                found.append(node["maxLength"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    if not found:
        raise GateError(
            "schemas/handout-config.schema.json に x_single_line フィールドの maxLength が無い"
        )
    return max(found)


def _enum_at(schema, key):
    props = (schema.get("properties") or {}).get(key) or {}
    values = props.get("enum")
    if not isinstance(values, list) or not values:
        raise GateError("schemas/handout-config.schema.json に %s の enum が無い" % key)
    return [str(v) for v in values]


def _section_enum(schema, key):
    section = ((schema.get("$defs") or {}).get("section") or {}).get("properties") or {}
    values = (section.get(key) or {}).get("enum")
    if not isinstance(values, list) or not values:
        raise GateError("schemas/handout-config.schema.json に section.%s の enum が無い" % key)
    return [str(v) for v in values]


def load_resources(config):
    """閾値と語彙を同梱データから引く。1 つでも欠ければ fail-closed。"""
    schema = _load_json(SCHEMA_PATH, "schemas/handout-config.schema.json")
    parts_doc = _load_json(PARTS_PATH, "config/handout-parts.json")
    sections_doc = _load_json(SECTIONS_PATH, "config/handout-sections.json")

    parts = parts_doc.get("parts")
    if not isinstance(parts, list) or not parts:
        raise GateError("config/handout-parts.json に parts が無い")
    in_section_parts = set()
    document_parts = []
    part_by_block = {}
    for part in parts:
        if not isinstance(part, dict) or not part.get("id"):
            raise GateError("config/handout-parts.json の parts[] が不正")
        if part.get("section_scope") == SECTION_SCOPE_IN_SECTION:
            in_section_parts.add(str(part["id"]))
        if part.get("section_scope") == SECTION_SCOPE_DOCUMENT:
            document_parts.append(str(part["id"]))
        block_type = part.get("data_block_type")
        if isinstance(block_type, str) and block_type:
            if block_type in part_by_block:
                raise GateError(
                    "config/handout-parts.json の data_block_type が一意でない: %s"
                    % block_type)
            part_by_block[block_type] = str(part["id"])
    if not in_section_parts:
        raise GateError("config/handout-parts.json に in-section の部品が無い")
    if len(document_parts) != 2:
        raise GateError(
            "config/handout-parts.json の骨格部品 (section_scope=%s) が"
            "ちょうど 2 件でない: %r" % (SECTION_SCOPE_DOCUMENT, document_parts))
    hero_part = document_parts[1]
    for block_type in (BLOCK_HANDSON, BLOCK_IMAGE):
        if block_type not in part_by_block:
            raise GateError(
                "config/handout-parts.json に block.type=%s の部品が無い" % block_type)

    kinds = sections_doc.get("section_kinds")
    if not isinstance(kinds, list) or not kinds:
        raise GateError("config/handout-sections.json に section_kinds が無い")
    required_role_by_kind = {}
    for kind in kinds:
        if not isinstance(kind, dict) or not kind.get("slug"):
            raise GateError("config/handout-sections.json の section_kinds[] が不正")
        if kind.get("required_role"):
            required_role_by_kind[str(kind["slug"])] = str(kind["required_role"])

    detail_levels = _enum_at(schema, "detail_level")
    evidence_depths = _enum_at(schema, "evidence_depth")
    presentation_orders = _enum_at(schema, "presentation_order")
    roles = _section_enum(schema, "role")
    single_line_max = _collect_single_line_max(schema)

    limits = _load_detail_limits(config, detail_levels)

    return {
        "in_section_parts": in_section_parts,
        "hero_part": hero_part,
        "handson_part": part_by_block[BLOCK_HANDSON],
        "image_part": part_by_block[BLOCK_IMAGE],
        "required_role_by_kind": required_role_by_kind,
        "detail_levels": detail_levels,
        "evidence_depths": evidence_depths,
        "presentation_orders": presentation_orders,
        "roles": roles,
        "single_line_max": single_line_max,
        "detail_limits": limits,
    }


def _load_detail_limits(config, detail_levels):
    """水準別の節あたり文章量予算 (min/max) をテーマトークンから引く。

    本 script は数値を持たない。水準の境界値はテーマトークンが正本で、
    「どれだけ書くか」を調整したい利用者はここだけを触れば全水準へ効く。
    """
    if not TOKENS_DIR.is_dir():
        raise GateError("テーマトークンのディレクトリが無い: %s" % TOKENS_DIR)
    candidates = []
    theme = config.get("theme") if isinstance(config, dict) else None
    if isinstance(theme, str) and theme:
        themed = TOKENS_DIR / ("%s.json" % theme)
        if themed.is_file():
            candidates.append(themed)
    for path in sorted(TOKENS_DIR.glob("*.json")):
        if path not in candidates:
            candidates.append(path)
    for path in candidates:
        data = _load_json(path, "assets/tokens/%s" % path.name)
        limits = (data.get("text_limits") or {}).get(BY_DETAIL_KEY)
        if isinstance(limits, dict) and all(
            isinstance(limits.get(level), dict)
            and isinstance(limits[level].get("min"), int)
            and isinstance(limits[level].get("max"), int)
            for level in detail_levels
        ):
            return dict(
                (level, {"min": limits[level]["min"], "max": limits[level]["max"]})
                for level in detail_levels
            )
    raise GateError(
        "テーマトークンに text_limits.%s が無い (水準の境界値を script に持たない)" % BY_DETAIL_KEY
    )


# --------------------------------------------------------------------------
# CSS の粗いトークナイザ (NAR-04 (e))
# --------------------------------------------------------------------------

_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_HIDING_RE = re.compile(r"(display\s*:\s*none|visibility\s*:\s*hidden)", re.I)


def _strip_at_rule_blocks(css):
    """@media 等の at-rule ブロックを丸ごと除去する (印刷時の非表示は正当な指定)。"""
    out = []
    index = 0
    length = len(css)
    while index < length:
        char = css[index]
        if char != "@":
            out.append(char)
            index += 1
            continue
        brace = css.find("{", index)
        semi = css.find(";", index)
        if brace == -1 or (semi != -1 and semi < brace):
            index = (semi + 1) if semi != -1 else length
            continue
        depth = 0
        cursor = brace
        while cursor < length:
            if css[cursor] == "{":
                depth += 1
            elif css[cursor] == "}":
                depth -= 1
                if depth == 0:
                    cursor += 1
                    break
            cursor += 1
        index = cursor
    return "".join(out)


def hiding_selectors(style_text):
    """display:none / visibility:hidden を宣言する (メディアクエリ外の) セレクタ集合。"""
    css = _CSS_COMMENT_RE.sub("", style_text)
    css = _strip_at_rule_blocks(css)
    selectors = set()
    for chunk in css.split("}"):
        if "{" not in chunk:
            continue
        selector_part, declarations = chunk.split("{", 1)
        if not _HIDING_RE.search(declarations):
            continue
        for selector in selector_part.split(","):
            token = re.sub(r"\s+", "", selector)
            if token:
                selectors.add(_normalize_attr_selector(token))
    return selectors


def _normalize_attr_selector(token):
    return re.sub(r"\[([^\]=]+)=(?:\"|')?([^\]\"']*)(?:\"|')?\]", r'[\1="\2"]', token)


def element_selector_keys(node):
    keys = set([node.tag])
    for cls in node.classes():
        keys.add("." + cls)
    if node.attr("id"):
        keys.add("#" + node.attr("id"))
    for name, value in node.attrs.items():
        keys.add("[%s]" % name)
        keys.add('[%s="%s"]' % (name, value))
    return keys


# --------------------------------------------------------------------------
# 違反レコード
# --------------------------------------------------------------------------


class Violation(object):
    __slots__ = ("detection", "location", "value", "reason")

    def __init__(self, detection, location, value, reason):
        self.detection = detection
        self.location = location
        self.value = _one_line(value)
        self.reason = _one_line(reason)

    def row(self):
        return "FAIL\t%s\t%s\t%s\t%s" % (self.detection, self.location, self.value, self.reason)

    def as_dict(self):
        return {
            "detection": self.detection,
            "location": self.location,
            "value": self.value,
            "reason": self.reason,
        }


def _one_line(value):
    return re.sub(r"[\t\r\n]+", " ", "" if value is None else str(value))


class Result(object):
    __slots__ = ("detection", "status", "checked", "violations", "extra")

    def __init__(self, detection, status, checked, violations, extra=None):
        self.detection = detection
        self.status = status
        self.checked = checked
        self.violations = violations
        self.extra = extra or {}

    def line(self):
        if self.status == "SKIP":
            tail = " ".join("%s=%s" % (k, v) for k, v in sorted(self.extra.items()))
            return ("%s SKIP %s" % (self.detection, tail)).rstrip()
        return "%s %s checked=%d violations=%d" % (
            self.detection,
            self.status,
            self.checked,
            len(self.violations),
        )


def make_result(detection, checked, violations, skip_reason=None):
    if skip_reason is not None:
        return Result(detection, "SKIP", 0, [], skip_reason)
    status = "FAIL" if violations else "PASS"
    return Result(detection, status, checked, violations)


# --------------------------------------------------------------------------
# 構成データの検証 (exit 2 の面)
# --------------------------------------------------------------------------


def load_config(path):
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise GateError("--config が存在しない: %s" % path)
    except OSError as exc:
        raise GateError("--config を読めない: %s (%s)" % (path, exc.__class__.__name__))
    except UnicodeDecodeError:
        raise GateError("--config をデコードできない: %s" % path)
    try:
        config = json.loads(raw)
    except ValueError:
        raise GateError("--config が JSON として不正: %s" % path)
    if not isinstance(config, dict):
        raise GateError("--config が object でない: %s" % path)

    provenance = config.get("provenance")
    if not isinstance(provenance, dict):
        raise GateError("--config が正規化済みでない (provenance が無い): %s" % path)
    if provenance.get("normalized_by") != NORMALIZED_BY:
        raise GateError(
            "--config が %s で正規化されていない (provenance.normalized_by=%r)"
            % (NORMALIZED_BY, provenance.get("normalized_by"))
        )
    for key in REQUIRED_CONFIG_KEYS:
        if key not in config:
            raise GateError("--config に必須フィールド %s が無い" % key)
        if config[key] is None:
            # 正規化済み構成データに null は無い (C12 が値を埋めるか落とすかを決める)。
            # null を「未宣言」として検査を飛ばすと、値を消すだけでゲートを
            # 無効化できてしまう — キー削除と同じ入力契約違反として扱う。
            raise GateError(
                "--config の必須フィールド %s が null (正規化済み構成データでは"
                "起こらない。キーの削除と同じ入力契約違反として扱う)" % key)
    sections = config.get("sections")
    if not isinstance(sections, list) or not sections:
        raise GateError("--config の sections が 0 件 (R19 の対象として成立しない)")
    for section in sections:
        if not isinstance(section, dict) or not section.get("id"):
            raise GateError("--config の sections[] に id を持たない要素がある")
    return config


def load_html(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise GateError("--html が存在しない: %s" % path)
    except OSError as exc:
        raise GateError("--html を読めない: %s (%s)" % (path, exc.__class__.__name__))
    except UnicodeDecodeError:
        raise GateError("--html をデコードできない (utf-8 として不正): %s" % path)


# --------------------------------------------------------------------------
# 文書モデル
# --------------------------------------------------------------------------


class Document(object):
    def __init__(self, collector, config, res):
        self.collector = collector
        self.config = config
        self.res = res
        self.nodes = collector.nodes
        self.style_text = "".join(collector.style_text)
        self.hiding_selectors = hiding_selectors(self.style_text)

        self.hero = None
        hero_part = res["hero_part"]
        for node in self.nodes:
            if node.attr("data-hb-part") == hero_part:
                self.hero = node
                break

        self.html_sections = [
            node for node in self.nodes if node.tag == "section" and node.attr("id")
        ]
        self.section_by_id = {}
        for node in self.html_sections:
            self.section_by_id.setdefault(node.attr("id"), node)
        self.first_section_seq = self.html_sections[0].seq if self.html_sections else None

        self.cfg_sections = config["sections"]
        self.cfg_ids = [str(section["id"]) for section in self.cfg_sections]
        self.cfg_by_id = dict((str(s["id"]), s) for s in self.cfg_sections)

        self.root_element = None
        for node in self.nodes:
            if node.tag == "html":
                self.root_element = node
                break

        self.nav = None
        for node in self.nodes:
            if node.tag == "nav" or "navbar" in node.classes():
                self.nav = node
                break
        self.nav_anchors = []
        if self.nav is not None:
            for node in self.nav.descendants():
                href = node.attr("href")
                if node.tag == "a" and href and href.startswith("#"):
                    self.nav_anchors.append(node)

    # -- 補助 --------------------------------------------------------------

    def fields(self, name):
        return [node for node in self.nodes if node.attr("data-hb-field") == name]

    def section_of(self, node):
        for ancestor in node.ancestors():
            if ancestor.tag == "section" and ancestor.attr("id"):
                return ancestor
        return None

    def is_part(self, node):
        return node.attr("data-hb-part") in self.res["in_section_parts"]

    def config_role(self, section_id):
        section = self.cfg_by_id.get(section_id)
        if section is None:
            return None
        return section.get("role")

    def main_section_nodes(self):
        return [
            node
            for node in self.html_sections
            if self.config_role(node.attr("id")) == "main"
        ]


# --------------------------------------------------------------------------
# NAR-01 / NAR-02
# --------------------------------------------------------------------------

_HERO_FIELD_ORDER_CACHE = None
# 冒頭に必ず在ることを求める 3 要素。順序は持たない (順序は正本の側にある)。
HERO_REQUIRED_FIELDS = frozenset((FIELD_PURPOSE, FIELD_BACKGROUND, FIELD_GOAL))


def hero_field_order():
    """冒頭 3 要素の文書順を正本から引く (fail-closed)。

    順序を本 script の定数で持たない。持つと、描画する C11 と順序を検査する
    本 script が別々の順序を持つ二名簿になり、正本を書き換えても片方だけが
    動く。正本は config/handout-visual-policy.json#opening.hero_card_fields.order。

    正本が読めないときに既定順へ落とさないのは、既定順が『何かの順に並んで
    いる』ことだけを担保して『正本どおりに並んでいる』ことを担保しないため。
    黙って旧順序を通す方が事故になる (利用者要求 R3 はゴール先頭)。
    """
    global _HERO_FIELD_ORDER_CACHE
    if _HERO_FIELD_ORDER_CACHE is not None:
        return _HERO_FIELD_ORDER_CACHE
    policy = _load_json(VISUAL_POLICY_PATH, "config/handout-visual-policy.json")
    order = (((policy.get("opening") or {}).get("hero_card_fields") or {})
             .get("order"))
    if not isinstance(order, list) or not order:
        raise GateError(
            "config/handout-visual-policy.json に "
            "opening.hero_card_fields.order が無い (冒頭の並び順の単一正本)")
    names = tuple(name for name in order if isinstance(name, str) and name)
    missing = HERO_REQUIRED_FIELDS - set(names)
    if missing:
        raise GateError(
            "opening.hero_card_fields.order に冒頭 3 要素が揃っていない (欠落: %s)"
            % ", ".join(sorted(missing)))
    _HERO_FIELD_ORDER_CACHE = names
    return names


def check_nar01(doc):
    violations = []
    seen = {}
    order = hero_field_order()
    for name in order:
        elements = doc.fields(name)
        if not elements:
            violations.append(
                Violation(
                    "NAR-01",
                    "-",
                    'data-hb-field="%s"' % name,
                    "冒頭 3 要素のうち %s が描画されていない" % name,
                )
            )
            continue
        if len(elements) > 1:
            violations.append(
                Violation(
                    "NAR-01",
                    elements[1].position(),
                    'data-hb-field="%s" x%d' % (name, len(elements)),
                    "%s はちょうど 1 個であること (%d 個ある)" % (name, len(elements)),
                )
            )
            continue
        node = elements[0]
        seen[name] = node
        if not node.text():
            violations.append(
                Violation(
                    "NAR-01",
                    node.position(),
                    'data-hb-field="%s"' % name,
                    "%s のテキストが空" % name,
                )
            )
            continue
        if not _is_in_hero_region(doc, node):
            violations.append(
                Violation(
                    "NAR-01",
                    node.position(),
                    'data-hb-field="%s"' % name,
                    "%s が冒頭 (hero または最初の section より前) に無い" % name,
                )
            )
    ordered = [seen[name].seq for name in order if name in seen]
    if len(ordered) > 1 and ordered != sorted(ordered):
        violations.append(
            Violation(
                "NAR-01",
                "-",
                " → ".join(name for name in order if name in seen),
                "文書順は %s であること (正本: config/handout-visual-policy.json"
                "#opening.hero_card_fields.order)" % " → ".join(order),
            )
        )
    return make_result("NAR-01", len(order), violations)


def _is_in_hero_region(doc, node):
    if doc.first_section_seq is not None and node.seq > doc.first_section_seq:
        return False
    if doc.hero is not None and node.seq < doc.hero.seq:
        return False
    return True


def check_nar02(doc):
    violations = []
    checked = 0
    for name in hero_field_order():
        elements = doc.fields(name)
        if not elements:
            continue
        checked += 1
        node = elements[0]
        actual = node.text()
        expected = normalize_text(doc.config.get(name))
        if actual != expected:
            violations.append(
                Violation(
                    "NAR-02",
                    node.position(),
                    "html=%r config=%r" % (actual, expected),
                    "%s の文言が構成データと一致しない" % name,
                )
            )
    return make_result("NAR-02", checked, violations)


# --------------------------------------------------------------------------
# NAR-03 / NAR-04
# --------------------------------------------------------------------------


def check_nar03(doc):
    violations = []
    for cfg_section in doc.cfg_sections:
        section_id = str(cfg_section["id"])
        goal = cfg_section.get("goal")
        if goal is None or not normalize_text(goal):
            violations.append(
                Violation(
                    "NAR-03",
                    section_id,
                    "config.sections[].goal=%r" % goal,
                    "構成データ側のセクションゴールが空 (HTML まで到達させない)",
                )
            )
            continue
        node = doc.section_by_id.get(section_id)
        if node is None:
            # 描画欠落そのものは NAR-06 が計上する (二重計上しない)。
            continue
        goal_elements = [
            child
            for child in node.descendants()
            if child.attr("data-hb-field") == FIELD_SECTION_GOAL
        ]
        if len(goal_elements) != 1:
            violations.append(
                Violation(
                    "NAR-03",
                    section_id,
                    'data-hb-field="%s" x%d' % (FIELD_SECTION_GOAL, len(goal_elements)),
                    "セクションゴールの要素がちょうど 1 個でない",
                )
            )
            continue
        goal_node = goal_elements[0]
        boundary = _section_body_boundary(doc, node)
        if boundary is not None and goal_node.seq > boundary.seq:
            violations.append(
                Violation(
                    "NAR-03",
                    section_id,
                    goal_node.position(),
                    "セクションゴールがセクション冒頭に無い (lead_line / 具体部品より後)",
                )
            )
            continue
        actual = goal_node.text()
        expected = normalize_text(goal)
        if actual != expected:
            violations.append(
                Violation(
                    "NAR-03",
                    section_id,
                    "html=%r config=%r" % (actual, expected),
                    "セクションゴールの文言が構成データと一致しない",
                )
            )
    return make_result("NAR-03", len(doc.cfg_sections), violations)


# 見出しの直後に置く絵。ここに並ぶ部品が節の先頭 1 個目に来ているときは、
# セクションゴールより前にあっても「冒頭を占めた」とは数えない
# (利用者指定 2026-08-19『セクションはタイトル → 画像 → 目的の順』)。
LEADING_VISUAL_PARTS = ("IMG", "DIAGRAM")


def _section_body_boundary(doc, section_node):
    """『冒頭』の境界: lead_line と具体部品のうち文書順で最初のもの。

    ただし節の 1 個目の部品が絵 (LEADING_VISUAL_PARTS) なら、それは境界に
    数えない。絵は読み手が文を読む前に何の話かを掴むための面であり、
    ゴールを押し下げる本文ではない。2 個目以降の絵は通常どおり境界になる
    (絵を並べてゴールを下へ流すことは許さない)。
    """
    candidates = []
    for child in section_node.descendants():
        if child.attr("data-hb-field") == FIELD_LEAD_LINE or doc.is_part(child):
            candidates.append(child)
    candidates.sort(key=lambda node: node.seq)
    if candidates and candidates[0].attr("data-hb-part") in LEADING_VISUAL_PARTS:
        candidates = candidates[1:]
    return candidates[0] if candidates else None


def check_nar04(doc):
    violations = []
    elements = doc.fields(FIELD_SECTION_GOAL)
    for node in elements:
        reason = _hidden_reason(doc, node)
        if reason is not None:
            section = doc.section_of(node)
            location = section.attr("id") if section is not None else node.position()
            violations.append(
                Violation(
                    "NAR-04",
                    location,
                    'data-hb-field="%s" @%s' % (FIELD_SECTION_GOAL, node.position()),
                    reason,
                )
            )
    return make_result("NAR-04", len(elements), violations)


def _hidden_reason(doc, node):
    if node.has_attr("hidden"):
        return "hidden 属性により常時表示でない"
    if (node.attr("aria-hidden") or "").strip().lower() == "true":
        return 'aria-hidden="true" により常時表示でない'
    if _HIDING_RE.search(node.attr("style") or ""):
        return "インライン style の display:none / visibility:hidden により常時表示でない"
    for ancestor in node.ancestors():
        if ancestor.tag == "details":
            return "<details> 配下にあり折り畳まれ得るため常時表示でない"
        if ancestor.has_attr("hidden"):
            return "祖先の hidden 属性により常時表示でない"
        if (ancestor.attr("aria-hidden") or "").strip().lower() == "true":
            return '祖先の aria-hidden="true" により常時表示でない'
        if _HIDING_RE.search(ancestor.attr("style") or ""):
            return "祖先のインライン style により常時表示でない"
    keys = element_selector_keys(node)
    matched = sorted(keys & doc.hiding_selectors)
    if matched:
        return "スタイルシートの %s が display:none / visibility:hidden を宣言している" % matched[0]
    return None


# --------------------------------------------------------------------------
# NAR-05 / NAR-06
# --------------------------------------------------------------------------

NAV_GOAL_ATTR = "data-hb-nav-goal"


def check_nar05(doc):
    violations = []
    if doc.nav is None:
        violations.append(
            Violation(
                "NAR-05",
                "-",
                "<nav>",
                "sticky nav が存在しない (全プリセット共通の型であり不在は違反)",
            )
        )
        return make_result("NAR-05", 0, violations)

    for anchor in doc.nav_anchors:
        target = (anchor.attr("href") or "")[1:]
        if target not in doc.cfg_by_id:
            violations.append(
                Violation(
                    "NAR-05",
                    anchor.position(),
                    'href="#%s"' % target,
                    "nav 項目の参照先が構成データの sections[].id に無い",
                )
            )
            continue
        expected = normalize_text(doc.cfg_by_id[target].get("goal"))
        present = {}
        for name in (NAV_GOAL_ATTR, "title"):
            if anchor.has_attr(name):
                value = normalize_text(anchor.attr(name))
                if value:
                    present[name] = value
        if not present:
            violations.append(
                Violation(
                    "NAR-05",
                    target,
                    "%s / title" % NAV_GOAL_ATTR,
                    "nav 項目がセクションゴールを補助属性で参照していない",
                )
            )
            continue
        mismatched = sorted(k for k, v in present.items() if v != expected)
        if mismatched:
            violations.append(
                Violation(
                    "NAR-05",
                    target,
                    "%s config=%r"
                    % (
                        " ".join("%s=%r" % (k, present[k]) for k in mismatched),
                        expected,
                    ),
                    "nav 項目のゴール参照がセクションゴールと一致しない (片方一致では PASS にしない)",
                )
            )
    return make_result("NAR-05", len(doc.nav_anchors), violations)


def check_nar06(doc):
    violations = []
    chain = []
    nav_targets = set((anchor.attr("href") or "")[1:] for anchor in doc.nav_anchors)
    for cfg_section in doc.cfg_sections:
        section_id = str(cfg_section["id"])
        goal = cfg_section.get("goal")
        node = doc.section_by_id.get(section_id)
        chain.append(
            {
                "section_id": section_id,
                "goal": normalize_text(goal),
                "goal_is_empty": not normalize_text(goal),
                "nav_reference": section_id in nav_targets,
                "rendered_at": node.position() if node is not None else None,
                "document_index": doc.html_sections.index(node) if node is not None else None,
                "role": cfg_section.get("role"),
            }
        )
        if not normalize_text(goal):
            violations.append(
                Violation(
                    "NAR-06",
                    section_id,
                    "goal=%r" % goal,
                    "連鎖表のセクションゴールが空",
                )
            )
        if node is None:
            violations.append(
                Violation(
                    "NAR-06",
                    section_id,
                    "config.sections[].id",
                    "構成データにあるセクションが HTML に描画されていない",
                )
            )
    for node in doc.html_sections:
        section_id = node.attr("id")
        if section_id not in doc.cfg_by_id:
            violations.append(
                Violation(
                    "NAR-06",
                    section_id,
                    node.position(),
                    "HTML に描画されているが構成データの sections に存在しない",
                )
            )
    return Result(
        "NAR-06",
        "FAIL" if violations else "PASS",
        len(doc.cfg_sections),
        violations,
        {"chain": chain},
    )


# --------------------------------------------------------------------------
# NAR-07 (CR-DEMO1)
# --------------------------------------------------------------------------

DEMO_FIRST = "demo_first"


def check_nar07(doc):
    order = doc.config.get("presentation_order")
    if order != DEMO_FIRST:
        return make_result("NAR-07", 0, [], skip_reason={"order": order})

    mains = doc.main_section_nodes()
    if not mains:
        return make_result("NAR-07", 0, [])
    start = mains[0]
    item = _first_presentation_item(doc, start)
    if item is None:
        return make_result("NAR-07", 0, [])

    label = item.attr("data-hb-part") or "段落"
    if _is_real_screen(doc, item):
        return make_result("NAR-07", 1, [])
    violation = Violation(
        "NAR-07",
        item.position(),
        'data-hb-part="%s"' % label if item.attr("data-hb-part") else "本文段落",
        "presentation_order=demo_first では実画面より前に %s を置いてはならない "
        "(最初の提示物は data-hb-asset-role=screenshot の画像か live demo の %s のみ)"
        % (label, doc.res["handson_part"]),
    )
    return make_result("NAR-07", 1, [violation])


def _first_presentation_item(doc, start_section):
    limit = doc.res["single_line_max"]
    for node in doc.nodes:
        if node.seq < start_section.seq:
            continue
        if doc.is_part(node):
            return node
        if node.tag == "p" and not node.has_attr("data-hb-field"):
            if node.text_length() > limit:
                return node
    return None


def _is_real_screen(doc, node):
    part = node.attr("data-hb-part")
    if part == doc.res["image_part"]:
        if (node.attr("data-hb-asset-role") or "") == "screenshot":
            return True
        for child in node.descendants():
            if child.tag == "img" and (child.attr("data-hb-asset-role") or "") == "screenshot":
                return True
        return False
    if part == doc.res["handson_part"]:
        return (node.attr("data-hb-live-demo") or "").strip().lower() == "true"
    return False


# --------------------------------------------------------------------------
# NAR-08 (R21 C48 の描画面)
# --------------------------------------------------------------------------

ROLE_ATTR = "data-hb-section-role"


def check_nar08(doc):
    violations = []
    doc_index = dict((node.attr("id"), i) for i, node in enumerate(doc.html_sections))
    nav_index = {}
    for i, anchor in enumerate(doc.nav_anchors):
        nav_index.setdefault((anchor.attr("href") or "")[1:], i)

    main_doc_positions = [
        doc_index[sid]
        for sid in doc.cfg_ids
        if doc.config_role(sid) == "main" and sid in doc_index
    ]
    main_nav_positions = [
        nav_index[sid]
        for sid in doc.cfg_ids
        if doc.config_role(sid) == "main" and sid in nav_index
    ]

    appendix_ids = [sid for sid in doc.cfg_ids if doc.config_role(sid) == "appendix"]
    for section_id in appendix_ids:
        node = doc.section_by_id.get(section_id)
        if node is None:
            continue
        position = doc_index[section_id]
        if main_doc_positions and position < max(main_doc_positions):
            violations.append(
                Violation(
                    "NAR-08",
                    section_id,
                    "document_index=%d" % position,
                    "付録セクションが本編セクションより前に描画されている",
                )
            )
            continue
        if (node.attr(ROLE_ATTR) or "") != "appendix":
            violations.append(
                Violation(
                    "NAR-08",
                    section_id,
                    "%s=%r" % (ROLE_ATTR, node.attr(ROLE_ATTR)),
                    '付録セクションに %s="appendix" が付いていない' % ROLE_ATTR,
                )
            )
            continue
        if section_id in nav_index and main_nav_positions:
            if nav_index[section_id] < max(main_nav_positions):
                violations.append(
                    Violation(
                        "NAR-08",
                        section_id,
                        "nav_index=%d" % nav_index[section_id],
                        "付録セクションが sticky nav 上で本編より前に並んでいる",
                    )
                )
                continue

    required_role_by_kind = doc.res["required_role_by_kind"]
    for cfg_section in doc.cfg_sections:
        kind = cfg_section.get("section_kind")
        required = required_role_by_kind.get(str(kind))
        if required is None:
            continue
        if cfg_section.get("role") != required:
            violations.append(
                Violation(
                    "NAR-08",
                    str(cfg_section["id"]),
                    "section_kind=%s role=%s" % (kind, cfg_section.get("role")),
                    "この section_kind は role=%s でなければならない "
                    "(資料のゴールにも主題にも紐づかない伝達事項が本編に混ざっている)" % required,
                )
            )
    return make_result("NAR-08", len(appendix_ids), violations)


# --------------------------------------------------------------------------
# NAR-09 / NAR-10 (R22 C66)
# --------------------------------------------------------------------------

DETAIL_ATTR = "data-hb-detail-level"
DEPTH_ATTR = "data-hb-evidence-depth"
CLAIM_ATTR = "data-hb-block-role"
CLAIM_ROLE = "claim"
EVIDENCE_ATTR = "data-hb-evidence"
EVIDENCE_SOURCE_ATTR = "data-hb-evidence-source"


def check_nar09(doc):
    if "detail_level" not in doc.config:
        return make_result("NAR-09", 0, [], skip_reason={"reason": "detail_level_not_declared"})

    mains = doc.main_section_nodes()
    root = doc.root_element
    declared = root.attr(DETAIL_ATTR) if root is not None else None
    if not declared:
        return make_result(
            "NAR-09",
            len(mains),
            [
                Violation(
                    "NAR-09",
                    "-",
                    DETAIL_ATTR,
                    "構成データが detail_level を宣言しているが HTML の root に %s が無い "
                    "(宣言が無ければ突合が成立しない)" % DETAIL_ATTR,
                )
            ],
        )
    levels = doc.res["detail_levels"]
    if declared not in levels:
        return make_result(
            "NAR-09",
            len(mains),
            [
                Violation(
                    "NAR-09",
                    "-",
                    "%s=%r" % (DETAIL_ATTR, declared),
                    "宣言された detail_level が値域 (%s) に無い" % "/".join(levels),
                )
            ],
        )
    if not mains:
        return make_result("NAR-09", 0, [])

    total = sum(node.text_length() for node in mains)
    average = total // len(mains)
    limits = doc.res["detail_limits"]
    budget = limits[declared]

    # 宣言した水準の予算帯で直接検査する。以前は「両端の水準を比べる」形だったため、
    # standard を宣言した資料は何字書いても素通りしていた (どの水準を宣言しても
    # 同じ検査が効かなければ、detail_level は調整軸として機能しない)。
    # 上下どちらの逸脱も同じ失敗 — 読み手は宣言された詳しさを期待して読み始める。
    violations = []
    if average > budget["max"]:
        violations.append(
            Violation(
                "NAR-09",
                "-",
                "declared=%s measured_avg_chars=%d" % (declared, average),
                "宣言 %s に対し本編 %d セクションの平均本文量が予算上限 (%d 字) を超えている "
                "(詳しく書くなら detail_level を上げる。水準を上げずに書き足すと、"
                "要点だけを期待した読み手に読み切れない量が渡る)"
                % (declared, len(mains), budget["max"]),
            )
        )
    elif average < budget["min"]:
        violations.append(
            Violation(
                "NAR-09",
                "-",
                "declared=%s measured_avg_chars=%d" % (declared, average),
                "宣言 %s に対し本編 %d セクションの平均本文量が予算下限 (%d 字) に届かない "
                "(要点だけで足りるなら detail_level を下げる。宣言だけ詳しくして中身が"
                "薄いと、読み手は書かれていない説明を探し続ける)"
                % (declared, len(mains), budget["min"]),
            )
        )
    return Result(
        "NAR-09",
        "FAIL" if violations else "PASS",
        len(mains),
        violations,
        {"declared": declared, "measured_avg_chars": average, "limits": limits},
    )


def check_nar10(doc):
    if "evidence_depth" not in doc.config:
        return make_result("NAR-10", 0, [], skip_reason={"reason": "evidence_depth_not_declared"})

    claims = []
    for section in doc.main_section_nodes():
        for node in section.descendants():
            if (node.attr(CLAIM_ATTR) or "") == CLAIM_ROLE:
                claims.append((section, node))

    root = doc.root_element
    declared = root.attr(DEPTH_ATTR) if root is not None else None
    if not declared:
        return make_result(
            "NAR-10",
            len(claims),
            [
                Violation(
                    "NAR-10",
                    "-",
                    DEPTH_ATTR,
                    "構成データが evidence_depth を宣言しているが HTML の root に %s が無い "
                    "(宣言が無ければ突合が成立しない)" % DEPTH_ATTR,
                )
            ],
        )
    depths = doc.res["evidence_depths"]
    if declared not in depths:
        return make_result(
            "NAR-10",
            len(claims),
            [
                Violation(
                    "NAR-10",
                    "-",
                    "%s=%r" % (DEPTH_ATTR, declared),
                    "宣言された evidence_depth が値域 (%s) に無い" % "/".join(depths),
                )
            ],
        )

    none_depth = depths[0]
    sourced_depth = depths[-1]
    violations = []
    if declared != none_depth:
        for section, claim in claims:
            evidences = [
                node for node in claim.descendants() if node.has_attr(EVIDENCE_ATTR)
            ]
            if not evidences:
                violations.append(
                    Violation(
                        "NAR-10",
                        section.attr("id"),
                        "%s @%s" % (CLAIM_ATTR, claim.position()),
                        "宣言 %s に対し主張ブロックが根拠参照 (%s) を内包していない"
                        % (declared, EVIDENCE_ATTR),
                    )
                )
                continue
            if declared == sourced_depth:
                missing = [
                    node
                    for node in evidences
                    if not normalize_text(node.attr(EVIDENCE_SOURCE_ATTR))
                ]
                if missing:
                    violations.append(
                        Violation(
                            "NAR-10",
                            section.attr("id"),
                            "%s @%s" % (EVIDENCE_SOURCE_ATTR, missing[0].position()),
                            "宣言 %s に対し根拠参照が出典表記 (%s) を持たない"
                            % (declared, EVIDENCE_SOURCE_ATTR),
                        )
                    )
    return Result(
        "NAR-10",
        "FAIL" if violations else "PASS",
        len(claims),
        violations,
        {"declared": declared},
    )


# --------------------------------------------------------------------------
# 実行
# --------------------------------------------------------------------------

CHECKS = (
    ("NAR-01", check_nar01),
    ("NAR-02", check_nar02),
    ("NAR-03", check_nar03),
    ("NAR-04", check_nar04),
    ("NAR-05", check_nar05),
    ("NAR-06", check_nar06),
    ("NAR-07", check_nar07),
    ("NAR-08", check_nar08),
    ("NAR-09", check_nar09),
    ("NAR-10", check_nar10),
)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise GateError("引数が不正: %s" % message)

    def exit(self, status=0, message=None):
        raise GateError("引数の解析に失敗した")


def build_parser():
    parser = Parser(add_help=False)
    parser.add_argument("--html", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--json-report", dest="json_report", default=None)
    return parser


def run(argv):
    args = build_parser().parse_args(argv)
    html_path = Path(args.html)
    config_path = Path(args.config)

    config = load_config(config_path)
    html_text = load_html(html_path)
    resources = load_resources(config)
    collector = parse_html(html_text)
    doc = Document(collector, config, resources)

    results = [check(doc) for _, check in CHECKS]

    stdout_lines = []
    verdict = "FAIL" if any(r.violations for r in results) else "PASS"
    stdout_lines.append("RESULT: %s %s" % (verdict, args.html))
    for result in results:
        stdout_lines.append(result.line())
    stdout_lines.append("OUT-OF-SCOPE:")
    for note in OUT_OF_SCOPE_NOTES:
        stdout_lines.append("  - %s" % note)

    stderr_lines = []
    for result in results:
        for violation in result.violations:
            stderr_lines.append(violation.row())

    if args.json_report is not None:
        report = {
            "script": "verify-handout-narrative.py",
            "component": "C22",
            "html": args.html,
            "config": args.config,
            "result": verdict,
            "detections": [
                {
                    "id": result.detection,
                    "status": result.status,
                    "checked": result.checked,
                    "violations": [v.as_dict() for v in result.violations],
                    "extra": result.extra,
                }
                for result in results
            ],
            "out_of_scope": list(OUT_OF_SCOPE_NOTES),
        }
        blob = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        try:
            Path(args.json_report).write_text(blob, encoding="utf-8")
        except OSError as exc:
            raise GateError(
                "--json-report を書けない: %s (%s)" % (args.json_report, exc.__class__.__name__)
            )

    sys.stdout.write("\n".join(stdout_lines) + "\n")
    if stderr_lines:
        sys.stderr.write("\n".join(stderr_lines) + "\n")
    return 1 if verdict == "FAIL" else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        return run(argv)
    except GateError as exc:
        sys.stderr.write("ERROR\t%s\n" % _one_line(str(exc)))
        return 2


if __name__ == "__main__":
    sys.exit(main())

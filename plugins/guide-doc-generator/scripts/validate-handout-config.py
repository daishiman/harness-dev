#!/usr/bin/env python3
# /// script
# name: validate-handout-config
# version: 0.1.0
# purpose: C12 構成データをスキーマと意味規約で検査し、--normalize 指定時は正規化済み構成データを書き出す fail-closed ゲート
# inputs:
#   - argv: --config <path> [--schema <path>] [--catalog <path>] [--normalize] [--out <path>] [--strict] [--today <YYYY-MM-DD>]
# outputs:
#   - file: --out の正規化済み構成データ
#   - stdout: 違反と警告の一覧
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out / --json-report / --config-out で明示された path のみ
# ///
# -*- coding: utf-8 -*-
"""handout 構成データの決定論ゲート (C12)。

契約の正本は plugin-plans/guide-doc-generator/briefs/script-brief-C12.json
(argv / exit_codes / algorithm / normalize_algorithm / acceptance_checks)。

この script は 2 つの仕事だけを持つ。

1. 構成データ JSON を schemas/handout-config.schema.json と意味規約で fail-closed 検証する。
2. --normalize 指定時に、正規化済み構成データを 1 箇所で確定して --out へ書き出す。

語彙と閾値は一切ここへ書かない。用途種別は C23 のモジュール API 経由で
config/handout-purposes.json から、section_kind とその閾値は
config/handout-sections.json から、部品 id と配置可否は config/handout-parts.json から、
値域と形は schemas/handout-config.schema.json から、本文の文字数上限は
assets/tokens/<テーマ>.json から動的に読む。

exit 0 = 適合 / exit 1 = 構成データ側の違反 / exit 2 = 起動側の不正。
"""

import argparse
import datetime
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_LAUNCH = 2

ROOT_ENV_VARS = ("HB_ROOT", "CLAUDE_PLUGIN_ROOT")
MANIFEST_RELPATH = Path(".claude-plugin") / "plugin.json"
MANIFEST_NAME = "guide-doc-generator"

PRESET_MODULE_RELPATH = Path("scripts") / "resolve-handout-preset.py"
PRESET_MODULE_NAME = "hb_preset_module_c23"
SCHEMA_RELPATH = Path("schemas") / "handout-config.schema.json"
SECTIONS_RELPATH = Path("config") / "handout-sections.json"
PARTS_RELPATH = Path("config") / "handout-parts.json"
VISUAL_POLICY_RELPATH = Path("config") / "handout-visual-policy.json"
TOKENS_RELDIR = Path("assets") / "tokens"

NORMALIZED_BY = "validate-handout-config.py"

# R21 C52 の既定上限。テーマトークンが text_limits を持たないときだけ使う
# (水準別の値はテーマトークンが正本であり、ここには持たない)。
FALLBACK_BODY_MAX_CHARS = 400
SENTENCE_ENDINGS_CLASS = "[。!?！？]"
LONG_SENTENCE_CHARS = 45
LONG_SENTENCE_COUNT = 3
TITLE_WARN_CHARS = 60
LEAD_LINE_WARN_CHARS = 60
SECTIONS_WARN_COUNT = 12
SLUG_MAX_CHARS = 40
MINUTES_PER_HOUR = 60

# 図解密度と散文量の方針。正本は config/handout-visual-policy.json であり、
# ここにあるのは正本を読めなかったときだけ使う fallback である (fail-soft)。
#
# 部品 id の集合は fallback にも書き下さない。部品 id の語彙は C11 の
# config/handout-parts.json だけが持ち、どの部品が視覚部品かは上記の正本だけが
# 持つ (AC-C11-19 / Y-05)。正本を読めないときは、id を綴らずに済む最小の集合
# (図解と画像) へ退避する。集合が狭いぶん警告は出やすくなるが、いずれも warning
# であり exit code は 0 のままなので、検証そのものは止まらない。
FALLBACK_VISUAL_PART_IDS = ("DIAGRAM", "IMG")
FALLBACK_MIN_VISUAL_PER_SECTION = 1
FALLBACK_MIN_DIAGRAM_RATIO = 0.34
FALLBACK_MIN_DIAGRAM_FLOOR = 1
FALLBACK_MAX_TEXT_RATIO = 0.5
FALLBACK_MAX_TEXT_RUN = 1
TEXT_PART_ID = "TEXT"
DIAGRAM_PART_ID = "DIAGRAM"
ROLE_MAIN = "main"
FALLBACK_MICRO_COPY_LIMITS = {
    "label": ("label", 14), "key": ("label", 14), "term": ("label", 14),
    "plain": ("label", 14), "header": ("label", 14), "columns": ("label", 14),
    "tag": ("label", 14), "kind": ("label", 14),
    "title": ("title", 24), "heading": ("title", 24), "summary": ("title", 24),
    "operation": ("title", 24), "name": ("title", 24),
    "text": ("caption", 40), "detail": ("caption", 40), "note": ("caption", 40),
    "expected": ("caption", 40), "alt": ("caption", 40), "cells": ("caption", 40),
    "sub": ("caption", 40), "body": ("caption", 40),
}
# 免除部品も id を綴らない。正本が無いときは本文部品だけを免除する
FALLBACK_MICRO_COPY_EXEMPT_PARTS = ("TEXT",)
FALLBACK_MICRO_COPY_EXEMPT_FIELDS = (
    "id", "asset_id", "diagram_id", "attachment_id", "filename",
    "mime", "due", "owner", "fallback_hint", "note_key", "tone", "time")

FALLBACK_HERO_FIELD_LIMITS = {"purpose": 60, "background": 80, "goal": 50}
# hero の総量。1 フィールドずつ短くても、短い行が積み上がれば冒頭は長くなる
FALLBACK_HERO_TOTAL_CHARS = 400
FALLBACK_HERO_TOTAL_FIELDS = (
    "purpose", "background", "goal", "lead", "goal_chips", "focus_theme",
    "target_tasks", "must_remember", "no_need_to_remember")
FALLBACK_SUMMARY_STEP = "overview"
# 詳細層らしい部品の集合も同様。正本が無いときは図解だけを手順の形として数える
FALLBACK_DETAIL_PART_IDS = ("DIAGRAM",)

FOLD_SUMMARY = "詳しい説明 (続き)"
CONT_SUFFIX = "-cont"

# section_kind ごとの追加検査規則の分岐点。値 (閾値) は catalog 側にあり、
# ここにあるのは「どの種別にどの規則を当てるか」という C12 固有の対応だけ。
KIND_AGENDA_TIMEBOX = "agenda-timebox"
KIND_DECISIONS = "decisions"
KIND_ACTION_ITEMS = "action-items"
KIND_SOURCES = "sources"
KIND_KNOWN_UNKNOWN_NEXT = "known-unknown-next"
KIND_HANDSON = "handson"
KIND_ANTICIPATED_QA = "anticipated-qa"
KIND_CAPABILITY_EXPLAINER = "capability-explainer"

ATTR_MAX_ITEMS = "max_items"
ATTR_FORBID_ROW_DETAIL = "forbid_row_detail"
ATTR_MIN_DURATION_SHARE = "min_duration_share"
ATTR_REQUIRED_ROLE = "required_role"

# 追加検査規則が名指しする「器」は構成データ側の block.type で指す (P03 Y-05 /
# AC-C11-19)。部品 id の literal はこの script に一切持たず、id が要る箇所は
# config/handout-parts.json の data_block_type 述語で実行時に引く
# (Context.part_of_block)。カタログ全件の名簿も持たない。generated-chrome の
# 判定は section_scope で行う。
BLOCK_TEXT = "text"
BLOCK_ACCORDION = "accordion"
BLOCK_TABS = "tabs"
BLOCK_ROWS = "steps"
BLOCK_TRIO = "trio"
BLOCK_CARDS = "features"
BLOCK_CHECKLIST = "checklist"
BLOCK_ACTIONS = "action-items"
BLOCK_HANDSON = "handson"

# 上の器はすべてカタログに実在していないと検査が黙って無効化されるので、
# 起動時に fail-closed で確認する。
REQUIRED_BLOCK_TYPES = (
    BLOCK_TEXT, BLOCK_ACCORDION, BLOCK_TABS, BLOCK_ROWS, BLOCK_TRIO,
    BLOCK_CARDS, BLOCK_CHECKLIST, BLOCK_ACTIONS, BLOCK_HANDSON,
)

IN_SECTION_SCOPE = "in-section"

TIE_GOAL = "goal"
TIE_FOCUS_PREFIX = "focus_theme:"
TIE_TASK_PREFIX = "target_task:"

DATE_INPUT_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
TODAY_ARG_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
MINUTES_RE = re.compile(r"^(\d{1,3})\s*分$")
HOURS_RE = re.compile(r"^(\d{1,3})\s*時間$")
HOURS_MINUTES_RE = re.compile(r"^(\d{1,3})\s*時間\s*(\d{1,3})\s*分$")
PART_DATA_POINTER_RE = re.compile(r"/parts/\d+/data(/|$)")
ASSET_ROLE_POINTER_RE = re.compile(r"^/assets/\d+/role$")

DEFAULT_CODES = {
    "missing": "E-FIELD-MISSING",
    "blank": "E-FIELD-EMPTY",
    "type": "E-TYPE-INVALID",
    "enum": "E-ENUM-INVALID",
    "const": "E-CONST-MISMATCH",
    "pattern": "E-FORMAT-INVALID",
    "length": "E-LENGTH-RANGE",
    "min_items": "E-ARRAY-LENGTH",
    "max_items": "E-ARRAY-LENGTH",
    "unique": "E-DUPLICATE-KEY",
    "range": "E-VALUE-RANGE",
    "single_line": "E-SINGLE-LINE",
    "unknown_key": "E-KEY-UNKNOWN",
    "oneof": "E-SHAPE-INVALID",
    "anyof": "E-FORMAT-INVALID",
}


class LaunchAbort(Exception):
    """起動側の不正 (exit 2)。"""


# ---------------------------------------------------------------------------
# 実体解決とデータ正本の読み込み
# ---------------------------------------------------------------------------


def manifest_matches(root):
    manifest = Path(root) / MANIFEST_RELPATH
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("name") == MANIFEST_NAME


def resolve_root():
    """plugin root の実体解決 4 段 (環境変数 → manifest 照合 → __file__ 相対)。"""
    for name in ROOT_ENV_VARS:
        value = os.environ.get(name)
        if value:
            return Path(value)
    try:
        cwd = Path.cwd().resolve()
    except OSError:
        cwd = None
    if cwd is not None:
        for base in (cwd, *cwd.parents):
            if manifest_matches(base):
                return base
    return Path(__file__).resolve().parent.parent


def load_preset_module(root):
    """C23 resolve-handout-preset.py をモジュールとして読み込む (語彙を自前に持たない)。"""
    candidates = [Path(root) / PRESET_MODULE_RELPATH,
                  Path(__file__).resolve().parent / PRESET_MODULE_RELPATH.name]
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location(PRESET_MODULE_NAME, str(path))
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise LaunchAbort("用途プリセット解決モジュールを実体解決できない: %s"
                      % (Path(root) / PRESET_MODULE_RELPATH))


def read_json_file(path, label):
    path = Path(path)
    if not path.is_file():
        raise LaunchAbort("%s が実在しない: %s" % (label, path))
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LaunchAbort("%s を読めない: %s (%s)" % (label, path, exc))
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise LaunchAbort("%s が JSON として parse できない: %s (%s)" % (label, path, exc))


# ---------------------------------------------------------------------------
# 小さな純関数
# ---------------------------------------------------------------------------


def nfc(text):
    return unicodedata.normalize("NFC", text)


def normalize_text(text):
    """NFC 正規化 + 行末空白除去 (文字列内の改行は保持する)。"""
    value = nfc(text).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in value.split("\n"))


def normalize_strings(value):
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        return [normalize_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_strings(item) for key, item in value.items()}
    return value


def is_blank(value):
    return not isinstance(value, str) or not value.strip()


def parse_minutes(value):
    """'30分' / '1時間' / '90 分' / '1時間30分' を分へ。解釈できなければ None。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = MINUTES_RE.match(text)
    if match:
        return int(match.group(1))
    match = HOURS_MINUTES_RE.match(text)
    if match:
        return int(match.group(1)) * MINUTES_PER_HOUR + int(match.group(2))
    match = HOURS_RE.match(text)
    if match:
        return int(match.group(1)) * MINUTES_PER_HOUR
    return None


def parse_date_parts(value):
    """受理する 4 書式を (year, month, day) へ。書式外は None。"""
    if not isinstance(value, str):
        return None
    match = DATE_INPUT_RE.match(value.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def calendar_valid(year, month, day):
    try:
        datetime.date(year, month, day)
    except ValueError:
        return False
    return True


def format_date(year, month, day):
    return "%04d/%02d/%02d" % (year, month, day)


def derive_slug(title):
    text = unicodedata.normalize("NFKC", title).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:SLUG_MAX_CHARS].strip("-")


def split_body(text, limit):
    """上限以前で最後に現れる文末の直後で切る (無ければ上限位置で切る)。"""
    chunks = []
    rest = text
    while len(rest) > limit:
        head = rest[:limit]
        cut = -1
        for match in re.finditer(SENTENCE_ENDINGS_CLASS, head):
            cut = match.start()
        cut = cut + 1 if cut >= 0 else limit
        chunks.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        chunks.append(rest)
    return chunks


def long_sentence_count(body):
    return sum(1 for piece in re.split(SENTENCE_ENDINGS_CLASS, body)
               if len(piece.strip()) > LONG_SENTENCE_CHARS)


def same_scalar(left, right):
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    return left == right


# ---------------------------------------------------------------------------
# 検証本体
# ---------------------------------------------------------------------------


class Checker(object):
    """schema (形) + 意味規約 (R11 / R19 / R21 / R22) の検査。"""

    def __init__(self, context):
        self.ctx = context
        self.schema = context.schema
        self.diags = []
        self.scope_stack = []

    # ---- 診断 ------------------------------------------------------------

    def add(self, code, pointer, message):
        self.diags.append((code, pointer or "/", " ".join(str(message).split())))

    def emit(self, kind, pointer, message):
        self.add(self.code_for(kind, pointer), pointer, message)

    def code_for(self, kind, pointer):
        if pointer == "/focus_theme" or pointer.startswith("/focus_theme/"):
            return "E-FOCUS-THEME"
        if pointer == "/schema_version":
            return "E-SCHEMA-VERSION"
        if kind in ("enum", "type", "oneof", "const"):
            if pointer == "/attainment_level" or pointer.endswith("/attainment_step"):
                return "E-ATTAINMENT-LEVEL"
            if pointer == "/presentation_order":
                return "E-PRESENTATION-ORDER"
        if kind == "min_items":
            if pointer == "/target_tasks":
                return "E-TARGET-TASKS-EMPTY"
            if pointer in ("/must_remember", "/no_need_to_remember"):
                return "E-REMEMBER-PAIR"
        if kind == "missing" and ASSET_ROLE_POINTER_RE.match(pointer):
            return "E-ASSET-ROLE-MISSING"
        if kind == "single_line":
            if pointer.endswith("/lead_line"):
                return "E-LEADLINE-MULTILINE"
            if pointer.endswith("/judgment_axis"):
                return "E-AXIS-MULTILINE"
        if kind == "unique" and "/glossary/" in pointer:
            return "E-GLOSSARY-DUP"
        if kind != "unknown_key" and PART_DATA_POINTER_RE.search(pointer):
            return "E-PART-SHAPE"
        return DEFAULT_CODES[kind]

    # ---- 汎用 schema 解釈 -------------------------------------------------

    def deref(self, node):
        guard = 0
        while isinstance(node, dict) and "$ref" in node and guard < 16:
            target = self.schema
            for token in node["$ref"].lstrip("#").strip("/").split("/"):
                target = target[token]
            node = target
            guard += 1
        return node

    def matches(self, node, value, pointer):
        saved = self.diags
        self.diags = []
        self.check(node, value, pointer)
        ok = not self.diags
        self.diags = saved
        return ok

    def type_ok(self, value, allowed):
        for name in allowed:
            if name == "null" and value is None:
                return True
            if name == "string" and isinstance(value, str):
                return True
            if name == "boolean" and isinstance(value, bool):
                return True
            if name == "integer" and isinstance(value, int) and not isinstance(value, bool):
                return True
            if name == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
                return True
            if name == "array" and isinstance(value, list):
                return True
            if name == "object" and isinstance(value, dict):
                return True
        return False

    def check(self, node, value, pointer, skip=()):
        node = self.deref(node)
        if not isinstance(node, dict):
            return
        if "oneOf" in node:
            if not any(self.matches(option, value, pointer) for option in node["oneOf"]):
                self.emit("oneof", pointer, "許容される形のどれにも一致しない")
            return
        types = node.get("type")
        if types is not None:
            allowed = types if isinstance(types, list) else [types]
            if not self.type_ok(value, allowed):
                self.emit("type", pointer, "型が %s でない" % "|".join(allowed))
                return
        if value is None:
            return
        if "const" in node and not same_scalar(value, node["const"]):
            self.emit("const", pointer, "既知の値と一致しない (期待 %s)" % json.dumps(
                node["const"], ensure_ascii=False))
            return
        if "enum" in node and not any(same_scalar(value, item) for item in node["enum"]):
            allowed = ", ".join(json.dumps(item, ensure_ascii=False) for item in node["enum"])
            self.emit("enum", pointer, "値域外の値。使える値: %s" % allowed)
            return
        if "anyOf" in node:
            if not any(self.matches(option, value, pointer) for option in node["anyOf"]):
                self.emit("anyof", pointer, "許容される書式のどれにも一致しない")
                return
        if isinstance(value, str):
            self.check_string(node, value, pointer)
        elif isinstance(value, bool):
            pass
        elif isinstance(value, (int, float)):
            self.check_number(node, value, pointer)
        elif isinstance(value, list):
            self.check_array(node, value, pointer)
        elif isinstance(value, dict):
            self.check_object(node, value, pointer, skip)

    def check_string(self, node, value, pointer):
        min_len = node.get("minLength")
        forbid_blank = bool(node.get("x_non_blank")) or (isinstance(min_len, int) and min_len >= 1)
        if forbid_blank and not value.strip():
            self.emit("blank", pointer, "空 (または空白のみ) で内容が無い")
            return
        if isinstance(min_len, int) and len(value) < min_len:
            self.emit("length", pointer, "%d 文字以上が必要 (実際 %d 文字)" % (min_len, len(value)))
        max_len = node.get("maxLength")
        if isinstance(max_len, int) and len(value) > max_len:
            self.emit("length", pointer, "%d 文字以下にする (実際 %d 文字)" % (max_len, len(value)))
        if node.get("x_single_line") and "\n" in value:
            self.emit("single_line", pointer, "1 行で書く (改行を含められない)")
        pattern = node.get("pattern")
        if pattern and not re.search(pattern, value):
            self.emit("pattern", pointer, "書式に一致しない")

    def check_number(self, node, value, pointer):
        minimum = node.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            self.emit("range", pointer, "下限 %s を下回る" % minimum)
        maximum = node.get("maximum")
        if isinstance(maximum, (int, float)) and value > maximum:
            self.emit("range", pointer, "上限 %s を超える" % maximum)

    def check_array(self, node, value, pointer):
        min_items = node.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            self.emit("min_items", pointer, "%d 件以上が必要 (実際 %d 件)" % (min_items, len(value)))
        max_items = node.get("maxItems")
        if isinstance(max_items, int) and len(value) > max_items:
            self.emit("max_items", pointer, "%d 件以下にする (実際 %d 件)" % (max_items, len(value)))
        length_ref = node.get("x_length_equals")
        if length_ref:
            other = self.lookup_scope_list(length_ref)
            if other is not None and len(other) != len(value):
                self.emit("length", pointer, "%s の件数 %d と一致しない (実際 %d 件)"
                          % (length_ref, len(other), len(value)))
        item_schema = node.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                self.check(item_schema, item, "%s/%d" % (pointer, index))
        unique_key = node.get("x_unique_by")
        if unique_key:
            seen = set()
            for index, item in enumerate(value):
                if not isinstance(item, dict) or unique_key not in item:
                    continue
                key = item[unique_key]
                key = nfc(key) if isinstance(key, str) else json.dumps(key, sort_keys=True)
                if key in seen:
                    self.emit("unique", "%s/%d" % (pointer, index),
                              "%s が重複している" % unique_key)
                else:
                    seen.add(key)

    def check_object(self, node, value, pointer, skip=()):
        props = node.get("properties") or {}
        if node.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    self.emit("unknown_key", "%s/%s" % (pointer, key),
                              "既知キーではない。ここで使えるキー: %s" % ", ".join(sorted(props)))
        for key in node.get("required", []):
            if key not in value:
                self.emit("missing", "%s/%s" % (pointer, key), "必須フィールドが無い")
        self.scope_stack.append(value)
        try:
            for key, sub in props.items():
                if key in skip or key not in value:
                    continue
                self.check(sub, value[key], "%s/%s" % (pointer, key))
        finally:
            self.scope_stack.pop()

    def lookup_scope_list(self, name):
        for scope in reversed(self.scope_stack):
            if isinstance(scope, dict) and isinstance(scope.get(name), list):
                return scope[name]
        return None

    # ---- 入口 -------------------------------------------------------------

    def run(self, cfg):
        ctx = self.ctx
        # normalize が充填する枠は null を「未指定」と同じ扱いにする (縫い目を 1 つに保つ)。
        skip = ["sections", "date"]
        for key in self.schema.get("x_required_after_normalize") or []:
            if cfg.get(key, False) is None:
                skip.append(key)
        self.check(self.schema, cfg, "", skip=tuple(skip))
        self.check_date(cfg)
        self.check_doc_type(cfg)
        self.check_remember(cfg)
        self.check_warnings(cfg)
        sections = cfg.get("sections")
        if isinstance(sections, list):
            for index, section in enumerate(sections):
                if isinstance(section, dict):
                    self.check_section(section, index)
                else:
                    self.emit("type", "/sections/%d" % index, "オブジェクトでない")
            self.check_section_ids(sections)
            self.check_ties(cfg, sections)
            self.check_roles(cfg, sections)
            self.check_attainment(cfg, sections)
            self.check_durations(sections)
            self.check_glossary_scopes(cfg, sections)
        self.check_references(cfg)
        del ctx
        return self.diags

    # ---- document ---------------------------------------------------------

    def check_date(self, cfg):
        if "date" not in cfg:
            return
        value = cfg["date"]
        if value is None:
            return
        if not isinstance(value, str):
            self.emit("type", "/date", "文字列でない")
            return
        parts = parse_date_parts(value)
        if parts is None:
            self.add("E-DATE-FORMAT", "/date",
                     "受理する日付書式ではない (yyyy/mm/dd または yyyy-mm-dd)")
            return
        if not calendar_valid(*parts):
            self.add("E-DATE-INVALID", "/date", "暦に存在しない日付")

    def check_doc_type(self, cfg):
        value = cfg.get("doc_type")
        if is_blank(value):
            return
        try:
            self.ctx.c23.resolve(self.ctx.catalog, value)
        except self.ctx.c23.UnknownPurposeError:
            known = ", ".join(self.ctx.c23.vocabulary(self.ctx.catalog))
            self.add("E-DOCTYPE-UNKNOWN", "/doc_type",
                     "用途種別が語彙正本に無い。使える値: %s" % known)

    def check_remember(self, cfg):
        must = cfg.get("must_remember")
        if not isinstance(must, list):
            return
        maximum = cfg.get("must_remember_max")
        if not isinstance(maximum, int) or isinstance(maximum, bool):
            maximum = self.ctx.must_remember_max_default
        if len(must) > maximum:
            self.add("E-REMEMBER-MAX", "/must_remember",
                     "件数の上限 %d 件を超える (実際 %d 件)" % (maximum, len(must)))

    def check_warnings(self, cfg):
        title = cfg.get("title")
        if isinstance(title, str) and len(title) > TITLE_WARN_CHARS:
            self.add("W-TITLE-LONG", "/title",
                     "%d 文字を超えるタイトルは hero で折り返しやすい" % TITLE_WARN_CHARS)
        sections = cfg.get("sections")
        if isinstance(sections, list) and len(sections) > SECTIONS_WARN_COUNT:
            self.add("W-SECTIONS-MANY", "/sections",
                     "セクションが %d 件を超える (%d 件)" % (SECTIONS_WARN_COUNT, len(sections)))
        glossary = cfg.get("glossary")
        prior = cfg.get("prior_knowledge_level")
        if (isinstance(glossary, list) and not glossary
                and prior == self.ctx.no_prior_knowledge_value):
            self.add("W-GLOSSARY-EMPTY", "/glossary",
                     "前提知識なしの読み手に対して用語の言い換え宣言が 1 件も無い")
        self.check_visual_density(cfg)
        self.check_micro_copy(cfg)
        self.check_layering(cfg)
        self.check_opening(cfg)

    # ---- 冒頭の置き方 ------------------------------------------------------

    def hero_volume(self, cfg):
        """hero へ描画される文の総字数と行数を返す。

        数える対象は正本 (opening.hero_total.counted_fields) が持つ。値の形は
        文字列・文字列配列・{label} を持つオブジェクト配列の 3 通りで、いずれも
        C11 build_hero が 1 行として描画する単位で数える。
        """
        total = 0
        lines = 0
        for name in self.ctx.hero_total_fields:
            value = cfg.get(name)
            if isinstance(value, str):
                text = value.strip()
                if text:
                    total += len(text)
                    lines += 1
                continue
            if not isinstance(value, list):
                continue
            for entry in value:
                text = entry.get("label") if isinstance(entry, dict) else entry
                if isinstance(text, str) and text.strip():
                    total += len(text.strip())
                    lines += 1
        return total, lines

    def check_opening(self, cfg):
        """『冒頭に散文を積まない』を当てる検査。

        文書の冒頭 (hero の 3 要素) と、各節の冒頭 (最初の部品) の両方を見る。
        正本は config/handout-visual-policy.json の opening にある。
        """
        for field, cap in sorted(self.ctx.hero_field_limits.items()):
            value = cfg.get(field)
            if not isinstance(value, str):
                continue
            length = len(value.strip())
            if length > cap:
                self.add("W-HERO-LONG", "/" + field,
                         "%d 文字 (上限 %d 文字)。冒頭の 3 要素は宣言であって説明ではない。"
                         "説明したい中身は先頭セクションのカードと図解へ移す"
                         % (length, cap))

        total, lines = self.hero_volume(cfg)
        if total > self.ctx.hero_total_chars:
            self.add("W-HERO-HEAVY", "/",
                     "冒頭に描画される文が %d 文字 %d 行ある (上限 %d 文字)。"
                     "1 フィールドずつ短くても、短い行が積み上がれば冒頭は長くなる。"
                     "『読み終えたときの持ち帰り』は冒頭の判断材料ではないので、"
                     "本編末尾か付録の節へ移す"
                     % (total, lines, self.ctx.hero_total_chars))

        sections = cfg.get("sections")
        if not isinstance(sections, list):
            return
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            if section.get("role") not in (None, ROLE_MAIN):
                continue
            ids = self.part_ids_of(section)
            if ids and ids[0] == TEXT_PART_ID:
                self.add("W-OPENS-PROSE", "/sections/%d/parts/0" % index,
                         "節が散文で始まっている。言いたいことは lead_line が 1 行で"
                         "担っている。その直後は形 (図解・カード・表) を置き、"
                         "TEXT はその後の補足として置く")

    # ---- 要点層と詳細層の切り分け ------------------------------------------

    def check_layering(self, cfg):
        """『要点だけ』でも『詳細だけ』でもない形になっているかを見る検査。

        層の印は section.attainment_step (順序つき enum) を再利用する。正本は
        config/handout-visual-policy.json の layering にある。
        """
        sections = cfg.get("sections")
        if not isinstance(sections, list):
            return
        order = self.ctx.attainment_order
        summary_rank = order.get(self.ctx.summary_step)
        if summary_rank is None:
            return

        mains = []
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            if section.get("role") not in (None, ROLE_MAIN):
                continue
            if not self.part_ids_of(section):
                continue
            mains.append((index, section))
        if len(mains) < 2:
            # 本編が 1 節しかない資料に層の分離を求めても意味がない
            return

        summary_count = sum(1 for _, s in mains
                            if order.get(s.get("attainment_step")) == summary_rank)
        if not summary_count:
            # 層を分けていない資料 (全節が同じ段) は本検査の対象外。層の分離を
            # 始めた資料だけを見る
            return

        detail_seen = False
        detail_count = 0
        for index, section in mains:
            pointer = "/sections/%d" % index
            rank = order.get(section.get("attainment_step"))
            if rank is None:
                continue
            if rank > summary_rank:
                detail_seen = True
                detail_count += 1
                ids = self.part_ids_of(section)
                if not any(pid in self.ctx.detail_part_ids for pid in ids):
                    self.add("W-DETAIL-FLOWLESS", pointer + "/parts",
                             "詳細層のセクションに手順・流れを表す部品が無い。"
                             "詳細を散文で書き下すと、要点層より読みにくい塊が"
                             "後半に生まれるだけになる (手順の形で見せる部品: %s)"
                             % "/".join(sorted(self.ctx.detail_part_ids)))
            elif detail_seen:
                self.add("W-LAYER-ORDER", pointer,
                         "詳細層のセクションより後ろに要点層のセクションがある。"
                         "要点を先に、詳細を後に置かないと読み手は今どちらを"
                         "読んでいるのか分からなくなる")

        if not detail_count:
            self.add("W-DETAIL-ABSENT", "/sections",
                     "本編が要点層 (attainment_step = %s) だけで構成されている。"
                     "手元の手順と突き合わせられる詳細層が無いと、読み手は"
                     "元の資料と何がどう違うのかを掴めない" % self.ctx.summary_step)

    # ---- 図解・カード内の 1 要素あたり文字数 --------------------------------

    def walk_micro_copy(self, node, pointer, emit):
        """data の中の文字列を、フィールド名を保ったまま辿る。

        配列は要素ごとに添字を足すが、フィールド名 (役割) は親から引き継ぐ。
        columns[] や cells[] のように「名前は複数形・中身は 1 要素」の形へ
        上限を当てるためである。
        """
        if isinstance(node, dict):
            for key, value in node.items():
                self.walk_micro_copy(value, "%s/%s" % (pointer, key), emit)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self.walk_micro_copy(value, "%s/%d" % (pointer, index), emit)
        elif isinstance(node, str):
            field = pointer.rsplit("/", 1)[-1]
            if field.isdigit():
                # 配列要素。役割はひとつ上のフィールド名が持つ
                parts = pointer.rsplit("/", 2)
                field = parts[1] if len(parts) > 2 else field
            emit(field, node, pointer)

    def check_micro_copy(self, cfg):
        """『図解やカードの 1 要素が長すぎる』を捕まえる検査。

        長い文章だけで説明された資料は読まれない。図で形を見せ、文はその補足に
        留めるという編集方針を、要素あたりの文字数として当てる。上限の正本は
        config/handout-visual-policy.json の micro_copy にある。
        """

        def emit_for(pointer_owner):
            def emit(field, value, pointer):
                if field in self.ctx.micro_copy_exempt_fields:
                    return
                limit = self.ctx.micro_copy_limits.get(field)
                if limit is None:
                    return
                role, cap = limit
                length = len(value.strip())
                if length <= cap:
                    return
                self.add("W-COPY-LONG", pointer,
                         "%s は %d 文字 (上限 %d 文字・役割 %s)。%sの中の 1 要素が"
                         "段落になっている。要点だけを残し、続きは本文か別の部品へ移す"
                         % (field, length, cap, role, pointer_owner))
            return emit

        sections = cfg.get("sections")
        if isinstance(sections, list):
            for s_index, section in enumerate(sections):
                if not isinstance(section, dict):
                    continue
                parts = section.get("parts")
                if not isinstance(parts, list):
                    continue
                for p_index, part in enumerate(parts):
                    if not isinstance(part, dict):
                        continue
                    if part.get("part") in self.ctx.micro_copy_exempt_parts:
                        continue
                    pointer = "/sections/%d/parts/%d/data" % (s_index, p_index)
                    self.walk_micro_copy(part.get("data"), pointer, emit_for("部品"))

        diagrams = cfg.get("diagrams")
        if isinstance(diagrams, list):
            for d_index, diagram in enumerate(diagrams):
                if not isinstance(diagram, dict):
                    continue
                pointer = "/diagrams/%d/data" % d_index
                self.walk_micro_copy(diagram.get("data"), pointer, emit_for("図解"))

    # ---- 図解密度と散文量 --------------------------------------------------

    def part_ids_of(self, section):
        """セクション直下の部品 id を出現順で返す (タブの中身は数えない)。"""
        parts = section.get("parts")
        if not isinstance(parts, list):
            return []
        found = []
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("part"), str):
                found.append(part["part"])
        return found

    def check_visual_density(self, cfg):
        """『図があるのとないのとで理解の粒度が変わる』を数値で当てる検査。

        いずれも warning である。値域の縛りではなく編集方針であり、警告 0 件を
        完了条件にするかは呼び出し側 (C01 のゴールシーク) が決める。
        """
        sections = cfg.get("sections")
        if not isinstance(sections, list):
            return

        main_count = 0
        diagram_count = 0
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            pointer = "/sections/%d" % index
            ids = self.part_ids_of(section)
            if not ids:
                continue
            is_main = section.get("role") in (None, ROLE_MAIN)
            if is_main:
                main_count += 1
            diagram_count += sum(1 for pid in ids if pid == DIAGRAM_PART_ID)

            visual = sum(1 for pid in ids if pid in self.ctx.visual_part_ids)
            if is_main and visual < self.ctx.min_visual_per_section:
                self.add("W-VISUAL-ABSENT", pointer + "/parts",
                         "本文だけのセクション。目で形が分かる部品が %d 件しかない "
                         "(下限 %d 件)。読み手は本文を読む前に何の話か掴めない"
                         % (visual, self.ctx.min_visual_per_section))

            text_count = sum(1 for pid in ids if pid == TEXT_PART_ID)
            if text_count and len(ids) and (float(text_count) / len(ids)) > self.ctx.max_text_ratio:
                self.add("W-TEXT-HEAVY", pointer + "/parts",
                         "部品 %d 件のうち %d 件が TEXT で、上限比率 %s を超える。"
                         "実質的に文章の塊になっている"
                         % (len(ids), text_count, self.ctx.max_text_ratio))

            run = 0
            for order, pid in enumerate(ids):
                run = run + 1 if pid == TEXT_PART_ID else 0
                if run > self.ctx.max_text_run:
                    self.add("W-TEXT-RUN", "%s/parts/%d" % (pointer, order),
                             "TEXT が %d 件続く (上限 %d 件)。画面上は 1 つの長文と"
                             "区別がつかない。間に形のある部品を挟むか 1 つへまとめる"
                             % (run, self.ctx.max_text_run))
                    break

        if main_count:
            required = max(self.ctx.min_diagram_floor,
                           int(math.ceil(main_count * self.ctx.min_diagram_ratio)))
            if diagram_count < required:
                self.add("W-DIAGRAM-FEW", "/diagrams",
                         "概念図解が %d 枚しかない (main セクション %d 個に対し下限 %d 枚)。"
                         "表と手順だけでは部分の詳細は伝わっても全体の関係が残らない"
                         % (diagram_count, main_count, required))

    # ---- section ----------------------------------------------------------

    def check_section(self, section, index):
        pointer = "/sections/%d" % index
        section_def = self.schema["$defs"]["section"]
        self.check(section_def, section, pointer, skip=("parts", "duration"))

        reserved = (section_def["properties"]["id"].get("x_reserved_ids") or [])
        if section.get("id") in reserved:
            self.add("E-SECTION-ID-RESERVED", pointer + "/id",
                     "予約された id は使えない: %s" % ", ".join(reserved))

        lead_line = section.get("lead_line")
        if isinstance(lead_line, str) and len(lead_line) > LEAD_LINE_WARN_CHARS:
            self.add("W-LEADLINE-LONG", pointer + "/lead_line",
                     "%d 文字を超える 1 行抽象は読みにくい" % LEAD_LINE_WARN_CHARS)

        self.check_section_duration(section, pointer)

        kind = section.get("section_kind")
        if kind is None:
            kind = self.ctx.default_section_kind
        attrs = self.ctx.kind_attributes.get(kind)
        if isinstance(kind, str) and attrs is None:
            self.add("E-SECTIONKIND-UNKNOWN", pointer + "/section_kind",
                     "section_kind が語彙正本に無い。使える値: %s"
                     % ", ".join(sorted(self.ctx.kind_attributes)))
            attrs = {}

        parts = section.get("parts")
        if isinstance(parts, list):
            min_parts = section_def["properties"]["parts"].get("minItems")
            if isinstance(min_parts, int) and len(parts) < min_parts:
                self.emit("min_items", pointer + "/parts",
                          "%d 件以上の部品が要る (実際 %d 件)" % (min_parts, len(parts)))
            seen_ids = set()
            for part_index, part in enumerate(parts):
                part_pointer = "%s/parts/%d" % (pointer, part_index)
                if not isinstance(part, dict):
                    self.emit("type", part_pointer, "オブジェクトでない")
                    continue
                self.check_part(part, part_pointer)
                part_id = part.get("id")
                if isinstance(part_id, str):
                    if part_id in seen_ids:
                        self.add("E-PART-ID-DUP", part_pointer + "/id",
                                 "セクション内で part id が重複している")
                    seen_ids.add(part_id)
            self.check_kind_constraints(section, parts, pointer, kind, attrs or {})

    def check_section_duration(self, section, pointer):
        if "duration" not in section:
            return
        value = section["duration"]
        if value is None:
            return
        if not isinstance(value, str):
            self.emit("type", pointer + "/duration", "文字列でない")
            return
        if parse_minutes(value) is None:
            self.add("E-SECTION-DURATION-FORMAT", pointer + "/duration",
                     "セクションの所要時間は分の単位で 1 値だけ書く (範囲表記や分量表記は不可)")

    def check_part(self, part, pointer, nested=False):
        self.check(self.schema["$defs"]["part"], part, pointer, skip=("data",))
        part_id = part.get("part")
        if not isinstance(part_id, str):
            return
        scope = self.ctx.part_scopes.get(part_id)
        if scope is None:
            self.add("E-PART-UNKNOWN", pointer + "/part",
                     "部品カタログに無い部品 id")
            return
        if scope != IN_SECTION_SCOPE:
            self.add("E-PART-PLACEMENT", pointer,
                     "この部品は document 構造から生成される chrome なので parts へ置けない")
            return
        data = part.get("data")
        data_schema = self.ctx.part_data.get(part_id)
        if isinstance(data, dict) and isinstance(data_schema, dict):
            self.check(data_schema, data, pointer + "/data")
            self.check_part_references(part_id, data, pointer, data_schema)
        if part_id == self.ctx.part_of_block(BLOCK_TABS) and isinstance(data, dict):
            self.check_nested_parts(data, pointer, nested)

    def check_nested_parts(self, data, pointer, nested):
        tabs = data.get("tabs")
        if not isinstance(tabs, list):
            return
        for tab_index, tab in enumerate(tabs):
            if not isinstance(tab, dict):
                continue
            panel_parts = tab.get("panel_parts")
            if not isinstance(panel_parts, list):
                continue
            for part_index, inner in enumerate(panel_parts):
                inner_pointer = "%s/data/tabs/%d/panel_parts/%d" % (pointer, tab_index, part_index)
                if not isinstance(inner, dict):
                    continue
                if inner.get("part") == self.ctx.part_of_block(BLOCK_TABS) or nested:
                    self.add("E-PART-NESTED-TABS", inner_pointer,
                             "タブ部品の中へさらにタブ部品を入れられない (ネストは 1 段まで)")
                    continue
                self.check_part(inner, inner_pointer, nested=True)

    def check_part_references(self, part_id, data, pointer, data_schema):
        props = data_schema.get("properties") or {}
        for key, sub in props.items():
            target = self.deref(sub).get("x_references") if isinstance(sub, dict) else None
            if not target:
                continue
            collection = target.split("[")[0]
            value = data.get(key)
            if not isinstance(value, str) or not value:
                continue
            known = self.ctx.reference_ids.get(collection, set())
            self.ctx.used_references.setdefault(collection, set()).add(value)
            if value not in known:
                self.add("E-REF-DANGLING", pointer + "/data/" + key,
                         "参照先が %s に存在しない" % collection)
        del part_id

    # ---- section_kind 追加検査 --------------------------------------------

    def check_kind_constraints(self, section, parts, pointer, kind, attrs):
        max_items = attrs.get(ATTR_MAX_ITEMS)
        if isinstance(max_items, int):
            for part in parts:
                if not isinstance(part, dict):
                    continue
                data = part.get("data")
                if not isinstance(data, dict):
                    continue
                for key in ("rows", "cards"):
                    items = data.get(key)
                    if isinstance(items, list) and len(items) > max_items:
                        self.add("E-SECTIONKIND-MAXITEMS", pointer,
                                 "この section_kind の列挙上限 %d 件を超える (実際 %d 件)"
                                 % (max_items, len(items)))
        if attrs.get(ATTR_FORBID_ROW_DETAIL):
            rows_part = self.ctx.part_of_block(BLOCK_ROWS)
            for part in parts:
                if not isinstance(part, dict) or part.get("part") != rows_part:
                    continue
                for row in (part.get("data") or {}).get("rows") or []:
                    if isinstance(row, dict) and row.get("sub") is not None:
                        self.add("E-SECTIONKIND-ROWDETAIL", pointer,
                                 "この section_kind では行の詳細 (sub) を書けない")
        if kind == KIND_ACTION_ITEMS:
            actions_part = self.ctx.part_of_block(BLOCK_ACTIONS)
            for part in parts:
                if not isinstance(part, dict) or part.get("part") != actions_part:
                    continue
                for row in (part.get("data") or {}).get("rows") or []:
                    if not isinstance(row, dict):
                        continue
                    if is_blank(row.get("owner")) or is_blank(row.get("due")):
                        self.add("E-SECTIONKIND-CONSTRAINT", pointer,
                                 "この section_kind では全ての行に担当と期限が要る")
        if kind == KIND_KNOWN_UNKNOWN_NEXT:
            trio_part = self.ctx.part_of_block(BLOCK_TRIO)
            for part in parts:
                if not isinstance(part, dict) or part.get("part") != trio_part:
                    continue
                cards = (part.get("data") or {}).get("cards")
                if not isinstance(cards, list):
                    continue
                if len(cards) != self.ctx.trio_card_count:
                    self.add("E-SECTIONKIND-CONSTRAINT", pointer,
                             "この section_kind では 3 分割 (カード %d 件) が要る"
                             % self.ctx.trio_card_count)
                for card in cards:
                    if isinstance(card, dict) and is_blank(card.get("note_key")):
                        self.add("E-SECTIONKIND-CONSTRAINT", pointer,
                                 "この section_kind では全カードにメモ機構への結線 (note_key) が要る")
        if kind == KIND_DECISIONS:
            checklist_part = self.ctx.part_of_block(BLOCK_CHECKLIST)
            for part in parts:
                if not isinstance(part, dict) or part.get("part") != checklist_part:
                    continue
                for row in (part.get("data") or {}).get("rows") or []:
                    if isinstance(row, dict) and not isinstance(row.get("decided"), bool):
                        self.add("E-SECTIONKIND-CONSTRAINT", pointer,
                                 "この section_kind では決定済みかどうかを曖昧にできない")
        if kind == KIND_SOURCES:
            cards_part = self.ctx.part_of_block(BLOCK_CARDS)
            for part in parts:
                if not isinstance(part, dict) or part.get("part") != cards_part:
                    continue
                cards = (part.get("data") or {}).get("cards")
                if isinstance(cards, list) and not any(
                        isinstance(card, dict) and not is_blank(card.get("footnote"))
                        for card in cards):
                    self.add("E-SECTIONKIND-CONSTRAINT", pointer,
                             "この section_kind では少なくとも 1 件に出所の表記が要る")
        if kind == KIND_ANTICIPATED_QA:
            accordion_part = self.ctx.part_of_block(BLOCK_ACCORDION)
            for part in parts:
                if not isinstance(part, dict) or part.get("part") != accordion_part:
                    continue
                items = (part.get("data") or {}).get("items")
                if not isinstance(items, list):
                    continue
                if len(items) < self.ctx.qa_min_items:
                    self.add("E-SECTIONKIND-CONSTRAINT", pointer,
                             "この section_kind では %d 件以上の問答が要る" % self.ctx.qa_min_items)
                for item in items:
                    if isinstance(item, dict) and item.get("open") is True:
                        self.add("E-SECTIONKIND-CONSTRAINT", pointer,
                                 "この section_kind では冒頭の情報量を増やさないため全件を畳む")
        if kind == KIND_HANDSON:
            handson_part = self.ctx.part_of_block(BLOCK_HANDSON)
            if not any(isinstance(part, dict) and part.get("part") == handson_part
                       for part in parts):
                self.add("E-SECTIONKIND-HANDSON", pointer,
                         "この section_kind ではその場で手を動かす手順部品が 1 件以上要る")
        if kind == KIND_AGENDA_TIMEBOX:
            self.check_timebox(section, parts, pointer)
        if kind == KIND_CAPABILITY_EXPLAINER:
            self.check_slots(parts, pointer)

    def check_timebox(self, section, parts, pointer):
        total = 0
        complete = True
        rows_part = self.ctx.part_of_block(BLOCK_ROWS)
        for part in parts:
            if not isinstance(part, dict) or part.get("part") != rows_part:
                continue
            for row in (part.get("data") or {}).get("rows") or []:
                if not isinstance(row, dict):
                    continue
                minutes = parse_minutes(row.get("time"))
                if minutes is None:
                    complete = False
                    self.add("E-SECTIONKIND-CONSTRAINT", pointer,
                             "この section_kind では全ての行に時間が要る")
                else:
                    total += minutes
        declared = parse_minutes(section.get("duration"))
        if complete and declared is not None and total != declared:
            self.add("E-TIMEBOX-SUM", pointer,
                     "行の時間の総和 %d 分がセクションの所要時間 %d 分と一致しない"
                     % (total, declared))

    def check_slots(self, parts, pointer):
        zones = [value for value in
                 (self.schema["$defs"]["part"]["properties"]["slot"].get("enum") or [])
                 if isinstance(value, str)]
        slots = []
        missing = False
        for index, part in enumerate(parts):
            if not isinstance(part, dict):
                continue
            slot = part.get("slot")
            if not isinstance(slot, str) or not slot:
                self.add("E-CAPABILITY-SLOT-MISSING", "%s/parts/%d" % (pointer, index),
                         "この section_kind では全ての部品に区画ラベルが要る")
                missing = True
                continue
            if slot in zones:
                slots.append(zones.index(slot))
        if missing or not slots:
            return
        ordered = all(slots[i] <= slots[i + 1] for i in range(len(slots) - 1))
        covered = set(slots) == set(range(len(zones)))
        if not ordered or not covered:
            self.add("E-CAPABILITY-SLOT-ORDER", pointer,
                     "この section_kind では %s の順に各区画 1 件以上を置く" % " → ".join(zones))

    # ---- 横断検査 ----------------------------------------------------------

    def check_section_ids(self, sections):
        seen = set()
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            section_id = section.get("id")
            if not isinstance(section_id, str):
                continue
            if section_id in seen:
                self.add("E-SECTION-ID-DUP", "/sections/%d/id" % index,
                         "セクション id が重複している")
            seen.add(section_id)

    def section_role(self, section):
        role = section.get("role")
        return role if isinstance(role, str) and role else self.ctx.default_role

    def check_ties(self, cfg, sections):
        focus = cfg.get("focus_theme") if isinstance(cfg.get("focus_theme"), list) else []
        task_ids = set()
        for task in cfg.get("target_tasks") or []:
            if isinstance(task, dict) and isinstance(task.get("id"), str):
                task_ids.add(task["id"])
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            pointer = "/sections/%d" % index
            ties = section.get("ties_to")
            ties = ties if isinstance(ties, list) else []
            has_goal = False
            has_task = False
            for tie_index, tie in enumerate(ties):
                if not isinstance(tie, str):
                    continue
                tie_pointer = "%s/ties_to/%d" % (pointer, tie_index)
                if tie == TIE_GOAL:
                    has_goal = True
                elif tie.startswith(TIE_FOCUS_PREFIX):
                    raw = tie[len(TIE_FOCUS_PREFIX):]
                    if raw.isdigit() and int(raw) < len(focus):
                        has_goal = True
                    else:
                        self.add("E-TIES-DANGLING", tie_pointer,
                                 "参照先の主題枠が存在しない")
                elif tie.startswith(TIE_TASK_PREFIX):
                    if tie[len(TIE_TASK_PREFIX):] in task_ids:
                        has_task = True
                    else:
                        self.add("E-TIES-DANGLING", tie_pointer,
                                 "参照先の具体業務が存在しない")
            if self.section_role(section) != self.ctx.appendix_role:
                if not has_goal:
                    self.add("E-SECTION-UNTIED-GOAL", pointer,
                             "本編のセクションは全体ゴールか主題枠のどちらかへ紐づける")
                if not has_task:
                    self.add("E-SECTION-UNTIED-TASK", pointer,
                             "本編のセクションは受講者の具体業務へ紐づける")

    def check_roles(self, cfg, sections):
        del cfg
        roles = []
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                roles.append(None)
                continue
            pointer = "/sections/%d" % index
            role = self.section_role(section)
            roles.append(role)
            kind = section.get("section_kind")
            if kind is None:
                kind = self.ctx.default_section_kind
            required_role = (self.ctx.kind_attributes.get(kind) or {}).get(ATTR_REQUIRED_ROLE)
            if isinstance(required_role, str) and role != required_role:
                self.add("E-SECTION-ROLE-CONFLICT", pointer,
                         "この section_kind は %s にしか置けない" % required_role)
        for index, role in enumerate(roles):
            if role != self.ctx.appendix_role:
                continue
            if any(later == self.ctx.default_role for later in roles[index + 1:]):
                self.add("E-APPENDIX-ORDER", "/sections/%d" % index,
                         "付録のセクションは全ての本編セクションより後ろに置く")

    def check_attainment(self, cfg, sections):
        levels = self.ctx.attainment_levels
        declared = cfg.get("attainment_level")
        if declared not in levels:
            return
        declared_index = levels.index(declared)
        reached = False
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            step = section.get("attainment_step")
            if step not in levels:
                continue
            step_index = levels.index(step)
            if step_index > declared_index:
                self.add("E-ATTAINMENT-OVERRUN", "/sections/%d/attainment_step" % index,
                         "宣言した到達段を超えている")
            if step_index == declared_index:
                reached = True
        if not reached:
            self.add("E-ATTAINMENT-UNREACHED", "/attainment_level",
                     "宣言した到達段に届くセクションが 1 件も無い")

    def check_durations(self, sections):
        share_kinds = {slug: attrs[ATTR_MIN_DURATION_SHARE]
                       for slug, attrs in self.ctx.kind_attributes.items()
                       if isinstance(attrs.get(ATTR_MIN_DURATION_SHARE), (int, float))}
        used = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            kind = section.get("section_kind")
            if kind is None:
                kind = self.ctx.default_section_kind
            used.append(kind)
        if not any(kind in share_kinds for kind in used):
            return
        total = 0
        per_kind = {}
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            kind = section.get("section_kind")
            if kind is None:
                kind = self.ctx.default_section_kind
            minutes = parse_minutes(section.get("duration"))
            if minutes is None:
                if section.get("duration") is None:
                    self.add("E-DURATION-INCOMPLETE", "/sections/%d/duration" % index,
                             "所要時間の下限割合を持つ種別がある資料では全セクションに所要時間が要る")
                continue
            total += minutes
            per_kind[kind] = per_kind.get(kind, 0) + minutes
        for slug, minimum in sorted(share_kinds.items()):
            if slug not in used:
                continue
            share = (per_kind.get(slug, 0) / total) if total > 0 else 0
            if share < minimum:
                pointer = "/sections"
                for index, section in enumerate(sections):
                    kind = section.get("section_kind") if isinstance(section, dict) else None
                    if kind is None:
                        kind = self.ctx.default_section_kind
                    if kind == slug:
                        pointer = "/sections/%d" % index
                        break
                self.add("E-SECTIONKIND-DURATION-SHARE", pointer,
                         "この種別の所要時間が全体に占める割合 %.3f が下限 %s を下回る"
                         % (share, minimum))

    def check_glossary_scopes(self, cfg, sections):
        seen = {}
        glossary = cfg.get("glossary")
        if isinstance(glossary, list):
            for entry in glossary:
                if isinstance(entry, dict) and isinstance(entry.get("term"), str):
                    seen.setdefault(nfc(entry["term"]), "/glossary")
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            entries = section.get("glossary")
            if not isinstance(entries, list):
                continue
            for entry_index, entry in enumerate(entries):
                if not isinstance(entry, dict) or not isinstance(entry.get("term"), str):
                    continue
                key = nfc(entry["term"])
                pointer = "/sections/%d/glossary/%d" % (index, entry_index)
                if key in seen:
                    self.add("E-GLOSSARY-DUP", pointer,
                             "同じ用語が %s でも宣言されている" % seen[key])
                else:
                    seen[key] = pointer

    def check_references(self, cfg):
        assets = cfg.get("assets")
        if not isinstance(assets, list):
            return
        used = self.ctx.used_references.get("assets", set())
        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                continue
            asset_id = asset.get("id")
            if isinstance(asset_id, str) and asset_id not in used:
                self.add("W-REF-UNUSED", "/assets/%d" % index,
                         "どの部品からも参照されていない")

    def check_text_bodies(self, cfg, report_overflow):
        text_part = self.ctx.part_of_block(BLOCK_TEXT)
        sections = cfg.get("sections")
        if not isinstance(sections, list):
            return
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            parts = section.get("parts")
            if not isinstance(parts, list):
                continue
            for part_index, part in enumerate(parts):
                if not isinstance(part, dict) or part.get("part") != text_part:
                    continue
                body = (part.get("data") or {}).get("body")
                if not isinstance(body, str):
                    continue
                pointer = "/sections/%d/parts/%d" % (index, part_index)
                if report_overflow and len(body) > self.ctx.body_limit:
                    self.add("E-TEXT-OVERFLOW", pointer,
                             "本文が上限 %d 文字を超える (実際 %d 文字)"
                             % (self.ctx.body_limit, len(body)))
                if long_sentence_count(body) >= LONG_SENTENCE_COUNT:
                    self.add("W-SENTENCE-LONG", pointer,
                             "%d 文字を超える文が %d つ以上ある"
                             % (LONG_SENTENCE_CHARS, LONG_SENTENCE_COUNT))


# ---------------------------------------------------------------------------
# 文脈 (データ正本から引いた値だけを持つ)
# ---------------------------------------------------------------------------


class Context(object):

    def __init__(self, root, schema, schema_path, sections_catalog, parts_catalog,
                 catalog, catalog_path, c23, visual_policy=None):
        self.root = root
        self.schema = schema
        self.schema_path = schema_path
        self.sections_catalog = sections_catalog
        self.parts_catalog = parts_catalog
        self.catalog = catalog
        self.catalog_path = catalog_path
        self.c23 = c23

        self.load_visual_policy(visual_policy)

        self.default_section_kind = sections_catalog.get("default")

        self.kind_attributes = {}
        for kind in sections_catalog.get("section_kinds") or []:
            if isinstance(kind, dict) and isinstance(kind.get("slug"), str):
                self.kind_attributes[kind["slug"]] = kind

        self.part_scopes = {}
        self.part_by_block = {}
        for part in parts_catalog.get("parts") or []:
            if isinstance(part, dict) and isinstance(part.get("id"), str):
                self.part_scopes[part["id"]] = part.get("section_scope")
                block_type = part.get("data_block_type")
                if isinstance(block_type, str):
                    if block_type in self.part_by_block:
                        raise LaunchAbort(
                            "部品カタログの data_block_type が一意でない: %s" % block_type)
                    self.part_by_block[block_type] = part["id"]
        missing = [b for b in REQUIRED_BLOCK_TYPES if b not in self.part_by_block]
        if missing:
            raise LaunchAbort(
                "部品カタログに追加検査規則が使う block.type が無い: %s" % ", ".join(missing))

        self.part_data = {key: value for key, value in (schema["$defs"]["part_data"]).items()
                          if isinstance(value, dict)}

        props = schema["properties"]
        section_props = schema["$defs"]["section"]["properties"]
        self.schema_version = props["schema_version"]["const"]
        self.must_remember_max_default = props["must_remember_max"]["default"]
        self.notes_enabled_default = props["notes_enabled"]["default"]
        self.default_role = section_props["role"]["default"]
        role_enum = section_props["role"]["enum"]
        self.appendix_role = [value for value in role_enum if value != self.default_role][0]
        self.prior_levels = props["prior_knowledge_level"]["enum"]
        self.no_prior_knowledge_value = self.prior_levels[0]
        self.presentation_orders = props["presentation_order"]["enum"]
        self.detail_levels = props["detail_level"]["enum"]
        self.evidence_depths = props["evidence_depth"]["enum"]
        self.attainment_levels = schema["$defs"]["attainment_level"]["enum"]
        self.trio_card_count = self.part_data[self.part_of_block(BLOCK_TRIO)]["properties"]["cards"]["maxItems"]
        self.qa_min_items = self.part_data[self.part_of_block(BLOCK_ACCORDION)]["properties"]["items"]["minItems"] + 1

        self.reference_ids = {}
        self.used_references = {}
        self.body_limit = FALLBACK_BODY_MAX_CHARS

    def part_of_block(self, block_type):
        """block.type からカタログの部品 id を引く (id 語彙をここに持たないため)。"""
        part_id = self.part_by_block.get(block_type)
        if part_id is None:
            raise LaunchAbort("部品カタログに block.type=%s の部品が無い" % block_type)
        return part_id

    def collect_reference_ids(self, cfg):
        self.reference_ids = {}
        self.used_references = {}
        for collection in ("assets", "attachments", "diagrams"):
            ids = set()
            for entry in cfg.get(collection) or []:
                if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                    ids.add(entry["id"])
            self.reference_ids[collection] = ids

    def theme_tokens(self, cfg):
        theme = cfg.get("theme")
        tokens_dir = self.root / TOKENS_RELDIR
        if not isinstance(theme, str) or not theme:
            names = sorted(path.stem for path in tokens_dir.glob("*.json")) \
                if tokens_dir.is_dir() else []
            theme = names[0] if names else None
        if not theme:
            return {}
        path = tokens_dir / ("%s.json" % theme)
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def load_visual_policy(self, policy):
        """図解密度と散文量の閾値を正本から引く。読めなければ fallback で進む。

        方針ファイルの欠落で検証そのものを止めない。閾値は編集方針であって
        構成データの妥当性ではないためである (fail-soft)。
        """
        if not isinstance(policy, dict):
            policy = {}
        ids = ((policy.get("visual_parts") or {}).get("ids")
               if isinstance(policy.get("visual_parts"), dict) else None)
        if isinstance(ids, list) and all(isinstance(x, str) for x in ids) and ids:
            self.visual_part_ids = set(ids)
        else:
            self.visual_part_ids = set(FALLBACK_VISUAL_PART_IDS)

        thresholds = policy.get("thresholds")
        thresholds = thresholds if isinstance(thresholds, dict) else {}

        def number(key, field, fallback):
            entry = thresholds.get(key)
            if isinstance(entry, dict):
                value = entry.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return value
            return fallback

        self.min_visual_per_section = number(
            "min_visual_parts_per_main_section", "value", FALLBACK_MIN_VISUAL_PER_SECTION)
        self.min_diagram_ratio = number(
            "min_diagrams_per_main_sections", "value", FALLBACK_MIN_DIAGRAM_RATIO)
        self.min_diagram_floor = number(
            "min_diagrams_per_main_sections", "floor", FALLBACK_MIN_DIAGRAM_FLOOR)
        self.max_text_ratio = number(
            "max_text_parts_ratio_per_section", "value", FALLBACK_MAX_TEXT_RATIO)
        self.max_text_run = number(
            "max_consecutive_text_parts", "value", FALLBACK_MAX_TEXT_RUN)
        self.load_micro_copy(policy.get("micro_copy"))
        self.load_layering(policy.get("layering"))
        self.load_opening(policy.get("opening"))

    def load_opening(self, opening):
        """冒頭の置き方の上限を正本から引く (fail-soft)。"""
        opening = opening if isinstance(opening, dict) else {}
        caps = ((opening.get("hero_fields") or {}).get("max_chars")
                if isinstance(opening.get("hero_fields"), dict) else None)
        limits = {}
        if isinstance(caps, dict):
            for name, value in caps.items():
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    limits[name] = value
        self.hero_field_limits = limits or dict(FALLBACK_HERO_FIELD_LIMITS)

        total = opening.get("hero_total")
        total = total if isinstance(total, dict) else {}
        cap = total.get("max_chars")
        self.hero_total_chars = (
            cap if isinstance(cap, int) and not isinstance(cap, bool) and cap > 0
            else FALLBACK_HERO_TOTAL_CHARS)
        names = total.get("counted_fields")
        self.hero_total_fields = (
            tuple(n for n in names if isinstance(n, str))
            if isinstance(names, list) and names else tuple(FALLBACK_HERO_TOTAL_FIELDS))

    def load_layering(self, layering):
        """要点層と詳細層の切り分け規則を正本から引く (fail-soft)。

        層の順序そのものは schema の attainment_level enum が持つ。ここは
        「どの段を要点層とみなすか」と「詳細層に要る部品」だけを引く。
        """
        layering = layering if isinstance(layering, dict) else {}
        enum = (((self.schema.get("$defs") or {}).get("attainment_level") or {})
                .get("enum"))
        self.attainment_order = (
            {name: rank for rank, name in enumerate(enum)}
            if isinstance(enum, list) else {})

        step = layering.get("summary_step")
        self.summary_step = (step if isinstance(step, str) and step in self.attainment_order
                             else FALLBACK_SUMMARY_STEP)

        ids = ((layering.get("detail_parts") or {}).get("ids")
               if isinstance(layering.get("detail_parts"), dict) else None)
        self.detail_part_ids = (
            set(x for x in ids if isinstance(x, str))
            if isinstance(ids, list) and ids else set(FALLBACK_DETAIL_PART_IDS))

    def load_micro_copy(self, micro):
        """図解・カード内の 1 要素あたり文字数上限を正本から引く (fail-soft)。

        フィールド名から上限を引く辞書へ畳んで持つ。役割の別は診断文でしか
        使わないため、辞書の値は (役割名, 上限) の対にする。
        """
        micro = micro if isinstance(micro, dict) else {}
        limits = {}
        roles = micro.get("roles")
        if isinstance(roles, list):
            for entry in roles:
                if not isinstance(entry, dict):
                    continue
                role = entry.get("role")
                cap = entry.get("max_chars")
                fields = entry.get("fields")
                if not (isinstance(role, str) and isinstance(fields, list)):
                    continue
                if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
                    continue
                for name in fields:
                    if isinstance(name, str):
                        limits[name] = (role, cap)
        self.micro_copy_limits = limits or dict(FALLBACK_MICRO_COPY_LIMITS)

        exempt_parts = ((micro.get("exempt_parts") or {}).get("ids")
                        if isinstance(micro.get("exempt_parts"), dict) else None)
        self.micro_copy_exempt_parts = (
            set(x for x in exempt_parts if isinstance(x, str))
            if isinstance(exempt_parts, list) else set(FALLBACK_MICRO_COPY_EXEMPT_PARTS))

        exempt_fields = ((micro.get("exempt_fields") or {}).get("names")
                         if isinstance(micro.get("exempt_fields"), dict) else None)
        self.micro_copy_exempt_fields = (
            set(x for x in exempt_fields if isinstance(x, str))
            if isinstance(exempt_fields, list) else set(FALLBACK_MICRO_COPY_EXEMPT_FIELDS))

    def resolve_body_limit(self, cfg):
        """本文上限。detail_level の明示があれば水準別の値を、無ければ既定値を使う。"""
        limits = self.theme_tokens(cfg).get("text_limits")
        limits = limits if isinstance(limits, dict) else {}
        default_limit = limits.get("block_body_max_chars")
        if not isinstance(default_limit, int) or isinstance(default_limit, bool):
            default_limit = FALLBACK_BODY_MAX_CHARS
        explicit = cfg.get("detail_level")
        if isinstance(explicit, str) and explicit in self.detail_levels:
            by_level = limits.get("block_body_max_chars_by_detail_level")
            if isinstance(by_level, dict):
                value = by_level.get(explicit)
                if isinstance(value, int) and not isinstance(value, bool):
                    return value
        return default_limit


# ---------------------------------------------------------------------------
# 正規化
# ---------------------------------------------------------------------------


def unique_cont_id(base, taken):
    candidate = "%s%s" % (base, CONT_SUFFIX)
    serial = 2
    while candidate in taken:
        candidate = "%s%s%d" % (base, CONT_SUFFIX, serial)
        serial += 1
    return candidate


def drop_empty_optionals(container, keys):
    """任意の集合フィールドの「0 件」を 1 つの形へ畳む。

    空配列とキー無しの 2 通りが正規化後も残ると、C20 の逆抽出はどちらか
    片方にしか合わせられず、round-trip が中身ではなく形の差だけで
    DIFFERENT になる。正規化済み構成データの正本の形は「0 件ならキーを
    出さない」。document の glossary は必須フィールド (E-FIELD-MISSING
    /glossary) なので、ここでは畳まない。
    """
    for key in keys:
        value = container.get(key)
        if isinstance(value, list) and not value:
            del container[key]


def normalize_config(cfg, ctx, today, diags):
    data = json.loads(json.dumps(cfg))
    data["schema_version"] = ctx.schema_version

    parts = parse_date_parts(data.get("date"))
    if parts is not None:
        data["date"] = format_date(*parts)
        date_source = "config"
    else:
        data["date"] = format_date(today.year, today.month, today.day)
        date_source = "default-today"

    slug = data.get("subject_slug")
    if is_blank(slug):
        derived = derive_slug(data.get("title") or "")
        if not derived:
            diags.append(("E-SLUG-UNDERIVABLE", "/subject_slug",
                          "title から subject_slug を導出できないので明示指定が要る"))
            return None, 0
        data["subject_slug"] = derived

    entry = ctx.c23.resolve(ctx.catalog, data.get("doc_type"))
    data["doc_type"] = entry["slug"]

    order = data.get("presentation_order")
    if isinstance(order, str) and order in ctx.presentation_orders:
        order_source = "explicit"
    else:
        prior = data.get("prior_knowledge_level")
        index = 1 if prior == ctx.prior_levels[-1] else 0
        data["presentation_order"] = ctx.presentation_orders[index]
        order_source = "derived-from-prior-knowledge"

    defaults = ctx.c23.granularity_defaults(ctx.catalog, data["doc_type"])
    granularity_sources = {}
    for field, domain in (("detail_level", ctx.detail_levels),
                          ("evidence_depth", ctx.evidence_depths)):
        value = data.get(field)
        if isinstance(value, str) and value in domain:
            granularity_sources[field] = "explicit"
        else:
            data[field] = defaults.get(field)
            granularity_sources[field] = "preset-default"

    if "must_remember_max" not in data or data.get("must_remember_max") is None:
        data["must_remember_max"] = ctx.must_remember_max_default
    if "notes_enabled" not in data or data.get("notes_enabled") is None:
        data["notes_enabled"] = ctx.notes_enabled_default

    fold_count = 0
    open_at_detailed = data.get("detail_level") == ctx.detail_levels[-1]
    for section in data.get("sections") or []:
        if not isinstance(section, dict):
            continue
        if is_blank(section.get("role")):
            section["role"] = ctx.default_role
        if is_blank(section.get("section_kind")):
            section["section_kind"] = ctx.default_section_kind
        normalize_section_duration(section, ctx)
        normalize_part_defaults(section, ctx)
        drop_empty_optionals(section, ("glossary",))
        fold_count += fold_section(section, ctx, ctx.body_limit, open_at_detailed)

    drop_empty_optionals(data, ("assets", "attachments", "diagrams"))

    data["provenance"] = {
        "normalized_by": NORMALIZED_BY,
        "schema_version": ctx.schema_version,
        "catalog_sha256": ctx.c23.catalog_sha256(ctx.catalog_path),
        "date_source": date_source,
        "presentation_order_source": order_source,
        "detail_level_source": granularity_sources["detail_level"],
        "evidence_depth_source": granularity_sources["evidence_depth"],
        "text_fold_count": fold_count,
    }
    return data, fold_count


def normalize_section_duration(section, ctx):
    minutes = parse_minutes(section.get("duration"))
    if minutes is not None:
        section["duration"] = "%d分" % minutes
        return
    if section.get("duration") is not None:
        return
    if section.get("section_kind") != KIND_AGENDA_TIMEBOX:
        return
    total = 0
    found = False
    rows_part = ctx.part_of_block(BLOCK_ROWS)
    for part in section.get("parts") or []:
        if not isinstance(part, dict) or part.get("part") != rows_part:
            continue
        for row in (part.get("data") or {}).get("rows") or []:
            if not isinstance(row, dict):
                continue
            row_minutes = parse_minutes(row.get("time"))
            if row_minutes is None:
                return
            total += row_minutes
            found = True
    if found:
        section["duration"] = "%d分" % total


def normalize_part_defaults(section, ctx):
    handson_part = ctx.part_of_block(BLOCK_HANDSON)
    live_demo_default = ctx.part_data[handson_part]["properties"]["live_demo"]["default"]
    for part in section.get("parts") or []:
        if not isinstance(part, dict):
            continue
        if part.get("part") == handson_part and isinstance(part.get("data"), dict):
            if "live_demo" not in part["data"] or part["data"]["live_demo"] is None:
                part["data"]["live_demo"] = live_demo_default


def fold_section(section, ctx, limit, open_flag):
    parts = section.get("parts")
    if not isinstance(parts, list):
        return 0
    text_part = ctx.part_of_block(BLOCK_TEXT)
    accordion_part = ctx.part_of_block(BLOCK_ACCORDION)
    taken = {part.get("id") for part in parts if isinstance(part, dict)}
    folded = 0
    result = []
    for part in parts:
        result.append(part)
        if not isinstance(part, dict) or part.get("part") != text_part:
            continue
        data = part.get("data")
        if not isinstance(data, dict):
            continue
        body = data.get("body")
        if not isinstance(body, str) or len(body) <= limit:
            continue
        chunks = split_body(body, limit)
        data["body"] = chunks[0]
        new_id = unique_cont_id(part.get("id"), taken)
        taken.add(new_id)
        result.append({
            "part": accordion_part,
            "id": new_id,
            "data": {"items": [{"summary": FOLD_SUMMARY, "body": chunk, "open": open_flag}
                               for chunk in chunks[1:]]},
        })
        folded += 1
    section["parts"] = result
    return folded


def write_output(path, payload):
    directory = str(Path(path).parent)
    handle, temp_name = tempfile.mkstemp(dir=directory, prefix=".hb-normalize-", suffix=".tmp")
    try:
        os.write(handle, payload.encode("utf-8"))
        os.close(handle)
        handle = None
        os.replace(temp_name, str(path))
    finally:
        if handle is not None:
            os.close(handle)
        if os.path.exists(temp_name):
            os.unlink(temp_name)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="handout 構成データを検証し、--normalize 指定時は正規化済みデータを書き出す")
    parser.add_argument("--config", required=True, help="構成データ JSON のパス")
    parser.add_argument("--schema", default=None, help="スキーマ正本のパス (既定は plugin 同梱)")
    parser.add_argument("--strict", action="store_true", help="警告も違反として扱う")
    parser.add_argument("--normalize", action="store_true", help="正規化済み構成データを書き出す")
    parser.add_argument("--out", default=None, help="--normalize の出力先 (--config と別実体)")
    parser.add_argument("--today", default=None, help="既定日付の縫い目 (YYYY-MM-DD)")
    parser.add_argument("--catalog", default=None, help="用途語彙正本のパス")
    return parser


def resolve_today(value):
    if value is None:
        return datetime.date.today()
    match = TODAY_ARG_RE.match(value.strip())
    if not match:
        raise LaunchAbort("--today は YYYY-MM-DD で指定する: %s" % value)
    year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if not calendar_valid(year, month, day):
        raise LaunchAbort("--today が暦に存在しない日付: %s" % value)
    return datetime.date(year, month, day)


def read_config_text(path):
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise LaunchAbort("--config を読めない: %s (%s)" % (path, exc))
    text = raw.decode("utf-8-sig", errors="strict")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def emit_diagnostics(diags):
    for code, pointer, message in diags:
        sys.stderr.write("%s %s %s\n" % (code, pointer, message))


def run(args):
    config_path = Path(args.config)
    if not config_path.is_file():
        raise LaunchAbort("--config のパスが存在しないか読めない: %s" % config_path)

    if args.normalize and not args.out:
        raise LaunchAbort("--normalize には --out が要る (標準出力へ構成データを流さない)")

    out_path = None
    if args.out:
        out_path = Path(args.out)
        if not out_path.parent.is_dir():
            raise LaunchAbort("--out の親ディレクトリが存在しない: %s" % out_path.parent)
        if os.path.realpath(str(out_path)) == os.path.realpath(str(config_path)):
            raise LaunchAbort("--out を --config と同一実体にできない (in-place 書き換えの禁止)")

    today = resolve_today(args.today)

    root = resolve_root()
    c23 = load_preset_module(root)

    schema_path = Path(args.schema) if args.schema else root / SCHEMA_RELPATH
    schema = read_json_file(schema_path, "スキーマ正本")
    sections_catalog = read_json_file(root / SECTIONS_RELPATH, "section_kind 正本")
    parts_catalog = read_json_file(root / PARTS_RELPATH, "部品カタログ正本")
    # 図解方針は欠落しても検証を止めない (Context 側の fallback へ落とす)。
    try:
        visual_policy = read_json_file(root / VISUAL_POLICY_RELPATH, "図解方針正本")
    except Exception:
        visual_policy = None

    try:
        catalog_path = c23.resolve_catalog_path(args.catalog)
        catalog = c23.load_catalog(catalog_path)
    except c23.LaunchError as exc:
        raise LaunchAbort("; ".join(exc.diagnostics))
    except c23.CatalogError as exc:
        emit_diagnostics([("E-CATALOG-INVALID", "/", line) for line in exc.diagnostics])
        return EXIT_VIOLATION

    ctx = Context(root, schema, schema_path, sections_catalog, parts_catalog,
                  catalog, catalog_path, c23, visual_policy)

    catalog_ids = {part_id for part_id in ctx.part_scopes}
    if catalog_ids != set(ctx.part_data):
        raise LaunchAbort("部品カタログと data 形定義表の id 集合が一致しない (二重名簿)")

    text = read_config_text(config_path)
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        line = getattr(exc, "lineno", 0)
        column = getattr(exc, "colno", 0)
        emit_diagnostics([("E-CONFIG-PARSE", "/",
                           "構成データが JSON として parse できない (line %d, column %d): %s"
                           % (line, column, getattr(exc, "msg", exc)))])
        return EXIT_VIOLATION
    if not isinstance(parsed, dict):
        emit_diagnostics([("E-CONFIG-SHAPE", "/", "構成データの最上位はオブジェクトである必要がある")])
        return EXIT_VIOLATION

    cfg = normalize_strings(parsed)
    ctx.collect_reference_ids(cfg)
    ctx.body_limit = ctx.resolve_body_limit(cfg)

    checker = Checker(ctx)
    diags = checker.run(cfg)
    checker.check_text_bodies(cfg, report_overflow=not args.normalize)

    errors = [entry for entry in diags if entry[0].startswith("E-")]
    warnings = [entry for entry in diags if not entry[0].startswith("E-")]
    if errors:
        emit_diagnostics(diags)
        return EXIT_VIOLATION
    if warnings and args.strict:
        emit_diagnostics(diags)
        return EXIT_VIOLATION

    if args.normalize:
        normalize_diags = []
        normalized, _ = normalize_config(cfg, ctx, today, normalize_diags)
        if normalized is None:
            emit_diagnostics(warnings + normalize_diags)
            return EXIT_VIOLATION
        payload = json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        write_output(out_path, payload)
        summary_source = normalized
    else:
        summary_source = cfg

    emit_diagnostics(warnings)

    sections = summary_source.get("sections") or []
    part_count = sum(len(section.get("parts") or [])
                     for section in sections if isinstance(section, dict))
    sys.stdout.write(
        "OK handout-config: sections=%d parts=%d glossary=%d doc_type=%s date=%s warnings=%d\n"
        % (len(sections), part_count, len(summary_source.get("glossary") or []),
           summary_source.get("doc_type"), summary_source.get("date") or "-", len(warnings)))
    return EXIT_OK


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except LaunchAbort as exc:
        sys.stderr.write("%s\n" % exc)
        return EXIT_LAUNCH


if __name__ == "__main__":
    sys.exit(main())

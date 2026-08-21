#!/usr/bin/env python3
# /// script
# name: extract-handout-config
# version: 0.1.0
# purpose: C20 生成済みの単一 HTML から構成データを逆抽出し、round-trip の等価性を判定する
# inputs:
#   - argv: --html <path> [--out <path>] [--compare <path>] [--report <path>] [--strict-fidelity]
# outputs:
#   - file: --out の構成データ / --report の抽出レポート
#   - stdout: 復元不能・heuristic 採用の警告行
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out / --json-report / --config-out で明示された path のみ
# ///
# -*- coding: utf-8 -*-
"""C20 extract-handout-config.py — 生成済み HTML から構成データを逆抽出する。

契約の正本は plugin-plans/guide-doc-generator/briefs/script-brief-C20.json
(argv / exit_codes / algorithm / parsing_strategy / roundtrip_granularity /
renderer_marker_requirements / heuristic_fallback / fail_semantics)。

設計上の要点は 3 つ。

1. C11 render-handout.py の逆関数である。値の出所は data-hb-* マーカーだけで、
   見た目のクラス名や本文の位置から意味情報を推測しない (heuristic_fallback の
   never_guessed)。復元できない箇所は捏造せず null にして人間へ返す。
2. 部品 id 語彙の単一正本は config/handout-parts.json (P03 Y-05)。本 script は
   部品 id を一切列挙しない。heuristic 経路の照合表は data_block_type を鍵に持ち、
   「部品 id → 根拠クラス名」はカタログとの join で導出する
   (裁定: schemas/PART-CLASS-MAP-RESOLUTION.md)。照合表とカタログの過不足は
   起動時に双方向で報告する。
3. 正規化は C12 validate-handout-config.py を importlib で読み込んで共有する。
   等価判定の基準を 2 つに増やさないため、自前の正規化を持たない。
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_LAUNCH = 2

ROOT_ENV_VARS = ("HB_ROOT", "CLAUDE_PLUGIN_ROOT")
MANIFEST_RELPATH = Path(".claude-plugin") / "plugin.json"
MANIFEST_NAME = "guide-doc-generator"

PARTS_RELPATH = Path("config") / "handout-parts.json"
SCHEMA_RELPATH = Path("schemas") / "handout-config.schema.json"
CONTRACT_RELPATH = Path("schemas") / "ROUNDTRIP-CONTRACT.md"
C12_RELPATH = Path("scripts") / "validate-handout-config.py"
C12_MODULE_NAME = "hb_c20_normalizer_c12"

# 診断コード (script-brief-C20.json#stderr)
E_UNRECOVERABLE = "E-EXTRACT-UNRECOVERABLE"
W_HEURISTIC = "W-EXTRACT-HEURISTIC"
W_OPTIONAL = "W-EXTRACT-OPTIONAL"
W_CATALOG_DRIFT = "W-EXTRACT-CATALOG-DRIFT"
E_ROUNDTRIP_DIFF = "E-ROUNDTRIP-DIFF"
E_HTML_MALFORMED = "E-HTML-MALFORMED"

# --------------------------------------------------------------------------
# heuristic 経路の照合表 (script-brief-C20.json#heuristic_fallback.class_map)
#
# 鍵は部品 id ではなくカタログの data_block_type である (PART-CLASS-MAP-RESOLUTION.md)。
# 「どの部品 id が存在するか」も「どの id がどの block type か」もカタログ側が持ち、
# 本 script が持つのは「その block type をクラス名から見分ける根拠」だけになる。
# 部品 id を鍵にすると、写像を持つ側が必然的に id を列挙してしまい第 2 の名簿へ
# 退化する。C11 render-handout.py の PART_DATA_PROJECTIONS / C17
# verify-handout-a11y-print.py の load_part_ids_by_block_type() と同じ形。
#
# 本文の受け皿となる block type (FALLBACK_BLOCK_TYPE) だけは根拠がクラス名ではなく
# 「どの型にも当たらない本文のタグ」なのでタグ名を値に持つ。最後に置くのは受け皿
# だからで、走査順に意味がある (build_part_class_map がこの順序を保つ)。
#
# 値はそれ以外すべてクラス名である。裸の <img> のような「タグだけを根拠にした同定」
# は行わない。クラス名を持たない画像は本文中の装飾 (アイコン・ロゴ) と区別できず、
# 部品として拾うと構造を捏造することになるため (never_guessed と同じ理由)。
# --------------------------------------------------------------------------
BLOCK_TYPE_CLASS_MAP = {
    "steps": ("step-row",),
    "trio": ("trio", "trio-card"),
    "table": ("table-wrap",),
    "versus": ("vs-grid",),
    "features": ("pop-features", "duo", "pop-feature"),
    "map": ("map-grid", "map-detail"),
    "checklist": ("pop-row",),
    "accordion": ("acc",),
    "prompt": ("prompt-box",),
    "download": ("dl-btn",),
    "tabs": ("prompt-panel",),
    "flow": ("flow", "flow-step"),
    "chips": ("pop-chips",),
    "action-items": ("action-items", "ai-row"),
    "handson": ("handson", "hs-row"),
    "diagram": ("diagram",),
    "image": ("asset", "asset-img"),
    "text": ("p", "div"),
}
# 照合表のうち「本文の受け皿」として使う行 (クラス名照合ではなくタグ名照合)
FALLBACK_BLOCK_TYPE = "text"

VOID_ELEMENTS = frozenset((
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
))
RAW_TEXT_ELEMENTS = frozenset(("script", "style"))
HEADING_ELEMENTS = frozenset(("h1", "h2", "h3", "h4", "h5", "h6"))
PREFORMATTED_ELEMENT = "pre"
SECTION_ELEMENT = "section"

# 生成 chrome をクラス名で切り落とす二重防御 (A3)
CHROME_CLASSES = ("pop-header", "pop-bottom")
CHROME_CLASS_PREFIXES = ("memo",)

ATTR_GENERATED = "data-hb-generated"
ATTR_PART = "data-hb-part"
ATTR_PART_ID = "data-hb-part-id"
ATTR_FIELD = "data-hb-field"
PART_REF = "#/$defs/part"
ATTR_PART_DATA = "data-hb-part-data"
ATTR_ENTRIES = "data-hb-entries"
ATTR_PANEL_FOR = "data-hb-panel-for"
ATTR_SECTION_KIND = "data-hb-section-kind"
ATTR_SECTION_ROLE = "data-hb-section-role"
ATTR_TIES_TO = "data-hb-ties-to"
ATTR_ATTAINMENT_STEP = "data-hb-attainment-step"
ATTR_KEY = "data-hb-key"
ATTR_OWNER = "data-hb-owner"
ATTR_DUE = "data-hb-due"
ATTR_SRC = "data-hb-src"
ATTR_ASSET_ID = "data-hb-asset-id"
ATTR_ASSET_ALT = "data-hb-asset-alt"
ATTR_ASSET_CAPTION = "data-hb-asset-caption"
ATTR_ASSET_ROLE = "data-hb-asset-role"
ATTR_ATTACHMENT_ID = "data-hb-attachment-id"
ATTR_FILENAME = "data-hb-filename"
ATTR_MIME = "data-hb-mime"
ATTR_FALLBACK_HINT = "data-hb-fallback-hint"
ATTR_MEDIA_RECORD = "data-hb-media-record"
ATTR_ASSET_KIND = "data-hb-asset-kind"
ATTR_DIAGRAM_ID = "data-hb-diagram-id"
ATTR_DIAGRAM_TITLE = "data-hb-diagram-title"
ATTR_DIAGRAM_RECORD_DATA = "data-hb-diagram-record-data"
ATTR_DIAGRAM_PATTERN = "data-hb-diagram-pattern"
ATTR_DIAGRAM_DATA = "data-hb-diagram-data"
ATTR_GLOSSARY_TERM = "data-hb-glossary-term"
ATTR_GLOSSARY_PLAIN = "data-hb-glossary-plain"
ATTR_GLOSSARY_SCOPE = "data-hb-glossary-scope"

DOC_META_ATTRS = (
    ("schema_version", "data-hb-schema-version", True),
    ("doc_type", "data-hb-doc-type", True),
    ("subject_slug", "data-hb-subject-slug", True),
    # data-hb-theme ではなく data-hb-config-theme を読む。前者は既定値の解決を
    # 経た実効テーマなので、著者が theme 欄を書かなかった資料でも値が入り、
    # 読み戻すと「書いていない」が「書いた」に化ける。
    ("theme", "data-hb-config-theme", False),
    # 日付は紙面に出さない (C11 build_doc_head)。可視要素ではなく root 属性で運ぶ。
    ("date", "data-hb-date", True),
    ("reader", "data-hb-meta-reader", True),
    ("prior_knowledge_level", "data-hb-meta-knowledge", True),
    ("essential_problem", "data-hb-meta-problem", True),
    ("presentation_order", "data-hb-presentation-order", True),
    ("detail_level", "data-hb-detail-level", True),
    ("evidence_depth", "data-hb-evidence-depth", True),
)

# 属性 1 本で運ぶ非文字列の文書メタ (値の型は schema が正本)。
DOC_TYPED_ATTRS = (
    ("must_remember_max", "data-hb-must-remember-max", "integer", True),
    # ROUNDTRIP-CONTRACT.md /notes_enabled = marker。既定値の充填に任せると
    # 著者が false を選んだ資料が true へ化けるため、値そのものを読む。
    ("notes_enabled", "data-hb-notes-enabled", "boolean", True),
)

# data-hb-field の値 → 構成データのフィールド名 (文書スコープ / セクションスコープ)
DOC_FIELDS = (
    ("title", "title", True),
    ("purpose", "purpose", True),
    ("background", "background", True),
    ("goal", "goal", True),
    ("lead", "lead", False),
    ("attainment_level", "attainment_level", True),
)
# 同じ data-hb-field 値が複数回現れ、文書順の配列として復元する項目 (R21)。
DOC_LIST_FIELDS = (
    # 達成目標チップ。1 チップ 1 マーカーで刻まれるため文書順の配列として戻る。
    ("goal_chips", "goal_chips", False),
    ("focus_theme", "focus_theme", True),
    ("must_remember", "must_remember", True),
    ("no_need_to_remember", "no_need_to_remember", True),
)
# 上 2 表のうち、著者が書かなければ C11 が要素そのものを描かない項目。
# マーカーが無いのは「復元できなかった」ではなく「その資料には無かった」であり、
# gap として数えない。数えると、完全に復元できた資料が毎回 W-EXTRACT-OPTIONAL を
# 吐き、警告が『見なくてよいもの』へ退化する (schema でも required に無い)。
# required=False との違いは、False が「常に刻まれるはずの任意項目」を指すこと。
ABSENCE_IS_NOT_A_GAP = frozenset({"lead", "goal_chips"})
# 反復要素の配列。id は data-hb-key が、表示文言は要素本文が運ぶ。
DOC_ENTRY_FIELDS = (
    ("target_task", "target_tasks", "label", True),
)
# 反復要素のうち、復元するのが key だけの配列。表示されている文言は別の正本
# (config/handout-vocabulary.json) が持っており、読み戻すと構成データ側に
# 同じ表記の第 2 の出所ができる。note だけは語彙に無い著者記述なので本文から拾う。
DOC_KEY_ONLY_ENTRY_FIELDS = (
    ("prerequisite_connector", "prerequisite_connectors", "connector",
     "prerequisite_connector_note", "note", False),
)
SECTION_FIELDS = (
    ("heading", "heading", True),
    ("section_goal", "goal", True),
    ("lead_line", "lead_line", True),
    ("judgment_axis", "judgment_axis", True),
)

GLOSSARY_SCOPE_SECTION = "section"

# 再生成される chrome であって構成データではないため、値を持たずキーだけ残す
# notes_enabled は DOC_TYPED_ATTRS で読むようになったためここには残さない
# (残すと後段の一括 null 埋めが読み取った値を上書きしてしまう)。
UNMARKED_DOCUMENT_KEYS = ()

DIGIT_RUN_RE = re.compile(r"\d+")

# 裁定表 (schemas/ROUNDTRIP-CONTRACT.md) の fenced JSON から属性名を拾うための形。
# マーカー名そのものはここへ書かない (書けば裁定表と二名簿になる)。
CONTRACT_FENCE_OPEN = "```json"
CONTRACT_FENCE_CLOSE = "```"
CONTRACT_ADJUDICATIONS_KEY = "adjudications"
CONTRACT_MARKER_DECISION = "marker"
DATA_ATTR_RE = re.compile(r"data-hb-[a-z0-9]+(?:-[a-z0-9]+)*")

ABSENT = object()


class LaunchAbort(Exception):
    """起動側の不正 (exit 2)。"""


class MalformedHtml(Exception):
    """親子が確定できない HTML (exit 1)。"""

    def __init__(self, line, detail):
        super().__init__(detail)
        self.line = line
        self.detail = detail


# ---------------------------------------------------------------------------
# 実体解決とデータ正本
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
    """plugin root の実体解決 (環境変数 → manifest 照合 → __file__ 相対)。"""
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


def fenced_json_blocks(text):
    """``` で括られた JSON ブロックを出現順に返す (裁定表の機械可読部の取り出し)。"""
    blocks = []
    buffer = None
    for line in text.splitlines():
        stripped = line.strip()
        if buffer is None:
            if stripped == CONTRACT_FENCE_OPEN:
                buffer = []
            continue
        if stripped == CONTRACT_FENCE_CLOSE:
            blocks.append("\n".join(buffer))
            buffer = None
            continue
        buffer.append(line)
    return blocks


def load_roundtrip_contract(root):
    """round-trip 裁定表 (schemas/ROUNDTRIP-CONTRACT.md の fenced JSON) を読む。

    裁定表は「どの項目を著者記述として復元するか」の正本であり、本 script は
    そこから導出するだけで写しを持たない。読めない場合は fail-closed にする
    (既定へ退避すると chrome 内側の著者記述が黙って消える側へ倒れるため)。
    """
    path = Path(root) / CONTRACT_RELPATH
    if not path.is_file():
        raise LaunchAbort("round-trip 裁定表が実在しない: %s" % path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LaunchAbort("round-trip 裁定表を読めない: %s (%s)" % (path, exc))
    for block in fenced_json_blocks(text):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get(CONTRACT_ADJUDICATIONS_KEY), list):
            return data
    raise LaunchAbort("round-trip 裁定表に %s を持つ JSON ブロックが無い: %s"
                      % (CONTRACT_ADJUDICATIONS_KEY, path))


def authored_data_markers(contract):
    """読み飛ばしから外す『著者データマーカー』の属性名を裁定表から導出する。

    出所は script-brief-C20.json#renderer_marker_requirements.chrome_boundary の
    authored_data_markers (「その集合は marker_source_of_truth の裁定表から導出する」)。
    したがって decision=marker の裁定が挙げる marker 文字列から属性名を機械抽出する。
    列挙をここへ書き写すと裁定表と二名簿になり、裁定が増えたときに黙って取りこぼす。

    data-hb-generated 自身は読み飛ばしを宣言する側の属性であって著者記述を運ばない
    ため除く (chrome_boundary: 「除外されないのは data-hb-generated 自身と、純粋な
    提示属性のみ」)。
    """
    names = set()
    for entry in contract.get(CONTRACT_ADJUDICATIONS_KEY) or []:
        if not isinstance(entry, dict) or entry.get("decision") != CONTRACT_MARKER_DECISION:
            continue
        marker = entry.get("marker")
        if isinstance(marker, str):
            names.update(DATA_ATTR_RE.findall(marker))
    names.discard(ATTR_GENERATED)
    if not names:
        raise LaunchAbort("round-trip 裁定表から著者データマーカーを 1 件も導出できない "
                          "(decision=%s の裁定が無いか marker が空)" % CONTRACT_MARKER_DECISION)
    return frozenset(names)


def load_c12_module(root):
    """C12 を importlib で読み込む。正規化を再実装しないための単一正本委譲。"""
    candidates = [Path(root) / C12_RELPATH,
                  Path(__file__).resolve().parent / C12_RELPATH.name]
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location(C12_MODULE_NAME, str(path))
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return None


class Catalog(object):
    """部品カタログ (id 語彙の単一正本) の読み手。"""

    def __init__(self, data, path):
        self.path = path
        parts = data.get("parts")
        if not isinstance(parts, list):
            raise LaunchAbort("部品カタログの parts が配列でない: %s" % path)
        self.scopes = {}
        self.block_types = {}
        for entry in parts:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                self.scopes[entry["id"]] = entry.get("section_scope")
                self.block_types[entry["id"]] = entry.get("data_block_type")
        markers = data.get("non_part_structure_markers") or {}
        values = markers.get("values") if isinstance(markers, dict) else None
        self.structure_markers = set(values) if isinstance(values, list) else set()

    def ids(self):
        return set(self.scopes)

    def in_section_ids(self):
        return {pid for pid, scope in self.scopes.items() if scope != "document"}

    def is_in_section(self, part_id):
        return part_id in self.scopes and self.scopes[part_id] != "document"


def part_ids_by_block_type(catalog):
    """data_block_type -> 部品 id の逆引き。同じ block type の先頭 1 件を採る。"""
    by_block = {}
    for part_id, block_type in catalog.block_types.items():
        if isinstance(block_type, str) and block_type:
            by_block.setdefault(block_type, part_id)
    return by_block


def build_part_class_map(catalog):
    """『部品 id → 根拠クラス名』をカタログとの join で導出する。

    本 script は部品 id を列挙しない。id は必ずカタログ由来であり、この関数の
    返り値は導出値である (第 2 の名簿にならない)。BLOCK_TYPE_CLASS_MAP の
    宣言順を保つので、本文の受け皿は走査の最後に来る。
    """
    by_block = part_ids_by_block_type(catalog)
    table = {}
    for block_type, evidences in BLOCK_TYPE_CLASS_MAP.items():
        part_id = by_block.get(block_type)
        if part_id is not None:
            table[part_id] = evidences
    return table


def _part_class_map_at_import():
    """import 時点のカタログで join を 1 度組む (モジュール内省用の既定値)。

    実行経路は main() が読んだカタログから作り直すので、この値の欠落は挙動へ
    影響しない。カタログが引けないときの fail-closed 判断は main() が行う。
    """
    try:
        path = resolve_root() / PARTS_RELPATH
        data = json.loads(path.read_text(encoding="utf-8"))
        return build_part_class_map(Catalog(data, path))
    except (OSError, ValueError, LaunchAbort, AttributeError):
        return {}


def self_check_catalog(catalog):
    """照合表とカタログの過不足を双方向に列挙する (Y-05)。

    鍵が data_block_type になったので、両側とも「その時点で実在する識別子」で
    報告する。カタログ側の過剰は部品 id で、照合表側の過剰は block type で名指す
    (カタログから消えた部品の id は、もうどこにも残っていないため名指せない)。
    """
    lines = []
    in_section = catalog.in_section_ids()
    block_types = catalog.block_types
    claimed = {block_types.get(pid) for pid in in_section}
    for block_type in sorted(bt for bt in BLOCK_TYPE_CLASS_MAP if bt not in claimed):
        lines.append("%s /parts block.type=%s は照合表の鍵にあるがカタログのどの部品も要求していない"
                     % (W_CATALOG_DRIFT, block_type))
    for part_id in sorted(pid for pid in in_section
                          if block_types.get(pid) not in BLOCK_TYPE_CLASS_MAP):
        lines.append("%s /parts %s はカタログにあるが照合表に鍵が無い (heuristic 経路なし)"
                     % (W_CATALOG_DRIFT, part_id))
    return lines


# 『部品 id → 根拠クラス名』の照合表。リテラルではなくカタログとの join の結果で
# あり、この名前が指す語彙の正本は config/handout-parts.json 側にある。
PART_CLASS_MAP = _part_class_map_at_import()


# ---------------------------------------------------------------------------
# HTML の木構築 (parsing_strategy)
# ---------------------------------------------------------------------------


class Node(object):
    __slots__ = ("tag", "attrs", "children", "line")

    def __init__(self, tag, attrs, line):
        self.tag = tag
        self.attrs = attrs
        self.children = []
        self.line = line

    def attr(self, name):
        value = self.attrs.get(name)
        return value if isinstance(value, str) else None

    def classes(self):
        value = self.attrs.get("class")
        return value.split() if isinstance(value, str) else []

    def elements(self):
        return [child for child in self.children if isinstance(child, Node)]


class TreeBuilder(HTMLParser):
    """スタックを積み降ろしして {tag, attrs, children} の木を作る最小の構築器。"""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = Node("#document", {}, 0)
        self.stack = [self.root]
        self.failure = None

    def _fail(self, line, detail):
        if self.failure is None:
            self.failure = (line, detail)

    def _make(self, tag, attrs):
        pairs = {}
        for name, value in attrs:
            if name not in pairs:
                pairs[name] = value if value is not None else ""
        return Node(tag, pairs, self.getpos()[0])

    def handle_starttag(self, tag, attrs):
        node = self._make(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(self._make(tag, attrs))

    def handle_endtag(self, tag):
        if tag in VOID_ELEMENTS:
            return
        if len(self.stack) < 2:
            self._fail(self.getpos()[0], "対応する開始タグの無い終了タグ: %s" % tag)
            return
        if self.stack[-1].tag != tag:
            self._fail(self.getpos()[0],
                       "終了タグ %s が開いている要素 %s と対応しない"
                       % (tag, self.stack[-1].tag))
            return
        self.stack.pop()

    def handle_data(self, data):
        current = self.stack[-1]
        if current.tag in RAW_TEXT_ELEMENTS:
            return
        current.children.append(data)

    def handle_comment(self, data):
        return

    def handle_decl(self, decl):
        return

    def handle_pi(self, data):
        return


def build_tree(text):
    builder = TreeBuilder()
    try:
        builder.feed(text)
        builder.close()
    except Exception as exc:                      # html.parser 自身の破綻も同じ扱い
        raise MalformedHtml(builder.getpos()[0], "HTML を解析できない: %s" % exc)
    if builder.failure is not None:
        raise MalformedHtml(builder.failure[0], builder.failure[1])
    if len(builder.stack) > 1:
        open_node = builder.stack[-1]
        raise MalformedHtml(open_node.line,
                            "閉じていない要素がある: %s" % open_node.tag)
    return builder.root


# ---------------------------------------------------------------------------
# テキストの取り出し (text_handling)
# ---------------------------------------------------------------------------


def nfc(text):
    return unicodedata.normalize("NFC", text)


def raw_text(node):
    chunks = []

    def walk(current):
        for child in current.children:
            if isinstance(child, str):
                chunks.append(child)
            else:
                walk(child)

    walk(node)
    return "".join(chunks)


def collapsed_text(node):
    return " ".join(raw_text(node).split())


def find_preformatted(node):
    if node.tag == PREFORMATTED_ELEMENT:
        return node
    for child in node.elements():
        found = find_preformatted(child)
        if found is not None:
            return found
    return None


def text_value(node):
    """<pre> 配下は原文のまま、それ以外は連続空白を畳んで trim してから NFC。"""
    pre = find_preformatted(node)
    if pre is not None:
        return nfc(raw_text(pre))
    return nfc(collapsed_text(node))


# ---------------------------------------------------------------------------
# 生成 chrome の切り落とし (A3)
# ---------------------------------------------------------------------------


def is_generated_chrome(node):
    if node.attr(ATTR_GENERATED) == "true":
        return True
    for name in node.classes():
        if name in CHROME_CLASSES:
            return True
        for prefix in CHROME_CLASS_PREFIXES:
            if name == prefix or name.startswith(prefix + "-"):
                return True
    return False


def has_authored_marker(node, authored_markers):
    return any(name in node.attrs for name in authored_markers)


def prune_chrome(node, authored_markers):
    """生成 chrome を走査対象から外す (A3)。

    読み飛ばしの単位は部分木そのものではなく『著者データマーカーを持つノードを
    抜いた部分木』である (chrome_boundary.rule)。したがって chrome に出会っても
    そこで走査を止めず、内側の著者データマーカーだけを穴として拾い上げる。
    枠は捨てるので、拾ったノードは chrome があった位置 — すなわち最も近い非 chrome
    の祖先の直下 — へそのまま繰り上がる。

    クラス名による二重防御の経路も同じ規定に従う (chrome_boundary.class_name_fallback:
    「クラス名は宣言より弱い根拠であり、宣言を覆さない」)。is_generated_chrome が
    両経路を 1 つの判定にまとめているため、ここで経路を分けない。
    """
    kept = []
    for child in node.children:
        if isinstance(child, str):
            kept.append(child)
            continue
        if is_generated_chrome(child):
            kept.extend(perforate_chrome(child, authored_markers))
            continue
        prune_chrome(child, authored_markers)
        kept.append(child)
    node.children = kept


def perforate_chrome(node, authored_markers):
    """読み飛ばす chrome 部分木から、残すべきノードだけを文書順に取り出す。

    著者データマーカーを持つノードに出会ったら、その要素と値の復元に必要な子孫を
    そのまま残す (chrome_boundary.rule)。残した領域の内側は通常の走査へ戻すので、
    そこへさらに data-hb-generated が現れれば再び読み飛ばし対象になる
    (chrome_boundary.nesting の「判定は最も内側の宣言が勝つ」)。
    マーカーを持たないノードは従来どおり捨てる — 残すのは穴だけで、chrome 由来の
    テキストも部品も外へ出さない (AC-C20-07)。
    """
    if has_authored_marker(node, authored_markers):
        prune_chrome(node, authored_markers)
        return [node]
    kept = []
    for child in node.elements():
        kept.extend(perforate_chrome(child, authored_markers))
    return kept


# ---------------------------------------------------------------------------
# 抽出本体
# ---------------------------------------------------------------------------


class Extractor(object):

    def __init__(self, catalog, part_properties, part_required=None):
        self.catalog = catalog
        self.part_properties = part_properties
        # 必須の文字列項目名。heuristic 経路で本文へ落とす対象を宣言側から
        # 決めるために持つ (部品 id もキー名も script に書き下さない)。
        self.part_required = part_required or {}
        # heuristic 経路の照合表は起動時のカタログとの join で作る (導出値)。
        self.part_class_map = build_part_class_map(catalog)
        self.fallback_part_id = part_ids_by_block_type(catalog).get(FALLBACK_BLOCK_TYPE)
        self.required_gaps = []
        self.optional_gaps = []
        self.heuristics = []
        self.exact_parts = 0
        self.heuristic_parts = 0
        self.assets = []
        self.attachments = []
        self.diagrams = []
        self.report_sections = []
        self._asset_ids = set()
        self._attachment_ids = set()
        self._diagram_ids = set()

    # ---- 記録 ----------------------------------------------------------

    def gap(self, pointer, reason, required=True):
        if required:
            self.required_gaps.append({"pointer": pointer, "reason": reason})
        else:
            self.optional_gaps.append({"pointer": pointer, "reason": reason})

    def heuristic(self, pointer, part_id, evidence):
        self.heuristics.append({"pointer": pointer, "part": part_id, "evidence": evidence})

    def marked_value(self, node, attr, pointer, field_label, required=True):
        value = node.attr(attr) if node is not None else None
        if value is None or value == "":
            self.gap(pointer, "%s を運ぶマーカー %s が無い" % (field_label, attr), required)
            return None
        return nfc(value)

    # ---- 文書レベル ----------------------------------------------------

    def extract(self, root):
        html_node = self.find_element(root, "html")
        if html_node is None:
            raise MalformedHtml(1, "<html> 要素が見つからず文書レベルのメタを確定できない")

        config = {}
        for field, attr, required in DOC_META_ATTRS:
            value = self.marked_value(html_node, attr, "/" + field, field, required)
            if value is None and not required:
                # 任意項目は「空」と「書いていない」を区別する。空文字を
                # 書き戻すと、著者が書かなかった欄が書いた欄に化ける。
                continue
            config[field] = value

        for field, attr, kind, required in DOC_TYPED_ATTRS:
            raw = html_node.attr(attr)
            if raw is None or raw == "":
                config[field] = None
                self.gap("/" + field, "%s を運ぶマーカー %s が無い" % (field, attr), required)
            else:
                config[field] = self.coerce_scalar(nfc(raw), [kind])

        found_nodes = {}
        self.collect_field_nodes(html_node, found_nodes, stop_at_section=True)
        for marker, field, required in DOC_FIELDS:
            nodes = found_nodes.get(marker)
            if nodes:
                config[field] = text_value(nodes[0])
            elif field in ABSENCE_IS_NOT_A_GAP:
                # キー自体を置かない。null を置くと「書いていない」が「null と
                # 書いた」になり、schema の型検査 (string) が読み戻し側だけで落ちる。
                pass
            else:
                config[field] = None
                self.gap("/" + field, "%s を運ぶ %s=\"%s\" が無い" % (field, ATTR_FIELD, marker),
                         required)

        for marker, field, required in DOC_LIST_FIELDS:
            nodes = found_nodes.get(marker)
            if nodes is None:
                if field not in ABSENCE_IS_NOT_A_GAP:
                    config[field] = None
                    self.gap("/" + field,
                             "%s を運ぶ %s=\"%s\" が無い" % (field, ATTR_FIELD, marker),
                             required)
            else:
                config[field] = [text_value(n) for n in nodes]

        for marker, field, text_field, required in DOC_ENTRY_FIELDS:
            nodes = found_nodes.get(marker)
            if nodes is None:
                config[field] = None
                self.gap("/" + field, "%s を運ぶ %s=\"%s\" が無い" % (field, ATTR_FIELD, marker),
                         required)
                continue
            entries = []
            for entry_node in nodes:
                key = entry_node.attr(ATTR_KEY)
                if key is None or key == "":
                    self.gap("/" + field, "%s の id を運ぶ %s が無い" % (field, ATTR_KEY), required)
                    continue
                entries.append({"id": nfc(key), text_field: text_value(entry_node)})
            config[field] = entries

        for (marker, field, key_field, note_marker, note_field,
             required) in DOC_KEY_ONLY_ENTRY_FIELDS:
            nodes = found_nodes.get(marker)
            if nodes is None:
                # 任意配列は assets 等と同じ扱いにする。無いときに null を置くと
                # 「キーごと書かなかった構成データ」と差が出て round-trip が
                # DIFFERENT になる。穴としても数えない — 著者が 1 件も書かなかった
                # 資料と、印が落ちた資料を、この位置では区別できないうえ、前者が
                # 通常であり後者は round-trip 比較が差分として捕らえる。
                if required:
                    config[field] = None
                    self.gap("/" + field,
                             "%s を運ぶ %s=\"%s\" が無い" % (field, ATTR_FIELD, marker), True)
                continue
            entries = []
            for entry_node in nodes:
                key = entry_node.attr(ATTR_KEY)
                if key is None or key == "":
                    self.gap("/" + field, "%s の id を運ぶ %s が無い" % (field, ATTR_KEY), required)
                    continue
                entry = {key_field: nfc(key)}
                note_node = self.first_descendant_field(entry_node, note_marker)
                if note_node is not None:
                    entry[note_field] = text_value(note_node)
                entries.append(entry)
            config[field] = entries

        for key in UNMARKED_DOCUMENT_KEYS:
            config[key] = None

        doc_glossary = []
        self.collect_glossary(html_node, doc_glossary, {}, stop_at_section=True)
        config["glossary"] = doc_glossary

        sections = []
        seen_ids = {}
        for index, node in enumerate(self.find_sections(html_node)):
            sections.append(self.extract_section(node, index, seen_ids))
        config["sections"] = sections

        # assets / attachments / diagrams は任意フィールドであり、正規化済み構成データ
        # (C12 --normalize の出力) では 0 件のときキー自体が現れない。空でも [] を出すと
        # 「キーなし」対「空配列」の差だけで round-trip が DIFFERENT になるため、
        # 非空のときだけ出す。glossary は必須フィールド (C12 が E-FIELD-MISSING を出す)
        # なので空でも常に出す。
        for key, value in (("assets", self.assets),
                           ("attachments", self.attachments),
                           ("diagrams", self.diagrams)):
            if value:
                config[key] = value
        return config

    def find_element(self, node, tag):
        for child in node.elements():
            if child.tag == tag:
                return child
            found = self.find_element(child, tag)
            if found is not None:
                return found
        return None

    def find_sections(self, node):
        """文書順に <section> を集める (入れ子の section は外側だけを見る)。"""
        result = []
        for child in node.elements():
            if child.tag == SECTION_ELEMENT:
                result.append(child)
            else:
                result.extend(self.find_sections(child))
        return result

    def collect_field_nodes(self, node, found, stop_at_section):
        """data-hb-field の値ごとに、印を持つ要素を文書順で全件集める。

        collect_fields が先頭 1 件しか残さないのは走査対象がスカラ項目だけ
        だった名残で、focus_theme / must_remember / target_tasks のように
        同じ印が複数回現れる配列項目は 2 件目以降が落ちる。要素そのものを
        返すのは、target_tasks の id が本文でなく data-hb-key にあるためである。
        """
        for child in node.elements():
            if stop_at_section and child.tag == SECTION_ELEMENT:
                continue
            marker = child.attr(ATTR_FIELD)
            if marker is not None:
                found.setdefault(marker, []).append(child)
            self.collect_field_nodes(child, found, stop_at_section)

    def first_descendant_field(self, node, marker):
        """要素の内側から data-hb-field=marker を 1 件だけ引く。

        but 書きは項目の内側に置かれるため、文書全体を走査すると別の項目の
        but 書きを拾う。親を限定した探索が要る。
        """
        for child in node.elements():
            if child.attr(ATTR_FIELD) == marker:
                return child
            found = self.first_descendant_field(child, marker)
            if found is not None:
                return found
        return None

    def collect_fields(self, node, found, stop_at_section):
        for child in node.elements():
            if stop_at_section and child.tag == SECTION_ELEMENT:
                continue
            marker = child.attr(ATTR_FIELD)
            if marker is not None and marker not in found:
                found[marker] = text_value(child)
            self.collect_fields(child, found, stop_at_section)

    def collect_glossary(self, node, document_bucket, section_buckets, stop_at_section,
                         section_id=None):
        for child in node.elements():
            if stop_at_section and child.tag == SECTION_ELEMENT:
                continue
            term = child.attr(ATTR_GLOSSARY_TERM)
            if term is not None:
                plain = child.attr(ATTR_GLOSSARY_PLAIN)
                entry = {"term": nfc(term), "plain": nfc(plain) if plain is not None else None}
                if plain is None:
                    self.gap("/glossary", "用語 %s の言い換えを運ぶ %s が無い"
                             % (term, ATTR_GLOSSARY_PLAIN))
                scope = child.attr(ATTR_GLOSSARY_SCOPE)
                if scope == GLOSSARY_SCOPE_SECTION and section_id is not None:
                    section_buckets.setdefault(section_id, []).append(entry)
                else:
                    document_bucket.append(entry)
            self.collect_glossary(child, document_bucket, section_buckets, stop_at_section,
                                  section_id)

    # ---- セクション ----------------------------------------------------

    def extract_section(self, node, index, seen_ids):
        pointer = "/sections/%d" % index
        section = {}
        section_id = node.attr("id")
        if section_id is None or section_id == "":
            section_id = None
            self.gap(pointer + "/id", "section の id 属性が無い")
        elif section_id in seen_ids:
            self.gap(pointer + "/id",
                     "section id が文書内で重複している: %s (どちらを採るか決めない)" % section_id)
        else:
            seen_ids[section_id] = index
        section["id"] = section_id

        found_fields = {}
        self.collect_section_fields(node, found_fields)
        for marker, field, required in SECTION_FIELDS:
            if marker in found_fields:
                section[field] = found_fields[marker]
            else:
                section[field] = None
                self.gap("%s/%s" % (pointer, field),
                         "%s を運ぶ %s=\"%s\" が無い" % (field, ATTR_FIELD, marker), required)

        kind = node.attr(ATTR_SECTION_KIND)
        if kind is None or kind == "":
            section["section_kind"] = None
            self.gap(pointer + "/section_kind",
                     "section_kind を運ぶ %s が無い" % ATTR_SECTION_KIND, False)
        else:
            section["section_kind"] = nfc(kind)

        # role / ties_to / attainment_step は C11 が section 要素の属性として出している
        # (render-handout.py:1967-1969)。既定値で埋めると appendix が本編扱いになる等の
        # 意味の変質を起こすため、無い場合は gap として残し推測しない。
        role = node.attr(ATTR_SECTION_ROLE)
        if role is None or role == "":
            section["role"] = None
            self.gap(pointer + "/role",
                     "role を運ぶ %s が無い" % ATTR_SECTION_ROLE, True)
        else:
            section["role"] = nfc(role)

        # ties_to は半角スペース区切りのトークン列 (ROUNDTRIP-CONTRACT
        # /sections/*/ties_to の required_serialization)。空文字列は空配列へ戻す。
        ties = node.attr(ATTR_TIES_TO)
        if ties is None:
            section["ties_to"] = None
            self.gap(pointer + "/ties_to",
                     "ties_to を運ぶ %s が無い" % ATTR_TIES_TO, True)
        else:
            section["ties_to"] = [nfc(t) for t in ties.split() if t]

        step = node.attr(ATTR_ATTAINMENT_STEP)
        if step is not None and step != "":
            section["attainment_step"] = nfc(step)

        section_glossary = []
        buckets = {}
        self.collect_glossary(node, section_glossary, buckets, stop_at_section=False,
                              section_id=section_id)
        # セクション配下では scope=document の宣言も section 側の記録として扱わない。
        # 宣言が 0 件のときはキー自体を出さない。C12 --normalize は空の
        # section glossary を充填しない (正規化済み構成データではキーが無い形が正)
        # ため、ここで [] を出すと「キーなし」対「空配列」の差だけで
        # round-trip が DIFFERENT になる。正本側の形に合わせる。
        section_terms = buckets.get(section_id)
        if section_terms:
            section["glossary"] = section_terms

        parts = []
        report_parts = []
        self.collect_parts(node, pointer, parts, report_parts, section_id)
        section["parts"] = parts
        self.report_sections.append({"id": section_id, "parts": report_parts})
        return section

    def collect_section_fields(self, node, found):
        for child in node.elements():
            if child.tag == SECTION_ELEMENT:
                continue
            marker = child.attr(ATTR_FIELD)
            if marker is not None and marker not in found:
                found[marker] = text_value(child)
            self.collect_section_fields(child, found)

    # ---- 部品 ----------------------------------------------------------

    def collect_parts(self, node, section_pointer, parts, report_parts, section_id):
        for child in node.elements():
            if child.tag == SECTION_ELEMENT:
                continue
            marker = child.attr(ATTR_PART)
            if marker is not None:
                if marker in self.catalog.structure_markers:
                    self.collect_parts(child, section_pointer, parts, report_parts, section_id)
                    continue
                pointer = "%s/parts/%d" % (section_pointer, len(parts))
                if not self.catalog.is_in_section(marker):
                    self.gap(pointer,
                             "カタログに無いかセクション外の部品種別: %s" % marker)
                    continue
                part = self.build_part(child, marker, pointer, section_id, len(parts))
                parts.append(part)
                report_parts.append({"id": part["id"], "part": marker, "fidelity": "exact"})
                self.exact_parts += 1
                continue

            if child.attr(ATTR_FIELD) is not None or child.tag in HEADING_ELEMENTS:
                self.collect_section_children_only(child, section_pointer, parts,
                                                   report_parts, section_id)
                continue

            guessed, evidence = self.guess_part(child)
            if guessed is None:
                self.collect_parts(child, section_pointer, parts, report_parts, section_id)
                continue
            pointer = "%s/parts/%d" % (section_pointer, len(parts))
            if not self.catalog.is_in_section(guessed):
                self.gap(pointer, "カタログに無いかセクション外の部品種別: %s" % guessed)
                continue
            part = self.build_part(child, guessed, pointer, section_id, len(parts),
                                   heuristic=True)
            parts.append(part)
            report_parts.append({"id": part["id"], "part": guessed, "fidelity": "heuristic"})
            self.heuristic_parts += 1
            self.heuristic(pointer, guessed, evidence)

    def collect_section_children_only(self, node, section_pointer, parts, report_parts,
                                      section_id):
        """フィールド担持要素と見出しは部品ではないが、配下は走査を続ける。"""
        self.collect_parts(node, section_pointer, parts, report_parts, section_id)

    def guess_part(self, node):
        """class_map による部品種別の推定 (heuristic_fallback)。"""
        names = node.classes()
        fallback = self.fallback_part_id
        for part_id, evidences in self.part_class_map.items():
            if part_id == fallback:
                continue
            for evidence in evidences:
                if evidence in names:
                    return part_id, evidence
        if fallback is not None and node.tag in self.part_class_map.get(fallback, ()):
            if collapsed_text(node) and not self.has_marked_descendant(node):
                return fallback, node.tag
        return None, None

    def has_marked_descendant(self, node):
        for child in node.elements():
            if child.attr(ATTR_PART) is not None or child.attr(ATTR_FIELD) is not None:
                return True
            if self.has_marked_descendant(child):
                return True
        return False

    def build_part(self, node, part_id, pointer, section_id, index, heuristic=False):
        part = {"part": part_id}
        given = node.attr(ATTR_PART_ID)
        if given:
            part["id"] = nfc(given)
        else:
            part["id"] = "%s-%d" % (section_id or "section", index + 1)
            self.gap(pointer + "/id", "部品 id を運ぶ %s が無い" % ATTR_PART_ID, False)
        part["data"] = self.build_part_data(node, part_id, pointer, heuristic)
        self.collect_media(node, pointer)
        return part

    def build_part_data(self, node, part_id, pointer, heuristic=False):
        """部品の data を **schema の properties を正本として** 組み立てる。

        以前は「配列らしきものが 1 本あるはず」と当て推量で入れ物を決め、
        表示テキストの連結を値に使っていたため、「1資料を開く手元で開く5分」
        のように連番・detail・time が混ざった文字列が構造データとして復元されて
        いた。ここでは形の宣言 (C12 の $defs.part_data) を読み、宣言された
        項目ごとに、対応するマーカーからだけ値を取る。宣言に無い項目は作らない
        ($defs 側は additionalProperties:false であり、発明したキーは必ず落ちる)。
        """
        props = self.part_properties.get(part_id)
        props = props if isinstance(props, dict) else {}

        blob = node.attr(ATTR_PART_DATA)
        if blob:
            # 図解部品は中身が C14 の SVG で、C11 の表示要素が無い。その場合だけ
            # 構成データそのものが属性で運ばれる (ROUNDTRIP-CONTRACT の marker)。
            try:
                parsed = json.loads(blob)
            except ValueError:
                self.gap(pointer + "/data", "%s が JSON として読めない" % ATTR_PART_DATA, True)
                parsed = None
            if isinstance(parsed, dict):
                return {k: v for k, v in parsed.items() if not props or k in props}

        data = {}
        required_names = self.part_required.get(part_id, ())
        for name, definition in props.items():
            if not isinstance(definition, dict):
                continue
            value = self.field_value(node, node, name, definition, pointer)
            if value is not None:
                data[name] = value
            elif name in required_names and not heuristic:
                # 印つき生成 HTML なのに必須項目の印が無い = 復元できない。
                # 黙って空の data を返すと「部品はあるが中身が消えた」資料が
                # 復元成功として出てしまうので、穴として見えるようにする。
                self.gap("%s/data/%s" % (pointer, name),
                         "%s を運ぶマーカーが無い" % name, True)

        if not props:
            body = text_value(node)
            if body:
                data["body"] = body
            return data

        if heuristic:
            # マーカーを 1 つも持たない手書き HTML では、表示テキストが値の
            # 唯一の実体である。宣言された項目を印からしか読まないと、部品
            # 種別だけ当たって中身が空の部品が復元される (実測: 参照 v1 相当の
            # 地の文が data={} になった)。推測の範囲を宣言側へ閉じ込めるため、
            # **必須の文字列項目が 1 つだけ空いている場合に限り**本文を入れる。
            # 2 つ以上あるとどちらへ入れるかは本文から決まらないので入れない。
            missing = [name for name in self.part_required.get(part_id, ())
                       if name not in data
                       and "string" in as_type_list(props.get(name, {}).get("type"))]
            if len(missing) == 1:
                body = text_value(node)
                if body:
                    data[missing[0]] = body
        return data

    # ---- 部品 data の項目 1 件を復元する -------------------------------

    def field_value(self, scope, part_node, name, definition, pointer):
        """宣言された 1 項目を、その型に応じたマーカーから復元する。

        型ごとに読む場所を変えるのは、HTML 上で無損失に運べる形が型で違うから
        である。文字列配列は空白区切りの属性 1 本へ潰すと空白を含む要素で境界が
        失われるので表示要素の側へ印を付ける。整数配列は空白を含まないので属性
        1 本で足りる。オブジェクト配列は 1 件が入れ子構造を持つので要素境界
        (data-hb-key) が要る。
        """
        kinds = definition.get("type")
        kinds = kinds if isinstance(kinds, list) else [kinds]
        attr_name = "data-hb-" + name.replace("_", "-")

        if "array" in kinds:
            items = definition.get("items")
            items = items if isinstance(items, dict) else {}
            item_kinds = items.get("type")
            item_kinds = item_kinds if isinstance(item_kinds, list) else [item_kinds]
            if items.get("$ref") == PART_REF:
                return None  # 入れ子部品は entry 側で組む (panel_parts)
            if "object" in item_kinds:
                container = self.entries_container(scope, name)
                if container is None:
                    return None
                return self.collect_entries(container, part_node, items, pointer)
            if "integer" in item_kinds:
                raw = scope.attr(attr_name)
                if raw is None:
                    return None
                return [int(t) for t in raw.split() if t.lstrip("-").isdigit()]
            return self.marked_texts(scope, name)

        if "object" in kinds:
            holder = self.find_marked(scope, name)
            if holder is None:
                return None
            sub = definition.get("properties")
            if not isinstance(sub, dict):
                return None
            out = {}
            for sub_name, sub_def in sub.items():
                if not isinstance(sub_def, dict):
                    continue
                value = self.field_value(holder, part_node, sub_name, sub_def, pointer)
                if value is not None:
                    out[sub_name] = value
            return out or None

        raw = scope.attr(attr_name)
        if raw is None or raw == "":
            return None
        return self.coerce_scalar(nfc(raw), kinds)

    def coerce_scalar(self, raw, kinds):
        """属性文字列 1 本を schema が宣言した型へ戻す。

        HTML の属性は文字列しか持てないので、boolean の false や integer の 0 は
        書き戻す側で型を復元しないと E-TYPE-INVALID になる。

        **合わない値は黙って直さず文字列のまま返す。** 例えば boolean 宣言の
        項目に "yes" が入っていたら、ここで True へ寄せると「復元できたように
        見えて元と違う資料」ができあがる。文字列のまま返せば C12 が
        E-TYPE-INVALID で落とすので、壊れていることが見える。
        """
        if "boolean" in kinds and raw in ("true", "false"):
            return raw == "true"
        if "integer" in kinds and raw.lstrip("-").isdigit():
            return int(raw)
        return raw

    def entries_container(self, scope, name):
        """反復要素の入れ物 (data-hb-entries=<name>) を探す。

        入れ物を名指しさせるのは、同じ部品の中に鍵つき要素が二重にある形
        (B13 のタブ本体とパネル) で取り違えないためである。印が無ければ
        復元しない — 鍵つき要素を手当たり次第に拾うと、B12 のように配列を
        1 本も宣言していない部品にまで rows が生える。
        """
        if scope.attr(ATTR_ENTRIES) == name:
            return scope
        for child in scope.elements():
            found = self.entries_container(child, name)
            if found is not None:
                return found
        return None

    def collect_entries(self, container, part_node, items, pointer):
        """入れ物直下の鍵つき要素を 1 件ずつ復元する。"""
        item_props = items.get("properties")
        item_props = item_props if isinstance(item_props, dict) else {}
        entries = []

        def walk(current):
            for child in current.elements():
                if child.attr(ATTR_KEY) is not None:
                    entries.append(self.build_entry(child, part_node, item_props, pointer))
                    continue
                walk(child)

        walk(container)
        return entries

    def build_entry(self, node, part_node, item_props, pointer):
        entry = {}
        for name, definition in item_props.items():
            if not isinstance(definition, dict):
                continue
            items = definition.get("items")
            if isinstance(items, dict) and items.get("$ref") == PART_REF:
                # B13 の panel_parts。パネルは data-hb-panel-for でタブ本体の
                # 鍵を指しているので、それを辿って中の部品を組み直す。
                nested = self.panel_parts(part_node, node.attr(ATTR_KEY), pointer)
                if nested is not None:
                    entry[name] = nested
                continue
            value = self.field_value(node, part_node, name, definition, pointer)
            if value is not None:
                entry[name] = value
        return entry

    def panel_parts(self, part_node, key, pointer):
        if key is None:
            return None
        panel = self.find_attr(part_node, ATTR_PANEL_FOR, key)
        if panel is None:
            return None
        parts = []
        self.collect_parts(panel, pointer + "/panel", parts, [], None)
        return parts

    def find_attr(self, scope, attr_name, value):
        for child in scope.elements():
            if child.attr(attr_name) == value:
                return child
            found = self.find_attr(child, attr_name, value)
            if found is not None:
                return found
        return None

    def find_marked(self, scope, name):
        return self.find_attr(scope, ATTR_FIELD, name)

    def marked_texts(self, scope, name):
        """data-hb-field=<name> の要素の表示テキストを文書順に集める。"""
        found = []

        def walk(current):
            for child in current.elements():
                if child.attr(ATTR_FIELD) == name:
                    found.append(text_value(child))
                walk(child)

        walk(scope)
        return found or None

    # ---- 素材 (A9) -----------------------------------------------------

    # 素材 1 種につき (id 属性, レジストリを組む手続き)。走査の入口は
    # data-hb-media-record ただ 1 本で、この表はその要素が名乗る id 属性から
    # 「どのレジストリの実体か」を決めるためだけに使う。
    MEDIA_BUILDERS = (
        (ATTR_ASSET_ID, "_asset_ids", "assets", "build_asset"),
        (ATTR_ATTACHMENT_ID, "_attachment_ids", "attachments", "build_attachment"),
        (ATTR_DIAGRAM_ID, "_diagram_ids", "diagrams", "build_diagram"),
    )

    def collect_media(self, node, pointer):
        """レジストリ実体を名乗る要素 (data-hb-media-record) だけから素材を組む。

        素材 id 属性そのものを入口にすると、素材を **参照するだけ** の部品
        (B17 の asset_id / B12 の attachment_id / B14 の図解部品) まで実体の
        持ち主に見え、付随情報を持たない要素が素材の出所に選ばれる
        (実測: alt / filename / mime が復元できず、存在しない diagrams[] が
        1 件発明されていた)。参照と実体は別の印で分ける。
        """
        for holder in self.iter_subtree(node):
            record = holder.attr(ATTR_MEDIA_RECORD)
            if not record:
                continue
            for id_attr, seen_name, bucket_name, builder_name in self.MEDIA_BUILDERS:
                if holder.attr(id_attr) != record:
                    continue
                seen = getattr(self, seen_name)
                if record in seen:
                    break
                seen.add(record)
                getattr(self, bucket_name).append(
                    getattr(self, builder_name)(holder, record))
                break

    def payload_in_subtree(self, node, attr_name):
        """部分木のどこかにある実体 (src / href) を 1 つ返す。"""
        for child in self.iter_subtree(node):
            value = child.attr(attr_name)
            if value:
                return value
        return None

    def iter_subtree(self, node):
        yield node
        for child in node.elements():
            for descendant in self.iter_subtree(child):
                yield descendant

    def build_asset(self, node, asset_id):
        pointer = "/assets/%d" % len(self.assets)
        # 実体 (data URI) を載せているのは表示要素の <img src> であり、
        # 付随情報 (alt / caption / role) を載せているのは外側の figure である。
        # 片方だけを見ると必ずどちらかを落とすので、記録の持ち主から下って探す。
        embedded = node.attr("src") or self.payload_in_subtree(node, "src")
        asset = {"id": nfc(asset_id)}
        kind = node.attr(ATTR_ASSET_KIND)
        if kind:
            asset["kind"] = nfc(kind)
        asset["alt"] = self.marked_value(node, ATTR_ASSET_ALT, pointer + "/alt", "alt")
        caption = node.attr(ATTR_ASSET_CAPTION)
        if caption is None:
            asset["caption"] = None
            self.gap(pointer + "/caption", "caption を運ぶ %s が無い" % ATTR_ASSET_CAPTION, False)
        else:
            asset["caption"] = nfc(caption)
        origin = node.attr(ATTR_SRC)
        if origin is None or origin == "":
            self.gap(pointer + "/src", "原本相対パスを運ぶ %s が無い (埋め込み後は data URI しか"
                                       " 残らない)" % ATTR_SRC, False)
            # ROUNDTRIP-CONTRACT.md /assets/*/data_uri の payload_field 規則:
            # data-hb-src が空なら著者が src へ data URI を直書きした経路であり、
            # 実体の置き場は src ただ 1 本。ここで data_uri を足すと
            # $defs.asset (additionalProperties:false) に無いキーを発明することに
            # なり、復元結果が --config を通らず「出発点」にならない。
            asset["src"] = embedded
        else:
            asset["src"] = nfc(origin)
            if embedded is not None:
                # 原本パスが残っている = C13 埋め込み後の方言。実体は捨てず
                # data_uri へ入れる (手元に原本 assets/ が無いのが普通のため)。
                asset["data_uri"] = embedded
        role = node.attr(ATTR_ASSET_ROLE)
        if role:
            asset["role"] = nfc(role)
        return asset

    def build_attachment(self, node, attachment_id):
        pointer = "/attachments/%d" % len(self.attachments)
        embedded = node.attr("href")
        attachment = {"id": nfc(attachment_id)}
        attachment["filename"] = self.marked_value(node, ATTR_FILENAME,
                                                   pointer + "/filename", "filename")
        attachment["mime"] = self.marked_value(node, ATTR_MIME, pointer + "/mime", "mime")
        attachment["fallback_hint"] = self.marked_value(
            node, ATTR_FALLBACK_HINT, pointer + "/fallback_hint", "fallback_hint")
        origin = node.attr(ATTR_SRC)
        if origin is None or origin == "":
            self.gap(pointer + "/src", "原本相対パスを運ぶ %s が無い" % ATTR_SRC, False)
            # /assets/*/data_uri と同じ裁定 (payload_field)。
            attachment["src"] = embedded
        else:
            attachment["src"] = nfc(origin)
            if embedded is not None:
                attachment["data_uri"] = embedded
        return attachment

    def build_diagram(self, node, diagram_id):
        pointer = "/diagrams/%d" % len(self.diagrams)
        diagram = {"id": nfc(diagram_id)}
        diagram["pattern"] = self.marked_value(node, ATTR_DIAGRAM_PATTERN,
                                               pointer + "/pattern", "pattern")
        # diagrams[].data は「部品へ平坦化した後の姿」(pattern / title を
        # 混ぜた data-hb-diagram-data) からは切り出せない — data 自身が
        # pattern や title というキーを持ちうるため境界が消える。実体の
        # 写しを別の属性で運ばせ、そちらを優先して読む。
        payload = node.attr(ATTR_DIAGRAM_RECORD_DATA)
        if payload is None or payload == "":
            payload = node.attr(ATTR_DIAGRAM_DATA)
        if payload is None or payload == "":
            diagram["data"] = None
            self.gap(pointer + "/data",
                     "構造データを運ぶ %s が無い (生成 SVG からは戻せない)" % ATTR_DIAGRAM_DATA)
        else:
            try:
                diagram["data"] = json.loads(payload)
            except ValueError as exc:
                diagram["data"] = None
                self.gap(pointer + "/data",
                         "%s が JSON として読めない (%s)" % (ATTR_DIAGRAM_DATA, exc))
        title = node.attr(ATTR_DIAGRAM_TITLE)
        if title:
            diagram["title"] = nfc(title)
        else:
            diagram["title"] = None
            self.gap(pointer + "/title", "title を運ぶ %s が無い" % ATTR_DIAGRAM_TITLE, False)
        return diagram


# ---------------------------------------------------------------------------
# 比較 (roundtrip_granularity)
# ---------------------------------------------------------------------------


def comparable_projection(config):
    if not isinstance(config, dict):
        return config
    return {key: value for key, value in config.items() if key != "provenance"}


def canonical_date(value, c12):
    """日付の書式ゆれを吸収する。書式の解釈は C12 の実装へ委ねる。"""
    if not isinstance(value, str) or c12 is None:
        return value
    parts = c12.parse_date_parts(value)
    if parts is None:
        runs = DIGIT_RUN_RE.findall(value)
        if len(runs) == 3:
            parts = tuple(int(run) for run in runs)
    if parts is None:
        return value
    return c12.format_date(*parts)


def normalize_for_compare(config, c12):
    """比較の前に両者を同じ正規化へ通す (基準を 2 つにしないため C12 を共有)。"""
    data = json.loads(json.dumps(config))
    if c12 is not None:
        data = c12.normalize_strings(data)
    if isinstance(data, dict) and "date" in data:
        data["date"] = canonical_date(data.get("date"), c12)
    return comparable_projection(data)


def render_scalar(value):
    if value is ABSENT:
        return "<absent>"
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text.replace("\n", "\\n").replace("\r", "")


def deep_diff(expected, actual, pointer, diffs):
    if expected is ABSENT or actual is ABSENT:
        diffs.append({"pointer": pointer, "expected": render_scalar(expected),
                      "actual": render_scalar(actual)})
        return
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            deep_diff(expected.get(key, ABSENT), actual.get(key, ABSENT),
                      "%s/%s" % (pointer, key), diffs)
        return
    if isinstance(expected, list) and isinstance(actual, list):
        for index in range(max(len(expected), len(actual))):
            left = expected[index] if index < len(expected) else ABSENT
            right = actual[index] if index < len(actual) else ABSENT
            deep_diff(left, right, "%s/%d" % (pointer, index), diffs)
        return
    if type(expected) is not type(actual) or expected != actual:
        diffs.append({"pointer": pointer, "expected": render_scalar(expected),
                      "actual": render_scalar(actual)})


# ---------------------------------------------------------------------------
# 出力
# ---------------------------------------------------------------------------


def serialize(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_atomic(path, text):
    path = Path(path)
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".hb-extract-")
    os.close(handle)
    try:
        with open(temp_name, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp_name, str(path))
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def emit(lines):
    for line in lines:
        sys.stderr.write(line + "\n")


# ---------------------------------------------------------------------------
# argv と実行
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="生成済み HTML から構成データ JSON を逆抽出する (C11 の逆関数)")
    parser.add_argument("--html", required=True, help="逆抽出対象の単一 HTML (読み取り専用)")
    parser.add_argument("--out", default=None, help="復元した構成データ JSON の書き出し先")
    parser.add_argument("--compare", default=None, help="round-trip 等価判定の比較対象 JSON")
    parser.add_argument("--strict-fidelity", action="store_true",
                        help="任意フィールドの復元不能と heuristic 推定も不合格にする")
    parser.add_argument("--report", default=None, help="抽出レポート JSON の書き出し先")
    return parser


def check_out_path(value, html_path, label):
    path = Path(value)
    if not path.parent.is_dir():
        raise LaunchAbort("%s の親ディレクトリが存在しない: %s" % (label, path.parent))
    if os.path.realpath(str(path)) == os.path.realpath(str(html_path)):
        raise LaunchAbort("%s を --html と同一実体にできない (入力の書き換えの禁止)" % label)
    return path


def as_type_list(kinds):
    """schema の type 宣言 (文字列 / 配列 / 省略) を必ず配列として扱う。"""
    if isinstance(kinds, list):
        return kinds
    return [kinds]


def load_part_properties(root):
    """部品ごとの data キー名の出所 (C12 のスキーマ。id 語彙の出所としては使わない)。"""
    path = Path(root) / SCHEMA_RELPATH
    if not path.is_file():
        return {}, {}
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    defs = schema.get("$defs") if isinstance(schema, dict) else None
    table = defs.get("part_data") if isinstance(defs, dict) else None
    if not isinstance(table, dict):
        return {}, {}
    result = {}
    required = {}
    for part_id, definition in table.items():
        if isinstance(definition, dict) and isinstance(definition.get("properties"), dict):
            result[part_id] = resolve_refs(definition["properties"], schema)
            names = definition.get("required")
            required[part_id] = tuple(names) if isinstance(names, list) else ()
    return result, required


def resolve_refs(node, schema, depth=0):
    """schema 内の $ref を展開した写しを返す。

    B06 の left / right は $defs.labeled_items への参照なので、参照のまま
    渡すと「型が書かれていない項目」に見えて復元先が決まらない。参照の
    実体は同じ 1 つの schema にあるので、ここで解いてから使う。
    再帰は $defs.part (B13 の panel_parts) が自己参照するため深さで止める。
    """
    if depth > 12:
        return node
    if isinstance(node, list):
        return [resolve_refs(v, schema, depth + 1) for v in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if ref == PART_REF:
        # 部品そのものへの参照 (B13 の panel_parts)。展開すると part_data 経由で
        # 自分自身へ戻るため参照のまま残し、入れ子部品として別扱いする。
        return node
    if isinstance(ref, str) and ref.startswith("#/"):
        target = schema
        for token in ref[2:].split("/"):
            target = target.get(token) if isinstance(target, dict) else None
            if target is None:
                return node
        merged = resolve_refs(target, schema, depth + 1)
        if isinstance(merged, dict):
            merged = dict(merged)
            merged["x_ref"] = ref
            return merged
        return merged
    return {k: resolve_refs(v, schema, depth + 1) for k, v in node.items()}


def run(args):
    html_path = Path(args.html)
    if not html_path.is_file():
        raise LaunchAbort("--html のパスが存在しないか読めない: %s" % html_path)
    try:
        source = html_path.read_bytes()
    except OSError as exc:
        raise LaunchAbort("--html を読めない: %s (%s)" % (html_path, exc))
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LaunchAbort("--html が UTF-8 で読めない: %s (%s)" % (html_path, exc))

    out_path = check_out_path(args.out, html_path, "--out") if args.out else None
    report_path = check_out_path(args.report, html_path, "--report") if args.report else None

    compare_config = None
    if args.compare:
        compare_config = read_json_file(args.compare, "--compare の構成データ")

    root = resolve_root()
    catalog = Catalog(read_json_file(root / PARTS_RELPATH, "部品カタログ正本"),
                      root / PARTS_RELPATH)
    part_properties, part_required = load_part_properties(root)
    # 読み飛ばしから外す著者データマーカーは裁定表からの導出値 (列挙を持たない)
    authored_markers = authored_data_markers(load_roundtrip_contract(root))
    c12 = load_c12_module(root)

    drift_lines = self_check_catalog(catalog)

    try:
        tree = build_tree(text)
        prune_chrome(tree, authored_markers)
        extractor = Extractor(catalog, part_properties, part_required)
        config = extractor.extract(tree)
    except MalformedHtml as exc:
        emit(drift_lines)
        emit(["%s %d %s" % (E_HTML_MALFORMED, exc.line, exc.detail)])
        return EXIT_VIOLATION

    diagnostics = list(drift_lines)
    for entry in extractor.required_gaps:
        diagnostics.append("%s %s %s" % (E_UNRECOVERABLE, entry["pointer"], entry["reason"]))
    for entry in extractor.heuristics:
        diagnostics.append("%s %s %s (根拠: %s)"
                           % (W_HEURISTIC, entry["pointer"], entry["part"], entry["evidence"]))
    for entry in extractor.optional_gaps:
        diagnostics.append("%s %s %s" % (W_OPTIONAL, entry["pointer"], entry["reason"]))

    roundtrip = {"compared": False, "equivalent": True, "diffs": []}
    if compare_config is not None:
        expected = normalize_for_compare(compare_config, c12)
        actual = normalize_for_compare(config, c12)
        diffs = []
        deep_diff(expected, actual, "", diffs)
        roundtrip = {"compared": True, "equivalent": not diffs, "diffs": diffs}
        for diff in diffs:
            diagnostics.append("%s %s expected=%s actual=%s"
                               % (E_ROUNDTRIP_DIFF, diff["pointer"] or "/",
                                  diff["expected"], diff["actual"]))

    section_count = len(config.get("sections") or [])
    part_count = extractor.exact_parts + extractor.heuristic_parts
    unrecoverable = len(extractor.required_gaps)

    if report_path is not None:
        report = {
            "source_html": str(html_path),
            "sections": extractor.report_sections,
            "fidelity_summary": {
                "exact": extractor.exact_parts,
                "heuristic": extractor.heuristic_parts,
                "unrecoverable": unrecoverable,
            },
            "unrecoverable": extractor.required_gaps,
            "roundtrip": roundtrip,
        }
        write_atomic(report_path, serialize(report))

    if out_path is not None and roundtrip["equivalent"]:
        write_atomic(out_path, serialize(config))

    summary = ("EXTRACTED sections=%d parts=%d exact=%d heuristic=%d unrecoverable=%d"
               % (section_count, part_count, extractor.exact_parts,
                  extractor.heuristic_parts, unrecoverable))
    if roundtrip["compared"]:
        summary += " roundtrip=%s" % ("EQUIVALENT" if roundtrip["equivalent"] else "DIFFERENT")
    sys.stdout.write(summary + "\n")

    emit(diagnostics)

    if not roundtrip["equivalent"]:
        return EXIT_VIOLATION
    if unrecoverable:
        return EXIT_VIOLATION
    if args.strict_fidelity and (extractor.optional_gaps or extractor.heuristics):
        return EXIT_VIOLATION
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

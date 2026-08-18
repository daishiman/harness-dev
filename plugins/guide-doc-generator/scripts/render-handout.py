#!/usr/bin/env python3
# /// script
# name: render-handout
# version: 0.1.0
# purpose: C11 正規化済みの構成データから外部依存ゼロの単一 HTML を決定論生成する。語彙の正本を 1 つも持たず config/ と C14/C15 から解決する
# inputs:
#   - argv: --config <path> [--out <path>] [--theme <name>] [--config-out <path>]
#   - file: config/handout-parts.json ほか語彙正本
# outputs:
#   - file: --out の単一 HTML / --config-out の採用値を書き戻した構成データ
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out / --json-report / --config-out で明示された path のみ
# ///
# -*- coding: utf-8 -*-
"""C11 render-handout.py — 正規化済み構成データから単一 HTML を決定論生成する。

契約の正本: plugin-plans/guide-doc-generator/briefs/script-brief-C11.json
受入の正本: plugins/guide-doc-generator/tests/render-handout.py/

本 script は語彙の正本を 1 つも持たない。
  - 部品 id の正本は config/handout-parts.json (part id をここへ列挙しない)
  - 用途 slug の正本は C23 resolve-handout-preset.py (8 語をここへ列挙しない)
  - 外部参照判定 / 絵文字判定の正本は C16 verify-handout-selfcontained.py
    (scan_external_references / scan_emoji を module import して呼ぶ)
  - 図解の描画は C14 render-diagram-svg.py の render_diagram()
  - アイコン sprite は C15 build-icon-sprite.py の build_sprite()
  - 色・字送り・本文上限の数値の正本は assets/tokens/<theme>.json

exit code: 0 = 出力した / 1 = 入力データの規約違反 / 2 = 実行不能。
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path

# ---------------------------------------------------------------------------
# 位置定数 (絶対パスを直書きしない)
# ---------------------------------------------------------------------------

MANIFEST_RELPATH = ".claude-plugin/plugin.json"
MANIFEST_NAME = "guide-doc-generator"
NAME_KEY = "name"
ROOT_ENV_VARS = ("HB_ROOT", "CLAUDE_PLUGIN_ROOT")

PARTS_CATALOG_RELPATH = "config/handout-parts.json"
CONFIG_SCHEMA_RELPATH = "schemas/handout-config.schema.json"
TOKENS_RELDIR = "assets/tokens"
ICON_SET_RELPATH = "assets/icons/icon-set.json"

SELFCONTAINED_RELPATH = "scripts/verify-handout-selfcontained.py"
SPRITE_RELPATH = "scripts/build-icon-sprite.py"
DIAGRAM_RELPATH = "scripts/render-diagram-svg.py"
PRESET_RELPATH = "scripts/resolve-handout-preset.py"

MODULE_ALIASES = {
    SELFCONTAINED_RELPATH: "hb_selfcontained",
    SPRITE_RELPATH: "hb_icon_sprite",
    DIAGRAM_RELPATH: "hb_diagram",
    PRESET_RELPATH: "hb_preset",
}

# 埋め込み実測値の報告しきい値 (判断は C13。C11 は報告だけを行う)
EMBED_REPORT_THRESHOLD = 1 << 18

# 入場アニメーションの刻み (min(index * STEP, CAP))
STAGGER_STEP_MS = 120
STAGGER_CAP_MS = 720

NAV_OFFSET_PX = 96

TEXT_LIMITS_KEY = "text_limits"
DEFAULT_LIMIT_KEY = "block_body_max_chars"
BY_LEVEL_LIMIT_KEY = "block_body_max_chars_by_detail_level"
CSS_VARIABLES_KEY = "css_variables"

DOC_REQUIRED_FIELDS = (
    "title", "date", "reader", "prior_knowledge_level", "doc_type",
    "essential_problem", "purpose", "background", "goal", "duration", "sections",
)
SECTION_REQUIRED_FIELDS = ("id", "heading", "goal", "lead_line", "judgment_axis")

SECTION_SCOPE_DOCUMENT = "document"
SECTION_SCOPE_IN_SECTION = "in-section"

MARKER_SECTION = "section"
MARKER_LIGHTBOX = "lightbox"
MARKER_MEMO = "memo"
MARKER_MEMO_GLOBAL = "memo-global"
MARKER_TOOLBAR = "toolbar"


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class LaunchError(Exception):
    """実行不能 (exit 2)。"""

    def __init__(self, diagnostics):
        if isinstance(diagnostics, str):
            diagnostics = [diagnostics]
        self.diagnostics = list(diagnostics)
        super().__init__("; ".join(self.diagnostics))


class DataError(Exception):
    """入力データの規約違反 (exit 1)。1 行 1 診断。"""

    def __init__(self, diagnostics):
        if isinstance(diagnostics, str):
            diagnostics = [diagnostics]
        self.diagnostics = list(diagnostics)
        super().__init__("; ".join(self.diagnostics))


# ---------------------------------------------------------------------------
# 実体解決 (4 段。C15 / C10 と同じ順序)
# ---------------------------------------------------------------------------


def _script_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _manifest_matches(root: Path) -> bool:
    manifest = Path(root) / MANIFEST_RELPATH
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get(NAME_KEY) == MANIFEST_NAME


def candidate_roots() -> list:
    entries = []
    seen = set()

    def add(label, path):
        try:
            key = str(Path(path).resolve())
        except OSError:
            key = str(path)
        if key in seen:
            return
        seen.add(key)
        entries.append((label, Path(path)))

    for env_name in ROOT_ENV_VARS:
        value = os.environ.get(env_name)
        if value:
            add(env_name, Path(value))
    cwd = Path.cwd().resolve()
    for base in (cwd, *cwd.parents):
        if _manifest_matches(base):
            add(MANIFEST_RELPATH, base)
    script_root = _script_root()
    if _manifest_matches(script_root):
        add(MANIFEST_RELPATH, script_root)
    add("__file__", script_root)
    return entries


def _stage_report() -> list:
    lines = []
    for env_name in ROOT_ENV_VARS:
        value = os.environ.get(env_name)
        lines.append("  {}: {}".format(env_name, value if value else "未設定"))
    matched = [str(p) for label, p in candidate_roots() if label == MANIFEST_RELPATH]
    lines.append("  {} (name={}) 照合: {}".format(
        MANIFEST_RELPATH, MANIFEST_NAME,
        ", ".join(matched) if matched else "cwd とその祖先に一致なし"))
    lines.append("  __file__ の親の親: {}".format(_script_root()))
    return lines


def resolve_under_roots(relpath: str, label: str) -> Path:
    tried = []
    for _stage, root in candidate_roots():
        candidate = Path(root) / relpath
        tried.append(str(candidate))
        if candidate.is_file():
            return candidate
    raise LaunchError(
        ["{}を実体解決できない (試した 4 段):".format(label)]
        + _stage_report()
        + ["  候補パス: " + p for p in tried]
    )


def resolve_dir_under_roots(relpath: str, label: str) -> Path:
    tried = []
    for _stage, root in candidate_roots():
        candidate = Path(root) / relpath
        tried.append(str(candidate))
        if candidate.is_dir():
            return candidate
    raise LaunchError(
        ["{}を実体解決できない (試した 4 段):".format(label)]
        + _stage_report()
        + ["  候補パス: " + p for p in tried]
    )


def load_peer_module(relpath: str, label: str):
    """兄弟 script を module として読み込む (ファイル名にハイフンを含むため importlib)。"""
    path = resolve_under_roots(relpath, label)
    alias = MODULE_ALIASES[relpath]
    spec = importlib.util.spec_from_file_location(alias, str(path))
    if spec is None or spec.loader is None:
        raise LaunchError("{} を module として読み込めない: {}".format(relpath, path))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        raise LaunchError("{} の import に失敗 ({}: {})".format(
            relpath, type(exc).__name__, exc))
    return module


def read_json(path: Path, label: str):
    path = Path(path)
    if not path.is_file():
        raise LaunchError("{} が実在しない: {}".format(label, path))
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LaunchError("{} を読めない: {} ({})".format(label, path, exc))
    try:
        return json.loads(raw, object_pairs_hook=OrderedDict)
    except ValueError as exc:
        raise LaunchError("{} が JSON として parse できない: {} ({})".format(
            label, path, exc))


# ---------------------------------------------------------------------------
# 部品カタログ (consumer_contract: C12 / C18 / C23 が使う module API)
# ---------------------------------------------------------------------------

_CATALOG_CACHE = None


def load_parts_catalog(path=None):
    """部品 id 語彙の単一正本を読む。"""
    global _CATALOG_CACHE
    if path is None and _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    target = Path(path) if path is not None else resolve_under_roots(
        PARTS_CATALOG_RELPATH, "部品カタログ正本")
    data = read_json(target, "部品カタログ正本")
    if not isinstance(data, dict) or not isinstance(data.get("parts"), list):
        raise LaunchError("部品カタログ正本の形が壊れている: {}".format(target))
    if path is None:
        _CATALOG_CACHE = data
    return data


def is_known_part(part_id) -> bool:
    for part in load_parts_catalog()["parts"]:
        if part.get("id") == part_id:
            return True
    return False


def in_section_parts() -> list:
    return [part["id"] for part in load_parts_catalog()["parts"]
            if part.get("section_scope") == SECTION_SCOPE_IN_SECTION]


def structure_markers() -> list:
    catalog = load_parts_catalog()
    markers = (catalog.get("non_part_structure_markers") or {}).get("values")
    if not isinstance(markers, list) or not markers:
        raise LaunchError("非部品の構造マーカー語彙が部品カタログに無い")
    return list(markers)


def document_part_ids() -> list:
    """セクションに属さない骨格部品 (カタログ順)。id をここへ列挙しない。"""
    ids = [part["id"] for part in load_parts_catalog()["parts"]
           if part.get("section_scope") == SECTION_SCOPE_DOCUMENT]
    if len(ids) != 2:
        raise LaunchError(
            "骨格部品 (section_scope={}) がちょうど 2 件でない: {}".format(
                SECTION_SCOPE_DOCUMENT, ids))
    return ids


def part_id_by_block_type() -> dict:
    table = OrderedDict()
    for part in load_parts_catalog()["parts"]:
        block_type = part.get("data_block_type")
        if isinstance(block_type, str) and block_type:
            table[block_type] = part["id"]
    return table


# ---------------------------------------------------------------------------
# テーマトークン
# ---------------------------------------------------------------------------


def tokens_dir() -> Path:
    return resolve_dir_under_roots(TOKENS_RELDIR, "テーマトークン置き場")


def load_theme_tokens(theme: str):
    path = tokens_dir() / (theme + ".json")
    if not path.is_file():
        raise DataError("theme: 実在しないテーマ名 {!r} (テーマトークンが無い: {})".format(
            theme, path))
    return read_json(path, "テーマトークン")


def default_theme_name() -> str:
    """既定テーマはトークン側の is_default 宣言から読む (script へ名前を書かない)。"""
    names = []
    for path in sorted(tokens_dir().glob("*.json")):
        data = read_json(path, "テーマトークン")
        if not isinstance(data, dict):
            continue
        if data.get("is_default") is True:
            names.append(str(data.get("theme") or path.stem))
    if len(names) != 1:
        raise LaunchError(
            "既定テーマ (is_default=true) がちょうど 1 件でない: {}".format(names))
    return names[0]


def text_limit_for(tokens, detail_level) -> str:
    limits = tokens.get(TEXT_LIMITS_KEY)
    if not isinstance(limits, dict):
        raise LaunchError("テーマトークンに {} が無い".format(TEXT_LIMITS_KEY))
    by_level = limits.get(BY_LEVEL_LIMIT_KEY)
    if isinstance(by_level, dict) and detail_level in by_level:
        value = by_level[detail_level]
    else:
        value = limits.get(DEFAULT_LIMIT_KEY)
    if not isinstance(value, int):
        raise LaunchError("テーマトークンの本文上限が整数でない: {!r}".format(value))
    return str(value)


# ---------------------------------------------------------------------------
# エスケープと属性
# ---------------------------------------------------------------------------


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def attrs_to_str(pairs) -> str:
    out = []
    for name, value in pairs:
        if value is None:
            continue
        if value is True:
            out.append(name)
            continue
        out.append('{}="{}"'.format(name, esc(value)))
    return "".join(" " + item for item in out)


def tag(name, pairs, inner="", void=False) -> str:
    if void:
        return "<{}{}>".format(name, attrs_to_str(pairs))
    return "<{}{}>{}</{}>".format(name, attrs_to_str(pairs), inner, name)


# ---------------------------------------------------------------------------
# 構成データの検査
# ---------------------------------------------------------------------------


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


DATA_URI_PREFIX = "data:"

_SCHEMA_CACHE = {}


def load_config_schema():
    """構成データ schema 正本 (C12) を読む。値の再定義はしない。"""
    if "schema" not in _SCHEMA_CACHE:
        target = resolve_under_roots(CONFIG_SCHEMA_RELPATH, "構成データ schema 正本 (C12)")
        _SCHEMA_CACHE["schema"] = read_json(target, "構成データ schema 正本")
    return _SCHEMA_CACHE["schema"]


def normalized_by_const():
    """正規化済みの証拠となる provenance.normalized_by の値を schema から引く。

    正規化済みかどうかの判定基準を本 script へ焼き込まない
    (裁定: schemas/INPUT-CONTRACT-RESOLUTION.md)。
    """
    schema = load_config_schema()
    try:
        return schema["$defs"]["provenance"]["properties"]["normalized_by"]["const"]
    except (KeyError, TypeError):
        raise LaunchError(
            "構成データ schema の $defs.provenance.properties.normalized_by.const が無く "
            "正規化済みの判定基準を導出できない: {}".format(CONFIG_SCHEMA_RELPATH))


def block_type_by_part_id() -> dict:
    """カタログの part id → data_block_type (骨格部品は None)。"""
    table = OrderedDict()
    for part in load_parts_catalog()["parts"]:
        table[part.get("id")] = part.get("data_block_type")
    return table


def _entry(*pairs):
    out = OrderedDict()
    for key, value in pairs:
        if value is not None:
            out[key] = value
    return out


def _project_steps(data, ctx):
    return {"items": [
        _entry(("key", row.get("key")), ("label", row.get("text")),
               ("detail", row.get("sub")), ("time", row.get("time")))
        for row in data.get("rows") or []
    ]}


def _project_trio(data, ctx):
    return {"cards": [
        _entry(("key", card.get("note_key")), ("title", card.get("label")),
               ("body", card.get("body")), ("tone", card.get("tone")))
        for card in data.get("cards") or []
    ]}


def _project_table(data, ctx):
    """行見出し列は schema 側で名前を持たない (cells 件数 = columns 件数)。

    描画モデルは行見出しを行配列の先頭要素として持つため、列見出し側にも
    空の先頭セルを 1 つ補う。highlight の整数は cells 上の 0 始まり位置なので
    先頭セル 1 つ分ずらして (行, 列) 座標へ写す。
    """
    columns = [""] + list(data.get("columns") or [])
    rows = []
    highlight = []
    for r_index, row in enumerate(data.get("rows") or []):
        if not isinstance(row, dict):
            raise DataError("sections[].parts[].data.rows[]: オブジェクトでない: {!r}".format(row))
        rows.append([row.get("header")] + list(row.get("cells") or []))
        for c_index in row.get("highlight") or []:
            if isinstance(c_index, int) and not isinstance(c_index, bool):
                highlight.append([r_index, c_index + 1])
    return {"columns": columns, "rows": rows, "highlight": highlight}


def _project_versus(data, ctx):
    def side(value):
        if not isinstance(value, dict):
            return None
        return _entry(("label", value.get("label")),
                      ("bullets", list(value.get("items") or [])))

    return {"left": side(data.get("left")), "right": side(data.get("right"))}


def _project_features(data, ctx):
    return {"cards": [
        _entry(("title", card.get("title")), ("body", card.get("body")),
               ("icon", card.get("icon")), ("footnote", card.get("footnote")))
        for card in data.get("cards") or []
    ]}


def _project_map(data, ctx):
    return {"items": [
        _entry(("key", item.get("key")), ("title", item.get("title")),
               ("detail", item.get("detail")))
        for item in data.get("items") or []
    ]}


def _project_checklist(data, ctx):
    return {"items": [
        _entry(("key", row.get("key")), ("label", row.get("text")))
        for row in data.get("rows") or []
    ]}


def _project_accordion(data, ctx):
    return {"items": [
        _entry(("summary", item.get("summary")), ("body", item.get("body")),
               ("open", item.get("open")))
        for item in data.get("items") or []
    ]}


def _project_prompt(data, ctx):
    return _entry(("label", data.get("label")), ("text", data.get("body")))


def _project_download(data, ctx):
    attachment_id = data.get("attachment_id")
    attachment = ctx["attachments"].get(attachment_id)
    if attachment is None:
        raise DataError(
            "sections[].parts[].data.attachment_id: attachments に無い添付 id である: {!r}"
            .format(attachment_id))
    return {"attachments": [attachment]}


def _project_tabs(data, ctx):
    tabs = []
    for tab in data.get("tabs") or []:
        if not isinstance(tab, dict):
            raise DataError("sections[].parts[].data.tabs[]: オブジェクトでない: {!r}".format(tab))
        tabs.append(_entry(
            ("id", tab.get("key")),
            ("label", tab.get("label")),
            ("blocks", [project_part(inner, ctx) for inner in tab.get("panel_parts") or []]),
        ))
    return {"tabs": tabs}


def _project_flow(data, ctx):
    return {"steps": [
        _entry(("label", step.get("title")), ("note", step.get("body")))
        for step in data.get("steps") or []
    ]}


def _project_chips(data, ctx):
    out = {"options": [
        _entry(("key", chip.get("key")), ("label", chip.get("label")))
        for chip in data.get("chips") or []
    ]}
    if data.get("single") is True:
        out["single"] = True
    return out


def _project_action_items(data, ctx):
    return {"items": [
        _entry(("key", row.get("key")), ("label", row.get("text")),
               ("owner", row.get("owner")), ("due", row.get("due")))
        for row in data.get("rows") or []
    ]}


def _project_handson(data, ctx):
    out = {"steps": [
        _entry(("operation", step.get("operation")), ("expected", step.get("expected")),
               ("stuck_hint", step.get("stuck_hint")))
        for step in data.get("steps") or []
    ]}
    if _nonempty(data.get("asset_id")):
        out["asset_id"] = data["asset_id"]
    if data.get("live_demo") is True:
        out["live_demo"] = True
    return out


def _project_image(data, ctx):
    asset_id = data.get("asset_id")
    if asset_id not in ctx["assets"]:
        raise DataError(
            "sections[].parts[].data.asset_id: assets に無い画像 id である: {!r}".format(asset_id))
    return {"asset_id": asset_id}


def _project_diagram(data, ctx):
    diagram_id = data.get("diagram_id")
    diagram = ctx["diagrams"].get(diagram_id)
    if diagram is None:
        raise DataError(
            "sections[].parts[].data.diagram_id: diagrams に無い図解 id である: {!r}"
            .format(diagram_id))
    out = OrderedDict()
    payload = diagram.get("data")
    if isinstance(payload, dict):
        out.update(payload)
    out["pattern"] = diagram.get("pattern")
    out["title"] = diagram.get("title")
    # レジストリ実体そのものを積む。投影後の block からは
    # 「どこまでが diagrams[].data だったか」が復元できない
    # (data のキーが pattern/title と衝突しうるため) ので、
    # 平坦化した写しではなく原本を持ち回る。
    out[SOURCE_DIAGRAM_KEY] = diagram
    return out


def _project_text(data, ctx):
    return {"body": data.get("body")}


# 鍵は部品カタログの data_block_type (Renderer.RENDERERS と同じ語彙であり
# 第 2 の名簿を作らない)。part id はここへ列挙しない。
PART_DATA_PROJECTIONS = {
    "steps": _project_steps,
    "trio": _project_trio,
    "table": _project_table,
    "versus": _project_versus,
    "features": _project_features,
    "map": _project_map,
    "checklist": _project_checklist,
    "accordion": _project_accordion,
    "prompt": _project_prompt,
    "download": _project_download,
    "tabs": _project_tabs,
    "flow": _project_flow,
    "chips": _project_chips,
    "action-items": _project_action_items,
    "handson": _project_handson,
    "image": _project_image,
    "diagram": _project_diagram,
    "text": _project_text,
}


def project_part(part, ctx):
    """schema の sections[].parts[] 1 件を描画モデルの block へ投影する。"""
    if not isinstance(part, dict):
        raise DataError("sections[].parts[]: オブジェクトでない: {!r}".format(part))
    part_id = part.get("part")
    table = ctx["block_type_by_part"]
    if part_id not in table:
        raise DataError(
            "sections[].parts[].part: 部品カタログに無い part id である: {!r} "
            "(既定部品へフォールバックしない)".format(part_id))
    block_type = table[part_id]
    if not isinstance(block_type, str) or not block_type:
        raise DataError(
            "sections[].parts[].part: 生成 chrome の部品は parts へ置けない: {!r} "
            "(document 構造から C11 が生成する)".format(part_id))
    data = part.get("data")
    if not isinstance(data, dict):
        raise DataError(
            "sections[].parts[].data: オブジェクトでない: {!r} (part={!r})".format(data, part_id))
    projector = PART_DATA_PROJECTIONS.get(block_type)
    if projector is None:
        raise LaunchError(
            "部品カタログの data_block_type {!r} に対応する投影が無い".format(block_type))
    block = OrderedDict()
    block["id"] = part.get("id")
    block["type"] = block_type
    if _nonempty(part.get("slot")):
        block["slot"] = part["slot"]
    block.update(projector(data, ctx))
    # 反復要素の **schema 方言のままの原本** を描画器へ渡す。data-hb-<field> の
    # 属性名は schema のフィールド名でなければならない — 読み戻す C20 の正本は
    # schema であり、描画モデル名 (label / detail) で出すと schema 名 (text / sub)
    # と噛み合わず黙って捨てられるためである。投影で名前が変わる事実はここ
    # (唯一の翻訳点) にしか無いので、対応付けもここで保持する。
    block[SOURCE_DATA_KEY] = data
    return block


SOURCE_DATA_KEY = "hb_source_data"
SOURCE_DIAGRAM_KEY = "hb_source_diagram"
# block に積む内部キー (描画にも直列化にも出さない)。spec 構築や属性刻みの
# 走査から一括で外せるよう 1 箇所に集める。
INTERNAL_BLOCK_KEYS = (SOURCE_DATA_KEY, SOURCE_DIAGRAM_KEY)


def source_data_of(block):
    """block に積んだ schema 方言の part.data を返す。無ければ空 dict。"""
    data = block.get(SOURCE_DATA_KEY)
    return data if isinstance(data, dict) else {}


def source_entries_of(block):
    """(反復要素配列の schema 上のキー名, 配列) を返す。無ければ (None, None)。

    schema の $defs.part_data では 1 部品につき object 配列は高々 1 本しか無い
    (B05 の columns は文字列配列なので該当しない)。ここで名前も返すのは、
    C20 が「どの property の反復要素か」を HTML から知るための
    data-hb-entries をレンダラが出せるようにするためである。
    """
    for name, value in source_data_of(block).items():
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            return name, value
    return None, None


def _project_asset(asset):
    """schema の asset (src が data URI か相対パス) を描画モデルへ寄せる。

    ROUNDTRIP-CONTRACT.md の /assets/*/data_uri の裁定どおり、埋め込み実体の
    置き場は src であり、data-hb-src が運ぶのは原本相対パスである。
    """
    out = OrderedDict(asset)
    src = out.get("src")
    if isinstance(src, str) and src.startswith(DATA_URI_PREFIX):
        out["data_uri"] = src
        out["src"] = ""
    return out


def _project_attachment(attachment):
    out = OrderedDict(attachment)
    if "filename" in out:
        out["name"] = out.get("filename")
    src = out.get("src")
    if isinstance(src, str):
        out["data_uri"] = src
    return out


def has_schema_dialect(config) -> bool:
    """構成データが schema 正本の方言 (sections[].parts) で書かれているか。"""
    if not isinstance(config, dict):
        return False
    for section in config.get("sections") or []:
        if isinstance(section, dict) and "parts" in section:
            return True
    return False


def project_schema_config(config):
    """schema 正本の構成データを描画モデルへ投影する (裁定 = schema が正本)。

    schema は normalized / nav / sections[].blocks を持たない。正規化済みで
    あることは schema 宣言済みの provenance.normalized_by で判定し、目次は
    sections から導出する (導出値を構成データへ書き下さない = PAT-1)。
    """
    expected = normalized_by_const()
    provenance = config.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("normalized_by") != expected:
        raise DataError([
            "provenance.normalized_by: 正規化済みの証拠が無い (期待値 {!r})。"
            "C12 --normalize を通した構成データだけを受け付ける".format(expected)
        ])

    assets = [_project_asset(a) if isinstance(a, dict) else a
              for a in config.get("assets") or []]
    attachments = [_project_attachment(a) if isinstance(a, dict) else a
                   for a in config.get("attachments") or []]
    ctx = {
        "assets": OrderedDict(
            (a["id"], a) for a in assets if isinstance(a, dict) and _nonempty(a.get("id"))),
        "attachments": OrderedDict(
            (a["id"], a) for a in attachments if isinstance(a, dict) and _nonempty(a.get("id"))),
        "diagrams": OrderedDict(
            (d["id"], d) for d in config.get("diagrams") or []
            if isinstance(d, dict) and _nonempty(d.get("id"))),
        "block_type_by_part": block_type_by_part_id(),
    }

    projected = OrderedDict(config)
    projected["assets"] = assets
    projected["attachments"] = attachments

    sections = []
    for section in config.get("sections") or []:
        if not isinstance(section, dict):
            sections.append(section)
            continue
        item = OrderedDict(section)
        parts = item.pop("parts", None)
        if parts is not None and not isinstance(parts, list):
            raise DataError("sections[].parts: 配列でない: {!r}".format(parts))
        item["blocks"] = [project_part(part, ctx) for part in parts or []]
        sections.append(item)
    projected["sections"] = sections

    # 目次は sections から導出する。構成データ側に第 2 の名簿を作らない。
    projected["nav"] = [
        OrderedDict([("href", "#" + section["id"]), ("label", section.get("heading"))])
        for section in sections
        if isinstance(section, dict) and isinstance(section.get("id"), str) and section["id"]
    ]
    # 正規化済みであることは provenance で確認済み。以降の検査は描画モデル上で
    # 従来どおり行う。
    projected["normalized"] = True
    return projected


def validate_config(config, purpose_module):
    problems = []
    if not isinstance(config, dict):
        raise DataError("構成データがオブジェクトでない")

    if config.get("normalized") is not True:
        problems.append(
            "normalized: 正規化済みフラグ (normalized=true) が無い。"
            "C12 --normalize を通した構成データだけを受け付ける")
    if not _nonempty(config.get("schema_version")):
        problems.append("schema_version: 必須フィールドが無い")

    for field in DOC_REQUIRED_FIELDS:
        if field not in config:
            problems.append("{}: 必須フィールドが無い".format(field))
        elif not _nonempty(config.get(field)):
            problems.append("{}: 必須フィールドが空である".format(field))

    doc_type = config.get("doc_type")
    if isinstance(doc_type, str) and doc_type.strip():
        try:
            catalog = purpose_module.load_catalog(resolve_under_roots(
                purpose_module.CATALOG_RELPATH, "用途語彙正本"))
        except LaunchError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LaunchError("用途語彙正本 (C23) を読めない: {}: {}".format(
                type(exc).__name__, exc))
        try:
            purpose_module.resolve(catalog, doc_type)
        except Exception as exc:  # noqa: BLE001
            problems.append("doc_type: 用途語彙正本 (C23) に無い値である ({})".format(exc))

    sections = config.get("sections")
    section_ids = []
    if isinstance(sections, list):
        for index, section in enumerate(sections):
            keypath = "sections[{}]".format(index)
            if not isinstance(section, dict):
                problems.append("{}: オブジェクトでない".format(keypath))
                continue
            sid = section.get("id")
            label = sid if isinstance(sid, str) and sid else keypath
            for field in SECTION_REQUIRED_FIELDS:
                if field not in section:
                    problems.append("{} ({}): 必須フィールド {} が無い".format(
                        keypath, label, field))
                elif not _nonempty(section.get(field)):
                    problems.append("{} ({}): 必須フィールド {} が空である".format(
                        keypath, label, field))
            if isinstance(sid, str) and sid:
                if sid in section_ids:
                    problems.append("{}: section id が重複している: {}".format(keypath, sid))
                section_ids.append(sid)
    elif "sections" in config:
        problems.append("sections: 配列でない")

    nav = config.get("nav")
    if nav is None:
        problems.append("nav: 目次データが無い")
    elif not isinstance(nav, list):
        problems.append("nav: 配列でない")
    else:
        referenced = []
        for index, entry in enumerate(nav):
            keypath = "nav[{}]".format(index)
            if not isinstance(entry, dict):
                problems.append("{}: オブジェクトでない".format(keypath))
                continue
            href = entry.get("href")
            if not isinstance(href, str) or not href.startswith("#"):
                problems.append("{}: href が文書内フラグメントでない: {!r}".format(keypath, href))
                continue
            target = href[1:]
            if target not in section_ids:
                problems.append(
                    "{}: 未解決のナビ参照 {} に対応する section id が無い".format(keypath, href))
            if target in referenced:
                problems.append("{}: 同一 section を 2 度参照している: {}".format(keypath, href))
            referenced.append(target)
        for sid in section_ids:
            if sid not in referenced:
                problems.append("sections: nav から参照されていない孤立 section: {}".format(sid))

    if problems:
        raise DataError(problems)


# ---------------------------------------------------------------------------
# 描画ヘルパ
# ---------------------------------------------------------------------------


def entry_key(entry, index):
    for name in ("key", "id"):
        value = entry.get(name) if isinstance(entry, dict) else None
        if isinstance(value, str) and value.strip():
            return value
    return "i{}".format(index)


def icon_svg(name):
    if not isinstance(name, str) or not name.strip():
        return ""
    return (
        '<svg class="ic" data-hb-kind="decor" aria-hidden="true" focusable="false">'
        '<use href="#hbic-{}"></use></svg>'.format(esc(name))
    )


def field_span(field, value, klass=None, element="span", extra=()):
    pairs = [("class", klass), ("data-hb-field", field)] + list(extra)
    return tag(element, pairs, esc(value))


def data_uri_bytes(value) -> int:
    if not isinstance(value, str):
        return 0
    marker = ","
    head, sep, payload = value.partition(marker)
    if not sep or not head.lower().startswith("data:"):
        return 0
    return len(payload.encode("utf-8"))


# ---------------------------------------------------------------------------
# 部品レンダラ (block.type ごと)
# ---------------------------------------------------------------------------


class Renderer:
    def __init__(self, ctx):
        self.ctx = ctx

    # -- 個別部品 ---------------------------------------------------------

    @staticmethod
    def scalar_pairs(source, skip=()):
        """schema 方言のスカラ値を data-hb-<field> として書き出す。

        **どのキーを出すかの名簿をここへ持たない。** 出す対象は source が実際に
        持っている非空のスカラ (str / bool / int) すべてである。名簿を持つと
        部品ごとに第 2 の名簿ができ、schema へフィールドを足したときに黙って
        落ちる (C20 の collect_entries が (time, owner, due) の 3 つだけを
        拾っていたのがまさにその状態だった)。読み戻す側は schema の properties
        と突き合わせるので、余分なキーが混ざっても復元側で捨てられる。

        配列と入れ子オブジェクトは属性 1 本へ潰すと順序と境界が失われるため
        ここでは扱わず、表示要素側のマーカー (field_marker / 反復要素) が運ぶ。
        """
        pairs = []
        for name, value in source.items():
            if name in skip:
                continue
            if isinstance(value, bool):
                text = "true" if value else "false"
            elif isinstance(value, int):
                text = str(value)
            elif isinstance(value, str) and value:
                text = value
            else:
                continue
            pairs.append(("data-hb-" + name.replace("_", "-"), text))
        return pairs

    @staticmethod
    def entry_data_pairs(entry, skip=("key", "id")):
        """反復要素 1 件のスカラを属性化する (key は要素境界のマーカーが持つ)。"""
        return Renderer.scalar_pairs(entry, skip=skip)

    @staticmethod
    def entries_pairs(block):
        """反復要素の入れ物へ付ける data-hb-entries を返す。

        C20 は「どの property の反復要素か」を知らないと復元先を決められない。
        入れ物を名指ししておくと、同じ部品の中に鍵つき要素が二重にある形
        (B13 のタブ本体とパネル) でも取り違えない。
        """
        name, _ = source_entries_of(block)
        return [("data-hb-entries", name)] if name else []

    @staticmethod
    def source_entry(block, index, fallback):
        """index 番目の反復要素を schema 方言のまま返す。

        入力が schema 方言なら project_part が原本を積んでいるのでそれを使う。
        描画モデル方言で直接渡された場合 (原本が無い) は投影後の要素で代替する。
        代替した場合、属性名は描画モデル名になるため C20 は schema と突き合わせて
        捨てる — 黙って別名で復元されるより落ちる方が安全である。
        """
        _, entries = source_entries_of(block)
        if isinstance(entries, list) and index < len(entries) \
                and isinstance(entries[index], dict):
            return entries[index]
        return fallback

    @staticmethod
    def source_list(block, name, fallback=()):
        """schema 方言の文字列配列を返す (原本が無ければ fallback)。"""
        value = source_data_of(block).get(name)
        return value if isinstance(value, list) else list(fallback)

    def steps(self, block, pairs):
        rows = []
        for index, item in enumerate(block.get("items") or []):
            inner = [
                '<span class="step-num num">{}</span>'.format(index + 1),
                '<span class="step-label">{}</span>'.format(esc(item.get("label"))),
                '<span class="step-detail">{}</span>'.format(esc(item.get("detail"))),
            ]
            if _nonempty(item.get("time")):
                inner.append('<span class="step-time num">{}</span>'.format(
                    esc(item.get("time"))))
            inner.append(icon_svg(item.get("icon")))
            rows.append(tag("li", [
                ("class", "step-row"),
                ("data-hb-key", entry_key(item, index)),
            ] + self.entry_data_pairs(self.source_entry(block, index, item)),
                "".join(inner)))
        return tag("ol", pairs + [("class", "steps")] + self.entries_pairs(block),
                   "".join(rows))

    def trio(self, block, pairs):
        cards = []
        for index, card in enumerate(block.get("cards") or []):
            inner = [
                icon_svg(card.get("icon")),
                '<h4 class="card-title">{}</h4>'.format(esc(card.get("title"))),
                '<p class="card-body">{}</p>'.format(esc(card.get("body"))),
            ]
            cards.append(tag("div", [
                ("class", "trio-card"),
                ("data-hb-key", entry_key(card, index)),
            ] + self.entry_data_pairs(self.source_entry(block, index, card)),
                "".join(inner)))
        return tag("div", pairs + [("class", "trio")] + self.entries_pairs(block),
                   "".join(cards))

    def table(self, block, pairs):
        columns = block.get("columns") or []
        rows = block.get("rows") or []
        highlight = set()
        for entry in block.get("highlight") or []:
            if isinstance(entry, list) and len(entry) == 2:
                highlight.add((entry[0], entry[1]))
        # columns / cells は文字列配列であり、空白区切りの属性 1 本へ潰すと
        # 空白を含む見出しで境界が失われる。順序を保つため表示要素の側へ
        # data-hb-field を刻み、C20 は文書順に読む。
        # 描画モデルの columns は行見出し列ぶんの空セルを先頭へ足した姿なので、
        # schema の columns に対応するのは 2 番目以降である。刻む位置を
        # 原本の件数から決め、対応の無い先頭セルには印を付けない。
        marked = len(self.source_list(block, "columns"))
        head = "".join(
            tag("th", [("scope", "col")]
                + ([("data-hb-field", "columns")]
                   if 1 <= index <= marked else []), esc(c))
            for index, c in enumerate(columns))
        body = []
        for r_index, row in enumerate(rows):
            cells = []
            for c_index, cell in enumerate(row):
                klass = "hl-cell" if (r_index, c_index) in highlight else None
                marker = ("data-hb-field", "header" if c_index == 0 else "cells")
                if c_index == 0:
                    cells.append(tag("th", [("scope", "row"), ("class", klass), marker],
                                     esc(cell)))
                else:
                    cells.append(tag("td", [("class", klass), marker], esc(cell)))
            source_row = self.source_entry(block, r_index, {})
            row_pairs = [("data-hb-key", "r{}".format(r_index))]
            row_pairs += self.entry_data_pairs(source_row)
            # highlight は整数配列。整数は空白を含まないので属性 1 本で無損失。
            marks = source_row.get("highlight")
            if isinstance(marks, list):
                row_pairs.append(("data-hb-highlight",
                                  " ".join(str(m) for m in marks)))
            body.append(tag("tr", row_pairs, "".join(cells)))
        table_html = "<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>".format(
            head, "".join(body))
        return tag("div", pairs + [("class", "table-wrap")] + self.entries_pairs(block),
                   table_html)

    def _side(self, block, name, slot):
        side = block.get(name)
        if not isinstance(side, dict):
            return ""
        # items は文字列配列なので 1 件ずつ表示要素へ刻む。左右そのものは
        # 入れ子オブジェクトなので、どちらの側かを data-hb-field で名指しする。
        bullets = "".join(
            tag("li", [("data-hb-field", "items")], esc(b))
            for b in side.get("bullets") or [])
        inner = '<h4 class="side-label">{}</h4>{}'.format(
            esc(side.get("label")),
            tag("ul", [("class", "side-bullets")], bullets))
        source = source_data_of(block).get(name)
        source = source if isinstance(source, dict) else side
        return tag("div", [
            ("class", "versus-side"),
            ("data-hb-field", name),
            ("data-hb-key", entry_key(side, slot)),
        ] + self.scalar_pairs(source, skip=("key", "id")), inner)

    def versus(self, block, pairs):
        inner = self._side(block, "left", 0) + self._side(block, "right", 1)
        return tag("div", pairs + [("class", "versus")], inner)

    def features(self, block, pairs):
        cards = []
        for index, card in enumerate(block.get("cards") or []):
            inner = [
                icon_svg(card.get("icon")),
                '<h4 class="card-title">{}</h4>'.format(esc(card.get("title"))),
                '<p class="card-body">{}</p>'.format(esc(card.get("body"))),
            ]
            if _nonempty(card.get("footnote")):
                inner.append('<p class="card-note">{}</p>'.format(esc(card.get("footnote"))))
            cards.append(tag("div", [
                ("class", "feature-card"),
                ("data-hb-key", entry_key(card, index)),
            ] + self.entry_data_pairs(self.source_entry(block, index, card)),
                "".join(inner)))
        return tag("div", pairs + [("class", "features")] + self.entries_pairs(block),
                   "".join(cards))

    def choice_map(self, block, pairs):
        items = []
        for index, item in enumerate(block.get("items") or []):
            inner = '<span class="map-title">{}</span><span class="map-detail">{}</span>'.format(
                esc(item.get("title")), esc(item.get("detail")))
            items.append(tag("button", [
                ("type", "button"),
                ("class", "map-item"),
                ("aria-pressed", "false"),
                ("data-hb-key", entry_key(item, index)),
            ] + self.entry_data_pairs(self.source_entry(block, index, item)), inner))
        return tag("div", pairs + [("class", "choice-map")] + self.entries_pairs(block),
                   "".join(items))

    def checklist(self, block, pairs):
        items = []
        for index, item in enumerate(block.get("items") or []):
            key = entry_key(item, index)
            box_id = "chk-{}-{}".format(block.get("id", "b"), key)
            inner = (
                '<label for="{0}"><input type="checkbox" id="{0}">'
                '<span class="check-label">{1}</span></label>'.format(
                    esc(box_id), esc(item.get("label")))
            )
            items.append(tag("li", [
                ("class", "check-row"),
                ("data-hb-key", key),
            ] + self.entry_data_pairs(self.source_entry(block, index, item)), inner))
        return tag("ul", pairs + [("class", "checklist")] + self.entries_pairs(block),
                   "".join(items))

    def accordion(self, block, pairs):
        items = []
        for index, item in enumerate(block.get("items") or []):
            inner = "<summary>{}</summary><div class=\"fold-body\">{}</div>".format(
                esc(item.get("summary")), esc(item.get("body")))
            items.append(tag("details", [
                ("class", "fold"),
                ("data-hb-key", entry_key(item, index)),
                ("open", True if item.get("open") is True else None),
            ] + self.entry_data_pairs(self.source_entry(block, index, item)), inner))
        return tag("div", pairs + [("class", "accordion")] + self.entries_pairs(block),
                   "".join(items))

    def prompt(self, block, pairs):
        inner = (
            '<div class="prompt-label">{}</div><pre class="prompt-text">{}</pre>'
            '<button type="button" class="prompt-copy" data-hb-part-role="aux">'
            "本文をコピーする</button>".format(
                esc(block.get("label")), esc(block.get("text")))
        )
        return tag("div", pairs + [("class", "prompt-box")], inner)

    def download(self, block, pairs):
        items = []
        for index, att in enumerate(block.get("attachments") or []):
            data_uri = att.get("data_uri") or ""
            self.ctx["embedded_bytes"] += data_uri_bytes(data_uri)
            link = tag("a", [
                ("class", "dl-btn"),
                ("href", data_uri),
                ("download", att.get("name", "")),
                ("data-hb-key", entry_key(att, index)),
                ("data-hb-attachment-id", att.get("id", "")),
                # attachments[] の実体を持つのはこのリンク。B12 の部品要素も
                # attachment_id を名乗るため、実体の側を名指ししておく。
                ("data-hb-media-record", att.get("id", "")),
                ("data-hb-filename", att.get("name", "")),
                ("data-hb-mime", att.get("mime", "")),
                ("data-hb-fallback-hint", att.get("fallback_hint", "")),
            ], esc(att.get("name")))
            hint = '<span class="dl-hint">{}</span>'.format(esc(att.get("fallback_hint")))
            items.append('<li class="dl-row">{}{}</li>'.format(link, hint))
        return tag("ul", pairs + [("class", "downloads")], "".join(items))

    def tabs(self, block, pairs, depth=0):
        if depth > 0:
            raise DataError(
                "sections[].blocks[].tabs: tabs の入れ子は 1 段まで "
                "(2 段目の tabs は受け付けない): {}".format(block.get("id")))
        buttons = []
        panels = []
        base = block.get("id", "tabs")
        for index, item in enumerate(block.get("tabs") or []):
            key = entry_key(item, index)
            tab_id = "tab-{}-{}".format(base, key)
            panel_id = "panel-{}-{}".format(base, key)
            selected = index == 0
            buttons.append(tag("button", [
                ("type", "button"),
                ("class", "tab-btn"),
                ("role", "tab"),
                ("id", tab_id),
                ("aria-selected", "true" if selected else "false"),
                ("aria-controls", panel_id),
                ("data-hb-key", key),
            ] + self.entry_data_pairs(self.source_entry(block, index, item)),
                esc(item.get("label"))))
            inner = "".join(
                self.block(child, depth=depth + 1) for child in item.get("blocks") or [])
            panels.append(tag("div", [
                ("class", "tab-panel"),
                ("role", "tabpanel"),
                ("id", panel_id),
                ("aria-labelledby", tab_id),
                ("hidden", None if selected else True),
                # パネルは反復要素ではなく「そのタブの panel_parts の置き場」。
                # data-hb-key で兼ねると C20 がタブ本体と二重に数えるため、
                # 所属先を別の属性で名指しする。
                ("data-hb-panel-for", key),
            ], inner))
        # 反復要素はタブ本体の側。入れ物を名指ししないとパネルまで拾われる。
        strip = tag("div", [("class", "tab-strip"), ("role", "tablist")]
                    + self.entries_pairs(block), "".join(buttons))
        return tag("div", pairs + [("class", "tabs")], strip + "".join(panels))

    def flow(self, block, pairs):
        """B14 は C14 の図解へ委譲する (フロー表現をレンダラ側で二重に持たない)。

        block.type がそのまま C14 の pattern 語であるため、pattern 欄が無い
        構成データでも block.type を既定の pattern として渡せる。
        """
        return self.diagram(block, pairs, default_pattern=block.get("type"))

    def chips(self, block, pairs):
        options = []
        for index, option in enumerate(block.get("options") or []):
            options.append(tag("button", [
                ("type", "button"),
                ("class", "chip"),
                ("aria-pressed", "false"),
                ("data-hb-key", entry_key(option, index)),
            ] + self.entry_data_pairs(self.source_entry(block, index, option)),
                esc(option.get("label"))))
        extra = [("class", "chips")] + self.entries_pairs(block)
        if block.get("single") is True and not source_data_of(block):
            # schema 方言なら single は block() のスカラ刻みで既に出ている。
            extra.append(("data-hb-single", "true"))
        return tag("div", pairs + extra, "".join(options))

    def action_items(self, block, pairs):
        rows = []
        for index, item in enumerate(block.get("items") or []):
            inner = (
                '<span class="ai-label">{}</span>'
                '<span class="ai-owner">{}</span>'
                '<span class="ai-due num">{}</span>'.format(
                    esc(item.get("label")), esc(item.get("owner")), esc(item.get("due")))
            )
            rows.append(tag("li", [
                ("class", "ai-row"),
                ("data-hb-key", entry_key(item, index)),
            ] + self.entry_data_pairs(self.source_entry(block, index, item)), inner))
        return tag("ul", pairs + [("class", "action-items")] + self.entries_pairs(block),
                   "".join(rows))

    def handson(self, block, pairs):
        rows = []
        for index, step in enumerate(block.get("steps") or []):
            inner = (
                '<span class="hs-operation">{}</span>'
                '<span class="hs-expected">{}</span>'
                '<span class="hs-hint">{}</span>'.format(
                    esc(step.get("operation")), esc(step.get("expected")),
                    esc(step.get("stuck_hint")))
            )
            rows.append(tag("li", [
                ("class", "hs-row"),
                ("data-hb-key", entry_key(step, index)),
            ] + self.entry_data_pairs(self.source_entry(block, index, step)), inner))
        extra = [("class", "handson")] + self.entries_pairs(block)
        if block.get("live_demo") is True and not source_data_of(block):
            # schema 方言なら live_demo は block() のスカラ刻みで既に出ている。
            extra.append(("data-hb-live-demo", "true"))
        return tag("ol", pairs + extra, "".join(rows))

    def image(self, block, pairs):
        asset = self.ctx["assets"].get(block.get("asset_id")) or {}
        # 埋め込み実体の正本は assets レジストリ。block 側は asset_id が
        # 解決できないときの控えとしてのみ読む。
        data_uri = asset.get("data_uri") or block.get("data_uri") or ""
        alt = block.get("alt") or asset.get("alt") or ""
        caption = block.get("caption") or asset.get("caption") or ""
        self.ctx["embedded_bytes"] += data_uri_bytes(data_uri)
        img = tag("img", [
            ("class", "asset-img"),
            ("src", data_uri),
            ("alt", alt),
        ], void=True)
        inner = img + '<figcaption class="asset-caption">{}</figcaption>'.format(esc(caption))
        extra = []
        if not source_data_of(block):
            # schema 方言なら asset_id は block() のスカラ刻みで既に出ている。
            extra.append(("data-hb-asset-id", block.get("asset_id", "")))
        return tag("figure", pairs + extra + [
            ("class", "asset"),
            # assets[] の実体を持つのはこの部品。参照だけする部品 (B17 の
            # asset_id など) と区別が付かないと、逆抽出が付随情報を持たない
            # 側を素材の出所に選んでしまう。
            ("data-hb-media-record", block.get("asset_id", "")),
            ("data-hb-asset-kind", asset.get("kind", "")),
            ("data-hb-asset-alt", alt),
            ("data-hb-asset-caption", caption),
            ("data-hb-asset-role", asset.get("role", "")),
            ("data-hb-src", asset.get("src", "")),
        ], inner)

    def diagram(self, block, pairs, default_pattern=None):
        module = self.ctx["diagram_module"]
        spec = OrderedDict()
        for key, value in block.items():
            if key == "type" or key in INTERNAL_BLOCK_KEYS:
                continue
            spec[key] = value
        if not _nonempty(spec.get("title")):
            spec["title"] = (block.get("caption") or block.get("label")
                             or self.ctx["section_heading"] or self.ctx["doc_title"])
        pattern = block.get("pattern") or default_pattern
        try:
            svg = module.render_diagram(spec, pattern)
        except module.DiagramError as exc:
            raise DataError("sections[].blocks[].diagram ({}): {}".format(
                block.get("id"), exc))
        svg = svg.strip()
        marker = "<svg"
        if svg.startswith(marker):
            svg = '<svg data-hb-kind="figure"' + svg[len(marker):]
        self.ctx["diagrams"] += 1
        payload = json.dumps(spec, ensure_ascii=False, sort_keys=False)
        source = source_data_of(block)
        extra = []
        if source:
            # 図解部品 (B14 / DIAGRAM) の中身は C14 が描く SVG であり、
            # C11 が持つ表示要素が無い。他の部品のように「表示している要素へ
            # 刻む」ことができないため、ここだけは構成データそのものを
            # 既存の data-hb-diagram-data と同じ流儀で JSON として運ぶ。
            extra.append(("data-hb-part-data",
                          json.dumps(source, ensure_ascii=False, sort_keys=True)))
        if not source.get("diagram_id"):
            # schema 方言では参照先 id を block() が既に刻んでいる。ここで
            # 部品自身の id を同じ属性名で重ねると属性が二重になる。
            extra.append(("data-hb-diagram-id", block.get("id", "")))
        registry = block.get(SOURCE_DIAGRAM_KEY)
        if isinstance(registry, dict):
            # diagrams[] の実体を持つのはこの部品だけ。B14 のように図解を
            # その場に書く部品は実体を持たないので印を付けない
            # (付けると逆抽出が存在しないレジストリ項目を発明する)。
            extra.append(("data-hb-media-record", registry.get("id", "")))
            extra.append(("data-hb-diagram-title", registry.get("title") or ""))
            extra.append(("data-hb-diagram-record-data",
                          json.dumps(registry.get("data"), ensure_ascii=False,
                                     sort_keys=True)))
        return tag("figure", pairs + [
            ("class", "diagram"),
            ("data-hb-diagram-pattern", pattern or ""),
            ("data-hb-diagram-data", payload),
        ] + extra, svg)

    def text(self, block, pairs):
        return tag("div", pairs + [("class", "prose")],
                   '<p class="prose-body">{}</p>'.format(esc(block.get("body"))))

    # -- 振り分け ---------------------------------------------------------

    RENDERERS = {
        "steps": "steps",
        "trio": "trio",
        "table": "table",
        "versus": "versus",
        "features": "features",
        "map": "choice_map",
        "checklist": "checklist",
        "accordion": "accordion",
        "prompt": "prompt",
        "download": "download",
        "tabs": "tabs",
        "flow": "flow",
        "chips": "chips",
        "action-items": "action_items",
        "handson": "handson",
        "image": "image",
        "diagram": "diagram",
        "text": "text",
    }

    def block(self, block, depth=0):
        if not isinstance(block, dict):
            raise DataError("sections[].blocks[]: オブジェクトでない: {!r}".format(block))
        block_type = block.get("type")
        table = self.ctx["part_by_type"]
        if not isinstance(block_type, str) or block_type not in table:
            raise DataError(
                "sections[].blocks[].type: 部品カタログに無い block.type である: {!r} "
                "(既定部品へフォールバックしない)".format(block_type))
        method_name = self.RENDERERS.get(block_type)
        if method_name is None:
            raise LaunchError(
                "部品カタログの block.type {!r} に対応する描画実装が無い".format(block_type))
        part_id = table[block_type]
        self.ctx["blocks_by_type"][block_type] = (
            self.ctx["blocks_by_type"].get(block_type, 0) + 1)
        pairs = [
            ("data-hb-part", part_id),
            ("data-hb-part-id", block.get("id") or "{}-{}".format(
                block_type, self.ctx["blocks_by_type"][block_type])),
        ]
        slot = block.get("slot")
        if isinstance(slot, str) and slot.strip():
            pairs.append(("data-hb-slot", slot))
        # 部品直下のスカラ (B11 の label/copyable、B15 の key/single、B17 の
        # asset_id/live_demo など) を schema のフィールド名のまま部品要素へ刻む。
        # 個別の描画器へ書くと部品ごとの第 2 の名簿になるため、唯一の入口である
        # ここでまとめて出す。
        pairs += self.scalar_pairs(source_data_of(block))
        method = getattr(self, method_name)
        if method_name == "tabs":
            return method(block, pairs, depth=depth)
        return method(block, pairs)


# ---------------------------------------------------------------------------
# CSS / JS
# ---------------------------------------------------------------------------


CSS_VARIABLE_PREFIX = "--"


def css_variables_of(tokens):
    """:root へ展開する変数表を組む。

    トークンファイルは CSS 変数の入口を 2 段で持つ。
      - `css_variables` … :root へ展開する変数表 (キー集合の正本)
      - トップレベルの `--` 始まりキー … その変数 1 本を 1 手で差し替える入口
    トップレベルの指定は「そこがアクセントの入口である」という宣言なので、
    同名キーがあればトップレベル側を採る。`css_variables` そのものの
    構造契約 (不在なら LaunchError) は弱めない。
    """
    variables = tokens.get(CSS_VARIABLES_KEY)
    if not isinstance(variables, dict) or not variables:
        raise LaunchError("テーマトークンに {} が無い".format(CSS_VARIABLES_KEY))
    merged = OrderedDict(variables)
    for name, value in tokens.items():
        if isinstance(name, str) and name.startswith(CSS_VARIABLE_PREFIX):
            merged[name] = value
    return merged


def build_css(tokens) -> str:
    variables = css_variables_of(tokens)
    lines = [":root {"]
    lines.append("  --nav-h: {}px;".format(NAV_OFFSET_PX))
    for name, value in variables.items():
        lines.append("  {}: {};".format(name, value))
    lines.append("}")
    typography = tokens.get("typography") or {}
    numeric = typography.get("numeric") or {}
    body_feature = (typography.get("body") or {}).get("font_feature_settings") or '"palt"'
    rest = """
* { box-sizing: border-box; }
html { scroll-padding-top: {NAV}px; }
body {
  margin: 0;
  background: var(--pop-bg);
  color: var(--ink);
  font-family: system-ui, sans-serif;
  font-feature-settings: {PALT};
  line-height: 1.8;
}
.num {
  font-family: var(--font-num);
  font-variant-numeric: {TABULAR};
  letter-spacing: {TRACKING};
  white-space: nowrap;
}
.unit { font-size: 62%; font-weight: 600; }
.pop-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--subtle);
  border-bottom: 1px solid var(--line);
}
.navbar { display: flex; gap: 12px; flex-wrap: wrap; padding: 10px 16px; }
.navbar a { color: var(--pop-primary-deep); text-decoration: none; }
.wrap { max-width: 960px; margin: 0 auto; padding: 16px; }
.doc-head { padding: 10px 16px 0; }
.doc-date { margin: 0; }
.hero {
  position: relative;
  padding: 24px;
  margin-bottom: 24px;
}
.hero-frame {
  position: absolute;
  inset: 0;
  background: var(--subtle);
  border: 1px solid var(--line);
  border-radius: var(--card-radius);
  pointer-events: none;
}
.hero > *:not(.hero-frame) { position: relative; }
.hero h1 { margin: 0 0 8px; }
.date-pill {
  display: inline-block;
  padding: 2px 12px;
  border-radius: 999px;
  background: var(--pop-primary-soft);
  color: var(--pop-primary-deep);
}
.goal-chip {
  display: inline-block;
  padding: 2px 12px;
  margin: 2px 4px 2px 0;
  border-radius: 999px;
  background: var(--pop-primary-soft);
  color: var(--pop-primary-deep);
}
.meta-list { margin: 8px 0; padding-left: 1.2em; }
.section-card {
  background: var(--subtle);
  border: 1px solid var(--line);
  border-radius: var(--card-radius);
  padding: 24px;
  margin-bottom: 24px;
  scroll-margin-top: var(--nav-h, {NAV}px);
  animation: rise-in 420ms ease-out both;
  animation-delay: var(--stagger, 0ms);
}
.section-label { margin: 0 0 8px; }
.lead-line { font-weight: 600; }
.judgment-axis {
  border-left: 4px solid var(--pop-primary);
  padding-left: 12px;
}
.steps, .checklist, .downloads, .action-items, .handson {
  list-style: none;
  margin: 0;
  padding: 0;
}
.step-row, .check-row, .dl-row, .ai-row, .hs-row {
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}
.step-num {
  display: inline-block;
  min-width: 2em;
  color: var(--pop-primary-deep);
  font-weight: 700;
}
.trio, .features { display: flex; gap: 12px; flex-wrap: wrap; }
.trio-card, .feature-card, .versus-side {
  flex: 1 1 220px;
  border: 1px solid var(--line);
  border-radius: var(--card-radius);
  padding: 12px;
  background: var(--pop-bg);
}
.versus { display: flex; gap: 12px; flex-wrap: wrap; }
.table-wrap { overflow-x: auto; }
.table-wrap table { border-collapse: collapse; width: 100%; }
.table-wrap th, .table-wrap td {
  border: 1px solid var(--line);
  padding: 6px 10px;
  text-align: left;
}
.hl-cell { background: var(--pop-primary-soft); }
.choice-map { display: flex; gap: 8px; flex-wrap: wrap; }
.map-item, .chip, .tab-btn {
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--pop-bg);
  color: var(--ink);
  padding: 6px 14px;
  cursor: pointer;
}
.map-item[aria-pressed="true"], .chip[aria-pressed="true"] {
  background: var(--pop-primary-soft);
  border-color: var(--pop-primary);
}
.prompt-box { border: 1px solid var(--line); border-radius: var(--card-radius); padding: 12px; }
.prompt-text { white-space: pre-wrap; margin: 0 0 8px; }
.prompt-copy, .memo-btn, .toolbar-toggle, .lightbox-close {
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--pop-bg);
  color: var(--ink);
  padding: 6px 14px;
  cursor: pointer;
}
.dl-hint { color: var(--ink-muted); font-size: 88%; }
.tab-strip { display: flex; gap: 8px; margin-bottom: 8px; }
.fold { border-bottom: 1px solid var(--line); }
.asset { margin: 12px 0; }
.asset-img { max-width: 100%; height: auto; cursor: zoom-in; }
.asset-caption { color: var(--ink-muted); font-size: 88%; }
.diagram svg { max-width: 100%; height: auto; }
.ic { width: 1.1em; height: 1.1em; vertical-align: -0.15em; color: var(--pop-primary-deep); }
.memo, .memo-global {
  border: 1px dashed var(--line);
  border-radius: var(--card-radius);
  padding: 12px;
  margin-top: 12px;
  background: var(--pop-bg);
}
.memo-body { width: 100%; min-height: 4.5em; border: 1px solid var(--line); border-radius: 12px; }
.toolbar { position: fixed; right: 16px; bottom: 16px; z-index: 30; }
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: var(--ink);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}
.lightbox[hidden] { display: none; }
.lightbox-stage img { max-width: 92vw; max-height: 82vh; }
a:focus-visible, button:focus-visible, summary:focus-visible, input:focus-visible,
textarea:focus-visible {
  outline: 3px solid var(--pop-primary-deep);
  outline-offset: 2px;
}
@keyframes rise-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  * { animation: none; transition: none; }
}
@page { size: A4; margin: 14mm; }
@media print {
  .pop-header { position: static; }
  .toolbar { position: static; }
  .lightbox { display: none; }
  [data-hb-part="{LIGHTBOX}"] { display: none; }
  [data-hb-part="{TOOLBAR}"] { display: none; }
  [data-hb-part="{MEMO}"] { display: none; }
  [data-hb-part="{MEMO_GLOBAL}"] { display: none; }
  .section-card { break-inside: avoid; page-break-inside: avoid; }
  h1, h2, h3, h4, h5, h6 { break-after: avoid; break-inside: avoid; }
}
"""
    rest = (rest
            .replace("{NAV}", str(NAV_OFFSET_PX))
            .replace("{PALT}", str(body_feature))
            .replace("{TABULAR}", str(numeric.get("font_variant_numeric") or "tabular-nums"))
            .replace("{TRACKING}", str(numeric.get("letter_spacing") or "-0.015em"))
            .replace("{LIGHTBOX}", MARKER_LIGHTBOX)
            .replace("{TOOLBAR}", MARKER_TOOLBAR)
            .replace("{MEMO_GLOBAL}", MARKER_MEMO_GLOBAL)
            .replace("{MEMO}", MARKER_MEMO))
    return "\n".join(lines) + rest


SCRIPT_BODY = """'use strict';
(function () {
  var STORE_PREFIX = 'handout:';
  var SLUG = document.documentElement.getAttribute('data-hb-subject-slug') || '';

  function storeKey(kind, id) {
    return STORE_PREFIX + SLUG + ':' + kind + ':' + id;
  }

  function headerOffset() {
    var header = document.querySelector('.pop-header');
    if (!header) { return 0; }
    return Math.ceil(header.getBoundingClientRect().height);
  }

  function jumpTo(id) {
    var target = document.getElementById(id);
    if (!target) { return; }
    var y = target.getBoundingClientRect().top + window.pageYOffset - headerOffset() - 8;
    window.scrollTo(0, y < 0 ? 0 : y);
  }

  function wireNav() {
    var links = document.querySelectorAll('.navbar a[href^="#"]');
    Array.prototype.forEach.call(links, function (link) {
      link.addEventListener('click', function (event) {
        event.preventDefault();
        var id = link.getAttribute('href').slice(1);
        jumpTo(id);
        if (window.history && window.history.replaceState) {
          window.history.replaceState(null, '', link.getAttribute('href'));
        }
      });
    });
  }

  function wireToggles() {
    var toggles = document.querySelectorAll('[aria-pressed]');
    Array.prototype.forEach.call(toggles, function (node) {
      node.addEventListener('click', function () {
        var group = node.closest('[data-hb-single="true"]');
        var on = node.getAttribute('aria-pressed') !== 'true';
        if (group && on) {
          Array.prototype.forEach.call(
            group.querySelectorAll('[aria-pressed="true"]'), function (other) {
              other.setAttribute('aria-pressed', 'false');
            });
        }
        node.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    });
  }

  function wireTabs() {
    var strips = document.querySelectorAll('[role="tablist"]');
    Array.prototype.forEach.call(strips, function (strip) {
      var tabs = strip.querySelectorAll('[role="tab"]');
      Array.prototype.forEach.call(tabs, function (tab) {
        tab.addEventListener('click', function () {
          Array.prototype.forEach.call(tabs, function (other) {
            var selected = other === tab;
            other.setAttribute('aria-selected', selected ? 'true' : 'false');
            var panel = document.getElementById(other.getAttribute('aria-controls'));
            if (!panel) { return; }
            if (selected) { panel.removeAttribute('hidden'); }
            else { panel.setAttribute('hidden', ''); }
          });
        });
      });
    });
  }

  function wireCheckboxes() {
    var boxes = document.querySelectorAll('.check-row input[type="checkbox"]');
    Array.prototype.forEach.call(boxes, function (box) {
      var key = storeKey('check', box.id);
      try {
        box.checked = window.localStorage.getItem(key) === '1';
      } catch (err) { /* 保存不可でも本文は読める */ }
      box.addEventListener('change', function () {
        try {
          window.localStorage.setItem(key, box.checked ? '1' : '0');
        } catch (err) { /* noop */ }
      });
    });
  }

  function memoFields() {
    return document.querySelectorAll('.memo-body');
  }

  function wireMemo() {
    Array.prototype.forEach.call(memoFields(), function (field) {
      var key = storeKey('memo', field.id);
      try {
        field.value = window.localStorage.getItem(key) || '';
      } catch (err) { /* noop */ }
      field.addEventListener('input', function () {
        try { window.localStorage.setItem(key, field.value); } catch (err) { /* noop */ }
      });
    });
  }

  function collectMemo() {
    var out = [];
    Array.prototype.forEach.call(memoFields(), function (field) {
      if (field.value) {
        out.push('# ' + (field.getAttribute('data-hb-key') || '') + '\\n' + field.value);
      }
    });
    return out.join('\\n\\n');
  }

  function wireMemoActions() {
    var copyBtn = document.querySelector('[data-hb-action="copy"]');
    var saveBtn = document.querySelector('[data-hb-action="save"]');
    var clearBtn = document.querySelector('[data-hb-action="clear"]');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        var text = collectMemo();
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text);
        }
      });
    }
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var body = encodeURIComponent(collectMemo());
        var link = document.createElement('a');
        link.setAttribute('href', 'data:text/plain;charset=utf-8,' + body);
        link.setAttribute('download', (SLUG || 'handout') + '-memo.txt');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        Array.prototype.forEach.call(memoFields(), function (field) {
          field.value = '';
          try {
            window.localStorage.removeItem(storeKey('memo', field.id));
          } catch (err) { /* noop */ }
        });
      });
    }
  }

  function wireLightbox() {
    var box = document.querySelector('[data-hb-part="__LIGHTBOX__"]');
    if (!box) { return; }
    var stage = box.querySelector('.lightbox-stage');
    var closeBtn = box.querySelector('.lightbox-close');
    function close() {
      box.setAttribute('hidden', '');
      if (stage) { stage.innerHTML = ''; }
    }
    if (closeBtn) { closeBtn.addEventListener('click', close); }
    box.addEventListener('click', function (event) {
      if (event.target === box) { close(); }
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { close(); }
    });
    var images = document.querySelectorAll('.asset-img');
    Array.prototype.forEach.call(images, function (image) {
      image.addEventListener('click', function () {
        if (!stage) { return; }
        var big = document.createElement('img');
        big.setAttribute('src', image.getAttribute('src'));
        big.setAttribute('alt', image.getAttribute('alt') || '');
        stage.innerHTML = '';
        stage.appendChild(big);
        box.removeAttribute('hidden');
      });
    });
  }

  function wireToolbar() {
    var toggle = document.querySelector('.toolbar-toggle');
    if (!toggle) { return; }
    toggle.addEventListener('click', function () {
      var on = toggle.getAttribute('aria-pressed') === 'true';
      Array.prototype.forEach.call(
        document.querySelectorAll('[data-hb-part="__MEMO__"]'), function (node) {
          node.style.display = on ? '' : 'none';
        });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    wireNav();
    wireToggles();
    wireTabs();
    wireCheckboxes();
    wireMemo();
    wireMemoActions();
    wireLightbox();
    wireToolbar();
    if (window.location.hash.length > 1) {
      jumpTo(window.location.hash.slice(1));
    }
  });
}());
"""


def build_script() -> str:
    return (SCRIPT_BODY
            .replace("__LIGHTBOX__", MARKER_LIGHTBOX)
            .replace("__MEMO__", MARKER_MEMO))


# ---------------------------------------------------------------------------
# 文書の組み立て
# ---------------------------------------------------------------------------


def stagger_style(index) -> str:
    return "--stagger: {}ms".format(min(index * STAGGER_STEP_MS, STAGGER_CAP_MS))


ICON_ACCESSIBLE_NAME_KEY = "title"


def decorative_icon_set(icon_set):
    """C11 はアイコンを装飾として置く (意味は隣の可読テキストが持つ)。

    C15 の sprite 外殻は aria-hidden="true" 固定なので、symbol 側に
    アクセシブル名 (<title>) を残すと「隠しているのに名前がある」矛盾になる。
    C11 の文書ではアイコンに名前を与えないため、名前欄を落として渡す。
    """
    projected = OrderedDict(icon_set)
    icons = []
    for icon in icon_set.get("icons") or []:
        entry = OrderedDict(icon)
        entry.pop(ICON_ACCESSIBLE_NAME_KEY, None)
        icons.append(entry)
    projected["icons"] = icons
    return projected


def build_doc_head(config) -> str:
    """日付表記を文書の冒頭 (header 要素の内側) へ 1 個だけ出す。

    sticky ナビ (B01) は生成 chrome なので `data-hb-generated="true"` を持ち、
    抽出器はその部分木を丸ごと読み飛ばす。日付は著者記述であり読み飛ばして
    よい値ではないので、ナビとは別の header 要素へ置く。
    """
    return tag("header", [("class", "doc-head")],
               '<p class="doc-date">{}</p>'.format(
                   field_span("date", config.get("date"), klass="date-pill num")))


def build_hero(config, hero_part) -> str:
    parts = []
    parts.append('<h1 data-hb-field="title">{}</h1>'.format(esc(config.get("title"))))
    parts.append('<p class="hero-meta">')
    parts.append(field_span("duration", config.get("duration"), klass="hero-duration num"))
    parts.append("</p>")
    if _nonempty(config.get("lead")):
        parts.append('<p class="hero-lead">{}</p>'.format(esc(config.get("lead"))))
    parts.append('<p class="hero-purpose"><span class="hero-label">目的</span>'
                 + field_span("purpose", config.get("purpose")) + "</p>")
    parts.append('<p class="hero-background"><span class="hero-label">背景</span>'
                 + field_span("background", config.get("background")) + "</p>")
    parts.append('<p class="hero-goal"><span class="hero-label">ゴール</span>'
                 + field_span("goal", config.get("goal")) + "</p>")

    chips = []
    for chip in config.get("goal_chips") or []:
        chips.append('<span class="goal-chip">{}</span>'.format(esc(chip)))
    if chips:
        parts.append('<p class="goal-chips">{}</p>'.format("".join(chips)))

    focus = config.get("focus_theme") or []
    if focus:
        items = "".join(
            field_span("focus_theme", value, element="li") for value in focus)
        parts.append('<ul class="meta-list focus-theme">{}</ul>'.format(items))

    tasks = config.get("target_tasks") or []
    if tasks:
        items = []
        for task in tasks:
            label = task.get("label") if isinstance(task, dict) else task
            extra = []
            if isinstance(task, dict) and _nonempty(task.get("id")):
                extra.append(("data-hb-key", task.get("id")))
            items.append(field_span("target_task", label, element="li", extra=extra))
        parts.append('<ul class="meta-list target-tasks">{}</ul>'.format("".join(items)))

    if _nonempty(config.get("attainment_level")):
        parts.append('<p class="attainment">'
                     + field_span("attainment_level", config.get("attainment_level"))
                     + "</p>")

    must = config.get("must_remember") or []
    if must:
        items = "".join(field_span("must_remember", value, element="li") for value in must)
        parts.append('<ul class="meta-list must-remember">{}</ul>'.format(items))
    no_need = config.get("no_need_to_remember") or []
    if no_need:
        items = "".join(
            field_span("no_need_to_remember", value, element="li") for value in no_need)
        parts.append('<ul class="meta-list no-need">{}</ul>'.format(items))

    # ヒーローの「枠」だけが再生成可能な chrome である。枠の内側に並ぶのは
    # 著者が書いた文書レベルの記述そのものなので、読み飛ばし境界を枠の要素へ
    # 限定する (枠を空の装飾要素として独立させ、著者記述はその外側へ置く)。
    frame = tag("div", [
        ("class", "hero-frame"),
        ("data-hb-part", hero_part),
        ("data-hb-part-id", "{}-1".format(hero_part.lower())),
        ("data-hb-generated", "true"),
        ("aria-hidden", "true"),
    ], "")
    return tag("div", [
        ("class", "hero"),
        ("style", stagger_style(0)),
    ], frame + "".join(parts))


def build_nav(config, nav_part) -> str:
    goals = {}
    for section in config.get("sections") or []:
        goals[section.get("id")] = section.get("goal")
    links = []
    for entry in config.get("nav") or []:
        href = entry.get("href")
        sid = href[1:]
        links.append(tag("a", [
            ("href", href),
            ("data-hb-nav-goal", goals.get(sid, "")),
            ("title", goals.get(sid, "")),
            ("aria-describedby", "goal-{}".format(sid)),
        ], esc(entry.get("label"))))
    nav = tag("nav", [("class", "navbar"), ("aria-label", "目次")], "".join(links))
    return tag("header", [
        ("class", "pop-header"),
        ("data-hb-part", nav_part),
        ("data-hb-part-id", "{}-1".format(nav_part.lower())),
        ("data-hb-generated", "true"),
    ], nav)


def build_glossary(entries, scope) -> str:
    """宣言用語の言い換え表。判定は C18 の責務で、C11 は所在を属性で示すだけ。"""
    if not entries:
        return ""
    rows = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        rows.append(
            tag("div", [
                ("class", "glossary-row"),
                ("data-hb-key", entry_key(entry, index)),
                ("data-hb-glossary-term", entry.get("term", "")),
                ("data-hb-glossary-plain", entry.get("plain", "")),
                ("data-hb-glossary-scope", scope),
            ],
                '<dt class="glossary-term">{}</dt>'
                '<dd class="glossary-plain">{}</dd>'.format(
                    esc(entry.get("term")), esc(entry.get("plain"))))
        )
    if not rows:
        return ""
    return tag("dl", [("class", "glossary")], "".join(rows))


def build_memo(scope_id) -> str:
    field_id = "memo-{}".format(scope_id)
    inner = (
        '<label class="memo-label" for="{0}">このセクションのメモ</label>'
        '<textarea class="memo-body" id="{0}" data-hb-key="{1}"></textarea>'.format(
            esc(field_id), esc(scope_id))
    )
    return tag("div", [
        ("class", "memo"),
        ("data-hb-part", MARKER_MEMO),
        ("data-hb-generated", "true"),
    ], inner)


def build_memo_global() -> str:
    buttons = (
        '<button type="button" class="memo-btn" data-hb-action="copy">'
        "メモをクリップボードへコピーする</button>"
        '<button type="button" class="memo-btn" data-hb-action="save">'
        "メモをファイルへ download する</button>"
        '<button type="button" class="memo-btn" data-hb-action="clear">'
        "メモを clear する</button>"
    )
    inner = (
        '<h2 class="memo-title">全体メモ</h2>'
        '<label class="memo-label" for="memo-all">資料全体のメモ</label>'
        '<textarea class="memo-body" id="memo-all" data-hb-key="all"></textarea>'
        + buttons
    )
    return tag("div", [
        ("class", "memo-global"),
        ("data-hb-part", MARKER_MEMO_GLOBAL),
        ("data-hb-generated", "true"),
    ], inner)


def build_lightbox() -> str:
    inner = (
        '<button type="button" class="lightbox-close">閉じる</button>'
        '<div class="lightbox-stage"></div>'
    )
    return tag("div", [
        ("class", "lightbox"),
        ("data-hb-part", MARKER_LIGHTBOX),
        ("data-hb-generated", "true"),
        ("role", "dialog"),
        ("aria-modal", "true"),
        ("aria-label", "画像の拡大表示"),
        ("hidden", True),
    ], inner)


def build_toolbar() -> str:
    inner = (
        '<button type="button" class="toolbar-toggle" aria-pressed="false" '
        'data-hb-part-role="aux">メモ欄の表示を切り替える</button>'
    )
    return tag("div", [
        ("class", "toolbar"),
        ("data-hb-part", MARKER_TOOLBAR),
        ("data-hb-generated", "true"),
    ], inner)


TOKEN_LIST_SEPARATOR = " "


def serialize_token_list(value) -> str:
    """トークン列を属性値へ直列化する。

    形式の正本は schemas/ROUNDTRIP-CONTRACT.md の裁定
    (`/sections/*/ties_to` の required_serialization):
    半角スペース区切りのトークン列。空配列は空文字列。
    Python の list をそのまま埋めると repr が漏れて読み戻せない。
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return TOKEN_LIST_SEPARATOR.join(str(item) for item in value)
    return str(value)


def build_section(renderer, section, index) -> str:
    sid = section.get("id")
    renderer.ctx["section_heading"] = section.get("heading")
    parts = []
    # 連番は index から再生成できる派生物なので、見出しの素値を運ぶ要素の
    # 外へ出す (見出しのテキストへ連番が混ざると素値へ戻せない)。
    parts.append('<h2 class="section-label"><span class="section-num num">{}</span>{}</h2>'.format(
        index + 1,
        field_span("heading", section.get("heading"), klass="section-heading")))
    parts.append(tag("p", [
        ("class", "goal-chip section-goal"),
        ("id", "goal-{}".format(sid)),
        ("data-hb-field", "section_goal"),
    ], esc(section.get("goal"))))
    parts.append(tag("p", [("class", "lead-line"), ("data-hb-field", "lead_line")],
                     esc(section.get("lead_line"))))
    if _nonempty(section.get("duration")):
        parts.append(field_span("section_duration", section.get("duration"),
                                klass="section-duration num"))
    for block in section.get("blocks") or []:
        parts.append(renderer.block(block))
    parts.append(tag("p", [("class", "judgment-axis"), ("data-hb-field", "judgment_axis")],
                     esc(section.get("judgment_axis"))))
    parts.append(build_glossary(section.get("glossary"), sid))
    parts.append(build_memo(sid))

    return tag("section", [
        ("id", sid),
        ("class", "section-card"),
        ("data-hb-part", MARKER_SECTION),
        ("data-hb-section-kind", section.get("section_kind", "")),
        ("data-hb-section-role", section.get("role", "")),
        ("data-hb-ties-to", serialize_token_list(section.get("ties_to"))),
        ("data-hb-attainment-step", section.get("attainment_step")
         if _nonempty(section.get("attainment_step")) else None),
        ("style", stagger_style(index + 1)),
    ], "".join(parts))


def render_document(config, theme, tokens, modules):
    catalog_markers = structure_markers()
    for marker in (MARKER_SECTION, MARKER_LIGHTBOX, MARKER_MEMO,
                   MARKER_MEMO_GLOBAL, MARKER_TOOLBAR):
        if marker not in catalog_markers:
            raise LaunchError(
                "構造マーカー {!r} が部品カタログの宣言に無い".format(marker))

    nav_part, hero_part = document_part_ids()

    assets = OrderedDict()
    for asset in config.get("assets") or []:
        if isinstance(asset, dict) and _nonempty(asset.get("id")):
            assets[asset["id"]] = asset

    ctx = {
        "assets": assets,
        "part_by_type": part_id_by_block_type(),
        "blocks_by_type": OrderedDict(),
        "embedded_bytes": 0,
        "diagrams": 0,
        "diagram_module": modules["diagram"],
        "doc_title": config.get("title"),
        "section_heading": "",
    }
    renderer = Renderer(ctx)

    sections_html = []
    for index, section in enumerate(config.get("sections") or []):
        sections_html.append(build_section(renderer, section, index))

    for attachment in config.get("attachments") or []:
        if isinstance(attachment, dict):
            ctx["embedded_bytes"] += data_uri_bytes(attachment.get("data_uri"))

    sprite = modules["sprite"].build_sprite(
        OrderedDict([("sections", config.get("sections") or [])]),
        decorative_icon_set(modules["icon_set"]),
        scan_emoji=modules["scan_emoji"],
    )
    icons_used = [entry["name"] for entry in sprite["used"]]

    detail_level = config.get("detail_level") or ""
    evidence_depth = config.get("evidence_depth") or ""
    provenance = config.get("provenance") or {}

    html_attrs = [
        ("lang", "ja"),
        ("data-hb-schema-version", config.get("schema_version", "")),
        ("data-hb-doc-type", config.get("doc_type", "")),
        ("data-hb-subject-slug", config.get("subject_slug", "")),
        # data-hb-theme は解決後の実効テーマ (CSS / 表示向け)。既定値の解決を
        # 経ているため、著者が theme 欄を書いたかどうかはここからは分からない。
        # round-trip はその区別を要するので、著者が書いた値を別の印で運ぶ。
        ("data-hb-theme", theme),
        ("data-hb-config-theme", config.get("theme") or ""),
        ("data-hb-meta-reader", config.get("reader", "")),
        ("data-hb-meta-knowledge", config.get("prior_knowledge_level", "")),
        ("data-hb-meta-problem", config.get("essential_problem", "")),
        ("data-hb-presentation-order", config.get("presentation_order", "")),
        ("data-hb-presentation-order-source",
         provenance.get("presentation_order_source", "")),
        ("data-hb-detail-level", detail_level),
        ("data-hb-evidence-depth", evidence_depth),
        ("data-hb-text-limit", text_limit_for(tokens, detail_level)),
        # ROUNDTRIP-CONTRACT.md の裁定 (/notes_enabled = marker)。メモ UI の
        # 有無からは推定させない (メモ UI は読み飛ばし対象の chrome である)。
        ("data-hb-notes-enabled",
         "false" if config.get("notes_enabled") is False else "true"),
        # 覚える項目の上限。整数 1 個なので属性 1 本で無損失に運べる。
        ("data-hb-must-remember-max",
         "" if config.get("must_remember_max") is None
         else str(config.get("must_remember_max"))),
    ]

    body = [
        sprite["symbols_svg"],
        build_doc_head(config),
        build_nav(config, nav_part),
        '<main class="wrap">',
        build_hero(config, hero_part),
        "".join(sections_html),
        build_glossary(config.get("glossary"), SECTION_SCOPE_DOCUMENT),
        build_memo_global(),
        "</main>",
        build_lightbox(),
        build_toolbar(),
        "<script>\n{}</script>".format(build_script()),
    ]

    document = "\n".join([
        "<!DOCTYPE html>",
        "<html{}>".format(attrs_to_str(html_attrs)),
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>{}</title>".format(esc(config.get("title"))),
        "<style>\n{}</style>".format(build_css(tokens)),
        "</head>",
        '<body class="handout">',
        "\n".join(item for item in body if item),
        "</body>",
        "</html>",
    ]) + "\n"

    stats = {
        "sections": len(config.get("sections") or []),
        "blocks_by_type": dict(ctx["blocks_by_type"]),
        "icons_used": icons_used,
        "diagrams": ctx["diagrams"],
        "embedded_bytes": ctx["embedded_bytes"],
    }
    return document, stats


# ---------------------------------------------------------------------------
# 出力前の門 (CR-EXT / CR-EMOJI は C16 の実装点だけを呼ぶ)
# ---------------------------------------------------------------------------


def gate_output(document, selfcontained):
    problems = []
    for violation in selfcontained.scan_external_references(document):
        problems.append("{} {}:{} {} — {}".format(
            violation.detection_id, violation.line, violation.col,
            violation.message, violation.evidence))
    for violation in selfcontained.scan_emoji(document):
        problems.append("{} {}:{} {} — {}".format(
            violation.detection_id, violation.line, violation.col,
            violation.message, violation.evidence))
    if problems:
        raise DataError(problems)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


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
    parser = _Parser(prog="render-handout.py", add_help=True)
    parser.add_argument("--config", required=True, help="正規化済み構成データ JSON")
    parser.add_argument("--theme", default=None, help="テーマ名 (--config-out と併用)")
    parser.add_argument("--out", default=None, help="生成 HTML の書き出し先")
    parser.add_argument("--config-out", dest="config_out", default=None,
                        help="テーマ確定後の構成データの書き出し先")
    return parser


def load_modules():
    selfcontained = load_peer_module(SELFCONTAINED_RELPATH, "C16 の自己完結判定モジュール")
    for export in ("scan_external_references", "scan_emoji"):
        if not callable(getattr(selfcontained, export, None)):
            raise LaunchError("{} が {}() を公開していない".format(
                SELFCONTAINED_RELPATH, export))
    sprite = load_peer_module(SPRITE_RELPATH, "C15 の sprite 生成モジュール")
    diagram = load_peer_module(DIAGRAM_RELPATH, "C14 の図解描画モジュール")
    preset = load_peer_module(PRESET_RELPATH, "C23 の用途語彙モジュール")
    icon_set = read_json(
        resolve_under_roots(ICON_SET_RELPATH, "アイコンセット正本"), "アイコンセット正本")
    return {
        "selfcontained": selfcontained,
        "scan_emoji": selfcontained.scan_emoji,
        "sprite": sprite,
        "diagram": diagram,
        "preset": preset,
        "icon_set": icon_set,
    }


def run(args) -> int:
    config_path = Path(args.config)
    if not config_path.is_file():
        raise LaunchError("--config のファイルが存在しない: {}".format(config_path))
    config = read_json(config_path, "構成データ")

    if args.theme is not None and args.config_out is None:
        raise LaunchError(
            "--theme はテーマ欄の書き戻し先を要する。--config-out を併せて指定すること")

    out_path = Path(args.out) if args.out else None
    if out_path is not None and not out_path.parent.is_dir():
        raise LaunchError(
            "--out の親ディレクトリが存在しない (掘るのは C19 の責務): {}".format(
                out_path.parent))

    modules = load_modules()

    if args.theme is not None and _nonempty(config.get("theme")):
        raise DataError(
            "theme: 構成データがテーマ欄を持つのに --theme も指定されている "
            "(テーマの決定点は 1 つだけ)")

    # schema 正本の方言で書かれた構成データは描画モデルへ投影してから検査する。
    # 書き戻し (--config-out) の対象は投影前の入力そのものであり、投影結果を
    # 構成データとして外へ出さない (二重方言を保存しない)。
    render_config = project_schema_config(config) if has_schema_dialect(config) else config

    validate_config(render_config, modules["preset"])

    if _nonempty(render_config.get("theme")):
        theme = str(render_config["theme"])
    elif args.theme is not None:
        theme = str(args.theme)
    else:
        theme = default_theme_name()
    tokens = load_theme_tokens(theme)

    # --theme の採用値は下で --config-out へ書き戻され、その書き戻し後の構成データが
    # 資料の再現単位になる。ここで render_config へも同じ値を落としておかないと
    # data-hb-config-theme だけが空のまま焼かれ、「同梱構成データから再生成すると
    # 1 属性だけ違う HTML が出る」= 起動引数が再現単位に混ざった状態になる。
    if args.theme is not None:
        render_config = OrderedDict(render_config)
        render_config["theme"] = theme

    document, stats = render_document(render_config, theme, tokens, modules)
    gate_output(document, modules["selfcontained"])

    warnings = []
    if stats["embedded_bytes"] > EMBED_REPORT_THRESHOLD:
        warnings.append(
            "埋め込み実体の実測値が報告しきい値を超えている: {} バイト "
            "(上限判断は C13 embed-* の責務。C11 は報告に留める)".format(
                stats["embedded_bytes"]))

    config_written = None
    if args.theme is not None:
        written = OrderedDict(config)
        written["theme"] = theme
        target = Path(args.config_out)
        if not target.parent.is_dir():
            raise LaunchError(
                "--config-out の親ディレクトリが存在しない: {}".format(target.parent))
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(written, ensure_ascii=False, indent=2) + "\n")
        config_written = str(target)

    if out_path is None:
        sys.stdout.write(document)
        return 0

    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(document)

    payload = OrderedDict([
        ("html_path", str(out_path)),
        ("bytes", len(document.encode("utf-8"))),
        ("sections", stats["sections"]),
        ("blocks_by_type", stats["blocks_by_type"]),
        ("icons_used", stats["icons_used"]),
        ("diagrams", stats["diagrams"]),
        ("embedded_bytes", stats["embedded_bytes"]),
        ("theme", theme),
        ("config_written", config_written),
        ("warnings", warnings),
    ])
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=False) + "\n")
    return 0


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    except UsageError as exc:
        sys.stderr.write("ERROR\t引数が不正: {}\n".format(" ".join(str(exc).split())))
        return 2
    try:
        return run(args)
    except DataError as exc:
        for line in exc.diagnostics:
            sys.stderr.write("FAIL\t{}\n".format(line))
        return 1
    except LaunchError as exc:
        for line in exc.diagnostics:
            sys.stderr.write("ERROR\t{}\n".format(line))
        return 2


if __name__ == "__main__":
    sys.exit(main())

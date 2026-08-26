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
import urllib.parse
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
VOCABULARY_RELPATH = "config/handout-vocabulary.json"
VISUAL_POLICY_RELPATH = "config/handout-visual-policy.json"
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

# 目次の置き場所として受理する値。実際にどちらを使うかは
# config/handout-visual-policy.json#nav.layout が決める (ここは受理集合だけ)。
NAV_LAYOUT_SIDEBAR = "sidebar"
NAV_LAYOUT_BAND = "band"
NAV_LAYOUTS = (NAV_LAYOUT_SIDEBAR, NAV_LAYOUT_BAND)

# 本文の入口 (目次を読み飛ばして本文へ跳ぶ先)。id は 1 個しか無いので定数で持つ。
MAIN_ANCHOR_ID = "handout-main"

TEXT_LIMITS_KEY = "text_limits"
DEFAULT_LIMIT_KEY = "block_body_max_chars"
BY_LEVEL_LIMIT_KEY = "block_body_max_chars_by_detail_level"
CSS_VARIABLES_KEY = "css_variables"

DOC_REQUIRED_FIELDS = (
    "title", "date", "reader", "prior_knowledge_level", "doc_type",
    "essential_problem", "purpose", "background", "goal", "sections",
)
SECTION_REQUIRED_FIELDS = ("id", "heading", "goal", "lead_line", "judgment_axis")

SECTION_SCOPE_DOCUMENT = "document"
SECTION_SCOPE_IN_SECTION = "in-section"

MARKER_SECTION = "section"
MARKER_LIGHTBOX = "lightbox"
MARKER_MEMO = "memo"
MARKER_MEMO_GLOBAL = "memo-global"
MARKER_TOOLBAR = "toolbar"

# 節の先頭で見出しの直後に置いてよい部品 (絵)。ここに並ぶ type が節の 1 番目に
# 来ているときだけ、目的・言いたいことより前へ描く (利用者指定 2026-08-19)。
SECTION_LEAD_VISUAL_TYPES = ("image", "diagram")


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


_VOCABULARY_CACHE = None


def load_vocabulary(path=None):
    """表示語彙の単一正本を読む。

    この script は日本語のラベルを 1 つも持たない。コネクタ名も達成段階の
    表示も、構成データが運ぶのは id / enum だけで、読者に見える表記は
    ここから引く。読めないときは既定の表記へ落とさず落ちる — 落とすと
    『語彙を書き換えたのに表示が変わらない』という無言の食い違いが出る。
    """
    global _VOCABULARY_CACHE
    if path is None and _VOCABULARY_CACHE is not None:
        return _VOCABULARY_CACHE
    target = Path(path) if path is not None else resolve_under_roots(
        VOCABULARY_RELPATH, "表示語彙正本")
    data = read_json(target, "表示語彙正本")
    if not isinstance(data, dict):
        raise LaunchError("表示語彙正本の形が壊れている: {}".format(target))
    if path is None:
        _VOCABULARY_CACHE = data
    return data


def vocabulary_labels(group, key_field):
    entries = (load_vocabulary().get(group) or {}).get("entries")
    if not isinstance(entries, list):
        raise LaunchError("表示語彙正本に {}.entries が無い".format(group))
    labels = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get(key_field), str):
            labels[entry[key_field]] = entry.get("label")
    return labels


_VISUAL_POLICY_CACHE = None


def load_visual_policy(path=None):
    """視覚方針の正本を読む。"""
    global _VISUAL_POLICY_CACHE
    if path is None and _VISUAL_POLICY_CACHE is not None:
        return _VISUAL_POLICY_CACHE
    target = Path(path) if path is not None else resolve_under_roots(
        VISUAL_POLICY_RELPATH, "視覚方針正本")
    data = read_json(target, "視覚方針正本")
    if not isinstance(data, dict):
        raise LaunchError("視覚方針正本の形が壊れている: {}".format(target))
    if path is None:
        _VISUAL_POLICY_CACHE = data
    return data


def hero_card_order():
    """冒頭カードの並び順を正本から引く。

    順序を script の定数で持たない。持つと『正本を書き換えたのに並びが
    変わらない』食い違いが出るうえ、順序を検査する C22 と描画する C11 が
    それぞれ別の順序を持つ二名簿になる。読めなければ既定順へ落とさず落ちる
    (利用者要求 R3 のゴール先頭は既定値で黙って崩れてよい性質ではない)。
    """
    order = (((load_visual_policy().get("opening") or {})
              .get("hero_card_fields") or {}).get("order"))
    if not isinstance(order, list) or not order:
        raise LaunchError(
            "視覚方針正本に opening.hero_card_fields.order が無い "
            "(冒頭カードの並び順の単一正本)")
    names = [name for name in order if isinstance(name, str) and name]
    if not names:
        raise LaunchError("opening.hero_card_fields.order が空")
    return names


def nav_max_rows() -> int:
    """目次を帯として出すときに占めてよい行数。正本は nav.max_rows。

    節数が増えると 1 行に収まらなくなる。何行まで見せるかは読み手の視野の
    問題であり、描画側の定数ではない (既定値へ落とさず、無ければ落とす)。
    layout=sidebar では柱に縦積みするため、この上限は帯へ戻す幅
    (nav.collapse_below_px 未満) と印刷でだけ効く。
    """
    value = (load_visual_policy().get("nav") or {}).get("max_rows")
    if not isinstance(value, int) or value < 1:
        raise LaunchError(
            "視覚方針正本に nav.max_rows (正の整数) が無い "
            "(目次の帯の行数上限の単一正本)")
    return value


def nav_positive_int(key: str, why: str) -> int:
    """nav 配下の寸法を 1 個引く。既定値へ落とさず、無ければ落とす。"""
    value = (load_visual_policy().get("nav") or {}).get(key)
    if not isinstance(value, int) or value < 1:
        raise LaunchError(
            "視覚方針正本に nav.{} (正の整数) が無い ({})".format(key, why))
    return value


def nav_collapse_below_px() -> int:
    """柱をやめて帯へ戻す画面幅。正本は nav.collapse_below_px。"""
    return nav_positive_int(
        "collapse_below_px", "目次を柱から帯へ戻す画面幅の単一正本")


def nav_layout() -> str:
    """目次の置き場所。正本は nav.layout。

    `sidebar` は左の柱 (常時表示・左揃え)、`band` は従来の上帯。どちらでも
    sticky は維持するので「スクロールしても目次が消えない」は共通。値を
    描画側の既定へ落とさないのは、置き場所が読み手の視野設計そのものであり
    資料ごとに正本で決まるべきものだから。
    """
    value = (load_visual_policy().get("nav") or {}).get("layout")
    if value not in NAV_LAYOUTS:
        raise LaunchError(
            "視覚方針正本の nav.layout が {} のいずれでもない "
            "(目次の置き場所の単一正本)".format(" / ".join(NAV_LAYOUTS)))
    return value


def section_number_separator() -> str:
    """節番号と見出しの間に置く記号。正本は opening.section_heading.number_separator。"""
    value = ((load_visual_policy().get("opening") or {})
             .get("section_heading") or {}).get("number_separator")
    if not isinstance(value, str) or not value:
        raise LaunchError(
            "視覚方針正本に opening.section_heading.number_separator が無い "
            "(節番号と見出しの区切り記号の単一正本)")
    return value


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
               ("detail", row.get("sub")))
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
    # --nav-h は「本文の上に目次が被る量」。柱では被らないので 0 になり、
    # 帯へ戻る幅 (下の @media) でだけ NAV_OFFSET_PX へ戻す。
    lines.append("  --nav-h: {}px;".format(
        0 if nav_layout() == NAV_LAYOUT_SIDEBAR else NAV_OFFSET_PX))
    lines.append("  --side-nav-w: {}px;".format(
        nav_positive_int("sidebar_width_px", "目次の柱の幅の単一正本")))
    for name, value in variables.items():
        lines.append("  {}: {};".format(name, value))
    lines.append("}")
    typography = tokens.get("typography") or {}
    numeric = typography.get("numeric") or {}
    body_feature = (typography.get("body") or {}).get("font_feature_settings") or '"palt"'
    rest = """
* { box-sizing: border-box; }
/* 停止位置の余白は 2 段に分ける。ここは節の上へ必ず空ける最小の余白 (定数)、
   目次に被る分は .section-card の scroll-margin-top (--nav-h) が足す。
   柱では --nav-h が 0 になるため、残るのはこの余白だけになる。 */
html { scroll-padding-top: 12px; }
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
  /* 本文がナビ帯の下へ潜るとき、境界が線 1 本だと重なりが読めない。
     影は高さを持たないので sticky のオフセット計算 (--nav-h) に影響しない。 */
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.06);
}
/* 節が増えても目次を隠さない。1 行に収まらなくなったら横スクロールではなく
   折り返して 2 行目へ回す (横スクロールは「まだ右に項目がある」ことが見えない)。
   行数の上限は config/handout-visual-policy.json#nav.max_rows が正本で、
   そこを超えた分だけこの帯の中で縦スクロールする。帯そのものは sticky なので
   どこまでスクロールしても目次は消えない。 */
/* 目次を左の柱へ置く (nav.layout=sidebar)。柱は本文と横に並ぶので、
   縦は 100vh を丸ごと使えて全項目が一望でき、本文の上には一切被らない
   (--nav-h が 0 になるのはこのため)。柱の中で溢れた分だけが柱の中で
   縦スクロールし、柱そのものは sticky なのでどこまで読んでも消えない。 */
.page-shell { display: block; }
/* 柱は DOM 上つねに本文より前にある。キーボードで読む人は毎回すべての札を
   通り抜けないと本文へ入れないので、最初の Tab で本文へ跳べる出口を置く。
   display:none にすると focus できないため、幅 1px へ畳んで隠し、
   focus されたときだけ柱の上へ現れる (マウスで読む人の紙面は変わらない)。 */
.skip-to-main {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.skip-to-main:focus {
  position: fixed;
  top: 8px;
  left: 8px;
  z-index: 40;
  width: auto;
  height: auto;
  margin: 0;
  padding: 8px 14px;
  clip-path: none;
  border-radius: 999px;
  background: var(--pop-primary-deep);
  color: #fff;
  font-size: 0.85rem;
  font-weight: 700;
  text-decoration: none;
}
.doc-title-bar {
  margin: 0;
  padding: 8px 16px 0;
  text-align: center;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.navbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
  align-content: flex-start;
  max-height: calc({NAV_ROWS} * 2.5rem + 20px);
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 10px 16px;
  scrollbar-width: thin;
}
@media (min-width: {NAV_COLLAPSE}px) {
  .page-shell {
    display: grid;
    /* 柱の幅は正本 (nav.sidebar_width_px)。本文側は minmax(0,1fr) にする —
       auto のままだと図表 1 枚が列幅を押し広げ、柱ごと横スクロールになる。 */
    grid-template-columns: var(--side-nav-w) minmax(0, 1fr);
    align-items: start;
  }
  .pop-header--sidebar {
    display: flex;
    flex-direction: column;
    height: 100vh;
    height: 100dvh;
    border-bottom: none;
    border-right: 1px solid var(--line);
    box-shadow: 1px 0 6px rgba(15, 23, 42, 0.06);
  }
  .pop-header--sidebar .doc-title-bar {
    /* 左揃え。柱では行頭が視線の起点になるため、題も札も同じ縦線へ揃える。 */
    text-align: left;
    white-space: normal;
    padding: 14px 14px 10px;
    border-bottom: 1px solid var(--line);
  }
  .pop-header--sidebar .navbar {
    flex-direction: column;
    flex-wrap: nowrap;
    justify-content: flex-start;
    align-items: stretch;
    gap: 4px;
    flex: 1 1 auto;
    min-height: 0;
    max-height: none;
    padding: 10px;
  }
  .pop-header--sidebar .nav-chip {
    max-width: none;
    width: 100%;
    justify-content: flex-start;
    text-align: left;
    border-radius: 10px;
    border-color: transparent;
    background: transparent;
  }
  .pop-header--sidebar .nav-chip:hover,
  .pop-header--sidebar .nav-chip:focus-visible { background: #fff; }
  .pop-header--sidebar .nav-chip[aria-current="true"] {
    background: var(--chip-accent);
    border-color: var(--chip-accent);
  }
  /* 下の帯は本文に対する操作なので、柱の上には掛けない。画面幅いっぱいに
     敷くと 100vh の柱の足元 (最後の札) が帯の下に隠れて押せなくなる。 */
  .toolbar { left: var(--side-nav-w); }
}
@media (max-width: {NAV_COLLAPSE_MAX}px) {
  /* 柱を置くと本文が読める幅を割る画面では、従来どおり上の帯へ戻す
     (nav.collapse_below_px が正本)。帯は本文の上に被るので、被る量
     --nav-h を戻さないとアンカー移動でセクション先頭が帯の下へ潜る。 */
  :root { --nav-h: {NAV}px; }
}
.navbar a { color: var(--pop-primary-deep); text-decoration: none; }
.nav-chip {
  /* 単色。未読・既読で色を変えず、現在地だけを塗りで示す。 */
  --chip-accent: var(--pop-primary-deep);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  max-width: 16em;
  padding: 3px 12px 3px 3px;
  /* 未選択の枠は罫線色。全チップを主題色で囲うと現在地の塗りが埋もれる。 */
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  color: var(--chip-accent);
  font-size: 0.9rem;
  line-height: 1.6;
  transition: background-color 0.12s ease, color 0.12s ease;
}
.nav-chip-num {
  flex: 0 0 auto;
  width: 1.5rem;
  height: 1.5rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--chip-accent);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
}
.nav-chip-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nav-chip:hover, .nav-chip:focus-visible { background: var(--subtle); }
.nav-chip[aria-current="true"] {
  background: var(--chip-accent);
  border-color: var(--chip-accent);
  color: #fff;
}
.nav-chip[aria-current="true"] .nav-chip-num { background: #fff; color: var(--chip-accent); }
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
.hero-thumb {
  margin: 0 0 16px;
  border-radius: var(--card-radius);
  overflow: hidden;
  border: 1px solid var(--line);
  background: #fff;
}
.hero-thumb-img {
  display: block;
  width: 100%;
  height: auto;
  /* 縦横比を固定して切り出す。素材の比率がまちまちでも冒頭の高さが揃い、
     タイトルの位置が資料ごとに上下しない。 */
  aspect-ratio: 16 / 9;
  object-fit: cover;
}
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
/* 冒頭は「読む段落」でなく「1 行ずつ拾える箇条書き」。ラベルを行頭の札に固定し、
   本文は 1 列で流す (利用者要求 R9/R3 + 2026-08-25『箇条書きでわかりやすく
   シンプルに』)。3 枚を横へ並べると 1 列が 220px まで細り、1 行 10 字前後で
   折り返して語の途中が切れる — 読みにくさの出所は文の長さでなく列の細さだった。 */
.hero-card-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 16px 0;
  padding: 0;
  list-style: none;
}
/* 面は白 1 色、区別は主題色 1 色の細い帯だけで付ける。新しい色トークンは足さない
   (テーマのアクセント 4 段以外の色を増やさない規約)。ラベル列の幅を固定すると
   3 行の本文の頭が縦に揃い、どこから読むかが迷わずに決まる。 */
.hero-card {
  position: relative;
  display: grid;
  grid-template-columns: 5.5em minmax(0, 1fr);
  align-items: baseline;
  column-gap: 14px;
  row-gap: 4px;
  border: 1px solid var(--line);
  border-left: 4px solid var(--pop-primary);
  border-radius: var(--card-radius);
  padding: 12px 16px;
  background: #fff;
}
/* 狭い画面ではラベル列を畳んで 2 段にする。5.5em を残したまま詰めると本文側が
   さらに細り、横並びカードと同じ折り返しの荒れ方に戻る。 */
@media (max-width: 640px) {
  .hero-card { grid-template-columns: minmax(0, 1fr); }
}
.hero-card-label {
  display: inline-block;
  margin: 0;
  padding: 1px 10px;
  border-radius: 999px;
  background: var(--pop-primary-soft);
  color: var(--pop-primary-deep);
  font-size: 0.8em;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-align: center;
  white-space: nowrap;
}
/* 日本語を語の途中で折らない。auto-phrase は文節の切れ目で折り、未対応の環境でも
   line-break: strict が最低限の禁則を担う (どちらも 1 行の見え方だけを変え、
   可視テキストは変えない = NAR-02 の一致は保たれる)。 */
.hero-card-body {
  margin: 0;
  line-height: 1.9;
  line-break: strict;
  overflow-wrap: break-word;
  word-break: auto-phrase;
  text-wrap: pretty;
}
/* 最初に読む 1 枚 (並び順の先頭 = goal) だけ面を淡く塗って視線の入口にする。 */
.hero-card:first-child { background: var(--pop-primary-soft); }
.hero-card:first-child .hero-card-label { background: #fff; }
/* 見出しの無い ul が縦に積まれると、何の一覧かを知らないまま行を読むことに
   なる。リストごとに見出しを付け、塊として区切る。 */
.hero-list {
  margin: 12px 0;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: var(--card-radius);
  background: #fff;
}
.hero-list-heading {
  display: inline-block;
  margin: 0 0 6px;
  padding: 1px 10px;
  border-radius: 999px;
  background: var(--pop-primary-soft);
  color: var(--pop-primary-deep);
  font-size: 0.8em;
  font-weight: 700;
}
.meta-list { margin: 8px 0; padding-left: 1.2em; }
/* 前提コネクタは「読む文」でなく「並ぶ札」。行頭記号と字下げを外し、
   チップとして横に並べる (箇条書きのまま長い行にしない・R11/R9)。 */
.prerequisite-connectors {
  list-style: none;
  padding-left: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.prerequisite-connectors .connector {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--subtle);
  font-size: 0.92em;
}
.prerequisite-connectors .connector-label { font-weight: 600; }
.prerequisite-connectors .connector-note { color: var(--ink-muted); font-size: 0.9em; }
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
.memo-note { margin: 8px 0; font-size: 0.85rem; color: var(--muted); line-height: 1.7; }
/* 画面下に常駐する帯。メモを残す手段 (埋め込み保存) は、全体メモの箱まで
   スクロールしないと押せない位置に置かない — 押されなければメモは消える。
   利用者指定 2026-08-19『フッターも常に表示。メモを埋め込んだ HTML のボタンは
   常に表示する』。 */
.toolbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  background: var(--subtle);
  border-top: 1px solid var(--line);
  box-shadow: 0 -1px 6px rgba(15, 23, 42, 0.06);
}
/* 帯の下へ本文の最後が潜らないようにする (帯は本文の上に浮いている)。 */
body.handout { padding-bottom: 64px; }
.toolbar-primary {
  background: var(--pop-primary-deep);
  border-color: var(--pop-primary-deep);
  color: #fff;
  font-weight: 700;
}
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
  /* 紙には横スクロールが無い。1 行固定のままだと溢れた項目が黙って消えるため
     折返しへ戻す (sticky でなくなるので高さ可変が無害になる)。
     柱も紙では成立しない (100vh の柱が 1 ページ目を占領する) ので、
     段組みを解いて目次を先頭の帯へ戻す。 */
  .page-shell { display: block; }
  .pop-header--sidebar { height: auto; border-right: none; box-shadow: none; }
  /* 紙に「本文へ移動」は届かない。焦点を持てない媒体では消す。 */
  .skip-to-main, .skip-to-main:focus { display: none; }
  .navbar { flex-wrap: wrap; overflow-x: visible; }
  .pop-header--sidebar .navbar { flex-direction: row; flex-wrap: wrap; max-height: none; overflow: visible; }
  .pop-header--sidebar .nav-chip { width: auto; max-width: 16em; }
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
            .replace("{NAV_ROWS}", str(nav_max_rows()))
            .replace("{NAV_COLLAPSE_MAX}", str(nav_collapse_below_px() - 1))
            .replace("{NAV_COLLAPSE}", str(nav_collapse_below_px()))
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
    var box = header.getBoundingClientRect();
    // 補正したいのは「目次が本文の上に被る量」であって目次の高さではない。
    // 柱 (画面の左端に立つ縦長) は本文に被らないので補正 0。画面幅の過半を
    // 占める帯のときだけ高さを引く (柱の 100vh を引くと行き過ぎる)。
    if (box.width < window.innerWidth * 0.5) { return 0; }
    return Math.ceil(box.height);
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

  function wireNavCurrent() {
    var chips = document.querySelectorAll('.nav-chip[href^="#"]');
    if (!chips.length || !window.IntersectionObserver) { return; }
    var byId = {};
    Array.prototype.forEach.call(chips, function (chip) {
      byId[chip.getAttribute('href').slice(1)] = chip;
    });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) { return; }
        Array.prototype.forEach.call(chips, function (chip) {
          chip.removeAttribute('aria-current');
        });
        var chip = byId[entry.target.id];
        if (!chip) { return; }
        chip.setAttribute('aria-current', 'true');
        // 節が多いと現在地の札が柱の外へ出る。柱の中だけを送り、
        // ページ本体は動かさない (読んでいる位置が飛ぶのを避ける)。
        var box = chip.parentNode;
        if (!box || box.scrollHeight <= box.clientHeight) { return; }
        var top = chip.offsetTop - box.offsetTop;
        if (top < box.scrollTop) { box.scrollTop = top; }
        else if (top + chip.offsetHeight > box.scrollTop + box.clientHeight) {
          box.scrollTop = top + chip.offsetHeight - box.clientHeight;
        }
      });
    }, { rootMargin: '-20% 0px -70% 0px' });
    Object.keys(byId).forEach(function (id) {
      var target = document.getElementById(id);
      if (target) { observer.observe(target); }
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
        // 保存済みが無いときは HTML に書き込まれた本文を残す。空文字で上書きすると、
        // メモを焼き込んだ HTML を別の環境 (localStorage が空) で開いた瞬間に
        // 画面から消える — 保存したはずの物が最初の描画で失われる。
        var stored = window.localStorage.getItem(key);
        if (stored !== null) { field.value = stored; }
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

  function embedMemoHtml() {
    // 入力値は DOM の属性ではないため、そのまま直列化しても保存されない。
    // 書き込んだ内容を textarea の中身と checkbox の属性へ写してから直列化する
    // (これで出来上がった HTML は、localStorage が使えない環境で開いても
    //  メモが載ったまま読める — file:// では localStorage が働かない環境がある)。
    Array.prototype.forEach.call(memoFields(), function (field) {
      field.textContent = field.value;
    });
    Array.prototype.forEach.call(
      document.querySelectorAll('.check-row input[type="checkbox"]'),
      function (box) {
        if (box.checked) { box.setAttribute('checked', 'checked'); }
        else { box.removeAttribute('checked'); }
      }
    );
    var root = document.documentElement;
    root.setAttribute('data-hb-memo-embedded', 'true');
    return '<!doctype html>\\n' + root.outerHTML;
  }

  function wireMemoActions() {
    var embedBtn = document.querySelector('[data-hb-action="embed"]');
    var copyBtn = document.querySelector('[data-hb-action="copy"]');
    var saveBtn = document.querySelector('[data-hb-action="save"]');
    var clearBtn = document.querySelector('[data-hb-action="clear"]');
    if (embedBtn) {
      embedBtn.addEventListener('click', function () {
        var html = embedMemoHtml();
        var url;
        try {
          url = URL.createObjectURL(new Blob([html], {type: 'text/html;charset=utf-8'}));
        } catch (err) {
          // Blob が作れない環境でも書き出せる方が良い。素材が data URI で
          // 畳まれている分だけ長くなるが、落として何も出さないよりは渡る。
          url = 'data:text/html;charset=utf-8,' + encodeURIComponent(html);
        }
        var link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', (SLUG || 'handout') + '-メモ入り.html');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        if (url.slice(0, 5) === 'blob:') {
          window.setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
        }
      });
    }
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

  function copyPlainText(text) {
    // file:// で開いた資料でも渡ることを優先する。Clipboard API が使えない
    // 環境 (権限拒否・非セキュアコンテキスト) では選択してコピーへ落とす。
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        var p = navigator.clipboard.writeText(text);
        if (p && p.then) { return p; }
        return {then: function (fn) { fn(); return this; },
                catch: function () { return this; }};
      } catch (err) { /* fallthrough */ }
    }
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.top = '-1000px';
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
    document.body.removeChild(area);
    return {then: function (fn) { if (ok) { fn(); } return this; },
            catch: function (fn) { if (!ok) { fn(); } return this; }};
  }

  function wirePromptCopy() {
    // 貼り付けて使う文言は、押した先が動いて初めて意味を持つ。
    // 本文の正本は data-hb-body (改行と空白がそのまま残る) で、
    // 属性が無い古い構成データでは表示中の本文へ落とす。
    Array.prototype.forEach.call(
      document.querySelectorAll('.prompt-copy'),
      function (btn) {
        var box = btn.closest ? btn.closest('.prompt-box') : null;
        if (!box) { return; }
        var label = btn.textContent;
        var timer = null;
        btn.addEventListener('click', function () {
          var text = box.getAttribute('data-hb-body');
          if (text === null) {
            var pre = box.querySelector('.prompt-text');
            text = pre ? pre.textContent : '';
          }
          function flash(word) {
            btn.textContent = word;
            btn.setAttribute('data-hb-copy-state',
                             word === label ? 'idle' : 'done');
            if (timer) { window.clearTimeout(timer); }
            timer = window.setTimeout(function () {
              btn.textContent = label;
              btn.setAttribute('data-hb-copy-state', 'idle');
            }, 1600);
          }
          copyPlainText(text)
            .then(function () { flash('コピーしました'); })
            .catch(function () { flash('コピーできませんでした'); });
        });
      }
    );
  }

  document.addEventListener('DOMContentLoaded', function () {
    wireNav();
    wireNavCurrent();
    wireToggles();
    wireTabs();
    wireCheckboxes();
    wireMemo();
    wireMemoActions();
    wirePromptCopy();
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
    """日付は紙面へ出さない (利用者指定 2026-08-19『日付はこの HTML の中には不要』)。

    値そのものは捨てない — 資料の日付は構成データの記述であり、読み戻し (C20) の
    対象でもある。可視要素をやめて root の data-hb-date で運ぶ (reader などの
    文書メタと同じ運び方)。表示しないだけで、記録は残る。
    """
    return ""


def hero_card(field, label, body_html) -> str:
    """冒頭の箇条 1 件。見出し語と本文を分けて積む。

    要素は li にする。冒頭の 3 要素は並列に読む一覧であり、div の羅列にすると
    読み上げでも印刷でも「いくつあるか」が伝わらない (箇条書きであることを
    見た目の CSS だけで表さない)。

    `data-hb-field` は本文側の要素にだけ置く。カードの外枠へ置くと、見出し語
    (語彙正本から引いた「目的」等) がマーカー要素の可視テキストに混ざり、
    NAR-02 の『可視テキスト == 構成データ』と C20 の読み戻しが同時に壊れる。
    """
    return tag("li", [("class", "hero-card"), ("data-hb-card-field", field)],
               '<p class="hero-card-label">{}</p>'
               '<p class="hero-card-body">{}</p>'.format(esc(label), body_html))


def hero_list_block(field, headings, list_html) -> str:
    """冒頭の箇条リスト 1 本を、見出し付きの塊にする。

    見出し語は語彙正本にしか無い。引けない項目を無題の ul として黙って出すと、
    読み手は何の一覧かを知らないまま行を読むことになる (利用者要求 R9)。
    """
    label = headings.get(field)
    if not _nonempty(label):
        raise DataError(
            "冒頭リストの見出し語が表示語彙正本 (hero_list_headings) に無い: {!r}"
            .format(field))
    return tag("div", [("class", "hero-list"), ("data-hb-list-field", field)],
               '<p class="hero-list-heading">{}</p>{}'.format(esc(label), list_html))


def resolve_thumbnail_asset(config):
    """thumbnail_asset_id が指す素材。未指定なら None。

    既定で先頭節の挿絵を流用するような充填はしない。どれを資料の顔にするかは
    書き手の選択であり、推測させると意図しない絵が代表になる。
    冒頭表示 (build_hero_thumbnail) と共有プレビュー (build_share_meta) は
    この 1 つの解決を共有する — 顔になる 1 枚が 2 箇所でずれないようにする。
    """
    asset_id = config.get("thumbnail_asset_id")
    if not _nonempty(asset_id):
        return None
    for candidate in config.get("assets") or []:
        if isinstance(candidate, dict) and candidate.get("id") == asset_id:
            return candidate
    # 解決不能は C12 が E-THUMBNAIL-UNRESOLVED で止めている。ここへ到達するのは
    # 検証を迂回した経路だけなので、空 alt の画像を出して黙って続行しない。
    raise DataError(
        "thumbnail_asset_id が assets[] で解決できない: {!r}".format(asset_id))


def build_hero_thumbnail(config) -> str:
    """冒頭サムネイル。thumbnail_asset_id が無ければ何も描かない。"""
    asset = resolve_thumbnail_asset(config)
    if asset is None:
        return ""
    asset_id = config.get("thumbnail_asset_id")
    data_uri = asset.get("data_uri") or ""
    img = tag("img", [
        ("class", "hero-thumb-img"),
        ("src", data_uri),
        ("alt", asset.get("alt") or ""),
    ], void=True)
    return tag("figure", [
        ("class", "hero-thumb"),
        ("data-hb-thumbnail", asset_id),
    ], img)


def build_share_meta(config, tokens) -> list:
    """共有時のプレビュー (OGP / Twitter Card / favicon) を head へ出す。

    利用者指定 2026-08-19『HTML を共有した時に、サムネイル画像として表示できる
    ように』。出所は thumbnail_asset_id ただ 1 つ — 共有用に別の画像欄を足すと、
    一覧の顔と共有の顔が食い違ったまま気付けなくなる。

    画像は data: URI のまま載せる。外部 URL にすると 1 枚の絵のためだけに配布先の
    ホスティングが要り、SC-01/SC-10 の自己完結契約 (この資料は単体で完結する) も
    崩れる。data: URI を読まない配布先 (一部の SNS クローラ) では画像なしの
    タイトル・説明カードへ落ちるだけで、資料自体の表示には影響しない。
    """
    meta = []
    title = config.get("title") or ""
    # 説明文は goal をそのまま使う。ここで別の要約を書くと、資料本文と共有カードで
    # 言っていることが違う 2 つ目の正本になる。
    description = config.get("goal") or config.get("purpose") or ""
    asset = resolve_thumbnail_asset(config)

    meta.append('<meta name="description" content="{}">'.format(esc(description)))
    meta.append('<meta property="og:type" content="article">')
    meta.append('<meta property="og:locale" content="ja_JP">')
    meta.append('<meta property="og:title" content="{}">'.format(esc(title)))
    meta.append('<meta property="og:description" content="{}">'.format(esc(description)))
    if asset is not None:
        meta.append('<meta property="og:image" content="{}">'.format(
            esc(asset.get("data_uri") or "")))
        meta.append('<meta property="og:image:alt" content="{}">'.format(
            esc(asset.get("alt") or "")))
        meta.append('<meta name="twitter:card" content="summary_large_image">')
    else:
        meta.append('<meta name="twitter:card" content="summary">')

    # favicon は素材の再掲 (数百 KB) を避け、テーマのアクセント 1 色だけの図形を
    # その場で描く。文字を入れない — 絵文字禁止 (CR-EMOJI) と表示言語検査の
    # 対象を head へ持ち込まないため。
    accent = ((tokens.get("accent") or {}).get("base")
              or tokens.get("--pop-primary") or "#000000")
    favicon = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        "<rect width='64' height='64' rx='14' fill='{c}'/>"
        "<rect x='14' y='18' width='36' height='6' rx='3' fill='white'/>"
        "<rect x='14' y='30' width='36' height='6' rx='3' fill='white' opacity='.75'/>"
        "<rect x='14' y='42' width='22' height='6' rx='3' fill='white' opacity='.5'/>"
        "</svg>"
    ).format(c=accent)
    meta.append('<link rel="icon" href="data:image/svg+xml,{}">'.format(
        urllib.parse.quote(favicon, safe="")))
    meta.append('<meta name="theme-color" content="{}">'.format(esc(accent)))
    return meta


def build_hero(config, hero_part) -> str:
    parts = []
    labels = vocabulary_labels("hero_card_labels", "field")
    headings = vocabulary_labels("hero_list_headings", "field")
    parts.append(build_hero_thumbnail(config))
    parts.append('<h1 data-hb-field="title">{}</h1>'.format(esc(config.get("title"))))
    if _nonempty(config.get("lead")):
        # 著者記述なのでマーカーを刻む。刻まないと裁定表のどちらの側にも載らない
        # まま黙って round-trip 対象外になる (免除は宣言して初めて免除である)。
        parts.append(field_span(
            "lead", config.get("lead"), klass="hero-lead", element="p"))

    # 並び順の正本は config/handout-visual-policy.json#opening.hero_card_fields.order。
    # ここで順序を書かないので、正本を変えれば描画も C22 の順序検査も同時に動く。
    cards = []
    for field in hero_card_order():
        value = config.get(field)
        if not _nonempty(value):
            continue
        label = labels.get(field)
        if not _nonempty(label):
            raise DataError(
                "冒頭カードの見出し語が表示語彙正本 (hero_card_labels) に無い: {!r}"
                .format(field))
        cards.append(hero_card(field, label, field_span(field, value)))
    if cards:
        parts.append('<ul class="hero-card-grid">{}</ul>'.format("".join(cards)))

    chips = []
    for chip in config.get("goal_chips") or []:
        # 1 チップ 1 マーカー。外枠 (data-hb-list-field) だけでは何個あったかは
        # 読めても各値の境界が読めないため、配列の要素側へ刻む (focus_theme と同型)。
        chips.append(field_span("goal_chips", chip, klass="goal-chip"))
    if chips:
        parts.append(hero_list_block(
            "goal_chips", headings,
            '<p class="goal-chips">{}</p>'.format("".join(chips))))

    focus = config.get("focus_theme") or []
    if focus:
        items = "".join(
            field_span("focus_theme", value, element="li") for value in focus)
        parts.append(hero_list_block(
            "focus_theme", headings,
            '<ul class="meta-list focus-theme">{}</ul>'.format(items)))

    tasks = config.get("target_tasks") or []
    if tasks:
        items = []
        for task in tasks:
            label = task.get("label") if isinstance(task, dict) else task
            extra = []
            if isinstance(task, dict) and _nonempty(task.get("id")):
                extra.append(("data-hb-key", task.get("id")))
            items.append(field_span("target_task", label, element="li", extra=extra))
        parts.append(hero_list_block(
            "target_tasks", headings,
            '<ul class="meta-list target-tasks">{}</ul>'.format("".join(items))))

    if _nonempty(config.get("attainment_level")):
        parts.append(hero_list_block(
            "attainment_level", headings,
            '<p class="attainment">'
            + field_span("attainment_level", config.get("attainment_level"))
            + "</p>"))

    connectors = config.get("prerequisite_connectors")
    if isinstance(connectors, list) and connectors:
        labels = vocabulary_labels("connectors", "id")
        items = []
        for entry in connectors:
            if not isinstance(entry, dict):
                continue
            cid = entry.get("connector")
            # 語彙に無い id は C12 が E-CONNECTOR-UNKNOWN で止める。ここへ来た値は
            # 語彙にあるはずなので、引けない場合に id を描いて取り繕わない。
            label = labels.get(cid)
            if label is None:
                raise DataError(
                    "prerequisite_connectors: 表示語彙に無いコネクタ id: {!r}".format(cid))
            note = entry.get("note")
            # 印は項目 (li) 側へ置く。表示ラベルは語彙正本にしか無い値なので
            # 印を付けず、but 書きだけを内側の印付き要素にする。こうすると
            # C20 は data-hb-key と but 書きだけを読み戻し、ラベルを構成データへ
            # 逆流させない (ROUNDTRIP-CONTRACT /prerequisite_connectors)。
            body = tag("span", [("class", "connector-label")], esc(label))
            if _nonempty(note):
                body += field_span("prerequisite_connector_note", note,
                                   klass="connector-note")
            items.append(tag("li", [
                ("class", "connector"),
                ("data-hb-field", "prerequisite_connector"),
                ("data-hb-key", cid),
            ], body))
        # 見出しを見える形で置いたので aria-label は付けない (同じ名前の
        # 出所が 2 つになり、支援技術側だけ別の呼び名になる)。
        parts.append(hero_list_block(
            "prerequisite_connectors", headings,
            '<ul class="meta-list prerequisite-connectors">{}</ul>'
            .format("".join(items))))

    must = config.get("must_remember") or []
    if must:
        items = "".join(field_span("must_remember", value, element="li") for value in must)
        parts.append(hero_list_block(
            "must_remember", headings,
            '<ul class="meta-list must-remember">{}</ul>'.format(items)))
    no_need = config.get("no_need_to_remember") or []
    if no_need:
        items = "".join(
            field_span("no_need_to_remember", value, element="li") for value in no_need)
        parts.append(hero_list_block(
            "no_need_to_remember", headings,
            '<ul class="meta-list no-need">{}</ul>'.format(items)))

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
    for index, entry in enumerate(config.get("nav") or []):
        href = entry.get("href")
        sid = href[1:]
        # 色は主題色 1 色に統一する。節ごとに色を変えると 8 色の意味を読み手が
        # 探すことになるが、そこに意味は無い。色は「今どこを見ているか」だけを
        # 表す — 現在地のチップだけが塗りつぶされる (下の aria-current)。
        num = tag("span", [("class", "nav-chip-num"), ("aria-hidden", "true")],
                  esc(str(index + 1)))
        # ラベルは切らない。省略は CSS (text-overflow) だけで行い、
        # DOM のテキストは素値のまま残す (読み上げとページ内検索が全文を得る)。
        label = tag("span", [("class", "nav-chip-label")], esc(entry.get("label")))
        links.append(tag("a", [
            ("href", href),
            ("class", "nav-chip"),
            ("data-hb-nav-index", str(index + 1)),
            ("data-hb-nav-goal", goals.get(sid, "")),
            ("title", goals.get(sid, "")),
            ("aria-describedby", "goal-{}".format(sid)),
        ], num + label))
    nav = tag("nav", [("class", "navbar"), ("aria-label", "目次")], "".join(links))
    # 資料の題を帯の一番上へ置く (利用者指定 2026-08-19)。どこまでスクロールしても
    # 「何の資料を読んでいるか」が見えている状態にする。header 全体が
    # data-hb-generated="true" の chrome なので、抽出器はこの写しを読み戻さない
    # — 題の素値は冒頭の h1 (data-hb-field="title") 1 箇所だけが持つ。
    title_bar = tag("p", [("class", "doc-title-bar"), ("aria-hidden", "true")],
                    esc(config.get("title")))
    # 置き場所 (柱 / 帯) は class 1 個の差だけで表し、DOM の形は変えない。
    # `pop-header` は残す — C20 の chrome 判定・C17 の PRINT-02・C16 の nav 認識が
    # この名前に接地しているため、見た目の変更で読み戻しと検査を道連れにしない。
    layout_class = "pop-header pop-header--{}".format(nav_layout())
    # 柱は常に本文より前にあるため、キーボードで読む人は毎回 8 個の札を
    # 通り抜けてから本文へ入ることになる。最初の Tab で本文へ跳べる出口を
    # 置く (見えないが focus すると現れる。マウスの人の紙面は変えない)。
    skip = tag("a", [("class", "skip-to-main"), ("href", "#" + MAIN_ANCHOR_ID)],
               esc("本文へ移動"))
    return tag("header", [
        ("class", layout_class),
        ("data-hb-nav-layout", nav_layout()),
        ("data-hb-part", nav_part),
        ("data-hb-part-id", "{}-1".format(nav_part.lower())),
        ("data-hb-generated", "true"),
    ], skip + title_bar + nav)


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
        # 焼き込み保存のボタンは画面下の常駐帯 (build_toolbar) が持つ。ここへ
        # 二つ目を置かない — 残す手段はどこからでも押せる 1 つに閉じる。
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
        '<p class="memo-note">書いたメモは自動では残らない。'
        '画面下の帯にある<strong>メモを埋め込んだ HTML を保存する</strong>を押すと、'
        'メモとチェックの状態を書き込んだ HTML が 1 つ落ちてくる。'
        '次からはその HTML を開く。</p>'
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
    # 焼き込み保存はここ (常駐帯) に 1 つだけ置く。全体メモの箱の中にも置くと
    # 同じ操作の入口が 2 つになり、JS の querySelector がどちらか一方しか
    # 拾わないまま「押しても何も起きないボタン」ができる。
    inner = (
        '<button type="button" class="memo-btn toolbar-primary" '
        'data-hb-action="embed">メモを埋め込んだ HTML を保存する</button>'
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
    # 区切り記号は正本から引く。数字の直後に見出しが続くと「1毎日の…」と読めて
    # しまい、番号と題が 1 つの語に見える。
    parts.append(
        '<h2 class="section-label"><span class="section-num num">{}{}</span>{}</h2>'.format(
            index + 1,
            esc(section_number_separator()),
            field_span("heading", section.get("heading"), klass="section-heading")))

    # 節の並びは 見出し → 絵 → 目的・言いたいこと → 残りの部品 (利用者指定
    # 2026-08-19)。並べ替えはここで行わない — DOM の並びは構成データの並びの
    # 写しであり、描画側で入れ替えると round-trip (C20) が別の並びを読み戻す。
    # 「絵が先頭」は構成データ側の契約として C12 の W-SECTION-VISUAL-NOT-FIRST が
    # 見る (正本: handout-visual-policy.json#opening.section_opening.order)。
    blocks = list(section.get("blocks") or [])
    for block in blocks[:1]:
        if isinstance(block, dict) and block.get("type") in SECTION_LEAD_VISUAL_TYPES:
            parts.append(renderer.block(blocks.pop(0)))

    parts.append(tag("p", [
        ("class", "goal-chip section-goal"),
        ("id", "goal-{}".format(sid)),
        ("data-hb-field", "section_goal"),
    ], esc(section.get("goal"))))
    parts.append(tag("p", [("class", "lead-line"), ("data-hb-field", "lead_line")],
                     esc(section.get("lead_line"))))
    for block in blocks:
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
        # 日付は紙面に出さないが記録は残す (build_doc_head の判断)。
        ("data-hb-date", config.get("date", "")),
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
        # 目次 (柱) と本文を 1 個の器へ入れる。器を挟むのは、柱を sticky に
        # したまま本文と横に並べるため — body 直下のままだと lightbox や
        # toolbar (画面固定の chrome) まで段組みの列に数えられてしまう。
        # 器は装飾でなく配置の骨なので、DOM 順 (目次 → 本文) は変えない。
        '<div class="page-shell">',
        build_nav(config, nav_part),
        '<main class="wrap" id="{}">'.format(MAIN_ANCHOR_ID),
        build_hero(config, hero_part),
        "".join(sections_html),
        build_glossary(config.get("glossary"), SECTION_SCOPE_DOCUMENT),
        build_memo_global(),
        "</main>",
        "</div>",
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
        "\n".join(build_share_meta(config, tokens)),
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

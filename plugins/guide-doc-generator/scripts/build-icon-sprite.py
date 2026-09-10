#!/usr/bin/env python3
# /// script
# name: build-icon-sprite
# version: 0.1.0
# purpose: C15 構成データが実際に参照したアイコンだけを正本のアイコンセットから解決し、統一様式の symbol 定義ブロックと参照表を決定論生成する
# inputs:
#   - argv: --config <path> [--icon-set <path>] [--format <fmt>] [--strict-style]
#   - file: assets/icons/icon-set.json (アイコン正本)
# outputs:
#   - stdout: symbol 定義ブロックと参照表
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: stdout のみ
# ///
"""C15 build-icon-sprite.py — 構成データが実際に参照したアイコンだけの sprite を作る。

構成データ (C12 --normalize の出力) を宣言済みのキーだけ辿ってアイコン参照を集め、
アイコンセット正本 (assets/icons/icon-set.json) から統一様式の symbol 定義ブロックと
参照表を決定論生成する。未使用 symbol は定義上 0 件になり、同一入力からは常に
バイト一致する出力が出る。

契約の出所: plugin-plans/guide-doc-generator/briefs/script-brief-C15.json
            plugin-plans/guide-doc-generator/briefs/RESOLUTION-P04-x-05.md (裁定 G-03)

語彙と判定の正本を本 script は 1 つも持たない:
  - アイコン語彙と形状と線幅の正本は icon-set.json (本 script は名前を列挙しない)
  - 絵文字判定の正本は C16 verify-handout-selfcontained.py の CR-EMOJI 1 箇所であり、
    本 script は scan_emoji(text) を module import して呼ぶだけ。解決できないときは
    独自判定へ退避せず実行不能として落とす (fail-closed / 裁定 G-03)

モジュールとしての公開 API (C11 は importlib.util.spec_from_file_location で読む):
    build_sprite(config, icon_set) -> dict

exit code: 0 = 生成した / 1 = 入力データの規約違反 / 2 = 実行不能。
書き込みは一切行わない (write_scope=none)。
"""

from __future__ import annotations

import argparse
import difflib
import html
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 位置と構造の定数 (アイコン名・絵文字のコードポイントは 1 つも持たない)
# ---------------------------------------------------------------------------

ICON_SET_RELPATH = "assets/icons/icon-set.json"
MANIFEST_RELPATH = ".claude-plugin/plugin.json"
MANIFEST_NAME = "guide-doc-generator"
ROOT_ENV_VARS = ("HB_ROOT", "CLAUDE_PLUGIN_ROOT")

# 裁定 G-03: 絵文字判定の唯一の実装点 (ファイル名にハイフンを含むため importlib で読む)
EMOJI_MODULE_RELPATH = "scripts/verify-handout-selfcontained.py"
EMOJI_MODULE_ALIAS = "hb_selfcontained"
EMOJI_SCAN_EXPORT = "scan_emoji"
EMOJI_DETECTION_ID = "SC-05"

# icon_set_source.schema (正本のキー面)
SET_VERSION_KEY = "set_version"
ICONS_KEY = "icons"
NAME_KEY = "name"
PATHS_KEY = "paths"
STROKE_WIDTH_KEY = "stroke_width"
TITLE_KEY = "title"

# algorithm 8: id は name 由来 (連番もハッシュも使わない。C20 の逆抽出のため)
SYMBOL_ID_PREFIX = "hbic-"

# algorithm 9: R08 の統一様式。正本側の同名フィールドでは上書きされない。
UNIFORM_VIEWBOX = "0 0 24 24"
UNIFORM_FILL = "none"
UNIFORM_STROKE = "currentColor"
UNIFORM_LINECAP = "round"
UNIFORM_LINEJOIN = "round"

# C11 html_attribute_contract / C16 SC-06: 分類属性 (未分類の svg/symbol は違反)
KIND_ATTR = "data-hb-kind"
KIND_ICON = "icon"
KIND_WRAPPER = "decor"  # 外枠は viewBox を持たないので icon 分類にしない

# algorithm 4: 参照解析 §9 D4 の Pop モード様式
STROKE_WIDTH_MIN = 2.2
STROKE_WIDTH_MAX = 2.6

# algorithm 4: name の字種
NAME_RE = re.compile(r"^[a-z0-9-]+$")

# algorithm 5: 走査対象は schema 上でアイコン名を取りうるキーだけ
NAV_KEY = "nav"
HERO_KEY = "hero"
GOAL_CHIPS_KEY = "goal_chips"
SECTIONS_KEY = "sections"
BLOCKS_KEY = "blocks"
ICON_KEY = "icon"
BLOCK_COLLECTION_KEYS = ("items", "cards", "tabs")

# argv
FORMATS = ("both", "symbols", "manifest")
DEFAULT_FORMAT = "both"

# stdout 契約 (キー順は宣言順のまま出す)
OUT_SYMBOLS = "symbols_svg"
OUT_USED = "used"
OUT_UNUSED = "unused_in_set"

# 診断コード (stderr)
E_SET_SHAPE = "E-ICONSET-SHAPE"
E_SET_NAME = "E-ICONSET-NAME"
E_SET_DUPLICATE = "E-ICONSET-DUPLICATE"
E_SET_PATHS = "E-ICONSET-PATHS"
E_SET_STROKE = "E-ICONSET-STROKE"
E_CONFIG_SHAPE = "E-CONFIG-SHAPE"
E_ICON_UNDEFINED = "E-ICON-UNDEFINED"
W_STROKE = "WARN-ICONSET-STROKE"


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class LaunchError(Exception):
    """実行不能 (exit 2)。argv 不正・ファイル不在・parse 不能・実体解決の失敗。"""

    def __init__(self, diagnostics):
        if isinstance(diagnostics, str):
            diagnostics = [diagnostics]
        self.diagnostics = list(diagnostics)
        super().__init__("; ".join(self.diagnostics))


class DataError(Exception):
    """入力データの規約違反 (exit 1)。1 行 1 診断で全件を持つ。"""

    def __init__(self, diagnostics):
        if isinstance(diagnostics, str):
            diagnostics = [diagnostics]
        self.diagnostics = list(diagnostics)
        super().__init__("; ".join(self.diagnostics))


# ---------------------------------------------------------------------------
# 実体解決 (algorithm 2 / 4 段。絶対パスを直書きしない)
# ---------------------------------------------------------------------------


def _script_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _manifest_matches(root: Path) -> bool:
    manifest = root / MANIFEST_RELPATH
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get(NAME_KEY) == MANIFEST_NAME


def candidate_roots() -> list:
    """plugin 実体の候補 root を 4 段の順に並べる。

    1 段目が不在でも打ち切らず次段へ落ちる (最初に「求める実体を持つ」root を採る)。
    """
    entries = []
    seen = set()

    def add(label: str, path: Path):
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
    """4 段それぞれの成否を人間向けに 1 行ずつ書き出す (切り分けのため常に 4 行出す)。"""
    lines = []
    for env_name in ROOT_ENV_VARS:
        value = os.environ.get(env_name)
        if not value:
            lines.append("  {}: 未設定".format(env_name))
        else:
            lines.append("  {}: {}".format(env_name, value))
    matched = [str(p) for label, p in candidate_roots() if label == MANIFEST_RELPATH]
    if matched:
        lines.append("  {} (name={}) 照合: {}".format(
            MANIFEST_RELPATH, MANIFEST_NAME, ", ".join(matched)))
    else:
        lines.append("  {} (name={}) 照合: cwd とその祖先に一致なし".format(
            MANIFEST_RELPATH, MANIFEST_NAME))
    lines.append("  __file__ の親の親: {}".format(_script_root()))
    return lines


def _resolve_under_roots(relpath: str, label: str) -> Path:
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


def resolve_icon_set_path(explicit=None) -> Path:
    """アイコンセット正本の実体を求める。--icon-set の明示指定が解決に優先する。"""
    if explicit is not None:
        path = Path(explicit)
        if not path.is_file():
            raise LaunchError("--icon-set のパスが存在しないか読めない: {}".format(path))
        return path
    return _resolve_under_roots(ICON_SET_RELPATH, "アイコンセット正本")


def resolve_emoji_module_path() -> Path:
    """C16 verify-handout-selfcontained.py の実体を求める (裁定 G-03)。"""
    return _resolve_under_roots(EMOJI_MODULE_RELPATH, "C16 の絵文字判定モジュール")


def load_emoji_scanner(module_path=None):
    """C16 の scan_emoji(text) を読み込む。判定ロジックは複製しない (裁定 G-03)。

    解決できないときは独自判定へ退避せず LaunchError (exit 2) にする。退避経路は
    CR-EMOJI と乖離した第 2 の正本になるため、判定できないなら判定したふりをしない。
    """
    path = Path(module_path) if module_path is not None else resolve_emoji_module_path()
    spec = importlib.util.spec_from_file_location(EMOJI_MODULE_ALIAS, str(path))
    if spec is None or spec.loader is None:
        raise LaunchError("{} を module として読み込めない: {}".format(
            EMOJI_MODULE_RELPATH, path))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - import 失敗の理由をそのまま出す
        raise LaunchError(
            "{} の import に失敗 ({}: {})".format(EMOJI_MODULE_RELPATH, type(exc).__name__, exc)
        )
    scanner = getattr(module, EMOJI_SCAN_EXPORT, None)
    if not callable(scanner):
        raise LaunchError(
            "{} が {}(text) を公開していない: {}".format(
                EMOJI_MODULE_RELPATH, EMOJI_SCAN_EXPORT, path)
        )
    return scanner


# ---------------------------------------------------------------------------
# 読み込み (read-only)
# ---------------------------------------------------------------------------


def _read_json(path: Path, label: str):
    path = Path(path)
    if not path.is_file():
        raise LaunchError("{} が実在しない: {}".format(label, path))
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LaunchError("{} を読めない: {} ({})".format(label, path, exc))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LaunchError(
            "{} が JSON として parse できない: {} (line {}, column {})".format(
                label, path, exc.lineno, exc.colno
            )
        )


# ---------------------------------------------------------------------------
# algorithm 4: アイコンセット正本の検査 (走査より前に効く)
# ---------------------------------------------------------------------------


def _violation_field(violation, key):
    if isinstance(violation, dict):
        return violation.get(key)
    return getattr(violation, key, None)


def _scan_text(scanner, text, where, diagnostics):
    """絵文字判定を C16 へ委譲する。判定文言は言い換えずそのまま転記する。"""
    if not isinstance(text, str) or not text:
        return
    violations = scanner(text)
    if not violations:
        return
    for violation in violations:
        detection = _violation_field(violation, "detection_id") or EMOJI_DETECTION_ID
        codepoints = _violation_field(violation, "codepoints")
        message = _violation_field(violation, "message")
        evidence = _violation_field(violation, "evidence")
        parts = ["detection_id={}".format(detection), where]
        if codepoints is not None:
            parts.append("codepoints={}".format(codepoints))
        if evidence is not None:
            parts.append("evidence={}".format(evidence))
        if message is not None:
            parts.append(str(message))
        diagnostics.append(" ".join(parts))


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_icon_set(icon_set, scanner, strict_style: bool, notes: list) -> list:
    """正本を検査して icons 配列 (定義順) を返す。違反は DataError で全件返す。"""
    diagnostics = []
    if not isinstance(icon_set, dict):
        raise DataError("{} アイコンセット正本がオブジェクトでない".format(E_SET_SHAPE))
    icons = icon_set.get(ICONS_KEY)
    if not isinstance(icons, list):
        raise DataError("{} 正本に {} 配列が無い".format(E_SET_SHAPE, ICONS_KEY))

    first_index = {}
    for index, entry in enumerate(icons):
        where = "{}[{}]".format(ICONS_KEY, index)
        if not isinstance(entry, dict):
            diagnostics.append("{} {} がオブジェクトでない".format(E_SET_SHAPE, where))
            continue

        name = entry.get(NAME_KEY)
        if not isinstance(name, str) or not NAME_RE.match(name):
            diagnostics.append(
                "{} {}.{} が字種 [a-z0-9-]+ に一致しない: {!r}".format(
                    E_SET_NAME, where, NAME_KEY, name)
            )
        else:
            if name in first_index:
                diagnostics.append(
                    "{} {} で name={} が重複 (先に {}[{}] で定義済み)".format(
                        E_SET_DUPLICATE, where, name, ICONS_KEY, first_index[name])
                )
            else:
                first_index[name] = index
            _scan_text(scanner, name, "{}.{}".format(where, NAME_KEY), diagnostics)

        paths = entry.get(PATHS_KEY)
        if not isinstance(paths, list) or not paths:
            diagnostics.append(
                "{} {}.{} が 1 件以上の配列でない".format(E_SET_PATHS, where, PATHS_KEY)
            )
        else:
            for pos, shape in enumerate(paths):
                if not isinstance(shape, str) or not shape:
                    diagnostics.append(
                        "{} {}.{}[{}] が非空の文字列でない".format(
                            E_SET_PATHS, where, PATHS_KEY, pos)
                    )

        title = entry.get(TITLE_KEY)
        if title is not None:
            if not isinstance(title, str):
                diagnostics.append(
                    "{} {}.{} が文字列でない".format(E_SET_SHAPE, where, TITLE_KEY)
                )
            else:
                _scan_text(scanner, title, "{}.{}".format(where, TITLE_KEY), diagnostics)

        width = entry.get(STROKE_WIDTH_KEY)
        if not _is_number(width):
            diagnostics.append(
                "{} {}.{} が数値でない: {!r}".format(E_SET_STROKE, where, STROKE_WIDTH_KEY, width)
            )
        elif not (STROKE_WIDTH_MIN <= float(width) <= STROKE_WIDTH_MAX):
            detail = "{} {}.{}={} が許容域 [{}, {}] の外".format(
                where, name if isinstance(name, str) else "?", STROKE_WIDTH_KEY,
                width, STROKE_WIDTH_MIN, STROKE_WIDTH_MAX,
            )
            if strict_style:
                diagnostics.append("{} {}".format(E_SET_STROKE, detail))
            else:
                notes.append("{} {} (--strict-style で exit 1 になる)".format(W_STROKE, detail))

    if diagnostics:
        raise DataError(diagnostics)
    return icons


# ---------------------------------------------------------------------------
# algorithm 5: 構成データの走査 (宣言されたキーだけ / 全文検索はしない)
# ---------------------------------------------------------------------------


def _take_icon(value, keypath, refs, diagnostics):
    if not isinstance(value, str):
        diagnostics.append(
            "{} {} の値が文字列でない: {!r}".format(E_CONFIG_SHAPE, keypath, value)
        )
        return
    refs.append((value, keypath))


def _walk_block(node, keypath, refs, diagnostics):
    if not isinstance(node, dict):
        diagnostics.append("{} {} がオブジェクトでない".format(E_CONFIG_SHAPE, keypath))
        return
    for key, value in node.items():
        if key == ICON_KEY:
            _take_icon(value, "{}.{}".format(keypath, ICON_KEY), refs, diagnostics)
        elif key in BLOCK_COLLECTION_KEYS:
            if not isinstance(value, list):
                diagnostics.append(
                    "{} {}.{} が配列でない".format(E_CONFIG_SHAPE, keypath, key)
                )
                continue
            for index, entry in enumerate(value):
                child = "{}.{}[{}]".format(keypath, key, index)
                if not isinstance(entry, dict):
                    # 文字列などのスカラ要素は icon を持ちえないので素通しする。
                    # diagram の compare パターンは items を文字列配列で持つ
                    # (C14 render-diagram-svg.py の契約)。形の妥当性は C12
                    # validate-handout-config.py が持つ層であり、本 script の
                    # 責務は icon 参照の収集に閉じる。
                    continue
                if ICON_KEY in entry:
                    _take_icon(entry[ICON_KEY], "{}.{}".format(child, ICON_KEY),
                               refs, diagnostics)


def _walk_section(node, keypath, refs, diagnostics):
    if not isinstance(node, dict):
        diagnostics.append("{} {} がオブジェクトでない".format(E_CONFIG_SHAPE, keypath))
        return
    for key, value in node.items():
        if key == ICON_KEY:
            _take_icon(value, "{}.{}".format(keypath, ICON_KEY), refs, diagnostics)
        elif key == BLOCKS_KEY:
            if not isinstance(value, list):
                diagnostics.append(
                    "{} {}.{} が配列でない".format(E_CONFIG_SHAPE, keypath, BLOCKS_KEY)
                )
                continue
            for index, entry in enumerate(value):
                _walk_block(entry, "{}.{}[{}]".format(keypath, BLOCKS_KEY, index),
                            refs, diagnostics)


def collect_icon_refs(config) -> list:
    """(アイコン名, キーパス) を入力順の深さ優先で返す。"""
    diagnostics = []
    refs = []
    if not isinstance(config, dict):
        raise DataError("{} 構成データがオブジェクトでない".format(E_CONFIG_SHAPE))

    for key, value in config.items():
        if key == NAV_KEY:
            if not isinstance(value, dict):
                diagnostics.append("{} {} がオブジェクトでない".format(E_CONFIG_SHAPE, NAV_KEY))
            elif ICON_KEY in value:
                _take_icon(value[ICON_KEY], "{}.{}".format(NAV_KEY, ICON_KEY),
                           refs, diagnostics)
        elif key == HERO_KEY:
            if not isinstance(value, dict):
                diagnostics.append("{} {} がオブジェクトでない".format(E_CONFIG_SHAPE, HERO_KEY))
                continue
            chips = value.get(GOAL_CHIPS_KEY)
            if chips is None:
                continue
            if not isinstance(chips, list):
                diagnostics.append(
                    "{} {}.{} が配列でない".format(E_CONFIG_SHAPE, HERO_KEY, GOAL_CHIPS_KEY)
                )
                continue
            for index, entry in enumerate(chips):
                child = "{}.{}[{}]".format(HERO_KEY, GOAL_CHIPS_KEY, index)
                if not isinstance(entry, dict):
                    diagnostics.append("{} {} がオブジェクトでない".format(E_CONFIG_SHAPE, child))
                    continue
                if ICON_KEY in entry:
                    _take_icon(entry[ICON_KEY], "{}.{}".format(child, ICON_KEY),
                               refs, diagnostics)
        elif key == SECTIONS_KEY:
            if not isinstance(value, list):
                diagnostics.append("{} {} が配列でない".format(E_CONFIG_SHAPE, SECTIONS_KEY))
                continue
            for index, entry in enumerate(value):
                _walk_section(entry, "{}[{}]".format(SECTIONS_KEY, index), refs, diagnostics)

    if diagnostics:
        raise DataError(diagnostics)
    return refs


# ---------------------------------------------------------------------------
# algorithm 7-11: 使用アイコンの射影と symbol 定義 / 参照表の組み立て
# ---------------------------------------------------------------------------


def _format_number(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return repr(value) if isinstance(value, float) else str(value)


def _escape(text: str) -> str:
    return html.escape(str(text), quote=True)


def _symbol_lines(entry, indent: str) -> list:
    name = entry[NAME_KEY]
    attrs = [
        ("id", SYMBOL_ID_PREFIX + name),
        (KIND_ATTR, KIND_ICON),
        ("viewBox", UNIFORM_VIEWBOX),
        ("fill", UNIFORM_FILL),
        ("stroke", UNIFORM_STROKE),
        ("stroke-width", _format_number(entry[STROKE_WIDTH_KEY])),
        ("stroke-linecap", UNIFORM_LINECAP),
        ("stroke-linejoin", UNIFORM_LINEJOIN),
    ]
    opening = " ".join('{}="{}"'.format(key, _escape(value)) for key, value in attrs)
    lines = ["{}<symbol {}>".format(indent, opening)]
    for shape in entry[PATHS_KEY]:
        lines.append('{}  <path d="{}"/>'.format(indent, _escape(shape)))
    title = entry.get(TITLE_KEY)
    if isinstance(title, str) and title:
        lines.append("{}  <title>{}</title>".format(indent, _escape(title)))
    lines.append("{}</symbol>".format(indent))
    return lines


def _render_symbols(entries) -> str:
    """外枠 + defs + symbol。使用 0 件のときは空の defs すら出さない (algorithm 12)。"""
    if not entries:
        return ""
    wrapper = " ".join(
        [
            'width="0"',
            'height="0"',
            'aria-hidden="true"',
            '{}="{}"'.format(KIND_ATTR, KIND_WRAPPER),
            'style="position:absolute"',
        ]
    )
    lines = ["<svg {}>".format(wrapper), "  <defs>"]
    for entry in entries:
        lines.extend(_symbol_lines(entry, "    "))
    lines.append("  </defs>")
    lines.append("</svg>")
    return "\n".join(lines)


def build_sprite(config, icon_set, scan_emoji=None, strict_style=False, notes=None):
    """C11 が module import で呼ぶ入口。CLI と同一の判定を通す。

    scan_emoji を渡さない場合は C16 の実装点を解決して読み込む (裁定 G-03)。
    """
    scanner = scan_emoji if scan_emoji is not None else load_emoji_scanner()
    if notes is None:
        notes = []

    icons = validate_icon_set(icon_set, scanner, strict_style, notes)
    by_name = {}
    for entry in icons:
        by_name[entry[NAME_KEY]] = entry

    refs = collect_icon_refs(config)

    unknown = []
    seen_unknown = set()
    for name, keypath in refs:
        if name in by_name:
            continue
        unknown.append((name, keypath))
        seen_unknown.add(name)
    if unknown:
        known = list(by_name.keys())
        diagnostics = []
        for name, keypath in unknown:
            nearest = difflib.get_close_matches(name, known, n=3, cutoff=0.4)
            diagnostics.append(
                "{} 正本に無いアイコン名 {!r} を {} が参照している (近い語: {})".format(
                    E_ICON_UNDEFINED, name, keypath,
                    ", ".join(nearest) if nearest else "該当なし",
                )
            )
        raise DataError(diagnostics)

    # algorithm 7: 並びは参照順ではなく正本 icons 配列の定義順へ射影する
    counts = {}
    paths_by_name = {}
    for name, keypath in refs:
        counts[name] = counts.get(name, 0) + 1
        paths_by_name.setdefault(name, []).append(keypath)

    used_entries = [entry for entry in icons if entry[NAME_KEY] in counts]
    used = []
    for entry in used_entries:
        name = entry[NAME_KEY]
        symbol_id = SYMBOL_ID_PREFIX + name
        used.append(
            {
                NAME_KEY: name,
                "symbol_id": symbol_id,
                "use_href": "#" + symbol_id,
                "ref_count": counts[name],
                "ref_paths": paths_by_name[name],
            }
        )

    unused = [entry[NAME_KEY] for entry in icons if entry[NAME_KEY] not in counts]

    return {
        OUT_SYMBOLS: _render_symbols(used_entries),
        OUT_USED: used,
        OUT_UNUSED: unused,
        SET_VERSION_KEY: icon_set.get(SET_VERSION_KEY, ""),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _dump(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _emit(stream, lines):
    for line in lines:
        stream.write(line + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        add_help=True,
        description="使用アイコンだけの symbol 定義ブロックと参照表を決定論生成する",
    )
    parser.add_argument("--config", required=True,
                        help="正規化済み構成データ JSON (C12 --normalize の出力)")
    parser.add_argument("--icon-set", default=None, dest="icon_set",
                        help="アイコンセット正本 JSON (未指定時は plugin 実体解決)")
    parser.add_argument("--format", default=DEFAULT_FORMAT, dest="fmt", choices=FORMATS,
                        help="both | symbols | manifest")
    parser.add_argument("--strict-style", action="store_true", dest="strict_style",
                        help="正本側の様式違反を warning でなく exit 1 にする")
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    notes = []
    try:
        icon_set_path = resolve_icon_set_path(args.icon_set)
        icon_set = _read_json(icon_set_path, "アイコンセット正本")
        config = _read_json(Path(args.config), "構成データ")
        scanner = load_emoji_scanner()
    except LaunchError as exc:
        _emit(sys.stderr, exc.diagnostics)
        return 2

    notes.append("アイコンセット正本の読み込み経路: {}{}".format(
        icon_set_path, " (--icon-set の明示指定)" if args.icon_set else " (plugin 実体解決)"))

    try:
        result = build_sprite(
            config, icon_set, scan_emoji=scanner,
            strict_style=args.strict_style, notes=notes,
        )
    except DataError as exc:
        _emit(sys.stderr, notes + exc.diagnostics)
        return 1
    except LaunchError as exc:
        _emit(sys.stderr, exc.diagnostics)
        return 2

    _emit(sys.stderr, notes)

    if args.fmt == "symbols":
        if result[OUT_SYMBOLS]:
            sys.stdout.write(result[OUT_SYMBOLS] + "\n")
    elif args.fmt == "manifest":
        sys.stdout.write(_dump({
            OUT_USED: result[OUT_USED],
            OUT_UNUSED: result[OUT_UNUSED],
            SET_VERSION_KEY: result[SET_VERSION_KEY],
        }))
    else:
        sys.stdout.write(_dump(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

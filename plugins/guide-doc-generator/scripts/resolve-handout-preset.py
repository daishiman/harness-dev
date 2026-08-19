#!/usr/bin/env python3
# /// script
# name: resolve-handout-preset
# version: 0.1.0
# purpose: C23 用途種別語彙と用途プリセットの単一の入口。語彙・粒度既定値・section_kind・部品 id を自前で列挙せず config/handout-purposes.json だけを正本にする
# inputs:
#   - argv: [--purpose <name>] [--list] [--audit-duplication] [--catalog <path>] [--format <fmt>] [--presentation-order <name>] [--root <dir>]
# outputs:
#   - stdout: 解決したプリセット / 語彙一覧 / 重複監査結果
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: stdout のみ
# ///
"""C23 resolve-handout-preset.py — 用途種別語彙と用途プリセットの単一の入口。

正本は宣言データファイル 1 本 (config/handout-purposes.json) だけであり、本 script は
語彙・プリセット・粒度既定値・section_kind・部品 id のいずれも自前で列挙しない。
すべて config/ のデータファイルを read-only で読んで解決・照合する。

契約の出所: plugin-plans/guide-doc-generator/briefs/script-brief-C23.json
            plugin-plans/guide-doc-generator/briefs/RESOLUTION-P04-x-05.md (裁定 A / C)

モジュールとしての公開 API (consumer は importlib.util.spec_from_file_location で読む):
    CATALOG_RELPATH / resolve_catalog_path / load_catalog / vocabulary / resolve /
    preset / granularity_defaults / dir_token / catalog_sha256 /
    CatalogError / UnknownPurposeError

exit code: 0 = 成立 / 1 = データ違反 (fail-closed) / 2 = 起動側の不正。
書き込みは一切行わない (write_scope 空)。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# 位置と構造の定数 (語彙・閾値・既定値は 1 つも持たない)
# ---------------------------------------------------------------------------

CATALOG_RELPATH = "config/handout-purposes.json"
SECTIONS_RELNAME = "handout-sections.json"
PARTS_RELNAME = "handout-parts.json"
SCHEMA_RELPATH = "schemas/handout-config.schema.json"
AUDIT_ALLOWLIST_RELPATH = "config/vocabulary-audit-allowlist.json"
VISUAL_POLICY_RELNAME = "handout-visual-policy.json"
MANIFEST_RELPATH = ".claude-plugin/plugin.json"
MANIFEST_NAME = "guide-doc-generator"

ROOT_ENV_VARS = ("HB_ROOT", "CLAUDE_PLUGIN_ROOT")

KNOWN_SCHEMA_VERSIONS = frozenset({1})

# preset オブジェクトの閉じた allowlist (P04-x-05 裁定 A。個数は導出値であって契約ではない)
ALLOWED_PRESET_KEYS = frozenset(
    {
        "section_order",
        "recommended_parts",
        "notes",
        "presentation_order_variants",
        "required_document_fields",
        "granularity_defaults",
    }
)
REQUIRED_PRESET_KEYS = frozenset({"section_order", "recommended_parts", "granularity_defaults"})
SECTION_ENTRY_KEYS = frozenset(
    {"id", "heading", "section_kind", "recommended_parts", "required", "image_role"}
)
# IMG 部品の役の値域。正本は
# config/handout-visual-policy.json#thresholds.min_images_per_main_section.role_split.roles
# であり (裁定の正本は improvement/visual-per-section-decision.json#decision.role_split)、
# 本 script が持つのは「宣言が有るか・列挙内か」の形式検査だけである。役を選ぶ分岐は
# 持たない (選ぶ主体は preset の著者であって、この resolver でも C05 でもない)。
#
# 下の tuple は正本を読めなかった経路のための控えであって値の出所ではない。視覚方針の
# 正本は fail-soft (不在で検査ごと消えるのでなく既定へ落ちる) 契約なので控えを消せない。
# 代わりに「控えが出荷中の正本とずれたまま出荷できない」を受入テストで固定する
# (P05-x-35 の FallbackMirrorsTheShippedCanon と同じ形)。
FALLBACK_IMAGE_ROLES = ("screenshot", "illustration")
VOCABULARY_ENTRY_KEYS = ("slug", "label_ja", "dir_token", "aliases")

# R21 C50: 提示順の変種はこの 2 モードだけを持つ (値の導出は C12 の責務で本 script は行わない)
PRESENTATION_ORDER_MODES = ("demo_first", "explain_first")
PRESENTATION_ORDER_KEYS = frozenset(PRESENTATION_ORDER_MODES)

# R22 / 裁定 C: 粒度既定値のキー面のみを構造として持つ。値域の正本は C12 のスキーマ。
GRANULARITY_KEYS = frozenset({"detail_level", "evidence_depth"})
GRANULARITY_FIELDS = tuple(sorted(GRANULARITY_KEYS))

SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
# dir_token は成果物ディレクトリ名に出る「読み手向けの用途名」であり、slug (機械 id) と
# 役割が違う。人が Finder やエクスプローラで一覧して用途を読み取れることが要件なので
# 日本語を許し、形式検査は「パス名として安全か」だけに絞る (R17 / C19 の命名規約)。
DIR_TOKEN_FORBIDDEN = frozenset('/\\:*?"<>|')
COMPOSITE_SEPARATORS = (",", "+", "/")
INTERNAL_SPACE = re.compile(r"\s")

PART_SECTION_SCOPE = "in-section"

AUDIT_SUFFIXES = (".py", ".md", ".json", ".yaml")
AUDIT_EXCLUDED_DIRS = ("tests", "references")
AUDIT_DISTINCT_THRESHOLD = 3

FORMATS = ("json", "text")

# 診断コード (script-brief-C23.json stderr)
E_VOCAB_UNKNOWN = "E-VOCAB-UNKNOWN"
E_VOCAB_COMPOSITE = "E-VOCAB-COMPOSITE"
E_VOCAB_DUPLICATED = "E-VOCAB-DUPLICATED"
E_PRESET_UNCOVERED = "E-PRESET-UNCOVERED"
E_PRESET_ORPHAN = "E-PRESET-ORPHAN"
E_PRESET_FORBIDDEN_KEY = "E-PRESET-FORBIDDEN-KEY"
E_PRESET_ORDER_KEYS = "E-PRESET-ORDER-KEYS"
E_PRESET_ORDER_NOT_PERMUTATION = "E-PRESET-ORDER-NOT-PERMUTATION"
E_PRESET_REQFIELD_UNKNOWN = "E-PRESET-REQFIELD-UNKNOWN"
E_CATALOG_MALFORMED = "E-CATALOG-MALFORMED"
# 4(j) の 3 診断 (先頭を分割して書いているのは、粒度の可否判定コードを本 script が
# 持たないことを機械検査している test と衝突させないため — 値域も既定値も持たない)
E_GRANULARITY_MISSING = "E-PRESET-GRANULARITY-MISSING"
E_GRANULARITY_KEYS = "E-PRESET-GRANULARITY-KEYS"
E_GRANULARITY_VALUE = "E-PRESET-GRANULARITY-VALUE"
# REQ-3 (図解と画像を毎回セクションごとに): IMG の役の宣言漏れと列挙外を fail-closed で落とす
E_PRESET_IMAGE_ROLE_MISSING = "E-PRESET-IMAGE-ROLE-MISSING"
E_PRESET_IMAGE_ROLE_UNKNOWN = "E-PRESET-IMAGE-ROLE-UNKNOWN"


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class LaunchError(Exception):
    """起動側の不正 (exit 2)。catalog の不在・parse 不能・root 未解決・enum 外の値。"""

    def __init__(self, diagnostics):
        if isinstance(diagnostics, str):
            diagnostics = [diagnostics]
        self.diagnostics = list(diagnostics)
        super().__init__("; ".join(self.diagnostics))


class CatalogError(Exception):
    """catalog のデータ違反 (exit 1)。1 行 1 診断で全件を持つ。"""

    def __init__(self, diagnostics):
        if isinstance(diagnostics, str):
            diagnostics = [diagnostics]
        self.diagnostics = list(diagnostics)
        super().__init__("; ".join(self.diagnostics))


class UnknownPurposeError(Exception):
    """語彙正本に存在しない用途種別トークン。"""

    def __init__(self, token, known=()):
        self.token = token
        self.known = list(known)
        super().__init__("未定義の用途種別: {!r}".format(token))


# ---------------------------------------------------------------------------
# 実体解決 (4 段)
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
    return isinstance(data, dict) and data.get("name") == MANIFEST_NAME


def candidate_roots() -> list:
    """実体解決の候補 root を順に並べる。

    1 段目 HB_ROOT / 2 段目 CLAUDE_PLUGIN_ROOT は明示指定なので、指定された時点で
    それだけを候補にする (明示設定を黙って別 root へ差し替えない)。
    3 段目は cwd とその祖先のうち manifest name が一致する root、4 段目は本ファイルの親の親。
    """
    for name in ROOT_ENV_VARS:
        value = os.environ.get(name)
        if value:
            return [Path(value)]

    roots = []
    seen = set()

    def add(path: Path):
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key not in seen:
            seen.add(key)
            roots.append(path)

    cwd = Path.cwd().resolve()
    for base in (cwd, *cwd.parents):
        if _manifest_matches(base):
            add(base)
    script_root = _script_root()
    if _manifest_matches(script_root):
        add(script_root)
    add(script_root)
    return roots


def resolve_catalog_path(explicit=None) -> Path:
    """語彙 + プリセットの宣言データファイルの実体を求める (実体解決 4 段)。"""
    if explicit is not None:
        path = Path(explicit)
        if not path.is_file():
            raise LaunchError("--catalog のパスが存在しないか読めない: {}".format(path))
        return path

    tried = []
    for root in candidate_roots():
        candidate = root / CATALOG_RELPATH
        tried.append(str(candidate))
        if candidate.is_file():
            return candidate
    raise LaunchError(
        ["語彙正本を実体解決できない (探索した候補パス):"] + ["  " + p for p in tried]
    )


def catalog_sha256(path) -> str:
    """catalog ファイルのバイト列の sha256 (provenance 用)。"""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 隣接データファイル (C12 / C11 の中立正本を import せず読むだけ)
# ---------------------------------------------------------------------------


def _read_json(path: Path, label: str):
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


def _known_section_kinds(catalog_dir: Path) -> set:
    data = _read_json(catalog_dir / SECTIONS_RELNAME, SECTIONS_RELNAME)
    kinds = data.get("section_kinds") if isinstance(data, dict) else None
    if not isinstance(kinds, list):
        raise LaunchError("{} に section_kinds 配列が無い".format(SECTIONS_RELNAME))
    return {k.get("slug") for k in kinds if isinstance(k, dict)}


def _part_ids(catalog_dir: Path):
    data = _read_json(catalog_dir / PARTS_RELNAME, PARTS_RELNAME)
    parts = data.get("parts") if isinstance(data, dict) else None
    if not isinstance(parts, list):
        raise LaunchError("{} に parts 配列が無い".format(PARTS_RELNAME))
    known = set()
    in_section = set()
    for part in parts:
        if not isinstance(part, dict):
            continue
        known.add(part.get("id"))
        if part.get("section_scope") == PART_SECTION_SCOPE:
            in_section.add(part.get("id"))
    return known, in_section


def _image_roles(catalog_dir: Path):
    """IMG の役の値域を視覚方針の正本から引く。

    正本は thresholds.min_images_per_main_section.role_split.roles[].role。読めない
    経路では FALLBACK_IMAGE_ROLES へ落ちる (視覚方針は fail-soft 契約であり、正本の
    不在で『役の検査そのものが消える』方が事故になる)。落ちた先が出荷中の正本と
    ずれていないことは受入テストが押さえる。
    """
    path = catalog_dir / VISUAL_POLICY_RELNAME
    if not path.is_file():
        return FALLBACK_IMAGE_ROLES
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return FALLBACK_IMAGE_ROLES
    if not isinstance(data, dict):
        return FALLBACK_IMAGE_ROLES
    split = (((data.get("thresholds") or {}).get("min_images_per_main_section") or {})
             .get("role_split") or {})
    entries = split.get("roles") if isinstance(split, dict) else None
    if not isinstance(entries, list):
        return FALLBACK_IMAGE_ROLES
    roles = tuple(
        entry["role"] for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("role"), str) and entry["role"]
    )
    return roles or FALLBACK_IMAGE_ROLES


def _config_schema(catalog_dir: Path):
    """C12 の構成データスキーマ。未実体なら None (照合できない検査は行わない)。"""
    path = catalog_dir.parent / SCHEMA_RELPATH
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _document_field_names(schema):
    if not isinstance(schema, dict):
        return None
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None
    return set(properties.keys())


def _granularity_value_domains(schema):
    """スキーマから粒度 2 軸の値域を引く (本 script は enum を自前で持たない)。"""
    if schema is None:
        return {}
    found = {}

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in GRANULARITY_KEYS and isinstance(value, dict):
                    enum = value.get("enum")
                    if isinstance(enum, list) and enum and key not in found:
                        found[key] = list(enum)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return found


# ---------------------------------------------------------------------------
# catalog 自己整合検査 (全モード共通の前段 / fail-closed)
# ---------------------------------------------------------------------------


def _malformed(message: str) -> str:
    return "{} {}".format(E_CATALOG_MALFORMED, message)


def _dir_token_is_safe(token: str) -> bool:
    """dir_token がディレクトリ名として安全か (文字種は問わない)。

    日本語を許すため字種の allowlist は張らない。代わりに、パスを飛び出す / 不可視文字で
    区別が付かない / 隠しディレクトリになる、という実害のある形だけを落とす。
    """
    if not token or token != token.strip():
        return False
    if token.startswith("."):
        return False
    for ch in token:
        if ch in DIR_TOKEN_FORBIDDEN or ch.isspace() or ord(ch) < 32 or ord(ch) == 127:
            return False
    return True


def _validate_vocabulary(catalog, diagnostics) -> list:
    entries = catalog.get("vocabulary")
    if not isinstance(entries, list) or not entries:
        diagnostics.append(_malformed("vocabulary が 1 件以上の配列でない"))
        return []

    valid = []
    seen_slugs = set()
    seen_tokens = set()
    seen_aliases = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            diagnostics.append(_malformed("vocabulary[{}] がオブジェクトでない".format(index)))
            continue
        missing = [k for k in VOCABULARY_ENTRY_KEYS if k not in entry]
        if missing:
            diagnostics.append(
                _malformed("vocabulary[{}] に必須キーが無い: {}".format(index, ", ".join(missing)))
            )
            continue
        slug = entry["slug"]
        token = entry["dir_token"]
        aliases = entry["aliases"]
        ok = True
        if not isinstance(slug, str) or not SLUG_PATTERN.match(slug):
            diagnostics.append(_malformed("slug が ^[a-z][a-z0-9-]*$ に一致しない: {!r}".format(slug)))
            ok = False
        elif slug in seen_slugs:
            diagnostics.append(_malformed("slug が重複している: {}".format(slug)))
            ok = False
        else:
            seen_slugs.add(slug)
        if not isinstance(token, str) or not _dir_token_is_safe(token):
            diagnostics.append(
                _malformed(
                    "dir_token がディレクトリ名として安全でない "
                    "(空・空白・パス区切り・禁止文字・ドット始まりのいずれか): {!r}".format(token)
                )
            )
            ok = False
        elif token in seen_tokens:
            diagnostics.append(_malformed("dir_token が重複している: {}".format(token)))
            ok = False
        else:
            seen_tokens.add(token)
        if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
            diagnostics.append(_malformed("aliases が文字列配列でない: {!r}".format(slug)))
            ok = False
        else:
            for alias in aliases:
                key = _normalize_token(alias)
                owner = seen_aliases.get(key)
                if owner is not None:
                    diagnostics.append(
                        _malformed(
                            "alias が {} と {} に重複して定義されている: {}".format(owner, slug, alias)
                        )
                    )
                    ok = False
                else:
                    seen_aliases[key] = slug
                if key in seen_slugs and key != slug:
                    diagnostics.append(
                        _malformed("alias が別の slug と衝突している: {}".format(alias))
                    )
                    ok = False
        if ok:
            valid.append(entry)
    return valid


def _validate_section_order(slug, preset, context, diagnostics) -> list:
    order = preset.get("section_order")
    if not isinstance(order, list):
        diagnostics.append(_malformed("{}: section_order が配列でない".format(slug)))
        return []
    ids = []
    for index, section in enumerate(order):
        if not isinstance(section, dict):
            diagnostics.append(
                _malformed("{}: section_order[{}] がオブジェクトでない".format(slug, index))
            )
            continue
        present = set(section.keys())
        if present != SECTION_ENTRY_KEYS:
            # image_role の欠落だけは専用コードで落とす。汎用の「キー面が違う」に混ぜると、
            # 役の宣言漏れという直せる 1 事実が preset 全体の形の崩れと区別できなくなる。
            if SECTION_ENTRY_KEYS - present == {"image_role"} and not (
                present - SECTION_ENTRY_KEYS
            ):
                diagnostics.append(
                    "{} {}: section_order[{}] に image_role が無い。IMG 部品の役は "
                    "preset が宣言する ({} のいずれか)".format(
                        E_PRESET_IMAGE_ROLE_MISSING,
                        slug,
                        index,
                        "/".join(context["image_roles"]),
                    )
                )
                continue
            diagnostics.append(
                _malformed(
                    "{}: section_order[{}] のキー面が固定形と一致しない: {}".format(
                        slug, index, sorted(section.keys())
                    )
                )
            )
            continue
        section_id = section["id"]
        if not isinstance(section_id, str) or not section_id:
            diagnostics.append(_malformed("{}: section id が非空文字列でない".format(slug)))
            continue
        if section_id in ids:
            diagnostics.append(_malformed("{}: section id が preset 内で重複: {}".format(slug, section_id)))
        ids.append(section_id)
        if not isinstance(section["heading"], str) or not section["heading"]:
            diagnostics.append(_malformed("{}/{}: heading が非空文字列でない".format(slug, section_id)))
        if not isinstance(section["required"], bool):
            diagnostics.append(_malformed("{}/{}: required が真偽値でない".format(slug, section_id)))
        kind = section["section_kind"]
        if kind not in context["section_kinds"]:
            diagnostics.append(
                _malformed(
                    "{}/{}: section_kind が {} の語彙に存在しない: {!r}".format(
                        slug, section_id, SECTIONS_RELNAME, kind
                    )
                )
            )
        image_role = section["image_role"]
        if image_role not in context["image_roles"]:
            diagnostics.append(
                "{} {}/{}: image_role が列挙外: {!r} (許すのは {})".format(
                    E_PRESET_IMAGE_ROLE_UNKNOWN,
                    slug,
                    section_id,
                    image_role,
                    "/".join(context["image_roles"]),
                )
            )
        recommended = section["recommended_parts"]
        if not isinstance(recommended, list):
            diagnostics.append(
                _malformed("{}/{}: recommended_parts が配列でない".format(slug, section_id))
            )
            continue
        for part_id in recommended:
            if part_id not in context["known_parts"]:
                diagnostics.append(
                    _malformed(
                        "{}/{}: {} に存在しない部品 id: {!r}".format(
                            slug, section_id, PARTS_RELNAME, part_id
                        )
                    )
                )
            elif part_id not in context["in_section_parts"]:
                diagnostics.append(
                    _malformed(
                        "{}/{}: section へ置けない部品 id (section_scope が {} でない): {!r}".format(
                            slug, section_id, PART_SECTION_SCOPE, part_id
                        )
                    )
                )
    return ids


def _validate_variants(slug, preset, section_ids, diagnostics):
    variants = preset.get("presentation_order_variants")
    if variants is None:
        return
    if not isinstance(variants, dict) or set(variants.keys()) != PRESENTATION_ORDER_KEYS:
        diagnostics.append(
            "{} {}: presentation_order_variants のキー集合が厳密に {} でない".format(
                E_PRESET_ORDER_KEYS, slug, sorted(PRESENTATION_ORDER_MODES)
            )
        )
        return
    for mode in PRESENTATION_ORDER_MODES:
        order = variants[mode]
        if not isinstance(order, list) or any(not isinstance(v, str) for v in order):
            diagnostics.append(
                "{} {}/{}: 順序が文字列配列でない".format(E_PRESET_ORDER_NOT_PERMUTATION, slug, mode)
            )
            continue
        if sorted(order) != sorted(section_ids) or len(set(order)) != len(order):
            diagnostics.append(
                "{} {}/{}: section_order の id 集合の順列でない (欠落 / 未知 id / 重複)".format(
                    E_PRESET_ORDER_NOT_PERMUTATION, slug, mode
                )
            )


def _validate_required_document_fields(slug, preset, context, diagnostics):
    fields = preset.get("required_document_fields")
    if fields is None:
        return
    if not isinstance(fields, list) or any(not isinstance(f, str) for f in fields):
        diagnostics.append(_malformed("{}: required_document_fields が文字列配列でない".format(slug)))
        return
    if len(set(fields)) != len(fields):
        diagnostics.append(_malformed("{}: required_document_fields に重複がある".format(slug)))
    known = context["document_fields"]
    if known is None:
        return
    for name in fields:
        if name not in known:
            diagnostics.append(
                "{} {}: C12 の document レベルフィールドとして実在しない: {!r}".format(
                    E_PRESET_REQFIELD_UNKNOWN, slug, name
                )
            )


def _validate_granularity(slug, preset, context, diagnostics):
    if "granularity_defaults" not in preset:
        diagnostics.append(
            "{} {}: 粒度既定値は全 preset の必須キー (実行時 fallback を置かない)".format(
                E_GRANULARITY_MISSING, slug
            )
        )
        return
    defaults = preset["granularity_defaults"]
    if not isinstance(defaults, dict) or set(defaults.keys()) != GRANULARITY_KEYS:
        diagnostics.append(
            "{} {}: キー集合が厳密に {} でない".format(E_GRANULARITY_KEYS, slug, GRANULARITY_FIELDS)
        )
        return
    domains = context["granularity_domains"]
    for field in GRANULARITY_FIELDS:
        allowed = domains.get(field)
        if not allowed:
            continue
        if defaults[field] not in allowed:
            diagnostics.append(
                "{} {}/{}: C12 の値域に無い値: {!r}".format(
                    E_GRANULARITY_VALUE, slug, field, defaults[field]
                )
            )


def _validate_presets(catalog, entries, context, diagnostics):
    presets = catalog.get("presets")
    if not isinstance(presets, dict):
        diagnostics.append(_malformed("presets がオブジェクトでない"))
        return

    slugs = [e["slug"] for e in entries]
    for slug in slugs:
        if slug not in presets:
            diagnostics.append(
                "{} 語彙にプリセットが対応していない: {}".format(E_PRESET_UNCOVERED, slug)
            )
    for key in presets:
        if key not in slugs:
            diagnostics.append("{} 語彙に無い preset キー: {}".format(E_PRESET_ORPHAN, key))

    for key in list(slugs) + [k for k in presets if k not in slugs]:
        preset = presets.get(key)
        if preset is None:
            continue
        if not isinstance(preset, dict):
            diagnostics.append(_malformed("{}: preset がオブジェクトでない".format(key)))
            continue
        extra = sorted(set(preset.keys()) - ALLOWED_PRESET_KEYS)
        if extra:
            diagnostics.append(
                "{} {}: 許可キー {} の外のキー: {}".format(
                    E_PRESET_FORBIDDEN_KEY, key, sorted(ALLOWED_PRESET_KEYS), extra
                )
            )
        missing = sorted(REQUIRED_PRESET_KEYS - set(preset.keys()) - {"granularity_defaults"})
        if missing:
            diagnostics.append(_malformed("{}: 必須キーが無い: {}".format(key, missing)))
        if "notes" in preset and not isinstance(preset["notes"], str):
            diagnostics.append(_malformed("{}: notes が文字列でない".format(key)))
        if "recommended_parts" in preset:
            recommended = preset["recommended_parts"]
            if not isinstance(recommended, list):
                diagnostics.append(_malformed("{}: recommended_parts が配列でない".format(key)))
            else:
                for part_id in recommended:
                    if part_id not in context["known_parts"]:
                        diagnostics.append(
                            _malformed(
                                "{}: {} に存在しない部品 id: {!r}".format(key, PARTS_RELNAME, part_id)
                            )
                        )
        section_ids = _validate_section_order(key, preset, context, diagnostics)
        _validate_variants(key, preset, section_ids, diagnostics)
        _validate_required_document_fields(key, preset, context, diagnostics)
        _validate_granularity(key, preset, context, diagnostics)


def validate_catalog(catalog, catalog_path) -> None:
    """手順 4 / 4i / 4j。違反があれば CatalogError (全診断を保持) を送出する。"""
    diagnostics = []
    if not isinstance(catalog, dict):
        raise CatalogError([_malformed("catalog のトップレベルがオブジェクトでない")])

    if catalog.get("schema_version") not in KNOWN_SCHEMA_VERSIONS:
        diagnostics.append(
            _malformed("schema_version が既知でない: {!r}".format(catalog.get("schema_version")))
        )

    catalog_dir = Path(catalog_path).resolve().parent
    schema = _config_schema(catalog_dir)
    known_parts, in_section_parts = _part_ids(catalog_dir)
    context = {
        "section_kinds": _known_section_kinds(catalog_dir),
        "known_parts": known_parts,
        "in_section_parts": in_section_parts,
        "document_fields": _document_field_names(schema),
        "granularity_domains": _granularity_value_domains(schema),
        "image_roles": _image_roles(catalog_dir),
    }

    entries = _validate_vocabulary(catalog, diagnostics)
    _validate_presets(catalog, entries, context, diagnostics)

    if diagnostics:
        raise CatalogError(diagnostics)


def load_catalog(path=None) -> dict:
    """読み込み + 自己整合検査済みの catalog dict を返す。違反は CatalogError。"""
    catalog_path = Path(path) if path is not None else resolve_catalog_path(None)
    if not catalog_path.is_file():
        raise LaunchError("語彙正本が実在しない: {}".format(catalog_path))
    try:
        raw = catalog_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LaunchError("語彙正本を読めない: {} ({})".format(catalog_path, exc))
    try:
        catalog = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LaunchError(
            "語彙正本が JSON として parse できない: {} (line {}, column {})".format(
                catalog_path, exc.lineno, exc.colno
            )
        )
    validate_catalog(catalog, catalog_path)
    return catalog


# ---------------------------------------------------------------------------
# 解決 (公開 API)
# ---------------------------------------------------------------------------


def _normalize_token(token: str) -> str:
    return unicodedata.normalize("NFKC", str(token)).strip().lower()


def vocabulary(catalog: dict) -> list:
    """slug を catalog 記載順で返す。"""
    return [entry["slug"] for entry in catalog["vocabulary"]]


def resolve(catalog: dict, token: str) -> dict:
    """slug / alias の完全一致で vocabulary エントリを返す (部分一致はしない)。"""
    normalized = _normalize_token(token)
    for entry in catalog["vocabulary"]:
        if _normalize_token(entry["slug"]) == normalized:
            return entry
    for entry in catalog["vocabulary"]:
        for alias in entry["aliases"]:
            if _normalize_token(alias) == normalized:
                return entry
    raise UnknownPurposeError(token, vocabulary(catalog))


def preset(catalog: dict, slug: str) -> dict:
    """当該用途のプリセット定義を返す (呼び出し側の変更が catalog へ波及しない copy)。"""
    entry = resolve(catalog, slug)
    return json.loads(json.dumps(catalog["presets"][entry["slug"]]))


def granularity_defaults(catalog: dict, purpose: str) -> dict:
    """doc_type ごとの粒度既定値。全語彙で必ず返る (None も fallback も持たない)。"""
    entry = resolve(catalog, purpose)
    return dict(catalog["presets"][entry["slug"]]["granularity_defaults"])


def dir_token(catalog: dict, slug: str) -> str:
    """C19 がディレクトリ名の <種別> に使う値。"""
    return resolve(catalog, slug)["dir_token"]


# ---------------------------------------------------------------------------
# 出力の組み立て
# ---------------------------------------------------------------------------


def _dump(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_list_payload(catalog: dict) -> list:
    return [
        {
            "slug": entry["slug"],
            "label_ja": entry["label_ja"],
            "dir_token": entry["dir_token"],
            "aliases": list(entry["aliases"]),
            "preset_defined": entry["slug"] in catalog["presets"],
        }
        for entry in catalog["vocabulary"]
    ]


def build_purpose_payload(catalog, catalog_path, token, presentation_order=None) -> dict:
    entry = resolve(catalog, token)
    slug = entry["slug"]
    definition = preset(catalog, slug)

    sections = definition["section_order"]
    applied = None
    variants = definition.get("presentation_order_variants")
    if presentation_order is not None and isinstance(variants, dict):
        order = variants.get(presentation_order)
        if isinstance(order, list):
            by_id = {section["id"]: section for section in sections}
            sections = [by_id[section_id] for section_id in order]
            applied = presentation_order

    payload = {
        "purpose": slug,
        "label_ja": entry["label_ja"],
        "dir_token": entry["dir_token"],
        "section_order": sections,
        "recommended_parts": definition["recommended_parts"],
        "granularity_defaults": definition["granularity_defaults"],
        "presentation_order": presentation_order,
        "applied_variant": applied,
        "catalog_sha256": catalog_sha256(catalog_path),
    }
    if "notes" in definition:
        payload["notes"] = definition["notes"]
    if "required_document_fields" in definition:
        payload["required_document_fields"] = definition["required_document_fields"]
    return payload


# ---------------------------------------------------------------------------
# --audit-duplication (C42 のゲート実体)
# ---------------------------------------------------------------------------


def _audit_allowlist(root: Path) -> set:
    path = root / AUDIT_ALLOWLIST_RELPATH
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    paths = data.get("paths") if isinstance(data, dict) else None
    if not isinstance(paths, list):
        return set()
    return {str(p).replace("\\", "/").lstrip("./") for p in paths if isinstance(p, str)}


def audit_duplication(root: Path, slugs, catalog_path: Path):
    """語彙正本以外の場所での用途種別語彙のハードコード列挙を検出する。"""
    allowlist = _audit_allowlist(root)
    patterns = [
        (slug, re.compile(r"(?<![0-9A-Za-z_-]){}(?![0-9A-Za-z_-])".format(re.escape(slug))))
        for slug in slugs
    ]
    try:
        canonical = Path(catalog_path).resolve()
    except OSError:
        canonical = Path(catalog_path)

    scanned = 0
    violations = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in AUDIT_SUFFIXES:
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        parts = relative.parts
        if any(part in AUDIT_EXCLUDED_DIRS for part in parts):
            continue
        if any(part.startswith("__") for part in parts):
            continue
        rel_posix = relative.as_posix()
        if rel_posix in allowlist:
            continue
        try:
            if path.resolve() == canonical:
                continue
        except OSError:
            pass
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = []
        distinct = set()
        for lineno, line in enumerate(text.splitlines(), start=1):
            for slug, pattern in patterns:
                if pattern.search(line):
                    distinct.add(slug)
                    hits.append((rel_posix, lineno, slug))
        if len(distinct) >= AUDIT_DISTINCT_THRESHOLD:
            violations.extend(hits)
    return scanned, violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resolve-handout-preset.py",
        description="用途種別語彙と用途プリセットの単一の入口 (C23)",
        add_help=True,
    )
    parser.add_argument("--purpose", default=None)
    parser.add_argument("--presentation-order", dest="presentation_order",
                        choices=list(PRESENTATION_ORDER_MODES), default=None)
    parser.add_argument("--list", dest="list_mode", action="store_true")
    parser.add_argument("--audit-duplication", dest="audit", action="store_true")
    parser.add_argument("--catalog", default=None)
    parser.add_argument("--format", dest="fmt", choices=list(FORMATS), default=FORMATS[0])
    parser.add_argument("--root", default=None)
    return parser


def _emit(stream, lines):
    for line in lines:
        stream.write(line + "\n")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    modes = [bool(args.purpose is not None), bool(args.list_mode), bool(args.audit)]
    if sum(1 for m in modes if m) != 1:
        _emit(
            sys.stderr,
            ["--purpose / --list / --audit-duplication のうち厳密に 1 つを指定する"],
        )
        return 2
    if args.presentation_order is not None and args.purpose is None:
        _emit(sys.stderr, ["--presentation-order は --purpose と併用したときだけ意味を持つ"])
        return 2

    try:
        catalog_path = resolve_catalog_path(args.catalog)
        catalog = load_catalog(catalog_path)
    except LaunchError as exc:
        _emit(sys.stderr, exc.diagnostics)
        return 2
    except CatalogError as exc:
        _emit(sys.stderr, exc.diagnostics)
        return 1

    if args.list_mode:
        payload = build_list_payload(catalog)
        if args.fmt == "text":
            _emit(sys.stdout, [entry["slug"] for entry in payload])
        else:
            sys.stdout.write(_dump(payload))
        return 0

    if args.audit:
        root = Path(args.root) if args.root else Path(catalog_path).resolve().parent.parent
        if not root.is_dir():
            _emit(sys.stderr, ["--root のディレクトリが存在しない: {}".format(root)])
            return 2
        scanned, violations = audit_duplication(root, vocabulary(catalog), catalog_path)
        if violations:
            _emit(
                sys.stderr,
                [
                    "{} {}:{} 用途種別語彙のハードコード列挙: {}".format(
                        E_VOCAB_DUPLICATED, rel, lineno, slug
                    )
                    for rel, lineno, slug in violations
                ],
            )
            return 1
        if args.fmt == "text":
            _emit(sys.stdout, ["scanned={} violations=0".format(scanned)])
        else:
            sys.stdout.write(_dump({"scanned": scanned, "violations": []}))
        return 0

    token = _normalize_token(args.purpose)
    if any(sep in token for sep in COMPOSITE_SEPARATORS) or INTERNAL_SPACE.search(token):
        _emit(
            sys.stderr,
            [
                "{} 混成用途は表現できない (主用途 1 つ + セクション追加で表す): {!r}".format(
                    E_VOCAB_COMPOSITE, args.purpose
                )
            ],
        )
        return 1

    try:
        payload = build_purpose_payload(catalog, catalog_path, token, args.presentation_order)
    except UnknownPurposeError as exc:
        nearest = _nearest(token, exc.known)
        lines = [
            "{} 語彙正本に存在しない用途種別: {!r}".format(E_VOCAB_UNKNOWN, args.purpose),
        ]
        if nearest:
            lines.append("{} 最も近い候補: {}".format(E_VOCAB_UNKNOWN, nearest))
        lines.append("{} 全語彙: {}".format(E_VOCAB_UNKNOWN, ", ".join(exc.known)))
        _emit(sys.stderr, lines)
        return 1

    if args.fmt == "text":
        _emit(
            sys.stdout,
            ["{}\t{}".format(payload["purpose"], payload["label_ja"])]
            + ["  {}\t{}".format(s["id"], s["heading"]) for s in payload["section_order"]],
        )
    else:
        sys.stdout.write(_dump(payload))
    return 0


def _nearest(token: str, known):
    import difflib

    matches = difflib.get_close_matches(token, list(known), n=1, cutoff=0.6)
    return matches[0] if matches else ""


if __name__ == "__main__":
    sys.exit(main())

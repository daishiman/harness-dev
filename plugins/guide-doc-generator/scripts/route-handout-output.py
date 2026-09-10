#!/usr/bin/env python3
# /// script
# name: route-handout-output
# version: 0.1.0
# purpose: C19 出力先ディレクトリを決定論解決し、命名規則と同梱 4 点 (HTML・構成データ・README・ルーティング記録) の充足を検査する
# inputs:
#   - argv: --config <path> [--out-dir <dir>] [--assets-src <dir>] [--place-config] [--check-only] [--json-report <path>]
#   - env: HB_OUT_DIR
#   - file: config/handout-output.json の default_out_dir
# outputs:
#   - dir: 解決した出力先とその同梱物
#   - file: --json-report の検査結果
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out / --json-report / --config-out で明示された path のみ
# ///
"""C19 route-handout-output.py — 出力先の決定論解決と同梱 4 点の検査。

契約の正本は plugin-plans/guide-doc-generator/briefs/script-brief-C19.json
(argv / stdout / stderr / exit_codes / write_scope / bundle_writers / algorithm /
naming_rule / acceptance_checks / failure_modes) と briefs/RESOLUTION-P03.md の Y-04。

本 script が持たないもの (いずれも外部の単一正本から受け取る):
- 種別語彙と dir_token → C23 resolve-handout-preset.py (importlib で 1 経路のみ)
- 既定出力先の値 → config/handout-output.json
- 現在日付 → 構成データの date フィールド (stdlib の日付 API を触らない)
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

TOOL = "route-handout-output"
STDERR_PREFIX = "[{}]".format(TOOL)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PRESET_SCRIPT = Path(__file__).resolve().parent / "resolve-handout-preset.py"
PRESET_MODULE_NAME = "hb_preset"

OUTPUT_CONFIG_RELPATH = "config/handout-output.json"
OUTPUT_CONFIG_KEY = "default_out_dir"
#: ディレクトリ名書式の正本キー。書式そのものは本ソースへ持たない (C18 / C10 と
#: 同じ値を 3 箇所へ焼いた結果、1 箇所を直しても他が古い区切りで判定していた)。
DIRNAME_CONFIG_KEY = "dir_name_format"
DIRNAME_PLACEHOLDERS = ("{date}", "{slug}")
ENV_OUT_DIR = "HB_OUT_DIR"

STAGE_ARGV = "--out-dir"
STAGE_ENV = ENV_OUT_DIR
STAGE_CONFIG = "handout-output.json"

ROUTE_MARKER = ".handout-route.json"
PLACED_CONFIG_NAME = "handout-config.json"
ASSETS_DIRNAME = "assets"
BODY_NAME = "handout.html"
READ_ME_NAME = "README.md"

# 同梱 4 点と writer。正本は brief bundle_writers (P03 Y-04)。
# kind: "file" | "dir"
BUNDLE = (
    (BODY_NAME, "C11", "file"),
    (PLACED_CONFIG_NAME, "C19", "file"),
    (ASSETS_DIRNAME, "C19", "dir"),
    (READ_ME_NAME, "C01", "file"),
)

# algorithm 3: 受理する日付書式は 1 つだけ (ゼロ埋め・スラッシュ区切り)。
DATE_PATTERN = re.compile(r"^\d{4}/\d{2}/\d{2}$")

SLUG_FORBIDDEN = set('/\\:*?"<>|')
SLUG_MAX_CHARS = 40
SLUG_FALLBACK_PREFIX = "topic-"
SEQUENCE_MAX = 99

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_CONTRACT = 2


class ContractError(Exception):
    """検査を実行できない契約違反 (exit 2)。"""


class ViolationError(Exception):
    """検査で検出した違反 (exit 1)。1 違反 1 行。"""

    def __init__(self, lines):
        if isinstance(lines, str):
            lines = [lines]
        self.lines = list(lines)
        super().__init__("; ".join(self.lines))


def emit_errors(lines) -> None:
    for line in lines:
        sys.stderr.write("{} {}\n".format(STDERR_PREFIX, line))


# ---------------------------------------------------------------------------
# argv (algorithm 1)
# ---------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # pragma: no cover - argparse 経路
        emit_errors(["引数が不正: {}".format(message)])
        raise SystemExit(EXIT_CONTRACT)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog=TOOL, add_help=True, allow_abbrev=False)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--assets-src", default=None)
    parser.add_argument("--place-config", action="store_true")
    parser.add_argument("--json-report", default=None)
    return parser


# ---------------------------------------------------------------------------
# 構成データ (algorithm 2 / 3 / 4 / 5)
# ---------------------------------------------------------------------------


def read_config(path_text: str):
    path = Path(path_text)
    if not path.is_file():
        raise ContractError("--config が読めない: {}".format(path))
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractError("--config を読めない: {} ({})".format(path, exc))
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("--config が JSON として parse できない: {} ({})".format(path, exc))
    if not isinstance(data, dict):
        raise ContractError("--config が object でない: {}".format(path))
    return path, raw, data


def require_normalized(data: dict) -> None:
    provenance = data.get("provenance")
    marker = provenance.get("normalized_by") if isinstance(provenance, dict) else None
    if not isinstance(marker, str) or not marker.strip():
        raise ContractError(
            "構成データが未正規化 (provenance.normalized_by が無い)。C12 の --normalize を先に通すこと"
        )


def require_date(data: dict) -> str:
    value = data.get("date")
    if not isinstance(value, str) or not DATE_PATTERN.match(value):
        raise ContractError("date フィールドが yyyy/mm/dd (ゼロ埋め) でない: {!r}".format(value))
    return value


def require_doc_type(data: dict) -> str:
    value = data.get("doc_type")
    if not isinstance(value, str) or not value.strip():
        raise ContractError("doc_type フィールドが無いか文字列でない: {!r}".format(value))
    return value


def load_preset_module():
    """C23 を importlib でモジュールとして読み込む (sanctioned_access の唯一の経路)。"""
    if not PRESET_SCRIPT.is_file():
        raise ContractError("語彙正本の入口 {} が実在しない".format(PRESET_SCRIPT.name))
    try:
        spec = importlib.util.spec_from_file_location(PRESET_MODULE_NAME, PRESET_SCRIPT)
        if spec is None or spec.loader is None:
            raise ImportError("spec を組み立てられない")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except BaseException as exc:
        raise ContractError("語彙正本の入口を読み込めない: {} ({})".format(PRESET_SCRIPT.name, exc))
    return module


def resolve_dir_token(module, doc_type: str):
    """語彙照合 (algorithm 4)。未知の doc_type は exit 1、正本を引けない場合は exit 2。"""
    try:
        catalog = module.load_catalog()
        known = list(module.vocabulary(catalog))
    except BaseException as exc:
        raise ContractError("語彙正本を読み出せない: {}".format(exc))
    if doc_type not in known:
        raise ViolationError("doc_type が語彙正本に無い: {!r}".format(doc_type))
    try:
        token = module.dir_token(catalog, doc_type)
    except BaseException as exc:
        raise ContractError("語彙正本から dir_token を引けない: {}".format(exc))
    if not isinstance(token, str) or not token:
        raise ContractError("語彙正本の dir_token が文字列でない: {!r}".format(token))
    return token


def derive_slug(title) -> str:
    """slug_rule (b) / (c): title からの決定論導出。"""
    source = title if isinstance(title, str) else ""
    normalized = unicodedata.normalize("NFKC", source)
    lowered = "".join(
        chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in normalized
    )
    replaced = "".join(
        "-" if (ch in SLUG_FORBIDDEN or ch.isspace() or ord(ch) < 32 or ord(ch) == 127) else ch
        for ch in lowered
    )
    collapsed = re.sub(r"-+", "-", replaced)
    trimmed = collapsed.strip("-. ")
    truncated = trimmed[:SLUG_MAX_CHARS].strip("-. ")
    if truncated:
        return truncated
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return SLUG_FALLBACK_PREFIX + digest


def check_explicit_slug(value: str) -> str:
    """slug_rule (a): 明示 subject_slug は禁止文字検査だけを通して採用する。"""
    if not value.strip():
        raise ContractError("subject_slug が空である")
    for ch in value:
        if ch in SLUG_FORBIDDEN or ord(ch) < 32 or ord(ch) == 127:
            raise ContractError("subject_slug に使えない文字がある: {!r}".format(value))
    if value in (".", "..") or value.startswith("."):
        raise ContractError("subject_slug がドットで始まる: {!r}".format(value))
    if os.sep in value or (os.altsep and os.altsep in value):
        raise ContractError("subject_slug にパス区切りがある: {!r}".format(value))
    return value


def resolve_slug(data: dict) -> str:
    explicit = data.get("subject_slug")
    if isinstance(explicit, str) and explicit != "":
        return check_explicit_slug(explicit)
    if explicit is not None and not isinstance(explicit, str):
        raise ContractError("subject_slug が文字列でない: {!r}".format(explicit))
    return derive_slug(data.get("title"))


# ---------------------------------------------------------------------------
# 出力先ルート (algorithm 6 / 7)
# ---------------------------------------------------------------------------


def expand(value: str) -> str:
    return os.path.expanduser(os.path.expandvars(value))


def declared_default_out_dir():
    path = PLUGIN_ROOT / OUTPUT_CONFIG_RELPATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError("{} を読めない: {}".format(OUTPUT_CONFIG_RELPATH, exc))
    value = data.get(OUTPUT_CONFIG_KEY) if isinstance(data, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def declared_dir_name_format() -> str:
    """ディレクトリ名書式を正本から引く (algorithm 6 と同じ config を読む)。

    キー不在・型不正・未知プレースホルダはいずれも既定値へ倒さず ContractError に
    する。既定値へ倒すと、正本を書き換えても script が黙って旧書式で出し続ける。
    """
    path = PLUGIN_ROOT / OUTPUT_CONFIG_RELPATH
    if not path.is_file():
        raise ContractError("{} が無い ({} を解決できない)".format(
            OUTPUT_CONFIG_RELPATH, DIRNAME_CONFIG_KEY))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError("{} を読めない: {}".format(OUTPUT_CONFIG_RELPATH, exc))
    value = data.get(DIRNAME_CONFIG_KEY) if isinstance(data, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise ContractError("{} に {} が無いか文字列でない: {!r}".format(
            OUTPUT_CONFIG_RELPATH, DIRNAME_CONFIG_KEY, value))
    for placeholder in DIRNAME_PLACEHOLDERS:
        if placeholder not in value:
            raise ContractError("{} に {} が含まれない: {!r}".format(
                DIRNAME_CONFIG_KEY, placeholder, value))
    stripped = value
    for placeholder in DIRNAME_PLACEHOLDERS:
        stripped = stripped.replace(placeholder, "")
    if "{" in stripped or "}" in stripped:
        raise ContractError("{} に未知のプレースホルダがある: {!r}".format(
            DIRNAME_CONFIG_KEY, value))
    return value


def build_base_name(date_value: str, slug: str) -> str:
    """正本の書式へ date / slug を差し込む。書式を組み立てる場所はここ 1 箇所。"""
    return declared_dir_name_format().format(
        date=date_value.replace("/", "-"), slug=slug
    )


def resolve_root(argv_value):
    """解決 4 段。どの段で解決したかを合わせて返す。"""
    if argv_value:
        return expand(str(argv_value)), STAGE_ARGV
    env_value = os.environ.get(ENV_OUT_DIR)
    if env_value and env_value.strip():
        return expand(env_value), STAGE_ENV
    declared = declared_default_out_dir()
    if declared:
        return expand(declared), STAGE_CONFIG
    raise ContractError(
        "出力先ルートを解決できない ({} > {} > {} の {} がいずれも無い)".format(
            STAGE_ARGV, STAGE_ENV, STAGE_CONFIG, OUTPUT_CONFIG_KEY
        )
    )


def prepare_root(root_text: str, create: bool) -> str:
    root = Path(root_text)
    if root.exists() and not root.is_dir():
        raise ContractError("出力先ルートがディレクトリでない: {}".format(root))
    if create and not root.exists():
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ContractError("出力先ルートを作れない: {} ({})".format(root, exc))
    return os.path.realpath(str(root))


def confine(root_real: str, name: str) -> str:
    candidate = os.path.join(root_real, name)
    real = os.path.realpath(candidate)
    if real != root_real and not real.startswith(root_real + os.sep):
        raise ContractError("解決先が出力先ルートの外へ出る: {}".format(candidate))
    if os.path.dirname(real) != root_real:
        raise ContractError("解決先が出力先ルート直下でない: {}".format(candidate))
    return candidate


# ---------------------------------------------------------------------------
# 衝突解決 (algorithm 8 / collision_rule)
# ---------------------------------------------------------------------------


def marker_sha256(directory: Path):
    marker = directory / ROUTE_MARKER
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("config_sha256") if isinstance(data, dict) else None
    return value if isinstance(value, str) else None


def resolve_collision(root_real: str, base_name: str, digest: str) -> str:
    base = Path(root_real) / base_name
    if not base.exists():
        return base_name
    if base.is_dir() and marker_sha256(base) == digest:
        return base_name
    for number in range(2, SEQUENCE_MAX + 1):
        name = "{}-{}".format(base_name, number)
        candidate = Path(root_real) / name
        if not candidate.exists():
            return name
        if candidate.is_dir() and marker_sha256(candidate) == digest:
            return name
    raise ViolationError(
        "同名ディレクトリの連番が上限 {} を超えた: {}".format(SEQUENCE_MAX, base_name)
    )


# ---------------------------------------------------------------------------
# 配置 (algorithm 9 / 9b / 9c)
# ---------------------------------------------------------------------------


def audit_assets_src(src_text: str) -> Path:
    src = Path(src_text)
    if not src.exists():
        raise ContractError("--assets-src が実在しない: {}".format(src))
    if not src.is_dir():
        raise ContractError("--assets-src がディレクトリでない: {}".format(src))
    src_real = os.path.realpath(str(src))
    for current, dirnames, filenames in os.walk(str(src), followlinks=False):
        for entry in list(dirnames) + list(filenames):
            path = os.path.join(current, entry)
            if not os.path.islink(path):
                continue
            target = os.path.realpath(path)
            if target != src_real and not target.startswith(src_real + os.sep):
                raise ContractError(
                    "--assets-src の外を指す symlink があるため複製しない: {}".format(path)
                )
    return src


def copy_assets(src: Path, dest_root: Path) -> None:
    src_text = str(src)
    for current, dirnames, filenames in os.walk(src_text, followlinks=False):
        dirnames.sort()
        rel = os.path.relpath(current, src_text)
        target_dir = dest_root if rel == "." else dest_root / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for filename in sorted(filenames):
            source_file = Path(current) / filename
            target_file = target_dir / filename
            if target_file.is_file():
                try:
                    if target_file.read_bytes() == source_file.read_bytes():
                        continue
                except OSError:
                    pass
            shutil.copy2(str(source_file), str(target_file))


def write_marker(directory: Path, payload: dict) -> None:
    (directory / ROUTE_MARKER).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# 同梱 4 点の検査 (algorithm 10)
# ---------------------------------------------------------------------------


def inspect_bundle(directory: Path):
    states = []
    for name, writer, kind in BUNDLE:
        path = directory / name
        present = path.is_dir() if kind == "dir" else path.is_file()
        states.append((name, writer, "present" if present else "absent"))
    return states


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def run(args) -> int:
    if args.check_only and args.place_config:
        raise ContractError("--check-only と --place-config は併用できない")

    config_path, config_bytes, config_data = read_config(args.config)
    require_normalized(config_data)
    date_value = require_date(config_data)
    doc_type = require_doc_type(config_data)

    module = load_preset_module()
    token = resolve_dir_token(module, doc_type)
    slug = resolve_slug(config_data)

    root_text, stage = resolve_root(args.out_dir)
    root_real = prepare_root(root_text, create=not args.check_only)

    # doc_type 由来の token はディレクトリ名へ出さず marker.json の dir_token として
    # 残す (語彙照合そのものは resolve_dir_token で済んでおり、未知 doc_type は
    # ここへ到達しない)。
    base_name = build_base_name(date_value, slug)
    confine(root_real, base_name)

    digest = hashlib.sha256(config_bytes).hexdigest()

    assets_src = audit_assets_src(args.assets_src) if args.assets_src else None

    if args.check_only:
        chosen = base_name
    else:
        chosen = resolve_collision(root_real, base_name, digest)
    target_text = confine(root_real, chosen)
    target = Path(target_text)

    if not args.check_only:
        target.mkdir(parents=True, exist_ok=True)
        (target / ASSETS_DIRNAME).mkdir(parents=True, exist_ok=True)
        if assets_src is not None:
            copy_assets(assets_src, target / ASSETS_DIRNAME)
        if args.place_config:
            (target / PLACED_CONFIG_NAME).write_bytes(config_bytes)
        write_marker(
            target,
            {
                "config_path": str(config_path),
                "config_sha256": digest,
                "date": date_value,
                "dir_token": token,
                "doc_type": doc_type,
                "resolved_from": stage,
                "subject_slug": slug,
            },
        )

    states = inspect_bundle(target)

    lines = [os.path.realpath(target_text), "resolved_from: {}".format(stage)]
    for name, writer, state in states:
        lines.append("{}: {} (writer: {})".format(name, state, writer))
    sys.stdout.write("\n".join(lines) + "\n")

    if args.json_report:
        report = {
            "resolved_path": os.path.realpath(target_text),
            "resolved_from": stage,
            "check_only": bool(args.check_only),
            "config_sha256": digest,
            "bundle": {name: state for name, _writer, state in states},
            "bundle_writers": {name: writer for name, writer, _state in states},
        }
        Path(args.json_report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if args.check_only:
        missing = [
            "同梱物が欠落している: {} (writer: {})".format(name, writer)
            for name, writer, state in states
            if state == "absent"
        ]
        if missing:
            emit_errors(missing)
            return EXIT_VIOLATION
    return EXIT_OK


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ViolationError as exc:
        emit_errors(exc.lines)
        return EXIT_VIOLATION
    except ContractError as exc:
        emit_errors([str(exc)])
        return EXIT_CONTRACT


if __name__ == "__main__":
    raise SystemExit(main())

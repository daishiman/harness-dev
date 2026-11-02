#!/usr/bin/env python3
# /// script
# name: embed-assets
# version: 0.1.0
# purpose: C13 素材ファイルを base64 data URI へ畳み込む。原本の複製・配置 (C19) と HTML への焼き込み (C11) は担わない
# inputs:
#   - argv: --config <path> --assets-dir <dir> [--out <path>] [--max-bytes <n>]
#   - dir: 素材ディレクトリ
# outputs:
#   - file: --out で指定した data URI 表 (省略時は stdout)
#   - exit: 0=成功 / 1=入力データ側の規約違反 (差し戻し先は構成データまたは HTML) / 2=実行不能 (argv 不正・入出力の不在や読取不可・契約違反)
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out / --json-report / --config-out で明示された path のみ
# ///
"""C13 embed-assets.py — 素材を base64 data URI へ畳み込む (script-brief-C13.json)。

責務は data URI の生成だけ。原本の複製・配置は C19、HTML への焼き込みは C11 が担う。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_CONTRACT = 2

DEFAULT_MAX_BYTES = 5242880

STATUS_EMBEDDED = "embedded"
STATUS_SKIPPED = "skipped-oversize"

OCTET = "application/octet-stream"

# algorithm 5: 拡張子 -> MIME の自前対応表。OS 依存の解決器を使うと同一入力から
# 別マシンで別 MIME が出て C29 のバイト一致が壊れるため、表を本 script に持つ。
MIME_BY_EXT = {
    # 画像
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".avif": "image/avif",
    # 文書・表計算・スライド
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    # 圧縮・テキスト系
    ".zip": "application/zip",
    ".gz": "application/gzip",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".xml": "application/xml",
}

_WS = b" \t\r\n\v\f"


# --- algorithm 1: argv --------------------------------------------------------


def _positive_int(value: str) -> int:
    """--max-bytes は 1 以上の整数のみ。int() の寛容さ (前置空白等) に頼らない。"""
    if not (value.isascii() and value.isdigit()):
        raise argparse.ArgumentTypeError("1 以上の整数を指定してください: {!r}".format(value))
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("1 以上の整数を指定してください: {!r}".format(value))
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="embed-assets.py",
        description="正規化済み構成データの素材を base64 data URI へ畳み込む",
        allow_abbrev=False,
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--assets-dir", required=True, dest="assets_dir")
    parser.add_argument("--max-bytes", dest="max_bytes", type=_positive_int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--out", default=None)
    return parser


# --- algorithm 5 / 6: MIME 判定 ------------------------------------------------


def mime_from_ext(name: str) -> str | None:
    """表は小文字化した拡張子で引く。表に無ければ None。"""
    ext = os.path.splitext(name)[1].lower()
    return MIME_BY_EXT.get(ext)


def mime_from_signature(head: bytes) -> str | None:
    """先頭バイトから画像 MIME を決める純関数 (バイト列だけに依存する)。"""
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"GIF8"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    stripped = head.lstrip(_WS)
    if stripped.startswith(b"<"):
        return "image/svg+xml"
    return None


# --- algorithm 4: assets-dir 相対解決とサンドボックス検査 -------------------------


class ContractError(Exception):
    """exit2: 呼び出し契約違反。"""


class InputError(Exception):
    """exit1: 入力データ由来の失敗。"""


def resolve_asset_path(root: Path, src: str) -> tuple[Path, str]:
    """(実パス, assets-dir 相対の正規化パス) を返す。脱出は ContractError。"""
    if not isinstance(src, str) or src == "":
        raise InputError("素材参照が文字列でない: {!r}".format(src))
    if Path(src).is_absolute() or os.path.isabs(src):
        raise ContractError("素材参照が絶対パス: {}".format(src))
    normalized = os.path.normpath(os.path.join(str(root), src))
    candidate = Path(normalized)
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        raise ContractError("素材参照が --assets-dir の外を指している: {}".format(src)) from None
    # symlink 先が外に出る場合も脱出として扱う。
    real = candidate.resolve()
    try:
        real.relative_to(root)
    except ValueError:
        raise ContractError("素材参照の実体が --assets-dir の外にある: {}".format(src)) from None
    return candidate, relative.as_posix()


# --- 走査対象の収集 (algorithm 3) ----------------------------------------------


def collect_entries(config: dict) -> list[tuple[dict, bool]]:
    """(素材オブジェクト, 画像か) を構成データ上の出現順で返す。

    C12 が確定する正規化済み構成データでは素材は資料直下の assets[] / attachments[]
    に集約され、セクション側は id 参照だけを持つ。
    """
    entries: list[tuple[dict, bool]] = []
    for key, is_image in (("assets", True), ("attachments", False)):
        items = config.get(key)
        if items is None:
            continue
        if not isinstance(items, list):
            raise InputError("{} がリストでない".format(key))
        for item in items:
            if not isinstance(item, dict):
                raise InputError("{} の要素がオブジェクトでない".format(key))
            if "src" not in item:
                continue
            entries.append((item, is_image))
    return entries


# --- 本体 ----------------------------------------------------------------------


def process(config: dict, root: Path, max_bytes: int) -> tuple[dict, list[dict]]:
    entries = collect_entries(config)

    warnings: list[dict] = []
    cache: dict[str, str] = {}
    embedded_count = 0
    skipped_count = 0
    total_source_bytes = 0
    total_encoded_chars = 0

    for entry, is_image in entries:
        asset_id = entry.get("id")
        asset_id = asset_id if isinstance(asset_id, str) else ""
        path, relative = resolve_asset_path(root, entry.get("src"))

        # algorithm 4: 宣言された素材が無い/読めないのは構成データの誤り (exit1)。
        if not path.exists():
            raise InputError("宣言された素材が --assets-dir に無い: {}".format(relative))
        if path.is_dir():
            raise InputError("素材参照がディレクトリを指している: {}".format(relative))
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise InputError("素材を読めない: {} ({})".format(relative, exc.strerror)) from None

        source_bytes = len(data)
        total_source_bytes += source_bytes
        entry["source_bytes"] = source_bytes
        entry["embed_source_path"] = relative

        # algorithm 7: 上限超過は埋め込まず warning を残して継続する (C30)。
        if source_bytes > max_bytes:
            reason = "原本 {} バイトが上限 {} バイトを超過".format(source_bytes, max_bytes)
            hint = entry.get("fallback_hint")
            if not isinstance(hint, str) or not hint.strip():
                hint = "同梱の素材ディレクトリの {} を参照".format(relative)
            entry["embed_status"] = STATUS_SKIPPED
            entry["embed_skip_reason"] = reason
            entry.pop("data_uri", None)
            entry.pop("encoded_chars", None)
            warnings.append({"asset_id": asset_id, "reason": reason, "hint": hint})
            skipped_count += 1
            continue

        # algorithm 5 / 6: MIME を決める。画像だけ実バイトのシグネチャを優先する。
        ext_mime = mime_from_ext(relative)
        mime = ext_mime
        if is_image:
            sig_mime = mime_from_signature(data[:16])
            if sig_mime is not None and sig_mime != ext_mime:
                reason = "拡張子由来 MIME ({}) と実バイトのシグネチャ ({}) が食い違う".format(
                    ext_mime or "不明", sig_mime
                )
                warnings.append(
                    {
                        "asset_id": asset_id,
                        "reason": reason,
                        "hint": "シグネチャ由来の {} を採用した".format(sig_mime),
                    }
                )
                mime = sig_mime
        if mime is None:
            reason = "拡張子が MIME 対応表に無いため {} として埋め込む".format(OCTET)
            warnings.append(
                {
                    "asset_id": asset_id,
                    "reason": reason,
                    "hint": "同梱の素材ディレクトリの {} を参照".format(relative),
                }
            )
            mime = OCTET

        # algorithm 8: 無加工の base64 1 行。同一素材は 1 回だけ符号化して使い回す。
        cache_key = "{}\x00{}".format(relative, mime)
        payload = cache.get(cache_key)
        if payload is None:
            payload = base64.b64encode(data).decode("ascii")
            cache[cache_key] = payload
        entry["data_uri"] = "data:{};base64,{}".format(mime, payload)
        entry["embed_status"] = STATUS_EMBEDDED
        entry["encoded_chars"] = len(payload)
        entry.pop("embed_skip_reason", None)
        embedded_count += 1
        total_encoded_chars += len(payload)

    # algorithm 9: 資料単位のサマリ (合計は事実の記録であって閾値ではない)。
    config["asset_embedding"] = {
        "max_bytes": max_bytes,
        "embedded_count": embedded_count,
        "skipped_count": skipped_count,
        "total_source_bytes": total_source_bytes,
        "total_encoded_chars": total_encoded_chars,
        "warnings": warnings,
    }
    return config, warnings


def serialize(config: dict) -> bytes:
    """algorithm 10: ensure_ascii=False / indent=2 / キー順保存 / 末尾改行 1 個。"""
    text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    return text.encode("utf-8")


def write_out(out_path: Path, payload: bytes) -> None:
    """テンポラリへ書いてから os.replace で原子的に差し替える。"""
    tmp_path = out_path.with_name(out_path.name + ".embed-tmp")
    try:
        with open(tmp_path, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, out_path)
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise InputError("--out へ書き込めない: {} ({})".format(out_path, exc.strerror)) from None


def main(argv: list[str]) -> int:
    # algorithm 1
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = Path(args.assets_dir)
    if not root.is_dir():
        parser.error("--assets-dir がディレクトリでない: {}".format(args.assets_dir))
    root = root.resolve()

    # algorithm 2
    try:
        raw = Path(args.config).read_text(encoding="utf-8")
        config = json.loads(raw)
    except (OSError, ValueError) as exc:
        sys.stderr.write("ERROR 構成データを読めない: {} ({})\n".format(args.config, exc))
        return EXIT_INPUT
    if not isinstance(config, dict):
        sys.stderr.write("ERROR 構成データがオブジェクトでない: {}\n".format(args.config))
        return EXIT_INPUT

    # algorithm 3-9
    try:
        config, warnings = process(config, root, args.max_bytes)
    except ContractError as exc:
        sys.stderr.write("ERROR {}\n".format(exc))
        return EXIT_CONTRACT
    except InputError as exc:
        sys.stderr.write("ERROR {}\n".format(exc))
        return EXIT_INPUT

    payload = serialize(config)

    # algorithm 10
    if args.out is not None:
        try:
            write_out(Path(args.out), payload)
        except InputError as exc:
            sys.stderr.write("ERROR {}\n".format(exc))
            return EXIT_INPUT
    else:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()

    # algorithm 11: warning とサマリは exit0 でも stderr へ出す。
    for item in warnings:
        sys.stderr.write(
            "WARN {}: {}; 代替手段: {}\n".format(item["asset_id"], item["reason"], item["hint"])
        )
    summary = config["asset_embedding"]
    sys.stderr.write(
        "素材 {} 件 / 埋め込み {} 件 / skip {} 件 / 原本合計 {} バイト / data URI 合計 {} 文字\n".format(
            summary["embedded_count"] + summary["skipped_count"],
            summary["embedded_count"],
            summary["skipped_count"],
            summary["total_source_bytes"],
            summary["total_encoded_chars"],
        )
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

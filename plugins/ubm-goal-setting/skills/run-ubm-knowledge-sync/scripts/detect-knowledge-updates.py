#!/usr/bin/env python3
# /// script
# name: detect-knowledge-updates
# version: 0.2.1
# purpose: ナレッジソース (.md) を registry.json と MD5 照合し NEW/MODIFIED を検知する決定論ゲート。
#          旧 detect-knowledge-updates.sh 183 行の契約移植 (bash3.2 declare -A / md5 -q 分岐を stdlib 化)。
#          検知は sources 配下を再帰スキャンする。除外の正本は EXCLUDED_SUBDIRS (目標設定/・挑戦宣言/)
#          で、sources からの相対パスの先頭要素が当たる .md はハッシュも取らずに飛ばす (読む側では除かない)。
# inputs:
#   - argv: --registry FILE --sources DIR [--since YYYY-MM-DD] [--all] [--dry-run]
# outputs:
#   - stdout: 検知サマリ + {STATUS}|{source_type}|{file_hash}|{file_path} 形式で NEW/MODIFIED を列挙
#   - exit: 0=検知完了(未接続sourcesは0件正常終了・--help) / 2=usage
#           1=入力異常 (--since 不正・registry が無い/読めない/形が違う・ソースの .md を読めない)
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""ナレッジソースの差分検知 (registry.json との MD5 照合)。

旧 detect-knowledge-updates.sh の契約移植。挙動の逐語ではなく「registry と MD5 照合して
NEW/MODIFIED を漏れなく列挙する」検知ロジックを保存する。--all は全件強制 NEW (mode:full)、
--since は指定日より後の同一ハッシュも再処理する追加条件（差分の期間フィルタではない）。registry キーは vault-root 相対 (05_Project/UBM/...) 形式。
利用者自身の記録 (EXCLUDED_SUBDIRS) は北原ナレッジではないので、検知の段階で除く。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# 除外の正本: --sources (05_Project/UBM) 直下のサブディレクトリのうち、利用者自身の記録を置くもの。
# 目標設定/ は run-ubm-goal-setting、挑戦宣言/ は run-ubm-challenge の保存先で、北原ナレッジに当たらない。
# ここで除かないと、利用者の言葉が北原ナレッジとして抽出・引用される因果ループになる。
EXCLUDED_SUBDIRS = ("目標設定", "挑戦宣言")


def is_excluded(rel_parts: tuple[str, ...]) -> bool:
    """sources からの相対パスの先頭要素が EXCLUDED_SUBDIRS に当たるか (sources 直下のファイルは除外しない)。"""
    return len(rel_parts) > 1 and unicodedata.normalize("NFC", rel_parts[0]) in EXCLUDED_SUBDIRS


# source_type 判定: パターン→ラベル (先頭一致優先・旧 get_source_type 準拠)
SOURCE_TYPE_RULES = [
    ("YouTube", "youtube"),
    ("合宿", "camp"),
    ("動画教材", "teaching-material"),
    ("月報フィードバック", "monthly-feedback"),
    ("minutes - ", "seminar"),
    ("UBM - ", "event"),
]


def get_source_type(path_str: str) -> str:
    for needle, label in SOURCE_TYPE_RULES:
        if needle in path_str:
            return label
    return "other"


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


class RegistryError(Exception):
    """registry.json を読めない・形が違う。traceback ではなく exit 1 (入力異常) にする。"""


def load_registry(registry_file: Path) -> dict[str, str]:
    """file_path -> file_hash の辞書を返す。

    file_hash は md5 の文字列か null (vault に実ファイルが無い直接貼付のソース)。
    形の違う entry を読み飛ばすと、そのソースが毎回 NEW になって再抽出されるので止める。
    """
    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise RegistryError(f"registry を読めません: {registry_file}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise RegistryError(f"registry のトップが object ではありません: {registry_file}")
    files = data.get("files", [])
    if not isinstance(files, list):
        raise RegistryError(f"registry の files が配列ではありません: {registry_file}")
    out: dict[str, str] = {}
    for i, entry in enumerate(files):
        if not isinstance(entry, dict):
            raise RegistryError(f"registry の files[{i}] が object ではありません")
        fp = entry.get("file_path")
        file_hash = entry.get("file_hash")
        if not isinstance(fp, str) or not fp:
            raise RegistryError(f"registry の files[{i}].file_path が空でない文字列ではありません")
        if file_hash is not None and not isinstance(file_hash, str):
            raise RegistryError(f"registry の files[{i}].file_hash が文字列か null ではありません ({fp})")
        out[fp] = file_hash or ""
    return out


def print_empty_result(prefix: str, reason: str) -> None:
    print("=== UBMナレッジ更新検知 ===")
    print("")
    print(f"--- ディレクトリスキャン ({prefix}/ 配下を全検索) ---")
    print(reason)
    print("")
    print("=== 検知結果 ===")
    print("スキャン: 0 件")
    print("除外: 0 件")
    print("新規: 0 件")
    print("更新: 0 件")
    print("処理対象合計: 0 件")
    print("")
    print("全ファイル処理済み。更新はありません。")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="ナレッジソースの差分検知 (registry.json との MD5 照合)",
        add_help=True,
    )
    ap.add_argument("--registry", required=True, help="registry.json のパス")
    ap.add_argument("--sources", required=True, help="ナレッジソースのルート (例: $UBM_VAULT_ROOT/05_Project/UBM)")
    ap.add_argument("--since", default="", help="指定日より後の同一ハッシュも再処理。未登録・ハッシュ変更は日付に関係なく対象")
    ap.add_argument("--all", action="store_true", help="全件を強制 NEW (mode:full・schema変更後の全再構築)")
    ap.add_argument("--dry-run", action="store_true", help="検知のみ。互換フラグとして受理し、このスクリプト自体は常に書き込まない")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        # --help は argparse が SystemExit(0) を投げる。2 に潰すと「usage は出たのに異常終了」になる。
        return 0 if exc.code == 0 else 2

    if args.since:
        try:
            if datetime.strptime(args.since, "%Y-%m-%d").strftime("%Y-%m-%d") != args.since:
                raise ValueError("YYYY-MM-DD の形式ではありません")
        except ValueError:
            print("エラー: --since は実在する日付 YYYY-MM-DD で指定してください", file=sys.stderr)
            return 1

    registry_file = Path(args.registry)
    sources = Path(args.sources)

    # L2 raw vault は任意接続。未接続の個人環境では capability B を0件正常終了に縮退させる。
    if not sources.is_dir():
        print_empty_result(sources.name or "(missing)", f"  [未接続] sources ディレクトリが見つかりません: {sources}")
        return 0
    if not args.all and not registry_file.is_file():
        print(f"エラー: registry ファイルが見つかりません: {registry_file}", file=sys.stderr)
        return 1

    try:
        registry = {} if args.all else load_registry(registry_file)
    except RegistryError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1

    # registry キー再構成用 prefix = --sources 末尾2成分 (05_Project/UBM)
    parts = sources.resolve().parts
    prefix = "/".join(parts[-2:]) if len(parts) >= 2 else sources.name

    print("=== UBMナレッジ更新検知 ===")
    if args.dry_run:
        print("mode: dry-run (検知のみ・書込なし)")
        print("")
    else:
        print("")
    excluded_label = "・".join(f"{name}/" for name in EXCLUDED_SUBDIRS)
    print(f"--- ディレクトリスキャン ({prefix}/ 配下を全検索。{excluded_label} は除く) ---")

    new_files: list[tuple[str, str, str]] = []       # (registry_key, source_type, hash)
    modified_files: list[tuple[str, str, str]] = []
    total_scanned = 0
    total_excluded = 0

    for md in sorted(sources.rglob("*.md")):
        # `x.md` という名前のディレクトリや壊れたリンクはソースではない。
        if not md.is_file():
            continue
        rel_path = md.relative_to(sources)
        if is_excluded(rel_path.parts):
            total_excluded += 1
            continue
        total_scanned += 1
        rel = rel_path.as_posix()
        registry_key = f"{prefix}/{rel}"
        try:
            current_hash = md5_of(md)
            mod_date = datetime.fromtimestamp(md.stat().st_mtime).strftime("%Y-%m-%d")
        except OSError as exc:
            print(f"エラー: ソースを読めません: {md}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        source_type = get_source_type(registry_key)

        if args.all:
            print(f"  [全件] {registry_key} ({source_type})")
            new_files.append((registry_key, source_type, current_hash))
            continue

        if registry_key not in registry:
            print(f"  [新規] {registry_key} ({source_type})")
            new_files.append((registry_key, source_type, current_hash))
        elif registry[registry_key] != current_hash:
            print(f"  [更新] {registry_key} (ハッシュ変更: {registry[registry_key][:8]}... → {current_hash[:8]}...)")
            modified_files.append((registry_key, source_type, current_hash))
        elif args.since and mod_date > args.since:
            print(f"  [更新] {registry_key} ({mod_date} > {args.since})")
            modified_files.append((registry_key, source_type, current_hash))

    total_target = len(new_files) + len(modified_files)
    print("")
    print("=== 検知結果 ===")
    print(f"スキャン: {total_scanned} 件")
    print(f"除外: {total_excluded} 件 ({excluded_label})")
    print(f"新規: {len(new_files)} 件")
    print(f"更新: {len(modified_files)} 件")
    print(f"処理対象合計: {total_target} 件")

    if total_target > 0:
        print("")
        print("--- 処理対象ファイル一覧（knowledge-extractor 入力用） ---")
        for key, stype, h in new_files:
            print(f"NEW|{stype}|{h}|{key}")
        for key, stype, h in modified_files:
            print(f"MODIFIED|{stype}|{h}|{key}")
    else:
        print("")
        print("全ファイル処理済み。更新はありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

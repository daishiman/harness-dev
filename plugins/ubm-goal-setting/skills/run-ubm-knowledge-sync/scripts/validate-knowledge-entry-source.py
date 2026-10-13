#!/usr/bin/env python3
# /// script
# name: validate-knowledge-entry-source
# version: 0.1.1
# purpose: knowledge/ のカテゴリ JSON の各エントリについて、source が file と type を持つ単一の object で、
#          type が schema.json の source.type の enum に入るかを検査する決定論ゲート。knowledge-extractor が
#          一時 knowledge_dir へエントリを格納したあと、router/sync-log/registry を確定する前に実行する。
#          enum と必須キーの正本は同じ knowledge_dir の schema.json で、この script は値を持たない。
# inputs:
#   - argv: --knowledge-dir DIR (絶対パスだけを受ける)
#   - file: DIR/schema.json (knowledge_entry_schema の source の required と type の enum)
#   - file: DIR/*.json のうち entries[] を持つカテゴリファイル
# outputs:
#   - stdout: 検査したカテゴリファイル数・エントリ数と OK
#   - stderr: 読めないファイルの一覧と、契約から外れたエントリの一覧 (file#entries[id=...].source.<key> と値) を別の見出しで
#   - exit: 0=OK・--help / 1=外れたエントリあり・JSON を読めない・schema に enum が無い・カテゴリが0件
#           2=usage (引数の誤り・DIR が空文字か相対パス・ディレクトリが無い)
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""ナレッジエントリの source の形と source.type の enum を検査する (knowledge-extractor の格納後ゲート)。

schema.json の source は file と type を必須にした単一の object で、type は enum の値に限る。
エントリのテンプレート・検知のラベル・agent の書き方のどれかがずれても、外れた値をここで止める。
カテゴリが1つも無いときは、検査していないのに通ったことにならないよう 1 で止める。
--knowledge-dir は絶対パスだけを受ける。空文字や相対パスは cwd で解決されるので、KNOWLEDGE_DIR が
未設定のまま呼ぶと一時コピーではなく正式先の knowledge/ を検査して 0 を返しうる。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValueError(f"{path.name}: JSON を読めない ({exc})") from exc


def source_contract(schema: object) -> tuple[list[str], set[str]]:
    """schema.json から source の必須キーと source.type の enum を取り出す。"""
    try:
        source = schema["knowledge_entry_schema"]["properties"]["entries"]["items"]["properties"]["source"]
        required = source["required"]
        enum = source["properties"]["type"]["enum"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"schema.json に source の required か type の enum が無い ({exc!r})") from exc
    if not (isinstance(required, list) and all(isinstance(k, str) for k in required)
            and isinstance(enum, list) and enum and all(isinstance(v, str) for v in enum)):
        raise ValueError("schema.json の source の required か type の enum の形が違う")
    return required, set(enum)


def check_entries(path: Path, entries: list, required: list[str], enum: set[str]) -> list[str]:
    violations: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            violations.append(f"{path.name}#entries[{index}]: エントリが object でない")
            continue
        entry_id = entry.get("id")
        where = f"{path.name}#entries[id={entry_id}]" if isinstance(entry_id, str) else f"{path.name}#entries[{index}]"
        if "source" not in entry:
            violations.append(f"{where}: source が無い")
            continue
        source = entry["source"]
        if not isinstance(source, dict):
            violations.append(f"{where}.source: 単一の object でない ({type(source).__name__})")
            continue
        violations += [f"{where}.source.{key}: 必須なのに無い" for key in required if key not in source]
        file_value = source.get("file")
        if "file" in source and not (isinstance(file_value, str) and file_value.strip()):
            violations.append(f"{where}.source.file: 空でない文字列でない ({file_value!r})")
        type_value = source.get("type")
        if "type" in source and not (isinstance(type_value, str) and type_value in enum):
            violations.append(f"{where}.source.type: enum に無い値 ({type_value!r})")
    return violations


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="ナレッジエントリの source の形と source.type の enum を検査する決定論ゲート",
        add_help=True,
    )
    ap.add_argument("--knowledge-dir", required=True, help="schema.json とカテゴリ JSON を含む knowledge/ ディレクトリの絶対パス")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    if not args.knowledge_dir.strip():
        print("ERROR: --knowledge-dir が空文字 (KNOWLEDGE_DIR が未設定のまま呼んでいないか確かめる)", file=sys.stderr)
        return 2
    kdir = Path(args.knowledge_dir)
    if not kdir.is_absolute():
        print(f"ERROR: --knowledge-dir は絶対パスで渡す (相対パスは cwd で解決される): {args.knowledge_dir}",
              file=sys.stderr)
        return 2
    if not kdir.is_dir():
        print(f"ERROR: ディレクトリが見つかりません: {kdir}", file=sys.stderr)
        return 2
    try:
        required, enum = source_contract(load_json(kdir / "schema.json"))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    violations: list[str] = []
    unreadable: list[str] = []
    files = entries = 0
    for path in sorted(kdir.glob("*.json")):
        if path.name == "schema.json":
            continue
        try:
            data = load_json(path)
        except ValueError as exc:
            unreadable.append(str(exc))
            continue
        if not (isinstance(data, dict) and isinstance(data.get("entries"), list)):
            continue  # router/registry/graph など、エントリを持たない管理・生成ファイル
        files += 1
        entries += len(data["entries"])
        violations += check_entries(path, data["entries"], required, enum)

    # 読めないファイルは中のエントリを検査できていないので、契約の外れとは別の見出しで数える
    if unreadable:
        print(f"NG: 読めないファイルが {len(unreadable)} 件ある（中のエントリは検査していない）", file=sys.stderr)
        for message in unreadable:
            print(f"  - {message}", file=sys.stderr)
    if violations:
        print(f"NG: source の契約から外れた箇所が {len(violations)} 件ある"
              f"（source.type の enum: {', '.join(sorted(enum))}）", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
    if unreadable or violations:
        return 1
    if files == 0:
        print(f"ERROR: entries[] を持つカテゴリファイルが {kdir} に1つも無い", file=sys.stderr)
        return 1
    print(f"OK: カテゴリ {files} ファイル・{entries} エントリの source が schema.json の契約に合う")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
# /// script
# name: lint-ssot-duplication
# purpose: プラグイン内の SSOT (単一情報源) 違反・重複・冗長を事前解析する。改善前の「全プラグイン重複解析→変更対象特定」を再現性高く機械実行するための lint。
# inputs:
#   - argv: --plugin-dir <dir> | <file>...
#   - flags: --strict (smell も exit 1 にする)
# outputs:
#   - stdout: OK status / 重複候補レポート
#   - stderr: ERROR (契約矛盾) / WARN (smell) の findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""harness-creator が「上書き更新で一本化」する前段の重複解析を機械化する lint。

検出ルール (run-elegant-review C1/C2 クラスタ・references/goal-seek-paradigm.md の SSOT 思想):
  ERROR (常に exit 1):
    - DUP-SCHEMA-ID: 同一 `$id` を持つ JSON schema が 2 ファイル以上 (どちらが正本か曖昧)。
  WARN (--strict 時のみ exit 1):
    - REDIRECT-FAT-BODY: `x-canonical-redirect` を宣言しながら自前 `properties` を再掲 (正本の本文コピー)。
    - DUP-REQUIRED-SET: redirect でない schema が同一の `required` 集合を持つ (同一成果物の二重定義疑い)。
    - DUP-PASSAGE: 同一の連続本文パッセージ (既定 6 行窓) が 2 ファイル以上に点在 (正本へ参照化すべき再掲)。

「両方残す」を防ぎ「正本 1 つ + 参照」へ寄せる判断材料を出すのが目的。Exit 0 = ok, 1 = violation, 2 = usage error。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

WINDOW = 6  # DUP-PASSAGE の連続行窓
MIN_LINE_LEN = 20  # 窓に含める「実質的」行の最小文字数 (定型・短文ノイズ除外)
# 参照宣言行や定型句は重複判定から除外する。
PASSAGE_IGNORE_RE = re.compile(r"(正本|canonical|詳細は|参照|references/|schemas/|SSOT)")


def parse_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def body_after_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :]
    return text


# ---- schema 系チェック -------------------------------------------------

def check_schemas(schemas: list[Path]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    by_id: dict[str, list[Path]] = defaultdict(list)
    by_required: dict[str, list[Path]] = defaultdict(list)

    for path in schemas:
        obj = parse_json(path)
        if not isinstance(obj, dict):
            continue
        is_redirect = "x-canonical-redirect" in obj
        sid = obj.get("$id")
        if sid and not is_redirect:
            by_id[sid].append(path)
        # REDIRECT-FAT-BODY: redirect 宣言なのに properties を再掲
        if is_redirect:
            props = obj.get("properties")
            if isinstance(props, dict) and len(props) > 0:
                warns.append(
                    f"REDIRECT-FAT-BODY {path}: x-canonical-redirect 宣言だが properties を "
                    f"{len(props)} 件再掲。$ref のみの薄いリダイレクトに縮約し正本へ一本化すること"
                )
        # DUP-REQUIRED-SET: 同一 required 集合 (redirect 除く)。
        # 汎用的な小集合 ([input,output] 等) は偶然一致が多いので 4 キー以上のみ対象。
        req = obj.get("required")
        if isinstance(req, list) and len(req) >= 4 and not is_redirect:
            key = ",".join(sorted(map(str, req)))
            by_required[key].append(path)

    for sid, paths in by_id.items():
        if len(paths) > 1:
            errors.append(
                f"DUP-SCHEMA-ID '{sid}': 同一 $id が {len(paths)} ファイルに存在 "
                f"({', '.join(str(p) for p in paths)})。正本 1 つに統合し他は redirect 化すること"
            )
    for key, paths in by_required.items():
        if len(paths) > 1:
            warns.append(
                f"DUP-REQUIRED-SET [{key}]: 同一 required 集合の schema が "
                f"{len(paths)} 件 ({', '.join(str(p) for p in paths)})。同一成果物の二重定義の疑い"
            )
    return errors, warns


# ---- markdown 本文の重複パッセージ -------------------------------------

def substantial_lines(md_text: str) -> list[str]:
    out: list[str] = []
    for raw in body_after_frontmatter(md_text).splitlines():
        s = raw.strip()
        if len(s) < MIN_LINE_LEN:
            continue
        if PASSAGE_IGNORE_RE.search(s):
            continue
        out.append(re.sub(r"\s+", " ", s))
    return out


def check_passages(md_files: list[Path]) -> list[str]:
    # templates/ 配下は「生成物に焼き込む唯一の実体コピー」= 伝搬例外
    # (goal-seek-paradigm.md「コンテキスト分離」節の伝搬例外)。テンプレ間の意図的重複は対象外にする。
    md_files = [p for p in md_files if "templates" not in p.parts]
    # 窓ハッシュ -> {file: 代表行}
    window_owners: dict[str, dict[Path, str]] = defaultdict(dict)
    for path in md_files:
        try:
            lines = substantial_lines(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        for i in range(len(lines) - WINDOW + 1):
            window = lines[i : i + WINDOW]
            h = hashlib.sha1("\n".join(window).encode("utf-8")).hexdigest()
            window_owners[h].setdefault(path, window[0])

    warns: list[str] = []
    seen: set[frozenset[Path]] = set()
    for h, owners in window_owners.items():
        if len(owners) > 1:
            fileset = frozenset(owners)
            if fileset in seen:
                continue
            seen.add(fileset)
            sample = next(iter(owners.values()))
            warns.append(
                f"DUP-PASSAGE: 同一の {WINDOW} 行パッセージが {len(owners)} ファイルに点在 "
                f"({', '.join(str(p) for p in owners)})。例: \"{sample[:50]}...\"。"
                "正本 1 箇所に置き他は参照化すること"
            )
    return warns


# ---- 収集 / main -------------------------------------------------------

def collect(argv: list[str]) -> tuple[list[Path], bool]:
    strict = "--strict" in argv
    argv = [a for a in argv if a != "--strict"]
    if argv and argv[0] == "--plugin-dir":
        if len(argv) < 2:
            return [], strict
        d = Path(argv[1])
        if not d.is_dir():
            return [], strict
        files = sorted(p for p in d.glob("**/*") if p.suffix in (".md", ".json"))
        return files, strict
    return [Path(p) for p in argv], strict


def main(argv: list[str]) -> int:
    files, strict = collect(argv)
    if not files:
        sys.stderr.write(
            "usage: lint-ssot-duplication.py --plugin-dir <dir> [--strict] | <file>... [--strict]\n"
        )
        return 2

    schemas = [p for p in files if p.suffix == ".json"]
    md_files = [p for p in files if p.suffix == ".md"]

    errors, warns = check_schemas(schemas)
    warns += check_passages(md_files)

    for e in errors:
        sys.stderr.write("ERROR " + e + "\n")
    for w in warns:
        sys.stderr.write("WARN  " + w + "\n")

    if errors or (strict and warns):
        return 1

    summary = f"OK: SSOT 重複チェック通過 (schemas={len(schemas)}, md={len(md_files)}"
    if warns:
        summary += f", warnings={len(warns)} 件は smell。--strict で fail 化"
    summary += ")\n"
    sys.stdout.write(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

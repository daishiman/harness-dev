#!/usr/bin/env python3
# /// script
# name: validate-knowledge-cards
# version: 0.1.0
# purpose: C04 の deep knowledge card 深度・catalog parity・open-world 契約を検証する決定論ゲート (要件 C11)。pointer-only の浅いカードを拒否し、実体ある本文・一次資料 locator・鮮度データ・seed/open-world 宣言を要求する。
# inputs:
#   - argv: [--root DIR]   # 既定 = 本 skill root (references/ を配下に持つ)
# outputs:
#   - stdout: OK summary
#   - stderr: violation 一覧
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""C04 deep-card depth, catalog parity, open-world contract validator.

Read-only and stdlib-only. It rejects pointer-only cards even when headings exist by
requiring substantive bodies, explicit primary-source locators, and freshness data.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = (
    "目的",
    "背景",
    "解決する問題",
    "中核概念",
    "適用条件",
    "非適用条件",
    "トレードオフ・失敗モード",
    "目的達成への寄与",
    "一次資料",
    "鮮度",
)
MIN_BODY_CHARS = 45
PLACEHOLDER = re.compile(r"^(?:なし|特になし|適宜|要検討|tbd|todo|n/?a|[-ー―\s]+)$", re.I)


def sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.M))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1).strip()] = text[match.end() : end].strip()
    return result


def validate_card(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    found = sections(text)
    errors: list[str] = []
    if "status: `seed-example`" not in text and "status: `curated`" not in text:
        errors.append(f"{path.name}: status marker missing")
    for name in REQUIRED_SECTIONS:
        body = found.get(name, "")
        if not body:
            errors.append(f"{path.name}: missing section {name}")
        elif len(re.sub(r"[`#*|>-]", "", body).strip()) < MIN_BODY_CHARS:
            errors.append(f"{path.name}: shallow section {name}")
        elif PLACEHOLDER.fullmatch(body.strip()):
            errors.append(f"{path.name}: placeholder section {name}")
    source = found.get("一次資料", "")
    if "http://" not in source and "https://" not in source:
        errors.append(f"{path.name}: primary source locator URL missing")
    fresh = found.get("鮮度", "")
    for token in ("class:", "last_checked:", "review_by:", "trigger:"):
        if token not in fresh:
            errors.append(f"{path.name}: freshness token missing: {token}")
    return errors


def validate_root(root: Path) -> list[str]:
    refs = root / "references"
    catalog = json.loads((refs / "knowledge-catalog.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    if catalog.get("open_world") is not True:
        errors.append("knowledge-catalog.json: open_world must be true")
    if "not an exhaustive" not in str(catalog.get("catalog_semantics", "")):
        errors.append("knowledge-catalog.json: non-exhaustive seed semantics missing")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or not entries:
        return errors + ["knowledge-catalog.json: entries missing"]
    ids: set[str] = set()
    for entry in entries:
        kid = entry.get("knowledge_id")
        filename = entry.get("file")
        if not kid or kid in ids:
            errors.append(f"knowledge-catalog.json: missing/duplicate knowledge_id {kid!r}")
        ids.add(kid)
        path = refs / str(filename)
        if not path.is_file():
            errors.append(f"knowledge-catalog.json: missing card {filename!r}")
        else:
            errors.extend(validate_card(path))
    lifecycle = (refs / "open-world-knowledge-lifecycle.md").read_text(encoding="utf-8")
    for stage in ("Discover", "Qualify", "Deepen", "Goal map", "Project candidate", "Curated promotion", "Freshness audit"):
        if stage not in lifecycle:
            errors.append(f"open-world lifecycle: missing stage {stage}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    try:
        errors = validate_root(args.root)
    except OSError as exc:
        print(f"入力ファイル読取失敗: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"knowledge-catalog.json の JSON parse 失敗: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("OK deep knowledge cards, catalog parity, open-world lifecycle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


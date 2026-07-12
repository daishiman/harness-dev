#!/usr/bin/env python3
# /// script
# name: lint-reference-attribution
# purpose: skill 私有 references/ の帰属完全性 (resource-map.yaml が全 reference を
#          列挙し、列挙先が実在する) を機械検証する。lint-skill-tree 第13条の
#          「resource-map.yaml 存在」検査を「内容の完全性 (orphan/dangling 0)」へ拡張する。
# inputs:
#   - argv: plugin directory (default: この script の 2 つ上 = plugin root) or --plugin-dir <dir>
# outputs:
#   - stdout: OK status
#   - stderr: attribution findings
# contexts: [C, E]
# network: false
# write-scope: none
# requires-python: ">=3.10"
# ///
"""skill 私有 references/ の帰属 (attribution) 完全性ゲート。

thin-adapter agent から昇格した手続き知識 reference が、所有 skill の
references/resource-map.yaml に漏れなく登録され (orphan 0)、かつ resource-map の
各エントリが実在ファイルを指す (dangling 0) ことを保証する。

judged 原則:
  - references/ が 3 ファイル以上ある skill は resource-map.yaml を持つ (lint-skill-tree 第13条)。
  - resource-map.yaml の `read_when[].file` / `run_scripts[].file` (skill dir 相対) の集合が、
    references/ 直下の全 reference (*.md / *.json、resource-map.yaml 自身を除く) を包含する。
  - 逆に列挙された file は全て実在する (skill dir 相対で解決)。

exit 0 = ok, 1 = 帰属欠落/dangling あり, 2 = usage error。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml  # PyYAML 6.x (repo で利用可能・feedback_contract_ssot.py 等でも使用)

    _HAVE_YAML = True
except ImportError:  # pragma: no cover - フォールバック
    _HAVE_YAML = False

REF_SUFFIXES = {".md", ".json"}
_FILE_RE = re.compile(r"^\s*-?\s*file:\s*(.+?)\s*$")


def _map_files(rmap_path: Path) -> set[str]:
    """resource-map.yaml が列挙する file 値の集合を返す (skill dir 相対の原文字列)。"""
    text = rmap_path.read_text(encoding="utf-8")
    if _HAVE_YAML:
        data = yaml.safe_load(text) or {}
        files: set[str] = set()
        for key in ("read_when", "run_scripts"):
            for item in data.get(key, []) or []:
                if isinstance(item, dict) and item.get("file"):
                    files.add(str(item["file"]).strip())
        # 追加: attribution 形式 (references: [{path: ...}]) も許容
        for item in data.get("references", []) or []:
            if isinstance(item, dict) and (item.get("path") or item.get("file")):
                files.add(str(item.get("path") or item.get("file")).strip())
        return files
    # フォールバック: `file: <path>` 行を正規表現で拾う
    return {m.group(1).strip() for line in text.splitlines() if (m := _FILE_RE.match(line))}


def lint_skill(skill_dir: Path) -> list[str]:
    refs_dir = skill_dir / "references"
    if not refs_dir.is_dir():
        return []
    ref_files = [
        f
        for f in sorted(refs_dir.iterdir())
        if f.is_file() and f.suffix in REF_SUFFIXES and f.name != "resource-map.yaml"
    ]
    # lint-skill-tree 第13条: 3 ファイル未満は resource-map.yaml 不要 (本 lint も対象外)
    if len(ref_files) < 3:
        return []
    rmap = refs_dir / "resource-map.yaml"
    if not rmap.exists():
        return [
            f"{skill_dir.name}: references/ が {len(ref_files)} 件 (>=3) だが"
            " resource-map.yaml が不在 (lint-skill-tree 第13条)"
        ]
    listed = _map_files(rmap)
    # skill dir 相対に正規化した listed の basename と full 相対の両方で照合
    listed_norm = {p.lstrip("./") for p in listed}
    findings: list[str] = []
    # orphan: references/ 実体が resource-map に未登録
    for f in ref_files:
        rel = f"references/{f.name}"
        if rel not in listed_norm and f.name not in {Path(p).name for p in listed_norm}:
            findings.append(
                f"{skill_dir.name}: reference 'references/{f.name}' が"
                " resource-map.yaml に未登録 (orphan・帰属欠落)"
            )
    # dangling: 列挙された skill-local file が実在しない (../../ 共有正本は skill dir 相対で解決)
    for p in sorted(listed):
        target = (skill_dir / p).resolve()
        if not target.exists():
            findings.append(
                f"{skill_dir.name}: resource-map.yaml の file '{p}' が実在しない (dangling)"
            )
    return findings


def find_skills_dir(plugin_dir: Path) -> Path | None:
    d = plugin_dir / "skills"
    return d if d.is_dir() else None


def main() -> int:
    args = sys.argv[1:]
    if "--plugin-dir" in args:
        idx = args.index("--plugin-dir")
        if idx + 1 >= len(args):
            print("usage: lint-reference-attribution.py --plugin-dir <dir>", file=sys.stderr)
            return 2
        plugin_dir = Path(args[idx + 1])
    elif args:
        plugin_dir = Path(args[0])
    else:
        # 既定: この script の 2 つ上 = plugin root
        plugin_dir = Path(__file__).resolve().parent.parent
    if not plugin_dir.is_dir():
        print(f"not a directory: {plugin_dir}", file=sys.stderr)
        return 2
    skills_dir = find_skills_dir(plugin_dir)
    if skills_dir is None:
        print(f"no skills/ under {plugin_dir}", file=sys.stderr)
        return 2
    total: list[str] = []
    n = 0
    for d in sorted(skills_dir.iterdir()):
        if d.is_dir():
            n += 1
            total.extend(lint_skill(d))
    if total:
        for e in total:
            print(e, file=sys.stderr)
        return 1
    print(f"ok: {plugin_dir.name} ({n} skills, reference attribution)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

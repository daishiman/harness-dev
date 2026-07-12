#!/usr/bin/env python3
# /// script
# name: lint-knowledge-layout
# purpose: knowledge/ と lessons-learned/ の SSOT 役割分担 (JSON ストア vs 散文ログ) を機械強制する。
# inputs:
#   - --plugins-dir: plugins ルート (既定 plugins)
#   - --json: 機械可読 JSON で結果を出す
# outputs:
#   - stdout: 違反レポート。違反ありで exit 1・なしで exit 0
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""knowledge/ ↔ lessons-learned/ の形式規約を fail-closed 検査する。

正本規約 (plugins/harness-creator/knowledge/README.md + lessons-learned/README.md):
  K1. knowledge/ には蒸留済み JSON/JSONL ストアと README.md のみ置く。
      散文の失敗ログ (.md) は lessons-learned/ が正本 (knowledge には source.file で参照)。
  K2. knowledge-lessons-index.json の各 items[].source.file は実在しなければならない
      (索引は本文をコピーせず参照のみ = dangling 参照禁止)。
  L1. lessons-learned/*.md は `YYYY-MM-DD-<slug>.md` 命名 (README.md は除く)。
  L2. lessons-learned/*.md は frontmatter に date: を持つ (dogfooding-metrics が参照)。
  L3. 必須セクションは lesson 種別ごとに検証する:
      - 人手記述 (既定): `## 背景` / `## 知見` / `## 適用先` (lessons-learned/README.md 正本)。
      - 自動記録 (frontmatter に trigger_event: を持つ = auto-record-lesson.py 生成):
        `## observation` / `## hypothesis` / `## proposed_action` (生成器の出力契約)。
  L4. lessons-learned/*.md 本文は 30 行以下 (掘り下げは設計書本体へ昇格)。

背景: 2026-07-11 に散文レッスンを knowledge/ 直下へ .md で直接置いてしまい (JSON ストアと混在)、
2 場所の役割分担が崩れた。宣言 (README) のみでは再発するため機械層で封じる。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# knowledge/ に置いてよいファイル (K1)。それ以外の .md = 散文混入で違反。
_KNOWLEDGE_ALLOWED_SUFFIXES = {".json", ".jsonl"}
_KNOWLEDGE_ALLOWED_NAMES = {"README.md"}

_LESSON_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_DATE_RE = re.compile(r"^date\s*:\s*", re.MULTILINE)
_TRIGGER_EVENT_RE = re.compile(r"^trigger_event\s*:\s*", re.MULTILINE)
# 人手記述レッスン (lessons-learned/README.md 正本) の必須セクション。
_SECTIONS_HUMAN = ("## 背景", "## 知見", "## 適用先")
# 自動記録レッスン (auto-record-lesson.py 生成) の必須セクション = 生成器の出力契約。
_SECTIONS_AUTO = ("## observation", "## hypothesis", "## proposed_action")
_LESSON_BODY_MAX_LINES = 30


def _iter_dirs(plugins_dir: Path, leaf: str):
    for d in sorted(plugins_dir.glob(f"*/{leaf}")):
        if d.is_dir():
            yield d


def check_knowledge_hygiene(plugins_dir: Path) -> list[dict]:
    """K1: knowledge/ 直下に JSON/JSONL/README 以外 (=散文 .md 等) がないか。"""
    violations: list[dict] = []
    for kdir in _iter_dirs(plugins_dir, "knowledge"):
        for f in sorted(kdir.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            if f.name in _KNOWLEDGE_ALLOWED_NAMES:
                continue
            if f.suffix in _KNOWLEDGE_ALLOWED_SUFFIXES:
                continue
            hint = (" → lessons-learned/ へ移す (散文ログの正本)"
                    if f.suffix == ".md" else "")
            violations.append({
                "rule": "K1", "file": str(f),
                "detail": f"knowledge/ 直下は JSON/JSONL/README.md のみ許可。'{f.name}' は不可{hint}",
            })
    return violations


def check_lessons_index_refs(plugins_dir: Path) -> list[dict]:
    """K2: knowledge-lessons-index.json の source.file が全て実在するか。"""
    violations: list[dict] = []
    repo_root = plugins_dir.parent
    for kdir in _iter_dirs(plugins_dir, "knowledge"):
        idx = kdir / "knowledge-lessons-index.json"
        if not idx.is_file():
            continue
        try:
            data = json.loads(idx.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            violations.append({"rule": "K2", "file": str(idx),
                               "detail": f"parse 不能: {exc}"})
            continue
        for item in data.get("items", []):
            ref = (item.get("source") or {}).get("file")
            if not ref:
                continue
            target = repo_root / ref
            if not target.is_file():
                violations.append({
                    "rule": "K2", "file": str(idx),
                    "detail": f"items[id={item.get('id')}].source.file が実在しない: {ref}",
                })
    return violations


def check_lesson_format(plugins_dir: Path) -> list[dict]:
    """L1-L4: lessons-learned/*.md の命名・frontmatter・必須セクション・行数。"""
    violations: list[dict] = []
    for ldir in _iter_dirs(plugins_dir, "lessons-learned"):
        for f in sorted(ldir.glob("*.md")):
            if f.name == "README.md":
                continue
            if not _LESSON_NAME_RE.match(f.name):
                violations.append({"rule": "L1", "file": str(f),
                                   "detail": "命名は YYYY-MM-DD-<kebab-slug>.md"})
            text = f.read_text(encoding="utf-8")
            fm = _FRONTMATTER_RE.match(text)
            fm_body = fm.group(1) if fm else ""
            if not fm or not _DATE_RE.search(fm_body):
                violations.append({"rule": "L2", "file": str(f),
                                   "detail": "frontmatter に date: が必要"})
            # lesson 種別で必須セクションを分岐 (auto-record 生成物を人手形式へ誤強制しない)。
            is_auto = bool(fm and _TRIGGER_EVENT_RE.search(fm_body))
            required = _SECTIONS_AUTO if is_auto else _SECTIONS_HUMAN
            kind = "自動記録" if is_auto else "人手記述"
            missing = [s for s in required if s not in text]
            if missing:
                violations.append({"rule": "L3", "file": str(f),
                                   "detail": f"必須セクション欠落 ({kind}): {', '.join(missing)}"})
            body = text[fm.end():] if fm else text
            body_lines = [ln for ln in body.splitlines() if ln.strip()]
            if len(body_lines) > _LESSON_BODY_MAX_LINES:
                violations.append({
                    "rule": "L4", "file": str(f),
                    "detail": f"本文 {len(body_lines)} 行 > 上限 {_LESSON_BODY_MAX_LINES} 行 (設計書へ昇格)",
                })
    return violations


def run(plugins_dir: Path) -> list[dict]:
    return (check_knowledge_hygiene(plugins_dir)
            + check_lessons_index_refs(plugins_dir)
            + check_lesson_format(plugins_dir))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lint-knowledge-layout.py")
    p.add_argument("--plugins-dir", default="plugins")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    plugins_dir = Path(args.plugins_dir)
    if not plugins_dir.is_dir():
        print(f"plugins dir がない: {plugins_dir}", file=sys.stderr)
        return 2
    violations = run(plugins_dir)

    if args.json:
        print(json.dumps({"violations": violations, "ok": not violations},
                         ensure_ascii=False, indent=2))
    else:
        if not violations:
            print("lint-knowledge-layout: OK (knowledge/ ↔ lessons-learned/ 規約準拠)")
        else:
            print(f"lint-knowledge-layout: {len(violations)} 件の違反")
            for v in violations:
                print(f"  [{v['rule']}] {v['file']}\n        {v['detail']}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())

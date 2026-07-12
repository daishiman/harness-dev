#!/usr/bin/env python3
# /// script
# name: re-evaluate-on-rubric-bump
# purpose: List skills that require re-evaluation after a rubric major bump.
# inputs:
#   - argv: no required arguments
# outputs:
#   - stdout: re-evaluation target list
#   - stderr: best-effort parsing warnings
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""re-evaluate-on-rubric-bump.py — major bump 時の再評価対象リストアップ.

現 rubric_version（upstream = ref-skill-design-rubric/rubric.json）と
eval-log/ 配下の過去評価ログに記録された rubric_version を比較し、
**major bump** が発生している場合に再評価が必要なスキル一覧を列挙する。

挙動:
  - 実行はせず、対象リストを stdout に出力するのみ（常に exit 0）。
  - 該当無し（major bump 無し / eval-log 空）の場合も exit 0。
  - eval-log/*.json から下記フィールドを best-effort に拾う:
      * rubric_version (もしくは current_version / target_version)
      * 対象スキル: skill_name / target_skill / proposer / proposal_id
  - JSONL (.jsonl) もサポート。

stdlib only / Python 3.9+.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]  # scripts/ 直下なので repo root は parents[1]
UPSTREAM_RUBRIC = (
    REPO_ROOT / "plugins" / "harness-creator" / "skills" / "ref-skill-design-rubric"
    / "references" / "rubric.json"
)
EVAL_LOG_DIR = REPO_ROOT / "eval-log"

VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def parse_semver(s: str | None) -> tuple[int, int, int] | None:
    """Extract the first semver-like (X.Y.Z) triple from a string."""
    if not s:
        return None
    m = VERSION_RE.search(str(s))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def iter_records(path: Path) -> Iterable[dict]:
    """Yield JSON records from .json (object or array) and .jsonl files."""
    try:
        if path.suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(rec, dict):
                        yield rec
        else:
            with path.open("r", encoding="utf-8") as f:
                doc = json.load(f)
            if isinstance(doc, list):
                for rec in doc:
                    if isinstance(rec, dict):
                        yield rec
            elif isinstance(doc, dict):
                yield doc
    except (OSError, json.JSONDecodeError):
        return


def extract_version(rec: dict) -> tuple[int, int, int] | None:
    for key in ("rubric_version", "current_version", "target_version", "version"):
        v = parse_semver(rec.get(key))
        if v is not None:
            return v
    return None


def extract_skill_identity(rec: dict, source: Path) -> str:
    for key in (
        "skill_name",
        "target_skill",
        "skill",
        "proposal_id",
        "proposer",
    ):
        if rec.get(key):
            return f"{rec[key]} (from {source.name})"
    return f"<unknown> (from {source.name})"


def main() -> int:
    if not UPSTREAM_RUBRIC.exists():
        print(f"# upstream rubric not found: {UPSTREAM_RUBRIC}", file=sys.stderr)
        return 0

    with UPSTREAM_RUBRIC.open("r", encoding="utf-8") as f:
        upstream = json.load(f)
    current = parse_semver(upstream.get("rubric_version"))
    if current is None:
        print(
            f"# could not parse upstream rubric_version "
            f"({upstream.get('rubric_version')!r}); aborting",
            file=sys.stderr,
        )
        return 0

    if not EVAL_LOG_DIR.exists():
        print(f"# no eval-log directory at {EVAL_LOG_DIR}; nothing to do")
        return 0

    targets: list[tuple[str, tuple[int, int, int]]] = []
    log_files = sorted(
        [p for p in EVAL_LOG_DIR.iterdir() if p.suffix in (".json", ".jsonl")]
    )
    if not log_files:
        print("# eval-log/ is empty; nothing to re-evaluate")
        return 0

    for path in log_files:
        for rec in iter_records(path):
            past = extract_version(rec)
            if past is None:
                continue
            # major bump = upstream major > past major
            if current[0] > past[0]:
                ident = extract_skill_identity(rec, path)
                past_str = ".".join(map(str, past))
                targets.append((ident, past))

    current_str = ".".join(map(str, current))
    print(f"# upstream rubric_version: {current_str}")
    print(f"# eval-log files scanned: {len(log_files)}")
    print(f"# re-evaluation targets (major bump detected): {len(targets)}")
    print("")
    if not targets:
        print("# no major bump detected against any logged evaluation. OK.")
        return 0

    print("# target list (skill / past_version -> current_version):")
    for ident, past in targets:
        past_str = ".".join(map(str, past))
        print(f"- {ident}\tpast={past_str}\tcurrent={current_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

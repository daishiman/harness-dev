#!/usr/bin/env python3
# /// script
# name: re-evaluate-on-rubric-bump
# purpose: List skills that require re-evaluation after a rubric major bump.
# inputs:
#   - argv: --rubric PATH (optional), --eval-log-dir PATH (optional)
# outputs:
#   - stdout: re-evaluation target list
#   - stderr: missing or unreadable upstream rubric
# contexts: [E]
# network: false
# write-scope: none
# dependencies: [extract-plugin-root.py]
# ///
"""re-evaluate-on-rubric-bump.py — major bump 時の再評価対象リストアップ.

現 rubric_version（upstream = 兄弟 plugin harness-creator の
skills/ref-skill-design-rubric/references/rubric.json）と eval-log/ 直下の
過去評価ログに記録された rubric_version を比較し、**major bump** が発生して
いる場合に再評価が必要なスキル一覧を列挙する。

挙動:
  - 実行はせず、対象リストを stdout に出力するのみ。
  - upstream rubric は同梱の scripts/extract-plugin-root.py で harness-creator の
    root を解決して読む（install 先では親ディレクトリ経由で兄弟に届かないため）。
    ``--rubric`` で明示もできる。
  - eval-log は consumer の作業ディレクトリの ``eval-log/``（``--eval-log-dir`` で明示可）。
  - exit 0: 走査できた（対象あり / 無し / eval-log 不在・空を含む）。
  - exit 2: upstream rubric が見つからない・読めない・rubric_version を解釈できない。
    入力の欠落を成功に畳まない。
  - eval-log/*.json から下記フィールドを best-effort に拾う:
      * rubric_version (もしくは current_version / target_version)
      * 対象スキル: skill_name / target_skill / proposer / proposal_id
  - JSONL (.jsonl) もサポート。

stdlib only / Python 3.9+.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Iterable

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUBRIC_REL = Path("skills") / "ref-skill-design-rubric" / "references" / "rubric.json"
# None のときは実行時に解決する (rubric は harness-creator の root、eval-log は cwd)。
UPSTREAM_RUBRIC: Path | None = None
EVAL_LOG_DIR: Path | None = None

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


def resolve_upstream_rubric() -> Path | None:
    """兄弟 plugin harness-creator を同梱の extract-plugin-root.py で解決し、L0 rubric の path を返す。"""
    resolver = PLUGIN_ROOT / "scripts" / "extract-plugin-root.py"
    # spec_from_file_location は実在しない path にも spec を返すので、先に実在を確かめる。
    spec = importlib.util.spec_from_file_location("_extract_plugin_root", resolver) if resolver.is_file() else None
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    found = module.resolve("harness-creator", PLUGIN_ROOT, Path.cwd())
    return None if found is None else found / RUBRIC_REL


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="rubric の major bump 後に再評価が必要なスキルを列挙する (書き込みなし)。"
    )
    parser.add_argument("--rubric", type=Path, help="upstream の L0 rubric.json (既定: harness-creator から解決)")
    parser.add_argument("--eval-log-dir", type=Path, help="過去評価ログの置き場 (既定: ./eval-log)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args([] if argv is None else argv)
    rubric = args.rubric or UPSTREAM_RUBRIC or resolve_upstream_rubric()
    eval_log_dir = args.eval_log_dir or EVAL_LOG_DIR or Path.cwd() / "eval-log"
    if rubric is None:
        print("# upstream rubric not found: harness-creator plugin is not resolvable", file=sys.stderr)
        return 2
    if not rubric.is_file():
        print(f"# upstream rubric not found: {rubric}", file=sys.stderr)
        return 2

    try:
        with rubric.open("r", encoding="utf-8") as f:
            upstream = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"# could not read upstream rubric {rubric}: {exc}", file=sys.stderr)
        return 2
    current = parse_semver(upstream.get("rubric_version")) if isinstance(upstream, dict) else None
    if current is None:
        print(
            f"# could not parse upstream rubric_version in {rubric}; aborting",
            file=sys.stderr,
        )
        return 2

    if not eval_log_dir.exists():
        print(f"# no eval-log directory at {eval_log_dir}; nothing to do")
        return 0

    targets: list[tuple[str, tuple[int, int, int]]] = []
    log_files = sorted(
        [p for p in eval_log_dir.iterdir() if p.suffix in (".json", ".jsonl")]
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
    sys.exit(main(sys.argv[1:]))

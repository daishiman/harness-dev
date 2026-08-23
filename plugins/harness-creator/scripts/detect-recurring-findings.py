#!/usr/bin/env python3
# /// script
# name: detect-recurring-findings
# purpose: eval-log/ と plugin-plans/*/plan-findings.json を横断して findings を収集し、
#          同一 key (finding_code / bucket / finding_id の完全一致) の反復を機械集計する。
#          学習ラチェット (verification-obligation-protocol.md) の運用口: 閾値以上の反復を
#          automation_candidates[] として台帳化し、schema/lint/test への昇格判断は
#          人間/AI レビューへ渡す。script は昇格の実行・除外の判断をしない (fail-closed:
#          全候補 status=unreviewed。意味類似の判定はせず完全一致キーの集計に留める)。
# inputs:
#   - argv: [--repo-root <dir>] [--threshold <n>=2] [--out <path>] [--json]
#   - files: <repo-root>/eval-log/**/findings*.json, <repo-root>/eval-log/**/*.jsonl,
#            <repo-root>/plugin-plans/*/plan-findings.json
# outputs:
#   - stdout: JSON report (automation_candidates[] / skipped[] / sources_scanned)
#   - stderr: 壊れた JSON 行/ファイルの警告 (行単位 fail-soft。skip して続行)
#   - --out: 同一 JSON をファイルへも書く (任意)
#   - exit: 0=集計完了 (候補の有無は exit に影響しない) / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: --out 指定パスのみ
# dependencies: []
# requires-python: ">=3.10"
# ///
"""反復 finding 検知 (学習ラチェット運用口)。

join key の設計:
  finding entry の形は evaluator ごとに多形だが、安定 slug を持つフィールドは
  finding_code > bucket > finding_id の 3 つ (この優先順で最初に存在するものを採用)。
  値の完全一致 (strip + lowercase 正規化) のみで集計し、observation の意味類似
  判定は行わない — 曖昧な類似判断は下流の人間/AI レビューの仕事として残す。

carrier 判定は注釈のみ:
  key 文字列が plugins/*/scripts/ または plugins/*/tests/ 配下に現れれば
  "machine"、なければ "unknown" (= prose のみか未昇格の可能性)。除外はしない。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

KEY_FIELDS = ("finding_code", "bucket", "finding_id")
OBSERVATION_FIELDS = ("observation", "summary", "description", "title", "reason")
FINDINGS_LIST_KEYS = ("findings", "paradigm_findings")
OBSERVATION_EXCERPT_LEN = 200


def _warn(msg: str) -> None:
    print(f"[detect-recurring-findings] warning: {msg}", file=sys.stderr)


def iter_finding_dicts(obj):
    """任意のネスト構造から findings/paradigm_findings リスト直下の dict を列挙する。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FINDINGS_LIST_KEYS and isinstance(v, list):
                for e in v:
                    if isinstance(e, dict):
                        yield e
            else:
                yield from iter_finding_dicts(v)
    elif isinstance(obj, list):
        for e in obj:
            yield from iter_finding_dicts(e)


def extract_entry(entry: dict):
    """finding dict から (key_field, raw_key, observation, severity) を取る。key 無しは None。"""
    for field in KEY_FIELDS:
        raw = entry.get(field)
        if isinstance(raw, str) and raw.strip():
            observation = ""
            for of in OBSERVATION_FIELDS:
                v = entry.get(of)
                if isinstance(v, str) and v.strip():
                    observation = v.strip()[:OBSERVATION_EXCERPT_LEN]
                    break
            severity = entry.get("severity")
            return field, raw.strip(), observation, severity if isinstance(severity, str) else None
    return None


def collect_source_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    eval_log = repo_root / "eval-log"
    if eval_log.is_dir():
        files += sorted(eval_log.rglob("findings*.json"))
        files += sorted(eval_log.rglob("*.jsonl"))
    files += sorted(repo_root.glob("plugin-plans/*/plan-findings.json"))
    return files


def load_documents(path: Path, rel: str, skipped: list[dict]):
    """1 ファイルから JSON document 群を yield する。壊れた行/ファイルは skip + 記録。"""
    if path.suffix == ".jsonl":
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as ex:
            skipped.append({"file": rel, "line": None, "reason": str(ex)})
            _warn(f"{rel}: {ex}")
            return
        for lineno, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as ex:
                skipped.append({"file": rel, "line": lineno, "reason": str(ex)})
                _warn(f"{rel}:{lineno}: broken JSON line skipped ({ex})")
    else:
        try:
            yield json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as ex:
            skipped.append({"file": rel, "line": None, "reason": str(ex)})
            _warn(f"{rel}: broken JSON file skipped ({ex})")


def detect_carrier(repo_root: Path, key: str) -> str:
    """key 文字列が機械検査資産 (scripts/tests) に現れるかの注釈。除外判断はしない。"""
    for pattern in ("plugins/*/scripts/*.py", "plugins/*/tests/*.py"):
        for p in repo_root.glob(pattern):
            try:
                if key in p.read_text(encoding="utf-8", errors="ignore").lower():
                    return "machine"
            except OSError:
                continue
    return "unknown"


def aggregate(repo_root: Path, threshold: int) -> dict:
    skipped: list[dict] = []
    occurrences: dict[str, list[dict]] = defaultdict(list)
    key_meta: dict[str, dict] = {}
    files = collect_source_files(repo_root)
    for path in files:
        rel = str(path.relative_to(repo_root))
        for doc in load_documents(path, rel, skipped):
            for entry in iter_finding_dicts(doc):
                extracted = extract_entry(entry)
                if extracted is None:
                    continue
                key_field, raw_key, observation, severity = extracted
                norm = raw_key.lower()
                occurrences[norm].append(
                    {"source": rel, "observation": observation, "severity": severity}
                )
                key_meta.setdefault(norm, {"key_field": key_field, "raw_key": raw_key})

    candidates = []
    for norm, occs in sorted(occurrences.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(occs) < threshold:
            continue
        meta = key_meta[norm]
        candidates.append(
            {
                "key": norm,
                "key_field": meta["key_field"],
                "count": len(occs),
                "sources": sorted({o["source"] for o in occs}),
                "severities": sorted({o["severity"] for o in occs if o["severity"]}),
                "observations": sorted({o["observation"] for o in occs if o["observation"]}),
                "carrier": detect_carrier(repo_root, norm),
                "status": "unreviewed",
            }
        )
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo_root": str(repo_root),
        "threshold": threshold,
        "sources_scanned": len(files),
        "keys_seen": len(occurrences),
        "skipped": skipped,
        "automation_candidates": candidates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="detect-recurring-findings",
        description="findings の反復を完全一致 key で集計し automation_candidates を台帳化する",
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--threshold", type=int, default=2)
    parser.add_argument("--out", type=Path, default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit as ex:
        return 2 if ex.code not in (0, None) else 0
    if args.threshold < 1:
        _warn("--threshold must be >= 1")
        return 2
    repo_root = args.repo_root or Path(__file__).resolve().parents[3]
    if not repo_root.is_dir():
        _warn(f"repo root not found: {repo_root}")
        return 2
    report = aggregate(repo_root, args.threshold)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

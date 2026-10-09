#!/usr/bin/env python3
# /// script
# name: record-knowledge-usage
# purpose: matched_ids/used_ids/satisfactionを呼出元eval-logのusage-log.jsonlへ記録する。
# inputs: ["--project-root absolute-path", "--entrypoint skill-name", "--search-result JSON", "--usage JSON", "--transcript JSON (feedback only)", "--ephemeral"]
# outputs: ["stdout usage receipt", "exit 0=recorded / 2=invalid input"]
# contexts: [C, E]
# network: false
# write-scope: caller-project/eval-log/ubm-goal-setting/knowledge/usage-log.jsonl only (ephemeral writes none)
# dependencies: []
# ///
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sys

ENTRYPOINTS = {"run-ubm-" + name for name in ("goal-setting", "journal", "challenge", "consult", "knowledge-sync", "youtube-ingest")}
LOG_RELATIVE = Path("eval-log/ubm-goal-setting/knowledge/usage-log.jsonl")
OFFICIAL_KNOWLEDGE = Path(__file__).resolve().parents[1] / "knowledge"


def read_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def record_usage(project_root: Path, entrypoint: str, candidate: dict, usage: dict,
                 transcript: list[dict] | None = None, *, ephemeral: bool = False) -> dict:
    if not project_root.is_absolute() or not project_root.is_dir() or entrypoint not in ENTRYPOINTS:
        raise ValueError("absolute caller project-root and known entrypoint required")
    root = project_root.resolve()
    if root == OFFICIAL_KNOWLEDGE.resolve() or OFFICIAL_KNOWLEDGE.resolve() in root.parents:
        raise ValueError("caller usage-log cannot be inside official knowledge")
    if not isinstance(candidate, dict) or candidate.get("schema_version") != 1 or not isinstance(usage, dict):
        raise ValueError("candidate/usage shape invalid")
    search_id = candidate.get("search_id")
    if not isinstance(search_id, str) or not re.fullmatch(r"[0-9a-f]{64}", search_id):
        raise ValueError("search_id invalid")
    matched_ids = candidate.get("matched_ids")
    used_ids = usage.get("used_ids")
    usage_id = usage.get("usage_id")
    if not isinstance(usage_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", usage_id):
        raise ValueError("stable usage_id required")
    for values in (matched_ids, used_ids):
        if not isinstance(values, list) or len(values) > 50 or any(not isinstance(v, str) or not v for v in values) or len(values) != len(set(values)):
            raise ValueError("matched_ids/used_ids must be unique string lists up to 50")
    matches = candidate.get("matches")
    if not isinstance(matches, list) or any(not isinstance(m, dict) for m in matches) or [m.get("id") for m in matches] != matched_ids:
        raise ValueError("matched_ids do not correspond to candidate matches")
    if not set(used_ids).issubset(matched_ids):
        raise ValueError("used_ids must be a subset of matched_ids")
    if "satisfaction" not in usage:
        raise ValueError("satisfaction must explicitly be null or actual user feedback")
    satisfaction = usage["satisfaction"]
    source_turn = usage.get("satisfaction_source_turn_id")
    if satisfaction is None:
        if source_turn is not None:
            raise ValueError("unknown satisfaction cannot claim a user turn")
    else:
        if satisfaction not in ("positive", "negative", "mixed") or not isinstance(source_turn, str) or not source_turn:
            raise ValueError("satisfaction must be positive/negative/mixed with a user turn id")
        if not isinstance(transcript, list) or any(not isinstance(t, dict) for t in transcript):
            raise ValueError("role/id/content transcript required for actual feedback")
        turns = [t for t in transcript if t.get("id") == source_turn]
        if len(turns) != 1 or turns[0].get("role") != "user" or not isinstance(turns[0].get("content"), str) or not turns[0]["content"].strip():
            raise ValueError("satisfaction source is not a unique actual user turn")
    core = {"schema_version": 1, "usage_id": usage_id, "entrypoint": entrypoint,
            "search_id": search_id, "matched_ids": matched_ids, "used_ids": used_ids,
            "unused_ids": [v for v in matched_ids if v not in used_ids],
            "satisfaction": satisfaction, "satisfaction_source_turn_id": source_turn,
            "search_result_sha256": hashlib.sha256(json.dumps(candidate, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
    row = {**core, "recorded_at": datetime.now(timezone.utc).isoformat()}
    if ephemeral:
        return {"status": "ephemeral", "row": row, "path": None}
    log = root / LOG_RELATIVE
    if any(p.is_symlink() for p in (log, *log.parents)) or log.resolve() != log:
        raise ValueError("usage-log path symlink or root escape")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        duplicate = None
        seen_usage_ids = set()
        for line in handle:
            if not line.endswith("\n"):
                raise ValueError("existing usage-log has an incomplete final line")
            previous = json.loads(line)
            if not isinstance(previous, dict) or not all(k in previous for k in (*core, "recorded_at")) or previous["schema_version"] != 1:
                raise ValueError("existing usage-log row is not a complete observation")
            prior_id = previous["usage_id"]
            if not isinstance(prior_id, str) or prior_id in seen_usage_ids:
                raise ValueError("existing usage-log has invalid or duplicate usage_id")
            seen_usage_ids.add(prior_id)
            if previous.get("usage_id") == usage_id:
                if {k: previous.get(k) for k in core} != core:
                    raise ValueError("usage_id already records a different observation")
                duplicate = previous
        if duplicate is not None:
            return {"status": "already_recorded", "row": duplicate, "path": str(log)}
        handle.seek(0, 2)
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
    return {"status": "recorded", "row": row, "path": str(log)}


def main() -> int:
    parser = argparse.ArgumentParser(description="実際の候補採用とユーザー反応を記録する")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--search-result", required=True)
    parser.add_argument("--usage", required=True)
    parser.add_argument("--transcript")
    parser.add_argument("--ephemeral", action="store_true")
    args = parser.parse_args()
    try:
        result = record_usage(Path(args.project_root), args.entrypoint, read_json(args.search_result),
                              read_json(args.usage), read_json(args.transcript) if args.transcript else None,
                              ephemeral=args.ephemeral)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

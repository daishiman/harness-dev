#!/usr/bin/env python3
# /// script
# name: search-knowledge
# purpose: routerが列挙するカテゴリentriesだけをフィールド重み付きで検索する読み取り専用stage。
# inputs: ["--knowledge-dir absolute-path", "--term keyword (repeatable)", "--category category (repeatable)", "--limit 1..50"]
# outputs: ["stdout candidate JSON", "exit 0=success including zero-hit / 2=invalid input"]
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

# 頻度ではなく、同じtermがどの意味フィールドへ当たったかを加点する。
FIELD_WEIGHTS = {
    "id": 20, "tags": 8, "keywords": 8, "applicable_when": 8, "trigger": 8,
    "lesson_applicable_when": 8, "title": 6, "situation": 6, "problem": 6,
    "root_cause": 6, "key_question": 5, "focus": 5, "intent": 5, "purpose": 5,
    "before": 4, "after": 4, "recommended": 4, "not_recommended": 4,
    "do": 4, "dont": 4, "content": 3, "advice": 3, "action": 3,
    "how_to_use": 3, "key_insight": 3, "insight": 3, "lesson": 3,
    "expected_outcome": 2, "background": 2, "rationale": 2, "result": 2,
    "outcome": 2, "summary": 2, "detail": 1, "quote": 1, "expression": 1,
}
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 10000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def text_value(value: object, depth: int = 0) -> str:
    if depth > 8:
        raise ValueError("search field nesting exceeds 8")
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize(value)
    if isinstance(value, list):
        return "\n".join(text_value(v, depth + 1) for v in value)
    if isinstance(value, dict):
        return "\n".join(text_value(value[k], depth + 1) for k in sorted(value))
    raise ValueError("search fields must be text, list or object (not boolean/number)")


def load_json(path: Path) -> tuple[object, str, int]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"regular JSON file required: {path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("knowledge file exceeds size bound")
    raw = path.read_bytes()
    return json.loads(raw), sha(raw), len(raw)


def search(knowledge_dir: Path, terms: list[str], categories: list[str] | None = None, limit: int = 20) -> dict:
    if not knowledge_dir.is_absolute():
        raise ValueError("knowledge-dir must be absolute")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise ValueError("limit must be 1..50")
    if not isinstance(terms, list) or not 1 <= len(terms) <= 12 or any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 120 for t in terms):
        raise ValueError("1..12 nonempty terms of at most 120 characters required")
    query_terms = sorted({normalize(term) for term in terms})
    root = knowledge_dir.resolve(strict=True)
    router, router_sha, total_bytes = load_json(root / "router.json")
    if not isinstance(router, dict) or not isinstance(router.get("categories"), dict) or not router["categories"]:
        raise ValueError("router.categories must be a nonempty object")
    declared = router["categories"]
    selected = sorted(set(categories)) if categories else sorted(declared)
    if not selected or any(not isinstance(c, str) or c not in declared for c in selected):
        raise ValueError("unknown or empty category selection")
    files = {}
    matches = []
    ids = set()
    entries_seen = 0
    for category in selected:
        spec = declared[category]
        names = spec.get("files") if isinstance(spec, dict) else None
        if not isinstance(names, list) or not names or any(not isinstance(n, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.json", n) for n in names):
            raise ValueError("category.files must list flat JSON basenames")
        if len(names) != len(set(names)):
            raise ValueError("duplicate file in category.files")
        for filename in sorted(names):
            if filename in {"router.json", "registry.json", "schema.json"}:
                raise ValueError("bookkeeping files cannot be category entries")
            path = root / filename
            if path.resolve() != path or path.is_symlink():
                raise ValueError("category file symlink/root escape")
            if filename in files:
                raise ValueError("category file listed in multiple categories")
            data, file_sha, byte_count = load_json(path)
            total_bytes += byte_count
            if total_bytes > MAX_TOTAL_BYTES:
                raise ValueError("selected knowledge exceeds total size bound")
            entries = data.get("entries") if isinstance(data, dict) else None
            if not isinstance(entries, list):
                raise ValueError("category file must have entries array")
            files[filename] = file_sha
            for entry in entries:
                entries_seen += 1
                if entries_seen > MAX_ENTRIES:
                    raise ValueError("selected entry count exceeds bound")
                identifier = entry.get("id") if isinstance(entry, dict) else None
                if not isinstance(identifier, str) or not identifier.strip() or identifier in ids:
                    raise ValueError("entry id missing or duplicated")
                if not isinstance(entry.get("source"), (str, dict, list)) or not entry["source"]:
                    raise ValueError(f"entry source missing: {identifier}")
                ids.add(identifier)
                field_hits = {}
                for field, weight in FIELD_WEIGHTS.items():
                    if field not in entry:
                        continue
                    value = text_value(entry[field])
                    hits = [term for term in query_terms if (term == value if field == "id" else term in value)]
                    if hits:
                        field_hits[field] = {"terms": hits, "weight": weight}
                score = sum(hit["weight"] * len(hit["terms"]) for hit in field_hits.values())
                if score:
                    matches.append({"id": identifier, "category": category, "score": score,
                                    "field_hits": field_hits, "source": entry["source"],
                                    "source_ref": str(path) + "#entries[id=" + identifier + "]",
                                    "file_sha256": file_sha, "entry": entry})
    matches.sort(key=lambda hit: (-hit["score"], hit["id"], hit["source_ref"]))
    results = matches[:limit]
    fingerprint = {"terms": query_terms, "categories": selected, "limit": limit,
                   "router_sha256": router_sha, "files": files, "field_weights": FIELD_WEIGHTS}
    return {"schema_version": 1, "search_id": sha(json.dumps(fingerprint, sort_keys=True, ensure_ascii=False).encode()),
            **fingerprint, "entries_scanned": entries_seen, "total_hits": len(matches),
            "zero_hit": not matches, "matched_ids": [m["id"] for m in results], "matches": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="router限定の決定論フィールド重み付き検索")
    parser.add_argument("--knowledge-dir", required=True)
    parser.add_argument("--term", action="append", required=True)
    parser.add_argument("--category", action="append")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    try:
        result = search(Path(args.knowledge_dir), args.term, args.category, args.limit)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

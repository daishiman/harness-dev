#!/usr/bin/env python3
# /// script
# name: normalized-source-path
# purpose: C01/oneshot共通の動画ID付き保存パスを決め既存ファイルの所有IDを検査する。
# inputs: ["--metadata JSON", "--source-out absolute-directory"]
# outputs: ["stdout JSON relative_path/absolute_path", "exit 0=valid / 2=invalid or conflict"]
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
import unicodedata


def sanitize_title(title: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]', "_", unicodedata.normalize("NFC", title)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned.encode("utf-8")[:96].decode("utf-8", errors="ignore").rstrip() or "untitled")


def normalized_rel_path(meta: dict) -> str:
    vid = meta.get("video_id")
    if not isinstance(vid, str) or not vid.strip() or len(vid.encode("utf-8")) > 32:
        raise ValueError("video_id must be nonempty UTF-8 text of at most 32 bytes")
    published_at = meta.get("published_at")
    title = meta.get("title", "untitled")
    if not isinstance(published_at, str) or not isinstance(title, str):
        raise ValueError("published_at and title must be text")
    published = published_at[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
        raise ValueError("published_at must start with YYYY-MM-DD")
    date.fromisoformat(published)
    # UTF-8 hex is injective even on case-insensitive filesystems; ID separators
    # and control bytes never become path characters. Retain the original in YAML.
    token = vid.encode("utf-8").hex()
    return f"YouTube/{published} - {sanitize_title(title)} [id-{token}].md"


def source_video_id(path: Path) -> str:
    with path.open(encoding="utf-8") as handle:
        prefix = handle.read(65536)
    lines = prefix.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError("existing source lacks bounded frontmatter")
    closing = lines.index("---", 1)
    ids = [line[len("video_id:"):].strip() for line in lines[1:closing] if line.startswith("video_id:")]
    if len(ids) != 1:
        raise ValueError("existing source has missing/ambiguous video_id")
    raw = ids[0]
    if raw.startswith('"'):
        value = json.loads(raw)
    elif len(raw) >= 2 and raw.startswith("'") and raw.endswith("'"):
        value = raw[1:-1].replace("''", "'")
    elif re.fullmatch(r"[A-Za-z0-9_-]+", raw):
        value = raw
    else:
        raise ValueError("existing video_id scalar is not safely readable")
    if not isinstance(value, str) or not value:
        raise ValueError("existing source video_id invalid")
    return value


def checked_source_path(source_out: Path, meta: dict) -> Path:
    if not source_out.is_absolute():
        raise ValueError("source-out must be absolute")
    root = source_out.resolve()
    if root.exists() and not root.is_dir():
        raise ValueError("source-out must be a directory")
    path = root / normalized_rel_path(meta)
    if any(p.is_symlink() for p in (path, path.parent)) or path.resolve() != path:
        raise ValueError("source path symlink or root escape")
    if path.exists():
        if not path.is_file() or source_video_id(path) != meta["video_id"]:
            raise ValueError("existing source belongs to a different video_id")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="動画ID付きの正規化保存パスと既存IDを読み取り専用検査")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--source-out", required=True)
    args = parser.parse_args()
    try:
        meta = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            raise ValueError("metadata must be an object")
        path = checked_source_path(Path(args.source_out), meta)
        result = {"relative_path": normalized_rel_path(meta), "absolute_path": str(path)}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

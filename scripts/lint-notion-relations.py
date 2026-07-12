#!/usr/bin/env python3
"""Notion 3DB リレーション不変条件 lint。

検証ルール:
  1. ヒアリングシート.紐づくプラグイン は 0 件か 1 件 (=1:1 上限)
  2. 改善要望.対象プラグイン は exactly 1 件 (必須)
  3. スキル一覧.プラグイン名 は重複なし

非ゼロ終了で違反検知。CI で実行する想定。
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "harness-creator" / "scripts"))
import notion_config  # noqa: E402

SCHEMA_DIR = ROOT / "doc" / "notion-schema"


def curl(method, url, tk, body=None):
    cmd = ["curl", "-sS", "-X", method,
           "-H", f"Authorization: Bearer {tk}",
           "-H", "Notion-Version: 2022-06-28",
           "-H", "Content-Type: application/json",
           "-w", "\n__HTTP__%{http_code}", url]
    tmp = None
    if body is not None:
        tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")
        json.dump(body, tmp); tmp.close()
        cmd += ["--data-binary", f"@{tmp.name}"]
    out = subprocess.check_output(cmd).decode()
    if tmp: os.unlink(tmp.name)
    payload, _, code = out.rpartition("__HTTP__")
    return int(code.strip()), json.loads(payload) if payload.strip() else {}


def query_all(db_id, tk):
    pages, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor: body["start_cursor"] = cursor
        code, data = curl("POST", f"https://api.notion.com/v1/databases/{db_id}/query", tk, body)
        if code >= 300:
            print(f"[ERR] query {db_id}: {code}"); sys.exit(2)
        pages.extend(data["results"])
        if not data.get("has_more"): break
        cursor = data.get("next_cursor")
    return pages


def main():
    cfg, tk = notion_config.require_or_skip()
    if not cfg:
        return 0
    db_ids = {k: notion_config.get_db_id(k)
              for k in ["hearing-sheet", "skill-list", "improvement-request"]}
    missing = [k for k, v in db_ids.items() if not v]
    if missing:
        print(f"[SKIP] missing db_id in .notion-config.json: {missing}")
        return 0
    violations = []

    # Rule 1: ヒアリングシート.紐づくプラグイン ≤ 1
    for p in query_all(db_ids["hearing-sheet"], tk):
        rel = p["properties"].get("紐づくプラグイン", {}).get("relation", [])
        if len(rel) > 1:
            violations.append(f"hearing-sheet {p['id']}: 紐づくプラグインが {len(rel)} 件 (max 1)")

    # Rule 2: 改善要望.対象プラグイン == 1
    for p in query_all(db_ids["improvement-request"], tk):
        rel = p["properties"].get("対象プラグイン", {}).get("relation", [])
        if len(rel) != 1:
            title = "".join(t.get("plain_text","") for t in
                            p["properties"].get("要望タイトル",{}).get("title",[]))
            violations.append(f"improvement-request '{title}': 対象プラグインが {len(rel)} 件 (must be 1)")

    # Rule 3: スキル一覧.プラグイン名 重複なし
    names = {}
    for p in query_all(db_ids["skill-list"], tk):
        title = "".join(t.get("plain_text","") for t in
                        p["properties"].get("プラグイン名",{}).get("title",[]))
        if not title: continue
        names.setdefault(title, []).append(p["id"])
    for n, ids in names.items():
        if len(ids) > 1:
            violations.append(f"skill-list: プラグイン名 '{n}' が {len(ids)} 件重複 -> {ids}")

    if violations:
        print(f"[FAIL] {len(violations)} violation(s):")
        for v in violations: print(f"  - {v}")
        sys.exit(1)
    print("[OK] all relation invariants satisfied")


if __name__ == "__main__":
    main()

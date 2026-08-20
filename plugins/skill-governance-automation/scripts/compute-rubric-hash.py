#!/usr/bin/env python3
# /// script
# name: compute-rubric-hash
# version: 0.1.0
# purpose: rubric.json の正規化 JSON SHA-256 を計算し rubric.normalized.json と rubric_hash を更新（27章§8.2 正本）
# inputs:
#   - --rubric: rubric.json のパス（必須）
#   - --out-normalized: 正規化 JSON 出力先（既定: 同階層 rubric.normalized.json）
#   - --dry-run: ハッシュ計算のみ、ファイル書込なし
# outputs:
#   - file: rubric.normalized.json, rubric.json (rubric_hash フィールド更新)
#   - stdout: sha256:<hex>
#   - exit: 0=OK / 1=入力エラー / 2=usage
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, B]
# network: false
# write-scope: output-dir
# ///
"""rubric.json の決定論的ハッシュを算出する。"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path


def normalize(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", required=True)
    ap.add_argument("--out-normalized", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rp = Path(args.rubric)
    if not rp.is_file():
        print(f"error: rubric not found: {rp}", file=sys.stderr)
        return 1
    data = json.loads(rp.read_text(encoding="utf-8"))
    data.pop("rubric_hash", None)
    norm = normalize(data)
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    hash_str = f"sha256:{digest}"
    print(hash_str)

    if args.dry_run:
        return 0

    out_norm = Path(args.out_normalized) if args.out_normalized else rp.with_suffix(".normalized.json")
    out_norm.write_text(norm + "\n", encoding="utf-8")

    data["rubric_hash"] = hash_str
    rp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

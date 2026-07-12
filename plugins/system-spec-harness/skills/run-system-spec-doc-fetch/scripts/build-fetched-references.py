#!/usr/bin/env python3
# /// script
# name: build-fetched-references
# version: 0.1.0
# purpose: run-system-spec-doc-fetch R3 の記録形状を決定論的に組み立てる assembler。取得済みドキュメントの record を必須フィールド検証・source_url host と official_host の一致検証付きで正規化し、fetched-references.json (共有データ契約) を出力する。恒久キャッシュ/ミラーリング/ネットワークは行わず WebSearch/WebFetch の取得結果を渡し込む純関数群として動く。内容が現行最新版かの意味判定は C08 が、対象一覧との全件対応の最終突合は plugin-root の validate-source-citation.py が担う。
# inputs:
#   - argv: assemble サブコマンドと --records FILE / --targets FILE / --out FILE
# outputs:
#   - fetched-references.json (stdout or --out)
#   - exit: 0=OK / 1=RecordError or IO / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: fetched-references.json
# dependencies: []
# requires-python: ">=3.9"
# ///
"""fetched-references.json の記録形状を決定論的に組み立てる R3 assembler。

本モジュールは R3-record の唯一の組み立て経路であり、WebSearch/WebFetch で得た
取得結果 (record 素材) を受け取り、共有データ契約 (validate-source-citation.py と
一致) の形状へ正規化する。時刻はネットワーク/壁時計に依存せず入力 record が持つ
retrieved_at / latest_checked_at をそのまま採用する (再現性)。

record 素材 (入力) の期待形状:
  {"target_id": "react",
   "retrieved_at": "2026-07-11T00:00:00Z",
   "source_url": "https://react.dev/reference/react",
   "official_publisher": "Meta",
   "official_host": "react.dev",          # 省略時は source_url から導出
   "version": "19.0",                      # version または last_updated のいずれか必須
   "last_updated": "2026-06-01",
   "latest_checked_at": "2026-07-11T00:00:00Z",
   "summary": "..."}

出力 (fetched-references.json):
  {"references": [<正規化 record>, ...]}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

# 全 record が必ず持つべき素材フィールド (official_host は導出可なので別扱い)。
REQUIRED_INPUT_FIELDS = (
    "target_id",
    "source_url",
    "official_publisher",
    "retrieved_at",
    "latest_checked_at",
    "summary",
)
# 正規化後の出力キー順 (契約の可読順)。存在するものだけ載せる。
OUTPUT_FIELD_ORDER = (
    "target_id",
    "retrieved_at",
    "source_url",
    "official_publisher",
    "official_host",
    "version",
    "last_updated",
    "latest_checked_at",
    "summary",
)


class RecordError(Exception):
    """record 素材が形状契約に反するときに送出する。"""


def norm_host(host: str) -> str:
    """host を小文字化し先頭 www. を落として比較用に正規化する。"""
    if not host:
        return ""
    # lstrip("www.") は文字集合 {w,.} の先頭剥がしで `web.dev`->`eb.dev` / `wix.com`->`ix.com`
    # のように別 host を破壊するため removeprefix を使う (C13 validate-source-citation.py の F6 と同一)。
    return host.lower().removeprefix("www.")


def host_of(url: str) -> str:
    """URL から正規化済み host を導出する (解決不能なら空文字)。"""
    return norm_host(urlparse(url or "").netloc)


def build_record(rec: dict) -> dict:
    """1 件の record 素材を契約形状へ正規化・検証する。

    - 必須素材フィールド欠落は RecordError。
    - version と last_updated のいずれも無ければ RecordError。
    - official_host は未指定なら source_url から導出し、指定時は host 一致を検証する。
    """
    if not isinstance(rec, dict):
        raise RecordError("record はオブジェクトでない")

    tid = rec.get("target_id")
    if not tid:
        raise RecordError("target_id が空/欠落")

    for field in REQUIRED_INPUT_FIELDS:
        if not rec.get(field):
            raise RecordError(f"{tid}: 必須フィールド {field} が空/欠落")

    if not (rec.get("version") or rec.get("last_updated")):
        raise RecordError(f"{tid}: version と last_updated の両方が空 (いずれか必須)")

    src = rec["source_url"]
    derived = host_of(src)
    if not derived:
        raise RecordError(f"{tid}: source_url={src!r} から host を解決できない")

    host = rec.get("official_host") or derived
    if norm_host(host) != derived:
        raise RecordError(
            f"{tid}: source_url host={derived!r} が official_host={host!r} と不一致"
        )

    normalized = dict(rec)
    normalized["official_host"] = host
    return {k: normalized[k] for k in OUTPUT_FIELD_ORDER if normalized.get(k)}


def assemble(records: list) -> dict:
    """record 素材列を fetched-references.json 形状へ組み立てる。

    target_id 重複は RecordError。順序は入力順を保つ (決定論)。
    """
    if not isinstance(records, list):
        raise RecordError("records は配列でない")
    seen: set[str] = set()
    refs: list[dict] = []
    for rec in records:
        built = build_record(rec)
        tid = built["target_id"]
        if tid in seen:
            raise RecordError(f"target_id={tid!r} が重複")
        seen.add(tid)
        refs.append(built)
    return {"references": refs}


def _target_ids(targets_data: dict) -> list[str]:
    """targets ファイルから target_id 一覧を抽出する (dict/str 配列の両対応)。"""
    ids: list[str] = []
    for t in targets_data.get("targets", []):
        if isinstance(t, str):
            ids.append(t)
        elif isinstance(t, dict) and t.get("target_id"):
            ids.append(t["target_id"])
    return ids


def missing_targets(targets_data: dict, references: dict) -> list[str]:
    """targets のうち references に record が無い target_id を返す。"""
    covered = {r.get("target_id") for r in references.get("references", [])}
    return [t for t in _target_ids(targets_data) if t not in covered]


def _load(path_str: str, label: str) -> dict:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"{label} ファイルが存在しない: {path_str}")
    return json.loads(path.read_text(encoding="utf-8"))


def _records_from(data) -> list:
    """--records の入力が list そのものか {"records": [...]} かを吸収する。"""
    if isinstance(data, dict):
        return data.get("records", [])
    return data


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="fetched-references.json の R3 決定論 assembler"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_asm = sub.add_parser("assemble", help="record 素材から fetched-references.json を組む")
    p_asm.add_argument("--records", required=True, help="record 素材 JSON (list か {records:[...]})")
    p_asm.add_argument("--targets", help="全件対応を突合する targets JSON (任意)")
    p_asm.add_argument("--out", help="出力先 (省略時 stdout)")

    args = ap.parse_args(argv)

    try:
        records = _records_from(_load(args.records, "records"))
        result = assemble(records)
        if args.targets:
            missing = missing_targets(_load(args.targets, "targets"), result)
            if missing:
                raise RecordError(f"対象 target_id の参照欠落: {missing}")
    except RecordError as exc:
        print(f"RecordError: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"JSON parse 失敗: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"OK: {len(result['references'])} 件を {args.out} へ書き出した")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""作成済みNotion DBが notion-db-schema.json の全プロパティを持つか検証する。

drift検知: DBプロパティと schema 正本の差分を報告。欠落があれば exit 1。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))
from mfk_api import load_config  # noqa: E402
from notion_invoice_sink import (  # noqa: E402
    _notion_token,
    _req,
    residual_extra_columns,
    suspect_summary_extras,
)


def load_schema():
    with open(os.path.join(_HERE, "..", "schemas", "notion-db-schema.json"), encoding="utf-8") as f:
        return json.load(f)


def property_errors(existing_props, schema):
    """Notion DB properties が schema の型/option/format と一致するか検証する。"""
    errs = []
    for name, spec in schema["properties"].items():
        prop = existing_props.get(name)
        if prop is None:
            continue
        actual_type = prop.get("type")
        expected_type = spec["type"]
        if actual_type != expected_type:
            errs.append(f"{name}: type が {actual_type!r} (期待 {expected_type!r})")
            continue
        if expected_type == "select":
            actual_options = {
                o.get("name")
                for o in ((prop.get("select") or {}).get("options") or [])
                if o.get("name")
            }
            missing_options = sorted(set(spec.get("options", [])) - actual_options)
            if missing_options:
                errs.append(f"{name}: select option 欠落 {missing_options}")
        if expected_type == "number":
            fmt = (prop.get("number") or {}).get("format")
            if fmt != "yen":
                errs.append(f"{name}: number format が {fmt!r} (期待 'yen')")
    return errs


def main():
    schema = load_schema()
    cfg = load_config()
    db_id = (cfg.get("notion") or {}).get("database_id")
    if not db_id:
        sys.stderr.write("[verify_db_schema] database_id 未設定。先に build_notion_db.py を実行してください。\n")
        return 2
    token = _notion_token()
    res = _req("GET", f"/databases/{db_id}", token)
    existing_props = res.get("properties") or {}
    existing = set(existing_props.keys())
    expected = set(schema["properties"].keys())
    stale_renames = sorted(
        old for old, new in schema.get("renames", {}).items()
        if old in existing and new in existing
    )
    missing = sorted(expected - existing)
    type_errors = property_errors(existing_props, schema)
    # 削除されるべき旧列が残っていないか (移行の drift)。extra のうち deprecated は致命。
    residual, extra = residual_extra_columns(existing_props, schema)
    # extra(schema 未知列)を集計疑い/その他に分ける。suspect は集計列の疑いとして強めに WARN するが
    # FAIL には昇格しない(正当な「合計確認メモ」等の偽陽性で恒常 FAIL=オオカミ少年を避ける)。
    suspect = suspect_summary_extras(extra)
    others = sorted(set(extra) - set(suspect))

    def _print_extra_warnings():
        if suspect:
            print(f"WARN 集計列の疑いがある追加列: {suspect} "
                  f"(意図的でなければ build_notion_db.py 再実行で掃除。集計は持たない設計)")
        if others:
            print(f"     (参考: DBにのみ存在する追加列: {others})")

    if missing or residual or type_errors or stale_renames:
        if missing:
            print(f"FAIL 欠落プロパティ: {missing}")
        if type_errors:
            print("FAIL プロパティ型/option/format 不一致:")
            for err in type_errors:
                print(f"  - {err}")
        if residual:
            print(f"FAIL 削除されるべき旧プロパティが残存: {residual} "
                  f"(build_notion_db.py を再実行して掃除してください)")
        if stale_renames:
            print(f"FAIL 改名済みの旧プロパティが新名と併存: {stale_renames} "
                  f"(build_notion_db.py を再実行して旧列を掃除してください)")
        _print_extra_warnings()
        return 1
    print(f"PASS 全 {len(expected)} プロパティが存在し、旧プロパティの残存もありません。")
    _print_extra_warnings()
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# kind: run-support
# purpose: reconcile 二層台帳 (DB1 契約マスタ / DB2 月次チェック) を冪等に用意する find-or-create ビルダー。
#   - config の reconcile_db1_id/reconcile_db2_id が実在すれば再利用し schema を冪等適用 (列追加のみ)。
#   - 欠落時のみ parent_page_id 配下へ新規作成し id を .mf-kessai-config.json へ記録する。
#   再実行で DB を重複作成しない (=「毎回新規作成」回避)。schema drift (列欠落) は再実行で自動補修。
# argv: [--parent-page-id <id>] [--config <path>] [--recreate]
# write-scope: Notion(DB1/DB2 の作成・プロパティ追加のみ。行データは触らない)。MF は触らない。
# exit: 0=OK / 2=fail-closed(parent 未解決で新規作成不能)
"""reconcile DB1/DB2 の冪等 find-or-create ビルダー。

旧 build_notion_db.py は旧フロー『請求書チェック_DB』専用で relation/last_edited_time 非対応の
ため reconcile 用に分離。月次運用では DB を作り直さず更新する設計 (DB1=最新状態マスタ /
DB2=対象年月キーで月別に積層する不変アーカイブ)。本ビルダーは「id があれば再利用・無ければ作成」
で冪等性を担保し、config(.mf-kessai-config.json) の id 喪失時に DB が断片化するのを防ぐ。
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))

import mfk_api  # noqa: E402
import notion_transport as nt  # noqa: E402

_SCHEMA_DIR = os.path.join(_PLUGIN_ROOT, "skills", "run-mf-invoice-reconcile", "schemas")
_LOCAL_CONFIG = os.path.join(_PLUGIN_ROOT, ".mf-kessai-config.json")

# 金額(円)列。件数列(期待明細数/分割回数/初回年間月数/期待件数/MF供給件数)は素の number。
_YEN_FIELDS = {"現行単価", "期待金額", "突合金額"}


def _load_schema(name):
    with open(os.path.join(_SCHEMA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def _load_config(explicit=None):
    """default + local の 2 層 config を読む (reconcile_invoices と同一規則)。"""
    default_path = os.path.join(_PLUGIN_ROOT, "mf-kessai-config.default.json")
    cfg = {}
    if os.path.exists(default_path):
        with open(default_path, encoding="utf-8") as f:
            cfg = json.load(f)
    local_path = explicit or _LOCAL_CONFIG
    if os.path.exists(local_path):
        with open(local_path, encoding="utf-8") as f:
            cfg = mfk_api._deep_merge(cfg, json.load(f))
    return cfg


def _save_local_id(key, value):
    """ローカル .mf-kessai-config.json の notion.<key> を更新する (他キーは保持)。"""
    cfg = {}
    if os.path.exists(_LOCAL_CONFIG):
        with open(_LOCAL_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
    cfg.setdefault("notion", {})[key] = value
    with open(_LOCAL_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _build_property(name, spec, db1_id=None):
    t = spec["type"]
    if t == "title":
        return {"title": {}}
    if t == "rich_text":
        return {"rich_text": {}}
    if t == "number":
        return {"number": {"format": "yen" if name in _YEN_FIELDS else "number"}}
    if t == "date":
        return {"date": {}}
    if t == "checkbox":
        return {"checkbox": {}}
    if t == "select":
        return {"select": {"options": [{"name": o} for o in spec.get("options", [])]}}
    if t == "last_edited_time":
        return {"last_edited_time": {}}
    if t == "relation":
        if not db1_id:
            raise SystemExit(f"relation 列 {name} の参照先 DB1 id が未解決です。")
        return {"relation": {"database_id": db1_id, "single_property": {}}}
    raise SystemExit(f"未対応の schema type: {t} ({name})")


def _resolve(db_id, token):
    """db_id が実在し DB として GET できるなら properties を返す。不在/不可なら None。"""
    if not db_id:
        return None
    try:
        res = nt._req("GET", f"/databases/{db_id}", token)
        return res.get("properties", {})
    except Exception:  # noqa: BLE001 — 不在/権限なしは「未配線」と同義に倒す
        return None


def _ensure_schema(db_id, schema, token, db1_id=None):
    """既存 DB に schema の不足プロパティだけを追加する (列削除はしない=非破壊)。"""
    existing = _resolve(db_id, token) or {}
    add = {}
    for name, spec in schema["properties"].items():
        if spec["type"] == "title":
            continue  # title は作成時に確定済み
        if name not in existing:
            add[name] = _build_property(name, spec, db1_id)
    if add:
        nt._req("PATCH", f"/databases/{db_id}", token, {"properties": add})
    return sorted(add.keys())


def _create(schema, parent, token, db1_id=None):
    props = {n: _build_property(n, s, db1_id) for n, s in schema["properties"].items()}
    body = {
        "parent": {"type": "page_id", "page_id": parent},
        "title": [{"text": {"content": schema["title"]}}],
        "properties": props,
    }
    res = nt._req("POST", "/databases", token, body)
    return res["id"], res.get("url", "")


def _ensure_db(label, cfg_key, schema, cfg, token, parent, db1_id=None, recreate=False):
    """find-or-create: id 実在なら再利用+schema冪等適用、無ければ作成。(db_id, mode) を返す。"""
    cur = (cfg.get("notion") or {}).get(cfg_key)
    if cur and not recreate and _resolve(cur, token) is not None:
        added = _ensure_schema(cur, schema, token, db1_id)
        mode = f"再利用(列追加 {added})" if added else "再利用(schema最新)"
        print(f"[{label}] {mode} id={cur}")
        return cur, "reused"
    if not parent:
        sys.stderr.write(
            f"[{label}] 新規作成が必要ですが parent_page_id 未解決です。\n"
            f"  --parent-page-id <id> か config notion.parent_page_id / 環境変数 "
            f"MFK_RECONCILE_PARENT_PAGE_ID を設定してください。\n")
        raise SystemExit(2)
    db_id, url = _create(schema, parent, token, db1_id)
    _save_local_id(cfg_key, db_id)
    print(f"[{label}] 新規作成 id={db_id}\n  {url}\n  → .mf-kessai-config.json notion.{cfg_key} に記録")
    return db_id, "created"


def main():
    p = argparse.ArgumentParser(description="reconcile DB1/DB2 冪等ビルダー (find-or-create)")
    p.add_argument("--parent-page-id", help="新規作成時の親ページ id (config/env より優先)")
    p.add_argument("--config", help="ローカル設定 JSON path")
    p.add_argument("--recreate", action="store_true",
                   help="既存 id を無視して新規作成する (断片化注意・通常は使わない)")
    a = p.parse_args()

    cfg = _load_config(a.config)
    notion = cfg.get("notion") or {}
    parent = (a.parent_page_id or os.environ.get("MFK_RECONCILE_PARENT_PAGE_ID")
              or notion.get("parent_page_id"))
    token = nt._notion_token(cfg)

    db1_schema = _load_schema("contract-master-db.schema.json")
    db2_schema = _load_schema("monthly-check-db.schema.json")

    # DB1 を先に解決 (DB2 の relation 参照先)。
    db1_id, _ = _ensure_db("DB1 契約マスタ", "reconcile_db1_id", db1_schema,
                           cfg, token, parent, recreate=a.recreate)
    cfg.setdefault("notion", {})["reconcile_db1_id"] = db1_id  # DB2 relation 解決用に反映
    _ensure_db("DB2 月次チェック", "reconcile_db2_id", db2_schema,
               cfg, token, parent, db1_id=db1_id, recreate=a.recreate)
    print("[done] reconcile DB1/DB2 を冪等に用意しました (再実行で重複作成しません)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

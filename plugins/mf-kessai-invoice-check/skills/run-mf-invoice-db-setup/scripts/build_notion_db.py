#!/usr/bin/env python3
"""schemas/notion-db-schema.json を読み、Notion 発行漏れチェックDBを用意する。

2 モード (冪等):
  - tenant overlay/ローカル config に database_id がある場合 → 既存DBにスキーマを適用
    (不足プロパティ追加・タイトル列リネーム)。配布既定の ID は空で fail-closed。
  - --parent-page-id 指定時、または database_id が無く parent_page_id がある場合 →
    親ページ配下に新規DBを作成し
    database_id をローカル .mf-kessai-config.json に記録する。
status型はNotion APIで作成不可のため、schema側で select に固定済み。
"""
import json
import os
import sys
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))
from mfk_api import load_config  # noqa: E402
from notion_invoice_sink import _notion_token, _req  # noqa: E402

CONFIG_PATH = os.path.join(_PLUGIN_ROOT, ".mf-kessai-config.json")


def load_schema():
    with open(os.path.join(_HERE, "..", "schemas", "notion-db-schema.json"), encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def build_property(spec):
    t = spec["type"]
    if t == "title":
        return {"title": {}}
    if t == "rich_text":
        return {"rich_text": {}}
    if t == "number":
        return {"number": {"format": "yen"}}
    if t == "date":
        return {"date": {}}
    if t == "checkbox":
        return {"checkbox": {}}
    if t == "select":
        return {"select": {"options": [{"name": o} for o in spec.get("options", [])]}}
    raise ValueError(f"unsupported property type: {t}")


def merge_select_property(existing_prop, spec):
    """既存 select option を消さず、schema 側の不足 option だけ追加する。"""
    existing_options = (existing_prop.get("select") or {}).get("options") or []
    by_name = {o.get("name"): dict(o) for o in existing_options if o.get("name")}
    for name in spec.get("options", []):
        by_name.setdefault(name, {"name": name})
    return {"select": {"options": list(by_name.values())}}


def _db_title(res):
    return "".join(t.get("plain_text", "") for t in res.get("title", [])) or "(無題)"


def ensure_schema(db_id, schema, token):
    """既存DBに schema のプロパティを冪等適用する (不足追加 + タイトル列リネーム)。

    既存データ・既存の管理列記入は壊さない (足りないものを足すだけ)。
    """
    res = _req("GET", f"/databases/{db_id}", token)
    existing = res.get("properties", {})
    want_title = next(n for n, s in schema["properties"].items() if s["type"] == "title")
    cur_title = next((n for n, p in existing.items() if p.get("type") == "title"), None)

    patch = {}
    # タイトル列を schema 名に合わせる (型は title のまま名前だけ変更)。既に正しければ何もしない
    if cur_title and cur_title != want_title and want_title not in existing:
        patch[cur_title] = {"name": want_title}
    # 宣言された列リネーム (値保持) を適用する。schema.renames = {old: new}。
    # old が既存 DB にあり new がまだ無ければ {old: {"name": new}} で改名する
    # (タイトル列リネームと同型。select の option 値はそのまま保持される)。
    # 既に new に改名済み (old が無い) なら何もしない=冪等。下の「不足追加」で new を
    # 新規作成して値ゼロの空列を生むのを防ぐため、renames は不足追加より先に処理する。
    renamed_targets = set()
    for old, new in schema.get("renames", {}).items():
        if old in existing and new not in existing:
            patch[old] = {"name": new}
            renamed_targets.add(new)
        elif old in existing and new in existing:
            # 旧名と新名が併存している drift。値保持リネームは既に完了しているため、
            # 旧列だけ削除して schema の単一名へ収束させる。
            patch[old] = None
    # 不足プロパティを追加 (title 型は1つだけなので除外)
    for name, spec in schema["properties"].items():
        if spec["type"] == "title":
            continue
        if name in renamed_targets:
            # この列は旧名からの値保持リネームで用意される。空列の新規追加で
            # リネームを潰さないようスキップする (option 値を保持する経路を優先)。
            continue
        if name not in existing:
            patch[name] = build_property(spec)
        elif spec["type"] == "select":
            existing_names = {
                o.get("name")
                for o in ((existing[name].get("select") or {}).get("options") or [])
                if o.get("name")
            }
            missing_options = set(spec.get("options", [])) - existing_names
            if missing_options:
                patch[name] = merge_select_property(existing[name], spec)

    # deprecated 列の自動削除 (whitelist のみ)。顧客ID集約への移行で不要になった旧列
    # (月次サマリ行モデルの件数列等) を消す。安全のため schema の現行 properties に
    # 含まれる名前は絶対に削除しない (誤削除防止)。Notion は properties.{name}=null で列削除。
    for name in schema.get("deprecated_properties", []):
        if name in existing and name not in schema["properties"]:
            patch[name] = None

    if not patch:
        print(f"OK 既存DB『{_db_title(res)}』は既にスキーマ最新 (database_id={db_id})。変更なし。")
        return 0
    _req("PATCH", f"/databases/{db_id}", token, {"properties": patch})
    removed = sorted(k for k, v in patch.items() if v is None)
    renamed = [f"{k}→{v['name']}" for k, v in patch.items() if v is not None and set(v) == {"name"}]
    added = sorted(k for k, v in patch.items() if v is not None and set(v) != {"name"})
    print(f"OK 既存DB『{_db_title(res)}』にスキーマ適用 (database_id={db_id})")
    if renamed:
        print(f"   列リネーム (値保持): {renamed}")
    if added:
        print(f"   追加プロパティ ({len(added)}): {added}")
    if removed:
        print(f"   削除した旧プロパティ ({len(removed)}): {removed}")
    print("   次に verify_db_schema.py で検証してください。")
    return 0


def create_database(parent, schema, token, cfg):
    props = {name: build_property(spec) for name, spec in schema["properties"].items()}
    body = {
        "parent": {"type": "page_id", "page_id": parent},
        "title": [{"text": {"content": schema["title"]}}],
        "properties": props,
    }
    res = _req("POST", "/databases", token, body)
    db_id = res["id"]
    cfg.setdefault("notion", {})["database_id"] = db_id
    cfg.setdefault("notion", {})["parent_page_id"] = parent
    save_config(cfg)
    print(f"OK DB作成完了 database_id={db_id}")
    print(f"   .mf-kessai-config.json に記録しました。次に verify_db_schema.py で検証してください。")
    return 0


def main():
    p = argparse.ArgumentParser(description="Notion 請求書チェック DB のスキーマ適用/新規作成")
    p.add_argument("--parent-page-id", help="この親ページ配下に新規 DB を作成する。指定時は既定 database_id より優先")
    a = p.parse_args()

    schema = load_schema()
    cfg = load_config()
    notion = cfg.get("notion", {})
    token = _notion_token()
    if a.parent_page_id:
        return create_database(a.parent_page_id, schema, token, cfg)
    if notion.get("database_id"):
        return ensure_schema(notion["database_id"], schema, token)
    parent = notion.get("parent_page_id")
    if not parent:
        sys.stderr.write(
            "[build_notion_db] .mf-kessai-config.json の notion.parent_page_id が空です。\n"
            "  Notionで親ページをインテグレーションに共有し、page_id を設定してください。\n"
        )
        return 2
    return create_database(parent, schema, token, cfg)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Notion 改善要望 DB へ要望を1件投入する汎用ユーティリティ。

harness-creator の run-skill-feedback (利用者が「こう直してほしい」と言ったとき発火) から呼ばれる。

Usage:
  python3 scripts/notion-submit-improvement.py \
      --title "プロンプトに具体例を追加してほしい" \
      --plugin harness-creator \
      --skill-name run-build-skill \
      --type プロンプト改善 \
      --desire "テンプレ生成時に good/bad の対比例を1つ含めてほしい" \
      --background "現状は抽象的で初学者がイメージしづらい" \
      --priority 中 --importance 高

検証:
  - --plugin で指定された名前のページがスキル一覧DBに存在しない場合、エラー終了
    (1:N relation を必ず張るため。lint-notion-relations.py が破綻を防ぐ前提)
  - --type / --priority / --importance はスキーマで定義された option 値のみ許可
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "harness-creator" / "scripts"))
import notion_config  # noqa: E402

SCHEMA_DIR = ROOT / "doc" / "notion-schema"

REQ_TYPES = ["バグ","機能追加","プロンプト改善","ドキュメント","挙動変更"]
PRIORITY  = ["高","中","低"]


def curl(method, url, token, body=None):
    cmd = ["curl","-sS","-X",method,
           "-H",f"Authorization: Bearer {token}",
           "-H","Notion-Version: 2022-06-28",
           "-H","Content-Type: application/json",
           "-w","\n__HTTP__%{http_code}", url]
    tmp=None
    if body is not None:
        tmp=tempfile.NamedTemporaryFile("w",delete=False,suffix=".json")
        json.dump(body, tmp); tmp.close()
        cmd += ["--data-binary", f"@{tmp.name}"]
    out = subprocess.check_output(cmd).decode()
    if tmp: os.unlink(tmp.name)
    payload, _, code = out.rpartition("__HTTP__")
    return int(code.strip()), (json.loads(payload) if payload.strip() else {})


def find_plugin_page(skill_list_db, plugin_name, token):
    code, data = curl("POST",
        f"https://api.notion.com/v1/databases/{skill_list_db}/query", token,
        {"filter":{"property":"プラグイン名","title":{"equals":plugin_name}}})
    if code >= 300: return None
    return data["results"][0]["id"] if data["results"] else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--plugin", required=True, help="紐づくプラグイン名 (スキル一覧の TITLE と一致)")
    ap.add_argument("--skill-name", default="", help="プラグイン内の個別スキル名 (任意)")
    ap.add_argument("--type", required=True, choices=REQ_TYPES, dest="req_type")
    ap.add_argument("--desire", required=True, help="やってほしいこと")
    ap.add_argument("--background", default="", help="背景・困っていること")
    ap.add_argument("--priority", choices=PRIORITY, default="中")
    ap.add_argument("--importance", choices=PRIORITY, default="中")
    ap.add_argument("--pr-url", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        print(json.dumps(vars(args), ensure_ascii=False, indent=2)); return

    cfg, token = notion_config.require_or_skip("improvement-request")
    if not cfg:
        return 0
    skill_list_db = notion_config.get_db_id("skill-list")
    req_db = notion_config.get_db_id("improvement-request")
    if not (skill_list_db and req_db):
        print("[SKIP] skill-list / improvement-request db_id missing in .notion-config.json")
        return 0
    plugin_page_id = find_plugin_page(skill_list_db, args.plugin, token)
    if not plugin_page_id:
        print(f"[ERR] スキル一覧に '{args.plugin}' が存在しません。先に notion-upsert-plugin.py で登録してください")
        sys.exit(2)

    props = {
        "要望タイトル": {"title":[{"text":{"content":args.title}}]},
        "対象プラグイン": {"relation":[{"id":plugin_page_id}]},
        "対象スキル名": {"rich_text":[{"text":{"content":args.skill_name}}]},
        "要望種別": {"select":{"name":args.req_type}},
        "やってほしいこと": {"rich_text":[{"text":{"content":args.desire}}]},
        "背景・困っていること": {"rich_text":[{"text":{"content":args.background}}]},
        "優先度": {"select":{"name":args.priority}},
        "重要度": {"select":{"name":args.importance}},
        "対応ステータス": {"select":{"name":"未着手"}},
    }
    if args.pr_url:
        props["関連PR/コミット"] = {"url": args.pr_url}

    code, data = curl("POST","https://api.notion.com/v1/pages", token,
                      {"parent":{"database_id":req_db},"properties":props})
    if code >= 300:
        print(f"[ERR] create: {code} {data}"); sys.exit(2)
    print(f"[CREATED] 改善要望: '{args.title}' -> {data['id']}")
    print(f"  対象プラグイン: {args.plugin} (page {plugin_page_id})")


if __name__ == "__main__":
    main()

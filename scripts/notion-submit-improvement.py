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
    """token を argv にも一時ファイルにも置かず、`--config -` で stdin から curl へ渡す。

    以前は `-H f"Authorization: Bearer {token}"` と argv に載せていた。argv は ps から見えるだけ
    でなく **`CalledProcessError.__str__()` が cmd 全体を含む**ため、呼び出し側の
    `except ... as e: print(f"...{e}")` が token を stdout へ出していた。stdout は
    run-skill-feedback の Claude が `[CREATED]` 判定のために読む経路そのもので、
    IN2 が名指しで禁じている露出先に一致する。print 側を直すのは対症療法 —
    **argv に載せない**のが唯一の根治で、以後どんな例外整形をしても漏れない。
    """
    cmd = ["curl","-sS","-X",method,
           "-H","Notion-Version: 2022-06-28",
           "-H","Content-Type: application/json",
           "-w","\n__HTTP__%{http_code}",
           "--config","-", url]
    tmp=None
    try:
        if body is not None:
            tmp=tempfile.NamedTemporaryFile("w",delete=False,suffix=".json")
            json.dump(body, tmp); tmp.close()
            cmd += ["--data-binary", f"@{tmp.name}"]
        # curl config 構文は " と \ をエスケープする。token 実体は英数字+_ だが、
        # 値の形を script 側の前提にしない (前提が破れたとき壊れるのは header 生成)。
        esc = token.replace("\\", "\\\\").replace('"', '\\"')
        out = subprocess.run(cmd, input=f'header = "Authorization: Bearer {esc}"\n'.encode(),
                             stdout=subprocess.PIPE, check=True).stdout.decode()
    finally:
        # 例外経路でも body の一時ファイルを残さない (旧実装は失敗時に leak していた)
        if tmp: os.unlink(tmp.name)
    payload, _, code = out.rpartition("__HTTP__")
    return int(code.strip()), (json.loads(payload) if payload.strip() else {})


class NotionApiError(RuntimeError):
    """API 到達・認可の失敗。『未登録』とは別事象なので同じ戻り値に潰さない。"""


def find_plugin_page(skill_list_db, plugin_name, token):
    """見つかれば page id、DB に無ければ None、API が失敗したら NotionApiError。

    以前は `code >= 300` を None に潰していたため、401/403/5xx でも「未登録」と表示され
    `--notion-register` という誤った復旧手順へ誘導していた。原因の異なる 2 事象は
    呼び出し側が別の exit code へ写像できるよう、型で区別して返す。
    """
    try:
        code, data = curl("POST",
            f"https://api.notion.com/v1/databases/{skill_list_db}/query", token,
            {"filter":{"property":"プラグイン名","title":{"equals":plugin_name}}})
    except (subprocess.CalledProcessError, OSError, ValueError) as e:
        raise NotionApiError(f"curl 失敗 (ネットワーク/実行環境): {e}") from e
    if code >= 300:
        raise NotionApiError(f"skill-list query が HTTP {code}: {data}")
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
    try:
        plugin_page_id = find_plugin_page(skill_list_db, args.plugin, token)
    except NotionApiError as e:
        # exit 3 = API 到達/認可の失敗。exit 2 (未登録) と混ぜると復旧手順を誤らせる。
        print(f"[ERR] スキル一覧 DB へ問い合わせできません: {e}")
        print("      token の有効期限・integration の DB 共有・ネットワークを確認してください "
              "(--notion-register は解決策になりません)")
        sys.exit(3)
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

    # ページ作成も API 到達/認可の失敗は exit 3。exit 2 は「入力が Notion 側の実体と噛み合っていない
    # (未登録・config 不在)」= 利用者が直せる事象に限る。ここを exit 2 のままにすると、token 失効や
    # 5xx を「登録し直せば直る」と読み違えさせる — find_plugin_page で分離した意味が消える。
    try:
        code, data = curl("POST","https://api.notion.com/v1/pages", token,
                          {"parent":{"database_id":req_db},"properties":props})
    except (subprocess.CalledProcessError, OSError, ValueError) as e:
        print(f"[ERR] 改善要望ページを作成できません: curl 失敗 (ネットワーク/実行環境): {e}")
        sys.exit(3)
    if code >= 300:
        print(f"[ERR] 改善要望ページを作成できません: create が HTTP {code}: {data}")
        print("      token の有効期限・integration の DB 共有・プロパティ名の一致を確認してください")
        sys.exit(3)
    print(f"[CREATED] 改善要望: '{args.title}' -> {data['id']}")
    print(f"  対象プラグイン: {args.plugin} (page {plugin_page_id})")


if __name__ == "__main__":
    main()

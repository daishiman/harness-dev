#!/usr/bin/env python3
"""Notion スキル一覧 DB へプラグインを冪等に upsert。

harness-creator の build 完了後フック・既存プラグインのバックフィル共通で使用。

Usage:
  python3 scripts/notion-upsert-plugin.py --plugin harness-creator
  python3 scripts/notion-upsert-plugin.py --plugin harness-creator --hearing-sheet-id <page-id>
  python3 scripts/notion-upsert-plugin.py --plugin harness-creator --dry-run

挙動:
  1. plugins/<name>/ を走査して skills/ 一覧・version (.claude-plugin/plugin.json) を取得
  2. Notion スキル一覧 DB を プラグイン名 TITLE で検索
  3. ヒット → ページプロパティ + 本文 (含まれるスキル節) を更新
     なし → 新規作成
  4. --hearing-sheet-id が指定されたら 紐づくヒアリングシート relation も埋める

冪等性: TITLE が一意キー。lint-notion-relations.py が重複検知。

Per-repo 設定: <repo-root>/.notion-config.json (gitignore対象)
  詳細: plugins/harness-creator/references/notion-per-repo-setup.md
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "harness-creator" / "scripts"))
import notion_config  # noqa: E402

SCHEMA_DIR = ROOT / "doc" / "notion-schema"


def curl(method, url, token, body=None):
    cmd = ["curl","-sS","-X",method,
           "-H",f"Authorization: Bearer {token}",
           "-H","Notion-Version: 2022-06-28",
           "-H","Content-Type: application/json",
           "-w","\n__HTTP__%{http_code}", url]
    tmp = None
    if body is not None:
        tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")
        json.dump(body, tmp); tmp.close()
        cmd += ["--data-binary", f"@{tmp.name}"]
    out = subprocess.check_output(cmd).decode()
    if tmp: os.unlink(tmp.name)
    payload, _, code = out.rpartition("__HTTP__")
    return int(code.strip()), (json.loads(payload) if payload.strip() else {})


def _parse_frontmatter(path: Path):
    """SKILL.md frontmatter (YAML) を簡易パース。description/triggers/argument-hint/kind/version 抽出。"""
    out = {"description":"", "triggers":[], "argument_hint":"", "kind":"", "version":"", "purpose":""}
    if not path.exists(): return out
    text = path.read_text()
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---": return out
    end = next((i for i,l in enumerate(lines[1:],1) if l.strip()=="---"), None)
    if end is None: return out
    fm, body = lines[1:end], "\n".join(lines[end+1:])
    in_triggers = False
    for ln in fm:
        if not in_triggers and ln.startswith("description:"):
            out["description"] = ln.split(":",1)[1].strip().strip("'\"")
        elif ln.startswith("argument-hint:"):
            out["argument_hint"] = ln.split(":",1)[1].strip().strip("'\"")
        elif ln.startswith("kind:"):
            out["kind"] = ln.split(":",1)[1].strip().strip("'\"")
        elif ln.startswith("version:"):
            out["version"] = ln.split(":",1)[1].strip().split("#")[0].strip().strip("'\"")
        elif ln.startswith("triggers:"):
            in_triggers = True
        elif in_triggers:
            stripped = ln.strip().rstrip(",")
            if stripped.startswith("- "):
                out["triggers"].append(stripped[2:].strip().strip("'\""))
            elif stripped in ("[", ""):
                pass
            elif stripped.startswith("[") and stripped.endswith("]"):
                inner = stripped[1:-1]
                for tok in inner.split(","):
                    t = tok.strip().strip("'\"")
                    if t: out["triggers"].append(t)
                in_triggers = False
            elif stripped == "]":
                in_triggers = False
            elif (stripped.startswith("'") and stripped.endswith("'")) or \
                 (stripped.startswith('"') and stripped.endswith('"')):
                out["triggers"].append(stripped.strip("'\""))
            elif ":" in stripped and not stripped.startswith("#"):
                in_triggers = False
    # body から「## Purpose」直後の最初の段落を抽出 (初心者向け説明として優先)
    body_lines = body.splitlines()
    for i, ln in enumerate(body_lines):
        if ln.startswith("## ") and ("Purpose" in ln or "purpose" in ln or "目的" in ln):
            buf = []
            for nl in body_lines[i+1:]:
                if nl.startswith("#") and buf: break
                if nl.strip(): buf.append(nl.strip())
                elif buf: break
            out["purpose"] = " ".join(buf)[:400]
            break
    return out


def scan_plugin(plugin_dir: Path):
    """plugins/<name>/ から version / skills / 詳細 frontmatter を抽出"""
    info = {"version": "", "plugin_desc": "", "skills": [], "distributable": True,
            "install_cmd": f"/plugin install {plugin_dir.name}"}
    pj = plugin_dir / ".claude-plugin" / "plugin.json"
    if not pj.exists():
        pj = plugin_dir / "plugin.json"
    if pj.exists():
        try:
            d = json.loads(pj.read_text())
            info["version"] = d.get("version", "")
            info["plugin_desc"] = d.get("description", "")
            info["distributable"] = d.get("distributable", True) is not False
        except Exception: pass
    if not info["distributable"]:
        info["install_cmd"] = "非配布: repo clone 環境で make sync を実行して利用"
    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        for s in sorted(skills_dir.iterdir()):
            if not s.is_dir(): continue
            fm = _parse_frontmatter(s / "SKILL.md")
            info["skills"].append({
                "name": s.name,
                "desc": fm["description"],
                "triggers": fm["triggers"],
                "argument_hint": fm["argument_hint"],
                "kind": fm["kind"],
                "purpose": fm["purpose"],
            })
    return info


def find_existing(db_id, plugin_name, token):
    code, data = curl("POST",
        f"https://api.notion.com/v1/databases/{db_id}/query", token,
        {"filter": {"property":"プラグイン名","title":{"equals":plugin_name}}})
    if code >= 300:
        print(f"[ERR] query: {code} {data}"); sys.exit(2)
    return data["results"][0] if data["results"] else None


def build_properties(plugin_name, info, hearing_sheet_id=None):
    props = {
        "プラグイン名": {"title":[{"text":{"content":plugin_name}}]},
        "バージョン":   {"rich_text":[{"text":{"content":info["version"]}}]},
        "概要":         {"rich_text":[{"text":{"content":f"{len(info['skills'])} skill(s)"}}]},
        "インストールコマンド": {"rich_text":[{"text":{"content":info["install_cmd"]}}]},
        "リポジトリパス": {"url": f"plugins/{plugin_name}"},
    }
    if hearing_sheet_id:
        props["紐づくヒアリングシート"] = {"relation":[{"id":hearing_sheet_id}]}
    return props


_PLUGIN_OVERVIEWS = {
    "harness-creator": "Claude Code のハーネス全体を構築・評価・統治する土台プラグイン。Skill / Agent / Hook / Command / 評価基準を束ね、要望ヒアリング→設計→生成→評価→公開までを一気通貫で支援します。",
    "skill-intake":   "ユーザーから『こんなスキルが欲しい』というふんわりした要望を受け取り、構造化されたヒアリングシートに落とすところを担当します。harness-creator の入口。",
    "prompt-creator": "スキル内で使うプロンプト(指示文)を7層構造のテンプレートに沿って作成・改善するプラグイン。プロンプトの品質と再現性を上げます。",
    "skill-governance-adapters":   "他システム(Notion・Slack・GitHub等)とスキルを繋ぐ『接続部品』を集めたプラグイン。",
    "skill-governance-automation": "スキル運用に必要な自動化(定期実行・通知・トリガ起動)を提供するプラグイン。",
    "skill-governance-config":     "スキル全体に関わる設定ファイル(allow-list, env, モデル選択等)の管理を担うプラグイン。",
    "skill-governance-hooks":      "スキルやイベントの前後で動かす『フック処理』(lint, 変更検知, ガード等)を提供するプラグイン。",
    "skill-governance-lint":       "スキルの構造・命名・記述ルール違反を機械的にチェックする検証プラグイン。",
    "skill-governance-migration":  "古いバージョンのスキル定義を新形式に移行するための変換プラグイン。",
    "skill-governance-secrets":    "API キー等のシークレット情報を安全に取り扱うための補助プラグイン。",
}


def _load_feedback_protocol():
    """skill-list.schema.json#feedback_protocol を SSOT として読む。triggers/SKILL.md/upsert が分散しないようここに一本化。"""
    sc = json.loads((SCHEMA_DIR / "skill-list.schema.json").read_text())
    fp = sc.get("feedback_protocol")
    if not fp:
        print("[ERR] skill-list.schema.json に feedback_protocol が欠落"); sys.exit(2)
    return fp


def _kind_label(k):
    return {"run":"実行系(コマンド)","ref":"参照系(資料)","assign":"評価系",
            "wrap":"ラップ系(既存に追加)","delegate":"委譲系(外部実行)"}.get(k, k or "未設定")


def build_page_children(plugin_name, info):
    """初心者にも分かるプラグイン詳細ページ。callout/heading/toggle/code を使った構造化レイアウト。"""
    def rt(text, bold=False, code=False):
        ann = {"bold":bold, "italic":False, "strikethrough":False, "underline":False, "code":code}
        return {"type":"text","text":{"content":text},"annotations":ann}
    def h2(t): return {"type":"heading_2","heading_2":{"rich_text":[rt(t)]}}
    def h3(t): return {"type":"heading_3","heading_3":{"rich_text":[rt(t)]}}
    def p(*parts):  # parts: 文字列または rt() 結果
        rich = [rt(x) if isinstance(x,str) else x for x in parts]
        return {"type":"paragraph","paragraph":{"rich_text":rich}}
    def bullet(*parts):
        rich = [rt(x) if isinstance(x,str) else x for x in parts]
        return {"type":"bulleted_list_item","bulleted_list_item":{"rich_text":rich}}
    def numbered(text):
        return {"type":"numbered_list_item","numbered_list_item":{"rich_text":[rt(text)]}}
    def code(text, lang="shell"):
        return {"type":"code","code":{"rich_text":[rt(text)],"language":lang}}
    def callout(emoji, text, color="blue_background"):
        return {"type":"callout","callout":{
            "rich_text":[rt(text)],
            "icon":{"type":"emoji","emoji":emoji},
            "color":color}}
    def toggle(title, children):
        return {"type":"toggle","toggle":{
            "rich_text":[rt(title)],
            "children":children}}
    def divider(): return {"type":"divider","divider":{}}

    overview = _PLUGIN_OVERVIEWS.get(plugin_name, info.get("plugin_desc") or
        f"{len(info['skills'])} 個のスキルをまとめたプラグインです。")

    blocks = []

    # ── ① 全体概要 (callout で目を引く) ──
    blocks.append(callout("📘", overview))

    # ── ② このプラグインで何ができる？ ──
    blocks.append(h2("🎯 このプラグインで何ができる？"))
    blocks.append(p(overview))
    if info["skills"]:
        blocks.append(p("具体的には、以下のことが可能です:"))
        for s in info["skills"][:8]:
            desc = s["desc"] or "(説明未設定)"
            blocks.append(bullet(rt(s["name"], bold=True), f" — {desc}"))
        if len(info["skills"]) > 8:
            blocks.append(p(f"…ほか {len(info['skills'])-8} スキル(下記『含まれるスキル一覧』参照)"))

    # ── ③ こんなときに使う ──
    blocks.append(h2("💡 こんなときに使う"))
    # 全スキルの triggers を集めて重複除去・最大10件表示
    all_triggers = []
    seen = set()
    for s in info["skills"]:
        for t in s["triggers"]:
            if t and t not in seen:
                seen.add(t); all_triggers.append(t)
    if all_triggers:
        blocks.append(p("以下のような状況・キーワードに当てはまったら、このプラグインを使うサインです:"))
        for t in all_triggers[:10]:
            blocks.append(bullet(f"「{t}」と感じたとき"))
    else:
        blocks.append(p("(トリガーが各スキルに設定されたら自動的にここへ表示されます)"))

    # ── ④ インストール方法 ──
    blocks.append(h2("🚀 インストール方法" if info.get("distributable", True) else "🚀 利用方法"))
    if info.get("distributable", True):
        blocks.append(p("Claude Code で以下のコマンドを実行してください:"))
    else:
        blocks.append(p("このプラグインは marketplace / bundle 配布対象外です。リポジトリを clone した開発環境で利用してください:"))
    blocks.append(code(info["install_cmd"]))
    blocks.append(callout("ℹ️",
        "Claude Code 本体が未導入の場合は先に https://claude.com/claude-code から導入してください。", "gray_background"))

    # ── ⑤ 含まれるスキル一覧 (各スキル詳細を toggle で折り畳み) ──
    blocks.append(h2("📦 含まれるスキル一覧"))
    if not info["skills"]:
        blocks.append(p("(このプラグインには個別スキルがまだ含まれていません)"))
    else:
        blocks.append(p(f"全 {len(info['skills'])} スキル。クリックで詳細を展開できます。"))
        for s in info["skills"]:
            tchildren = []
            tchildren.append(p(rt("種別: ", bold=True), _kind_label(s["kind"])))
            tchildren.append(p(rt("何をする？: ", bold=True), s["desc"] or "(説明未設定)"))
            if s["purpose"]:
                tchildren.append(p(rt("目的・出力: ", bold=True), s["purpose"]))
            if s["triggers"]:
                tchildren.append(p(rt("こんなときに使う:", bold=True)))
                for t in s["triggers"][:6]:
                    tchildren.append(bullet(t))
            tchildren.append(p(rt("使い方コマンド例:", bold=True)))
            arg = s["argument_hint"] or ""
            tchildren.append(code(f"/{s['name']} {arg}".rstrip()))
            blocks.append(toggle(f"▶ {s['name']} — {s['desc'] or '(説明未設定)'}", tchildren))

    # ── ⑥ 使い方の流れ(典型シナリオ) ──
    blocks.append(h2("📖 使い方の流れ (典型シナリオ)"))
    if info["skills"]:
        first = info["skills"][0]
        blocks.append(p("はじめての場合は、以下の順で試してみてください:"))
        blocks.append(numbered(f"Claude Code を開き、入力欄に半角スラッシュ ' / ' を打つ → 上記コマンド (例: /{first['name']}) を選択"))
        blocks.append(numbered("画面の対話に沿って質問へ回答する (キャンセルしたいときは Esc キー)"))
        blocks.append(numbered("生成された成果物・実行結果を確認し、必要なら手で微修正する"))
        blocks.append(numbered("『もっとこうしてほしい』があれば下の『改善要望の出し方』へ"))
    else:
        blocks.append(p("(個別スキル追加後にここへシナリオが入ります)"))

    # ── ⑦ 改善要望の出し方 (フィードバックループ / schema feedback_protocol が SSOT) ──
    fb = _load_feedback_protocol()
    blocks.append(h2("🔁 改善要望の出し方"))
    blocks.append(callout("✉️", fb["callout_summary"], "yellow_background"))
    blocks.append(p(rt("発火条件 (どんなときに使うか):", bold=True)))
    for cond in fb["firing_conditions"]:
        blocks.append(bullet(cond))
    blocks.append(p(rt("コマンド:", bold=True)))
    blocks.append(code(fb["command"].replace("<plugin-name>", plugin_name)))
    blocks.append(p(rt("入力する内容 (対話で順に聞かれます):", bold=True)))
    for f in fb["intake_fields"]:
        suffix = "" if f.get("required") else " (任意)"
        blocks.append(bullet(rt(f["name"], bold=True), f"{suffix}: {f['hint']}"))
    blocks.append(p(rt("投入後の流れ (約束):", bold=True)))
    blocks.append(p(fb["promise_to_reporter"]))
    blocks.append(p(rt("対応ステータスの遷移:", bold=True), " → ".join(fb["status_lifecycle"])))

    # ── ⑧ 困ったときは ──
    blocks.append(h2("❓ 困ったときは"))
    blocks.append(bullet("コマンドが見つからない: ", rt("/plugin list", code=True), " で導入済みプラグインを確認"))
    blocks.append(bullet("動作がおかしい: ", rt(f"/run-skill-feedback {plugin_name}", code=True), " で『バグ』として要望提出"))
    blocks.append(bullet("使い方が分からない: 上記『使い方の流れ』を試したうえで、", rt("/run-skill-feedback", code=True), " に『ドキュメント』種別で投げる"))

    return blocks


def replace_page_children(page_id, children, token):
    """既存子ブロックを全削除して新規追加。100件超は分割 PATCH。"""
    # delete existing (paginate)
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        if cursor: url += f"&start_cursor={cursor}"
        code, data = curl("GET", url, token)
        if code >= 300: break
        for b in data.get("results", []):
            curl("DELETE", f"https://api.notion.com/v1/blocks/{b['id']}", token)
        if not data.get("has_more"): break
        cursor = data.get("next_cursor")
    # append in chunks of 100
    for i in range(0, len(children), 100):
        chunk = children[i:i+100]
        code, _ = curl("PATCH",
            f"https://api.notion.com/v1/blocks/{page_id}/children", token,
            {"children": chunk})
        if code >= 300: return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True, help="プラグイン名 (plugins/<name>)")
    ap.add_argument("--hearing-sheet-id", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plugin_dir = ROOT / "plugins" / args.plugin
    if not plugin_dir.is_dir():
        print(f"[ERR] plugin dir not found: {plugin_dir}"); sys.exit(2)

    info = scan_plugin(plugin_dir)
    props = build_properties(args.plugin, info, args.hearing_sheet_id)
    children = build_page_children(args.plugin, info)

    if args.dry_run:
        print(json.dumps({"plugin": args.plugin, "info": info,
                          "properties_keys": list(props.keys()),
                          "children_count": len(children)}, ensure_ascii=False, indent=2))
        return

    cfg, token = notion_config.require_or_skip("skill-list")
    if not cfg:
        return 0
    db_id = notion_config.get_db_id("skill-list")
    existing = find_existing(db_id, args.plugin, token)

    if existing:
        code, _ = curl("PATCH", f"https://api.notion.com/v1/pages/{existing['id']}",
                       token, {"properties": props})
        if code >= 300: print(f"[ERR] update page: {code}"); sys.exit(2)
        replace_page_children(existing["id"], children, token)
        print(f"[UPDATED] {args.plugin} -> {existing['id']}")
    else:
        code, data = curl("POST", "https://api.notion.com/v1/pages", token,
                          {"parent":{"database_id":db_id},
                           "properties":props, "children":children})
        if code >= 300: print(f"[ERR] create page: {code} {data}"); sys.exit(2)
        print(f"[CREATED] {args.plugin} -> {data['id']}")


if __name__ == "__main__":
    main()

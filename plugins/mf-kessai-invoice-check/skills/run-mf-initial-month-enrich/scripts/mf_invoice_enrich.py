#!/usr/bin/env python3
"""初回契約月 差分エンリッチ (集中取得型の本体)。

Notion DB で管理列『初回契約月』が空の顧客だけを対象に、MFクラウド請求書APIで
取引先名を名寄せして最古 billing_date を取得し、Notion に書き込む。一度埋めた顧客は
列が非空になるため次回以降の対象から外れる(差分のみ=毎回ほぼゼロコスト)。

  --plan   : 読み取りのみ。対象顧客(未取得)を一覧表示。MFトークン不要(Notion側の検証用)。
  (既定)   : MFクラウド請求書APIで取得し Notion に書き込む(要 OAuth トークン)。
  --limit N: 1回の処理件数上限(初回の大量投入を分割するため)。

管理列『初回契約月』は掛け払いの月次 sink が空欄初期化のみ行い値には触れない列。
ここで MFクラウド請求書の最古 billing_date を初期推定値として埋める。掛け払いの月次
sink はこの管理列に触れないため、エンリッチした値が月次実行で上書きされない。
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# プラグイン root は CLAUDE_PLUGIN_ROOT 優先、無ければ __file__ から3階層上
# (skills/run-mf-initial-month-enrich/scripts → plugin root)。check_invoice_gaps.py と同型。
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))  # 共有 lib (notion_invoice_sink / mfk_api)
sys.path.insert(0, _HERE)  # 同梱スクリプト (mf_invoice_api / mf_invoice_oauth)
import notion_invoice_sink as nis  # Notion token/_req を再利用  # noqa: E402
from mfk_api import load_config  # noqa: E402
from mf_invoice_names import norm  # 名寄せ正規化の単一正本 (csv_match と共有)  # noqa: E402

AUTH_COL = "初回契約月"  # 管理列 (rich_text, YYYY-MM)。空=未取得マーカー。
TITLE_COL = "取引先企業名"
CID_COL = "顧客ID"


def _title(page):
    t = (page["properties"].get(TITLE_COL) or {}).get("title") or []
    return "".join(x.get("plain_text", "") for x in t)


def _rt(page, name):
    pr = page["properties"].get(name) or {}
    return "".join(x.get("plain_text", "") for x in (pr.get("rich_text") or []))


def query_all_pages(db, token):
    out, cur = [], None
    while True:
        body = {"page_size": 100}
        if cur:
            body["start_cursor"] = cur
        res = nis._req("POST", f"/databases/{db}/query", token, body)
        out += res.get("results", [])
        if not res.get("has_more"):
            break
        cur = res.get("next_cursor")
    return out


def needs_enrichment(page):
    """権威列が空(=未取得)の実データ顧客を対象にする。"""
    cid = _rt(page, CID_COL)
    if not cid:
        return False
    return _rt(page, AUTH_COL).strip() == ""


def main():
    p = argparse.ArgumentParser(description="初回契約月 差分エンリッチ")
    p.add_argument("--plan", action="store_true", help="対象顧客を表示のみ (MFトークン不要)")
    p.add_argument("--limit", type=int, default=0, help="処理件数上限 (0=無制限)")
    a = p.parse_args()

    token = nis._notion_token()
    db = (load_config().get("notion") or {}).get("database_id")
    if not db:
        sys.stderr.write("notion.database_id 未設定。\n")
        return 2

    pages = query_all_pages(db, token)
    # 顧客IDで重複排除 (1顧客=1ページのはずだが念のため)。
    seen, targets = set(), []
    for pg in pages:
        cid = _rt(pg, CID_COL)
        if cid in seen:
            continue
        seen.add(cid)
        if needs_enrichment(pg):
            targets.append(pg)
    if a.limit:
        targets = targets[:a.limit]

    print(f"DB総ページ: {len(pages)} / 一意顧客: {len(seen)} / 未取得(エンリッチ対象): {len(targets)}")

    if a.plan:
        print("\n[エンリッチ対象 サンプル 上位20] (管理列『初回契約月』が空の顧客)")
        for pg in targets[:20]:
            print(f"  {_title(pg)}  (cid={_rt(pg, CID_COL)})")
        print("\n--plan のため書き込みなし。MFトークン取得後、--plan を外すと実取得します。")
        return 0

    # --- 実取得 (要 OAuth トークン) ---
    import mf_invoice_api as inv
    print("MFクラウド請求書 /partners を取得して名寄せインデックスを構築中...")
    partners = inv.all_partners()
    by_norm = {}
    for pt in partners:
        by_norm.setdefault(norm(pt.get("name", "")), pt)
    print(f"  partners {len(partners)}件")

    written, unmatched, nodata = 0, [], []
    for pg in targets:
        name = _title(pg)
        pt = by_norm.get(norm(name))
        if not pt:
            unmatched.append(name)
            continue
        ym, cnt = inv.oldest_billing_month(pt.get("id"))
        if not ym:
            nodata.append(name)
            continue
        nis._req("PATCH", f"/pages/{pg['id']}", token,
                 {"properties": {AUTH_COL: {"rich_text": [{"text": {"content": ym}}]}}})
        written += 1
        print(f"  ✓ {name}: 初回契約月={ym} (請求書{cnt}件)")

    print(f"\n完了: 書込 {written} / 名寄せ失敗 {len(unmatched)} / 請求書なし {len(nodata)}")
    if unmatched:
        print("名寄せ失敗(請求書側に同名取引先なし):", unmatched[:20])
    return 0


if __name__ == "__main__":
    sys.exit(main())

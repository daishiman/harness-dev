#!/usr/bin/env python3
# /// script
# name: clear_unsupported_end_dates
# purpose: 請求確認シートで「確認内容に終了根拠が無いのに契約終了月が入っている行」を検出し、
#          契約終了月を空欄へ戻す (継続契約を終了扱いにして請求漏れを隠す状態の健全化)。dry-run 既定。
# inputs:
#   - argv: [--apply] [--sheet-db ID] [--config PATH]
#   - config: .mf-kessai-config.json (notion.sheet_db_id)
# outputs:
#   - stdout: 契約終了月の入った行数・根拠あり/なしの内訳・クリア件数
#   - exit: 0=OK / 2=fail-closed (sheet_db 欠落) / 2=apply 部分失敗
# contexts: [C, E]
# network: true   # Notion REST (read + apply時のみ write: 契約終了月 列の空欄化のみ)
# write-scope: notion(請求確認シート 契約終了月 列を空欄へ戻す) ※ --apply 時のみ
# dependencies: [notion_sheet_writeback, reconcile_invoices, notion_transport]
# requires-python: ">=3.11"
# ///
"""請求確認シート 契約終了月の健全性クリア (独立パス・dry-run 既定)。

契約終了月は、自由文からの誤推定や同一取引先伝播で「終了根拠が無いのに値が入る」と、
継続契約を終了扱いにして発行漏れを隠す。本スクリプトは確認内容に終了注記
(『（YYMM終了）』『契約終了』『請求なし』『解約』『終了月』) が無い行の契約終了月を
空欄へ戻し、人間が確認内容に終了を明記した行のみ残す。

判定基準は notion_sheet_writeback.has_end_basis に SSOT 化 (曖昧語「まで」は誤検出回避の
ため含めない)。冪等 (既にクリア済みなら対象0)・非破壊 (根拠ありの行は不可侵)・個別失敗を
握りつぶさない。既定は dry-run (集計のみ)。--apply で初めてシートを更新する。
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))

import notion_sheet_writeback  # noqa: E402
import notion_transport  # noqa: E402
import reconcile_invoices as O  # noqa: E402 (query_sheet_rows / load_orchestrator_config 再利用)


def _resolve_sheet_db(cfg, arg_sheet_db):
    """請求確認シート DB id を 引数 > 環境変数 > config(notion.sheet_db_id) の順で解決する。"""
    notion = cfg.get("notion") or {}
    return (arg_sheet_db or os.environ.get("MFK_SHEET_DB_ID")
            or notion.get("sheet_db_id") or "").strip()


def run(sheet_db, apply, req=None, token=None):
    """シート全行を取得し、根拠の無い契約終了月を検出 (apply 時は空欄へ戻す)。"""
    req = req or notion_transport._req
    token = token or notion_transport._notion_token()
    mode = "APPLY (実書き込み)" if apply else "DRY-RUN (集計のみ・書き込みなし)"
    print(f"== 契約終了月 健全性クリア sheet_db={sheet_db} mode={mode} ==")

    rows = O.query_sheet_rows(sheet_db, token, req)  # 全行 (target_ym=None)
    plan = notion_sheet_writeback.plan_unsupported_end_date_clear(rows)
    st = plan["stats"]
    print(f"[clear] シート {len(rows)}行 / 契約終了月が入っている {st['with_end']}行")
    print(f"[clear]   ├ 確認内容に終了根拠あり(残す): {st['grounded']}行")
    print(f"[clear]   └ 根拠なし(クリア対象)        : {st['unsupported']}行")

    if not apply:
        print("[clear] dry-run のため書き込みは行いません (--apply で実行)")
        return 0

    res = notion_sheet_writeback.apply_end_date_clear(plan["clears"], sheet_db, token, req)
    print(f"[clear] 契約終了月クリア: {res['cleared']}ページ / 失敗 {len(res['failed'])}")
    for f in res["failed"]:
        sys.stderr.write(f"[clear] 失敗: page_id={f['page_id']} error={f['error']}\n")
    return 0 if not res["failed"] else 2


def main(argv=None):
    p = argparse.ArgumentParser(
        description="請求確認シート 契約終了月の健全性クリア (dry-run 既定)")
    p.add_argument("--apply", action="store_true",
                   help="実書き込みを行う (既定は dry-run・集計のみ)")
    p.add_argument("--sheet-db", dest="sheet_db", help="請求確認シート DB id (config 上書き)")
    p.add_argument("--config", help="ローカル設定 JSON path (省略時は親探索)")
    a = p.parse_args(argv)

    cfg = O.load_orchestrator_config(a.config)
    sheet_db = _resolve_sheet_db(cfg, a.sheet_db)
    if not sheet_db:
        sys.stderr.write(
            "[clear] 請求確認シート DB id が解決できません。"
            ".mf-kessai-config.json の notion.sheet_db_id か --sheet-db を指定してください。\n")
        return 2
    return run(sheet_db, a.apply)


if __name__ == "__main__":
    sys.exit(main())

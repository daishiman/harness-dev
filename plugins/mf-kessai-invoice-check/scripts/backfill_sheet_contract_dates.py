#!/usr/bin/env python3
# /// script
# name: backfill_sheet_contract_dates
# purpose: 請求確認シート全行を横断し、同一取引先の契約開始日の既知値を空欄行へ
#          伝播 backfill する (複数契約で値が食い違う取引先は非伝播=conflicts)。dry-run 既定。
# inputs:
#   - argv: [--apply] [--sheet-db ID] [--config PATH]
#   - config: .mf-kessai-config.json (notion.sheet_db_id)
# outputs:
#   - stdout: 伝播対象行数・列別・競合取引先サマリ
#   - exit: 0=OK / 2=fail-closed (sheet_db 欠落) / 2=apply 部分失敗
# contexts: [C, E]
# network: true   # Notion REST (read + apply時のみ write: 契約開始日の空欄セルのみ)
# write-scope: notion(請求確認シート 契約開始日 列の空欄セルのみ) ※ --apply 時のみ
# dependencies: [notion_sheet_writeback, reconcile_invoices, notion_transport]
# requires-python: ">=3.11"
# ///
"""請求確認シート 契約開始日の同一取引先 backfill (独立パス・dry-run 既定)。

当月照合 (reconcile_invoices) のシート書き戻しとは別経路。請求確認シート全行を横断して、
同一取引先の既知の契約開始日を空欄行へ伝播する。契約終了月は自由文や同一取引先伝播で
根拠なく入ると請求漏れを隠すため、機械では伝播しない。

安全規律 (notion_sheet_writeback.plan_contract_date_propagation):
  - 取引先 (normalize で表記ゆれ吸収) 単位で group。
  - 契約開始日が正規化後ちょうど 1 種類に収束する時だけ空欄行へ伝播する。
  - 2 種類以上 (複数契約で値が食い違う) 取引先は伝播せず conflicts として可視化する。
  - 契約終了月は正当に空欄の継続契約があるため、空欄行へ伝播しない。
  - 空欄セルのみ・冪等・非破壊 (人間入力の非空値は不可侵)。
既定は dry-run (集計サマリのみ・書き込みゼロ)。--apply で初めてシートを更新する。
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
    """シート全行を取得し契約日 backfill 計画を出力 (apply 時は空欄セルへ書き込む)。"""
    req = req or notion_transport._req
    token = token or notion_transport._notion_token()
    mode = "APPLY (実書き込み)" if apply else "DRY-RUN (集計のみ・書き込みなし)"
    print(f"== 契約日 backfill sheet_db={sheet_db} mode={mode} ==")

    rows = O.query_sheet_rows(sheet_db, token, req)  # 全行 (target_ym=None)
    plan = notion_sheet_writeback.plan_contract_date_propagation(rows)
    st = plan["stats"]
    print(f"[backfill] シート {len(rows)}行 / 取引先 {st['groups']}グループ")
    print(f"[backfill] 伝播対象: 契約開始日 {st['start_filled']}セル / "
          f"契約終了月 {st['end_filled']}セル (終了月は安全のため伝播しない, 対象ページ {len(plan['updates'])}件)")
    if plan["conflicts"]:
        print(f"[backfill] 競合 (複数契約で値が食い違うため非伝播) {len(plan['conflicts'])}件:")
        for c in plan["conflicts"]:
            print(f"    取引先={c['取引先']!r} 列={c['列']} 値={c['values']}")

    if not apply:
        print("[backfill] dry-run のため書き込みは行いません (--apply で実行)")
        return 0

    res = notion_sheet_writeback.apply_contract_date_propagation(
        plan["updates"], sheet_db, token, req)
    print(f"[backfill] シート更新: 書込 {res['written']}ページ / 失敗 {len(res['failed'])}")
    for f in res["failed"]:
        sys.stderr.write(f"[backfill] 失敗: page_id={f['page_id']} error={f['error']}\n")
    return 0 if not res["failed"] else 2


def main(argv=None):
    p = argparse.ArgumentParser(
        description="請求確認シート 契約開始日の同一取引先 backfill (dry-run 既定)")
    p.add_argument("--apply", action="store_true",
                   help="実書き込みを行う (既定は dry-run・集計のみ)")
    p.add_argument("--sheet-db", dest="sheet_db", help="請求確認シート DB id (config 上書き)")
    p.add_argument("--config", help="ローカル設定 JSON path (省略時は親探索)")
    a = p.parse_args(argv)

    cfg = O.load_orchestrator_config(a.config)
    sheet_db = _resolve_sheet_db(cfg, a.sheet_db)
    if not sheet_db:
        sys.stderr.write(
            "[backfill] 請求確認シート DB id が解決できません。"
            ".mf-kessai-config.json の notion.sheet_db_id か --sheet-db を指定してください。\n")
        return 2
    return run(sheet_db, a.apply)


if __name__ == "__main__":
    sys.exit(main())

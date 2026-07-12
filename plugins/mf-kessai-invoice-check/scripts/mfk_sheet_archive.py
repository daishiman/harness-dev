#!/usr/bin/env python3
# kind: run-support
# purpose: 請求書確認シートの月次アーカイブ&ロールオーバー。対象月 (年月==YYMM) のシート行を月別 DB
#   『請求書確認シートYYMM』へ完全移行し、写像先の読み戻し検証に成功した行だけ元シートから削除する。
#   run-mf-invoice-report の --apply --verified 完了後に自動連鎖する末尾工程 (R5)。移行/検証/削除の
#   engine は lib/notion_sheet_archive.py。本 CLI は config/token/親ページ解決と二段確認ゲートを担う。
# argv: --target YYMM [--apply --verified] [--parent-page-id id] [--sheet-db id] [--config path]
# write-scope: Notion (写像先 DB 作成 + 行 upsert + 元シート行 archive)。MF は一切触らない。
# exit: 0=OK(clean/no-op) / 1=完走したが未移行行が元シートに残存(安全・要再実行) /
#       2=fail-closed(--apply に --verified 欠落 / target 不正 / sheet-db 未解決 / 新規作成の親未解決)
"""請求書確認シートの月次アーカイブ&ロールオーバー CLI。

既定は **dry-run** (Notion 書き込みゼロ・移行計画のプレビューのみ)。実移行 (写像先 DB 作成 +
行 upsert + 元シート行の archive) を伴う `--apply` は、二段確認完了を示す `--verified` を必須に
する **機械ゲート** である (未指定は exit 2)。これは prose の約束でなく本 CLI が
`--apply` かつ not `--verified` で書込を拒否する物理境界で、正本シートからの誤削除を防ぐ
(MEMORY『保証要件は機械層で担保』・notion_report_sink の --verified ゲートと同型)。

親ページ解決順 (写像先 DB を作る page_id 親):
  --parent-page-id > env MFK_ARCHIVE_PARENT_PAGE_ID > config notion.archive_parent_page
  > シート自身の親ページ (GET /databases/{sheet_db}.parent が page_id のとき) > report_parent_page
既定はシート自身の親ページ配下 (兄弟 DB として作成)。
"""
import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))

import mfk_api  # noqa: E402
import notion_transport as nt  # noqa: E402
import notion_sheet_archive as arch  # noqa: E402

_LOCAL_CONFIG = os.path.join(_PLUGIN_ROOT, ".mf-kessai-config.json")
_DEFAULT_CONFIG = os.path.join(_PLUGIN_ROOT, "mf-kessai-config.default.json")


def _load_config(explicit=None):
    """default + local の 2 層 config を読む (reconcile_invoices / build_reconcile_dbs と同一規則)。"""
    cfg = {}
    if os.path.exists(_DEFAULT_CONFIG):
        with open(_DEFAULT_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
    local_path = explicit or _LOCAL_CONFIG
    if os.path.exists(local_path):
        with open(local_path, encoding="utf-8") as f:
            cfg = mfk_api._deep_merge(cfg, json.load(f))
    return cfg


def _valid_target(target):
    """YYMM (4桁数字) か。"""
    return bool(re.fullmatch(r"\d{4}", target or ""))


def resolve_parent_page_id(meta, cfg, explicit=None):
    """写像先 DB を作る親 page_id を解決する。(page_id, source) を返す (未解決は (None, 'unresolved'))。

    順: explicit(--parent-page-id) > env > config notion.archive_parent_page
        > シート自身の親ページ (meta.parent が page_id) > config notion.report_parent_page。
    """
    notion = cfg.get("notion") or {}
    cand = (explicit or os.environ.get("MFK_ARCHIVE_PARENT_PAGE_ID")
            or notion.get("archive_parent_page"))
    if cand:
        return cand, "explicit/config"
    parent = (meta or {}).get("parent") or {}
    if parent.get("type") == "page_id" and parent.get("page_id"):
        return parent["page_id"], "sheet-parent"
    rp = notion.get("report_parent_page")
    if rp:
        return rp, "report-parent-fallback"
    return None, "unresolved"


def _print_dry_run(planned, parent_src):
    """dry-run プレビューを stdout(JSON) + 人間可読サマリで出す (書き込みゼロ)。"""
    preview = planned.get("customers_preview") or []
    summary = {
        "mode": "dry-run",
        "target_ym": planned["target_ym"],
        "source_count": planned["source_count"],
        "archive_db_title": planned["archive_db_title"],
        "archive_db_exists": planned["archive_db_exists"],
        "parent_page_id": planned["parent_page_id"],
        "parent_source": parent_src,
        "columns": planned["columns"],
        "demoted_columns": planned["demoted_columns"],
        "lossy_hold_preview": planned.get("lossy_hold_preview", 0),
        "customers_preview": preview[:10],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    n = planned["source_count"]
    if n == 0:
        sys.stderr.write(
            f"[dry-run] 対象月 {planned['target_ym']} のシート行はありません "
            "(既にアーカイブ済み or 未入力)。--apply しても no-op です。\n")
    else:
        head = "、".join(preview[:10]) + (f" 他{n - 10}件" if n > 10 else "")
        sys.stderr.write(
            f"[dry-run] {n} 行を『{planned['archive_db_title']}』へ移行し、検証後に"
            f"請求書確認シートから削除します: {head}\n"
            "  実行するには --apply --verified を付けてください。\n")
    held = planned.get("lossy_hold_preview", 0)
    if held:
        sys.stderr.write(
            f"[dry-run] うち {held} 行は添付ファイル (files) を持つためコピーのみ・元行は削除保留します "
            "(実体を text で保てないため)。\n")
    if planned["demoted_columns"]:
        sys.stderr.write(
            f"[dry-run] 型降格して text 温存する列 (Notion API で同型作成不可・集計/検索用の型は失う): "
            f"{'、'.join(planned['demoted_columns'])}\n")


def _print_apply(result):
    """apply 結果を stdout(JSON) + 人間可読サマリで出す。"""
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.stderr.write(
        f"[apply] 写像先 DB {'新規作成' if result['archive_db_created'] else '再利用'} "
        f"id={result['archive_db_id']} / 移行 {result['migrated']} / 検証OK {result['verified']} / "
        f"元シート削除 {result['archived_source']} / 未削除(温存) {len(result['failed'])}\n")
    for f in result["failed"]:
        stage = f.get("stage")
        if stage == "verify":
            cols = "、".join(m["col"] for m in f.get("mismatches", []))
            sys.stderr.write(
                f"[apply] 検証不一致で元行を温存 (削除せず): page={f['page_id']} 列=[{cols}]\n")
        elif stage == "lossy-hold":
            cols = "、".join(f.get("cols", []))
            sys.stderr.write(
                f"[apply] 添付ファイル列 [{cols}] を持つためコピーのみ・元行は温存 (削除せず): "
                f"page={f['page_id']}\n")
        else:
            sys.stderr.write(
                f"[apply] 例外で元行を温存 (削除せず): page={f['page_id']} {f.get('error', '')}\n")
    if result.get("status") == "incomplete":
        sys.stderr.write(
            f"[apply] ⚠️ 未完了: 対象 {result['source_count']} 行中 {result['archived_source']} 行のみ"
            f"削除しました。残り {len(result['failed'])} 行は元シートに温存されています "
            "(要確認・原因解消後に再実行)。これを『アーカイブ完了』と扱わないでください。\n")
    if result["archived_source"]:
        sys.stderr.write(
            "[apply] 誤削除時は Notion 各ページのゴミ箱 (trash) から 30 日以内に復元できます。\n")


def main(argv=None):
    p = argparse.ArgumentParser(
        description="請求書確認シートの月次アーカイブ&ロールオーバー (対象月行を月別 DB へ移行し元行削除)")
    p.add_argument("--target", required=True, help="対象月 YYMM (例 2606)")
    p.add_argument("--apply", action="store_true", help="実移行 (書き込み)。--verified 必須")
    p.add_argument("--verified", action="store_true",
                   help="二段確認完了フラグ。--apply と対で必須 (未指定の --apply は exit 2)")
    p.add_argument("--parent-page-id", help="写像先 DB を作る親ページ id (config/env より優先)")
    p.add_argument("--sheet-db", help="請求書確認シート DB id (config notion.sheet_db_id より優先)")
    p.add_argument("--config", help="ローカル設定 JSON path")
    a = p.parse_args(argv)

    if not _valid_target(a.target):
        sys.stderr.write(f"[fail-closed] --target は YYMM (4桁) を指定してください: {a.target!r}\n")
        return 2

    # 機械ゲート: --apply は --verified 必須 (正本シートからの誤削除を物理的に拒否)。
    if a.apply and not a.verified:
        sys.stderr.write(
            "[fail-closed] --apply には --verified が必須です (二段確認ゲート)。"
            "まず dry-run で移行計画を確認してから --apply --verified を付けてください。\n")
        return 2

    cfg = _load_config(a.config)
    sheet_db = (a.sheet_db or os.environ.get("MFK_SHEET_DB_ID")
                or (cfg.get("notion") or {}).get("sheet_db_id"))
    if not sheet_db:
        sys.stderr.write(
            "[fail-closed] 請求書確認シート DB id が未解決です "
            "(--sheet-db / env MFK_SHEET_DB_ID / config notion.sheet_db_id)。\n")
        return 2

    token = nt._notion_token(cfg)
    req = nt._req

    # ここから先の Notion I/O は予期せぬ API エラー (schema drift・権限・404 等) を traceback で
    # 落とさず fail-closed (exit 2) にする (誤って中途状態を成功扱いしない)。
    try:
        meta = req("GET", f"/databases/{sheet_db}", token)
        source_props = meta.get("properties") or {}

        # preflight: 年月 select / title 列の存在を検査 (Notion 400 の前に明示 fail-closed)。
        ok, reason = arch.preflight_source_schema(source_props)
        if not ok:
            sys.stderr.write(f"[fail-closed] 元シートのスキーマが移行要件を満たしません: {reason}\n")
            return 2

        parent, parent_src = resolve_parent_page_id(meta, cfg, a.parent_page_id)
        planned = arch.plan_archive(sheet_db, a.target, parent, source_props, token, req)

        if not a.apply:
            _print_dry_run(planned, parent_src)
            return 0

        # no-op: 対象月行が無ければ書き込まず完了 (冪等・既にアーカイブ済み)。
        if planned["source_count"] == 0:
            sys.stderr.write(
                f"[apply] 対象月 {a.target} のシート行はありません。no-op で完了します。\n")
            print(json.dumps({"mode": "apply", "target_ym": a.target, "source_count": 0,
                              "archived_source": 0, "status": "complete", "note": "no-op"},
                             ensure_ascii=False, indent=2))
            return 0

        # 新規作成が必要 (写像先 DB 未存在) なのに親未解決 → fail-closed。
        if not planned["archive_db_exists"] and not parent:
            sys.stderr.write(
                "[fail-closed] 写像先 DB の新規作成に親ページ id が必要ですが未解決です "
                "(--parent-page-id / env MFK_ARCHIVE_PARENT_PAGE_ID / config archive_parent_page / "
                "シート親 / report_parent_page)。\n")
            return 2

        result = arch.apply_archive(planned, token, req)
    except Exception as e:  # noqa: BLE001 — 予期せぬ API エラーは fail-closed で明示停止
        sys.stderr.write(f"[fail-closed] アーカイブ中に Notion API エラー: {type(e).__name__}: {e}\n")
        return 2

    _print_apply(result)
    # 未移行行が元シートに残った (検証失敗/lossy-hold/例外) → exit 1 (安全・過剰削除なし・要再実行)。
    return 1 if result["failed"] else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

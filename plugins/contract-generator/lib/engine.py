#!/usr/bin/env python3
# /// script
# name: engine
# purpose: 契約書量産の共有エンジン。--phase{draft,poll,finalize,legacy,all}でステータスマシンを駆動。各スキルから呼ばれる。
# inputs:
#   - argv: --type --phase --row --config --dry-run --allow-drift --strict
# outputs:
#   - Google Docs/PDF 生成 + Slack通知/承認検知 + 台帳書き戻し + 完了レポート
# contexts: [C, E]
# network: true
# write-scope: google-drive,google-sheets
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: オーケストレータ CLI(標準ライブラリのみ・pip不要。全責務を束ねる)。

フロー: config+auth → ensure-schema → 対象行抽出 → (validate) → docx差込 →
drift検知 → Google Docs版(黄色維持)+PDF版(黄色除去)保存 → 台帳書き戻し → レポート。

phase ハンドラは PHASE_HANDLERS dispatcher で分離(draft/poll/finalize/legacy)。
legacy は後方互換の1パス即時生成(Docs+PDF)。phase 未指定時は legacy フォールバック+
DeprecationWarning を stderr へ出す。
"""

import argparse
import os
import shutil
import sys
import tempfile
from datetime import datetime

# 同じ lib/ 内モジュールを、起動方法(任意 cwd・絶対パス起動・-m 等)に依存せず import できるよう
# 自身のディレクトリを sys.path 先頭へ明示追加する。導入後ユーザーがどこから起動しても堅牢。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import appendix  # noqa: E402
import config_auth  # noqa: E402
import docx_fill  # noqa: E402
import ledger  # noqa: E402
import render  # noqa: E402
import validate  # noqa: E402

TYPES = {"individual": "個人", "corporate": "法人"}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _filename(row, title):
    no = (row.get("No", "") or str(row.get("_row_number", ""))).strip()
    name = (row.get("乙氏名・名称") or row.get("乙法人名・名称") or "乙").strip()
    ymd = datetime.now().strftime("%Y%m%d")
    safe = name.replace("/", "_").replace(" ", "")
    return f"{no}_{safe}_業務委託契約書_{ymd}"


def _ledger_url(cfg, title):
    return f"https://docs.google.com/spreadsheets/d/{cfg['spreadsheet_id']}/edit (シート:{title})"


def _slack_ts(row):
    return (row.get("Slack_メッセージTS（自動）") or row.get("Slack_メッセージTS") or "").strip()


def _prepare_validation(ctx, row):
    """validate + 必須欠損検査の共通前処理。続行可なら (type_map, warnings, None) を返し、
    中断結果があれば (type_map, warnings, result_dict) を返す。"""
    type_map = ctx["mapping"][ctx["t_key"]]
    label = row.get("乙氏名・名称") or row.get("乙法人名・名称") or f"row{row['_row_number']}"
    errors, warnings = validate.validate_row(row, type_map)
    warnings = list(warnings)
    if ctx["t_key"] == "corporate":
        warnings.extend(appendix.appendix_warnings(row))
    missing = validate.required_missing_columns(row, type_map)
    if missing:
        msg = f"[SKIP] {label}: 必須列が空 {missing} → AskUserQuestion で補完が必要"
        if ctx["strict"]:
            raise SystemExit(msg)
        return type_map, warnings, {"row": row["_row_number"], "status": "needs-input",
                                    "missing": missing, "note": msg}
    if errors:
        return type_map, warnings, {"row": row["_row_number"], "status": "invalid", "errors": errors}
    return type_map, warnings, None


def _fill_documents(ctx, row, type_map):
    """テンプレ取得+差込。drift があれば結果を返す。OKなら (base, out_yellow, out_clean,
    drift, appendices, None) を返す。"""
    tpl = render.fetch_template(ctx["token"], ctx["cfg"]["templates_folder_id"],
                                type_map["template_name_pattern"])
    tpl_dir = os.path.dirname(tpl)
    try:
        base = _filename(row, ctx["title"])
        out_yellow = os.path.join(tempfile.gettempdir(), base + "_黄色.docx")
        out_clean = os.path.join(tempfile.gettempdir(), base + ".docx")
        post_fill = None
        appendices = []
        if ctx["t_key"] == "corporate" and appendix.needs_appendix(row):
            def post_fill(doc, _row=row, _made=appendices):
                _made.extend(appendix.append_appendices(doc, _row))
        drift, _, _ = docx_fill.fill_to_files(tpl, type_map, row, ctx["mapping"],
                                              out_yellow, out_clean, post_fill)
    finally:
        shutil.rmtree(tpl_dir, ignore_errors=True)
    if drift["leftover_markers"] and not ctx["allow_drift"]:
        return base, out_yellow, out_clean, drift, appendices, {
            "row": row["_row_number"], "status": "drift", "drift": drift,
            "note": "未置換プレースホルダ残存。scan_template.py で診断し template-mapping.json/台帳を更新。",
        }
    return base, out_yellow, out_clean, drift, appendices, None


def _handle_poll(ctx, row):
    """poll: 差込せず Slack 承認検知のみ。"""
    import slack_poll
    ts = _slack_ts(row)
    if not ts:
        return {"row": row["_row_number"], "status": "no-ts",
                "note": "Slack_メッセージTS未記録(先にdraft)"}
    approved, approver = slack_poll.check_approved(ctx["cfg"], ts)
    if approved and not ctx["dry_run"]:
        now = _now()
        ledger.writeback(ctx["token"], ctx["cfg"]["spreadsheet_id"], ctx["title"],
                         row["_row_number"],
                         {"ステータス": "approved", "承認者": approver or "",
                          "承認日時": now, "更新日時": now}, ctx["dry_run"])
    return {"row": row["_row_number"], "status": "approved" if approved else "waiting",
            "approver": approver}


def _handle_draft(ctx, row):
    """draft: Docs 黄色版のみ生成 + Slack通知 + 台帳 draft 書込。"""
    type_map, warnings, halt = _prepare_validation(ctx, row)
    if halt:
        return halt
    base, out_yellow, out_clean, drift, appendices, halt = _fill_documents(ctx, row, type_map)
    if halt:
        for p in (out_yellow, out_clean):
            try: os.unlink(p)
            except OSError: pass
        return halt
    if ctx["dry_run"]:
        for p in (out_yellow, out_clean):
            try: os.unlink(p)
            except OSError: pass
        return {"row": row["_row_number"], "status": "dry-run", "file": base,
                "drift": drift, "warnings": warnings, "appendices": appendices, "phase": "draft"}
    import slack_notify
    folder = ctx["cfg"][type_map["output_folder_key"]]
    ts = _now()
    try:
        doc_id, doc_url = render.upload_as_gdoc(ctx["token"], out_yellow, base, folder)
    finally:
        for p in (out_yellow, out_clean):
            try: os.unlink(p)
            except OSError: pass
    msg = slack_notify.build_draft_message(row, ctx["title"], doc_url,
                                           _ledger_url(ctx["cfg"], ctx["title"]),
                                           row.get("No", ""))
    slack_ts = slack_notify.post(ctx["cfg"], msg, dry_run=ctx["dry_run"])
    updates = {
        "ファイル名": base + ".docx", "契約書URL": doc_url, "ステータス": "draft",
        "冪等キー": ledger.idempotency_key(row),
        "Slack_メッセージTS": slack_ts or "", "Slack_通知日時": ts,
        "作成日時": row.get("作成日時（自動記入）") or ts, "更新日時": ts,
    }
    if appendices:
        updates["別紙URL"] = doc_url
    ledger.writeback(ctx["token"], ctx["cfg"]["spreadsheet_id"], ctx["title"],
                     row["_row_number"], updates, ctx["dry_run"])
    return {"row": row["_row_number"], "status": "draft", "file": base,
            "doc_url": doc_url, "slack_ts": slack_ts, "warnings": warnings,
            "appendices": appendices}


def _handle_finalize(ctx, row):
    """finalize: 黄色除去 PDF 生成 + Slackスレッド再共有 + 台帳 completed。"""
    type_map, warnings, halt = _prepare_validation(ctx, row)
    if halt:
        return halt
    base, out_yellow, out_clean, drift, appendices, halt = _fill_documents(ctx, row, type_map)
    if halt:
        for p in (out_yellow, out_clean):
            try: os.unlink(p)
            except OSError: pass
        return halt
    if ctx["dry_run"]:
        for p in (out_yellow, out_clean):
            try: os.unlink(p)
            except OSError: pass
        return {"row": row["_row_number"], "status": "dry-run", "file": base,
                "drift": drift, "warnings": warnings, "appendices": appendices, "phase": "finalize"}
    import slack_notify
    folder = ctx["cfg"][type_map["output_folder_key"]]
    ts = _now()
    try:
        _, pdf_url = render.store_pdf(ctx["token"], out_clean, base, folder)
    finally:
        for p in (out_yellow, out_clean):
            try: os.unlink(p)
            except OSError: pass
    slack_notify.post(ctx["cfg"], f"📄 提出用PDF(黄色除去版)を作成しました: {pdf_url}",
                      thread_ts=_slack_ts(row) or None, dry_run=ctx["dry_run"])
    updates = {"PDF_URL": pdf_url, "ステータス": "completed", "更新日時": ts}
    ledger.writeback(ctx["token"], ctx["cfg"]["spreadsheet_id"], ctx["title"],
                     row["_row_number"], updates, ctx["dry_run"])
    return {"row": row["_row_number"], "status": "completed", "file": base,
            "pdf_url": pdf_url, "warnings": warnings}


def _handle_legacy(ctx, row):
    """legacy: 後方互換の1パス即時生成(Docs黄色版 + PDF即時 + 台帳 completed)。
    呼出元が --phase を指定しない場合のフォールバック経路。テスト/単発実行で価値あり。"""
    type_map, warnings, halt = _prepare_validation(ctx, row)
    if halt:
        return halt
    base, out_yellow, out_clean, drift, appendices, halt = _fill_documents(ctx, row, type_map)
    if halt:
        for p in (out_yellow, out_clean):
            try: os.unlink(p)
            except OSError: pass
        return halt
    if ctx["dry_run"]:
        for p in (out_yellow, out_clean):
            try: os.unlink(p)
            except OSError: pass
        return {"row": row["_row_number"], "status": "dry-run", "file": base,
                "drift": drift, "warnings": warnings, "appendices": appendices, "phase": "legacy"}
    folder = ctx["cfg"][type_map["output_folder_key"]]
    ts = _now()
    try:
        doc_id, doc_url = render.upload_as_gdoc(ctx["token"], out_yellow, base, folder)
        _, pdf_url = render.store_pdf(ctx["token"], out_clean, base, folder)
    finally:
        for p in (out_yellow, out_clean):
            try: os.unlink(p)
            except OSError: pass
    updates = {
        "ファイル名": base + ".docx", "契約書URL": doc_url, "PDF_URL": pdf_url,
        "ステータス": "completed", "冪等キー": ledger.idempotency_key(row),
        "作成日時": row.get("作成日時（自動記入）") or ts, "更新日時": ts,
    }
    if appendices:
        updates["別紙URL"] = doc_url
    ledger.writeback(ctx["token"], ctx["cfg"]["spreadsheet_id"], ctx["title"],
                     row["_row_number"], updates, ctx["dry_run"])
    return {"row": row["_row_number"], "status": "completed", "file": base,
            "doc_url": doc_url, "pdf_url": pdf_url, "warnings": warnings,
            "appendices": appendices}


PHASE_HANDLERS = {
    "draft": _handle_draft,
    "poll": _handle_poll,
    "finalize": _handle_finalize,
    "legacy": _handle_legacy,
}

# phase → skill 名 (goal_seek_log のファイル分離キー)。H3: ハードコード排除。
# draft/legacy は run-contract-generate, poll/finalize は run-contract-finalize に紐づく。
PHASE_TO_SKILL = {
    "draft": "run-contract-generate",
    "legacy": "run-contract-generate",
    "poll": "run-contract-finalize",
    "finalize": "run-contract-finalize",
}


def phase_to_skill(phase):
    """phase → 所属 skill 名。ハンドラ外からも参照する単一 SSOT。"""
    return PHASE_TO_SKILL.get(phase or "legacy", "run-contract-generate")


def process_row(token, cfg, mapping, t_key, title, row, dry_run, allow_drift, strict, phase=None):
    """phase ディスパッチャ。phase=None は legacy フォールバック(DeprecationWarning)。"""
    if phase is None:
        print("[DeprecationWarning] --phase 未指定。legacy(1パス即時生成)へフォールバック。"
              "今後は --phase draft|poll|finalize|legacy を明示してください。", file=sys.stderr)
        phase = "legacy"
    handler = PHASE_HANDLERS.get(phase)
    if handler is None:
        raise SystemExit(f"unknown phase: {phase}")
    ctx = {"token": token, "cfg": cfg, "mapping": mapping, "t_key": t_key, "title": title,
           "dry_run": dry_run, "allow_drift": allow_drift, "strict": strict}
    return handler(ctx, row)


def _run_phase(token, cfg, mapping, a, phase):
    """1フェーズ分を処理して results を返す。

    H3: phase 末尾で goal_seek_log.record_iteration を呼び、skill 別ファイル
    ({skill}-progress.json / {skill}-intermediate.jsonl) に記録する。
    skill は --skill 明示があればそれを優先、未指定なら phase_to_skill(phase) で導出。
    """
    scope = ["individual", "corporate"] if a.type == "all" else [a.type]
    results = []
    for t_key in scope:
        title = TYPES[t_key]
        schema_state = getattr(a, "_schema_report", {}).get(title)
        if a.dry_run and schema_state == "would-create":
            print(f"[{title}][phase={phase or 'legacy'}] シート未作成(dry-runのため読取スキップ)")
            continue
        _, rows = ledger.read_rows(token, cfg["spreadsheet_id"], title)
        targets = ledger.select_target_rows(rows, ledger.phase_filter(phase))
        if a.row:
            targets = [r for r in targets if r["_row_number"] == a.row]
        print(f"[{title}][phase={phase or 'legacy'}] 対象 {len(targets)} 行")
        for row in targets:
            res = process_row(token, cfg, mapping, t_key, title, row,
                              a.dry_run, a.allow_drift, a.strict, phase)
            res["type"] = title
            results.append(res)
            print(f"  row{res['row']}: {res['status']}"
                  + (f" {res.get('file','')}" if res.get("file") else "")
                  + (f" 欠損={res.get('missing')}" if res.get("missing") else ""))
    import goal_seek_log
    import feedback_loop
    skill = getattr(a, "skill", None) or phase_to_skill(phase)
    goal_seek_log.record_iteration(skill, results, a.progress_dir, a.dry_run)

    # O39: 正負シグナルを feedback_loop に蓄積し次周回 directive に反映 (片肺解消)。
    # 判定根拠: phase=finalize 完了 or status=completed/approved は positive、
    # drift/invalid/needs-input/timeout/error は negative。dry-run は記録対象外。
    if not a.dry_run:
        for r in results:
            status = r.get("status")
            evidence = {"phase": phase, "row": r.get("row"), "type": r.get("type"),
                        "file": r.get("file")}
            if status in ("completed", "approved") or (
                    phase == "finalize" and status == "completed"):
                feedback_loop.record_positive(
                    skill, signal=f"{phase}:{status}", evidence=evidence,
                    eval_log_dir=a.progress_dir)
            elif status in ("drift", "invalid", "needs-input", "timeout", "error"):
                neg_evidence = dict(evidence)
                if r.get("drift"):
                    neg_evidence["drift"] = r["drift"]
                if r.get("errors"):
                    neg_evidence["errors"] = r["errors"]
                if r.get("missing"):
                    neg_evidence["missing"] = r["missing"]
                feedback_loop.record_negative(
                    skill, signal=f"{phase}:{status}", evidence=neg_evidence,
                    eval_log_dir=a.progress_dir)
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["individual", "corporate", "all"], default="all")
    p.add_argument("--phase", choices=["draft", "poll", "finalize", "legacy", "all"],
                   help="状態マシン: draft(Docs+通知)/poll(承認検知)/finalize(PDF+共有)/"
                        "legacy(後方互換の1パス即時生成: Docs+PDF同時)/all(draft→poll→finalize順次)。"
                        "未指定時は legacy にフォールバック(DeprecationWarning)")
    p.add_argument("--row", type=int, help="特定の台帳行番号のみ処理")
    p.add_argument("--config")
    p.add_argument("--dry-run", action="store_true", help="台帳書込・Drive保存をしない")
    p.add_argument("--allow-drift", action="store_true", help="未置換残存でも続行")
    p.add_argument("--strict", action="store_true", help="欠損必須列で異常終了")
    p.add_argument("--progress-dir", default="eval-log", help="ゴールシーク周回記録の出力先")
    p.add_argument("--skill", default=None,
                   help="goal_seek_log のファイル分離キー。未指定なら phase から自動導出 "
                        "(draft/legacy→run-contract-generate, poll/finalize→run-contract-finalize)")
    a = p.parse_args()

    cfg = config_auth.load_config(a.config)
    token = config_auth.get_access_token(cfg)
    mapping = docx_fill.load_mapping()

    ensure = ledger.ensure_schema(token, cfg["spreadsheet_id"], a.dry_run)
    a._schema_report = ensure
    print(f"[schema] {ensure}")

    if a.phase == "all":
        phases = ["draft", "poll", "finalize"]
    elif a.phase is None:
        print("[DeprecationWarning] --phase 未指定。legacy にフォールバック。", file=sys.stderr)
        phases = ["legacy"]
    else:
        phases = [a.phase]
    results = []
    for ph in phases:
        results.extend(_run_phase(token, cfg, mapping, a, ph))

    # サマリ
    done = sum(1 for r in results if r["status"] == "completed")
    print(f"\n=== 完了 {done}/{len(results)} ===")
    for r in results:
        if r["status"] == "completed":
            print(f"  ✅ {r['type']} row{r['row']}: {r['doc_url']}")
        elif r["status"] != "dry-run":
            print(f"  ⚠️ {r['type']} row{r['row']}: {r['status']} {r.get('note') or r.get('errors') or ''}")

    # H3: record_iteration は _run_phase 内で phase ごとに呼ぶよう移設済。
    # ここでは追加呼出しない (skill 別ファイルへの混入防止)。
    return 0


if __name__ == "__main__":
    sys.exit(main())

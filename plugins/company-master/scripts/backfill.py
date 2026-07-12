#!/usr/bin/env python3
# /// script
# name: backfill
# purpose: 企業マスタDBの空欄列・要確認行のみを対象に必要APIだけ起動し情報の確かさ付きで書き戻す(gBizINFO/Notion precondition gate + JSONL退避リプレイ)。
# inputs:
#   - argv: --dry-run (副作用抑止) / --web-findings <json> (page_id キーの属性別候補マップ。2パス運用の再投入口)
#   - config: notion_config.get_db_id("company-master") 経由 (解決順 env COMPANY_MASTER_NOTION_DATABASE_ID -> .notion-config.json -> notion-config.fixed.json)
# outputs:
#   - stdout: JSON {scanned, backfilled, deferred, needs_web_search}
#   - <repo-root|plugin-root>/eval-log/backfill-replay.jsonl (障害時退避。cwd 非依存)
#   - exit: 0=OK / 2=precondition gate or schema preflight fail-closed
# contexts: [C, E]
# network: true
# write-scope: notion,replay-log
# dependencies: []
# requires-python: ">=3.10"
# ///
"""notion-driven-backfill 責務の決定論層。

DB の空欄列・『要確認』(ネット検索(要確認)/未確定(要確認)) 行のみを対象に、空欄列ごとに
必要 API のみ起動して『情報の確かさ』付きで書き戻す。既存非空セルは上書きしない。
PATCH 前に validate_company_master.validate_row で行検証し、違反行は書かずに
deferred + replay 退避へ回す (単発 upsert と対称の検証ゲート)。
ネット検索由来値は根拠 URL をページ本文の確認用URLセクション (confirm-url-template.md 正本) へ
冪等同期し、再失敗時は『備考』を定型文言で更新する。

precondition gate (fail-closed): Notion token / gBizINFO トークン未登録は exit 2 で停止
(silent-skip 禁止)。日本郵便鍵は郵便番号取得用の任意追加設定として扱い、未設定時は郵便番号だけ
空欄 + 備考へ縮退する。外部依存障害時は取れた項目だけ書き、取れない項目は要確認とし、
中間結果を JSONL 退避して次回リプレイ可能にする (縮退設計)。

2 パス運用 (fallback tier3 = Web 検索の受け口): backfill 自体は Web 検索しない (責務分離)。
1 パス目の出力 `needs_web_search` (Claude 介入が必要な行リスト = page_id + missing_fields) を
agent が読んで Web 検索し、`--web-findings '{"<page_id>": {"phone": {"value": ..,
"source_url": ..}}}'` で再投入する。enrich 出力の missing_fields / attempts は
replay JSONL と results に併記する (gap-driven 単調前進の入力)。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# sys.path 解決の意図 (B3): このスクリプトを `python3 backfill.py` で直接起動しても
# 兄弟モジュール (notion_config 等) を import 解決できるよう、自分の親 (skill scripts/) を
# sys.path 先頭へ入れる。wrapper 経由起動時は bootstrap_plugin が同ディレクトリを既に追加済みで、
# 重複追加は bootstrap 側の `if text not in sys.path` ガードと相まって冪等 (二重化しない)。
sys.path.insert(0, str(Path(__file__).resolve().parent))
import enrich_company  # noqa: E402
import notion_config  # noqa: E402
import notion_upsert  # noqa: E402
import remarks as remarks_module  # noqa: E402
import resolve_company  # noqa: E402
import validate_company_master  # noqa: E402


def _eval_log_dir() -> Path:
    """退避ログの基底を repo-root (無ければ plugin-root) 起点で解決する。

    cwd 相対だと任意 cwd 実行・plugin 単独 install で退避先が散逸し『次回リプレイ可能』の
    工程連結が壊れるため、notion_config の root 探索ヘルパを再利用して固定する。
    """
    root = notion_config.find_repo_root() or notion_config.plugin_root()
    return root / "eval-log"


REPLAY_LOG = _eval_log_dir() / "backfill-replay.jsonl"
REQUIRE_REVERIFY_CERTAINTIES = ("ネット検索(要確認)", "未確定(要確認)")
HOJIN_BANGO_RE = re.compile(r"^\d{13}$")


def precondition_gate() -> tuple[dict, str]:
    """Notion + gBizINFO を fail-closed で検査する (build _preflight_gate と対称)。

    日本郵便鍵は郵便番号だけの供給段なので、未設定でも backfill 自体は継続する。該当列は
    `enrich_company` / `postal_api` の通常縮退により空欄 + 備考へ落とす。中央プロキシ経由
    (proxy_url 設定時) は鍵がプロキシ側にあるためローカル鍵を見ない。
    """
    cfg, token = notion_config.require_or_skip("company-master")  # Notion 不在は exit 2
    gtoken = notion_config.get_gbizinfo_token(cfg)
    if not gtoken:
        sys.stderr.write(
            "[backfill] FATAL: gBizINFO トークン不在 (Keychain "
            "'gbizinfo-api-token.<keychain-prefix>')。precondition gate fail-closed。\n"
        )
        sys.exit(2)
    if not notion_config.get_postal_proxy_url() and not notion_config.has_japanpost_credentials():
        sys.stderr.write(
            "[backfill] WARN: 日本郵便 client_id/secret_key 未設定のため、"
            "郵便番号は空欄 + 備考に縮退します "
            "(設定手順: references/japanpost-api-setup.md)。\n"
        )
    return cfg, token


def append_replay(record: dict) -> None:
    """障害時退避: 中間結果を JSONL 追記し次回リプレイ可能にする。

    郵便番号は日本郵便 API 逆引き (ローカルキャッシュ版なし) のため版情報は記録しない。
    """
    REPLAY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with REPLAY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def select_backfill_targets(rows: list[dict], migrate_company_title: bool = False) -> list[dict]:
    """空欄列を持つ or 要確認の行のみを対象に絞る。

    company_name(通称) は会社名 title へ official_name を統合した後 (R3/R4) は独立 DB 列として
    永続化されず enrich の補完対象でもないため、空欄判定から除外する (恒久的に空欄扱いされ全行が
    無限 backfill 対象化するのを防ぐ・F6)。official_name も列を持たないが row_from_page で title
    から導出されるため非空 (空欄判定に影響しない)。

    移行モード (migrate_company_title=True): 有効な法人番号 (13桁) を持つ行を対象に含める。
    正式名称列を物理削除した後は row_from_page の official_name が title (通称) へフォールバックし
    company_name と一致するため、選定段では登記名差を判定できない (列差で判定する旧経路は
    列削除後に常時 no-op 化する)。よって選定では『再 resolve で登記名を得られる行 = 法人番号保有行』
    を候補化し、登記名への上書き要否 (official != 既存 title) の冪等判定は再 resolve 後の
    patch_empty_cells に委ねる (既に title が登記名なら patch が no-op)。
    """
    targets = []
    for row in rows:
        f = row.get("fields", {})
        empty_cols = [k for k, v in f.items() if not v and k != "company_name"]
        needs_reverify = row.get("certainty") in REQUIRE_REVERIFY_CERTAINTIES
        needs_title_migration = bool(
            migrate_company_title and HOJIN_BANGO_RE.match(f.get("hojin_bango", "") or "")
        )
        if empty_cols or needs_reverify or needs_title_migration:
            targets.append({"row": row, "empty_cols": empty_cols})
    return targets


def _plain_rich_text(prop: dict) -> str:
    return "".join((x.get("plain_text") or x.get("text", {}).get("content", "")) for x in prop.get("rich_text", []))


def _plain_title(prop: dict) -> str:
    return "".join((x.get("plain_text") or x.get("text", {}).get("content", "")) for x in prop.get("title", []))


def _plain_select(prop: dict) -> str:
    return ((prop.get("select") or {}).get("name") or "")


def row_from_page(page: dict) -> dict:
    """Notion page を backfill 対象判定用の共通 row へ変換する (7 列構成・移行対応)。

    正式名称列は会社名(title)へ統合 (R4) したため、company_name は title 文字列を読む。
    official_name は best-effort で旧『正式名称』列があればそれを読むが、列を物理削除した後は
    常に空となり title へフォールバックする (= company_name と一致)。よって既存行の登記名は
    本関数からは復元できず、移行は select_backfill_targets が法人番号保有行を候補化し再 resolve
    (gBizINFO) で登記名を得てから patch_empty_cells が title を上書きする経路で行う。
    """
    props = page.get("properties", {})
    title_text = _plain_title(props.get(notion_upsert.COL_COMPANY_NAME, {}))
    legacy_official = _plain_rich_text(props.get(notion_upsert.COL_OFFICIAL_NAME, {}))
    fields = {
        "company_name": title_text,
        "official_name": legacy_official or title_text,
        "address": _plain_rich_text(props.get(notion_upsert.COL_ADDRESS, {})),
        "postal_code": _plain_rich_text(props.get(notion_upsert.COL_POSTAL, {})),
        "hojin_bango": _plain_rich_text(props.get(notion_upsert.COL_HOJIN_BANGO, {})),
        "phone_number": _plain_rich_text(props.get(notion_upsert.COL_PHONE, {})),
    }
    return {
        "page_id": page.get("id"),
        "fields": fields,
        "certainty": _plain_select(props.get(notion_upsert.COL_CERTAINTY, {})),
        "remarks_text": _plain_rich_text(props.get(notion_upsert.COL_REMARKS, {})),
    }


def query_rows(db_id: str, token: str) -> list[dict]:
    """Notion DB を全件 query し、7列共通 row に変換する (確認用URLはページ本文へ移行)。"""
    rows: list[dict] = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = notion_upsert._api("POST", f"/databases/{db_id}/query", token, body)
        rows.extend(row_from_page(p) for p in res.get("results", []))
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return rows


def resolve_row(row: dict, gtoken: str) -> dict:
    """既存 row の値から再同定する。確定できなければ entity を返さない。

    住所の出所は既存マスタ行 (address_provenance="master")。Web 検索由来住所での
    再 resolve (provenance="web") は agent 側経路の責務で、自動確定しない (信頼キー不変条項)。
    """
    f = row.get("fields", {})
    hojin = f.get("hojin_bango", "")
    name = f.get("company_name", "") or f.get("official_name", "")
    address = f.get("address", "")
    if hojin and HOJIN_BANGO_RE.match(hojin):
        return resolve_company.resolve_by_hojin_bango(hojin, gtoken)
    if name:
        return resolve_company.resolve_by_name(name, gtoken, address or None,
                                               address_provenance="master")
    if address:
        return resolve_company.resolve_by_address(address, gtoken)
    return {"certainty": "未確定(要確認)", "reason": "会社名・住所・法人番号がすべて空欄"}


def merge_entity_defaults(row: dict, resolved: dict) -> dict | None:
    """resolve 結果と既存 row を enrich 入力 entity に統合する。"""
    if "entity" not in resolved:
        return None
    f = row.get("fields", {})
    entity = dict(resolved["entity"])
    entity["company_name"] = f.get("company_name") or entity.get("official_name", "")
    # 既存住所があり、resolve 側住所が空なら既存値を使う。resolve 側がある場合は公的値を優先する。
    if not entity.get("address") and f.get("address"):
        entity["address"] = f["address"]
    for field in ("postal_code", "phone_number"):
        if f.get(field):
            entity[field] = f[field]
    # per-field provenance 伝搬: gBizINFO 法人詳細ページ URL を enrich (source_by_field) へ渡す。
    # 旧 replay の resolved/entity に source_url が無くても .get 既定で後方互換。
    entity.setdefault("source_url", resolved.get("source_url", ""))
    return entity


def validate_enriched(enriched: dict) -> list[str]:
    """PATCH 前の行検証ゲート (VERT-01 解消: 単発 upsert と対称の deterministic_checks)。

    違反理由 list を返す (空 = PASS)。違反行は PATCH せず deferred + replay 退避へ回し、
    不正形式値が『既存非空セル保護』で恒久固着する自己強化ループを断つ。
    """
    remark_phrases = set(remarks_module.load_templates().values())
    return validate_company_master.validate_row(enriched, 0, remark_phrases)


def patch_empty_cells(page_id: str, token: str, row: dict, enriched: dict, dry_run: bool,
                      migrate_company_title: bool = False) -> dict:
    """既存空欄セルだけ PATCH し、確認用URLはページ本文へ URL 非減少マージで冪等同期する。

    本文同期の入力正本は enriched.source_by_field ({field:{origin,url}})。旧形式 record は
    source_urls へフォールバック (後方互換)。今回 URL を提示できない属性の既存出典は
    sync_confirm_url_body のマージが保持する (出典 URL を本文同期で喪失させない)。
    dry-run 時は副作用を抑止し PATCH 内容だけ返す (本文同期も抑止)。

    移行モード (migrate_company_title=True): official_name(登記名) 取得済み行に限り、会社名 title を
    登記名で上書きする (title に限り既存非空セル保護を解除)。official_name 空行は触らず、住所/郵便/
    法人番号/電話の非空保護は維持し、alt_key の素材 (company_name 通称) も不変。既に title が登記名
    なら no-op (冪等)。
    """
    existing = dict(row.get("fields", {}))
    existing.update({
        "overall_certainty": row.get("certainty", ""),
        "remarks_text": row.get("remarks_text", ""),
    })
    props = notion_upsert.build_fill_empty_properties(enriched, existing)
    if migrate_company_title:
        official = (enriched.get("fields", {}) or {}).get("official_name", "")
        if official and existing.get("company_name") != official:
            # title は build_properties の SSOT (official_name 優先) で組み、会社名列のみ上書き対象に追加。
            props[notion_upsert.COL_COMPANY_NAME] = (
                notion_upsert.build_properties(enriched)[notion_upsert.COL_COMPANY_NAME])
    body = None
    if not dry_run:
        if props:
            notion_upsert._api("PATCH", f"/pages/{page_id}", token, {"properties": props})
        # 全属性出典の確認用URL本文を冪等同期 (URL 非減少マージ。失敗は呼び出し元が顕在化)。
        source = enriched.get("source_by_field") or enriched.get("source_urls", [])
        body = notion_upsert.sync_confirm_url_body(page_id, token, source)
    result = {
        "action": ("dry-run" if dry_run else ("updated" if props else "skipped")),
        "page_id": page_id,
        "patched_properties": sorted(props),
    }
    if body is not None:
        result["confirm_url_body"] = body
        result["body_sync"] = body.get("confirm_url_body", "failed")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="notion-driven backfill of company master")
    ap.add_argument("--dry-run", action="store_true", help="外部副作用を抑止して検証")
    ap.add_argument(
        "--web-findings", default=None,
        help="page_id キーの属性別候補マップ JSON (2パス運用の再投入口。"
             "例 {\"<page_id>\": {\"phone\": {\"value\": \"03-...\", \"source_url\": \"https://...\"}}})",
    )
    ap.add_argument(
        "--migrate-company-title", action="store_true",
        help="移行モード: official_name(登記名) 取得済み行の会社名 title を登記名へ上書きする "
             "(title に限り既存非空セル保護を解除。住所/郵便/法人番号/電話の保護と alt_key は不変)。"
             "--dry-run と併用で書き込まず対象だけ確認できる。",
    )
    args = ap.parse_args()
    try:
        web_findings_map = json.loads(args.web_findings) if args.web_findings else {}
        if not isinstance(web_findings_map, dict):
            raise ValueError("--web-findings は page_id キーの dict でなければならない")
    except (json.JSONDecodeError, ValueError) as e:
        sys.stderr.write(f"[backfill] FATAL: --web-findings の JSON が不正: {e}\n")
        return 2

    cfg, token = precondition_gate()
    gtoken = notion_config.get_gbizinfo_token(cfg)
    db_id = notion_config.get_db_id("company-master")

    # live スキーマ preflight (fail-closed): 列欠落・型不一致・確度 select 改名・API 不達は
    # 全行処理に入る前に exit 2 で停止 (precondition gate と同格。多重照会はプロセス内キャッシュで回避)。
    try:
        notion_upsert.ensure_schema_preflight(db_id, token)
    except notion_upsert.SchemaPreflightError as e:
        sys.stderr.write(
            "[backfill] FATAL: Notion live スキーマ preflight 失敗 (fail-closed):\n"
            + "".join(f"  - {v}\n" for v in e.violations)
        )
        return 2

    rows = query_rows(db_id, token)
    targets = select_backfill_targets(rows, migrate_company_title=args.migrate_company_title)
    results = []
    deferred = 0
    backfilled = 0
    # Claude 介入が必要な行リスト (2 パス運用の 1 パス目出力)。agent はこのリストの
    # missing_fields を Web 検索 (許可段ホワイトリスト内のみ) し、--web-findings で再投入する。
    needs_web_search: list[dict] = []

    for target in targets:
        row = target["row"]
        try:
            resolved = resolve_row(row, gtoken)
            entity = merge_entity_defaults(row, resolved)
            if not entity:
                deferred += 1
                item = {"page_id": row.get("page_id"), "status": "deferred",
                        "reason": resolved.get("reason", "一意確定不可"), "resolved": resolved}
                append_replay(item)
                results.append(item)
                continue
            enriched = enrich_company.enrich(
                entity, web_findings_map.get(row.get("page_id") or ""))
            # gap-driven 2 パス運用: 空欄のまま残った属性を Claude 介入リストへ載せる
            # (attempts 併記で agent は未試行 (source, pattern) のみ次試行できる)。
            if enriched.get("missing_fields"):
                needs_web_search.append({
                    "page_id": row.get("page_id"),
                    "missing_fields": enriched.get("missing_fields", []),
                    "attempts": enriched.get("attempts", []),
                })
            violations = validate_enriched(enriched)
            if violations:
                deferred += 1
                item = {"page_id": row.get("page_id"), "status": "deferred",
                        "reason": "validate_row 違反のため PATCH せず退避 (検証ゲート)",
                        "violations": violations, "resolved": resolved,
                        "missing_fields": enriched.get("missing_fields", []),
                        "attempts": enriched.get("attempts", [])}
                append_replay(item)
                results.append(item)
                continue
            patched = patch_empty_cells(row["page_id"], token, row, enriched, args.dry_run,
                                        migrate_company_title=args.migrate_company_title)
            if patched["action"] in {"updated", "dry-run"} and patched["patched_properties"]:
                backfilled += 1
            item = {"page_id": row.get("page_id"), "resolved": resolved, "patch": patched,
                    "missing_fields": enriched.get("missing_fields", []),
                    "attempts": enriched.get("attempts", [])}
            # 本文同期失敗は黙認せず顕在化する: action=body_failed として replay 退避し、
            # 次回実行 (sync は冪等・URL 非減少) で本文だけ再同期できるようにする。
            if patched.get("body_sync") == "failed":
                item["action"] = "body_failed"
                append_replay({
                    "page_id": row.get("page_id"), "status": "body_failed",
                    "reason": "確認用URL本文同期に失敗 (プロパティ書き込みは完了)",
                    "error": (patched.get("confirm_url_body") or {}).get("error", ""),
                    "source_by_field": enriched.get("source_by_field"),
                })
            results.append(item)
        except Exception as e:  # noqa: BLE001 - 行単位縮退が目的
            # レート制限上限超過 (NotionAPIRetryExhausted) や行処理中の中断もここで捕捉され、
            # 当該行は replay JSONL へ退避済み・処理済み行は確定済みのため、次回再実行で再開できる。
            deferred += 1
            item = {"page_id": row.get("page_id"), "status": "error", "reason": str(e)}
            append_replay(item)
            results.append(item)

    summary = {"db_id_resolved": bool(db_id), "dry_run": args.dry_run,
               "scanned": len(rows), "targets": len(targets),
               "backfilled": backfilled, "deferred": deferred,
               "needs_web_search": needs_web_search,
               "results": results}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Executable wrapper for the company-master plugin.

The skill remains the orchestration source of truth. This wrapper gives users
and slash commands a stable, self-contained Python entrypoint installed with
the plugin.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap_plugin  # noqa: E402

PLUGIN_ROOT = bootstrap_plugin.bootstrap()

import enrich_company  # noqa: E402
import notion_config  # noqa: E402
import notion_upsert  # noqa: E402
import remarks  # noqa: E402
import resolve_company  # noqa: E402
import validate_company_master  # noqa: E402


def _resolve(args: argparse.Namespace) -> dict:
    token = notion_config.get_gbizinfo_token(notion_config.load_config())
    if not token:
        sys.stderr.write(
            "[company_master] FATAL: gBizINFO トークン不在 "
            "(Keychain 'gbizinfo-api-token.<keychain-prefix>')。\n"
        )
        sys.exit(2)
    try:
        if args.hojin_bango:
            return resolve_company.resolve_by_hojin_bango(args.hojin_bango, token)
        if args.name:
            return resolve_company.resolve_by_name(
                args.name, token, args.address,
                address_provenance=getattr(args, "address_provenance", "user"))
        if args.address:
            return resolve_company.resolve_by_address(args.address, token)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"certainty": "未確定(要確認)", "reason": f"gBizINFO照会失敗: {e}"}
    sys.stderr.write("usage: --hojin-bango | --name | --address のいずれか必須\n")
    sys.exit(2)


def _preflight_gate(require_upsert: bool) -> None:
    """バックグラウンド実行前の fail-fast 検査。

    gBizINFO は企業同定の必須入力なので欠ければ exit 2 で停止する。日本郵便 API は郵便番号だけの
    供給段なので、client_id/secret_key または proxy_url が無い場合も実行は継続し、郵便番号を空欄
    + 備考へ縮退させる。送信元IP は env 未設定でも自動検出で解決するため preflight の hard-gate
    には含めない (登録IPとのズレは実行時に 401→postal_api_unauthorized 備考で surface)。
    require_upsert=True (--upsert / backfill 本実行) 時は Notion トークン + 出力先 DB ID も必須。
    """
    missing: list[str] = []
    try:
        cfg = notion_config.load_config()
    except FileNotFoundError:
        cfg = None
    if not notion_config.get_gbizinfo_token(cfg):
        missing.append("gBizINFO トークン (Keychain gbizinfo-api-token.<keychain-prefix>) — 企業同定に必須")
    if not notion_config.get_postal_proxy_url() and not notion_config.has_japanpost_credentials():
        sys.stderr.write(
            "[company_master] WARN: 日本郵便 client_id/secret_key 未設定のため、"
            "郵便番号は空欄 + 備考に縮退します "
            "(設定手順: references/japanpost-api-setup.md)。\n"
        )
    if require_upsert:
        if not notion_config.get_token(cfg):
            missing.append("Notion トークン (Keychain notion-api-key.<keychain-prefix>) — --upsert 書き込みに必須")
        if not notion_config.get_db_id("company-master"):
            missing.append("出力先 DB ID (env / .notion-config.json) — --upsert 書き込みに必須")
    if missing:
        sys.stderr.write("[company_master] FATAL: 実行前提の認証情報が不足しています:\n")
        for m in missing:
            sys.stderr.write(f"  - {m}\n")
        sys.stderr.write("  → `company_master.py doctor` で診断し、不足を解消してください。\n")
        sys.exit(2)


def run_one(args: argparse.Namespace) -> int:
    _preflight_gate(require_upsert=bool(args.upsert))
    resolved = _resolve(args)
    if "entity" not in resolved:
        print(json.dumps(
            {
                "resolved": resolved,
                "upsert": "skipped",
                "upsert_skip_reason": "resolve未確定のためupsert対象外 (entity不在)",
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    entity = dict(resolved["entity"])
    if args.name and not entity.get("company_name"):
        entity["company_name"] = args.name
    elif not entity.get("company_name"):
        entity["company_name"] = entity.get("official_name", "")
    # per-field provenance 伝搬: resolve の gBizINFO 法人詳細ページ URL を enrich へ渡す
    # (entity 内に無い旧形式 resolve 出力でも top-level source_url から補完。.get で後方互換)。
    entity.setdefault("source_url", resolved.get("source_url", ""))

    web_findings = json.loads(args.web_findings) if args.web_findings else None
    enriched = enrich_company.enrich(entity, web_findings)
    validation_errors = []
    for err in validate_company_master.validate_row(enriched, 0, set(remarks.load_templates().values())):
        validation_errors.append(err)

    result = {"resolved": resolved, "record": enriched, "validation_errors": validation_errors}
    if args.upsert:
        if validation_errors:
            result["upsert"] = "skipped-validation-failed"
            result["upsert_skip_reason"] = "検証エラーのためupsertスキップ (validation_errors を参照)"
        else:
            result["upsert"] = notion_upsert.upsert(enriched)
    else:
        result["upsert"] = "skipped"
        result["upsert_skip_reason"] = "--upsert未指定のため書き込みスキップ (resolve/enrich のみ実行)"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if validation_errors else 0


def run_backfill(args: argparse.Namespace) -> int:
    _preflight_gate(require_upsert=not args.dry_run)
    import backfill  # noqa: E402

    argv = ["backfill.py"]
    if args.dry_run:
        argv.append("--dry-run")
    # 移行モード: official_name(登記名) 取得済み行の会社名 title を登記名へ上書きする (opt-in)。
    if getattr(args, "migrate_company_title", False):
        argv.append("--migrate-company-title")
    # 2 パス運用の再投入口: 1 パス目の needs_web_search を agent が Web 検索した結果を伝搬。
    if getattr(args, "web_findings", None):
        argv += ["--web-findings", args.web_findings]
    sys.argv = argv
    return backfill.main()


# --- doctor: セットアップ一括診断 (contract-generator setup_doctor を参考に自己完結実装) ----
#
# 各項目を OK/WARN/FAIL/SKIP + 次アクション (日本語) で表示し、FAIL が 1 つでもあれば exit 1。
# 機密値 (token 平文) は一切表示しない。Notion 到達検査はトークン未設定なら SKIP (次アクション提示)。

_DOCTOR_ICON = {"OK": "OK  ", "WARN": "WARN", "FAIL": "FAIL", "SKIP": "SKIP"}


def _doctor_item(status: str, label: str, detail: str = "", next_action: str = "") -> dict:
    return {"status": status, "label": label, "detail": detail, "next_action": next_action}


def _doctor_check_keychain(cfg: dict | None) -> list[dict]:
    """(a) Keychain 2鍵の存在確認 (値は取得のみで表示しない)。"""
    items = []
    notion_service, notion_account = notion_config.credential_ref("notion-api-key")
    gbiz_service, gbiz_account = notion_config.credential_ref("gbizinfo-api-token")
    if notion_config.get_token(cfg):
        items.append(_doctor_item("OK", f"Keychain: {notion_service}", "Notion トークン取得可"))
    else:
        items.append(_doctor_item(
            "FAIL", f"Keychain: {notion_service}", "Notion トークンが取得できない",
            f"README 5-1 の手順で Keychain へ登録 (service={notion_service}, account={notion_account})",
        ))
    if notion_config.get_gbizinfo_token(cfg):
        items.append(_doctor_item("OK", f"Keychain: {gbiz_service}", "gBizINFO トークン取得可"))
    else:
        items.append(_doctor_item(
            "FAIL", f"Keychain: {gbiz_service}", "gBizINFO トークンが取得できない",
            f"README 5-2 の手順で Keychain へ登録 (service={gbiz_service}, account={gbiz_account})",
        ))
    return items


def _doctor_check_db_id(cfg: dict | None) -> tuple[list[dict], str]:
    """(b) 出力先 DB ID の解決経路 (env / .notion-config.json / fixed) を表示する。"""
    env_name = notion_config.DB_ENV_NAMES["company-master"]
    db_id = notion_config.get_db_id("company-master")
    if not db_id:
        return [_doctor_item(
            "FAIL", "出力先 DB ID", "databases.company-master.db_id を解決できない",
            f"env {env_name} を設定するか .notion-config.json / notion-config.fixed.json に db_id を記載",
        )], ""
    if os.environ.get(env_name):
        route = f"env {env_name}"
    elif cfg and cfg.get("__path__", "").endswith(notion_config.BUNDLED_CONFIG_FILENAME):
        route = f"同梱既定 {notion_config.BUNDLED_CONFIG_FILENAME} ({cfg['__path__']})"
    elif cfg:
        route = f"{notion_config.CONFIG_FILENAME} ({cfg.get('__path__', '?')})"
    else:
        route = "不明 (config 不在だが env も未設定)"
    return [_doctor_item("OK", "出力先 DB ID", f"db_id={db_id} / 解決経路: {route}")], db_id


def _doctor_check_notion_reach(db_id: str, notion_token: str | None) -> list[dict]:
    """(c) Notion API 到達 + DB アクセス + schema preflight (トークン未設定は SKIP)。"""
    if not notion_token:
        return [_doctor_item(
            "SKIP", "Notion 到達 + schema preflight", "Notion トークン未設定のため未実施",
            "README 5-1 でトークン登録後に doctor を再実行",
        )]
    if not db_id:
        return [_doctor_item(
            "SKIP", "Notion 到達 + schema preflight", "DB ID 未解決のため未実施",
            "出力先 DB ID の FAIL を先に解消",
        )]
    try:
        notion_upsert.preflight_schema(db_id, notion_token)
        return [_doctor_item(
            "OK", "Notion 到達 + schema preflight",
            "DB アクセス可・live スキーマは 7列定義 (notion-db-schema.json) と一致",
        )]
    except notion_upsert.SchemaPreflightError as e:
        return [_doctor_item(
            "FAIL", "Notion 到達 + schema preflight", "; ".join(e.violations),
            "README 5-4 の Integration 接続と、references/company-master-columns.md の7列定義に DB を合わせる",
        )]


def _settings_hardening_deny() -> list[str]:
    """配布 deny ルール正本 (references/settings-hardening.json) の deny エントリを返す。"""
    path = PLUGIN_ROOT / "references" / "settings-hardening.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return list((data.get("permissions") or {}).get("deny") or [])


def _doctor_check_settings_hardening() -> list[dict]:
    """(d) settings-hardening deny の適用有無 (静的層は深層防御のため未適用は warn 止まり)。"""
    try:
        expected = _settings_hardening_deny()
    except (OSError, json.JSONDecodeError) as e:
        return [_doctor_item("FAIL", "settings-hardening 配布物", f"references/settings-hardening.json が読めない: {e}",
                             "plugin 配布物の破損。再インストールする")]
    root = notion_config.find_repo_root() or notion_config.plugin_root()
    applied: set[str] = set()
    for name in ("settings.json", "settings.local.json"):
        p = root / ".claude" / name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        applied |= set((data.get("permissions") or {}).get("deny") or [])
    missing = [d for d in expected if d not in applied]
    if not missing:
        return [_doctor_item("OK", "settings-hardening (静的層 deny)", f"deny {len(expected)} 件適用済み ({root}/.claude)")]
    return [_doctor_item(
        "WARN", "settings-hardening (静的層 deny)",
        f"未適用 {len(missing)}/{len(expected)} 件 (動的層 hook が fail-closed で単独完結するため警告止まり)",
        "references/settings-hardening.json の deny を .claude/settings.json の permissions.deny へマージ (任意・深層防御)",
    )]


_JAPANPOST_SETUP_ACTION = (
    "references/japanpost-api-setup.md の手順で client_id/secret_key を Keychain "
    "(service=japanpost-da-api.<keychain-prefix>, account=client_id / secret_key) に登録する。"
    "送信元IPは既定で自動検出。固定が必要な場合のみ Keychain "
    "(service=japanpost-da-api.<keychain-prefix>, account=egress_ip) に pin する (env ファイルは使わない)"
)


def _japanpost_probe_item(postal_api) -> dict:
    """実 API へテスト検索し結果を 1 項目で返す (直叩き/プロキシ共通)。

    本番 (base_url 未設定) は「東京都千代田区霞が関」を検索。base_url 設定済み
    (テスト/stub 環境) は stub のテストデータ「東京都千代田区飯田橋」に切り替える。
    """
    is_stub = bool(notion_config.get_japanpost_base_url())
    query = "東京都千代田区飯田橋" if is_stub else "東京都千代田区霞が関"
    try:
        r = postal_api.lookup_postal(query)
        err = next((a for a in (r.get("attempts") or []) if a.get("result") == "error"), None)
        if err and str(err.get("reject_reason", "")).startswith("auth"):
            return _doctor_item(
                "FAIL", "日本郵便 API 実疎通", f"認証失敗: {err.get('reject_reason')}",
                "送信元IPが登録IPと一致しているか、client_id/secret_key (またはプロキシ通行トークン) が正しいか確認")
        if err:
            return _doctor_item(
                "WARN", "日本郵便 API 実疎通", f"通信障害: {err.get('reject_reason')}",
                "ネットワーク/プロキシ/日本郵便側の一時障害の可能性。時間をおいて再試行")
        value = r.get("value")
        if not value:
            # 認証/通信は成功したが候補が確定しなかった (例: 検索語が API のデータ対象外)。
            # 「テスト検索 OK」と出すと誤解を招くため WARN で明示区別する。
            return _doctor_item(
                "WARN", "日本郵便 API 実疎通",
                f"認証OKだが確定せず ({query}→候補確定せず)",
                "認証・通信は成功。検索語が API のデータ対象外の可能性 (郵便番号付与には影響なし)")
        env_note = " ※stub/テスト環境 (本番データではない)" if is_stub else ""
        return _doctor_item(
            "OK", "日本郵便 API 実疎通",
            f"テスト検索 OK ({query}→{value}){env_note}")
    except Exception as e:  # noqa: BLE001  probe の予期せぬ失敗も FAIL + 手順案内へ倒す
        return _doctor_item(
            "FAIL", "日本郵便 API 実疎通", f"予期せぬ失敗 ({type(e).__name__}: {e})",
            _JAPANPOST_SETUP_ACTION)


def _doctor_check_japanpost(probe: bool = False) -> list[dict]:
    """(e) 日本郵便 addresszip API の認証情報診断 (郵便番号逆引きの可用性)。

    client_id/secret_key (Keychain japanpost-da-api.<keychain-prefix>) の有無と、送信元IP
    (Keychain pin 優先 → env (低優先) → 自動検出) を表示する。
    BYO: 表示された送信元IP を各ユーザが日本郵便 for Biz に登録する必要がある
    (登録要否自体は --probe で確定)。郵便番号は空欄+備考へ縮退するだけなので未設定は WARN 止まり
    (FAIL にしない)。--probe 指定時のみ実 API へ token 発行 + テスト検索を試み、登録IPとのズレ
    (401/403) を FAIL として検知する (検索語は本番=霞が関 / stub 環境=飯田橋)。
    """
    import postal_api  # noqa: E402  (egress 自動検出 / probe 用。import 自体はネットを叩かない)
    items: list[dict] = []
    proxy_url = notion_config.get_postal_proxy_url()
    if proxy_url:
        # 中央プロキシモード: 鍵/IP はプロキシ側に集約。クライアントは proxy_url (+任意 token) のみ。
        items.append(_doctor_item(
            "OK", "郵便番号取得モード",
            f"中央プロキシ経由: {proxy_url} (各クライアントに日本郵便鍵/送信元IP登録は不要)"))
        if probe:
            items.append(_japanpost_probe_item(postal_api))
        else:
            items.append(_doctor_item(
                "SKIP", "日本郵便 API 実疎通", "--probe 指定時にプロキシ経由で疎通確認"))
        return items
    # proxy_url 未設定 = BYO 直結 (各メンバーが自分の client_id/secret_key + 送信元IP で日本郵便を
    # 直接叩く・チーム既定)。プロキシ分岐と対称に「郵便番号取得モード」を明示する。
    items.append(_doctor_item(
        "OK", "郵便番号取得モード",
        "BYO 直結 (自分の client_id/secret_key + 送信元IP で日本郵便 API を直接呼ぶ。チーム既定)"))
    # 接続先ホスト: base_url 上書きが stub/テスト環境を指していると「stub で通った=本番OK」と誤読されるため、
    # plain doctor (probe なし) でも本番/stub を明示する。stub の上書きは WARN で本番移行を促す。
    base_override = notion_config.get_japanpost_base_url()
    if not base_override or base_override.rstrip("/") == postal_api.BASE_URL.rstrip("/"):
        items.append(_doctor_item(
            "OK", "接続先", f"本番 {postal_api.BASE_URL}"))
    else:
        items.append(_doctor_item(
            "WARN", "接続先",
            f"stub/テスト環境に接続中: {base_override} (本番の実在企業データは引けない)",
            "本番へ戻す: security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a base_url -w "
            f"'{postal_api.BASE_URL}' (delete はフックが禁止のため上書きで戻す)"))
    has_creds = notion_config.has_japanpost_credentials()
    japanpost_service = notion_config._japanpost_service() or "japanpost-da-api.<unresolved>"
    if has_creds:
        items.append(_doctor_item(
            "OK", f"Keychain: {japanpost_service}",
            "client_id / secret_key 取得可"))
    else:
        items.append(_doctor_item(
            "WARN", f"Keychain: {japanpost_service}",
            "client_id / secret_key が取得できない (郵便番号は空欄+備考へ縮退)",
            _JAPANPOST_SETUP_ACTION))
    # 送信元IP: Keychain pin 優先 → env (低優先) → 自動検出の「実際に外へ出ていくIP」を提示する。
    # BYO ではこの IP を日本郵便 for Biz に登録する (要否は --probe で確定)。
    _EGRESS_PIN_ACTION = ("固定したい場合のみ Keychain に pin: "
                          "security add-generic-password -U -s japanpost-da-api.<keychain-prefix> -a egress_ip -w '<IP>'")
    pinned_ip = notion_config.get_japanpost_egress_ip()  # Keychain pin → env (低優先)
    detected_ip = postal_api.detect_egress_ip()
    eff_ip = pinned_ip or detected_ip
    if pinned_ip and detected_ip and pinned_ip != detected_ip:
        items.append(_doctor_item(
            "WARN", "送信元IP",
            f"pin={pinned_ip} だが実際の送信元は {detected_ip} (ズレ→認証失敗の可能性)",
            "Keychain の egress_ip を実際の送信元IP に直すか、pin を外して自動検出に任せる"))
    elif eff_ip:
        src = "Keychain pin" if pinned_ip else "自動検出"
        items.append(_doctor_item(
            "OK", "送信元IP",
            f"{eff_ip} ({src})。この IP を日本郵便 for Biz に登録してください (登録要否は --probe で確認)"))
    else:
        items.append(_doctor_item(
            "WARN", "送信元IP", "自動検出失敗 (ネット不達の可能性) かつ Keychain pin なし",
            f"ネット接続を確認する。{_EGRESS_PIN_ACTION}"))
    if not probe:
        items.append(_doctor_item(
            "SKIP", "日本郵便 API 実疎通", "--probe 指定時のみ実施 (登録IPとのズレ検知)"))
        return items
    if not has_creds:
        items.append(_doctor_item(
            "SKIP", "日本郵便 API 実疎通", "認証情報 (Keychain) 未設定のため未実施",
            "上記 WARN を解消後に doctor --probe を再実行"))
        return items
    items.append(_japanpost_probe_item(postal_api))
    return items


def doctor_checks(probe: bool = False) -> list[dict]:
    """全診断項目を実行し結果 list を返す (表示と分離してテスト可能にする)。

    probe=True で日本郵便 API の実疎通 (token 発行 + テスト検索) も実施する。
    """
    try:
        cfg = notion_config.load_config()
    except FileNotFoundError:
        cfg = None  # NOTION_CONFIG_PATH が不正でも doctor 自体は続行して各項目を診断する
    items: list[dict] = []
    items += _doctor_check_keychain(cfg)
    db_items, db_id = _doctor_check_db_id(cfg)
    items += db_items
    items += _doctor_check_notion_reach(db_id, notion_config.get_token(cfg))
    items += _doctor_check_japanpost(probe)
    items += _doctor_check_settings_hardening()
    return items


def run_doctor(args: argparse.Namespace) -> int:
    print("company-master doctor — セットアップ一括診断")
    print("=" * 56)
    items = doctor_checks(probe=getattr(args, "probe", False))
    for it in items:
        line = f"[{_DOCTOR_ICON.get(it['status'], it['status'])}] {it['label']}"
        if it["detail"]:
            line += f": {it['detail']}"
        print(line)
        if it["next_action"]:
            print(f"       → 次アクション: {it['next_action']}")
    print("=" * 56)
    fails = [it for it in items if it["status"] == "FAIL"]
    if fails:
        print(f"FAIL {len(fails)} 件。上記の次アクションを実施して doctor を再実行してください。")
        return 1
    print("FAIL なし。セットアップは整っています (WARN/SKIP は上記参照)。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="company-master executable wrapper")
    sub = parser.add_subparsers(dest="command")
    backfill_parser = sub.add_parser("backfill", help="Notion 企業マスタの空欄を backfill")
    backfill_parser.add_argument("--dry-run", action="store_true")
    backfill_parser.add_argument(
        "--migrate-company-title", action="store_true",
        help="移行モード: official_name(登記名) 取得済み行の会社名 title を登記名へ上書き "
             "(title のみ非空保護解除・alt_key 不変。--dry-run 併用で確認のみ)")
    # SUPPRESS: 未指定時に top-level --web-findings の値 (run_one 用) を上書きしない。
    backfill_parser.add_argument("--web-findings", dest="web_findings",
                                 default=argparse.SUPPRESS,
                                 help="page_id キーの属性別候補マップ JSON (2パス運用の再投入口)")
    doctor_parser = sub.add_parser(
        "doctor", help="セットアップ一括診断 (Keychain/DB ID/Notion 到達/日本郵便API/settings)")
    doctor_parser.add_argument(
        "--probe", action="store_true",
        help="日本郵便 API へ実疎通 (token 発行 + テスト検索) し登録IPとのズレを検知する")

    parser.add_argument("--hojin-bango")
    parser.add_argument("--name")
    parser.add_argument("--address")
    parser.add_argument("--address-provenance", choices=("user", "master", "web"),
                        default="user",
                        help="住所の出所。web は信頼キー不変条項により自動確定しない")
    parser.add_argument("--web-findings", help="Claude Web検索結果 JSON")
    parser.add_argument("--upsert", action="store_true", help="検証PASS時にNotionへ書き込む")
    args = parser.parse_args()
    if args.command == "backfill":
        return run_backfill(args)
    if args.command == "doctor":
        return run_doctor(args)
    return run_one(args)


if __name__ == "__main__":
    sys.exit(main())

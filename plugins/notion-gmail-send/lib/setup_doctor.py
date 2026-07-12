#!/usr/bin/env python3
# /// script
# name: setup_doctor
# purpose: notion-gmail-send のセットアップ状態 (config / Keychain / 送信ログDB ID / 任意の Gmail sendAs 実API probe) を横断診断する。
# inputs:
#   - argv: [--config <path>] [--from <addr>] [--probe] [--json]
# outputs:
#   - stdout: GateResult 一覧 / exit 0=PASS, 1=未充足, 2=設定読み込み失敗
# contexts: [C, E]
# network: true   # --probe 時のみ gmail.googleapis.com
# write-scope: none
# dependencies: ["google-auth"]
# requires-python: ">=3.9"
# ///
"""setup doctor for notion-gmail-send.

本送信は行わず、live-send preflight の前提を単独で点検する薄い入口。
`--probe` を付けた場合だけ Gmail の実 API で sendAs を検証する。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from lib import notion_config, preflight  # noqa: E402


def _result(gate: str, passed: bool, reason: str = "", action: str = "", detail: str = "") -> dict:
    return {"gate": gate, "passed": passed, "reason": reason, "action": action, "detail": detail}


def _unresolved_keys(cfg: dict) -> list[tuple[str, str]]:
    """まだ placeholder/空のままの必須キーを (path, 現在値) の一覧で返す。"""
    nc = notion_config
    src = ((cfg.get("notion_gmail_send") or {}).get("source")) or {}
    sender = ((cfg.get("notion_gmail_send") or {}).get("sender")) or {}
    checks = [
        ("databases.gmail-send-log.db_id", ((cfg.get("databases") or {}).get("gmail-send-log") or {}).get("db_id")),
        ("notion_gmail_send.source.body_db", src.get("body_db")),
        ("notion_gmail_send.source.recipient_db", src.get("recipient_db")),
        ("notion_gmail_send.sender.impersonate", sender.get("impersonate")),
    ]
    out: list[tuple[str, str]] = []
    for path, val in checks:
        if not isinstance(val, str) or not val.strip() or nc.is_placeholder_value(val):
            out.append((path, val if isinstance(val, str) else ""))
    return out


def _do_init(config_path: str | None, values: dict | None = None, force: bool = False) -> int:
    """config 不在時の前進手段。雛形を作業フォルダへ生成する (送信はしない)。

    values(非機密の DB ID / 送信元アドレス)を渡すと該当キーを実値で埋めた config を一発生成する
    (既知値からの 1 ステップ立ち上げ)。未指定キーは placeholder のまま=実値を埋めるまで dry-run も
    送信もできない (fail-closed を弱めない)。実値は gitignored .notion-config.json にのみ書き、
    example/skeleton(git 追跡) には書かない。既存 config は --force 指定時のみ上書きする。
    """
    try:
        dest = notion_config.write_skeleton(config_path, overwrite=force, values=values)
    except notion_config.ConfigError as e:
        print(f"[skip] {e}")
        existing = notion_config.find_config_path(config_path)
        if existing:
            print(f"既存 config: {existing}")
            print("既存を実値で入れ直すには --force を付ける: "
                  "doctor --init --force --body-db <id> --recipient-db <id> --log-db <id> --impersonate <addr>")
        return 0

    cfg = notion_config.load_config(str(dest))
    remaining = _unresolved_keys(cfg)
    if values:
        print(f"config を生成しました (指定値を反映): {dest}")
    else:
        print(f"placeholder config を生成しました: {dest}")
    if remaining:
        print("まだ実値が必要な項目 (placeholder のまま):")
        for path, val in remaining:
            print(f"  - {path} = {val or '(空)'}")
        print("実値を埋めるには直接編集するか、値を渡して入れ直す:")
        print("  doctor --init --force --body-db <id> --recipient-db <id> --log-db <id> --impersonate <addr>")
        print("  ※ db_id は Notion ページURL末尾の32桁。API鍵/SA鍵は config でなく Keychain に登録する。")
        print("  ※ placeholder が残る間は1通も送信できません (実値を埋めるまで fail-closed)。")
    else:
        print("必須項目が揃いました。次の手順:")
        print("  1) 認証鍵を Keychain に登録 (README『セットアップ 3. 認証鍵』)")
        print("  2) doctor で点検 → /run-notion-gmail-dry-run で送信計画を生成")
    return 0


def _print_text(results: list[dict]) -> None:
    print("notion-gmail-send setup-doctor")
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        line = f"[{mark}] {r['gate']}"
        if r.get("reason"):
            line += f" {r['reason']}"
        if r.get("detail"):
            line += f" - {r['detail']}"
        if r.get("action"):
            line += f" (next: {r['action']})"
        print(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help=".notion-config.json path")
    ap.add_argument("--from", dest="from_addr", default="", help="sendAs 検証する From。未指定時は sender.impersonate")
    ap.add_argument("--probe", action="store_true", help="Gmail 実APIで DWD/sendAs まで検証する")
    ap.add_argument("--json", action="store_true", help="結果を JSON で出力する")
    ap.add_argument("--init", action="store_true",
                    help="config 雛形を作業フォルダへ生成する (送信はしない)。値フラグ併用で実値を一発で埋める")
    ap.add_argument("--body-db", dest="body_db", help="(init) メール本文DB の id を実値で埋める")
    ap.add_argument("--recipient-db", dest="recipient_db", help="(init) メール送信先_DB の id")
    ap.add_argument("--log-db", dest="log_db", help="(init) 送信ログDB の id")
    ap.add_argument("--impersonate", dest="impersonate", help="(init) 送信元アドレス(DWD成りすまし/sendAs)")
    ap.add_argument("--force", action="store_true", help="(init) 既存 config を上書きする")
    args = ap.parse_args()

    if args.init:
        values = {k: v for k, v in {
            "body_db": args.body_db, "recipient_db": args.recipient_db,
            "log_db": args.log_db, "impersonate": args.impersonate,
        }.items() if v}
        return _do_init(args.config, values=values or None, force=args.force)

    results: list[dict] = []
    if args.config and not Path(args.config).is_file():
        results.append(_result("G0.config", False, "config_missing", "create_config",
                               f"指定パスが見つかりません: {args.config}"))
        if args.json:
            print(json.dumps({"passed": False, "results": results}, ensure_ascii=False, indent=2))
        else:
            _print_text(results)
            print("\nconfig がありません。placeholder 雛形を生成するには: doctor --init")
        return 2
    try:
        cfg = notion_config.load_config(args.config)
        config_path = notion_config.find_config_path(args.config)
        results.append(_result("G0.config", True, detail=str(config_path) if config_path else "loaded"))
    except notion_config.ConfigError as e:
        results.append(_result("G0.config", False, "config_missing", "create_config", str(e)))
        if args.json:
            print(json.dumps({"passed": False, "results": results}, ensure_ascii=False, indent=2))
        else:
            _print_text(results)
            print("\nconfig がありません。placeholder 雛形を生成するには: doctor --init")
        return 2

    try:
        log_db_id = notion_config.get_db_id("gmail-send-log", cfg)
        results.append(_result("G2.log_db", True, detail=f"db_id={log_db_id[:8]}..."))
    except notion_config.ConfigError as e:
        results.append(_result("G2.log_db", False, "log_db_id_missing", "db_setup", str(e)))

    sender = notion_config.get_sender(cfg)
    from_addr = args.from_addr or sender.get("impersonate") or ""
    results.extend(preflight.gate_g1_auth(
        cfg,
        from_addr,
        probe_api=args.probe,
        verify_from_addrs=[from_addr] if from_addr else None,
    ))

    passed = preflight.all_passed(results)
    if args.json:
        print(json.dumps({"passed": passed, "results": results}, ensure_ascii=False, indent=2))
    else:
        _print_text(results)
        if not args.probe:
            print("\nGmail の DWD/sendAs 実API確認まで行う場合は --probe を付けてください。")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

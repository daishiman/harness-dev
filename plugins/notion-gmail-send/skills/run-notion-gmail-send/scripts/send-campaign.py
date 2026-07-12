#!/usr/bin/env python3
# /// script
# name: send_campaign
# purpose: 承認済み plan.json を入力に live-send preflight(G1/G2/G3) を通し、各送信単位を Notion へ reserved 事前予約→send_guard内蔵 Gmail 送信→sent/unknown 更新する。quota安全停止・部分再開・日本語レポートを行う。
# inputs:
#   - argv: --plan <plan.json> --approved-plan-hash <h> --approved-count <n> --approved-first-to <to> [--config]
#   - keychain: notion-api-key.<keychain-prefix> / Google SA鍵
# outputs:
#   - Notion 送信ログDB 更新 + Gmail 送信 + stdout 日本語レポート
#   - exit: 0=完了(全送信orスキップ) / 1=preflight中断 / 2=設定/接続エラー / 3=quota安全停止(部分送信)
#          / 10=preview(最小確認1回の確認段・要約とCONFIRM_TOKENを出し1通も送らない) / 11=preview後にNotion変化(再確認要)
# contexts: [E, C]
# network: true   # api.notion.com + gmail.googleapis.com への HTTPS
# write-scope: external-email   # 不可逆送信。send_guard 通過時のみ
# dependencies: ["google-auth"]
# requires-python: ">=3.9"
# ///
"""live-send オーケストレーション (仕様書 §8 step5-11/§10/§11)。

承認の所在は Notion の `送信対象=✅` (データ層)。確認の重さで直交する3つの非対話モード +
後方互換の厳格対話モードを持つ:
  - 既定 (最小確認1回): 引数なしで preview (要約+CONFIRM_TOKEN を出し exit 10・送信しない) →
    R1 が人間の単一確認を取り `--confirm-token <plan_hash>` で再実行 → 新鮮 plan を再構築し
    plan_hash が token と一致する時だけ送信 (ユーザーが見た内容へ束縛)。
  - 無人確認0 (`--auto-approve`/`--yes`): cron 等。端末確認なしで送信。high 残存で fail-closed。
  - 厳格対話 (`--plan` + `--approved-*`): orchestrator(LLM) が受領した
    APPROVE <plan_hash> <count> <first_to> <確認語> を渡す読解強制モード。
いずれも送信直前に最新 Notion から新鮮 plan を構築 (fresh rebuild) し、preflight 全充足まで送信
フェーズへ進まない。send_guard は gmail_client 内部で必ず呼ばれるため、本 script が guard を
呼び忘れても送信に到達しない。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT))
from lib import (  # noqa: E402
    notion_client, notion_config, secrets, preflight,
    idempotent_log as ilog, gmail_client,
    render_substitute as rs, plan_build as pb, message_assemble as ma,
    send_guard as sg, plan_compose as pc, mail_db_audit as audit,
)


def _abort(results: list[dict]) -> int:
    print("\n❌ preflight 未充足。1通も送信していません。")
    for r in results:
        if not r["passed"]:
            print(f"  [{r['gate']}] {r['reason']} → 対応: {r['action']}  {r['detail']}")
            if r["action"] == "gcp_setup":
                print("    → doc/GCP-Gmail送信設定手順.md を参照")
            elif r["action"] == "db_setup":
                print("    → /run-notion-gmail-sendlog-setup で送信ログDBを構築")
            elif r["action"] == "fill_body":
                print("    → メッセージ対象=✅ かつ {{}}入り本文 を記入")
    return 1


def _resolve_source_dbs(cfg: dict, db1: str | None, db2: str | None) -> tuple[str, str]:
    """auto-send 用に本文DB/送信先DB を config(または override)から解決する。"""
    if not (db1 and db2):
        source = (cfg.get("notion_gmail_send") or {}).get("source") or {}
        db1 = db1 or source.get("body_db")
        db2 = db2 or source.get("recipient_db")
    if not db1 or not db2:
        raise notion_config.ConfigError(
            "body_db / recipient_db が未解決 (config notion_gmail_send.source または --db1/--db2)")
    return (notion_config.require_resolved_value(db1, "body_db"),
            notion_config.require_resolved_value(db2, "recipient_db"))


def _write_auto_plan(config_path_arg: str | None, plan: dict) -> Path:
    """auto-send が構築した新鮮 plan を監査証跡としてローカルへ書く (本文全文含むため git 外・§12)。"""
    cfgp = notion_config.find_config_path(config_path_arg)
    out = (Path(cfgp.parent if cfgp else ".") / "eval-log" / "notion-gmail-send"
           / f"plan-{plan['campaign_id']}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _auto_source_audit_gate(client, db1: str, db2: str) -> int | None:
    """無人 cron 送信 (--auto-approve/--yes) の入口ゲート。high が残れば 1 を返す (1通も送らない)。

    None を返したら通過。**人間の目視が一切ない無人実行モード限定**の fail-closed。空本文/未知トークン/
    To/From 不正・空差し込み値を行レベルで機械検出する。既定の最小確認1回モードでは全停止せず、これらの
    high を確認要約に ⚠️ 警告として列挙し人間が判断する (`_audit_warnings`)。high の各 issue は該当 unit が
    送信時に per-unit skip されるため row-isolatable だが、無人実行では「気づかぬ部分送信」を避けるため
    保守的に全停止する (原則的非対称: 人間がループに居る既定は警告・無人 cron は fail-closed)。
    """
    audit_res = audit.run_full_audit(client, db1, db2)
    if not audit_res["high"]:
        return None
    print("\n❌ source-audit: high severity の問題が残っています。無人確認0送信を中止し1通も送信していません:",
          file=sys.stderr)
    for i in audit_res["high"]:
        loc = i.get("subject") or i.get("name") or i.get("page_id") or ""
        print(f"  [{i['code']}] {i['db']}: {loc} → {i['detail']}", file=sys.stderr)
    print("\nNotion 上で修正してから再実行するか、人間が要約を見て送る既定の最小確認1回モード "
          "(引数なし→preview→確認) を使ってください (/run-notion-gmail-source-audit で全件確認できます)。",
          file=sys.stderr)
    return 1


def _audit_warnings(client, db1: str, db2: str) -> list[str]:
    """既定 (最小確認1回) の preview 用に high severity の品質問題を人間可読な1行警告へ整形する。

    無人 cron の `_auto_source_audit_gate` と異なり**送信を止めない**。各 high は該当 unit が送信時に
    per-unit skip される (row-isolatable) ため、人間が要約でこれを見た上で送信可否を判断する。
    """
    try:
        audit_res = audit.run_full_audit(client, db1, db2)
    except notion_client.NotionError:
        return []
    out: list[str] = []
    for i in audit_res["high"]:
        loc = i.get("subject") or i.get("name") or i.get("page_id") or ""
        out.append(f"[{i['code']}] {i['db']}: {loc} → {i['detail']} (該当のみ送信時 skip)")
    return out


def _rerun_flags(args) -> str:
    """preview と同じ plan を再構築するために confirm 送信で**必ず再付与すべき**フラグを文字列化する。

    --canary/--db1/--db2/--config/--allow-resend は compose 入力や送信対象に影響するため、preview 時と
    異なると新鮮 plan の plan_hash が CONFIRM_TOKEN と不一致になり exit 11 になる。preview がこの完全な
    再実行コマンドを自己記述することで、利用者が canary 等を付け忘れて token 不一致になる混乱を防ぐ。
    """
    parts: list[str] = []
    if args.canary is not None:
        parts.append(f"--canary {args.canary}")
    if args.db1:
        parts.append(f"--db1 {args.db1}")
    if args.db2:
        parts.append(f"--db2 {args.db2}")
    if args.config:
        parts.append(f"--config {args.config}")
    if args.allow_resend:
        parts.append("--allow-resend")
    return " ".join(parts)


def _print_confirm_summary(plan: dict, warnings: list[str], rerun_flags: str = "") -> None:
    """既定 (最小確認1回) の preview 要約を stdout へ出す。R1 がこれをユーザーへ提示し単一確認を取る。

    重い対話 (APPROVE+確認語の読解強制) を、`件数 + 先頭To + 本文先頭 + 抑制/skip 内訳 + ⚠️ 警告` の
    コンパクト要約 + 単一確認へ圧縮する (ユーザー選択=常に1回確認)。CONFIRM_TOKEN(=plan_hash) は送信を
    preview 内容に束縛する: send 時に新鮮 plan を再構築し plan_hash がトークンと一致する時だけ送信する。
    rerun_flags は preview と同じ plan を作るため confirm 送信で再付与すべきフラグ (canary 等)。
    """
    u0 = plan["units"][0]
    body_head = " ".join((u0.get("body") or "").split())[:80]
    subj_head = (u0.get("subject") or "")[:60]
    print("\n===== 送信内容の確認 (最小確認1回) =====")
    print(f"campaign_id : {plan['campaign_id']}")
    print(f"送信予定     : {plan['count']} 通")
    print(f"先頭To       : {plan['first_to']}")
    print(f"本文先頭     : 件名「{subj_head}」/ {body_head}…")
    print(f"抑制(送らない) {len(plan.get('suppressed', []))} / 重複除外 {len(plan.get('duplicate_dropped', []))} / "
          f"skip {len(plan.get('skipped', []))} / メール空 {len(plan.get('recipient_skipped', []))} 件")
    if plan.get("canary_applied"):
        print(f"canary       : 送信可能 {plan['available_unit_count']} 通のうち先頭 {plan['count']} 通のみ")
    if warnings:
        print(f"⚠️ source-audit warning {len(warnings)} 件 (該当宛先/本文は送信時に skip されます):")
        for w in warnings:
            print(f"   - {w}")
    print(f"\nCONFIRM_TOKEN: {plan['plan_hash']}")
    extra = (f" {rerun_flags}" if rerun_flags else "")
    print("→ この内容で送るなら、人間の確認を得た上で次を再実行してください (preview は1通も送信していません):")
    print(f"   send-campaign.py --confirm-token {plan['plan_hash']}{extra}")
    if rerun_flags:
        print(f"   ※ preview と同じ `{rerun_flags}` を必ず付けること (異なると plan が変わり token 不一致 exit 11)。")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", help="dry-run が生成した plan.json (対話モード必須)。auto モードでは内部生成のため不要")
    ap.add_argument("--approved-plan-hash", default="")
    ap.add_argument("--approved-count", type=int, default=None)
    ap.add_argument("--approved-first-to", default="")
    ap.add_argument("--approved-nonce", default="", help="承認確認語 (対話モードでプレビュー該当単位を目視確認した値)")
    ap.add_argument("--auto-approve", "--yes", dest="auto_approve", action="store_true",
                    help="確認0の非対話送信 (cron/無人自動化用)。端末確認を一切求めず、Notion のチェック"
                         "(送信対象=✅)を承認とみなし、送信直前に最新 Notion から新鮮 plan を構築して送る。"
                         "無人実行のため source-audit high 残存時は fail-closed で1通も送らない")
    ap.add_argument("--confirm-token", default="",
                    help="(既定の最小確認1回モード) 直前の preview が出した confirm token (=plan_hash)。"
                         "送信直前に新鮮 plan を再構築し plan_hash がトークンと一致する時だけ送信する "
                         "(一致しなければ内容変化として再 preview を促す)")
    ap.add_argument("--canary", "--limit", dest="canary", type=int,
                    help="(auto) 送信可能 unit を安定順先頭 N 件に限定して送る。残りは再実行で送信 "
                         "(content dedup が既送を自動 skip)")
    ap.add_argument("--db1", help="(auto) メール本文DB id (config override)")
    ap.add_argument("--db2", help="(auto) メール送信先_DB id (config override)")
    ap.add_argument("--allow-resend", action="store_true",
                    help="同一内容の既送信を意図的に再送する (既定はクロス実行の二重送信を機構で防止)")
    ap.add_argument("--config")
    args = ap.parse_args()

    if args.canary is not None and args.canary < 1:
        print("[ERROR] --canary/--limit は 1 以上を指定してください", file=sys.stderr)
        return 2

    try:
        cfg = notion_config.load_config(args.config)
    except notion_config.ConfigError as e:
        print(f"[ERROR] config 読み込み失敗: {e}", file=sys.stderr)
        return 2

    interactive = bool(args.plan)
    if interactive and (args.auto_approve or args.confirm_token):
        print("[ERROR] --plan(厳格対話モード) と --auto-approve/--confirm-token は同時指定できません", file=sys.stderr)
        return 2
    if args.auto_approve and args.confirm_token:
        print("[ERROR] --auto-approve(無人確認0) と --confirm-token(最小確認1回) は同時指定できません", file=sys.stderr)
        return 2
    if not interactive and (
        args.approved_plan_hash or args.approved_count is not None or args.approved_first_to or args.approved_nonce
    ):
        print("[ERROR] 対話モードの承認引数 (--approved-*) を使う場合は --plan を指定してください", file=sys.stderr)
        return 2

    # 3つの送信モード (確認の重さで直交):
    #   true_zero   : --auto-approve/--yes      無人 cron 確認0 (端末確認なし・high で fail-closed)
    #   confirm_send: --confirm-token <hash>     既定の最小確認1回の send 段 (preview 後・token 束縛)
    #   preview     : 引数なし                    既定の最小確認1回の確認段 (要約+token を出し送信しない)
    #   interactive : --plan + --approved-*       厳格対話 (後方互換・APPROVE+確認語の読解強制)
    true_zero = bool(args.auto_approve)
    confirm_send = bool(args.confirm_token) and not interactive
    preview = not interactive and not true_zero and not confirm_send

    if not interactive:
        # ---- 非対話3モード共通: 送信直前に最新 Notion から新鮮 plan を構築 (fresh rebuild) ----
        # 承認の所在を「端末の APPROVE 文字列」から「Notion のチェック(データ層)」へ移す。古い plan.json を
        # 使い回さない (承認後のアドレス編集による旧アドレス送信を封じる)。機械的安全層(Class A)の per-unit
        # guard loop は確認回数と独立に下で必ず効くが、auto では承認 tuple が同一プロセス内 plan からの
        # self-derive ゆえ plan_hash/件数/content_hash 照合は恒真 (改竄介在窓なし)。auto で実効する独立検証は
        # source-audit/fresh rebuild/C-1 送信時 suppress 再検証/from 検証/content dedup の各層が担う。
        try:
            db1, db2 = _resolve_source_dbs(cfg, args.db1, args.db2)
            client = notion_client.NotionClient(secrets.get_notion_api_key())
        except (notion_config.ConfigError, secrets.KeychainError) as e:
            print(f"[ERROR] 送信初期化失敗: {e}", file=sys.stderr)
            return 2
        try:
            if true_zero:
                # 無人 cron は人間の目視がないため high 残存で fail-closed (1通も送らない)。
                gate = _auto_source_audit_gate(client, db1, db2)
                if gate is not None:
                    return gate
                warnings: list[str] = []
            else:
                # 既定 (最小確認1回): high は止めず警告へ整形し要約へ出す (人間が見て判断・該当は送信時 skip)。
                warnings = _audit_warnings(client, db1, db2)
            plan = pc.compose_plan(client, db1, db2, canary=args.canary)
        except notion_client.NotionError as e:
            print(f"[ERROR] 送信事前処理失敗 (source-audit/plan 構築): {e}", file=sys.stderr)
            return 2
        out_plan = _write_auto_plan(args.config, plan)
        if plan["count"] == 0:
            print("\n送信可能 0 通でした。送信対象=✅ の宛先と、メッセージ対象=✅ かつ {{}}入り本文 を確認してください。")
            print(f"  抑制 {len(plan['suppressed'])} / 重複除外 {len(plan['duplicate_dropped'])} / "
                  f"メール空 {len(plan['recipient_skipped'])} 件")
            print(f"plan.json: {out_plan}")
            return 0
        if preview:
            # 送信せず確認要約 + CONFIRM_TOKEN(=plan_hash) を出す。R1 が人間の単一確認を取り --confirm-token で再実行。
            _print_confirm_summary(plan, warnings, _rerun_flags(args))
            return 10
        if confirm_send:
            # 単一確認後の send 段。新鮮 plan の plan_hash が token と一致する時だけ送る (preview 内容へ束縛)。
            # 不一致=preview 後に Notion が変化 → 送らず再 preview を促す (見た物と byte 等価な物だけ送る)。
            if plan["plan_hash"] != args.confirm_token:
                print(f"\n⚠️ 内容が変わりました。preview 時の CONFIRM_TOKEN ({args.confirm_token}) と"
                      f"現在の新鮮 plan の plan_hash ({plan['plan_hash']}) が不一致です。"
                      f"再度 preview して内容を確認してください (1通も送信していません)。", file=sys.stderr)
                return 11
            print(f"[confirm-send] 最小確認1回: campaign={plan['campaign_id']} 送信予定 {plan['count']} 通 "
                  f"(CONFIRM_TOKEN 一致を確認)")
        else:  # true_zero
            print(f"[auto-approve] 無人確認0送信: campaign={plan['campaign_id']} plan_hash={plan['plan_hash']} "
                  f"送信予定 {plan['count']} 通 (Notion 送信対象=✅ を承認とみなす)")
        if plan["canary_applied"]:
            print(f"canary: 送信可能 {plan['available_unit_count']} 通のうち先頭 {plan['count']} 通のみ送信。"
                  f"残りは再実行で送信 (dedup が既送を skip)。")
        # 承認 tuple を新鮮 plan から self-derive (人間 APPROVE 入力の代替。Notion チェック=承認)。
        approved_plan_hash = plan["plan_hash"]
        approved_count = plan["count"]
        approved_first_to = plan["first_to"]
        approved_nonce_in = ""        # nonce(読解強制) は非対話モードで撤去 → guard で照合しない
        enforce_nonce = False
    else:
        # ---- 厳格対話モード (後方互換): plan.json + APPROVE <plan_hash> <count> <first_to> <確認語> ----
        if not args.approved_plan_hash or args.approved_count is None or not args.approved_first_to:
            print("[ERROR] 厳格対話モードは --approved-plan-hash/--approved-count/--approved-first-to が必要です",
                  file=sys.stderr)
            return 2
        try:
            plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[ERROR] plan 読み込み失敗: {e}", file=sys.stderr)
            return 2
        approved_plan_hash = args.approved_plan_hash
        approved_count = args.approved_count
        approved_first_to = args.approved_first_to
        approved_nonce_in = args.approved_nonce
        enforce_nonce = True

    units = plan.get("units", [])

    # ---- 決定論セルフチェック ----
    # plan.json の自己申告スカラ (count/first_to/plan_hash) を信じず、units から再計算して
    # 承認値・plan 宣言値の三者一致を fail-closed で確認する。1つでも崩れたら1通も送らない。
    # 【保護価値の所在 (正直化)】厳格対話モードでは plan.json がディスク経由の非信頼アーティファクトのため、
    # この再計算照合が plan 改竄/件数偽装を実際に捕捉する (信頼境界を跨ぐ)。非対話 (preview/confirm/auto) では
    # 承認値が同一プロセス内の新鮮 plan からの self-derive ゆえ三者は恒真で、ここでの照合と下の per-unit
    # content_hash 再計算は「将来のリファクタが compose 後に units を変異させた場合の保険 (compose バグ検出)」
    # = defense-in-depth に留まる (改竄介在窓がないため "plan 改竄検出" の保護価値は持たない)。非対話で実効
    # する独立検証は source-audit/fresh rebuild/C-1 送信時 suppress 再検証/from 検証/content dedup の各層。
    det_errors: list[str] = []
    recomputed_ph = pb.plan_hash(units) if units else ""
    recomputed_first_to = units[0]["to_list"][0] if units and units[0].get("to_list") else ""
    expected_nonce_idx, expected_nonce = pb.approval_nonce(plan.get("plan_hash", ""), units)
    nonce_for_guard = expected_nonce if enforce_nonce else ""   # 確認0モードは nonce 照合を無効化
    if recomputed_ph != plan.get("plan_hash"):
        det_errors.append("units から再計算した plan_hash が plan.json の値と不一致 (plan 改竄/破損)")
    if plan.get("plan_hash") != approved_plan_hash:
        det_errors.append("plan.json の plan_hash が承認 plan_hash と不一致")
    if len(units) != plan.get("count"):
        det_errors.append(f"units 実数({len(units)}) が plan.count({plan.get('count')}) と不一致")
    if len(units) != approved_count:
        det_errors.append(f"units 実数({len(units)}) が承認件数({approved_count}) と不一致")
    if recomputed_first_to != (approved_first_to or ""):
        det_errors.append("units 先頭 To が承認先頭 To と不一致")
    if enforce_nonce and expected_nonce and approved_nonce_in != expected_nonce:
        det_errors.append("承認確認語(nonce)が plan から計算した値と不一致 (プレビュー未確認の疑い)")
    if det_errors:
        print("\n❌ 決定論セルフチェック失敗。1通も送信していません:")
        for e in det_errors:
            print(f"  - {e}")
        return 1
    # ---- G2 依存実体 ----
    # 本文 true 行数は plan が保持する値を正本とする。len(units) は本文×宛先の直積後件数で、
    # 宛先0件や全skip時に「本文無し(no_body)」と誤誘導するため母数に使わない (plan が無い旧版のみ fallback)。
    bodies_true = plan.get("body_true_count", len(units))
    g2 = preflight.gate_g2_dependencies(cfg, bodies_true_count=bodies_true)
    # ---- G1 認証 (実API probe) ----
    from_addr0 = units[0]["from_addr"] if units else (notion_config.get_sender(cfg).get("impersonate") or "")
    # 複数本文が異なる From を持ちうるため、先頭だけでなく全 distinct From を sendAs 検証する (preflight 網羅性)。
    distinct_from = list(dict.fromkeys(u["from_addr"] for u in units)) or [from_addr0]
    g1 = preflight.gate_g1_auth(cfg, from_addr0, probe_api=True, verify_from_addrs=distinct_from)
    # ---- G3 キャンペーン整合 (self-report でなく units 実体から) ----
    g3 = preflight.gate_g3_presend(
        approved_plan_hash=approved_plan_hash, plan_hash=recomputed_ph,
        approved_count=approved_count, actual_count=len(units),
        approved_first_to=approved_first_to, actual_first_to=recomputed_first_to,
    )
    all_results = g1 + g2 + [g3]
    if not preflight.all_passed(all_results):
        return _abort(all_results)

    try:
        log_db_id = notion_config.get_db_id("gmail-send-log", cfg)
        client = notion_client.NotionClient(secrets.get_notion_api_key())
        sender = notion_config.get_sender(cfg)
        sa = sender.get("sa_keychain") or {}
        sa_key = secrets.get_google_sa_key(sa.get("service"), sa.get("account"))
        impersonate = sender.get("impersonate") or from_addr0
        gclient = gmail_client.GmailClient(sa_key, impersonate)
        # 送信時 suppress 再検証 (C-1): dry-run 承認後に Notion で「メールを送らない=✅」や
        # 「送信対象=☐」に変えられた宛先へ追い越し送信しないよう、plan の宛先 page を再取得して
        # 現在の送信可否を引く。subtract-only (承認件数を超えて送ることは決してない)。
        # C-1 再検証は plan 構築元の宛先DBに束縛する。--db2 override や対話planで config と
        # 異なるDBを使った場合に、別DBのチェック状態で送信可否を判断しないため。
        recipient_db = (plan.get("source") or {}).get("recipient_db")
        if not recipient_db:
            recipient_db = ((cfg.get("notion_gmail_send") or {}).get("source") or {}).get("recipient_db")
        if not recipient_db and not interactive:
            # F8 fail-closed: 非対話(auto/confirm/cron)は compose が source を必ず設定するため未解決は起きない。
            # 万一未解決なら C-1 送信時 suppress 再検証が不能 → 送信時抑制を取りこぼすため fail-closed で中止。
            # (厳格対話は plan が source を欠いても cfg フォールバック＋人間の dry-run 目視があるため best-effort)
            print("[ERROR] recipient_db 未解決のため送信時 suppress 再検証 (C-1) ができません。送信を中止します。",
                  file=sys.stderr)
            return 2
        suppress_state = notion_client.fetch_recipient_send_state(client, recipient_db) if recipient_db else None
    except (notion_config.ConfigError, secrets.KeychainError, gmail_client.GmailUnavailable, notion_client.NotionError) as e:
        print(f"[ERROR] live-send 初期化失敗: {e}", file=sys.stderr)
        return 2

    verified_from: dict[str, bool] = {}
    tally: Counter = Counter()
    details: list[str] = []

    resend_cid = plan["campaign_id"] if args.allow_resend else None
    for u in units:
        # 送信単位の自己検証 (F2/F8): content_hash を再計算し plan の宣言値と照合、
        # 送信バイト列 raw は plan の値を信用せずフィールドから都度再生成する。
        recomputed_ch = pb.content_hash(u)
        # dedup キーは content ベース (campaign_id 非依存)。再計算 content_hash で再導出する。
        key = pb.dedup_key(u["body_page_id"], u["recipient_page_id"], recomputed_ch, resend_campaign_id=resend_cid)
        fields = {
            "idempotency_key": key, "campaign_id": plan["campaign_id"], "plan_hash": plan["plan_hash"],
            "content_hash": recomputed_ch, "body_page_id": u["body_page_id"],
            "recipient_page_id": u["recipient_page_id"], "from_addr": u["from_addr"],
            "to_list": u["to_list"], "cc_list": u["cc_list"], "subject": u["subject"],
        }
        # 送信時 suppress 再検証 (C-1): 承認後に「メールを送らない=✅」or「送信対象=☐」へ変更された宛先は送らない。
        if suppress_state is not None:
            st = suppress_state.get(u["recipient_page_id"])
            if st is None or st["do_not_send"] or not st["send_target"]:
                ilog.mark_skipped(client, log_db_id, fields, "send_suppressed")
                tally["skipped_validation"] += 1
                reason = "宛先削除/取得不可" if st is None else ("メールを送らない=✅" if st["do_not_send"] else "送信対象=☐")
                details.append(f"[send_suppressed] {u['subject']} → {u['to_list']} (承認後に{reason}・送信せず)")
                continue
        if recomputed_ch != u.get("content_hash"):
            # plan 内の content_hash と再計算が不一致 = plan 改変。送信せず skipped_validation で記録。
            ilog.mark_skipped(client, log_db_id, {**fields, "content_hash": u.get("content_hash", "")}, "content_hash_mismatch")
            tally["skipped_validation"] += 1
            details.append(f"[content_hash_mismatch] {u['subject']} → {u['to_list']} (plan 改変の疑い・送信せず)")
            continue
        # 送信バイト列を都度再生成 (raw を plan に依存させない)
        asm = ma.assemble(u["subject"], u["body"], u["from_addr"],
                          ", ".join(u["to_list"]), ", ".join(u["cc_list"]))
        if asm["raw"] is None:
            ilog.mark_skipped(client, log_db_id, fields, "invalid_addr_at_send")
            tally["skipped_validation"] += 1
            details.append(f"[invalid_addr] {u['subject']} → {u['to_list']} ({asm['invalid_addrs']})")
            continue
        raw = asm["raw"]

        # 事前予約
        try:
            rsv = ilog.reserve(client, log_db_id, fields)
        except notion_client.NotionError as e:
            tally["error"] += 1
            details.append(f"[error] {key[:40]}… reserve失敗: {e}")
            continue
        if rsv["action"] == "duplicate":
            tally["duplicate_log_key"] += 1
            details.append(f"[duplicate_log_key] {u['subject']} → {u['to_list']} (ログ行 {rsv['matched']} 件・自動送信せず)")
            continue
        if rsv["action"] == "skip":
            tally["skipped_idempotent"] += 1
            continue
        if rsv["action"] == "skip_manual":
            tally["needs_reconcile" if rsv["status"] == ilog.UNKNOWN else "skipped_existing"] += 1
            details.append(f"[{rsv['status']}] {u['subject']} → {u['to_list']} (自動再送せず)")
            continue

        reserved_id = rsv["page_id"]
        # 送信直前の二段確認(決定論版): 未置換トークン再検査 + sendAs 検証 + 承認 nonce
        unresolved = rs.find_unresolved_tokens(u["subject"]) + rs.find_unresolved_tokens(u["body"])
        fa = u["from_addr"]
        if fa not in verified_from:
            verified_from[fa] = gclient.verify_sendas(fa)
        guard_kwargs = dict(
            approved_plan_hash=approved_plan_hash, plan_hash=recomputed_ph,
            approved_count=approved_count, actual_count=len(units),
            approved_first_to=approved_first_to, actual_first_to=recomputed_first_to,
            reserved_log_id=reserved_id, unresolved_tokens=unresolved,
            from_verified=verified_from[fa],
            approved_nonce=approved_nonce_in, actual_nonce=nonce_for_guard,
        )
        # F13: guard を mark_sending の前に明示実行し、guard 違反では SENDING を作らない。
        try:
            sg.check(**guard_kwargs)
        except gmail_client.SendGuardError as e:
            ilog.mark_error(client, reserved_id, e.code, str(e))
            tally["skipped_validation"] += 1
            details.append(f"[guard:{e.code}] {u['subject']} → {u['to_list']}")
            continue

        try:
            ilog.mark_sending(client, reserved_id)
            message_id = gclient.send_unit(raw, **guard_kwargs)  # send_unit 内で guard 再実行 (多層防御)
        except gmail_client.SendGuardError as e:  # 多層防御で再検出した場合
            ilog.mark_error(client, reserved_id, e.code, str(e))
            tally["skipped_validation"] += 1
            details.append(f"[guard:{e.code}] {u['subject']} → {u['to_list']}")
            continue
        except gmail_client.QuotaStopped as e:
            # サーバ拒否=未送信確定。当該単位を reserved へ戻し次回自動再開 (F4)。
            ilog.mark_reserved(client, reserved_id, reason_code="quota_stopped")
            ilog.append_journal(plan["campaign_id"], {"event": "quota_stopped", "key": key})
            tally["quota_stopped"] += 1
            details.append(f"[quota_stopped] {e} — 当該単位を reserved へ戻し次回再開")
            break
        except gmail_client.SendOutcomeUnknown as e:
            # 送信成否不明。自動再送禁止 → unknown_needs_reconcile (F3/F9)。
            ilog.append_journal(plan["campaign_id"], {"event": "send_outcome_unknown", "key": key, "detail": str(e)})
            ilog.mark_unknown(client, reserved_id, f"send outcome unknown: {type(e).__name__}")
            tally["unknown_needs_reconcile"] += 1
            details.append(f"[unknown_needs_reconcile] {u['subject']} → {u['to_list']} (送信成否不明・手動照合要)")
            continue
        except Exception as e:  # 送信前にサーバ拒否が確定した 4xx 等 → 未送信扱い
            ilog.mark_error(client, reserved_id, "send_failed", type(e).__name__)
            tally["error"] += 1
            details.append(f"[error] {u['subject']} → {u['to_list']}: {type(e).__name__}")
            continue

        # 送信成功 → ログ更新。失敗時は unknown_needs_reconcile + journal
        try:
            ilog.mark_sent(client, reserved_id, message_id)
            tally["sent"] += 1
        except notion_client.NotionError:
            ilog.append_journal(plan["campaign_id"], {"event": "send_success_log_failed", "key": key, "messageId": message_id, "plan_hash": plan["plan_hash"]})
            try:
                ilog.mark_unknown(client, reserved_id, "sent but log update failed")
            except notion_client.NotionError:
                pass
            tally["unknown_needs_reconcile"] += 1
            details.append(f"[unknown_needs_reconcile] {u['subject']} → 送信済だがログ更新失敗。手動照合要")

    # ---- レポート ----
    plan_skipped = len(plan.get("skipped", []))
    plan_suppressed = len(plan.get("suppressed", []))
    plan_dup_dropped = len(plan.get("duplicate_dropped", []))
    print("\n===== 送信レポート =====")
    print(f"campaign_id : {plan['campaign_id']}")
    print(f"送信 (sent) : {tally['sent']}")
    print(f"dry-run 抑制 (メールを送らない): {plan_suppressed} / 重複除外 (プロ人材最新created_time1件): {plan_dup_dropped}")
    print(f"冪等スキップ (skipped_idempotent): {tally['skipped_idempotent']}")
    print(f"検証スキップ (dry-run skipped_validation): {plan_skipped}")
    print(f"送信前ガード除外 (skipped_validation): {tally['skipped_validation']}")
    print(f"既存予約・自動再送せず: {tally['skipped_existing']}")
    print(f"失敗 (error) : {tally['error'] + tally['duplicate_log_key']}")
    print(f"要照合 (unknown_needs_reconcile): {tally['unknown_needs_reconcile'] + tally['needs_reconcile']}")
    if tally["quota_stopped"]:
        print("⚠️ quota 安全停止しました。再実行で残件 (reserved) を継続します。")
    if details:
        print("\n--- 内訳 ---")
        for d in details:
            print(" " + d)
    print("\n注意: status=sent は Gmail API 受理であり受信者への到達保証ではありません。")
    return 3 if tally["quota_stopped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

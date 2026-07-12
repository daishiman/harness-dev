#!/usr/bin/env python3
# /// script
# name: sync
# purpose: run-template-sync のエントリ。ひな形変更を検知し、影響行に再生成フラグを立てて未作成へ差し戻す。
# inputs:
#   - argv: --type {individual,corporate,all} --config --docx(任意) --dry-run --apply
# outputs:
#   - ひな形差分レポート(MISSING/UNMAPPED) + (--apply時)completed行を未作成へ差し戻し
# contexts: [C, E]
# network: true
# write-scope: google-sheets
# dependencies: []
# requires-python: ">=3.11"
# ///
"""run-template-sync(ひな形変更追従責務)のエントリ。

「ひな形が変わった」という明示意図でのみ発火する独立スキル(誤発火・常時発火を防ぐ)。
1) scan_template でひな形と template-mapping.json の差分(MISSING/UNMAPPED)を診断。
2) --apply 時、該当タイプの completed 行に再生成フラグを立て ステータスを未作成へ差し戻す
   (→次回 run-contract-generate(draft) で作り直し対象になる)。
共有ライブラリ lib を呼ぶ。
"""

import argparse
import os
import sys

LIB = os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib")
sys.path.insert(0, os.path.abspath(LIB))

import config_auth  # noqa: E402
import ledger  # noqa: E402
import scan_template  # noqa: E402

TYPES = {"individual": "個人", "corporate": "法人"}


def _scan(t_key, cfg_path):
    """scan_template.main 相当を呼び exit code(0=整合/5=drift)を返す。"""
    argv = ["scan_template", "--type", t_key]
    if cfg_path:
        argv += ["--config", cfg_path]
    old = sys.argv
    sys.argv = argv
    try:
        return scan_template.main()
    finally:
        sys.argv = old


def _flag_regen(token, cfg, title, dry_run):
    """completed 行に再生成フラグを立て、ステータスを未作成へ差し戻す。

    REST 化以降、ledger.read_rows / writeback は token を第1引数に取る (旧 sheets service
    オブジェクトは廃止)。本関数も token-first シグネチャに揃える。
    """
    _, rows = ledger.read_rows(token, cfg["spreadsheet_id"], title)
    n = 0
    for r in rows:
        if (r.get("ステータス", "") or "").strip().lower() == "completed":
            if not dry_run:
                ledger.writeback(token, cfg["spreadsheet_id"], title, r["_row_number"],
                                 {"再生成フラグ": "◯", "ステータス": "未作成"}, dry_run)
            n += 1
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["individual", "corporate", "all"], default="all")
    p.add_argument("--config")
    p.add_argument("--apply", action="store_true",
                   help="diff検知後、completed行に再生成フラグを立て未作成へ差し戻す")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    scope = ["individual", "corporate"] if a.type == "all" else [a.type]
    drift_found = False
    for t_key in scope:
        print(f"=== ひな形診断: {TYPES[t_key]} ===")
        rc = _scan(t_key, a.config)
        if rc == 5:
            drift_found = True

    if a.apply:
        cfg = config_auth.load_config(a.config)
        svc = config_auth.build_services(cfg)
        token = svc["sheets_token"]
        for t_key in scope:
            n = _flag_regen(token, cfg, TYPES[t_key], a.dry_run)
            print(f"[{TYPES[t_key]}] 再生成フラグ: {n} 行を未作成へ差し戻し")
        print("→ 次回 run-contract-generate (--phase draft) で作り直されます。")
    elif drift_found:
        print("\nDRIFT 検出。template-mapping.json/台帳を更新後、--apply で再生成フラグを立ててください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

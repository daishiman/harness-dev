#!/usr/bin/env python3
# /// script
# name: validate-output-mode
# purpose: 下流送信前に output_mode (slide/report) と reportType (report 時 4 enum) の値域を fail-closed 検証する plugin-root glue。--preflight で node/npm/vendor/node_modules/codex CLI を fail-soft 検出する。CLI と import (pytest) 両対応。
# inputs:
#   - CLI: --mode slide|report [--report-type <enum>] [--preflight] [--json]
# outputs:
#   - stdout: JSON (呼び出し側が食える検証結果)
#   - exit: 0=valid / 2=mode|report-type 値域外・矛盾 (fail-closed)。preflight 単独は常に 0。
# contexts: [glue]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""output_mode / reportType の値域検証 (fail-closed) + 実行環境 preflight (fail-soft)。

契約 §D/§H の SSOT:
  - mode enum (2): slide / report
  - reportType enum (4): internal-analysis / client-proposal / tech-doc / learning
    (report 時のみ必須。slide 時に指定するのは矛盾としてエラー。)

exit code 規約:
  - 0: 検証成功 (valid)。または --preflight 単独実行 (欠落は warning でも 0)。
  - 2: mode 値域外 / report で report-type 欠落 or 値域外 / slide で report-type 指定 (fail-closed)。

pytest からは validate_output_mode() / run_preflight() を import して使う。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# 契約 §D の enum SSOT。ここが唯一の値域定義。
VALID_MODES = ("slide", "report")
VALID_REPORT_TYPES = (
    "internal-analysis",
    "client-proposal",
    "tech-doc",
    "learning",
)


def validate_output_mode(mode, report_type=None):
    """mode / report_type の値域・整合を検証し dict を返す (fail-closed 判定は valid で表現)。

    返り値: {"valid": bool, "mode": str, "report_type": str|None, "errors": [str]}
    - mode が VALID_MODES 外 → invalid
    - mode=report で report_type 欠落 or VALID_REPORT_TYPES 外 → invalid
    - mode=slide で report_type 指定 → invalid (矛盾。slide に reportType は意味を持たない)
    """
    errors: list[str] = []

    if mode not in VALID_MODES:
        errors.append(
            f"invalid mode: {mode!r} (expected one of {list(VALID_MODES)})"
        )

    if mode == "report":
        if not report_type:
            errors.append(
                "report mode requires --report-type "
                f"(one of {list(VALID_REPORT_TYPES)})"
            )
        elif report_type not in VALID_REPORT_TYPES:
            errors.append(
                f"invalid report_type: {report_type!r} "
                f"(expected one of {list(VALID_REPORT_TYPES)})"
            )
    elif mode == "slide":
        if report_type:
            errors.append(
                "slide mode does not accept --report-type "
                f"(got {report_type!r}); reportType is report-only"
            )

    return {
        "valid": not errors,
        "mode": mode,
        "report_type": report_type,
        "errors": errors,
    }


def _plugin_root() -> Path:
    """CLAUDE_PLUGIN_ROOT 優先。無ければ scripts/ の親 (= plugin root)。"""
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent


def run_preflight():
    """node/npm/vendor/node_modules/codex CLI を検出 (fail-soft)。

    返り値: {"ok": bool, "detected": {...}, "warnings": [str]}
    ok は「必須 (node/npm/vendor) が揃っているか」の目安。欠落は warnings に載るが
    呼び出し側の exit code には影響しない (mode 検証とは独立)。
    """
    root = _plugin_root()
    vendor = root / "vendor"
    node_modules = vendor / "node_modules"

    node = shutil.which("node")
    npm = shutil.which("npm")
    codex = shutil.which("codex")

    detected = {
        "node": node,
        "npm": npm,
        "vendor_dir": str(vendor) if vendor.is_dir() else None,
        "node_modules": str(node_modules) if node_modules.is_dir() else None,
        "codex_cli": codex,
    }

    warnings: list[str] = []
    if not node:
        warnings.append("node not found on PATH (決定論レンダラ/評価に必要)")
    if not npm:
        warnings.append("npm not found on PATH (vendor 依存インストールに必要)")
    if not vendor.is_dir():
        warnings.append(f"vendor dir missing: {vendor}")
    if not node_modules.is_dir():
        warnings.append(
            "vendor/node_modules 未インストール "
            "(vendor で npm install / mermaid 等が要る場合)"
        )
    if not codex:
        warnings.append("codex CLI not found (Codex 画像生成を使う場合のみ必要)")

    ok = bool(node and npm and vendor.is_dir())
    return {"ok": ok, "detected": detected, "warnings": warnings}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate-output-mode",
        description="output_mode/reportType 値域検証 (fail-closed) + 実行環境 preflight (fail-soft)",
    )
    p.add_argument("--mode", choices=None, default=None, help="slide|report")
    p.add_argument(
        "--report-type",
        dest="report_type",
        default=None,
        help="report 時: internal-analysis|client-proposal|tech-doc|learning",
    )
    p.add_argument(
        "--preflight",
        action="store_true",
        help="node/npm/vendor/node_modules/codex CLI 検出 (fail-soft)",
    )
    p.add_argument("--json", action="store_true", help="(既定で JSON 出力・互換用フラグ)")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    result: dict = {}
    exit_code = 0

    if args.mode is not None:
        validation = validate_output_mode(args.mode, args.report_type)
        result["validation"] = validation
        if not validation["valid"]:
            exit_code = 2  # fail-closed。
    elif not args.preflight:
        # mode も preflight も無い呼び出しは使い方エラー (fail-closed)。
        result["validation"] = {
            "valid": False,
            "mode": None,
            "report_type": args.report_type,
            "errors": ["--mode is required (unless --preflight is used alone)"],
        }
        exit_code = 2

    if args.preflight:
        result["preflight"] = run_preflight()  # exit code には影響させない (独立)。

    # 常に JSON を stdout に出す (呼び出し側が食える形)。
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

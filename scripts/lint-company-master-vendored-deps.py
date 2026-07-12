#!/usr/bin/env python3
# /// script
# name: lint-company-master-vendored-deps
# purpose: company-master の scripts 配下が外部依存を持つなら vendor/ 同梱を機械強制し、空 vendor の正当性と vendored notion_config.py の正本 drift 不在を保証する。
# inputs:
#   - argv: optional plugin root path (default: plugins/company-master)
# outputs:
#   - stdout: OK status
#   - stderr: 未同梱の外部 import findings / vendored notion_config drift findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""company-master の vendor 機構を機械保証する lint。

背景: company-master は「外部 Python ライブラリが必要になれば plugin-root/vendor/ に同梱し、
ユーザー手動 pip install を前提にしない」を配布方針とする (SKILL.md 設計判断ログ §3)。現状の
全 script は標準ライブラリのみで動作し vendor/ は空。本 lint は「空 vendor が正常」を機械的に
正当化する: scripts 配下 .py の import を走査し、stdlib・plugin 内部モジュール以外の外部
ライブラリ import が現れたら、vendor/ に同名の同梱物が無い限り exit 1。

これにより、将来うっかり `import requests` 等を追加して pip install 前提に退行する回帰を
CI で検出する (空 vendor + 外部 import = FAIL / 外部 import + vendor 同梱 = OK / 外部 import 無し = OK)。

追加チェック (vendored notion_config drift): company-master が vendoring する
notion_config.py は意図的拡張 (get_gbizinfo_token / plugin_root 上向き探索) を含むため、
skill-intake 系の byte一致 lint (lint-intake-vendored-ssot.py) を適用できない。代わりに
**関数単位 AST 比較 + ホワイトリスト宣言** (allowed-patch 方式) を採る: 正本
(plugins/harness-creator/scripts/notion_config.py) 由来の共通関数群は docstring を除いた
AST が正本と一致しなければ FAIL、vendored 固有の関数/差分はホワイトリスト
(ALLOWED_EXTRA_FUNCS / ALLOWED_DIVERGENT_FUNCS) に宣言済みでなければ FAIL。
正本還流 (正本側の変更) は lint-intake-vendored-ssot.py の byte一致を壊すため行わない。
AST 比較 (コメント/docstring 非感応) のため vendored 側へのマーカー整形も不要 (意味変更ゼロ)。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLUGIN = ROOT / "plugins" / "company-master"


def stdlib_module_names() -> set[str]:
    """標準ライブラリのトップレベル名集合。3.10+ は sys.stdlib_module_names を使う。"""
    names = set(getattr(sys, "stdlib_module_names", set()))
    # フォールバック / 取りこぼし補完 (3.10 で網羅されるが念のため)。
    names |= {
        "argparse", "ast", "csv", "dataclasses", "datetime", "functools", "hashlib",
        "io", "json", "os", "pathlib", "re", "subprocess", "sys", "sysconfig",
        "typing", "unicodedata", "urllib", "zipfile", "collections", "itertools",
        "tempfile", "shutil", "textwrap", "math", "time", "string", "html",
    }
    return names


def plugin_internal_modules(plugin_root: Path) -> set[str]:
    """plugin 内部で import される自前モジュール名 (scripts/*.py のステム + bootstrap)。"""
    internal: set[str] = set()
    for scripts_dir in plugin_root.rglob("scripts"):
        if not scripts_dir.is_dir():
            continue
        for py in scripts_dir.glob("*.py"):
            internal.add(py.stem)
    return internal


def vendored_top_levels(plugin_root: Path) -> set[str]:
    """vendor/ に同梱されたトップレベルモジュール/パッケージ名。"""
    vendor = plugin_root / "vendor"
    names: set[str] = set()
    if not vendor.is_dir():
        return names
    for entry in vendor.iterdir():
        if entry.name in {"README.md", "__pycache__"} or entry.name.startswith("."):
            continue
        names.add(entry.stem if entry.is_file() and entry.suffix == ".py" else entry.name)
    return names


def imported_top_levels(py: Path) -> set[str]:
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    tops: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                tops.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # 相対 import は内部
            if node.module:
                tops.add(node.module.split(".")[0])
    return tops


# --- vendored notion_config drift check (関数単位 AST 比較 + ホワイトリスト) ----

CANONICAL_NOTION_CONFIG = ROOT / "plugins" / "harness-creator" / "scripts" / "notion_config.py"
VENDORED_NOTION_CONFIG_REL = Path("scripts/notion_config.py")

# company-master 固有拡張のホワイトリスト宣言 (これ以外の差分は drift として FAIL)。
# - get_gbizinfo_token: gBizINFO API トークンの Keychain 解決 (company-master 専用追加関数)
# - get_japanpost_credentials / has_japanpost_credentials: 日本郵便 addresszip API の
#   client_id/secret_key を Keychain (japanpost-da-api) から解決 (郵便番号取得の認証)
# - get_japanpost_egress_ip / has_egress_ip: 送信元IP 解決 (Keychain `egress_ip` が主 /
#   env COMPANY_MASTER_EGRESS_IP が従の低優先フォールバック。日本郵便 IP 認証の x-forwarded-for 供給)
# - _keychain_password: 上記 japanpost 認証情報の Keychain 読み出しヘルパ
ALLOWED_EXTRA_FUNCS = {
    "get_gbizinfo_token",
    "get_japanpost_credentials", "has_japanpost_credentials",
    "get_japanpost_egress_ip", "has_egress_ip", "_keychain_password",
    "get_postal_proxy_url", "get_postal_proxy_token", "get_japanpost_base_url",
    "_japanpost_service",
}
# - plugin_root: 単独 install 対応の .claude-plugin/.codex-plugin 上向き探索拡張
#   (正本は parents[1] 固定。skill 階層が深い company-master では上向き探索が必要)
ALLOWED_DIVERGENT_FUNCS = {"plugin_root"}


def _top_level_functions(path: Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _strip_docstring(fn: ast.FunctionDef) -> ast.FunctionDef:
    """docstring (文言は plugin 文脈で意図的に差し替え済み) を比較対象から除外する。"""
    if (
        fn.body
        and isinstance(fn.body[0], ast.Expr)
        and isinstance(fn.body[0].value, ast.Constant)
        and isinstance(fn.body[0].value.value, str)
    ):
        fn.body = fn.body[1:] or [ast.Pass()]
    return fn


def check_vendored_notion_config(canonical: Path, vendored: Path) -> list[str]:
    """正本と vendored の関数単位 AST 比較。違反理由 list を返す (空 = PASS)。"""
    issues: list[str] = []
    if not vendored.exists():
        return [f"vendored notion_config.py 不在: {vendored}"]
    try:
        canon_funcs = _top_level_functions(canonical)
        vend_funcs = _top_level_functions(vendored)
    except SyntaxError as e:
        return [f"notion_config.py のパース失敗: {e}"]
    for name, fn in canon_funcs.items():
        if name not in vend_funcs:
            issues.append(
                f"正本関数 '{name}' が vendored 側に不在 (削除 drift)。正本から再同期すること"
            )
            continue
        if name in ALLOWED_DIVERGENT_FUNCS:
            continue  # 意図的差分としてホワイトリスト宣言済み
        if ast.dump(_strip_docstring(fn)) != ast.dump(_strip_docstring(vend_funcs[name])):
            issues.append(
                f"共通関数 '{name}' が正本 (plugins/harness-creator/scripts/notion_config.py) と"
                f" AST 不一致 (drift)。正本の実装へ追従するか、意図的差分なら"
                f" ALLOWED_DIVERGENT_FUNCS へ宣言を追加すること"
            )
    for name in vend_funcs:
        if name not in canon_funcs and name not in ALLOWED_EXTRA_FUNCS:
            issues.append(
                f"vendored 固有関数 '{name}' がホワイトリスト (ALLOWED_EXTRA_FUNCS) 未宣言。"
                f" 拡張なら宣言を追加、不要なら削除すること"
            )
    return issues


def main() -> int:
    plugin_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_PLUGIN
    if not plugin_root.exists():
        sys.stderr.write(f"[lint-company-master-vendored-deps] plugin root 不在: {plugin_root}\n")
        return 1

    stdlib = stdlib_module_names()
    internal = plugin_internal_modules(plugin_root)
    vendored = vendored_top_levels(plugin_root)
    allowed = stdlib | internal | vendored | {"__future__"}

    findings: list[tuple[Path, str]] = []
    scanned = 0
    for scripts_dir in plugin_root.rglob("scripts"):
        if not scripts_dir.is_dir():
            continue
        for py in scripts_dir.glob("*.py"):
            scanned += 1
            for top in imported_top_levels(py):
                if top not in allowed:
                    findings.append((py, top))

    if findings:
        sys.stderr.write("[lint-company-master-vendored-deps] FAIL: 未同梱の外部 import\n")
        for py, top in findings:
            try:
                shown = py.relative_to(ROOT)
            except ValueError:
                shown = py
            sys.stderr.write(
                f"  - {shown}: import '{top}' は stdlib/内部/vendor のいずれでもない。"
                f" plugins/company-master/vendor/ に同梱するか標準ライブラリで置き換えること。\n"
            )
        return 1

    # vendored notion_config drift チェック (正本不在 = repo 外単独実行時はスキップ)。
    drift_note = ""
    if CANONICAL_NOTION_CONFIG.exists():
        drift_issues = check_vendored_notion_config(
            CANONICAL_NOTION_CONFIG, plugin_root / VENDORED_NOTION_CONFIG_REL
        )
        if drift_issues:
            sys.stderr.write(
                "[lint-company-master-vendored-deps] FAIL: vendored notion_config.py の正本 drift\n"
            )
            for issue in drift_issues:
                sys.stderr.write(f"  - {issue}\n")
            return 1
        drift_note = " vendored notion_config は正本と関数単位一致 (拡張はホワイトリスト宣言済み)。"
    else:
        drift_note = " (正本 notion_config 不在のため drift チェックはスキップ: 単独実行環境)"

    print(
        f"[lint-company-master-vendored-deps] OK: scripts {scanned} 件は外部依存ゼロ "
        f"(vendor 同梱 {len(vendored)} 件)。空 vendor は正常。" + drift_note
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""runtime hook script の単独 install ポータビリティを静的検査する (fail-closed)。

検証する不変条件:
  runtime hook script (plugins/*/.claude-plugin/plugin.json の hooks[] に配線された
  command script) は、import-time (モジュールトップレベル) に **自 plugin root 外**の
  モジュールへ依存して `raise` してはならない。

なぜ: hook は Stop / Edit / Write / Skill 等で毎回 import-time 実行される。plugin を
marketplace から単独 install すると plugin 外 (repo-root scripts/ 等) は存在しない。
トップレベルで外部モジュールを動的 import 解決し、不在時に raise すると、その plugin の
全フックが import 時クラッシュ (exit≠0) する。フックの "exit は常に 0" 設計と矛盾し、
ユーザの全 Edit/Write/Stop が壊れる。必須依存は plugin 内へ vendoring し、ローダは
fail-soft (fallback で raise しない) にすること。

検出する違反パターン:
  (i)  module トップレベル (関数/try 外) で、ファイルパス指定の動的 import ローダ
       (importlib.util.spec_from_file_location を使う関数) を呼び、その戻り値を
       束縛している (= import-time に外部解決が走る)。
  (ii) その動的 import ローダ関数の本体に `raise` 文が含まれる (= 解決失敗時に
       例外を送出しうる)。fail-soft なローダは失敗時に fallback を return し raise を
       一切持たないため、raise の有無が「import-time にクラッシュしうるか」を分ける。

両方が揃うと FAIL (fail-closed)。トップレベル呼び出しでも、ローダが raise を撤廃し
fail-soft (失敗時に fallback を return) なら PASS。今回修正前の
`_FC = _load_feedback_contract_ssot()` (ローダが「成功時 return / 全滅時 raise」) は
raise を持つため FAIL、修正後 (raise 撤廃・fallback return) は PASS になる。
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _resolve_hook_map(plugin_root: Path, hooks: object) -> dict:
    """plugin.json の hooks を event->matchers の dict へ正規化する。

    Claude Code は hooks を (a) inline object、または (b) 別ファイル参照の相対パス
    文字列 ("hooks": "./hooks/hooks.json") のいずれでも受ける。文字列参照時はその
    ファイルを読み、{"hooks": {...}} ラッパがあれば剥がして event map を取り出す。
    inline dict は event map そのものなので unwrap しない (hook event 名に "hooks"
    は存在しないため衝突しない)。解決不能・非 dict は空 map を返し fail-soft する。
    """
    if isinstance(hooks, str):
        try:
            loaded = json.loads((plugin_root / hooks).read_text(encoding="utf-8"))
        except Exception:
            return {}
        hooks = loaded.get("hooks", loaded) if isinstance(loaded, dict) else {}
    if not isinstance(hooks, dict):
        return {}
    return hooks


def _hook_scripts() -> list[Path]:
    """全 plugin.json の hooks[] に配線された command script の絶対パスを集める。"""
    scripts: list[Path] = []
    for pj in sorted(ROOT.glob("plugins/*/.claude-plugin/plugin.json")):
        plugin_root = pj.parent.parent  # plugins/<plugin>/
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except Exception:
            continue
        hook_map = _resolve_hook_map(plugin_root, data.get("hooks"))
        for _ev, matchers in hook_map.items():
            for m in matchers or []:
                for h in m.get("hooks", []) or []:
                    cmd = h.get("command", "") or ""
                    # $CLAUDE_PLUGIN_ROOT と ${CLAUDE_PLUGIN_ROOT} の両記法を拾う。
                    mm = re.search(r"\$\{?CLAUDE_PLUGIN_ROOT\}?/(\S+?\.py)", cmd)
                    if not mm:
                        continue
                    p = plugin_root / mm.group(1)
                    if p.is_file():
                        scripts.append(p)
    # 重複排除 (同一 script が複数イベントに配線されることがある)。
    seen: set[Path] = set()
    out: list[Path] = []
    for p in scripts:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def _uses_spec_from_file(func: ast.FunctionDef) -> bool:
    """関数内で importlib spec_from_file_location を呼ぶか (= ファイルパス動的 import)。"""
    for node in ast.walk(func):
        if isinstance(node, ast.Attribute) and node.attr == "spec_from_file_location":
            return True
    return False


def _func_raises(func: ast.FunctionDef) -> bool:
    """関数本体に raise 文があるか (= 解決失敗時に import-time クラッシュしうる)。

    fail-soft なローダは失敗時に fallback を return し raise を一切持たない。
    bare re-raise も含め raise の存在自体を「クラッシュしうる経路あり」と見なす。
    """
    for node in ast.walk(func):
        if isinstance(node, ast.Raise):
            return True
    return False


def _toplevel_loader_calls(tree: ast.Module) -> set[str]:
    """module トップレベル (関数/クラス本体外) で呼ばれる関数名の集合を返す。

    `_FC = _load_x()` / `_load_x()` のような直接呼び出しを拾う。try 本体内の
    呼び出しは保護されている (import 失敗を握れる) ため対象外とする。
    """
    called: set[str] = set()

    def _collect_calls(node: ast.AST) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                called.add(sub.func.id)

    for stmt in tree.body:
        # try 本体は import 失敗を握れるので未保護ではない → スキップ。
        if isinstance(stmt, ast.Try):
            continue
        # 関数/クラス定義の内部はトップレベルではない → スキップ。
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        _collect_calls(stmt)
    return called


def check_script(path: Path) -> list[str]:
    """1 script を検査し違反メッセージのリストを返す (空なら PASS)。"""
    rel = path.relative_to(ROOT)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"{rel}: syntax error ({exc})"]

    # トップレベル関数定義を名前で索引化。
    funcs: dict[str, ast.FunctionDef] = {
        s.name: s for s in tree.body if isinstance(s, ast.FunctionDef)
    }
    toplevel_called = _toplevel_loader_calls(tree)

    violations: list[str] = []
    for name in sorted(toplevel_called):
        func = funcs.get(name)
        if func is None:
            continue
        # ファイルパス動的 import を行うローダか?
        if not _uses_spec_from_file(func):
            continue
        # トップレベルで未保護に呼ばれ、かつローダ本体に raise が残る → 違反。
        # fail-soft ローダは失敗時 fallback を return し raise を持たないため PASS。
        if _func_raises(func):
            violations.append(
                f"{rel}: トップレベルで {name}() を未保護に呼び、外部モジュールを "
                "import-time 解決するローダが raise を含む。"
                "単独 install で外部依存が不在のとき import-time クラッシュする。"
                "ローダを fail-soft 化 (raise を撤廃し失敗時 fallback を return) し、"
                "必須依存は plugin 内へ vendoring すること。"
            )
    return violations


def main() -> int:
    scripts = _hook_scripts()
    all_violations: list[str] = []
    for p in scripts:
        all_violations.extend(check_script(p))

    if all_violations:
        sys.stderr.write("[lint-runtime-portability] FAIL\n")
        for v in all_violations:
            sys.stderr.write(f"  - {v}\n")
        return 1
    print(
        f"[lint-runtime-portability] OK: hook script {len(scripts)} 件が "
        "import-time に自 plugin 外を fail-closed 依存しない"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

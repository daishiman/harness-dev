#!/usr/bin/env python3
# /// script
# name: hook-postgen-eval
# purpose: slide/report 生成完了 (中核ファイル書込) を PostToolUse(Write|Edit|MultiEdit) で検知し、mode を判定して生成後評価 (deck-evaluator, mode-aware) を Claude に促す誘導フック。移植元 vendor/scripts/hooks/deck-postgen-hook.js の mode-aware 版。
# inputs:
#   - stdin: Claude Code hook JSON (tool_input.file_path 等)
# outputs:
#   - stdout: hookSpecificOutput.additionalContext (deck-evaluator 起動指示) / systemMessage
#   - exit: 常に 0 (fail-soft・非ブロッキング・通常編集を絶対に妨げない)
# contexts: [PostToolUse]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""slide/report 生成後評価の誘導フック (mode-aware・fail-soft)。

Claude Code の PostToolUse フック (matcher: Write|Edit|MultiEdit) から呼ばれる。
stdin にフックペイロード (JSON) を受け取り、書き込まれたファイルが slide deck /
report の「中核ファイル」のときだけ mode を判定し、生成後評価 (deck-evaluator) を
additionalContext で促す。それ以外は無音で exit 0 し、通常の編集作業を一切妨げない。

設計意図 (移植元 deck-postgen-hook.js のトレードオフを踏襲):
 - 中核ファイル名の完全一致 + 同階層の index.html/report.html 存在を条件に過剰発火を封鎖。
 - 重い動的 (playwright) / LLM (30 種思考法) 評価はここでは走らせず additionalContext で遅延誘発。
   → 「うるさすぎ/全く動かない」「速い/精密」の両立。hook timeout 内 (15s) に node を起動しない。
 - fail-soft: いかなる例外でも exit 0 で握りつぶし、通常編集をブロックしない。

出力契約: 常に exit 0。中核ファイルでなければ何も出力しない。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# mode 判定の SSOT。契約 §H (index.html=slide / report.html=report) に準拠。
SLIDE_FILES = frozenset({"index.html", "structure.json", "structure.md"})
REPORT_FILES = frozenset({"report.html", "report-structure.json"})
# styles.css / scripts.js は両 mode 共有資産。同階層の生成物 (index/report.html) で mode を判定する。
SHARED_FILES = frozenset({"styles.css", "scripts.js"})
CORE_FILES = SLIDE_FILES | REPORT_FILES | SHARED_FILES

# deploy/single 派生 (最終配布用) は生成後評価の対象外。
EXCLUDED_SUFFIXES = (".deploy.html", "-single.html", ".single.html")

# mode 別の生成完了マーカー (この HTML が同階層に在って初めて「生成後」とみなす)。
MODE_MARKER = {"slide": "index.html", "report": "report.html"}


def _read_stdin() -> str:
    try:
        return sys.stdin.read()
    except Exception:
        return ""


def _plugin_root() -> Path:
    """CLAUDE_PLUGIN_ROOT 優先。無ければ hooks/ の親 (= plugin root) を採用 (portability)。"""
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent


def _edited_file_path(payload: dict) -> str:
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    for key in ("file_path", "filePath", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def resolve_target(file_path: str):
    """書込ファイルが deck/report 中核なら (mode, deck_dir) を返す。対象外は None。

    移植元 resolveDeckDir の mode-aware 版。汎用化のため upstream の '/スライド/' 日本語
    パス依存や slide-*/ 限定は撤廃し、「中核ファイル名一致」+「同階層に mode マーカー
    (index.html or report.html) が存在」で deck/report を同定する。
    """
    if not file_path:
        return None
    base = os.path.basename(file_path)
    if any(file_path.endswith(sfx) for sfx in EXCLUDED_SUFFIXES):
        return None
    if base not in CORE_FILES:
        return None

    deck_dir = os.path.dirname(file_path) or "."

    # mode 判定: 中核ファイル名で一次判定。共有資産は同階層の生成マーカーで判定。
    if base in SLIDE_FILES:
        mode = "slide"
    elif base in REPORT_FILES:
        mode = "report"
    else:  # SHARED_FILES: 同階層に report.html があれば report、index.html があれば slide。
        if os.path.exists(os.path.join(deck_dir, "report.html")):
            mode = "report"
        elif os.path.exists(os.path.join(deck_dir, "index.html")):
            mode = "slide"
        else:
            return None  # 生成物が同定できない共有ファイル編集は誤爆回避のため無視。

    # 生成完了マーカー (mode 別) が同階層に存在して初めて評価を促す。
    # 例: structure.json だけ書いて index.html 未生成の段階では起動しない。
    marker = MODE_MARKER[mode]
    if not os.path.exists(os.path.join(deck_dir, marker)):
        return None
    return mode, deck_dir


def build_context(mode: str, deck_dir: str) -> str:
    plugin_root = _plugin_root()
    evaluator = plugin_root / "vendor" / "scripts" / "evaluate-deck.js"
    report_visual = plugin_root / "scripts" / "validate-report-visual.py"
    ref = plugin_root / "references" / "post-generation-evaluation.md"
    deck_name = os.path.basename(os.path.normpath(deck_dir)) or deck_dir
    label = "スライドデッキ" if mode == "slide" else "レポート"
    if mode == "slide":
        mechanical = (
            "1) slide 機械評価 (broken img・はみ出し・computed フォント・16:9 等の静的/動的検証):\n"
            f'   node "{evaluator}" "{deck_dir}"\n'
            "   (chromium 未導入なら vendor で npx playwright install chromium 後に再実行)"
        )
    else:
        report_html = os.path.join(deck_dir, "report.html")
        report_structure = os.path.join(deck_dir, "report-structure.json")
        mechanical = (
            "1) report 機械評価 (section 構造・1項目1ビジュアル・段落密度・placeholder・印刷):\n"
            f'   python3 "{report_visual}" "{report_html}" '
            f'--structure "{report_structure}" --require-structure --json\n'
            "   (report-structure.json 欠落時は exit 2: 構造正本無しの fail-open を禁止)\n"
            "   report では slide 用 evaluate-deck.js を必須扱いしない"
        )
    return (
        f"【生成後評価フックが起動 (mode={mode})】\n"
        f"{label}: {deck_name}\n"
        f"出力先: {deck_dir}\n\n"
        f"次の生成後評価を必ず実施すること:\n"
        f"{mechanical}\n"
        f"2) deck-evaluator エージェント (思考リセット後 30 種思考法・mode={mode} の rubric) を起動し、\n"
        f"   mode 別の機械評価結果を入力に、要望↔構成の矛盾・仕組み反映を含む\n"
        f"   多角的・視覚的評価と 4 条件 (矛盾なし/漏れなし/整合性/依存関係整合) の最終判定を行う。\n"
        f"   参照: {ref}"
    )


def emit(mode: str, deck_dir: str) -> None:
    ctx = build_context(mode, deck_dir)
    deck_name = os.path.basename(os.path.normpath(deck_dir)) or deck_dir
    payload = {
        "systemMessage": f"生成後評価 (deck-evaluator, mode={mode}) を推奨: {deck_name}",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": ctx,
        },
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


def main() -> int:
    # fail-soft: いかなる例外も握りつぶし、通常編集を絶対にブロックしない。
    try:
        raw = _read_stdin()
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return 0
        if not isinstance(payload, dict):
            return 0

        file_path = _edited_file_path(payload)
        target = resolve_target(file_path)
        if target is None:
            return 0  # 中核ファイルでなければ無音終了 (通常編集を妨げない)。
        mode, deck_dir = target
        emit(mode, deck_dir)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

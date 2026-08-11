#!/usr/bin/env python3
# /// script
# name: hook-postgen-eval
# purpose: slide/report 生成完了 (中核ファイル書込) を PostToolUse(Write|Edit|MultiEdit) で検知し、mode を判定して図解静的契約 (validate-svg-diagram.py D0-D21) を hook 内で機械実行した上で、生成後評価 (deck-evaluator, mode-aware) を Claude に促すフック。移植元 vendor/scripts/hooks/deck-postgen-hook.js の mode-aware 版。
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
 - 例外: 図解静的契約 (validate-svg-diagram.py D0-D21) は純 Python・実描画なしで軽量なため
   hook 内で毎回機械実行し、実結果 (PASS/FAIL/未検査(対象0件) + 出力末尾) を
   additionalContext に注入する。「対象 0 件」は PASS と区別して表示する
   (検査対象が無いだけの空振りを合格の保証として発行しない)。
   → 「毎回同じ手順で検査する」再現性を LLM の自主性でなく hook が担保する (fail-soft は維持)。
 - fail-soft: いかなる例外でも exit 0 で握りつぶし、通常編集をブロックしない。

出力契約: 常に exit 0。中核ファイルでなければ何も出力しない。
"""
from __future__ import annotations

import glob as _glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# 図解静的契約 (D0-D21) の hook 内インライン実行予算 (秒)。hook 全体 15s の内側に収める。
SVG_LINT_TIMEOUT_SEC = 8

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

# 図解静的契約の判定表示。「未検査」を PASS と書かないための SSOT。
LINT_VERDICT_TEXT = {
    "pass": "PASS (検査対象 1 件以上・error 0)",
    "fail": "FAIL (修正必須。修正後に再実行して PASS を確認すること)",
    "no-target": (
        "未検査 (対象 0 件) — PASS ではない。この HTML には <svg> も CSS/HTML 図解ブロックも "
        "無く、D0-D21 は 1 項目も評価されていない (D3 マウント点のみの生成物など)。"
        "図解がある想定なら、なぜ検査対象として抽出されないかを確かめること"
    ),
    "unknown": (
        "判定不能 (検査を完了できず、検査量も読めない)。下記コマンドを手動実行して確認すること"
    ),
}


def _read_stdin() -> str:
    try:
        return sys.stdin.read()
    except Exception:
        return ""


def _plugin_root() -> Path:
    """SRG_ROOT 優先。無ければ hooks/ の親 (= plugin 実体) を __file__ から自己解決。

    ObsidianMemo 等では CLAUDE_PLUGIN_ROOT が別プラグイン (ubm-goal-setting) に env 固定
    されるため、それを採用すると slide-report と別の root を指してしまう。よって
    slide-report 専用の SRG_ROOT を優先し、無ければ symlink 経由でも実体を指す
    Path(__file__).resolve() から自己解決する (CLAUDE_PLUGIN_ROOT は採用しない)。
    """
    env_root = os.environ.get("SRG_ROOT")
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


def run_svg_diagram_lint(svg_diagram: Path, targets: list[str]) -> tuple[str, str]:
    """validate-svg-diagram.py (D0-D21) を hook 内で実際に実行し、結果要約と判定を返す。

    純 Python・実描画なしの静的検査なので hook 予算内で毎回機械実行できる。
    これにより「毎回同じ手順で検査が走る」ことが LLM の自主性でなく hook で担保される。
    実行不能 (validator 不在 / timeout / 例外) の場合は fail-soft でその旨を返し、
    呼び出し側が従来どおりコマンド提示にフォールバックする。

    返す判定は 4 値:
      pass       検査対象 >= 1 かつ finding 0
      fail       error/warning あり (strict mode の exit != 0)
      no-target  exit 0 だが検査対象 0 件 = 未検査。PASS と呼んではいけない
      unknown    実行不能・件数を読み取れない。合否を名乗らない
    「対象 0 件」を PASS と表示すると、D3 経路 (生成物が <script data-d3-mount>
    しか持たず <svg> が 1 つも無い) の図解が「検査済み・合格」として通る。
    exit code は validator 側の契約 (error 件数だけで決まる) を尊重して変えず、
    ここでは表示の嘘だけを消す。fail-closed 化の是非は別判断。
    """
    existing = [t for t in targets if os.path.exists(t)]
    if not existing:
        return "(対象 HTML 不在のため未実行)", "unknown"
    try:
        proc = subprocess.run(
            [sys.executable, str(svg_diagram), "--check-grid", "--strict", *existing],
            capture_output=True,
            text=True,
            timeout=SVG_LINT_TIMEOUT_SEC,
        )
    except Exception as exc:  # timeout 含む。fail-soft でコマンド提示へフォールバック。
        return f"(hook 内実行不能: {type(exc).__name__}。下記コマンドを手動実行すること)", "unknown"
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = [ln for ln in output.splitlines() if ln.strip()]
    tail = "\n".join(lines[-20:]) if lines else "(出力なし)"
    if proc.returncode != 0:
        return tail, "fail"
    # exit 0 のときだけ検査量を読む。inspected= が無い (古い validator 等) 場合は
    # 「0 件でなかった」と決め付けず unknown にする。嘘の PASS を作らないため。
    m = re.search(r"\binspected=(\d+)\b", output)
    if not m:
        return tail, "unknown"
    return tail, "pass" if int(m.group(1)) > 0 else "no-target"


INFO_VERDICT_TEXT = {
    "pass": "PASS (検査対象 1 件以上・error 0)",
    "fail": (
        "FAIL (参照の取りこぼし I-ER-REF か孤立節点 I-REL-ISO。"
        "構造から確定的に判る欠陥なので修正必須)"
    ),
    "warn": (
        "error 0・warning あり — 合否には入れない。warning は語彙の存在による近似判定で、"
        "図の意図によっては正しく満たされている場合がある。**読んで判断する**対象であって、"
        "潰すべきノルマではない。ここを合否へ入れると、通すためだけの語を足す圧力が生まれ、"
        "『使える情報が多いのが正義』が『情報が多いのが正義』へ反転する"
    ),
    "no-target": (
        "未検査 (対象 0 件) — PASS ではない。図解の入力語彙 (nodes/entities/relations) を "
        "1 つも持たない生成物である。図解がある想定なら抽出されない理由を確かめること"
    ),
    "unknown": "判定不能 (検査を完了できず、検査量も読めない)。下記コマンドを手動実行すること",
}


def run_information_lint(validator: Path, targets: list[str]) -> tuple[str, str]:
    """validate-diagram-information.py (I1-I5 + 型別スロット) を hook 内で実行する。

    幾何契約 (D0-D21) が見るのは**上限**で、こちらが見るのは**下限**である。
    主キーの無い ER 図も依存線の無いガント図も D 検査は全部緑で通す。

    **--strict を渡さない。** warning を合否へ入れると、検査を通すためだけに
    語を足す圧力が生まれ、本契約の原則 (「情報が多いのが正義ではない。
    使える情報が多いのが正義である」) がちょうど反転する。
    error になるのは参照の取りこぼしと孤立節点だけで、これは語彙近似ではなく
    構造から確定的に判るため、合否へ入れてよい。

    返す判定は 5 値。幾何側の 4 値に warn を足したもの。
    """
    existing = [t for t in targets if os.path.exists(t)]
    if not existing:
        return "(対象 HTML 不在のため未実行)", "unknown"
    try:
        proc = subprocess.run(
            [sys.executable, str(validator), *existing],
            capture_output=True, text=True, timeout=SVG_LINT_TIMEOUT_SEC,
        )
    except Exception as exc:
        return f"(hook 内実行不能: {type(exc).__name__}。下記コマンドを手動実行すること)", "unknown"
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = [ln for ln in output.splitlines() if ln.strip()]
    tail = "\n".join(lines[-20:]) if lines else "(出力なし)"
    if proc.returncode != 0:
        return tail, "fail"
    m = re.search(r"\binspected=(\d+)\b", output)
    if not m:
        return tail, "unknown"
    if int(m.group(1)) == 0:
        return tail, "no-target"
    w = re.search(r"\bwarnings=(\d+)\b", output)
    return tail, "warn" if (w and int(w.group(1)) > 0) else "pass"


def build_context(mode: str, deck_dir: str) -> tuple[str, str, str]:
    plugin_root = _plugin_root()
    evaluator = plugin_root / "vendor" / "scripts" / "evaluate-deck.js"
    report_visual = plugin_root / "scripts" / "validate-report-visual.py"
    svg_diagram = plugin_root / "scripts" / "validate-svg-diagram.py"
    info_contract = plugin_root / "scripts" / "validate-diagram-information.py"
    report_layout = plugin_root / "scripts" / "validate-report-layout.js"
    slide_layout = plugin_root / "scripts" / "validate-slide-layout.js"
    ref = plugin_root / "references" / "post-generation-evaluation.md"
    deck_name = os.path.basename(os.path.normpath(deck_dir)) or deck_dir
    label = "スライドデッキ" if mode == "slide" else "レポート"
    if mode == "slide":
        lint_targets = sorted(
            p for p in _glob.glob(os.path.join(deck_dir, "*.html"))
            if not any(p.endswith(sfx) for sfx in EXCLUDED_SUFFIXES)
        )
    else:
        lint_targets = [os.path.join(deck_dir, "report.html")]
    lint_summary, lint_status = run_svg_diagram_lint(svg_diagram, lint_targets)
    info_summary, info_status = run_information_lint(info_contract, lint_targets)
    lint_verdict = LINT_VERDICT_TEXT.get(lint_status, LINT_VERDICT_TEXT["unknown"])
    lint_block = (
        "1b) 図解の静的契約 (D0-D21: viewBox 収容・marker 解決・最小フォント・線幅・"
        "4px グリッド・複雑度予算・accent 個数・斜め線) — hook が実行済み:\n"
        f"   判定: {lint_verdict}\n"
        f"   結果末尾:\n{lint_summary}\n"
        f'   再実行コマンド: python3 "{svg_diagram}" --check-grid --strict <生成 HTML>'
    )
    info_block = (
        "1d) 図解の情報契約 (I1-I5 + 型別スロット: 出所と時点・caption と図の一致・"
        "記号の凡例・軸の宣言・完了条件) — hook が実行済み:\n"
        f"   判定: {INFO_VERDICT_TEXT.get(info_status, INFO_VERDICT_TEXT['unknown'])}\n"
        f"   結果末尾:\n{info_summary}\n"
        f'   再実行コマンド: python3 "{info_contract}" <生成 HTML>\n'
        "   (仕上げ前の最終ゲートとして warning ごと失格にしたいときだけ --strict を足す。"
        "hook は付けない)"
    )
    if mode == "slide":
        mechanical = (
            "1) slide 機械評価 (broken img・はみ出し・computed フォント・16:9 等の静的/動的検証):\n"
            f'   node "{evaluator}" "{deck_dir}"\n'
            "   (Chromium 未導入なら scripts/setup-playwright.py --install 後に再実行)\n"
            f"{lint_block}\n"
            "1c) スライドの実描画レイアウト:\n"
            f'   node "{slide_layout}" "{os.path.join(deck_dir, "index.html")}" --strict\n'
            f"{info_block}"
        )
    else:
        report_html = os.path.join(deck_dir, "report.html")
        report_structure = os.path.join(deck_dir, "report-structure.json")
        mechanical = (
            "1) report 機械評価 (section 構造・1項目1ビジュアル・段落密度・placeholder・印刷):\n"
            f'   python3 "{report_visual}" "{report_html}" '
            f'--structure "{report_structure}" --require-structure --json\n'
            "   (report-structure.json 欠落時は exit 2: 構造正本無しの fail-open を禁止)\n"
            "   report では slide 用 evaluate-deck.js を必須扱いしない\n"
            f"{lint_block}\n"
            "1c) 読書レイアウトの実描画契約 (R1-R7: 重なり・可読幅・追従ナビ・4 viewport):\n"
            f'   node "{report_layout}" "{report_html}"\n'
            f"{info_block}"
        )
    ctx = (
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
    return ctx, lint_status, info_status


def emit(mode: str, deck_dir: str) -> None:
    ctx, lint_status, info_status = build_context(mode, deck_dir)
    deck_name = os.path.basename(os.path.normpath(deck_dir)) or deck_dir
    # 情報契約の error は「参照の取りこぼし」「孤立節点」の 2 件だけで、
    # どちらも構造から確定的に判る。幾何が緑でもここが赤なら図は成立していない
    # (主キーの無い ER 図は D 検査を全部通る) ので、合図を握り潰さない。
    # warning は合否に入れない — 入れると通すためだけに語を足す圧力が生まれる。
    if info_status == "fail" and lint_status != "fail":
        message = (
            f"図解情報契約 (I-ER-REF / I-REL-ISO) FAIL を検出: {deck_name} — "
            f"幾何 (D0-D21) は通っているが図として成立していない (mode={mode})"
        )
    elif lint_status == "pass":
        message = f"生成後評価 (deck-evaluator, mode={mode}) を推奨: {deck_name}"
    elif lint_status == "fail":
        message = (
            f"図解静的契約 (D0-D21) FAIL を検出: {deck_name} — "
            f"修正して validate-svg-diagram.py PASS を確認すること (mode={mode})"
        )
    elif lint_status == "no-target":
        # 「対象 0 件」を PASS と言わない。ブロックもしない (exit 0 は維持) が、
        # 保証が発行されていない事実だけは必ず伝える。
        message = (
            f"図解静的契約 (D0-D21) は未検査 (対象 0 件): {deck_name} — "
            f"PASS ではない。図解がある想定なら抽出されない理由を確認すること (mode={mode})"
        )
    else:
        message = (
            f"図解静的契約 (D0-D21) の判定不能: {deck_name} — "
            f"validate-svg-diagram.py を手動実行すること (mode={mode})"
        )
    payload = {
        "systemMessage": message,
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

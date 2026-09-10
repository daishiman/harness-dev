#!/usr/bin/env python3
# /// script
# name: hook-postgen-eval
# purpose: slide/reportの実HTML生成を検知し、UTF-8 open/HTML parse/破損/secretの最小guard後に成果物提示と利用者選択を促す。semantic evaluatorは自動起動しない。
# inputs:
#   - stdin: Claude Code hook JSON (tool_input.file_path 等)
# outputs:
#   - stdout: hookSpecificOutput.additionalContext (artifact presentation/user choice 指示) / systemMessage
#   - exit: 常に 0 (fail-soft・非ブロッキング・通常編集を絶対に妨げない)
# contexts: [PostToolUse]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""slide/report usable artifactの最小guard・提示誘導フック。

Claude Code の PostToolUse フック (matcher: Write|Edit|MultiEdit) から呼ばれる。
stdin にフックペイロード (JSON) を受け取り、書き込まれたファイルが slide deck /
report の「中核ファイル」のときだけ mode を判定し、最小guard結果と
artifact提示→利用者choiceの順をadditionalContextで促す。それ以外は無音で exit 0。

設計意図:
 - 中核ファイル名の完全一致 + 同階層の index.html/report.html 存在で過剰発火を封鎖する。
 - hook内は実HTMLのopen/UTF-8 decode/HTML閉じ/空・NUL/secretだけを検査する。
 - 実描画、図解、レイアウト、30思考法、multi-agent改善は利用者choice後のR6責務で、hookから起動しない。
 - fail-soft: いかなる例外でも exit 0 で握りつぶし、通常編集をブロックしない。

出力契約: 常に exit 0。中核ファイルでなければ何も出力しない。
"""
from __future__ import annotations

import json
import os
import re
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


_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"][^'\"]{12,}['\"]", re.I),
)


def run_minimal_artifact_guard(mode: str, deck_dir: str) -> tuple[str, list[str]]:
    """Open/parse/corruption/secret checks only; semantic quality is post-choice."""
    artifact = Path(deck_dir) / MODE_MARKER[mode]
    failures: list[str] = []
    if artifact.is_symlink() or not artifact.is_file():
        return "fail", ["actual artifact is missing, non-regular, or a symlink"]
    try:
        raw = artifact.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return "fail", ["artifact cannot be opened as UTF-8"]
    if not raw or b"\x00" in raw:
        failures.append("artifact is empty or corrupt (NUL byte)")
    lowered = text.lower()
    if "<html" not in lowered or "</html>" not in lowered:
        failures.append("artifact is not a complete HTML document")
    if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
        failures.append("possible embedded secret")
    # slide/report generation is local-artifact only; irreversible operations are
    # not authorized by this hook and therefore remain explicitly not-applicable.
    return ("fail", failures) if failures else ("pass", [])


def build_context(mode: str, deck_dir: str) -> tuple[str, str]:
    """Return the minimal guard receipt and a presentation/choice instruction."""
    guard_status, failures = run_minimal_artifact_guard(mode, deck_dir)
    artifact = os.path.join(deck_dir, MODE_MARKER[mode])
    detail = "; ".join(failures) if failures else "UTF-8 open/HTML parse/corrupt/secret guard PASS"
    ctx = (
        f"【usable artifact delivery (mode={mode})】\n"
        f"artifact_created: {artifact}\n"
        f"minimal_guard_passed: {guard_status == 'pass'} ({detail}; irreversible=not-applicable/local-artifact)\n"
    )
    if guard_status == "pass":
        ctx += (
            "artifact_presented: 成果物のpathと開き方を利用者へ先に提示する。\n"
            "user_choice_recorded: 提示後に accept-as-is / light / standard / detailed を聞く。\n"
            "accept-as-is はevaluator=0 / improver=0。semantic reviewは明示選択後のみ起動する。"
            " release/exhaustiveは、このchoiceとは別のexplicit eventがある場合だけ実行する。"
        )
    else:
        ctx += "guard FAIL: 提示前に最小破損/秘密検査だけを修復する。"
    return ctx, guard_status


def emit(mode: str, deck_dir: str) -> None:
    ctx, guard_status = build_context(mode, deck_dir)
    message = (
        f"usable artifact guard {guard_status.upper()} (mode={mode}); "
        "semantic evaluation is queued only after user choice"
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

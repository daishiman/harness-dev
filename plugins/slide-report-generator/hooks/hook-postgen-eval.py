#!/usr/bin/env python3
# /// script
# name: hook-postgen-eval
# purpose: slide/report 生成完了 (中核ファイル書込) を PostToolUse(Write|Edit|MultiEdit) で検知し、mode を判定して図解静的契約 (validate-svg-diagram.py D0-D28) を hook 内で機械実行した上で、生成後評価 (deck-evaluator, mode-aware) を Claude に促すフック。移植元 vendor/scripts/hooks/deck-postgen-hook.js の mode-aware 版。
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
 - LLM (30 種思考法) 評価はここでは走らせず additionalContext で遅延誘発。
   → 「うるさすぎ/全く動かない」「速い/精密」の両立。
 - 例外 2: slide の実描画レイアウト契約 (validate-slide-layout.js L0-L9) は hook 内で実行する。
   面の余白率・充填率の正本 (frame-contract.json の fill_policy / vertical_margin_policy) を
   書いても、実行経路から必ず走る主体が無ければ規約は発火しない。ここがその主体である。
   ただし chromium 起動を伴うので、hook 全体予算の残余を計算して渡し、予算不足なら
   起動せずコマンド提示へ落とす (hook ごと殺されて先行検査の結果まで失うのを避ける)。
   **--strict は付けない** (L8/L9 は観測期。理由は run_slide_layout_gate の docstring)。
 - 例外: 図解静的契約 (validate-svg-diagram.py D0-D28) は純 Python・実描画なしで軽量なため
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
import time
from pathlib import Path

# hook 起動時刻。実描画ゲートへ渡す残余予算の基準にする。
_HOOK_START = time.monotonic()

# 図解静的契約 (D0-D28) の hook 内インライン実行予算 (秒)。hook 全体予算の内側に収める。
SVG_LINT_TIMEOUT_SEC = 8

# hook 全体の予算 (秒)。.claude-plugin/plugin.json の PostToolUse timeout と同値を保つこと
# (ズレると子プロセスが自前 timeout に達する前に hook ごと殺され、先に済んだ検査結果まで失われる)。
HOOK_BUDGET_SEC = 45
# 実描画ゲートを起動しても意味がある最低残余 (秒)。chromium 起動だけで数秒かかるため、
# これを割ったら起動せず「予算不足」として再実行コマンド提示へフォールバックする。
LAYOUT_MIN_BUDGET_SEC = 12
# 予算切れで hook ごと殺されないための安全マージン (秒)。
HOOK_BUDGET_MARGIN_SEC = 3
# 実描画レイアウト契約を hook で見る viewport。既定の 2 種は hook 予算に対して重いので、
# hook では主 viewport 1 種に絞る (2 種目は additionalContext の再実行コマンドが担う)。
LAYOUT_HOOK_VIEWPORT = "1920x1080"

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
        "無く、D0-D28 は 1 項目も評価されていない (D3 マウント点のみの生成物など)。"
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
    """validate-svg-diagram.py (D0-D28) を hook 内で実際に実行し、結果要約と判定を返す。

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

    幾何契約 (D0-D28) が見るのは**上限**で、こちらが見るのは**下限**である。
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


VISUAL_VERDICT_TEXT = {
    "pass": "PASS (面 1 つ以上・error 0)",
    "fail": (
        "FAIL (E1-E6 / VGCONST。面の上に階層が作れていない。"
        "既存 deck を再生成した場合、ここが赤で出るのは想定どおりで、"
        "検査を緩めたり除外を作ったりして黙らせないこと)"
    ),
    "warn": "error 0・warning あり — 合否には入れない。読んで判断する対象",
    "no-target": (
        "未検査 (面 0) — PASS ではない。面が 1 つも同定されていないので、"
        "E1-E6 は 1 項目も評価されていない"
    ),
    "unknown": (
        "判定不能 (検査を完了できず、検査量も読めない)。"
        "依存 (bs4 / tinycss2) 不足なら exit 3 で出る。下記コマンドを手動実行すること"
    ),
    "n/a": "report mode では未配線 (理由は run_visual_generation_gate の docstring)",
}


def run_visual_generation_gate(validator: Path, index_html: str) -> tuple[str, str]:
    """validate-visual-generation.py (E1-E6 / VGCONST) を hook 内で実行する。slide 専用。

    D0-D28 も L0-L9 も「超えるな」という上限の検査で、面の上に階層を**作れているか**
    を見る検査は無かった。意匠を手で直しても次の生成で平板へ戻るのはそのためで、
    この検査器がその欠けた側を踏む。規約 (visual-generation-rules.md) に条文を
    書いても、実行経路から必ず走る主体が無ければ発火しない。ここがその主体である。

    **--strict を渡さない。** 情報契約・レイアウト契約と同じ理由で、warning を
    合否へ入れると通すためだけに意匠をいじる圧力が生まれる。error 側は非 strict
    でも exit 1 になる。

    **report mode では呼ばない。** この検査器は「面 (slide の 1 枚)」を単位に
    数えており、report.html に当てたときに面が同定できるかを**測れていない**
    (リポジトリ内に report.html の実物が 1 つも無い)。同定できなければ VG99
    「面を 1 つも同定できない」が error で出て、欠陥でない赤を毎回出すことになる。
    偽の赤は、本物の赤を無視する運用を教育する。測れるまでは配線しない。

    件数は --json から読む。散文の要約行を正規表現で読むと、書式を変えた瞬間に
    黙って unknown へ落ちる。
    """
    if not os.path.exists(index_html):
        return "(index.html 不在のため未実行)", "unknown"
    try:
        proc = subprocess.run(
            [sys.executable, str(validator), index_html, "--json"],
            capture_output=True, text=True, timeout=SVG_LINT_TIMEOUT_SEC,
        )
    except Exception as exc:
        return f"(hook 内実行不能: {type(exc).__name__}。下記コマンドを手動実行すること)", "unknown"
    if proc.returncode not in (0, 1):
        # 2 = 引数不正 / 3 = 規約または入力が読めない (fail-closed)。合否を名乗らない。
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        return ("\n".join(err[-5:]) or f"(exit {proc.returncode})"), "unknown"
    try:
        decks = json.loads(proc.stdout)["decks"]
    except Exception:
        return "(JSON を解釈できない)", "unknown"
    faces = sum(d.get("faces", 0) for d in decks)
    errors = sum(d.get("errors", 0) for d in decks)
    warns = sum(d.get("warns", 0) for d in decks)
    # 件数の多い順に code 別内訳を出す。52 件を全部並べても読めないため。
    tally: dict[str, int] = {}
    for d in decks:
        for f in d.get("findings", []):
            key = f"{f.get('severity')} {f.get('code')}"
            tally[key] = tally.get(key, 0) + 1
    breakdown = " / ".join(f"{k}×{v}" for k, v in sorted(tally.items(), key=lambda kv: -kv[1]))
    tail = f"面 {faces} / error {errors} 件 warn {warns} 件" + (f"\n   内訳: {breakdown}" if breakdown else "")
    if errors:
        return tail, "fail"
    if faces == 0:
        return tail, "no-target"
    return tail, "warn" if warns else "pass"


LINEBREAK_VERDICT_TEXT = {
    "pass": "PASS (<br> を 1 件以上検査・違反 0)",
    "fail": (
        "FAIL (SR-3-09 / V-021。<br> が文節の切れ目に無い。"
        "文字数で折るのではなく、句読点・助詞の切れ目で折ること)"
    ),
    "no-target": (
        "未検査 (<br> 0 件) — PASS ではない。この生成物には文章としての <br> が 1 つも無く、"
        "SR-3-09 は 1 件も評価されていない。**現時点のこのリポジトリでは構造的にこうなる** "
        "(生成物が <br> を出さない)。0 件であり続ける保証は無いので配線は残す"
    ),
    "unknown": (
        "判定不能 (検査を完了できず、検査量も読めない)。"
        "規約 (spec-registry.md SR-3-09) を読めないと exit 3 で出る。下記コマンドを手動実行すること"
    ),
}


def run_linebreak_gate(validator: Path, targets: list[str]) -> tuple[str, str]:
    """validate-linebreak-position.mjs (SR-3-09 / V-021) を hook 内で実行する。両 mode。

    **report mode でも呼ぶ。**面の生成則 (E1-E6) を report で呼ばなかったのは、
    面を同定できるかが未測定で、同定できなければ VG99 が error で毎回出るからだった。
    こちらは条件が違う: 対象が無ければ error ではなく `verdict=not-checked` へ落ちる。
    偽の赤を作らないので、測れていない入力に当てても運用を壊さない。
    「report では不要」と判断したのではなく、**当てても安全な形をしている**。

    判定は検査器の `verdict` をそのまま採る (not-checked / pass / fail)。
    ここで checked と violations から再計算すると、検査器側の言い分けと hook 側の
    言い分けが二重定義になり、片方だけ直したときに黙ってズレる。

    `--json` から読む。散文を正規表現で読むと書式変更で黙って unknown へ落ちる。
    exit code だけでも読まない — **対象 0 件と違反 0 件はどちらも exit 0** で、
    exit code はこの 2 つを区別しない (区別できるのは verdict だけ)。
    """
    existing = [t for t in targets if os.path.exists(t)]
    if not existing:
        return "(対象 HTML 不在のため未実行)", "unknown"
    try:
        proc = subprocess.run(
            ["node", str(validator), *existing, "--json"],
            capture_output=True, text=True, timeout=SVG_LINT_TIMEOUT_SEC,
        )
    except Exception as exc:  # node 不在・timeout 含む。fail-soft。
        return f"(hook 内実行不能: {type(exc).__name__}。下記コマンドを手動実行すること)", "unknown"
    if proc.returncode not in (0, 1):
        # 2 = 引数不正 / 3 = 規約を読めない (fail-closed)。合否を名乗らない。
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        return ("\n".join(err[-5:]) or f"(exit {proc.returncode})"), "unknown"
    try:
        data = json.loads(proc.stdout)
        verdict = data["verdict"]
        checked = data["checked"]
        violations = data["violations"]
    except Exception:
        return "(JSON を解釈できない)", "unknown"
    status = {"not-checked": "no-target", "pass": "pass", "fail": "fail"}.get(verdict)
    if status is None:
        return f"(未知の verdict: {verdict})", "unknown"
    tail = f"<br> {checked} 件を検査 / 違反 {violations} 件"
    if violations:
        detail = [
            f"   {r['file']} 行 {f['line']}: {f['reason']}"
            for r in data.get("results", []) for f in r.get("findings", [])
        ]
        tail += "\n" + "\n".join(detail[:10])
    return tail, status


COVERAGE_VERDICT_TEXT = {
    "pass": "PASS (判定できた面が 1 面以上・図解被覆が下限以上)",
    "fail": (
        "FAIL (DC1/DC2: 文字リストだけの面がある。ul>li・カードの羅列は図ではない。"
        "項目間の関係 (順序・包含・比較・分岐・循環) を決めてから図の型を選ぶこと。"
        "関係が無いなら、その項目を並べる必要があるのかを先に疑う)"
    ),
    "no-target": (
        "未検査 (判定できた面が 0) — **PASS ではない**。面を同定できなかったか、"
        "全面が除外型・判定保留。分母が 0 の緑を作らないため exit 2 で分離してある"
    ),
    "unknown": "判定不能 (検査を完了できず、分母も読めない)。下記コマンドを手動実行すること",
}


def run_diagram_coverage_gate(validator: Path, targets: list[str]) -> tuple[str, str]:
    """validate-diagram-coverage.py (DC1-DC6) を hook 内で実行する。**両 mode**。

    既存の 2 本 (D0-D28 の幾何 / I1-I5 の情報) が見るのは**見つけた図**であって、
    面が図を持っているかではない。SVG が 0 個の面はどちらにとっても検査対象が
    存在しないので、文字リストだけの deck は両方緑で通る (分母 0 の緑)。
    ここが唯一その分母を数える検査で、対象 0 件は exit 2 として緑と分離する。

    **--min-ratio を渡さない。** 既定 (検査器側 0.50) は「いま当てても検査ごと
    無視されない床」であって目標ではない。床の値を hook 側にも書くと二重定義に
    なり、片方だけ直したときに黙ってズレる。値の正本は検査器に置く。
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
    status = {0: "pass", 1: "fail", 2: "no-target"}.get(proc.returncode, "unknown")
    return tail, status


LAYOUT_VERDICT_TEXT = {
    "pass": "PASS (検査対象 1 面以上・error 0・warning 0)",
    "fail": (
        "FAIL (L0/L7/L1/L2/L3/L8-font のいずれか。重なり・はみ出し・溢れ・体系混在・"
        "書体下限割れは実描画で確定的に判るので修正必須)"
    ),
    "warn": (
        "error 0・warning あり (L4/L5/L6/L8/L9) — **合否に入れない (観測)**。"
        "L8 充填率・L9 縦の残余配分は engine 既定の面が現時点で多数 warning を出すため、"
        "hook は --strict を付けず分布の観測から始める。warning は面ごとに読み、"
        "契約 (frame-contract.json の fill_policy / vertical_margin_policy) の側が実態に"
        "合っていないのか、面の側が崩れているのかを判断する対象であって、"
        "通すためだけに面を詰める指標ではない"
    ),
    "no-target": (
        "未検査 (対象 0 面) — PASS ではない。slide が 1 面も抽出されていない"
        "(体系判別に失敗している可能性)。抽出されない理由を確かめること"
    ),
    "unknown": "判定不能 (検査を完了できず、検査量も読めない)。下記コマンドを手動実行すること",
}


def run_slide_layout_gate(validator: Path, index_html: str, budget_sec: float) -> tuple[str, str]:
    """validate-slide-layout.js (L0-L9) を hook 内で実際に実行する。slide mode 専用。

    D0-D28 / I1-I5 が静的に見るのに対し、こちらは chromium で実描画してから
    「要素どうしの位置関係」と「面の埋まり方」を見る。規約 (frame-contract.json の
    fill_policy / vertical_margin_policy) だけ書いても、実行経路から必ず走る主体が
    無ければ規約は発火しない。ここがその主体である。

    **--strict を渡さない (意図的)。** L8 (充填率) / L9 (縦方向の残余配分) は
    severity=warning で、engine 既定の面が現時点で大量に warning を出す。いきなり
    strict にすると「規約内に解が無い赤」が積み、検査そのものを無視する運用を
    教育してしまう。まず非 strict で分布を観測し、engine 既定の面が契約レンジへ
    収まったことを確認してから strict へ昇格させる (昇格時はこの呼び出しへ
    '--strict' を足すだけでよい)。error 側 (L1/L2/L3/L7/L8-font) は非 strict でも
    exit 1 になるので、確定的に判る欠陥は今日から止まる。

    実行不能 (validator 不在 / chromium 未導入 / timeout / 予算不足) は fail-soft で
    unknown を返し、呼び出し側が従来どおり再実行コマンド提示へフォールバックする。

    返す判定は情報契約と同じ 5 値 (pass / fail / warn / no-target / unknown)。
    """
    if not os.path.exists(index_html):
        return "(index.html 不在のため未実行)", "unknown"
    if budget_sec < LAYOUT_MIN_BUDGET_SEC:
        return (
            f"(hook 予算不足のため未実行: 残余 {budget_sec:.1f}s < {LAYOUT_MIN_BUDGET_SEC}s。"
            "下記コマンドを手動実行すること)"
        ), "unknown"
    try:
        proc = subprocess.run(
            ["node", str(validator), index_html, "--viewport", LAYOUT_HOOK_VIEWPORT],
            capture_output=True, text=True, timeout=budget_sec,
        )
    except Exception as exc:  # node 不在・chromium 未導入・timeout 含む。fail-soft。
        return f"(hook 内実行不能: {type(exc).__name__}。下記コマンドを手動実行すること)", "unknown"
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = [ln for ln in output.splitlines() if ln.strip()]
    tail = "\n".join(lines[-20:]) if lines else "(出力なし)"
    if proc.returncode != 0:
        return tail, "fail"
    m = re.search(r"\bslides_checked=(\d+)\b", output)
    if not m:
        return tail, "unknown"
    if int(m.group(1)) == 0:
        return tail, "no-target"
    w = re.search(r"\bwarnings=(\d+)\b", output)
    return tail, "warn" if (w and int(w.group(1)) > 0) else "pass"


def build_context(mode: str, deck_dir: str) -> tuple[str, str, str, str, str, str, str]:
    """(評価文, 幾何契約, 情報契約, 実描画レイアウト契約, 生成則, 改行位置, 図解被覆) の判定を返す。

    7 つ目 (図解被覆 DC1-DC6) は**両 mode で走る**。幾何契約・情報契約はどちらも
    「見つけた図」を見る検査なので、図が 0 個の面には検査対象が無く緑を返す。
    面が図を持っているかを数えるのはここだけで、対象 0 件は no-target へ落ちる。

    4 つ目と 5 つ目は slide mode でのみ意味を持つ。report は読書レイアウト側 (R1-R8) の
    validate-report-layout.js が担当するので "n/a" を返す。生成則 (E1-E6) を report で
    呼ばない理由は run_visual_generation_gate の docstring。
    6 つ目 (改行位置) は**両 mode で走る** — 対象が無ければ偽の赤ではなく未検査へ
    落ちるため、測れていない入力に当てても運用を壊さない (run_linebreak_gate の docstring)。
    """
    plugin_root = _plugin_root()
    evaluator = plugin_root / "vendor" / "scripts" / "evaluate-deck.js"
    report_visual = plugin_root / "scripts" / "validate-report-visual.py"
    svg_diagram = plugin_root / "scripts" / "validate-svg-diagram.py"
    info_contract = plugin_root / "scripts" / "validate-diagram-information.py"
    report_layout = plugin_root / "scripts" / "validate-report-layout.js"
    slide_layout = plugin_root / "scripts" / "validate-slide-layout.js"
    visual_gen = plugin_root / "scripts" / "validate-visual-generation.py"
    linebreak = plugin_root / "scripts" / "validate-linebreak-position.mjs"
    coverage = plugin_root / "scripts" / "validate-diagram-coverage.py"
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
    break_summary, break_status = run_linebreak_gate(linebreak, lint_targets)
    cover_summary, cover_status = run_diagram_coverage_gate(coverage, lint_targets)
    cover_block = (
        "1g) 図解被覆 (DC1-DC6: 面が視覚構造を持っているか。既存 2 本が見るのは"
        "『見つけた図の質』で、図 0 個の面は検査対象が無いため両方緑になる) — hook が実行済み:\n"
        f"   判定: {COVERAGE_VERDICT_TEXT.get(cover_status, COVERAGE_VERDICT_TEXT['unknown'])}\n"
        f"   結果末尾:\n{cover_summary}\n"
        f'   再実行コマンド: python3 "{coverage}" <生成 HTML> [--min-ratio 0.5]\n'
        "   (分母を 3 つとも読むこと — faces / needs-figure / judged。judged が 0 のときの"
        " exit 2 は緑ではない。除外は面番号でなく面の型で決まり、除外した面と理由は DC4、"
        "機械が答えを出していない面は DC5 判定保留として毎回出る。DC5 は目視で決める)"
    )
    break_block = (
        "1f) 改行位置 (SR-3-09 / V-021: <br> が文節の切れ目か) — hook が実行済み:\n"
        f"   判定: {LINEBREAK_VERDICT_TEXT.get(break_status, LINEBREAK_VERDICT_TEXT['unknown'])}\n"
        f"   結果: {break_summary}\n"
        f'   再実行コマンド: node "{linebreak}" <生成 HTML>\n'
        "   (自己診断は --self-test。**exit code だけで判定しないこと** — "
        "対象 0 件と違反 0 件はどちらも exit 0 で、区別できるのは --json の verdict だけ)"
    )
    lint_verdict = LINT_VERDICT_TEXT.get(lint_status, LINT_VERDICT_TEXT["unknown"])
    lint_block = (
        "1b) 図解の静的契約 (D0-D28: viewBox 収容・marker 解決・最小フォント・線幅・"
        "4px グリッド・複雑度予算・accent 個数・斜め線・系列の符号) — hook が実行済み:\n"
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
        index_html = os.path.join(deck_dir, "index.html")
        remaining = HOOK_BUDGET_SEC - (time.monotonic() - _HOOK_START) - HOOK_BUDGET_MARGIN_SEC
        layout_summary, layout_status = run_slide_layout_gate(slide_layout, index_html, remaining)
        visual_summary, visual_status = run_visual_generation_gate(visual_gen, index_html)
        visual_block = (
            "1e) 面の生成則 (E1 強度差・E2 役割の配分・E4 反転ブロック・"
            "VGCONST 角丸/線幅/字面/影) — hook が実行済み (非 strict):\n"
            f"   判定: {VISUAL_VERDICT_TEXT.get(visual_status, VISUAL_VERDICT_TEXT['unknown'])}\n"
            f"   結果: {visual_summary}\n"
            f'   再実行コマンド: python3 "{visual_gen}" "{index_html}"\n'
            "   (閾値は検査器に直値を持たず references/visual-generation-rules.md から実行時に"
            "抽出する。条文を直したら同じ md の json ブロックも同時に直すこと。"
            "片方だけだと fail-closed で exit 3 になる)"
        )
        layout_block = (
            "1c) スライドの実描画レイアウト契約 (L1 重なり・L2 はみ出し・L3 溢れ・L4 図解面積・"
            "L5 余白・L6 文字量・L8 充填率・L8-font 書体下限・L9 縦の残余配分) — hook が実行済み"
            f" (viewport={LAYOUT_HOOK_VIEWPORT}・非 strict):\n"
            f"   判定: {LAYOUT_VERDICT_TEXT.get(layout_status, LAYOUT_VERDICT_TEXT['unknown'])}\n"
            f"   結果末尾:\n{layout_summary}\n"
            f'   再実行コマンド (既定 2 viewport): node "{slide_layout}" "{index_html}"\n'
            "   (L8/L9 は観測期のため hook は --strict を付けない。engine 既定の面が "
            "fill_policy / vertical_margin_policy のレンジへ収まったのを確認してから "
            "--strict へ昇格する。出荷前に warning ごと失格にしたいときだけ手動で --strict を足す)"
        )
        mechanical = (
            "1) slide 機械評価 (broken img・はみ出し・computed フォント・16:9 等の静的/動的検証):\n"
            f'   node "{evaluator}" "{deck_dir}"\n'
            "   (Chromium 未導入なら scripts/setup-playwright.py --install 後に再実行)\n"
            f"{lint_block}\n"
            f"{layout_block}\n"
            f"{info_block}\n"
            f"{visual_block}\n"
            f"{break_block}\n"
            f"{cover_block}"
        )
    else:
        layout_status = "n/a"  # report は下の validate-report-layout.js が担当する。
        visual_status = "n/a"  # 面を同定できるか未測定。理由は run_visual_generation_gate。
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
            f"{info_block}\n"
            f"{break_block}\n"
            f"{cover_block}"
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
    return ctx, lint_status, info_status, layout_status, visual_status, break_status, cover_status


def emit(mode: str, deck_dir: str) -> None:
    (ctx, lint_status, info_status, layout_status, visual_status, break_status,
     cover_status) = build_context(mode, deck_dir)
    deck_name = os.path.basename(os.path.normpath(deck_dir)) or deck_dir
    # 情報契約の error は「参照の取りこぼし」「孤立節点」の 2 件だけで、
    # どちらも構造から確定的に判る。幾何が緑でもここが赤なら図は成立していない
    # (主キーの無い ER 図は D 検査を全部通る) ので、合図を握り潰さない。
    # warning は合否に入れない — 入れると通すためだけに語を足す圧力が生まれる。
    # 実描画レイアウトの error (L1 重なり / L2 はみ出し / L3 溢れ / L7 体系混在 /
    # L8-font 書体下限割れ) は静的検査が原理的に見られないもので、かつ実描画で
    # 確定的に判る。静的が両方緑でもここが赤なら面は読めていないので先に出す。
    # L8/L9 の warning は観測期なので合図にしない (非 strict のため exit 0 側に入る)。
    if layout_status == "fail":
        message = (
            f"実描画レイアウト契約 (L1-L9) FAIL を検出: {deck_name} — "
            f"静的契約が緑でも面が読めていない (mode={mode})"
        )
    elif info_status == "fail" and lint_status != "fail":
        message = (
            f"図解情報契約 (I-ER-REF / I-REL-ISO) FAIL を検出: {deck_name} — "
            f"幾何 (D0-D28) は通っているが図として成立していない (mode={mode})"
        )
    elif visual_status == "fail" and lint_status != "fail":
        # 生成則の赤は「上限を超えた」ではなく「階層を作れていない」。他の検査が全部
        # 緑でもここが赤なら、面は平板なまま出ていく。既存 deck を再生成したときに
        # 出る赤は想定どおりで、黙らせずに出す。
        message = (
            f"面の生成則 (E1-E6 / VGCONST) FAIL を検出: {deck_name} — "
            f"上限の検査は通っているが面に階層が作れていない (mode={mode})"
        )
    elif cover_status == "fail" and lint_status != "fail":
        # 被覆の赤は「図の質が悪い」ではなく「面が図を持っていない」。他の検査は
        # 全部緑のまま通る (図が 0 個の面には、幾何にも情報にも検査対象が無い)。
        # **no-target は合図にしない** — 面を同定できない入力 (図解ゴールデンの
        # 断片など) へ当たったときに毎回鳴り、本物の赤を無視する運用を教育する。
        # additionalContext には「PASS ではない」と明記して残す。
        message = (
            f"図解被覆 (DC1/DC2) FAIL を検出: {deck_name} — "
            f"文字リストだけの面がある。既存の図解検査は図 0 個の面を検査対象と"
            f"見なさないため全部緑で通る (mode={mode})"
        )
    elif break_status == "fail" and lint_status != "fail":
        # 改行位置の赤は「文字数で折った」ことの証拠で、他の検査は全部緑のまま通る
        # (幾何も面積も充足するため)。**no-target は合図にしない** — 現時点の生成物は
        # <br> を 1 つも出さないので、未検査を合図にすると毎回鳴り、本物の赤を
        # 無視する運用を教育する。additionalContext には未検査と明記して残す。
        message = (
            f"改行位置 (SR-3-09 / V-021) FAIL を検出: {deck_name} — "
            f"<br> が文節の切れ目に無い (mode={mode})"
        )
    elif lint_status == "pass":
        message = f"生成後評価 (deck-evaluator, mode={mode}) を推奨: {deck_name}"
    elif lint_status == "fail":
        message = (
            f"図解静的契約 (D0-D28) FAIL を検出: {deck_name} — "
            f"修正して validate-svg-diagram.py PASS を確認すること (mode={mode})"
        )
    elif lint_status == "no-target":
        # 「対象 0 件」を PASS と言わない。ブロックもしない (exit 0 は維持) が、
        # 保証が発行されていない事実だけは必ず伝える。
        message = (
            f"図解静的契約 (D0-D28) は未検査 (対象 0 件): {deck_name} — "
            f"PASS ではない。図解がある想定なら抽出されない理由を確認すること (mode={mode})"
        )
    else:
        message = (
            f"図解静的契約 (D0-D28) の判定不能: {deck_name} — "
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

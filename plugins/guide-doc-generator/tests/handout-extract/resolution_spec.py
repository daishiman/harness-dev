"""/handout-extract (C08) の引数解決の正解表 (オラクル)。

`command-brief-C08.json` の `arguments[]` と `failure_modes` から起こした、
「argv とファイルシステムの状態」→「解決結果と取る行動」の写像である。
テスト側がこの表を持ち、command 定義が宣言する `CR-EXTRACT-ARGS` ブロックを
この表と 13 通り全件で突き合わせる。

出典:
  - arguments[html-path] required=true / default="なし" /
    「ディレクトリを渡された場合は展開せず停止する」
  - arguments[--out] default="入力 HTML と同じディレクトリの handout-config.json" /
    「既存ファイルがある場合は黙って上書きせず、上書き可否を確認する」/
    「逆抽出レポートは --out と同じディレクトリへ併置する」
  - failure_modes「html-path 未指定 / 不在 / ディレクトリ指定」→ 委譲先を起動せず停止
  - behavior 1「html-path が無い / 存在しない / ディレクトリの場合は委譲先を起動せず停止する」

標準ライブラリのみ。
"""

from __future__ import annotations

import posixpath
from collections import namedtuple

# --------------------------------------------------------------------------
# 語彙
# --------------------------------------------------------------------------

# case が使う固定の引数値 (相対パスで揃える)
HTML_ARG = "docs/handout.html"
HTML_DIR = "docs"
OUT_ARG = "artifacts/extracted-config.json"

#: html-path が指す先の状態。"absent" は positional そのものが無い場合。
HTML_STATES = ("file", "missing", "dir", "absent")

#: command が取りうる行動。
ACTIONS = ("delegate", "confirm-overwrite", "stop")

#: 停止理由の語彙 (brief failure_modes 1 の 3 分岐に 1:1 で対応する)。
STOP_REASONS = (
    "html-path-missing",       # positional 未指定
    "html-path-not-found",     # 指定されたが存在しない
    "html-path-is-directory",  # ディレクトリを渡された
)

#: --out の既定値テンプレート。{html_dir} だけを展開する。
DEFAULT_OUT_TEMPLATE = "{html_dir}/handout-config.json"

#: 逆抽出レポートの配置テンプレート。{out_dir} だけを展開する。
REPORT_PLACEMENT_TEMPLATE = "{out_dir}"

Case = namedtuple("Case", ["name", "html_state", "out_given", "out_exists"])


class SpecError(Exception):
    """宣言された CR-EXTRACT-ARGS ブロックが解釈できないときに送出する。"""


# --------------------------------------------------------------------------
# 入力空間
# --------------------------------------------------------------------------


def enumerate_cases():
    """13 通りの入力を列挙する (positional 欠落 1 + 3 状態 x --out 2 x 既存 2)。"""
    cases = [Case("no-positional", "absent", False, False)]
    for html_state in ("file", "missing", "dir"):
        for out_given in (False, True):
            for out_exists in (False, True):
                cases.append(
                    Case(
                        name=f"{html_state}/out={'given' if out_given else 'default'}"
                        f"/exists={'yes' if out_exists else 'no'}",
                        html_state=html_state,
                        out_given=out_given,
                        out_exists=out_exists,
                    )
                )
    return cases


def case_argv(case: Case):
    """case に対応する $ARGUMENTS の並びを返す (宣言例の可読性のため)。"""
    if case.html_state == "absent":
        return []
    argv = [HTML_ARG]
    if case.out_given:
        argv += ["--out", OUT_ARG]
    return argv


# --------------------------------------------------------------------------
# 正解表
# --------------------------------------------------------------------------


def _result(action, *, stop_reason=None, out=None):
    return {
        "action": action,
        "stop_reason": stop_reason,
        "out": out,
        "report_dir": None if out is None else (posixpath.dirname(out) or "."),
    }


def expected(case: Case):
    """brief から起こした正解。入口検証 → --out 解決 → 上書き確認 の順。"""
    if case.html_state == "absent":
        return _result("stop", stop_reason="html-path-missing")
    if case.html_state == "missing":
        return _result("stop", stop_reason="html-path-not-found")
    if case.html_state == "dir":
        return _result("stop", stop_reason="html-path-is-directory")

    out = OUT_ARG if case.out_given else posixpath.join(HTML_DIR, "handout-config.json")
    if case.out_exists:
        # 黙って上書きせず、上書き可否を確認する (委譲はその後)。
        return _result("confirm-overwrite", out=out)
    return _result("delegate", out=out)


# --------------------------------------------------------------------------
# 宣言されたブロックの解釈
# --------------------------------------------------------------------------


def _expand(template, **values):
    if not isinstance(template, str):
        raise SpecError(f"テンプレートが文字列でない: {template!r}")
    try:
        return template.format(**values)
    except KeyError as exc:
        raise SpecError(f"テンプレート {template!r} が未知のプレースホルダ {exc} を使っている")
    except (IndexError, ValueError) as exc:
        raise SpecError(f"テンプレート {template!r} を展開できない: {exc}")


def _matches(when, case: Case, out_exists_getter):
    if not isinstance(when, dict) or not when:
        raise SpecError(f"preconditions[].when が空か dict でない: {when!r}")
    for key, value in when.items():
        if key == "positional_present":
            if bool(value) != (case.html_state != "absent"):
                return False
        elif key == "html_path":
            if case.html_state == "absent" or value != case.html_state:
                return False
        elif key == "out_exists":
            if bool(value) != out_exists_getter():
                return False
        else:
            raise SpecError(f"preconditions[].when に未知のキー {key!r} がある")
    return True


def resolve_declared(block, case: Case):
    """command 定義が宣言した CR-EXTRACT-ARGS ブロックを case に適用する。"""
    if not isinstance(block, dict):
        raise SpecError("CR-EXTRACT-ARGS ブロックが object でない")

    flags = block.get("flags")
    if not isinstance(flags, dict) or "--out" not in flags:
        raise SpecError("flags['--out'] の宣言が無い")
    out_spec = flags["--out"]
    if not isinstance(out_spec, dict):
        raise SpecError("flags['--out'] が object でない")

    def out_value():
        if case.out_given:
            return OUT_ARG
        return _expand(out_spec.get("default"), html_dir=HTML_DIR)

    preconditions = block.get("preconditions")
    if not isinstance(preconditions, list) or not preconditions:
        raise SpecError("preconditions の宣言が無い")

    for rule in preconditions:
        if not isinstance(rule, dict):
            raise SpecError(f"preconditions の要素が object でない: {rule!r}")
        if not _matches(rule.get("when"), case, lambda: case.out_exists):
            continue
        action = rule.get("action")
        if action not in ACTIONS:
            raise SpecError(f"未知の action {action!r} (許されるのは {ACTIONS})")
        if action == "stop":
            reason = rule.get("reason")
            if reason not in STOP_REASONS:
                raise SpecError(f"未知の stop reason {reason!r} (許されるのは {STOP_REASONS})")
            return _result("stop", stop_reason=reason)
        out = out_value()
        return _result(action, out=out)

    out = out_value()
    report_dir = _expand(
        block.get("report_placement"),
        out_dir=posixpath.dirname(out) or ".",
    )
    result = _result("delegate", out=out)
    result["report_dir"] = report_dir
    return result


def declared_stop_reasons(block):
    """宣言側が使っている stop reason の集合を返す。"""
    reasons = set()
    for rule in (block or {}).get("preconditions") or []:
        if isinstance(rule, dict) and rule.get("action") == "stop":
            reasons.add(rule.get("reason"))
    return reasons


def diff_against_oracle(block):
    """全 case を突き合わせ、食い違いの一覧を返す。"""
    mismatches = []
    for case in enumerate_cases():
        want = expected(case)
        got = resolve_declared(block, case)
        if got != want:
            mismatches.append((case, want, got))
    return mismatches

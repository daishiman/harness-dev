"""C10 guard-handout-external-ref (PostToolUse hook) 受入テストの共通ハーネス。

このモジュール自体はテストを持たない (discover の pattern test_*.py に一致しない)。
契約の正本は次の 2 つであり、ここには「契約をどう観測するか」だけを置く:

  - plugin-plans/guide-doc-generator/briefs/hook-brief-C10.json  (適用範囲・入出力・exit)
  - plugin-plans/guide-doc-generator/briefs/script-brief-C16.json (canonical_rules CR-EXT / CR-EMOJI)

判定規則そのもの (外部スキームの列挙・絵文字コードポイントの列挙) は
テスト側にも置かない。C10 が C16 と一致することは test_parity_with_c16.py が
C16 の module_api を正解として突き合わせる形で検査する。

実装が未着手のあいだ require_hook() は AssertionError を投げる。
これにより各テストは error ではなく failure (赤) として記録される。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parents[1]          # plugins/guide-doc-generator
REPO_ROOT = TESTS_DIR.parents[3]            # repo root

HOOK = PLUGIN_ROOT / "hooks" / "guard-handout-external-ref.py"
C16_SCRIPT = PLUGIN_ROOT / "scripts" / "verify-handout-selfcontained.py"

#: 走査予算の正本 (hook-brief-C10.json#budget_thresholds.canonical_location)
BUDGET_CONFIG = PLUGIN_ROOT / "config" / "handout-output.json"
BUDGET_SECTION_KEY = "size_limits"
BUDGET_KEY = "hook_scan_budget"

# output_contract.block の stderr 先頭 (hook-brief-C10.json#output_contract.block)
BLOCK_PREFIX = "[guard-handout-external-ref] BLOCKED:"

D1 = "D1-external-url-attr"
D2 = "D2-emoji"

def scan_budget():
    """fail_closed_scope (c) の走査予算を **config から実測で** 読む。

    数値をここへ写すとテストが第 2 正本になり、config を変えた瞬間に
    「上限超え」fixture が上限未満へ落ちて検査が黙って空振りする。
    acceptance_checks[10] も『閾値はテスト側も config から読み、テストに
    数値を焼かない』を明示的に要求している。

    キーが無い / 型が違う場合は既定値へ倒さず AssertionError で赤にする
    (倒すと config 不在という不具合そのものを見逃す)。
    """
    if not BUDGET_CONFIG.is_file():
        raise AssertionError("走査予算の正本が存在しない: {}".format(BUDGET_CONFIG))
    try:
        data = json.loads(BUDGET_CONFIG.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise AssertionError("{} が JSON として読めない: {}".format(BUDGET_CONFIG, exc))
    section = data.get(BUDGET_SECTION_KEY)
    if not isinstance(section, dict) or BUDGET_KEY not in section:
        raise AssertionError(
            "{}#{}.{} が無い。hook はこのキーを正本として参照しており、"
            "不在なら全経路で未検査 (exit0 + systemMessage) になる "
            "(hook-brief-C10.json#budget_thresholds.if_key_missing)".format(
                BUDGET_CONFIG, BUDGET_SECTION_KEY, BUDGET_KEY))
    budget = section[BUDGET_KEY]
    if not isinstance(budget, dict):
        raise AssertionError("{} は object でなければならない: {!r}".format(BUDGET_KEY, budget))
    out = {}
    for key in ("max_bytes", "max_seconds"):
        value = budget.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise AssertionError(
                "{}.{} は正の数でなければならない: {!r}".format(BUDGET_KEY, key, value))
        out[key] = value
    return out


def size_limit_bytes():
    """走査予算の max_bytes (バイト)。"""
    return int(scan_budget()["max_bytes"])


def time_budget_seconds():
    """走査予算の max_seconds (秒)。"""
    return float(scan_budget()["max_seconds"])


def require_hook():
    """実装が存在しなければ赤で落とす。"""
    if not HOOK.exists():
        raise AssertionError(
            "未実装: {} が存在しない。P05 でこの build_target を実装すること "
            "(hook-brief-C10.json#build_target)".format(HOOK)
        )


def require_c16():
    if not C16_SCRIPT.exists():
        raise AssertionError(
            "未実装: {} が存在しない (C10 の判定正本。rule_delegation.canonical_owner)".format(C16_SCRIPT)
        )


def load_c16():
    """C16 を module_api の作法どおりに読み込む (rule_delegation.how と同じ)。"""
    import importlib.util

    require_c16()
    spec = importlib.util.spec_from_file_location("hb_selfcontained", C16_SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("module として読み込めない: {}".format(C16_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hook_source():
    require_hook()
    return HOOK.read_text(encoding="utf-8")


def hook_code_only():
    """hook 本体から コメントと docstring を除いた『実行される側』を返す。

    規則本文の非複製検査 (acceptance_checks[13][14]) は説明文ではなくコードに
    対して行う。設計意図を日本語コメントで書くことは禁じていない。
    """
    import ast
    import re as _re

    src = hook_source()
    lines = src.splitlines()
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:  # 実装が壊れているなら赤で知らせる
        raise AssertionError("hook 本体が Python として構文解析できない: {}".format(exc))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            for i in range(first.lineno - 1, first.end_lineno):
                lines[i] = ""
    return _re.sub(r"#.*", "", "\n".join(lines))


class Result:
    __slots__ = ("rc", "out", "err")

    def __init__(self, rc, out, err):
        self.rc = rc
        self.out = out
        self.err = err

    def __repr__(self):  # 失敗時の可読性のため
        return "Result(rc={!r}, out={!r}, err={!r})".format(self.rc, self.out, self.err)

    # --- stderr (output_contract.block) ---
    def blocked(self):
        return self.rc == 2

    def block_lines(self):
        return [l for l in self.err.splitlines() if l.strip()]

    def mentions(self, detection_id):
        return any(detection_id in l for l in self.err.splitlines())

    # --- stdout (output_contract.abort) ---
    def system_message(self):
        """打ち切りの systemMessage JSON (1 行) を返す。無ければ None。"""
        lines = [l for l in self.out.splitlines() if l.strip()]
        if len(lines) != 1:
            return None
        try:
            obj = json.loads(lines[0])
        except ValueError:
            return None
        if not isinstance(obj, dict) or "systemMessage" not in obj:
            return None
        return obj


# --------------------------------------------------------------------------
# fixture
# --------------------------------------------------------------------------

_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>配布資料</title>
<style>:root{--fg:#111}body{font-family:system-ui,"Hiragino Sans",sans-serif}</style>
<!--HEAD-->
</head>
<body>
<nav class="navbar"><a href="#s1">導入</a><a href="#s2">まとめ</a></nav>
<section id="s1"><h2>導入</h2><p>本日の狙いを 3 点で確認します。</p></section>
<section id="s2"><h2>まとめ</h2>
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==" alt="構成図">
<!--EXTRA-->
</section>
</body>
</html>
"""


#: hook-brief-C10.json#detection_rules[D1].violation_example そのもの
EXTERNAL_LINK = ('<link rel="stylesheet" '
                 'href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP">')
#: hook-brief-C10.json#detection_rules[D2].violation_example そのもの
EMOJI_HEADING = "<h2>ポイント \U0001F680 3 つ</h2>"


def clean_html(extra="", head=""):
    """外部参照 0 件・絵文字 0 件の土台 (output_contract.pass の期待入力)。"""
    return _TEMPLATE.replace("<!--EXTRA-->", extra).replace("<!--HEAD-->", head)


def external_html():
    """D1 が必ず 1 件立つ HTML。"""
    return clean_html(head=EXTERNAL_LINK)


def emoji_html():
    """D2 が必ず 1 件立つ HTML。"""
    return clean_html(extra=EMOJI_HEADING)


def line_of(html_text, needle):
    """needle が現れる 1 始まりの行番号 (stderr の行番号検査用)。"""
    for i, line in enumerate(html_text.splitlines(), start=1):
        if needle in line:
            return i
    raise AssertionError("fixture に {!r} が無い".format(needle))


class C10TestCase(unittest.TestCase):
    """hook を PostToolUse 契約どおりに stdin 起動して観測するテストの土台。"""

    #: applies_to (5) を満たすディレクトリ名
    IN_SCOPE_DIR = "2026-08-17-lecture-生成AIの業務活用入門"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hb-c10-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    # --- 入力の組み立て ---
    def make_dir(self, name, with_config=True):
        d = self.tmp / name
        d.mkdir(parents=True, exist_ok=True)
        if with_config:
            (d / "handout-config.json").write_text("{}\n", encoding="utf-8")
        return d

    def make_target(self, html_text, filename="handout.html",
                    dirname=None, with_config=True):
        """applies_to を満たす (既定) 書込先ファイルを作ってパスを返す。"""
        d = self.make_dir(self.IN_SCOPE_DIR if dirname is None else dirname,
                          with_config=with_config)
        p = d / filename
        p.write_text(html_text, encoding="utf-8")
        return p

    # --- 実行 ---
    def run_hook_raw(self, stdin_text, hook_path=None):
        require_hook()
        # 実体解決は hook 自身の 4 段解決に委ねる。呼び出し側の shell に
        # HB_ROOT / CLAUDE_PLUGIN_ROOT が残っていると、複製 root を指した
        # 起動が黙って正本の config を読んでしまい検査が空になる。
        env = dict(os.environ)
        for name in ("HB_ROOT", "CLAUDE_PLUGIN_ROOT"):
            env.pop(name, None)
        proc = subprocess.run(
            [sys.executable, str(hook_path or HOOK)],
            input=stdin_text, capture_output=True, text=True,
            cwd=str(self.tmp), timeout=120, env=env,
        )
        return Result(proc.returncode, proc.stdout, proc.stderr)

    def payload(self, path=None, tool_name="Write", path_key="file_path", **extra):
        p = {"tool_name": tool_name,
             "hook_event_name": "PostToolUse",
             "tool_input": {},
             "tool_response": {"success": True},
             "cwd": str(self.tmp)}
        if path is not None:
            p["tool_input"][path_key] = str(path)
        p["tool_input"].update(extra.pop("tool_input", {}))
        p.update(extra)
        return p

    def run_hook(self, payload_obj, hook_path=None):
        return self.run_hook_raw(json.dumps(payload_obj, ensure_ascii=False),
                                 hook_path=hook_path)

    def run_on(self, html_text, **kw):
        """in-scope な handout.html へ html_text を書いた状態で hook を起動する。"""
        target = self.make_target(html_text,
                                  filename=kw.pop("filename", "handout.html"),
                                  dirname=kw.pop("dirname", None),
                                  with_config=kw.pop("with_config", True))
        return self.run_hook(self.payload(target, **kw))

    # --- 断言ヘルパ ---
    def assertPassSilently(self, res, msg=""):
        """output_contract.pass: exit 0 / stdout・stderr とも無出力。"""
        self.assertEqual(0, res.rc, "exit 0 (素通し) を期待した {}\n{}".format(msg, res))
        self.assertEqual("", res.out.strip(), "stdout は無出力を期待した {}\n{}".format(msg, res))
        self.assertEqual("", res.err.strip(), "stderr は無出力を期待した {}\n{}".format(msg, res))

    def assertBlocked(self, res, detection_id, msg=""):
        """output_contract.block: exit 2 / stderr に BLOCKED 見出しと detection id。"""
        self.assertEqual(2, res.rc, "違反時は exit 2 {}\n{}".format(msg, res))
        self.assertIn(BLOCK_PREFIX, res.err,
                      "stderr の先頭に {!r} が要る {}\n{}".format(BLOCK_PREFIX, msg, res))
        self.assertTrue(res.err.startswith(BLOCK_PREFIX),
                        "BLOCKED 見出しは stderr の先頭 {}\n{}".format(msg, res))
        self.assertTrue(res.mentions(detection_id),
                        "stderr に {} が出ていない {}\n{}".format(detection_id, msg, res))

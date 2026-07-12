#!/usr/bin/env python3
"""PreToolUse hook `guard-mfk-no-reinvent.py` の再発明/TODO(human) 遮断の回帰テスト。

守るべき不変条件 (現行の実挙動を忠実に固定する・理想化しない):
  - 照合ドメイン文脈で `TODO(human)` を **コード**に書く Write/Edit/MultiEdit は exit 2 で遮断 (R1)。
  - 正本 (mfk_reconcile.py / reconcile_invoices.py) 以外の新規ファイルへ照合エンジンを
    再実装する `def classify`/`def reconcile` 等は exit 2 で遮断 (R2)。
  - 正本ファイル自身の編集 (allowlist)・ドキュメント (.md)・テスト (/tests/) は対象外で許可。
  - **ドメイン信号が無いコンテンツは一切遮断しない** (他プロジェクトの正当な TODO(human)/
    classify を誤遮断しない)。
  - Write/Edit/MultiEdit 以外の tool は対象外で許可。

guard はファイル名にハイフンを含むため通常 import できない。importlib の SourceFileLoader で
module ロードし `main()`/`evaluate()` を直接呼ぶ経路と、実 hook を subprocess で起動して exit
code を見る経路の両方で境界を固定する。
"""
import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest


_HOOK_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "hooks", "guard-mfk-no-reinvent.py")
)


def _load_guard():
    spec = importlib.util.spec_from_file_location("guard_mfk_no_reinvent", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load_guard()


def _run_main(payload, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload, ensure_ascii=False)))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    return guard.main()


def _run_subprocess(payload):
    proc = subprocess.run(
        [sys.executable, _HOOK_PATH],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stderr


def _write(file_path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}


# --- R1: TODO(human) をドメイン文脈のコードに書くと遮断 -----------------------------

def test_todo_human_in_domain_code_is_blocked(monkeypatch):
    payload = _write(
        "/repo/reconcile_judgments.py",
        "def classify(sheet_row, mf_match):\n    # 請求確認シート×MF掛け払い照合\n    TODO(human)\n",
    )
    assert _run_main(payload, monkeypatch) == 2


def test_todo_human_block_mentions_existing_engine(monkeypatch):
    payload = _write("/repo/x.py", "# mfk_reconcile 照合\nTODO(human)\n")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload, ensure_ascii=False)))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    assert guard.main() == 2
    assert "lib/mfk_reconcile.py" in err.getvalue()


def test_todo_human_without_domain_is_allowed(monkeypatch):
    # 別プロジェクトの正当な TODO(human) は誤遮断しない (ドメイン信号なし)。
    payload = _write("/other/project/foo.py", "def helper():\n    TODO(human)\n")
    assert _run_main(payload, monkeypatch) == 0


# --- R2: 正本以外への照合エンジン再実装を遮断 ----------------------------------------

def test_reinvented_classify_in_new_file_is_blocked(monkeypatch):
    payload = _write(
        "/repo/my_reconcile.py",
        "def reconcile(contracts, mf_index):\n    return 発行漏れ判定\n",
    )
    assert _run_main(payload, monkeypatch) == 2


def test_reinvent_block_points_to_canonical_entry(monkeypatch):
    payload = _write("/repo/my_reconcile.py", "請求確認シート\ndef classify(row):\n    pass\n")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload, ensure_ascii=False)))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    assert guard.main() == 2
    assert "reconcile_invoices.py" in err.getvalue()
    assert "mfk_reconcile.py" in err.getvalue()


def test_reinvent_def_without_domain_is_allowed(monkeypatch):
    # 無関係な classify (ML 等) はドメイン信号が無ければ通す。
    payload = _write("/ml/model.py", "def classify(image):\n    return label\n")
    assert _run_main(payload, monkeypatch) == 0


# --- C05 名前ゆらぎ回帰 (SS-F1): period-report 分類エンジンの語幹前方一致 -------------
# 完全一致だと compare_periods / classify_period_transition / diff_prev_curr 等の派生名が
# すり抜け C05 の再発明遮断が vacuous 化する。C05 実関数名を語幹で捕捉することを byte 固定する。


@pytest.mark.parametrize(
    "reinvent_def",
    [
        "def compare_periods(prev_set, curr_set):\n    pass\n",          # C05 実関数名 (compare 語幹)
        "def classify_period_transition(prev, curr):\n    pass\n",      # C05 実関数名 (classify 語幹)
        "def build_period_diff(prev, curr):\n    pass\n",               # period_diff 語幹
        "def diff_prev_curr_compare(a, b):\n    pass\n",                # 派生名 (compare 語幹)
    ],
)
def test_period_report_reinvention_in_new_file_is_blocked(monkeypatch, reinvent_def):
    # 非 sanctioned なドメインファイルへ前月↔今月比較エンジンを再実装すると遮断される。
    payload = _write("/repo/my_period_report.py", "# 先月と今月の比較 発行漏れレポート\n" + reinvent_def)
    assert _run_main(payload, monkeypatch) == 2


@pytest.mark.parametrize(
    "reinvent_def",
    [
        "def compare_periods(prev_set, curr_set):\n    pass\n",
        "def classify_period_transition(prev, curr):\n    pass\n",
        "def build_period_diff(prev, curr):\n    pass\n",
    ],
)
def test_period_report_engine_in_sanctioned_file_is_allowed(monkeypatch, reinvent_def):
    # C05 正本 mfk_period_report.py 自身は分類系関数を持ってよい (sanctioned)。
    payload = _write(
        "/p/scripts/mfk_period_report.py", "# 先月と今月の比較 発行漏れレポート\n" + reinvent_def
    )
    assert _run_main(payload, monkeypatch) == 0


def test_period_report_reinvention_without_domain_is_allowed(monkeypatch):
    # ドメイン信号が無ければ compare 系も誤遮断しない (他プロジェクトの正当な compare)。
    payload = _write("/other/util.py", "def compare_periods(a, b):\n    return a == b\n")
    assert _run_main(payload, monkeypatch) == 0


# --- allowlist / 対象外 -----------------------------------------------------------

def test_editing_sanctioned_engine_is_allowed(monkeypatch):
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/p/lib/mfk_reconcile.py",
            "new_string": "def classify(contracts, mf_index, target_ym):\n    # 請求確認シート照合\n    ...\n",
        },
    }
    assert _run_main(payload, monkeypatch) == 0


def test_todo_human_in_sanctioned_engine_is_still_blocked(monkeypatch):
    # allowlist は R2 (再実装) のみ免除。R1 (判定丸投げ) は正本上でも意図的に遮断する。
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/p/lib/mfk_reconcile.py",
            "new_string": "def classify(contract, mf):\n    # 請求確認シート照合の判定\n    TODO(human)\n",
        },
    }
    assert _run_main(payload, monkeypatch) == 2


def test_sanctioned_orchestrator_is_allowed(monkeypatch):
    payload = _write(
        "/p/scripts/reconcile_invoices.py",
        "# 請求確認シート orchestrator\ndef reconcile_main():\n    pass\n",
    )
    assert _run_main(payload, monkeypatch) == 0


def test_markdown_doc_is_exempt(monkeypatch):
    # README/SKILL が反パターンを文章で説明・引用するのは正当。
    payload = _write(
        "/p/README.md",
        "請求確認シート照合では `TODO(human)` を使わず classify を呼ぶ。",
    )
    assert _run_main(payload, monkeypatch) == 0


def test_tests_dir_is_exempt(monkeypatch):
    # hook 自身の回帰テストが fixture として TODO(human) / classify を持てるように。
    payload = _write(
        "/p/tests/test_x.py",
        "請求確認シート\ndef classify(x):\n    TODO(human)\n",
    )
    assert _run_main(payload, monkeypatch) == 0


# --- tool 種別・MultiEdit ----------------------------------------------------------

def test_non_write_tool_is_ignored(monkeypatch):
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo TODO(human) 請求確認シート"}}
    assert _run_main(payload, monkeypatch) == 0


def test_bash_heredoc_reinvented_classify_is_blocked(monkeypatch):
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                "cat > reconcile_judgments.py <<'PY'\n"
                "# 請求確認シート × MF掛け払い 照合\n"
                "def classify(sheet_row, mf_match):\n"
                "    TODO(human)\n"
                "PY\n"
            )
        },
    }
    assert _run_main(payload, monkeypatch) == 2


def test_bash_readonly_search_for_reinvent_terms_is_allowed(monkeypatch):
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "rg 'def classify|TODO\\\\(human\\\\)' plugins/mf-kessai-invoice-check"
        },
    }
    assert _run_main(payload, monkeypatch) == 0


def test_bash_todo_human_in_sanctioned_file_is_blocked(monkeypatch):
    # F-5: SANCTIONED ファイルへの Bash 書込でも TODO(human)(R1) は遮断する (Write/Edit と対称)。
    # allowlist は R2(再実装)のみ免除し、R1(判定丸投げ)は正本を含む全ドメインファイルへ適用する。
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                "cat > scripts/mfk_period_report.py <<'PY'\n"
                "# 先月と今月の比較 発行漏れレポート\n"
                "def classify_period(prev, curr):\n"
                "    TODO(human)\n"
                "PY\n"
            )
        },
    }
    assert _run_main(payload, monkeypatch) == 2


def test_bash_sanctioned_clean_write_is_still_allowed(monkeypatch):
    # F-5 の裏: sanctioned ファイルへの TODO(human) 無し再実装は許可 (R2 免除・R1 非該当)。
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                "cat > scripts/mfk_period_report.py <<'PY'\n"
                "# 先月と今月の比較 発行漏れレポート\n"
                "def compare_periods(prev, curr):\n"
                "    return prev == curr\n"
                "PY\n"
            )
        },
    }
    assert _run_main(payload, monkeypatch) == 0


def test_multiedit_reinvention_is_blocked(monkeypatch):
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "/repo/adhoc.py",
            "edits": [
                {"old_string": "a", "new_string": "# 掛け払い照合"},
                {"old_string": "b", "new_string": "def detect_orphans(mf, contracts):\n    pass\n"},
            ],
        },
    }
    assert _run_main(payload, monkeypatch) == 2


def test_empty_content_is_allowed(monkeypatch):
    assert _run_main(_write("/repo/x.py", ""), monkeypatch) == 0


# --- subprocess 経路で実 exit code を固定 -------------------------------------------

def test_subprocess_blocks_todo_human_in_domain():
    code, err = _run_subprocess(
        _write("/repo/reconcile_judgments.py", "請求確認シート\nTODO(human)\n")
    )
    assert code == 2
    assert "guard-mfk-no-reinvent" in err


def test_subprocess_allows_unrelated_write():
    code, _ = _run_subprocess(_write("/repo/notes.py", "x = 1\n"))
    assert code == 0


def test_malformed_payload_is_safe():
    proc = subprocess.run(
        [sys.executable, _HOOK_PATH], input="not json", capture_output=True, text=True
    )
    assert proc.returncode == 0

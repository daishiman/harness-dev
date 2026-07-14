# /// script
# name: test-parse-spec-diff
# purpose: parse-spec-diff.py (C08) の hunk 構造化・完全性ゲート (fail-closed exit2)・複数ファイル/hunk 積層を固定する pytest。scripts/tests/ 配下のため lint-script-frontmatter を充足する frontmatter を持つ。
# inputs:
#   - pytest: SCRIPT (../parse-spec-diff.py) を importlib と subprocess で駆動する
# outputs:
#   - pytest: assertion 結果 (0=緑)
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""parse-spec-diff.py (C08) の機能テスト。

C11 の complete=true な正規化完全 diff 集合を unified diff hunk 単位へ構造化する
決定論変換の受入・完全性ゲート (fail-closed exit2)・複数ファイル/hunk の積層を固定する。

- (a) 正常な unified diff → 期待 hunk 配列
- (b) complete:false 入力で exit2
- (c) digest mismatch で exit2
- (d) 複数ファイル・複数 hunk の積層パース
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "parse-spec-diff.py"


def _load_module():
    """ハイフン名スクリプトを importlib で file-path import する。"""
    spec = importlib.util.spec_from_file_location("parse_spec_diff", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


psd = _load_module()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _entry(diff: str, *, complete: bool = True, sha: str | None = None,
           base: str = "base0000", source: str = "src11111") -> dict:
    """C11 entry 形状 ({...,diff_sha256,complete,diff}) を組み立てる。"""
    return {
        "event_at": "2026-07-13T00:00:00Z",
        "history_heading": "chore: update yaml-spec-cache",
        "base_commit": base,
        "source_commit": source,
        "diff_sha256": sha if sha is not None else _sha(diff),
        "complete": complete,
        "diff": diff,
    }


def _payload(*entries: dict) -> dict:
    return {"entries": list(entries)}


def _run(payload, *, use_file=None):
    """スクリプトを subprocess で実行し (returncode, stdout, stderr) を返す。"""
    if use_file is not None:
        cmd = [sys.executable, str(SCRIPT), "--diffs", str(use_file)]
        inp = None
    else:
        cmd = [sys.executable, str(SCRIPT), "--stdin"]
        inp = json.dumps(payload)
    proc = subprocess.run(cmd, input=inp, capture_output=True, text=True)
    return proc


# ─────────────────── fixtures (diff テキスト) ───────────────────
DIFF_MODIFY = (
    "diff --git a/foo.txt b/foo.txt\n"
    "index e69de29..4b825dc 100644\n"
    "--- a/foo.txt\n"
    "+++ b/foo.txt\n"
    "@@ -1,3 +1,4 @@ def foo():\n"
    " line1\n"
    "-line2\n"
    "+line2-changed\n"
    "+line2b\n"
    " line3\n"
)

DIFF_ADD = (
    "diff --git a/new.py b/new.py\n"
    "new file mode 100644\n"
    "index 0000000..1234567\n"
    "--- /dev/null\n"
    "+++ b/new.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+import os\n"
    "+print(os)\n"
)

DIFF_DELETE = (
    "diff --git a/old.py b/old.py\n"
    "deleted file mode 100644\n"
    "index 1234567..0000000\n"
    "--- a/old.py\n"
    "+++ /dev/null\n"
    "@@ -1,2 +0,0 @@\n"
    "-gone1\n"
    "-gone2\n"
)

DIFF_MULTI_HUNK = (
    "diff --git a/mod.py b/mod.py\n"
    "index 111..222 100644\n"
    "--- a/mod.py\n"
    "+++ b/mod.py\n"
    "@@ -1,2 +1,2 @@\n"
    " keep\n"
    "-old\n"
    "+new\n"
    "@@ -10,3 +10,3 @@ context\n"
    " a\n"
    "-b\n"
    "+B\n"
    " c\n"
)


# ─────────────────── (a) 正常 unified diff → 期待 hunk 配列 ───────────────────
def test_single_modify_hunk_parsed():
    hunks = psd.transform(_payload(_entry(DIFF_MODIFY)))
    assert len(hunks) == 1
    h = hunks[0]
    assert h == {
        "source_commit": "src11111",
        "base_commit": "base0000",
        "diff_sha256": _sha(DIFF_MODIFY),
        "file_path": "foo.txt",
        "change_type": "modify",
        "old_start": 1,
        "old_lines": 3,
        "new_start": 1,
        "new_lines": 4,
        "added_lines": ["line2-changed", "line2b"],
        "removed_lines": ["line2"],
        "header": "@@ -1,3 +1,4 @@ def foo():",
    }


def test_add_hunk_change_type_and_dev_null_path():
    (h,) = psd.transform(_payload(_entry(DIFF_ADD)))
    assert h["change_type"] == "add"
    assert h["file_path"] == "new.py"
    assert h["old_lines"] == 0
    assert h["added_lines"] == ["import os", "print(os)"]
    assert h["removed_lines"] == []


def test_delete_hunk_change_type_and_dev_null_path():
    (h,) = psd.transform(_payload(_entry(DIFF_DELETE)))
    assert h["change_type"] == "delete"
    assert h["file_path"] == "old.py"
    assert h["new_lines"] == 0
    assert h["removed_lines"] == ["gone1", "gone2"]
    assert h["added_lines"] == []


def test_normal_run_exit0_and_stdout_json():
    proc = _run(_payload(_entry(DIFF_MODIFY)))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert isinstance(out, list) and len(out) == 1
    assert out[0]["file_path"] == "foo.txt"


def test_empty_diff_yields_zero_hunks_but_passes_gate():
    proc = _run(_payload(_entry("")))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == []


# ─────────────────── (b) complete:false → exit2 ───────────────────
def test_complete_false_exits_2():
    proc = _run(_payload(_entry(DIFF_MODIFY, complete=False)))
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""
    assert "fail-closed" in proc.stderr


def test_complete_missing_exits_2():
    entry = _entry(DIFF_MODIFY)
    del entry["complete"]
    proc = _run(_payload(entry))
    assert proc.returncode == 2


# ─────────────────── (c) digest mismatch → exit2 ───────────────────
def test_digest_mismatch_exits_2():
    proc = _run(_payload(_entry(DIFF_MODIFY, sha="deadbeef" * 8)))
    assert proc.returncode == 2
    assert "diff_sha256" in proc.stderr


def test_digest_missing_exits_2():
    entry = _entry(DIFF_MODIFY)
    del entry["diff_sha256"]
    proc = _run(_payload(entry))
    assert proc.returncode == 2


# ─────────────────── (d) 複数ファイル・複数 hunk の積層 ───────────────────
def test_multi_file_multi_hunk_stacked_across_entries():
    # entry1: 1 hunk (modify), entry2: add(1) + multi-hunk modify(2) = 3 hunks。
    entry1 = _entry(DIFF_MODIFY, base="b1", source="s1")
    entry2 = _entry(DIFF_ADD + DIFF_MULTI_HUNK, base="b2", source="s2")
    hunks = psd.transform(_payload(entry1, entry2))
    assert len(hunks) == 4

    # entry 出現順 → file 出現順 → hunk 出現順で安定していること。
    assert [h["file_path"] for h in hunks] == ["foo.txt", "new.py", "mod.py", "mod.py"]
    assert [h["change_type"] for h in hunks] == ["modify", "add", "modify", "modify"]

    # commit フィールドが entry 単位で継承されること。
    assert hunks[0]["source_commit"] == "s1" and hunks[0]["base_commit"] == "b1"
    for h in hunks[1:]:
        assert h["source_commit"] == "s2" and h["base_commit"] == "b2"

    # 2 hunk 目 (mod.py 前半) と 3 hunk 目 (mod.py 後半・section 付き header)。
    assert hunks[2]["header"] == "@@ -1,2 +1,2 @@"
    assert hunks[2]["added_lines"] == ["new"] and hunks[2]["removed_lines"] == ["old"]
    assert hunks[3]["old_start"] == 10 and hunks[3]["header"] == "@@ -10,3 +10,3 @@ context"
    assert hunks[3]["added_lines"] == ["B"] and hunks[3]["removed_lines"] == ["b"]


def test_multi_hunk_run_exit0():
    proc = _run(_payload(_entry(DIFF_MULTI_HUNK)))
    assert proc.returncode == 0, proc.stderr
    assert len(json.loads(proc.stdout)) == 2


# ─────────────────── 入出力チャネル / 一般エラー ───────────────────
def test_diffs_file_input(tmp_path):
    f = tmp_path / "c11.json"
    f.write_text(json.dumps(_payload(_entry(DIFF_MODIFY))), encoding="utf-8")
    proc = _run(None, use_file=f)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)[0]["file_path"] == "foo.txt"


def test_missing_file_exits_1():
    proc = _run(None, use_file="/no/such/c11.json")
    assert proc.returncode == 1


def test_invalid_json_exits_1():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--stdin"],
        input="not json", capture_output=True, text=True,
    )
    assert proc.returncode == 1


def test_missing_entries_key_exits_1():
    proc = _run({"latest_entry": {}})
    assert proc.returncode == 1


def test_help_exits_0():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "--diffs" in proc.stdout and "--stdin" in proc.stdout


def test_removed_line_starting_with_dashes_not_misread_as_header():
    # content 行 "--- old header text" が file header と誤認されないこと (budget 追跡)。
    diff = (
        "diff --git a/doc.md b/doc.md\n"
        "--- a/doc.md\n"
        "+++ b/doc.md\n"
        "@@ -1,2 +1,2 @@\n"
        "-- old header text\n"
        " keep\n"
        "++ new header text\n"
    )
    (h,) = psd.transform(_payload(_entry(diff)))
    assert h["removed_lines"] == ["- old header text"]
    assert h["added_lines"] == ["+ new header text"]
    assert h["file_path"] == "doc.md"

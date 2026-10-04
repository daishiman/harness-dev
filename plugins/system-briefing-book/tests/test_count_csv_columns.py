"""count-csv-columns.mjs: CSV の列を 空・固定・値 に分けて数える (値そのものは出さない)。"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import run_script

SCRIPT = "count-csv-columns"
# 引用符の中のカンマと改行、"" (引用符 1 文字) を含む。行の区切りは Excel と同じ CRLF
CSV = (
    "番号,相手,メモ,空欄,区分\r\n"
    '1,"東, 西","1 行目\n2 行目",,A\r\n'
    '2,"言う""はい""",,,A\r\n'
    "3,南,,,A\r\n"
)
EXPECTED = [
    {"no": 1, "name": "番号", "kind": "value", "filled": 3, "distinct": 3},
    {"no": 2, "name": "相手", "kind": "value", "filled": 3, "distinct": 3},
    {"no": 3, "name": "メモ", "kind": "fixed", "filled": 1, "distinct": 1},
    {"no": 4, "name": "空欄", "kind": "blank", "filled": 0, "distinct": 0},
    {"no": 5, "name": "区分", "kind": "fixed", "filled": 3, "distinct": 1},
]


def test_utf8_with_bom_splits_quoted_fields(tmp_path: Path) -> None:
    src = tmp_path / "出力.csv"
    src.write_bytes(CSV.encode("utf-8-sig"))
    rc, out, err = run_script(SCRIPT, "--src", str(src))
    assert rc == 0, err
    assert out["status"] == "ok" and out["encoding"] == "utf-8"
    assert out["rows"] == 3
    assert out["columns"] == EXPECTED
    assert out["counts"] == {"blank": 1, "fixed": 2, "value": 2}
    shown = json.dumps(out, ensure_ascii=False)
    assert "東, 西" not in shown and "はい" not in shown and "行目" not in shown


def test_shift_jis_is_read_when_utf8_fails(tmp_path: Path) -> None:
    src = tmp_path / "出力_sjis.csv"
    src.write_bytes(CSV.encode("shift_jis"))
    rc, out, err = run_script(SCRIPT, "--src", str(src))
    assert rc == 0, err
    assert out["encoding"] == "shift_jis"
    assert out["columns"] == EXPECTED

    # 文字コードを決めて渡したときは、読めなければ使い方の誤り
    rc, out, _ = run_script(SCRIPT, "--src", str(src), "--encoding", "utf-8")
    assert rc == 2 and out["status"] == "usage-error"


def test_missing_file_is_usage_error(tmp_path: Path) -> None:
    rc, out, _ = run_script(SCRIPT, "--src", str(tmp_path / "なし.csv"))
    assert rc == 2
    assert out["status"] == "usage-error"

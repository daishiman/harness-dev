"""Genuine functional tests for plugins/skill-intake/scripts/append_eval_log.py.

カバレッジ方針:
- 純関数 (parse_args / safe_read / iso_date / count_sections) を **in-process** で
  実値検証する。フラグ解析の各分岐・JSON 読込失敗の握りつぶし・section 数の
  各データ形 (sections list / 5_axes / five_axes / 非 dict) を境界込みで網羅。
- `main()` を argv 直渡しで駆動し、usage error (hint 欠落)・正常系 (self-update.json /
  intake.json 有無)・value_realized_score の型ガード・questions_added の 3 経路
  (candidates_applied 数値 / added_questions list / 既定 0)・status フォールバック・
  jsonl 追記 (append 維持) を検証する。
- すべての I/O は tmp_path 配下に限定し repo を汚さない。network/keychain/secret 系の
  依存はこのスクリプトには無い (pure file I/O) ため stub は不要。
- __main__ 経路は subprocess で実起動し exit code を確認する。

ファイル名は他ディレクトリ (scripts/scripts2/scripts3) と衝突しないよう `_r4` を付して
新規作成 (pytest basename 衝突回避)。
"""
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "append_eval_log.py"

_SPEC = importlib.util.spec_from_file_location("append_eval_log_s4", SCRIPT)
AEL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(AEL)


# ===================== parse_args =====================

def test_parse_args_all_flags():
    args = AEL.parse_args(["--hint", "my-hint", "--root", "/r", "--out", "/o"])
    assert args == {"hint": "my-hint", "root": "/r", "out": "/o"}


def test_parse_args_empty():
    assert AEL.parse_args([]) == {}


def test_parse_args_partial_hint_only():
    assert AEL.parse_args(["--hint", "h"]) == {"hint": "h"}


def test_parse_args_unknown_flags_ignored():
    # 未知フラグ・位置引数は黙って無視される
    args = AEL.parse_args(["--bogus", "x", "stray", "--hint", "h"])
    assert args == {"hint": "h"}


def test_parse_args_last_wins_on_duplicate():
    # 同じフラグが複数あれば最後が勝つ
    args = AEL.parse_args(["--hint", "first", "--hint", "second"])
    assert args["hint"] == "second"


# ===================== safe_read =====================

def test_safe_read_valid_json(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"k": "v", "n": 3}), encoding="utf-8")
    assert AEL.safe_read(p) == {"k": "v", "n": 3}


def test_safe_read_missing_file(tmp_path):
    # 不在ファイルは例外を握りつぶして None
    assert AEL.safe_read(tmp_path / "absent.json") is None


def test_safe_read_broken_json(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    assert AEL.safe_read(p) is None


def test_safe_read_non_object_json(tmp_path):
    # 配列など dict 以外も読めるが、本体側で `or {}` される
    p = tmp_path / "arr.json"
    p.write_text(json.dumps([1, 2]), encoding="utf-8")
    assert AEL.safe_read(p) == [1, 2]


# ===================== iso_date =====================

def test_iso_date_format():
    dt = datetime(2026, 6, 24, 9, 0, 0, tzinfo=timezone.utc)
    assert AEL.iso_date(dt) == "2026-06-24"


def test_iso_date_zero_pads():
    dt = datetime(2026, 1, 5, tzinfo=timezone.utc)
    assert AEL.iso_date(dt) == "2026-01-05"


# ===================== count_sections =====================

def test_count_sections_none():
    assert AEL.count_sections(None) == 0


def test_count_sections_empty_dict():
    # 空 dict は falsy ではない → sections/5_axes 無し → 0
    assert AEL.count_sections({}) == 0


def test_count_sections_sections_list():
    assert AEL.count_sections({"sections": ["a", "b", "c"]}) == 3


def test_count_sections_five_axes_underscore_prefix():
    # '5_axes' を採用
    assert AEL.count_sections({"5_axes": {"x": 1, "y": 2}}) == 2


def test_count_sections_five_axes_word_alias():
    # sections 不在時 'five_axes' を採用
    assert AEL.count_sections({"five_axes": {"a": 1}}) == 1


def test_count_sections_sections_takes_priority_over_axes():
    # sections list が優先 (axes より先に評価)
    assert AEL.count_sections({"sections": ["only-one"], "5_axes": {"a": 1, "b": 2}}) == 1


def test_count_sections_sections_not_list_falls_to_axes():
    # sections が list でなければ axes を見る
    assert AEL.count_sections({"sections": "nope", "5_axes": {"a": 1, "b": 2, "c": 3}}) == 3


def test_count_sections_axes_not_dict():
    # 5_axes が dict でなければ 0
    assert AEL.count_sections({"5_axes": ["not", "dict"]}) == 0


def test_count_sections_non_dict_input():
    assert AEL.count_sections(["list", "input"]) == 0
    assert AEL.count_sections("string") == 0


# ===================== main: usage error =====================

def test_main_usage_error_no_hint(capsys):
    rc = AEL.main(["--root", "/x"])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


# ===================== main: happy path & data shaping =====================

def _setup_output(root: Path, hint: str, self_update=None, intake=None):
    d = root / "output" / hint
    d.mkdir(parents=True, exist_ok=True)
    if self_update is not None:
        (d / "self-update.json").write_text(json.dumps(self_update), encoding="utf-8")
    if intake is not None:
        (d / "intake.json").write_text(json.dumps(intake), encoding="utf-8")


def _read_record_from_stdout(captured_out):
    payload = json.loads(captured_out)
    assert payload["ok"] is True
    return payload


def test_main_happy_full_record(tmp_path, capsys):
    _setup_output(
        tmp_path, "h1",
        self_update={
            "value_realized_score": 0.73,
            "candidates_applied": 4,
            "session_status": "done",
        },
        intake={"sections": ["a", "b"]},
    )
    out_dir = tmp_path / "log"
    rc = AEL.main(["--hint", "h1", "--root", str(tmp_path), "--out", str(out_dir)])
    assert rc == 0
    payload = _read_record_from_stdout(capsys.readouterr().out)
    rec = payload["record"]
    assert rec["hint"] == "h1"
    assert rec["value_realized_score"] == 0.73
    assert rec["sections_count"] == 2
    assert rec["questions_added"] == 4
    assert rec["status"] == "done"
    # ファイルが <date>.jsonl で作られ、record が 1 行追記されている
    date = AEL.iso_date(datetime.now(timezone.utc))
    f = out_dir / f"{date}.jsonl"
    assert f.exists()
    lines = f.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["hint"] == "h1"
    assert payload["file"] == str(f)


def test_main_missing_artifacts_defaults(tmp_path, capsys):
    # output/<hint>/ が存在しても両 json が無ければ既定値
    (tmp_path / "output" / "h2").mkdir(parents=True)
    out_dir = tmp_path / "log"
    rc = AEL.main(["--hint", "h2", "--root", str(tmp_path), "--out", str(out_dir)])
    assert rc == 0
    rec = _read_record_from_stdout(capsys.readouterr().out)["record"]
    assert rec["value_realized_score"] is None
    assert rec["sections_count"] == 0
    assert rec["questions_added"] == 0
    assert rec["status"] == "completed"   # 既定フォールバック


def test_main_questions_added_from_added_questions_list(tmp_path, capsys):
    # candidates_applied 不在 → added_questions の長さを使う
    _setup_output(
        tmp_path, "h3",
        self_update={"added_questions": ["q1", "q2", "q3"]},
    )
    rc = AEL.main(["--hint", "h3", "--root", str(tmp_path), "--out", str(tmp_path / "log")])
    assert rc == 0
    rec = _read_record_from_stdout(capsys.readouterr().out)["record"]
    assert rec["questions_added"] == 3


def test_main_questions_added_candidates_float_coerced(tmp_path, capsys):
    # candidates_applied が float でも int 化される
    _setup_output(tmp_path, "h4", self_update={"candidates_applied": 2.0})
    rc = AEL.main(["--hint", "h4", "--root", str(tmp_path), "--out", str(tmp_path / "log")])
    assert rc == 0
    rec = _read_record_from_stdout(capsys.readouterr().out)["record"]
    assert rec["questions_added"] == 2
    assert isinstance(rec["questions_added"], int)


def test_main_vrs_non_numeric_becomes_none(tmp_path, capsys):
    # value_realized_score が文字列なら None に落ちる (型ガード)
    _setup_output(tmp_path, "h5", self_update={"value_realized_score": "high"})
    rc = AEL.main(["--hint", "h5", "--root", str(tmp_path), "--out", str(tmp_path / "log")])
    assert rc == 0
    rec = _read_record_from_stdout(capsys.readouterr().out)["record"]
    assert rec["value_realized_score"] is None


def test_main_status_alias_status_field(tmp_path, capsys):
    # session_status 不在時 'status' を採用
    _setup_output(tmp_path, "h6", self_update={"status": "in_progress"})
    rc = AEL.main(["--hint", "h6", "--root", str(tmp_path), "--out", str(tmp_path / "log")])
    assert rc == 0
    rec = _read_record_from_stdout(capsys.readouterr().out)["record"]
    assert rec["status"] == "in_progress"


def test_main_sections_from_five_axes(tmp_path, capsys):
    _setup_output(tmp_path, "h7", intake={"5_axes": {"a": 1, "b": 2, "c": 3}})
    rc = AEL.main(["--hint", "h7", "--root", str(tmp_path), "--out", str(tmp_path / "log")])
    assert rc == 0
    rec = _read_record_from_stdout(capsys.readouterr().out)["record"]
    assert rec["sections_count"] == 3


def test_main_appends_multiple_records_same_day(tmp_path, capsys):
    # 2 回呼ぶと同一 jsonl に追記 (truncate しない)
    _setup_output(tmp_path, "h8", self_update={"candidates_applied": 1})
    out_dir = tmp_path / "log"
    AEL.main(["--hint", "h8", "--root", str(tmp_path), "--out", str(out_dir)])
    capsys.readouterr()
    AEL.main(["--hint", "h8", "--root", str(tmp_path), "--out", str(out_dir)])
    capsys.readouterr()
    date = AEL.iso_date(datetime.now(timezone.utc))
    lines = (out_dir / f"{date}.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_main_default_out_dir_under_root(tmp_path, capsys):
    # --out 省略時は root/eval-log/skill-intake 配下
    _setup_output(tmp_path, "h9", self_update={"candidates_applied": 0})
    rc = AEL.main(["--hint", "h9", "--root", str(tmp_path)])
    assert rc == 0
    payload = _read_record_from_stdout(capsys.readouterr().out)
    expected_dir = (tmp_path / "eval-log" / "skill-intake").resolve()
    assert Path(payload["file"]).parent == expected_dir
    assert expected_dir.exists()


def test_main_creates_nested_out_dir(tmp_path, capsys):
    # --out が深いパスでも mkdir(parents=True) で作られる
    _setup_output(tmp_path, "h10", self_update={"candidates_applied": 1})
    out_dir = tmp_path / "a" / "b" / "c"
    rc = AEL.main(["--hint", "h10", "--root", str(tmp_path), "--out", str(out_dir)])
    assert rc == 0
    assert out_dir.exists()


# ===================== __main__ subprocess =====================

def test_main_entrypoint_subprocess_happy(tmp_path):
    _setup_output(tmp_path, "sp1", self_update={"candidates_applied": 5},
                  intake={"sections": ["x"]})
    out_dir = tmp_path / "log"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--hint", "sp1",
         "--root", str(tmp_path), "--out", str(out_dir)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["record"]["questions_added"] == 5
    assert payload["record"]["sections_count"] == 1


def test_main_entrypoint_subprocess_usage_error(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "usage:" in proc.stderr

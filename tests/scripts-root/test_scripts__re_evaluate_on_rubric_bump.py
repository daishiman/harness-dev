"""re-evaluate-on-rubric-bump.py の genuine 機能テスト。

純関数 (parse_semver / iter_records / extract_version / extract_skill_identity) を
実入力で呼び実出力を assert する。main() は (1) subprocess で実引数なし実行し
returncode/出力を検証、(2) module 定数 (UPSTREAM_RUBRIC / EVAL_LOG_DIR) を tmp_path へ
monkeypatch して major-bump 検出ロジックを in-process で genuine に駆動する。
network/keychain/Notion 等の外部 I/O は存在しない (network: false)。
"""
import importlib.util
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "re-evaluate-on-rubric-bump.py"

SPEC = importlib.util.spec_from_file_location("re_evaluate_on_rubric_bump", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- parse_semver: 実入力 -> 実出力 ---

def test_parse_semver_basic_triple():
    assert MOD.parse_semver("2.5.9") == (2, 5, 9)


def test_parse_semver_embedded_in_text():
    # 文字列中の最初の semver-like を拾う
    assert MOD.parse_semver("rubric v3.0.1-rc") == (3, 0, 1)


def test_parse_semver_none_and_non_semver_return_none():
    assert MOD.parse_semver(None) is None
    assert MOD.parse_semver("") is None
    assert MOD.parse_semver("not-a-version") is None
    assert MOD.parse_semver("1.2") is None  # 三つ組でない


def test_parse_semver_accepts_non_str_via_str_coercion():
    # int を渡しても str() 変換され、semver が含まれなければ None
    assert MOD.parse_semver(123) is None


# --- iter_records: .json (object / array) と .jsonl ---

def test_iter_records_json_object(tmp_path):
    p = tmp_path / "single.json"
    p.write_text(json.dumps({"rubric_version": "1.0.0", "skill_name": "run-x"}), encoding="utf-8")
    recs = list(MOD.iter_records(p))
    assert recs == [{"rubric_version": "1.0.0", "skill_name": "run-x"}]


def test_iter_records_json_array_filters_non_dict(tmp_path):
    p = tmp_path / "arr.json"
    p.write_text(json.dumps([{"a": 1}, "stringentry", {"b": 2}]), encoding="utf-8")
    recs = list(MOD.iter_records(p))
    assert recs == [{"a": 1}, {"b": 2}]


def test_iter_records_jsonl_skips_blank_and_malformed(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text(
        '{"x": 1}\n'
        "\n"  # blank
        "not-json\n"  # malformed -> skipped
        '"a-string"\n'  # valid json but not dict -> skipped
        '{"y": 2}\n',
        encoding="utf-8",
    )
    recs = list(MOD.iter_records(p))
    assert recs == [{"x": 1}, {"y": 2}]


def test_iter_records_missing_file_yields_nothing(tmp_path):
    assert list(MOD.iter_records(tmp_path / "nope.json")) == []


def test_iter_records_malformed_json_object_file_yields_nothing(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert list(MOD.iter_records(p)) == []


# --- extract_version: キー優先順位 ---

def test_extract_version_prefers_rubric_version():
    rec = {"rubric_version": "4.1.0", "version": "1.0.0"}
    assert MOD.extract_version(rec) == (4, 1, 0)


def test_extract_version_falls_back_to_current_then_version():
    assert MOD.extract_version({"current_version": "2.0.0"}) == (2, 0, 0)
    assert MOD.extract_version({"version": "3.3.3"}) == (3, 3, 3)


def test_extract_version_none_when_absent():
    assert MOD.extract_version({"unrelated": "x"}) is None


# --- extract_skill_identity: キー優先順位 + source name ---

def test_extract_skill_identity_prefers_skill_name(tmp_path):
    src = tmp_path / "eval.json"
    out = MOD.extract_skill_identity({"skill_name": "run-foo", "proposer": "bob"}, src)
    assert out == "run-foo (from eval.json)"


def test_extract_skill_identity_falls_back_to_proposer(tmp_path):
    src = tmp_path / "eval2.json"
    out = MOD.extract_skill_identity({"proposer": "alice"}, src)
    assert out == "alice (from eval2.json)"


def test_extract_skill_identity_unknown_when_no_keys(tmp_path):
    src = tmp_path / "empty.json"
    assert MOD.extract_skill_identity({}, src) == "<unknown> (from empty.json)"


# --- main(): in-process で定数を tmp へ monkeypatch して genuine 駆動 ---

def _run_main_capture(monkeypatch, upstream, eval_dir):
    monkeypatch.setattr(MOD, "UPSTREAM_RUBRIC", upstream)
    monkeypatch.setattr(MOD, "EVAL_LOG_DIR", eval_dir)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = MOD.main()
    return rc, out.getvalue(), err.getvalue()


def test_main_missing_upstream_returns_0(monkeypatch, tmp_path):
    rc, out, err = _run_main_capture(monkeypatch, tmp_path / "none.json", tmp_path / "eval-log")
    assert rc == 0
    assert "upstream rubric not found" in err


def test_main_unparseable_upstream_version_returns_0(monkeypatch, tmp_path):
    up = tmp_path / "rubric.json"
    up.write_text(json.dumps({"rubric_version": "garbage"}), encoding="utf-8")
    rc, out, err = _run_main_capture(monkeypatch, up, tmp_path / "eval-log")
    assert rc == 0
    assert "could not parse upstream rubric_version" in err


def test_main_no_eval_log_dir_returns_0(monkeypatch, tmp_path):
    up = tmp_path / "rubric.json"
    up.write_text(json.dumps({"rubric_version": "3.0.0"}), encoding="utf-8")
    rc, out, err = _run_main_capture(monkeypatch, up, tmp_path / "missing-eval-log")
    assert rc == 0
    assert "no eval-log directory" in out


def test_main_empty_eval_log_dir_returns_0(monkeypatch, tmp_path):
    up = tmp_path / "rubric.json"
    up.write_text(json.dumps({"rubric_version": "3.0.0"}), encoding="utf-8")
    eval_dir = tmp_path / "eval-log"
    eval_dir.mkdir()
    rc, out, err = _run_main_capture(monkeypatch, up, eval_dir)
    assert rc == 0
    assert "eval-log/ is empty" in out


def test_main_no_major_bump_reports_ok(monkeypatch, tmp_path):
    up = tmp_path / "rubric.json"
    up.write_text(json.dumps({"rubric_version": "3.0.0"}), encoding="utf-8")
    eval_dir = tmp_path / "eval-log"
    eval_dir.mkdir()
    # past major == current major -> no major bump
    (eval_dir / "a.json").write_text(
        json.dumps({"rubric_version": "3.1.0", "skill_name": "run-a"}), encoding="utf-8"
    )
    rc, out, err = _run_main_capture(monkeypatch, up, eval_dir)
    assert rc == 0
    assert "re-evaluation targets (major bump detected): 0" in out
    assert "no major bump detected" in out


def test_main_skips_records_without_version(monkeypatch, tmp_path):
    # version フィールドの無いレコードは continue でスキップ (line 139)
    up = tmp_path / "rubric.json"
    up.write_text(json.dumps({"rubric_version": "4.0.0"}), encoding="utf-8")
    eval_dir = tmp_path / "eval-log"
    eval_dir.mkdir()
    (eval_dir / "mixed.json").write_text(
        json.dumps([
            {"skill_name": "run-noversion"},  # version 無し -> skip
            {"rubric_version": "1.0.0", "skill_name": "run-bumped"},  # bump
        ]),
        encoding="utf-8",
    )
    rc, out, err = _run_main_capture(monkeypatch, up, eval_dir)
    assert rc == 0
    assert "re-evaluation targets (major bump detected): 1" in out
    assert "run-bumped" in out
    assert "run-noversion" not in out


def test_main_detects_major_bump_lists_targets(monkeypatch, tmp_path):
    up = tmp_path / "rubric.json"
    up.write_text(json.dumps({"rubric_version": "4.0.0"}), encoding="utf-8")
    eval_dir = tmp_path / "eval-log"
    eval_dir.mkdir()
    # past major 2 < current major 4 -> bump
    (eval_dir / "old.json").write_text(
        json.dumps({"rubric_version": "2.5.0", "skill_name": "run-old"}), encoding="utf-8"
    )
    # jsonl with one bumped record and one current record
    (eval_dir / "log.jsonl").write_text(
        json.dumps({"rubric_version": "1.0.0", "target_skill": "run-legacy"}) + "\n"
        + json.dumps({"rubric_version": "4.0.0", "skill_name": "run-current"}) + "\n",
        encoding="utf-8",
    )
    rc, out, err = _run_main_capture(monkeypatch, up, eval_dir)
    assert rc == 0
    assert "upstream rubric_version: 4.0.0" in out
    assert "eval-log files scanned: 2" in out
    assert "re-evaluation targets (major bump detected): 2" in out
    # genuine: 具体的な対象が past/current 付きで列挙される
    assert "run-old (from old.json)\tpast=2.5.0\tcurrent=4.0.0" in out
    assert "run-legacy (from log.jsonl)\tpast=1.0.0\tcurrent=4.0.0" in out
    # current major と同じものは含まれない
    assert "run-current" not in out


# --- main(): subprocess 実行 (実引数なし, repo の実 path math) ---

def test_subprocess_runs_clean_exit_0():
    # parents[2] が repo-root にならない環境でも常に exit 0 で終わる契約
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0
    # 出力が空でない (stderr の rubric not found か stdout のサマリのいずれか)
    assert (proc.stdout + proc.stderr).strip() != ""

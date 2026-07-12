"""skill-governance-automation/scripts/re-evaluate-on-rubric-bump.py の genuine 機能テスト。

upstream rubric_version と eval-log/ 配下の過去評価ログの rubric_version を比較し、
major bump 発生時に再評価が必要なスキル一覧を列挙するスクリプト。常に exit 0。

純関数 (parse_semver / iter_records / extract_version / extract_skill_identity) は
実ファイルパスから importlib でロードして実入力で assert。main は module グローバル
(UPSTREAM_RUBRIC / EVAL_LOG_DIR) を monkeypatch で tmp_path fixture に差し替え、
全分岐(rubric 不在 / version 解析不能 / eval-log 不在 / eval-log 空 / major bump 無 /
major bump 有)を in-process で網羅し stdout/stderr/exit code を assert。
さらに実 repo に対する subprocess 起動で rubric 不在の早期 return 経路を実測。

network: false, keychain: なし, 実 repo 書換: なし (tmp_path / monkeypatch のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-governance-automation"
    / "scripts"
    / "re-evaluate-on-rubric-bump.py"
)

SPEC = importlib.util.spec_from_file_location("re_evaluate_on_rubric_bump_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _write_json(p: Path, data) -> Path:
    return _write(p, json.dumps(data, ensure_ascii=False))


# ── parse_semver ─────────────────────────────────────────────────────────────
def test_parse_semver_plain():
    assert MOD.parse_semver("2.3.4") == (2, 3, 4)


def test_parse_semver_embedded():
    # 文字列中の最初の X.Y.Z を拾う
    assert MOD.parse_semver("rubric v10.0.1 (stable)") == (10, 0, 1)


def test_parse_semver_none_and_empty():
    assert MOD.parse_semver(None) is None
    assert MOD.parse_semver("") is None


def test_parse_semver_no_match():
    assert MOD.parse_semver("not-a-version") is None
    assert MOD.parse_semver("1.2") is None  # X.Y.Z 三連でない


def test_parse_semver_coerces_non_str():
    # str(s) で数値も受ける (3.0.0 のような float 表現は X.Y.Z 不成立 → None)
    assert MOD.parse_semver(123) is None


# ── iter_records: .json ──────────────────────────────────────────────────────
def test_iter_records_json_object(tmp_path):
    p = _write_json(tmp_path / "log.json", {"rubric_version": "1.0.0"})
    recs = list(MOD.iter_records(p))
    assert recs == [{"rubric_version": "1.0.0"}]


def test_iter_records_json_array(tmp_path):
    p = _write_json(tmp_path / "log.json", [{"a": 1}, "skip-str", {"b": 2}])
    recs = list(MOD.iter_records(p))
    # dict 以外 (str) はスキップ
    assert recs == [{"a": 1}, {"b": 2}]


def test_iter_records_json_invalid_returns_empty(tmp_path):
    p = _write(tmp_path / "bad.json", "{ not json")
    assert list(MOD.iter_records(p)) == []


def test_iter_records_missing_file_returns_empty(tmp_path):
    assert list(MOD.iter_records(tmp_path / "nope.json")) == []


# ── iter_records: .jsonl ─────────────────────────────────────────────────────
def test_iter_records_jsonl(tmp_path):
    p = _write(
        tmp_path / "log.jsonl",
        '{"rubric_version": "1.0.0"}\n\n{"rubric_version": "2.0.0"}\n',
    )
    recs = list(MOD.iter_records(p))
    assert recs == [{"rubric_version": "1.0.0"}, {"rubric_version": "2.0.0"}]


def test_iter_records_jsonl_skips_bad_lines(tmp_path):
    p = _write(
        tmp_path / "log.jsonl",
        '{"ok": 1}\n{ broken line\n"plain-string"\n{"ok": 2}\n',
    )
    recs = list(MOD.iter_records(p))
    # 壊れた行・dict でない行はスキップ
    assert recs == [{"ok": 1}, {"ok": 2}]


# ── extract_version ──────────────────────────────────────────────────────────
def test_extract_version_priority_order():
    # rubric_version が最優先
    rec = {"rubric_version": "3.1.0", "current_version": "1.0.0"}
    assert MOD.extract_version(rec) == (3, 1, 0)


def test_extract_version_fallback_keys():
    assert MOD.extract_version({"current_version": "2.0.0"}) == (2, 0, 0)
    assert MOD.extract_version({"target_version": "4.5.6"}) == (4, 5, 6)
    assert MOD.extract_version({"version": "9.9.9"}) == (9, 9, 9)


def test_extract_version_none_when_absent():
    assert MOD.extract_version({"skill_name": "x"}) is None


# ── extract_skill_identity ───────────────────────────────────────────────────
def test_extract_skill_identity_priority(tmp_path):
    src = tmp_path / "eval-2026.json"
    rec = {"skill_name": "run-foo", "target_skill": "ignored"}
    assert MOD.extract_skill_identity(rec, src) == "run-foo (from eval-2026.json)"


def test_extract_skill_identity_fallback_chain(tmp_path):
    src = tmp_path / "e.json"
    assert MOD.extract_skill_identity({"target_skill": "t"}, src) == "t (from e.json)"
    assert MOD.extract_skill_identity({"proposal_id": "P1"}, src) == "P1 (from e.json)"
    assert MOD.extract_skill_identity({"proposer": "alice"}, src) == "alice (from e.json)"


def test_extract_skill_identity_unknown(tmp_path):
    src = tmp_path / "e.json"
    assert MOD.extract_skill_identity({"nothing": 1}, src) == "<unknown> (from e.json)"


# ── main: in-process with monkeypatched globals ──────────────────────────────
def _setup(monkeypatch, tmp_path, upstream_version=None, write_upstream=True):
    """upstream rubric と eval-log dir を tmp_path に作って module グローバルを差し替える。"""
    rubric = tmp_path / "rubric.json"
    if write_upstream:
        if upstream_version is None:
            _write_json(rubric, {"name": "no-version"})
        else:
            _write_json(rubric, {"rubric_version": upstream_version})
    eval_dir = tmp_path / "eval-log"
    monkeypatch.setattr(MOD, "UPSTREAM_RUBRIC", rubric)
    monkeypatch.setattr(MOD, "EVAL_LOG_DIR", eval_dir)
    return rubric, eval_dir


def _run_main(monkeypatch):
    # main() は int を返す (sys.exit はしない)
    return MOD.main()


def test_main_upstream_missing_returns_0(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, write_upstream=False)
    assert _run_main(monkeypatch) == 0
    assert "upstream rubric not found" in capsys.readouterr().err


def test_main_upstream_version_unparseable_returns_0(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, upstream_version=None)  # version キー無し
    assert _run_main(monkeypatch) == 0
    assert "could not parse upstream rubric_version" in capsys.readouterr().err


def test_main_eval_dir_missing_returns_0(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, upstream_version="2.0.0")
    # eval-log dir は作らない
    assert _run_main(monkeypatch) == 0
    assert "no eval-log directory" in capsys.readouterr().out


def test_main_eval_dir_empty_returns_0(monkeypatch, tmp_path, capsys):
    _, eval_dir = _setup(monkeypatch, tmp_path, upstream_version="2.0.0")
    eval_dir.mkdir()
    # .json/.jsonl 以外のファイルのみ → log_files 空
    _write(eval_dir / "readme.txt", "ignored")
    assert _run_main(monkeypatch) == 0
    assert "eval-log/ is empty" in capsys.readouterr().out


def test_main_no_major_bump(monkeypatch, tmp_path, capsys):
    _, eval_dir = _setup(monkeypatch, tmp_path, upstream_version="2.5.0")
    eval_dir.mkdir()
    # past major == current major (2) → bump 無し
    _write_json(eval_dir / "log1.json", {"rubric_version": "2.0.0", "skill_name": "s1"})
    # version 解析不能なレコードは continue (拾われない)
    _write_json(eval_dir / "log2.json", {"skill_name": "no-version"})
    assert _run_main(monkeypatch) == 0
    out = capsys.readouterr().out
    assert "upstream rubric_version: 2.5.0" in out
    assert "eval-log files scanned: 2" in out
    assert "re-evaluation targets (major bump detected): 0" in out
    assert "no major bump detected" in out


def test_main_major_bump_detected(monkeypatch, tmp_path, capsys):
    _, eval_dir = _setup(monkeypatch, tmp_path, upstream_version="3.0.0")
    eval_dir.mkdir()
    # past major (1,2) < current major (3) → bump 対象
    _write_json(eval_dir / "a.json", {"rubric_version": "1.2.0", "skill_name": "run-alpha"})
    # jsonl: 2 レコード, 片方は bump 対象 (major 2<3), 片方は同 major (3)
    _write(
        eval_dir / "b.jsonl",
        '{"rubric_version": "2.9.9", "target_skill": "run-beta"}\n'
        '{"rubric_version": "3.1.0", "skill_name": "run-current"}\n',
    )
    assert _run_main(monkeypatch) == 0
    out = capsys.readouterr().out
    assert "re-evaluation targets (major bump detected): 2" in out
    assert "target list" in out
    assert "run-alpha (from a.json)\tpast=1.2.0\tcurrent=3.0.0" in out
    assert "run-beta (from b.jsonl)\tpast=2.9.9\tcurrent=3.0.0" in out
    # 3.1.0 は同 major (current major 3) なので対象外
    assert "run-current" not in out


def test_main_major_bump_json_array(monkeypatch, tmp_path, capsys):
    _, eval_dir = _setup(monkeypatch, tmp_path, upstream_version="4.0.0")
    eval_dir.mkdir()
    _write_json(
        eval_dir / "batch.json",
        [
            {"rubric_version": "1.0.0", "proposal_id": "P-1"},
            {"rubric_version": "2.0.0", "proposer": "bob"},
        ],
    )
    assert _run_main(monkeypatch) == 0
    out = capsys.readouterr().out
    assert "re-evaluation targets (major bump detected): 2" in out
    assert "P-1 (from batch.json)\tpast=1.0.0\tcurrent=4.0.0" in out
    assert "bob (from batch.json)\tpast=2.0.0\tcurrent=4.0.0" in out


# ── subprocess: 実 repo に対する早期 return 経路 (exit 0 必ず) ────────────────
def test_cli_runs_and_exits_0():
    # 実 repo では UPSTREAM_RUBRIC が REPO_ROOT(=parents[2]=plugins) 解決で
    # 不在のため early-return するが、いずれにせよ常に exit 0。
    res = subprocess.run(
        [sys.executable, str(SCRIPT)], text=True, capture_output=True
    )
    assert res.returncode == 0
    # rubric 不在 (stderr) か eval-log 系メッセージ (stdout) のいずれか
    combined = res.stdout + res.stderr
    assert combined.strip() != ""

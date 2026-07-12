"""re-evaluate-on-rubric-bump.py の genuine 機能テスト (scripts4 / 独立計測用)。

対象: plugins/skill-governance-automation/scripts/re-evaluate-on-rubric-bump.py

挙動の要約:
  upstream rubric_version (ref-skill-design-rubric/rubric.json) と eval-log/ 配下の
  過去評価ログの rubric_version を比較し、**major bump** (upstream major > past major)
  が起きているレコードを再評価対象として列挙する。実行はせず常に exit 0。

検証方針:
  - 純関数 (parse_semver / iter_records / extract_version / extract_skill_identity) は
    importlib で実ファイルからロードし、正常系・各異常系・エッジ (None/空/不正JSON/
    欠落ファイル/dict 非該当行/.jsonl) を実入力で assert。
  - main は module グローバル UPSTREAM_RUBRIC / EVAL_LOG_DIR を monkeypatch で tmp_path
    に差し替え、全分岐 (rubric 不在 / version 解析不能 / eval-dir 不在 / eval-dir 空 /
    major bump 無 / major bump 有 / .json array / .jsonl 混在 / minor bump 非対象) を
    in-process で網羅し stdout/stderr/戻り値 (int) を assert。
  - CLI 経路 (__main__ guard 経由 sys.exit) は subprocess(sys.executable) で exit 0 を実測。

network: false / keychain: なし / 実 repo 書換: なし (tmp_path + monkeypatch のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-governance-automation"
    / "scripts"
    / "re-evaluate-on-rubric-bump.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("re_eval_rubric_uut_r4", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _w(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _wj(p: Path, data) -> Path:
    return _w(p, json.dumps(data, ensure_ascii=False))


# ── parse_semver ─────────────────────────────────────────────────────────────
def test_parse_semver_basic_triple():
    assert MOD.parse_semver("0.0.0") == (0, 0, 0)
    assert MOD.parse_semver("12.34.56") == (12, 34, 56)


def test_parse_semver_finds_first_in_noisy_string():
    # 文中の最初の X.Y.Z を採用する (後続の別バージョンは無視)
    assert MOD.parse_semver("schema 7.8.9 supersedes 1.0.0") == (7, 8, 9)


def test_parse_semver_rejects_two_part_and_garbage():
    assert MOD.parse_semver("3.4") is None  # X.Y は三連でない
    assert MOD.parse_semver("vNEXT") is None
    assert MOD.parse_semver("...") is None


def test_parse_semver_none_empty_and_nonstr():
    assert MOD.parse_semver(None) is None
    assert MOD.parse_semver("") is None
    # str(123) == "123" は X.Y.Z にならない
    assert MOD.parse_semver(123) is None
    # float が文字列化されると "3.0" になり三連にならず None
    assert MOD.parse_semver(3.0) is None


# ── iter_records (.json) ─────────────────────────────────────────────────────
def test_iter_records_single_object(tmp_path):
    p = _wj(tmp_path / "one.json", {"k": "v"})
    assert list(MOD.iter_records(p)) == [{"k": "v"}]


def test_iter_records_array_filters_non_dict(tmp_path):
    p = _wj(tmp_path / "arr.json", [{"x": 1}, 42, None, ["nested"], {"y": 2}])
    # dict 以外 (int/None/list) は除外される
    assert list(MOD.iter_records(p)) == [{"x": 1}, {"y": 2}]


def test_iter_records_toplevel_scalar_yields_nothing(tmp_path):
    # JSON のトップが list でも dict でもない (数値) → 何も yield しない
    p = _w(tmp_path / "scalar.json", "99")
    assert list(MOD.iter_records(p)) == []


def test_iter_records_corrupt_json(tmp_path):
    p = _w(tmp_path / "broken.json", "{ this is : not json ]")
    assert list(MOD.iter_records(p)) == []


def test_iter_records_nonexistent_file(tmp_path):
    assert list(MOD.iter_records(tmp_path / "absent.json")) == []


# ── iter_records (.jsonl) ────────────────────────────────────────────────────
def test_iter_records_jsonl_multi(tmp_path):
    p = _w(
        tmp_path / "log.jsonl",
        '{"a": 1}\n  \n{"b": 2}\n{"c": 3}\n',
    )
    assert list(MOD.iter_records(p)) == [{"a": 1}, {"b": 2}, {"c": 3}]


def test_iter_records_jsonl_drops_bad_and_nondict(tmp_path):
    p = _w(
        tmp_path / "mixed.jsonl",
        '{"good": 1}\n'      # 採用
        "not-json-at-all\n"  # JSONDecodeError → skip
        "[1, 2, 3]\n"        # dict でない → skip
        "123\n"              # dict でない → skip
        '{"good": 2}\n',     # 採用
    )
    assert list(MOD.iter_records(p)) == [{"good": 1}, {"good": 2}]


def test_iter_records_jsonl_empty_file(tmp_path):
    p = _w(tmp_path / "empty.jsonl", "")
    assert list(MOD.iter_records(p)) == []


# ── extract_version ──────────────────────────────────────────────────────────
def test_extract_version_prefers_rubric_version():
    rec = {"rubric_version": "5.0.0", "current_version": "1.0.0", "version": "0.0.1"}
    assert MOD.extract_version(rec) == (5, 0, 0)


def test_extract_version_walks_fallback_keys_in_order():
    assert MOD.extract_version({"current_version": "2.3.4"}) == (2, 3, 4)
    assert MOD.extract_version({"target_version": "8.0.0"}) == (8, 0, 0)
    assert MOD.extract_version({"version": "1.1.1"}) == (1, 1, 1)


def test_extract_version_skips_unparseable_value_then_finds_next():
    # rubric_version が解析不能 (X.Y) → 次の有効キー (version) を採用
    rec = {"rubric_version": "bad", "version": "6.6.6"}
    assert MOD.extract_version(rec) == (6, 6, 6)


def test_extract_version_none_when_no_version_keys():
    assert MOD.extract_version({"skill_name": "s", "note": "x"}) is None


# ── extract_skill_identity ───────────────────────────────────────────────────
def test_extract_skill_identity_first_nonempty_wins(tmp_path):
    src = tmp_path / "eval-x.json"
    rec = {"skill_name": "run-foo", "target_skill": "shadowed"}
    assert MOD.extract_skill_identity(rec, src) == "run-foo (from eval-x.json)"


def test_extract_skill_identity_empty_value_is_skipped(tmp_path):
    src = tmp_path / "e.json"
    # skill_name が空文字 (falsy) → 次の非空 (skill) を採用
    rec = {"skill_name": "", "target_skill": "", "skill": "run-bar"}
    assert MOD.extract_skill_identity(rec, src) == "run-bar (from e.json)"


def test_extract_skill_identity_fallback_to_proposal_and_proposer(tmp_path):
    src = tmp_path / "e.json"
    assert MOD.extract_skill_identity({"proposal_id": "P9"}, src) == "P9 (from e.json)"
    assert MOD.extract_skill_identity({"proposer": "carol"}, src) == "carol (from e.json)"


def test_extract_skill_identity_unknown_label(tmp_path):
    src = tmp_path / "e.json"
    assert MOD.extract_skill_identity({"irrelevant": 1}, src) == "<unknown> (from e.json)"


# ── main: in-process via monkeypatched globals ───────────────────────────────
def _patch(monkeypatch, tmp_path, *, upstream=None, write_upstream=True):
    rubric = tmp_path / "rubric.json"
    if write_upstream:
        _wj(rubric, {"rubric_version": upstream} if upstream else {"name": "x"})
    eval_dir = tmp_path / "eval-log"
    monkeypatch.setattr(MOD, "UPSTREAM_RUBRIC", rubric)
    monkeypatch.setattr(MOD, "EVAL_LOG_DIR", eval_dir)
    return rubric, eval_dir


def test_main_returns_zero_when_upstream_missing(monkeypatch, tmp_path, capsys):
    _patch(monkeypatch, tmp_path, write_upstream=False)
    assert MOD.main() == 0
    assert "upstream rubric not found" in capsys.readouterr().err


def test_main_returns_zero_when_upstream_version_unparseable(monkeypatch, tmp_path, capsys):
    _patch(monkeypatch, tmp_path, upstream=None)  # rubric_version キー無し
    assert MOD.main() == 0
    assert "could not parse upstream rubric_version" in capsys.readouterr().err


def test_main_returns_zero_when_eval_dir_absent(monkeypatch, tmp_path, capsys):
    _patch(monkeypatch, tmp_path, upstream="2.0.0")
    assert MOD.main() == 0
    assert "no eval-log directory" in capsys.readouterr().out


def test_main_returns_zero_when_eval_dir_has_no_json(monkeypatch, tmp_path, capsys):
    _, eval_dir = _patch(monkeypatch, tmp_path, upstream="2.0.0")
    eval_dir.mkdir()
    _w(eval_dir / "notes.md", "# not a log")  # .json/.jsonl でない
    assert MOD.main() == 0
    assert "eval-log/ is empty" in capsys.readouterr().out


def test_main_no_major_bump_reports_zero_targets(monkeypatch, tmp_path, capsys):
    _, eval_dir = _patch(monkeypatch, tmp_path, upstream="2.9.0")
    eval_dir.mkdir()
    # 同一 major (2) → bump 対象外
    _wj(eval_dir / "a.json", {"rubric_version": "2.0.0", "skill_name": "run-keep"})
    # version 取得不能 → continue
    _wj(eval_dir / "b.json", {"skill_name": "run-noversion"})
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "upstream rubric_version: 2.9.0" in out
    assert "eval-log files scanned: 2" in out
    assert "re-evaluation targets (major bump detected): 0" in out
    assert "no major bump detected" in out
    assert "run-keep" not in out


def test_main_major_bump_lists_targets_and_excludes_same_major(monkeypatch, tmp_path, capsys):
    _, eval_dir = _patch(monkeypatch, tmp_path, upstream="3.0.0")
    eval_dir.mkdir()
    _wj(eval_dir / "a.json", {"rubric_version": "1.5.0", "skill_name": "run-alpha"})
    _w(
        eval_dir / "b.jsonl",
        '{"rubric_version": "2.9.9", "target_skill": "run-beta"}\n'
        '{"rubric_version": "3.4.0", "skill_name": "run-same-major"}\n',
    )
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "re-evaluation targets (major bump detected): 2" in out
    assert "target list" in out
    assert "run-alpha (from a.json)\tpast=1.5.0\tcurrent=3.0.0" in out
    assert "run-beta (from b.jsonl)\tpast=2.9.9\tcurrent=3.0.0" in out
    # current と同 major (3) は対象外
    assert "run-same-major" not in out


def test_main_major_bump_from_json_array(monkeypatch, tmp_path, capsys):
    _, eval_dir = _patch(monkeypatch, tmp_path, upstream="10.0.0")
    eval_dir.mkdir()
    _wj(
        eval_dir / "batch.json",
        [
            {"rubric_version": "1.0.0", "proposal_id": "P-1"},
            {"rubric_version": "9.9.9", "proposer": "dave"},
        ],
    )
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "re-evaluation targets (major bump detected): 2" in out
    assert "P-1 (from batch.json)\tpast=1.0.0\tcurrent=10.0.0" in out
    assert "dave (from batch.json)\tpast=9.9.9\tcurrent=10.0.0" in out


def test_main_files_sorted_and_count_includes_jsonl(monkeypatch, tmp_path, capsys):
    _, eval_dir = _patch(monkeypatch, tmp_path, upstream="5.0.0")
    eval_dir.mkdir()
    _wj(eval_dir / "z.json", {"rubric_version": "4.0.0", "skill_name": "run-z"})
    _w(eval_dir / "a.jsonl", '{"rubric_version": "4.1.0", "skill_name": "run-a"}\n')
    assert MOD.main() == 0
    out = capsys.readouterr().out
    assert "eval-log files scanned: 2" in out
    assert "re-evaluation targets (major bump detected): 2" in out


# ── CLI subprocess (exit code 実測 / __main__ guard) ─────────────────────────
def test_cli_always_exits_zero_and_emits_output():
    res = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True)
    assert res.returncode == 0
    assert (res.stdout + res.stderr).strip() != ""

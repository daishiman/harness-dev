"""skill-governance-automation/scripts/re-evaluate-on-rubric-bump.py の genuine 機能テスト。

upstream rubric_version と eval-log/ 配下の過去評価ログの rubric_version を比較し、
major bump 発生時に再評価が必要なスキル一覧を列挙するスクリプト。走査できれば exit 0、
upstream rubric が無い・読めない・版を解釈できないときは exit 2 (入力欠落を成功に畳まない)。

純関数 (parse_semver / iter_records / extract_version / extract_skill_identity) は
実ファイルパスから importlib でロードして実入力で assert。main は module グローバル
(UPSTREAM_RUBRIC / EVAL_LOG_DIR) を monkeypatch で tmp_path fixture に差し替え、
全分岐(rubric 不在 / 読めない / version 解析不能 / eval-log 不在 / eval-log 空 / major bump 無 /
major bump 有)を in-process で網羅し stdout/stderr/exit code を assert。
さらに実 repo に対する subprocess 起動で、兄弟 harness-creator の rubric を解決できることと
--help・--rubric 欠落の終了コードを実測。

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


def test_main_upstream_missing_returns_2(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, write_upstream=False)
    assert _run_main(monkeypatch) == 2
    assert "upstream rubric not found" in capsys.readouterr().err


def test_main_upstream_unreadable_returns_2(monkeypatch, tmp_path, capsys):
    rubric, _ = _setup(monkeypatch, tmp_path, write_upstream=False)
    _write(rubric, "{not json")
    assert _run_main(monkeypatch) == 2
    assert "could not read upstream rubric" in capsys.readouterr().err


def test_main_upstream_version_unparseable_returns_2(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, upstream_version=None)  # version キー無し
    assert _run_main(monkeypatch) == 2
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


# ── score ログ (eval-log/<plugin>/*-score.jsonl) ─────────────────────────────
def test_extract_version_prefers_nested_rubric_version():
    rec = {"rubric": {"rubric_version": "1.5.0"}, "version": "9.9.9"}
    assert MOD.extract_version(rec) == (1, 5, 0)


def test_extract_version_nested_without_version_falls_back_to_top_level():
    assert MOD.extract_version({"rubric": {"name": "x"}, "rubric_version": "2.0.0"}) == (2, 0, 0)


def test_read_score_log_counts_broken_and_versionless_lines(tmp_path):
    p = tmp_path / "s-score.jsonl"
    _write(
        p,
        '{"rubric": {"rubric_version": "1.0.0"}, "skill_name": "ok"}\n'
        "\n"
        "{broken\n"
        '["not", "object"]\n'
        '{"skill_name": "no-version"}\n',
    )
    records, unreadable = MOD.read_score_log(p)
    assert [r["skill_name"] for r in records] == ["ok"]
    assert unreadable == 3


def test_main_detects_major_bump_from_nested_score_log(monkeypatch, tmp_path, capsys):
    _, eval_dir = _setup(monkeypatch, tmp_path, upstream_version="2.0.0")
    _write(
        eval_dir / "plugin-a" / "2026-01-01-score.jsonl",
        '{"rubric": {"rubric_version": "1.5.0"}, "skill_name": "run-nested"}\n',
    )
    assert _run_main(monkeypatch) == 0
    out = capsys.readouterr().out
    assert "eval-log files scanned: 1" in out
    assert "run-nested (from plugin-a/2026-01-01-score.jsonl)\tpast=1.5.0\tcurrent=2.0.0" in out


def test_main_unreadable_score_record_lists_targets_then_exits_2(monkeypatch, tmp_path, capsys):
    _, eval_dir = _setup(monkeypatch, tmp_path, upstream_version="2.0.0")
    _write(
        eval_dir / "plugin-a" / "2026-01-01-score.jsonl",
        '{"rubric": {"rubric_version": "1.0.0"}, "skill_name": "run-old"}\n'
        '{"skill_name": "run-versionless"}\n',
    )
    assert _run_main(monkeypatch) == 2
    captured = capsys.readouterr()
    assert "run-old (from plugin-a/2026-01-01-score.jsonl)\tpast=1.0.0" in captured.out
    assert "1 score record(s) had no readable rubric_version" in captured.err


# ── subprocess: 実 repo に対する CLI 経路 ─────────────────────────────────────
def test_cli_resolves_sibling_rubric_and_exits_0():
    # 兄弟 plugin harness-creator の references/rubric.json を extract-plugin-root.py で解決する。
    # 以前は parents[2]=plugins を repo root と取り違えて常に rubric 不在で exit 0 になっていた。
    res = subprocess.run(
        [sys.executable, str(SCRIPT)], text=True, capture_output=True, cwd=ROOT
    )
    assert res.returncode == 0, res.stderr
    assert "# upstream rubric_version:" in res.stdout
    assert "upstream rubric not found" not in res.stderr


def test_cli_help_exits_0_without_scanning():
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], text=True, capture_output=True
    )
    assert res.returncode == 0
    assert res.stdout.startswith("usage:")
    assert "upstream rubric_version" not in res.stdout


def test_cli_missing_explicit_rubric_exits_2(tmp_path):
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--rubric", str(tmp_path / "absent.json")],
        text=True,
        capture_output=True,
    )
    assert res.returncode == 2
    assert "upstream rubric not found" in res.stderr


# ── eval-log の置き場 (write-eval-log.py と同じ順) ───────────────────────────
def test_default_eval_log_dir_follows_write_eval_log_order(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "EVAL_LOG_DIR", None)
    monkeypatch.delenv("EVAL_LOG_DIR", raising=False)
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert MOD.default_eval_log_dir() == tmp_path / "eval-log"
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path / "proj"))
    assert MOD.default_eval_log_dir() == tmp_path / "proj" / "eval-log"
    monkeypatch.setenv("EVAL_LOG_DIR", str(tmp_path / "logs"))
    assert MOD.default_eval_log_dir() == tmp_path / "logs"


def test_main_reads_score_logs_from_env_eval_log_dir(monkeypatch, tmp_path, capsys):
    rubric = _write_json(tmp_path / "rubric.json", {"rubric_version": "3.0.0"})
    logs = tmp_path / "logs"
    _write(
        logs / "plugin-a" / "2026-10-10-score.jsonl",
        json.dumps({"skill": "run-old", "rubric": {"rubric_version": "2.0.0"}}) + "\n",
    )
    monkeypatch.setattr(MOD, "EVAL_LOG_DIR", None)
    monkeypatch.setenv("EVAL_LOG_DIR", str(logs))
    assert MOD.main(["--rubric", str(rubric)]) == 0
    out = capsys.readouterr().out
    assert "re-evaluation targets (major bump detected): 1" in out
    assert "run-old (from plugin-a/2026-10-10-score.jsonl)" in out


# ── --post-tool-use (Claude Code の PostToolUse hook) ────────────────────────
def test_edited_rubric_path_only_matches_rubric_json():
    assert MOD.edited_rubric_path('{"tool_input": {"file_path": "a/b/rubric.json"}}') == "a/b/rubric.json"
    assert MOD.edited_rubric_path('{"tool_input": {"file_path": "a/b/SKILL.md"}}') is None
    assert MOD.edited_rubric_path('{"tool_input": {"file_path": "a/rubric.json.bak"}}') is None
    assert MOD.edited_rubric_path("not json") is None
    assert MOD.edited_rubric_path('["tool_input"]') is None
    assert MOD.edited_rubric_path('{"tool_input": "x"}') is None


def _hook(tmp_path, payload, rubric):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--post-tool-use", "--rubric", str(rubric)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0
    return proc


def _context(proc) -> str:
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PostToolUse"
    return out["additionalContext"]


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_input": {"file_path": "x/SKILL.md"}},
        # upstream でない rubric.json の編集は走査しない (比べる相手は upstream の L0 だけ)
        {"tool_input": {"file_path": "other/references/rubric.json"}},
        "broken",
    ],
)
def test_post_tool_use_ignores_non_upstream_edits(tmp_path, payload):
    proc = _hook(tmp_path, payload, tmp_path / "x" / "references" / "rubric.json")
    assert proc.stdout == "" and proc.stderr == ""


def test_post_tool_use_reports_scan_failure_in_additional_context(tmp_path):
    # upstream rubric が無い (scan なら exit 2) 状況でも、hook モードは exit 0 で編集を止めない。
    # 結果は素の stdout でなく additionalContext に入れて Claude の文脈に届ける。
    proc = _hook(tmp_path, {"tool_input": {"file_path": "x/references/rubric.json"}},
                 tmp_path / "x" / "references" / "rubric.json")
    ctx = _context(proc)
    assert "# rubric edited: x/references/rubric.json" in ctx
    assert "upstream rubric not found" in ctx
    assert "hook mode only notifies" in ctx
    assert proc.stderr == ""


def test_post_tool_use_lists_targets_for_upstream_edit(tmp_path):
    rubric = _write_json(tmp_path / "x" / "references" / "rubric.json",
                         {"rubric_id": "skill-design", "rubric_version": "2.0.0"})
    _write(tmp_path / "eval-log" / "log.jsonl",
           json.dumps({"skill_name": "run-ü", "rubric_version": "1.0.0"}) + "\n")
    proc = _hook(tmp_path, {"tool_input": {"file_path": str(rubric)}}, rubric)
    ctx = _context(proc)
    assert "# upstream rubric_version: 2.0.0" in ctx
    assert "run-ü (from log.jsonl)\tpast=1.0.0\tcurrent=2.0.0" in ctx
    assert "hook mode only notifies" not in ctx


# ── plugin の区別 (レビュー A の指摘) ─────────────────────────────────────────
def test_same_skill_name_in_different_plugins_is_not_merged(monkeypatch, tmp_path, capsys):
    # 以前は skill_name だけで key を作り、plugB の 2.0.0 の記録で plugA の 1.3.0 を隠していた
    _, eval_dir = _setup(monkeypatch, tmp_path, upstream_version="2.0.0")
    _write(eval_dir / "plugA" / "2026-01-01-score.jsonl",
           json.dumps({"plugin": "plugA", "skill_name": "run-skill-feedback",
                       "rubric": {"rubric_id": "skill-design", "rubric_version": "1.3.0"}}) + "\n")
    _write(eval_dir / "plugB" / "2026-01-01-score.jsonl",
           json.dumps({"plugin": "plugB", "skill_name": "run-skill-feedback",
                       "rubric": {"rubric_id": "skill-design", "rubric_version": "2.0.0"}}) + "\n")
    assert _run_main(monkeypatch) == 0
    out = capsys.readouterr().out
    assert "re-evaluation targets (major bump detected): 1" in out
    assert "- run-skill-feedback (from plugA/2026-01-01-score.jsonl)\tpast=1.3.0\tcurrent=2.0.0" in out


def test_skill_key_prefers_the_plugin_in_the_skill_path(tmp_path):
    src = tmp_path / "core" / "2026-06-06-score.jsonl"
    # 記録の plugin (core) や置き場より、SKILL.md のパスの plugins/<plugin>/skills/<skill> を使う。
    # checkout が違っても同じスキルになる
    a = {"plugin": "core", "skill_name": "/a/xl-skills/plugins/skill-intake/skills/run-intake/SKILL.md"}
    b = {"skill_name": "/b/.worktrees/wt-5/plugins/skill-intake/skills/run-intake/SKILL.md"}
    assert MOD.skill_key(a, src, "core") == MOD.skill_key(b, src, "other") == ("skill", "skill-intake", "run-intake")
    assert MOD.skill_key({"plugin": "plugA", "skill": "run-x"}, src, "core") == ("skill", "plugA", "run-x")
    assert MOD.skill_key({"skill": "run-x"}, src, "core") == ("skill", "core", "run-x")
    assert MOD.skill_key({"skill": "run-x"}, tmp_path / "top.json") == ("skill", "", "run-x")


def test_unknown_records_are_grouped_per_file_not_per_file_name(monkeypatch, tmp_path, capsys):
    _, eval_dir = _setup(monkeypatch, tmp_path, upstream_version="2.0.0")
    _write(eval_dir / "plugA" / "2026-01-01-score.jsonl", '{"rubric": {"rubric_version": "1.0.0"}}\n')
    _write(eval_dir / "plugB" / "2026-01-01-score.jsonl", '{"rubric": {"rubric_version": "2.0.0"}}\n')
    assert _run_main(monkeypatch) == 0
    out = capsys.readouterr().out
    assert "- <unknown> (from plugA/2026-01-01-score.jsonl)\tpast=1.0.0\tcurrent=2.0.0" in out
    assert "plugB" not in out

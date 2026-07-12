"""write-eval-log.py の genuine 機能テスト (scripts4 / 独立計測用)。

対象: plugins/skill-governance-automation/scripts/write-eval-log.py

挙動の要約:
  evaluator が STDOUT へ出す評価 JSON を stdin / --input から受け取り、
  27章 score JSONL schema へ正規化 (normalize) して
  eval-log/<plugin>/<date>-score.jsonl に1行=1評価として append する。
  Sink Contract v1.0: exit 0 成功 / 1 validation 失敗。

検証方針:
  - 純関数 (resolve_log_path / validate / normalize) を importlib で実ファイルから
    ロードし、正常系・各異常系・エッジ (空 dict / 型不正 / findings 欠落 id /
    target dict 各形 / setdefault 既存値保持 / env 経路) を実入力で assert。
  - main は monkeypatch で stdin / argv / env / cwd を差し替え、全分岐
    (stdin 経路 / --input 経路 / 不正 JSON / validation 失敗 / --dry-run /
     --log-path override / resolve_log_path 経由 append / 実書込内容) を
    in-process で網羅し戻り値・stdout・stderr・生成ファイル内容を assert。
  - CLI 経路 (__main__ guard 経由 sys.exit) は subprocess(sys.executable) で
    exit code と append 結果を実測。

network: false / keychain: なし / 実 repo 書換: なし (tmp_path + monkeypatch のみ)。
"""
import importlib.util
import io
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-governance-automation"
    / "scripts"
    / "write-eval-log.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("write_eval_log_uut_r4", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()

# 全必須キーを持つ最小 valid record の生成ヘルパ
def _valid_record(**over):
    rec = {
        "rubric_id": "ref-skill-design-rubric",
        "rubric_version": "1.2.3",
        "rubric_hash": "deadbeef",
        "target": "run-foo",
        "score": 88,
        "passed": True,
    }
    rec.update(over)
    return rec


# ── resolve_log_path ─────────────────────────────────────────────────────────
def test_resolve_log_path_uses_eval_log_dir_env(monkeypatch):
    monkeypatch.setenv("EVAL_LOG_DIR", "/eval/base")
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    p = MOD.resolve_log_path({"plugin": "harness-creator"})
    date = time.strftime("%Y-%m-%d")
    assert p == Path("/eval/base") / "harness-creator" / f"{date}-score.jsonl"


def test_resolve_log_path_falls_back_to_project_root(monkeypatch):
    monkeypatch.delenv("EVAL_LOG_DIR", raising=False)
    monkeypatch.setenv("PROJECT_ROOT", "/repo")
    p = MOD.resolve_log_path({"plugin": "intake"})
    date = time.strftime("%Y-%m-%d")
    assert p == Path("/repo") / "eval-log" / "intake" / f"{date}-score.jsonl"


def test_resolve_log_path_default_relative_and_core_plugin(monkeypatch):
    monkeypatch.delenv("EVAL_LOG_DIR", raising=False)
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    # plugin キー無し → "core" が使われる
    p = MOD.resolve_log_path({})
    date = time.strftime("%Y-%m-%d")
    assert p == Path("eval-log") / "core" / f"{date}-score.jsonl"


def test_resolve_log_path_plugin_none_coerces_to_core(monkeypatch):
    monkeypatch.delenv("EVAL_LOG_DIR", raising=False)
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    # plugin が None → "core"、plugin が数値 → str() 化
    assert "core" in str(MOD.resolve_log_path({"plugin": None}))
    assert "/42/" in str(MOD.resolve_log_path({"plugin": 42})).replace("\\", "/")


# ── validate ─────────────────────────────────────────────────────────────────
def test_validate_passes_full_record():
    assert MOD.validate(_valid_record()) == []


def test_validate_reports_each_missing_required_key():
    errors = MOD.validate({})
    for k in MOD.REQUIRED_KEYS:
        assert f"missing key: {k}" in errors
    # 6 個全て検出
    assert len([e for e in errors if e.startswith("missing key")]) == 6


def test_validate_score_must_be_numeric():
    errors = MOD.validate(_valid_record(score="high"))
    assert "score must be numeric" in errors


def test_validate_score_bool_is_rejected_when_passed_present():
    # bool は int のサブクラスなので score=True は numeric を通る → score エラー無し
    errors = MOD.validate(_valid_record(score=1))
    assert "score must be numeric" not in errors


def test_validate_passed_must_be_bool():
    errors = MOD.validate(_valid_record(passed="yes"))
    assert "passed must be bool" in errors


def test_validate_findings_must_be_list_when_present():
    errors = MOD.validate(_valid_record(findings={"not": "a list"}))
    assert "findings must be list when present" in errors


def test_validate_finding_items_must_be_objects():
    errors = MOD.validate(_valid_record(findings=["string-not-dict", 99]))
    assert "findings[0] must be object" in errors
    assert "findings[1] must be object" in errors


def test_validate_finding_requires_id_or_rubric_item_id():
    # id も rubric_item_id も無い finding はエラー
    errors = MOD.validate(_valid_record(findings=[{"note": "x"}]))
    assert "findings[0].id or rubric_item_id is required" in errors


def test_validate_finding_id_or_rubric_item_id_satisfies():
    assert MOD.validate(_valid_record(findings=[{"id": "F1"}])) == []
    assert MOD.validate(_valid_record(findings=[{"rubric_item_id": "R1"}])) == []


def test_validate_no_findings_key_is_ok():
    # findings キー自体が無ければ [] 扱いでエラー無し
    assert MOD.validate(_valid_record()) == []


# ── normalize ────────────────────────────────────────────────────────────────
def test_normalize_extracts_skill_name_from_string_target(monkeypatch):
    monkeypatch.delenv("PLUGIN_NAME", raising=False)
    monkeypatch.delenv("RELEASE_VERSION", raising=False)
    out = MOD.normalize(_valid_record(target="run-foo"))
    assert out["skill_name"] == "run-foo"
    # rubric 三キーは rubric サブオブジェクトへ集約され元キーは消える
    assert out["rubric"] == {
        "rubric_id": "ref-skill-design-rubric",
        "rubric_version": "1.2.3",
        "rubric_hash": "deadbeef",
    }
    assert "rubric_id" not in out and "rubric_version" not in out and "rubric_hash" not in out


def test_normalize_skill_name_from_dict_target_priority():
    # skill_name > name > path > "unknown" の優先順
    assert MOD.normalize(_valid_record(target={"skill_name": "S", "name": "N"}))["skill_name"] == "S"
    assert MOD.normalize(_valid_record(target={"name": "N", "path": "P"}))["skill_name"] == "N"
    assert MOD.normalize(_valid_record(target={"path": "plugins/x/SKILL.md"}))["skill_name"] == "plugins/x/SKILL.md"


def test_normalize_dict_target_unknown_when_empty():
    assert MOD.normalize(_valid_record(target={}))["skill_name"] == "unknown"


def test_normalize_none_target_becomes_unknown():
    assert MOD.normalize(_valid_record(target=None))["skill_name"] == "unknown"


def test_normalize_fills_defaults_from_env(monkeypatch):
    monkeypatch.setenv("RELEASE_VERSION", "v9.9")
    monkeypatch.setenv("PLUGIN_NAME", "harness-creator")
    out = MOD.normalize(_valid_record())
    assert out["release"] == "v9.9"
    assert out["plugin"] == "harness-creator"
    assert out["threshold"] == 80
    assert out["schema_version"] == MOD.SCHEMA_VERSION
    assert "timestamp" in out


def test_normalize_preserves_existing_values_setdefault(monkeypatch):
    monkeypatch.setenv("PLUGIN_NAME", "env-plugin")
    # 既に plugin/threshold が record にあれば env / 既定値で上書きしない
    out = MOD.normalize(_valid_record(plugin="explicit-plugin", threshold=70, timestamp="T0"))
    assert out["plugin"] == "explicit-plugin"
    assert out["threshold"] == 70
    assert out["timestamp"] == "T0"


def test_normalize_backfills_rubric_item_id_from_finding_id():
    out = MOD.normalize(_valid_record(findings=[{"id": "F7"}]))
    assert out["findings"][0]["rubric_item_id"] == "F7"
    # 既に rubric_item_id があるものは id で上書きしない
    out2 = MOD.normalize(_valid_record(findings=[{"id": "F8", "rubric_item_id": "R-keep"}]))
    assert out2["findings"][0]["rubric_item_id"] == "R-keep"


def test_normalize_skips_non_dict_findings_without_error():
    # findings に dict 以外が混ざっても normalize は例外を出さない
    out = MOD.normalize(_valid_record(findings=[{"id": "F1"}, "garbage", 5]))
    assert out["findings"][0]["rubric_item_id"] == "F1"


# ── main: in-process via monkeypatched stdin / argv / env ────────────────────
def _run_main(monkeypatch, tmp_path, argv, stdin_text=None, env=None):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["write-eval-log.py", *argv])
    if stdin_text is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    for k in ("EVAL_LOG_DIR", "PROJECT_ROOT", "PLUGIN_NAME", "RELEASE_VERSION"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    return MOD.main()


def test_main_invalid_json_returns_1(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, tmp_path, [], stdin_text="{not json")
    assert rc == 1
    assert "invalid JSON" in capsys.readouterr().err


def test_main_validation_failure_returns_1_and_lists_errors(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, tmp_path, [], stdin_text=json.dumps({"score": "x"}))
    assert rc == 1
    err = capsys.readouterr().err
    assert "missing key: rubric_id" in err
    assert "score must be numeric" in err


def test_main_dry_run_does_not_write(monkeypatch, tmp_path, capsys):
    rc = _run_main(
        monkeypatch, tmp_path, ["--dry-run"], stdin_text=json.dumps(_valid_record())
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "(dry-run) would append to" in out
    # normalized record が JSON で出力される
    last_line = out.strip().splitlines()[-1]
    parsed = json.loads(last_line)
    assert parsed["rubric"]["rubric_id"] == "ref-skill-design-rubric"
    # 何も書き込まれていない
    assert not list(tmp_path.rglob("*-score.jsonl"))


def test_main_appends_to_log_path_override(monkeypatch, tmp_path, capsys):
    log = tmp_path / "custom" / "out.jsonl"
    rc = _run_main(
        monkeypatch,
        tmp_path,
        ["--log-path", str(log)],
        stdin_text=json.dumps(_valid_record(target="run-bar")),
    )
    assert rc == 0
    assert f"appended to {log}" in capsys.readouterr().out
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["skill_name"] == "run-bar"
    assert rec["rubric"]["rubric_version"] == "1.2.3"
    assert rec["passed"] is True


def test_main_appends_twice_one_line_each(monkeypatch, tmp_path):
    log = tmp_path / "acc.jsonl"
    for name in ("run-1", "run-2"):
        _run_main(
            monkeypatch,
            tmp_path,
            ["--log-path", str(log)],
            stdin_text=json.dumps(_valid_record(target=name)),
        )
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert [json.loads(l)["skill_name"] for l in lines] == ["run-1", "run-2"]


def test_main_reads_from_input_file(monkeypatch, tmp_path, capsys):
    inp = tmp_path / "eval.json"
    inp.write_text(json.dumps(_valid_record(target="run-input")), encoding="utf-8")
    log = tmp_path / "log.jsonl"
    rc = _run_main(monkeypatch, tmp_path, ["--input", str(inp), "--log-path", str(log)])
    assert rc == 0
    assert json.loads(log.read_text(encoding="utf-8").strip())["skill_name"] == "run-input"


def test_main_resolve_log_path_via_eval_log_dir_env(monkeypatch, tmp_path):
    base = tmp_path / "evalbase"
    rc = _run_main(
        monkeypatch,
        tmp_path,
        [],
        stdin_text=json.dumps(_valid_record(plugin="harness-creator")),
        env={"EVAL_LOG_DIR": str(base)},
    )
    assert rc == 0
    date = time.strftime("%Y-%m-%d")
    expected = base / "harness-creator" / f"{date}-score.jsonl"
    assert expected.exists()
    assert json.loads(expected.read_text(encoding="utf-8").strip())["plugin"] == "harness-creator"


# ── CLI subprocess (exit code 実測 / __main__ guard) ─────────────────────────
def test_cli_subprocess_appends_and_exits_zero(tmp_path):
    log = tmp_path / "cli.jsonl"
    payload = json.dumps(_valid_record(target="run-cli"))
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--log-path", str(log)],
        input=payload,
        text=True,
        capture_output=True,
    )
    assert res.returncode == 0, res.stderr
    assert log.exists()
    assert json.loads(log.read_text(encoding="utf-8").strip())["skill_name"] == "run-cli"


def test_cli_subprocess_invalid_json_exit_1(tmp_path):
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="{bad",
        text=True,
        capture_output=True,
    )
    assert res.returncode == 1
    assert "invalid JSON" in res.stderr

"""detect-repeated-rubric-violations.py の genuine 機能テスト (network 不要)。

純関数 load_eval_results を実 JSON fixture で駆動し、main() は
--log-dir/--out を tmp_path へ向け sys.argv を差し替えて in-process 実行する
(実 eval-log/ には一切書かない)。さらに subprocess で実 CLI の exit code を検証。

カバー分岐:
- load_eval_results: ディレクトリ非存在 / 正常 JSON / 不正 JSON skip / sort 順
- main: 違反なし(exit0) / 閾値到達(exit1) / 閾値未満は除外 / threshold 引数
        artifact|skill_name|file の skill 名フォールバック
        rubric_id 既定 "unknown" / area←rule_id←"unknown" フォールバック
        findings が None / 空配列

network: false, keychain: なし。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "detect-repeated-rubric-violations.py"

SPEC = importlib.util.spec_from_file_location("detect_repeated_rubric_violations_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _write(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


# ── load_eval_results ─────────────────────────────────────────────────────
def test_load_eval_results_missing_dir_returns_empty(tmp_path):
    assert MOD.load_eval_results(tmp_path / "nope") == []


def test_load_eval_results_reads_valid_json(tmp_path):
    _write(tmp_path / "a.json", {"artifact": "run-x", "findings": []})
    out = MOD.load_eval_results(tmp_path)
    assert len(out) == 1
    assert out[0]["file"] == "a.json"
    assert out[0]["data"]["artifact"] == "run-x"


def test_load_eval_results_skips_invalid_json(tmp_path):
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    _write(tmp_path / "good.json", {"artifact": "ok"})
    out = MOD.load_eval_results(tmp_path)
    assert [o["file"] for o in out] == ["good.json"]


def test_load_eval_results_sorted_by_name(tmp_path):
    _write(tmp_path / "b.json", {"artifact": "b"})
    _write(tmp_path / "a.json", {"artifact": "a"})
    _write(tmp_path / "c.json", {"artifact": "c"})
    out = MOD.load_eval_results(tmp_path)
    assert [o["file"] for o in out] == ["a.json", "b.json", "c.json"]


def test_load_eval_results_ignores_non_json_files(tmp_path):
    _write(tmp_path / "x.json", {"artifact": "x"})
    (tmp_path / "readme.txt").write_text("ignore me", encoding="utf-8")
    out = MOD.load_eval_results(tmp_path)
    assert [o["file"] for o in out] == ["x.json"]


# ── main (in-process via sys.argv) ────────────────────────────────────────
def _run_main(monkeypatch, log_dir: Path, out: Path, *extra):
    argv = [
        "detect-repeated-rubric-violations.py",
        "--log-dir", str(log_dir),
        "--out", str(out),
        *extra,
    ]
    monkeypatch.setattr(sys, "argv", argv)
    return MOD.main()


def test_main_no_results_writes_none_and_exit0(monkeypatch, tmp_path, capsys):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    out = tmp_path / "trigger.json"
    rc = _run_main(monkeypatch, log_dir, out)
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["triggered"] == []
    assert data["next_action"] == "none"
    assert data["threshold"] == 2
    assert "No repeated violations." in capsys.readouterr().out


def test_main_below_threshold_not_triggered(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    # 同一 (skill,rubric,area) が 1 回だけ → threshold 2 未満
    _write(log_dir / "r1.json", {
        "artifact": "run-x",
        "rubric": {"rubric_id": "R-01"},
        "findings": [{"area": "structure"}],
    })
    out = tmp_path / "trigger.json"
    rc = _run_main(monkeypatch, log_dir, out)
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["triggered"] == []
    assert data["next_action"] == "none"


def test_main_repeated_violation_triggers_exit1(monkeypatch, tmp_path, capsys):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    # 2 ファイルで同一 (skill,rubric,area) → count 2 == threshold
    for i in (1, 2):
        _write(log_dir / f"r{i}.json", {
            "artifact": "run-x",
            "rubric": {"rubric_id": "R-01"},
            "findings": [{"area": "structure"}],
        })
    out = tmp_path / "trigger.json"
    rc = _run_main(monkeypatch, log_dir, out)
    assert rc == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["next_action"] == "run-skill-rubric-governance"
    assert len(data["triggered"]) == 1
    t = data["triggered"][0]
    assert t == {"skill": "run-x", "rubric_id": "R-01", "area": "structure", "count": 2}
    cap = capsys.readouterr().out
    assert "REPEATED VIOLATIONS DETECTED: 1 pattern(s)" in cap
    assert "skill=run-x rubric=R-01 area=structure count=2" in cap
    assert "run-skill-rubric-governance" in cap


def test_main_custom_threshold(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    # count 2 だが threshold 3 → 未到達
    for i in (1, 2):
        _write(log_dir / f"r{i}.json", {
            "artifact": "run-x",
            "rubric": {"rubric_id": "R-01"},
            "findings": [{"area": "a"}],
        })
    out = tmp_path / "trigger.json"
    rc = _run_main(monkeypatch, log_dir, out, "--threshold", "3")
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["threshold"] == 3
    assert data["triggered"] == []


def test_main_skill_name_fallback_chain(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    # artifact 欠落 → skill_name、両方欠落 → file 名
    _write(log_dir / "byname.json", {
        "skill_name": "by-skill-name",
        "rubric": {"rubric_id": "R"},
        "findings": [{"area": "x"}, {"area": "x"}],
    })
    _write(log_dir / "byfile.json", {
        "rubric": {"rubric_id": "R"},
        "findings": [{"area": "y"}, {"area": "y"}],
    })
    out = tmp_path / "trigger.json"
    rc = _run_main(monkeypatch, log_dir, out)
    assert rc == 1
    triggered = json.loads(out.read_text(encoding="utf-8"))["triggered"]
    skills = {t["skill"] for t in triggered}
    assert "by-skill-name" in skills
    assert "byfile.json" in skills


def test_main_rubric_id_defaults_unknown(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    # rubric キー無し → rubric_id "unknown"
    for i in (1, 2):
        _write(log_dir / f"r{i}.json", {
            "artifact": "run-x",
            "findings": [{"area": "structure"}],
        })
    out = tmp_path / "trigger.json"
    assert _run_main(monkeypatch, log_dir, out) == 1
    t = json.loads(out.read_text(encoding="utf-8"))["triggered"][0]
    assert t["rubric_id"] == "unknown"


def test_main_area_falls_back_to_rule_id_then_unknown(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    # area 欠落 → rule_id、両方欠落 → "unknown"
    _write(log_dir / "ruleid1.json", {
        "artifact": "s1", "rubric": {"rubric_id": "R"},
        "findings": [{"rule_id": "RULE-9"}],
    })
    _write(log_dir / "ruleid2.json", {
        "artifact": "s1", "rubric": {"rubric_id": "R"},
        "findings": [{"rule_id": "RULE-9"}],
    })
    _write(log_dir / "noarea1.json", {
        "artifact": "s2", "rubric": {"rubric_id": "R"},
        "findings": [{}],
    })
    _write(log_dir / "noarea2.json", {
        "artifact": "s2", "rubric": {"rubric_id": "R"},
        "findings": [{}],
    })
    out = tmp_path / "trigger.json"
    assert _run_main(monkeypatch, log_dir, out) == 1
    triggered = json.loads(out.read_text(encoding="utf-8"))["triggered"]
    by_skill = {t["skill"]: t["area"] for t in triggered}
    assert by_skill["s1"] == "RULE-9"
    assert by_skill["s2"] == "unknown"


def test_main_findings_none_and_empty_no_trigger(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    _write(log_dir / "nofindings.json", {"artifact": "s", "rubric": {"rubric_id": "R"}})
    _write(log_dir / "emptyfindings.json", {"artifact": "s", "rubric": {"rubric_id": "R"}, "findings": []})
    out = tmp_path / "trigger.json"
    rc = _run_main(monkeypatch, log_dir, out)
    assert rc == 0
    assert json.loads(out.read_text(encoding="utf-8"))["triggered"] == []


def test_main_creates_out_parent_dir(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    out = tmp_path / "deep" / "nested" / "trigger.json"  # parent 不存在
    rc = _run_main(monkeypatch, log_dir, out)
    assert rc == 0
    assert out.exists()
    assert out.parent.is_dir()


# ── subprocess: 実 CLI ────────────────────────────────────────────────────
def test_cli_subprocess_exit1_on_repeated(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    for i in (1, 2):
        _write(log_dir / f"r{i}.json", {
            "artifact": "run-x", "rubric": {"rubric_id": "R-01"},
            "findings": [{"area": "structure"}],
        })
    out = tmp_path / "trigger.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--log-dir", str(log_dir), "--out", str(out)],
        cwd=tmp_path, text=True, capture_output=True, timeout=60,
    )
    assert proc.returncode == 1
    assert "REPEATED VIOLATIONS DETECTED" in proc.stdout
    assert json.loads(out.read_text(encoding="utf-8"))["triggered"][0]["count"] == 2


def test_cli_subprocess_exit0_on_clean(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    out = tmp_path / "trigger.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--log-dir", str(log_dir), "--out", str(out)],
        cwd=tmp_path, text=True, capture_output=True, timeout=60,
    )
    assert proc.returncode == 0
    assert "No repeated violations." in proc.stdout

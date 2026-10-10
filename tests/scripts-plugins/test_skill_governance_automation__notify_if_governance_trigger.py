"""notify-if-governance-trigger.py の Stop Hook 契約を subprocess で確かめる。

Stop Hook なので、どの入力でも exit 0 で Hook を通す。そのうえで、
  - trigger.json が無い / bootstrap / breached が空 → 何も出さない（発火していない通常の状態）
  - breached がある → stdout に招集メッセージ
  - 読めない・JSON が壊れている・形が違う → stdout は空のまま stderr に警告
    （以前は黙って exit 0 にしたり、dict でない入力で AttributeError の traceback を出していた。harness-2ix）
を実ファイルで確かめる。network: false。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-automation" / "scripts" / "notify-if-governance-trigger.py"


def _run(trigger: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--trigger", str(trigger)],
        capture_output=True,
        text=True,
    )


def test_missing_trigger_is_silent(tmp_path):
    proc = _run(tmp_path / "trigger.json")
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "")


@pytest.mark.parametrize(
    "payload",
    [{"bootstrap": True, "breached": [{"rubric_item_id": "X"}]}, {"breached": []}, {"n": 3}],
)
def test_not_fired_is_silent(tmp_path, payload):
    trigger = tmp_path / "trigger.json"
    trigger.write_text(json.dumps(payload), encoding="utf-8")
    proc = _run(trigger)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "")


def test_breached_items_are_announced(tmp_path):
    trigger = tmp_path / "trigger.json"
    trigger.write_text(
        json.dumps({"breached": [{"rubric_item_id": "R-1"}, {"x": 1}, "odd"], "n": 3, "threshold": 0.2}),
        encoding="utf-8",
    )
    proc = _run(trigger)
    assert proc.returncode == 0
    assert "違反継続項目: R-1, ?, ?" in proc.stdout
    assert "n=3、閾値 threshold=0.2" in proc.stdout
    assert proc.stderr == ""


@pytest.mark.parametrize(
    ("raw", "needle"),
    [
        (b"{broken", "JSONDecodeError"),
        (b"\xff\xfe{}", "UnicodeDecodeError"),
        (b"[1, 2]", "object でない"),
        (b'{"breached": "R-1"}', "breached が配列でない"),
    ],
)
def test_unreadable_or_malformed_trigger_warns_but_never_blocks(tmp_path, raw, needle):
    trigger = tmp_path / "trigger.json"
    trigger.write_bytes(raw)
    proc = _run(trigger)
    assert proc.returncode == 0
    assert proc.stdout == ""
    assert "[governance] warning: " in proc.stderr and needle in proc.stderr
    assert "Traceback" not in proc.stderr


@pytest.mark.parametrize("breached", ["", 0, False, "R-1", {"rubric_item_id": "R-1"}])
def test_non_list_breached_warns_instead_of_silent_noop(tmp_path, breached):
    # 以前は `breached or []` で ""・0・false が黙って「発火していない」になっていた。
    trigger = tmp_path / "trigger.json"
    trigger.write_text(json.dumps({"breached": breached}), encoding="utf-8")
    proc = _run(trigger)
    assert proc.returncode == 0
    assert proc.stdout == ""
    assert "breached が配列でない" in proc.stderr


def test_null_breached_is_not_fired(tmp_path):
    trigger = tmp_path / "trigger.json"
    trigger.write_text(json.dumps({"breached": None, "bootstrap": False}), encoding="utf-8")
    proc = _run(trigger)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "")


@pytest.mark.parametrize("bootstrap", ["false", "true", 1, 0, [], {}])
def test_non_bool_bootstrap_warns_and_still_announces_breach(tmp_path, bootstrap):
    # 文字列の "false" を真とみなして発火を捨てない。型が違えば警告し、breached を確かめる。
    trigger = tmp_path / "trigger.json"
    trigger.write_text(
        json.dumps({"bootstrap": bootstrap, "breached": [{"rubric_item_id": "R-9"}]}), encoding="utf-8"
    )
    proc = _run(trigger)
    assert proc.returncode == 0
    assert "bootstrap が真偽値でない" in proc.stderr
    assert "違反継続項目: R-9" in proc.stdout


def test_bootstrap_false_with_breach_is_announced_without_warning(tmp_path):
    trigger = tmp_path / "trigger.json"
    trigger.write_text(json.dumps({"bootstrap": False, "breached": [{"rubric_item_id": "R-2"}]}), encoding="utf-8")
    proc = _run(trigger)
    assert proc.returncode == 0
    assert "違反継続項目: R-2" in proc.stdout
    assert proc.stderr == ""


def test_unknown_argument_exit_2_is_documented(tmp_path):
    # Stop hook で exit 2 は停止の阻止になる。挙動と header の記述が合っていることを縛る。
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--unknown"], capture_output=True, text=True
    )
    assert proc.returncode == 2
    assert "未知の引数だけは argparse が usage を出して 2" in SCRIPT.read_text(encoding="utf-8")

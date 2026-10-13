"""render-pkg-findings.py の markdown 変換と入力エラーの exit code を確かめる。

対象 script:
  plugins/harness-creator/skills/assign-plugin-package-evaluator/scripts/render-pkg-findings.py

fixture は tmp_path に書き、repo は汚さない。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins" / "harness-creator" / "skills" / "assign-plugin-package-evaluator"
    / "scripts" / "render-pkg-findings.py"
)

FINDINGS = {
    "run_id": "pkg-validate-sample-20261010-001",
    "target_plugin": "sample",
    "package_mode": "bundle",
    "verdict": {"pass": 1, "fail": 1, "skip": 1, "not_applicable": 0},
    "pkg_checks": {
        "PKG-003": {
            "status": "fail",
            "findings": [
                {
                    "id": "PKG-003-001",
                    "severity": "high",
                    "location": "plugins/sample/.claude-plugin/plugin.json",
                    "evidence": "version がない",
                    "suggested_fix": "version を足す",
                }
            ],
        },
        "PKG-002": {"status": "pass", "findings": []},
        "PKG-014": {"status": "skip", "skip_reason": "対象なし", "findings": []},
    },
}


def _run(args, stdin=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )


def test_renders_markdown_sorted_by_pkg_id(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps(FINDINGS, ensure_ascii=False), encoding="utf-8")
    r = _run([str(p)])
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert out.startswith("# PKG Validator Report: sample")
    assert "pass=1 fail=1 skip=1 not_applicable=0" in out
    assert out.index("## [OK] PKG-002") < out.index("## [FAIL] PKG-003") < out.index("## [SKIP] PKG-014")
    assert "- **PKG-003-001** (high)" in out
    assert "    - fix: version を足す" in out
    assert "- skip_reason: 対象なし" in out


def test_reads_stdin():
    r = _run(["-"], stdin=json.dumps(FINDINGS))
    assert r.returncode == 0, r.stderr
    assert "# PKG Validator Report: sample" in r.stdout


def test_missing_file_is_exit2(tmp_path):
    r = _run([str(tmp_path / "ghost.json")])
    assert r.returncode == 2
    assert "cannot read findings JSON" in r.stderr
    assert "Traceback" not in r.stderr


def test_broken_json_is_exit2(tmp_path):
    p = tmp_path / "f.json"
    p.write_text("{not json", encoding="utf-8")
    r = _run([str(p)])
    assert r.returncode == 2
    assert "JSONDecodeError" in r.stderr


def test_non_utf8_is_exit2(tmp_path):
    p = tmp_path / "f.json"
    p.write_bytes(b'{"run_id": "\xff"}')
    r = _run([str(p)])
    assert r.returncode == 2
    assert "UnicodeDecodeError" in r.stderr


def test_wrong_shape_is_exit2(tmp_path):
    # validate-plugin-package の出力でない JSON (キー不足・最上位が配列) は traceback にしない
    for bad in ({"run_id": "x"}, [1, 2]):
        p = tmp_path / "f.json"
        p.write_text(json.dumps(bad), encoding="utf-8")
        r = _run([str(p)])
        assert r.returncode == 2, bad
        assert "not a findings JSON" in r.stderr
        assert "Traceback" not in r.stderr

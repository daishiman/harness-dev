# /// script
# name: test-guard-spec-drift-close
# purpose: C07 guard-spec-drift-close の close 検出・artifact 解決・C10 委譲 fail-closed 契約を検証する。
#          (a) 非該当 command → exit0 pass-through / (b) artifact 欠落 → exit2 / (c) C10 OK → exit0 /
#          (d) C10 INCOMPLETE → exit2、加えて C10 不在・issue 番号抽出不能の境界を固定する。
#          hook は PreToolUse/Bash の gh issue close のみ捕捉。
# inputs:
#   - C07 hook script / tmp_path 上の .spec-drift/<N>/ artifact と check-triage-complete.py スタブ
# outputs:
#   - pytest assertions and coverage evidence
# contexts: [E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///
"""guard-spec-drift-close.py (C07) の機能テスト。

PreToolUse/Bash 経路の `gh issue close <N>` を検出し、C10 (check-triage-complete.py) へ
4 artifact と --target-root を供給する close 前 fail-closed ゲートの受入・遮断・pass-through を固定する。

exit code 契約:
  0  非該当 pass-through / C10 OK (close 許可)
  2  artifact 欠落 / C10 不在・INCOMPLETE / issue 番号抽出不能 (fail-closed)

C10 の起動は「一時 plugin root の scripts/check-triage-complete.py スタブ」を CLAUDE_PLUGIN_ROOT で
差し替えて制御する (OK=exit0 / INCOMPLETE=exit3 のスタブ)。実 C10 実装には依存しない。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "guard-spec-drift-close.py"

_ARTIFACT_NAMES = (
    "triage-report.json",
    "triage-verdict.json",
    "sync-proposal.json",
    "sync-audit-verdict.json",
)


def _run(command: str, project_dir: Path, plugin_root: Path | None = None) -> subprocess.CompletedProcess:
    """hook を subprocess で起動し stdin に hook input JSON を渡す。"""
    payload = {"tool_input": {"command": command}, "cwd": str(project_dir)}
    # 親 process の COVERAGE_PROCESS_START/COVERAGE_FILE/PYTHONPATH を保持し、hook の
    # subprocess coverage を測定可能にする。必要な plugin 環境だけを上書きする。
    env = os.environ.copy()
    env.update({
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "PATH": _os_path(),
    })
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def _os_path() -> str:
    import os

    return os.environ.get("PATH", "")


def _write_artifacts(project_dir: Path, issue: int) -> None:
    """対象 issue の .spec-drift/<N>/ に 4 artifact のダミーを作成する。"""
    art_dir = project_dir / ".spec-drift" / str(issue)
    art_dir.mkdir(parents=True, exist_ok=True)
    for name in _ARTIFACT_NAMES:
        (art_dir / name).write_text(json.dumps({"issue": issue}), encoding="utf-8")


def _make_c10_stub(plugin_root: Path, exit_code: int) -> None:
    """CLAUDE_PLUGIN_ROOT/scripts/check-triage-complete.py に固定 exit code を返すスタブを置く。"""
    scripts = plugin_root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    stub = scripts / "check-triage-complete.py"
    stub.write_text(
        "import sys\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )


# ─────────────────── (a) 非該当コマンド → pass-through exit0 ───────────────────
def test_non_close_command_passes_through(tmp_path):
    res = _run("git commit -m 'close #17 fix'", tmp_path)
    assert res.returncode == 0, res.stderr


def test_gh_issue_list_passes_through(tmp_path):
    res = _run("gh issue list --state open", tmp_path)
    assert res.returncode == 0, res.stderr


# ─────────────────── (b) artifact 欠落 → exit2 (fail-closed) ───────────────────
def test_missing_artifacts_blocks(tmp_path):
    # .spec-drift/17/ を作らないまま close → artifact 欠落で遮断。
    res = _run("gh issue close 17", tmp_path)
    assert res.returncode == 2, res.stdout + res.stderr
    assert "artifact" in res.stderr


def test_partial_artifacts_blocks(tmp_path):
    # 3/4 だけ存在 → 欠落 1 件でも fail-closed。
    art_dir = tmp_path / ".spec-drift" / "17"
    art_dir.mkdir(parents=True)
    for name in _ARTIFACT_NAMES[:3]:
        (art_dir / name).write_text("{}", encoding="utf-8")
    res = _run("gh issue close 17", tmp_path)
    assert res.returncode == 2, res.stdout + res.stderr
    assert "sync-audit-verdict.json" in res.stderr


# ─────────────────── (c) C10 OK → exit0 (close 許可) ───────────────────
def test_c10_ok_allows_close(tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    plugin_root = tmp_path / "plugin"
    _write_artifacts(project_dir, 17)
    _make_c10_stub(plugin_root, exit_code=0)  # OK
    res = _run("gh issue close 17 --reason completed", project_dir, plugin_root=plugin_root)
    assert res.returncode == 0, res.stdout + res.stderr


def test_c10_ok_allows_close_url_form(tmp_path):
    # URL 形式 (.../issues/17) からも issue 番号を抽出できること。
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    plugin_root = tmp_path / "plugin"
    _write_artifacts(project_dir, 17)
    _make_c10_stub(plugin_root, exit_code=0)
    res = _run(
        "gh issue close https://github.com/o/r/issues/17",
        project_dir,
        plugin_root=plugin_root,
    )
    assert res.returncode == 0, res.stdout + res.stderr


# ─────────────────── (d) C10 INCOMPLETE → exit2 (遮断) ───────────────────
def test_c10_incomplete_blocks(tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    plugin_root = tmp_path / "plugin"
    _write_artifacts(project_dir, 17)
    _make_c10_stub(plugin_root, exit_code=3)  # INCOMPLETE
    res = _run("gh issue close 17", project_dir, plugin_root=plugin_root)
    assert res.returncode == 2, res.stdout + res.stderr
    assert "C10" in res.stderr


# ─────────────────── 追加境界: C10 不在 / 番号抽出不能 → exit2 ───────────────────
def test_missing_c10_blocks(tmp_path):
    # artifact は揃っているが C10 スクリプトが存在しない plugin root → 環境不備で fail-closed。
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    plugin_root = tmp_path / "empty-plugin"
    plugin_root.mkdir()
    _write_artifacts(project_dir, 17)
    res = _run("gh issue close 17", project_dir, plugin_root=plugin_root)
    assert res.returncode == 2, res.stdout + res.stderr
    assert "C10" in res.stderr


def test_close_without_number_blocks(tmp_path):
    res = _run("gh issue close", tmp_path)
    assert res.returncode == 2, res.stdout + res.stderr
    assert "抽出" in res.stderr

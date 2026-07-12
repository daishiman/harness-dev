"""evaluate-create-gates.py の genuine 機能テスト (scripts4 / 独立計測用)。

対象: plugins/prompt-creator/skills/run-prompt-create/scripts/evaluate-create-gates.py

挙動の要約:
  run-prompt-create の elegant-review 起動可否 / fast_mode 適用可否をファイル状態のみで
  機械決定する。LLM 判断で揺れないよう副作用は stdout への JSON 出力のみ (exit 常に 0)。
  判定基準:
    * 出力ファイルが存在しない (new prompt)         → elegant-review 必須
    * diff_lines(出力ファイル) > threshold (既定 30) → elegant-review 必須
    * --fast 指定 かつ 上記いずれも非該当            → fast_mode 適用
    * それ以外                                       → 通常フロー
  output_path の決定: --output 明示 > brief JSON の output_path > None (=new 扱い)。
  diff_lines: git diff --numstat HEAD の追加+削除行を返す。
    - path 不在 → 0
    - git 未インストール (FileNotFoundError) → 0
    - git diff が空/非0 (untracked) → ファイル全行数
    - numstat パース不能 → 0

検証方針:
  - 純関数 diff_lines は (a) monkeypatch で subprocess.run/FileNotFoundError を stub し
    tracked/untracked/numstat異常/path不在の各経路を assert、(b) 実 git repo (tmp_path)
    でも追跡済みファイルの追加削除行を実測する genuine 統合テストを併用。
  - main は argv を monkeypatch して in-process 実行し stdout JSON を parse、
    全分岐 (new_prompt / diff超過 / fast適用 / fast不適用 / brief推定 / brief壊れ /
    output明示 / threshold境界) を網羅。
  - CLI 経路 (__main__ guard / argparse required) は subprocess(sys.executable) で
    exit code と stdout を実測。

network: false / keychain: なし / 実 repo 書換: なし (tmp_path + monkeypatch のみ)。
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
    / "prompt-creator"
    / "skills"
    / "run-prompt-create"
    / "scripts"
    / "evaluate-create-gates.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("evaluate_create_gates_uut_r4", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(cwd) if cwd else None,
    )


def _main_payload(monkeypatch, argv, capsys):
    """main() を in-process 実行し stdout の JSON payload を返す。"""
    monkeypatch.setattr(MOD.sys, "argv", argv)
    rc = MOD.main()
    out = capsys.readouterr().out
    return rc, json.loads(out)


# ── diff_lines: monkeypatch stub による分岐網羅 ──────────────────────────────
def test_diff_lines_missing_path_returns_zero(tmp_path):
    assert MOD.diff_lines(tmp_path / "does-not-exist.md") == 0


def test_diff_lines_tracked_sums_added_and_deleted(tmp_path, monkeypatch):
    f = tmp_path / "p.md"
    f.write_text("x\n", encoding="utf-8")

    class R:
        returncode = 0
        stdout = "12\t7\tp.md\n"

    monkeypatch.setattr(MOD.subprocess, "run", lambda *a, **k: R())
    assert MOD.diff_lines(f) == 19


def test_diff_lines_git_missing_returns_zero(tmp_path, monkeypatch):
    f = tmp_path / "p.md"
    f.write_text("x\n", encoding="utf-8")

    def boom(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(MOD.subprocess, "run", boom)
    assert MOD.diff_lines(f) == 0


def test_diff_lines_untracked_counts_all_lines(tmp_path, monkeypatch):
    # git diff returncode!=0 (untracked) → ファイル全行数を返す
    f = tmp_path / "p.md"
    f.write_text("a\nb\nc\nd\n", encoding="utf-8")

    class R:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(MOD.subprocess, "run", lambda *a, **k: R())
    assert MOD.diff_lines(f) == 4


def test_diff_lines_empty_stdout_returncode_zero_counts_all(tmp_path, monkeypatch):
    # returncode 0 だが stdout 空 → untracked 分岐 (or not result.stdout.strip())
    f = tmp_path / "p.md"
    f.write_text("only-one-line\n", encoding="utf-8")

    class R:
        returncode = 0
        stdout = "   \n"

    monkeypatch.setattr(MOD.subprocess, "run", lambda *a, **k: R())
    assert MOD.diff_lines(f) == 1


def test_diff_lines_untracked_open_oserror_returns_zero(tmp_path, monkeypatch):
    # untracked 分岐で path.open が OSError → except OSError → 0
    # ディレクトリは exists() True だが open() で IsADirectoryError(OSError) を投げる
    d = tmp_path / "as_dir"
    d.mkdir()

    class R:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(MOD.subprocess, "run", lambda *a, **k: R())
    assert MOD.diff_lines(d) == 0


def test_diff_lines_binary_numstat_dash_returns_zero(tmp_path, monkeypatch):
    # binary ファイルは numstat が "-\t-\t..." → int 変換失敗 → 0
    f = tmp_path / "bin.dat"
    f.write_text("x\n", encoding="utf-8")

    class R:
        returncode = 0
        stdout = "-\t-\tbin.dat\n"

    monkeypatch.setattr(MOD.subprocess, "run", lambda *a, **k: R())
    assert MOD.diff_lines(f) == 0


def test_diff_lines_real_git_repo_tracked_change(tmp_path):
    # genuine: 実 git repo を作りコミット後に追記、numstat 追加行を実測。
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        pytest.skip("git not available")
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@e",
    }
    import os as _os

    full_env = {**_os.environ, **env}
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    f = repo / "p.md"
    f.write_text("line1\nline2\n", encoding="utf-8")
    subprocess.run(["git", "add", "p.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True, env=full_env)
    # 3 行追加
    f.write_text("line1\nline2\nadd3\nadd4\nadd5\n", encoding="utf-8")
    cur = _os.getcwd()
    try:
        _os.chdir(repo)
        # diff_lines は cwd 相対の git を呼ぶため repo 内で実行
        n = MOD.diff_lines(Path("p.md"))
    finally:
        _os.chdir(cur)
    assert n == 3, "3 行追加 (削除なし) を numstat から読む"


# ── main: in-process via argv monkeypatch ────────────────────────────────────
def test_main_new_prompt_no_output_file(monkeypatch, capsys, tmp_path):
    # --output 指定だがファイル未作成 → new_prompt → elegant 必須
    out = tmp_path / "absent.md"
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p1", "--output", str(out)],
        capsys,
    )
    assert rc == 0
    assert p["prompt_name"] == "p1"
    assert p["elegant_review_required"] is True
    assert p["fast_mode"] is False
    assert p["diff_lines"] == 0
    assert "new_prompt" in p["reasons"]


def test_main_existing_small_diff_no_elegant(monkeypatch, capsys, tmp_path):
    out = tmp_path / "exists.md"
    out.write_text("body\n", encoding="utf-8")
    # diff_lines を 5 に固定 (threshold 30 未満)
    monkeypatch.setattr(MOD, "diff_lines", lambda path: 5)
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p2", "--output", str(out)],
        capsys,
    )
    assert rc == 0
    assert p["elegant_review_required"] is False
    assert p["fast_mode"] is False
    assert p["diff_lines"] == 5
    assert p["reasons"] == []


def test_main_existing_large_diff_requires_elegant(monkeypatch, capsys, tmp_path):
    out = tmp_path / "exists.md"
    out.write_text("body\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "diff_lines", lambda path: 40)
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p3", "--output", str(out)],
        capsys,
    )
    assert p["elegant_review_required"] is True
    assert p["diff_lines"] == 40
    assert any(r.startswith("diff_lines=40>30") for r in p["reasons"])


def test_main_threshold_boundary_equal_is_not_over(monkeypatch, capsys, tmp_path):
    # lines == threshold は ">" なので超過扱いしない
    out = tmp_path / "exists.md"
    out.write_text("body\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "diff_lines", lambda path: 30)
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p4", "--output", str(out), "--threshold", "30"],
        capsys,
    )
    assert p["elegant_review_required"] is False
    assert p["reasons"] == []


def test_main_custom_threshold_triggers_elegant(monkeypatch, capsys, tmp_path):
    out = tmp_path / "exists.md"
    out.write_text("body\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "diff_lines", lambda path: 11)
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p5", "--output", str(out), "--threshold", "10"],
        capsys,
    )
    assert p["elegant_review_required"] is True
    assert any("diff_lines=11>10" in r for r in p["reasons"])


def test_main_fast_applied_when_no_elegant(monkeypatch, capsys, tmp_path):
    out = tmp_path / "exists.md"
    out.write_text("body\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "diff_lines", lambda path: 3)
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p6", "--output", str(out), "--fast"],
        capsys,
    )
    assert p["elegant_review_required"] is False
    assert p["fast_mode"] is True
    assert "fast_mode_applied" in p["reasons"]


def test_main_fast_ignored_when_elegant_required(monkeypatch, capsys, tmp_path):
    # new prompt なので elegant 必須 → --fast 無視
    out = tmp_path / "absent.md"
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p7", "--output", str(out), "--fast"],
        capsys,
    )
    assert p["elegant_review_required"] is True
    assert p["fast_mode"] is False
    assert "fast_mode_applied" not in p["reasons"]


def test_main_output_path_inferred_from_brief(monkeypatch, capsys, tmp_path):
    target = tmp_path / "generated.md"  # 存在しない → new_prompt
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"output_path": str(target)}), encoding="utf-8")
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p8", "--brief", str(brief)],
        capsys,
    )
    assert p["elegant_review_required"] is True
    assert "new_prompt" in p["reasons"]


def test_main_brief_existing_output_uses_diff(monkeypatch, capsys, tmp_path):
    target = tmp_path / "generated.md"
    target.write_text("body\n", encoding="utf-8")
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"output_path": str(target)}), encoding="utf-8")
    monkeypatch.setattr(MOD, "diff_lines", lambda path: 2)
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p9", "--brief", str(brief)],
        capsys,
    )
    assert p["elegant_review_required"] is False
    assert p["diff_lines"] == 2


def test_main_brief_without_output_path_is_new(monkeypatch, capsys, tmp_path):
    # brief は存在するが output_path キー無し → output_path None → new_prompt
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"unrelated": 1}), encoding="utf-8")
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p10", "--brief", str(brief)],
        capsys,
    )
    assert p["elegant_review_required"] is True
    assert "new_prompt" in p["reasons"]


def test_main_brief_invalid_json_swallowed_is_new(monkeypatch, capsys, tmp_path):
    # 壊れた brief JSON → JSONDecodeError を握りつぶし output_path None → new_prompt
    brief = tmp_path / "brief.json"
    brief.write_text("{ not json", encoding="utf-8")
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p11", "--brief", str(brief)],
        capsys,
    )
    assert rc == 0
    assert p["elegant_review_required"] is True
    assert "new_prompt" in p["reasons"]


def test_main_brief_absent_default_path_is_new(monkeypatch, capsys, tmp_path):
    # brief パスを存在しない場所に向ける (既定 eval-log/... も無い前提) → new_prompt
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p12", "--brief", str(tmp_path / "no-brief.json")],
        capsys,
    )
    assert p["elegant_review_required"] is True
    assert "new_prompt" in p["reasons"]


def test_main_output_overrides_brief(monkeypatch, capsys, tmp_path):
    # --output 明示は brief 推定より優先 (brief の output_path は無視される)
    explicit = tmp_path / "explicit.md"
    explicit.write_text("body\n", encoding="utf-8")
    brief = tmp_path / "brief.json"
    brief.write_text(
        json.dumps({"output_path": str(tmp_path / "from-brief.md")}), encoding="utf-8"
    )
    monkeypatch.setattr(MOD, "diff_lines", lambda path: 1 if Path(path) == explicit else 999)
    rc, p = _main_payload(
        monkeypatch,
        ["x", "--prompt-name", "p13", "--output", str(explicit), "--brief", str(brief)],
        capsys,
    )
    # explicit を見ているので diff=1 (small) → elegant 不要
    assert p["diff_lines"] == 1
    assert p["elegant_review_required"] is False


# ── CLI subprocess (exit code / argparse required / __main__ guard) ──────────
def test_cli_missing_required_prompt_name_exit_2():
    res = _run_cli()
    assert res.returncode == 2
    assert "--prompt-name" in res.stderr or "required" in res.stderr.lower()


def test_cli_new_prompt_outputs_json(tmp_path):
    out = tmp_path / "absent.md"
    res = _run_cli("--prompt-name", "cli1", "--output", str(out))
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["prompt_name"] == "cli1"
    assert payload["elegant_review_required"] is True
    assert payload["fast_mode"] is False


def test_cli_fast_applied(tmp_path):
    out = tmp_path / "exists.md"
    out.write_text("body\n", encoding="utf-8")
    # tmp_path は git 管理外 → diff_lines は untracked → 1 行 (threshold 未満)
    res = _run_cli("--prompt-name", "cli2", "--output", str(out), "--fast", cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["elegant_review_required"] is False
    assert payload["fast_mode"] is True
    assert "fast_mode_applied" in payload["reasons"]

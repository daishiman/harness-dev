"""hook-guard-skillgen.py の機械バリア動作を実証する。

skill-intake 実行中 (lock 有効) は スキル生成 (run-skill-create 等) を exit 2 で遮断し、
非実行中・子スキル・stale lock では素通し (exit 0) であることを、hook を subprocess 起動して検証する。
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "plugins" / "skill-intake" / "hooks" / "hook-guard-skillgen.py"
LOCK_REL = Path("eval-log") / "intake-locks" / "intake-active.lock"


def run_hook(payload: dict) -> int:
    # lock パスは本番で CLAUDE_PROJECT_DIR を最優先する (F-STRAT-01)。テストは payload.cwd と
    # 同一値を CLAUDE_PROJECT_DIR に明示注入し、ambient な CLAUDE_PROJECT_DIR (実リポジトリ) に
    # 汚染されず tmp_path 内で完結させる。
    env = dict(os.environ)
    if payload.get("cwd"):
        env["CLAUDE_PROJECT_DIR"] = payload["cwd"]
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode


def pre_skill(cwd, skill):
    return {"hook_event_name": "PreToolUse", "tool_name": "Skill",
            "tool_input": {"skill": skill}, "cwd": str(cwd)}


def pre_task(cwd, subagent_type):
    return {"hook_event_name": "PreToolUse", "tool_name": "Task",
            "tool_input": {"subagent_type": subagent_type}, "cwd": str(cwd)}


def pre_bash(cwd, command):
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": command}, "cwd": str(cwd)}


def post_skill(cwd, skill):
    return {"hook_event_name": "PostToolUse", "tool_name": "Skill",
            "tool_input": {"skill": skill}, "cwd": str(cwd)}


def lock_file(cwd) -> Path:
    return Path(cwd) / LOCK_REL


def test_intake_start_creates_lock(tmp_path):
    assert run_hook(pre_skill(tmp_path, "run-skill-intake")) == 0
    assert lock_file(tmp_path).is_file()


def test_generation_blocked_while_intake_active(tmp_path):
    run_hook(pre_skill(tmp_path, "run-skill-intake"))  # lock 作成
    # 生成スキルは bare / plugin-prefix いずれも遮断
    assert run_hook(pre_skill(tmp_path, "run-skill-create")) == 2
    assert run_hook(pre_skill(tmp_path, "harness-creator:run-build-skill")) == 2
    assert run_hook(pre_skill(tmp_path, "capability-build")) == 2
    # Task 経由の生成 worker も遮断
    assert run_hook(pre_task(tmp_path, "run-build-skill-subagent")) == 2


def test_generation_blocked_from_bash_while_intake_active(tmp_path):
    run_hook(pre_skill(tmp_path, "run-skill-intake"))  # lock 作成
    assert run_hook(pre_bash(tmp_path, "claude /capability-build foo")) == 2
    assert run_hook(pre_bash(tmp_path, "claude Skill(run-build-skill, args=foo)")) == 2
    assert run_hook(pre_bash(tmp_path, "echo run-build-skillful")) == 0


def test_child_skills_pass_while_intake_active(tmp_path):
    run_hook(pre_skill(tmp_path, "run-skill-intake"))  # lock 作成
    # intake の 11 phase 子委譲・SubAgent は denylist 非該当 → 素通し (誤爆ゼロ)
    for child in ("run-intake-kickoff", "skill-intake:run-intake-finalize",
                  "run-notion-intake-publish", "run-intake-next-action"):
        assert run_hook(pre_skill(tmp_path, child)) == 0
    assert run_hook(pre_task(tmp_path, "skill-intake-summarizer")) == 0


def test_generation_allowed_when_not_intake(tmp_path):
    # lock 無し (intake 非実行) → 通常の run-skill-create 単独起動は妨げない
    assert run_hook(pre_skill(tmp_path, "run-skill-create")) == 0
    assert run_hook(pre_task(tmp_path, "run-build-skill-subagent")) == 0
    assert run_hook(pre_bash(tmp_path, "claude /capability-build foo")) == 0


def test_lock_released_on_intake_post(tmp_path):
    run_hook(pre_skill(tmp_path, "run-skill-intake"))
    assert run_hook(pre_skill(tmp_path, "run-skill-create")) == 2  # 実行中は遮断
    run_hook(post_skill(tmp_path, "run-skill-intake"))             # intake 終了
    assert not lock_file(tmp_path).is_file()
    assert run_hook(pre_skill(tmp_path, "run-skill-create")) == 0  # 終了後は許可


def test_stale_lock_fails_open(tmp_path):
    # 失効 lock は無視され生成は素通し (dangling 防止・可用性優先)
    lf = lock_file(tmp_path)
    lf.parent.mkdir(parents=True, exist_ok=True)
    lf.write_text(json.dumps({"intake_skill": "run-skill-intake",
                              "created_at": 0, "expires_at": time.time() - 1}))
    assert run_hook(pre_skill(tmp_path, "run-skill-create")) == 0
    assert not lf.is_file()  # stale lock は自動掃除される


def test_stop_event_does_not_clear_lock(tmp_path):
    # Stop は応答ターン毎に発火しうる。intake は複数ターンに跨るため Stop で解除すると
    # 途中の生成が素通る (F-LOOP-01)。Stop では lock を解除しないことを保証する。
    run_hook(pre_skill(tmp_path, "run-skill-intake"))
    assert lock_file(tmp_path).is_file()
    run_hook({"hook_event_name": "Stop", "cwd": str(tmp_path)})
    assert lock_file(tmp_path).is_file()  # Stop では解除されない
    # Stop 後も intake 実行中とみなし生成は遮断され続ける
    assert run_hook(pre_skill(tmp_path, "run-skill-create")) == 2


def test_session_end_clears_lock(tmp_path):
    # セッション終了 backstop でのみ解除する
    run_hook(pre_skill(tmp_path, "run-skill-intake"))
    assert lock_file(tmp_path).is_file()
    run_hook({"hook_event_name": "SessionEnd", "cwd": str(tmp_path)})
    assert not lock_file(tmp_path).is_file()


def test_lock_tamper_via_bash_blocked_while_intake_active(tmp_path):
    # lock ファイルの削除・移動で遮断を無効化する回避路を封鎖する (paradox attack_path_1)
    run_hook(pre_skill(tmp_path, "run-skill-intake"))
    assert run_hook(pre_bash(tmp_path, "rm eval-log/intake-locks/intake-active.lock")) == 2
    assert run_hook(pre_bash(tmp_path, "rm -f ./eval-log/intake-locks/intake-active.lock")) == 2
    assert run_hook(pre_bash(tmp_path, "mv eval-log/intake-locks/intake-active.lock /tmp/x")) == 2
    # lock は依然有効で生成も遮断され続ける
    assert lock_file(tmp_path).is_file()
    assert run_hook(pre_skill(tmp_path, "run-skill-create")) == 2


def test_lock_tamper_allowed_when_not_intake(tmp_path):
    # intake 非実行中は lock 操作自体が無意味なので素通し (誤爆ゼロ)
    assert run_hook(pre_bash(tmp_path, "rm eval-log/intake-locks/intake-active.lock")) == 0


def test_lock_path_prefers_project_dir_over_cwd(tmp_path):
    # CLAUDE_PROJECT_DIR を最優先。cwd が別ディレクトリでも同一 lock を参照し分裂しない (F-STRAT-01)
    project = tmp_path / "project"
    other_cwd = tmp_path / "subagent-cwd"
    project.mkdir()
    other_cwd.mkdir()
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)

    def run_with_cwd(payload):
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload), capture_output=True, text=True, env=env,
        )
        return proc.returncode

    # intake は project 根で開始 (cwd=project)
    run_with_cwd({"hook_event_name": "PreToolUse", "tool_name": "Skill",
                  "tool_input": {"skill": "run-skill-intake"}, "cwd": str(project)})
    assert (project / LOCK_REL).is_file()
    # 生成起動が別 cwd (SubAgent) でも CLAUDE_PROJECT_DIR の lock を見て遮断される
    assert run_with_cwd({"hook_event_name": "PreToolUse", "tool_name": "Skill",
                         "tool_input": {"skill": "run-skill-create"}, "cwd": str(other_cwd)}) == 2


def test_skill_name_key_variants_create_lock(tmp_path):
    # tool_input のキー揺れ (skill / skill_name / name) いずれでも intake 起動を検出する (F-CAUSAL-01)
    for key in ("skill", "skill_name", "name"):
        lf = lock_file(tmp_path)
        lf.unlink(missing_ok=True)
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Skill",
                   "tool_input": {key: "run-skill-intake"}, "cwd": str(tmp_path)}
        assert run_hook(payload) == 0
        assert lf.is_file(), f"key={key} で lock 未作成"


def test_malformed_input_is_graceful(tmp_path):
    proc = subprocess.run([sys.executable, str(HOOK)], input="not json",
                          capture_output=True, text=True)
    assert proc.returncode == 0  # 解釈不能入力でセッションを壊さない

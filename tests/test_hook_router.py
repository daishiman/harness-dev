"""hook-router と build-hook-registry の粒度・ホスト等価性・fail-closed を固定する。

粒度: event / tool / plugin / slash-command / skill の 5 軸で発火対象が決まること。
等価性: Claude の Bash と Codex の shell_command が同一 handler 集合を選ぶこと。
fail-closed: registry 不読・handler 失敗・timeout が緑にならないこと。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ROUTER_PATH = ROOT / "plugins" / "harness-creator" / "scripts" / "hook-router.py"
BUILDER_PATH = ROOT / "plugins" / "harness-creator" / "scripts" / "build-hook-registry.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ROUTER = _load(ROUTER_PATH, "hook_router")
BUILDER = _load(BUILDER_PATH, "build_hook_registry")


def _entry(**over):
    base = {
        "id": "demo:PreToolUse:0:0",
        "plugin": "demo",
        "event": "PreToolUse",
        "tool_scoped": True,
        "matcher": {"claude": "Bash", "codex": "shell_command|exec_command"},
        "scope": {},
        "command": "true",
        "timeout": 5,
        "async": False,
        "products": ["claude", "codex"],
    }
    base.update(over)
    return base


def _registry(*entries):
    return {"schema_version": 1, "entries": list(entries), "codex_unreachable": []}


# --- 粒度: tool / host ---------------------------------------------------------

def test_same_handler_selected_on_both_hosts():
    """Claude の Bash と Codex の shell_command は同じ handler を選ぶこと。"""
    reg = _registry(_entry())
    claude = ROUTER.select(reg, "PreToolUse", "claude", {"tool_name": "Bash"})
    codex = ROUTER.select(reg, "PreToolUse", "codex", {"tool_name": "shell_command"})
    assert [e["id"] for e in claude] == [e["id"] for e in codex] == ["demo:PreToolUse:0:0"]


def test_non_matching_tool_is_skipped():
    reg = _registry(_entry())
    assert ROUTER.select(reg, "PreToolUse", "claude", {"tool_name": "Read"}) == []


def test_entry_unreachable_on_codex_never_fires_there():
    """products に codex が無い entry は Codex で選ばれないこと (虚偽の到達主張の遮断)。"""
    reg = _registry(_entry(matcher={"claude": "Skill", "codex": ""}, products=["claude"]))
    assert ROUTER.select(reg, "PreToolUse", "codex", {"tool_name": "shell_command"}) == []
    assert len(ROUTER.select(reg, "PreToolUse", "claude", {"tool_name": "Skill"})) == 1


def test_event_isolation():
    reg = _registry(_entry())
    assert ROUTER.select(reg, "PostToolUse", "claude", {"tool_name": "Bash"}) == []


# --- 粒度: skill / slash-command ----------------------------------------------

def test_skill_scope_selects_only_declared_skill():
    reg = _registry(
        _entry(id="a", scope={"skills": ["run-build-*"]}, matcher={"claude": "Skill", "codex": ""}),
        _entry(id="b", scope={"skills": ["run-other"]}, matcher={"claude": "Skill", "codex": ""}),
    )
    payload = {"tool_name": "Skill", "tool_input": {"skill_name": "run-build-skill"}}
    assert [e["id"] for e in ROUTER.select(reg, "PreToolUse", "claude", payload)] == ["a"]


def test_skill_scope_is_fail_closed_when_skill_unknown():
    """スコープ宣言のある entry は、対象を特定できない実行へ発火しないこと。"""
    reg = _registry(_entry(scope={"skills": ["run-build-*"]}))
    assert ROUTER.select(reg, "PreToolUse", "claude", {"tool_name": "Bash"}) == []


def test_unscoped_entry_fires_for_every_skill():
    reg = _registry(_entry(matcher={"claude": "Skill", "codex": ""}))
    payload = {"tool_name": "Skill", "tool_input": {"skill_name": "anything"}}
    assert len(ROUTER.select(reg, "PreToolUse", "claude", payload)) == 1


def test_slash_command_scope():
    reg = _registry(_entry(
        id="c", event="UserPromptSubmit", tool_scoped=False,
        matcher={"claude": ".*", "codex": ".*"}, scope={"commands": ["build-app"]},
    ))
    hit = ROUTER.select(reg, "UserPromptSubmit", "claude", {"prompt": "/build-app 引数"})
    miss = ROUTER.select(reg, "UserPromptSubmit", "claude", {"prompt": "/other"})
    assert [e["id"] for e in hit] == ["c"] and miss == []


def test_slash_command_resolution():
    assert ROUTER.resolve_slash_command({"prompt": "  /run-skill:x arg"}) == "run-skill:x"
    assert ROUTER.resolve_slash_command({"prompt": "普通の依頼"}) is None


# --- fail-closed ---------------------------------------------------------------

@pytest.mark.parametrize(
    "codes,expected",
    [([], 0), ([0, 0], 0), ([0, 2], 2), ([1, 0], 1), ([1, 2], 2), ([3], 1)],
)
def test_combine_verdicts_block_wins(codes, expected):
    """どの guard も単独で拒否権を持ち、失敗は 0 に丸められないこと。"""
    assert ROUTER.combine_verdicts(codes) == expected


def test_unreadable_registry_exits_nonzero(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(ROUTER_PATH), "--event", "PreToolUse",
         "--registry", str(tmp_path / "absent.json")],
        input="{}", text=True, capture_output=True,
    )
    assert proc.returncode == 1 and "registry unreadable" in proc.stderr


def test_blocking_handler_blocks_router(tmp_path):
    reg = _registry(_entry(command="exit 2"))
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROUTER_PATH), "--event", "PreToolUse", "--host", "claude",
         "--registry", str(path)],
        input=json.dumps({"tool_name": "Bash"}), text=True, capture_output=True,
    )
    assert proc.returncode == ROUTER.BLOCK


def test_payload_reaches_handler_verbatim(tmp_path):
    """stdin の hook JSON が委譲先へそのまま渡ること (両ホスト共通スキーマの前提)。"""
    sink = tmp_path / "seen.json"
    reg = _registry(_entry(command=f"cat > {sink}"))
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg), encoding="utf-8")
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    subprocess.run(
        [sys.executable, str(ROUTER_PATH), "--event", "PreToolUse", "--host", "claude",
         "--registry", str(path)],
        input=json.dumps(payload), text=True, capture_output=True,
    )
    assert json.loads(sink.read_text(encoding="utf-8")) == payload


# --- builder -------------------------------------------------------------------

def test_matcher_translation_maps_claude_tools_to_codex():
    matcher, dead = BUILDER.translate_matcher("Bash|Edit|Write")
    assert matcher == "shell_command|exec_command|apply_patch" and dead == []


def test_matcher_translation_reports_unreachable_tools():
    """Codex に対応 tool が無いものは黙って落とさず報告されること。"""
    matcher, dead = BUILDER.translate_matcher("Skill|Task")
    assert matcher == "" and dead == ["Skill", "Task"]


def test_matcher_translation_passes_through_codex_names():
    matcher, _ = BUILDER.translate_matcher("Bash|shell_command|apply_patch")
    assert matcher.split("|") == ["shell_command", "exec_command", "apply_patch"]


def test_codex_skill_guard_reaches_codex_via_prompt():
    """Codex に skill tool は無く $skill-name で起動するため、PreToolUse+Skill の
    guard は UserPromptSubmit の companion 経由でのみ Codex に届くこと。"""
    registry = json.loads((ROOT / ".codex" / "hooks" / "registry.json").read_text(encoding="utf-8"))
    companions = [e for e in registry["entries"] if e["id"].endswith(":codex-skill-invocation")]
    assert companions, "skill 起動 guard の Codex 経路が失われている"
    for entry in companions:
        assert entry["products"] == ["codex"] and entry["event"] == "UserPromptSubmit"
    hit = ROUTER.select(registry, "UserPromptSubmit", "codex", {"prompt": "$run-skill-intake x"})
    miss = ROUTER.select(registry, "UserPromptSubmit", "codex", {"prompt": "普通の依頼"})
    assert any(e["id"].endswith(":codex-skill-invocation") for e in hit)
    assert not any(e["id"].endswith(":codex-skill-invocation") for e in miss)


def test_companion_is_not_created_for_post_execution_hooks():
    """実行後 hook に companion を作ると発火時点が変わって嘘になるため作らないこと。"""
    entry = _entry(event="PostToolUse", matcher={"claude": "Skill", "codex": ""}, products=["claude"])
    assert BUILDER.skill_invocation_companion(entry, ["Skill"]) is None


def test_codex_skill_name_resolved_from_dollar_prefix():
    assert ROUTER.resolve_skill({"prompt": "$run-build-skill 引数"}) == "run-build-skill"


def test_repo_projection_is_in_sync():
    """生成物が commit 済みの内容と一致すること (drift は make で落ちる)。"""
    report, code = BUILDER.run(ROOT, "check")
    assert code == 0, f"hook registry drift: {report['paths']}"


def test_every_codex_entry_has_a_reachable_matcher():
    registry = json.loads((ROOT / ".codex" / "hooks" / "registry.json").read_text(encoding="utf-8"))
    for entry in registry["entries"]:
        if "codex" in entry["products"] and entry["tool_scoped"]:
            assert entry["matcher"]["codex"], f"{entry['id']} claims codex without a matcher"


def test_codex_hooks_json_preserves_foreign_handlers():
    """bd の handler を投影が食い潰していないこと。"""
    doc = json.loads((ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    commands = [h["command"] for groups in doc["hooks"].values()
                for g in groups for h in g["hooks"]]
    assert any(c.startswith("bd codex-hook") for c in commands)

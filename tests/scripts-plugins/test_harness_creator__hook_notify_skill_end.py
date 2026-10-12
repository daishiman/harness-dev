"""run-skill-update-notifier の PostToolUse hook (hook-notify-skill-end.py) の単体テスト。

feedback_contract IN2 (run-skill-update-notifier) を機械検証する:
- 表示経路: 通知は `{"systemMessage": "<plugin>: <1 行>"}` の JSON 1 個として stdout に出る
  (PostToolUse の素の stdout は debug log 行きで利用者に見えない。JSON 1 個なら
  Claude Code が読み、systemMessage を利用者に表示する)。通知が無いときは何も出さない
- filter: tool_name == "Skill" のときだけ通知し、Read や Bash では何も出さない
- 重複抑止: 同じ session で同じ plugin の通知は 1 回だけ (cache の
  notified.<plugin> に session_id と last_notified_at が残る)

hook は本番と同じく subprocess で起動し、stdin に hook payload を渡す。
notifier-check.py は Path.home() 配下の cache を読むので、HOME を tmp_path に
差し替えてユーザーの実 cache (~/.cache/harness) を一切触らない。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "harness-creator"
HOOK = PLUGIN / "skills" / "run-skill-update-notifier" / "scripts" / "hook-notify-skill-end.py"
# hooks/hooks.json が実際に起動する公開 entry point (HOOK へ execv で委譲する)
ENTRY = PLUGIN / "hooks" / "notify-skill-end.py"

NOTICE = ("(plugin.json: v1.0.0 / CHANGELOG: v1.2.0 — "
          "plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性)")


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


def _cache_path(home: Path) -> Path:
    return home / ".cache" / "harness" / "version-snapshot.json"


def _seed(home: Path, plugins: dict) -> None:
    path = _cache_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_refreshed_at": "2026-10-11T00:00:00+00:00",
                                "plugins": plugins}), encoding="utf-8")


def _run(home: Path, payload, *, script: Path = HOOK, extra_env: dict | None = None):
    env = {k: v for k, v in os.environ.items() if k != "HARNESS_SKILLS_NOTIFY"}
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra_env or {})
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(script)], input=stdin, env=env,
                          capture_output=True, text=True, timeout=30)


def _shown(r) -> str:
    """hook の stdout を Claude Code と同じく JSON 1 個として読み、利用者に表示される文字列を返す。"""
    assert r.returncode == 0
    output = json.loads(r.stdout)
    # additionalContext (Claude への文脈) は付けず、利用者への表示だけにする
    assert set(output) == {"systemMessage"}
    return output["systemMessage"]


def _payload(tool_name="Skill", skill="alpha:run-x", session_id="s1"):
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool_name,
               "tool_input": {"skill": skill}}
    if session_id is not None:
        payload["session_id"] = session_id
    return payload


@pytest.fixture
def outdated(home):
    _seed(home, {"alpha": {"installed": "1.0.0", "latest": "1.2.0"}})
    return home


# ===================== IN2: filter =====================

def test_skill_tool_shows_notice_as_system_message(outdated):
    r = _run(outdated, _payload())
    assert _shown(r) == f"alpha: {NOTICE}"
    assert r.stdout.count("\n") == 1  # JSON 1 個を 1 行で出す


@pytest.mark.parametrize("installed,latest,expected", [
    ("1.0.0", "1.2.0", NOTICE),
    ("1.4.45", "1.2.0", "(plugin.json: v1.4.45 / CHANGELOG: v1.2.0 — "
                        "CHANGELOG が plugin.json の version より古い。CHANGELOG の節の足し忘れの可能性)"),
    ("dev", "1.2.0", "(plugin.json: dev / CHANGELOG: v1.2.0 — 版を比べられない)"),
])
def test_every_notice_kind_reaches_system_message(home, installed, latest, expected):
    # 3 種 (manifest-behind / changelog-behind / not-comparable) がどれも hook を通って表示される
    _seed(home, {"alpha": {"installed": installed, "latest": latest}})
    assert _shown(_run(home, _payload())) == f"alpha: {expected}"


def test_in_sync_prints_nothing(home):
    # 通知が無いときは空の JSON も出さない
    _seed(home, {"alpha": {"installed": "1.2.0", "latest": "v1.2.0"}})
    r = _run(home, _payload())
    assert r.returncode == 0
    assert r.stdout == ""


@pytest.mark.parametrize("tool_name", ["Read", "Bash", "Edit"])
def test_non_skill_tools_get_no_notice(outdated, tool_name):
    r = _run(outdated, _payload(tool_name=tool_name))
    assert r.returncode == 0
    assert r.stdout == ""
    # 通知していないので通知済みの記録も残らない
    assert "notified" not in json.loads(_cache_path(outdated).read_text(encoding="utf-8"))


def test_skill_without_plugin_prefix_is_noop(outdated):
    r = _run(outdated, _payload(skill="run-x"))
    assert r.returncode == 0
    assert r.stdout == ""


def test_public_entry_point_delegates_to_hook(outdated):
    # hooks/hooks.json は hooks/notify-skill-end.py を起動する。委譲後も同じ挙動になる
    r = _run(outdated, _payload(), script=ENTRY)
    assert _shown(r) == f"alpha: {NOTICE}"


# ===================== IN2: 1 セッション 1 回 =====================

def test_same_session_same_plugin_notifies_once(outdated):
    first = _run(outdated, _payload(session_id="s1"))
    second = _run(outdated, _payload(skill="alpha:run-y", session_id="s1"))
    assert _shown(first) == f"alpha: {NOTICE}"
    assert second.returncode == 0
    assert second.stdout == ""
    record = json.loads(_cache_path(outdated).read_text(encoding="utf-8"))["notified"]["alpha"]
    assert record["session_id"] == "s1"
    assert record["last_notified_at"]


def test_new_session_notifies_again(outdated):
    _run(outdated, _payload(session_id="s1"))
    r = _run(outdated, _payload(session_id="s2"))
    assert _shown(r) == f"alpha: {NOTICE}"


def test_dedup_is_per_plugin(home):
    _seed(home, {"alpha": {"installed": "1.0.0", "latest": "1.2.0"},
                 "beta": {"installed": "2.0.0", "latest": "2.1.0"}})
    _run(home, _payload(skill="alpha:run-x", session_id="s1"))
    r = _run(home, _payload(skill="beta:run-x", session_id="s1"))
    assert _shown(r) == ("beta: (plugin.json: v2.0.0 / CHANGELOG: v2.1.0 — "
                         "plugin.json の version が CHANGELOG より古い。version の上げ忘れの可能性)")


def test_payload_without_session_id_is_not_deduplicated(outdated):
    # session を特定できないときは抑止しない (通知を黙って失わない側へ倒す)
    for _ in range(2):
        r = _run(outdated, _payload(session_id=None))
        assert _shown(r) == f"alpha: {NOTICE}"


# ===================== graceful degradation =====================

@pytest.mark.parametrize("stdin", ["", "   ", "{not json", "[]"])
def test_bad_stdin_is_noop_exit0(outdated, stdin):
    r = _run(outdated, stdin)
    assert r.returncode == 0
    assert r.stdout == ""


def test_no_cache_is_noop(home):
    r = _run(home, _payload())
    assert r.returncode == 0
    assert r.stdout == ""


def test_suppressed_by_env(outdated):
    r = _run(outdated, _payload(), extra_env={"HARNESS_SKILLS_NOTIFY": "off"})
    assert r.returncode == 0
    assert r.stdout == ""

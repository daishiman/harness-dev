"""Codex実走で、利用者が保存した2hookの信頼だけを限定継承する境界。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = (Path(__file__).resolve().parents[1] / "plugins/harness-creator/skills/"
          "run-skill-live-trial/scripts/manage-codex-live-trial.py")


def load():
    spec = importlib.util.spec_from_file_location("native_hook_trust_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def trusted(tmp_path, monkeypatch):
    mod = load()
    fx = tmp_path / "fixture"
    hooks = fx / ".codex/hooks.json"
    hooks.parent.mkdir(parents=True)
    control = tmp_path / "private"
    control.mkdir()
    defs, rows = {}, []
    for event, suffix, digest in (("UserPromptSubmit", "user_prompt_submit", "1" * 64),
                                  ("PreToolUse", "pre_tool_use", "2" * 64)):
        command = f"python3 /private/pinned-hook.py {event}"
        defs[event] = [{"hooks": [{"type": "command", "command": command}]}]
        rows.append({"key": f"{hooks}:{suffix}:0:0", "sourcePath": str(hooks),
                     "currentHash": "sha256:" + digest, "trustStatus": "trusted",
                     "handlerType": "command", "command": command, "async": False,
                     "enabled": True})
    hooks.write_text(json.dumps({"hooks": defs}))
    inspection = control / "native-list.json"
    inspection.write_text(json.dumps({"hooks_list": {"data": [{"cwd": str(fx), "hooks": rows}]}}))
    user = control / "test-user-config.toml"
    user.write_text("model = 'untouched-user-model'\n"
                    f"[projects.{json.dumps(str(fx))}]\ntrust_level = 'trusted'\n" +
                    "\n".join(f"[hooks.state.{json.dumps(row['key'])}]\n"
                              f"trusted_hash = {json.dumps(row['currentHash'])}\n" for row in rows))
    monkeypatch.setattr(mod, "_codex_user_config", lambda: user)
    cfg = {"repo_root": str(fx), "workdir": str(tmp_path / "public"),
           "external_confirmation_fixture": {"declared": True},
           "native_hook_trust": {"hooks_file": str(hooks), "hooks_sha256": sha(hooks),
                                 "native_list_file": str(inspection), "native_list_sha256": sha(inspection)}}
    return mod, cfg, hooks, inspection, user


def test_reapplies_only_persisted_exact_native_trust_without_writes(trusted):
    mod, cfg, hooks, inspection, user = trusted
    before = {p: p.read_bytes() for p in (hooks, inspection, user)}
    argv = mod.native_hook_trust_argv(cfg)
    assert len(argv) == 8
    assert argv[1] == "features.hooks=true"
    assert sum("trusted_hash=" in arg for arg in argv) == 2
    assert sum("trust_level=" in arg for arg in argv) == 1
    assert not any("dangerously" in arg or "untouched-user-model" in arg for arg in argv)
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize("kind", ["untrusted", "hash-mismatch", "project-untrusted",
                                  "native-drift", "wrong-definition", "writable-inspection"])
def test_rejects_incomplete_or_changed_trust(trusted, kind):
    mod, cfg, hooks, inspection, user = trusted
    if kind == "untrusted":
        doc = json.loads(inspection.read_text())
        doc["hooks_list"]["data"][0]["hooks"][0]["trustStatus"] = "untrusted"
        inspection.write_text(json.dumps(doc))
        cfg["native_hook_trust"]["native_list_sha256"] = sha(inspection)
    elif kind == "hash-mismatch":
        user.write_text(user.read_text().replace("sha256:" + "1" * 64, "sha256:" + "3" * 64))
    elif kind == "project-untrusted":
        user.write_text(user.read_text().replace("trust_level = 'trusted'", "trust_level = 'untrusted'"))
    elif kind == "native-drift":
        inspection.write_text(inspection.read_text() + "\n")
    elif kind == "wrong-definition":
        hooks.write_text(hooks.read_text() + "\n")
    else:
        mutable = Path(cfg["repo_root"]) / "inspection.json"
        mutable.write_bytes(inspection.read_bytes())
        cfg["native_hook_trust"]["native_list_file"] = str(mutable)
    with pytest.raises(ValueError):
        mod.native_hook_trust_argv(cfg)


def test_external_fixture_requires_trust_and_other_trials_do_not():
    mod = load()
    assert mod.native_hook_trust_argv({}) == []
    with pytest.raises(ValueError, match="persisted"):
        mod.native_hook_trust_argv({"external_confirmation_fixture": {}})
    with pytest.raises(ValueError, match="limited"):
        mod.native_hook_trust_argv({"native_hook_trust": {}})

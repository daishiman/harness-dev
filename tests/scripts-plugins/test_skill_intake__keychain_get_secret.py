"""Genuine functional tests for plugins/skill-intake/scripts/keychain_get_secret.py.

The script's sole external side effect is invoking `/usr/bin/security` (macOS
Keychain) via subprocess.run. Every test below either:
  - exercises pure helpers (mask_token, KeychainError) with real inputs, or
  - drives get_secret() with subprocess.run / sys.platform monkeypatched so NO
    real keychain lookup occurs, or
  - resolves _default_service / _default_account through the env-override path
    (which short-circuits before notion_config is consulted), or
  - runs main() via a child process with INTAKE_* env / args that hit only the
    config-resolution + platform-guard error branches (no keychain success path,
    which is host-dependent and would be non-deterministic).

No network, no real keychain access, repo untouched (tmp_path / env only).
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "keychain_get_secret.py"


# keychain_get_secret.py は同 dir の tenant_runtime を bare-import する。
# 他テストの sys.path 挿入に依存すると単独実行で collection が落ちるため自立させる。
sys.path.insert(0, str(SCRIPT.parent))


def _load():
    spec = importlib.util.spec_from_file_location("keychain_get_secret_under_test", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mod = _load()


@pytest.fixture(autouse=True)
def _tenant_ctx(xlocal_tenant_env):
    """全テストを xlocal tenant 文脈で実行する (CI には ambient tenant が無い)。"""


# ── mask_token (pure) ─────────────────────────────────────────────────────
def test_mask_token_empty_returns_placeholder():
    assert mod.mask_token("") == "(empty)"
    assert mod.mask_token(None) == "(empty)"


def test_mask_token_shows_prefix_and_length():
    out = mod.mask_token("secret_abcdef1234")
    assert out == "secr... (len=17)"
    # never leaks the full token
    assert "abcdef1234" not in out


def test_mask_token_short_token():
    # fewer than 4 chars: prefix is the whole (short) token, length is correct
    assert mod.mask_token("ab") == "ab... (len=2)"


# ── KeychainError (pure) ──────────────────────────────────────────────────
def test_keychain_error_default_exit_code():
    e = mod.KeychainError("boom")
    assert e.exit_code == 44
    assert str(e) == "boom"


def test_keychain_error_custom_exit_code():
    e = mod.KeychainError("nope", exit_code=2)
    assert e.exit_code == 2


# ── _default_service / _default_account env override (no notion_config) ────
def test_default_service_env_override(monkeypatch):
    monkeypatch.setenv("INTAKE_KEYCHAIN_SERVICE", "notion-api-key.myrepo")
    # env short-circuits before _load_config_if_available is reached
    assert mod._default_service() == "notion-api-key.myrepo"


def test_default_account_env_override(monkeypatch):
    monkeypatch.setenv("INTAKE_KEYCHAIN_ACCOUNT", "myrepo-acct")
    assert mod._default_account() == "myrepo-acct"


def test_default_service_falls_back_to_constant_when_no_config(monkeypatch):
    # ensure env not set, and force config loader to yield nothing
    monkeypatch.delenv("INTAKE_KEYCHAIN_SERVICE", raising=False)
    monkeypatch.setattr(mod, "_load_config_if_available", lambda: None)
    assert mod.DEFAULT_SERVICE == ""
    assert mod._default_service() == "notion-api-key.xlocal"


def test_default_account_falls_back_to_constant_when_no_config(monkeypatch):
    monkeypatch.delenv("INTAKE_KEYCHAIN_ACCOUNT", raising=False)
    monkeypatch.setattr(mod, "_load_config_if_available", lambda: None)
    assert mod.DEFAULT_ACCOUNT == ""
    assert mod._default_account() == "xlocal"


def test_default_service_uses_config_value(monkeypatch):
    monkeypatch.delenv("INTAKE_KEYCHAIN_SERVICE", raising=False)
    monkeypatch.setattr(
        mod, "_load_config_if_available",
        lambda: {"keychain_service": "notion-api-key.from-config"},
    )
    assert mod._default_service() == "notion-api-key.from-config"


def test_default_account_uses_config_value(monkeypatch):
    monkeypatch.delenv("INTAKE_KEYCHAIN_ACCOUNT", raising=False)
    monkeypatch.setattr(
        mod, "_load_config_if_available",
        lambda: {"keychain_account": "acct-from-config"},
    )
    assert mod._default_account() == "acct-from-config"


# ── get_secret (subprocess + platform monkeypatched, never real keychain) ─
def _fake_completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["security"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_get_secret_non_darwin_raises(monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "linux")
    with pytest.raises(mod.KeychainError) as ei:
        mod.get_secret(service="s", account="a")
    assert "unsupported platform" in str(ei.value)


def test_get_secret_success(monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    captured = {}

    def fake_run(cmd, capture_output, text):
        captured["cmd"] = cmd
        return _fake_completed(returncode=0, stdout="tok_value\n")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    token = mod.get_secret(service="svc1", account="acct1")
    assert token == "tok_value"
    # confirm the exact security invocation the script builds
    assert captured["cmd"] == [
        "/usr/bin/security", "find-generic-password",
        "-s", "svc1", "-a", "acct1", "-w",
    ]


def test_get_secret_lookup_failure_raises_with_stderr(monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    monkeypatch.setattr(
        mod.subprocess, "run",
        lambda *a, **k: _fake_completed(returncode=44, stderr="item not found\n"),
    )
    with pytest.raises(mod.KeychainError) as ei:
        mod.get_secret(service="svc", account="acct")
    msg = str(ei.value)
    assert "Keychain lookup failed" in msg
    assert "svc" in msg and "acct" in msg
    assert "item not found" in msg


def test_get_secret_empty_token_raises(monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    monkeypatch.setattr(
        mod.subprocess, "run",
        lambda *a, **k: _fake_completed(returncode=0, stdout="\n"),
    )
    with pytest.raises(mod.KeychainError) as ei:
        mod.get_secret(service="svc", account="acct")
    assert "empty token" in str(ei.value)


def test_get_secret_uses_explicit_args_over_defaults(monkeypatch):
    # if service/account are passed, _default_* must not be consulted
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    monkeypatch.setattr(
        mod, "_default_service",
        lambda: (_ for _ in ()).throw(AssertionError("default should not be used")),
    )
    monkeypatch.setattr(
        mod, "_default_account",
        lambda: (_ for _ in ()).throw(AssertionError("default should not be used")),
    )
    monkeypatch.setattr(
        mod.subprocess, "run",
        lambda *a, **k: _fake_completed(returncode=0, stdout="abc"),
    )
    assert mod.get_secret(service="x", account="y") == "abc"


# ── main() via child process (deterministic error/help paths only) ────────
def _run(*args, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT, text=True, capture_output=True, env=env,
    )


def test_cli_help_exits_zero():
    proc = _run("--help")
    assert proc.returncode == 0
    assert "--service" in proc.stdout
    assert "--check" in proc.stdout


@pytest.mark.skipif(sys.platform == "darwin", reason="non-darwin platform guard path")
def test_cli_non_darwin_returns_keychain_exit_code():
    # On non-mac CI the platform guard fires -> KeychainError default exit 44.
    proc = _run(
        "--service", "notion-api-key.unit-test", "--account", "unit-test",
        env_extra={
            "INTAKE_KEYCHAIN_SERVICE": "notion-api-key.unit-test",
            "INTAKE_KEYCHAIN_ACCOUNT": "unit-test",
        },
    )
    assert proc.returncode == 44
    assert "unsupported platform" in proc.stderr


def test_cli_lookup_failure_returns_exit_44():
    # Use a service/account that cannot exist so the keychain lookup fails
    # deterministically (mac) OR the platform guard fires (non-mac); both map
    # to KeychainError.exit_code == 44. No real secret is ever read.
    proc = _run(
        "--service", "no-such-service.xlskills-unit-test-DO-NOT-CREATE",
        "--account", "no-such-account-xlskills-unit-test",
        "--check",
    )
    assert proc.returncode == 44
    assert "[keychain_get_secret]" in proc.stderr

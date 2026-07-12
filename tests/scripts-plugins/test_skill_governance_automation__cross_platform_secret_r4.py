"""Genuine functional tests for
plugins/skill-governance-automation/scripts/cross_platform_secret.py.

カバレッジ方針:
- detect_os の OS マッピング、env / linux(xdg) / windows(base64) / mac(keychain) の
  get / set 経路、get_secret のフォールバック優先 (env > os-native > failure)、probe、
  main の各 argv 分岐 (--probe / --get / --set / --value 欠落 / no-op help) を網羅。
- **実 keychain / 実 security CLI / 実  HOME は叩かない**:
    - mac 経路は `subprocess.run` を monkeypatch で stub (returncode 制御)。
    - OS 判定は `platform.system` (detect_os 経由) を monkeypatch で固定。
    - linux/windows のファイル backend は `XDG_CONFIG_HOME` / `APPDATA` / `HOME` を
      tmp_path に向けて repo・実ユーザー環境を汚さない。

ファイル名は他 dir の secret 系と衝突しないよう `_r4` を付して新規作成。
"""
import base64
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "plugins" / "skill-governance-automation" / "scripts"
          / "cross_platform_secret.py")

_SPEC = importlib.util.spec_from_file_location("cross_platform_secret_s4", SCRIPT)
CPS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CPS)


def _force_os(monkeypatch, name):
    """platform.system() を固定し detect_os を所望の OS に向ける。"""
    sysname = {"mac": "Darwin", "linux": "Linux", "windows": "Windows",
               "unknown": "SunOS"}[name]
    monkeypatch.setattr(CPS.platform, "system", lambda: sysname)


# ===================== detect_os =====================

def test_detect_os_all(monkeypatch):
    monkeypatch.setattr(CPS.platform, "system", lambda: "Darwin")
    assert CPS.detect_os() == "mac"
    monkeypatch.setattr(CPS.platform, "system", lambda: "Linux")
    assert CPS.detect_os() == "linux"
    monkeypatch.setattr(CPS.platform, "system", lambda: "Windows")
    assert CPS.detect_os() == "windows"
    monkeypatch.setattr(CPS.platform, "system", lambda: "Plan9")
    assert CPS.detect_os() == "unknown"


# ===================== _env_lookup =====================

def test_env_lookup_hit(monkeypatch):
    monkeypatch.setenv("HARNESS_SECRET_XLOCAL_MY_KEY", "v1")
    assert CPS._env_lookup("my-key") == "v1"   # hyphen→_ / upper


def test_env_lookup_miss(monkeypatch):
    monkeypatch.delenv("HARNESS_SECRET_XLOCAL_NOPE", raising=False)
    assert CPS._env_lookup("nope") is None


# ===================== _xdg_path =====================

def test_xdg_path_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = CPS._xdg_path("k")
    assert p == tmp_path / "harness" / "xlocal" / "secrets.json"


def test_xdg_path_default_home(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(CPS.Path, "home", staticmethod(lambda: tmp_path))
    p = CPS._xdg_path("k")
    assert p == tmp_path / ".config" / "harness" / "xlocal" / "secrets.json"


# ===================== linux get/set =====================

def test_linux_set_then_get_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert CPS._linux_set("api-key", "secret-val") is True
    assert CPS._linux_get("api-key") == "secret-val"
    # chmod 600 が掛かっている
    p = CPS._xdg_path("api-key")
    mode = stat.S_IMODE(p.stat().st_mode)
    assert mode == 0o600


def test_linux_get_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert CPS._linux_get("absent") is None


def test_linux_get_corrupt_json(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = CPS._xdg_path("k")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{broken", encoding="utf-8")
    assert CPS._linux_get("k") is None


def test_linux_set_appends_to_existing(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    CPS._linux_set("a", "1")
    CPS._linux_set("b", "2")
    assert CPS._linux_get("a") == "1"
    assert CPS._linux_get("b") == "2"


def test_linux_set_overwrites_corrupt(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = CPS._xdg_path("k")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{corrupt", encoding="utf-8")
    # 壊れた既存ファイルでも set は新規 dict で書き直す
    assert CPS._linux_set("k", "v") is True
    assert CPS._linux_get("k") == "v"


# ===================== windows get/set =====================

def test_windows_set_then_get_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert CPS._windows_set("tok", "wv") is True
    assert CPS._windows_get("tok") == "wv"
    # 保存はそのまま base64(JSON)
    storage = tmp_path / "harness" / "xlocal" / "secrets.bin"
    decoded = json.loads(base64.b64decode(storage.read_text(encoding="utf-8")).decode("utf-8"))
    assert decoded["tok"] == "wv"


def test_windows_get_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert CPS._windows_get("absent") is None


def test_windows_get_corrupt(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    storage = tmp_path / "harness" / "xlocal" / "secrets.bin"
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_text("not-base64!!!", encoding="utf-8")
    assert CPS._windows_get("k") is None


def test_windows_set_appends(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    CPS._windows_set("a", "1")
    CPS._windows_set("b", "2")
    assert CPS._windows_get("a") == "1"
    assert CPS._windows_get("b") == "2"


def test_windows_set_overwrites_corrupt(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    storage = tmp_path / "harness" / "xlocal" / "secrets.bin"
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_text("@@@not-base64", encoding="utf-8")
    assert CPS._windows_set("k", "v") is True
    assert CPS._windows_get("k") == "v"


def test_windows_default_home_when_no_appdata(monkeypatch, tmp_path):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(CPS.Path, "home", staticmethod(lambda: tmp_path))
    assert CPS._windows_set("k", "v") is True
    assert CPS._windows_get("k") == "v"


# ===================== mac get (subprocess stub) =====================

class _Proc:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


def test_mac_get_success(monkeypatch):
    monkeypatch.setattr(CPS.subprocess, "run",
                        lambda *a, **k: _Proc(returncode=0, stdout="kc-secret\n"))
    assert CPS._mac_get("k") == "kc-secret"


def test_mac_get_not_found_returncode(monkeypatch):
    monkeypatch.setattr(CPS.subprocess, "run",
                        lambda *a, **k: _Proc(returncode=44, stdout=""))
    assert CPS._mac_get("k") is None


def test_mac_get_subprocess_oserror(monkeypatch):
    def boom(*a, **k):
        raise OSError("security not found")
    monkeypatch.setattr(CPS.subprocess, "run", boom)
    assert CPS._mac_get("k") is None


def test_mac_get_timeout(monkeypatch):
    def boom(*a, **k):
        raise CPS.subprocess.TimeoutExpired(cmd="security", timeout=10)
    monkeypatch.setattr(CPS.subprocess, "run", boom)
    assert CPS._mac_get("k") is None


def test_mac_get_command_shape(monkeypatch):
    captured = {}

    def fake_run(cmd, **k):
        captured["cmd"] = cmd
        return _Proc(returncode=0, stdout="s")

    monkeypatch.setenv("USER", "tester")
    monkeypatch.setattr(CPS.subprocess, "run", fake_run)
    CPS._mac_get("mykey")
    cmd = captured["cmd"]
    assert cmd[0] == "security"
    assert "find-generic-password" in cmd
    assert "mykey.xlocal" in cmd
    assert "xlocal" in cmd
    assert "tester" not in cmd


# ===================== get_secret フォールバック優先 =====================

def test_get_secret_env_wins(monkeypatch):
    monkeypatch.setenv("HARNESS_SECRET_XLOCAL_K", "envval")
    _force_os(monkeypatch, "mac")
    # mac backend が呼ばれる前に env で返るはず → subprocess は呼ばれない
    monkeypatch.setattr(CPS.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not call")))
    r = CPS.get_secret("k")
    assert r == {"status": "ok", "os": "mac", "backend": "env", "value": "envval", "errors": []}


def test_get_secret_mac_keychain(monkeypatch):
    monkeypatch.delenv("HARNESS_SECRET_XLOCAL_K", raising=False)
    _force_os(monkeypatch, "mac")
    monkeypatch.setattr(CPS, "_mac_get", lambda k: "kc")
    r = CPS.get_secret("k")
    assert r["status"] == "ok" and r["backend"] == "keychain" and r["value"] == "kc"


def test_get_secret_mac_failure(monkeypatch):
    monkeypatch.delenv("HARNESS_SECRET_XLOCAL_K", raising=False)
    _force_os(monkeypatch, "mac")
    monkeypatch.setattr(CPS, "_mac_get", lambda k: None)
    r = CPS.get_secret("k")
    assert r["status"] == "failure"
    assert "mac keychain lookup failed" in r["errors"]


def test_get_secret_linux(monkeypatch, tmp_path):
    monkeypatch.delenv("HARNESS_SECRET_XLOCAL_K", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _force_os(monkeypatch, "linux")
    CPS._linux_set("k", "lv")
    r = CPS.get_secret("k")
    assert r["status"] == "ok" and r["backend"] == "xdg" and r["value"] == "lv"


def test_get_secret_linux_failure(monkeypatch, tmp_path):
    monkeypatch.delenv("HARNESS_SECRET_XLOCAL_K", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _force_os(monkeypatch, "linux")
    r = CPS.get_secret("k")
    assert r["status"] == "failure"
    assert "linux xdg lookup failed" in r["errors"]


def test_get_secret_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("HARNESS_SECRET_XLOCAL_K", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    _force_os(monkeypatch, "windows")
    CPS._windows_set("k", "wv")
    r = CPS.get_secret("k")
    assert r["status"] == "ok" and r["backend"] == "base64-file" and r["value"] == "wv"


def test_get_secret_windows_failure(monkeypatch, tmp_path):
    monkeypatch.delenv("HARNESS_SECRET_XLOCAL_K", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    _force_os(monkeypatch, "windows")
    r = CPS.get_secret("k")
    assert r["status"] == "failure"
    assert "windows base64-file lookup failed" in r["errors"]


def test_get_secret_unknown_os(monkeypatch):
    monkeypatch.delenv("HARNESS_SECRET_XLOCAL_K", raising=False)
    _force_os(monkeypatch, "unknown")
    r = CPS.get_secret("k")
    assert r["status"] == "failure" and r["os"] == "unknown"
    assert any("OS判定失敗" in e for e in r["errors"])


# ===================== set_secret =====================

def test_set_secret_mac_success(monkeypatch):
    _force_os(monkeypatch, "mac")
    monkeypatch.setattr(CPS.subprocess, "run", lambda *a, **k: _Proc(returncode=0))
    r = CPS.set_secret("k", "v")
    assert r == {"status": "ok", "os": "mac", "backend": "keychain"}


def test_set_secret_mac_nonzero(monkeypatch):
    _force_os(monkeypatch, "mac")
    monkeypatch.setattr(CPS.subprocess, "run", lambda *a, **k: _Proc(returncode=1))
    r = CPS.set_secret("k", "v")
    assert r["status"] == "failure"
    assert "security add-generic-password failed" in r["errors"]


def test_set_secret_mac_exception(monkeypatch):
    _force_os(monkeypatch, "mac")

    def boom(*a, **k):
        raise OSError("no security binary")

    monkeypatch.setattr(CPS.subprocess, "run", boom)
    r = CPS.set_secret("k", "v")
    assert r["status"] == "failure"
    assert "no security binary" in r["errors"][0]


def test_set_secret_mac_timeout(monkeypatch):
    _force_os(monkeypatch, "mac")

    def boom(*a, **k):
        raise CPS.subprocess.TimeoutExpired(cmd="security", timeout=10)

    monkeypatch.setattr(CPS.subprocess, "run", boom)
    r = CPS.set_secret("k", "v")
    assert r["status"] == "failure"


def test_set_secret_linux(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _force_os(monkeypatch, "linux")
    r = CPS.set_secret("k", "v")
    assert r == {"status": "ok", "os": "linux", "backend": "xdg"}
    assert CPS._linux_get("k") == "v"


def test_set_secret_windows(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    _force_os(monkeypatch, "windows")
    r = CPS.set_secret("k", "v")
    assert r == {"status": "ok", "os": "windows", "backend": "base64-file"}
    assert CPS._windows_get("k") == "v"


def test_set_secret_unknown(monkeypatch):
    _force_os(monkeypatch, "unknown")
    r = CPS.set_secret("k", "v")
    assert r["status"] == "failure" and r["backend"] == "none"
    assert any("OS判定失敗" in e for e in r["errors"])


# ===================== probe =====================

def test_probe(monkeypatch, tmp_path):
    _force_os(monkeypatch, "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = CPS.probe()
    assert p["os"] == "linux"
    assert p["xdg_config_home"] == str(tmp_path)
    assert set(p["supported_backends"]) == {"mac", "linux", "windows", "unknown"}
    assert p["fallback_priority"] == ["env", "os-native", "failure"]
    assert "." in p["python"]


# ===================== main argv 分岐 =====================

def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["cross_platform_secret.py", *args])


def test_main_probe(monkeypatch, capsys):
    _argv(monkeypatch, "--probe")
    assert CPS.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert "supported_backends" in out


def test_main_get_ok(monkeypatch, capsys):
    monkeypatch.setenv("HARNESS_SECRET_XLOCAL_K", "v")
    _argv(monkeypatch, "--get", "k")
    assert CPS.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok" and out["value"] == "v"


def test_main_get_failure_exit1(monkeypatch, capsys):
    monkeypatch.delenv("HARNESS_SECRET_XLOCAL_MISS", raising=False)
    _force_os(monkeypatch, "unknown")
    _argv(monkeypatch, "--get", "miss")
    assert CPS.main() == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "failure"


def test_main_set_ok(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _force_os(monkeypatch, "linux")
    _argv(monkeypatch, "--set", "k", "--value", "v")
    assert CPS.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert CPS._linux_get("k") == "v"


def test_main_set_missing_value_exit2(monkeypatch, capsys):
    _argv(monkeypatch, "--set", "k")
    assert CPS.main() == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "failure"
    assert "--value required" in out["errors"][0]


def test_main_set_failure_exit1(monkeypatch, capsys):
    _force_os(monkeypatch, "unknown")
    _argv(monkeypatch, "--set", "k", "--value", "v")
    assert CPS.main() == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "failure"


def test_main_no_action_prints_help_exit2(monkeypatch, capsys):
    _argv(monkeypatch)
    assert CPS.main() == 2
    # argparse help が stdout に出る
    assert "usage" in capsys.readouterr().out.lower()

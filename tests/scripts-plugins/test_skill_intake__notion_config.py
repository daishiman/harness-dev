"""Genuine functional tests for plugins/skill-intake/scripts/notion_config.py.

外部 I/O (Keychain `security` コマンド) は monkeypatch で遮断し、純関数 / 解決順 /
fail-closed / fail-open 経路を実入力で検証する。tmp_path で repo を汚さない。

検査対象:
  - canonical_notion_id: UUID/compact/URL(query p 優先)/不正入力
  - find_config_path: env 最優先 / env 不在 fail-closed / plugin-root フォールバック
  - load_config: __path__ 付与 / 不在 None
  - get_db_id: env-specific 優先 / config フォールバック
  - get_parent_page_id: env / parent_page.page_id / legacy parent_page_id
  - get_token: env(許可フラグ要) / Keychain(monkeypatch) / 失敗時 None
  - require_or_skip: fail-closed exit2 / allow_skip fail-open
"""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "notion_config.py"


def _load():
    spec = importlib.util.spec_from_file_location("notion_config_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NC = _load()

# Notion 関連 env を必ずクリーンにするフィクスチャ
_ENV_KEYS = [
    "NOTION_CONFIG_PATH",
    "CLAUDE_PLUGIN_ROOT",
    "NOTION_TOKEN",
    "INTAKE_ALLOW_ENV_TOKEN",
    "INTAKE_NOTION_DATABASE_ID",
    "NOTION_DB_SKILL_LIST",
    "NOTION_DB_IMPROVEMENT_REQUEST",
    "INTAKE_NOTION_PARENT_PAGE_ID",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    yield


# --- canonical_notion_id -----------------------------------------------------
def test_canonical_from_hyphenated_uuid():
    u = "36607a0c-d18c-80bf-9eff-c74aa736645c"
    assert NC.canonical_notion_id(u) == u


def test_canonical_from_compact_32hex():
    assert (
        NC.canonical_notion_id("36607a0cd18c80bf9effc74aa736645c")
        == "36607a0c-d18c-80bf-9eff-c74aa736645c"
    )


def test_canonical_from_url_query_p_takes_priority():
    # database view URL: path に view ID, query p に page ID。p を優先する。
    url = (
        "https://app.notion.com/workspace/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "?v=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        "&p=36607a0cd18c80bf9effc74aa736645c"
    )
    assert NC.canonical_notion_id(url) == "36607a0c-d18c-80bf-9eff-c74aa736645c"


def test_canonical_from_path_compact_suffix():
    url = "https://app.notion.com/p/36607a0cd18c80bf9effc74aa736645c"
    assert NC.canonical_notion_id(url) == "36607a0c-d18c-80bf-9eff-c74aa736645c"


def test_canonical_bare_32hex_no_url():
    # path/segment 経由でなく raw が純 32hex の最終フォールバック分岐
    assert (
        NC.canonical_notion_id("ABCDEF0123456789abcdef0123456789")
        == "abcdef01-2345-6789-abcd-ef0123456789"
    )


def test_canonical_invalid_returns_none():
    assert NC.canonical_notion_id("not-an-id") is None
    assert NC.canonical_notion_id("") is None
    assert NC.canonical_notion_id(None) is None


def test_find_config_path_repo_root(tmp_path, monkeypatch):
    # repo-root (marker あり) 直下の .notion-config.json を採用する分岐
    root = tmp_path / "myrepo"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "marketplace.json").write_text("{}", encoding="utf-8")
    cfg = _write_cfg(root / NC.CONFIG_FILENAME)
    found = NC.find_config_path(start=root)
    assert found == cfg


# --- find_config_path resolution order --------------------------------------
def _write_cfg(path: Path, **overrides) -> Path:
    cfg = {
        "keychain_service": "svc",
        "keychain_account": "acct",
        "parent_page": {"page_id": "36607a0c-d18c-80bf-9eff-c74aa736645c"},
        "databases": {
            "skill-list": {"db_id": "DB_SKILL"},
            "hearing-sheet": {"db_id": "DB_HEARING"},
        },
    }
    cfg.update(overrides)
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def test_find_config_path_env_highest_priority(tmp_path, monkeypatch):
    cfg = _write_cfg(tmp_path / "explicit.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.find_config_path() == cfg


def test_find_config_path_env_missing_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(tmp_path / "nope.json"))
    with pytest.raises(FileNotFoundError):
        NC.find_config_path()


def test_find_config_path_plugin_root_fallback(tmp_path, monkeypatch):
    # repo-root marker 不在環境を CLAUDE_PLUGIN_ROOT で再現
    pr = tmp_path / "plugin"
    pr.mkdir()
    cfg = _write_cfg(pr / NC.CONFIG_FILENAME)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    # start を marker の無い tmp ディレクトリにして repo-root 探索を空振りさせる
    found = NC.find_config_path(start=tmp_path)
    assert found == cfg


def test_find_config_path_bundled_fallback(tmp_path, monkeypatch):
    pr = tmp_path / "plugin"
    pr.mkdir()
    cfg = _write_cfg(pr / NC.BUNDLED_CONFIG_FILENAME)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    found = NC.find_config_path(start=tmp_path)
    assert found == cfg


def test_find_config_path_none_when_nothing(tmp_path, monkeypatch):
    pr = tmp_path / "empty_plugin"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    assert NC.find_config_path(start=tmp_path) is None


# --- find_repo_root ----------------------------------------------------------
def test_find_repo_root_requires_marker(tmp_path):
    # .git だけでは採用しない (別 repo の盗み読み防止)
    (tmp_path / ".git").mkdir()
    assert NC.find_repo_root(start=tmp_path) is None
    # marker を足すと採用
    (tmp_path / "marketplace.json").write_text("{}", encoding="utf-8")
    assert NC.find_repo_root(start=tmp_path) == tmp_path.resolve()


# --- load_config -------------------------------------------------------------
def test_load_config_adds_path(tmp_path, monkeypatch):
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    loaded = NC.load_config()
    assert loaded["__path__"] == str(cfg)
    assert loaded["databases"]["skill-list"]["db_id"] == "DB_SKILL"


def test_load_config_none_when_missing(tmp_path, monkeypatch):
    pr = tmp_path / "p"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    assert NC.load_config(start=tmp_path) is None


# --- get_db_id ---------------------------------------------------------------
def test_get_db_id_env_takes_priority(tmp_path, monkeypatch):
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("NOTION_DB_SKILL_LIST", "ENV_OVERRIDE")
    assert NC.get_db_id("skill-list") == "ENV_OVERRIDE"


def test_get_db_id_from_config(tmp_path, monkeypatch):
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.get_db_id("hearing-sheet") == "DB_HEARING"


def test_get_db_id_none_when_no_config(tmp_path, monkeypatch):
    pr = tmp_path / "p"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    assert NC.get_db_id("skill-list", start=tmp_path) is None


# --- get_parent_page_id ------------------------------------------------------
def test_get_parent_page_id_env(monkeypatch):
    monkeypatch.setenv("INTAKE_NOTION_PARENT_PAGE_ID", "36607a0cd18c80bf9effc74aa736645c")
    assert NC.get_parent_page_id() == "36607a0c-d18c-80bf-9eff-c74aa736645c"


def test_get_parent_page_id_from_config(tmp_path, monkeypatch):
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.get_parent_page_id() == "36607a0c-d18c-80bf-9eff-c74aa736645c"


def test_get_parent_page_id_legacy_field(tmp_path, monkeypatch):
    cfg = _write_cfg(
        tmp_path / "c.json",
        parent_page={},
        parent_page_id="36607a0cd18c80bf9effc74aa736645c",
    )
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.get_parent_page_id() == "36607a0c-d18c-80bf-9eff-c74aa736645c"


# --- get_token (Keychain monkeypatched, no real I/O) ------------------------
def test_get_token_env_requires_allow_flag(monkeypatch):
    # 許可フラグ無しでは env NOTION_TOKEN を読まず、Keychain に落ちる
    monkeypatch.setenv("NOTION_TOKEN", "env-secret")
    monkeypatch.setattr(
        NC.subprocess, "check_output",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("no security")),
    )
    assert NC.get_token({}) is None


def test_get_token_env_with_allow_flag(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "env-secret")
    monkeypatch.setenv("INTAKE_ALLOW_ENV_TOKEN", "1")
    assert NC.get_token({}) == "env-secret"


def test_get_token_from_keychain(monkeypatch):
    captured = {}

    def fake_check_output(cmd, *a, **k):
        captured["cmd"] = cmd
        return "  keychain-secret  \n"

    monkeypatch.setattr(NC.subprocess, "check_output", fake_check_output)
    tok = NC.get_token({"keychain_service": "svcX", "keychain_account": "acctX"})
    assert tok == "keychain-secret"
    # service / account が security コマンドへ正しく渡る
    assert "svcX" in captured["cmd"]
    assert "acctX" in captured["cmd"]
    assert "-a" in captured["cmd"]


def test_get_token_keychain_failure_returns_none(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "security")

    monkeypatch.setattr(NC.subprocess, "check_output", boom)
    assert NC.get_token({}) is None


# --- require_or_skip ---------------------------------------------------------
def test_require_or_skip_fail_closed_no_config(tmp_path, monkeypatch, capsys):
    pr = tmp_path / "p"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    monkeypatch.chdir(tmp_path)  # cwd 起点の repo-root 探索も空振りさせる
    with pytest.raises(SystemExit) as ei:
        NC.require_or_skip("hearing-sheet")
    assert ei.value.code == 2
    err = capsys.readouterr().err
    assert "FATAL" in err


def test_require_or_skip_fail_open_with_allow_skip(tmp_path, monkeypatch, capsys):
    pr = tmp_path / "p"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    monkeypatch.chdir(tmp_path)
    cfg, tok = NC.require_or_skip("hearing-sheet", allow_skip=True)
    assert cfg is None and tok is None
    assert "allow-skip" in capsys.readouterr().err


def test_require_or_skip_happy_path(tmp_path, monkeypatch):
    cfg_file = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr(NC, "get_token", lambda cfg=None: "tok123")
    cfg, tok = NC.require_or_skip("hearing-sheet")
    assert tok == "tok123"
    assert cfg["__path__"] == str(cfg_file)


def test_require_or_skip_missing_db_fails_closed(tmp_path, monkeypatch):
    # token はあるが db_id が無い key を要求 → exit 2
    cfg_file = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr(NC, "get_token", lambda cfg=None: "tok123")
    with pytest.raises(SystemExit) as ei:
        NC.require_or_skip("improvement-request")  # config に無い
    assert ei.value.code == 2


# --- warn_missing ------------------------------------------------------------
def test_warn_missing_writes_guidance():
    import io

    buf = io.StringIO()
    NC.warn_missing(stream=buf)
    out = buf.getvalue()
    assert NC.CONFIG_FILENAME in out
    assert "NOTION_CONFIG_PATH" in out


# --- __main__ via subprocess (no config -> exit 0, warn) --------------------
def test_main_no_config_exits_zero(tmp_path):
    import os
    import sys

    env = dict(os.environ)
    for k in _ENV_KEYS:
        env.pop(k, None)
    env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)  # 空の plugin-root
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "WARN" in r.stderr


def test_main_prints_config_json(tmp_path):
    import os
    import sys

    cfg_file = _write_cfg(tmp_path / "c.json")
    env = dict(os.environ)
    for k in _ENV_KEYS:
        env.pop(k, None)
    env["NOTION_CONFIG_PATH"] = str(cfg_file)
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "loaded from" in r.stdout
    # __path__ は出力 JSON から除外される
    payload = r.stdout.split("# loaded from")[0]
    assert "__path__" not in payload
    assert "databases" in payload

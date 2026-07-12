"""Genuine functional tests for plugins/harness-creator/scripts/notion_config.py.

harness-creator に vendoring 実体として同梱された per-repo Notion config loader。
skill-intake 側の同名スクリプトとは別ファイル (vendored copy) なので独立にカバーする。

カバレッジ方針:
- 純関数 (canonical_notion_id の URL/ID 正規化各分岐, find_repo_root の marker ガード,
  plugin_root の env 優先, find_config_path の 5 段解決順, load_config, get_db_id,
  get_parent_page_id, warn_missing) を **in-process** で実値検証する。
- network / Notion API / keychain (security CLI) / secret は一切叩かない:
    - `get_token` の Keychain 経路は `subprocess.check_output` を monkeypatch で stub。
    - env 経路 (INTAKE_ALLOW_ENV_TOKEN / NOTION_TOKEN) は monkeypatch.setenv/delenv。
    - config 解決はすべて tmp_path 配下に置き、`NOTION_CONFIG_PATH` /
      `CLAUDE_PLUGIN_ROOT` を tmp_path に向けて repo・実環境を汚さない。
- require_or_skip の fail-closed (sys.exit(2)) / fail-open (allow_skip) 両系を網羅。

config 探索が repo-root marker を上向き走査するため、テストは必ず
`NOTION_CONFIG_PATH` か `CLAUDE_PLUGIN_ROOT` を明示し、かつ `find_repo_root` の
start を tmp_path に固定して実 repo の .notion-config.json に到達しないようにする。

ファイル名は他 dir の notion_config 系と衝突しないよう `_r4` を付して新規作成。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "harness-creator" / "scripts" / "notion_config.py"

# notion_config.py は同 dir の tenant_runtime を bare-import する。
# 他テストの sys.path 挿入に依存すると単独実行で collection が落ちるため自立させる。
sys.path.insert(0, str(SCRIPT.parent))

_SPEC = importlib.util.spec_from_file_location("notion_config_sc_s4", SCRIPT)
NC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(NC)

# 実値 UUID と compact / URL 表現
UUID = "36607a0c-d18c-80bf-9eff-c74aa736645c"
COMPACT = "36607a0cd18c80bf9effc74aa736645c"


@pytest.fixture(autouse=True)
def _tenant_ctx(xlocal_tenant_env):
    """全テストを xlocal tenant 文脈で実行する (CI には ambient tenant が無い)。"""


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """各テストで env 由来の解決経路を確実に無効化し、明示分のみ効かせる。"""
    for k in (
        "NOTION_CONFIG_PATH", "CLAUDE_PLUGIN_ROOT", "NOTION_TOKEN",
        "INTAKE_ALLOW_ENV_TOKEN", "INTAKE_NOTION_DATABASE_ID",
        "NOTION_DB_SKILL_LIST", "NOTION_DB_IMPROVEMENT_REQUEST",
        "INTAKE_NOTION_PARENT_PAGE_ID",
    ):
        monkeypatch.delenv(k, raising=False)


def _write_cfg(path: Path, **over):
    cfg = {
        "keychain_service": "svc",
        "keychain_account": "acct",
        "parent_page": {"page_id": UUID},
        "databases": {
            "skill-list": {"db_id": "db-skill"},
            "hearing-sheet": {"db_id": "db-hearing"},
            "improvement-request": {"db_id": "db-improve"},
        },
    }
    cfg.update(over)
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


# ===================== canonical_notion_id =====================

def test_canonical_none_and_empty():
    assert NC.canonical_notion_id(None) is None
    assert NC.canonical_notion_id("") is None


def test_canonical_already_uuid_in_segment():
    assert NC.canonical_notion_id(UUID) == UUID


def test_canonical_compact_32_hex():
    assert NC.canonical_notion_id(COMPACT) == UUID


def test_canonical_url_path_segment_compact():
    # /p/<compact> path から復元
    url = f"https://app.notion.com/p/{COMPACT}"
    assert NC.canonical_notion_id(url) == UUID


def test_canonical_url_path_segment_uuid():
    url = f"https://www.notion.so/workspace/Title-{UUID}"
    assert NC.canonical_notion_id(url) == UUID


def test_canonical_query_p_takes_priority_over_path():
    # database view URL: path に view id、query p に page id → p を優先
    other_compact = "11111111111111111111111111111111"
    url = f"https://app.notion.com/{other_compact}?v=abc&p={COMPACT}"
    assert NC.canonical_notion_id(url) == UUID


def test_canonical_query_page_id_key():
    url = f"https://app.notion.com/x?page_id={COMPACT}"
    assert NC.canonical_notion_id(url) == UUID


def test_canonical_query_p_invalid_falls_to_path():
    # query p が 32hex でなければ path セグメントへフォールバック
    url = f"https://app.notion.com/p/{COMPACT}?p=tooshort"
    assert NC.canonical_notion_id(url) == UUID


def test_canonical_trailing_dash_token():
    # "Some-Title-<compact>" のように末尾トークンが 32hex
    assert NC.canonical_notion_id(f"Title-Words-{COMPACT}") == UUID


def test_canonical_garbage_returns_none():
    assert NC.canonical_notion_id("not-an-id-at-all") is None


def test_canonical_dashed_uuid_inside_path_with_slash():
    url = f"https://x/{UUID}/"
    assert NC.canonical_notion_id(url) == UUID


# ===================== find_repo_root =====================

def test_find_repo_root_hit(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "marketplace.json").write_text("{}", encoding="utf-8")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert NC.find_repo_root(sub) == tmp_path.resolve()


def test_find_repo_root_git_without_marker_rejected(tmp_path):
    # .git はあるが marker が無い → グローバル誤ヒット防止で None
    (tmp_path / ".git").mkdir()
    assert NC.find_repo_root(tmp_path) is None


def test_find_repo_root_marker_without_git_rejected(tmp_path):
    # marker はあるが .git が無い → None
    (tmp_path / ".notion-config.json").write_text("{}", encoding="utf-8")
    assert NC.find_repo_root(tmp_path) is None


def test_find_repo_root_via_example_marker(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".notion-config.example.json").write_text("{}", encoding="utf-8")
    assert NC.find_repo_root(tmp_path) == tmp_path.resolve()


# ===================== plugin_root =====================

def test_plugin_root_env_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
    assert NC.plugin_root() == tmp_path


def test_plugin_root_default_is_plugin_dir():
    # env 無しなら scripts/ の親 = plugin root
    assert NC.plugin_root() == SCRIPT.resolve().parents[1]


# ===================== find_config_path (5 段解決) =====================

def test_find_config_path_env_explicit(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path / "explicit.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.find_config_path() == cfg


def test_find_config_path_env_missing_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(tmp_path / "nope.json"))
    with pytest.raises(FileNotFoundError):
        NC.find_config_path()


def test_find_config_path_repo_root(monkeypatch, tmp_path):
    # 2 段目: repo-root marker + .git + .notion-config.json
    (tmp_path / ".git").mkdir()
    cfg = _write_cfg(tmp_path / NC.CONFIG_FILENAME)
    # plugin-root を別の空 dir に向けて 3/4 段目に流れないことを保証
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "empty-plugin"))
    (tmp_path / "empty-plugin").mkdir()
    assert NC.find_config_path(start=tmp_path) == cfg


def test_find_config_path_plugin_root(monkeypatch, tmp_path):
    # 3 段目: repo-root 不在 → plugin-root 直下 .notion-config.json
    pr = tmp_path / "plugin"
    pr.mkdir()
    cfg = _write_cfg(pr / NC.CONFIG_FILENAME)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    # start は marker の無い空 dir → repo-root None
    blank = tmp_path / "blank"
    blank.mkdir()
    assert NC.find_config_path(start=blank) == cfg


def test_find_config_path_bundled_fixed(monkeypatch, tmp_path):
    # 4 段目: notion-config.fixed.json
    pr = tmp_path / "plugin"
    pr.mkdir()
    fixed = _write_cfg(pr / NC.BUNDLED_CONFIG_FILENAME)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    blank = tmp_path / "blank"
    blank.mkdir()
    assert NC.find_config_path(start=blank) == fixed


def test_find_config_path_none(monkeypatch, tmp_path):
    # 5 段目: どこにも無い → None
    pr = tmp_path / "plugin"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    blank = tmp_path / "blank"
    blank.mkdir()
    assert NC.find_config_path(start=blank) is None


# ===================== load_config =====================

def test_load_config_attaches_path(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    loaded = NC.load_config()
    assert loaded["__path__"] == str(cfg)
    assert loaded["keychain_service"] == "svc"


def test_load_config_none_when_no_path(monkeypatch, tmp_path):
    pr = tmp_path / "plugin"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    blank = tmp_path / "blank"
    blank.mkdir()
    assert NC.load_config(start=blank) is None


# ===================== get_db_id =====================

def test_get_db_id_env_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("INTAKE_NOTION_DATABASE_ID", "env-db")
    # config を立てても env が優先される
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.get_db_id("hearing-sheet") == "env-db"


def test_get_db_id_from_config(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.get_db_id("skill-list") == "db-skill"
    assert NC.get_db_id("improvement-request") == "db-improve"


def test_get_db_id_unknown_key_no_env(monkeypatch, tmp_path):
    # DB_ENV_NAMES に無いキー → env 無し → config に無ければ None
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.get_db_id("does-not-exist") is None


def test_get_db_id_no_config(monkeypatch, tmp_path):
    pr = tmp_path / "plugin"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    blank = tmp_path / "blank"
    blank.mkdir()
    assert NC.get_db_id("skill-list", start=blank) is None


def test_get_db_id_config_missing_databases(monkeypatch, tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"keychain_service": "s"}), encoding="utf-8")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(p))
    assert NC.get_db_id("skill-list") is None


# ===================== get_parent_page_id =====================

def test_get_parent_page_id_env(monkeypatch, tmp_path):
    monkeypatch.setenv("INTAKE_NOTION_PARENT_PAGE_ID", COMPACT)
    assert NC.get_parent_page_id() == UUID


def test_get_parent_page_id_from_config_page_id(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.get_parent_page_id() == UUID


def test_get_parent_page_id_from_page_url(monkeypatch, tmp_path):
    cfg = _write_cfg(
        tmp_path / "c.json",
        parent_page={"page_url": f"https://app.notion.com/p/{COMPACT}"},
    )
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    assert NC.get_parent_page_id() == UUID


def test_get_parent_page_id_legacy_top_level(monkeypatch, tmp_path):
    # parent_page 無し、legacy parent_page_id を採用
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"parent_page_id": COMPACT}), encoding="utf-8")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(p))
    assert NC.get_parent_page_id() == UUID


def test_get_parent_page_id_no_config(monkeypatch, tmp_path):
    pr = tmp_path / "plugin"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    blank = tmp_path / "blank"
    blank.mkdir()
    assert NC.get_parent_page_id(start=blank) is None


# ===================== get_token (keychain / env stub) =====================

def test_get_token_env_allowed(monkeypatch):
    monkeypatch.setenv("INTAKE_ALLOW_ENV_TOKEN", "1")
    monkeypatch.setenv("NOTION_TOKEN", "env-token")
    # env 許可時は Keychain を一切叩かない
    monkeypatch.setattr(NC.subprocess, "check_output",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no keychain")))
    assert NC.get_token() == "env-token"


def test_get_token_env_present_but_not_allowed_falls_to_keychain(monkeypatch):
    # NOTION_TOKEN はあるが ALLOW フラグ無し → Keychain 経路
    monkeypatch.setenv("NOTION_TOKEN", "should-be-ignored")
    monkeypatch.setattr(NC.subprocess, "check_output", lambda *a, **k: "kc-token\n")
    assert NC.get_token() == "kc-token"


def test_get_token_keychain_success_command_shape(monkeypatch):
    captured = {}

    def fake(cmd, **k):
        captured["cmd"] = cmd
        return "secret-from-kc\n"

    monkeypatch.setattr(NC.subprocess, "check_output", fake)
    tok = NC.get_token({"keychain_service": "my-svc", "keychain_account": "my-acct"})
    assert tok == "secret-from-kc"
    cmd = captured["cmd"]
    assert cmd[0] == "security" and "find-generic-password" in cmd
    assert "my-svc" in cmd and "my-acct" in cmd
    assert "-w" in cmd


def test_get_token_keychain_default_service_account(monkeypatch):
    captured = {}

    def fake(cmd, **k):
        captured["cmd"] = cmd
        return "x"

    monkeypatch.setattr(NC.subprocess, "check_output", fake)
    NC.get_token(None)
    assert "notion-api-key.xlocal" in captured["cmd"]
    assert "xlocal" in captured["cmd"]


def test_get_token_keychain_no_account(monkeypatch):
    captured = {}

    def fake(cmd, **k):
        captured["cmd"] = cmd
        return "x"

    monkeypatch.setattr(NC.subprocess, "check_output", fake)
    NC.get_token({"keychain_service": "svc", "keychain_account": ""})
    # account 空は active tenant の account へ fail-closed に導出される
    assert "-a" in captured["cmd"]
    assert "xlocal" in captured["cmd"]


def test_get_token_keychain_called_process_error(monkeypatch):
    def boom(*a, **k):
        raise NC.subprocess.CalledProcessError(returncode=44, cmd="security")

    monkeypatch.setattr(NC.subprocess, "check_output", boom)
    assert NC.get_token({}) is None


def test_get_token_keychain_binary_missing(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("security not on PATH")

    monkeypatch.setattr(NC.subprocess, "check_output", boom)
    assert NC.get_token({}) is None


# ===================== warn_missing =====================

def test_warn_missing_writes_guidance(monkeypatch):
    import io
    buf = io.StringIO()
    NC.warn_missing(stream=buf)
    text = buf.getvalue()
    assert "WARN" in text
    assert NC.CONFIG_FILENAME in text
    assert NC.BUNDLED_CONFIG_FILENAME in text


# ===================== require_or_skip =====================

def _full_env_config(monkeypatch, tmp_path):
    """find_config_path が cwd 経由で解決する require_or_skip 用に env 明示。"""
    cfg = _write_cfg(tmp_path / "c.json")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(cfg))
    return cfg


def test_require_or_skip_happy(monkeypatch, tmp_path):
    _full_env_config(monkeypatch, tmp_path)
    monkeypatch.setattr(NC, "get_token", lambda cfg=None: "tok")
    cfg, tok = NC.require_or_skip("hearing-sheet")
    assert tok == "tok"
    assert cfg["keychain_service"] == "svc"


def test_require_or_skip_no_config_fail_closed(monkeypatch, tmp_path):
    # config 不在 → fail-closed で sys.exit(2)
    pr = tmp_path / "plugin"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    monkeypatch.chdir(pr)   # cwd も marker 無し dir
    with pytest.raises(SystemExit) as e:
        NC.require_or_skip("hearing-sheet")
    assert e.value.code == 2


def test_require_or_skip_no_config_allow_skip(monkeypatch, tmp_path, capsys):
    pr = tmp_path / "plugin"
    pr.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(pr))
    monkeypatch.chdir(pr)
    cfg, tok = NC.require_or_skip("hearing-sheet", allow_skip=True)
    assert cfg is None and tok is None
    assert "allow-skip" in capsys.readouterr().err


def test_require_or_skip_no_token_fail_closed(monkeypatch, tmp_path):
    _full_env_config(monkeypatch, tmp_path)
    monkeypatch.setattr(NC, "get_token", lambda cfg=None: None)
    with pytest.raises(SystemExit) as e:
        NC.require_or_skip("hearing-sheet")
    assert e.value.code == 2


def test_require_or_skip_no_token_allow_skip(monkeypatch, tmp_path, capsys):
    _full_env_config(monkeypatch, tmp_path)
    monkeypatch.setattr(NC, "get_token", lambda cfg=None: None)
    cfg, tok = NC.require_or_skip("hearing-sheet", allow_skip=True)
    assert cfg is None and tok is None
    assert "token unavailable" in capsys.readouterr().err


def test_require_or_skip_missing_db_fail_closed(monkeypatch, tmp_path):
    # databases に無いキーを要求 → db_id missing で exit 2
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"keychain_service": "s", "databases": {}}), encoding="utf-8")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(p))
    monkeypatch.setattr(NC, "get_token", lambda cfg=None: "tok")
    with pytest.raises(SystemExit) as e:
        NC.require_or_skip("skill-list")
    assert e.value.code == 2


def test_require_or_skip_no_key_skips_db_check(monkeypatch, tmp_path):
    # key="" の時は db_id チェックを飛ばす
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"keychain_service": "s", "databases": {}}), encoding="utf-8")
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(p))
    monkeypatch.setattr(NC, "get_token", lambda cfg=None: "tok")
    cfg, tok = NC.require_or_skip("")
    assert tok == "tok"


# ===================== __main__ subprocess =====================

def test_main_entrypoint_subprocess_loaded(tmp_path):
    import subprocess
    cfg = _write_cfg(tmp_path / "c.json")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
        env={"NOTION_CONFIG_PATH": str(cfg), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0
    # __path__ は出力から除外される
    assert "__path__" not in proc.stdout
    assert "loaded from" in proc.stdout
    assert "svc" in proc.stdout


def test_main_entrypoint_subprocess_no_config(tmp_path):
    import subprocess
    pr = tmp_path / "plugin"
    pr.mkdir()
    blank = tmp_path / "blank"
    blank.mkdir()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, cwd=str(blank),
        env={"CLAUDE_PLUGIN_ROOT": str(pr), "PATH": "/usr/bin:/bin"},
    )
    # config 不在でも exit 0 (warn して終了)
    assert proc.returncode == 0
    assert "WARN" in proc.stderr

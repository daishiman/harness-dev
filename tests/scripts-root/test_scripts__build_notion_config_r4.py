"""Genuine functional tests (scripts4) for scripts/build-notion-config.py.

このスクリプトは新規 repo で .notion-config.json を repo-slug namespacing 付きで
1 コマンド生成する。keychain は **書く** だけで実通信はしない (security コマンドを
ユーザーへ提示するのみ)。git remote 呼び出しと input() は monkeypatch で stub し、
ファイル書き込みは module-level ROOT/CONFIG/EXAMPLE を tmp_path へ差し替えて repo を
汚さない。

network/keychain/secret に到達しない:
  - derive_slug() の `git remote get-url` を呼ぶ subprocess.check_output を stub。
  - print-keychain-cmd / config 書き込み / 既存 abort / 対話 Y/n / 引数伝播 を genuine に検証。

他ディレクトリと同名にならないよう _r4 サフィックスを付す。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-notion-config.py"

_SPEC = importlib.util.spec_from_file_location("build_notion_config_r4", SCRIPT)
BNC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(BNC)


# ============================================================
# fixtures: tmp_path に repo を組み立て module の ROOT/CONFIG/EXAMPLE を差し替える
# ============================================================

EXAMPLE_JSON = {
    "_comment": "example comment that must be stripped",
    "keychain_service": "notion-api-key.<REPLACE_WITH_REPO_SLUG>",
    "keychain_account": "<REPLACE_WITH_REPO_SLUG>",
    "parent_page": {"page_id": "<your-parent-page-id>", "page_url": "<your-parent-page-url>"},
    "databases": {
        "skill-list": {"db_id": "<your-skill-list-db-id>"},
        "hearing-sheet": {"db_id": "<your-hearing-sheet-db-id>"},
        "improvement-request": {"db_id": "<your-improvement-request-db-id>"},
    },
    "schema_dir": "doc/notion-schema",
}


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """tmp_path を repo-root に見立て module-level path を差し替える。"""
    root = tmp_path / "myrepo"
    root.mkdir()
    example = root / ".notion-config.example.json"
    example.write_text(json.dumps(EXAMPLE_JSON, ensure_ascii=False), encoding="utf-8")
    config = root / ".notion-config.json"
    monkeypatch.setattr(BNC, "ROOT", root)
    monkeypatch.setattr(BNC, "CONFIG", config)
    monkeypatch.setattr(BNC, "EXAMPLE", example)
    return {"root": root, "config": config, "example": example}


def _run(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["build-notion-config.py", *argv])
    return BNC.main()


# ============================================================
# derive_slug: git remote 成功 / .git suffix 除去 / 失敗時 dir 名 fallback / 空 url
# ============================================================

def test_derive_slug_from_git_remote_strips_git_suffix(fake_repo, monkeypatch):
    monkeypatch.setattr(
        subprocess, "check_output",
        lambda *a, **k: "git@github.com:xl-manju/xl-skills.git\n",
    )
    assert BNC.derive_slug() == "xl-skills"


def test_derive_slug_https_url_trailing_slash(fake_repo, monkeypatch):
    monkeypatch.setattr(
        subprocess, "check_output",
        lambda *a, **k: "https://github.com/acme/cool-repo/\n",
    )
    assert BNC.derive_slug() == "cool-repo"


def test_derive_slug_falls_back_to_dir_name_on_error(fake_repo, monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(subprocess, "check_output", boom)
    # ROOT は fake_repo["root"] = .../myrepo
    assert BNC.derive_slug() == "myrepo"


def test_derive_slug_empty_url_falls_back_to_dir_name(fake_repo, monkeypatch):
    # git が空文字を返す → slug 偽 → ROOT.name
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "\n")
    assert BNC.derive_slug() == "myrepo"


# ============================================================
# --print-keychain-cmd: config を書かず security コマンドのみ出力 (実行はしない)
# ============================================================

def test_print_keychain_cmd_only(fake_repo, monkeypatch, capsys):
    ret = _run(monkeypatch, ["--slug", "demo-repo", "--print-keychain-cmd"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "security add-generic-password" in out
    assert "-s notion-api-key.demo-repo" in out
    assert "-a demo-repo" in out
    # config は書かれていない
    assert not fake_repo["config"].exists()


def test_print_keychain_cmd_uses_derived_slug(fake_repo, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "https://x/y/derived.git\n")
    ret = _run(monkeypatch, ["--print-keychain-cmd"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "notion-api-key.derived" in out


# ============================================================
# 既存 config 冪等 abort (--force 無し → 2 / 有り → 上書き)
# ============================================================

def test_existing_config_aborts_without_force(fake_repo, monkeypatch, capsys):
    fake_repo["config"].write_text('{"existing": true}', encoding="utf-8")
    ret = _run(monkeypatch, ["--slug", "x", "--non-interactive"])
    assert ret == 2
    assert "already exists" in capsys.readouterr().err
    # 既存内容が保持される (上書きされていない)
    assert json.loads(fake_repo["config"].read_text()) == {"existing": True}


def test_existing_config_overwritten_with_force(fake_repo, monkeypatch):
    fake_repo["config"].write_text('{"existing": true}', encoding="utf-8")
    ret = _run(monkeypatch, ["--slug", "x", "--non-interactive", "--force"])
    assert ret == 0
    data = json.loads(fake_repo["config"].read_text())
    assert "existing" not in data
    assert data["keychain_service"] == "notion-api-key.x"


# ============================================================
# 非対話で config を書く: 全フィールド + _comment 除去 + slug namespacing
# ============================================================

def test_non_interactive_writes_full_config(fake_repo, monkeypatch, capsys):
    ret = _run(monkeypatch, [
        "--slug", "team-alpha",
        "--non-interactive",
        "--parent-page-id", "PPID",
        "--parent-page-url", "https://www.notion.so/PPID",
        "--skill-list-db", "SL",
        "--hearing-sheet-db", "HS",
        "--improvement-request-db", "IR",
    ])
    assert ret == 0
    data = json.loads(fake_repo["config"].read_text())
    # slug namespacing が keychain に焼かれる
    assert data["keychain_service"] == "notion-api-key.team-alpha"
    assert data["keychain_account"] == "team-alpha"
    # _comment は除去される
    assert "_comment" not in data
    # 引数が全て伝播
    assert data["parent_page"]["page_id"] == "PPID"
    assert data["parent_page"]["page_url"] == "https://www.notion.so/PPID"
    assert data["databases"]["skill-list"]["db_id"] == "SL"
    assert data["databases"]["hearing-sheet"]["db_id"] == "HS"
    assert data["databases"]["improvement-request"]["db_id"] == "IR"
    # schema_dir は template から保持される
    assert data["schema_dir"] == "doc/notion-schema"
    out = capsys.readouterr().out
    assert "wrote" in out
    assert "Next steps" in out


def test_non_interactive_defaults_fill_placeholders(fake_repo, monkeypatch):
    # 引数省略時は <your-*> placeholder が入る
    ret = _run(monkeypatch, ["--slug", "p", "--non-interactive"])
    assert ret == 0
    data = json.loads(fake_repo["config"].read_text())
    assert data["parent_page"]["page_id"] == "<your-parent-page-id>"
    assert data["parent_page"]["page_url"] == "<your-parent-page-url>"
    assert data["databases"]["skill-list"]["db_id"] == "<your-skill-list-db-id>"
    assert data["databases"]["hearing-sheet"]["db_id"] == "<your-hearing-sheet-db-id>"
    assert data["databases"]["improvement-request"]["db_id"] == "<your-improvement-request-db-id>"


def test_config_trailing_newline_and_indent(fake_repo, monkeypatch):
    ret = _run(monkeypatch, ["--slug", "p", "--non-interactive"])
    assert ret == 0
    text = fake_repo["config"].read_text(encoding="utf-8")
    assert text.endswith("\n")
    # indent=2 でフォーマットされる
    assert '\n  "keychain_service"' in text


# ============================================================
# 対話モード: input() を stub。Y / 空Enter で続行、n で abort
# ============================================================

def test_interactive_yes_writes_config(fake_repo, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a, **k: "Y")
    ret = _run(monkeypatch, ["--slug", "ix"])
    assert ret == 0
    assert fake_repo["config"].exists()
    out = capsys.readouterr().out
    assert "repo slug: ix" in out
    assert "keychain_service: notion-api-key.ix" in out


def test_interactive_empty_enter_continues(fake_repo, monkeypatch):
    # 空 Enter (デフォルト Y 扱い)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    ret = _run(monkeypatch, ["--slug", "ie"])
    assert ret == 0
    assert fake_repo["config"].exists()


def test_interactive_no_aborts(fake_repo, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
    ret = _run(monkeypatch, ["--slug", "ino"])
    assert ret == 1
    assert "aborted" in capsys.readouterr().out
    assert not fake_repo["config"].exists()


def test_interactive_random_answer_aborts(fake_repo, monkeypatch):
    # "y" 以外の非空回答 → abort
    monkeypatch.setattr("builtins.input", lambda *a, **k: "maybe")
    ret = _run(monkeypatch, ["--slug", "ir"])
    assert ret == 1
    assert not fake_repo["config"].exists()


# ============================================================
# slug 未指定 → derive_slug 経由 (git remote stub)
# ============================================================

def test_main_derives_slug_when_not_given(fake_repo, monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "https://x/y/auto-slug.git\n")
    ret = _run(monkeypatch, ["--non-interactive"])
    assert ret == 0
    data = json.loads(fake_repo["config"].read_text())
    assert data["keychain_service"] == "notion-api-key.auto-slug"
    assert data["keychain_account"] == "auto-slug"


# ============================================================
# subprocess(sys.executable) で main を実 CLI 起動 (end-to-end smoke)
# ============================================================

def test_cli_print_keychain_cmd_subprocess():
    """実 CLI として --print-keychain-cmd を起動。config を書かない安全経路。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--slug", "cli-demo", "--print-keychain-cmd"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "security add-generic-password" in proc.stdout
    assert "notion-api-key.cli-demo" in proc.stdout

"""run-skill-feedback の Notion 投入境界をネットワーク無しで固定する。

scripts/notion-submit-improvement.py の exit 契約 (未登録=2 / API 到達・認可失敗=3) と、
token を argv に載せず `--config -` で curl の stdin へ渡す経路を、curl / subprocess を
monkeypatch して検証する。Notion へは一切送信しない。
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "notion-submit-improvement.py"
SKILL = ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-feedback" / "SKILL.md"
MANIFEST = SKILL.parent / "workflow-manifest.json"

TOKEN = "secret-token"


def _load():
    spec = importlib.util.spec_from_file_location("notion_submit_improvement", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _argv(*extra: str) -> list[str]:
    return [
        "notion-submit-improvement.py",
        "--title",
        "title",
        "--plugin",
        "sample-plugin",
        "--type",
        "バグ",
        "--desire",
        "fix it",
        *extra,
    ]


def _configured(monkeypatch, mod):
    monkeypatch.setattr(
        mod.notion_config,
        "require_or_skip",
        lambda *_a, **_kw: ({"configured": True}, TOKEN),
    )
    monkeypatch.setattr(mod.notion_config, "get_db_id", lambda key: f"{key}-db")


def test_dry_run_only_prints_payload(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(
        mod.notion_config,
        "require_or_skip",
        lambda *_a, **_kw: pytest.fail("dry-run で Notion 設定を解決してはいけない"),
    )
    monkeypatch.setattr(sys, "argv", _argv("--dry-run"))

    mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["plugin"] == "sample-plugin"
    assert payload["dry_run"] is True


def test_unregistered_plugin_exits_2_with_registration_guidance(monkeypatch, capsys):
    mod = _load()
    _configured(monkeypatch, mod)
    monkeypatch.setattr(mod, "find_plugin_page", lambda *_a: None)
    monkeypatch.setattr(
        mod, "curl", lambda *_a, **_kw: pytest.fail("未登録ならページ作成へ進んではいけない")
    )
    monkeypatch.setattr(sys, "argv", _argv())

    with pytest.raises(SystemExit) as exc:
        mod.main()

    assert exc.value.code == 2
    output = capsys.readouterr().out
    assert "'sample-plugin'" in output
    assert "notion-upsert-plugin.py" in output
    assert TOKEN not in output


def test_api_failure_on_lookup_exits_3_not_unregistered(monkeypatch, capsys):
    """401/5xx を『未登録』(exit 2) に潰すと --notion-register という誤った復旧へ誘導する。"""
    mod = _load()
    _configured(monkeypatch, mod)

    def _raise(*_a):
        raise mod.NotionApiError("skill-list query が HTTP 401: {}")

    monkeypatch.setattr(mod, "find_plugin_page", _raise)
    monkeypatch.setattr(sys, "argv", _argv())

    with pytest.raises(SystemExit) as exc:
        mod.main()

    assert exc.value.code == 3
    output = capsys.readouterr().out
    assert "--notion-register は解決策になりません" in output
    assert TOKEN not in output


@pytest.mark.parametrize("status", [401, 403, 500])
def test_find_plugin_page_raises_on_http_error(monkeypatch, status):
    mod = _load()
    monkeypatch.setattr(mod, "curl", lambda *_a, **_kw: (status, {"message": "x"}))

    with pytest.raises(mod.NotionApiError):
        mod.find_plugin_page("skill-list-db", "sample-plugin", TOKEN)


def test_find_plugin_page_returns_none_only_for_empty_results(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "curl", lambda *_a, **_kw: (200, {"results": []}))
    assert mod.find_plugin_page("skill-list-db", "sample-plugin", TOKEN) is None

    monkeypatch.setattr(mod, "curl", lambda *_a, **_kw: (200, {"results": [{"id": "p1"}]}))
    assert mod.find_plugin_page("skill-list-db", "sample-plugin", TOKEN) == "p1"


def test_curl_passes_token_via_stdin_config_not_argv(monkeypatch):
    mod = _load()
    seen = {}

    class _Done:
        stdout = b'{"results": []}\n__HTTP__200'

    def _run(cmd, input=None, **_kw):
        seen["cmd"] = cmd
        seen["input"] = input
        body_arg = next((a for a in cmd if a.startswith("@")), None)
        seen["body_path"] = Path(body_arg[1:]) if body_arg else None
        return _Done()

    monkeypatch.setattr(mod.subprocess, "run", _run)

    code, data = mod.curl("POST", "https://api.notion.com/v1/x", TOKEN, {"k": "v"})

    assert (code, data) == (200, {"results": []})
    cmd = seen["cmd"]
    assert cmd[cmd.index("--config") + 1] == "-"
    assert all(TOKEN not in arg for arg in cmd)
    assert TOKEN.encode() in seen["input"]
    assert seen["body_path"] is not None and not seen["body_path"].exists()


def test_created_record_prints_page_id_without_token(monkeypatch, capsys):
    mod = _load()
    _configured(monkeypatch, mod)
    monkeypatch.setattr(mod, "find_plugin_page", lambda *_a: "plugin-page-id")
    monkeypatch.setattr(
        mod,
        "curl",
        lambda *_a, **_kw: (200, {"id": "01234567-89ab-cdef-0123-456789abcdef"}),
    )
    monkeypatch.setattr(sys, "argv", _argv())

    mod.main()

    output = capsys.readouterr().out
    assert "[CREATED]" in output
    assert "01234567-89ab-cdef-0123-456789abcdef" in output
    assert TOKEN not in output


def test_page_create_http_error_exits_3(monkeypatch, capsys):
    mod = _load()
    _configured(monkeypatch, mod)
    monkeypatch.setattr(mod, "find_plugin_page", lambda *_a: "plugin-page-id")
    monkeypatch.setattr(mod, "curl", lambda *_a, **_kw: (500, {"message": "x"}))
    monkeypatch.setattr(sys, "argv", _argv())

    with pytest.raises(SystemExit) as exc:
        mod.main()

    assert exc.value.code == 3
    assert TOKEN not in capsys.readouterr().out


def test_manifest_models_registration_check_inside_submit():
    phases = json.loads(MANIFEST.read_text(encoding="utf-8"))["phases"]
    by_id = {phase["id"]: phase for phase in phases}

    assert "verify-plugin" not in by_id
    assert by_id["submit"]["dependsOn"] == ["collect"]
    assert "find_plugin_page" in by_id["submit"]["title"]


def test_token_resolution_has_no_cli_path_documented():
    skill = SKILL.read_text(encoding="utf-8")

    assert "CLI 引数で token / DB ID を渡す経路は無い" in skill
    assert "CLI > env > per-repo" not in skill
    assert "CLI > env > `.notion-config.json`" not in skill


def test_skill_scan_instruction_uses_declared_tools():
    skill = SKILL.read_text(encoding="utf-8")

    assert 'glob="plugins/*/skills/*/SKILL.md"' in skill
    assert "Read: `plugins/<plugin>/skills/<skill_name>/SKILL.md`" in skill
    assert "grep -r --include=\"SKILL.md\"" not in skill
    assert "cat plugins/<plugin>/skills/<skill_name>/SKILL.md" not in skill

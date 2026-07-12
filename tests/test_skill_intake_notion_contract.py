import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cmd(*args, env=None):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def test_intake_command_uses_canonical_orchestrator():
    command = (ROOT / "plugins/skill-intake/commands/intake.md").read_text(encoding="utf-8")
    assert "Skill(run-skill-intake, args=\"$ARGUMENTS\")" in command
    assert "Skill(run-skill-intake-aggregator" not in command


def test_intake_manifest_publishes_before_next_action():
    manifest = json.loads(
        (ROOT / "plugins/skill-intake/skills/run-skill-intake/workflow-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    phases = {phase["id"]: phase for phase in manifest["phases"]}
    assert phases["P10-notion"]["delegateSkill"] == "run-notion-intake-publish"
    assert phases["P11-next-action"]["delegateSkill"] == "run-intake-next-action"
    assert phases["P11-next-action"]["dependsOn"] == ["P10-notion"]


def test_publish_pipeline_rejects_missing_target_by_default(tmp_path):
    # 有効な notion_target (mode=create-explicit かつ allow_create=true) が無い intake は
    # 既定で create fallback せず exit 51 (fail-closed)。fixture 直参照だと pipeline が
    # out_dir=fixture へ notion-log.json を書く副作用があるため tmp_path へ複製して起動する。
    src = json.loads(
        (ROOT / "plugins/skill-intake/fixtures/intake-final-smoke/context.json").read_text(
            encoding="utf-8"
        )
    )
    src.pop("notion_target", None)
    intake = tmp_path / "context.json"
    intake.write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    result = run_cmd(
        "plugins/skill-intake/scripts/intake_publish_pipeline.py",
        "--intake",
        str(intake),
        "--manifest",
        "plugins/skill-intake/fixtures/intake-final-smoke/notion-blocks.json",
        "--dry-run",
    )
    assert result.returncode == 51
    assert "create fallback is disabled by default" in result.stderr


def test_app_notion_url_uses_query_page_id():
    sys.path.insert(0, str(ROOT / "plugins/skill-intake/scripts"))
    from publish_notion_page import _extract_page_id_from_url

    url = (
        "https://app.notion.com/p/36607a0cd18c80bf9effc74aa736645c"
        "?v=36607a0cd18c809fb075000c267faadf"
        "&p=37707a0cd18c80139966cb05b2859594&pm=s"
    )
    assert _extract_page_id_from_url(url) == "37707a0c-d18c-8013-9966-cb05b2859594"


def test_notion_config_extracts_parent_page_from_url():
    sys.path.insert(0, str(ROOT / "plugins/skill-intake/scripts"))
    import notion_config

    url = "https://app.notion.com/p/36607a0cd18c80bf9effc74aa736645c?v=36607a0cd18c809fb075000c267faadf"
    assert notion_config.canonical_notion_id(url) == "36607a0c-d18c-80bf-9eff-c74aa736645c"


def test_create_notion_database_uses_config_parent_page_in_dry_run(tmp_path):
    cfg = tmp_path / ".notion-config.json"
    cfg.write_text(
        json.dumps({
            "parent_page": {
                "page_url": "https://app.notion.com/p/36607a0cd18c80bf9effc74aa736645c?v=36607a0cd18c809fb075000c267faadf"
            },
            "databases": {},
        }),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["NOTION_CONFIG_PATH"] = str(cfg)

    result = run_cmd(
        "plugins/skill-intake/scripts/create_notion_database.py",
        "--mode=create",
        "--dry-run",
        env=env,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["dry_run"] is True
    assert payload["parent_page_id"] == "36607a0c-d18c-80bf-9eff-c74aa736645c"


def test_notion_config_uses_bundled_fixed_config_when_local_config_missing(tmp_path):
    plugin_root = tmp_path / "skill-intake"
    plugin_root.mkdir()
    fixed = plugin_root / "notion-config.fixed.json"
    fixed.write_text(
        json.dumps({
            "parent_page": {
                "page_url": "https://app.notion.com/p/36607a0cd18c80bf9effc74aa736645c?v=36607a0cd18c809fb075000c267faadf"
            },
            "databases": {
                "hearing-sheet": {
                    "db_id": "36607a0c-d18c-80bf-9eff-c74aa736645c"
                }
            },
        }),
        encoding="utf-8",
    )

    sys.path.insert(0, str(ROOT / "plugins/skill-intake/scripts"))
    import notion_config

    old_plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    old_config_path = os.environ.get("NOTION_CONFIG_PATH")
    old_db = os.environ.get("INTAKE_NOTION_DATABASE_ID")
    try:
        os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
        os.environ.pop("NOTION_CONFIG_PATH", None)
        os.environ.pop("INTAKE_NOTION_DATABASE_ID", None)
        start = tmp_path / "standalone" / "nested"
        start.mkdir(parents=True)
        assert notion_config.find_config_path(start) == fixed
        assert notion_config.get_db_id("hearing-sheet", start=start) == "36607a0c-d18c-80bf-9eff-c74aa736645c"
        assert notion_config.get_parent_page_id(start=start) == "36607a0c-d18c-80bf-9eff-c74aa736645c"
    finally:
        if old_plugin_root is None:
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
        else:
            os.environ["CLAUDE_PLUGIN_ROOT"] = old_plugin_root
        if old_config_path is None:
            os.environ.pop("NOTION_CONFIG_PATH", None)
        else:
            os.environ["NOTION_CONFIG_PATH"] = old_config_path
        if old_db is None:
            os.environ.pop("INTAKE_NOTION_DATABASE_ID", None)
        else:
            os.environ["INTAKE_NOTION_DATABASE_ID"] = old_db


def test_bundled_fixed_config_fails_closed_without_tenant_target():
    fixed = json.loads((ROOT / "plugins/skill-intake/notion-config.fixed.json").read_text(encoding="utf-8"))
    assert fixed["databases"]["hearing-sheet"]["db_id"] == ""
    assert fixed["keychain_service"] == ""
    assert fixed["keychain_account"] == ""
    assert fixed["databases"]["hearing-sheet"]["url"] == ""


def test_bundled_fixed_config_parent_page_is_blank_fail_closed():
    # 同梱 fixed config の parent_page は意図的に空。DB を親ページとして誤指定する
    # 回帰 (parent_page.page_id == databases.*.db_id) を封じ、DB 新規作成をユーザー
    # 指定の親ページ必須 (fail-closed) にする。
    fixed = json.loads((ROOT / "plugins/skill-intake/notion-config.fixed.json").read_text(encoding="utf-8"))
    assert fixed["parent_page"]["page_id"] == ""
    assert fixed["parent_page"]["page_url"] == ""


def test_create_notion_database_rejects_parent_page_equal_to_db_id(tmp_path):
    # 親ページ ID が databases.*.db_id と同一 (親が DB を指す誤設定) は create を拒否する。
    cfg = tmp_path / ".notion-config.json"
    cfg.write_text(
        json.dumps({
            "parent_page": {"page_id": "36607a0c-d18c-80bf-9eff-c74aa736645c"},
            "databases": {
                "hearing-sheet": {"db_id": "36607a0c-d18c-80bf-9eff-c74aa736645c"}
            },
        }),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["NOTION_CONFIG_PATH"] = str(cfg)
    env.pop("INTAKE_NOTION_PARENT_PAGE_ID", None)

    result = run_cmd(
        "plugins/skill-intake/scripts/create_notion_database.py",
        "--mode=create",
        "--dry-run",
        env=env,
    )
    assert result.returncode == 2
    assert "DB新規作成には親“ページ”IDが必要です" in result.stderr


def test_check_notion_ready_reports_fixed_target_with_env_token(tmp_path):
    plugin_root = tmp_path / "skill-intake"
    plugin_root.mkdir()
    (plugin_root / "notion-config.fixed.json").write_text(
        json.dumps({
            "keychain_service": "notion-api-key.xl-skills",
            "keychain_account": "xl-skills",
            "parent_page": {"page_id": "36607a0c-d18c-80bf-9eff-c74aa736645c"},
            "databases": {"hearing-sheet": {"db_id": "36607a0c-d18c-80bf-9eff-c74aa736645c"}},
        }),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env.pop("NOTION_CONFIG_PATH", None)
    env.pop("INTAKE_NOTION_DATABASE_ID", None)
    env["INTAKE_ALLOW_ENV_TOKEN"] = "1"
    env["NOTION_TOKEN"] = "secret_test"
    # mmdc preflight (DEPENDENCY_ERROR=3) を通すため、実 mmdc 非依存の shim を PATH 先頭に置く。
    mmdc_dir = tmp_path / "bin"
    mmdc_dir.mkdir()
    (mmdc_dir / "mmdc").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (mmdc_dir / "mmdc").chmod(0o755)
    env["PATH"] = f"{mmdc_dir}{os.pathsep}{env.get('PATH', '')}"

    result = run_cmd(
        "plugins/skill-intake/scripts/validate-notion-ready.py",
        "--json",
        env=env,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["database_id"] == "36607a0c-d18c-80bf-9eff-c74aa736645c"
    assert payload["token"] == "available"
    assert payload["mmdc"] == "available"
    assert payload["api"] == "not_checked"


def test_intake_prompts_do_not_reask_api_key_after_ready_check():
    skill = (ROOT / "plugins/skill-intake/skills/run-skill-intake/SKILL.md").read_text(encoding="utf-8")
    prompt = (ROOT / "plugins/skill-intake/skills/run-skill-intake/prompts/R1-main.md").read_text(
        encoding="utf-8"
    )
    publish = (ROOT / "plugins/skill-intake/skills/run-notion-intake-publish/SKILL.md").read_text(
        encoding="utf-8"
    )
    revise = (ROOT / "plugins/skill-intake/skills/run-intake-revise/SKILL.md").read_text(
        encoding="utf-8"
    )
    for text in (skill, prompt, publish, revise):
        assert "validate-notion-ready.py --check-api" in text
        assert "再質問しない" in text or "再入力を求めない" in text


def test_smoke_notion_publish_requires_target(tmp_path):
    (tmp_path / "intake.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notion-manifest.json").write_text("{}", encoding="utf-8")
    result = run_cmd(
        "plugins/skill-intake/scripts/smoke_notion_publish.py",
        "--dir",
        str(tmp_path),
    )
    assert result.returncode == 2
    assert "target page is required" in result.stderr


def test_smoke_notion_publish_default_is_non_mutating(tmp_path):
    page_id = "12345678-1234-1234-1234-123456789abc"
    (tmp_path / "intake.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notion-manifest.json").write_text("{}", encoding="utf-8")
    result = run_cmd(
        "plugins/skill-intake/scripts/smoke_notion_publish.py",
        "--dir",
        str(tmp_path),
        "--page-id",
        page_id,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["execute"] is False
    assert "--revise" in payload["command"]
    assert "--allow-create" not in payload["command"]
    assert payload["target"]["page_id"] == page_id


def test_run_skill_create_publish_ready_accepts_matching_target(tmp_path):
    page_id = "12345678-1234-1234-1234-123456789abc"
    compact = page_id.replace("-", "")
    (tmp_path / "intake.json").write_text(
        json.dumps({"schema_version": "2.0.0", "notion_target": {"mode": "update", "page_id": page_id}}),
        encoding="utf-8",
    )
    (tmp_path / "notion-publish-result.json").write_text(
        json.dumps({"page_id": page_id, "url": f"https://www.notion.so/Test-{compact}"}),
        encoding="utf-8",
    )
    (tmp_path / "notion-log.json").write_text(
        json.dumps({"status": "published", "page_id": page_id}),
        encoding="utf-8",
    )
    (tmp_path / "notion-url.txt").write_text(f"https://www.notion.so/Test-{compact}\n", encoding="utf-8")

    result = run_cmd(
        "plugins/harness-creator/skills/run-skill-create/scripts/validate-intake-publish-ready.py",
        "--dir",
        str(tmp_path),
        "--page-id",
        page_id,
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_run_skill_create_publish_ready_rejects_mismatched_target(tmp_path):
    actual = "12345678-1234-1234-1234-123456789abc"
    expected = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    compact = actual.replace("-", "")
    (tmp_path / "intake.json").write_text(
        json.dumps({"schema_version": "2.0.0", "notion_target": {"mode": "update", "page_id": expected}}),
        encoding="utf-8",
    )
    (tmp_path / "notion-publish-result.json").write_text(
        json.dumps({"page_id": actual, "url": f"https://www.notion.so/Test-{compact}"}),
        encoding="utf-8",
    )
    (tmp_path / "notion-log.json").write_text(
        json.dumps({"status": "published", "page_id": actual}),
        encoding="utf-8",
    )
    (tmp_path / "notion-url.txt").write_text(f"https://www.notion.so/Test-{compact}\n", encoding="utf-8")

    result = run_cmd(
        "plugins/harness-creator/skills/run-skill-create/scripts/validate-intake-publish-ready.py",
        "--dir",
        str(tmp_path),
        "--page-id",
        expected,
    )
    assert result.returncode == 2
    assert "page_id mismatch" in result.stderr

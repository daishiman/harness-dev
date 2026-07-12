"""harness-creator が plugin-root 空展開事故を再発させない生成契約を持つことの回帰テスト。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_BUILD = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
RUNTIME_REF = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "ref-cross-platform-runtime"
    / "references"
    / "runtime-portability.md"
)


def test_run_build_skill_requires_doctor_and_readme_portability_lint():
    text = (RUN_BUILD / "SKILL.md").read_text(encoding="utf-8")
    assert "__file__" in text
    assert "doctor" in text
    assert "scripts/lint-readme-plugin-root-portability.py" in text
    assert "${CLAUDE_PLUGIN_ROOT:-plugins/<name>}" in text
    # setup 手順 (references/*-setup.md) も裸変数/repo相対禁止の射程に入ること
    # (README だけの被覆では company-master 型の setup docs が抜ける穴を塞いだ)。
    assert "references/*-setup.md" in text


def test_cross_platform_runtime_documents_readme_empty_expansion_failure_mode():
    text = RUNTIME_REF.read_text(encoding="utf-8")
    assert "README ドキュメント層" in text
    assert "can't open file '/lib/...'" in text
    assert "scripts/lint-readme-plugin-root-portability.py" in text
    assert "doctor スクリプト" in text
    assert "${CLAUDE_PLUGIN_ROOT:-plugins/<name>}" in text
    # lint の走査対象が README のみでなく setup 手順まで及ぶことを正本に明記させる。
    assert "references/*-setup.md" in text


def test_command_skeleton_supports_direct_script_doctor_without_bare_root():
    text = (RUN_BUILD / "templates" / "command-skeleton.md").read_text(encoding="utf-8")
    assert "direct-script command" in text
    assert "${CLAUDE_PLUGIN_ROOT:-plugins/<plugin-name>}" in text
    assert "__file__" in text
    assert "lint-readme-plugin-root-portability.py" in text


def test_command_schema_allows_direct_script_command_with_portability_contract():
    text = (RUN_BUILD / "references" / "capability-manifest.schema.json").read_text(
        encoding="utf-8"
    )
    assert "direct-script command" in text
    assert "${CLAUDE_PLUGIN_ROOT:-plugins/<plugin-name>}" in text
    assert "__file__" in text


def test_plugin_composition_skeleton_uses_plugin_root_relative_paths():
    text = (RUN_BUILD / "templates" / "plugin-composition-skeleton.yaml").read_text(
        encoding="utf-8"
    )
    assert "`plugins/<name>/` を入れない" in text
    assert "EVALS.json" in text
    assert "{{PLUGIN_DIR}}EVALS.json" not in text
    assert "{{PLUGIN_DIR}}CHANGELOG.md" not in text
    assert "{{PLUGIN_DIR}}LESSONS.md" not in text


def test_hook_skeleton_requires_runtime_portability_contract():
    text = (RUN_BUILD / "templates" / "hook-skeleton.md").read_text(encoding="utf-8")
    assert "導入者向け README / 手動実行例には裸 $CLAUDE_PLUGIN_ROOT を出さない" in text
    assert "import-time に plugin root 外へ fail-closed 依存しない" in text
    assert "`__file__` / plugin-relative" in text
    assert "lint-runtime-portability.py" in text

"""x-longpost-creator の配布面と実行手順が同じ公開契約を指すことを確かめる。"""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "x-longpost-creator"


def _json(relative_path: str):
    return json.loads((PLUGIN / relative_path).read_text(encoding="utf-8"))


def _text(relative_path: str):
    return (PLUGIN / relative_path).read_text(encoding="utf-8")


def test_release_metadata_and_visual_capability_match_on_both_hosts():
    claude = _json(".claude-plugin/plugin.json")
    codex = _json(".codex-plugin/plugin.json")
    composition = _text("plugin-composition.yaml")
    readme = _text("README.md")

    composition_version = re.search(r"^version:\s*(\S+)$", composition, re.MULTILINE)
    assert composition_version

    # 版番号をここへ直接書くと、build-plugin-release.py が bump するたびに本テストが
    # 落ちる。しかし守りたいのは「配布面どうしが食い違っていないこと」であって番号の
    # 値ではない。CHANGELOG の最上位見出しを基準に据えると、番号が動いても検査は生き
    # 続け、さらに「CHANGELOG に節の無い版を配らない」ことまで同時に保証される。
    changelog_version = re.search(r"^## (\S+) — ", _text("CHANGELOG.md"), re.MULTILINE)
    assert changelog_version, "CHANGELOG.md の最上位に `## <version> — <date>` の節がない"
    assert (
        claude["version"]
        == codex["version"]
        == composition_version.group(1)
        == changelog_version.group(1)
    )
    assert claude["description"] == codex["description"] == codex["interface"]["longDescription"]
    assert "図解" in claude["description"] and "サムネイル" in claude["description"]
    assert "$run-x-visual-generate" in readme
    assert "4 skill" not in readme


def test_governance_dependency_matches_package_contract():
    claude = _json(".claude-plugin/plugin.json")
    package_contract = _json("references/package-contract.json")

    # harness-creator は skills/run-skill-feedback/ の owned-vendored 元。
    # 実体コピーで持つ以上、所有者を依存として宣言しないと出所が追えなくなる。
    assert package_contract["depends_on"] == claude["dependencies"] == [
        "harness-creator",
        "skill-governance-adapters",
    ]


def test_runtime_paths_use_prompts_and_env_only_output_resolution():
    skill = _text("skills/run-x-longpost-create/SKILL.md")
    resource_yaml = _text("skills/run-x-longpost-create/references/resource-map.yaml")
    resource_md = _text("skills/run-x-longpost-create/references/resource-map.md")
    output_config = _json("skills/run-x-longpost-create/references/output-config.json")

    combined = "\n".join((skill, resource_yaml, resource_md))
    assert "${CLAUDE_PLUGIN_ROOT}/agents" not in combined
    assert "defaults.vaultRoot" not in combined
    assert "agents / scripts" not in combined
    assert "agents 11" not in combined
    assert "${CLAUDE_PLUGIN_ROOT}/prompts" in skill
    assert output_config["resolutionOrder"] == [
        "XLP_OUTPUT_DIR (出力ディレクトリを直接指定)",
        "XLP_VAULT_ROOT (vault ルート。出力先は ${XLP_VAULT_ROOT}/05_Project/X)",
    ]
    assert "defaults" not in output_config


def test_composition_models_esm_logger_as_adapter_not_a_runtime_call():
    composition = _text("plugin-composition.yaml")
    longpost_skill = _text("skills/run-x-longpost-create/SKILL.md")
    assert "ref: scripts/log_usage.mjs" in composition
    assert "to: scripts/log_usage.mjs" not in composition
    assert "runtime adapter" in composition
    assert "../../scripts/log_usage.mjs" not in longpost_skill


def test_output_is_validated_under_the_final_basename_before_promotion():
    skill = _text("skills/run-x-longpost-create/SKILL.md")
    output_prompt = _text("prompts/x-longpost-output-file.md")

    assert "draft.md" not in skill + output_prompt
    assert "scratch" in skill.lower()
    assert "scratch" in output_prompt.lower()
    assert "正規 basename" in skill
    assert "正規 basename" in output_prompt
    assert "検証後" in skill and "正規配置" in skill


def test_visual_handoff_always_builds_two_thumbnails_and_keeps_diagram_optional():
    longpost_skill = _text("skills/run-x-longpost-create/SKILL.md")
    visual_skill = _text("skills/run-x-visual-generate/SKILL.md")
    diagram_prompt = _text("prompts/x-longpost-design-diagram-prompt.md")
    thumbnail_prompt = _text("prompts/x-longpost-design-thumbnail-prompt.md")

    assert "別セッション" in longpost_skill
    assert "--only x-thumb,note-thumb" in visual_skill
    assert "accept-as-is" in visual_skill and "2枚" in visual_skill
    assert "diagram" in visual_skill and "optional" in visual_skill.lower()
    assert "diagram.prompt.txt" in visual_skill
    assert "x-thumb.prompt.txt" in visual_skill
    assert "note-thumb.prompt.txt" in visual_skill
    assert "diagram,x-thumb" in visual_skill.split("---", 2)[1]
    assert "optional" in diagram_prompt.lower()
    assert "--only diagram" in diagram_prompt
    assert "並行して作る" not in diagram_prompt
    assert "標準" in thumbnail_prompt
    assert "--only x-thumb,note-thumb" in thumbnail_prompt


def test_visual_handoff_opens_recovered_image_on_both_supported_hosts():
    visual_skill = _text("skills/run-x-visual-generate/SKILL.md")
    output_config = _json("skills/run-x-longpost-create/references/output-config.json")

    assert "XLP_ATTACHMENT_DIR" in visual_skill
    assert "--attachment-dir" in visual_skill
    assert "Claude Code" in visual_skill and "Read" in visual_skill
    assert "Codex" in visual_skill and "view_image" in visual_skill
    assert "artifact_presented" in visual_skill
    assert "x-thumb" in visual_skill and "note-thumb" in visual_skill
    assert "record-thumbnail-review.js" in visual_skill
    assert "results[].presentation" in visual_skill
    assert "`presentations`" not in visual_skill
    assert output_config["paths"]["obsidianAttachmentDir"] == (
        "${XLP_VAULT_ROOT}/02_Configs/Extra"
    )


def test_visual_outputs_are_declared_by_the_plugin_contract():
    composition = _text("plugin-composition.yaml")

    contract_block = composition.split("contract:", 1)[1].split("capabilities:", 1)[0]
    for output in (
        "diagram.png",
        "x-thumb.png",
        "note-thumb.png",
        "投稿ファイルの図解・サムネイル欄更新",
    ):
        assert output in contract_block


def test_visual_composition_declares_review_receipt_runtime_dependency():
    composition = _text("plugin-composition.yaml")
    package_contract = _text("references/package-contract.json")

    assert "ref: scripts/record-thumbnail-review.js" in composition
    assert (
        "from: skills/run-x-visual-generate, to: scripts/record-thumbnail-review.js, type: calls"
        in composition
    )
    assert "review receipt" in package_contract.lower()


def test_visual_docs_follow_the_current_spec_and_gated_flow():
    resource_map = _text("skills/run-x-longpost-create/references/resource-map.md")
    changelog = _text("CHANGELOG.md")
    thumbnail_prompt = _text("prompts/x-longpost-design-thumbnail-prompt.md")

    assert "画風・アイコン語彙・サムネ寸法の正本（3本）" not in resource_map
    assert "visual-spec.json" in resource_map
    assert "27 テスト" not in changelog
    assert "寸法の三重定義" not in changelog
    assert "3つの `.prompt.txt` をまとめて処理" not in thumbnail_prompt
    assert "2560x1440" not in thumbnail_prompt
    assert "2560x1024" not in thumbnail_prompt
    assert "2560x1340" not in thumbnail_prompt


def test_text_validator_contract_is_declared_at_each_runtime_surface():
    skill = _text("skills/run-x-longpost-create/SKILL.md")
    composition = _text("plugin-composition.yaml")
    resource_map = _text("skills/run-x-longpost-create/references/resource-map.md")

    for text in (skill, composition, resource_map):
        assert "F4" in text and "F5" in text
    assert "A/B" in skill and "1文=1行" in skill


def test_evals_follow_current_release_without_erasing_baselines():
    evals = _json("EVALS.json")
    skills = [entry["skill"] for entry in evals["evaluations"]]

    assert evals["x_longpost_creator_version"] == "1.1.0"
    assert skills[:4] == [
        "run-x-longpost-create",
        "run-x-multipost-create",
        "run-x-shortpost-optimize",
        "ref-x-longpost-canon",
    ]
    assert "run-x-visual-generate" in skills
    assert not any("H10" in item for item in evals["known_limitations"])
    assert any(
        "H10" in entry["note"] and "FAIL" in entry["note"]
        for entry in evals["evaluations"]
    )


def test_canon_delegates_machine_rules_to_specs_and_scripts():
    canon = _text("skills/ref-x-longpost-canon/SKILL.md")

    assert "visual-spec.json" in canon
    assert "機械可読 spec/script が判定" in canon
    assert "スクリプトの実装値を正とする" not in canon

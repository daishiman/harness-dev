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


# plugin root の正規表記。Claude Code は CLAUDE_PLUGIN_ROOT を渡すが Codex は渡さない
# ので、Codex 側で解決した PLUGIN_ROOT を先に見る二段構えにしてある。
# `\$` はテンプレートリテラル内でのエスケープ形 (expand-template.js) を吸収する。
PLUGIN_ROOT_EXPR = re.compile(r"\\?\$\{PLUGIN_ROOT:-\\?\$\{CLAUDE_PLUGIN_ROOT\}\}")


def _normalize_plugin_root(text: str) -> str:
    """plugin root の表記を <ROOT> へ潰す。指し先だけを検査したいときに使う。"""
    return PLUGIN_ROOT_EXPR.sub("<ROOT>", text)


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


def test_governance_dependency_follows_repository_convention():
    """依存宣言が他 plugin の慣行から外れていないことを見る。

    この 2 層は同じ「依存」という語を使いながら別のものを指しており、内容も
    一致しない。

      - package-contract.json の depends_on: 設計上どの plugin に依っているか。
        run-skill-feedback の正本を持つ harness-creator は全 plugin が書く
      - plugin.json の dependencies: install 時に何を一緒に解決するか。
        run-skill-feedback は実体コピーなので単体で動き、harness-creator は不要

    両者が一致するものとして書くと、実体コピーで自己完結しているはずの plugin
    が install 時に所有者を引き連れる。期待値を直書きせず他 plugin から導出す
    るのは、慣行が動いたときにこの plugin だけ取り残される形を避けるためであ
    る。
    """
    claude = _json(".claude-plugin/plugin.json")
    package_contract = _json("references/package-contract.json")

    plugins_dir = ROOT / "plugins"
    others = [
        d for d in sorted(plugins_dir.iterdir())
        if d.is_dir() and d.name != "x-longpost-creator"
        and (d / ".claude-plugin" / "plugin.json").is_file()
    ]

    def _load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    # install 依存: 自分自身を依存に書けない adapters を除いた全 plugin が
    # 同一の集合を宣言している。その集合と一致すること。
    install_deps = {
        tuple(_load(d / ".claude-plugin" / "plugin.json").get("dependencies") or [])
        for d in others
        if _load(d / ".claude-plugin" / "plugin.json").get("dependencies")
    }
    assert len(install_deps) == 1, f"他 plugin の install 依存が割れている: {install_deps}"
    assert tuple(claude["dependencies"]) == next(iter(install_deps))

    # 設計依存: 全 plugin が harness-creator を書く (harness-creator 自身は除く)。
    for d in others:
        contract = d / "references" / "package-contract.json"
        if d.name == "harness-creator" or not contract.is_file():
            continue
        assert "harness-creator" in _load(contract)["depends_on"], (
            f"{d.name} が harness-creator を depends_on に書いていない (慣行が変わった可能性)"
        )
    assert "harness-creator" in package_contract["depends_on"]


def test_runtime_paths_use_prompts_and_env_only_output_resolution():
    skill = _text("skills/run-x-longpost-create/SKILL.md")
    resource_yaml = _text("skills/run-x-longpost-create/references/resource-map.yaml")
    resource_md = _text("skills/run-x-longpost-create/references/resource-map.md")
    output_config = _json("skills/run-x-longpost-create/references/output-config.json")

    combined = "\n".join((skill, resource_yaml, resource_md))
    # plugin root の表記は `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` の二段構えで、
    # ホストごとに与えられる変数が違うことを吸収している。ここで確かめたいのは
    # 「どの変数名で書いてあるか」ではなく「plugin root 起点でどこを指しているか」
    # なので、表記を潰してから相対部分だけを見る。表記を直書きすると、記法を変える
    # たびに指し先の検査まで巻き添えで落ちる。
    combined = _normalize_plugin_root(combined)
    assert "<ROOT>/agents" not in combined
    assert "defaults.vaultRoot" not in combined
    assert "agents / scripts" not in combined
    assert "agents 11" not in combined
    assert "<ROOT>/prompts" in _normalize_plugin_root(skill)
    assert output_config["resolutionOrder"] == [
        "XLP_OUTPUT_DIR (出力ディレクトリを直接指定)",
        "XLP_VAULT_ROOT (vault ルート。出力先は ${XLP_VAULT_ROOT}/05_Project/X)",
    ]
    assert "defaults" not in output_config


def test_plugin_root_is_always_written_in_the_host_neutral_form():
    """plugin root を Claude Code 専用の変数だけで書いた箇所が無いことを見る。

    `${CLAUDE_PLUGIN_ROOT}` は Claude Code が渡す変数で、Codex は渡さない。裸で
    書くと Codex では空文字へ展開され、`/prompts/...` という絶対パスを読みに行って
    静かに失敗する。落ちるのが実行時なので、書いた時点では気づけない。

    1 箇所でも裸で残ると「二段構えで書いてある」という README の申告が崩れるため、
    件数ではなく存在で判定する。指し先ではなく表記そのものを守る検査なので、ここ
    だけは _normalize_plugin_root を通さない。
    """
    # placeholder が現れうる面をすべて見る。scripts の .js も対象に含めるのは、
    # エラーメッセージや nextAction として利用者へ提示するパスが同じ規約に従う
    # 必要があるためである。
    suffixes = {".md", ".yaml", ".yml", ".json", ".js", ".mjs"}
    offenders = []
    for path in sorted(PLUGIN.rglob("*")):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        # CHANGELOG は過去の状態を記述する場所で、「旧記法を裸で書いていたのを直した」
        # と書くには旧記法を引用するほかない。ここを検査対象に含めると、何を直したかを
        # 書けなくなる。実行時に読まれるファイルではないので除外する。
        if path.name == "CHANGELOG.md":
            continue
        text = path.read_text(encoding="utf-8")
        if "CLAUDE_PLUGIN_ROOT" not in text:
            continue
        # 探すのは展開される `${...}` の形だけである。規約そのものを説明する散文
        # (README の「Claude Code は `CLAUDE_PLUGIN_ROOT` を渡す」など) は変数名を
        # 地の文で名指しているだけで、パスとして展開されることはない。
        # 正規表記を伏せ字にしてから探せば、残るのは裸で書かれたものだけになる。
        for lineno, line in enumerate(_normalize_plugin_root(text).splitlines(), 1):
            if "${CLAUDE_PLUGIN_ROOT}" in line:
                offenders.append(f"{path.relative_to(PLUGIN)}:{lineno}: {line.strip()}")

    assert not offenders, (
        "plugin root が Claude Code 専用の変数だけで書かれている箇所がある。\n"
        "`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` へ揃えること "
        "(テンプレートリテラル内では `\\${PLUGIN_ROOT:-\\${CLAUDE_PLUGIN_ROOT}}`)。\n  "
        + "\n  ".join(offenders)
    )


def test_runtime_root_contract_is_declared_where_skills_are_read():
    """各 skill が root 解決の規約を自分の中で宣言していることを見る。

    skill は 1 本ずつ独立に読まれる。README に書いてあっても、その skill だけを
    渡されたホストには届かない。frontmatter の宣言と本文の節を skill 側に持たせる
    ことで、読み手が root をどう解決すべきかを skill 単体から判断できる。
    """
    for skill_dir in sorted((PLUGIN / "skills").iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8")
        # 共通 skill (run-skill-feedback) は harness-creator が所有する正本の実体
        # コピーで、本 plugin の規約を後付けする対象ではない。
        if skill_dir.name == "run-skill-feedback":
            continue
        if "CLAUDE_PLUGIN_ROOT" not in text:
            continue
        assert "runtime_root_policy: host-skill-path" in text, (
            f"{skill_dir.name}/SKILL.md の frontmatter に runtime_root_policy が無い"
        )
        assert "## Runtime root contract" in text, (
            f"{skill_dir.name}/SKILL.md に Runtime root contract 節が無い"
        )


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

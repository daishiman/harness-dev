"""lint-prompt-contract-drift.py の検出ロジック回帰テスト。

7 層プロンプトの契約記述 (参照パス / allowed-tools) が実装と乖離する再発を
封じる lint そのものが腐らないよう、解決規約・除外規則・tier 分離を pytest で
機械保証する。CI の `python3 -m pytest tests/ -q` (harness-creator-kit-ci.yml)
が本ファイルを自動的に拾う。

検証する不変条件:
  Tier1 (参照パス実在):
    ①実在参照 → PASS   ②非実在参照 → drift
    ③../ 相対 (prompt-dir 起点) の自 skill 参照 → PASS
    ④$CLAUDE_PLUGIN_ROOT/ 前置 → plugin-root 解決 → PASS
    ⑤resource://<plugin>/... の plugin 共有参照 (PLUGINS_DIR base) → PASS
    ⑥任意/gitignore マーカー行 → 除外   ⑦placeholder (<>/foo) → 除外
    ⑧prose 列挙 (全 seg が dir token・拡張子なし) → 除外
  Tier2 (allowed-tools):
    ⑨prompt L3.2 ツール ⊆ SKILL.md allowed-tools → PASS
    ⑩宣言ツールが未 grant → drift   ⑪「Bash 不使用」否定 → 除外
    ⑫Task→Agent エイリアス正規化   ⑬allowed-tools 宣言なし → 非対象
  tier 分離:
    ⑭Tier1 は fatal (exit 1)   ⑮Tier2 単独は WARN (exit 0)
    ⑯--strict-tools で Tier2 も fatal (exit 1)

import 経路: dash 入り script のため importlib.util.spec_from_file_location
(test_lint_readme_plugin_root_portability.py のパターンに倣う)。
"""
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint-prompt-contract-drift.py"
SPEC = importlib.util.spec_from_file_location("lint_prompt_contract_drift", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def make_skill(tmp_path, allowed_tools=None, ref_files=(), plugin="demo-plugin", skill="demo-skill"):
    """tmp に plugins/<p>/skills/<s>/ の最小骨格を作り skill root を返す。"""
    skill_root = tmp_path / "plugins" / plugin / "skills" / skill
    (skill_root / "prompts").mkdir(parents=True)
    for rf in ref_files:
        p = skill_root / rf if not rf.startswith("plugin:") else (skill_root.parent.parent / rf[len("plugin:"):])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    if allowed_tools is not None:
        fm = "---\nname: %s\nallowed-tools: [%s]\n---\n# skill\n" % (skill, ", ".join(allowed_tools))
        (skill_root / "SKILL.md").write_text(fm, encoding="utf-8")
    return skill_root


def write_prompt(skill_root, body):
    p = skill_root / "prompts" / "R1.md"
    p.write_text(body, encoding="utf-8")
    return p


def t1(prompt_path):
    return MOD.check_tier1_referenced_paths(prompt_path, prompt_path.read_text(encoding="utf-8"))


def t2(prompt_path):
    return MOD.check_tier2_allowed_tools(prompt_path, prompt_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- Tier1
class TestTier1ReferencedPaths:
    def test_existing_ref_passes(self, tmp_path):  # ①
        sk = make_skill(tmp_path, ref_files=["references/exists.md"])
        p = write_prompt(sk, "本文 `references/exists.md` を読む。\n")
        assert t1(p) == []

    def test_missing_ref_drifts(self, tmp_path):  # ②
        sk = make_skill(tmp_path)
        p = write_prompt(sk, "本文 `references/missing-xyz-unique.md` を読む。\n")
        f = t1(p)
        assert len(f) == 1 and f[0]["ref"] == "references/missing-xyz-unique.md"

    def test_dotdot_relative_resolves_from_prompt_dir(self, tmp_path):  # ③
        sk = make_skill(tmp_path, ref_files=["schemas/x.json"])
        p = write_prompt(sk, "schema: `../schemas/x.json`\n")
        assert t1(p) == []

    def test_plugin_root_env_prefix_resolves(self, tmp_path):  # ④
        sk = make_skill(tmp_path, ref_files=["plugin:scripts/tool.py"])
        p = write_prompt(sk, "run `$CLAUDE_PLUGIN_ROOT/scripts/tool.py`\n")
        assert t1(p) == []

    def test_plugins_dir_base_resolves_shared_reference(self, tmp_path):  # ⑤
        # resource://<plugin>/references/X → plugins/<plugin>/references/X
        sk = make_skill(tmp_path, ref_files=["plugin:references/shared.md"])
        p = write_prompt(sk, "`resource://demo-plugin/references/shared.md`\n")
        assert t1(p) == []

    def test_optional_marker_line_excluded(self, tmp_path):  # ⑥
        sk = make_skill(tmp_path)
        p = write_prompt(sk, "- `references/gone.md` (任意。未配置なら markdown 可)\n")
        assert t1(p) == []

    def test_gitignore_marker_line_excluded(self, tmp_path):  # ⑥b
        sk = make_skill(tmp_path)
        p = write_prompt(sk, "- `references/params.json` (gitignore・未配備時 provision)\n")
        assert t1(p) == []

    def test_placeholder_excluded(self, tmp_path):  # ⑦
        sk = make_skill(tmp_path)
        p = write_prompt(sk, "`references/<id>.md` と `plugins/foo/bar.md`\n")
        assert t1(p) == []

    def test_glob_star_after_truncation_excluded(self, tmp_path):  # ⑦c
        # references/diagram-*.md は char class 外の * 手前で 'references/diagram-' に
        # 切り詰められ in-raw の placeholder 判定を素通りするが、捕捉境界の直後が glob 継続
        # 文字 (*) のため binding 不能としてスキップされ drift にならない (実ファイル不要)。
        sk = make_skill(tmp_path)
        p = write_prompt(sk, "| 図解 | `references/diagram-*.md` | 図解29種 |\n")
        assert t1(p) == []

    def test_prose_enumeration_helper(self):  # ⑧
        assert MOD._is_prose_dir_enumeration("prompts/schemas/references") is True
        assert MOD._is_prose_dir_enumeration("references/real.md") is False
        assert MOD._is_prose_dir_enumeration("schemas") is False


# ---------------------------------------------------------------- Tier2
def _l32(tool_line):
    return "## Layer 3\n### 3.2 外部ツール / API\n%s\n## Layer 4\n" % tool_line


class TestTier2AllowedTools:
    def test_subset_passes(self, tmp_path):  # ⑨
        sk = make_skill(tmp_path, allowed_tools=["Read", "Grep"])
        p = write_prompt(sk, _l32("- Read / Grep のみ。"))
        assert t2(p) == []

    def test_undeclared_tool_drifts(self, tmp_path):  # ⑩
        sk = make_skill(tmp_path, allowed_tools=["Read"])
        p = write_prompt(sk, _l32("- Read / Grep のみ。"))
        f = t2(p)
        assert len(f) == 1 and f[0]["ref"] == "Grep" and f[0]["tier"] == 2

    def test_negation_excluded(self, tmp_path):  # ⑪
        sk = make_skill(tmp_path, allowed_tools=["Read"])
        p = write_prompt(sk, _l32("- Read のみ。Bash 不使用。"))
        assert t2(p) == []

    def test_task_agent_alias(self, tmp_path):  # ⑫
        sk = make_skill(tmp_path, allowed_tools=["Agent"])
        p = write_prompt(sk, _l32("- Task で SubAgent を fork。"))
        assert t2(p) == []

    def test_no_allowed_tools_declaration_skips(self, tmp_path):  # ⑬
        sk = tmp_path / "plugins" / "p" / "skills" / "s"
        (sk / "prompts").mkdir(parents=True)
        (sk / "SKILL.md").write_text("---\nname: s\n---\n# no allowed-tools\n", encoding="utf-8")
        p = write_prompt(sk, _l32("- Read / Grep のみ。"))
        assert t2(p) == []

    def test_region_scoped_outside_l32_ignored(self, tmp_path):
        # 外部ツール節の外に現れる tool 名は検出しない (region 限定)
        sk = make_skill(tmp_path, allowed_tools=["Read"])
        p = write_prompt(sk, "## Layer 5\n- Grep で走査する説明文。\n")
        assert t2(p) == []


# ---------------------------------------------------------------- tier 分離 / exit code
class TestTierSeparationExit:
    def test_tier1_is_fatal(self, tmp_path):  # ⑭
        sk = make_skill(tmp_path, allowed_tools=["Read"])
        p = write_prompt(sk, "`references/missing-unique-abc.md`\n")
        assert MOD.main(["prog", str(p)]) == 1

    def test_tier2_only_is_warn_not_fatal(self, tmp_path):  # ⑮
        sk = make_skill(tmp_path, allowed_tools=["Read"])
        p = write_prompt(sk, _l32("- Read / Grep のみ。"))
        assert MOD.main(["prog", str(p)]) == 0

    def test_strict_tools_promotes_tier2(self, tmp_path):  # ⑯
        sk = make_skill(tmp_path, allowed_tools=["Read"])
        p = write_prompt(sk, _l32("- Read / Grep のみ。"))
        assert MOD.main(["prog", "--strict-tools", str(p)]) == 1


# ---------------------------------------------------------------- allowed-tools parser
class TestAllowedToolsParser:
    def test_inline_list_form(self, tmp_path):
        sk = make_skill(tmp_path, allowed_tools=["Read", "Bash(python3 *)"])
        assert MOD._parse_skill_allowed_tools(sk) == {"Read", "Bash"}

    def test_block_list_form(self, tmp_path):
        sk = tmp_path / "plugins" / "p" / "skills" / "s"
        sk.mkdir(parents=True)
        (sk / "SKILL.md").write_text(
            "---\nname: s\nallowed-tools:\n  - Read\n  - Task\n---\n#\n", encoding="utf-8"
        )
        assert MOD._parse_skill_allowed_tools(sk) == {"Read", "Agent"}

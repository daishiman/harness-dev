"""lint-plugin-lint-coverage.py のメタ検査ロジック回帰テスト。

elegant-review finding (per-plugin 手書き配線による新 plugin 追加時の lint 被覆
漏れ) の再発防止器そのものが腐らないよう、被覆検出 / allowlist / 非対象判定の
分岐を pytest で機械保証する。CI の `python3 -m pytest tests/ -q`
(harness-creator-kit-ci.yml) が本ファイルを自動的に拾う。

検証する不変条件:
  - 被覆抽出: Makefile / workflow yml の `--skills-dir plugins/<name>/skills`
    配線 (backslash 継続・YAML 複数行 run 含む) を検出する
  - 非対象判定: skills/ 無し plugin・symlink 共有のみの plugin は被覆要求外
  - 未被覆 plugin は plugin 名 + 修正方法付きでエラーになる (fail-closed)
  - allowlist: 理由付きエントリで例外化でき、空理由 / stale エントリはエラー
  - 実 repo 統合: 現状の被覆マトリクスで exit 0

import 経路: dash 入り script のため importlib.util.spec_from_file_location
(test_build_claude_symlinks.py のパターンに倣う)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint-plugin-lint-coverage.py"
SPEC = importlib.util.spec_from_file_location("lint_plugin_lint_coverage", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def make_repo(
    tmp_path: Path,
    plugins: dict[str, list[str]],
    makefile: str = "",
    workflow: str = "",
    symlink_skills: dict[str, list[tuple[str, str]]] | None = None,
) -> Path:
    """最小の repo 構造を組み立てる。

    plugins: {plugin名: [実体skill名, ...]} (空リスト = skills/ 無し)
    symlink_skills: {plugin名: [(skill名, link先相対パス), ...]}
    """
    root = tmp_path / "repo"
    (root / ".claude-plugin").mkdir(parents=True)
    entries = [{"name": name, "source": f"./plugins/{name}"} for name in plugins]
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "fixture", "plugins": entries}), encoding="utf-8"
    )
    for name, skills in plugins.items():
        plugin_dir = root / "plugins" / name
        plugin_dir.mkdir(parents=True)
        if skills:
            for skill in skills:
                skill_dir = plugin_dir / "skills" / skill
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(
                    f"---\nname: {skill}\n---\n", encoding="utf-8"
                )
    for name, links in (symlink_skills or {}).items():
        skills_dir = root / "plugins" / name / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        for skill, target in links:
            (skills_dir / skill).symlink_to(target)
    (root / "Makefile").write_text(makefile, encoding="utf-8")
    if workflow:
        wf_dir = root / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(workflow, encoding="utf-8")
    return root


FULL_MAKEFILE = """lint:
\tpython3 scripts/lint-skill-name.py --skills-dir plugins/alpha/skills
\tpython3 scripts/lint-skill-description.py --skills-dir plugins/alpha/skills
\tpython3 scripts/validate-frontmatter.py --skills-dir plugins/alpha/skills
"""


class TestCoverageDetection:
    def test_fully_covered_plugin_passes(self, tmp_path):
        root = make_repo(tmp_path, {"alpha": ["run-a"]}, makefile=FULL_MAKEFILE)
        errors, report = MOD.check_coverage(root, allowlist={})
        assert errors == []
        assert any("alpha" in line and "covered" in line for line in report)

    def test_uncovered_plugin_fails_with_name_and_fix(self, tmp_path):
        root = make_repo(
            tmp_path, {"alpha": ["run-a"], "beta": ["run-b"]}, makefile=FULL_MAKEFILE
        )
        errors, _ = MOD.check_coverage(root, allowlist={})
        # beta は 3 lint 種別すべて未被覆
        beta_errors = [e for e in errors if e.startswith("beta:")]
        assert len(beta_errors) == len(MOD.LINT_KINDS)
        # 修正方法 (配線追加 or allowlist) がエラーメッセージに含まれる
        assert all("--skills-dir plugins/beta/skills" in e for e in beta_errors)
        assert all("ALLOWLIST" in e for e in beta_errors)

    def test_partial_coverage_flags_only_missing_kind(self, tmp_path):
        makefile = FULL_MAKEFILE + (
            "\tpython3 scripts/lint-skill-name.py --skills-dir plugins/beta/skills\n"
            "\tpython3 scripts/lint-skill-description.py --skills-dir plugins/beta/skills\n"
        )
        root = make_repo(
            tmp_path, {"alpha": ["run-a"], "beta": ["run-b"]}, makefile=makefile
        )
        errors, _ = MOD.check_coverage(root, allowlist={})
        assert len(errors) == 1
        assert "beta" in errors[0] and "frontmatter" in errors[0]

    def test_workflow_yaml_coverage_counts(self, tmp_path):
        workflow = """jobs:
  check:
    steps:
      - name: beta frontmatter
        run: python3 plugins/lint/scripts/validate-frontmatter.py --skills-dir plugins/beta/skills
      - name: beta name
        run: python3 plugins/lint/scripts/lint-skill-name.py --skills-dir plugins/beta/skills
      - name: beta description (継続行)
        run: python3 plugins/lint/scripts/lint-skill-description.py \\
               --skills-dir plugins/beta/skills
"""
        root = make_repo(
            tmp_path,
            {"alpha": ["run-a"], "beta": ["run-b"]},
            makefile=FULL_MAKEFILE,
            workflow=workflow,
        )
        errors, _ = MOD.check_coverage(root, allowlist={})
        assert errors == []

    def test_multiline_run_block_next_line_counts(self, tmp_path):
        # YAML の run: | で script 行の直後行に --skills-dir が来るパターン
        workflow = """jobs:
  check:
    steps:
      - name: beta all
        run: |
          python3 scripts/lint-skill-name.py
          --skills-dir plugins/beta/skills
          python3 scripts/lint-skill-description.py --skills-dir plugins/beta/skills
          python3 scripts/validate-frontmatter.py --skills-dir plugins/beta/skills
"""
        root = make_repo(
            tmp_path, {"beta": ["run-b"]}, makefile="", workflow=workflow
        )
        errors, _ = MOD.check_coverage(root, allowlist={})
        assert errors == []


class TestExemption:
    def test_plugin_without_skills_dir_not_required(self, tmp_path):
        root = make_repo(
            tmp_path, {"alpha": ["run-a"], "no-skills": []}, makefile=FULL_MAKEFILE
        )
        errors, report = MOD.check_coverage(root, allowlist={})
        assert errors == []
        assert not any("no-skills" in line for line in report)

    def test_symlink_only_plugin_not_required(self, tmp_path):
        # 共有 skill の symlink しか持たない plugin は実体所有 0 → 被覆要求外
        # (PKG-003 と同じ「実体のみ所有カウント」原則)
        root = make_repo(
            tmp_path,
            {"alpha": ["run-a"], "linker": []},
            makefile=FULL_MAKEFILE,
            symlink_skills={
                "linker": [("run-shared", "../../alpha/skills/run-a")]
            },
        )
        errors, report = MOD.check_coverage(root, allowlist={})
        assert errors == []
        assert not any(line.startswith("linker:") for line in report)


class TestAllowlist:
    def test_allowlisted_kind_passes(self, tmp_path):
        makefile = FULL_MAKEFILE + (
            "\tpython3 scripts/lint-skill-name.py --skills-dir plugins/beta/skills\n"
            "\tpython3 scripts/lint-skill-description.py --skills-dir plugins/beta/skills\n"
        )
        root = make_repo(
            tmp_path, {"alpha": ["run-a"], "beta": ["run-b"]}, makefile=makefile
        )
        allowlist = {("beta", "frontmatter"): "lint FAIL のため後日是正 (fixture)"}
        errors, report = MOD.check_coverage(root, allowlist=allowlist)
        assert errors == []
        assert any("frontmatter=allowlisted" in line for line in report)

    def test_allowlist_requires_reason(self, tmp_path):
        root = make_repo(tmp_path, {"alpha": ["run-a"]}, makefile=FULL_MAKEFILE)
        errors, _ = MOD.check_coverage(
            root, allowlist={("beta", "frontmatter"): "  "}
        )
        assert any("理由" in e for e in errors)

    def test_allowlist_rejects_unknown_kind(self, tmp_path):
        root = make_repo(tmp_path, {"alpha": ["run-a"]}, makefile=FULL_MAKEFILE)
        errors, _ = MOD.check_coverage(
            root, allowlist={("beta", "no-such-lint"): "reason"}
        )
        assert any("lint 種別が不正" in e for e in errors)

    def test_stale_allowlist_entry_fails(self, tmp_path):
        # 被覆済みなのに allowlist に残っているエントリは掃除を強制する
        root = make_repo(tmp_path, {"alpha": ["run-a"]}, makefile=FULL_MAKEFILE)
        allowlist = {("alpha", "frontmatter"): "もう不要のはずの理由"}
        errors, _ = MOD.check_coverage(root, allowlist=allowlist)
        assert any("stale" in e for e in errors)


class TestRealAllowlistHygiene:
    def test_real_allowlist_reasons_nonempty(self):
        for (plugin, kind), reason in MOD.ALLOWLIST.items():
            assert kind in MOD.LINT_KINDS, (plugin, kind)
            assert str(reason).strip(), f"({plugin}, {kind}) の理由が空"


class TestRealRepoIntegration:
    def test_real_repo_coverage_passes(self):
        """実 repo の被覆マトリクスが合格状態であること (配線 drift の回帰検知)。"""
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(ROOT)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"

    def test_usage_error_on_bad_root(self, tmp_path):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 2

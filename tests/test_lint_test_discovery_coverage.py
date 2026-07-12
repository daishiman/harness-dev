"""discover_repo_tests.py / lint-test-discovery-coverage.py の回帰テスト。

elegant-review finding (2026-06-30, 3 analyst 収束 LS-F1 / SS-02 / SS-05):
  「repo 全域の全 test が CI で 1 回以上実行される」機械保証が不在で、tests/・plugins/
  以外 (scripts/・doc/・repo-root 直下) に置いた test が無言で未実行になりうる。
  その再発防止器 (orphan を fail-closed 検出する lint) 自体が腐らないよう、探索 /
  到達判定 / orphan 検出 / CI 実行証跡 / allowlist の分岐を pytest で機械保証する。
  CI の `python3 -m pytest tests/ -q` (harness-creator-kit-ci.yml 機構A) が本ファイルを自動収集する。

検証する不変条件:
  - discover_test_files: test_*.py / *_test.py を収集し除外 dir (.git/vendor 等) を剪定
  - is_ci_reachable / orphan_test_files: 先頭成分が tests/・plugins/ 以外 = orphan
  - group_plugin_tests: 機構B の per-plugin グルーピング (tests/ 配下/colocate 双方)
  - lint check_orphans: orphan で fail / clean で ok / allowlist 空理由・stale で fail
  - lint check_ci_runs_roots: 実行証跡欠落で fail / 揃えば ok / CI yml 不在で skip
  - 実 repo 統合: 現状 orphan=0 で lint exit 0
"""
import importlib.util
import subprocess
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "discover_repo_tests.py"
LINT = ROOT / "scripts" / "lint-test-discovery-coverage.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DRT = _load("discover_repo_tests", MODULE)
LINTMOD = _load("lint_test_discovery_coverage", LINT)


def make_repo(tmp_path: Path, files: list[str], ci_yml: str | None = None) -> Path:
    """files (repo-relative posix) を空 test として配置した最小 repo を作る。"""
    root = tmp_path / "repo"
    for rel in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    if ci_yml is not None:
        wf = root / ".github" / "workflows" / "harness-creator-kit-ci.yml"
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text(ci_yml, encoding="utf-8")
    return root


# harness-creator-kit-ci.yml の到達 root 実行証跡 (機構A + 機構B) を満たす最小 yml。
GOOD_CI = """jobs:
  verify:
    steps:
      - run: python3 -m pytest tests/ plugins/skill-governance-lint/tests/ -q
      - run: |
          root = Path("plugins")
          subprocess.run([sys.executable, "-m", "pytest", *args, "-q"], cwd=test_root)
"""


class TestDiscovery:
    def test_finds_test_files_both_patterns(self, tmp_path):
        root = make_repo(
            tmp_path,
            ["tests/test_a.py", "plugins/foo/tests/b_test.py", "tests/helpers.py"],
        )
        found = {str(p) for p in DRT.discover_test_files(root)}
        assert "tests/test_a.py" in found  # test_*.py
        assert "plugins/foo/tests/b_test.py" in found  # *_test.py
        assert "tests/helpers.py" not in found  # どちらのパターンにも非一致

    def test_prunes_excluded_dirs(self, tmp_path):
        root = make_repo(
            tmp_path,
            [
                "tests/test_keep.py",
                "plugins/foo/vendor/test_skip.py",
                "node_modules/pkg/test_skip2.py",
                "plugins/foo/__pycache__/test_skip3.py",
            ],
        )
        found = {str(p) for p in DRT.discover_test_files(root)}
        assert found == {"tests/test_keep.py"}

    def test_is_ci_reachable(self):
        assert DRT.is_ci_reachable(PurePosixPath("tests/test_a.py"))
        assert DRT.is_ci_reachable(PurePosixPath("plugins/foo/tests/test_b.py"))
        assert not DRT.is_ci_reachable(PurePosixPath("scripts/test_c.py"))
        assert not DRT.is_ci_reachable(PurePosixPath("test_root_level.py"))

    def test_orphan_detection(self, tmp_path):
        root = make_repo(
            tmp_path,
            [
                "tests/test_ok.py",
                "plugins/foo/tests/test_ok2.py",
                "scripts/test_orphan.py",
                "doc/some_test.py",
            ],
        )
        orphans = {str(p) for p in DRT.orphan_test_files(root)}
        assert orphans == {"scripts/test_orphan.py", "doc/some_test.py"}

    def test_group_plugin_tests_tests_dir_and_colocated(self, tmp_path):
        root = make_repo(
            tmp_path,
            [
                "plugins/foo/skills/run-x/tests/test_a.py",
                "plugins/foo/scripts/test_colocated.py",
                "tests/test_ignored_by_grouping.py",
            ],
        )
        groups = DRT.group_plugin_tests(root)
        # tests/ 配下は tests/ の親が test_root
        assert groups["plugins/foo/skills/run-x"] == ["tests/test_a.py"]
        # colocate (tests/ 無し) は自身の親が test_root
        assert groups["plugins/foo/scripts"] == ["test_colocated.py"]
        # tests/ (repo-root) は機構B (plugins walk) の対象外
        assert all(not k.startswith("tests") for k in groups)

    def test_cli_modes(self, tmp_path):
        root = make_repo(tmp_path, ["tests/test_a.py", "scripts/test_orphan.py"])
        assert DRT.main(["--repo-root", str(root), "--list"]) == 0
        assert DRT.main(["--repo-root", str(root), "--orphans"]) == 0
        assert DRT.main(["--repo-root", str(root), "--ci-plan"]) == 0
        assert DRT.main(["--repo-root", str(root), "--json"]) == 0
        assert DRT.main(["--repo-root", str(root), "--bogus"]) == 2
        assert DRT.main(["--repo-root"]) == 2  # 引数欠落


class TestLintOrphans:
    def test_clean_repo_passes(self, tmp_path):
        root = make_repo(tmp_path, ["tests/test_a.py", "plugins/foo/tests/test_b.py"])
        errors, report = LINTMOD.check_orphans(root, allowlist={})
        assert errors == []
        assert any("orphan 0" in line for line in report)

    def test_orphan_fails_with_fix_hint(self, tmp_path):
        root = make_repo(tmp_path, ["tests/test_a.py", "scripts/test_orphan.py"])
        errors, _ = LINTMOD.check_orphans(root, allowlist={})
        assert len(errors) == 1
        assert "scripts/test_orphan.py" in errors[0]
        assert "tests/ または plugins/" in errors[0]

    def test_allowlist_suppresses_orphan(self, tmp_path):
        root = make_repo(tmp_path, ["scripts/test_orphan.py"])
        allow = {"scripts/test_orphan.py": "手動専用 fixture のため CI 非実行 (fixture)"}
        errors, _ = LINTMOD.check_orphans(root, allowlist=allow)
        assert errors == []

    def test_allowlist_requires_reason(self, tmp_path):
        root = make_repo(tmp_path, ["scripts/test_orphan.py"])
        errors, _ = LINTMOD.check_orphans(root, allowlist={"scripts/test_orphan.py": "  "})
        assert any("理由が無い" in e for e in errors)

    def test_stale_allowlist_entry_fails(self, tmp_path):
        # 到達集合内 (= orphan でない) パスを allowlist に残すと stale エラー
        root = make_repo(tmp_path, ["tests/test_a.py"])
        errors, _ = LINTMOD.check_orphans(root, allowlist={"tests/test_a.py": "不要な理由"})
        assert any("stale" in e for e in errors)


class TestLintCiRunsRoots:
    def test_good_ci_passes(self, tmp_path):
        root = make_repo(tmp_path, ["tests/test_a.py"], ci_yml=GOOD_CI)
        errors, report = LINTMOD.check_ci_runs_roots(root)
        assert errors == []
        assert any("CI runs 'tests/'" in line for line in report)
        assert any("CI runs 'plugins/'" in line for line in report)

    def test_missing_mechanism_fails(self, tmp_path):
        # 機構B (plugins walk) を欠いた CI yml
        bad_ci = "jobs:\n  verify:\n    steps:\n      - run: python3 -m pytest tests/ -q\n"
        root = make_repo(tmp_path, ["tests/test_a.py"], ci_yml=bad_ci)
        errors, _ = LINTMOD.check_ci_runs_roots(root)
        assert any("plugins/" in e for e in errors)

    def test_absent_ci_yml_skips(self, tmp_path):
        root = make_repo(tmp_path, ["tests/test_a.py"])  # ci_yml 無し
        errors, report = LINTMOD.check_ci_runs_roots(root)
        assert errors == []
        assert any("skip" in line for line in report)


class TestEvidenceParity:
    def test_real_config_parity_holds(self):
        # 実 config: CI_RUN_EVIDENCE のキー == CI_REACHABLE_TOP_LEVEL
        errors, report = LINTMOD.check_evidence_parity()
        assert errors == []
        assert any("evidence parity: OK" in line for line in report)

    def test_drift_detected(self, monkeypatch):
        # CI_REACHABLE_TOP_LEVEL に root を足したが CI_RUN_EVIDENCE 追加を忘れた drift。
        # lint が実際に参照する drt インスタンス (LINTMOD.drt) を patch する
        # (importlib で別ロードした DRT とは別オブジェクトのため)。
        monkeypatch.setattr(LINTMOD.drt, "CI_REACHABLE_TOP_LEVEL", ("tests", "plugins", "extra"))
        errors, _ = LINTMOD.check_evidence_parity()
        assert any("不一致" in e and "extra" in e for e in errors)


class TestLintMain:
    def test_main_exit0_on_clean(self, tmp_path):
        root = make_repo(tmp_path, ["tests/test_a.py", "plugins/foo/tests/test_b.py"], ci_yml=GOOD_CI)
        assert LINTMOD.main(["--repo-root", str(root)]) == 0

    def test_main_exit1_on_orphan(self, tmp_path):
        root = make_repo(tmp_path, ["scripts/test_orphan.py"], ci_yml=GOOD_CI)
        assert LINTMOD.main(["--repo-root", str(root)]) == 1

    def test_main_usage_error(self):
        assert LINTMOD.main(["--repo-root"]) == 2


class TestRealAllowlistHygiene:
    def test_real_allowlist_reasons_nonempty(self):
        for rel, reason in LINTMOD.ALLOWLIST.items():
            assert str(reason).strip(), f"{rel} の理由が空"


class TestRealRepoIntegration:
    def test_real_repo_lint_passes(self):
        """実 repo で全 test が CI 到達 (orphan=0) であることの回帰検知。"""
        proc = subprocess.run(
            [sys.executable, str(LINT), "--repo-root", str(ROOT)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"

    def test_real_repo_module_orphans_empty(self):
        assert DRT.orphan_test_files(ROOT) == []

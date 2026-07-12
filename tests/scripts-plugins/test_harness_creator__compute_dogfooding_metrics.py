"""plugins/harness-creator/scripts/compute-dogfooding-metrics.py の genuine 機能テスト。

dogfooding メトリクス集計スクリプトの 6 メトリクス純関数 + collect_all + upsert_evals +
main(CLI) の全分岐を tmp_path fixture で網羅する。git/yaml への依存は実 git リポジトリを
tmp_path に作って実通信なしで再現、または monkeypatch で _git を stub して経路を確定する。

カバー分岐:
- _git: 成功 / 失敗(コマンド異常)で None
- compute_lessons_per_pr: lessons-learned 無 / 有(.md/.json) / git None / pr_count=0 / ratio 計算
- compute_review_cycle_time_ms: dir 無 / frontmatter 無 / date 無 / 不正date / commit 無 / 正常平均
- _parse_iso: 各 fmt / fromisoformat fallback(Z) / 解析不能 None
- compute_rubric_bump_frequency: rubric 無 / git None / version 変更カウント
- _load_yaml_capabilities + compute_capability_count_by_kind: yaml有/簡易parser/未知kind/inline形式
- compute_hook_wired_count: ファイル無 / 不正JSON / list形 / dict形 / hooks 無
- compute_rubric_kind_coverage: rubric 無 / 不正JSON skip / applies_to_kinds / rules[].applies_to_kinds
- collect_all: 全キー存在
- upsert_evals: 新規作成 / 既存マージ / 既存不正JSON リセット
- main: --self-test / --dry-run / 通常(EVALS書込) / 例外非ブロック exit0

network: false, keychain: なし, 実 repo 書換: なし(全 tmp_path)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "harness-creator" / "scripts" / "compute-dogfooding-metrics.py"

SPEC = importlib.util.spec_from_file_location("compute_dogfooding_metrics_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ── tmp git repo ヘルパ ───────────────────────────────────────────────────────
def _init_git(repo: Path):
    """tmp_path に最小 git リポジトリを用意(実通信なし)。"""
    env_args = dict(check=True, capture_output=True, text=True, cwd=str(repo))
    subprocess.run(["git", "init", "-q"], **env_args)
    subprocess.run(["git", "config", "user.email", "t@t.t"], **env_args)
    subprocess.run(["git", "config", "user.name", "t"], **env_args)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], **env_args)


def _commit_all(repo: Path, msg: str = "c"):
    env_args = dict(check=True, capture_output=True, text=True, cwd=str(repo))
    subprocess.run(["git", "add", "-A"], **env_args)
    subprocess.run(["git", "commit", "-q", "-m", msg], **env_args)


# ── _git ─────────────────────────────────────────────────────────────────────
def test_git_success(tmp_path):
    _init_git(tmp_path)
    out = MOD._git(["rev-parse", "--is-inside-work-tree"], tmp_path)
    assert out is not None
    assert "true" in out


def test_git_failure_returns_none(tmp_path):
    # git リポジトリでないディレクトリで log → エラー → None
    out = MOD._git(["log"], tmp_path)
    assert out is None


# ── _parse_iso ───────────────────────────────────────────────────────────────
def test_parse_iso_date_only():
    dt = MOD._parse_iso("2026-06-24")
    assert dt is not None and dt.year == 2026 and dt.tzinfo is not None


def test_parse_iso_datetime_no_tz_gets_utc():
    dt = MOD._parse_iso("2026-06-24T10:00:00")
    assert dt is not None and dt.tzinfo is not None


def test_parse_iso_datetime_with_tz():
    dt = MOD._parse_iso("2026-06-24T10:00:00+0000")
    assert dt is not None and dt.tzinfo is not None


def test_parse_iso_fromisoformat_z_fallback():
    dt = MOD._parse_iso("2026-06-24T10:00:00.500Z")
    assert dt is not None


def test_parse_iso_unparseable_returns_none():
    assert MOD._parse_iso("not-a-date") is None


# ── compute_lessons_per_pr ───────────────────────────────────────────────────
def test_lessons_per_pr_no_dir(tmp_path):
    _init_git(tmp_path)
    res = MOD.compute_lessons_per_pr(tmp_path)
    assert res["lessons_count"] == 0
    assert res["pr_merge_count"] == 0
    assert res["ratio"] == 0.0


def test_lessons_per_pr_counts_files_and_zero_pr(tmp_path):
    _init_git(tmp_path)
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    (ld / "a.md").write_text("x", encoding="utf-8")
    (ld / "b.json").write_text("{}", encoding="utf-8")
    (ld / "ignore.txt").write_text("x", encoding="utf-8")  # 対象外 suffix
    res = MOD.compute_lessons_per_pr(tmp_path)
    assert res["lessons_count"] == 2  # .txt 除外
    # マージコミットなし → pr_count 0 → ratio 0.0
    assert res["pr_merge_count"] == 0
    assert res["ratio"] == 0.0


def test_lessons_per_pr_git_none_branch(tmp_path):
    # git でないディレクトリ → log None → 早期 return
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    (ld / "a.md").write_text("x", encoding="utf-8")
    res = MOD.compute_lessons_per_pr(tmp_path)
    assert res["lessons_count"] == 1
    assert res["pr_merge_count"] == 0
    assert res["ratio"] == 0.0


def test_lessons_per_pr_ratio_with_merge(tmp_path, monkeypatch):
    # _git を stub して 2 マージコミット相当を返し ratio を確定計算
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    (ld / "a.md").write_text("x", encoding="utf-8")
    (ld / "b.md").write_text("x", encoding="utf-8")
    (ld / "c.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(MOD, "_git", lambda args, cwd: "h1\nh2\n")
    res = MOD.compute_lessons_per_pr(tmp_path)
    assert res["lessons_count"] == 3
    assert res["pr_merge_count"] == 2
    assert res["ratio"] == 1.5


# ── compute_review_cycle_time_ms ─────────────────────────────────────────────
def test_review_cycle_no_dir(tmp_path):
    assert MOD.compute_review_cycle_time_ms(tmp_path) is None


def test_review_cycle_no_diffs_when_no_frontmatter(tmp_path):
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    (ld / "plain.md").write_text("no frontmatter here", encoding="utf-8")
    assert MOD.compute_review_cycle_time_ms(tmp_path) is None


def test_review_cycle_no_date_field(tmp_path):
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    (ld / "fm.md").write_text("---\ntitle: x\n---\nbody\n", encoding="utf-8")
    assert MOD.compute_review_cycle_time_ms(tmp_path) is None


def test_review_cycle_bad_date(tmp_path):
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    (ld / "fm.md").write_text("---\ndate: not-a-date\n---\nbody\n", encoding="utf-8")
    assert MOD.compute_review_cycle_time_ms(tmp_path) is None


def test_review_cycle_commit_missing(tmp_path, monkeypatch):
    # frontmatter date あり、ただし _git が None(commit 取得失敗)→ diffs 空 → None
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    (ld / "fm.md").write_text("---\ndate: '2026-06-24'\n---\nbody\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "_git", lambda args, cwd: None)
    assert MOD.compute_review_cycle_time_ms(tmp_path) is None


def test_review_cycle_unreadable_file_skipped(tmp_path, monkeypatch):
    # read_text が例外を投げるファイルは continue でスキップ → diffs 空 → None
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    bad = ld / "fm.md"
    bad.write_text("---\ndate: '2026-06-24'\n---\nbody\n", encoding="utf-8")
    orig_read = Path.read_text

    def boom(self, *a, **k):
        if self == bad:
            raise OSError("cannot read")
        return orig_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", boom)
    assert MOD.compute_review_cycle_time_ms(tmp_path) is None


def test_review_cycle_commit_unparseable_skipped(tmp_path, monkeypatch):
    # commit log が parse 不能 → commit_dt None → diffs 空 → None
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    (ld / "fm.md").write_text("---\ndate: '2026-06-24T00:00:00'\n---\nbody\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "_git", lambda args, cwd: "garbage-not-a-date")
    assert MOD.compute_review_cycle_time_ms(tmp_path) is None


def test_review_cycle_computes_average_ms(tmp_path, monkeypatch):
    ld = tmp_path / "lessons-learned"
    ld.mkdir()
    (ld / "fm.md").write_text("---\ndate: '2026-06-24T00:00:00'\n---\nbody\n", encoding="utf-8")
    # commit 時刻を date より 1 時間後に
    monkeypatch.setattr(MOD, "_git", lambda args, cwd: "2026-06-24T01:00:00+00:00")
    ms = MOD.compute_review_cycle_time_ms(tmp_path)
    assert ms == 3600 * 1000


# ── compute_rubric_bump_frequency ────────────────────────────────────────────
def test_rubric_bump_no_files(tmp_path):
    res = MOD.compute_rubric_bump_frequency(tmp_path)
    assert res["window_days"] == 30
    assert res["total_bumps"] == 0
    assert res["per_file"] == {}


def test_rubric_bump_git_none(tmp_path):
    # rubric file は存在するが git でないディレクトリ → log None → per_file=0
    rf = tmp_path / "skills" / "ref-x-rubric" / "v1" / "rubric.json"
    rf.parent.mkdir(parents=True)
    rf.write_text('{"version": 1}', encoding="utf-8")
    res = MOD.compute_rubric_bump_frequency(tmp_path)
    rel = "skills/ref-x-rubric/v1/rubric.json"
    assert res["per_file"][rel] == 0
    assert res["total_bumps"] == 0


def test_rubric_bump_counts_version_commits(tmp_path, monkeypatch):
    rf = tmp_path / "skills" / "ref-x-rubric" / "rubric.json"
    rf.parent.mkdir(parents=True)
    rf.write_text('{"version": 1}', encoding="utf-8")

    calls = {"n": 0}

    def fake_git(args, cwd):
        # 2 回目(-G "version" 付き)で 2 コミットを返す
        if "-G" in args:
            return "h1\nh2\n"
        return "h1\n"

    monkeypatch.setattr(MOD, "_git", fake_git)
    res = MOD.compute_rubric_bump_frequency(tmp_path)
    rel = "skills/ref-x-rubric/rubric.json"
    assert res["per_file"][rel] == 2
    assert res["total_bumps"] == 2


# ── _load_yaml_capabilities / compute_capability_count_by_kind ───────────────
def test_capability_count_missing_file(tmp_path):
    out = MOD.compute_capability_count_by_kind(tmp_path)
    # 既知 kind 全て 0
    assert all(out[k] == 0 for k in MOD.KNOWN_KINDS)


def test_load_yaml_capabilities_missing_returns_empty(tmp_path):
    assert MOD._load_yaml_capabilities(tmp_path / "nope.yaml") == []


def test_capability_count_with_yaml(tmp_path):
    comp = tmp_path / "plugin-composition.yaml"
    comp.write_text(
        "capabilities:\n"
        "  - kind: skill\n"
        "    name: a\n"
        "  - kind: skill\n"
        "    name: b\n"
        "  - kind: agent\n"
        "    name: c\n"
        "  - kind: customkind\n"
        "    name: d\n",
        encoding="utf-8",
    )
    out = MOD.compute_capability_count_by_kind(tmp_path)
    assert out["skill"] == 2
    assert out["agent"] == 1
    assert out["hook"] == 0  # 既知だが 0 埋め
    assert out["customkind"] == 1  # 未知 kind 保持


def test_load_yaml_capabilities_line_parser_when_no_yaml(tmp_path, monkeypatch):
    # _HAS_YAML を False にして簡易 line-based parser 経路を踏ませる
    monkeypatch.setattr(MOD, "_HAS_YAML", False)
    comp = tmp_path / "plugin-composition.yaml"
    comp.write_text(
        "name: demo\n"
        "capabilities:\n"
        "  # comment line\n"
        "\n"
        "  - kind: skill\n"
        "    name: alpha\n"
        "  - kind: hook\n"
        "    name: beta\n"
        "other_top_key: stop_here\n"
        "  - kind: agent\n",  # トップレベル復帰後は無視
        encoding="utf-8",
    )
    caps = MOD._load_yaml_capabilities(comp)
    kinds = sorted(c.get("kind") for c in caps)
    assert kinds == ["hook", "skill"]


def test_load_yaml_capabilities_yaml_parse_error_falls_back(tmp_path, monkeypatch):
    # yaml はあるが parse 例外 → 簡易 parser fallback
    if not MOD._HAS_YAML:
        pytest.skip("yaml 未インストール環境では fallback 経路は別テストで網羅")
    comp = tmp_path / "plugin-composition.yaml"
    # safe_load が dict を返さない/例外を起こさない形式でも、capabilities を取れる line 形式
    comp.write_text(
        "capabilities:\n  - kind: command\n    name: x\n",
        encoding="utf-8",
    )

    class _Boom:
        def safe_load(self, text):
            raise ValueError("boom")

    monkeypatch.setattr(MOD, "yaml", _Boom(), raising=False)
    caps = MOD._load_yaml_capabilities(comp)
    assert any(c.get("kind") == "command" for c in caps)


# ── compute_hook_wired_count ─────────────────────────────────────────────────
def test_hook_count_no_file(tmp_path):
    assert MOD.compute_hook_wired_count(tmp_path) == 0


def test_hook_count_invalid_json(tmp_path):
    pj = tmp_path / ".claude-plugin"
    pj.mkdir()
    (pj / "plugin.json").write_text("{not json", encoding="utf-8")
    assert MOD.compute_hook_wired_count(tmp_path) == 0


def test_hook_count_no_hooks_key(tmp_path):
    (tmp_path / "plugin.json").write_text('{"name": "x"}', encoding="utf-8")
    assert MOD.compute_hook_wired_count(tmp_path) == 0


def test_hook_count_list_form(tmp_path):
    # event -> [ {matcher, hooks:[...]} ]
    pj = tmp_path / ".claude-plugin"
    pj.mkdir()
    data = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command"}, {"type": "command"}]},
                {"matcher": "Edit", "hooks": [{"type": "command"}]},
            ]
        }
    }
    (pj / "plugin.json").write_text(json.dumps(data), encoding="utf-8")
    assert MOD.compute_hook_wired_count(tmp_path) == 3


def test_hook_count_dict_form(tmp_path):
    # event -> { matcher: {hooks:[...]} }
    (tmp_path / "plugin.json").write_text(
        json.dumps({"hooks": {"Stop": {"*": {"hooks": [{"a": 1}, {"b": 2}]}}}}),
        encoding="utf-8",
    )
    assert MOD.compute_hook_wired_count(tmp_path) == 2


# ── compute_rubric_kind_coverage ─────────────────────────────────────────────
def test_rubric_coverage_no_files(tmp_path):
    res = MOD.compute_rubric_kind_coverage(tmp_path)
    assert res["covered_kinds"] == []
    assert res["coverage_ratio"] == 0.0
    assert res["per_file"] == {}


def test_rubric_coverage_invalid_json_skipped(tmp_path):
    rf = tmp_path / "skills" / "ref-x-rubric" / "rubric.json"
    rf.parent.mkdir(parents=True)
    rf.write_text("{bad", encoding="utf-8")
    res = MOD.compute_rubric_kind_coverage(tmp_path)
    assert res["covered_kinds"] == []


def test_rubric_coverage_top_level_and_rules(tmp_path):
    rf = tmp_path / "skills" / "ref-x-rubric" / "rubric.json"
    rf.parent.mkdir(parents=True)
    data = {
        "applies_to_kinds": ["skill", "agent"],
        "rules": [
            {"applies_to_kinds": ["hook"]},
            {"id": "no-kinds"},
            "not-a-dict",
        ],
    }
    rf.write_text(json.dumps(data), encoding="utf-8")
    res = MOD.compute_rubric_kind_coverage(tmp_path)
    assert set(res["covered_kinds"]) == {"skill", "agent", "hook"}
    rel = "skills/ref-x-rubric/rubric.json"
    assert set(res["per_file"][rel]) == {"skill", "agent", "hook"}
    assert res["coverage_ratio"] == round(3 / len(MOD.KNOWN_KINDS), 4)


# ── collect_all ──────────────────────────────────────────────────────────────
def test_collect_all_has_all_keys(tmp_path):
    _init_git(tmp_path)
    res = MOD.collect_all(tmp_path)
    for k in (
        "generated_at",
        "plugin_root",
        "lessons_per_pr",
        "review_cycle_time_ms",
        "rubric_bump_frequency",
        "capability_count_by_kind",
        "hook_wired_count",
        "rubric_kind_coverage",
    ):
        assert k in res
    assert res["plugin_root"] == str(tmp_path)


# ── upsert_evals ─────────────────────────────────────────────────────────────
def test_upsert_evals_creates_new(tmp_path):
    p = MOD.upsert_evals(tmp_path, {"x": 1})
    assert p == tmp_path / "EVALS.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["dogfooding_metrics"] == {"x": 1}


def test_upsert_evals_merges_existing(tmp_path):
    ep = tmp_path / "EVALS.json"
    ep.write_text(json.dumps({"keep": "me"}), encoding="utf-8")
    MOD.upsert_evals(tmp_path, {"y": 2})
    data = json.loads(ep.read_text(encoding="utf-8"))
    assert data["keep"] == "me"
    assert data["dogfooding_metrics"] == {"y": 2}


def test_upsert_evals_resets_on_invalid_existing(tmp_path):
    ep = tmp_path / "EVALS.json"
    ep.write_text("{not json", encoding="utf-8")
    MOD.upsert_evals(tmp_path, {"z": 3})
    data = json.loads(ep.read_text(encoding="utf-8"))
    assert data == {"dogfooding_metrics": {"z": 3}}


# ── main (in-process, PLUGIN_ROOT を tmp に差し替え) ──────────────────────────
def test_main_self_test_no_write(tmp_path, monkeypatch, capsys):
    _init_git(tmp_path)
    monkeypatch.setattr(MOD, "PLUGIN_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["compute-dogfooding-metrics.py", "--self-test"])
    rc = MOD.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "lessons_per_pr" in out
    assert not (tmp_path / "EVALS.json").exists()  # self-test は書込なし


def test_main_dry_run_no_write(tmp_path, monkeypatch, capsys):
    _init_git(tmp_path)
    monkeypatch.setattr(MOD, "PLUGIN_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["compute-dogfooding-metrics.py", "--dry-run"])
    rc = MOD.main()
    assert rc == 0
    assert not (tmp_path / "EVALS.json").exists()


def test_main_writes_evals(tmp_path, monkeypatch, capsys):
    _init_git(tmp_path)
    monkeypatch.setattr(MOD, "PLUGIN_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["compute-dogfooding-metrics.py"])
    rc = MOD.main()
    assert rc == 0
    ep = tmp_path / "EVALS.json"
    assert ep.exists()
    data = json.loads(ep.read_text(encoding="utf-8"))
    assert "dogfooding_metrics" in data
    err = capsys.readouterr().err
    assert "wrote dogfooding_metrics" in err


def test_main_exception_is_non_blocking(tmp_path, monkeypatch, capsys):
    # collect_all が例外を投げても main は exit 0 (非ブロック設計)
    monkeypatch.setattr(MOD, "PLUGIN_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["compute-dogfooding-metrics.py"])

    def boom(_root):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(MOD, "collect_all", boom)
    rc = MOD.main()
    assert rc == 0
    err = capsys.readouterr().err
    assert "failed: kaboom" in err


# ── CLI subprocess: 実 module を main 経由で起動(--self-test は副作用なし) ────
def test_cli_self_test_subprocess():
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],
        text=True,
        capture_output=True,
    )
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert "capability_count_by_kind" in data
    assert "rubric_kind_coverage" in data

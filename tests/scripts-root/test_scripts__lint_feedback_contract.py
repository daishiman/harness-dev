"""genuine 機能テスト: scripts/lint-feedback-contract.py

純関数 (_read_kind / _fallback_warnings / _check_skill) を実入力で呼び実出力を assert。
PLUGINS_DIR を tmp_path に monkeypatch して loop-kind 判定 / criteria 欠落 / N/A escape /
正常系を実 SKILL.md テキストで網羅。main() は subprocess で usage / --all を検証。
外部 I/O (git) は --all 経路を使い遮断。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-feedback-contract.py"


def _load_module():
    # 同階層 SSOT (feedback_contract_ssot) を import 解決できるよう scripts/ を path 先頭へ。
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("lint_feedback_contract_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# --- frontmatter 組み立てヘルパ (実 SKILL.md と同形) ---
def _skill_md(kind, fc_block="", extra=""):
    parts = [
        "---",
        "name: dummy-skill",
        f"kind: {kind}",
        "description: テスト用",
    ]
    if fc_block:
        parts.append(fc_block.rstrip("\n"))
    if extra:
        parts.append(extra.rstrip("\n"))
    parts.append("---")
    parts.append("")
    parts.append("# 本文")
    return "\n".join(parts) + "\n"


_VALID_FC = """feedback_contract:
  criteria:
    - id: IN1
      loop_scope: inner
      text: 量産スキルの完了チェックリストが具体的に検証される
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: ユーザーの真の目的を満たす成果物が出る
      verify_by: elegant-review
"""


def _write_skill(plugins_dir, plugin, skill, text, symlink=False):
    d = plugins_dir / plugin / "skills" / skill
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    return d


# ---------------- _read_kind ----------------
def test_read_kind_extracts_loop_kind():
    assert MOD._read_kind(_skill_md("run")) == "run"
    assert MOD._read_kind(_skill_md("wrap")) == "wrap"
    assert MOD._read_kind(_skill_md("delegate")) == "delegate"


def test_read_kind_handles_trailing_comment_and_hyphen():
    text = _skill_md("ref").replace("kind: ref", "kind: ref  # 非ループ系")
    assert MOD._read_kind(text) == "ref"


def test_read_kind_none_when_absent():
    assert MOD._read_kind("no frontmatter here") is None


# ---------------- _fallback_warnings ----------------
def test_fallback_warnings_flags_fallback_text():
    # SSOT のフォールバック suffix をそのまま含む criteria は WARN 対象。
    fb_inner = "dummy-skill " + MOD.FC.FALLBACK_INNER_SUFFIX
    fc = {"criteria": [{"id": "IN1", "loop_scope": "inner", "text": fb_inner, "verify_by": "test"}]}
    warns = MOD._fallback_warnings("plug", "skill", fc)
    assert len(warns) == 1
    assert "IN1" in warns[0]
    assert "フォールバック既定文" in warns[0]


def test_fallback_warnings_empty_for_real_criteria():
    fc = {"criteria": [{"id": "IN1", "loop_scope": "inner", "text": "固有の具体基準", "verify_by": "test"}]}
    assert MOD._fallback_warnings("plug", "skill", fc) == []


def test_fallback_warnings_empty_when_criteria_not_list():
    assert MOD._fallback_warnings("plug", "skill", {"criteria": "oops"}) == []
    assert MOD._fallback_warnings("plug", "skill", {}) == []


# ---------------- _check_skill ----------------
def test_check_skill_non_loop_kind_skipped(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p", "ref-thing", _skill_md("ref"))
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    # 非ループ系 (ref) は criteria 不要 => 違反なし。
    assert MOD._check_skill("p", "ref-thing") == []


def test_check_skill_missing_feedback_contract_is_violation(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p", "run-x", _skill_md("run"))  # fc 無し
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    errs = MOD._check_skill("p", "run-x")
    assert len(errs) == 1
    assert "feedback_contract がありません" in errs[0]


def test_check_skill_valid_criteria_passes(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p", "run-ok", _skill_md("run", _VALID_FC))
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    assert MOD._check_skill("p", "run-ok") == []


@pytest.mark.parametrize("kind", sorted(MOD.LOOP_KINDS))
def test_check_skill_loop_kind_skip_reason_is_violation(tmp_path, monkeypatch, kind):
    # loop 実行系の skip_reason escape は封鎖 (FEEDBACK_SKIP_KINDS 限定)。
    pdir = tmp_path / "plugins"
    fc = "feedback_contract:\n  skip_reason: このスキルは評価不要\n"
    _write_skill(pdir, "p", f"{kind}-skip", _skill_md(kind, fc))
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    errs = MOD._check_skill("p", f"{kind}-skip")
    assert len(errs) == 1
    assert "skip_reason では criteria 必須を免除できません" in errs[0]


@pytest.mark.parametrize("kind", sorted(MOD.FC.FEEDBACK_SKIP_KINDS))
def test_check_skill_skip_kind_skip_reason_allowed(tmp_path, monkeypatch, kind):
    # ref/assign (FEEDBACK_SKIP_KINDS) は criteria 不要 => skip_reason 有無に関わらず違反なし。
    pdir = tmp_path / "plugins"
    fc = "feedback_contract:\n  skip_reason: read-only 評価器のため N/A\n"
    _write_skill(pdir, "p", f"{kind}-skip", _skill_md(kind, fc))
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    assert MOD._check_skill("p", f"{kind}-skip") == []


def test_check_skill_loop_kind_valid_criteria_with_skip_reason_passes(tmp_path, monkeypatch):
    # criteria が整備済みなら skip_reason が残存していても criteria 検査へ進み PASS。
    pdir = tmp_path / "plugins"
    fc = _VALID_FC + "  skip_reason: 残存フィールド\n"
    _write_skill(pdir, "p", "run-both", _skill_md("run", fc))
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    assert MOD._check_skill("p", "run-both") == []


def test_check_skill_invalid_criteria_reports_errors(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    bad_fc = """feedback_contract:
  criteria:
    - id: BAD9
      loop_scope: inner
      text: id pattern 違反
      verify_by: test
"""
    _write_skill(pdir, "p", "run-bad", _skill_md("run", bad_fc))
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    errs = MOD._check_skill("p", "run-bad")
    # id=BAD9 は ^(IN|OUT|C)[0-9]+$ 不一致 + outer 欠落 で複数違反。
    assert errs
    assert any("must match" in e for e in errs)
    assert any("outer" in e for e in errs)


def test_check_skill_missing_file_returns_empty(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    assert MOD._check_skill("nope", "nope") == []


# ---------------- _all_skills (実 FS 走査) ----------------
def test_all_skills_discovers_real_and_skips_symlink(tmp_path, monkeypatch):
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p1", "run-a", _skill_md("run", _VALID_FC))
    _write_skill(pdir, "p1", "run-b", _skill_md("wrap", _VALID_FC))
    # symlink スキルは実体側で検査するため除外される。
    real_target = pdir / "p1" / "skills" / "run-a"
    link = pdir / "p2" / "skills"
    link.mkdir(parents=True)
    (link / "run-a-link").symlink_to(real_target)
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    found = MOD._all_skills()
    assert ("p1", "run-a") in found
    assert ("p1", "run-b") in found
    assert ("p2", "run-a-link") not in found


def test_all_skills_empty_when_no_plugins(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "PLUGINS_DIR", tmp_path / "absent")
    assert MOD._all_skills() == set()


# ---------------- main() via subprocess (CLI 契約) ----------------
def test_main_requires_mode_flag():
    # 排他必須グループ未指定 => argparse usage error exit 2。
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 2
    assert "one of the arguments" in r.stderr


def test_main_all_on_real_repo_passes():
    # 実 repo は P0 で全 loop-kind が criteria 携帯済 => OK exit 0。
    r = subprocess.run([sys.executable, str(SCRIPT), "--all"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "[OK] lint-feedback-contract" in r.stdout
    assert "loop-kind skill(s) carry per-skill criteria" in r.stdout


def test_main_help_exits_zero():
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "--changed-only" in r.stdout and "--all" in r.stdout


# ---------------- main() in-process (--all, PLUGINS_DIR を tmp に差し替え) ----------------
def _run_main_all(monkeypatch, pdir):
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    monkeypatch.setattr(sys, "argv", ["lint-feedback-contract.py", "--all"])
    return MOD.main()


def test_main_all_ok_summary_on_valid_tree(tmp_path, monkeypatch, capsys):
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p", "run-ok", _skill_md("run", _VALID_FC))
    _write_skill(pdir, "p", "ref-x", _skill_md("ref"))  # 非ループは checked に数えない
    rc = _run_main_all(monkeypatch, pdir)
    out = capsys.readouterr().out
    assert rc == 0
    assert "[OK] lint-feedback-contract: 1 loop-kind skill(s)" in out


def test_main_all_reports_violations_exit_1(tmp_path, monkeypatch, capsys):
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p", "run-missing", _skill_md("run"))  # fc 欠落 => 違反
    rc = _run_main_all(monkeypatch, pdir)
    out = capsys.readouterr().out
    assert rc == 1
    assert "[FAIL] lint-feedback-contract" in out
    assert "feedback_contract.criteria" in out
    assert "Fix:" in out


# ---------------- live-trial ratchet (D7 P2) ----------------
_LIVE_TOOLS = "allowed-tools:\n  - Read\n  - Agent"  # Agent => derive_acceptance_tier live
_FORK_TOOLS = "allowed-tools: [Read, Bash(python3 *)]"  # live 信号なし => fork

_FC_OUT_LIVE_TRIAL = """feedback_contract:
  criteria:
    - id: IN1
      loop_scope: inner
      text: 固有の内側基準
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 実走 acceptance で goal 適合が検証される
      verify_by: live-trial
"""


def _run_main_all_with_baseline(monkeypatch, pdir, baseline_path):
    monkeypatch.setattr(MOD, "PLUGINS_DIR", pdir)
    monkeypatch.setattr(MOD, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(sys, "argv", ["lint-feedback-contract.py", "--all"])
    return MOD.main()


def test_ratchet_live_tier_with_out_live_trial_passes(tmp_path, monkeypatch, capsys):
    # 正: live 導出 + OUT criteria に verify_by: live-trial => PASS (WARN も出ない)。
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p", "run-live-ok", _skill_md("run", _FC_OUT_LIVE_TRIAL, _LIVE_TOOLS))
    rc = _run_main_all_with_baseline(monkeypatch, pdir, tmp_path / "absent.json")
    out = capsys.readouterr().out
    assert rc == 0
    assert "[WARN]" not in out


def test_ratchet_live_tier_missing_criteria_outside_baseline_fails(tmp_path, monkeypatch, capsys):
    # 負: live 導出 + live-trial 欠落 + baseline 外 (=新規 build) => FAIL exit 1。
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p", "run-live-miss", _skill_md("run", _VALID_FC, _LIVE_TOOLS))
    rc = _run_main_all_with_baseline(monkeypatch, pdir, tmp_path / "absent.json")
    out = capsys.readouterr().out
    assert rc == 1
    assert "verify_by: live-trial が1件もない" in out
    assert "baseline への追記は禁止" in out


def test_ratchet_live_tier_missing_criteria_in_baseline_warns(tmp_path, monkeypatch, capsys):
    # 免除: baseline 内の既存 skill => WARN のみで exit 0 (ratchet)。
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p", "run-live-old", _skill_md("run", _VALID_FC, _LIVE_TOOLS))
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"exempt": ["p/run-live-old"]}', encoding="utf-8")
    rc = _run_main_all_with_baseline(monkeypatch, pdir, baseline)
    out = capsys.readouterr().out
    assert rc == 0
    assert "[WARN] lint-feedback-contract" in out
    assert "baseline 免除中" in out


def test_ratchet_non_live_tier_not_checked(tmp_path, monkeypatch, capsys):
    # 非 live: hooks/live ツールなし (fork 導出) は live-trial criteria 不要 => PASS。
    pdir = tmp_path / "plugins"
    _write_skill(pdir, "p", "run-fork", _skill_md("run", _VALID_FC, _FORK_TOOLS))
    rc = _run_main_all_with_baseline(monkeypatch, pdir, tmp_path / "absent.json")
    out = capsys.readouterr().out
    assert rc == 0
    assert "live-trial" not in out


def test_ratchet_self_test_cli_passes():
    r = subprocess.run([sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "[OK] self-test" in r.stdout


def test_main_all_emits_fallback_warning_but_passes(tmp_path, monkeypatch, capsys):
    pdir = tmp_path / "plugins"
    # criteria は有効 (inner+outer 各1) だが inner text がフォールバック既定 => WARN かつ PASS。
    fb_inner = "dummy-skill " + MOD.FC.FALLBACK_INNER_SUFFIX
    fc = f"""feedback_contract:
  criteria:
    - id: IN1
      loop_scope: inner
      text: {fb_inner}
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 固有の外側基準
      verify_by: elegant-review
"""
    _write_skill(pdir, "p", "run-fb", _skill_md("run", fc))
    rc = _run_main_all(monkeypatch, pdir)
    out = capsys.readouterr().out
    assert rc == 0
    assert "[WARN] lint-feedback-contract" in out
    assert "fallback criteria" in out

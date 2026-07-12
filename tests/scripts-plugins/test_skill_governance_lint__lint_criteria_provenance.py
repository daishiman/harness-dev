"""lint-criteria-provenance.py の写像検査 + main CLI 契約を network 無しで網羅する。

このスクリプトは完了チェックリストの CL アンカーと feedback_contract.criteria[]
.derived_from の被覆・実在を突合する (finding LS-05/PF-DLOOP: 完了条件多系統
分散に対する Checklist→criteria 写像の機械層)。presence-based opt-in で、
アンカーも derived_from も無い skill は対象外。本テストは:
  - check_skill_md: 整合 PASS / R1 重複 / R2 アンカー無し derived_from /
    R3 dangling 参照 + 非 CL 形式 / R4 derived_from 皆無 / R5 被覆漏れ /
    R6 exempt 空理由 / opt-in 前 skill の skip
  - main: 実 repo の harness-creator 3 skill が整合 (回帰ゲート) / --skills-dir /
    --self-test exit0 / usage exit2 / 違反 exit1
を tmp_path fixture と実入力で genuine に assert する。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-criteria-provenance.py"
SKILLS_DIR = ROOT / "plugins" / "harness-creator" / "skills"

_SPEC = importlib.util.spec_from_file_location("lint_criteria_provenance_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


OK_MD = (
    "---\nfeedback_contract:\n  criteria:\n"
    "    - id: IN1\n      derived_from: [CL-1, CL-2]\n---\n"
    "# t\n- [ ] a <!-- CL-1 -->\n- [ ] b <!-- CL-2 -->\n"
    "- [ ] c <!-- CL-3 exempt: 運用操作項目 -->\n"
)


def _check(tmp_path, text):
    p = tmp_path / "SKILL.md"
    p.write_text(text, encoding="utf-8")
    return MOD.check_skill_md(p)


def test_consistent_mapping_passes(tmp_path):
    assert _check(tmp_path, OK_MD) == []


def test_r1_duplicate_anchor(tmp_path):
    errs = _check(tmp_path, OK_MD.replace(" <!-- CL-2 -->", " <!-- CL-1 -->"))
    assert any("R1" in e for e in errs)


def test_r2_derived_from_without_anchors(tmp_path):
    text = OK_MD.split("# t\n")[0] + "# t\n- [ ] a\n"
    errs = _check(tmp_path, text)
    assert any("R2" in e for e in errs)


def test_r3_dangling_reference(tmp_path):
    errs = _check(tmp_path, OK_MD.replace("[CL-1, CL-2]", "[CL-1, CL-9]"))
    assert any("R3" in e and "CL-9" in e for e in errs)


def test_r3_non_cl_token(tmp_path):
    errs = _check(tmp_path, OK_MD.replace("[CL-1, CL-2]", "[CL-1, IN9]"))
    assert any("R3" in e and "IN9" in e for e in errs)


def test_r4_anchors_without_any_derived_from(tmp_path):
    text = "---\nx: 1\n---\n# t\n- [ ] a <!-- CL-1 -->\n"
    errs = _check(tmp_path, text)
    assert any("R4" in e for e in errs)


def test_r5_uncovered_anchor(tmp_path):
    errs = _check(tmp_path, OK_MD.replace("[CL-1, CL-2]", "[CL-1]"))
    assert any("R5" in e and "CL-2" in e for e in errs)


def test_r6_empty_exempt_reason(tmp_path):
    errs = _check(tmp_path, OK_MD.replace("exempt: 運用操作項目", "exempt:"))
    assert any("R6" in e for e in errs)


def test_opt_in_skill_without_anchors_is_skipped(tmp_path):
    assert _check(tmp_path, "---\nx: 1\n---\n# 素\n- [ ] a\n") == []


def test_main_real_harness_creator_skills_consistent():
    """実 repo の harness-creator 全 skill が写像整合 (回帰ゲート)。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--skills-dir", str(SKILLS_DIR)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "写像整合" in proc.stdout


def test_main_self_test_ok():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True
    )
    assert proc.returncode == 0 and "ok" in proc.stdout


def test_main_usage_without_args():
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 2


def test_main_violation_exit1(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(OK_MD.replace("[CL-1, CL-2]", "[CL-1]"), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(p)], capture_output=True, text=True
    )
    assert proc.returncode == 1 and "R5" in proc.stderr

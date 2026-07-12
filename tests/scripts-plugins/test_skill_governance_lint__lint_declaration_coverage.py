"""lint-declaration-coverage.py の純関数 + main CLI 契約を network 無しで網羅する。

このスクリプトは plugin-composition.yaml の `enforcement: manual` 残存数を
baseline 定数と突合する ratchet lint (finding LS-10: 宣言面追加時の突合 lint
同時配線義務) であり、実通信・実 keychain は一切叩かない。

本テストは:
  - count_manual: 0件 / 複数件 / enforcement 接頭辞なし manual の非計上 /
    空白ゆれ / 理由注記付き行の計上
  - evaluate: 増加→FAIL exit1 / 同数→PASS / 減少→PASS+baseline 更新促し
  - lint_file: baseline 注入で超過・一致・欠落ファイル (exit 2)
  - main: 合格 OK / 違反 exit1 / 引数無し usage exit2 / --self-test exit0
  - baseline 同期: repo 実ファイル (plugins/harness-creator/plugin-composition.yaml)
    の実残存数が MANUAL_BASELINE と一致する (drift 検出の二重化。composition の
    manual を増減させたら本定数も同時更新する契約を pytest 側でも強制)

を tmp_path 上に合格 fixture と各違反 fixture を作り実入力で genuine に assert する。
main は subprocess(sys.executable) で exit code / stdout / stderr を assert する。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-declaration-coverage.py"
)
COMPOSITION = ROOT / "plugins" / "harness-creator" / "plugin-composition.yaml"

_SPEC = importlib.util.spec_from_file_location(
    "lint_declaration_coverage_under_test", SCRIPT
)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# count_manual
# --------------------------------------------------------------------------

def test_count_manual_zero():
    assert MOD.count_manual("") == 0
    assert MOD.count_manual('- "x (enforcement: lint-y.py)"\n') == 0


def test_count_manual_multiple_with_reason_note():
    text = (
        '- "a (enforcement: manual)"\n'
        '- "b (enforcement: manual。manual 維持の理由: コスト過大)"\n'
    )
    assert MOD.count_manual(text) == 2


def test_count_manual_ignores_bare_manual_word():
    # enforcement 接頭辞なしの「manual」やメタ不変条件の言い換えは数えない
    text = '- "manual 宣言の残存数を ratchet 監視 (enforcement: lint-declaration-coverage.py)"\n'
    assert MOD.count_manual(text) == 0


def test_count_manual_whitespace_variants():
    assert MOD.count_manual("(enforcement:  manual)") == 1
    assert MOD.count_manual("(enforcement:manual)") == 1


# --------------------------------------------------------------------------
# evaluate (ratchet 3 分岐)
# --------------------------------------------------------------------------

def test_evaluate_increase_fails():
    code, msg = MOD.evaluate(4, 3)
    assert code == 1
    assert "FAIL" in msg
    assert "突合 lint" in msg


def test_evaluate_equal_passes():
    code, msg = MOD.evaluate(3, 3)
    assert code == 0
    assert "一致" in msg


def test_evaluate_decrease_passes_with_tighten_prompt():
    code, msg = MOD.evaluate(2, 3)
    assert code == 0
    assert "MANUAL_BASELINE" in msg
    assert "2" in msg


# --------------------------------------------------------------------------
# lint_file
# --------------------------------------------------------------------------

def test_lint_file_over_and_at_baseline(tmp_path):
    p = tmp_path / "plugin-composition.yaml"
    p.write_text(
        'invariant:\n  - "a (enforcement: manual)"\n  - "b (enforcement: manual)"\n',
        encoding="utf-8",
    )
    code, msg = MOD.lint_file(p, baseline=1)
    assert code == 1
    assert "FAIL" in msg
    code, msg = MOD.lint_file(p, baseline=2)
    assert code == 0


def test_lint_file_missing_is_usage_error(tmp_path):
    code, msg = MOD.lint_file(tmp_path / "missing.yaml", baseline=0)
    assert code == 2
    assert "read error" in msg


# --------------------------------------------------------------------------
# baseline 同期 (repo 実ファイル)
# --------------------------------------------------------------------------

def test_repo_composition_matches_baseline():
    text = COMPOSITION.read_text(encoding="utf-8")
    assert MOD.count_manual(text) == MOD.MANUAL_BASELINE, (
        "plugins/harness-creator/plugin-composition.yaml の enforcement: manual 残存数が"
        " MANUAL_BASELINE と不一致。manual を増減させたら lint-declaration-coverage.py"
        " の定数も同時更新すること (増加は突合 lint 同時配線が原則)"
    )


# --------------------------------------------------------------------------
# main CLI (subprocess)
# --------------------------------------------------------------------------

def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_main_repo_file_passes():
    proc = run_cli(str(COMPOSITION))
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_main_violation_exit1(tmp_path):
    p = tmp_path / "plugin-composition.yaml"
    manuals = "\n".join(
        f'  - "inv{i} (enforcement: manual)"' for i in range(MOD.MANUAL_BASELINE + 1)
    )
    p.write_text(f"invariant:\n{manuals}\n", encoding="utf-8")
    proc = run_cli(str(p))
    assert proc.returncode == 1
    assert "FAIL" in proc.stderr


def test_main_no_args_usage_exit2():
    proc = run_cli()
    assert proc.returncode == 2
    assert "usage" in proc.stderr


def test_main_self_test():
    proc = run_cli("--self-test")
    assert proc.returncode == 0
    assert "self-test ok" in proc.stdout

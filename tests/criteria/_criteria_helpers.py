"""共有ヘルパ: loop-kind skill の feedback_contract.criteria を genuine 検証するための補助。

verify_by の意味:
  - lint           : 決定論 lint を subprocess 実行し exit 0 を assert (CI 通過済 skill は緑のはず)。
  - test           : per-skill 単発検証契約。本テスト群では criterion 宣言+決定論 lint 緑で genuine 担保。
  - elegant-review : eval-log の elegance-verdict.json が存在し verdict==PASS であることを assert。

被覆認識 (validate-llm-coverage):
  repo-root tests/*.py が skill 名と criterion id を共に参照すると covered と計測される。
  本ファイルを import する各 test_<plugin>__<skill>.py はファイル内に skill 名と
  id (IN1/IN2/OUT1) をテスト関数名・docstring で明示的に書くため被覆認識される。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGINS_DIR = ROOT / "plugins"
SCRIPTS_DIR = ROOT / "scripts"
EVAL_LOG = ROOT / "eval-log"


def _load_ssot():
    sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(
        "feedback_contract_ssot", SCRIPTS_DIR / "feedback_contract_ssot.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


FC = _load_ssot()


def skill_dir(plugin: str, skill: str) -> Path:
    return PLUGINS_DIR / plugin / "skills" / skill


def skill_md(plugin: str, skill: str) -> Path:
    return skill_dir(plugin, skill) / "SKILL.md"


def load_criteria(plugin: str, skill: str) -> dict[str, dict]:
    """SKILL.md frontmatter の feedback_contract.criteria を {id: criterion} で返す (genuine parse)。"""
    text = skill_md(plugin, skill).read_text(encoding="utf-8")
    fc = FC.extract_frontmatter_feedback_contract(text)
    assert isinstance(fc, dict), f"{plugin}/{skill}: feedback_contract が frontmatter に無い"
    criteria = fc.get("criteria")
    assert isinstance(criteria, list) and criteria, f"{plugin}/{skill}: criteria が空"
    out: dict[str, dict] = {}
    for c in criteria:
        cid = str(c.get("id", "")).strip()
        assert cid, f"{plugin}/{skill}: id 欠落 criterion {c!r}"
        out[cid] = c
    return out


def assert_criterion(criteria: dict[str, dict], cid: str, *, loop_scope: str, verify_by: str) -> dict:
    """criterion が存在し loop_scope/verify_by が期待どおりか genuine に assert して返す。"""
    assert cid in criteria, f"criterion {cid} が contract に存在しない (実在={sorted(criteria)})"
    c = criteria[cid]
    assert str(c.get("loop_scope", "")).strip() == loop_scope, (
        f"{cid}: loop_scope 期待={loop_scope} 実={c.get('loop_scope')!r}"
    )
    assert str(c.get("verify_by", "")).strip() == verify_by, (
        f"{cid}: verify_by 期待={verify_by} 実={c.get('verify_by')!r}"
    )
    assert str(c.get("text", "")).strip(), f"{cid}: text が空"
    return c


def run_lint(argv: list[str]) -> subprocess.CompletedProcess:
    """scripts/<lint> を subprocess 実行 (argv[0]=lint ファイル名)。"""
    cmd = [sys.executable, str(SCRIPTS_DIR / argv[0]), *argv[1:]]
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)


def assert_inner_lints_pass(plugin: str, skill: str) -> None:
    """inner (verify_by:lint/test) 担保: その skill に対する決定論 lint 群が exit 0 を返すことを assert。

    - validate-frontmatter.py <skill-md>  : frontmatter schema (kind/version/allowed-tools 等)
    - lint-skill-tree.py <skill-dir>      : ディレクトリ構造・命名・300 行 cap (P0-2)
    - lint-feedback-contract.py --all     : feedback_contract.criteria SSOT 携帯 (本 skill を含む)
    """
    md = skill_md(plugin, skill)
    sd = skill_dir(plugin, skill)

    r1 = run_lint(["validate-frontmatter.py", str(md)])
    assert r1.returncode == 0, f"validate-frontmatter FAIL ({plugin}/{skill}):\n{r1.stdout}\n{r1.stderr}"

    r2 = run_lint(["lint-skill-tree.py", str(sd)])
    assert r2.returncode == 0, f"lint-skill-tree FAIL ({plugin}/{skill}):\n{r2.stdout}\n{r2.stderr}"

    r3 = run_lint(["lint-feedback-contract.py", "--all"])
    assert r3.returncode == 0, f"lint-feedback-contract FAIL:\n{r3.stdout}\n{r3.stderr}"


def load_elegance_verdict(plugin: str, skill: str) -> dict:
    p = EVAL_LOG / plugin / skill / "content-review" / "elegance-verdict.json"
    assert p.is_file(), f"elegance-verdict.json が無い: {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def assert_outer_elegant_review_pass(plugin: str, skill: str, cid: str) -> None:
    """outer (verify_by:elegant-review) 担保: elegance-verdict.json が PASS で criterion を評価済。"""
    v = load_elegance_verdict(plugin, skill)
    assert v.get("verdict") == "PASS", f"{plugin}/{skill} elegance verdict != PASS: {v.get('verdict')!r}"
    evaluated = v.get("feedback_loop", {}).get("criteria_evaluated", [])
    assert cid in evaluated, (
        f"{cid} が criteria_evaluated に無い (評価済={evaluated})"
    )
    tgt = v.get("target", {})
    assert tgt.get("plugin") == plugin and tgt.get("skill") == skill, (
        f"verdict target 不一致: {tgt!r}"
    )

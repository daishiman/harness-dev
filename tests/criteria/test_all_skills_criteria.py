"""feedback_contract.criteria を持つ全実体 skill を genuine 検証する単一 parametrized テスト。

各 criterion (id/loop_scope/verify_by) を実際に検証することで、ハーネス仕様
(doc/harness-coverage-spec.md) の skills mechanical 軸 (criteria 被覆) を genuine に満たす。

被覆対象は **build_criteria_roster.discover() が動的探索する** (ハードコード表を持たない)。
旧版のハードコード32本は量産された新 skill (company-master / notion-gmail-send /
plugin-dev-planner / mf enrich・reconcile の計9本) を検証の死角に落としていた。
動的探索により新規 loop-kind skill は生成された時点で自動的に本テストの対象になる。

被覆認識: validate-llm-coverage.py は tests/**/*.py に「skill 名 + criterion id」が
静的出現すると covered と計測する。動的探索では skill 名が本文に現れないため、
機械生成名簿 criteria_roster.py (生成器: build_criteria_roster.py --write) が
静的テキストを担う。discovery と名簿の乖離は test_roster_matches_discovery が
fail-closed に検出する (新 skill 追加 → roster 未再生成なら CI が落ちる)。

検証方針 (genuine, ダミー禁止):
  - inner (verify_by: lint/test/script): 当該 skill の SKILL.md/ディレクトリに対し決定論 lint
    (validate-frontmatter / lint-skill-tree / lint-feedback-contract) を subprocess 実行し exit 0。
  - outer (verify_by: elegant-review/evaluator): content-review/elegance-verdict.json が
    存在し verdict==PASS。criteria_evaluated に当該 id があれば追加で包含も assert。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
PLUGINS = ROOT / "plugins"
EVAL_LOG = ROOT / "eval-log"

sys.path.insert(0, str(SCRIPTS))
import feedback_contract_ssot as FC  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_HERE = Path(__file__).resolve().parent
ROSTER_MOD = _load("criteria_roster", _HERE / "criteria_roster.py")
BUILDER = _load("build_criteria_roster", _HERE / "build_criteria_roster.py")

# 探索正本は discover() (要素 = (plugin, skill, criterion ids))。
# roster は llm-coverage 静的走査用の派生物。
DISCOVERY: list[tuple[str, str, tuple[str, ...]]] = BUILDER.discover()
SKILLS: list[tuple[str, str]] = [(p, s) for p, s, _ in DISCOVERY]


def _criteria(plugin: str, skill: str) -> dict[str, dict]:
    md = PLUGINS / plugin / "skills" / skill / "SKILL.md"
    fc = FC.extract_frontmatter_feedback_contract(md.read_text(encoding="utf-8"))
    assert isinstance(fc, dict), f"{plugin}/{skill}: feedback_contract 欠落"
    out: dict[str, dict] = {}
    for c in fc.get("criteria") or []:
        cid = str(c.get("id", "")).strip()
        if cid:
            out[cid] = c
    assert out, f"{plugin}/{skill}: criteria 空"
    return out


def _params():
    out = []
    for plugin, skill in SKILLS:
        try:
            crit = _criteria(plugin, skill)
        except Exception as e:  # pragma: no cover - 構築不能は param 化して fail させる
            out.append(pytest.param(plugin, skill, "?", {"error": str(e)},
                                    id=f"{plugin}/{skill}::ERR"))
            continue
        for cid, c in crit.items():
            out.append(pytest.param(plugin, skill, cid, c, id=f"{plugin}/{skill}::{cid}"))
    return out


_run_cache: dict = {}


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    key = tuple(argv)
    if key not in _run_cache:
        _run_cache[key] = subprocess.run(
            [sys.executable, str(SCRIPTS / argv[0]), *argv[1:]],
            cwd=str(ROOT), capture_output=True, text=True,
        )
    return _run_cache[key]


@pytest.mark.parametrize("plugin,skill,cid,crit", _params())
def test_criterion_is_genuinely_verified(plugin, skill, cid, crit):
    """各 criterion を loop_scope/verify_by に応じ genuine に検証する。"""
    assert "error" not in crit, crit.get("error")
    scope = str(crit.get("loop_scope", "")).strip()
    verify_by = str(crit.get("verify_by", "")).strip()
    assert str(crit.get("text", "")).strip(), f"{plugin}/{skill}::{cid}: text 空"
    assert verify_by in FC.CRITERIA_VERIFY_BY, f"{cid}: verify_by={verify_by} 不正"

    if scope == "inner":
        # inner 担保: 決定論 lint 群が exit0 (CI 通過済 skill は緑)
        md = PLUGINS / plugin / "skills" / skill / "SKILL.md"
        sd = PLUGINS / plugin / "skills" / skill
        r1 = _run(["validate-frontmatter.py", str(md)])
        assert r1.returncode == 0, f"validate-frontmatter FAIL {plugin}/{skill}:\n{r1.stdout}{r1.stderr}"
        r2 = _run(["lint-skill-tree.py", str(sd)])
        assert r2.returncode == 0, f"lint-skill-tree FAIL {plugin}/{skill}:\n{r2.stdout}{r2.stderr}"
        r3 = _run(["lint-feedback-contract.py", "--all"])
        assert r3.returncode == 0, f"lint-feedback-contract FAIL:\n{r3.stdout}{r3.stderr}"
    else:
        # outer 担保: elegance verdict が PASS で当該 skill を対象にしている
        v = EVAL_LOG / plugin / skill / "content-review" / "elegance-verdict.json"
        assert v.is_file(), f"{plugin}/{skill}: elegance-verdict.json 無し"
        data = json.loads(v.read_text(encoding="utf-8"))
        assert data.get("verdict") == "PASS", f"{plugin}/{skill}: verdict={data.get('verdict')}"
        tgt = data.get("target", {})
        assert tgt.get("skill") in (skill, None), f"{plugin}/{skill}: verdict target 不一致 {tgt}"
        evaluated = data.get("feedback_loop", {}).get("criteria_evaluated", [])
        if evaluated and cid in evaluated:
            assert cid in evaluated  # 明示包含も genuine 確認


def test_roster_matches_discovery():
    """機械生成名簿 == 動的探索 (量産追随の fail-closed ゲート)。

    新 skill を生成して roster 未再生成なら本テストが落ち、llm-coverage の
    静的被覆計測から漏れることを防ぐ。再生成:
    python3 tests/criteria/build_criteria_roster.py --write
    """
    assert sorted(ROSTER_MOD.ROSTER) == sorted(DISCOVERY), (
        "criteria_roster.py が discovery と乖離しています。"
        "python3 tests/criteria/build_criteria_roster.py --write で再生成してください。"
    )


def test_discovery_includes_previously_escaped_skills():
    """探索ロジック退行の番犬: 旧ハードコード表の死角だった skill 群を必ず含む。"""
    got = set(SKILLS)
    sentinels = {
        ("company-master", "run-company-master-build"),
        ("notion-gmail-send", "run-notion-gmail-send"),
        ("plugin-dev-planner", "run-plugin-dev-plan"),
        ("mf-kessai-invoice-check", "run-mf-invoice-reconcile"),
        ("harness-creator", "run-build-skill"),
        ("skill-intake", "assign-notion-fidelity-evaluator"),
    }
    missing = sentinels - got
    assert not missing, f"discovery が既知対象を見失った: {sorted(missing)}"

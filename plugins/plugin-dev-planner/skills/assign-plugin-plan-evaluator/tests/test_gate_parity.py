"""決定論ゲート集合の単一 SSOT 化を機械強制する parity テスト。

正本は `evaluate-plan.py` の `_gate_defs` (= 評価器が実際に実行する決定論ランナーのゲート定義)。
本テストは次の一致を縛る:
  1. `_gate_defs` (mechanical runner) ↔ `plan-rubric.json` deterministic_gates (採点ルール)
     を id / name / conditions まで一致させる。
  2. `EVALS.json` mechanical[] (CI harness) が全ゲートスクリプトを invocation として持つ。
  3. 評価器の人間可読 projection (agent / assign SKILL の Step1 bash) が、全ゲートを束ねる
     決定論ランナー `evaluate-plan.py` を実際に起動する。

背景 (2026-06-30 elegant-review): build handoff gate を追加した際、SSOT 群 (rubric/EVALS/io-contract)
には反映されたのに独立評価器 (proposer≠approver) の実行経路には伝播せず、rubric が exit0 を要求する
ゲートを評価器が走らせない依存破れ — 壊れた handoff routing を持つ plan が独立評価を PASS しうる
Goodhart 穴 — を検出した。真因は invocation 集合の parity を機械照合する test/lint が不在だったこと。
本テストは「ゲートを 1 本足したら全 SSOT が追従しないと fail」させ (test_kind_key_doc_parity.py と
同じ forward-parity 哲学)、この drift を fail-closed で恒久封止する。
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]                 # assign-plugin-plan-evaluator
PLUGIN_ROOT = SKILL_DIR.parents[1]                              # plugin-dev-planner
RUN_SKILL = PLUGIN_ROOT / "skills" / "run-plugin-dev-plan"


def _load_evaluator():
    path = SKILL_DIR / "scripts" / "evaluate-plan.py"
    spec = importlib.util.spec_from_file_location("evaluate_plan", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_specfm():
    path = RUN_SKILL / "scripts" / "specfm.py"
    spec = importlib.util.spec_from_file_location("specfm_parity", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gate_defs() -> list[dict]:
    # _gate_defs(run_skill, plan_dir) はコマンド組み立てにパスしか使わない (実行はしない)
    return _load_evaluator()._gate_defs(RUN_SKILL, Path("/tmp/plan"))


def _gate_script(command: list) -> str:
    for token in command:
        if str(token).endswith(".py"):
            return Path(str(token)).name
    raise AssertionError(f"gate command に .py が無い: {command}")


def _rubric() -> dict:
    return json.loads((SKILL_DIR / "references" / "plan-rubric.json").read_text(encoding="utf-8"))


def _bash_blocks(path: Path) -> str:
    return "\n".join(re.findall(r"```bash\n(.*?)```", path.read_text(encoding="utf-8"), re.DOTALL))


def test_gate_defs_match_rubric_by_id_name_conditions():
    """evaluate-plan.py の _gate_defs と plan-rubric.json deterministic_gates が
    id / name / conditions まで一致する (mechanical runner と採点ルールの単一 SSOT 化)。
    ゲートを足して片方だけ更新すると fail する。"""
    runner = {g["id"]: (g["name"], tuple(g["conditions"])) for g in _gate_defs()}
    rubric = {g["id"]: (g["name"], tuple(g["conditions"])) for g in _rubric()["deterministic_gates"]}
    assert runner == rubric, (
        "evaluate-plan.py の _gate_defs と plan-rubric.json deterministic_gates が乖離。"
        "ゲートを追加/改名したら mechanical runner と rubric を同時更新すること"
    )


def test_eval_harness_runs_every_gate_script():
    """EVALS.json mechanical[] が全ゲートスクリプトを invocation として持つ
    (CI harness が独立評価器と同じ決定論ゲート集合を走らせる)。"""
    expected = {_gate_script(g["command"]) for g in _gate_defs()}
    evals = json.loads((PLUGIN_ROOT / "EVALS.json").read_text(encoding="utf-8"))
    harness = "\n".join(evals["harness"]["mechanical"])
    missing = sorted(s for s in expected if s not in harness)
    assert not missing, f"EVALS.json mechanical[] が次のゲートスクリプトを欠く: {missing}"


def test_gate_defs_covers_specfm_plan_scoped_gates():
    """独立評価器 _gate_defs が specfm.evaluator_plan_gate_scripts (= GATE_SCRIPTS の
    plan-scoped 集合) を漏れなく実行する。

    2026-07-02 elegant-review (S2/S11): planner 側 SSOT GATE_SCRIPTS.extended へ
    check-runtime-portability を足したのに評価器 _gate_defs へ伝播せず、install 携帯性の
    壊れた plan が独立評価 (proposer≠approver) を PASS しうる Goodhart 穴を検出した。
    build-handoff (2026-06-30) と完全同型の再発。真因は GATE_SCRIPTS→_gate_defs を縛る
    parity 辺の不在。本テストが plan-scoped ゲートを足したら評価器が実行しないと fail させ、
    invocation 集合 parity の欠けていた辺を恒久で閉じる。"""
    sf = _load_specfm()
    runner = {_gate_script(g["command"]) for g in _gate_defs()}
    expected = set(sf.evaluator_plan_gate_scripts())
    assert runner == expected, (
        "evaluate-plan.py._gate_defs と specfm.evaluator_plan_gate_scripts が drift。"
        f"評価器欠落={sorted(expected - runner)} / 余剰={sorted(runner - expected)}。"
        "plan-scoped ゲートを増減したら _gate_defs と GATE_SCOPE を同時更新すること"
    )


def test_gate_scope_classifies_every_gate_script():
    """specfm.GATE_SCOPE が GATE_SCRIPTS の全 script を過不足なく scope 分類する
    (分類漏れ = scope 不明ゲートの無音混入。plan-scoped 集合の導出母数を健全に保つ)。"""
    sf = _load_specfm()
    assert set(sf.GATE_SCOPE) == set(sf.all_gate_scripts()), (
        "GATE_SCOPE と GATE_SCRIPTS が drift: "
        f"{sorted(set(sf.GATE_SCOPE) ^ set(sf.all_gate_scripts()))}"
    )


def test_evaluator_projections_invoke_mechanical_runner():
    """評価器の人間可読 projection (agent / assign SKILL の Step1 bash) が、全ゲートを束ねる
    決定論ランナー evaluate-plan.py を実際に起動する。projection が実行を伴わない『紙ゲート』へ
    退化する (今回 drift の構造) のを防ぐ。"""
    targets = {
        "agents/plugin-dev-plan-evaluator.md": PLUGIN_ROOT / "agents" / "plugin-dev-plan-evaluator.md",
        "assign-plugin-plan-evaluator/SKILL.md": SKILL_DIR / "SKILL.md",
    }
    for label, path in targets.items():
        assert "evaluate-plan.py" in _bash_blocks(path), (
            f"{label} の Step1 bash が evaluate-plan.py を起動しない "
            "(全ゲートを束ねる決定論ランナーを projection が踏まないと独立評価の穴になる)"
        )


def test_parity_guard_catches_dropped_gate():
    """本ガードが「ゲートを 1 本落とした」drift を確かに検出する回帰固定。"""
    runner = {g["id"]: (g["name"], tuple(g["conditions"])) for g in _gate_defs()}
    rubric = {g["id"]: (g["name"], tuple(g["conditions"])) for g in _rubric()["deterministic_gates"]}
    # 正例: 現状は一致
    assert runner == rubric
    # 負例: rubric から build-handoff (G8) を落とすと parity が崩れ検出される
    tampered = {k: v for k, v in rubric.items() if k != "G8"}
    assert runner != tampered


def test_condition_pass_when_covers_deterministic_gates():
    """plan-rubric.json の人間可読 conditions[C].pass_when が、同 rubric の deterministic_gates で
    その条件へ写像された全ゲートを必ず言及する (pass_when と deterministic_gates の内部ドリフト封止)。
    例: G7 check-surface-inventory→C2 を足したら C2.pass_when にも現れないと fail。"""
    rubric = _rubric()
    conditions = rubric["conditions"]
    for gate in rubric["deterministic_gates"]:
        token = gate["name"]
        for suffix in ("-self-test", "-plan"):  # 同一スクリプトの 2 起動を script 名へ正規化
            if token.endswith(suffix):
                token = token[: -len(suffix)]
        for cond in gate["conditions"]:
            pass_when = " ".join(conditions[cond]["pass_when"])
            assert token in pass_when, (
                f"deterministic_gates {gate['id']}({gate['name']})→{cond} だが "
                f"conditions.{cond}.pass_when が '{token}' を言及しない (rubric 内部ドリフト)"
            )


def test_global_thresholds_loaded_from_rubric_ssot():
    """評価器の閾値が plan-rubric.json global_thresholds から読まれる (ハードコード排除)。

    2026-06-30 elegant-review: rubric が medium_max を宣言しても runner はハードコードの
    `high_count==0` しか見ず、medium_max が空文化していた宣言↔実装 inconsistency を封止。
    閾値の二重定義を禁じ rubric SSOT 一本に固定する。
    """
    ev = _load_evaluator()
    loaded = ev._load_thresholds(SKILL_DIR)
    gt = _rubric()["global_thresholds"]
    assert loaded == {
        "high_max": int(gt["high_max"]),
        "medium_max": int(gt["medium_max"]),
        "all_deterministic_gates_exit0": bool(gt["all_deterministic_gates_exit0"]),
    }


def test_verdict_enforces_global_thresholds():
    """_verdict が high_max / medium_max / gates を rubric SSOT 通り機械強制する。

    medium が medium_max を超えたら FAIL になることを固定 (宣言だけで未強制だった穴の回帰)。
    """
    ev = _load_evaluator()
    th = ev._load_thresholds(SKILL_DIR)
    mmax = th["medium_max"]
    # medium: 境界以下は PASS / 超過は FAIL (high=high_max, gates exit0 固定)
    assert ev._verdict(th["high_max"], mmax, True, th) == "PASS"
    assert ev._verdict(th["high_max"], mmax + 1, True, th) == "FAIL", "medium_max 超過が FAIL にならない"
    # high_max 超過 / deterministic gate 非 exit0 も引き続き FAIL
    assert ev._verdict(th["high_max"] + 1, 0, True, th) == "FAIL"
    assert ev._verdict(th["high_max"], 0, False, th) == "FAIL"


def test_required_plugin_surfaces_parity_with_specfm():
    """評価器 REQUIRED_PLUGIN_SURFACES が specfm.PLUGIN_LEVEL_SURFACES と一致する。

    2026-06-30 elegant-review: 評価器は proposer (run-plugin-dev-plan) に依存しない独立性の
    ため surface 集合を独自保持する (意図的複製) が、両者が drift すると評価器が plugin-level
    surface の過不足を誤判定する。複製を許容しつつ drift を fail-closed 封止する
    (test_gate_defs_match_rubric / test_global_thresholds_loaded_from_rubric_ssot と同哲学)。
    """
    ev = _load_evaluator()
    sf = _load_specfm()
    assert tuple(ev.REQUIRED_PLUGIN_SURFACES) == tuple(sf.PLUGIN_LEVEL_SURFACES), (
        "評価器 REQUIRED_PLUGIN_SURFACES と specfm PLUGIN_LEVEL_SURFACES が drift。"
        "plugin-level surface を増減したら両定数を同時更新すること"
    )


# --- advisory semantic_checks (S3-S9) parity ---------------------------------
# S3 以降の意味判定は llm-only で mechanical runner (evaluate-plan.py) では縛れず、
# 評価者プロンプト prompts/R1-evaluate.md が唯一の実行契約。rubric に bucket を足したのに
# プロンプトへ判定手順が伝播しない drift を deterministic_gates と同じ forward-parity 哲学で封止する。


def _prompt_r1() -> str:
    return (SKILL_DIR / "prompts" / "R1-evaluate.md").read_text(encoding="utf-8")


def test_semantic_check_buckets_are_mentioned_in_prompt():
    """plan-rubric.json semantic_checks の各 bucket が prompts/R1-evaluate.md に必ず現れる。

    S3-S9 は llm-only advisory ゆえ機械 runner では実行契約を持てず、prompt が唯一の判定手順。
    rubric に bucket を追加したのに評価者プロンプトが判定手順を持たない drift を fail-closed 封止する
    (task-graph-consumer/execution-envelope(C17)/cycle-knowledge(C19) 等を足したら prompt 追従必須)。
    """
    prompt = _prompt_r1()
    rubric = _rubric()
    missing = [
        s["bucket"]
        for s in rubric["semantic_checks"]
        if s.get("bucket") and s["bucket"] not in prompt
    ]
    assert not missing, (
        f"plan-rubric.json semantic_checks の bucket が R1-evaluate.md に不在: {missing}。"
        "advisory semantic_check を足したら評価者プロンプトへ judgment 手順を追加すること"
    )


def test_semantic_check_buckets_are_mentioned_in_agent_md():
    """plan-rubric.json semantic_checks の各 bucket が agents/plugin-dev-plan-evaluator.md にも現れる。

    agent md は prompt R1-evaluate.md の fork 実体 (自己完結 7 層コピー)。rubric/prompt に bucket を
    足したのに agent 層へ判定手順が伝播しない drift (LS-6 で実捕捉: S5-S9 が prompt のみで agent md
    未伝播) を fail-closed 封止する。
    """
    agent_md = (SKILL_DIR.parent.parent / "agents" / "plugin-dev-plan-evaluator.md").read_text(
        encoding="utf-8")
    rubric = _rubric()
    missing = [
        s["bucket"]
        for s in rubric["semantic_checks"]
        if s.get("bucket") and s["bucket"] not in agent_md
    ]
    assert not missing, (
        f"plan-rubric.json semantic_checks の bucket が agents/plugin-dev-plan-evaluator.md に不在: "
        f"{missing}。advisory semantic_check を足したら agent md (fork 実体) へも判定手順を追加すること"
    )


def test_task_graph_projection_semantic_checks_present():
    """task-graph 射影の 5 意味判定 (S5-S9) が rubric に揃う。

    C8=task-graph-semantics / C14b=shape-ab-comparison / task-graph-consumer /
    C17=execution-envelope / C19=cycle-knowledge。C17/C19 を additive 追加した際の回帰固定。
    """
    names = {s["name"] for s in _rubric()["semantic_checks"]}
    for required in (
        "task-graph-semantics",
        "shape-ab-comparison",
        "task-graph-consumer",
        "execution-envelope",
        "cycle-knowledge",
    ):
        assert required in names, f"semantic_checks に {required} が無い (task-graph 射影 5 判定の欠落)"


def test_advisory_semantic_checks_have_uniform_shape():
    """bucket 付き advisory semantic_check (S3-S9) が統一 shape・llm-only・conditions=[] を保つ。

    S8/S9 を足した際に既存 (S3-S7) と異形にならず、機械 verdict accounting (G1-G11) へ
    混入しない (llm-only・C1-C4 verdict 非写像) ことを固定する。
    """
    required_keys = {
        "id", "name", "conditions", "bucket",
        "severity_on_fail", "source", "runner", "verdict_impact",
    }
    for s in _rubric()["semantic_checks"]:
        if not s.get("bucket"):
            continue  # S1/S2 は conditions へ写像する別 shape
        assert required_keys <= set(s), (
            f"{s.get('id')} が advisory semantic_check の統一 shape を欠く: "
            f"{sorted(required_keys - set(s))}"
        )
        assert s["runner"] == "llm-only", f"{s['id']} は llm-only であるべき (機械 verdict 非混入)"
        assert s["conditions"] == [], f"{s['id']} は conditions=[] (C1-C4 verdict へ非写像) であるべき"


def test_rubric_purpose_declares_full_semantic_check_range():
    """plan-rubric.json purpose の宣言 (S1-SN) が実際の semantic_checks 件数と一致する。

    purpose が 'S1-S7' のまま S8/S9 を足すと宣言↔実体の drift になる。宣言レンジの末尾番号を
    semantic_checks の最大 S 番号へ追従させる (人間可読宣言のドリフト封止)。
    """
    rubric = _rubric()
    max_n = max(int(s["id"][1:]) for s in rubric["semantic_checks"])
    assert f"S1-S{max_n}" in rubric["purpose"], (
        f"purpose が 'S1-S{max_n}' を宣言しない (semantic_checks 最大は S{max_n})。"
        f"purpose: {rubric['purpose']!r}"
    )

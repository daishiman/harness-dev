"""aggregate-evals.py の正規化・異常検出・3ソース合流を実証する。

外ループの負フィードバック検知 (連続 FAIL / スコア低下) と、
sink 断線解消で追加された score.jsonl + content-review verdict の合流が要点。
末尾に書込先 (env の明示 → project の state → user の state。plugin のツリーには書かない) と、
read-only での graceful degrade、提案を両方の置き場から読むことを追加。
引数は、hook が渡さない（空のときだけ hook の経路）ことと、引数があれば --list-proposals だけを受け、
綴り違いなどは exit 2 で止めて何も書かないことを固定する。
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-skill-rubric-governance"
    / "scripts"
    / "aggregate-evals.py"
)
SPEC = importlib.util.spec_from_file_location("aggregate_evals", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- 正規化: 各 sink を共通形へ ---

def test_normalize_score_record_passed_true_is_pass():
    rec = {
        "skill_name": "run-z",
        "passed": True,
        "score": 0.9,
        "timestamp": "2026-06-10T00:00:00Z",
        "findings": [],
    }
    n = MOD._normalize_score_record(rec)
    assert n["skill"] == "run-z"
    assert n["verdict"] == "PASS"
    assert n["date"] == "2026-06-10"


def test_normalize_score_record_passed_false_is_fail():
    rec = {"skill_name": "run-z", "passed": False, "timestamp": "2026-06-10T00:00:00Z"}
    assert MOD._normalize_score_record(rec)["verdict"] == "FAIL"


def test_normalize_score_record_without_skill_is_dropped():
    assert MOD._normalize_score_record({"passed": True}) is None


def test_normalize_verdict_record_reads_target_skill():
    rec = {
        "target": {"plugin": "p", "skill": "run-z"},
        "verdict": "FAIL",
        "reviewed_at": "2026-06-11T09:00:00+0900",
    }
    n = MOD._normalize_verdict_record(rec)
    assert n["skill"] == "run-z"
    assert n["verdict"] == "FAIL"
    assert n["date"] == "2026-06-11"


# --- 異常検出: 外ループの負フィードバック ---

def test_detect_consecutive_fail():
    evals = [
        {"skill": "run-x", "date": f"2026-06-0{i}", "verdict": "FAIL", "findings": []}
        for i in (1, 2, 3)
    ]
    anomalies = MOD._detect_anomalies(evals)
    assert any(a["kind"] == "consecutive_fail" and a["rubric_id"] == "run-x" for a in anomalies)


def test_two_fails_do_not_trigger_consecutive_fail():
    evals = [
        {"skill": "run-x", "date": f"2026-06-0{i}", "verdict": "FAIL", "findings": []}
        for i in (1, 2)
    ]
    assert not any(a["kind"] == "consecutive_fail" for a in MOD._detect_anomalies(evals))


def test_detect_score_drop():
    # 6 件: prior=最古1件(高スコア) vs recent=直近5件(低スコア) で 0.1 以上低下。
    scores = [1.0, 0.5, 0.5, 0.5, 0.5, 0.5]
    evals = [
        {"skill": "run-y", "date": f"2026-06-{i + 1:02d}", "verdict": "PASS", "score": s}
        for i, s in enumerate(scores)
    ]
    anomalies = MOD._detect_anomalies(evals)
    assert any(a["kind"] == "score_drop" and a["rubric_id"] == "run-y" for a in anomalies)


# --- 苦戦密度 (friction_density): PASS-only commit 制約下の第 3 発火条件 ---

def _pass_record(skill: str, date: str, iterations=1, negative=0, findings=None):
    return {
        "skill": skill,
        "date": date,
        "verdict": "PASS",
        "findings": findings or [],
        "iterations": iterations,
        "negative_feedback_count": negative,
    }


def test_normalize_verdict_record_carries_friction_fields():
    rec = {
        "target": {"plugin": "p", "skill": "run-z"},
        "verdict": "PASS",
        "reviewed_at": "2026-06-11T09:00:00+0900",
        "iterations": 3,
        "feedback_loop": {"negative_feedback": ["a", "b"]},
    }
    n = MOD._normalize_verdict_record(rec)
    assert n["iterations"] == 3
    assert n["negative_feedback_count"] == 2


def test_friction_density_fires_on_corroborated_iterations():
    # elegance + rubric の両 verdict が再評価ループ (iterations>=2) を要した skill。
    evals = [
        _pass_record("run-x", "2026-06-01", iterations=3),
        _pass_record("run-x", "2026-06-01", iterations=3),
    ]
    anomalies = MOD._detect_anomalies(evals)
    hit = [a for a in anomalies if a["kind"] == "friction_density"]
    assert hit and hit[0]["rubric_id"] == "run-x"
    assert hit[0]["friction_records"] == 2


def test_friction_density_fires_on_repeated_negative_feedback():
    evals = [
        _pass_record("run-y", "2026-06-01", negative=2),
        _pass_record("run-y", "2026-06-02", negative=2),
    ]
    assert any(a["kind"] == "friction_density" for a in MOD._detect_anomalies(evals))


def test_friction_density_counts_findings_volume():
    evals = [
        _pass_record("run-w", "2026-06-01", findings=["f1", "f2", "f3"]),
        _pass_record("run-w", "2026-06-02", iterations=2),
    ]
    assert any(a["kind"] == "friction_density" for a in MOD._detect_anomalies(evals))


def test_single_friction_record_does_not_fire():
    # 単独レビューアの摩擦のみでは発火しない (相互裏付け _FRICTION_MIN_RECORDS=2)。
    evals = [
        _pass_record("run-x", "2026-06-01", iterations=3),
        _pass_record("run-x", "2026-06-01"),
    ]
    assert not any(a["kind"] == "friction_density" for a in MOD._detect_anomalies(evals))


def test_light_negative_feedback_does_not_fire():
    # negative_feedback 1 件 (iterations=1) は正常な指摘量であり摩擦扱いしない。
    evals = [
        _pass_record("run-x", "2026-06-01", negative=1),
        _pass_record("run-x", "2026-06-01", negative=1),
    ]
    assert not any(a["kind"] == "friction_density" for a in MOD._detect_anomalies(evals))


def test_legacy_evals_records_without_friction_fields_do_not_fire():
    # EVALS.json 旧形式 (iterations/negative_feedback_count 欠落) は非該当。
    evals = [
        {"skill": "run-x", "date": "2026-05-22", "verdict": "baseline", "findings": []},
        {"skill": "run-x", "date": "2026-05-23", "verdict": "baseline", "findings": []},
    ]
    assert not any(a["kind"] == "friction_density" for a in MOD._detect_anomalies(evals))


def test_friction_outside_recent_window_does_not_fire():
    # 古い摩擦 2 件が直近窓 (6件) の外へ押し出されれば発火しない。
    old = [
        _pass_record("run-x", "2026-05-01", iterations=3),
        _pass_record("run-x", "2026-05-02", iterations=3),
    ]
    clean = [_pass_record("run-x", f"2026-06-{i:02d}") for i in range(1, 7)]
    assert not any(
        a["kind"] == "friction_density" for a in MOD._detect_anomalies(old + clean)
    )


# --- 3 ソース合流 (sink 断線解消) ---

def test_load_evals_merges_score_jsonl_and_verdict(monkeypatch, tmp_path):
    eval_log = tmp_path / "eval-log"
    # score.jsonl sink
    score_dir = eval_log / "demo"
    score_dir.mkdir(parents=True)
    (score_dir / "2026-06-10-score.jsonl").write_text(
        json.dumps({
            "skill_name": "run-x", "passed": True, "score": 0.8,
            "timestamp": "2026-06-10T00:00:00Z", "findings": [],
        }) + "\n",
        encoding="utf-8",
    )
    # content-review verdict sink
    cr_dir = eval_log / "demo" / "run-y" / "content-review"
    cr_dir.mkdir(parents=True)
    (cr_dir / "elegance-verdict.json").write_text(
        json.dumps({
            "target": {"plugin": "demo", "skill": "run-y"},
            "verdict": "FAIL", "reviewed_at": "2026-06-11T00:00:00Z",
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")

    evals = MOD._load_evals()["evaluations"]
    skills = {e["skill"] for e in evals}
    assert {"run-x", "run-y"}.issubset(skills)


def _write_review_round(cr_dir, *, skill, reviewed_at, iterations, negatives, kinds=("elegance", "rubric")):
    """content-review 規約どおり、1 レビューを複数ファイルへ同値投影する。"""
    cr_dir.mkdir(parents=True, exist_ok=True)
    for kind in kinds:
        (cr_dir / f"{kind}-verdict.json").write_text(
            json.dumps({
                "target": {"plugin": "demo", "skill": skill},
                "verdict": "PASS",
                "reviewed_at": reviewed_at,
                "iterations": iterations,
                "feedback_loop": {"negative_feedback": ["n"] * negatives},
            }),
            encoding="utf-8",
        )


def test_review_projections_of_one_round_collapse_to_one_record(monkeypatch, tmp_path):
    """elegance/rubric の 2 ファイル投影は 1 レビュー = 1 レコードへ畳まれる。"""
    eval_log = tmp_path / "eval-log"
    _write_review_round(
        eval_log / "demo" / "run-y" / "content-review",
        skill="run-y", reviewed_at="2026-06-11T00:00:00Z", iterations=4, negatives=4,
    )
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)

    recs = MOD._load_content_review_verdicts()
    assert len(recs) == 1
    assert recs[0]["iterations"] == 4
    assert recs[0]["negative_feedback_count"] == 4


def test_self_corroborating_projections_do_not_fire_friction_density(monkeypatch, tmp_path):
    """自分自身のコピーでは相互裏付けにならない (これが二重計上バグの本体)。"""
    eval_log = tmp_path / "eval-log"
    _write_review_round(
        eval_log / "demo" / "run-y" / "content-review",
        skill="run-y", reviewed_at="2026-06-11T00:00:00Z", iterations=4, negatives=4,
    )
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)

    evals = MOD._load_content_review_verdicts()
    assert not any(a["kind"] == "friction_density" for a in MOD._detect_anomalies(evals))


def test_distinct_rounds_still_corroborate_each_other():
    """畳んでも、別ラウンド 2 件の本物の裏付けは従来どおり発火する。

    content-review の verdict は同じ 2 ファイルを毎回上書きするので、eval-log 上に別ラウンドが
    並ぶのは score.jsonl / live-trial など他 sink と合流した後になる。ここは合流後の窓を
    直接組んで、畳み込みが「別レコード同士の裏付け」まで潰していないことを見る。
    """
    evals = [
        {"skill": "run-y", "date": "2026-06-11", "verdict": "PASS", "iterations": 4,
         "negative_feedback_count": 4, "findings": []},
        {"skill": "run-y", "date": "2026-06-12", "verdict": "PASS", "iterations": 4,
         "negative_feedback_count": 4, "findings": []},
    ]
    hit = [a for a in MOD._detect_anomalies(evals) if a["kind"] == "friction_density"]
    assert len(hit) == 1
    assert hit[0]["friction_records"] == 2


def test_same_day_distinct_rounds_are_not_collapsed():
    """同日 2 回のレビューは別ラウンド。date へ丸めて畳むと本物の裏付けが消える。"""
    am = {"skill": "run-y", "date": "2026-06-11", "reviewed_at": "2026-06-11T01:00:00Z"}
    pm = {"skill": "run-y", "date": "2026-06-11", "reviewed_at": "2026-06-11T20:00:00Z"}
    assert MOD._review_identity(am) != MOD._review_identity(pm)


def test_same_round_projections_share_one_identity():
    """同一ラウンドの 2 投影は reviewed_at が同値なので同じキーになる。"""
    a = {"skill": "run-y", "date": "2026-06-11", "reviewed_at": "2026-06-11T01:00:00Z"}
    b = dict(a)
    assert MOD._review_identity(a) == MOD._review_identity(b)


def test_merge_keeps_the_larger_friction_when_projections_disagree(monkeypatch, tmp_path):
    """片方だけ更新された中途半端な状態では、摩擦の大きい側を採って情報を捨てない。"""
    cr_dir = tmp_path / "eval-log" / "demo" / "run-y" / "content-review"
    cr_dir.mkdir(parents=True)
    # elegance は sorted() 順で先に読まれる。先勝ちなら iterations=1 が残ってしまう。
    for kind, iterations, negatives in (("elegance", 1, 0), ("rubric", 5, 3)):
        (cr_dir / f"{kind}-verdict.json").write_text(
            json.dumps({
                "target": {"plugin": "demo", "skill": "run-y"},
                "verdict": "PASS",
                "reviewed_at": "2026-06-11T00:00:00Z",
                "iterations": iterations,
                "feedback_loop": {"negative_feedback": ["n"] * negatives},
            }),
            encoding="utf-8",
        )
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "eval-log")

    recs = MOD._load_content_review_verdicts()
    assert len(recs) == 1
    assert recs[0]["iterations"] == 5
    assert recs[0]["negative_feedback_count"] == 3


def test_merge_survives_missing_iterations(monkeypatch, tmp_path):
    """iterations は verdict に無ければ None。max へ直接渡すと TypeError で落ちる。"""
    cr_dir = tmp_path / "eval-log" / "demo" / "run-y" / "content-review"
    cr_dir.mkdir(parents=True)
    for kind, rec in (
        ("elegance", {"verdict": "PASS", "reviewed_at": "2026-06-11T00:00:00Z"}),
        ("rubric", {"verdict": "PASS", "reviewed_at": "2026-06-11T00:00:00Z", "iterations": 3}),
    ):
        rec["target"] = {"plugin": "demo", "skill": "run-y"}
        (cr_dir / f"{kind}-verdict.json").write_text(json.dumps(rec), encoding="utf-8")
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "eval-log")

    recs = MOD._load_content_review_verdicts()
    assert len(recs) == 1
    assert recs[0]["iterations"] == 3


def test_different_skills_are_never_collapsed(monkeypatch, tmp_path):
    """同時刻でも skill が違えば別レコード。"""
    eval_log = tmp_path / "eval-log"
    for skill in ("run-y", "run-z"):
        _write_review_round(
            eval_log / "demo" / skill / "content-review",
            skill=skill, reviewed_at="2026-06-11T00:00:00Z", iterations=4, negatives=4,
        )
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)

    assert {r["skill"] for r in MOD._load_content_review_verdicts()} == {"run-y", "run-z"}


def test_load_evals_empty_when_no_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "missing")
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    assert MOD._load_evals()["evaluations"] == []


# --- 書込先移植性 (read-only install での graceful degrade) ---

def _anomalous_score_jsonl(eval_log: Path) -> None:
    """3 連続 FAIL を含む score.jsonl を仕込み、必ず anomaly を発火させる。"""
    d = eval_log / "demo"
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({
            "skill_name": "run-x", "passed": False,
            "timestamp": f"2026-06-0{i}T00:00:00Z", "findings": [],
        })
        for i in (1, 2, 3)
    ]
    (d / "2026-06-03-score.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _state_env(monkeypatch, tmp_path, *, project=True):
    """書込先を決める env を tmp にそろえる。実 repo と実 home の state を指さない。"""
    monkeypatch.delenv("HARNESS_CREATOR_PROPOSALS_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    if project:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "proj"))
    else:
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    project_dir = tmp_path / "proj" / ".claude" / "state" / "harness-creator" / "proposals"
    user_dir = tmp_path / "xdg" / "harness-creator" / "proposals"
    return project_dir, user_dir


def test_default_proposals_dir_is_project_state(monkeypatch, tmp_path):
    project_dir, _ = _state_env(monkeypatch, tmp_path)
    assert MOD._proposals_dir() == project_dir
    assert MOD._plugin_root().name == "harness-creator"


def test_proposals_env_override_is_sole_candidate(monkeypatch, tmp_path):
    _state_env(monkeypatch, tmp_path)
    monkeypatch.setenv("HARNESS_CREATOR_PROPOSALS_DIR", str(tmp_path / "pd"))
    assert MOD._candidate_proposals_dirs() == [(tmp_path / "pd").resolve()]


def test_candidates_are_project_state_then_user_state(monkeypatch, tmp_path):
    project_dir, user_dir = _state_env(monkeypatch, tmp_path)
    assert MOD._candidate_proposals_dirs() == [project_dir, user_dir]


def test_candidates_without_project_dir_use_user_state_once(monkeypatch, tmp_path):
    _, user_dir = _state_env(monkeypatch, tmp_path, project=False)
    assert MOD._candidate_proposals_dirs() == [user_dir]


def test_candidates_never_point_into_the_plugin_tree(monkeypatch, tmp_path):
    """plugin のディレクトリを cwd にして session を回すと $CLAUDE_PROJECT_DIR が plugin 自身を
    指す。そのまま書くと plugin の中に生成物が落ち、fingerprint が動く。"""
    _, user_dir = _state_env(monkeypatch, tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(MOD._plugin_root()))
    candidates = MOD._candidate_proposals_dirs()
    assert candidates == [user_dir]
    assert not any(MOD._is_inside_plugin(d) for d in candidates)


def test_main_writes_to_project_state_not_plugin_tree(monkeypatch, tmp_path, capsys):
    """候補の決め方を差し替えずに main を流し、書いた先が project の state であって、
    手書きの提案が残る従来の置き場には何も増えないことを確かめる。"""
    project_dir, user_dir = _state_env(monkeypatch, tmp_path)
    eval_log = tmp_path / "eval-log"
    _anomalous_score_jsonl(eval_log)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    legacy = MOD._legacy_proposals_dir()
    before = sorted(p.name for p in legacy.glob("*"))
    assert MOD.main() == 0
    written = list(project_dir.glob("*-rubric-update.md"))
    assert len(written) == 1, "project の state に提案が書かれていない"
    assert MOD._GENERATED_MARKER in written[0].read_text(encoding="utf-8")
    assert not user_dir.exists()
    assert sorted(p.name for p in legacy.glob("*")) == before, "plugin のツリーに書いた"
    assert str(written[0]) in capsys.readouterr().err


def test_list_proposals_reads_both_places(monkeypatch, tmp_path, capsys):
    """自動ドラフトは state に、手書きの提案は従来の置き場にある。片方だけ読むと見落とす。"""
    project_dir, _ = _state_env(monkeypatch, tmp_path)
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "2026-10-09-ja-heading-alias.md").write_text("status: applied\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "_legacy_proposals_dir", lambda: legacy)
    project_dir.mkdir(parents=True)
    (project_dir / "2026-10-12-rubric-update.md").write_text(
        MOD._render_proposal([], [], {}), encoding="utf-8"
    )
    assert MOD.main(["--list-proposals"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dirs"][0] == str(project_dir)
    assert out["dirs"][-1] == str(legacy)
    assert {(Path(p["path"]).name, p["generated"]) for p in out["proposals"]} == {
        ("2026-10-12-rubric-update.md", True),
        ("2026-10-09-ja-heading-alias.md", False),
    }


# --- 引数: hook は渡さない。手で流すときは --list-proposals だけ ---

HOOK_ENTRY = ROOT / "plugins" / "harness-creator" / "hooks" / "aggregate-evals.py"
HOOK_CONFIGS = (
    ROOT / "plugins" / "harness-creator" / "hooks" / "hooks.json",
    ROOT / ".codex" / "hooks" / "registry.json",
)


def _anomalous_main_env(monkeypatch, tmp_path):
    """hook の経路へ進めば必ず提案を書く状態にする。書いたかどうかで、どちらの経路へ進んだかが分かる。"""
    project_dir, user_dir = _state_env(monkeypatch, tmp_path)
    eval_log = tmp_path / "eval-log"
    _anomalous_score_jsonl(eval_log)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    return project_dir, user_dir


@pytest.mark.parametrize("argv", [
    ["--list-proposal"], ["--list"], ["--list-proposals", "extra"], ["--"], ["-x"], ["--dry-run"],
])
def test_unknown_args_exit_2_without_writing(monkeypatch, tmp_path, capsys, argv):
    # 以前は --list-proposals と完全に一致しない引数を hook の経路へ流し、一覧のつもりの綴り違いで提案を書いていた
    project_dir, user_dir = _anomalous_main_env(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as exc:
        MOD.main(argv)
    assert exc.value.code == 2
    assert "usage:" in capsys.readouterr().err
    assert not project_dir.exists() and not user_dir.exists()


def test_help_prints_usage_and_exits_0(monkeypatch, tmp_path, capsys):
    project_dir, user_dir = _anomalous_main_env(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as exc:
        MOD.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "usage:" in out and "--list-proposals" in out
    assert not project_dir.exists() and not user_dir.exists()


def test_empty_argv_is_the_hook_path(monkeypatch, tmp_path):
    project_dir, _ = _anomalous_main_env(monkeypatch, tmp_path)
    assert MOD.main([]) == 0
    assert len(list(project_dir.glob("*-rubric-update.md"))) == 1


def _commands(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                yield value
            else:
                yield from _commands(value)
    elif isinstance(node, list):
        for value in node:
            yield from _commands(value)


def test_hook_configs_call_the_entry_without_args():
    """hook の経路は argv が空のときだけ。設定が引数を付けると、SessionEnd のたびに exit 2 で止まる。"""
    for config in HOOK_CONFIGS:
        commands = [c for c in _commands(json.loads(config.read_text(encoding="utf-8")))
                    if "hooks/aggregate-evals.py" in c]
        assert commands, config
        for command in commands:
            assert command.rstrip().endswith('hooks/aggregate-evals.py"'), (config, command)


def test_hook_entry_forwards_args_to_the_parser(tmp_path):
    """shim は argv を素通しする。shim を手で叩いても、綴り違いは exit 2 で止まり何も書かない。"""
    proposals = tmp_path / "pd"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    env.update(HOME=str(tmp_path / "home"), CLAUDE_PROJECT_DIR=str(tmp_path / "proj"),
               XDG_STATE_HOME=str(tmp_path / "xdg"), HARNESS_CREATOR_PROPOSALS_DIR=str(proposals),
               PYTHONDONTWRITEBYTECODE="1")

    def run(*args):
        return subprocess.run([sys.executable, str(HOOK_ENTRY), *args], env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=30)

    bad = run("--list-proposal")
    assert bad.returncode == 2 and "usage:" in bad.stderr, bad.stderr
    shown = run("--help")
    assert shown.returncode == 0 and "--list-proposals" in shown.stdout, shown.stderr
    assert not proposals.exists()


def _git_repo_with_draft(tmp_path) -> tuple[Path, Path]:
    """.git のある作業ツリーと、その project の state に置いた自動ドラフトを作る。"""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "sub").mkdir()
    state = repo / ".claude" / "state" / "harness-creator" / "proposals"
    state.mkdir(parents=True)
    (state / "2026-10-12-rubric-update.md").write_text(MOD._render_proposal([], [], {}), encoding="utf-8")
    return repo.resolve(), state.resolve()


def test_list_proposals_without_project_dir_reads_git_toplevel_state(monkeypatch, tmp_path, capsys):
    """Bash から手で流すと CLAUDE_PROJECT_DIR が無い。hook が project の state に書いた自動ドラフトを
    見落とさないよう、cwd を含む git の作業ツリーの root を project とみなして読む。"""
    _, user_dir = _state_env(monkeypatch, tmp_path, project=False)
    repo, state = _git_repo_with_draft(tmp_path)
    monkeypatch.chdir(repo / "sub")
    assert MOD.main(["--list-proposals"]) == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert str(state) in out["dirs"]
    assert str(user_dir) in out["dirs"]
    assert (str(state / "2026-10-12-rubric-update.md"), True) in {
        (p["path"], p["generated"]) for p in out["proposals"]
    }
    assert "CLAUDE_PROJECT_DIR が無い" in captured.err


def test_list_proposals_without_project_dir_reads_cwd_state(monkeypatch, tmp_path):
    """git の作業ツリーの外でも、cwd を project とみなして読む。"""
    _state_env(monkeypatch, tmp_path, project=False)
    proj = tmp_path / "plain"
    state = proj / ".claude" / "state" / "harness-creator" / "proposals"
    state.mkdir(parents=True)
    monkeypatch.chdir(proj)
    assert state.resolve() in MOD._proposal_read_dirs()


def test_inferred_project_state_is_read_only(monkeypatch, tmp_path):
    """推し量った project は読む側だけで使う。書き先には足さない（hook の書き先とずれると提案が散らばる）。"""
    _, user_dir = _state_env(monkeypatch, tmp_path, project=False)
    repo, state = _git_repo_with_draft(tmp_path)
    monkeypatch.chdir(repo)
    assert MOD._candidate_proposals_dirs() == [user_dir]
    assert state in MOD._proposal_read_dirs()


def test_inferred_project_state_skips_plugin_tree(monkeypatch, tmp_path):
    """cwd が plugin の中でも、推し量った置き場が plugin のツリーを指すことはない。"""
    _state_env(monkeypatch, tmp_path, project=False)
    monkeypatch.chdir(MOD._plugin_root())
    dirs = MOD._proposal_read_dirs()
    inside = [d for d in dirs if MOD._is_inside_plugin(d)]
    assert inside == [MOD._legacy_proposals_dir()]


def test_project_dir_env_disables_inference(monkeypatch, tmp_path):
    """CLAUDE_PROJECT_DIR があれば、それだけを project とみなす（cwd は推し量らない）。"""
    project_dir, _ = _state_env(monkeypatch, tmp_path)
    repo, state = _git_repo_with_draft(tmp_path)
    monkeypatch.chdir(repo)
    dirs = MOD._proposal_read_dirs()
    assert dirs[0] == project_dir
    assert state not in dirs


def test_main_writes_to_primary_when_writable(monkeypatch, tmp_path, capsys):
    eval_log = tmp_path / "eval-log"
    _anomalous_score_jsonl(eval_log)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    primary = tmp_path / "proposals"
    monkeypatch.setattr(MOD, "_candidate_proposals_dirs", lambda: [primary, tmp_path / "fb"])
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    rc = MOD.main()
    assert rc == 0
    assert list(primary.glob("*-rubric-update.md")), "primary に提案が書かれていない"
    assert "proposal ->" in capsys.readouterr().err


def test_main_falls_back_when_primary_unwritable(monkeypatch, tmp_path, capsys):
    eval_log = tmp_path / "eval-log"
    _anomalous_score_jsonl(eval_log)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    primary = tmp_path / "ro" / "proposals"
    fallback = tmp_path / "state" / "proposals"
    monkeypatch.setattr(MOD, "_candidate_proposals_dirs", lambda: [primary, fallback])
    monkeypatch.setattr(MOD, "_dir_is_writable", lambda d: d == fallback)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    rc = MOD.main()
    assert rc == 0
    assert list(fallback.glob("*-rubric-update.md")), "fallback に退避されていない"


def test_main_noop_exit0_when_no_writable_sink(monkeypatch, tmp_path, capsys):
    eval_log = tmp_path / "eval-log"
    _anomalous_score_jsonl(eval_log)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    monkeypatch.setattr(MOD, "_candidate_proposals_dirs", lambda: [tmp_path / "a", tmp_path / "b"])
    monkeypatch.setattr(MOD, "_dir_is_writable", lambda d: False)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    rc = MOD.main()
    assert rc == 0
    err = capsys.readouterr().err
    assert "no writable sink" in err
    assert "Traceback" not in err

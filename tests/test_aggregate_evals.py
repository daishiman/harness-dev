"""aggregate-evals.py の正規化・異常検出・3ソース合流を実証する。

外ループの負フィードバック検知 (連続 FAIL / スコア低下) と、
sink 断線解消で追加された score.jsonl + content-review verdict の合流が要点。
末尾に書込先移植性 (3 段 fallback: read-only install での graceful degrade) を追加。
"""
import importlib.util
import io
import json
from pathlib import Path


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


def test_default_proposals_dir_is_plugin_root(monkeypatch):
    monkeypatch.delenv("HARNESS_CREATOR_PROPOSALS_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    d = MOD._proposals_dir()
    assert d.name == "proposals"
    assert d.parent.name == "run-skill-rubric-governance"
    assert MOD._plugin_root().name == "harness-creator"


def test_proposals_env_override_is_sole_candidate(monkeypatch, tmp_path):
    monkeypatch.setenv("HARNESS_CREATOR_PROPOSALS_DIR", str(tmp_path / "pd"))
    assert MOD._candidate_proposals_dirs() == [(tmp_path / "pd").resolve()]


def test_state_fallback_prefers_project_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "proj"))
    assert MOD._state_fallback_root() == tmp_path / "proj" / ".claude" / "state" / "harness-creator"


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

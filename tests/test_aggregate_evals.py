"""aggregate-evals.py の正規化・異常検出・入力源の合流・観測差分の書き込みを実証する。

外ループの負フィードバック検知 (連続 FAIL / スコア低下 / 苦戦の重なり) と、
score.jsonl + content-review verdict + live-trial の合流が要点。
契約ごとに正本を分ける:
- 書込先 (env の明示 → project の state → user の state。plugin のツリーには書かない)、
  read-only での graceful degrade、--list-proposals、marker は 0.2.x の契約をそのまま固定する。
- target の正準化・score の単位・episode の識別 (skill_md_sha256)・health・delta は 0.3.0 で移した契約。
引数は、hook が渡さない（空のときだけ hook の経路）ことと、引数があれば --list-proposals だけを受け、
綴り違いなどは exit 2 で止めて何も書かないことを固定する。
loader の失敗注入・lock の backend・render の細部は
tests/scripts-plugins/test_harness_creator__aggregate_evals.py が受け持つ。
"""
import datetime as dt
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
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
CONTENT_REVIEW_SCHEMA_PATH = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "schemas"
    / "content-review-verdict.schema.json"
)


@pytest.fixture(autouse=True)
def _isolated_lock_dir(tmp_path_factory, monkeypatch):
    """_sink_lock は OS の一時ディレクトリに書込先ごとの lock ファイルを残す。テストの分は pytest の一時領域に閉じる。

    tmp_path の外に置くのは、tmp_path の中身を数えるテスト (一時ファイルの残りが無いこと) を乱さないため。
    """
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path_factory.mktemp("os-tmp")))


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
    assert n["skill"] == "p:run-z"
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
        {"skill": "run-y", "date": f"2026-06-{i + 1:02d}", "verdict": "PASS", "score": s,
         "score_unit": "ratio"}
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
    assert hit[0]["friction_episodes"] == 2


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
    # 単独レビューアの摩擦のみでは発火しない (相互裏付け _FRICTION_MIN_EPISODES=2)。
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
    # target は plugin:skill。score.jsonl の plugin は eval-log/<plugin>/ から取る
    assert {"demo:run-x", "demo:run-y"}.issubset(skills)


DIGEST = "0" * 64


def _write_review_round(cr_dir, *, skill, reviewed_at, iterations, negatives,
                        kinds=("elegance", "rubric"), digest=DIGEST):
    """content-review 規約どおり、1 レビューを複数ファイルへ同値投影する (skill_md_sha256 付き)。"""
    cr_dir.mkdir(parents=True, exist_ok=True)
    for kind in kinds:
        (cr_dir / f"{kind}-verdict.json").write_text(
            json.dumps({
                "target": {"plugin": "demo", "skill": skill, "skill_md_sha256": digest},
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
    assert hit[0]["friction_episodes"] == 2


def test_same_day_reviews_of_different_skill_md_are_not_collapsed():
    """同日 2 回のレビューでも、SKILL.md の版 (digest) が違えば別のレビュー。"""
    am = {"skill": "demo:run-y", "date": "2026-06-11", "reviewed_at": "2026-06-11T01:00:00Z",
          "skill_md_sha256": "a" * 64}
    pm = {"skill": "demo:run-y", "date": "2026-06-11", "reviewed_at": "2026-06-11T20:00:00Z",
          "skill_md_sha256": "b" * 64}
    assert MOD._review_identity(am) != MOD._review_identity(pm)


def test_same_digest_projections_share_one_identity_despite_timestamps():
    """同じ版の SKILL.md を見た 2 投影は、reviewed_at が数秒ずれても 1 レビュー。"""
    a = {"skill": "demo:run-y", "date": "2026-06-11", "reviewed_at": "2026-06-11T01:00:00Z",
         "skill_md_sha256": "a" * 64}
    b = dict(a, reviewed_at="2026-06-11T01:00:03Z")
    assert MOD._review_identity(a) == MOD._review_identity(b)


def test_fallback_identity_keeps_same_day_rounds_apart():
    """digest の無い記録は (skill, reviewed_at, date) で数える。date へ丸めて畳むと本物の裏付けが消える。"""
    am = {"skill": "demo:run-y", "date": "2026-06-11", "reviewed_at": "2026-06-11T01:00:00Z"}
    pm = {"skill": "demo:run-y", "date": "2026-06-11", "reviewed_at": "2026-06-11T20:00:00Z"}
    assert MOD._review_identity(am) != MOD._review_identity(pm)
    assert MOD._review_identity(am)[0] == "fallback"


def test_fallback_identity_joins_same_round_projections():
    """digest の無い同一ラウンドの 2 投影は reviewed_at が同値なので同じキーになる。"""
    a = {"skill": "demo:run-y", "date": "2026-06-11", "reviewed_at": "2026-06-11T01:00:00Z"}
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
                "target": {"plugin": "demo", "skill": "run-y", "skill_md_sha256": DIGEST},
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
    """iterations は verdict に無ければ None。max へ直接渡すと TypeError で落ちる。

    digest の無い古い記録のまま残し、fallback キーでも 2 投影が 1 件に畳まれることを見る。
    """
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
    assert recs[0]["digest_missing"] is True


def test_different_skills_are_never_collapsed(monkeypatch, tmp_path):
    """同時刻でも skill が違えば別レコード。"""
    eval_log = tmp_path / "eval-log"
    for skill in ("run-y", "run-z"):
        _write_review_round(
            eval_log / "demo" / skill / "content-review",
            skill=skill, reviewed_at="2026-06-11T00:00:00Z", iterations=4, negatives=4,
        )
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)

    assert {r["skill"] for r in MOD._load_content_review_verdicts()} == {"demo:run-y", "demo:run-z"}


def test_load_evals_empty_when_no_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "missing")
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    loaded = MOD._load_evals()
    assert loaded["evaluations"] == []
    # 入力源が無いのは空の入力で健全 (absent)。欠けた入力 (incomplete) とは分ける
    assert loaded["health"]["complete"] is True
    assert {h["status"] for h in loaded["health"]["sources"].values()} == {"absent"}


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


# --- 識別: target の正準化・score の単位・episode (0.3.0 で移した契約) ---

def test_canonical_target_removes_absolute_worktree_path():
    target = MOD._canonical_target(
        "/Users/alice/project/.worktrees/x/"
        "plugins/dev-graph/skills/run-dev-graph-schedule/SKILL.md"
    )
    assert target == "dev-graph:run-dev-graph-schedule"
    assert not target.startswith("/")


def test_invalid_plugin_value_never_leaks_path():
    target = MOD._canonical_target({"plugin": "/Users/alice/private/repo", "skill": "run-x"})
    assert target.endswith(":run-x")
    assert "/Users/" not in target


def test_score_scale_boundaries_share_one_internal_unit():
    assert MOD._normalize_score(90, scale="percent") == 0.9
    assert MOD._normalize_score(1, scale="percent") == 0.01
    assert MOD._normalize_score(0.9, scale="ratio") == 0.9
    assert MOD._normalize_score(1.0, scale="ratio") == 1.0
    assert MOD._normalize_score(-1, scale="percent") is None
    assert MOD._normalize_score(101, scale="percent") is None
    assert MOD._normalize_score(True, scale="ratio") is None


def test_score_jsonl_score_is_read_as_percent():
    """write-eval-log の score は 0..100。0..1 に揃えて持ち、元の単位も残す。"""
    rec = {"skill_name": "run-z", "passed": True, "score": 85, "timestamp": "2026-06-10T00:00:00Z"}
    n = MOD._normalize_score_record(rec, plugin="demo")
    assert n["skill"] == "demo:run-z"
    assert n["score"] == 0.85
    assert n["score_unit"] == "ratio"
    assert n["source_score_scale"] == "percent"
    assert MOD._score_of(n) == 0.85
    out_of_range = MOD._normalize_score_record(dict(rec, score=150), plugin="demo")
    assert out_of_range["score"] is None


def test_score_without_declared_unit_is_ignored():
    """単位の宣言が無い score は平均に混ぜない (percent と ratio の取り違えで score_drop が誤発火する)。"""
    assert MOD._score_of({"score": 0.5}) is None
    assert MOD._score_of({"score": 50, "score_unit": "percent"}) == 0.5


def test_score_drop_detection_is_scale_invariant():
    ratios = [1.0, 0.5, 0.5, 0.5, 0.5, 0.5]
    percentages = [100, 50, 50, 50, 50, 50]

    def detect(scores, scale):
        records = [
            {
                "skill": "run-y",
                "observed_at": f"2026-06-{index + 1:02d}T00:00:00Z",
                "verdict": "PASS",
                "score": MOD._normalize_score(score, scale=scale),
                "score_unit": "ratio",
            }
            for index, score in enumerate(scores)
        ]
        return next(
            anomaly for anomaly in MOD._detect_anomalies(records) if anomaly["kind"] == "score_drop"
        )

    assert detect(ratios, "ratio")["drop"] == detect(percentages, "percent")["drop"] == 0.5


def _content_raw(*, digest, reviewed_at, view, skill="run-x"):
    """content-review-verdict.schema.json に沿った 1 投影。"""
    return {
        "target": {"plugin": "demo", "skill": skill, "skill_md_sha256": digest},
        "review_kind": view,
        "verdict": "PASS",
        "reviewer": "independent-test-reviewer",
        "reviewed_at": reviewed_at,
        "iterations": 3,
        "feedback_loop": {
            "loop_scope": "both",
            "criteria_evaluated": ["identity"],
            "positive_feedback": ["schema-conforming fixture"],
            "negative_feedback": [],
            "iteration": 3,
            "iteration_limit": 3,
            "hook_trigger": "test",
            "next_action": "none",
        },
    }


def _content_record(*, digest, reviewed_at, view):
    return MOD._normalize_verdict_record(
        _content_raw(digest=digest, reviewed_at=reviewed_at, view=view), source_view=view
    )


def test_content_review_fixture_conforms_to_schema():
    """fixture が実際の verdict の形から外れていないこと (jsonschema を読めない環境では飛ばす)。

    importorskip は ModuleNotFoundError しか飛ばさない。拡張の arch 違いなどの ImportError も飛ばす。
    """
    try:
        import jsonschema
    except ImportError as exc:
        pytest.skip(f"jsonschema を読み込めない: {exc}")
    schema = json.loads(CONTENT_REVIEW_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(
        _content_raw(digest="a" * 64, reviewed_at="2026-06-01T00:00:00Z", view="elegance")
    )


def test_content_review_views_share_episode_and_do_not_double_count():
    elegance = _content_record(digest="abc", reviewed_at="2026-06-01T00:00:00Z", view="elegance")
    rubric = _content_record(digest="abc", reviewed_at="2026-06-01T00:00:00Z", view="rubric")

    assert elegance["skill"] == "demo:run-x"
    assert elegance["source_kind"] == "content-review"
    assert elegance["episode_id"] == rubric["episode_id"]
    merged = MOD._coalesce_episodes([elegance, rubric])
    assert len(merged) == 1
    assert merged[0]["source_views"] == ["elegance", "rubric"]
    assert not any(
        anomaly["kind"] == "friction_density"
        for anomaly in MOD._detect_anomalies([elegance, rubric])
    )


def test_content_views_coalesce_same_digest_despite_different_timestamps():
    elegance = _content_record(digest="abc", reviewed_at="2026-06-01T00:00:00Z", view="elegance")
    rubric = _content_record(digest="abc", reviewed_at="2026-06-01T00:00:03Z", view="rubric")
    assert elegance["episode_id"] == rubric["episode_id"]
    merged = MOD._coalesce_episodes([elegance, rubric])
    assert len(merged) == 1
    # 代表は最新の reviewed_at
    assert merged[0]["observed_at"] == "2026-06-01T00:00:03Z"


def test_coalesce_is_idempotent():
    """loader で畳んだ episode を _detect_anomalies がもう一度畳んでも同じ結果になる。"""
    elegance = _content_record(digest="abc", reviewed_at="2026-06-01T00:00:00Z", view="elegance")
    rubric = _content_record(digest="abc", reviewed_at="2026-06-01T00:00:03Z", view="rubric")
    once = MOD._coalesce_episodes([elegance, rubric])
    assert MOD._coalesce_episodes(once) == once


def test_content_review_revision_digest_separates_episodes():
    first = _content_record(digest="abc", reviewed_at="2026-06-01T00:00:00Z", view="elegance")
    second = _content_record(digest="def", reviewed_at="2026-06-01T00:00:00Z", view="rubric")
    assert first["episode_id"] != second["episode_id"]


def test_distinct_content_review_episodes_trigger_friction_density():
    records = [
        _content_record(digest="abc", reviewed_at="2026-06-01T00:00:00Z", view="elegance"),
        _content_record(digest="def", reviewed_at="2026-06-02T00:00:00Z", view="elegance"),
    ]
    anomaly = next(
        item for item in MOD._detect_anomalies(records) if item["kind"] == "friction_density"
    )
    assert anomaly["rubric_id"] == "demo:run-x"
    assert anomaly["friction_episodes"] == 2


def test_missing_revision_digest_is_counted_with_fallback_key():
    """skill_md_sha256 の無い記録は捨てずに fallback キーで数え、digest_missing を立てる。"""
    record = {
        "target": {"plugin": "demo", "skill": "run-x", "skill_md_sha256": ""},
        "review_kind": "elegance",
        "verdict": "PASS",
        "reviewer": "independent-test-reviewer",
        "reviewed_at": "2026-06-01T00:00:00Z",
        "iterations": 1,
        "feedback_loop": {"negative_feedback": []},
    }
    n = MOD._normalize_verdict_record(record, source_view="elegance")
    assert n is not None
    assert n["digest_missing"] is True
    assert n["skill_md_sha256"] is None
    assert n["episode_id"].startswith("content-review:")
    with_digest = dict(record, target=dict(record["target"], skill_md_sha256="a" * 64))
    assert MOD._normalize_verdict_record(with_digest)["episode_id"] != n["episode_id"]


def test_digest_missing_is_reported_in_health_and_draft(monkeypatch, tmp_path):
    """digest 欠落の件数は health と観測差分ドラフトの両方に出る (止めない)。"""
    eval_log = tmp_path / "eval-log"
    _write_review_round(
        eval_log / "demo" / "run-y" / "content-review",
        skill="run-y", reviewed_at="2026-06-11T00:00:00Z", iterations=1, negatives=0, digest="",
    )
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")

    loaded = MOD._load_evals()
    health = loaded["health"]
    assert health["complete"] is True
    assert health["digest_missing"] == 1
    assert health["sources"]["content-review"]["status"] == "ok"
    assert health["sources"]["content-review"]["digest_missing"] == 1
    assert len(loaded["evaluations"]) == 1  # 2 投影は fallback キーで 1 件
    summary = MOD._compute_summary(loaded["evaluations"])
    assert summary["digest_missing"] == 1
    draft = MOD._render_proposal([], [], summary)
    assert "skill_md_sha256 の無い content-review: 1 件" in draft


def test_observed_sort_key_places_missing_time_last():
    records = [
        {"observed_at": None, "name": "missing"},
        {"observed_at": "2026-06-01T12:00:00Z", "name": "new"},
        {"observed_at": "2026-06-01T09:00:00Z", "name": "old"},
    ]
    assert [record["name"] for record in sorted(records, key=MOD._date_sort_key)] == [
        "old",
        "new",
        "missing",
    ]


def test_same_day_input_permutation_has_same_consecutive_result():
    records = [
        {"skill": "run-x", "observed_at": "2026-06-01T09:00:00Z", "verdict": "PASS"},
        {"skill": "run-x", "observed_at": "2026-06-01T10:00:00Z", "verdict": "FAIL"},
        {"skill": "run-x", "observed_at": "2026-06-01T11:00:00Z", "verdict": "FAIL"},
        {"skill": "run-x", "observed_at": "2026-06-01T12:00:00Z", "verdict": "FAIL"},
    ]
    forward = MOD._detect_anomalies(records)
    reverse = MOD._detect_anomalies(list(reversed(records)))
    assert forward == reverse
    assert any(item["kind"] == "consecutive_fail" for item in forward)


def test_unknown_observed_time_is_excluded_from_recent_window():
    records = [
        {"skill": "run-x", "observed_at": f"2026-06-01T0{i}:00:00Z", "verdict": "PASS"}
        for i in range(1, 4)
    ]
    records += [{"skill": "run-x", "observed_at": None, "verdict": "FAIL"} for _ in range(3)]
    assert not any(item["kind"] == "consecutive_fail" for item in MOD._detect_anomalies(records))


# --- live-trial の run-id: 先頭 8 桁の日付だけが必須 ---

@pytest.mark.parametrize("run_id, expected", [
    ("20261030T1234-pr12", ("2026-10-30", "2026-10-30T12:34:00Z")),
    ("20261030T123456-r9", ("2026-10-30", "2026-10-30T12:34:56Z")),
    ("20261030T123456Z", ("2026-10-30", "2026-10-30T12:34:56Z")),
    ("20261030-manual", ("2026-10-30", None)),
    ("20261030", ("2026-10-30", None)),
    ("manual-20261030", (None, None)),
    ("20261345T0000", (None, None)),
])
def test_run_id_requires_only_leading_date(run_id, expected):
    assert MOD._run_id_observed(run_id) == expected


def _write_live_trial(eval_log, run_id, verdict="FAIL"):
    d = eval_log / "demo" / "run-x" / "live-trial" / run_id
    d.mkdir(parents=True)
    (d / "verdict.json").write_text(
        json.dumps({"target_skill": "demo:run-x", "overall": {"verdict": verdict}}), encoding="utf-8"
    )


def test_live_trial_loader_reads_real_run_id_shapes(monkeypatch, tmp_path):
    eval_log = tmp_path / "eval-log"
    _write_live_trial(eval_log, "20261030T1234-pr12")
    _write_live_trial(eval_log, "20261031T010203-r9")
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    diag = {}
    recs = MOD._load_live_trial_verdicts(diag)
    assert diag["errors"] == []
    assert sorted(r["observed_at"] for r in recs) == ["2026-10-30T12:34:00Z", "2026-10-31T01:02:03Z"]
    assert {r["skill"] for r in recs} == {"demo:run-x"}


def test_live_trial_run_id_without_date_makes_health_incomplete(monkeypatch, tmp_path):
    eval_log = tmp_path / "eval-log"
    _write_live_trial(eval_log, "manual-run")
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    health = MOD._load_evals()["health"]
    assert health["complete"] is False
    assert health["sources"]["live-trial"]["status"] == "incomplete"
    assert any("run-id has no leading YYYYMMDD date" in e for e in health["errors"])


# --- delta: 前回の観測との差分 ---

def test_delta_classifies_new_changed_resolved_and_ongoing():
    baseline_anomalies = [
        {"rubric_id": "demo:a", "kind": "friction_density", "window": 2},
        {"rubric_id": "demo:b", "kind": "score_drop", "drop": 0.2},
        {"rubric_id": "demo:d", "kind": "consecutive_fail", "count": 3},
    ]
    baseline = MOD._compute_delta(baseline_anomalies, {})["state"]
    current = [
        {"rubric_id": "demo:a", "kind": "friction_density", "window": 2},
        {"rubric_id": "demo:b", "kind": "score_drop", "drop": 0.3},
        {"rubric_id": "demo:c", "kind": "consecutive_fail", "count": 3},
    ]

    delta = MOD._compute_delta(current, baseline)

    assert delta["new"] == ["demo:c#consecutive-fail"]
    assert delta["changed"] == ["demo:b#score-drop"]
    assert delta["resolved"] == ["demo:d#consecutive-fail"]
    assert delta["ongoing"] == ["demo:a#friction-density"]
    assert delta["actionable"] is True


def test_delta_with_only_ongoing_is_not_actionable():
    anomalies = [{"rubric_id": "demo:a", "kind": "friction_density", "window": 2}]
    baseline = MOD._compute_delta(anomalies, {})["state"]
    delta = MOD._compute_delta(anomalies, baseline)
    assert delta["ongoing"] == ["demo:a#friction-density"]
    assert delta["actionable"] is False


def test_legacy_snapshot_canonicalizes_absolute_target():
    text = (
        "- **/tmp/wt/plugins/dev-graph/skills/run-dev-graph-schedule/SKILL.md**: "
        'friction_density — {"window": 2}\n'
    )
    state = MOD._snapshot_state(text)
    assert list(state) == ["dev-graph:run-dev-graph-schedule#friction-density"]
    assert "/tmp/wt" not in next(iter(state))


def test_legacy_bare_skill_id_aligns_to_plugin_target():
    """0.2.x のドラフトは plugin の無い skill 名で書いた。一意に決まれば今回の plugin:skill に寄せる。"""
    current = {"demo:run-x#consecutive-fail": "fp"}
    assert MOD._align_legacy_state({"run-x#consecutive-fail": "fp"}, current) == current
    ambiguous = {"demo:run-x#consecutive-fail": "fp", "other:run-x#consecutive-fail": "fp"}
    assert MOD._align_legacy_state({"run-x#consecutive-fail": "fp"}, ambiguous) == {
        "run-x#consecutive-fail": "fp"
    }


def test_render_proposal_wrapper_keeps_marker_and_kind():
    """_render_proposal は前回の観測なしの薄いラッパ。marker が無いと build-plugin-release が手書き扱いする。"""
    text = MOD._render_proposal(
        [{"rubric_id": "demo:run-x", "kind": "consecutive_fail", "count": 3}], [("naming", 4)], {}
    )
    assert MOD._GENERATED_MARKER in text
    assert "kind: rubric-anomaly-delta" in text
    assert "status: draft" in text
    assert "baseline: none" in text
    assert "- **demo:run-x#consecutive-fail** — " in text
    assert "- naming: 4 件" in text
    assert MOD._snapshot_state(text) == MOD._compute_delta(
        [{"rubric_id": "demo:run-x", "kind": "consecutive_fail", "count": 3}], {}
    )["state"]


# --- main: 差分があるときだけ書く・入力が欠けたら変えない・使用中なら飛ばす ---

def _today_draft(project_dir: Path) -> Path:
    return project_dir / f"{dt.date.today().isoformat()}-rubric-update.md"


def test_second_run_with_same_anomalies_is_ongoing_and_does_not_write(monkeypatch, tmp_path, capsys):
    project_dir, _ = _anomalous_main_env(monkeypatch, tmp_path)
    assert MOD.main([]) == 0
    draft = _today_draft(project_dir)
    first = draft.read_bytes()
    assert "<!-- anomaly-state: " in first.decode("utf-8")
    assert "demo:run-x#consecutive-fail" in first.decode("utf-8")
    capsys.readouterr()

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert MOD.main([]) == 0
    assert draft.read_bytes() == first
    err = capsys.readouterr().err
    assert "no anomaly delta (ongoing 1)" in err
    assert "proposal ->" not in err


def test_previous_day_snapshot_is_the_baseline(monkeypatch, tmp_path, capsys):
    """前の日の自動ドラフトに埋めた anomaly-state と同じなら、今日は書かない。"""
    project_dir, _ = _anomalous_main_env(monkeypatch, tmp_path)
    anomalies = MOD._detect_anomalies(MOD._load_evals()["evaluations"])
    project_dir.mkdir(parents=True)
    (project_dir / "2026-01-01-rubric-update.md").write_text(
        MOD._render_proposal(anomalies, [], {}), encoding="utf-8"
    )
    assert MOD.main([]) == 0
    assert not _today_draft(project_dir).exists()
    assert "no anomaly delta" in capsys.readouterr().err


def test_retired_anomaly_is_written_once(monkeypatch, tmp_path, capsys):
    """前の日に観測した異常が観測されなくなったら retired として 1 回書き、その次は書かない。"""
    project_dir, _ = _anomalous_main_env(monkeypatch, tmp_path)
    anomalies = MOD._detect_anomalies(MOD._load_evals()["evaluations"])
    project_dir.mkdir(parents=True)
    (project_dir / "2026-01-01-rubric-update.md").write_text(
        MOD._render_proposal(anomalies, [], {}), encoding="utf-8"
    )
    score = tmp_path / "eval-log" / "demo" / "2026-06-03-score.jsonl"
    score.write_text(
        json.dumps({"skill_name": "run-x", "passed": True, "timestamp": "2026-06-04T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert MOD.main([]) == 0
    text = _today_draft(project_dir).read_text(encoding="utf-8")
    assert "- retired / not reproduced: 1" in text
    assert "- demo:run-x#consecutive-fail" in text
    assert "<!-- anomaly-state: {} -->" in text
    capsys.readouterr()

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    before = _today_draft(project_dir).read_bytes()
    assert MOD.main([]) == 0
    assert _today_draft(project_dir).read_bytes() == before
    assert "proposal ->" not in capsys.readouterr().err


def _consecutive_fail_score(eval_log: Path, skill: str) -> None:
    lines = [
        json.dumps({"skill_name": skill, "passed": False, "timestamp": f"2026-06-0{i}T00:00:00Z"})
        for i in (1, 2, 3)
    ]
    (eval_log / "demo" / f"2026-06-03-{skill}-score.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def test_same_day_rerun_keeps_first_new_with_details(monkeypatch, tmp_path, capsys):
    """同じ日の 2 回目に異常が増えても、1 回目の New は根拠つきの New のまま残る。

    今日のドラフトを前回の観測にすると、上書きで 1 回目の New が id だけの Ongoing に下がる。
    """
    project_dir, _ = _anomalous_main_env(monkeypatch, tmp_path)
    assert MOD.main([]) == 0
    _consecutive_fail_score(tmp_path / "eval-log", "run-y")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert MOD.main([]) == 0
    text = _today_draft(project_dir).read_text(encoding="utf-8")
    assert "- new: 2" in text
    assert "- ongoing: 0" in text
    assert "- **demo:run-x#consecutive-fail** — " in text
    assert "- **demo:run-y#consecutive-fail** — " in text


def test_same_day_rerun_rewrites_a_new_that_disappeared(monkeypatch, tmp_path, capsys):
    """前の日に無く今日だけ出て消えた異常は、今日のドラフトに古い New として残さない。"""
    project_dir, _ = _anomalous_main_env(monkeypatch, tmp_path)
    assert MOD.main([]) == 0
    score = tmp_path / "eval-log" / "demo" / "2026-06-03-score.jsonl"
    score.write_text(
        json.dumps({"skill_name": "run-x", "passed": True, "timestamp": "2026-06-04T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert MOD.main([]) == 0
    text = _today_draft(project_dir).read_text(encoding="utf-8")
    assert "<!-- anomaly-state: {} -->" in text
    assert "- new: 0" in text
    assert "demo:run-x" not in text
    capsys.readouterr()

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    before = _today_draft(project_dir).read_bytes()
    assert MOD.main([]) == 0
    assert _today_draft(project_dir).read_bytes() == before
    assert "proposal ->" not in capsys.readouterr().err


def test_project_without_history_does_not_read_the_shared_fallback(monkeypatch, tmp_path):
    """project の state に履歴が無くても、後ろの退避先 (全 project が共有) の観測は前回にしない。

    読むと、別の project の異常が retired として出る。
    """
    project_dir, user_dir = _anomalous_main_env(monkeypatch, tmp_path)
    user_dir.mkdir(parents=True)
    (user_dir / "2026-01-01-rubric-update.md").write_text(
        MOD._render_proposal([{"rubric_id": "other:run-z", "kind": "consecutive_fail", "count": 3}], [], {}),
        encoding="utf-8",
    )
    assert MOD.main([]) == 0
    text = _today_draft(project_dir).read_text(encoding="utf-8")
    assert "baseline: none" in text
    assert "- retired / not reproduced: 0" in text
    assert "other:run-z" not in text


def test_fallback_sink_borrows_the_history_of_a_preferred_sink(monkeypatch, tmp_path, capsys):
    """第一の書込先に書けないときは退避先に書き、前回の観測は第一の書込先の履歴を借りる。"""
    eval_log = tmp_path / "eval-log"
    _anomalous_score_jsonl(eval_log)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    primary = tmp_path / "ro" / "proposals"
    fallback = tmp_path / "state" / "proposals"
    primary.mkdir(parents=True)
    anomalies = MOD._detect_anomalies(MOD._load_evals()["evaluations"])
    (primary / "2026-01-01-rubric-update.md").write_text(
        MOD._render_proposal(anomalies, [], {}), encoding="utf-8"
    )
    monkeypatch.setattr(MOD, "_candidate_proposals_dirs", lambda: [primary, fallback])
    monkeypatch.setattr(MOD, "_dir_is_writable", lambda d: d == fallback)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert MOD.main([]) == 0
    assert not list(fallback.glob("*-rubric-update.md"))
    assert "no anomaly delta (ongoing 1)" in capsys.readouterr().err


def test_incomplete_source_leaves_snapshot_unchanged(monkeypatch, tmp_path, capsys):
    """入力源のどれかが読めなければ、前回の観測をバイト単位で変えずに exit 0。

    読めなかった記録を無視して集計すると、消えていない異常を retired と書いてしまう。
    """
    project_dir, _ = _anomalous_main_env(monkeypatch, tmp_path)
    assert MOD.main([]) == 0
    draft = _today_draft(project_dir)
    before = draft.read_bytes()
    score = tmp_path / "eval-log" / "demo" / "2026-06-03-score.jsonl"
    score.write_text("{not json\n", encoding="utf-8")
    capsys.readouterr()

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert MOD.main([]) == 0
    assert draft.read_bytes() == before
    err = capsys.readouterr().err
    assert "[aggregate-evals] incomplete source; snapshot unchanged" in err
    assert "score.jsonl" in err


def test_broken_evals_json_is_an_incomplete_source(monkeypatch, tmp_path, capsys):
    project_dir, _ = _anomalous_main_env(monkeypatch, tmp_path)
    broken = tmp_path / "EVALS.json"
    broken.write_text("{", encoding="utf-8")
    assert MOD.main([]) == 0
    assert not project_dir.exists()
    assert "EVALS.json" in capsys.readouterr().err


def test_hand_written_same_name_file_is_not_overwritten(monkeypatch, tmp_path, capsys):
    """marker の無い同名のファイルは手書き。上書きもしないし、前回の観測にもしない。"""
    project_dir, _ = _anomalous_main_env(monkeypatch, tmp_path)
    project_dir.mkdir(parents=True)
    draft = _today_draft(project_dir)
    draft.write_text("手書きのメモ\n", encoding="utf-8")
    assert MOD.main([]) == 0
    assert draft.read_text(encoding="utf-8") == "手書きのメモ\n"
    assert "hand-written" in capsys.readouterr().err


def test_sink_lock_is_not_waited_for(monkeypatch, tmp_path):
    """lock は待たない。待ち時間内に取れなければ _SinkBusy。"""
    target = tmp_path / "proposals"
    with MOD._sink_lock(target, wait=0):
        with pytest.raises(MOD._SinkBusy):
            with MOD._sink_lock(target, wait=0.05):
                pass
    with MOD._sink_lock(target, wait=0):  # 手放した後は取れる
        pass


def test_main_skips_when_sink_is_busy(monkeypatch, tmp_path, capsys):
    """別の session が同じ書込先を更新中なら、待たずに飛ばして exit 0 (SessionEnd の timeout は 3 秒)。"""
    project_dir, user_dir = _anomalous_main_env(monkeypatch, tmp_path)
    monkeypatch.setattr(MOD, "_LOCK_WAIT_SECONDS", 0.05)
    with MOD._sink_lock(project_dir, wait=0):
        assert MOD.main([]) == 0
    assert not project_dir.exists()
    assert not user_dir.exists(), "使用中のときに退避先へ書くと前回の観測が 2 か所に分かれる"
    assert "sink busy, skipped" in capsys.readouterr().err

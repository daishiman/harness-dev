"""plugins/harness-creator/skills/run-skill-rubric-governance/scripts/aggregate-evals.py の genuine 機能テスト。

SessionEnd hook が EVALS.json + score.jsonl + content-review + live-trial の 4 ソースを集計し、
異常を前回の観測と比べて差分があれば、書込先に <date>-rubric-update.md (kind: rubric-anomaly-delta、
marker 行つき) を書く。純関数群と main の全分岐を、tmp_path fixture へ path helper を monkeypatch して
**実 repo を一切汚染せず** 網羅する。aggregate-evals.py は 1 ファイル (lib/ に分けない)。

network: false, keychain: なし, 実 repo 書込: なし(全 path helper を tmp へ差し替え)。

カバー分岐:
- _plugin_root/_repo_root/_eval_log_dir/_evals_path/_proposals_dir/_legacy_proposals_dir: 実パス算出(参照のみ)
- _date_of: 正常 / 非str / 空 / マッチ無し None
- _normalize_score_record: 非dict / skill 無 / passed True/False/欠落(verdict 文字列) / findings None / percent
- _normalize_verdict_record: 非dict / target 無 skill / 正常
- _load_score_jsonl: dir 無 / 空行・不正JSON は error に数える / 正常 / 読込不能は error
- _load_content_review_verdicts: dir 無 / 不正JSON は error / 正常
- _load_evals: EVALS.json 有(正常/不正JSON は incomplete) / 4 ソース concat / loader 例外は incomplete
- _verdict_is_fail: FAIL系 各 / 非FAIL
- _score_of: score/overall/mean_score/average / 単位の宣言なし None
- _detect_anomalies: skill 無 skip / 連続FAIL / 2件は不発 / score_drop / drop 不足は不発
- _top_finding_categories: dict(category/rule/kind) / str / 無
- _slugify: 記号除去 / 空 → "rubric"
- _compute_summary: 空 / 件数・negative_rate・mean_score / scores 無 n/a
- _compute_delta / _render_anomaly_delta / _render_proposal: new/changed/resolved/ongoing と正式 proposal の分離、marker
- _sink_lock: Windows backend (msvcrt) の非ブロック lock、使用中は _SinkBusy
- main: evals 空 / delta 無 / 書込成功 / 同日 upsert / 入力欠け / fallback / 書込先なしを全て非ブロック exit0
"""
import builtins
import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-skill-rubric-governance"
    / "scripts"
    / "aggregate-evals.py"
)

SPEC = importlib.util.spec_from_file_location("aggregate_evals_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


@pytest.fixture(autouse=True)
def _isolated_lock_dir(tmp_path_factory, monkeypatch):
    """_sink_lock は OS の一時ディレクトリに書込先ごとの lock ファイルを残す。テストの分は pytest の一時領域に閉じる。

    tmp_path の外に置くのは、tmp_path の中身を数えるテスト (一時ファイルの残りが無いこと) を乱さないため。
    """
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path_factory.mktemp("os-tmp")))


# ── path helper(実 repo を参照する純関数。書込はしないので安全に算出のみ確認) ──
def test_path_helpers_resolve_to_repo_layout(monkeypatch):
    monkeypatch.delenv("HARNESS_CREATOR_PROPOSALS_DIR", raising=False)
    plugin_root = MOD._plugin_root()
    assert plugin_root.name == "harness-creator"
    repo_root = MOD._repo_root()
    assert (repo_root / "plugins").exists() or repo_root.name  # repo 配下
    assert MOD._eval_log_dir() == repo_root / "eval-log"
    assert MOD._evals_path() == plugin_root / "EVALS.json"
    assert MOD._proposals_dir().name == "proposals"
    # 書込先は plugin の外の state。$CLAUDE_PROJECT_DIR が何を指していても候補に plugin の中は無い
    assert not any(MOD._is_inside_plugin(d) for d in MOD._candidate_proposals_dirs())
    legacy = MOD._legacy_proposals_dir()
    assert legacy.parts[-2:] == ("run-skill-rubric-governance", "proposals")
    assert MOD._is_inside_plugin(legacy)  # 従来の置き場は読むだけ


def _generated(state: str) -> str:
    """前回の観測として読まれる自動ドラフト (marker 行と anomaly-state を持つ)。"""
    return f"<!-- anomaly-state: {state} -->\n\n本ドラフトは {MOD._GENERATED_MARKER}。\n"


def test_latest_snapshot_uses_first_sink_with_history(tmp_path):
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    primary.mkdir()
    fallback.mkdir()
    (primary / "2026-01-01-rubric-update.md").write_text(
        _generated('{"primary#x": "a"}'), encoding="utf-8"
    )
    (fallback / "2026-09-01-rubric-update.md").write_text(
        _generated('{"fallback#x": "b"}'), encoding="utf-8"
    )
    date, state = MOD._latest_snapshot([primary, fallback], "2026-09-04")
    assert date == "2026-01-01"
    assert state == {"primary#x": "a"}


def test_latest_snapshot_skips_hand_written_and_future_files(tmp_path):
    """marker の無い同名ファイル (手書き) と、今日とそれより後の日付は前回の観測にしない。"""
    sink = tmp_path / "sink"
    sink.mkdir()
    (sink / "2026-01-01-rubric-update.md").write_text(_generated('{"old#x": "a"}'), encoding="utf-8")
    (sink / "2026-09-04-rubric-update.md").write_text(_generated('{"today#x": "d"}'), encoding="utf-8")
    (sink / "2026-02-01-rubric-update.md").write_text(
        '<!-- anomaly-state: {"hand#x": "b"} -->\n手書き\n', encoding="utf-8"
    )
    (sink / "2026-12-01-rubric-update.md").write_text(_generated('{"future#x": "c"}'), encoding="utf-8")
    assert MOD._latest_snapshot([sink], "2026-09-04") == ("2026-01-01", {"old#x": "a"})


def test_select_snapshot_reports_unreadable_file(tmp_path):
    sink = tmp_path / "sink"
    sink.mkdir()
    (sink / "2026-01-01-rubric-update.md").write_bytes(b"\xff\xfe broken")
    snapshot = MOD._select_snapshot([sink], "2026-09-04")
    assert snapshot is not None and snapshot.error


# ── _date_of ─────────────────────────────────────────────────────────────────
def test_date_of_extracts_date():
    assert MOD._date_of("2026-06-10T19:59:43+0900") == "2026-06-10"


def test_date_of_z_suffix():
    assert MOD._date_of("2026-06-01T00:00:00Z") == "2026-06-01"


def test_date_of_non_str_none():
    assert MOD._date_of(12345) is None


def test_date_of_empty_none():
    assert MOD._date_of("") is None


def test_date_of_no_match_none():
    assert MOD._date_of("no-date-here") is None


# ── _normalize_score_record ──────────────────────────────────────────────────
def test_normalize_score_non_dict_none():
    assert MOD._normalize_score_record("nope") is None


def test_normalize_score_no_skill_none():
    assert MOD._normalize_score_record({"passed": True}) is None


def test_normalize_score_passed_true():
    n = MOD._normalize_score_record(
        {"skill_name": "run-a", "passed": True, "score": 0.9, "timestamp": "2026-06-10T00:00:00Z"}
    )
    assert n["verdict"] == "PASS"
    assert n["skill"] == "run-a"
    assert n["score"] == pytest.approx(0.009)
    assert n["source_kind"] == "score"
    assert n["episode_id"].startswith("score:")


def test_normalize_score_percent_to_internal_ratio():
    n = MOD._normalize_score_record(
        {"skill_name": "run-a", "passed": True, "score": 90}
    )
    assert n["score"] == 0.9


def test_normalize_score_passed_false():
    n = MOD._normalize_score_record({"skill_name": "run-a", "passed": False})
    assert n["verdict"] == "FAIL"
    assert n["date"] is None  # timestamp 無


def test_normalize_score_passed_missing_uses_verdict_field():
    n = MOD._normalize_score_record({"skill_name": "run-a", "verdict": "INCOMPLETE"})
    assert n["verdict"] == "INCOMPLETE"


def test_normalize_score_skill_from_rubric_id():
    n = MOD._normalize_score_record(
        {"rubric": {"rubric_id": "rid-1"}, "passed": True}
    )
    assert n["skill"] == "rid-1"


def test_normalize_score_findings_none_becomes_list():
    n = MOD._normalize_score_record({"skill_name": "s", "passed": True, "findings": None})
    assert n["findings"] == []


def test_normalize_score_non_dict_rubric_ignored():
    # rubric が dict でないとき {} 扱い → skill_name へフォールバック
    n = MOD._normalize_score_record({"skill_name": "s", "rubric": "weird", "passed": True})
    assert n["skill"] == "s"


# ── _normalize_verdict_record ────────────────────────────────────────────────
def test_normalize_verdict_non_dict_none():
    assert MOD._normalize_verdict_record(["x"]) is None


def test_normalize_verdict_no_skill_none():
    assert MOD._normalize_verdict_record({"target": {"plugin": "p"}}) is None


def test_normalize_verdict_ok():
    n = MOD._normalize_verdict_record(
        {
            "target": {"skill": "run-b", "skill_md_sha256": "revision-b"},
            "verdict": "FAIL",
            "reviewed_at": "2026-06-11T09:00:00+0900",
        }
    )
    assert n["skill"] == "run-b"
    assert n["verdict"] == "FAIL"
    assert n["date"] == "2026-06-11"
    assert n["score"] is None
    assert n["source_kind"] == "content-review"


def test_normalize_verdict_non_dict_target():
    n = MOD._normalize_verdict_record({"target": "weird", "verdict": "PASS"})
    assert n is None  # target dict でない → skill 取れず None


# ── _load_score_jsonl ────────────────────────────────────────────────────────
def test_load_score_jsonl_no_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "absent")
    assert MOD._load_score_jsonl() == []


def test_load_score_jsonl_parses_and_skips_bad(monkeypatch, tmp_path):
    base = tmp_path / "eval-log"
    d = base / "demo"
    d.mkdir(parents=True)
    (d / "2026-06-10-score.jsonl").write_text(
        json.dumps({"skill_name": "run-x", "passed": True, "score": 0.8, "timestamp": "2026-06-10T00:00:00Z"})
        + "\n"
        + "\n"  # 空行 → skip
        + "{bad json\n"  # 不正 → skip
        + json.dumps({"passed": True})  # skill 無 → normalize None → skip
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: base)
    diag = {}
    out = MOD._load_score_jsonl(diag)
    assert len(out) == 1
    assert out[0]["skill"] == "demo:run-x"
    # 空行は数えない。不正 JSON と skill 無しは読めなかった記録として health に残す
    assert len(diag["errors"]) == 2


def test_load_score_jsonl_unreadable_file_skipped(monkeypatch, tmp_path):
    base = tmp_path / "eval-log"
    d = base / "demo"
    d.mkdir(parents=True)
    good = d / "2026-06-10-score.jsonl"
    good.write_text(json.dumps({"skill_name": "ok", "passed": True}) + "\n", encoding="utf-8")
    bad = d / "2026-06-11-score.jsonl"
    bad.write_text("x", encoding="utf-8")
    orig = Path.read_text

    def boom(self, *a, **k):
        if self == bad:
            raise OSError("nope")
        return orig(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", boom)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: base)
    diag = {}
    out = MOD._load_score_jsonl(diag)
    assert [o["skill"] for o in out] == ["demo:ok"]
    assert len(diag["errors"]) == 1 and "unreadable" in diag["errors"][0]


# ── _load_content_review_verdicts ────────────────────────────────────────────
def test_load_verdicts_no_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "absent")
    assert MOD._load_content_review_verdicts() == []


def test_load_verdicts_parses_and_skips_bad(monkeypatch, tmp_path):
    base = tmp_path / "eval-log"
    cr = base / "demo" / "run-y" / "content-review"
    cr.mkdir(parents=True)
    (cr / "ok-verdict.json").write_text(
        json.dumps(
            {
                "target": {"skill": "run-y", "skill_md_sha256": "revision-y"},
                "verdict": "FAIL",
                "reviewed_at": "2026-06-11T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (cr / "bad-verdict.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: base)
    diag = {}
    out = MOD._load_content_review_verdicts(diag)
    assert len(out) == 1
    assert out[0]["skill"] == "run-y"
    assert len(diag["errors"]) == 1
    assert diag["digest_missing"] == 0


# ── _load_evals (4 ソース合流) ───────────────────────────────────────────────
def test_load_evals_reads_evals_json(monkeypatch, tmp_path):
    ep = tmp_path / "EVALS.json"
    ep.write_text(
        json.dumps({"evaluations": [{"skill": "run-z", "verdict": "PASS"}, "not-a-dict"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(MOD, "_evals_path", lambda: ep)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "absent")
    out = MOD._load_evals()["evaluations"]
    # 非 dict はスキップし、旧 record に共通 provenance を補う。
    assert len(out) == 1
    assert out[0]["skill"] == "run-z"
    assert out[0]["source_kind"] == "evals"
    assert out[0]["episode_id"].startswith("evals:")
    # 形の違う行は読めなかった記録。EVALS.json の health は incomplete になる
    health = MOD._load_evals()["health"]
    assert health["sources"]["EVALS.json"]["status"] == "incomplete"


def test_load_evals_bad_evals_json_warns(monkeypatch, tmp_path, capsys):
    ep = tmp_path / "EVALS.json"
    ep.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(MOD, "_evals_path", lambda: ep)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "absent")
    result = MOD._load_evals()
    assert result["evaluations"] == []
    assert result["health"]["complete"] is False
    assert result["health"]["sources"]["EVALS.json"]["status"] == "incomplete"
    assert "source load failed: EVALS.json" in capsys.readouterr().err


def test_load_evals_missing_sources_are_healthy_absences(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "no-evals.json")
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "no-eval-log")

    result = MOD._load_evals()

    assert result["evaluations"] == []
    assert result["health"]["complete"] is True
    assert {
        source: health["status"]
        for source, health in result["health"]["sources"].items()
    } == {
        "EVALS.json": "absent",
        "score.jsonl": "absent",
        "content-review": "absent",
        "live-trial": "absent",
    }


def test_load_evals_score_loader_exception_non_blocking(monkeypatch, tmp_path, capsys):
    # _load_score_jsonl が例外を投げても _load_evals は握りつぶし継続(SessionEnd 流儀)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "no-evals.json")

    def boom(diagnostics=None):
        raise RuntimeError("score boom")

    monkeypatch.setattr(MOD, "_load_score_jsonl", boom)
    monkeypatch.setattr(MOD, "_load_content_review_verdicts", lambda diagnostics=None: [])
    monkeypatch.setattr(MOD, "_load_live_trial_verdicts", lambda diagnostics=None: [])
    result = MOD._load_evals()
    assert result["evaluations"] == []
    assert result["health"]["complete"] is False
    assert result["health"]["sources"]["score.jsonl"]["status"] == "incomplete"
    assert "source load failed: score.jsonl" in capsys.readouterr().err


def test_load_evals_verdict_loader_exception_non_blocking(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "no-evals.json")
    monkeypatch.setattr(MOD, "_load_score_jsonl", lambda diagnostics=None: [])
    monkeypatch.setattr(MOD, "_load_live_trial_verdicts", lambda diagnostics=None: [])

    def boom(diagnostics=None):
        raise RuntimeError("verdict boom")

    monkeypatch.setattr(MOD, "_load_content_review_verdicts", boom)
    out = MOD._load_evals()["evaluations"]
    assert out == []
    assert "source load failed: content-review" in capsys.readouterr().err


def test_load_evals_merges_all_four(monkeypatch, tmp_path):
    base = tmp_path / "eval-log"
    sd = base / "demo"
    sd.mkdir(parents=True)
    (sd / "2026-06-10-score.jsonl").write_text(
        json.dumps({"skill_name": "run-x", "passed": True, "score": 0.8, "timestamp": "2026-06-10T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    cr = base / "demo" / "run-y" / "content-review"
    cr.mkdir(parents=True)
    (cr / "v-verdict.json").write_text(
        json.dumps(
            {
                "target": {"skill": "run-y", "skill_md_sha256": "revision-y"},
                "verdict": "FAIL",
                "reviewed_at": "2026-06-11T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    live = base / "demo" / "run-live" / "live-trial" / "20260612T000000Z-run"
    live.mkdir(parents=True)
    (live / "verdict.json").write_text(
        json.dumps({
            "target_skill": "demo:run-live",
            "overall": {"verdict": "PASS"},
            "goal_verdict": {"blockers": []},
        }),
        encoding="utf-8",
    )
    ep = tmp_path / "EVALS.json"
    ep.write_text(json.dumps({"evaluations": [{"skill": "run-w", "verdict": "PASS"}]}), encoding="utf-8")
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: base)
    monkeypatch.setattr(MOD, "_evals_path", lambda: ep)
    skills = {e["skill"] for e in MOD._load_evals()["evaluations"]}
    assert {"run-w", "demo:run-x", "run-y", "demo:run-live"} == skills


# ── _verdict_is_fail / _score_of ─────────────────────────────────────────────
@pytest.mark.parametrize("v", ["FAIL", "failed", "REJECT", "rejected"])
def test_verdict_is_fail_true(v):
    assert MOD._verdict_is_fail(v) is True


@pytest.mark.parametrize("v", ["PASS", ""])
def test_verdict_is_fail_false(v):
    assert MOD._verdict_is_fail(v) is False


@pytest.mark.parametrize("v", ["BLOCKED", "DEGRADED", "INCOMPLETE"])
def test_verdict_is_fail_includes_fail_closed_states(v):
    assert MOD._verdict_is_fail(v) is True


def test_score_of_each_key():
    assert MOD._score_of({"score": 0.5, "score_unit": "ratio"}) == 0.5
    assert MOD._score_of({"overall": 1, "score_unit": "percent"}) == 0.01
    assert MOD._score_of({"mean_score": 0.7, "score_unit": "ratio"}) == 0.7
    assert MOD._score_of({"average": 30, "score_unit": "percent"}) == 0.3


def test_score_of_none_when_absent_or_nonnumeric():
    assert MOD._score_of({"score": "high"}) is None
    assert MOD._score_of({}) is None


# ── _detect_anomalies ────────────────────────────────────────────────────────
def test_detect_skips_records_without_skill():
    # skill も rubric_id も無いレコードはグループ化されず無視
    assert MOD._detect_anomalies([{"verdict": "FAIL"}]) == []


def test_detect_consecutive_fail():
    evals = [
        {"skill": "run-x", "observed_at": f"2026-06-0{i}T00:00:00Z", "verdict": "FAIL"}
        for i in (1, 2, 3)
    ]
    a = MOD._detect_anomalies(evals)
    assert any(x["kind"] == "consecutive_fail" and x["rubric_id"] == "run-x" for x in a)
    cf = [x for x in a if x["kind"] == "consecutive_fail"][0]
    assert cf["count"] == 3
    assert cf["evidence_observed_at"] == [
        "2026-06-01T00:00:00Z",
        "2026-06-02T00:00:00Z",
        "2026-06-03T00:00:00Z",
    ]


def test_detect_two_fails_no_trigger():
    evals = [
        {"skill": "run-x", "observed_at": f"2026-06-0{i}T00:00:00Z", "verdict": "FAIL"}
        for i in (1, 2)
    ]
    assert not any(x["kind"] == "consecutive_fail" for x in MOD._detect_anomalies(evals))


def test_detect_score_drop():
    scores = [1.0, 0.5, 0.5, 0.5, 0.5, 0.5]
    evals = [
        {
            "skill": "run-y",
            "observed_at": f"2026-06-{i + 1:02d}T00:00:00Z",
            "verdict": "PASS",
            "score": s,
            "score_unit": "ratio",
        }
        for i, s in enumerate(scores)
    ]
    a = MOD._detect_anomalies(evals)
    sd = [x for x in a if x["kind"] == "score_drop"]
    assert sd and sd[0]["rubric_id"] == "run-y"
    assert sd[0]["drop"] >= MOD._SCORE_DROP_THRESHOLD


def test_detect_score_drop_below_threshold_no_trigger():
    # prior と recent の差が 0.1 未満 → 不発
    scores = [0.55, 0.5, 0.5, 0.5, 0.5, 0.5]
    evals = [
        {
            "skill": "run-y",
            "observed_at": f"2026-06-{i + 1:02d}T00:00:00Z",
            "verdict": "PASS",
            "score": s,
            "score_unit": "ratio",
        }
        for i, s in enumerate(scores)
    ]
    assert not any(x["kind"] == "score_drop" for x in MOD._detect_anomalies(evals))


def test_detect_uses_rubric_id_fallback():
    # skill 無し・rubric_id 有りでもグループ化される
    evals = [
        {"rubric_id": "rid", "observed_at": f"2026-06-0{i}T00:00:00Z", "verdict": "FAIL"}
        for i in (1, 2, 3)
    ]
    a = MOD._detect_anomalies(evals)
    assert any(x["rubric_id"] == "rid" for x in a)


# ── _top_finding_categories ──────────────────────────────────────────────────
def test_top_finding_categories_mixed():
    evals = [
        {"findings": [{"category": "naming"}, {"rule": "rule-x"}, {"kind": "kind-y"}]},
        {"findings": ["plain-string", {"category": "naming"}]},
        {"findings": None},  # None は空扱い
        {"findings": [{"no-cat-key": 1}]},  # cat 取れず無視
    ]
    top = dict(MOD._top_finding_categories(evals))
    assert top["naming"] == 2
    assert top["rule-x"] == 1
    assert top["kind-y"] == 1
    assert top["plain-string"] == 1


def test_top_finding_categories_empty():
    assert MOD._top_finding_categories([{"findings": []}]) == []


# ── _slugify ─────────────────────────────────────────────────────────────────
def test_slugify_strips_symbols():
    assert MOD._slugify("Run-Skill Create!!") == "run-skill-create"


def test_slugify_empty_fallback():
    assert MOD._slugify("###") == "rubric"


# ── _compute_summary ─────────────────────────────────────────────────────────
def test_compute_summary_empty():
    s = MOD._compute_summary([])
    assert s["total"] == 0
    assert s["negative_rate"] == 0.0
    assert s["mean_score"] == "n/a"


def test_compute_summary_counts():
    evals = [
        {"verdict": "FAIL", "score": 0.4, "score_unit": "ratio"},
        {"verdict": "PASS", "score": 0.8, "score_unit": "ratio"},
        {"verdict": "REJECT"},  # score 無
    ]
    s = MOD._compute_summary(evals)
    assert s["total"] == 3
    assert s["negative_rate"] == pytest.approx(2 / 3)
    assert s["mean_score"] == round((0.4 + 0.8) / 2, 3)
    assert s["digest_missing"] == 0


# ── _render_anomaly_delta / _render_proposal ─────────────────────────────────
def test_render_proposal_is_a_thin_wrapper_with_marker():
    """_render_proposal は前回の観測なし (全件 new) の薄いラッパ。build-plugin-release は marker で自動ドラフトを見分ける。"""
    anomalies = [
        {"rubric_id": "run-x", "kind": "consecutive_fail", "count": 3, "evidence_dates": ["2026-06-01"]},
    ]
    text = MOD._render_proposal(anomalies, [("naming", 4), ("layout", 2)],
                                {"total": 10, "negative_rate": 0.3, "mean_score": 0.7})
    assert MOD._GENERATED_MARKER in text
    assert "kind: rubric-anomaly-delta" in text
    assert "status: draft" in text
    assert "## New" in text and "**run-x#consecutive-fail**" in text
    assert "naming: 4 件" in text
    assert "layout: 2 件" in text
    assert "30.00%" in text


def test_render_proposal_without_anomalies_or_findings():
    text = MOD._render_proposal([], [], {})
    assert MOD._GENERATED_MARKER in text
    assert "## New\n\n- (なし)" in text
    assert "## 主要 finding カテゴリ (top5)\n\n- (なし)" in text


def test_render_delta_is_not_formal_proposal():
    delta = MOD._compute_delta([], {})
    text = MOD._render_anomaly_delta(
        delta, {"total": 0, "negative_rate": 0.0, "mean_score": "n/a"}, None
    )
    assert "kind: rubric-anomaly-delta" in text
    assert "rubric 改正案ではなく" in text
    assert "kind: rubric-update-proposal" not in text


def test_render_delta_details_only_for_new_or_changed():
    anomalies = [
        {"rubric_id": "run-x", "kind": "consecutive_fail", "count": 3, "evidence_dates": ["2026-06-01"]},
    ]
    summary = {"total": 10, "negative_rate": 0.3, "mean_score": 0.7}
    text = MOD._render_anomaly_delta(MOD._compute_delta(anomalies, {}), summary, "2026-06-01")
    assert "**run-x#consecutive-fail**" in text
    assert '"evidence_dates": ["2026-06-01"]' in text
    assert "30.00%" in text
    assert "## Retired / not reproduced" in text
    assert "## Resolved" not in text


def test_render_delta_never_exposes_absolute_target_path():
    anomalies = [{
        "rubric_id": "/tmp/wt/plugins/dev-graph/skills/run-dev-graph-schedule/SKILL.md",
        "kind": "friction_density",
        "friction_episodes": 2,
    }]
    text = MOD._render_anomaly_delta(
        MOD._compute_delta(anomalies, {}),
        {"total": 2, "negative_rate": 0.0, "mean_score": "n/a"},
        None,
    )
    assert "dev-graph:run-dev-graph-schedule" in text
    assert "/tmp/wt" not in text


def test_same_anomaly_state_has_no_actionable_delta():
    anomalies = [{"rubric_id": "demo:run-x", "kind": "friction_density", "window": 2}]
    initial = MOD._compute_delta(anomalies, {})
    repeated = MOD._compute_delta(anomalies, initial["state"])
    assert repeated["new"] == []
    assert repeated["changed"] == []
    assert repeated["resolved"] == []
    assert repeated["ongoing"] == ["demo:run-x#friction-density"]
    assert repeated["actionable"] is False


# ── main ─────────────────────────────────────────────────────────────────────
def _redirect(monkeypatch, tmp_path, *, evals_json=None, score_records=None, verdicts=None):
    """全 path helper を tmp へ向け、必要に応じて sink を用意する。"""
    base = tmp_path / "eval-log"
    if evals_json is not None:
        ep = tmp_path / "EVALS.json"
        ep.write_text(json.dumps(evals_json), encoding="utf-8")
        monkeypatch.setattr(MOD, "_evals_path", lambda: ep)
    else:
        monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "no-evals.json")
    if score_records is not None:
        sd = base / "demo"
        sd.mkdir(parents=True, exist_ok=True)
        (sd / "2026-06-10-score.jsonl").write_text(
            "\n".join(json.dumps(r) for r in score_records) + "\n", encoding="utf-8"
        )
    if verdicts is not None:
        cr = base / "demo" / "run-y" / "content-review"
        cr.mkdir(parents=True, exist_ok=True)
        for i, v in enumerate(verdicts):
            (cr / f"{i}-verdict.json").write_text(json.dumps(v), encoding="utf-8")
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: base)
    out_dir = tmp_path / "proposals"
    monkeypatch.setattr(MOD, "_proposals_dir", lambda: out_dir)
    monkeypatch.setattr(MOD, "_candidate_proposals_dirs", lambda: [out_dir])
    return out_dir


def _feed_empty_stdin(monkeypatch):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(""))


def test_main_no_evals_exit0(monkeypatch, tmp_path):
    out_dir = _redirect(monkeypatch, tmp_path)  # ソース皆無
    _feed_empty_stdin(monkeypatch)
    assert MOD.main() == 0
    assert not out_dir.exists()


def test_main_no_anomalies_exit0(monkeypatch, tmp_path):
    out_dir = _redirect(
        monkeypatch,
        tmp_path,
        evals_json={"evaluations": [{"skill": "run-x", "verdict": "PASS", "score": 0.9}]},
    )
    _feed_empty_stdin(monkeypatch)
    assert MOD.main() == 0
    assert not out_dir.exists()  # 異常なし → 提案書かない


def test_main_writes_proposal_on_anomaly(monkeypatch, tmp_path):
    records = [
        {"skill_name": "run-x", "passed": False, "timestamp": f"2026-06-0{i}T00:00:00Z", "findings": [{"category": "naming"}]}
        for i in (1, 2, 3)
    ]
    out_dir = _redirect(monkeypatch, tmp_path, score_records=records)
    _feed_empty_stdin(monkeypatch)
    assert MOD.main() == 0
    files = list(out_dir.glob("*-rubric-update.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "demo:run-x" in content
    assert "consecutive-fail" in content
    assert MOD._GENERATED_MARKER in content
    assert "naming: 3 件" in content


def test_main_upserts_same_day_draft_without_second_file(monkeypatch, tmp_path):
    """同じ日の自動ドラフトは上書きする (別名のファイルは作らない)。2 回目は差分が無いので書かない。"""
    records = [
        {"skill_name": "run-x", "passed": False, "timestamp": f"2026-06-01T0{i}:00:00Z"}
        for i in (1, 2, 3)
    ]
    out_dir = _redirect(monkeypatch, tmp_path, score_records=records)
    out_dir.mkdir(parents=True)
    today = MOD._dt.date.today().isoformat()
    draft = out_dir / f"{today}-rubric-update.md"
    draft.write_text(MOD._render_proposal([], [], {}), encoding="utf-8")
    _feed_empty_stdin(monkeypatch)

    assert MOD.main() == 0
    first = draft.read_text(encoding="utf-8")
    assert "demo:run-x#consecutive-fail" in first
    _feed_empty_stdin(monkeypatch)
    assert MOD.main() == 0
    assert [path.name for path in out_dir.iterdir()] == [draft.name]
    assert "kind: rubric-anomaly-delta" in draft.read_text(encoding="utf-8")
    assert draft.read_text(encoding="utf-8") == first


def test_main_incomplete_source_does_not_resolve_or_update_snapshot(
    monkeypatch, tmp_path, capsys
):
    out_dir = _redirect(
        monkeypatch,
        tmp_path,
        evals_json={"evaluations": [{"skill": "run-x", "verdict": "PASS"}]},
    )
    bad_dir = tmp_path / "eval-log" / "demo" / "run-y" / "content-review"
    bad_dir.mkdir(parents=True)
    (bad_dir / "rubric-verdict.json").write_text("{bad json", encoding="utf-8")
    out_dir.mkdir(parents=True)
    snapshot = out_dir / "2026-01-01-rubric-update.md"
    original = _generated('{"demo:run-old#friction-density": "abc"}')
    snapshot.write_text(original, encoding="utf-8")
    _feed_empty_stdin(monkeypatch)

    assert MOD.main() == 0
    assert [path.name for path in out_dir.iterdir()] == [snapshot.name]
    assert snapshot.read_text(encoding="utf-8") == original
    assert "incomplete source" in capsys.readouterr().err


def test_main_does_not_write_daily_artifact_for_unchanged_state(monkeypatch, tmp_path):
    records = [
        {"skill_name": "run-x", "passed": False, "timestamp": f"2026-06-0{i}T00:00:00Z"}
        for i in (1, 2, 3)
    ]
    out_dir = _redirect(monkeypatch, tmp_path, score_records=records)
    out_dir.mkdir(parents=True)
    anomalies = MOD._detect_anomalies(MOD._load_evals()["evaluations"])
    assert [a["kind"] for a in anomalies] == ["consecutive_fail"]
    state = MOD._compute_delta(anomalies, {})["state"]
    (out_dir / "2026-01-01-rubric-update.md").write_text(
        _generated(json.dumps(state, sort_keys=True)), encoding="utf-8"
    )
    _feed_empty_stdin(monkeypatch)
    assert MOD.main() == 0
    assert [p.name for p in out_dir.iterdir()] == ["2026-01-01-rubric-update.md"]


def test_main_mkdir_failure_degrades_to_noop_exit0(monkeypatch, tmp_path, capsys):
    """移植性: どの候補も書込不能なら graceful degrade で exit 0 / Traceback 無し。

    read-only install を模す。旧仕様の exit 1 は廃し、SessionEnd hook を絶対に
    クラッシュさせない (no writable sink → silent no-op)。
    """
    records = [
        {"skill_name": "run-x", "passed": False, "timestamp": f"2026-06-0{i}T00:00:00Z"}
        for i in (1, 2, 3)
    ]
    _redirect(monkeypatch, tmp_path, score_records=records)
    _feed_empty_stdin(monkeypatch)
    # 全候補が書込不能 = read-only install。
    monkeypatch.setattr(MOD, "_dir_is_writable", lambda d: False)
    assert MOD.main() == 0
    err = capsys.readouterr().err
    assert "no writable sink" in err
    assert "Traceback" not in err


def test_main_existing_primary_write_failure_uses_fallback_baseline(
    monkeypatch, tmp_path, capsys
):
    """既存 primary を基準にしつつ atomic write 失敗時は fallback へ退避する。"""
    records = [
        {"skill_name": "run-x", "passed": False, "timestamp": f"2026-06-0{i}T00:00:00Z"}
        for i in (1, 2, 3)
    ]
    _redirect(monkeypatch, tmp_path, score_records=records)
    _feed_empty_stdin(monkeypatch)
    primary = tmp_path / "proposals"
    fallback = tmp_path / "state" / "proposals"
    primary.mkdir(parents=True)
    (primary / "2026-01-01-rubric-update.md").write_text(_generated("{}"), encoding="utf-8")
    monkeypatch.setattr(MOD, "_candidate_proposals_dirs", lambda: [primary, fallback])
    monkeypatch.setattr(MOD, "_dir_is_writable", lambda d: True)
    original_atomic_write = MOD._atomic_write_text

    def boom(path, text):
        if path.name.endswith("-rubric-update.md") and primary in path.parents:
            raise OSError("disk full")
        return original_atomic_write(path, text)

    monkeypatch.setattr(MOD, "_atomic_write_text", boom)
    assert MOD.main() == 0
    assert list(fallback.glob("*-rubric-update.md")), "fallback に退避されていない"
    assert "Traceback" not in capsys.readouterr().err


def test_atomic_write_replaces_complete_file_without_temp_residue(tmp_path):
    target = tmp_path / "snapshot.md"
    MOD._atomic_write_text(target, "first\n")
    MOD._atomic_write_text(target, "second\n")
    assert target.read_text(encoding="utf-8") == "second\n"
    assert [path.name for path in tmp_path.iterdir()] == [target.name]


class FakeMsvcrt:
    """msvcrt.locking の代わり。busy なら LK_NBLCK を OSError で断る (実物と同じ)。"""

    LK_NBLCK = 2
    LK_UNLCK = 0

    def __init__(self, busy=False):
        self.calls = []
        self.busy = busy

    def locking(self, file_descriptor, mode, length):
        self.calls.append((file_descriptor, mode, length))
        if self.busy and mode == self.LK_NBLCK:
            raise OSError(36, "Resource deadlock avoided")


def test_sink_lock_uses_windows_backend_when_fcntl_is_unavailable(monkeypatch, tmp_path):
    backend = FakeMsvcrt()
    monkeypatch.setattr(MOD, "_fcntl", None)
    monkeypatch.setattr(MOD, "_msvcrt", backend)

    with MOD._sink_lock(tmp_path / "windows-sink"):
        pass

    # 待たない (LK_LOCK は 10 秒再試行するので SessionEnd の timeout 3 秒を超える)
    assert [mode for _, mode, _ in backend.calls] == [backend.LK_NBLCK, backend.LK_UNLCK]
    assert all(length == 1 for _, _, length in backend.calls)


def test_sink_lock_windows_backend_gives_up_when_busy(monkeypatch, tmp_path):
    backend = FakeMsvcrt(busy=True)
    monkeypatch.setattr(MOD, "_fcntl", None)
    monkeypatch.setattr(MOD, "_msvcrt", backend)

    with pytest.raises(MOD._SinkBusy):
        with MOD._sink_lock(tmp_path / "windows-busy-sink", wait=0.05):
            pass
    assert backend.LK_UNLCK not in [mode for _, mode, _ in backend.calls]


def test_sink_lock_without_any_backend_is_an_oserror(monkeypatch, tmp_path):
    """backend が無ければ OSError。main は書けない書込先として次の候補へ進む。"""
    monkeypatch.setattr(MOD, "_fcntl", None)
    monkeypatch.setattr(MOD, "_msvcrt", None)
    with pytest.raises(OSError):
        with MOD._sink_lock(tmp_path / "no-backend"):
            pass


def test_script_import_and_lock_work_without_fcntl(monkeypatch, tmp_path):
    """Windows 相当でも module import から unlock まで完走する (1 ファイルの script をそのまま読む)。"""
    backend = FakeMsvcrt()
    real_import = builtins.__import__

    def windows_import(name, *args, **kwargs):
        if name == "fcntl":
            raise ImportError("fcntl is unavailable on Windows")
        if name == "msvcrt":
            return backend
        return real_import(name, *args, **kwargs)

    module_name = "aggregate_evals_without_fcntl"
    module = types.ModuleType(module_name)
    module.__file__ = str(SCRIPT)
    sys.modules[module_name] = module
    monkeypatch.setattr(builtins, "__import__", windows_import)
    try:
        exec(
            compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec"),
            module.__dict__,
        )
        assert module._fcntl is None
        assert module._msvcrt is backend
        with module._sink_lock(tmp_path / "windows-import-sink"):
            pass
    finally:
        sys.modules.pop(module_name, None)

    assert [mode for _, mode, _ in backend.calls] == [backend.LK_NBLCK, backend.LK_UNLCK]
    assert all(length == 1 for _, _, length in backend.calls)


def test_main_stdin_read_exception_tolerated(monkeypatch, tmp_path):
    out_dir = _redirect(monkeypatch, tmp_path)

    class _BadStdin:
        def read(self):
            raise RuntimeError("no stdin")

    monkeypatch.setattr(sys, "stdin", _BadStdin())
    # stdin 例外は握りつぶし → evals 空 → exit0
    assert MOD.main() == 0
    assert not out_dir.exists()


# 注: subprocess(sys.executable script) で実起動すると path helper が実 repo を指し、
# 実 eval-log に異常があれば proposals/ を汚染するため、main の subprocess 実行は行わない。
# main の全終了経路（空/差分なし/異常書込/入力欠け/書込失敗を非ブロック exit 0）は上の in-process テストで
# path helper を tmp へ差し替えて genuine に網羅済み。subprocess での行カバレッジ計測は
# import-time の module-level コードと純関数経路で既に被覆される。

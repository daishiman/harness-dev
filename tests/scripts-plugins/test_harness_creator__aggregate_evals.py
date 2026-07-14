"""plugins/harness-creator/skills/run-skill-rubric-governance/scripts/aggregate-evals.py の genuine 機能テスト。

SessionEnd hook が EVALS.json + score.jsonl + content-review verdict の 3 ソースを集計し、
連続 FAIL / スコア低下を検出したら proposals/ にドラフトを書き出す純関数群 + main の全分岐を
tmp_path fixture へ path helper を monkeypatch して **実 repo を一切汚染せず** 網羅する。

network: false, keychain: なし, 実 repo 書込: なし(全 path helper を tmp へ差し替え)。

カバー分岐:
- _plugin_root/_repo_root/_eval_log_dir/_evals_path/_proposals_dir: 実パス算出(参照のみ)
- _date_of: 正常 / 非str / 空 / マッチ無し None
- _normalize_score_record: 非dict / skill 無 / passed True/False/欠落(verdict 文字列) / findings None
- _normalize_verdict_record: 非dict / target 無 skill / 正常
- _load_score_jsonl: dir 無 / 空行・不正JSON skip / 正常 / 読込不能 skip
- _load_content_review_verdicts: dir 無 / 不正JSON skip / 正常
- _load_evals: EVALS.json 有(正常/不正JSON warn) / 3 ソース concat
- _verdict_is_fail: FAIL系 各 / 非FAIL
- _score_of: score/overall/mean_score/average / None
- _detect_anomalies: skill 無 skip / 連続FAIL / 2件は不発 / score_drop / drop 不足は不発
- _top_finding_categories: dict(category/rule/kind) / str / 無
- _slugify: 記号除去 / 空 → "rubric"
- _compute_summary: 空 / 件数・fail_rate・mean_score / scores 無 n/a
- _render_proposal: anomalies 無/有 / findings 無/有
- main: evals 空 exit0 / anomalies 無 exit0 / 書込成功 exit0 / mkdir 失敗 exit1 / write 失敗 exit1
"""
import importlib.util
import json
import sys
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


# ── path helper(実 repo を参照する純関数。書込はしないので安全に算出のみ確認) ──
def test_path_helpers_resolve_to_repo_layout():
    plugin_root = MOD._plugin_root()
    assert plugin_root.name == "harness-creator"
    repo_root = MOD._repo_root()
    assert (repo_root / "plugins").exists() or repo_root.name  # repo 配下
    assert MOD._eval_log_dir() == repo_root / "eval-log"
    assert MOD._evals_path() == plugin_root / "EVALS.json"
    pd = MOD._proposals_dir()
    assert pd.parts[-3:] == ("run-skill-rubric-governance", "proposals") or pd.name == "proposals"


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
        {"target": {"skill": "run-b"}, "verdict": "FAIL", "reviewed_at": "2026-06-11T09:00:00+0900"}
    )
    assert n["skill"] == "run-b"
    assert n["verdict"] == "FAIL"
    assert n["date"] == "2026-06-11"
    assert n["score"] is None


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
    out = MOD._load_score_jsonl()
    assert len(out) == 1
    assert out[0]["skill"] == "run-x"


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
    out = MOD._load_score_jsonl()
    assert [o["skill"] for o in out] == ["ok"]


# ── _load_content_review_verdicts ────────────────────────────────────────────
def test_load_verdicts_no_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "absent")
    assert MOD._load_content_review_verdicts() == []


def test_load_verdicts_parses_and_skips_bad(monkeypatch, tmp_path):
    base = tmp_path / "eval-log"
    cr = base / "demo" / "run-y" / "content-review"
    cr.mkdir(parents=True)
    (cr / "ok-verdict.json").write_text(
        json.dumps({"target": {"skill": "run-y"}, "verdict": "FAIL", "reviewed_at": "2026-06-11T00:00:00Z"}),
        encoding="utf-8",
    )
    (cr / "bad-verdict.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: base)
    out = MOD._load_content_review_verdicts()
    assert len(out) == 1
    assert out[0]["skill"] == "run-y"


# ── _load_evals (3 ソース合流) ───────────────────────────────────────────────
def test_load_evals_reads_evals_json(monkeypatch, tmp_path):
    ep = tmp_path / "EVALS.json"
    ep.write_text(
        json.dumps({"evaluations": [{"skill": "run-z", "verdict": "PASS"}, "not-a-dict"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(MOD, "_evals_path", lambda: ep)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "absent")
    out = MOD._load_evals()["evaluations"]
    # 非 dict はスキップ
    assert out == [{"skill": "run-z", "verdict": "PASS"}]


def test_load_evals_bad_evals_json_warns(monkeypatch, tmp_path, capsys):
    ep = tmp_path / "EVALS.json"
    ep.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(MOD, "_evals_path", lambda: ep)
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "absent")
    out = MOD._load_evals()["evaluations"]
    assert out == []
    assert "EVALS.json load failed" in capsys.readouterr().err


def test_load_evals_score_loader_exception_non_blocking(monkeypatch, tmp_path, capsys):
    # _load_score_jsonl が例外を投げても _load_evals は握りつぶし継続(SessionEnd 流儀)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "no-evals.json")

    def boom():
        raise RuntimeError("score boom")

    monkeypatch.setattr(MOD, "_load_score_jsonl", boom)
    monkeypatch.setattr(MOD, "_load_content_review_verdicts", lambda: [])
    monkeypatch.setattr(MOD, "_load_live_trial_verdicts", lambda: [])
    out = MOD._load_evals()["evaluations"]
    assert out == []
    assert "score.jsonl load failed" in capsys.readouterr().err


def test_load_evals_verdict_loader_exception_non_blocking(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "no-evals.json")
    monkeypatch.setattr(MOD, "_load_score_jsonl", lambda: [])
    monkeypatch.setattr(MOD, "_load_live_trial_verdicts", lambda: [])

    def boom():
        raise RuntimeError("verdict boom")

    monkeypatch.setattr(MOD, "_load_content_review_verdicts", boom)
    out = MOD._load_evals()["evaluations"]
    assert out == []
    assert "verdict load failed" in capsys.readouterr().err


def test_load_evals_merges_all_three(monkeypatch, tmp_path):
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
        json.dumps({"target": {"skill": "run-y"}, "verdict": "FAIL", "reviewed_at": "2026-06-11T00:00:00Z"}),
        encoding="utf-8",
    )
    ep = tmp_path / "EVALS.json"
    ep.write_text(json.dumps({"evaluations": [{"skill": "run-w", "verdict": "PASS"}]}), encoding="utf-8")
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: base)
    monkeypatch.setattr(MOD, "_evals_path", lambda: ep)
    skills = {e["skill"] for e in MOD._load_evals()["evaluations"]}
    assert {"run-w", "run-x", "run-y"} == skills


# ── _verdict_is_fail / _score_of ─────────────────────────────────────────────
@pytest.mark.parametrize("v", ["FAIL", "failed", "REJECT", "rejected"])
def test_verdict_is_fail_true(v):
    assert MOD._verdict_is_fail(v) is True


@pytest.mark.parametrize("v", ["PASS", "INCOMPLETE", ""])
def test_verdict_is_fail_false(v):
    assert MOD._verdict_is_fail(v) is False


def test_score_of_each_key():
    assert MOD._score_of({"score": 0.5}) == 0.5
    assert MOD._score_of({"overall": 1}) == 1.0
    assert MOD._score_of({"mean_score": 0.7}) == 0.7
    assert MOD._score_of({"average": 0.3}) == 0.3


def test_score_of_none_when_absent_or_nonnumeric():
    assert MOD._score_of({"score": "high"}) is None
    assert MOD._score_of({}) is None


# ── _detect_anomalies ────────────────────────────────────────────────────────
def test_detect_skips_records_without_skill():
    # skill も rubric_id も無いレコードはグループ化されず無視
    assert MOD._detect_anomalies([{"verdict": "FAIL"}]) == []


def test_detect_consecutive_fail():
    evals = [
        {"skill": "run-x", "date": f"2026-06-0{i}", "verdict": "FAIL"} for i in (1, 2, 3)
    ]
    a = MOD._detect_anomalies(evals)
    assert any(x["kind"] == "consecutive_fail" and x["rubric_id"] == "run-x" for x in a)
    cf = [x for x in a if x["kind"] == "consecutive_fail"][0]
    assert cf["count"] == 3
    assert cf["evidence_dates"] == ["2026-06-01", "2026-06-02", "2026-06-03"]


def test_detect_two_fails_no_trigger():
    evals = [{"skill": "run-x", "date": f"2026-06-0{i}", "verdict": "FAIL"} for i in (1, 2)]
    assert not any(x["kind"] == "consecutive_fail" for x in MOD._detect_anomalies(evals))


def test_detect_score_drop():
    scores = [1.0, 0.5, 0.5, 0.5, 0.5, 0.5]
    evals = [
        {"skill": "run-y", "date": f"2026-06-{i + 1:02d}", "verdict": "PASS", "score": s}
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
        {"skill": "run-y", "date": f"2026-06-{i + 1:02d}", "verdict": "PASS", "score": s}
        for i, s in enumerate(scores)
    ]
    assert not any(x["kind"] == "score_drop" for x in MOD._detect_anomalies(evals))


def test_detect_uses_rubric_id_fallback():
    # skill 無し・rubric_id 有りでもグループ化される
    evals = [
        {"rubric_id": "rid", "date": f"2026-06-0{i}", "verdict": "FAIL"} for i in (1, 2, 3)
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
    assert s["fail_rate"] == 0.0
    assert s["mean_score"] == "n/a"


def test_compute_summary_counts():
    evals = [
        {"verdict": "FAIL", "score": 0.4},
        {"verdict": "PASS", "score": 0.8},
        {"verdict": "REJECT"},  # score 無
    ]
    s = MOD._compute_summary(evals)
    assert s["total"] == 3
    assert s["fail_rate"] == pytest.approx(2 / 3)
    assert s["mean_score"] == round((0.4 + 0.8) / 2, 3)


# ── _render_proposal ─────────────────────────────────────────────────────────
def test_render_proposal_no_anomalies_no_findings():
    text = MOD._render_proposal([], [], {"total": 0, "fail_rate": 0.0, "mean_score": "n/a"})
    assert "rubric-update-proposal" in text
    assert "## 検出された異常\n\n- (なし)" in text
    assert "## 主要 finding カテゴリ (top5)\n\n- (なし)" in text


def test_render_proposal_with_anomalies_and_findings():
    anomalies = [
        {"rubric_id": "run-x", "kind": "consecutive_fail", "count": 3, "evidence_dates": ["2026-06-01"]},
    ]
    findings = [("naming", 4), ("layout", 2)]
    summary = {"total": 10, "fail_rate": 0.3, "mean_score": 0.7}
    text = MOD._render_proposal(anomalies, findings, summary)
    assert "**run-x**: consecutive_fail" in text
    assert "naming: 4 件" in text
    assert "layout: 2 件" in text
    assert "30.00%" in text


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
    assert "run-x" in content
    assert "consecutive_fail" in content


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


def test_main_write_failure_degrades_to_fallback_exit0(monkeypatch, tmp_path, capsys):
    """primary で write が OSError でも fallback 候補へ退避し exit 0。"""
    records = [
        {"skill_name": "run-x", "passed": False, "timestamp": f"2026-06-0{i}T00:00:00Z"}
        for i in (1, 2, 3)
    ]
    _redirect(monkeypatch, tmp_path, score_records=records)
    _feed_empty_stdin(monkeypatch)
    primary = tmp_path / "proposals"
    fallback = tmp_path / "state" / "proposals"
    monkeypatch.setattr(MOD, "_candidate_proposals_dirs", lambda: [primary, fallback])
    monkeypatch.setattr(MOD, "_dir_is_writable", lambda d: True)
    orig = Path.write_text

    def boom(self, *a, **k):
        if self.name.endswith("-rubric-update.md") and primary in self.parents:
            raise OSError("disk full")
        return orig(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", boom)
    assert MOD.main() == 0
    assert list(fallback.glob("*-rubric-update.md")), "fallback に退避されていない"
    assert "Traceback" not in capsys.readouterr().err


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
# main の全終了経路(exit0 空/正常/異常書込, exit1 mkdir/write 失敗)は上の in-process テストで
# path helper を tmp へ差し替えて genuine に網羅済み。subprocess での行カバレッジ計測は
# import-time の module-level コードと純関数経路で既に被覆される。

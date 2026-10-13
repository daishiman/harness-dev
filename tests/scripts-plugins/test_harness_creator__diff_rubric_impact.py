"""diff-rubric-impact.py が score ログだけを数え、数えられないときは止まることを確かめる。

対象 script:
  plugins/harness-creator/skills/run-skill-rubric-governance/scripts/diff-rubric-impact.py

以前は --logs 直下の *.jsonl をすべて読み、score の無いレコードを 100 点として数えていた。
SKILL.md の手順どおり governance log（$SKILL_DIR/log）を渡すと flip_rate が常に 0 になり、
30% 超の判定が働かなかった（fail-open）。ここでは次を固定する。

- score を持つレコードが 0 件なら exit 2（governance log だけのディレクトリ、空のディレクトリ）
- score ログ（*-score.jsonl を再帰で探す）から flip_rate を正しく出す
- score の無いレコードは数えず、skipped_no_score に件数を出す

また以前は提案の向きを見ず、緩和（ルール削除など）の提案でも「改正した rule が全レコードで
新たに発火する」最悪の場合で見積もり、major に強制昇格していた（Key Rule 2 の minor=緩和と矛盾）。
ここでは向きごとの見積もりも固定する。

- remove と modify+relax は緩和: would_flip 0（impact_model: relaxation_no_new_failures）
- add と modify+tighten は厳格化: 今までどおり最悪の場合（impact_model: worst_case_tightening）
- modify で direction が無いときは厳格化とみなし、仮定したことを direction_source: assumed で出す
- change.type・change.direction の値が不正、または食い違うときは exit 2

さらに以前は required_bump を flip_rate だけで決め、厳格化でも 30% 以下なら提案の bump
（minor や patch）をそのまま返していた（Key Rule 2 の major=厳格化と矛盾）。ここでは次も固定する。

- 厳格化の required_bump は flip_rate に関わらず major
- 30% の判定は exceeds_flip_rate_limit に別に出す（bump は決めない）

さらに以前は緩和の required_bump を提案の bump のまま返し、閾値や severity を下げる緩和を
patch で出すと required_bump も patch になっていた（semver 規約の「内容を変えるなら最低 minor」と
矛盾）。bump の値も確かめず、"huge" のような値をそのまま出していた。ここでは次も固定する。

- 緩和の required_bump は提案の bump と minor の大きい方（patch は minor に上げる）
- 提案の bump が required_bump に届かないときは stderr に出す（文言だけの patch と緊急パッチは承認者が確かめる）
- bump が無いとき、major・minor・patch 以外のときは exit 2

さらに以前は、最上位と change.bump の両方に bump があると change.bump だけを確かめて使い、最上位の
不正な値（"huge"）や両方の食い違い（minor と patch）を黙って通していた。severity も、high・medium・low
以外（critical・High・error・warn など）や無いときは、黙って medium の重みで見積もっていた（最悪の場合で
なくなる）。ここでは次も固定する。

- 最上位と change.bump の両方があり、どちらかの値が不正か、値が違うときは exit 2
- 厳格化で severity から重みが決まらないときは、一番重い重みで見積もって stderr に出す（exit 2 にはしない）
- 使った重みと、それが宣言どおりか推し量ったかを stdout の severity_weight と severity_source にも残す
  （declared / assumed。緩和は重みを使わないので null）

fixture は tmp_path に書き、repo の eval-log は読まない。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-rubric-governance"
SCRIPT = SKILL / "scripts" / "diff-rubric-impact.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, timeout=30)


def _proposal(tmp_path: Path, severity: str = "high", bump: str = "minor", **change) -> Path:
    """改正提案の JSON を書く。change に type・direction などを足せる（値が None のキーは書かない）。"""
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "proposal.json"
    body = {"severity": severity, "bump": bump, **{k: v for k, v in change.items() if v is not None}}
    p.write_text(json.dumps({"proposal_id": "PROP-T", "change": body}), encoding="utf-8")
    return p


def _write_jsonl(path: Path, records) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [r if isinstance(r, str) else json.dumps(r) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _score(score, *rules):
    return {"score": score, "threshold": 80, "passed": score >= 80,
            "findings": [{"id": r, "rubric_item_id": r, "severity": "high"} for r in rules]}


GOVERNANCE_RECORDS = [
    {"proposal_id": "PROP-1", "bump": "minor", "applied_at": "2026-10-09T00:00:00Z",
     "approvers": ["a"], "reviewers": ["b"], "flip_rate": 0.0},
    {"event": "rollback", "rubric_version": "1.3.0"},
    {"proposal_id": "PROP-2", "bump": "patch", "findings": []},
    {"proposal_id": "PROP-3", "bump": "major", "flip_rate": 0.5},
]

# high（-20）・合格点 80 で: 100→80 は合格のまま、95→75 と 85→65 は不合格に変わる、79 と 60 は元から不合格
SCORES = [100, 95, 85, 79, 60]


def test_governance_log_only_dir_exits_2(tmp_path):
    log_dir = tmp_path / "log"
    _write_jsonl(log_dir / "governance-log.jsonl", GOVERNANCE_RECORDS)
    proc = _run("--proposal", str(_proposal(tmp_path)), "--logs", str(log_dir))
    assert proc.returncode == 2, proc.stdout
    assert proc.stdout == ""
    assert "score を持つレコードが無い" in proc.stderr


def test_governance_log_named_like_score_log_still_exits_2(tmp_path):
    # 名前が *-score.jsonl でも、score を持たないレコードは数えない
    log_dir = tmp_path / "log"
    _write_jsonl(log_dir / "2026-10-10-score.jsonl", GOVERNANCE_RECORDS)
    proc = _run("--proposal", str(_proposal(tmp_path)), "--logs", str(log_dir))
    assert proc.returncode == 2, proc.stdout
    assert "score なし 4" in proc.stderr


def test_empty_and_missing_dir_exit_2(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    prop = str(_proposal(tmp_path))
    assert _run("--proposal", prop, "--logs", str(empty)).returncode == 2
    assert _run("--proposal", prop, "--logs", str(tmp_path / "missing")).returncode == 2
    a_file = _write_jsonl(tmp_path / "x-score.jsonl", [_score(90)])
    assert _run("--proposal", prop, "--logs", str(a_file)).returncode == 2


def test_flip_rate_from_score_logs(tmp_path):
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(s) for s in SCORES])
    proc = _run("--proposal", str(_proposal(tmp_path)), "--logs", str(log_dir))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert (out["total"], out["would_flip"], out["flip_rate"]) == (5, 2, 0.4)
    assert (out["proposed_bump"], out["required_bump"]) == ("minor", "major")
    assert (out["flip_rate_limit"], out["exceeds_flip_rate_limit"]) == (0.3, True)
    assert (out["score_logs"], out["skipped_no_score"], out["skipped_invalid"], out["unreadable_logs"]) == (1, 0, 0, 0)


def test_records_without_score_are_not_counted(tmp_path):
    # 以前は score の無いレコードを 100 点として分母に入れ、flip_rate を小さく出していた
    log_dir = tmp_path / "eval-log"
    no_score = [{"findings": []}, {"score": None}, {"score": "90"}, {"score": True}, {"passed": True}]
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl",
                 [_score(s) for s in SCORES] + no_score + ["not json", "[1, 2]"])
    proc = _run("--proposal", str(_proposal(tmp_path)), "--logs", str(log_dir))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert (out["total"], out["would_flip"], out["flip_rate"]) == (5, 2, 0.4)
    assert (out["skipped_no_score"], out["skipped_invalid"]) == (5, 2)
    assert out["required_bump"] == "major"
    assert "数えなかったレコード 7 件" in proc.stderr


def test_reads_score_logs_recursively_and_ignores_other_jsonl(tmp_path):
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-09-score.jsonl", [_score(95), _score(100)])
    _write_jsonl(log_dir / "other" / "nested" / "2026-10-10-score.jsonl", [_score(85)])
    # score ログでない jsonl は、score を持っていても読まない
    _write_jsonl(log_dir / "transcript.jsonl", [_score(100)] * 10)
    _write_jsonl(log_dir / "core" / "governance-log.jsonl", [_score(100)] * 10)
    proc = _run("--proposal", str(_proposal(tmp_path)), "--logs", str(log_dir))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert (out["total"], out["would_flip"], out["score_logs"]) == (3, 2, 2)


def test_tightening_below_limit_is_still_major(tmp_path):
    # 以前は flip_rate が 30% 以下なら、厳格化でも提案の minor・patch をそのまま返していた
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(s) for s in SCORES])
    for change in ({"type": "add", "bump": "minor"},
                   {"type": "modify", "direction": "tighten", "bump": "patch"},
                   {"bump": "minor"}):  # 向きの無い提案は厳格化とみなす（assumed）
        proc = _run("--proposal", str(_proposal(tmp_path, severity="low", **change)), "--logs", str(log_dir))
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout)
        # low（-3）: 合格から不合格に変わるのは無い。それでも厳格化なので major
        assert (out["would_flip"], out["flip_rate"]) == (0, 0.0), change
        assert (out["proposed_bump"], out["required_bump"]) == (change["bump"], "major"), change
        assert out["exceeds_flip_rate_limit"] is False, change


def test_hook_mode_without_args_is_noop(tmp_path):
    proc = _run()
    assert (proc.returncode, proc.stdout) == (0, "")


def test_partial_args_fail_as_usage(tmp_path):
    # 以前は "--proposal" が argv に無いと hook とみなして 0 で抜けていた
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(90)])
    assert _run("--logs", str(log_dir)).returncode == 2
    prop = _proposal(tmp_path)
    assert _run(f"--proposal={prop}").returncode == 2


def test_bad_proposal_exits_2(tmp_path):
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(90)])
    bad = tmp_path / "bad.json"
    for text in ("{not json", "[1]", '{"change": 3}'):
        bad.write_text(text, encoding="utf-8")
        proc = _run("--proposal", str(bad), "--logs", str(log_dir))
        assert proc.returncode == 2 and "Traceback" not in proc.stderr, text
    assert _run("--proposal", str(tmp_path / "none.json"), "--logs", str(log_dir)).returncode == 2


# --- 提案の向き（緩和か厳格化か）で見積もりを変える ------------------------------------


def _impact(tmp_path: Path, **change) -> tuple[subprocess.CompletedProcess, dict]:
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(s) for s in SCORES])
    proc = _run("--proposal", str(_proposal(tmp_path, **change)), "--logs", str(log_dir))
    assert proc.returncode == 0, proc.stderr
    return proc, json.loads(proc.stdout)


def test_remove_is_relaxation_and_keeps_minor(tmp_path):
    # 以前は remove でも最悪の場合で見積もり、would_flip 2・flip_rate 0.4 で major に上げていた
    _, out = _impact(tmp_path, type="remove")
    assert (out["would_flip"], out["flip_rate"]) == (0, 0.0)
    assert (out["proposed_bump"], out["required_bump"]) == ("minor", "minor")
    assert (out["change_type"], out["direction"], out["direction_source"]) == ("remove", "relax", "type")
    assert out["impact_model"] == "relaxation_no_new_failures"
    assert out["total"] == 5


def test_add_is_tightening_as_before(tmp_path):
    _, out = _impact(tmp_path, type="add")
    assert (out["would_flip"], out["flip_rate"], out["required_bump"]) == (2, 0.4, "major")
    assert (out["direction"], out["direction_source"]) == ("tighten", "type")
    assert out["impact_model"] == "worst_case_tightening"


def test_modify_relax_has_no_flip(tmp_path):
    _, out = _impact(tmp_path, type="modify", direction="relax")
    assert (out["would_flip"], out["flip_rate"], out["required_bump"]) == (0, 0.0, "minor")
    assert (out["direction"], out["direction_source"]) == ("relax", "declared")
    assert out["impact_model"] == "relaxation_no_new_failures"
    assert out["exceeds_flip_rate_limit"] is False


def test_relaxation_requires_at_least_minor(tmp_path):
    # 以前は緩和を提案の bump のまま返し、patch の緩和が required_bump patch で通っていた
    for change, required in (({"type": "modify", "direction": "relax", "bump": "patch"}, "minor"),
                             ({"type": "remove", "bump": "patch"}, "minor"),
                             ({"type": "modify", "direction": "relax", "bump": "minor"}, "minor"),
                             ({"type": "remove", "bump": "major"}, "major")):
        proc, out = _impact(tmp_path, **change)
        assert (out["proposed_bump"], out["required_bump"]) == (change["bump"], required), change
        assert out["would_flip"] == 0, change
        # 提案が required_bump に届かないときだけ stderr に出す
        assert ("に届かない" in proc.stderr) == (change["bump"] != required), change


def test_tightening_below_major_warns(tmp_path):
    proc, out = _impact(tmp_path, type="add", bump="minor")
    assert (out["proposed_bump"], out["required_bump"]) == ("minor", "major")
    assert "に届かない" in proc.stderr


def test_invalid_or_missing_bump_exits_2(tmp_path):
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(s) for s in SCORES])
    proposals = [_proposal(tmp_path / str(i), type="remove", bump=bump)
                 for i, bump in enumerate(("huge", "", 1, ["minor"], "Minor", None))]
    missing = tmp_path / "missing" / "proposal.json"
    missing.parent.mkdir()
    missing.write_text(json.dumps({"change": {"type": "remove", "severity": "high"}}), encoding="utf-8")
    for pf in [*proposals, missing]:
        proc = _run("--proposal", str(pf), "--logs", str(log_dir))
        assert proc.returncode == 2, pf.read_text(encoding="utf-8")
        assert proc.stdout == "" and "Traceback" not in proc.stderr, pf
        assert "提案の bump を読めない" in proc.stderr, pf


def _write_proposal(path: Path, body: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_top_level_and_change_bump_must_agree(tmp_path):
    # 以前は change.bump だけを確かめて使い、最上位の "huge" や、最上位 minor と change.bump patch の食い違いを通していた
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(s) for s in SCORES])
    cases = [
        ("huge", "minor", "最上位の bump が major・minor・patch のどれでもない"),
        ("minor", "huge", "change.bump が major・minor・patch のどれでもない"),
        (None, "minor", "最上位の bump が major・minor・patch のどれでもない"),
        ("minor", "patch", "値が違う"),
        ("major", "minor", "値が違う"),
    ]
    for i, (top, inner, reason) in enumerate(cases):
        pf = _write_proposal(tmp_path / f"c{i}" / "proposal.json",
                             {"bump": top, "change": {"type": "remove", "severity": "high", "bump": inner}})
        proc = _run("--proposal", str(pf), "--logs", str(log_dir))
        assert proc.returncode == 2, (top, inner)
        assert proc.stdout == "" and "Traceback" not in proc.stderr, (top, inner)
        assert "提案の bump を読めない" in proc.stderr and reason in proc.stderr, (top, inner, proc.stderr)
    # 両方が同じ値なら通る。片方だけでも通る（最上位だけは templates/proposal.json の形）
    for i, body in enumerate(({"bump": "minor", "change": {"type": "remove", "bump": "minor"}},
                              {"bump": "minor", "change": {"type": "remove"}},
                              {"change": {"type": "remove", "bump": "minor"}})):
        proc = _run("--proposal", str(_write_proposal(tmp_path / f"ok{i}" / "proposal.json", body)),
                    "--logs", str(log_dir))
        assert proc.returncode == 0, (body, proc.stderr)
        assert json.loads(proc.stdout)["proposed_bump"] == "minor", body


def test_unknown_severity_tightening_uses_heaviest_weight_and_warns(tmp_path):
    # 以前は high・medium・low 以外や無い severity を黙って medium（-10）とみなし、would_flip を 1 と小さく出していた。
    # 一番重い high（-20）なら SCORES のうち 95 と 85 が不合格に変わり、would_flip は 2
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(s) for s in SCORES])
    for i, severity in enumerate(("critical", "High", "error", "warn", "", 3, None, "<missing>")):
        change = {"type": "add"} if severity == "<missing>" else {"type": "add", "severity": severity}
        pf = _write_proposal(tmp_path / f"s{i}" / "proposal.json", {"bump": "major", "change": change})
        proc = _run("--proposal", str(pf), "--logs", str(log_dir))
        assert proc.returncode == 0, (severity, proc.stderr)
        out = json.loads(proc.stdout)
        assert (out["would_flip"], out["flip_rate"], out["required_bump"]) == (2, 0.4, "major"), severity
        assert "一番重い -20 で見積もった" in proc.stderr, severity
    # 分かる severity では出さない。medium は -10 なので 85 だけが変わる
    proc, out = _impact(tmp_path / "medium", type="add", severity="medium", bump="major")
    assert out["would_flip"] == 1
    assert "一番重い" not in proc.stderr


def test_severity_source_records_whether_the_weight_was_declared(tmp_path):
    # 以前は推し量った重みが stderr にしか出ず、stdout の JSON だけを読む承認者には宣言どおりの見積もりに見えた
    for severity, weight in (("high", -20), ("medium", -10), ("low", -3)):
        _, out = _impact(tmp_path / severity, type="add", severity=severity, bump="major")
        assert (out["severity_weight"], out["severity_source"]) == (weight, "declared"), severity
    # _proposal は severity=None なら null を書く。キーごと無い提案と、知らない値も assumed
    _, out = _impact(tmp_path / "null", type="add", severity=None, bump="major")
    assert (out["severity_weight"], out["severity_source"]) == (-20, "assumed")
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(s) for s in SCORES])
    for name, change in (("missing", {"type": "add"}), ("critical", {"type": "add", "severity": "critical"})):
        pf = _write_proposal(tmp_path / name / "proposal.json", {"bump": "major", "change": change})
        proc = _run("--proposal", str(pf), "--logs", str(log_dir))
        out = json.loads(proc.stdout)
        assert (out["severity_weight"], out["severity_source"]) == (-20, "assumed"), name
        assert "severity_source: assumed" in proc.stderr, name
    # 向きも severity も推し量ったときは、両方に assumed が残る
    pf = _write_proposal(tmp_path / "both" / "proposal.json", {"bump": "major", "change": {"type": "modify"}})
    out = json.loads(_run("--proposal", str(pf), "--logs", str(log_dir)).stdout)
    assert (out["direction_source"], out["severity_source"], out["severity_weight"]) == ("assumed", "assumed", -20)


def test_unknown_severity_on_relaxation_is_not_warned(tmp_path):
    # 緩和は severity の重みを使わない（would_flip は定義上 0）ので、知らない値でも黙って通す
    proc, out = _impact(tmp_path, type="remove", severity="warn")
    assert (out["would_flip"], out["impact_model"]) == (0, "relaxation_no_new_failures")
    assert "一番重い" not in proc.stderr
    # 重みを使っていないので、宣言の有無にかかわらず severity_weight と severity_source は null
    assert (out["severity_weight"], out["severity_source"]) == (None, None)
    _, out = _impact(tmp_path / "declared", type="modify", direction="relax", severity="high")
    assert (out["severity_weight"], out["severity_source"]) == (None, None)


def test_missing_type_with_direction_follows_declaration(tmp_path):
    # change.type が無く change.direction があるときは、宣言に従う（docstring のとおり）
    _, out = _impact(tmp_path, direction="relax")
    assert (out["change_type"], out["direction"], out["direction_source"]) == (None, "relax", "declared")
    assert (out["would_flip"], out["required_bump"]) == (0, "minor")


def test_modify_tighten_is_worst_case_as_before(tmp_path):
    proc, out = _impact(tmp_path, type="modify", direction="tighten")
    assert (out["would_flip"], out["flip_rate"], out["required_bump"]) == (2, 0.4, "major")
    assert (out["direction"], out["direction_source"]) == ("tighten", "declared")
    assert out["impact_model"] == "worst_case_tightening"
    assert "direction_source: assumed" not in proc.stderr


def test_modify_without_direction_assumes_tightening_and_says_so(tmp_path):
    # 黙って緩和として扱わない。最悪の場合で見積もり、仮定したことを出力と stderr に出す
    proc, out = _impact(tmp_path, type="modify")
    assert (out["would_flip"], out["flip_rate"], out["required_bump"]) == (2, 0.4, "major")
    assert (out["direction"], out["direction_source"]) == ("tighten", "assumed")
    assert out["impact_model"] == "worst_case_tightening"
    assert "direction_source: assumed" in proc.stderr


def test_missing_type_assumes_tightening(tmp_path):
    _, out = _impact(tmp_path)
    assert (out["change_type"], out["direction"], out["direction_source"]) == (None, "tighten", "assumed")
    assert (out["would_flip"], out["required_bump"]) == (2, "major")


def test_invalid_direction_or_type_exits_2(tmp_path):
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(s) for s in SCORES])
    cases = [
        {"type": "modify", "direction": "loosen"},
        {"type": "modify", "direction": ""},
        {"type": "modify", "direction": 1},
        {"type": "modify", "direction": ["relax"]},
        {"type": "delete"},
        {"type": ["remove"]},
        # type と食い違う direction
        {"type": "remove", "direction": "tighten"},
        {"type": "add", "direction": "relax"},
    ]
    for change in cases:
        proc = _run("--proposal", str(_proposal(tmp_path, **change)), "--logs", str(log_dir))
        assert proc.returncode == 2, change
        assert proc.stdout == "" and "Traceback" not in proc.stderr, change
        assert "提案の向きを決められない" in proc.stderr, change


def test_template_example_matches_semver_rules(tmp_path):
    # 例が規約に合っていること（add なら major・14 日以上、modify なら direction を書く）
    template = SKILL / "templates" / "proposal.json"
    proposal = json.loads(template.read_text(encoding="utf-8"))
    change = proposal["change"]
    if change["type"] == "add":
        assert proposal["bump"] == "major" and proposal["sunset_days"] >= 14
    if change["type"] == "modify":
        assert change["direction"] in ("relax", "tighten")
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl", [_score(s) for s in SCORES])
    proc = _run("--proposal", str(template), "--logs", str(log_dir))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["direction_source"] != "assumed"
    assert out["required_bump"] == proposal["bump"]


# --- 手順書が governance log を渡さないこと（指摘の再発防止） -----------------------


def test_skill_docs_pass_score_log_location():
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    commands = [line for line in skill_md.splitlines()
                if "--logs " in line and ("diff-rubric-impact.py" in line or "lint-rubric-violation.py" in line)
                and "governance log" not in line]  # Gotcha の「governance log を渡したときも同じ」は除く
    assert len(commands) >= 3, commands
    for line in commands:
        assert "--logs eval-log" in line and "$SKILL_DIR/log" not in line, line
    proposal = json.loads((SKILL / "templates" / "proposal.json").read_text(encoding="utf-8"))
    assert proposal["impact_assessment"]["past_eval_logs"] == "eval-log"
    board = (SKILL / "references" / "governance-board.md").read_text(encoding="utf-8")
    # diff-rubric-impact.py の出力に無いキーで判定させない
    assert "newly_failing_count" not in board
    assert "would_flip == 0" in board


def test_docs_describe_direction_and_current_output_keys():
    # 緩和の定義と責任、向きの宣言を手順書と board に書き、古い出力キーで判定させない
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    board = (SKILL / "references" / "governance-board.md").read_text(encoding="utf-8")
    for text in (skill_md, board):
        assert "今まで合格したものがすべて合格のままである変更" in text
        assert "change.direction" in text and "relaxation_no_new_failures" in text
        assert "direction_source: assumed" in text
    prompt = (SKILL / "prompts" / "R1-govern.md").read_text(encoding="utf-8")
    assert "proposal_path |" not in prompt and "warn_only" not in prompt
    assert "--proposal <proposal.json> --logs eval-log" in prompt
    for params in (ROOT / "plugins" / "skill-governance-config" / "config" / "governance-params.json.example",
                   ROOT / "references" / "governance-params.json.example"):
        conds = json.loads(params.read_text(encoding="utf-8"))["solo_operator_mode"]["self_approval_conditions"]
        assert not any("newly_failing" in c for c in conds), params
        assert any(c.startswith("would_flip == 0") for c in conds), params


def test_docs_state_bump_and_grace_rules_the_same_way():
    # 厳格化は常に major（30% は board 招集の根拠）。猶予期間 0 日の minor は条件付きの例外として、
    # 規約・手順・プロンプト・ひな形・27章が同じ条件（would_flip 0 と承認者の確認）を書く
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "major へ強制昇格" not in skill_md
    assert "exceeds_flip_rate_limit" in skill_md
    key_rule_3 = next(line for line in skill_md.splitlines() if line.startswith("3. **猶予期間**"))
    rules = (SKILL / "references" / "version-rules.md").read_text(encoding="utf-8")
    minor_section = rules.split("## minor", 1)[1].split("\n## ", 1)[0]
    prompt = (SKILL / "prompts" / "R1-govern.md").read_text(encoding="utf-8")
    grace_term = next(line for line in prompt.splitlines() if line.startswith("| 猶予 (grace)"))
    notes = json.loads((SKILL / "templates" / "proposal.json").read_text(encoding="utf-8"))["notes"]
    runbook = (ROOT / "doc" / "ClaudeCodeスキルの設計書" / "27-rubric-governance-runbook.md").read_text(encoding="utf-8")
    for name, text in (("Key Rule 3", key_rule_3), ("version-rules minor", minor_section),
                       ("R1 猶予", grace_term), ("template notes", notes), ("27章", runbook)):
        assert "would_flip" in text and "承認者が緩和の根拠を確かめた" in text, name
    assert "newly_failing>0" not in runbook


def test_grace_days_and_proposal_status_follow_version_rules():
    # 猶予日数の正本は Key Rule 3。params の min_days は major の最低日数の写しで、23章は日数を書き写さない。
    # 提案 md の status は version-rules.md の表にある値だけを使う
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    key_rule_3 = next(line for line in skill_md.splitlines() if line.startswith("3. **猶予期間**"))
    for params in (ROOT / "plugins" / "skill-governance-config" / "config" / "governance-params.json.example",
                   ROOT / "references" / "governance-params.json.example"):
        min_days = json.loads(params.read_text(encoding="utf-8"))["grace_period"]["min_days"]
        assert f"major は最低{min_days}日" in key_rule_3, params
    ch23 = (ROOT / "doc" / "ClaudeCodeスキルの設計書" / "23-meta-skill-architecture.md").read_text(encoding="utf-8")
    assert "または 30 日" not in ch23
    rules = (SKILL / "references" / "version-rules.md").read_text(encoding="utf-8")
    status_section = rules.split("## 提案 md の status", 1)[1].split("\n## ", 1)[0]
    defined = set(re.findall(r"^\| `([a-z]+)` \|", status_section, re.M))
    assert defined == {"draft", "pending", "applied", "rejected"}
    for md in sorted((SKILL / "proposals").glob("*.md")):
        status = next(line for line in md.read_text(encoding="utf-8").splitlines() if line.startswith("status:"))
        assert status.split(":", 1)[1].strip() in defined, md.name


def test_skill_md_commands_stay_within_allowed_tools():
    # allowed-tools は Bash(python3 *)。shasum や、環境変数を前に付けたコマンドを手順に書かない
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "shasum" not in skill_md
    assert "RELEASE_VERSION=" not in skill_md

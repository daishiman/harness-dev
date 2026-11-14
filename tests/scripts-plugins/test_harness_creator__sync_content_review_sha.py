"""Functional tests for run-elegant-review/scripts/sync-content-review-sha.py.

レビュー由来の修正を当てた直後に限り content-review verdict の sha を結び直す script。
CLI 契約 (exit 0/1/2・書く/書かない) は subprocess で、結び直し後の verdict が
scripts/lint-content-review.py の _check_verdict を通ることは lint の module を tmp の
repo へ向けて確かめる (repo の eval-log は触らない)。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins" / "harness-creator"
SCRIPT = PLUGIN / "skills" / "run-elegant-review" / "scripts" / "sync-content-review-sha.py"
SCHEMA = PLUGIN / "skills" / "run-build-skill" / "schemas" / "content-review-verdict.schema.json"
LINT = REPO_ROOT / "scripts" / "lint-content-review.py"
AGENT = PLUGIN / "agents" / "elegant-improvement-executor.md"
PROTOCOL = PLUGIN / "skills" / "run-build-skill" / "references" / "content-review-protocol.md"

PLUGIN_NAME, SKILL_NAME = "p1", "run-x"
BEFORE = "---\nname: run-x\nkind: run\n---\n本文 (修正前)\n"
AFTER = "---\nname: run-x\nkind: run\n---\n本文 (指摘を当てた後)\n"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _verdict(review_kind: str, sha: str, negative: list[str], verdict: str = "PASS") -> dict:
    return {
        "target": {"plugin": PLUGIN_NAME, "skill": SKILL_NAME, "skill_md_sha256": sha},
        "review_kind": review_kind,
        "verdict": verdict,
        "findings_summary": {"contradiction": 0, "omission": 0, "inconsistency": 0, "dependency_break": 0, "smell": len(negative)},
        "reviewer": "assign-skill-design-evaluator",
        "reviewed_at": "2026-11-13T00:00:00Z",
        "iterations": 1,
        "human_review_required": False,
        "feedback_loop": {
            "loop_scope": "both",
            "criteria_evaluated": ["IN1"],
            "positive_feedback": ["良い判断"],
            "negative_feedback": negative,
            "iteration": 1,
            "iteration_limit": 3,
            "hook_trigger": "manual",
            "next_action": "none",
        },
        "notes": "日本語のメモ",
    }


@pytest.fixture
def repo(tmp_path):
    md = tmp_path / "plugins" / PLUGIN_NAME / "skills" / SKILL_NAME / "SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text(BEFORE, encoding="utf-8")
    review_dir = tmp_path / "eval-log" / PLUGIN_NAME / SKILL_NAME / "content-review"
    review_dir.mkdir(parents=True)
    paths = {
        "elegance": review_dir / "elegance-verdict.json",
        "rubric": review_dir / "rubric-verdict.json",
    }
    sha_before = _sha(BEFORE)
    for kind, negative in (("elegance", ["[low] 指摘 A", "[low] 指摘 B"]), ("rubric", ["[low] 指摘 A'"])):
        text = json.dumps(_verdict(kind, sha_before, negative), ensure_ascii=False, indent=2) + "\n"
        paths[kind].write_text(text, encoding="utf-8")
    # レビューの勧めた修正を当てた状態 (SKILL.md が変わった)
    md.write_text(AFTER, encoding="utf-8")
    return {"root": tmp_path, "md": md, "paths": paths, "before": sha_before, "after": _sha(AFTER)}


def _run(repo, *, from_sha=None, ids="elegance:1", extra=()):
    cmd = [
        sys.executable, str(SCRIPT),
        "--plugin", PLUGIN_NAME, "--skill", SKILL_NAME,
        "--from-sha", from_sha if from_sha is not None else repo["before"],
        "--finding-ids", ids,
        "--repo-root", str(repo["root"]),
        *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def _snapshot(repo) -> dict:
    return {kind: path.read_bytes() for kind, path in repo["paths"].items() if path.exists()}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_lint(repo, monkeypatch):
    spec = importlib.util.spec_from_file_location("lint_content_review_for_sync", LINT)
    lint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lint)
    monkeypatch.setattr(lint, "ROOT", repo["root"])
    monkeypatch.setattr(lint, "PLUGINS_DIR", repo["root"] / "plugins")
    monkeypatch.setattr(lint, "EVAL_LOG", repo["root"] / "eval-log")
    return lint


# ---------- 結び直し (成功) ----------

def test_rebind_updates_both_verdicts_and_appends_audit_record(repo):
    originals = {kind: _load(path) for kind, path in repo["paths"].items()}
    proc = _run(repo, ids="elegance:2, rubric:1")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "rebound"
    assert out["to_sha"] == repo["after"]

    for kind, path in repo["paths"].items():
        data = _load(path)
        assert data["target"]["skill_md_sha256"] == repo["after"]
        (entry,) = data["sha_rebinds"]
        assert entry["from_sha"] == repo["before"]
        assert entry["to_sha"] == repo["after"]
        assert entry["finding_ids"] == ["elegance:2", "rubric:1"]
        assert entry["tool"] == "sync-content-review-sha"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["rebound_at"])
        # sha と監査記録のほかは変えない (verdict・reviewer・reviewed_at・iterations を含む)
        expected = dict(originals[kind])
        expected["target"] = {**expected["target"], "skill_md_sha256": repo["after"]}
        expected["sha_rebinds"] = data["sha_rebinds"]
        assert data == expected
        Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(data)


def test_rebind_keeps_the_original_json_layout(repo):
    assert _run(repo).returncode == 0
    for path in repo["paths"].values():
        text = path.read_text(encoding="utf-8")
        assert text == json.dumps(_load(path), ensure_ascii=False, indent=2) + "\n"
        assert "日本語のメモ" in text  # ensure_ascii=False の元ファイルを \\u エスケープへ変えない


def test_rebound_verdicts_pass_lint_content_review(repo, monkeypatch):
    lint = _load_lint(repo, monkeypatch)
    review_dir = repo["paths"]["elegance"].parent
    for fname in ("elegance-verdict.json", "rubric-verdict.json"):
        before = lint._check_verdict(review_dir / fname, PLUGIN_NAME, SKILL_NAME, fname)
        assert before.startswith("stale-sha:")  # 修正を当てただけで stale になる (因果ループの起点)

    assert _run(repo).returncode == 0

    for fname in ("elegance-verdict.json", "rubric-verdict.json"):
        assert lint._check_verdict(review_dir / fname, PLUGIN_NAME, SKILL_NAME, fname) is None


# ---------- 拒否 (exit 1・ファイルは変えない) ----------

def test_fail_verdict_is_rejected(repo):
    path = repo["paths"]["rubric"]
    data = _load(path)
    data["verdict"] = "FAIL"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    snapshot = _snapshot(repo)

    proc = _run(repo)
    assert proc.returncode == 1
    assert "verdict='FAIL'" in proc.stderr
    assert "要再レビュー" in proc.stderr
    assert _snapshot(repo) == snapshot


def test_from_sha_mismatch_is_rejected(repo):
    snapshot = _snapshot(repo)
    proc = _run(repo, from_sha=_sha("別の内容\n"))
    assert proc.returncode == 1
    assert "--from-sha" in proc.stderr
    assert _snapshot(repo) == snapshot


@pytest.mark.parametrize("ids", ["elegance:3", "rubric:2", "elegance:1,rubric:9"])
def test_unknown_finding_id_is_rejected(repo, ids):
    snapshot = _snapshot(repo)
    proc = _run(repo, ids=ids)
    assert proc.returncode == 1
    assert "negative_feedback" in proc.stderr
    assert _snapshot(repo) == snapshot


def test_empty_finding_ids_are_rejected(repo):
    snapshot = _snapshot(repo)
    proc = _run(repo, ids=" , ")
    assert proc.returncode == 1
    assert "--finding-ids が空" in proc.stderr
    assert _snapshot(repo) == snapshot


def test_verdict_without_negative_feedback_cannot_be_rebound(repo):
    path = repo["paths"]["elegance"]
    data = _load(path)
    data["feedback_loop"]["negative_feedback"] = []
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    snapshot = _snapshot(repo)
    proc = _run(repo, ids="elegance:1")
    assert proc.returncode == 1
    assert _snapshot(repo) == snapshot


def test_missing_one_verdict_is_rejected(repo):
    repo["paths"]["rubric"].unlink()
    snapshot = _snapshot(repo)
    proc = _run(repo)
    assert proc.returncode == 1
    assert "rubric-verdict.json" in proc.stderr
    assert _snapshot(repo) == snapshot


def test_a_finding_rebinds_only_once(repo):
    assert _run(repo, ids="elegance:1").returncode == 0
    # 結び直した後にもう一度 SKILL.md を書き換え、同じ指摘で通そうとする
    repo["md"].write_text(AFTER + "審査されていない追記\n", encoding="utf-8")
    snapshot = _snapshot(repo)
    proc = _run(repo, from_sha=repo["after"], ids="elegance:1")
    assert proc.returncode == 1
    assert "すでに sha_rebinds で使われた" in proc.stderr
    assert _snapshot(repo) == snapshot
    # まだ使っていない指摘なら結び直せる (記録は 2 件になる)
    assert _run(repo, from_sha=repo["after"], ids="elegance:2").returncode == 0
    assert len(_load(repo["paths"]["rubric"])["sha_rebinds"]) == 2


def _share_text_between_verdicts(repo):
    """rubric の 1 番目を elegance の 1 番目と同じ本文にする (1 文脈が 2 verdict を書く実態)。"""
    path = repo["paths"]["rubric"]
    data = _load(path)
    data["feedback_loop"]["negative_feedback"] = ["[low]  指摘 A"]  # 空白の揺れも同じ指摘とみなす
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_same_finding_cannot_be_reused_under_the_other_verdicts_id(repo):
    _share_text_between_verdicts(repo)
    assert _run(repo, ids="elegance:1").returncode == 0
    repo["md"].write_text(AFTER + "審査されていない追記\n", encoding="utf-8")
    snapshot = _snapshot(repo)
    proc = _run(repo, from_sha=repo["after"], ids="rubric:1")
    assert proc.returncode == 1
    assert "同じ本文の指摘" in proc.stderr
    assert _snapshot(repo) == snapshot


def test_both_ids_of_one_finding_may_be_listed_in_one_call(repo):
    _share_text_between_verdicts(repo)
    proc = _run(repo, ids="elegance:1,rubric:1")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "rebound"


# ---------- 書かない成功 (noop / dry-run / already-bound) ----------

def test_noop_when_skill_md_is_unchanged(repo):
    repo["md"].write_text(BEFORE, encoding="utf-8")
    snapshot = _snapshot(repo)
    proc = _run(repo)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["status"] == "noop"
    assert _snapshot(repo) == snapshot


def test_dry_run_does_not_write(repo):
    snapshot = _snapshot(repo)
    proc = _run(repo, extra=("--dry-run",))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"] == "dry-run"
    assert out["entry"]["to_sha"] == repo["after"]
    assert _snapshot(repo) == snapshot
    assert not list(repo["paths"]["elegance"].parent.glob(".*"))  # 一時ファイルも残さない


def test_rerun_with_same_arguments_is_idempotent(repo):
    assert _run(repo).returncode == 0
    snapshot = _snapshot(repo)
    proc = _run(repo)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["status"] == "already-bound"
    assert _snapshot(repo) == snapshot


# ---------- 引数・入出力の誤り (exit 2) ----------

@pytest.mark.parametrize("args", [
    {"ids": "F-001"},
    {"ids": "elegance:0"},
    {"from_sha": "abc"},
])
def test_malformed_arguments_exit_2(repo, args):
    snapshot = _snapshot(repo)
    proc = _run(repo, **args)
    assert proc.returncode == 2
    assert _snapshot(repo) == snapshot


def test_missing_skill_md_exits_2(repo):
    repo["md"].unlink()
    assert _run(repo).returncode == 2


def test_broken_verdict_json_exits_2(repo):
    repo["paths"]["elegance"].write_text("{not json", encoding="utf-8")
    assert _run(repo).returncode == 2


# ---------- 配線 ----------

def test_executor_and_protocol_point_to_the_script():
    agent = AGENT.read_text(encoding="utf-8")
    protocol = PROTOCOL.read_text(encoding="utf-8")
    for text in (agent, protocol):
        assert "sync-content-review-sha.py" in text
        assert "--finding-ids" in text
    assert "要再レビュー" in agent

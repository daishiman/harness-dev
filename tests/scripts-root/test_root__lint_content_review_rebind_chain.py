"""scripts/lint-content-review.py の結び直しの連鎖・pair・skill_dir_digest の検査 (harness-g67)。

sync-content-review-sha.py が書く記録を lint が後から確かめる側の test。
  - sha_rebinds[] が元のレビュー (target.reviewed_skill_md_sha256) から現在の sha まで
    切れずにつながっているか (rebind-chain)。
  - elegance と rubric が同じ記録を持ち、1 つの指摘を 2 回使っていないか (pair-mismatch)。
  - references/ などが変わったら verdict を期限切れにするか (stale-dir-digest)。
  - 実在する sha_rebinds が新しい連鎖検査を通るか (検査を足して既存の緑を壊していない)。
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-content-review.py"

_SPEC = importlib.util.spec_from_file_location("lint_content_review_chain", SCRIPT)
LCR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LCR)

PLUGIN, SKILL = "p1", "run-x"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _entry(from_sha, to_sha, ids=("elegance:1",), replay=None):
    entry = {"from_sha": from_sha, "to_sha": to_sha, "rebound_at": "2026-11-14T00:00:00Z", "tool": "sync-content-review-sha"}
    if replay is not None:
        entry["replay"] = replay
    if ids is not None:
        entry["finding_ids"] = list(ids)
    return entry


def _verdict(kind, sha, negative, **target_extra):
    return {
        "target": {"plugin": PLUGIN, "skill": SKILL, "skill_md_sha256": sha, **target_extra},
        "review_kind": kind,
        "verdict": "PASS",
        "reviewer": "tester",
        "reviewed_at": "2026-11-14T00:00:00Z",
        "iterations": 1,
        "feedback_loop": {
            "criteria_evaluated": ["IN1"],
            "iteration_limit": 3,
            "iteration": 1,
            "loop_scope": "both",
            "positive_feedback": ["good"],
            "negative_feedback": negative,
            "next_action": "none",
            "hook_trigger": "manual",
        },
    }


@pytest.fixture
def tree(tmp_path, monkeypatch):
    md = tmp_path / "plugins" / PLUGIN / "skills" / SKILL / "SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text("---\nname: run-x\nkind: run\n---\n# run-x\n\n## 手順\n\n現在\n", encoding="utf-8")
    review_dir = tmp_path / "eval-log" / PLUGIN / SKILL / "content-review"
    review_dir.mkdir(parents=True)
    monkeypatch.setattr(LCR, "ROOT", tmp_path)
    monkeypatch.setattr(LCR, "PLUGINS_DIR", tmp_path / "plugins")
    monkeypatch.setattr(LCR, "EVAL_LOG", tmp_path / "eval-log")
    current = hashlib.sha256(md.read_bytes()).hexdigest()
    return {"root": tmp_path, "md": md, "dir": review_dir, "current": current}


def _write_pair(tree, elegance, rubric):
    for name, data in (("elegance-verdict.json", elegance), ("rubric-verdict.json", rubric)):
        (tree["dir"] / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _errors(tree):
    errors = []
    for name in ("elegance-verdict.json", "rubric-verdict.json"):
        err = LCR._check_verdict(tree["dir"] / name, PLUGIN, SKILL, name)
        if err:
            errors.append(err)
    if not errors:
        err = LCR._check_pair(tree["dir"])
        if err:
            errors.append(err)
    return errors


def _rebound_pair(tree, rebinds, *, reviewed=None, elegance_negative=("[low] A", "[low] B"), rubric_negative=("[low] C",)):
    extra = {} if reviewed is None else {"reviewed_skill_md_sha256": reviewed}
    elegance = _verdict("elegance", tree["current"], list(elegance_negative), **extra)
    rubric = _verdict("rubric", tree["current"], list(rubric_negative), **extra)
    elegance["sha_rebinds"] = copy.deepcopy(rebinds)
    rubric["sha_rebinds"] = copy.deepcopy(rebinds)
    return elegance, rubric


A, B = _sha("reviewed\n"), _sha("middle\n")


# ---------- 連鎖 (rebind-chain) ----------

def test_single_rebind_from_the_reviewed_sha_passes(tree):
    _write_pair(tree, *_rebound_pair(tree, [_entry(A, tree["current"])], reviewed=A))
    assert _errors(tree) == []


def test_two_chained_rebinds_pass(tree):
    rebinds = [_entry(A, B, ids=["elegance:1"]), _entry(B, tree["current"], ids=["rubric:1"])]
    _write_pair(tree, *_rebound_pair(tree, rebinds, reviewed=A))
    assert _errors(tree) == []


def test_legacy_rebind_without_reviewed_sha_passes(tree):
    # g67 より前の verdict は reviewed_skill_md_sha256 を持たない。連鎖の内側と末尾だけを見る
    _write_pair(tree, *_rebound_pair(tree, [_entry(A, tree["current"])]))
    assert _errors(tree) == []


def test_replay_rebind_passes(tree):
    rebinds = [_entry(A, tree["current"], ids=None, replay="artifact-delivery-v1")]
    _write_pair(tree, *_rebound_pair(tree, rebinds, reviewed=A))
    assert _errors(tree) == []


@pytest.mark.parametrize("rebinds, reviewed, message", [
    # 最初の from_sha が元のレビューの sha ではない (レビューしていない版から結び直した)
    (lambda cur: [_entry(B, cur)], A, "target.reviewed_skill_md_sha256"),
    # 途中が切れている (記録を 1 件消した・手で足した)
    (lambda cur: [_entry(A, B), _entry(_sha("x\n"), cur, ids=["rubric:1"])], A, "sha_rebinds[1].to_sha"),
    # 末尾が現在の sha ではない (target だけ手で書き換えた)
    (lambda cur: [_entry(A, B)], A, "last sha_rebinds.to_sha"),
    # 記録が無いのに起点と現在が違う
    (lambda cur: [], A, "without sha_rebinds"),
])
def test_broken_chain_is_reported(tree, rebinds, reviewed, message):
    _write_pair(tree, *_rebound_pair(tree, rebinds(tree["current"]), reviewed=reviewed))
    (error, *_) = _errors(tree)
    assert error.startswith("rebind-chain:")
    assert message in error


@pytest.mark.parametrize("mutate, message", [
    (lambda e: e.update({"replay": "artifact-delivery-v1"}), "exactly one of"),
    (lambda e: e.pop("finding_ids"), "exactly one of"),
    (lambda e: (e.pop("finding_ids"), e.update({"replay": "made-up"})), "not a registered migration"),
    (lambda e: e.update({"tool": "hand"}), "tool must be"),
    (lambda e: e.update({"finding_ids": ["F-001"]}), "finding_ids must be"),
    (lambda e: e.update({"finding_ids": []}), "finding_ids must be"),
    (lambda e: e.update({"finding_ids": ["elegance:1", "elegance:1"]}), "finding_ids must be"),
    # 独立レビューの再現: 文字列でない要素は isinstance の確認より前の set(ids) で unhashable だった
    (lambda e: e.update({"finding_ids": [{}]}), "finding_ids must be"),
    (lambda e: e.update({"finding_ids": [["elegance:1"]]}), "finding_ids must be"),
    # 再現: replay=[] は REPLAY_IDS の in で unhashable だった
    (lambda e: (e.pop("finding_ids"), e.update({"replay": []})), "replay [] is not a registered migration"),
    (lambda e: (e.pop("finding_ids"), e.update({"replay": {}})), "replay {} is not a registered migration"),
    (lambda e: e.update({"from_sha": "abc"}), "64-hex"),
])
def test_malformed_rebind_entry_is_reported(tree, mutate, message):
    entry = _entry(A, tree["current"])
    mutate(entry)
    _write_pair(tree, *_rebound_pair(tree, [entry], reviewed=A))
    (error, *_) = _errors(tree)
    assert message in error


def test_rebind_to_the_same_sha_is_reported(tree):
    cur = tree["current"]
    _write_pair(tree, *_rebound_pair(tree, [_entry(cur, cur)], reviewed=cur))
    (error, *_) = _errors(tree)
    assert "from_sha == to_sha" in error


def test_chain_is_checked_before_stale_sha(tree):
    # target を手で現在の sha に書き換えても、記録の末尾と合わなければ rebind-chain で止まる
    _write_pair(tree, *_rebound_pair(tree, [_entry(A, B)], reviewed=A))
    (error, *_) = _errors(tree)
    assert error.startswith("rebind-chain:")


# ---------- pair (elegance と rubric) ----------

def test_rebinds_that_differ_between_the_two_verdicts_are_reported(tree):
    elegance, rubric = _rebound_pair(tree, [_entry(A, tree["current"])], reviewed=A)
    rubric["sha_rebinds"][0]["finding_ids"] = ["elegance:2"]
    _write_pair(tree, elegance, rubric)
    assert _errors(tree) == ["pair-mismatch: sha_rebinds differ between elegance and rubric"]


def test_reviewed_sha_that_differs_between_the_two_verdicts_is_reported(tree):
    elegance, rubric = _rebound_pair(tree, [_entry(A, tree["current"])], reviewed=A)
    del rubric["target"]["reviewed_skill_md_sha256"]
    _write_pair(tree, elegance, rubric)
    assert _errors(tree) == ["pair-mismatch: target.reviewed_skill_md_sha256 differs between elegance and rubric"]


def test_finding_id_reused_across_rebinds_is_reported(tree):
    rebinds = [_entry(A, B, ids=["elegance:1"]), _entry(B, tree["current"], ids=["elegance:1"])]
    _write_pair(tree, *_rebound_pair(tree, rebinds, reviewed=A))
    (error,) = _errors(tree)
    assert "reuses finding elegance:1" in error


def test_same_finding_text_under_the_other_id_is_reported(tree):
    rebinds = [_entry(A, B, ids=["elegance:1"]), _entry(B, tree["current"], ids=["rubric:1"])]
    _write_pair(tree, *_rebound_pair(tree, rebinds, reviewed=A, rubric_negative=("[low]  A",)))
    (error,) = _errors(tree)
    assert "reuses finding rubric:1" in error


def test_both_ids_of_one_finding_in_one_rebind_are_allowed(tree):
    rebinds = [_entry(A, tree["current"], ids=["elegance:1", "rubric:1"])]
    _write_pair(tree, *_rebound_pair(tree, rebinds, reviewed=A, rubric_negative=("[low] A",)))
    assert _errors(tree) == []


def test_rebind_naming_a_missing_finding_is_reported(tree):
    _write_pair(tree, *_rebound_pair(tree, [_entry(A, tree["current"], ids=["rubric:2"])], reviewed=A))
    (error,) = _errors(tree)
    assert "does not name a negative_feedback entry" in error


# ---------- finding_locations ----------

@pytest.mark.parametrize("locations", [
    {"rubric:1": {"sections": ["手順"]}},       # 他方の verdict の id
    {"elegance:3": {"sections": ["手順"]}},     # negative_feedback の範囲外
    {"elegance:1": {"sections": []}},           # 節が空
    {"elegance:1": {"sections": ["  "]}},       # 空白だけの節
    {"elegance:1": ["手順"]},                   # 形が違う
])
def test_malformed_finding_locations_are_reported(tree, locations):
    elegance, rubric = _rebound_pair(tree, [], reviewed=tree["current"])
    elegance["finding_locations"] = locations
    _write_pair(tree, elegance, rubric)
    (error,) = _errors(tree)
    assert "finding_locations" in error


def test_valid_finding_locations_pass(tree):
    elegance, rubric = _rebound_pair(tree, [], reviewed=tree["current"])
    elegance["finding_locations"] = {"elegance:2": {"sections": ["手順"], "source_id": "F-0003"}}
    _write_pair(tree, elegance, rubric)
    assert _errors(tree) == []


# ---------- scoped re-review を手で作った記録 ----------

def _hand_made_scoped_pair(tree, sections):
    """範囲つき再レビューの記録と写しを、sync-content-review-sha.py を通さず手で作る。"""
    to_sha = tree["current"]
    review = {
        "kind": "scoped-content-review", "plugin": PLUGIN, "skill": SKILL,
        "from_sha": A, "to_sha": to_sha, "sections": sections,
        "verdicts": {"elegance": "PASS", "rubric": "PASS"}, "negative_feedback": [],
        "reviewer": "assign-skill-design-evaluator", "reviewed_at": "2026-11-14T00:00:00Z",
    }
    raw = (json.dumps(review, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    copy_dir = tree["dir"] / "scoped-reviews"
    copy_dir.mkdir()
    (copy_dir / f"{to_sha}.json").write_bytes(raw)
    entry = _entry(A, to_sha, ids=None)
    entry["scoped_review"] = {
        "sections": sections, "reviewer": review["reviewer"], "reviewed_at": review["reviewed_at"],
        "review_ref": f"scoped-reviews/{to_sha}.json", "review_sha256": hashlib.sha256(raw).hexdigest(),
    }
    _write_pair(tree, *_rebound_pair(tree, [entry], reviewed=A))


def test_hand_made_scoped_review_outside_the_contract_passes(tree):
    _hand_made_scoped_pair(tree, ["手順"])
    assert _errors(tree) == []


@pytest.mark.parametrize("section, contract", [
    ("入出力契約", "入出力契約"),
    ("Purpose & Output Contract", "Purpose & Output Contract"),
    ("Purpose & Output Contract > 出力", "Purpose & Output Contract"),
    ("手順 > 入出力契約", "入出力契約"),
])
def test_hand_made_scoped_review_of_the_contract_is_reported(tree, section, contract):
    # 独立レビューの再現: 節に「入出力契約」を名乗る scoped review を手で作ると rc0 で通った
    # (書く側の sync-content-review-sha.py は拒否する)。入出力契約の変更は全体の再レビューへ回す
    _hand_made_scoped_pair(tree, [section])
    errors = _errors(tree)
    assert len(errors) == 2  # elegance と rubric の両方
    for error in errors:
        assert error == (
            f"rebind-chain: sha_rebinds[1] scoped_review.sections {section!r} is inside the output contract"
            f" ({contract}); a contract change needs a full content review"
        )


# ---------- skill_dir_digest ----------

def test_reference_change_makes_the_verdict_stale_when_the_digest_is_recorded(tree):
    skill_dir = tree["md"].parent
    (skill_dir / "references").mkdir()
    guide = skill_dir / "references" / "guide.md"
    guide.write_text("レビューした版\n", encoding="utf-8")
    digest = LCR._skill_dir_digest(PLUGIN, SKILL)
    cur = tree["current"]
    _write_pair(
        tree,
        _verdict("elegance", cur, [], reviewed_skill_md_sha256=cur, skill_dir_digest=digest),
        _verdict("rubric", cur, [], reviewed_skill_md_sha256=cur, skill_dir_digest=digest),
    )
    assert _errors(tree) == []

    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "x.py").write_text("print(1)\n", encoding="utf-8")
    assert _errors(tree) == []  # scripts/ は digest の外 (コードは別の test が見る)

    guide.write_text("レビューしていない版\n", encoding="utf-8")
    errors = _errors(tree)
    assert len(errors) == 2 and all(err.startswith("stale-dir-digest:") for err in errors)


def test_verdict_without_a_digest_ignores_reference_changes(tree):
    cur = tree["current"]
    _write_pair(tree, _verdict("elegance", cur, []), _verdict("rubric", cur, []))
    (tree["md"].parent / "references").mkdir()
    (tree["md"].parent / "references" / "guide.md").write_text("x\n", encoding="utf-8")
    assert _errors(tree) == []


def test_changed_only_picks_up_reference_changes_only_for_verdicts_with_a_digest(tree, monkeypatch):
    cur = tree["current"]
    digest = LCR._skill_dir_digest(PLUGIN, SKILL)
    changed = {(PLUGIN, SKILL): {"references/guide.md"}}
    monkeypatch.setattr(LCR, "_git_changed_paths", lambda base: changed)

    _write_pair(tree, _verdict("elegance", cur, []), _verdict("rubric", cur, []))
    assert LCR._git_changed_skills("origin/main") == set()

    _write_pair(
        tree,
        _verdict("elegance", cur, [], skill_dir_digest=digest),
        _verdict("rubric", cur, [], skill_dir_digest=digest),
    )
    assert LCR._git_changed_skills("origin/main") == {(PLUGIN, SKILL)}

    changed[(PLUGIN, SKILL)] = {"scripts/x.py", "tests/test_x.py"}
    assert LCR._git_changed_skills("origin/main") == set()

    changed[(PLUGIN, SKILL)] = {"SKILL.md"}
    assert LCR._git_changed_skills("origin/main") == {(PLUGIN, SKILL)}


# ---------- --print-target ----------

def test_print_target_emits_the_target_for_a_new_verdict():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--print-target", "harness-creator/run-goal-seek"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    target = json.loads(proc.stdout)
    md = ROOT / "plugins" / "harness-creator" / "skills" / "run-goal-seek" / "SKILL.md"
    sha = hashlib.sha256(md.read_bytes()).hexdigest()
    assert target == {
        "plugin": "harness-creator",
        "skill": "run-goal-seek",
        "skill_md_sha256": sha,
        "reviewed_skill_md_sha256": sha,
        "skill_dir_digest": LCR.FC.content_review_dir_digest(md.parent),
    }


@pytest.mark.parametrize("spec", ["harness-creator", "harness-creator/no-such-skill", "/run-x"])
def test_print_target_rejects_unknown_skills(spec):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--print-target", spec], capture_output=True, text=True, cwd=ROOT
    )
    assert proc.returncode == 2


# ---------- 実在の記録 ----------

def _real_verdicts_with_rebinds():
    found = []
    for path in sorted((ROOT / "eval-log").glob("*/*/content-review/*-verdict.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("sha_rebinds"):
            found.append(pytest.param(path, data, id=path.relative_to(ROOT / "eval-log").as_posix()))
    return found


@pytest.mark.parametrize("path, data", _real_verdicts_with_rebinds())
def test_existing_rebind_records_pass_the_chain_check(path, data):
    assert LCR._check_rebind_chain(data["target"], data["sha_rebinds"]) is None


def test_there_are_existing_rebind_records_to_check():
    assert len(_real_verdicts_with_rebinds()) >= 6  # run-build-skill / run-skill-create / run-skill-elicit の 2 verdict ずつ

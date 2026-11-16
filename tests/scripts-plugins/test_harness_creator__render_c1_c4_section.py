"""run-skill-create の render-c1-c4-section.py が完了レポートの C1-C4 節を固定の文面で描画することを確かめる。

run-skill-create の OUT2 (完了レポートの C1-C4 は run-build-skill の初稿診断 receipt
から描画し、create 内で評価し直さず、receipt が無ければ未診断と明記する) の検証。
receipt (review.json / improvement-result.json / post-target-manifest.json /
improvement-validation.json) を tmp_path に組み立て、receipt あり (改善なし・改善あり)
・無し・壊れている・診断後に成果物が変わった、の各場合の出力を文字列そのもので固定する。
fixture が build 側の schema から外れていないことも jsonschema で確かめる。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-create" / "scripts" / "render-c1-c4-section.py"
BUILD_SCHEMAS = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill" / "schemas"

FP = "a" * 64
FP_OLD = "b" * 64
SKILL_REL = "plugins/demo/skills/run-demo"
RECEIPT_ROOT = "eval-log/demo/build/initial-draft-review"
HEAD = (
    "## build_evaluation_receipt (C1-C4)\n"
    "\n"
    "> run-build-skill の初稿診断 receipt から `render-c1-c4-section.py` が生成した節。"
    "run-skill-create では評価し直していない。\n"
    "\n"
)
UNDIAGNOSED = "- C1-C4: 未診断 (run-skill-create では評価していない)\n"

INITIAL_CONDITIONS = {
    "C1": {"verdict": "PASS", "summary": "手順と出力契約に矛盾は無い", "finding_refs": []},
    "C2": {"verdict": "PARTIAL", "summary": "失敗時の扱いが書かれていない", "finding_refs": ["IDR-001"]},
    "C3": {"verdict": "PASS", "summary": "用語は揃っている", "finding_refs": []},
    "C4": {"verdict": "FAIL", "summary": "参照先の script が\n  無い", "finding_refs": ["IDR-002"]},
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    elif isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _manifest(repo: Path, skill_rel: str = SKILL_REL) -> list[dict]:
    files = sorted(path for path in (repo / skill_rel).rglob("*") if path.is_file())
    return [
        {"path": path.relative_to(repo).as_posix(), "sha256": _sha(path.read_bytes()), "size": path.stat().st_size}
        for path in files
    ]


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _write(repo / SKILL_REL / "SKILL.md", "v1\n")
    _write(repo / SKILL_REL / "scripts" / "__pycache__" / "x.cpython-311.pyc", b"pyc-1")
    _write(repo / "plugins/demo/skills/run-other/SKILL.md", "other\n")
    return repo


def _review(repo: Path, fingerprint: str = FP, *, skill_rel: str = SKILL_REL, subject: str = "demo:run-demo",
            produced_at: str = "2026-11-01T00:00:00Z", runtime: str = "claude-code") -> dict:
    manifest = _manifest(repo, skill_rel)
    findings = [
        {
            "id": finding_id,
            "title": title,
            "description": title,
            "severity": severity,
            "affects_goal": True,
            "actionable": True,
            "recommendation": "直す",
            "location": {"path": f"{skill_rel}/SKILL.md", "line": 1},
            "remediation_paths": [f"{skill_rel}/SKILL.md"],
            "condition_signals": [condition],
        }
        for finding_id, title, severity, condition in (
            ("IDR-001", "失敗時の扱いが無い", "high", "C2"),
            ("IDR-002", "参照先が無い", "low", "C4"),
        )
    ]
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "subject": subject,
        "baseline_fingerprint_sha256": fingerprint,
        "review_claim_id": "IRC-" + "c" * 32,
        "launch_request_id": "IRL-" + "d" * 64,
        "contract_binding": {
            "target_manifest_sha256": _canonical(manifest),
            "method_catalog_sha256": "e" * 64,
            "method_catalog_version": "1",
            "prompt_sha256": "e" * 64,
            "review_schema_sha256": "e" * 64,
            "review_schema_version": 1,
        },
        "target_manifest": manifest,
        "evaluator": {"id": "elegant-initial-draft-evaluator", "context_count": 1, "runtime": runtime},
        "review_mode": "diagnostic-only",
        "edited_target": False,
        "thought_reset": {
            "performed": True,
            "physical_deletion_performed": False,
            "parent_history_used": False,
            "fresh_target_read": True,
            "attested_at": produced_at,
        },
        "evidence": [{"id": "EVD-001", "path": f"{skill_rel}/SKILL.md", "line": 1}],
        "method_observations": [
            {
                "method_id": f"method-{index}",
                "rationale": "観点",
                "observation": "観察",
                "evidence_refs": ["EVD-001"],
                "finding_refs": [],
            }
            for index in range(30)
        ],
        "findings": findings,
        "four_conditions": json.loads(json.dumps(INITIAL_CONDITIONS)),
        "recommended_level": "light",
        "summary": "初稿は使えるが C2/C4 に穴がある",
        "produced_at": produced_at,
    }


def _put_review(repo: Path, review: dict, fingerprint: str = FP) -> Path:
    return _write(repo / RECEIPT_ROOT / fingerprint / "review.json", review)


def _put_improvement(repo: Path, review_path: Path, review: dict) -> dict:
    """SKILL.md を v2 に直したことにし、Step 12.7-12.8 の receipt を置く。"""
    _write(repo / SKILL_REL / "SKILL.md", "v2\n")
    post = _manifest(repo)
    directory = review_path.parent
    _write(directory / "post-target-manifest.json", post)
    evidence = [{"path": f"{SKILL_REL}/SKILL.md", "line": 1, "sha256": post[0]["sha256"]}]
    result = {
        "schema_version": 1,
        "run_id": review["run_id"],
        "subject": review["subject"],
        "review_sha256": _sha(review_path.read_bytes()),
        "decision_sha256": "f" * 64,
        "baseline_target_manifest_sha256": _canonical(review["target_manifest"]),
        "post_target_manifest_sha256": _canonical(post),
        "selected_level": "light",
        "rounds_used": 1,
        "changed_paths": [f"{SKILL_REL}/SKILL.md"],
        "change_trace": [
            {
                "path": f"{SKILL_REL}/SKILL.md",
                "finding_ids": ["IDR-001", "IDR-002"],
                "summary": "失敗時の扱いと参照先を足した",
                "validation_refs": ["pytest"],
            }
        ],
        "finding_outcomes": {"resolved": ["IDR-001", "IDR-002"], "residual": [], "regressed": []},
        "four_conditions": {
            key: {"verdict": "PASS", "summary": f"{key} は満たした", "evidence_refs": evidence}
            for key in ("C1", "C2", "C3", "C4")
        },
        "completion_status": "complete",
        "next_stage": "draft",
        "next_profile": "incremental",
        "auto_promote_release": False,
        "auto_promote_exhaustive": False,
        "produced_at": "2026-11-02T00:00:00Z",
    }
    _write(directory / "improvement-result.json", result)
    validation = {
        "schema_version": 1,
        "status": "pass",
        "run_id": review["run_id"],
        "subject": review["subject"],
        "completion_status": "complete",
        "selected_finding_ids": ["IDR-001", "IDR-002"],
        "changed_paths": [f"{SKILL_REL}/SKILL.md"],
        "rounds_used": 1,
        "max_rounds": 1,
        "next_stage": "draft",
        "next_profile": "incremental",
        "auto_promote_release": False,
        "auto_promote_exhaustive": False,
    }
    _write(directory / "improvement-validation.json", validation)
    return result


def _run(repo: Path, *args: str, skill: str = "run-demo") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--plugin", "demo", "--skill", skill, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _render(repo: Path, *args: str) -> str:
    proc = _run(repo, *args)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


# --- fixture が build 側の schema に合っている ---

def test_fixtures_match_build_schemas(tmp_path):
    repo = _repo(tmp_path)
    review = _review(repo)
    review_path = _put_review(repo, review)
    result = _put_improvement(repo, review_path, review)
    jsonschema.validate(review, json.loads((BUILD_SCHEMAS / "initial-draft-review.schema.json").read_text()))
    jsonschema.validate(result, json.loads((BUILD_SCHEMAS / "improvement-result.schema.json").read_text()))


# --- receipt あり ---

def test_receipt_without_improvement_renders_initial_c1_c4(tmp_path):
    repo = _repo(tmp_path)
    _put_review(repo, _review(repo))
    assert _render(repo) == HEAD + (
        "- 状態: 診断済み (改善なし)\n"
        f"- receipt: {RECEIPT_ROOT}/{FP}/review.json\n"
        "- subject: demo:run-demo (run_id run-1)\n"
        "- 診断者: elegant-initial-draft-evaluator (claude-code)\n"
        "- 推奨 level: light\n"
        "- 所見: 2 件 (critical 0 / high 1 / medium 0 / low 1)\n"
        "- C1 矛盾なし: PASS — 手順と出力契約に矛盾は無い (所見: なし)\n"
        "- C2 漏れなし: PARTIAL — 失敗時の扱いが書かれていない (所見: IDR-001)\n"
        "- C3 整合性あり: PASS — 用語は揃っている (所見: なし)\n"
        "- C4 依存関係整合: FAIL — 参照先の script が 無い (所見: IDR-002)\n"
    )


def test_receipt_with_improvement_renders_before_and_after(tmp_path):
    repo = _repo(tmp_path)
    review = _review(repo, runtime="codex")
    _put_improvement(repo, _put_review(repo, review), review)
    directory = f"{RECEIPT_ROOT}/{FP}"
    assert _render(repo) == HEAD + (
        "- 状態: 診断済み・改善済み\n"
        f"- receipt: {directory}/review.json, {directory}/improvement-result.json, "
        f"{directory}/improvement-validation.json\n"
        "- subject: demo:run-demo (run_id run-1)\n"
        "- 診断者: elegant-initial-draft-evaluator (codex)\n"
        "- 推奨 level: light\n"
        "- 所見: 2 件 (critical 0 / high 1 / medium 0 / low 1)\n"
        "- 改善: level light、選んだ所見 IDR-001, IDR-002、round 1/1、completion_status complete\n"
        "- 所見の結果: resolved 2 / residual 0 / regressed 0\n"
        "- C1 矛盾なし: PASS → PASS\n"
        "  - 初稿: 手順と出力契約に矛盾は無い (所見: なし)\n"
        "  - 改善後: C1 は満たした\n"
        "- C2 漏れなし: PARTIAL → PASS\n"
        "  - 初稿: 失敗時の扱いが書かれていない (所見: IDR-001)\n"
        "  - 改善後: C2 は満たした\n"
        "- C3 整合性あり: PASS → PASS\n"
        "  - 初稿: 用語は揃っている (所見: なし)\n"
        "  - 改善後: C3 は満たした\n"
        "- C4 依存関係整合: FAIL → PASS\n"
        "  - 初稿: 参照先の script が 無い (所見: IDR-002)\n"
        "  - 改善後: C4 は満たした\n"
    )


def test_pycache_changes_do_not_make_receipt_stale(tmp_path):
    repo = _repo(tmp_path)
    _put_review(repo, _review(repo))
    _write(repo / SKILL_REL / "scripts" / "__pycache__" / "x.cpython-311.pyc", b"pyc-2")
    assert "- 状態: 診断済み (改善なし)\n" in _render(repo)


def test_latest_fresh_receipt_wins_and_unused_receipts_are_noted(tmp_path):
    repo = _repo(tmp_path)
    _put_review(repo, _review(repo, FP_OLD, produced_at="2026-10-01T00:00:00Z"), FP_OLD)
    _put_review(repo, _review(repo, FP, produced_at="2026-11-01T00:00:00Z"), FP)
    broken = "c" * 64
    _put_review(repo, {**_review(repo, broken), "four_conditions": {}}, broken)
    out = _render(repo)
    assert f"- receipt: {RECEIPT_ROOT}/{FP}/review.json\n" in out
    assert "- 注記: 今の成果物と一致する receipt が 2 件あり、produced_at が最新のものを使った\n" in out
    assert "- 注記: 使わなかった receipt (壊れている 1 件 / 診断後に成果物が変わった 0 件)\n" in out


def test_explicit_fingerprint_selects_that_receipt(tmp_path):
    repo = _repo(tmp_path)
    _put_review(repo, _review(repo, FP_OLD, produced_at="2026-10-01T00:00:00Z"), FP_OLD)
    _put_review(repo, _review(repo, FP), FP)
    assert f"- receipt: {RECEIPT_ROOT}/{FP_OLD}/review.json\n" in _render(repo, "--fingerprint", FP_OLD)


# --- receipt 無し ---

def test_no_receipt_is_undiagnosed(tmp_path):
    repo = _repo(tmp_path)
    assert _render(repo) == HEAD + (
        "- 状態: 未診断\n"
        "- 理由: 初稿診断 receipt が無い。run-build-skill の現状で試すか診断するかの選択で accept-as-is を選んだか、診断を行っていない\n"
        f"- 探した場所: {RECEIPT_ROOT}/\n"
        + UNDIAGNOSED
    )


def test_no_receipt_with_accept_as_is_choice_names_the_choice(tmp_path):
    repo = _repo(tmp_path)
    _write(
        repo / "eval-log/demo/build/diagnostic-choice.json",
        {"subject": "demo:run-demo", "artifact_path": f"{SKILL_REL}/SKILL.md", "selected_level": "accept-as-is"},
    )
    assert _render(repo) == HEAD + (
        "- 状態: 未診断\n"
        "- 理由: 初稿診断 receipt が無い。run-build-skill の現状で試すか診断するかの選択で accept-as-is が選ばれている\n"
        f"- 探した場所: {RECEIPT_ROOT}/\n"
        "- 現状で試すか診断するかの選択: accept-as-is (eval-log/demo/build/diagnostic-choice.json)\n"
        + UNDIAGNOSED
    )


def test_diagnosis_chosen_but_receipt_missing_is_called_out(tmp_path):
    repo = _repo(tmp_path)
    _write(
        repo / "eval-log/demo/build/diagnostic-choice.json",
        {"subject": "demo:run-demo", "artifact_path": f"{SKILL_REL}/SKILL.md", "selected_level": "diagnose"},
    )
    assert "- 理由: 現状で試すか診断するかの選択で diagnose が選ばれているが、初稿診断 receipt が無い\n" in _render(repo)


def test_receipt_of_another_skill_is_not_used(tmp_path):
    repo = _repo(tmp_path)
    other = "plugins/demo/skills/run-other"
    _put_review(repo, _review(repo, skill_rel=other, subject="demo:run-other"))
    out = _render(repo)
    assert "- 状態: 未診断\n" in out
    assert "- 理由: 初稿診断 receipt が無い。" in out


def test_missing_explicit_fingerprint_is_undiagnosed(tmp_path):
    repo = _repo(tmp_path)
    assert f"- 理由: 指定した fingerprint の receipt が無い ({RECEIPT_ROOT}/{FP}/)\n" in _render(repo, "--fingerprint", FP)


# --- receipt が壊れている ---

def test_unparseable_review_with_fingerprint_is_broken(tmp_path):
    repo = _repo(tmp_path)
    _write(repo / RECEIPT_ROOT / FP / "review.json", "{not json")
    assert _render(repo, "--fingerprint", FP) == HEAD + (
        "- 状態: 未診断\n"
        "- 理由: receipt が壊れている。review.json が JSON として読めない (JSONDecodeError)\n"
        f"- receipt: {RECEIPT_ROOT}/{FP}/\n"
        + UNDIAGNOSED
    )


def test_unparseable_review_without_fingerprint_cannot_be_attributed(tmp_path):
    repo = _repo(tmp_path)
    _write(repo / RECEIPT_ROOT / FP / "review.json", "{not json")
    assert _render(repo) == HEAD + (
        "- 状態: 未診断\n"
        "- 理由: receipt が壊れていて、この skill のものか判定できない。review.json が JSON として読めない (JSONDecodeError)\n"
        f"- receipt: {RECEIPT_ROOT}/{FP}/\n"
        + UNDIAGNOSED
    )


def _drop_c3(review: dict) -> None:
    del review["four_conditions"]["C3"]


def _bad_verdict(review: dict) -> None:
    review["four_conditions"]["C1"]["verdict"] = "OK"


def _other_fingerprint(review: dict) -> None:
    review["baseline_fingerprint_sha256"] = FP_OLD


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (_drop_c3, "review.json の four_conditions.C3 が無い"),
        (_bad_verdict, "review.json の four_conditions.C1.verdict が PASS/FAIL/PARTIAL ではない"),
        (_other_fingerprint, "review.json の baseline_fingerprint_sha256 がディレクトリ名と一致しない"),
    ],
)
def test_broken_review_is_undiagnosed_with_one_line_reason(tmp_path, mutate, reason):
    repo = _repo(tmp_path)
    review = _review(repo)
    mutate(review)
    _put_review(repo, review)
    assert _render(repo) == HEAD + (
        "- 状態: 未診断\n"
        f"- 理由: receipt が壊れている。{reason}\n"
        f"- receipt: {RECEIPT_ROOT}/{FP}/\n"
        + UNDIAGNOSED
    )


def _edit_json(path: Path, **changes) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.update(changes)
    _write(path, doc)


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        (
            lambda d: _edit_json(d / "improvement-validation.json", status="fail"),
            "improvement-validation.json の status が pass ではない",
        ),
        (
            lambda d: _edit_json(d / "improvement-result.json", review_sha256="0" * 64),
            "improvement-result.json の review_sha256 が review.json と一致しない",
        ),
        (
            lambda d: (d / "improvement-validation.json").unlink(),
            "improvement-result.json はあるが improvement-validation.json が無い (Step 12.8 の検証を通っていない)",
        ),
        (
            lambda d: (d / "improvement-result.json").unlink(),
            "improvement-validation.json はあるが improvement-result.json が無い",
        ),
        (
            lambda d: _write(d / "post-target-manifest.json", []),
            "post-target-manifest.json が path の配列ではない",
        ),
        (
            lambda d: _edit_json(d / "improvement-validation.json", rounds_used=2),
            "improvement-result.json の rounds_used が improvement-validation.json と一致しない",
        ),
    ],
)
def test_broken_improvement_receipt_is_undiagnosed_with_one_line_reason(tmp_path, damage, reason):
    repo = _repo(tmp_path)
    review = _review(repo)
    review_path = _put_review(repo, review)
    _put_improvement(repo, review_path, review)
    damage(review_path.parent)
    assert _render(repo) == HEAD + (
        "- 状態: 未診断\n"
        f"- 理由: receipt が壊れている。{reason}\n"
        f"- receipt: {RECEIPT_ROOT}/{FP}/\n"
        + UNDIAGNOSED
    )


# --- 診断後に成果物が変わった ---

def test_receipt_older_than_current_artifact_is_undiagnosed(tmp_path):
    repo = _repo(tmp_path)
    _put_review(repo, _review(repo))
    _write(repo / SKILL_REL / "SKILL.md", "v2 (Gate 2 で差し戻して build し直した)\n")
    assert _render(repo) == HEAD + (
        "- 状態: 未診断\n"
        f"- 理由: 診断後に成果物が変わっている (1 件。例: {SKILL_REL}/SKILL.md)。この receipt は今の成果物の診断ではない\n"
        f"- receipt: {RECEIPT_ROOT}/{FP}/\n"
        + UNDIAGNOSED
    )


def test_improved_receipt_is_checked_against_post_manifest(tmp_path):
    repo = _repo(tmp_path)
    review = _review(repo)
    _put_improvement(repo, _put_review(repo, review), review)
    _write(repo / SKILL_REL / "SKILL.md", "v3\n")
    assert "- 理由: 診断後に成果物が変わっている (1 件。" in _render(repo)


def test_file_added_after_diagnosis_makes_receipt_stale(tmp_path):
    """manifest に載ったファイルが変わらなくても、診断後に足したファイルがあれば今の成果物の診断ではない。"""
    repo = _repo(tmp_path)
    _put_review(repo, _review(repo))
    _write(repo / SKILL_REL / "scripts" / "new-tool.py", "print('added after review')\n")
    assert _render(repo) == HEAD + (
        "- 状態: 未診断\n"
        f"- 理由: 診断後に成果物が変わっている (1 件。例: {SKILL_REL}/scripts/new-tool.py (診断後に追加))。"
        "この receipt は今の成果物の診断ではない\n"
        f"- receipt: {RECEIPT_ROOT}/{FP}/\n"
        + UNDIAGNOSED
    )


def test_file_added_after_improvement_makes_receipt_stale(tmp_path):
    repo = _repo(tmp_path)
    review = _review(repo)
    _put_improvement(repo, _put_review(repo, review), review)
    _write(repo / SKILL_REL / "references" / "extra.md", "added\n")
    assert f"例: {SKILL_REL}/references/extra.md (診断後に追加))" in _render(repo)


def test_subject_must_match_even_if_manifest_covers_the_skill(tmp_path):
    """target_manifest に自 skill の path があっても、subject が別 skill の receipt は使わない。"""
    repo = _repo(tmp_path)
    _put_review(repo, _review(repo, subject="demo:run-other"))
    out = _render(repo)
    assert "- 状態: 未診断\n" in out
    assert "- 理由: 初稿診断 receipt が無い。" in out
    proc = _run(repo, "--fingerprint", FP)
    assert f"- 理由: receipt が壊れている。review.json が {SKILL_REL} の receipt ではない\n" in proc.stdout


def test_produced_at_is_compared_as_time_not_text(tmp_path):
    """"18:00+09:00" (= 09:00Z) は "10:00Z" より古い。文字列で比べると逆になる。"""
    repo = _repo(tmp_path)
    newer = _review(repo, FP, produced_at="2026-11-01T10:00:00Z")
    newer["run_id"] = "run-new"
    older = _review(repo, FP_OLD, produced_at="2026-11-01T18:00:00+09:00")
    older["run_id"] = "run-old"
    _put_review(repo, newer, FP)
    _put_review(repo, older, FP_OLD)
    assert "- subject: demo:run-demo (run_id run-new)\n" in _render(repo)


def _inject_heading(review: dict) -> None:
    review["four_conditions"]["C1"]["finding_refs"] = ["IDR-001\n## 偽の見出し\n- C2 漏れなし: PASS"]


def _dangling_ref(review: dict) -> None:
    review["four_conditions"]["C1"]["finding_refs"] = ["IDR-999"]


def _absolute_manifest_path(review: dict) -> None:
    review["target_manifest"].append({"path": "/etc/hosts", "sha256": "0" * 64, "size": 1})


def _dotdot_manifest_path(review: dict) -> None:
    review["target_manifest"].append({"path": SKILL_REL + "/../../../../../outside.txt", "sha256": "0" * 64, "size": 1})


def _bad_finding_id(review: dict) -> None:
    review["findings"][0]["id"] = "IDR-1\n## x"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (_inject_heading, "review.json の four_conditions.C1.finding_refs に findings に無い ID がある"),
        (_dangling_ref, "review.json の four_conditions.C1.finding_refs に findings に無い ID がある"),
        (_absolute_manifest_path, "review.json の target_manifest に repo 外を指す path がある"),
        (_dotdot_manifest_path, "review.json の target_manifest に repo 外を指す path がある"),
        (_bad_finding_id, "review.json の findings に id か severity が不正なものがある"),
    ],
)
def test_receipt_that_could_forge_lines_or_read_outside_is_broken(tmp_path, mutate, reason):
    repo = _repo(tmp_path)
    review = _review(repo)
    mutate(review)
    _put_review(repo, review)
    out = _render(repo)
    assert out == HEAD + (
        "- 状態: 未診断\n"
        f"- 理由: receipt が壊れている。{reason}\n"
        f"- receipt: {RECEIPT_ROOT}/{FP}/\n"
        + UNDIAGNOSED
    )
    assert "偽の見出し" not in out


def test_manifest_entry_through_symlink_to_outside_is_not_fresh(tmp_path):
    repo = _repo(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("v1\n", encoding="utf-8")
    (repo / SKILL_REL / "SKILL.md").unlink()
    (repo / SKILL_REL / "SKILL.md").symlink_to(outside)
    _put_review(repo, _review(repo))
    assert f"- 理由: 診断後に成果物が変わっている (1 件。例: {SKILL_REL}/SKILL.md)" in _render(repo)


def test_unreadable_receipt_root_exits_2_without_traceback(tmp_path):
    repo = _repo(tmp_path)
    _put_review(repo, _review(repo))
    root = repo / RECEIPT_ROOT
    root.chmod(0)
    try:
        proc = _run(repo)
    finally:
        root.chmod(0o755)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "Traceback" not in proc.stderr
    assert "receipt の置き場か skill ディレクトリを読めない (PermissionError" in proc.stderr


# --- 引数の誤り ---

@pytest.mark.parametrize(
    "args",
    [
        ("--fingerprint", "not-a-sha"),
        ("--plugin", "../demo"),
    ],
)
def test_invalid_arguments_exit_2(tmp_path, args):
    repo = _repo(tmp_path)
    proc = _run(repo, *args)
    assert proc.returncode == 2
    assert proc.stdout == ""


def test_missing_skill_directory_exits_2(tmp_path):
    repo = _repo(tmp_path)
    proc = _run(repo, skill="run-missing")
    assert proc.returncode == 2
    assert "skill ディレクトリが無い" in proc.stderr
